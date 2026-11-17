"""📱 Android ilovasini server boshqaradi — yangi APK'siz o'zgaradigan qism.

GET /app/v1/config?lang=uz&build=3 (ochiq, kirishsiz ham) ilovaga beradi:
  * versiya: eng yangisi va majburiy minimal build. Eskirgan ilova
    «Yangi versiya bor» deydi, minimaldan pastda esa ishlamay yangilashni so'raydi;
  * features: funksiyalarni yoqish/o'chirish kalitlari;
  * delivery: Toshkent ichida va viloyatlarda qaysi yetkazish usullari;
  * home: katalog tepasidagi bloklar — aksiya, chegirma, e'lonlar va
    EXTRA_BLOCKS ga qo'shilgan har narsa.

Ilova o'zi tanimagan blok turini e'tiborsiz qoldiradi. Shuning uchun keyin
yangi blok turi qo'shilsa, eski ilovalar yiqilmaydi, faqat uni ko'rsatmaydi.

Yangi narsani APK'siz qo'shish: shu fayldagi qiymatni o'zgartirib master'ga
push qilish kifoya (avtomatik deploy). Ilova sozlamani har ochilishda va har
30 daqiqada qayta o'qiydi.
"""
from __future__ import annotations

import logging
import os
import re
import time

from aiohttp import web

logger = logging.getLogger(__name__)

# Har yangi APK chiqqanda LATEST_* ni oshiring. MIN_BUILD ni faqat eski
# ilova umuman ishlay olmaydigan bo'lsa ko'taring (masalan, API o'zgarsa).
LATEST_VERSION = "1.0.0"
LATEST_BUILD = 1
MIN_BUILD = 1

FEATURES = {
    "search": True,          # «Qidiruv» tabi
    "home_blocks": True,     # katalog tepasidagi bloklar
    "restock_wait": True,    # «🔔 Kelganda xabar bering»
    "keto_redeem": True,     # checkout'da Keto bilan to'lash (server baribir o'zi tekshiradi)
}

DELIVERY = {
    "tashkent": ["self", "yandex_taxi"],
    "regions": ["uzpost", "bts", "emu"],
}

# Qo'lda qo'shiladigan bloklar. Har biri {"uz": ..., "ru": ...} matnlar bilan;
# uz_cyr Lotin matndan transliteratsiya qilinadi. Turlari:
#   {"type": "notice", "id": "...", "text": {...}, "tone": "info|success|warning"}
#   {"type": "banner", "id": "...", "title": {...}, "text": {...}, "image_url": "/img/7", "link": "https://t.me/..."}
#   {"type": "link", "id": "...", "text": {...}, "url": "https://..."}
#   {"type": "category", "id": "...", "text": {...}, "category": "<kalit>"}
#   {"type": "products", "id": "...", "title": {...}, "product_ids": [1, 2, 3]}
EXTRA_BLOCKS: list[dict] = []

_UPDATE_TEXT = {
    "uz": "Ilovaning yangi versiyasi chiqdi: tezroq va yangi imkoniyatlar bilan.",
    "ru": "Вышла новая версия приложения: быстрее и с новыми возможностями.",
}

_CACHE_SECONDS = 60
_cache: dict[str, tuple[float, dict]] = {}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _pick(value, lang: str) -> str:
    if isinstance(value, str):
        text = value
    elif isinstance(value, dict):
        text = value.get("ru" if lang == "ru" else "uz") or value.get("uz") or ""
    else:
        return ""
    if lang == "uz_cyr":
        import translit
        text = translit.lat_to_cyr(text)
    return text


def _plain(text: str | None) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def update_url() -> str:
    """Where the new APK is: APP_APK_URL (a GitHub release, the shop's
    site, a channel post); by default the shop's channel."""
    from config import REQUIRED_CHANNEL_USERNAME
    return os.getenv("APP_APK_URL", "").strip() or f"https://t.me/{REQUIRED_CHANNEL_USERNAME.lstrip('@')}"


