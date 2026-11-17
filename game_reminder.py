"""
🔥 O'yin seriyasi eslatmasi (owner, 2026-11-18: "streakli o'yinlarni eslatib tur").

Every morning at 07:30 Tashkent the bot reminds the people who play the
site's daily games (games.py) that today's step is waiting:

  * 🧩 the daily puzzle, when their streak is alive — solved yesterday, or
    missed one day with the week's one forgiven day still unused (then the
    message says so honestly: today keeps the streak);
  * 📖 the next chapter of «Keto yo'li» and 🗺 the next Ketoland station, when
    they played one in the last two days and a new one opened today.

Why the morning: the daily cap (push_cap.py — 2 a day for active buyers, 1
for everybody else, first come first served) is usually spent by noon, so an
evening "don't lose your streak" would hardly ever pass. 07:30 runs before
the 07:45 feedback ask and the 08:00 tip, and still counts against the cap —
the owner's limit stays whole.

Kept humane: a 🔕 «Eslatmasin» button under every reminder (🔔 brings it back),
and after 3 reminders in a row with no game played the reminders stop until
the person plays again. Never staff or the shop's own accounts. Not on the
Eritritol comeback morning (gift_campaign.comeback_day), whose announcement
gets that day's message slot. Switch: /oyin_eslatma on|off|test.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

import database
import games
from config import ADMIN_IDS, WEBAPP_URL

logger = logging.getLogger(__name__)
router = Router(name="game_reminder")

SEND_AT = (7, 30)             # Tashkent — before the 07:45 feedback ask and the 08:00 tip
LAST_HOUR = 11                # not started after this (a late deploy waits for tomorrow)
SEND_DELAY = 0.06
SETTING = "game_reminder"
KIND = "oyin"                 # push_cap kind
MAX_IGNORED = 3               # reminders in a row with no game played → stop until they play


def _now_tk() -> datetime:
    return datetime.utcnow() + games.TZ


def _d(s) -> date | None:
    try:
        return date.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None


# ─────────────────────────────── who and what ──────────────────────────────

def plan_for(state: dict, day: date) -> dict | None:
    """What to remind this player of today, or None. Pure."""
    if state.get("remind_off") or int(state.get("remind_ignored") or 0) >= MAX_IGNORED:
        return None
    plan: dict = {}
    last = _d(state.get("clue_last"))
    streak = int(state.get("streak") or 0)
    if last != day and streak > 0:
        if last == day - timedelta(days=1):
            plan["streak"] = streak
        elif last == day - timedelta(days=2) and _d(state.get("freeze_week")) != games.week_start(day):
            plan["streak"] = streak
            plan["last_chance"] = True
    recent = day - timedelta(days=2)
    story_day, map_day = _d(state.get("story_day")), _d(state.get("map_day"))
    done = int(state.get("story_done") or 0)
    if story_day and recent <= story_day < day and games.story_open(state, day) > done:
        plan["chapter"] = done + 1
    done = int(state.get("map_done") or 0)
    if map_day and recent <= map_day < day and games.map_open(state, day) > done:
        plan["station"] = done + 1
    return plan or None


_T = {
    "uz": {
        "streak": "🔥 Seriyangiz: <b>{n} kun</b>! Bugungi jumboq tayyor — yechsangiz <b>{m}</b> bo'ladi.",
        "last": ("🔥 <b>{n} kunlik</b> seriyangiz hali saqlanib turibdi: haftada bitta o'tkazib yuborilgan "
                 "kun kechiriladi. Bugungi jumboqni yechsangiz — <b>{m}</b> bo'ladi."),
        "chapter": "📖 «Keto yo'li»: <b>{n}-bob</b> ochildi — Malika opa sizni kutyapti.",
        "station": "🗺 Ketoland xaritasi: <b>{n}-bekat</b> ochildi.",
        "keto": "⭐ Jumboq uchun 15 Keto gacha.",
        "tail": "Bir daqiqalik o'yin 🙂",
        "go_clue": "🧩 Jumboqni yechish", "go_story": "📖 Bobni o'qish", "go_map": "🗺 Bekatga kirish",
        "off": "🔕 Eslatmasin", "on": "🔔 Eslatmani qaytarish",
        "off_done": "Yaxshi, o'yin eslatmalari to'xtatildi. Qaytarish — shu tugma.",
        "on_done": "Eslatmalar qaytdi 🔔",
    },
    "ru": {
        "streak": "🔥 Ваша серия: <b>{n} дн.</b>! Загадка дня готова — отгадаете, и будет <b>{m}</b>.",
        "last": ("🔥 Ваша серия <b>{n} дн.</b> ещё жива: один пропущенный день в неделю прощается. "
                 "Отгадайте загадку сегодня — и будет <b>{m}</b>."),
        "chapter": "📖 «Путь кето»: открылась <b>глава {n}</b> — Малика-опа ждёт вас.",
        "station": "🗺 Карта Кетоландии: открылась <b>станция {n}</b>.",
        "keto": "⭐ За загадку — до 15 Keto.",
        "tail": "Игра на одну минуту 🙂",
        "go_clue": "🧩 Отгадать загадку", "go_story": "📖 Читать главу", "go_map": "🗺 На станцию",
        "off": "🔕 Не напоминать", "on": "🔔 Вернуть напоминания",
        "off_done": "Хорошо, напоминания об играх выключены. Вернуть — этой же кнопкой.",
        "on_done": "Напоминания снова включены 🔔",
    },
}


def _t(key: str, lang: str, **kw) -> str:
    text = _T["ru" if lang == "ru" else "uz"][key].format(**kw)
    if lang == "uz_cyr":
        from translit import lat_to_cyr
        text = lat_to_cyr(text)
    return text


def message_text(plan: dict, lang: str, keto_on: bool = True) -> str:
    lines = []
    if plan.get("streak"):
        n = plan["streak"]
        lines.append(_t("last" if plan.get("last_chance") else "streak", lang, n=n, m=n + 1))
    if plan.get("chapter"):
        lines.append(_t("chapter", lang, n=plan["chapter"]))
    if plan.get("station"):
        lines.append(_t("station", lang, n=plan["station"]))
    tail = _t("tail", lang)
    if plan.get("streak") and keto_on:
        tail = _t("keto", lang) + " " + tail
    return "\n\n".join(lines + [tail])


def _game_of(plan: dict) -> str:
    return "clue" if plan.get("streak") else "story" if plan.get("chapter") else "map"


def keyboard(plan: dict, lang: str, off: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if WEBAPP_URL:
        game = _game_of(plan)
        rows.append([InlineKeyboardButton(text=_t("go_" + game, lang),
                                          web_app=WebAppInfo(url=f"{WEBAPP_URL.rstrip('/')}/?game={game}"))])
    rows.append([InlineKeyboardButton(text=_t("on" if off else "off", lang),
                                      callback_data="g2rem:" + ("on:" if off else "off:") + _game_of(plan))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─────────────────────────────── the round ────────────────────────────────

async def enabled() -> bool:
    try:
        import ai_sales
        values = await ai_sales._load_settings()
        return str(values.get(SETTING, "1")) != "0"
    except Exception:
        return True


async def _keto_on() -> bool:
    try:
        return bool((await database.get_gamification_state()).get("enabled"))
    except Exception:
        return False


async def _players() -> list[tuple[int, dict]]:
    await games.ensure()
    async with database.pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, state FROM game_progress")
    out = []
    for r in rows:
        try:
            out.append((int(r["user_id"]), json.loads(r["state"] or "{}")))
        except ValueError:
            continue
    return out


async def _update_state(user_id: int, **changes) -> None:
    """Merge a few keys into the player's game_progress state."""
    await games.ensure()
    async with database.pool.acquire() as conn:
        async with conn.transaction():
            raw = await conn.fetchval("SELECT state FROM game_progress WHERE user_id = $1 FOR UPDATE", user_id)
            try:
                state = json.loads(raw) if raw else {}
            except ValueError:
                state = {}
            state.update(changes)
            await conn.execute(
                """INSERT INTO game_progress (user_id, state) VALUES ($1, $2)
                   ON CONFLICT (user_id) DO UPDATE SET state = EXCLUDED.state,
                       updated_at = NOW() AT TIME ZONE 'UTC'""",
                user_id, json.dumps(state, ensure_ascii=False))


