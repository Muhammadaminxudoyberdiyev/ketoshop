"""📲 Android ilovasiga push xabarlar (Firebase Cloud Messaging).

Egasi (2026-11-21): "push bildirishnoma ... umumiy feature qilib qo'shsak
keyin ... APK ni yangilamasdan qo'shsa bo'ladigan", "apkni yangilashga deyarli
99.99% zarurat bo'lmasin"; tanlovlari: Firebase (FCM) va "ilovasi borga faqat
push".

Ilova hech qanday xabar turini bilmaydi. Har bir push — data-xabar: sarlavha,
matn, rasm, bosilganda ochiladigan sahifa va telefon bildirishnoma bo'limi
(kanal) nomi; ilova ularni ko'rsatadi, kanalni o'zi yaratadi. Yangi tur
qo'shish = shu fayldagi CATEGORIES ga qator + uni chaqiradigan kod.

  * POST /app/v1/push/register  — ilova (imzolangan so'rov) FCM tokenini beradi;
  * deliver(uid, kind, texts, url, image) — bitta xaridorga, uning tilida;
  * broadcast(uids, ...)                  — ko'pchilikka (100 000+), parallel;
  * app_user_ids(uids)                    — kimga push boradi (bot o'rniga).

Kalit: Firebase «service account» JSON — admin paneldan yuklanadi
(app_settings.fcm_service_account) yoki FCM_SERVICE_ACCOUNT_JSON muhitda.
Kalitsiz hammasi jim o'chiq: deliver False qaytaradi, xabar botdan ketadi.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass

import aiohttp
from aiohttp import web

import database

logger = logging.getLogger(__name__)

# id → (telefon sozlamalarida ko'rinadigan bo'lim nomi, muhimligi)
# importance: "high" (ovoz + ekranda chiqadi), "default" (ovoz), "low" (jim).
CATEGORIES: dict[str, tuple[dict[str, str], str]] = {
    "buyurtma": ({"uz": "Buyurtmalar", "ru": "Заказы"}, "high"),
    "aksiya": ({"uz": "Aksiyalar va chegirmalar", "ru": "Акции и скидки"}, "high"),
    "yangi_mahsulot": ({"uz": "Yangi mahsulotlar", "ru": "Новинки"}, "default"),
    "yangilik": ({"uz": "Yangiliklar", "ru": "Новости"}, "default"),
    "eslatma": ({"uz": "Eslatmalar", "ru": "Напоминания"}, "default"),
    "oyin": ({"uz": "O'yinlar", "ru": "Игры"}, "low"),
}
DEFAULT_KIND = "yangilik"

SETTING = "fcm_service_account"
SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
CONCURRENCY = 64
TTL_SECONDS = 24 * 3600
MAX_TITLE, MAX_BODY = 120, 600

_ready = False
_http: aiohttp.ClientSession | None = None
_sa_cache: tuple[float, dict | None] = (0.0, None)
_token_cache: tuple[float, str] = (0.0, "")


# ─────────────────────────────── schema ─────────────────────────────────────

async def ensure_schema() -> None:
    global _ready
    if _ready:
        return
    async with database.pool.acquire() as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_push_devices (
                session_id   BIGINT PRIMARY KEY,
                user_id      BIGINT NOT NULL,
                token        TEXT NOT NULL UNIQUE,
                enabled      BOOLEAN NOT NULL DEFAULT TRUE,
                app_build    INTEGER,
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                last_sent_at TIMESTAMPTZ,
                last_error   TEXT
            )""")
        await conn.execute("CREATE INDEX IF NOT EXISTS app_push_devices_user ON app_push_devices (user_id)")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_push_log (
                id         BIGSERIAL PRIMARY KEY,
                kind       TEXT NOT NULL,
                title      TEXT NOT NULL,
                url        TEXT,
                audience   TEXT NOT NULL,
                sent       INTEGER NOT NULL DEFAULT 0,
                failed     INTEGER NOT NULL DEFAULT 0,
                created_by TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                done_at    TIMESTAMPTZ
            )""")
    _ready = True


# A device counts while its app session is alive (logout / «Chiqarib
# yuborish» / expiry end it) and the phone allows our notifications.
_ACTIVE = """FROM app_push_devices d
             JOIN app_sessions s ON s.id = d.session_id
             WHERE s.revoked_at IS NULL AND s.refresh_expires > now() AND d.enabled"""


async def app_user_ids(user_ids: list[int] | None = None) -> set[int]:
    """Who gets pushes instead of bot messages."""
    if not await configured():
        return set()
    await ensure_schema()
    async with database.pool.acquire() as conn:
        if user_ids is None:
            rows = await conn.fetch(f"SELECT DISTINCT d.user_id {_ACTIVE}")
        else:
            rows = await conn.fetch(f"SELECT DISTINCT d.user_id {_ACTIVE} AND d.user_id = ANY($1::bigint[])",
                                    list(user_ids))
    return {r["user_id"] for r in rows}


async def _tokens(user_ids: list[int]) -> dict[int, list[str]]:
    await ensure_schema()
    async with database.pool.acquire() as conn:
        rows = await conn.fetch(f"SELECT d.user_id, d.token {_ACTIVE} AND d.user_id = ANY($1::bigint[])",
                                list(user_ids))
    out: dict[int, list[str]] = {}
    for r in rows:
        out.setdefault(r["user_id"], []).append(r["token"])
    return out


async def stats() -> dict:
    await ensure_schema()
    async with database.pool.acquire() as conn:
        row = await conn.fetchrow(f"""SELECT count(*) AS devices, count(DISTINCT d.user_id) AS users {_ACTIVE}""")
        off = await conn.fetchval("""SELECT count(*) FROM app_push_devices d JOIN app_sessions s ON s.id = d.session_id
                                     WHERE s.revoked_at IS NULL AND s.refresh_expires > now() AND NOT d.enabled""")
        log = await conn.fetch("""SELECT id, kind, title, audience, sent, failed, created_by, created_at, done_at
                                  FROM app_push_log ORDER BY id DESC LIMIT 20""")
    sa = await _service_account()
    return {
        "configured": sa is not None,
        "project_id": (sa or {}).get("project_id", ""),
        "devices": row["devices"], "users": row["users"], "notifications_off": off,
        "categories": [{"id": k, "name": v[0]["uz"]} for k, v in CATEGORIES.items()],
        "log": [dict(r, created_at=r["created_at"].isoformat(),
                     done_at=r["done_at"].isoformat() if r["done_at"] else None) for r in log],
    }


# ─────────────────────────────── the key ────────────────────────────────────

def parse_service_account(raw: str) -> dict:
    """The JSON Firebase gives under «Generate new private key» (raw or
    base64). Raises ValueError with a reason the admin can act on."""
    raw = (raw or "").strip()
    if raw and not raw.startswith("{"):
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except Exception:
            raise ValueError("JSON emas") from None
    try:
        data = json.loads(raw)
    except Exception:
        raise ValueError("JSON emas") from None
    if not isinstance(data, dict) or data.get("type") != "service_account":
        raise ValueError("bu «service account» kaliti emas (google-services.json emas, Service accounts bo'limidagisi)")
    for field in ("project_id", "client_email", "private_key", "token_uri"):
        if not data.get(field):
            raise ValueError(f"«{field}» yo'q")
    from cryptography.hazmat.primitives import serialization
    try:
        serialization.load_pem_private_key(data["private_key"].encode(), password=None)
    except Exception:
        raise ValueError("private_key o'qilmadi") from None
    return data


async def _service_account() -> dict | None:
    global _sa_cache
    at, cached = _sa_cache
    if time.monotonic() - at < 60:
        return cached
    raw = os.getenv("FCM_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        try:
            await ensure_schema()
            async with database.pool.acquire() as conn:
                raw = await conn.fetchval("SELECT value FROM app_settings WHERE key = $1", SETTING) or ""
        except Exception:
            logger.exception("push: reading the key failed")
            raw = ""
    try:
        sa = parse_service_account(raw) if raw else None
    except ValueError as e:
        logger.error("push: stored key unusable: %s", e)
        sa = None
    _sa_cache = (time.monotonic(), sa)
    return sa


async def configured() -> bool:
    return await _service_account() is not None


async def save_service_account(raw: str) -> dict:
    global _sa_cache, _token_cache
    data = parse_service_account(raw)
    await ensure_schema()
    async with database.pool.acquire() as conn:
        await conn.execute("""INSERT INTO app_settings (key, value) VALUES ($1, $2)
                              ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
                           SETTING, json.dumps(data))
    _sa_cache = (0.0, None)
    _token_cache = (0.0, "")
    return {"project_id": data["project_id"], "client_email": data["client_email"]}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_assertion(sa: dict, now: float | None = None) -> str:
    """RS256 JWT for Google's OAuth token endpoint (service-account flow)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    iat = int(now if now is not None else time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = _b64url(json.dumps({"iss": sa["client_email"], "scope": SCOPE, "aud": sa["token_uri"],
                                 "iat": iat, "exp": iat + 3600}).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    signature = key.sign(f"{header}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{claims}.{_b64url(signature)}"


async def _session() -> aiohttp.ClientSession:
    global _http
    if _http is None or _http.closed:
        _http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),
                                      connector=aiohttp.TCPConnector(limit=CONCURRENCY))
    return _http


async def _access_token(sa: dict, force: bool = False) -> str:
    global _token_cache
    at, token = _token_cache
    if token and not force and time.time() - at < 50 * 60:
        return token
    http = await _session()
    async with http.post(sa["token_uri"], data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": make_assertion(sa)}) as r:
        body = await r.json(content_type=None)
        if r.status != 200 or "access_token" not in body:
            raise RuntimeError(f"FCM auth failed: {r.status} {str(body)[:200]}")
    _token_cache = (time.time(), body["access_token"])
    return body["access_token"]


# ─────────────────────────────── messages ───────────────────────────────────

@dataclass
class Texts:
    """Title/body per language. uz_cyr is made from uz when not given."""
    title: dict[str, str]
    body: dict[str, str]

    def for_lang(self, lang: str) -> tuple[str, str]:
        return _localize(self.title, lang), _localize(self.body, lang)


def _localize(texts: dict[str, str], lang: str) -> str:
    if lang in texts and texts[lang]:
        return texts[lang]
    if lang == "ru":
        return texts.get("ru") or texts.get("uz", "")
    text = texts.get("uz") or texts.get("ru", "")
    if lang == "uz_cyr":
        import translit
        return translit.lat_to_cyr(text)
    return text


def _alphabet(text: str, lang: str) -> str:
    """New Latin (Ö Ğ Ş Ç) for Latin-Uzbek readers when the switch is on —
    the same rule the bot applies to everything it sends."""
    if lang != "uz":
        return text
    try:
        import alphabet
        if alphabet.is_on():
            from translit import to_new_latin
            return to_new_latin(text)
    except Exception:
        pass
    return text


_URL_RE = re.compile(r"^/[^/\\\s][^\s]*$|^/$")


def clean_url(url: str) -> str:
    """Where a tap goes: a path on our own site («/?product=12», «/?game=quiz»,
    «/?recipe=slug»). Full https://<our host>/… links are cut to the path;
    anything else is dropped (the app opens the shop's home)."""
    url = (url or "").strip()
    if not url:
        return ""
    from config import WEBAPP_URL
    base = (WEBAPP_URL or "").rstrip("/")
    if base and url.startswith(base):
        url = url[len(base):] or "/"
    return url if _URL_RE.match(url) else ""


def clean_image(image: str) -> str:
    """An image the phone may download: our own /img/N or https on our host."""
    image = (image or "").strip()
    if not image:
        return ""
    from config import WEBAPP_URL
    base = (WEBAPP_URL or "").rstrip("/")
    if image.startswith("/") and not image.startswith("//"):
        return base + image if base else ""
    return image if base and image.startswith(base + "/") else ""


def build_data(kind: str, lang: str, texts: Texts, url: str, image: str, msg_id: int, user_id: int) -> dict[str, str]:
    """The data message the app renders (FCM data values must be strings)."""
    names, importance = CATEGORIES.get(kind, CATEGORIES[DEFAULT_KIND])
    title, body = texts.for_lang(lang)
    channel_name = _localize(names, lang)
    return {
        "v": "1",
        "id": str(msg_id),
        "kind": kind,
        "ch": kind if kind in CATEGORIES else DEFAULT_KIND,
        "ch_name": _alphabet(channel_name, lang),
        "ch_imp": importance,
        "title": _alphabet(title, lang)[:MAX_TITLE],
        "body": _alphabet(body, lang)[:MAX_BODY],
        "image": clean_image(image),
        "url": clean_url(url),
        "uid": str(user_id),
    }


async def _send(sa: dict, token: str, data: dict[str, str]) -> str:
    """One device: "ok", "gone" (token dead — forget it) or "error"."""
    http = await _session()
    url = f"https://fcm.googleapis.com/v1/projects/{sa['project_id']}/messages:send"
    payload = {"message": {"token": token, "data": data,
                           "android": {"priority": "high", "ttl": f"{TTL_SECONDS}s"}}}
    refresh = False
    for attempt in range(4):
        try:
            access = await _access_token(sa, force=refresh)
            refresh = False
            async with http.post(url, json=payload, headers={"Authorization": f"Bearer {access}"}) as r:
                if r.status == 200:
                    return "ok"
                body = await r.json(content_type=None)
                status = ((body or {}).get("error") or {}).get("status", "")
                detail = json.dumps(body)[:300]
                if r.status == 404 or status in ("NOT_FOUND", "UNREGISTERED") or "UNREGISTERED" in detail:
                    return "gone"
                if r.status == 400 and "registration token" in detail.lower():
                    return "gone"
                if r.status == 401:
                    refresh = True
                    continue
                if r.status in (429, 500, 502, 503, 504):
                    try:
                        wait = float(r.headers.get("Retry-After", 0) or 0)
                    except ValueError:
                        wait = 0.0
                    await asyncio.sleep(min(30.0, 2 ** attempt + wait))
                    continue
                logger.warning("push: FCM %s %s", r.status, detail)
                return "error"
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await asyncio.sleep(2 ** attempt)
    return "error"


async def _forget(tokens: list[str]) -> None:
    if not tokens:
        return
    async with database.pool.acquire() as conn:
        await conn.execute("DELETE FROM app_push_devices WHERE token = ANY($1::text[])", tokens)


async def broadcast(user_ids: list[int], kind: str, texts: Texts, url: str = "", image: str = "",
                    audience: str = "", created_by: str = "", log: bool = True) -> dict:
    """Push to every device of these buyers, each in their own language.
    Returns {"users": n reached, "sent": devices ok, "failed": devices failed}."""
    sa = await _service_account()
    if sa is None or not user_ids:
        return {"users": 0, "sent": 0, "failed": 0, "reached": set()}
    await ensure_schema()
    msg_id = 0
    if log:
        async with database.pool.acquire() as conn:
            msg_id = await conn.fetchval(
                """INSERT INTO app_push_log (kind, title, url, audience, created_by)
                   VALUES ($1, $2, $3, $4, $5) RETURNING id""",
                kind, (texts.title.get("uz") or texts.title.get("ru") or "")[:200], clean_url(url),
                audience or f"{len(user_ids)} ta", created_by or None)
    else:
        msg_id = int(time.time())
    tokens = await _tokens(user_ids)
    langs = await database.get_user_languages(list(tokens))
    sem = asyncio.Semaphore(CONCURRENCY)
    gone: list[str] = []
    reached: set[int] = set()
    counts = {"ok": 0, "error": 0}

    async def one(uid: int, token: str):
        async with sem:
            result = await _send(sa, token, build_data(kind, langs.get(uid, "uz"), texts, url, image, msg_id, uid))
        if result == "ok":
            counts["ok"] += 1
            reached.add(uid)
        elif result == "gone":
            gone.append(token)
        else:
            counts["error"] += 1

    await asyncio.gather(*(one(uid, tok) for uid, toks in tokens.items() for tok in toks))
    await _forget(gone)
    async with database.pool.acquire() as conn:
        if reached:
            await conn.execute("UPDATE app_push_devices SET last_sent_at = now() WHERE user_id = ANY($1::bigint[])",
                               list(reached))
        if log:
            await conn.execute("UPDATE app_push_log SET sent = $2, failed = $3, done_at = now() WHERE id = $1",
                               msg_id, counts["ok"], counts["error"] + len(gone))
    return {"users": len(reached), "sent": counts["ok"], "failed": counts["error"] + len(gone), "reached": reached}


async def deliver(user_id: int, kind: str, texts: Texts, url: str = "", image: str = "") -> bool:
    """One buyer. True when at least one of their phones took it — the
    caller then skips the bot message («ilovasi borga faqat push»)."""
    try:
        result = await broadcast([user_id], kind, texts, url, image, log=False)
        return bool(result["reached"])
    except Exception:
        logger.exception("push: deliver to %s failed", user_id)
        return False


# ─────────────────────────────── the app's door ─────────────────────────────

async def handle_register(request: web.Request) -> web.Response:
    """POST /app/v1/push/register {token, enabled, build} — signed app request."""
    import app_auth
    session = await app_auth.authenticate(request)
    if isinstance(session, web.Response):
        return session
    try:
        body = json.loads((await app_auth.read_body(request)) or b"{}")
    except Exception:
        return web.json_response({"error": "bad_json"}, status=400)
    token = str(body.get("token") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_:\-]{20,4096}", token):
        return web.json_response({"error": "bad_token"}, status=400)
    enabled = bool(body.get("enabled", True))
    build = body.get("build") if isinstance(body.get("build"), int) else None
    await ensure_schema()
    async with database.pool.acquire() as conn:
        async with conn.transaction():
            # A token belongs to one phone; it may have moved to a new login.
            await conn.execute("DELETE FROM app_push_devices WHERE token = $1 AND session_id <> $2", token, session.id)
            await conn.execute(
                """INSERT INTO app_push_devices (session_id, user_id, token, enabled, app_build, updated_at)
                   VALUES ($1, $2, $3, $4, $5, now())
                   ON CONFLICT (session_id) DO UPDATE SET token = EXCLUDED.token, user_id = EXCLUDED.user_id,
                       enabled = EXCLUDED.enabled, app_build = EXCLUDED.app_build, updated_at = now(),
                       last_error = NULL""",
                session.id, session.user_id, token, enabled, build)
    return web.json_response({"ok": True, "configured": await configured()},
                             headers={"Cache-Control": "no-store"})


def add_routes(app: web.Application) -> None:
    app.router.add_post("/app/v1/push/register", handle_register)
