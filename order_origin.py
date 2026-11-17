"""
🧭 Buyurtma qayerdan keldi (owner, 2026-11-17: "botda buyurtma qayerdan
qilinganini ham ko'rsatib tur yangi buyurtma xabarida: saytdanmi, botdanmi,
ai bilanmi, instagram yoki boshqa joydan ... bu biz buyurtmalar qayerdan ko'p
bo'layotganini bilishimiz uchun kerak"; "shuni ajratib saqla, saytdan,
ilovadan yoki botdan").

Every bot / Mini App / Android-app order gets one `orders.origin` record
(JSON text), written once when the admins are told about the order:

  placed — where the buyer pressed «buyurtma berish»:
           'bot' (the bot's own checkout), 'webapp' (the Mini App, «sayt»),
           'app' (the Android app, app_auth.py).
  ai     — the buyer talked to the AI seller (bot, site «Yordamchi» or the
           channel's group) in the AI_WINDOW before ordering: the channel.
  touch  — how the buyer reached us, most specific first:
           a tracked shop link opened in the last TOUCH_DAYS (shop_links.py;
           ?startapp=instagram is the one sent in Instagram comments and
           Direct), else the buyer's sign-up source: an ad link (ad_sources.py,
           fb_/ig_), a blogger's link (bloggers.py) or a friend's invite.

The new-order card and every later status card show it in one line
(🧭 Qayerdan: ...). /buyurtma_manba counts it for the last 7 / 30 days.
Nothing here may ever stop an order or its card: every lookup is guarded.
"""
from __future__ import annotations

import html
import json
import logging
from collections import Counter

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import database
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()

AI_WINDOW_HOURS = 48
TOUCH_DAYS = 30
INSTAGRAM_CODE = "instagram"          # shop_links code used in Instagram comments / Direct
PLACES = ("bot", "webapp", "app")
PERIODS = {"7": 7, "30": 30}

_TXT = {
    "uz": {
        "head": "🧭 Qayerdan:",
        "bot": "💬 Botdan", "webapp": "🌐 Saytdan", "app": "📱 Ilovadan",
        "ai": "🤖 AI bilan gaplashgan ({where})",
        "ai_where": {"bot": "botda", "site": "saytda", "group": "guruhda"},
        "instagram": "📸 Instagram (izoh / Direct havolasi)",
        "link": "🔗 Havola: {name}",
        "ad_ig": "📣 Instagram reklamasi ({src})",
        "ad_fb": "📣 Facebook reklamasi ({src})",
        "ad": "📣 Reklama ({src})",
        "blogger": "🎤 Bloger: {name}",
        "referral": "👥 Do'st taklifi",
    },
    "ru": {
        "head": "🧭 Откуда:",
        "bot": "💬 Из бота", "webapp": "🌐 С сайта", "app": "📱 Из приложения",
        "ai": "🤖 Общался с ИИ ({where})",
        "ai_where": {"bot": "в боте", "site": "на сайте", "group": "в группе"},
        "instagram": "📸 Instagram (ссылка из комментария / Direct)",
        "link": "🔗 Ссылка: {name}",
        "ad_ig": "📣 Реклама в Instagram ({src})",
        "ad_fb": "📣 Реклама в Facebook ({src})",
        "ad": "📣 Реклама ({src})",
        "blogger": "🎤 Блогер: {name}",
        "referral": "👥 Приглашение друга",
    },
}

_ready = False


async def ensure() -> None:
    global _ready
    if _ready or database.pool is None:
        return
    async with database.pool.acquire() as conn:
        await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS origin TEXT")
    _ready = True


def _esc(v) -> str:
    return html.escape(str(v or ""), quote=False)


def place_of(request) -> str:
    """Mini App or Android app — the app's requests carry a device session."""
    try:
        return "app" if request.get("app_session") else "webapp"
    except Exception:
        return "webapp"


# ─────────────────────────────── detection ───────────────────────────────

async def _ai_channel(conn, user_id: int) -> str | None:
    try:
        return await conn.fetchval(
            """SELECT channel FROM ai_conversations
               WHERE user_id = $1
                 AND last_at >= (NOW() AT TIME ZONE 'UTC') - make_interval(hours => $2::int)
               ORDER BY last_at DESC LIMIT 1""",
            int(user_id), AI_WINDOW_HOURS)
    except Exception:
        logger.debug("ai_conversations lookup failed", exc_info=True)
        return None


