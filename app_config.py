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


def build(lang: str) -> dict:
    import app_terms
    lang = lang if lang in ("uz", "uz_cyr", "ru") else "uz"
    latest_build = _int_env("APP_LATEST_BUILD", LATEST_BUILD)
    return {
        "latest_version": os.getenv("APP_LATEST_VERSION", "").strip() or LATEST_VERSION,
        "latest_build": latest_build,
        "min_build": min(_int_env("APP_MIN_BUILD", MIN_BUILD), latest_build),
        "update_url": update_url(),
        "update_notes": _text(_UPDATE_TEXT, lang),
        "terms_version": app_terms.VERSION,
    }


async def handle_config(request: web.Request) -> web.Response:
    """Public: the app reads it before login too (version check)."""
    data = build(request.query.get("lang", "uz"))
    return web.json_response(dict(data, server_time=int(time.time() * 1000)),
                             headers={"Cache-Control": "no-store"})


def add_routes(app: web.Application) -> None:
    app.router.add_get("/app/v1/config", handle_config)
