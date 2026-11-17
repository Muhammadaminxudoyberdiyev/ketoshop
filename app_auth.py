"""📱 Ketoshop Android ilovasi: Telegram orqali kirish va har bir so'rovning imzosi.

The app (mobile/) talks to the same /api/* routes as the Mini App. Inside
Telegram a request carries signed initData; outside Telegram there is none,
so the app gets its own session. Threat model and the reasoning behind each
rule: mobile/SECURITY.md.

How a buyer logs in (no password, no SMS):
  1. The phone makes a P-256 key inside the Android Keystore (TEE/StrongBox,
     cannot be exported) and POSTs its public half to /app/v1/auth/start,
     signed with that key. The answer: a login id, a bot link and a 2-digit
     number shown on screen.
  2. The app opens t.me/<bot>?start=applogin_<id>. The bot asks the buyer to
     tap the number they see in the app among three. A link someone forwarded
     to a victim can't be approved by mistake: the victim doesn't see the
     attacker's screen. A wrong tap kills the request.
  3. The app polls /app/v1/auth/poll, signed with the same key, and on
     approval receives an access token (15 min) and a refresh token (30 days,
     rotated on every use; a session lives at most 90 days).

Every later request is signed with the device key too:
    KS1 \\n METHOD \\n /path?query \\n timestamp_ms \\n nonce \\n b64url(sha256(body))
The server keeps the public key only, so a token copied off the phone (a
backup, a log, a compromised proxy) is useless without the phone's Keystore.
The timestamp window and the one-time nonce stop replays. Tokens are 256-bit
randoms; the database stores only their SHA-256.
"""
from __future__ import annotations

import base64
import functools
import hashlib
import html
import json
import logging
import os
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from aiohttp import web
from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

import database

logger = logging.getLogger(__name__)
router = Router(name="app_auth")

LOGIN_PREFIX = "applogin_"
LOGIN_TTL = 300                    # s — the buyer has 5 min to confirm in the bot
APPROVED_PICKUP = 120              # s — after approval, the app has this long to collect
ACCESS_TTL = 15 * 60
REFRESH_TTL = 30 * 86400
SESSION_MAX_AGE = 90 * 86400
REFRESH_GRACE = 60                 # s — a just-rotated refresh token still works (lost reply)
MAX_SESSIONS_PER_USER = 10
SIG_VERSION = "KS1"
SIG_WINDOW_MS = 120_000            # the app corrects its clock from server_time
MAX_UPLOAD = 10 * 1024 * 1024      # cheque photo/PDF, same cap as the Mini App

H_TS, H_NONCE, H_SIG = "X-KS-Timestamp", "X-KS-Nonce", "X-KS-Signature"

_ID_RE = re.compile(r"[A-Za-z0-9_-]{22}")
_NONCE_RE = re.compile(r"[A-Za-z0-9_-]{16,64}")
_TOKEN_RE = re.compile(r"ks[ar]_[A-Za-z0-9_-]{43}")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f​-‏‪-‮⁦-⁩]")
_ENV_FLAGS = ("rooted", "hooked", "debugged", "emulator", "tampered")


def require_clean_device() -> bool:
    """APP_REQUIRE_CLEAN=1: refuse login/refresh from a phone the app itself
    reports as hooked, debugged, emulated or re-signed. Off by default — a
    rooted phone is still a paying customer; the flags are logged either way."""
    return os.getenv("APP_REQUIRE_CLEAN", "").strip() == "1"


# ───────────────────────────── primitives ──────────────────────────────

def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def unb64u(text: str) -> bytes:
    if not isinstance(text, str) or not re.fullmatch(r"[A-Za-z0-9_-]*", text):
        raise ValueError("not base64url")
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("ascii")).digest()


def new_token(kind: str) -> str:
    """'a' access / 'r' refresh — 256 random bits behind a greppable prefix."""
    return f"ks{kind}_{b64u(secrets.token_bytes(32))}"


def canonical(method: str, target: str, ts: int, nonce: str, body: bytes) -> bytes:
    body_hash = b64u(hashlib.sha256(body).digest())
    return "\n".join((SIG_VERSION, method.upper(), target, str(ts), nonce, body_hash)).encode("utf-8")


