"""📱 Android ilovasi: versiya va yangilanish — serverdan boshqariladi.

Ilovaning do'kon qismi saytning o'zi (Mini App sahifasi ilova ichida), shuning
uchun do'kondagi har o'zgarish APK'siz darhol chiqadi. Bu yerda faqat
ilovaning o'z native qismi uchun kerak bo'lgan narsalar:

GET /app/v1/config?lang=uz (ochiq, kirishsiz ham):
  * latest_build / min_build — eskirgan ilova «Yangi versiya bor» deydi,
    minimaldan pastdagisi esa yangilashni talab qiladi;
  * update_url — yangi APK manzili (APP_APK_URL, bo'lmasa do'kon kanali);
  * terms_version — amaldagi Oferta tahriri (app_terms.py).

Yangi APK chiqqanda LATEST_* ni oshiring. MIN_BUILD ni faqat eski ilova
umuman ishlay olmaydigan bo'lsa ko'taring.
"""
from __future__ import annotations

import os
import time

from aiohttp import web

LATEST_VERSION = "1.1.0"
LATEST_BUILD = 2
MIN_BUILD = 1

_UPDATE_TEXT = {
    "uz": "Ilovaning yangi versiyasi chiqdi: tezroq va yangi imkoniyatlar bilan.",
    "ru": "Вышла новая версия приложения: быстрее и с новыми возможностями.",
}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _text(value: dict, lang: str) -> str:
    text = value.get("ru" if lang == "ru" else "uz") or value["uz"]
    if lang == "uz_cyr":
        import translit
        text = translit.lat_to_cyr(text)
    return text


def update_url() -> str:
    """Where the new APK is: APP_APK_URL (a GitHub release, the shop's
    site, a channel post); by default the shop's channel."""
    from config import REQUIRED_CHANNEL_USERNAME
    return os.getenv("APP_APK_URL", "").strip() or f"https://t.me/{REQUIRED_CHANNEL_USERNAME.lstrip('@')}"


def build(lang: str, release: dict | None = None) -> dict:
    """`release` — the newest APK uploaded in the admin panel
    (app_release.latest()); when there is one, the app downloads it itself
    («Yangilash» → install) instead of sending the buyer to the channel."""
    import app_terms
    lang = lang if lang in ("uz", "uz_cyr", "ru") else "uz"
    latest_build = _int_env("APP_LATEST_BUILD", LATEST_BUILD)
    data = {
        "latest_version": os.getenv("APP_LATEST_VERSION", "").strip() or LATEST_VERSION,
        "latest_build": latest_build,
        "min_build": min(_int_env("APP_MIN_BUILD", MIN_BUILD), latest_build),
        "update_url": update_url(),
        "update_notes": _text(_UPDATE_TEXT, lang),
        "apk_sha256": "",
        "apk_size": 0,
        "terms_version": app_terms.VERSION,
        # Where the shop opens inside the app, and the bridge script the
        # shop page gets (served by the server, so it changes without an APK).
        "shop_path": "/",
        "shim_path": "/app/v1/shim.js",
    }
    if release and release["build"] >= latest_build:
        from config import WEBAPP_URL
        notes = release.get("notes_ru" if lang == "ru" else "notes_uz") or release.get("notes_uz")
        if notes and lang == "uz_cyr":
            import translit
            notes = translit.lat_to_cyr(notes)
        data.update({
            "latest_version": release["version"],
            "latest_build": release["build"],
            "min_build": min(max(data["min_build"], release.get("min_build") or 0), release["build"]),
            "update_url": f"{WEBAPP_URL.rstrip('/')}/app/download/ketoshop-{release['build']}.apk",
            "apk_sha256": release["sha256"],
            "apk_size": release["size"],
        })
        if notes:
            data["update_notes"] = notes
    return data


async def handle_config(request: web.Request) -> web.Response:
    """Public: the app reads it before login too (version check)."""
    import app_release
    data = build(request.query.get("lang", "uz"), await app_release.latest())
    return web.json_response(dict(data, server_time=int(time.time() * 1000)),
                             headers={"Cache-Control": "no-store"})


_SHIM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp", "app_shim.js")


async def handle_shim(request: web.Request) -> web.Response:
    """The app ⇄ shop bridge (webapp/app_shim.js). Public: it holds no
    secrets — the app puts the session's initData in front of it."""
    with open(_SHIM, "rb") as f:
        body = f.read()
    return web.Response(body=body, content_type="application/javascript", charset="utf-8",
                        headers={"Cache-Control": "no-cache"})


def add_routes(app: web.Application) -> None:
    app.router.add_get("/app/v1/config", handle_config)
    app.router.add_get("/app/v1/shim.js", handle_shim)
