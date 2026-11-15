"""Saytdagi fon musiqasi — haqiqiy yozuvlar (egasi, 2026-11-15: "fondagi saytdagi
klassik musiqa ham claude tomonidan yozilgan emas balki original internetdan
olingan top classic musiqalar bo'lsin, yuqori sifatli").

Faqat erkin litsenziyali yozuvlar — Wikimedia Commons'da public domain yoki
CC0 (muallifni ko'rsatish majburiyati yo'q); har biri 2026-11-15 da Commons
API orqali tekshirilgan (LicenseShortName). Fayllar repoga qo'yilmaydi.

Ikki yo'l:
  * SITE_MUSIC_CONTACT berilgan bo'lsa (Wikimedia qoidasi: server so'rovining
    User-Agent'ida aloqa — sayt manzili yoki email), server Commons'ning MP3
    nusxasini bir marta yuklab CACHE_DIR ga saqlaydi va /music/<nom>.mp3 dan
    o'zi beradi (Range — iOS uchun — FileResponse orqali).
  * Berilmagan bo'lsa — server Wikimedia'ga umuman murojaat qilmaydi; sahifa
    fayllarni xaridorning telefoni orqali to'g'ridan-to'g'ri upload.wikimedia.org
    dan oladi (oddiy brauzer so'rovi). 2026-11-15: aloqasiz server so'rovi
    403 oldi.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

import aiohttp
from aiohttp import web

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("SITE_MUSIC_DIR", "/tmp/ketoshop-music"))
# Egasi, 2026-11-15: "ruxsat beraman" — aloqa sifatida do'konning ochiq sayt
# manzili (config.WEBAPP_URL); SITE_MUSIC_CONTACT bilan almashtirsa bo'ladi.
CONTACT = (os.getenv("SITE_MUSIC_CONTACT") or os.getenv("WEBAPP_URL") or "").strip()
FAIL_PAUSE = 3600                     # yuklab bo'lmadi — bir soat qayta urinmaymiz
_C = "https://upload.wikimedia.org/wikipedia/commons/"

# nom → (manba, nomi uz, nomi ru, litsenziya)
TRACKS: dict[str, tuple[str, str, str, str]] = {
    "moonlight": (
        _C + "transcoded/4/48/Ludwig_van_Beethoven_-_sonata_no._14_in_c_sharp_minor_%27moonlight%27%2C_op._27_no._2_-"
             "_i._adagio_sostenuto.ogg/Ludwig_van_Beethoven_-_sonata_no._14_in_c_sharp_minor_%27moonlight%27%2C_op._"
             "27_no._2_-_i._adagio_sostenuto.ogg.mp3",
        "Betxoven — «Oy nuri» sonatasi", "Бетховен — «Лунная соната»", "Public domain"),
    "clair-de-lune": (
        _C + "transcoded/b/be/Clair_de_lune_%28Claude_Debussy%29_Suite_bergamasque.ogg/"
             "Clair_de_lune_%28Claude_Debussy%29_Suite_bergamasque.ogg.mp3",
        "Debyussi — «Oy nuri» (Clair de lune)", "Дебюсси — «Лунный свет»", "Public domain"),
    "bach-prelude": (
        _C + "transcoded/b/b6/Kimiko_Ishizaka_-_Bach_-_Well-Tempered_Clavier%2C_Book_1_-_01_Prelude_No._1_in_C_major"
             "%2C_BWV_846.ogg/Kimiko_Ishizaka_-_Bach_-_Well-Tempered_Clavier%2C_Book_1_-_01_Prelude_No._1_in_C_major"
             "%2C_BWV_846.ogg.mp3",
        "Bax — Prelyudiya do-major", "Бах — Прелюдия до мажор", "CC0 (Kimiko Ishizaka)"),
    "gymnopedie": (
        _C + "transcoded/b/b7/Gymnopedie_No._1..ogg/Gymnopedie_No._1..ogg.mp3",
        "Sati — Gimnopediya №1", "Сати — Гимнопедия №1", "CC0"),
    "bach-air": (
        _C + "e/ec/Air_-_Air_Force_Strings_-_United_States_Air_Force_Band.mp3",
        "Bax — «Air»", "Бах — «Ария»", "Public domain (US Air Force Band)"),
    "mozart-romance": (
        _C + "transcoded/b/be/Mozart_K525_Serenade_in_G_Major_2_-_Romance.ogg/"
             "Mozart_K525_Serenade_in_G_Major_2_-_Romance.ogg.mp3",
        "Motsart — «Kichik tungi serenada»: Romans", "Моцарт — «Маленькая ночная серенада»: Романс",
        "Public domain"),
}

_locks: dict[str, asyncio.Lock] = {}
_failed: dict[str, float] = {}


def enabled() -> bool:
    """Server keshlaydimi (Wikimedia talab qilgan aloqa berilganmi)."""
    return bool(CONTACT)


def user_agent() -> str:
    return f"KetoshopSite/1.0 ({CONTACT}) aiohttp"


def path_for(name: str) -> Path:
    return CACHE_DIR / f"{name}.mp3"


async def ensure(name: str, session: aiohttp.ClientSession | None = None) -> Path | None:
    """Kesh fayli (kerak bo'lsa yuklab olinadi) yoki None — manba ochilmadi."""
    if name not in TRACKS or not enabled():
        return None
    path = path_for(name)
    if path.exists() and path.stat().st_size > 0:
        return path
    lock = _locks.setdefault(name, asyncio.Lock())
    async with lock:
        if path.exists() and path.stat().st_size > 0:
            return path
        if time.monotonic() - _failed.get(name, -1e9) < FAIL_PAUSE:
            return None
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        own = session is None
        session = session or aiohttp.ClientSession()
        try:
            async with session.get(TRACKS[name][0], headers={"User-Agent": user_agent()},
                                   timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status != 200:
                    logger.warning("site music %s: HTTP %s", name, resp.status)
                    _failed[name] = time.monotonic()
                    return None
                with open(tmp, "wb") as fh:
                    async for chunk in resp.content.iter_chunked(1 << 16):
                        fh.write(chunk)
            os.replace(tmp, path)
            logger.info("site music %s cached (%d KB)", name, path.stat().st_size // 1024)
            return path
        except Exception:
            logger.warning("site music %s download failed", name, exc_info=True)
            _failed[name] = time.monotonic()
            try:
                tmp.unlink()
            except OSError:
                pass
            return None
        finally:
            if own:
                await session.close()


async def music_file(request: web.Request) -> web.StreamResponse:
    name = request.match_info.get("name", "").removesuffix(".mp3")
    path = await ensure(name)
    if path is None:
        return web.Response(status=404 if name not in TRACKS else 503)
    return web.FileResponse(path, headers={"Cache-Control": "public, max-age=604800",
                                           "Content-Type": "audio/mpeg"})


async def prefetch() -> None:
    """Ishga tushganda hammasini birma-bir keshga — birinchi xaridor kutmasin."""
    async with aiohttp.ClientSession() as session:
        for name in TRACKS:
            await ensure(name, session)


def setup_routes(app: web.Application) -> None:
    app.router.add_get("/music/{name}", music_file)

    async def _start(_app):
        if enabled():
            _app["site_music_task"] = asyncio.create_task(prefetch())

    app.on_startup.append(_start)


def playlist() -> list[dict]:
    """Sahifa uchun (#music-playlist): [{id, src, remote, uz, ru}] — tartib bilan.
    src — bizning server (kesh yoqilgan bo'lsa) yoki to'g'ridan-to'g'ri Wikimedia;
    remote — Wikimedia (serverdagi nusxa ochilmasa, sahifa shunga o'tadi)."""
    return [{"id": k, "src": f"/music/{k}.mp3" if enabled() else v[0], "remote": v[0], "uz": v[1], "ru": v[2]}
            for k, v in TRACKS.items()]
