"""
🎮 O'yinlar markazi — the server side of the Mini App's games (2026-11-17).

Owner: "keto o'yinlarni yana noodatiy bilim o'yinlarini va sarguzasht sifat
o'yinlarni ko'paytirishimiz kerak" → "hamma taklif qilingan o'yinlarni qur va
prodga chiqar faqat yuqori strategiya va inson psixologiyasini ham hisobga olib
qur bog'liqlik bo'lsin". The proposal he approved: seven new games, a small
daily-capped Keto reward, a weekly leaderboard and a share button.

The games themselves run in the page (webapp/games2.js). The server keeps
what must not live on one phone and pays the Keto:

  * a finished play         POST /api/games/finish {game, points, ...}
      - leaderboard points: the best result per game per Tashkent day counts,
        so replaying one game can't farm the board — trying more games can;
      - Keto: the first finished play of a game each day pays REWARD[game];
        the daily puzzle pays by the hints used and builds a streak;
        a story chapter and a map station pay once, ever; finishing all three
        «Bugungi topshiriqlar» pays a small bonus. Every payment goes through
        keto_ledger with a unique note (no double pay on a retry) and the sum
        of a buyer's game Keto per day never passes DAILY_CAP.
  * the state of the page   GET  /api/games/state
      today's puzzle number, streak, story chapter and map station open now,
      today's Keto from games, the week's top 10 and the buyer's own place,
      and how many people solved today's puzzle (social proof).

Psychology, kept honest (no paid boosts, no fake scarcity, no countdowns):
  - a daily ritual (one puzzle a day, the same for everyone) and a streak with
    one free "missed day" a week, so one busy day doesn't wipe a long streak;
  - goal gradient: three small daily tasks with a progress ring and a bonus;
  - curiosity: one story chapter and one map station open per day, each
    ending with what comes next;
  - mastery and social proof: best results, the week's board, "N people
    solved it today".
Staff and the shop's own accounts never earn and never show on the board.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiohttp import web

import database
from config import ADMIN_IDS, BOT_USERNAME

logger = logging.getLogger(__name__)
router = Router()

TZ = timedelta(hours=5)
KIND = "game"
DAILY_CAP = max(0, int(os.getenv("GAMES_KETO_DAILY", "60")))

# id -> (Keto for the day's first finished play, max leaderboard points a play may claim)
GAMES = {
    # the four games that were already there (client-only until now)
    "keto": (5, 10), "duel": (5, 30), "quiz": (5, 10), "memory": (5, 10),
    # new, 2026-11-17
    "swap": (5, 40), "label": (5, 40), "myth": (5, 12), "bazaar": (8, 60),
    "clue": (15, 3),        # daily puzzle: points = 3 / 2 / 1 by hints used
    "story": (5, 10),       # per chapter, once ever
    "map": (10, 10),        # per station, once ever
}
CLUE_KETO = {3: 15, 2: 10, 1: 5}
STREAK_BONUS = {3: 10, 7: 25, 14: 30, 30: 50}
TASKS_BONUS = 10
STORY_CHAPTERS = 30
MAP_STATIONS = 10
BOARD_SIZE = 10
PASS = {"swap": 0.5, "label": 0.5, "myth": 0.5, "bazaar": 0.5, "keto": 0.5, "quiz": 0.5}

_ready = False


def today_tk(now: datetime | None = None) -> date:
    return ((now or datetime.utcnow()) + TZ).date()


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())          # Monday


def clue_index(day: date, count: int) -> int:
    """Today's puzzle — the same for everyone, a new one each Tashkent day."""
    return (day.toordinal() * 7 + 3) % max(1, count)


async def ensure() -> None:
    global _ready
    if _ready:
        return
    async with database.pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS game_plays (
                id         BIGSERIAL PRIMARY KEY,
                user_id    BIGINT NOT NULL,
                game       TEXT NOT NULL,
                day        DATE NOT NULL,
                points     INTEGER NOT NULL DEFAULT 0,
                keto       INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
            )""")
        await conn.execute("CREATE INDEX IF NOT EXISTS game_plays_day ON game_plays (day, game)")
        await conn.execute("CREATE INDEX IF NOT EXISTS game_plays_user ON game_plays (user_id, day)")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS game_progress (
                user_id    BIGINT PRIMARY KEY,
                state      TEXT NOT NULL DEFAULT '{}',
                updated_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
            )""")
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_keto_ledger_game_once "
            "ON keto_ledger(user_id, note) WHERE kind = 'game'")
    _ready = True