async def _touch(conn, user_id: int) -> dict | None:
    uid = int(user_id)
    try:
        row = await conn.fetchrow(
            """SELECT o.code, l.name FROM shop_link_opens o
               LEFT JOIN shop_links l ON l.code = o.code
               WHERE o.user_id = $1
                 AND o.opened_at >= LOCALTIMESTAMP - make_interval(days => $2::int)
               ORDER BY o.opened_at DESC LIMIT 1""",
            uid, TOUCH_DAYS)
        if row:
            if row["code"] == INSTAGRAM_CODE:
                return {"kind": "instagram"}
            return {"kind": "link", "code": row["code"], "name": row["name"] or row["code"]}
    except Exception:
        logger.debug("shop link lookup failed", exc_info=True)
    try:
        src = await conn.fetchval("SELECT source FROM ad_referrals WHERE user_id = $1", uid)
        if src:
            return {"kind": "ad", "source": src}
    except Exception:
        logger.debug("ad referral lookup failed", exc_info=True)
    try:
        name = await conn.fetchval(
            """SELECT b.name FROM blogger_referrals r JOIN bloggers b ON b.id = r.blogger_id
               WHERE r.user_id = $1""", uid)
        if name:
            return {"kind": "blogger", "name": name}
    except Exception:
        logger.debug("blogger referral lookup failed", exc_info=True)
    try:
        if await conn.fetchval("SELECT 1 FROM referrals WHERE referred_user_id = $1", uid):
            return {"kind": "referral"}
    except Exception:
        logger.debug("referral lookup failed", exc_info=True)
    return None


async def detect(user_id: int | None, placed: str) -> dict:
    origin: dict = {"placed": placed if placed in PLACES else "bot"}
    if not user_id or database.pool is None:
        return origin
    async with database.pool.acquire() as conn:
        ai = await _ai_channel(conn, user_id)
        if ai:
            origin["ai"] = ai
        touch = await _touch(conn, user_id)
        if touch:
            origin["touch"] = touch
    return origin


async def record(order_id: int, user_id: int | None, placed: str) -> dict | None:
    """Detect and store once; a later call (e.g. the cheque arriving) keeps
    the first record. Returns what is stored, or None if anything failed."""
    try:
        await ensure()
        origin = await detect(user_id, placed)
        async with database.pool.acquire() as conn:
            stored = await conn.fetchval(
                """UPDATE orders SET origin = COALESCE(origin, $2) WHERE id = $1
                   RETURNING origin""",
                int(order_id), json.dumps(origin, ensure_ascii=False))
        return parse(stored) or origin
    except Exception:
        logger.warning("order %s origin not recorded", order_id, exc_info=True)
        return None


# ─────────────────────────────── display ─────────────────────────────────

def parse(raw) -> dict | None:
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except (TypeError, ValueError):
        return None


def _lang(lang: str | None) -> dict:
    return _TXT["ru" if lang == "ru" else "uz"]


def touch_text(touch: dict | None, lang: str) -> str | None:
    if not touch:
        return None
    t = _lang(lang)
    kind = touch.get("kind")
    if kind == "instagram":
        return t["instagram"]
    if kind == "link":
        return t["link"].format(name=_esc(touch.get("name") or touch.get("code")))
    if kind == "ad":
        src = str(touch.get("source") or "")
        key = "ad_ig" if src.startswith("ig_") else "ad_fb" if src.startswith("fb_") else "ad"
        return t[key].format(src=_esc(src))
    if kind == "blogger":
        return t["blogger"].format(name=_esc(touch.get("name")))
    if kind == "referral":
        return t["referral"]
    return None


def line(origin, lang: str | None) -> str:
    """'🧭 Qayerdan: 🌐 Saytdan · 🤖 AI bilan gaplashgan (saytda) · 📣 …' or ''."""
    o = parse(origin)
    if not o or o.get("placed") not in PLACES:
        return ""
    t = _lang(lang)
    parts = [t[o["placed"]]]
    if o.get("ai"):
        parts.append(t["ai"].format(where=t["ai_where"].get(o["ai"], _esc(o["ai"]))))
    touch = touch_text(o.get("touch"), lang)
    if touch:
        parts.append(touch)
    return f"{t['head']} " + " · ".join(parts)