@functools.lru_cache(maxsize=4096)
def _public_key(device_key: str) -> ec.EllipticCurvePublicKey | None:
    try:
        raw = unb64u(device_key)
        if not 60 <= len(raw) <= 120:
            return None
        key = serialization.load_der_public_key(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(key, ec.EllipticCurvePublicKey) or key.curve.name != "secp256r1":
        return None
    return key


def valid_device_key(device_key) -> bool:
    return isinstance(device_key, str) and _public_key(device_key) is not None


def verify_signature(device_key: str, signature: str, message: bytes) -> bool:
    key = _public_key(device_key)
    if key is None:
        return False
    try:
        sig = unb64u(signature)
        if not 8 <= len(sig) <= 80:
            return False
        key.verify(sig, message, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError):
        return False


def clean_device_name(value) -> str:
    text = _CONTROL_RE.sub("", str(value or "")).strip()
    return text[:60] or "Android"


def clean_env(value) -> dict:
    """The app's own view of the phone. Only known flags, only booleans."""
    if not isinstance(value, dict):
        return {}
    return {k: bool(value.get(k)) for k in _ENV_FLAGS if k in value}


def env_is_dirty(env: dict) -> bool:
    return any(env.get(k) for k in ("hooked", "debugged", "emulator", "tampered"))


class NonceCache:
    """Nonces seen within the signature window, per signer. Filled only after
    a signature checks out, so unsigned junk can't grow it."""

    def __init__(self, ttl_s: float):
        self._ttl = ttl_s
        self._seen: dict[str, float] = {}
        self._ops = 0

    def add(self, scope: str, nonce: str, now: float) -> bool:
        key = f"{scope}:{nonce}"
        expires = self._seen.get(key)
        if expires is not None and expires > now:
            return False
        self._seen[key] = now + self._ttl
        self._ops += 1
        if self._ops % 1024 == 0:
            self._seen = {k: v for k, v in self._seen.items() if v > now}
        return True


class RateLimit:
    """Token bucket per key: `per_minute` steady, `burst` at once."""

    def __init__(self, per_minute: float, burst: int):
        self._rate = per_minute / 60.0
        self._burst = float(burst)
        self._buckets: dict[str, tuple[float, float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        tokens, at = self._buckets.get(key, (self._burst, now))
        tokens = min(self._burst, tokens + (now - at) * self._rate)
        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False
        self._buckets[key] = (tokens - 1.0, now)
        if len(self._buckets) > 50_000:
            self._buckets = {k: v for k, v in self._buckets.items() if now - v[1] < 600}
        return True


_nonces = NonceCache(ttl_s=2 * SIG_WINDOW_MS / 1000)
_start_per_ip = RateLimit(per_minute=6, burst=4)
_start_global = RateLimit(per_minute=300, burst=60)
_poll_per_login = RateLimit(per_minute=60, burst=5)
_refresh_per_session = RateLimit(per_minute=12, burst=4)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _json(data: dict, status: int = 200) -> web.Response:
    return web.json_response(data, status=status, headers={"Cache-Control": "no-store"})


def _error(code: str, status: int, **extra) -> web.Response:
    return _json({"error": code, **extra}, status=status)


def client_ip(request: web.Request) -> str:
    """APP_TRUST_PROXY=1 behind our own reverse proxy: its X-Forwarded-For
    entry is the last one (anything to the left was sent by the client)."""
    if os.getenv("APP_TRUST_PROXY", "").strip() == "1":
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()[:64]
    return request.remote or "?"


async def read_body(request: web.Request) -> bytes:
    """The request body, read once. JSON comes through request.read() (aiohttp
    caches it, so the handler's request.json() still works; client_max_size
    caps it). A cheque photo/PDF is read here with its own 10 MB cap and
    handed to the handler as request["raw_body"]."""
    ctype = request.content_type or ""
    if ctype.startswith("image/") or ctype == "application/pdf":
        if (request.content_length or 0) > MAX_UPLOAD:
            raise web.HTTPRequestEntityTooLarge(max_size=MAX_UPLOAD, actual_size=request.content_length)
        buf = bytearray()
        async for chunk in request.content.iter_chunked(64 * 1024):
            buf.extend(chunk)
            if len(buf) > MAX_UPLOAD:
                raise web.HTTPRequestEntityTooLarge(max_size=MAX_UPLOAD, actual_size=len(buf))
        request["raw_body"] = bytes(buf)
        return request["raw_body"]
    return await request.read()


def check_signature(request: web.Request, body: bytes, device_key: str, scope: str) -> web.Response | None:
    """None when the request is signed by `device_key`, fresh and not a
    replay; otherwise the 401 to send back."""
    ts_raw = request.headers.get(H_TS, "")
    nonce = request.headers.get(H_NONCE, "")
    signature = request.headers.get(H_SIG, "")
    if not (ts_raw.isdigit() and len(ts_raw) <= 15 and _NONCE_RE.fullmatch(nonce) and signature):
        return _error("bad_signature", 401)
    now_ms = _now_ms()
    ts = int(ts_raw)
    if abs(now_ms - ts) > SIG_WINDOW_MS:
        return _error("clock_skew", 401, server_time=now_ms)
    message = canonical(request.method, request.raw_path, ts, nonce, body)
    if not verify_signature(device_key, signature, message):
        return _error("bad_signature", 401)
    if not _nonces.add(scope, nonce, time.time()):
        return _error("replayed", 401)
    return None


# ───────────────────────────── storage ──────────────────────────────

_ready = False


async def ensure_schema() -> None:
    global _ready
    if _ready:
        return
    async with database.pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_login_requests (
                id          TEXT PRIMARY KEY,
                device_key  TEXT NOT NULL,
                device_name TEXT NOT NULL,
                match_code  SMALLINT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                user_id     BIGINT,
                profile     JSONB,
                env         JSONB,
                ip          TEXT,
                terms_version TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                expires_at  TIMESTAMPTZ NOT NULL,
                decided_at  TIMESTAMPTZ
            )""")
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS app_login_requests_expires ON app_login_requests (expires_at)")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_sessions (
                id                BIGSERIAL PRIMARY KEY,
                user_id           BIGINT NOT NULL,
                device_key        TEXT NOT NULL,
                device_name       TEXT NOT NULL,
                profile           JSONB,
                env               JSONB,
                access_hash       BYTEA NOT NULL UNIQUE,
                access_expires    TIMESTAMPTZ NOT NULL,
                refresh_hash      BYTEA NOT NULL UNIQUE,
                prev_refresh_hash BYTEA,
                refresh_expires   TIMESTAMPTZ NOT NULL,
                rotated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                last_seen         TIMESTAMPTZ NOT NULL DEFAULT now(),
                revoked_at        TIMESTAMPTZ,
                revoke_reason     TEXT,
                -- Oferta shartlari (app_terms.py): which edition, accepted when.
                terms_version     TEXT,
                terms_accepted_at TIMESTAMPTZ
            )""")
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS app_sessions_user ON app_sessions (user_id) WHERE revoked_at IS NULL")
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS app_sessions_prev_refresh ON app_sessions (prev_refresh_hash)")
    _ready = True


def _utc(seconds: float = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def _profile(row) -> dict:
    value = row["profile"]
    if isinstance(value, str):
        value = json.loads(value)
    return value or {}


async def _issue(conn, *, user_id: int, device_key: str, device_name: str,
                 profile: dict, env: dict, terms_version: str | None = None) -> tuple[int, str, str]:
    access, refresh = new_token("a"), new_token("r")
    session_id = await conn.fetchval(
        """INSERT INTO app_sessions (user_id, device_key, device_name, profile, env,
                                     access_hash, access_expires, refresh_hash, refresh_expires,
                                     terms_version, terms_accepted_at)
           VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $7, $8, $9, $10::text,
                   CASE WHEN $10::text IS NULL THEN NULL ELSE now() END) RETURNING id""",
        user_id, device_key, device_name, json.dumps(profile), json.dumps(env),
        token_hash(access), _utc(ACCESS_TTL), token_hash(refresh), _utc(REFRESH_TTL), terms_version)
    # Oldest sessions beyond the cap go first — a stolen phone can't pile up.
    await conn.execute(
        """UPDATE app_sessions SET revoked_at = now(), revoke_reason = 'session_cap'
           WHERE id IN (SELECT id FROM app_sessions WHERE user_id = $1 AND revoked_at IS NULL
                        ORDER BY created_at DESC OFFSET $2)""",
        user_id, MAX_SESSIONS_PER_USER)
    return session_id, access, refresh


async def revoke(session_id: int, reason: str, user_id: int | None = None) -> bool:
    await ensure_schema()
    async with database.pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE app_sessions SET revoked_at = now(), revoke_reason = $2
               WHERE id = $1 AND revoked_at IS NULL AND ($3::bigint IS NULL OR user_id = $3)""",
            session_id, reason, user_id)
    return result.endswith(" 1")


# ───────────────────────────── /api/* (Bearer) ──────────────────────────────

@dataclass(frozen=True)
class AppSession:
    id: int
    user_id: int
    device_name: str
    profile: dict


async def authenticate(request: web.Request) -> AppSession | web.Response:
    """Authorization: Bearer <access> plus a valid device signature."""
    token = request.headers.get("Authorization", "")[7:].strip()
    if not _TOKEN_RE.fullmatch(token) or not token.startswith("ksa_"):
        return _error("invalid_token", 401)
    await ensure_schema()
    async with database.pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, user_id, device_key, device_name, profile, access_expires, last_seen
               FROM app_sessions
               WHERE access_hash = $1 AND revoked_at IS NULL
                 AND refresh_expires > now() AND created_at > now() - make_interval(secs => $2)""",
            token_hash(token), float(SESSION_MAX_AGE))
    if row is None:
        return _error("invalid_token", 401)
    if row["access_expires"] <= _utc():
        return _error("token_expired", 401)
    body = await read_body(request)
    failure = check_signature(request, body, row["device_key"], f"s{row['id']}")
    if failure is not None:
        return failure
    if row["last_seen"] < _utc(-300):
        async with database.pool.acquire() as conn:
            await conn.execute("UPDATE app_sessions SET last_seen = now() WHERE id = $1", row["id"])
    return AppSession(row["id"], row["user_id"], row["device_name"], _profile(row))


async def _signed_json(request: web.Request, limit: int = 8192) -> tuple[bytes, dict] | web.Response:
    if (request.content_length or 0) > limit:
        return _error("too_large", 413)
    body = await request.read()
    if len(body) > limit:
        return _error("too_large", 413)
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        return _error("bad_request", 400)
    if not isinstance(data, dict):
        return _error("bad_request", 400)
    return body, data


# ───────────────────────────── /app/v1/* ──────────────────────────────

async def handle_start(request: web.Request) -> web.Response:
    from config import BOT_USERNAME
    ip = client_ip(request)
    if not _start_global.allow("*") or not _start_per_ip.allow(ip):
        return _error("rate_limited", 429, retry_after=30)
    parsed = await _signed_json(request)
    if isinstance(parsed, web.Response):
        return parsed
    body, data = parsed
    device_key = data.get("device_key")
    if not valid_device_key(device_key):
        return _error("bad_device_key", 400)
    failure = check_signature(request, body, device_key, "k" + hashlib.sha256(device_key.encode()).hexdigest()[:24])
    if failure is not None:
        return failure
    env = clean_env(data.get("env"))
    if env_is_dirty(env):
        logger.warning("App login start from a flagged device (ip=%s): %s", ip, env)
        if require_clean_device():
            return _error("device_untrusted", 403)
    login_id = b64u(secrets.token_bytes(16))
    match_code = 10 + secrets.randbelow(90)
    # The Oferta edition the buyer saw on the login screen (app_terms.py);
    # logging in is its acceptance.
    import app_terms
    terms_version = app_terms.clean_version(data.get("terms_version"))
    await ensure_schema()
    async with database.pool.acquire() as conn:
        await conn.execute("DELETE FROM app_login_requests WHERE expires_at < now() - interval '1 day'")
        await conn.execute(
            """INSERT INTO app_login_requests (id, device_key, device_name, match_code, env, ip, expires_at,
                                               terms_version)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)""",
            login_id, device_key, clean_device_name(data.get("device_name")), match_code,
            json.dumps(env), ip, _utc(LOGIN_TTL), terms_version)
    return _json({
        "request_id": login_id,
        "bot_url": f"https://t.me/{BOT_USERNAME}?start={LOGIN_PREFIX}{login_id}",
        "match_code": match_code,
        "expires_in": LOGIN_TTL,
        "server_time": _now_ms(),
    })


async def handle_poll(request: web.Request) -> web.Response:
    parsed = await _signed_json(request, limit=1024)
    if isinstance(parsed, web.Response):
        return parsed
    body, data = parsed
    login_id = data.get("request_id")
    if not isinstance(login_id, str) or not _ID_RE.fullmatch(login_id):
        return _error("bad_request", 400)
    if not _poll_per_login.allow(login_id):
        return _error("rate_limited", 429, retry_after=2)
    await ensure_schema()
    async with database.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT device_key, status, expires_at FROM app_login_requests WHERE id = $1", login_id)
    if row is None:
        return _json({"status": "expired", "server_time": _now_ms()}, status=410)
    failure = check_signature(request, body, row["device_key"], "l" + login_id)
    if failure is not None:
        return failure
    now = _utc()
    if row["status"] == "pending":
        if row["expires_at"] <= now:
            return _json({"status": "expired", "server_time": _now_ms()}, status=410)
        return _json({"status": "pending", "server_time": _now_ms()}, status=202)
    if row["status"] != "approved":
        return _json({"status": row["status"], "server_time": _now_ms()}, status=410)

    async with database.pool.acquire() as conn:
        async with conn.transaction():
            claimed = await conn.fetchrow(
                """UPDATE app_login_requests SET status = 'consumed'
                   WHERE id = $1 AND status = 'approved'
                     AND expires_at > now() - make_interval(secs => $2)
                   RETURNING user_id, device_key, device_name, profile, env, terms_version""",
                login_id, float(APPROVED_PICKUP))
            if claimed is None:
                return _json({"status": "expired", "server_time": _now_ms()}, status=410)
            env = claimed["env"]
            env = json.loads(env) if isinstance(env, str) else (env or {})
            session_id, access, refresh = await _issue(
                conn, user_id=claimed["user_id"], device_key=claimed["device_key"],
                device_name=claimed["device_name"], profile=_profile(claimed), env=env,
                terms_version=claimed["terms_version"])
    profile = _profile(claimed)
    logger.info("App session %s opened for user %s (%s)", session_id, claimed["user_id"],
                claimed["device_name"])
    bot = request.app.get("bot")
    if bot is not None:
        import asyncio
        asyncio.create_task(_notify_new_device(bot, claimed["user_id"], session_id, claimed["device_name"]))
    return _json({
        "status": "approved",
        "access_token": access,
        "refresh_token": refresh,
        "access_expires_in": ACCESS_TTL,
        "user": {"id": claimed["user_id"], "first_name": profile.get("first_name") or ""},
        "server_time": _now_ms(),
    })


async def handle_refresh(request: web.Request) -> web.Response:
    parsed = await _signed_json(request, limit=2048)
    if isinstance(parsed, web.Response):
        return parsed
    body, data = parsed
    presented = data.get("refresh_token")
    if not isinstance(presented, str) or not _TOKEN_RE.fullmatch(presented) or not presented.startswith("ksr_"):
        return _error("session_ended", 401)
    digest = token_hash(presented)
    await ensure_schema()
    async with database.pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, device_key FROM app_sessions
               WHERE (refresh_hash = $1 OR prev_refresh_hash = $1) AND revoked_at IS NULL""", digest)
    if row is None:
        return _error("session_ended", 401)
    if not _refresh_per_session.allow(str(row["id"])):
        return _error("rate_limited", 429, retry_after=5)
    failure = check_signature(request, body, row["device_key"], f"s{row['id']}")
    if failure is not None:
        return failure
    env = clean_env(data.get("env"))
    if env_is_dirty(env):
        logger.warning("App refresh from a flagged device (session %s): %s", row["id"], env)
        if require_clean_device():
            await revoke(row["id"], "device_untrusted")
            return _error("device_untrusted", 403)

    access, refresh = new_token("a"), new_token("r")
    async with database.pool.acquire() as conn:
        async with conn.transaction():
            cur = await conn.fetchrow(
                """SELECT refresh_hash, prev_refresh_hash, rotated_at, refresh_expires, created_at, revoked_at
                   FROM app_sessions WHERE id = $1 FOR UPDATE""", row["id"])
            now = _utc()
            if cur is None or cur["revoked_at"] is not None:
                return _error("session_ended", 401)
            if cur["refresh_hash"] != digest:
                # An already-rotated token: fine right after a rotation whose
                # reply the phone never got; later it means two copies exist.
                if cur["prev_refresh_hash"] != digest or cur["rotated_at"] < _utc(-REFRESH_GRACE):
                    await conn.execute(
                        "UPDATE app_sessions SET revoked_at = now(), revoke_reason = 'refresh_reuse' WHERE id = $1",
                        row["id"])
                    logger.warning("App session %s revoked: refresh token reused", row["id"])
                    return _error("session_ended", 401)
            if cur["refresh_expires"] <= now or cur["created_at"] <= _utc(-SESSION_MAX_AGE):
                return _error("session_ended", 401)
            await conn.execute(
                """UPDATE app_sessions
                   SET access_hash = $2, access_expires = $3, prev_refresh_hash = refresh_hash,
                       refresh_hash = $4, refresh_expires = $5, rotated_at = now(), last_seen = now(),
                       env = $6::jsonb
                   WHERE id = $1""",
                row["id"], token_hash(access), _utc(ACCESS_TTL), token_hash(refresh),
                min(_utc(REFRESH_TTL), cur["created_at"] + timedelta(seconds=SESSION_MAX_AGE)),
                json.dumps(env))
    return _json({"access_token": access, "refresh_token": refresh,
                  "access_expires_in": ACCESS_TTL, "server_time": _now_ms()})


async def handle_logout(request: web.Request) -> web.Response:
    session = await authenticate(request)
    if isinstance(session, web.Response):
        return session
    await revoke(session.id, "logout")
    return _json({"ok": True})


async def handle_sessions(request: web.Request) -> web.Response:
    session = await authenticate(request)
    if isinstance(session, web.Response):
        return session
    async with database.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, device_name, created_at, last_seen FROM app_sessions
               WHERE user_id = $1 AND revoked_at IS NULL AND refresh_expires > now()
               ORDER BY last_seen DESC""", session.user_id)
    return _json({"sessions": [{
        "id": r["id"], "device_name": r["device_name"],
        "created_at": r["created_at"].isoformat(), "last_seen": r["last_seen"].isoformat(),
        "current": r["id"] == session.id,
    } for r in rows]})


async def handle_revoke_others(request: web.Request) -> web.Response:
    session = await authenticate(request)
    if isinstance(session, web.Response):
        return session
    async with database.pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE app_sessions SET revoked_at = now(), revoke_reason = 'revoked_by_user'
               WHERE user_id = $1 AND id <> $2 AND revoked_at IS NULL""",
            session.user_id, session.id)
    return _json({"ok": True, "revoked": int(result.split()[-1])})


# ───────────────────────────── the shop view ──────────────────────────────
# The app shows the shop itself — the Mini App page — inside a WebView. That
# page authenticates the Telegram way (Authorization: tma <initData>), so the
# signed-in app asks for initData minted here for its own session: same
# format and HMAC as Telegram's (the server holds the bot token), plus
# `ks_sid`. webapp_server accepts it only on the shop's /api/*, only while
# the session is live, and for at most WEB_TTL.

WEB_TTL = 12 * 3600


def mint_web_init_data(session: AppSession, bot_token: str, now: float | None = None) -> str:
    import hmac as _hmac
    from urllib.parse import quote, urlencode
    profile = session.profile or {}
    user = {k: v for k, v in {
        "id": session.user_id,
        "first_name": profile.get("first_name") or "",
        "last_name": profile.get("last_name") or "",
        "username": profile.get("username") or "",
        "language_code": profile.get("language_code") or "",
        "allows_write_to_pm": True,
    }.items() if v != ""}
    fields = {
        "auth_date": str(int(now if now is not None else time.time())),
        "ks_sid": str(session.id),
        "user": json.dumps(user, ensure_ascii=False, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = _hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = _hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields, quote_via=quote)


async def web_session_ok(sid, user_id: int, auth_date) -> bool:
    """Minted initData is good while its app session is: not revoked, not
    expired, the same buyer, and no older than WEB_TTL."""
    try:
        sid, auth = int(sid), int(auth_date)
    except (TypeError, ValueError):
        return False
    if not 0 <= time.time() - auth <= WEB_TTL:
        return False
    await ensure_schema()
    async with database.pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT user_id FROM app_sessions
               WHERE id = $1 AND revoked_at IS NULL AND refresh_expires > now()""", sid)
    return row is not None and row["user_id"] == user_id


