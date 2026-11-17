"""
Saytdagi retseptlar — har 2 kunda bitta (egasi, 2026-10-08).

Kontent recipes_content.py da. Bu modul:
  • qaysi retsept "bugungi" ekanini hisoblaydi (saytda faqat shu bitta
    ko'rinadi — egasi: "har kuni faqat 1 ta retsept ko'rsat, hammasini emas") — START dan boshlab har
    EVERY_DAYS kunda bitta "slot"; qaysi slotga qaysi retsept tushishi
    pastdagi «Jadval» bo'limida. Yangi retsept qo'shish = recipes_content.RECIPES
    oxiriga qo'shish + webapp/recipes/<slug>.jpg rasmi (rasmsiz chiqmaydi);
  • retsept masalliqlarini katalogdagi haqiqiy mahsulotlarga bog'laydi
    (rasm, joriy narx, omborda bormi) — narx kontentda yozilmaydi, shuning
    uchun narx o'zgarsa retsept o'zi to'g'ri ko'rsatadi;
  • "🛒 Barcha masalliqlarni savatga": omborda bor har bir mahsulotdan 1 ta
    qadoq savatga tushadi; savatda allaqachon bori qayta qo'shilmaydi.

Rasmlar sun'iy intellekt yordamida yaratilgan va matnda buni ochiq aytamiz
(egasi: "rasmlar ai yordamida qilinganini bildirib qo'yishimiz kerak, matnda").

Jadval — the schedule (2026-11-13)
  The first LEGACY_COUNT (15) recipes went out one per slot from START.
  When they ran out (05.11) the old rule cycled them, so every slot before
  QUEUE_START is exactly what that rule gave: slot k → RECIPES[k % 15].
  That history is a formula and never changes.

  From QUEUE_START (15.11) each slot is either
    NEW    — the first recipe, in library order, that has never been out
             and whose photo webapp/recipes/<slug>.jpg exists; or
    REPEAT — when no such recipe is ready: one already out, taken in turn
             (never the same as the slot before).
  A recipe without its photo is never shown — not on the site, not in the
  channel, not by a link (find). It waits; meanwhile the slots are
  repeats, and the first slot after its photo arrives is its own. So the
  new recipes come out in library order, one per slot, none skipped.

  "The first slot after its photo arrives" needs memory: from the files
  alone a photo added on 20.11 looks the same as one that was there on
  15.11, and a replay would give that recipe to 15.11 — a day nobody saw
  it — and push every later one along. So every slot's recipe is written
  down once, the first time the slot is looked at (sync(): the recipe
  scheduler loop every 10 minutes, and every site / bot request that shows
  a recipe), as a release_notes_sent key "recipe-slot-YYYY-MM-DD:<slug>" —
  the table every once-only send here uses, no new table. A written slot
  never changes: a deploy that brings photos mid-slot leaves the current
  slot alone, and the new recipe takes the next one.

  plan() replays that log from QUEUE_START: the recipe of any day, whether
  it is new, and every recipe out so far (find opens only those). A slot
  with no entry follows the rule above — for the current slot that is
  exactly what sync() is about to write; an older one (the bot was down for
  the whole slot) counts as a repeat, so nothing is ever "published" on a
  day nobody saw it. If a day were ever written twice, its first entry wins.
"""
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import database
from recipes_content import RECIPES

logger = logging.getLogger(__name__)

START = date(2026, 10, 8)
EVERY_DAYS = 2
TZ_OFFSET = timedelta(hours=5)
CATALOG_TTL = 300
# «Jadval»: the first 15 went out by the old rule; the photo-gated queue
# starts with the first slot after the cycled ones (13.11 was the last).
LEGACY_COUNT = 15
QUEUE_START = date(2026, 11, 15)
PHOTO_DIR = Path(__file__).parent / "webapp" / "recipes"
SLOT_KEY = "recipe-slot-"

AI_NOTE = {
    "uz": "📸 Rasm sun'iy intellekt yordamida yaratilgan",
    "ru": "📸 Изображение создано с помощью ИИ",
}

