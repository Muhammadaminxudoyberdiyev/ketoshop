"""
📱 «Saytda nima bor?» — kanalga vaqti-vaqti bilan sayt imkoniyatlari haqida
sodda post (owner, 2026-11-21: "o'yinlar haqida ora orada kanalda ham e'lon
bergin ularni foydasi va bilim ulashishi haqida ..." va "saytdagi o'yinlar va
sayt imkoniyatlari haqida ham barchaga sodda va qancha imkoniyatlardan
foydalanishlari mumkinligini tushuntirib ham kanalga orada postlar tashlab tur").

Every 3 days at 17:30 Tashkent — clear of «Keto fakt» (16:00, every 2 days)
and the evening posts (19:47) — one post from POSTS in order, round again.
Written in Latin here, posted in the channel's Cyrillic, rewritten by
channel_voice like the other channel posts (facts and numbers locked); the
link is in the text, no buttons (comments stay open). The numbers in the
posts are the site's real rules (games.py, site_time.py, gamification).

Admin: /imkoniyat_test (the next one, to you only), /imkoniyat_off, /imkoniyat_on.
"""
import asyncio
import html
import logging
from datetime import date, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

import channel_link
import database
from config import ADMIN_IDS, BOT_USERNAME, REQUIRED_CHANNEL_ID

logger = logging.getLogger(__name__)
router = Router(name="channel_features")

START = date(2026, 11, 22)
EVERY_DAYS = 3
POST_AT = (17, 30)
LAST_HOUR = 21
CHECK_EVERY = 600
TZ_OFFSET = timedelta(hours=5)
SETTING = "channel_features"
HASHTAG = "#сайтданимабор"
GAMES = "games"          # the link opens the games page (?startapp=oyin, a tracked link)
SHOP = "shop"