def with_line(text: str, origin_line: str) -> str:
    """The card's title stays first; the origin line goes right under it."""
    if not origin_line:
        return text
    head, sep, rest = text.partition("\n")
    return f"{head}\n{origin_line}{sep}{rest}" if sep else f"{head}\n{origin_line}"


# ─────────────────────────────── report ──────────────────────────────────

def _staff() -> list[int]:
    return list(set(ADMIN_IDS) | set(database.LEADERBOARD_EXCLUDED_USER_IDS))


async def counts(days: int) -> dict:
    await ensure()
    async with database.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT origin, total FROM orders
               WHERE origin IS NOT NULL
                 AND created_at >= LOCALTIMESTAMP - make_interval(days => $1::int)
                 AND status <> 'cancelled'
                 AND COALESCE(source, '') NOT IN ('manual', 'b2b', 'test')
                 AND NOT (user_id = ANY($2::bigint[]))""",
            int(days), _staff())
    placed, placed_sum, touches = Counter(), Counter(), Counter()
    ai = ai_sum = 0
    for r in rows:
        o = parse(r["origin"]) or {}
        total = float(r["total"] or 0)
        p = o.get("placed") if o.get("placed") in PLACES else "bot"
        placed[p] += 1
        placed_sum[p] += total
        if o.get("ai"):
            ai += 1
            ai_sum += total
        touches[touch_text(o.get("touch"), "uz") or "🔎 O'zi topgan / kanal"] += 1
    return {"orders": len(rows), "placed": placed, "placed_sum": placed_sum,
            "ai": ai, "ai_sum": ai_sum, "touches": touches}


def _som(v: float) -> str:
    return f"{int(round(v)):,}".replace(",", " ")


def _pct(n: int, total: int) -> str:
    return f"{round(100 * n / total)}%" if total else "0%"


async def report_text(period: str) -> str:
    days = PERIODS.get(period, 30)
    c = await counts(days)
    n = c["orders"]
    lines = [f"🧭 <b>Buyurtmalar qayerdan — oxirgi {days} kun</b>",
             f"Jami: <b>{n} ta</b> (bekor qilingan, qo'lda, optom va xodimlarniki sanalmaydi)", ""]
    if not n:
        lines.append("Hali ma'lumot yo'q: manba 17.11.2026 dan keyingi buyurtmalarda yoziladi.")
        return "\n".join(lines)
    t = _TXT["uz"]
    lines.append("<b>Qayerda buyurtma berildi:</b>")
    for p in PLACES:
        k = c["placed"][p]
        lines.append(f"{t[p]}: <b>{k} ta</b> ({_pct(k, n)}) · {_som(c['placed_sum'][p])} so'm")
    lines += ["", f"🤖 Buyurtmadan oldingi {AI_WINDOW_HOURS} soatda AI bilan gaplashgan: "
                  f"<b>{c['ai']} ta</b> ({_pct(c['ai'], n)}) · {_som(c['ai_sum'])} so'm", "",
              "<b>Mijoz qayerdan kelgan:</b>"]
    for label, k in c["touches"].most_common(12):
        lines.append(f"{label}: <b>{k} ta</b> ({_pct(k, n)})")
    lines += ["", "Har bir yangi buyurtma kartochkasida ham «🧭 Qayerdan» qatori bor."]
    return "\n".join(lines)


def _kb(period: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=("• " if p == period else "") + f"{d} kun", callback_data=f"ordorig:{p}")
        for p, d in PERIODS.items()]])


@router.message(Command("buyurtma_manba"), F.chat.type == "private")
async def cmd_report(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(await report_text("30"), parse_mode="HTML", reply_markup=_kb("30"))


@router.callback_query(F.data.startswith("ordorig:"))
async def cb_report(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer()
        return
    period = cb.data.split(":", 1)[1]
    try:
        await cb.message.edit_text(await report_text(period), parse_mode="HTML", reply_markup=_kb(period))
    except Exception:
        pass
    await cb.answer()
