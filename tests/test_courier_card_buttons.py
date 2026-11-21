"""Kuryer kartochkasidagi holat tugmalari (egasi, 2026-11-21). Bazaga va
Telegram'ga ulanmaydi."""
import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import database
import order_admin_feed
from handlers import courier

ORDER = {"id": 7, "user_id": 10, "status": "confirmed", "delivery_method": "courier",
         "latitude": 41.3, "longitude": 69.2, "address": "Chilonzor"}


def texts(kb):
    return [b.text for row in kb.inline_keyboard for b in row] if kb else []


class KeyboardTest(unittest.TestCase):
    def test_next_step_by_status(self):
        self.assertIn("🚚 Yo'lga chiqdi", texts(courier.card_keyboard(ORDER)))
        carrying = texts(courier.card_keyboard(dict(ORDER, status="shipped"), "ali"))
        self.assertIn("🏁 Yetkazildi", carrying)
        self.assertIn("↩️ Yetkazilmadi — qaytarish", carrying)
        self.assertIn("💬 Mijozga yozish", carrying)
        for status in ("pending", "delivered", "cancelled"):
            self.assertIsNone(courier.card_keyboard(dict(ORDER, status=status)))
        self.assertIsNone(courier.card_keyboard(dict(ORDER, delivery_method="pickup")))

    def test_watcher_card_gets_it_admin_keeps_seller_buttons(self):
        with patch.object(order_admin_feed, "ADMIN_IDS", [1]):
            watcher = order_admin_feed._markup(ORDER, "uz", 3, None)
            self.assertEqual(watcher.inline_keyboard[0][0].callback_data, "cwq:ship:7")
            admin = order_admin_feed._markup(ORDER, "uz", 1, None)
            self.assertFalse(any(b.callback_data and b.callback_data.startswith("cwq:")
                                 for row in admin.inline_keyboard for b in row))


class Conn:
    def __init__(self, row):
        self.row, self.sql = row, []

    async def fetchrow(self, *a):
        return self.row

    async def execute(self, sql, *a):
        self.sql.append(sql)


class Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return False
        return Ctx()


class StepTest(unittest.TestCase):
    def press(self, data, row):
        cb = MagicMock()
        cb.data = data
        cb.from_user.id = 3
        cb.answer = AsyncMock()
        cb.message.edit_reply_markup = AsyncMock()
        bot = MagicMock()
        bot.send_message = AsyncMock()
        conn = Conn(row)
        with patch.object(database, "pool", Pool(conn)), patch("config.ORDER_WATCHER_IDS", [3]), \
             patch.object(courier, "_feed") as feed, \
             patch.object(courier, "_rewards", AsyncMock()) as rewards, \
             patch.object(database, "get_user_language", AsyncMock(return_value="uz")):
            asyncio.run(courier.cb_card_step(cb, bot))
        return conn, feed, rewards, bot, cb

    def test_ship_then_deliver(self):
        conn, feed, rewards, bot, _ = self.press("cwq:ship:7", dict(ORDER))
        self.assertIn("status = 'shipped'", conn.sql[0])
        self.assertEqual(feed.call_args.args[2:4], ("confirmed", "shipped"))
        self.assertIn("yo'lga chiqdi", bot.send_message.await_args.args[1])
        rewards.assert_not_awaited()
        conn, feed, rewards, bot, _ = self.press("cwq:done:7", dict(ORDER, status="shipped"))
        self.assertIn("status = 'delivered'", conn.sql[0])
        rewards.assert_awaited_once()

    def test_wrong_order_of_steps_is_refused(self):
        conn, feed, _, _, cb = self.press("cwq:done:7", dict(ORDER))
        self.assertEqual(conn.sql, [])
        feed.assert_not_called()
        self.assertTrue(cb.answer.await_args.kwargs.get("show_alert"))

    def test_back_unassigns(self):
        conn, feed, _, bot, _ = self.press("cwq:back:7", dict(ORDER, status="shipped"))
        self.assertIn("courier_id = NULL", conn.sql[0])
        bot.send_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()


class OrderListAddressTest(unittest.TestCase):
    """«Барча буюртмалар» ro'yxatida manzil (egasi, 2026-11-21: "Адрес ҳам кўринсин")."""

    def render(self, orders):
        from handlers import admin
        cb = MagicMock()
        cb.message.edit_text = AsyncMock()
        with patch.object(admin, "get_all_orders", AsyncMock(return_value=(orders, len(orders)))):
            asyncio.run(admin.render_orders_list(cb, "confirmed", 0, "uz"))
        return cb.message.edit_text.await_args_list[0].args[0], cb.message.edit_text.await_args_list[0].kwargs

    def test_address_and_map_link(self):
        from datetime import datetime
        o = dict(ORDER, total=112000, customer_name="Ali", phone="+998901234567",
                 created_at=datetime(2026, 11, 19, 12, 36), address="Chilonzor 9-kvartal, 12-uy")
        text, kw = self.render([o])
        self.assertIn("📍 Chilonzor 9-kvartal, 12-uy", text)
        self.assertIn("yandex.uz/maps", text)
        self.assertTrue(kw.get("disable_web_page_preview"))

    def test_a_full_page_still_fits_one_message(self):
        from datetime import datetime
        orders = [dict(ORDER, id=i, total=112000, customer_name="Ali Valiyev Toshkent", phone="+998901234567",
                       created_at=datetime(2026, 11, 19, 12, 36), confirmed_at=datetime(2026, 11, 19, 12, 40),
                       address="Toshkent shahri, Chilonzor tumani, 9-kvartal, 12-uy, 45-xonadon, mo'ljal: maktab")
                  for i in range(15)]
        text, _ = self.render(orders)
        self.assertLessEqual(len(text), 4096)
        self.assertIn("📍", text)