LABELS = {
    "badge": {"uz": "🍳 Yangi retsept", "ru": "🍳 Новый рецепт"},
    "open": {"uz": "Retseptni ochish", "ru": "Открыть рецепт"},
    "minutes": {"uz": "{n} daqiqa", "ru": "{n} мин"},
    "carbs": {"uz": "≈{n} g uglevod", "ru": "≈{n} г углеводов"},
    "kcal": {"uz": "≈{n} kkal", "ru": "≈{n} ккал"},
    "per_serving": {"uz": "1 porsiyada, taxminan", "ru": "на порцию, примерно"},
    "ingredients": {"uz": "Masalliqlar", "ru": "Ингредиенты"},
    "from_home": {"uz": "uydan", "ru": "из дома"},
    "out_of_stock": {"uz": "⏳ tez orada qaytadi", "ru": "⏳ скоро вернётся"},
    "add_all": {"uz": "🛒 Barcha masalliqlarni savatga", "ru": "🛒 Все ингредиенты в корзину"},
    "add_all_sub": {"uz": "Ketoshop mahsulotlari — har biridan 1 qadoq",
                    "ru": "Продукты Ketoshop — по 1 упаковке"},
    # The bar pinned to the bottom of the recipe (2026-10-22): the add-all
    # button used to sit mid-page and was almost never pressed. Not "hammasi"
    # (everything): eggs, water and the like come from home (owner).
    "bar_title": {"uz": "Retseptdagi Ketoshop mahsulotlari", "ru": "Продукты Ketoshop из рецепта"},
    "bar_count": {"uz": "{n} ta mahsulot, har biridan 1 qadoq",
                  "ru": "Товаров: {n}, по 1 упаковке"},
    "bar_btn": {"uz": "🛒 Savatga", "ru": "🛒 В корзину"},
    # 2026-11-12: recipes are read (~86 s a visit) but rarely lead to a
    # product — the same button now also sits right under the ingredients
    # and at the end of the steps (the bar hides while one of them shows).
    "cta": {"uz": "🛒 Masalliqlarni savatga qo'shish", "ru": "🛒 Добавить ингредиенты в корзину"},
    "end_title": {"uz": "Pishirishga tayyormisiz? Ketoshop mahsulotlari bir bosishda savatda",
                  "ru": "Готовы готовить? Продукты Ketoshop — в корзину одним нажатием"},
    "go_cart": {"uz": "Savatni ochish →", "ru": "Открыть корзину →"},
    "steps": {"uz": "Tayyorlash", "ru": "Приготовление"},
    "tip": {"uz": "💡 Maslahat", "ru": "💡 Совет"},
    # Owner, 2026-10-13: "keyingi retsept shu sanasida e'lon qilinadi,
    # kuzatib boring" — a full sentence instead of a bare date.
    "next": {"uz": "Keyingi retsept {date} kuni e'lon qilinadi — kuzatib boring",
             "ru": "Следующий рецепт выйдет {date} — следите за обновлениями"},
    "added": {"uz": "✅ {n} ta mahsulot savatga qo'shildi", "ru": "✅ Добавлено в корзину: {n}"},
    "already": {"uz": "👍 Masalliqlar allaqachon savatingizda", "ru": "👍 Ингредиенты уже в корзине"},
    "missing": {"uz": "⏳ Tez orada qaytadi, hozircha savatga qo'shilmadi: {names}",
                "ru": "⏳ Скоро вернутся, пока не добавлены: {names}"},
    "back": {"uz": "← Orqaga", "ru": "← Назад"},
}

_catalog_cache: dict = {"at": 0.0, "rows": []}
_BY_SLUG = {r["slug"]: r for r in RECIPES}
_slot_log: dict = {"slots": {}, "day": None}     # sync(): {slot day: slug}, the slot it was read for


def labels(lang: str) -> dict:
    return {key: _pick(entry, lang) for key, entry in LABELS.items()}


def _pick(entry: dict, lang: str) -> str:
    if lang == "ru":
        return entry["ru"]
    if lang == "uz_cyr":
        from translit import lat_to_cyr
        return lat_to_cyr(entry["uz"])
    return entry["uz"]


def today_tk() -> date:
    return (datetime.utcnow() + TZ_OFFSET).date()


# ─────────────────────────────── jadval ───────────────────────────────

def has_photo(recipe: dict) -> bool:
    """Its photo is on disk. Without it a recipe is never shown («Jadval»)."""
    return (PHOTO_DIR / f"{recipe['slug']}.jpg").is_file()