async def handle_web_session(request: web.Request) -> web.Response:
    session = await authenticate(request)
    if isinstance(session, web.Response):
        return session
    from config import BOT_TOKEN
    return _json({"init_data": mint_web_init_data(session, request.app.get("bot_token") or BOT_TOKEN),
                  "expires_in": WEB_TTL, "server_time": _now_ms()})


def add_routes(app: web.Application) -> None:
    app.router.add_post("/app/v1/web-session", handle_web_session)
    app.router.add_post("/app/v1/auth/start", handle_start)
    app.router.add_post("/app/v1/auth/poll", handle_poll)
    app.router.add_post("/app/v1/auth/refresh", handle_refresh)
    app.router.add_post("/app/v1/auth/logout", handle_logout)
    app.router.add_get("/app/v1/sessions", handle_sessions)
    app.router.add_post("/app/v1/sessions/revoke-others", handle_revoke_others)


# ───────────────────────────── the bot ──────────────────────────────

_TEXTS = {
    "uz": {
        "confirm": ("📱 <b>Ketoshop ilovasiga kirish</b>\n\n"
                    "Qurilma: <b>{device}</b>\n\n"
                    "Ilova ekranida ko'rsatilgan raqamni bosing 👇\n\n"
                    "⚠️ Bu so'rovni o'zingiz yubormagan bo'lsangiz, «❌ Men emasman»ni bosing. "
                    "Bu xabarni hech kimga yubormang."),
        "not_me": "❌ Men emasman",
        "approved": "✅ Tasdiqlandi. Ilovaga qayting — kirish o'zi yakunlanadi.",
        "wrong": ("❌ Raqam mos kelmadi. Xavfsizlik uchun bu so'rov bekor qilindi — "
                  "ilovada qaytadan urinib ko'ring."),
        "denied": "🚫 So'rov bekor qilindi. Hisobingizga hech kim kira olmaydi.",
        "expired": "⌛ Bu kirish so'rovi eskirgan. Ilovada «Telegram orqali kirish»ni qayta bosing.",
        "new_device": ("🔐 Hisobingizga yangi qurilmadan kirildi: <b>{device}</b> ({time}).\n\n"
                       "Bu siz bo'lmasangiz, «🚫 Chiqarib yuborish»ni bosing."),
        "kick": "🚫 Chiqarib yuborish",
        "kicked": "✅ Qurilma hisobingizdan chiqarib yuborildi.",
        "kick_gone": "Bu qurilma allaqachon chiqib ketgan.",
    },
    "ru": {
        "confirm": ("📱 <b>Вход в приложение Ketoshop</b>\n\n"
                    "Устройство: <b>{device}</b>\n\n"
                    "Нажмите число, которое показано в приложении 👇\n\n"
                    "⚠️ Если вход запросили не вы, нажмите «❌ Это не я». "
                    "Никому не пересылайте это сообщение."),
        "not_me": "❌ Это не я",
        "approved": "✅ Подтверждено. Вернитесь в приложение — вход завершится сам.",
        "wrong": "❌ Число не совпало. Для безопасности запрос отменён — попробуйте ещё раз в приложении.",
        "denied": "🚫 Запрос отменён. Никто не войдёт в ваш аккаунт.",
        "expired": "⌛ Этот запрос на вход устарел. Нажмите «Войти через Telegram» в приложении ещё раз.",
        "new_device": ("🔐 В ваш аккаунт вошли с нового устройства: <b>{device}</b> ({time}).\n\n"
                       "Если это не вы, нажмите «🚫 Отключить устройство»."),
        "kick": "🚫 Отключить устройство",
        "kicked": "✅ Устройство отключено от вашего аккаунта.",
        "kick_gone": "Это устройство уже отключено.",
    },
}