async def _send(bot: Bot, uid: int, text: str, markup) -> bool:
    for attempt in range(2):
        try:
            await bot.send_message(uid, text, parse_mode=ParseMode.HTML, reply_markup=markup)
            return True
        except TelegramRetryAfter as exc:
            if attempt:
                return False
            await asyncio.sleep(exc.retry_after + 1)
        except (TelegramForbiddenError, TelegramBadRequest):
            return False
        except Exception:
            logger.exception("game reminder to %s failed", uid)
            return False
    return False


async def send_round(bot: Bot, day: date) -> dict:
    import push_cap
    staff = set(ADMIN_IDS) | set(database.LEADERBOARD_EXCLUDED_USER_IDS)
    players = [(uid, st) for uid, st in await _players() if uid not in staff]
    plans = [(uid, st, plan_for(st, day)) for uid, st in players]
    plans = [(uid, st, p) for uid, st, p in plans if p]
    langs = await database.get_user_languages([uid for uid, _, _ in plans]) if plans else {}
    keto_on = await _keto_on()
    stats = {"players": len(players), "due": len(plans), "sent": 0, "capped": 0, "failed": 0, "streaks": 0}
    for uid, st, plan in plans:
        if not await push_cap.claim(uid, KIND):
            stats["capped"] += 1
            continue
        lang = langs.get(uid, "uz")
        if await _send(bot, uid, message_text(plan, lang, keto_on), keyboard(plan, lang)):
            stats["sent"] += 1
            stats["streaks"] += bool(plan.get("streak"))
            try:
                await _update_state(uid, remind_ignored=int(st.get("remind_ignored") or 0) + 1,
                                    remind_last=day.isoformat())
            except Exception:
                logger.exception("game reminder: state not updated for %s", uid)
        else:
            stats["failed"] += 1
        await asyncio.sleep(SEND_DELAY)
    return stats