def _staff() -> set[int]:
    return set(ADMIN_IDS) | set(database.LEADERBOARD_EXCLUDED_USER_IDS)


async def earning_on(user_id: int) -> bool:
    if user_id in _staff():
        return False
    try:
        state = await database.get_gamification_state()
        return bool(state.get("enabled"))
    except Exception:
        return False


# ─────────────────────────────── pure rules ───────────────────────────────

def _d(s) -> date | None:
    try:
        return date.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None


def streak_after(state: dict, day: date) -> tuple[int, bool]:
    """The streak once today's puzzle is solved, and whether the weekly free
    'missed day' was used for it. One missed day a week is forgiven."""
    last = _d(state.get("clue_last"))
    streak = int(state.get("streak") or 0)
    if last == day:
        return streak, False
    if last == day - timedelta(days=1):
        return streak + 1, False
    if last == day - timedelta(days=2) and streak > 0:
        used = _d(state.get("freeze_week"))
        if used != week_start(day):
            return streak + 1, True
    return 1, False


def story_open(state: dict, day: date) -> int:
    """The highest chapter that may be played today: one new chapter a day,
    in order. 0 = all done."""
    done = int(state.get("story_done") or 0)
    if done >= STORY_CHAPTERS:
        return 0
    if _d(state.get("story_day")) == day:          # today's chapter already played
        return done                                  # replays only
    return done + 1


def map_open(state: dict, day: date) -> int:
    done = int(state.get("map_done") or 0)
    if done >= MAP_STATIONS:
        return 0
    if _d(state.get("map_day")) == day:
        return done
    return done + 1


def tasks_of(state: dict, day: date, played_today: set[str]) -> dict:
    """«Bugungi topshiriqlar»: today's puzzle, a story chapter (or a map
    station once the story is over) and one more game."""
    clue = _d(state.get("clue_last")) == day
    journey = _d(state.get("story_day")) == day or _d(state.get("map_day")) == day
    other = bool(played_today - {"clue", "story", "map"})
    return {"clue": clue, "journey": journey, "game": other,
            "done": sum((clue, journey, other)), "bonus_paid": _d(state.get("tasks_day")) == day}


def clamp_points(game: str, points) -> int:
    try:
        p = int(points)
    except (TypeError, ValueError):
        return 0
    return max(0, min(GAMES[game][1], p))


def passed(game: str, points: int, total) -> bool:
    need = PASS.get(game)
    if need is None:
        return True
    try:
        t = int(total)
    except (TypeError, ValueError):
        return points > 0
    return t > 0 and points >= need * min(t, GAMES[game][1])


# ─────────────────────────────── storage ──────────────────────────────────

async def _state(conn, user_id: int) -> dict:
    raw = await conn.fetchval("SELECT state FROM game_progress WHERE user_id = $1", user_id)
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


async def _save(conn, user_id: int, state: dict) -> None:
    await conn.execute(
        """INSERT INTO game_progress (user_id, state) VALUES ($1, $2)
           ON CONFLICT (user_id) DO UPDATE SET state = EXCLUDED.state,
               updated_at = NOW() AT TIME ZONE 'UTC'""",
        user_id, json.dumps(state, ensure_ascii=False))


async def keto_today(conn, user_id: int, day: date) -> int:
    start = datetime.combine(day, datetime.min.time()) - TZ
    return int(await conn.fetchval(
        """SELECT COALESCE(SUM(amount), 0) FROM keto_ledger
           WHERE user_id = $1 AND kind = 'game' AND created_at >= $2 AND created_at < $3""",
        user_id, start, start + timedelta(days=1)) or 0)


async def _pay(user_id: int, amount: int, note: str, day: date) -> int:
    """Pay up to `amount` within today's cap. Returns what was paid."""
    if amount <= 0 or DAILY_CAP <= 0:
        return 0
    async with database.pool.acquire() as conn:
        room = DAILY_CAP - await keto_today(conn, user_id, day)
    amount = min(amount, room)
    if amount <= 0:
        return 0
    try:
        return amount if await database.credit_keto(user_id, None, amount, KIND, note) else 0
    except Exception:
        logger.exception("Game Keto not paid: user %s, %s", user_id, note)
        return 0


def _name(full_name: str | None, user_id: int) -> str:
    parts = (full_name or "").split()
    if not parts:
        return f"O'yinchi {str(user_id)[-3:]}"
    return parts[0][:16] + (f" {parts[1][0]}." if len(parts) > 1 and parts[1] else "")