def text(key: str, lang: str, **kwargs) -> str:
    """uz / ru as written; uz_cyr is the Latin text transliterated."""
    base = _TEXTS["ru" if lang == "ru" else "uz"][key]
    if lang == "uz_cyr":
        import translit
        base = translit.lat_to_cyr(base)
    return base.format(**kwargs) if kwargs else base


def is_app_login_event(event) -> bool:
    """/start applogin_… and its buttons — never held behind the channel gate:
    logging in is not shopping (the API's own gate still applies after)."""
    if isinstance(event, Message):
        return (event.text or "").strip().startswith(f"/start {LOGIN_PREFIX}")
    if isinstance(event, CallbackQuery):
        return (event.data or "").startswith(("applogin:", "appsess:"))
    return False


async def _buyer_lang(tg_user) -> str:
    from database import get_user
    user = await get_user(tg_user.id)
    if user and user.get("language") in ("uz", "uz_cyr", "ru"):
        return user["language"]
    return "ru" if (tg_user.language_code or "").startswith("ru") else "uz"


def _tashkent_time() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=5)).strftime("%d.%m %H:%M")


@router.message(CommandStart(deep_link=True, magic=F.args.startswith(LOGIN_PREFIX)), F.chat.type == "private")
async def on_login_link(message: Message, command: CommandObject) -> None:
    lang = await _buyer_lang(message.from_user)
    login_id = (command.args or "")[len(LOGIN_PREFIX):]
    row = None
    if _ID_RE.fullmatch(login_id):
        await ensure_schema()
        async with database.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT device_name, match_code FROM app_login_requests
                   WHERE id = $1 AND status = 'pending' AND expires_at > now()""", login_id)
    if row is None:
        await message.answer(text("expired", lang))
        return
    right = int(row["match_code"])
    choices = {right}
    while len(choices) < 3:
        choices.add(10 + secrets.randbelow(90))
    order = sorted(choices, key=lambda _: secrets.randbelow(1000))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(n), callback_data=f"applogin:{login_id}:{n}") for n in order],
        [InlineKeyboardButton(text=text("not_me", lang), callback_data=f"applogin:{login_id}:0")],
    ])
    await message.answer(text("confirm", lang, device=html.escape(row["device_name"])), reply_markup=keyboard)


@router.callback_query(F.data.startswith("applogin:"))
async def on_login_choice(callback: CallbackQuery) -> None:
    lang = await _buyer_lang(callback.from_user)
    parts = (callback.data or "").split(":")
    if len(parts) != 3 or not _ID_RE.fullmatch(parts[1]) or not parts[2].isdigit():
        await callback.answer()
        return
    login_id, picked = parts[1], int(parts[2])
    user = callback.from_user
    profile = {"id": user.id, "first_name": user.first_name or "", "last_name": user.last_name or "",
               "username": user.username or "", "language_code": user.language_code or ""}
    await ensure_schema()
    async with database.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT match_code FROM app_login_requests
                   WHERE id = $1 AND status = 'pending' AND expires_at > now() FOR UPDATE""", login_id)
            if row is None:
                outcome = "expired"
            elif picked != 0 and picked == int(row["match_code"]):
                await conn.execute(
                    """UPDATE app_login_requests SET status = 'approved', user_id = $2,
                              profile = $3::jsonb, decided_at = now() WHERE id = $1""",
                    login_id, user.id, json.dumps(profile))
                outcome = "approved"
            else:
                await conn.execute(
                    "UPDATE app_login_requests SET status = 'rejected', decided_at = now() WHERE id = $1",
                    login_id)
                outcome = "denied" if picked == 0 else "wrong"
    if outcome == "approved":
        # A first-time buyer gets the same users row and welcome as /start.
        try:
            from handlers.start import ensure_registered
            await ensure_registered(callback.bot, user)
        except Exception:
            logger.exception("App login: registering user %s failed", user.id)
    else:
        logger.info("App login %s for user %s: %s", login_id, user.id, outcome)
    await callback.answer()
    try:
        await callback.message.edit_text(text(outcome, lang), reply_markup=None)
    except Exception:
        await callback.bot.send_message(user.id, text(outcome, lang))


async def _notify_new_device(bot, user_id: int, session_id: int, device_name: str) -> None:
    """Every new session is announced in the chat with a one-tap revoke."""
    try:
        from database import get_user_language
        lang = await get_user_language(user_id)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=text("kick", lang), callback_data=f"appsess:off:{session_id}")]])
        await bot.send_message(user_id, text("new_device", lang, device=html.escape(device_name),
                                             time=_tashkent_time()), reply_markup=keyboard)
    except Exception:
        logger.warning("New-device notice to %s failed", user_id, exc_info=True)


@router.callback_query(F.data.startswith("appsess:off:"))
async def on_kick_device(callback: CallbackQuery) -> None:
    lang = await _buyer_lang(callback.from_user)
    raw = (callback.data or "").rsplit(":", 1)[-1]
    done = raw.isdigit() and await revoke(int(raw), "revoked_from_bot", user_id=callback.from_user.id)
    await callback.answer(text("kicked" if done else "kick_gone", lang), show_alert=True)
    if done:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
