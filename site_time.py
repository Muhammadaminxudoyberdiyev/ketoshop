"""
Saytda faol vaqt uchun Keto (owner, 2026-11-15: "saytda qancha ko'p vaqt
o'tkazsa, shuncha ko'p Keto tanga berilsin"; the same day: "saytni har
daqiqa qimirlatib turish kerak, firibgarlik va sun'iy qurilmalar ishlamasin —
saytdan haqiqiy odam foydalanayotgan bo'lsin").

The Mini App earns Keto for the time a buyer really spends on it. The
server is the only one that counts that time — the page can only report
that a minute happened, never claim a reward:

  - The page sends a beat (POST /api/site-time) after each full minute the
    shop was on screen and focused AND the buyer touched, scrolled or typed
    in it at least once (trusted browser events only; a minute without one
    is not sent). A beat carries how many interactions there were and the
    gaps between them.
  - The server credits at most BEAT_MAX seconds per beat and never more
    than the wall-clock time since this buyer's previous beat (one clock
    per buyer, so two phones or tabs can't double it). Beats closer than
    MIN_GAP seconds are ignored.
  - At most DAILY_CAP seconds count per Tashkent day.
  - Every 20–40 minutes of credited time (at random) the server asks "are
    you still there?" — no more time counts until the buyer taps the small
    card the page then shows (a tap within CHECK_MIN_REPLY of the question
    is not accepted).
  - A session whose beats repeat the same interaction count and the same
    gaps for SAME_PATTERN_LIMIT seconds is a script, not a person: it stops
    earning, and the buyer's row records it (flags / flagged_at) with a
    warning in the log. The buyer is told nothing.

Rewards follow LADDER (the ONE place the owner changes amounts): lifetime
active time reached → Keto, each rung paid once (keto_ledger kind
'site_time', its note is the rung's key, unique per buyer —
idx_keto_ledger_site_time_once). Rung 0 is the first visit itself.

Never paid: shop accounts (LEADERBOARD_EXCLUDED_USER_IDS). Admins earn like
buyers, so they can test it. Off when the Keto program is off (/keto_off)
or this part alone is (/sayt_keto_off).

Public API:
  milestones_up_to(seconds)   -> (threshold, amount, key) for every rung reached
  next_milestone(seconds)     -> the next rung or None
  accrue(state, beat, now)    -> credit one beat into a site_time row (pure)
  confirm_presence(state, token, now) -> the "still there?" answer (pure)
  handle_beat(user_id, body)  -> /api/site-time response
  handle_presence(user_id, body) -> /api/site-time/here response
"""
import hmac
import logging
import random
import secrets
from datetime import datetime, timedelta

import database

logger = logging.getLogger(__name__)

KIND = "site_time"

# ── The ladder (owner, 2026-11-15) ──────────────────────────────────────────
# (lifetime active seconds on the site, Keto paid once on reaching them).
# 0 is the first visit itself. From 3 h to 10 h every hour pays 50 more than
# the one before.
LADDER = (
    (0, 5),             # first visit to the site
    (60, 10),           # 1 min
    (10 * 60, 50),      # 10 min
    (30 * 60, 100),     # 30 min
    (1 * 3600, 200),    # 1 h
    (2 * 3600, 250),
    (3 * 3600, 300),
    (4 * 3600, 350),
    (5 * 3600, 400),
    (6 * 3600, 450),
    (7 * 3600, 500),
    (8 * 3600, 550),
    (9 * 3600, 600),
    (10 * 3600, 650),
)
# After the last rung: this much for every further full hour (11 h, 12 h, …).
EVERY_HOUR_AFTER = 500

# TODO(owner, 2026-11-15): should a buyer WITHOUT an active YANGI5 window
# also get an 8-hour discount in the first-visit celebration? Asked, not
# decided — nothing like it is built. The page shows the 8-hour discount
# only to buyers the server says really have YANGI5 running
# (/api/promo → perks.welcome_promo).

# ── Real-person rules ───────────────────────────────────────────────────────
BEAT_MAX = 60                       # seconds credited per beat at most
MIN_GAP = 10                        # beats closer than this are ignored
DAILY_CAP = 8 * 3600                # credited seconds per Tashkent day
CHECK_EVERY = (20 * 60, 40 * 60)    # "still there?" after this much credited time
CHECK_MIN_REPLY = 0.3               # seconds; a faster "yes" is not a person
SAME_PATTERN_LIMIT = 30 * 60        # identical beats this long = a script
GAP_TOLERANCE_MS = 120              # "identical": every gap within this (or 2%)
MAX_GAPS = 40
TZ_OFFSET = timedelta(hours=5)      # Asia/Tashkent, no DST


