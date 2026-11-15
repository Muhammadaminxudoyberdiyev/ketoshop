"""Bitta userga kuniga nechta rejali xabar — umumiy chegara (egasi, 2026-11-15:
"kuniga 3–3,5 ta bu juda ko'p, maximum 2 ta, 3 kun ichida botda umuman tugma
bosmasa unda 1 ta kuniga" va "Hali xarid qilmagan user … maximum 1 ta").

Chegara (Toshkent kuni bo'yicha):
  * xaridor (bekor qilinmagan buyurtmasi bor) va oxirgi QUIET_AFTER_DAYS kunda
    botda tugma bosgan, yozgan yoki saytni ishlatgan — ACTIVE_BUYER_MAX (2);
  * qolgan hamma — xarid qilmaganlar va 3 kundan beri jimlar — QUIET_MAX (1).

Rejali, hammaga boradigan xabarlar shu darvozadan o'tadi (claim): maslahat,
shaxsiy tavsiya, aksiya ko'rgazmasi/e'loni, kun mahsuloti, qiziqish eslatmasi,
Keto savol, qayta sotuv, tashlab ketilgan savat, sovg'a kampaniyasi e'loni.
Kun ichida birinchi kelgan yuboradi: 08:00 maslahat → 09:30 qayta sotuv →
10:00 tavsiya → 12:00 aksiya → 13:00 kun mahsuloti → 18:00 qiziqish →
20:00 Keto savol.

Darvozadan o'tmaydi (hisobga ham kirmaydi): buyurtma va to'lov xabarlari, odam
o'zi so'ragani («Kelganda xabar bering», AI suhbat), yangi a'zoning birinchi
kungi tanishuvi (til, video, 100 Keto, YANGI5), admin qo'lda yuborgan xabar.
"""
from __future__ import annotations

import logging

import database

logger = logging.getLogger(__name__)

ACTIVE_BUYER_MAX = 2
QUIET_MAX = 1
QUIET_AFTER_DAYS = 3


async def claim(user_id: int, kind: str) -> bool:
    """True — shu xabar bugun yuborilishi mumkin (va hisobga yozildi);
    False — bugungi chegara to'lgan. Baza xatosida False: chegara
    hech qachon oshib ketmasin."""
    try:
        return await database.claim_user_push(user_id, kind, ACTIVE_BUYER_MAX, QUIET_MAX, QUIET_AFTER_DAYS)
    except Exception:
        logger.exception("push cap: claim failed for %s (%s) — not sent", user_id, kind)
        return False


# ─────────────────────────────── /xabar_soni ────────────────────────────────
from aiogram import Router  # noqa: E402
from aiogram.filters import Command  # noqa: E402
from aiogram.types import Message  # noqa: E402

router = Router(name="push_cap")

KIND_NAMES = {"tips": "Keto maslahat", "reco": "Shaxsiy tavsiya", "aksiya": "Aksiya", "kun_mahsuloti": "Kun mahsuloti",
              "qiziqish": "Qiziqish eslatmasi", "keto_savol": "Keto savol", "qayta_sotuv": "Qayta sotuv",
              "savat": "Savat eslatmasi", "sovga": "Sovg'a kampaniyasi"}


def stats_text(st: dict, days: int) -> str:
    per_user_day = st["total"] / st["user_days"] if st["user_days"] else 0
    lines = [f"📨 <b>Rejali xabarlar — oxirgi {days} kun</b>", "",
             f"Jami: <b>{st['total']}</b> ta, {st['users']} ta userga",
             f"Xabar olgan userga kuniga o'rtacha: <b>{per_user_day:.1f}</b> ta",
             f"Chegara: faol xaridorga kuniga {ACTIVE_BUYER_MAX} ta, xarid qilmagan va "
             f"{QUIET_AFTER_DAYS} kundan beri jimlarga {QUIET_MAX} ta", ""]
    for kind, n in st["kinds"].items():
        lines.append(f"• {KIND_NAMES.get(kind, kind)}: {n}")
    lines.append("")
    lines.append("Buyurtma xabarlari, «Kelganda xabar bering», AI suhbat va yangi a'zoning birinchi kuni "
                 "hisobga kirmaydi.")
    return "\n".join(lines)


@router.message(Command("xabar_soni"))
async def cmd_push_stats(message: Message):
    from config import ADMIN_IDS
    if message.from_user.id not in ADMIN_IDS:
        return
    st = await database.user_push_stats(7)
    await message.answer(stats_text(st, 7), parse_mode="HTML")