# (link, title, body, how-to lines, closing question)
POSTS = [
    (SHOP, "Ketoshop saytida nimalar bor? 🤔",
     "Ko'pchilik saytimizni faqat do'kon deb biladi. Aslida u yerda xarid qilishdan tashqari "
     "bilim oshirish, o'ynash va sovg'a yig'ish ham mumkin.",
     ["🛒 Katalog — barcha keto va PP mahsulotlar, narxi va tarkibi bilan",
      "📖 Retseptlar — masalliqlarni bir bosishda savatga",
      "🎮 11 ta bilim o'yini — keto va sog'lom ovqatlanish haqida",
      "🪙 Keto tangalar — saytda vaqt, o'yin va xarid uchun; 1 Keto = 1 so'm",
      "🤖 «Yordamchi» — istalgan savolga darhol javob"],
     "Shulardan qaysi birini hali sinab ko'rmagansiz?"),
    (GAMES, "Har kuni bitta jumboq — «3 ta ishora» 🧩",
     "Har kuni yarim tunda hamma uchun bitta yangi jumboq ochiladi: 3 ta ishoradan keto mahsulotini "
     "topish kerak. Kamroq ishora — ko'proq Keto.",
     ["⭐ Birinchi ishoradayoq topsangiz — 15 Keto",
      "🔥 Har kuni yechsangiz — seriya o'sadi: 3, 7, 14, 30 kunda qo'shimcha bonus",
      "🙂 Bir kun o'tkazib yuborsangiz ham qo'rqmang: haftada bitta kun kechiriladi"],
     "Bugungi jumboqni necha ishorada topdingiz?"),
    (GAMES, "«Keto yo'li: 30 kun» — o'zingiz hal qiladigan hikoya 📖",
     "Malika opa ketoni boshladi: to'y, mehmondorchilik, bozor, kechki ochlik... Har kuni yangi bob "
     "ochiladi va har bir vaziyatda qanday yo'l tutishni siz tanlaysiz. Tanlov energiya, natija va "
     "kayfiyatga ta'sir qiladi.",
     ["📅 Kuniga bitta bob — 30 kun",
      "🪙 Har yangi bob uchun 5 Keto",
      "💡 Har bob oxirida — hayotda ishlatsa bo'ladigan maslahat"],
     "To'yda siz nimani tanlagan bo'lardingiz?"),
    (GAMES, "Ketoland xaritasi va Bozor sarguzashti 🗺",
     "Sarguzasht yoqadiganlar uchun ikki o'yin: Ketoland bo'ylab 10 bekatli sayohat va bozorda "
     "retsept uchun masalliq yig'ish — tuzoqlardan qochib.",
     ["🗺 Kuniga bitta yangi bekat; 3 savoldan 2 tasiga to'g'ri javob — bekat sizniki (10 Keto)",
      "🧺 Bozorda 5 ta rasta va 3 ta jon: noto'g'ri mahsulot — tuzoq",
      "🛒 O'yin oxirida — retsept masalliqlari bir bosishda savatga"],
     "Ketoland poytaxtiga kim birinchi yetib boradi?"),
    (GAMES, "Do'konda yorliqni o'qishni o'rganing 🏷",
     "«Shakarsiz», «fitnes», «diabetik» yozuvlari har doim ham to'g'ri emas. «Yorliq detektivi» "
     "o'yinida tarkibdagi yashirin shakarni topasiz: dekstroza, maltodekstrin, maltit, sharbat "
     "konsentrati...",
     ["🔍 Har yorliqda yashirin shakarni bosing — keyin izohini o'qing",
      "🔁 «Almashtir!» o'yinida somsa, chak-chak, palovni keto yoki PP qilasiz",
      "📚 Bu bilim do'konda pul va sog'liqni tejaydi"],
     "Siz yorliqni o'qib xarid qilasizmi?"),
    (SHOP, "Keto tangalar qanday yig'iladi va qayerga ishlatiladi? 🪙",
     "Keto — Ketoshopning sovg'a tangachalari: 1 Keto = 1 so'm chegirma. Ular yo'qolmaydi, "
     "hisobingizda yig'ilib boradi.",
     ["⏱ Saytda vaqt o'tkazganingiz uchun — birinchi daqiqadan boshlab",
      "🎮 O'yinlar uchun — kuniga 60 Keto gacha",
      "🛍 Har yetkazilgan xariddan keshbek",
      "🛒 Ishlatish: buyurtma berayotganda «Ketochalarni ishlatish» ni tanlang"],
     "Hisobingizda hozir qancha Keto bor?"),
    (SHOP, "Savolingiz bormi? «Yordamchi»ga yozing 🤖",
     "Saytda ham, botda ham AI yordamchi bor: mahsulotning foydasi va zarari, qaysi biri qaysi "
     "biridan farq qiladi, qanday ishlatiladi, retsept, buyurtmangiz qayerda — hammasini so'rasa "
     "bo'ladi.",
     ["💬 Saytda — pastdagi «Yordamchi» tugmasi",
      f"💬 Telegramda — @{BOT_USERNAME} ga oddiy xabar yozing",
      "🕐 Kecha-kunduz, darhol javob"],
     "Bugun qaysi mahsulot haqida bilmoqchisiz?"),
    (SHOP, "Retseptlar bo'limi — pishiring, masalliq izlamang 📖",
     "Saytda keto va PP retseptlar bor: har birida masalliqlar, tayyorlash bosqichlari va "
     "uglevodlar. Kerakli masalliqlarni bir bosishda savatga qo'shasiz.",
     ["🧾 Har retseptda — aniq miqdorlar",
      "🛒 «Masalliqlarni savatga» — bitta tugma",
      "🆕 Yangi retseptlar muntazam qo'shiladi"],
     "Qaysi taomning keto variantini ko'rmoqchisiz?"),
    (GAMES, "Afsona yoki haqiqat? Haftalik reytingda o'z o'rningizni toping ⭐",
     "Keto haqida ko'p gaplar yuradi: «mevalar umuman mumkin emas», «yog' semirtiradi»... "
     "«Afsona yoki haqiqat» o'yinida 10 ta gapni ajratasiz, har biriga qisqa izoh bilan.",
     ["✨ Har o'yinda bitta «oltin savol» — ikki ochko",
      "🏆 Haftaning eng zo'rlari reytingi — har dushanba yangilanadi",
      "📤 Natijangizni do'stingizga yuborib, bellashing"],
     "«Yog' yesangiz semirasiz» — afsonami yoki haqiqat?"),
    (SHOP, "Mahsulot tugab qolsa nima qilish kerak? 🔔",
     "Ba'zi mahsulotlar tez sotiladi. Tugagan mahsulot saytdan yo'qolmaydi: uning sahifasida "
     "«Kelganda xabar bering» tugmasi bor — mahsulot kelishi bilan bot sizga yozadi.",
     ["🔔 Bir bosish — kelganda xabar",
      "🚚 «Yo'lda» belgisi — mahsulot tez orada keladi",
      "🛒 Savatdagi mahsulot bir necha soat siz uchun band turadi"],
     "Qaysi mahsulot kelishini kutyapsiz?"),
]