async def board(conn, user_id: int, day: date) -> dict:
    """This week's top players: per (user, game, day) the best play counts."""
    rows = await conn.fetch(
        """WITH best AS (
               SELECT user_id, game, day, MAX(points) AS p FROM game_plays
               WHERE day >= $1 AND NOT (user_id = ANY($2::bigint[]))
               GROUP BY user_id, game, day),
           tot AS (SELECT user_id, SUM(p)::int AS pts FROM best GROUP BY user_id)
           SELECT t.user_id, t.pts, u.full_name,
                  RANK() OVER (ORDER BY t.pts DESC) AS rnk
           FROM tot t LEFT JOIN users u ON u.user_id = t.user_id
           WHERE t.pts > 0
           ORDER BY t.pts DESC, t.user_id LIMIT 500""",
        week_start(day), list(_staff()))
    top, me = [], None
    for r in rows:
        item = {"name": _name(r["full_name"], r["user_id"]), "points": r["pts"], "rank": int(r["rnk"]),
                "me": r["user_id"] == user_id}
        if len(top) < BOARD_SIZE:
            top.append(item)
        if r["user_id"] == user_id:
            me = item
    return {"top": top, "me": me, "players": len(rows)}


# ─────────────────────────────── handlers ─────────────────────────────────

async def state_for(user_id: int, now: datetime | None = None) -> dict:
    await ensure()
    day = today_tk(now)
    async with database.pool.acquire() as conn:
        st = await _state(conn, user_id)
        played = {r["game"] for r in await conn.fetch(
            "SELECT DISTINCT game FROM game_plays WHERE user_id = $1 AND day = $2", user_id, day)}
        ktoday = await keto_today(conn, user_id, day)
        solvers = int(await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM game_plays WHERE game = 'clue' AND day = $1", day) or 0)
        top = await board(conn, user_id, day)
    streak = int(st.get("streak") or 0)
    last = _d(st.get("clue_last"))
    if last and last < day - timedelta(days=1) and streak_after(st, day)[0] == 1:
        streak = 0                                          # broken: shown as 0 until solved again
    return {
        "ok": True, "day": day.isoformat(), "clue_seed": day.toordinal(),
        "clue_solved": last == day, "clue_hints": st.get("clue_hints") if last == day else None,
        "streak": streak, "best_streak": int(st.get("best_streak") or 0),
        "story": {"done": int(st.get("story_done") or 0), "open": story_open(st, day),
                  "stats": st.get("story_stats") or {}},
        "map": {"done": int(st.get("map_done") or 0), "open": map_open(st, day)},
        "tasks": tasks_of(st, day, played),
        "keto_today": ktoday, "keto_cap": DAILY_CAP, "earning": await earning_on(user_id),
        "solvers_today": solvers, "board": top,
        # «Do'stga yuborish»: a tracked shop link (shop_links.py) — a friend's order
        # then says 🔗 O'yin under «🧭 Qayerdan» (order_origin.py).
        "share_url": f"https://t.me/{BOT_USERNAME}/shop?startapp=oyin",
    }


async def finish(user_id: int, body: dict, now: datetime | None = None) -> tuple[dict, int]:
    await ensure()
    game = str((body or {}).get("game") or "")
    if game not in GAMES:
        return {"ok": False, "error": "game"}, 400
    day = today_tk(now)
    points = clamp_points(game, body.get("points"))
    earn = await earning_on(user_id)
    paid, notes = 0, []
    async with database.pool.acquire() as conn:
        st = await _state(conn, user_id)

    if game == "clue":
        if _d(st.get("clue_last")) == day:
            return {"ok": True, "already": True, **(await state_for(user_id, now))}, 200
        hints = max(1, min(3, 4 - points)) if points else 3
        if points:
            streak, freeze = streak_after(st, day)
            st.update(clue_last=day.isoformat(), clue_hints=hints, streak=streak,
                      best_streak=max(streak, int(st.get("best_streak") or 0)))
            if freeze:
                st["freeze_week"] = week_start(day).isoformat()
            if earn:
                paid += await _pay(user_id, CLUE_KETO.get(points, 5), f"clue:{day}", day)
                bonus = STREAK_BONUS.get(streak)
                if bonus:
                    got = await _pay(user_id, bonus, f"streak:{day}:{streak}", day)
                    if got:
                        notes.append({"kind": "streak", "streak": streak, "keto": got})
                    paid += got
        else:                                     # gave up: today is spent, the streak waits
            st.update(clue_last=day.isoformat(), clue_hints=0)
    elif game == "story":
        chapter = int(body.get("chapter") or 0)
        if chapter < 1 or chapter > story_open(st, day) or chapter > STORY_CHAPTERS:
            return {"ok": False, "error": "locked"}, 409
        if chapter == int(st.get("story_done") or 0) + 1:
            st["story_done"] = chapter
            st["story_day"] = day.isoformat()
            stats = st.get("story_stats") or {}
            for key, delta in (body.get("stats") or {}).items():
                if key in ("energiya", "natija", "kayfiyat"):
                    try:
                        stats[key] = max(0, min(100, int(stats.get(key, 50)) + int(delta)))
                    except (TypeError, ValueError):
                        pass
            st["story_stats"] = stats
            if earn:
                paid += await _pay(user_id, GAMES["story"][0], f"story:{chapter}", day)
    elif game == "map":
        station = int(body.get("station") or 0)
        if station < 1 or station > map_open(st, day) or station > MAP_STATIONS:
            return {"ok": False, "error": "locked"}, 409
        if station == int(st.get("map_done") or 0) + 1 and points >= 2:      # 2 of 3 right
            st["map_done"] = station
            st["map_day"] = day.isoformat()
            if earn:
                paid += await _pay(user_id, GAMES["map"][0], f"map:{station}", day)
    else:
        if earn and passed(game, points, body.get("total")):
            paid += await _pay(user_id, GAMES[game][0], f"{game}:{day}", day)

    async with database.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO game_plays (user_id, game, day, points, keto) VALUES ($1, $2, $3, $4, $5)",
            user_id, game, day, points, paid)
        played = {r["game"] for r in await conn.fetch(
            "SELECT DISTINCT game FROM game_plays WHERE user_id = $1 AND day = $2", user_id, day)}
        tasks = tasks_of(st, day, played)
        if tasks["done"] == 3 and not tasks["bonus_paid"]:
            st["tasks_day"] = day.isoformat()
            if earn:
                got = await _pay(user_id, TASKS_BONUS, f"tasks:{day}", day)
                if got:
                    notes.append({"kind": "tasks", "keto": got})
                paid += got
        st["remind_ignored"] = 0          # played → the morning reminders may go on (game_reminder.py)
        await _save(conn, user_id, st)
    out = await state_for(user_id, now)
    out.update(paid=paid, notes=notes, points=points)
    return out, 200


