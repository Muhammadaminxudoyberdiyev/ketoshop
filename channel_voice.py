"""Kanal postlari — jonli, norasmiy va har xil uzunlikda (egasi, 2026-11-15:
"faqat standart matnlarni yuboraverma, kanalda ham juda rasmiy postlar
ko'payib ketti, postlar kaltaroq va norasmiyroq bo'lsin, va uzunligi xar xil
bo'lsin zerikarli bo'lmasin").

Tayyor shablon (kunlik kontent, «Keto fakt», retsept, kun mahsuloti) kanalga
chiqishdan oldin GPT orqali qayta yoziladi: do'stona, «biz» nomidan, har safar
tasodifiy uzunlikda — qisqa (ko'pincha), o'rta yoki uzunroq. Faktlar shablondan:

  * havolalar (href), @username va t.me havolalari — hammasi saqlanadi;
  * javobda shablonda yo'q birorta raqam bo'lmasligi kerak (narx, gramm,
    foiz o'ylab topilmaydi; qisqartirishda tushib qolishi mumkin);
  * faqat Telegram HTML teglari, juft-juft; spoiler bo'lsa — qoladi;
  * shablon yozuvida (kirill bo'lsa — kirill);
  * Telegram chegarasiga sig'adi (imzo va pastki qatorlarga joy qoladi).

Shulardan biri buzilsa yoki AI javob bermasa — shablonning o'zi chiqadi.
Ro'yxatli postlar (TOP-10, eng ko'p sotilganlar, oylik hisobot) va e'lonlar
qayta yozilmaydi: ulardagi raqamlar muhim.

Boshqaruv: /kanal_ovoz (holat) · /kanal_ovoz on|off · /kanal_ovoz test
(navbatdagi kontent postini shablon va qayta yozilgan holda ko'rsatadi,
kanalga hech narsa chiqmaydi).
"""
from __future__ import annotations

import html
import json
import logging
import random
import re
from html.parser import HTMLParser

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)
router = Router(name="channel_voice")

SETTING = "channel_voice"
USAGE_TAG = " · kanal"
MARGIN = 220                        # imzo, manzil, chegirma qatori va havola uchun joy
LENGTHS = [                         # (nomi, oralig'i belgida, ehtimoli)
    ("qisqa", (90, 280), 45),
    ("o'rta", (280, 600), 40),
    ("uzun", (600, 950), 15),
]
ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "a", "code", "pre",
                "blockquote", "tg-spoiler", "span"}

RULES = """Sen Keto shop'ning Telegram kanali uchun post yozasan (keto, PP va glyutensiz mahsulotlar
do'koni). Senga tayyor post (SHABLON) beriladi — uni JONLI, NORASMIY qilib qayta yoz.

OHANG: do'stona, samimiy, xuddi tanish odam kanalga yozgandek — «biz» nomidan (Keto shop jamoasi).
Rasmiy, idoraviy gaplar yo'q («hurmatli mijozlar», «ma'lum qilamiz», «diqqatingizga» va hokazo).
Qisqa jumlalar, oddiy so'zlar, o'rinli 1–3 ta emoji. Har safar boshqacha boshla — «Assalomu alaykum»
bilan boshlama. Ozgina hazil yoki savol mumkin, lekin majburiy emas.

UZUNLIK: aytilgan oraliqda (belgilar soni) yoz. Qisqa post — eng asosiy fikr, ortiqcha tafsilotsiz.

FAKTLAR:
- Faqat SHABLONdagi faktlar. Yangi raqam, narx, foiz, gramm, muddat yoki va'da qo'shma.
- Shablondagi barcha havolalar (<a href="..."> va @username) javobda AYNAN shunday qolsin.
- Tibbiy va'da yo'q («davolaydi», «qandni tushiradi» kabi).
- Shablon qaysi tilda va yozuvda bo'lsa (o'zbek kirill / o'zbek lotin / rus) — o'shanda yoz.
- Faqat Telegram HTML teglari: <b>, <i>, <u>, <s>, <a href>, <code>, <blockquote>, <tg-spoiler>.
  Shablonda <tg-spoiler> bo'lsa — javobda ham qolsin (javobni yashiradi).
- Imzo va do'kon manzilini yozma — o'zimiz qo'shamiz."""

SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}},
          "required": ["text"], "additionalProperties": False}

_HREF = re.compile(r'href="([^"]+)"')
_HANDLE = re.compile(r"(?<![\w/])@[A-Za-z][A-Za-z0-9_]{3,31}")
_TME = re.compile(r"t\.me/[A-Za-z0-9_/?=&.-]+")
_NUMBER = re.compile(r"\d+(?:[ .,]\d{3})*(?:[.,]\d+)?")


def _numbers(text: str) -> set[str]:
    plain = re.sub(r"<[^>]+>", " ", text)
    return {re.sub(r"[ .,]", "", n) for n in _NUMBER.findall(plain)}


def _visible(text: str) -> int:
    from channel_signature import _visible_length
    return _visible_length(text)


class _TagCheck(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ok = [], True

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            self.ok = False
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.ok = False
        else:
            self.stack.pop()


def _tags_ok(text: str) -> bool:
    p = _TagCheck()
    try:
        p.feed(text)
        p.close()
    except Exception:
        return False
    return p.ok and not p.stack


def problems(original: str, new: str, limit: int) -> list[str]:
    """Nima uchun qayta yozilgan matn yaramaydi — bo'sh ro'yxat: yaraydi."""
    out = []
    if not new or not new.strip():
        return ["bo'sh"]
    if _visible(new) > limit - MARGIN:
        out.append("uzun")
    for href in _HREF.findall(original):
        if f'href="{href}"' not in new:
            out.append(f"havola yo'qoldi: {href[:40]}")
    for handle in set(_HANDLE.findall(original)):
        if handle not in new:
            out.append(f"{handle} yo'qoldi")
    for link in set(_TME.findall(re.sub(r'href="[^"]+"', "", original))):
        if link not in new:
            out.append(f"{link} yo'qoldi")
    invented = _numbers(new) - _numbers(original)
    if invented:
        out.append("yangi raqam: " + ", ".join(sorted(invented)[:5]))
    if not _tags_ok(new):
        out.append("HTML teglari")
    if "<tg-spoiler>" in original and "<tg-spoiler>" not in new:
        out.append("spoiler yo'qoldi")
    try:
        from comment_ai import is_cyrillic
        if is_cyrillic(_words(original)) != is_cyrillic(_words(new)):
            out.append("yozuv boshqa")
    except Exception:
        pass
    return out


def _words(text: str) -> str:
    """Faqat o'qiladigan so'zlar — teglar, havolalar va @username'larsiz (yozuvni aniqlash uchun)."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+|t\.me/\S+", " ", text)
    return _HANDLE.sub(" ", text)


def pick_length(original: str, limit: int, rng=random) -> tuple[str, int, int]:
    name, (lo, hi), _ = rng.choices(LENGTHS, weights=[w for *_, w in LENGTHS])[0]
    cap = max(80, min(limit - MARGIN, _visible(original)))
    hi = min(hi, cap)
    lo = min(lo, max(60, hi - 60))
    return name, lo, hi


async def enabled() -> bool:
    try:
        import ai_sales
        values = await ai_sales._load_settings()
        return str(values.get(SETTING, "1")) != "0"
    except Exception:
        return True


async def _ask(original: str, lo: int, hi: int) -> str | None:
    import comment_ai
    key = await comment_ai._openai_key()
    if not key:
        return None
    import ai_provider
    import openai
    model = comment_ai.openai_model()
    client = openai.AsyncOpenAI(api_key=key, timeout=60.0, max_retries=1)
    user = f"UZUNLIK: {lo}–{hi} belgi.\n\nSHABLON:\n{original}"
    resp = await client.responses.create(
        model=model, instructions=RULES, input=[{"role": "user", "content": [{"type": "input_text", "text": user}]}],
        reasoning={"effort": "low"}, max_output_tokens=1500,
        text={"format": {"type": "json_schema", "name": "kanal_post", "schema": SCHEMA, "strict": True}})
    try:
        import database
        usage = ai_provider._openai_usage(getattr(resp, "usage", None))
        await database.record_ai_usage(model + USAGE_TAG, "openai", usage.input, usage.cached, usage.output,
                                       ai_provider.estimate_cost(model, usage.input, usage.cached, usage.output))
    except Exception:
        logger.warning("channel voice usage not recorded", exc_info=True)
    if getattr(resp, "status", "completed") == "incomplete":
        return None
    try:
        return (json.loads(getattr(resp, "output_text", "") or "{}").get("text") or "").strip() or None
    except ValueError:
        return None


async def rewrite(original: str, kind: str, limit: int = 4096) -> str:
    """Kanalga chiqadigan matn: jonli qayta yozilgani yoki (biror shart
    buzilsa) shablonning o'zi. Hech qachon xato tashlamaydi."""
    if not original or not await enabled():
        return original
    name, lo, hi = pick_length(original, limit)
    try:
        new = await _ask(original, lo, hi)
    except Exception:
        logger.warning("channel voice (%s): AI failed — template posted", kind, exc_info=True)
        return original
    issues = problems(original, new or "", limit)
    if issues:
        logger.info("channel voice (%s, %s): template kept — %s", kind, name, "; ".join(issues))
        return original
    logger.info("channel voice (%s): %s, %d → %d chars", kind, name, _visible(original), _visible(new))
    return new


# ──────────────────────────────── /kanal_ovoz ───────────────────────────────

@router.message(Command("kanal_ovoz"))
async def cmd_channel_voice(message: Message):
    import ai_sales
    if message.from_user.id not in ai_sales.ADMIN_IDS:
        return
    parts = (message.text or "").split()
    arg = parts[1].lower() if len(parts) > 1 else ""
    if arg in ("on", "off"):
        await ai_sales.set_setting(SETTING, "1" if arg == "on" else "0", message.from_user.id)
        ai_sales._settings["at"] = float("-inf")
    if arg == "test":
        import channel_posts
        import channel_posts_content as content
        slug = random.choice(content.ORDER)
        original = channel_posts.build_text(slug)
        name, lo, hi = pick_length(original, 4096)
        try:
            new = await _ask(original, lo, hi)
        except Exception as exc:
            new, issues = None, [f"AI xatosi: {exc}"]
        else:
            issues = problems(original, new or "", 4096)
        verdict = "✅ kanalga shu chiqardi" if not issues else "⚠️ shablon chiqardi: " + "; ".join(issues)
        await message.answer(f"🧪 <b>Kanal ovozi — sinov</b> ({html.escape(slug)}, {name} {lo}–{hi})\n\n"
                             f"<b>Shablon:</b>\n{original}", parse_mode="HTML", disable_web_page_preview=True)
        await message.answer(f"<b>Qayta yozilgan:</b>\n{new or '—'}\n\n{html.escape(verdict)}",
                             parse_mode="HTML" if new and not issues else None, disable_web_page_preview=True)
        return
    on = await enabled()
    await message.answer(
        f"🗣 <b>Kanal ovozi</b>: {'yoqilgan ✅' if on else 'o‘chiq ⏸'}\n\n"
        "Kunlik kontent, «Keto fakt», retsept va kun mahsuloti posti kanalga chiqishdan oldin "
        "jonli, norasmiy va har xil uzunlikda qayta yoziladi; havola, raqam yoki HTML buzilsa — "
        "shablonning o'zi chiqadi.\n\n"
        "<code>/kanal_ovoz off</code> — o'chirish · <code>/kanal_ovoz on</code> — yoqish · "
        "<code>/kanal_ovoz test</code> — sinov (kanalga chiqmaydi)", parse_mode="HTML")
