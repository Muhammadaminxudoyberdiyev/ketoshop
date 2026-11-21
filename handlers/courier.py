import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import database
from config import ADMIN_IDS

# The bot menu works on the same statuses as the Kuryer board (courier_board
# .COLUMNS): an order waiting for a courier is confirmed / preparing / ready,
# one a courier took is 'shipped' («Yo'lda»). Until 2026-11-06 a pickup here
# wrote 'delivering', which no board column shows — the order vanished from
# the board while the courier carried it. 'delivering' stays readable for
# orders taken before that.
_WAITING = ("confirmed", "preparing", "ready")
_CARRYING = ("shipped", "delivering")

router = Router()
logger = logging.getLogger(__name__)

def _feed(bot: Bot, order_id: int, old: str | None, new: str, by) -> None:
    """The status card every admin and order watcher gets — the same one the
    board and the seller buttons send (order_admin_feed)."""
    try:
        import order_admin_feed
        order_admin_feed.status_changed(bot, order_id, old, new, by)
    except Exception:
        logger.exception("order feed for courier move #%s failed", order_id)


# ── Holat tugmalari buyurtma kartochkasining o'zida (owner, 2026-11-21:
# "kuryer uchun ochilgan profilda ... tugmalar kuryer statuslari uchun qo'shib
# ber chiqib turishi kerak, yo'lga chiqdi, yetkazildi vahokazo"; "faqat 2 ta
# tugma emas, boshqa tugmalar ham kerak bo'lsa qo'shgin"). The order watcher
# (config.ORDER_WATCHER_IDS, a courier) gets every status card; the card now
# carries the courier's next step, the route and a way to write to the buyer.
# A step moves the order exactly as the courier menu does, and the fresh
# status card comes back with the step after.

def card_keyboard(order: dict, username: str | None = None) -> InlineKeyboardMarkup | None:
    status = order.get("status")
    oid = order.get("id")
    if not oid or order.get("delivery_method") == "pickup" or status in ("pending", "cancelled", "delivered"):
        return None
    rows = []
    if status in _WAITING:
        rows.append([InlineKeyboardButton(text="🚚 Yo'lga chiqdi", callback_data=f"cwq:ship:{oid}")])
    elif status in _CARRYING:
        rows.append([InlineKeyboardButton(text="🏁 Yetkazildi", callback_data=f"cwq:done:{oid}")])
        rows.append([InlineKeyboardButton(text="↩️ Yetkazilmadi — qaytarish", callback_data=f"cwq:back:{oid}")])
    links = []
    try:
        import order_admin_feed
        route = order_admin_feed.map_url(order)
    except Exception:
        route = None
    if route:
        links.append(InlineKeyboardButton(text="🧭 Marshrut", url=route))
    if username:
        links.append(InlineKeyboardButton(text="💬 Mijozga yozish", url=f"https://t.me/{username}"))
    if links:
        rows.append(links)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def _rewards(order: dict, bot: Bot) -> None:
    """Delivery rewards — the same three the courier menu triggers; each is
    idempotent per order."""
    for name, mod, func in (("Keto", "gamification", "award_keto_for_order"),
                            ("Blogger", "bloggers", "award_for_order"),
                            ("Referral", "referral_program", "award_order_cashback")):
        try:
            module = __import__(mod)
            await getattr(module, func)(order, bot)
        except Exception:
            logger.exception("%s reward failed for card-delivered order %s", name, order.get("id"))


_BUYER = {
    "shipped": ("🚚 Buyurtmangiz #{id} yo'lga chiqdi!", "🚚 Ваш заказ #{id} в пути!"),
    "delivered": ("✅ Buyurtmangiz #{id} yetkazib berildi!", "✅ Ваш заказ #{id} доставлен!"),
}