async def api_state(request: web.Request):
    try:
        return web.json_response(await state_for(request["user_id"]))
    except Exception:
        logger.exception("games state failed for %s", request.get("user_id"))
        return web.json_response({"ok": False}, status=500)


async def api_finish(request: web.Request):
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)
    try:
        data, status = await finish(request["user_id"], body)
    except Exception:
        logger.exception("games finish failed for %s", request.get("user_id"))
        return web.json_response({"ok": False}, status=500)
    return web.json_response(data, status=status)


def add_routes(app: web.Application) -> None:
    app.router.add_get("/api/games/state", api_state)
    app.router.add_post("/api/games/finish", api_finish)


# ─────────────────────────────── admin ────────────────────────────────────

async def admin_stats(now: datetime | None = None) -> dict:
    await ensure()
    day = today_tk(now)
    async with database.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT game, COUNT(*) AS plays, COUNT(DISTINCT user_id) AS players, SUM(keto) AS keto
               FROM game_plays WHERE day >= $1 AND NOT (user_id = ANY($2::bigint[]))
               GROUP BY game ORDER BY plays DESC""",
            day - timedelta(days=6), list(_staff()))
        today_players = int(await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM game_plays WHERE day = $1 AND NOT (user_id = ANY($2::bigint[]))",
            day, list(_staff())) or 0)
    return {"rows": [dict(r) for r in rows], "today_players": today_players}


def admin_text(stats: dict) -> str:
    lines = ["🎮 <b>O'yinlar — oxirgi 7 kun</b>",
             f"Bugun o'ynaganlar: <b>{stats['today_players']}</b> kishi",
             f"Keto chegarasi: kuniga {DAILY_CAP} ta (GAMES_KETO_DAILY)", ""]
    if not stats["rows"]:
        lines.append("Hali hech kim o'ynamadi.")
    for r in stats["rows"]:
        lines.append(f"• {r['game']}: {r['plays']} marta, {r['players']} kishi, {int(r['keto'] or 0)} Keto")
    return "\n".join(lines)


@router.message(Command("oyinlar"), F.chat.type == "private")
async def cmd_games(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        text = admin_text(await admin_stats())
    except Exception:
        logger.exception("games admin stats failed")
        text = "🎮 O'yinlar statistikasi hozircha olinmadi."
    await message.answer(text, parse_mode="HTML")
