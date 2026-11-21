"""
"Nima yangi" — one message to every admin after a deploy (2026-09-17).

broadcast_updates_script.py does the same job by hand, but it has to be run on
the server with production credentials. This sends the notes from the running
bot itself, so a deploy through GitHub is enough.

Each release has a KEY. The first time a bot with that key runs, the notes go
to every admin — hardcoded and the ones added through the bot (bot.py merges
those into ADMIN_IDS at startup) — once, during daytime. The key is claimed in
the database before sending, so restarts and redeploys never repeat it.

For the next release: change RELEASE_KEY and rewrite NOTES.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.enums import ParseMode

import database
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

RELEASE_KEY = "2026-11-21-oyinlar-kuryer-tezlik"
TZ_OFFSET = timedelta(hours=5)
SEND_WINDOW = (8, 22)          # never wake admins at night
# True bypasses the daytime window (used 2026-09-25, and 2026-10-22 at 03:00
# when the owner said "hozir yubor"). Tied to this release's key, so the next
# release is back to daytime without anyone remembering to switch it off.
SEND_NOW = RELEASE_KEY == "2026-10-22-sayt-yangiliklari"
CHECK_EVERY = 300

NOTES = (
    "🆕 <b>Nima yangi (17–21.11): o'yinlar, kuryer tugmalari, buyurtma manbai, tezlik</b>\n"
    "\n"
    "📦 <b>Buyurtmalar</b>\n"
    "1. Har yangi buyurtma kartochkasida <b>«🧭 Qayerdan»</b> qatori: 💬 botdan / 🌐 saytdan / 📱 ilovadan, "
    "AI bilan gaplashganmi, 📸 Instagram, reklama, bloger yoki do'st taklifi. Hisobot: /buyurtma_manba\n"
    "2. «Barcha buyurtmalar» ro'yxatida endi <b>📍 manzil</b> va Yandex xarita havolasi bor.\n"
    "3. ✏️ Bot va saytdan kelgan buyurtmani <b>yo'lga chiqqandan va yetkazilgandan keyin ham</b> "
    "tahrirlash mumkin («Tarkibni o'zgartirish») — ombor farq bo'yicha o'zgaradi.\n"
    "\n"
    "🚚 <b>Kuryer</b>\n"
    "4. Kuryer profiliga keladigan har buyurtma kartochkasida tugmalar: <b>🚚 Yo'lga chiqdi → 🏁 Yetkazildi</b>, "
    "«↩️ Yetkazilmadi — qaytarish», «🧭 Marshrut», «💬 Mijozga yozish». Bosilganda mijozga xabar ketadi.\n"
    "\n"
    "🎁 <b>Eritritol sovg'asi</b>\n"
    "5. 20.11 dan yana <b>40 kun (30.12 gacha)</b> har bot/sayt buyurtmasiga 100 gr Eritritol.\n"
    "\n"
    "🎮 <b>Saytda o'yinlar markazi</b>\n"
    "6. 7 ta yangi o'yin: 🧩 «3 ta ishora» (kunlik jumboq), 📖 «Keto yo'li: 30 kun», 🗺 «Ketoland xaritasi», "
    "🔁 «Almashtir!», 🏷 «Yorliq detektivi», ⭐ «Afsona yoki haqiqat», 🧺 «Bozor sarguzashti». "
    "Ketma-ketlik 🔥, kunlik 3 topshiriq, haftalik reyting; o'yinlardan Keto kuniga ko'pi bilan 60. "
    "Statistika: /oyinlar\n"
    "7. O'ynayotganlarga har kuni 07:30 da seriya eslatmasi (kunlik xabar chegarasi ichida, 🔕 bilan o'chiriladi). "
    "Boshqaruv: /oyin_eslatma\n"
    "\n"
    "⚡ <b>Sayt</b>\n"
    "8. Bosh sahifa ancha tez ochiladi; o'yinlarda to'g'ri javob endi qotmaydi.\n"
    "9. Musiqa balandroq, sahifa bilan darhol boshlanadi va o'zidan o'chib qolmaydi. Qushlar — "
    "<b>haqiqiy yozuvlar</b>: Bulbul, Zarg'aldoq, Qorayaloq, To'rg'ay, Chittak va boshqalar, nomi bilan.\n"
    "10. Saytda vaqt uchun Keto tabrigida endi <b>«🛒 Xarid qilish»</b> tugmasi (savatda narsa bo'lsa — "
    "«Savatga — Keto bilan to'lash»).\n"
    "11. «Yordamchi» tugmasi faqat bosh sahifa va katalogda, pastga aylantirganda yashirinadi.\n"
    "\n"
    "📱 <b>Android ilova</b>\n"
    "12. Ilovada do'kon — saytning o'zi; ilova belgisi — Ketoshop logosi.\n"
    "\n"
    "G'alati narsa ko'rsangiz — skrinshot yuboring.\n"
    "\n"
    "Rahmat 🤝"
)


def _now_tk() -> datetime:
    return datetime.utcnow() + TZ_OFFSET


async def send_if_due(bot: Bot) -> bool:
    if not SEND_NOW and not (SEND_WINDOW[0] <= _now_tk().hour < SEND_WINDOW[1]):
        return False
    if not await database.claim_release_notes(RELEASE_KEY):
        return False                    # already sent for this release
    sent = failed = 0
    for admin_id in list(dict.fromkeys(ADMIN_IDS)):
        try:
            await bot.send_message(admin_id, NOTES, parse_mode=ParseMode.HTML)
            sent += 1
        except Exception as exc:
            failed += 1
            logger.warning("Release notes to admin %s failed: %s", admin_id, exc)
        await asyncio.sleep(0.05)
    logger.info("Release notes %s: %d sent, %d failed", RELEASE_KEY, sent, failed)
    return True


async def scheduler_loop(bot: Bot) -> None:
    while True:
        try:
            if await send_if_due(bot):
                return
        except Exception:
            logger.exception("Release notes check failed")
        await asyncio.sleep(CHECK_EVERY)