def slot_day(day: date) -> date:
    """The first day of the slot `day` falls in (a day before START → START)."""
    return START + timedelta(days=max(0, (day - START).days) // EVERY_DAYS * EVERY_DAYS)


def _slot_no(day: date) -> int:
    return (day - START).days // EVERY_DAYS


def _repeat(k: int, published: list[dict], prev: dict | None) -> dict:
    """Slot k's repeat: the recipes already out, in turn — never the one of
    the slot before (that one was new, or the turn would not land on it)."""
    pick = published[k % len(published)]
    if prev is not None and pick["slug"] == prev["slug"] and len(published) > 1:
        pick = published[(k + 1) % len(published)]
    return pick


def _replay(day: date, slots: dict, photo) -> tuple[dict, bool, list[dict]]:
    """Walk the slots from QUEUE_START to `day` (a slot day, ≥ QUEUE_START).
    → (its recipe, is it new, every recipe out so far in the order they
    first came out — its own included)."""
    published = [r for r in RECIPES[:LEGACY_COUNT] if photo(r)]
    seen = {r["slug"] for r in published}
    d = QUEUE_START
    prev = RECIPES[(_slot_no(d) - 1) % LEGACY_COUNT]
    while True:
        recipe = _BY_SLUG.get(slots.get(d, ""))
        if recipe is None or not photo(recipe):
            recipe = None
            if d == day:            # not written yet: what sync() writes for it
                recipe = next((r for r in RECIPES if r["slug"] not in seen and photo(r)), None)
            recipe = recipe or _repeat(_slot_no(d), published or RECIPES[:1], prev)
        is_new = recipe["slug"] not in seen
        if is_new:
            published.append(recipe)
            seen.add(recipe["slug"])
        if d >= day:
            return recipe, is_new, published
        prev = recipe
        d += timedelta(days=EVERY_DAYS)


def plan(today: date | None = None, slots: dict | None = None, photo=None) -> dict:
    """The slot `today` is in: {"day", "recipe", "is_new", "earlier" (out
    before, newest first), "next_at"}. `slots` / `photo` default to the slot
    log read by sync() and the photo files."""
    today = today or today_tk()
    slots = _slot_log["slots"] if slots is None else slots
    photo = photo or has_photo
    day = slot_day(today)
    k = _slot_no(day)
    out = {"day": day, "next_at": day + timedelta(days=EVERY_DAYS)}
    if day < QUEUE_START:                       # the old rule, kept as it was
        idx = k % LEGACY_COUNT
        if k < LEGACY_COUNT:
            earlier = list(reversed(RECIPES[:idx]))
        else:
            earlier = [RECIPES[(idx - j) % LEGACY_COUNT] for j in range(1, LEGACY_COUNT)]
        return {**out, "recipe": RECIPES[idx], "is_new": k < LEGACY_COUNT, "earlier": earlier}
    recipe, is_new, published = _replay(day, slots, photo)
    earlier = [r for r in reversed(published) if r["slug"] != recipe["slug"]]
    return {**out, "recipe": recipe, "is_new": is_new, "earlier": earlier}


def schedule(today: date | None = None, slots: dict | None = None,
             photo=None) -> tuple[dict, list[dict], date]:
    """(bugungi retsept, avvalgilari — yangisi birinchi, keyingisi qachon)."""
    p = plan(today, slots, photo)
    return p["recipe"], p["earlier"], p["next_at"]


def waiting(today: date | None = None, slots: dict | None = None, photo=None) -> dict:
    """Recipes not out yet: {"no_photo": [...], "ready": [...]} — "ready"
    have their photo and only wait for their slot."""
    photo = photo or has_photo
    p = plan(today, slots, photo)
    out = {p["recipe"]["slug"], *(r["slug"] for r in p["earlier"])}
    rest = [r for r in RECIPES if r["slug"] not in out]
    return {"no_photo": [r for r in rest if not photo(r)], "ready": [r for r in rest if photo(r)]}


def find(slug: str, today: date | None = None) -> dict | None:
    """Faqat chiqqan retseptlar — kelajakdagisi (va rasmsizi) havola bilan ham ochilmaydi."""
    current, earlier, _ = schedule(today)
    for recipe in [current, *earlier]:
        if recipe["slug"] == slug:
            return recipe
    return None


def parse_slots(keys) -> dict:
    """"recipe-slot-2026-11-15:<slug>" keys, oldest first → {date: slug};
    the first entry of a day wins."""
    slots: dict = {}
    for key in keys:
        day, sep, slug = key[len(SLOT_KEY):].partition(":")
        try:
            when = date.fromisoformat(day)
        except ValueError:
            continue
        if sep and slug:
            slots.setdefault(when, slug)
    return slots


async def _load_slots() -> dict:
    async with database.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key FROM release_notes_sent WHERE key LIKE $1 ORDER BY sent_at, key",
            SLOT_KEY + "%")
    return parse_slots(r["key"] for r in rows)


async def sync(today: date | None = None) -> bool:
    """Read the slot log and, the first time the current slot is looked at,
    write its recipe down («Jadval»). One round trip per slot. Never raises:
    False when the log could not be read or written — the last one read
    (empty after a restart) stays in use."""
    day = slot_day(today or today_tk())
    if day < QUEUE_START or _slot_log["day"] == day:
        return True
    if database.pool is None:                   # no database (tests, before startup)
        return False
    try:
        slots = await _load_slots()
        if day not in slots:
            recipe = _replay(day, slots, has_photo)[0]
            await database.claim_release_notes(f"{SLOT_KEY}{day.isoformat()}:{recipe['slug']}")
            slots = await _load_slots()
    except Exception:
        logger.warning("Recipe slot log could not be read or written", exc_info=True)
        return False
    _slot_log.update(slots=slots, day=day)
    return True


# ───────────────────────────── mahsulotlar ─────────────────────────────