@router.callback_query(F.data.startswith("cwq:"))
async def cb_card_step(callback: CallbackQuery, bot: Bot):
    from config import ORDER_WATCHER_IDS
    uid = callback.from_user.id
    if uid not in ORDER_WATCHER_IDS and not await is_courier(uid):
        await callback.answer()
        return
    try:
        _, step, oid = callback.data.split(":")
        order_id = int(oid)
    except ValueError:
        await callback.answer()
        return
    async with database.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
        if not row:
            await callback.answer("Buyurtma topilmadi.", show_alert=True)
            return
        order = dict(row)
        if step == "ship":
            if order["status"] not in _WAITING:
                await callback.answer("Bu buyurtma allaqachon yo'lda yoki yopilgan.", show_alert=True)
                return
            await conn.execute(
                "UPDATE orders SET courier_id = COALESCE(courier_id, $1), status = 'shipped', "
                "shipped_at = COALESCE(shipped_at, CURRENT_TIMESTAMP) WHERE id = $2", uid, order_id)
            new = "shipped"
        elif step == "done":
            import sinov_buyurtma
            if sinov_buyurtma.is_test(order):
                await callback.answer(sinov_buyurtma.NO_DELIVERY, show_alert=True)
                return
            if order["status"] not in _CARRYING:
                await callback.answer("Avval «🚚 Yo'lga chiqdi» bo'lishi kerak.", show_alert=True)
                return
            await conn.execute(
                "UPDATE orders SET status = 'delivered', courier_id = COALESCE(courier_id, $1), "
                "delivered_at = COALESCE(delivered_at, CURRENT_TIMESTAMP) WHERE id = $2", uid, order_id)
            new = "delivered"
        elif step == "back":
            if order["status"] not in _CARRYING:
                await callback.answer("Bu buyurtma yo'lda emas.", show_alert=True)
                return
            await conn.execute("UPDATE orders SET status = 'confirmed', courier_id = NULL WHERE id = $1", order_id)
            new = "confirmed"
        else:
            await callback.answer()
            return
    _feed(bot, order_id, order["status"], new, callback.from_user)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)    # the fresh card brings the next step
    except Exception:
        pass
    await callback.answer({"shipped": "🚚 Yo'lga chiqdi", "delivered": "🏁 Yetkazildi",
                           "confirmed": "↩️ Qaytarildi"}[new])
    if new in _BUYER and order.get("user_id"):
        lang = await database.get_user_language(order["user_id"])
        try:
            await bot.send_message(order["user_id"], _BUYER[new][1 if lang == "ru" else 0].format(id=order_id))
        except Exception:
            pass
    if new == "delivered":
        await _rewards(dict(order, status="delivered"), bot)


async def is_courier(user_id: int) -> bool:
    couriers = await database.get_courier_ids()
    return user_id in couriers or user_id in ADMIN_IDS

def get_courier_keyboard(lang: str) -> InlineKeyboardMarkup:
    from keyboards import courier_panel_button
    board = courier_panel_button(lang)
    return InlineKeyboardMarkup(inline_keyboard=([[board]] if board else []) + [
        [InlineKeyboardButton(text="📦 Yangi buyurtmalar", callback_data="courier:new_orders")],
        [InlineKeyboardButton(text="🚚 Mening buyurtmalarim", callback_data="courier:my_orders")]
    ])

