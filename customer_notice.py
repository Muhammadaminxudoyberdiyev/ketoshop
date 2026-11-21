"""
Bir martalik xabar bitta mijozga — egasi matnni tasdiqlagandan keyin.

2026-11-21: mijoz (id 6908484737) saytimizga kirgach "jarima" haqida SMS kelganini
yozdi; AI javob bera olmadi. Ketoshop SMS yubormaydi va jarima qo'ymaydi — egasi:
"agar mijoz adashtirayotgan yoki xato qilayotgan bo'lsa unda unga buni bildirib
isbotlab bot orqali xabar yubor va undan avval menga tasdiqlat" → matn ko'rsatildi,
egasi "ok tasdiqlayman" dedi (buyurtmasi yo'qligini ham tasdiqladi).

Each notice: (key, user_id, text). Sent once (the key is claimed in the database
before sending), in daytime only (09:00–21:00 Tashkent), then the admins are told.
For a future one: add a tuple with a new key.
"""
import asyncio
import html
import logging
from datetime import datetime, timedelta

from aiogram import Bot

import database
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

WINDOW = (9, 21)
CHECK_EVERY = 300

NOTICES = [
    ("notice-2026-11-21-sms-jarima", 6908484737,
     "Ассалому алайкум, Моҳира опа! Ketoshop'дан ёзяпмиз.\n\n"
     "Хотиржам бўлинг: <b>Ketoshop ҳеч қачон СМС юбормайди ва жарима қўймайди.</b> Биз фақат шу "
     "Telegram бот орқали ёзамиз. Сайтимизга кириш, маҳсулотларни кўриш ва саватга солиш бепул ва "
     "сизни ҳеч нарсага мажбурламайди. Буюртма бермаган бўлсангиз, сиздан ҳеч нарса талаб қилинмайди.\n\n"
     "Келган СМС бизнинг дўкондан эмас. У бошқа хизматдан (масалан, саватга нарса солган бошқа дўкон "
     "ёки банк) ёки фирибгарлардан бўлиши мумкин. Илтимос:\n"
     "• СМСдаги ҳаволани очманг;\n"
     "• карта рақами, СМС код ва паролни ҳеч кимга берманг;\n"
     "• жарима ростми — банк иловангизда ёки my.gov.uz да текширинг.\n\n"
     "Ноқулайлик учун узр. Саволингиз бўлса, шу ерга ёзинг, ёрдам берамиз 🤝"),
]


def _now_tk() -> datetime:
    return datetime.utcnow() + timedelta(hours=5)


async def _tick(bot: Bot) -> bool:
    """True when nothing is left to send."""
    if not WINDOW[0] <= _now_tk().hour < WINDOW[1]:
        return False
    for key, user_id, text in NOTICES:
        if not await database.claim_release_notes(key):
            continue                                   # already sent
        try:
            await bot.send_message(user_id, text, parse_mode="HTML")
            result = "✅ yuborildi"
        except Exception as exc:
            logger.warning("customer notice %s to %s failed: %s", key, user_id, exc)
            result = f"⚠️ yetmadi ({html.escape(type(exc).__name__)})"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"📨 <b>Mijozga tasdiqlangan xabar</b> ({user_id}): {result}",
                                       parse_mode="HTML", disable_notification=True)
            except Exception:
                pass
    return True


async def scheduler_loop(bot: Bot) -> None:
    await asyncio.sleep(60)
    while True:
        try:
            if await _tick(bot):
                return
        except Exception:
            logger.exception("customer notice tick failed")
        await asyncio.sleep(CHECK_EVERY)
