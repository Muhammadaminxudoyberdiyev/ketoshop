"""📦 Ilovaning yangi versiyasi — serverning o'zidan, bitta tugma bilan.

Egasi (2026-11-21): "apkni yangilang deb bitta tugma bilan yangilash
imkoniyatini qo'shsak ... alohida ularga jo'natib chiqmasdan ilovani o'zidan".

  * admin paneldan yangi APK yuklanadi (versiya + build raqami + izoh);
  * GET /app/download/ketoshop-<build>.apk — o'sha fayl (ochiq: APK sir emas);
  * /app/v1/config uni e'lon qiladi (app_config.build): latest_build,
    update_url, apk_sha256, apk_size — ilova yuklab oladi, SHA-256 ni
    tekshiradi va Android'ning «O'rnatish» oynasini ochadi. Android o'zi ham
    imzo boshqacha bo'lsa yangilashni rad etadi.

Fayl bazada (bytea) turadi, bir nusxasi xotirada — har yuklab olishda baza
o'qilmaydi.
"""
from __future__ import annotations

import hashlib
import logging
import zipfile
from io import BytesIO

from aiohttp import web

import database

logger = logging.getLogger(__name__)

MAX_APK = 60 * 1024 * 1024
_ready = False
_blob: dict[int, bytes] = {}
_latest_cache: tuple[float, dict | None] = (0.0, None)


async def ensure_schema() -> None:
    global _ready
    if _ready:
        return
    async with database.pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_releases (
                build       INTEGER PRIMARY KEY,
                version     TEXT NOT NULL,
                apk         BYTEA NOT NULL,
                sha256      TEXT NOT NULL,
                size        INTEGER NOT NULL,
                notes_uz    TEXT,
                notes_ru    TEXT,
                min_build   INTEGER,
                uploaded_by TEXT,
                uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
    _ready = True


def check_apk(data: bytes) -> None:
    """Enough to catch a wrong file: a zip with an Android manifest and a
    signature. The phone checks the signer itself."""
    if not data or len(data) > MAX_APK:
        raise ValueError("fayl bo'sh yoki juda katta")
    try:
        names = set(zipfile.ZipFile(BytesIO(data)).namelist())
    except zipfile.BadZipFile:
        raise ValueError("bu APK emas") from None
    if "AndroidManifest.xml" not in names or "classes.dex" not in names:
        raise ValueError("bu APK emas")


async def latest() -> dict | None:
    """The newest uploaded release (without the bytes), cached for 30 s."""
    global _latest_cache
    import time
    at, cached = _latest_cache
    if time.monotonic() - at < 30:
        return cached
    try:
        await ensure_schema()
        async with database.pool.acquire() as conn:
            row = await conn.fetchrow("""SELECT build, version, sha256, size, notes_uz, notes_ru, min_build, uploaded_at
                                         FROM app_releases ORDER BY build DESC LIMIT 1""")
        cached = dict(row) if row else None
    except Exception:
        logger.exception("app_release: latest failed")
        cached = None
    _latest_cache = (time.monotonic(), cached)
    return cached


async def save(data: bytes, version: str, build: int, notes_uz: str = "", notes_ru: str = "",
               min_build: int | None = None, uploaded_by: str = "") -> dict:
    global _latest_cache
    check_apk(data)
    if build <= 0:
        raise ValueError("build raqami musbat bo'lsin")
    current = await latest()
    if current and build <= current["build"]:
        raise ValueError(f"build {current['build']} dan katta bo'lsin")
    sha = hashlib.sha256(data).hexdigest()
    await ensure_schema()
    async with database.pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO app_releases (build, version, apk, sha256, size, notes_uz, notes_ru, min_build, uploaded_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            build, version.strip()[:32], data, sha, len(data), notes_uz.strip() or None, notes_ru.strip() or None,
            min_build, uploaded_by or None)
        # Keep the newest three; older APKs only take space.
        await conn.execute("""DELETE FROM app_releases WHERE build NOT IN
                              (SELECT build FROM app_releases ORDER BY build DESC LIMIT 3)""")
    _latest_cache = (0.0, None)
    _blob.clear()
    return {"build": build, "version": version, "sha256": sha, "size": len(data)}


async def handle_download(request: web.Request) -> web.StreamResponse:
    try:
        build = int(request.match_info["build"])
    except (KeyError, ValueError):
        raise web.HTTPNotFound
    data = _blob.get(build)
    if data is None:
        await ensure_schema()
        async with database.pool.acquire() as conn:
            data = await conn.fetchval("SELECT apk FROM app_releases WHERE build = $1", build)
        if data is None:
            raise web.HTTPNotFound
        data = bytes(data)
        _blob.clear()
        _blob[build] = data
    return web.Response(body=data, content_type="application/vnd.android.package-archive", headers={
        "Content-Disposition": f'attachment; filename="Ketoshop-{build}.apk"',
        "Cache-Control": "public, max-age=31536000, immutable",
    })


def add_routes(app: web.Application) -> None:
    app.router.add_get(r"/app/download/ketoshop-{build:\d+}.apk", handle_download)