@router.message(Command("addcourier"), F.chat.type == "private")
async def cmd_add_courier(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Format: /addcourier [user_id]")
        return
        
    courier_id = int(parts[1])
    await database.add_courier_db(courier_id, message.from_user.id)
    await message.answer(f"✅ Kuryer qo'shildi: {courier_id}")

@router.message(Command("rmcourier"), F.chat.type == "private")
async def cmd_rm_courier(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Format: /rmcourier [user_id]")
        return
        
    courier_id = int(parts[1])
    await database.remove_courier_db(courier_id)
    await message.answer(f"❌ Kuryer o'chirildi: {courier_id}")

@router.message(Command("courier"), F.chat.type == "private")
async def cmd_courier(message: Message, state: FSMContext):
    if not await is_courier(message.from_user.id):
        return
    
    lang = await database.get_user_language(message.from_user.id)
    await message.answer(
        "📦 <b>Kuryer paneli</b>\n\nQuyidagi menyudan kerakli bo'limni tanlang:",
        reply_markup=get_courier_keyboard(lang),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("courier:"))
async def courier_callback_handler(callback: CallbackQuery, bot: Bot):
    if not await is_courier(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
        
    parts = callback.data.split(":")
    action = parts[1]
    
    lang = await database.get_user_language(callback.from_user.id)
    
    async def get_new_orders():
        async with database.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM orders WHERE status = ANY($1::text[]) AND delivery_method IS DISTINCT FROM 'pickup' AND courier_id IS NULL ORDER BY created_at ASC", list(_WAITING))
            
    async def get_my_orders():
        async with database.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM orders WHERE courier_id = $1 AND status = ANY($2::text[]) ORDER BY created_at ASC", callback.from_user.id, list(_CARRYING))
            
    def build_text(row, total_count, current_idx, title="Yangi buyurtma"):
        return (
            f"📦 <b>{title}</b> ({current_idx + 1}/{total_count})\n\n"
            f"🛒 <b>Buyurtma #{row['id']}</b>\n"
            f"👤 Ism: {row['customer_name']}\n"
            f"📞 Telefon: {row['phone']}\n"
            f"📍 Manzil: {row['address']}\n"
            f"💵 Summa: {row['total']:,.0f} so'm\n"
            f"🕒 Vaqt: {row['created_at'].strftime('%d.%m %H:%M')}\n"
        )
        
    def build_nav_kb(action_type, current_idx, total_count, row_id):
        kb = []
        
        # Action buttons
        if action_type == "new":
            kb.append([InlineKeyboardButton(text="✅ Olib ketish (Pick up)", callback_data=f"courier:pickup:{row_id}:{current_idx}")])
        elif action_type == "my":
            kb.append([
                InlineKeyboardButton(text="🏁 Yetkazildi", callback_data=f"courier:delivered:{row_id}:{current_idx}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"courier:cancel:{row_id}:{current_idx}")
            ])
            
        # Pagination buttons
        nav_row = []
        if total_count > 1:
            prev_idx = (current_idx - 1) % total_count
            next_idx = (current_idx + 1) % total_count
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"courier:nav_{action_type}:{prev_idx}"))
            nav_row.append(InlineKeyboardButton(text=f"{current_idx + 1}/{total_count}", callback_data="ignore"))
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"courier:nav_{action_type}:{next_idx}"))
            kb.append(nav_row)
            
        kb.append([InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="courier:menu")])
        return InlineKeyboardMarkup(inline_keyboard=kb)

    async def show_list(action_type: str, idx: int, empty_text: str):
        """Redraw an orders list in place after a status change. When it has
        run dry, open the other list instead of dropping the courier on the
        menu (owner request 2026-10-01): after a pickup that's their own
        deliveries, after a delivery it's the next orders to take."""
        title = {"new": "Yangi buyurtma", "my": "Mening buyurtmam"}
        for kind in (action_type, "my" if action_type == "new" else "new"):
            orders = await get_new_orders() if kind == "new" else await get_my_orders()
            if orders:
                i = min(idx, len(orders) - 1) if kind == action_type else 0
                await callback.message.edit_text(
                    build_text(orders[i], len(orders), i, title[kind]),
                    reply_markup=build_nav_kb(kind, i, len(orders), orders[i]['id']),
                    parse_mode="HTML")
                return
        await callback.message.edit_text(empty_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Yangi buyurtmalar", callback_data="courier:new_orders")],
            [InlineKeyboardButton(text="🚚 Mening buyurtmalarim", callback_data="courier:my_orders")],
        ]))

    # Main Menu
    if action == "menu":
        await callback.message.edit_text(
            "📦 <b>Kuryer paneli</b>\n\nQuyidagi menyudan kerakli bo'limni tanlang:",
            reply_markup=get_courier_keyboard(lang),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    # Entry points
    if action in ("new_orders", "my_orders"):
        action_type = "new" if action == "new_orders" else "my"
        orders = await get_new_orders() if action_type == "new" else await get_my_orders()
        
        if not orders:
            await callback.answer("Hozircha buyurtmalar yo'q.", show_alert=True)
            return
            
        text = build_text(orders[0], len(orders), 0, "Yangi buyurtma" if action_type == "new" else "Mening buyurtmam")
        kb = build_nav_kb(action_type, 0, len(orders), orders[0]['id'])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        return
        
    # Navigation
    if action in ("nav_new", "nav_my"):
        action_type = "new" if action == "nav_new" else "my"
        idx = int(parts[2])
        orders = await get_new_orders() if action_type == "new" else await get_my_orders()
        
        if not orders:
            await callback.message.edit_text("Buyurtmalar tugadi.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="courier:menu")]]))
            return
            
        if idx >= len(orders):
            idx = 0
            
        text = build_text(orders[idx], len(orders), idx, "Yangi buyurtma" if action_type == "new" else "Mening buyurtmam")
        kb = build_nav_kb(action_type, idx, len(orders), orders[idx]['id'])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        return

    # Actions: pickup
    if action == "pickup":
        order_id = int(parts[2])
        idx = int(parts[3])
        
        async with database.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
            if not row or row["courier_id"] is not None or row.get("delivery_method") == "pickup" or row.get("status") not in _WAITING:
                await callback.answer("Bu buyurtma allaqachon boshqa kuryer tomonidan olingan yoki topilmadi!", show_alert=True)
            else:
                await conn.execute(
                    "UPDATE orders SET courier_id = $1, status = 'shipped', "
                    "shipped_at = COALESCE(shipped_at, CURRENT_TIMESTAMP) WHERE id = $2",
                    callback.from_user.id, order_id)
                _feed(bot, order_id, row["status"], "shipped", callback.from_user)
                await callback.answer("Buyurtmani olib ketdingiz!", show_alert=True)
                # Notify user
                user_lang = await database.get_user_language(row["user_id"])
                try:
                    msg = f"🚚 Ваш заказ #{order_id} передан курьеру!" if user_lang == 'ru' else f"🚚 Buyurtmangiz #{order_id} kuryerga topshirildi!"
                    await bot.send_message(row["user_id"], msg)
                except Exception:
                    pass
        
        # Refresh the new orders list, staying at the same index (which now points to the next order)
        await show_list("new", idx, "Yangi buyurtmalar qolmadi.")
        return

    # Actions: delivered / cancel
    if action in ("delivered", "cancel"):
        order_id = int(parts[2])
        idx = int(parts[3])
        
        delivered_order = None
        async with database.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM orders WHERE id = $1 AND courier_id = $2", order_id, callback.from_user.id)
            import sinov_buyurtma
            if row and action == "delivered" and sinov_buyurtma.is_test(dict(row)):
                # A 🧪 test order never "arrives" — that would book the courier
                # expense, Keto and cashback for nothing.
                await callback.answer(sinov_buyurtma.NO_DELIVERY, show_alert=True)
                return
            if row:
                if action == "delivered":
                    await conn.execute(
                        "UPDATE orders SET status = 'delivered', "
                        "delivered_at = COALESCE(delivered_at, CURRENT_TIMESTAMP) WHERE id = $1",
                        order_id)
                    _feed(bot, order_id, row["status"], "delivered", callback.from_user)
                    await callback.answer("Yetkazib berildi!", show_alert=True)
                    user_lang = await database.get_user_language(row["user_id"])
                    try:
                        msg = f"✅ Ваш заказ #{order_id} доставлен!" if user_lang == 'ru' else f"✅ Buyurtmangiz #{order_id} yetkazib berildi!"
                        await bot.send_message(row["user_id"], msg)
                    except Exception:
                        pass
                    delivered_order = dict(row)
                    delivered_order["status"] = "delivered"
                else: # cancel
                    await conn.execute("UPDATE orders SET status = 'confirmed', courier_id = NULL WHERE id = $1", order_id)
                    _feed(bot, order_id, row["status"], "confirmed", callback.from_user)
                    await callback.answer("Buyurtma qaytarildi.", show_alert=True)

        # An order closed out by the courier reaches 'delivered' without ever
        # passing through the seller panel, so both delivery rewards have to
        # be triggered here as well: the buyer's own Keto (gamification.py)
        # and, if they came through a partner link, the blogger's cashback
        # (bloggers.py). Both are idempotent per order, so an order that
        # somehow gets marked delivered twice still pays exactly once. Run
        # outside the pool.acquire() block above — each of them takes its own
        # connection, and neither may hold the courier's UI hostage on error.
        if delivered_order is not None:
            try:
                from gamification import award_keto_for_order
                await award_keto_for_order(delivered_order, bot)
            except Exception:
                logger.exception("Keto award failed for courier-delivered order %s", order_id)
            try:
                import bloggers
                await bloggers.award_for_order(delivered_order, bot)
            except Exception:
                logger.exception("Blogger payout failed for courier-delivered order %s", order_id)
            try:
                import referral_program
                await referral_program.award_order_cashback(delivered_order, bot)
            except Exception:
                logger.exception("Referral cashback failed for courier-delivered order %s", order_id)

        
        # Refresh my orders list
        await show_list("my", idx, "Sizda boshqa yetkazilayotgan buyurtmalar qolmadi.")
        return