async def _tick(bot: Bot) -> None:
    now = _now_tk()
    if (now.hour, now.minute) < SEND_AT or now.hour >= LAST_HOUR:
        return
    import gift_campaign
    if gift_campaign.comeback_day(now.date()):
        return          # the gift's comeback announcement takes this morning's slot
    if not await enabled():
        return
    if not await database.claim_release_notes(f"game-remind-{now.date().isoformat()}"):
        return
    stats = await send_round(bot, now.date())
    logger.info("game reminder round: %s", stats)
    if not stats["due"]:
        return
    text = (f"🔥 <b>O'yin eslatmasi</b>: {stats['sent']} ta o'yinchiga yuborildi "
            f"(seriyasi borlar {stats['streaks']}) · chegarada qoldi {stats['capped']} · yetmadi {stats['failed']}\n"
            "Boshqaruv: /oyin_eslatma")
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode=ParseMode.HTML, disable_notification=True)
        except Exception:
            pass


async def scheduler_loop(bot: Bot) -> None:
    await asyncio.sleep(75)
    while True:
        try:
            await _tick(bot)
        except Exception:
            logger.exception("game reminder tick failed")
        await asyncio.sleep(300)


# ─────────────────────────────── buttons ──────────────────────────────────

@router.callback_query(F.data.startswith("g2rem:"))
async def cb_toggle(cb: CallbackQuery):
    parts = (cb.data or "").split(":")
    turn_off = len(parts) > 1 and parts[1] == "off"
    plan = {"streak": 1} if (len(parts) < 3 or parts[2] == "clue") else {"chapter": 1} if parts[2] == "story" else {"station": 1}
    lang = await database.get_user_language(cb.from_user.id) or "uz"
    try:
        await _update_state(cb.from_user.id, remind_off=turn_off, remind_ignored=0)
    except Exception:
        logger.exception("game reminder toggle failed for %s", cb.from_user.id)
        await cb.answer()
        return
    try:
        await cb.message.edit_reply_markup(reply_markup=keyboard(plan, lang, off=turn_off))
    except Exception:
        pass
    await cb.answer(_t("off_done" if turn_off else "on_done", lang), show_alert=turn_off)


# ─────────────────────────────── admin ────────────────────────────────────

@router.message(Command("oyin_eslatma"), F.chat.type == "private")
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    import ai_sales
    parts = (message.text or "").split()
    arg = parts[1].lower() if len(parts) > 1 else ""
    if arg in ("on", "off"):
        await ai_sales.set_setting(SETTING, "1" if arg == "on" else "0", message.from_user.id)
        ai_sales._settings["at"] = float("-inf")
    if arg == "test":
        lang = await database.get_user_language(message.from_user.id) or "uz"
        for plan in ({"streak": 4, "chapter": 6}, {"streak": 9, "last_chance": True}, {"station": 3}):
            await message.answer(message_text(plan, lang, await _keto_on()), parse_mode=ParseMode.HTML,
                                 reply_markup=keyboard(plan, lang))
        await message.answer("☝️ Namunalar — faqat sizga.")
        return
    day = _now_tk().date()
    due = 0
    try:
        staff = set(ADMIN_IDS) | set(database.LEADERBOARD_EXCLUDED_USER_IDS)
        due = sum(1 for uid, st in await _players() if uid not in staff and plan_for(st, day))
    except Exception:
        logger.exception("game reminder status failed")
    on = await enabled()
    await message.answer(
        f"🔥 <b>O'yin seriyasi eslatmasi</b>: {'yoqilgan ✅' if on else 'o‘chiq ⏸'}\n\n"
        f"Har kuni {SEND_AT[0]:02d}:{SEND_AT[1]:02d} da saytdagi kunlik o'yinlarni o'ynayotganlarga: "
        "seriyasi bor bo'lsa — bugungi jumboq, hikoyaning yangi bobi, xaritaning yangi bekati. "
        "Kuniga xabar chegarasiga kiradi. Odam o'zi 🔕 bosib o'chira oladi; 3 marta ketma-ket "
        "o'ynamasa, eslatma to'xtaydi.\n"
        f"Bugungi ro'yxatda: {due} kishi\n\n"
        "<code>/oyin_eslatma test</code> — namuna · <code>/oyin_eslatma off</code> — o'chirish",
        parse_mode=ParseMode.HTML)
