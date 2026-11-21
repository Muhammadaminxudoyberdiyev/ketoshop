"""Mijoz bilan oxirgi suhbatlar — bot, sayt va kanal guruhi bitta joyda.

Egasi, 2026-11-16. Kanal guruhida mijoz allulozaning zarari haqida so'ragan,
keyin "farqini ayting" degan (javob olmagan), keyin "qaysi birini maslahat
berasiz" deb so'ragan. AI bunga un haqida javob bergan, chunki guruhda har
xabar oldingi gaplarsiz ketardi. Egasi: "bitta mijoz guruhda gaplashadimi,
chatdami, botdami farqi yo'q, mijoz xotirasini kengaytirib boraver".

Uzoq muddatli xotira — ai_memory (qiziqish, fikr, buyurtmalar). Bu jurnal esa
qisqa muddatli: oxirgi savol-javoblar va ular qaysi kanalda bo'lgani. AI ularni
keyingi xabardan oldin oladi:
  * guruhda — har safar (guruh chaqiruvi zanjirsiz). Shunda "farqini ayting"
    yoki "yo'q, men shirinlatgich haqida so'radim" nimaga tegishli ekanini
    biladi;
  * botda va saytda — suhbat boshida (deploy yoki 3 soat jimlikdan keyin
    ham gap uzilmaydi) va bu orada guruhda yozilgani.

Maxfiylik: guruh — ochiq joy. Bot va saytdagi gaplardan guruhga faqat mijoz
nima so'ragani (mavzu) beriladi. AI javoblari (buyurtma, summa, manzil)
berilmaydi, telefon kabi uzun raqamlar yashiriladi. /malumotlarim da
ma'lumotini o'chirgan mijozning gapi yozilmaydi. O'chirish buyrug'i bu
jurnalni ham tozalaydi (ai_memory.forget).

Hamma yozuv to'liq matni bilan MUDDATSIZ saqlanadi (egasi, 2026-11-17: "biz
hammasini cheksiz saqlashimiz kerak"). AI ga esa faqat oxirgilari ko'rsatiladi
(RECENT_TURNS, RECENT_HOURS) va qisqartirib (_short) — bu prompt hajmi uchun,
saqlash uchun emas. Yagona o'chirish — mijozning o'zi /malumotlarim da
so'raganda yoki admin buyrug'i (ai_memory.forget).

Jadval shu modulda yaratiladi (ai_memory dagidek). Hech bir funksiya xato
ko'tarmaydi: jurnal ishlamasa ham suhbat davom etadi.
"""
import logging
import re
from datetime import timedelta

import database

logger = logging.getLogger(__name__)

RECENT_TURNS = 6            # promptga tushadigan oxirgi savol-javoblar
RECENT_HOURS = 72           # bundan eskisi "oxirgi suhbat" emas
TEXT_MAX = 600              # promptdagi bitta matn (bazada to'liq qoladi)
CHANNELS = {"bot": "botda", "site": "saytda", "group": "kanal guruhida"}
PUBLIC_CHANNEL = "group"

_table_ready = False


async def _ensure(conn) -> None:
    global _table_ready
    if _table_ready:
        return
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_dialog (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            channel TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_dialog_user ON ai_dialog(user_id, id)")
    _table_ready = True


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())[:TEXT_MAX]


def _short(text: str, limit: int) -> str:
    text = _clean(text)
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


async def record(user_id: int, channel: str, question: str, answer: str) -> None:
    """Bitta savol-javobni to'liq matni bilan yozadi. Hech narsa o'chirilmaydi."""
    question, answer = (question or "").strip(), (answer or "").strip()
    if not question or channel not in CHANNELS or database.pool is None:
        return
    try:
        import customer_portrait
        async with database.pool.acquire() as conn:
            await _ensure(conn)
            if await customer_portrait.is_opted_out(user_id, conn):
                return
            await conn.execute(
                "INSERT INTO ai_dialog (user_id, channel, question, answer) VALUES ($1, $2, $3, $4)",
                user_id, channel, question, answer)
    except Exception:
        logger.warning("AI dialog could not be recorded for %s", user_id, exc_info=True)