def _manual_block(block: dict, lang: str) -> dict | None:
    kind = block.get("type")
    out: dict = {"type": kind, "id": str(block.get("id") or kind)}
    if kind == "notice":
        out.update(text=_pick(block.get("text"), lang), tone=block.get("tone") or "info")
    elif kind == "banner":
        out.update(title=_pick(block.get("title"), lang), text=_pick(block.get("text"), lang),
                   image_url=block.get("image_url"), link=block.get("link"))
    elif kind == "link":
        out.update(text=_pick(block.get("text"), lang), url=block.get("url"))
    elif kind == "category":
        out.update(text=_pick(block.get("text"), lang), category=block.get("category"))
    elif kind == "products":
        out.update(title=_pick(block.get("title"), lang),
                   product_ids=[int(i) for i in block.get("product_ids") or []])
    else:
        return None
    return out


async def home_blocks(lang: str) -> list[dict]:
    """Live blocks from what the shop already runs, then EXTRA_BLOCKS. Any
    part that fails is left out — the catalog must open regardless."""
    blocks: list[dict] = []
    try:
        import promotions
        from webapp_server import photo_url
        promo = await promotions.get_active()
        if promo:
            days = promotions.days_left(promo)
            blocks.append({
                "type": "banner", "id": f"aksiya-{promo.get('id')}",
                "title": "🎁 " + promotions.promo_name(promo, lang),
                "text": _plain(promotions.promo_conditions(promo, lang)),
                "image_url": photo_url(promo.get("image_url")),
                "badge": (f"{days} kun" if lang != "ru" else f"{days} дн.") if days else None,
            })
    except Exception:
        logger.warning("app home: promotion block failed", exc_info=True)
    try:
        import bot_discount
        banner = await bot_discount.site_banner(lang)
        if banner:
            text = " ".join(_plain(banner.get(k)) for k in ("sub", "deadline") if banner.get(k))
            blocks.append({"type": "banner", "id": "bot-discount", "title": _plain(banner.get("title")),
                           "text": text, "image_url": None})
    except Exception:
        logger.warning("app home: discount block failed", exc_info=True)
    try:
        import mystery_gift
        for key, line in (("mystery", mystery_gift.card_line(lang)),
                          ("free-delivery", mystery_gift.free_delivery_card_line(lang))):
            if _plain(line):
                blocks.append({"type": "notice", "id": key, "text": _plain(line), "tone": "success"})
    except Exception:
        logger.warning("app home: perk lines failed", exc_info=True)
    for block in EXTRA_BLOCKS:
        try:
            built = _manual_block(block, lang)
            if built:
                blocks.append(built)
        except Exception:
            logger.warning("app home: bad EXTRA_BLOCKS entry %r", block.get("id"), exc_info=True)
    return blocks


async def build(lang: str) -> dict:
    lang = lang if lang in ("uz", "uz_cyr", "ru") else "uz"
    hit = _cache.get(lang)
    if hit and time.monotonic() - hit[0] < _CACHE_SECONDS:
        return hit[1]
    latest_build = _int_env("APP_LATEST_BUILD", LATEST_BUILD)
    import app_terms
    data = {
        # The Oferta edition in force; the app asks to accept a newer one.
        "terms_version": app_terms.VERSION,
        "latest_version": os.getenv("APP_LATEST_VERSION", "").strip() or LATEST_VERSION,
        "latest_build": latest_build,
        "min_build": min(_int_env("APP_MIN_BUILD", MIN_BUILD), latest_build),
        "update_url": update_url(),
        "update_notes": _pick(_UPDATE_TEXT, lang),
        "features": dict(FEATURES),
        "delivery": {k: list(v) for k, v in DELIVERY.items()},
        "home": await home_blocks(lang) if FEATURES.get("home_blocks") else [],
    }
    _cache[lang] = (time.monotonic(), data)
    return data


async def handle_config(request: web.Request) -> web.Response:
    """Public: the app reads it before login too (version check)."""
    data = await build(request.query.get("lang", "uz"))
    return web.json_response(dict(data, server_time=int(time.time() * 1000)),
                             headers={"Cache-Control": "no-store"})


def add_routes(app: web.Application) -> None:
    app.router.add_get("/app/v1/config", handle_config)