def _now_tk() -> datetime:
    return datetime.utcnow() + TZ_OFFSET


def is_post_day(day: date) -> bool:
    return day >= START and (day - START).days % EVERY_DAYS == 0


def post_for(day: date) -> tuple:
    return POSTS[((day - START).days // EVERY_DAYS) % len(POSTS)]


def next_post_day(day: date) -> date:
    nxt = max(day, START)
    while not is_post_day(nxt):
        nxt += timedelta(days=1)
    return nxt


def _link(kind: str) -> str:
    if kind == GAMES:
        return channel_link.link_line(f"https://t.me/{BOT_USERNAME}/shop?startapp=oyin", "🎮 Ўйинларни очиш")
    return channel_link.link_line(channel_link.SHOP_URL, channel_link.SHOP_LABEL)


def post_text(post: tuple) -> str:
    from keto_fakt import to_channel_script

    def t(s: str) -> str:
        return html.escape(to_channel_script(s), quote=False)
    kind, title, body, lines, question = post
    return (f"<b>{t(title)}</b>\n\n{t(body)}\n\n" + "\n".join(t(x) for x in lines)
            + f"\n\n{_link(kind)}\n\n💬 {t(question)}\n\n{HASHTAG}")


async def is_enabled() -> bool:
    try:
        async with database.pool.acquire() as conn:
            value = await conn.fetchval("SELECT value FROM app_settings WHERE key = $1", SETTING)
        return value != "0"
    except Exception:
        return True


async def set_enabled(on: bool) -> None:
    async with database.pool.acquire() as conn:
        await conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        await conn.execute("INSERT INTO app_settings (key, value) VALUES ($1, $2) "
                           "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", SETTING, "1" if on else "0")


async def _tick(bot: Bot) -> None:
    now = _now_tk()
    day = now.date()
    if not REQUIRED_CHANNEL_ID or not is_post_day(day) or (now.hour, now.minute) < POST_AT or now.hour >= LAST_HOUR:
        return
    if not await is_enabled():
        return
    key = f"channel-features-{day.isoformat()}"
    if not await database.claim_release_notes(key):
        return
    post = post_for(day)
    try:
        import channel_voice
        text = await channel_voice.rewrite(post_text(post), "imkoniyat", 4096)
        await bot.send_message(REQUIRED_CHANNEL_ID, text, parse_mode=ParseMode.HTML,
                               disable_web_page_preview=True)
    except Exception:
        await database.release_release_notes(key)
        logger.exception("Channel features post failed (%s)", key)
        return
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"📣 <b>Kanalga «Saytda nima bor?» chiqdi:</b> "
                                             f"{html.escape(post[1], quote=False)}\nKeyingisi: /imkoniyat_test",
                                   parse_mode=ParseMode.HTML, disable_notification=True)
        except Exception:
            pass


async def scheduler_loop(bot: Bot) -> None:
    while True:
        try:
            await _tick(bot)
        except Exception:
            logger.exception("Channel features tick failed")
        await asyncio.sleep(CHECK_EVERY)


@router.message(Command("imkoniyat_test"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_preview(message: Message):
    day = next_post_day(_now_tk().date())
    state = "✅ yoqilgan" if await is_enabled() else "⏸ to'xtatilgan (/imkoniyat_on)"
    await message.answer(f"📱 <b>«Saytda nima bor?»</b> — {state}. Navbatdagisi: {day:%d.%m} soat "
                         f"{POST_AT[0]:02d}:{POST_AT[1]:02d} da ({len(POSTS)} ta post aylanadi, har {EVERY_DAYS} kunda):",
                         parse_mode=ParseMode.HTML)
    await message.answer(post_text(post_for(day)), parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@router.message(Command("imkoniyat_off"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_off(message: Message):
    await set_enabled(False)
    await message.answer("⏸ «Saytda nima bor?» to'xtatildi. Yoqish: /imkoniyat_on")


@router.message(Command("imkoniyat_on"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_on(message: Message):
    await set_enabled(True)
    await message.answer(f"✅ «Saytda nima bor?» yoqildi — har {EVERY_DAYS} kunda soat 17:30 da. Ko'rish: /imkoniyat_test")