async def review_page(limit: int = 100, before_id: int | None = None, staff: list[int] | None = None) -> list[dict]:
    """The newest AI turns across all customers, for reviewing the AI's answers
    (owner, 2026-11-21: AI'ni haqiqiy suhbatlar asosida o'qitish). Staff excluded."""
    if database.pool is None:
        return []
    limit = max(1, min(500, int(limit)))
    async with database.pool.acquire() as conn:
        await _ensure(conn)
        rows = await conn.fetch(
            """SELECT d.id, d.user_id, d.channel, d.question, d.answer, d.created_at,
                      u.full_name, u.username
               FROM ai_dialog d LEFT JOIN users u ON u.user_id = d.user_id
               WHERE ($1::int IS NULL OR d.id < $1) AND NOT (d.user_id = ANY($2::bigint[]))
               ORDER BY d.id DESC LIMIT $3""",
            before_id, list(staff or []), limit)
    return [dict(r, created_at=r["created_at"].isoformat() if r["created_at"] else None) for r in rows]


async def recent(user_id: int, after_id: int = 0, limit: int = RECENT_TURNS,
                 hours: int = RECENT_HOURS) -> list[dict]:
    """Oxirgi savol-javoblar, eskisidan yangisiga. after_id — shundan keyingilari."""
    if database.pool is None:
        return []
    try:
        async with database.pool.acquire() as conn:
            await _ensure(conn)
            rows = await conn.fetch(
                """SELECT id, channel, question, answer, created_at FROM ai_dialog
                    WHERE user_id = $1 AND id > $2
                      AND created_at > (NOW() AT TIME ZONE 'UTC') - make_interval(hours => $3)
                    ORDER BY id DESC LIMIT $4""",
                user_id, after_id, hours, limit)
    except Exception:
        logger.warning("AI dialog could not be read for %s", user_id, exc_info=True)
        return []
    return [dict(r) for r in reversed(rows)]


async def forget(user_id: int) -> int:
    if database.pool is None:
        return 0
    try:
        async with database.pool.acquire() as conn:
            await _ensure(conn)
            result = await conn.execute("DELETE FROM ai_dialog WHERE user_id = $1", user_id)
        return int(result.split()[-1])
    except Exception:
        logger.warning("AI dialog could not be forgotten for %s", user_id, exc_info=True)
        return 0


_LONG_NUMBER = re.compile(r"\+?\d[\d\s()\-]{6,}\d")


def _mask(text: str) -> str:
    return _LONG_NUMBER.sub("…", text)


def _when(created_at) -> str:
    try:
        return (created_at + timedelta(hours=5)).strftime("%d.%m %H:%M")   # Toshkent vaqti
    except Exception:
        return ""


def context_block(turns: list[dict], public: bool = False) -> str:
    """Promptga qo'shiladigan blok. public=True — guruh uchun: bot va saytdagi
    gaplardan faqat mijozning savoli (mavzusi), AI javobisiz."""
    if not turns:
        return ""
    lines = []
    for turn in turns:
        channel = turn.get("channel")
        head = f"({_when(turn.get('created_at'))}, {CHANNELS.get(channel, channel)})"
        if public and channel != PUBLIC_CHANNEL:
            lines.append(f"{head} Mijoz so'ragan: «{_mask(_short(turn.get('question'), 200))}»")
            continue
        lines.append(f"{head} Mijoz: «{_short(turn.get('question'), 300)}»")
        if turn.get("answer"):
            lines.append(f"   Siz: «{_short(turn.get('answer'), 400)}»")
    if public:
        intro = ("[SHU ODAM BILAN OXIRGI SUHBATLAR (eskisidan yangisiga). Yangi xabar ularning davomi "
                 "bo'lishi mumkin: 'farqini ayting', 'qaysi biri yaxshi', 'yo'q, men X haqida so'radim' — "
                 "bular shu suhbatdagi mavzu haqida, kanal postidagi mahsulotlar haqida emas. Botdagi va "
                 "saytdagi gaplar SHAXSIY: guruhda ularni eslatma va iqtibos keltirma, faqat nima "
                 "haqida gaplashayotganingizni tushunish uchun.]")
    else:
        intro = ("[SHU MIJOZ BILAN OXIRGI SUHBATLAR (bot, sayt va kanal guruhi; eskisidan yangisiga). "
                 "Mijoz shulardan birini davom ettirayotgan bo'lsa, o'sha joydan davom et: bilgan "
                 "narsangni qayta so'rama, aytganingni qaytarib takrorlama.]")
    return intro + "\n" + "\n".join(lines)