def _key(threshold: int) -> str:
    return f"{KIND}:{int(threshold)}"


def milestones_up_to(seconds: int):
    """Every rung reached at `seconds` of lifetime active time, in order, as
    (threshold_seconds, amount, key); the key is unique per rung."""
    for threshold, amount in LADDER:
        if threshold > seconds:
            return
        yield threshold, amount, _key(threshold)
    hour = LADDER[-1][0] // 3600 + 1
    while hour * 3600 <= seconds:
        yield hour * 3600, EVERY_HOUR_AFTER, _key(hour * 3600)
        hour += 1


def next_milestone(seconds: int) -> dict | None:
    for threshold, amount in LADDER:
        if threshold > seconds:
            return {"seconds": threshold, "amount": amount, "left": threshold - int(seconds)}
    hour = max(LADDER[-1][0] // 3600 + 1, int(seconds) // 3600 + 1)
    return {"seconds": hour * 3600, "amount": EVERY_HOUR_AFTER, "left": hour * 3600 - int(seconds)}


def parse_beat(body) -> dict | None:
    """{sid, n, gaps} from the page, validated; None when malformed."""
    if not isinstance(body, dict):
        return None
    sid = body.get("sid")
    if not isinstance(sid, str) or not 4 <= len(sid) <= 32:
        return None
    n = body.get("n", 0)
    if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= 10_000:
        return None
    gaps = body.get("gaps") or []
    if not isinstance(gaps, list):
        return None
    clean = []
    for g in gaps[-MAX_GAPS:]:
        if isinstance(g, bool) or not isinstance(g, (int, float)) or not 0 <= g <= 3_600_000:
            return None
        clean.append(int(g))
    return {"sid": sid, "n": n, "gaps": clean}


def pattern_of(beat: dict) -> str:
    return f"{beat['n']}|" + ",".join(str(g) for g in beat["gaps"])


def same_pattern(previous: str | None, current: str) -> bool:
    """Same interaction count and every gap within GAP_TOLERANCE_MS (or 2%)
    of the previous beat's — what a scripted clicker produces minute after
    minute, and a person practically never does."""
    if not previous:
        return False
    try:
        n0, g0 = previous.split("|", 1)
        n1, g1 = current.split("|", 1)
        a = [int(x) for x in g0.split(",") if x]
        b = [int(x) for x in g1.split(",") if x]
    except ValueError:
        return False
    if n0 != n1 or len(a) != len(b):
        return False
    return all(abs(x - y) <= max(GAP_TOLERANCE_MS, 0.02 * x) for x, y in zip(a, b))


def _new_check_at(state: dict, rng) -> int:
    return int(state.get("active_seconds") or 0) + rng.randint(*CHECK_EVERY)


def accrue(state: dict, beat: dict, now: datetime, rng=random) -> dict:
    """Credit one beat into a site_time row (`state`, changed in place).
    Returns {"credited": seconds, "reason": why nothing was, "flagged": bool}.

    Order matters: a too-early beat changes nothing; any other beat moves
    the buyer's clock; only a beat with real interaction, from a session
    that isn't flagged, with no presence check waiting, under the day's cap,
    earns — and never more than the time since the previous beat."""
    out = {"credited": 0, "reason": None, "flagged": False}
    last = state.get("last_beat_at")
    if last is not None and (now - last).total_seconds() < MIN_GAP:
        out["reason"] = "too_soon"
        return out
    elapsed = (now - last).total_seconds() if last is not None else 0
    state["last_beat_at"] = now
    today = (now + TZ_OFFSET).date()
    if state.get("day_date") != today:
        state["day_date"], state["day_seconds"] = today, 0
    if state.get("check_at") is None:
        state["check_at"] = _new_check_at(state, rng)
    if beat["n"] < 1:
        out["reason"] = "idle"
        return out
    if state.get("flagged_sid") and state["flagged_sid"] == beat["sid"]:
        out["reason"] = "flagged"
        return out
    pattern = pattern_of(beat)
    if same_pattern(state.get("pattern"), pattern):
        state["pattern_seconds"] = int(state.get("pattern_seconds") or 0) + int(min(BEAT_MAX, elapsed))
    else:
        state["pattern_seconds"] = 0
    state["pattern"] = pattern
    if state["pattern_seconds"] >= SAME_PATTERN_LIMIT:
        state["flagged_sid"] = beat["sid"]
        state["flags"] = int(state.get("flags") or 0) + 1
        state["flagged_at"] = now
        state["pattern_seconds"] = 0
        out["reason"], out["flagged"] = "flagged", True
        return out
    if state.get("check_token"):
        out["reason"] = "check"
        return out
    room = max(0, DAILY_CAP - int(state.get("day_seconds") or 0))
    credit = int(min(BEAT_MAX, elapsed, room))
    if credit <= 0:
        out["reason"] = "daily_cap" if room <= 0 else "first_beat"
        return out
    state["active_seconds"] = int(state.get("active_seconds") or 0) + credit
    state["day_seconds"] = int(state.get("day_seconds") or 0) + credit
    out["credited"] = credit
    if state["active_seconds"] >= state["check_at"]:
        state["check_token"] = secrets.token_hex(8)
        state["check_issued_at"] = now
    return out


def confirm_presence(state: dict, token, now: datetime, rng=random) -> bool:
    """The buyer tapped «Davom etyapsizmi? ✅»: time counts again, and the
    next question comes after another 20–40 credited minutes."""
    pending = state.get("check_token")
    if not pending or not isinstance(token, str) or not hmac.compare_digest(token, pending):
        return False
    issued = state.get("check_issued_at")
    if issued is not None and (now - issued).total_seconds() < CHECK_MIN_REPLY:
        return False
    state["check_token"] = None
    state["check_issued_at"] = None
    state["check_at"] = _new_check_at(state, rng)
    return True


# ── Server side of the page ─────────────────────────────────────────────────

async def is_on(user_id: int) -> bool:
    """Earning switched on for this buyer: never shop accounts; never while
    the Keto program (/keto_off) or this part (/sayt_keto_off) is off."""
    if user_id in database.LEADERBOARD_EXCLUDED_USER_IDS:
        return False
    state = await database.get_gamification_state()
    return bool(state.get("enabled")) and bool(state.get("site_time_enabled", True))


async def _pay(user_id: int, state: dict) -> list[dict]:
    """Pay every rung reached and not yet paid. The ledger's unique index
    makes a second payment impossible even if two beats race here; a rung
    that fails to pay is retried on the next beat."""
    paid = []
    upto = int(state.get("paid_through") if state.get("paid_through") is not None else -1)
    start = upto
    for threshold, amount, key in milestones_up_to(int(state.get("active_seconds") or 0)):
        if threshold <= upto:
            continue
        try:
            fresh = await database.credit_keto(user_id, None, amount, KIND, key)
        except Exception:
            logger.exception("Site-time Keto not paid: user %s, %s", user_id, key)
            break
        if fresh:
            paid.append({"seconds": threshold, "amount": amount})
        upto = threshold
    if upto != start:
        await database.set_site_time_paid_through(user_id, upto)
        state["paid_through"] = upto
    return paid


async def info(user_id: int) -> dict:
    """What «Batafsil» explains, from the live rules: cashback by level,
    this buyer's rate, whether Keto can be spent now, the referral share and
    the ladder."""
    import gamification
    import referral_program
    levels = [{"emoji": lvl["emoji"], "label": lvl["label"], "threshold": lvl["threshold"],
               "rate": gamification.EARN_RATES.get(lvl["code"], gamification.EARN_RATE)}
              for lvl in reversed(gamification.LEVELS)]
    try:
        my_rate = await gamification.buyer_rate(user_id) or 0
        redeem = await gamification.is_redemption_enabled(user_id)
    except Exception:
        logger.warning("Site-time info lookup failed for %s", user_id, exc_info=True)
        my_rate, redeem = 0, False
    return {
        "levels": levels,
        "my_rate": my_rate,
        "redeem": bool(redeem),
        "referral_percent": referral_program.CASHBACK_PERCENT,
        "ladder": [{"seconds": s, "amount": a} for s, a in LADDER],
        "every_hour_after": EVERY_HOUR_AFTER,
        "daily_cap": DAILY_CAP,
    }


async def _balance(user_id: int) -> int:
    user = await database.get_user(user_id)
    return int((user or {}).get("keto_balance") or 0)


async def handle_beat(user_id: int, body, now: datetime | None = None) -> tuple[dict, int]:
    """POST /api/site-time → (response, HTTP status).

    {"ok", "enabled", "active", "credited", "awards": [{seconds, amount}],
     "balance", "next": {seconds, amount, left} | None, "check": token | None,
     "info": {...} on the first beat of a visit (hello) and with awards}."""
    beat = parse_beat(body)
    if beat is None:
        return {"ok": False, "error": "bad_beat"}, 400
    if not await is_on(user_id):
        return {"ok": True, "enabled": False}, 200
    now = now or datetime.utcnow()
    result, state = await database.update_site_time(user_id, lambda s: accrue(s, beat, now))
    if result["flagged"]:
        logger.warning("Site-time: suspicious session stopped — user %s, sid %s, same interaction "
                       "pattern for %d min (flag #%s)", user_id, beat["sid"],
                       SAME_PATTERN_LIMIT // 60, state.get("flags"))
    awards = await _pay(user_id, state)
    active = int(state.get("active_seconds") or 0)
    response = {
        "ok": True,
        "enabled": True,
        "active": active,
        "credited": result["credited"],
        "awards": awards,
        "balance": await _balance(user_id),
        "next": next_milestone(active),
        "check": state.get("check_token"),
    }
    if awards or (isinstance(body, dict) and body.get("hello")):
        response["info"] = await info(user_id)
    return response, 200


async def handle_presence(user_id: int, body, now: datetime | None = None) -> tuple[dict, int]:
    """POST /api/site-time/here {token} → {"ok": confirmed}."""
    token = body.get("token") if isinstance(body, dict) else None
    if not isinstance(token, str) or not 1 <= len(token) <= 64:
        return {"ok": False, "error": "bad_token"}, 400
    if not await is_on(user_id):
        return {"ok": False, "enabled": False}, 200
    now = now or datetime.utcnow()
    confirmed, state = await database.update_site_time(user_id, lambda s: confirm_presence(s, token, now))
    return {"ok": bool(confirmed), "check": state.get("check_token")}, 200


# ── Admin view (/sayt_keto) ────────────────────────────────────────────────

def _hours(seconds: int) -> str:
    seconds = int(seconds or 0)
    if seconds < 3600:
        return f"{seconds // 60} daq"
    return f"{seconds // 3600} soat {seconds % 3600 // 60} daq"


def ladder_text() -> str:
    parts = []
    for s, a in LADDER:
        parts.append(("1-tashrif" if s == 0 else _hours(s).replace(" 0 daq", "")) + f" — {a}")
    parts.append(f"keyin har soat — {EVERY_HOUR_AFTER}")
    return " · ".join(parts)


def admin_status_text(enabled: bool, program_on: bool, stats: dict) -> str:
    holat = "🟢 yoqilgan" if enabled else "🔴 o'chirilgan"
    lines = [
        "⏱ <b>Saytda faol vaqt uchun Keto</b>",
        "",
        f"Holat: {holat}",
    ]
    if not program_on:
        lines.append("⚠️ Keto dasturi umuman to'xtatilgan (/keto_on) — hozir hech kimga berilmaydi.")
    lines += [
        f"Qatnashganlar: <b>{stats['users']}</b>, bugun: <b>{stats['today_users']}</b>",
        f"Jami faol vaqt: <b>{_hours(stats['seconds'])}</b>, bugun: <b>{_hours(stats['today_seconds'])}</b>",
        f"Berilgan Keto: <b>{stats['keto']:,}</b>".replace(",", " "),
        f"Shubhali (bir xil harakat) sessiyalar: <b>{stats['flags']}</b>"
        + (f", oxirgisi {stats['last_flag']:%d.%m %H:%M} UTC" if stats.get("last_flag") else ""),
        "",
        f"Pog'onalar: {ladder_text()}",
        f"Kuniga ko'pi bilan {DAILY_CAP // 3600} soat hisoblanadi.",
        "",
        "/sayt_keto_off — to'xtatish · /sayt_keto_on — yoqish",
    ]
    return "\n".join(lines)