def _norm(text: str) -> str:
    text = (text or "").lower()
    for ch in "ʻʼ‘’`´":
        text = text.replace(ch, "'")
    return text


async def _catalog() -> list[dict]:
    now = time.monotonic()
    if now - _catalog_cache["at"] < CATALOG_TTL and _catalog_cache["rows"]:
        return _catalog_cache["rows"]
    async with database.pool.acquire() as conn:
        rows = [dict(r) for r in await conn.fetch(
            """SELECT id, name, name_ru, price, unit, COALESCE(quantity, 0) AS quantity,
                      photo_id, COALESCE(discount_percent, 0) AS discount_percent, discount_until
                 FROM products
                WHERE is_active = 1 AND (b2b_only IS NOT TRUE) AND COALESCE(price, 0) > 0""")]
    _catalog_cache.update(at=now, rows=rows)
    return rows


def match_product(groups: list[list[str]], catalog: list[dict]) -> dict | None:
    """Birinchi mos guruh; bir nechta qadoq bo'lsa — omborda bor eng hamyonbopi."""
    for group in groups:
        hits = [p for p in catalog if all(tok in _norm(p["name"]) for tok in group)]
        if not hits:
            continue
        in_stock = [p for p in hits if float(p["quantity"]) > 0]
        return min(in_stock or hits, key=lambda p: float(p["price"]))
    return None


def _photo(ref) -> str | None:
    """Telegram file_id — /api/photo proksi orqali; yuklangan rasm — o'zi."""
    if not ref:
        return None
    ref = str(ref).strip()
    return ref if ref.startswith(("/", "http://", "https://")) else f"/api/photo/{ref}"


def _product_view(p: dict, lang: str) -> dict:
    from locales import get_display_unit, localize_product_text
    price = database.effective_price(p["price"], p.get("discount_percent"), p.get("discount_until"))
    return {
        "id": p["id"],
        "name": localize_product_text(p["name"], p.get("name_ru"), lang),
        "price": price,
        "unit": get_display_unit(p["unit"], lang),
        "photo_url": _photo(p.get("photo_id")),
        "out_of_stock": float(p["quantity"]) <= 0,
    }


async def view(recipe: dict, lang: str, *, full: bool = True) -> dict:
    """Mini App uchun: tarjima qilingan matn + bog'langan mahsulotlar."""
    out = {
        "slug": recipe["slug"],
        "title": _pick(recipe["title"], lang),
        "intro": _pick(recipe["intro"], lang),
        "image_url": f"/static/recipes/{recipe['slug']}.jpg",
        "minutes": recipe["minutes"],
        "rest": _pick(recipe["rest"], lang) if recipe.get("rest") else "",
        "servings": _pick(recipe["servings"], lang),
        "per_serving": recipe["per_serving"],
        "ai_note": _pick(AI_NOTE, lang),
    }
    if not full:
        return out
    catalog = await _catalog()
    ingredients, shown = [], []
    for item in recipe["ingredients"]:
        row = {"amount": _pick(item["amount"], lang), "name": _pick(item["name"], lang)}
        if item.get("why"):
            row["why"] = _pick(item["why"], lang)
        if item.get("match"):
            p = match_product(item["match"], catalog)
            row["product"] = _product_view(p, lang) if p else None
            if p:
                shown.append((row["product"], p))
        ingredients.append(row)
    # 10% bot-order price, the same as on every product card (bot_discount.py).
    import bot_discount
    for (card, p), bot_price in zip(shown, await bot_discount.display_prices([p for _, p in shown])):
        if bot_price is not None:
            card.update(price=bot_price, original_price=float(p["price"]),
                        discount_percent=bot_discount.shown_percent(p["price"], bot_price))
    out.update(
        ingredients=ingredients,
        steps=[_pick(s, lang) for s in recipe["steps"]],
        tip=_pick(recipe["tip"], lang),
    )
    return out


async def add_all_to_cart(user_id: int, recipe: dict, lang: str = "uz") -> dict:
    """Omborda bor har bir retsept mahsulotidan 1 qadoq. Savatda bori qoladi."""
    catalog = await _catalog()
    added, already, missing = [], [], []
    seen: set[int] = set()
    for item in recipe["ingredients"]:
        if not item.get("match"):
            continue
        name = _pick(item["name"], lang)
        p = match_product(item["match"], catalog)
        if not p or float(p["quantity"]) <= 0:
            missing.append(name)
            continue
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        _, in_cart = await database.get_cart_line_for_product(user_id, p["id"])
        if in_cart:
            already.append(name)
            continue
        # Savat broni: nothing goes in when other buyers' carts hold it all.
        if await database.add_to_cart(user_id, product_id=p["id"], quantity=1) <= 0:
            missing.append(name)
            continue
        added.append(name)
    return {"added": added, "already": already, "missing": missing}
