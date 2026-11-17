"""🧭 Buyurtma qayerdan (egasi, 2026-11-17): bot / sayt / ilova, AI, Instagram,
reklama, bloger, do'st — yangi buyurtma kartochkasida va /buyurtma_manba da.

Telegram'ga ulanmaydi. SQL qismi ORDER_ORIGIN_PG_URL berilsa haqiqiy Postgres'da
(o'z sxemasida) tekshiriladi, aks holda o'tkazib yuboriladi."""
import asyncio
import json
import os
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import database
import order_admin_feed
import order_origin as oo
from handlers import cart


def run(coro):
    return asyncio.run(coro)


class LineTest(unittest.TestCase):
    def test_placed_ai_and_touch_in_one_line(self):
        o = {"placed": "webapp", "ai": "site", "touch": {"kind": "instagram"}}
        self.assertEqual(oo.line(o, "uz"),
                         "🧭 Qayerdan: 🌐 Saytdan · 🤖 AI bilan gaplashgan (saytda) · "
                         "📸 Instagram (izoh / Direct havolasi)")
        self.assertEqual(oo.line(json.dumps({"placed": "app"}), "ru"), "🧭 Откуда: 📱 Из приложения")
        self.assertEqual(oo.line({"placed": "bot", "ai": "bot"}, "uz_cyr"),
                         "🧭 Qayerdan: 💬 Botdan · 🤖 AI bilan gaplashgan (botda)")

    def test_every_touch_kind(self):
        cases = [({"kind": "link", "code": "kepak", "name": "Kepak <1>"}, "🔗 Havola: Kepak &lt;1&gt;"),
                 ({"kind": "ad", "source": "ig_eritritol1"}, "📣 Instagram reklamasi (ig_eritritol1)"),
                 ({"kind": "ad", "source": "fb_kepak"}, "📣 Facebook reklamasi (fb_kepak)"),
                 ({"kind": "ad", "source": "tiktok1"}, "📣 Reklama (tiktok1)"),
                 ({"kind": "blogger", "name": "Malika"}, "🎤 Bloger: Malika"),
                 ({"kind": "referral"}, "👥 Do'st taklifi")]
        for touch, text in cases:
            self.assertEqual(oo.touch_text(touch, "uz"), text)

    def test_nothing_for_old_or_broken_records(self):
        for raw in (None, "", "not json", "[]", {"placed": "manual"}):
            self.assertEqual(oo.line(raw, "uz"), "")

    def test_goes_right_under_the_title(self):
        card = "🔔 <b>Yangi buyurtma #5</b>\n\n👤 Ali"
        self.assertEqual(oo.with_line(card, "🧭 Qayerdan: 💬 Botdan"),
                         "🔔 <b>Yangi buyurtma #5</b>\n🧭 Qayerdan: 💬 Botdan\n\n👤 Ali")
        self.assertEqual(oo.with_line(card, ""), card)

    def test_site_or_android_app(self):
        self.assertEqual(oo.place_of({"app_session": 7}), "app")
        self.assertEqual(oo.place_of({}), "webapp")


ORDER = {"id": 5, "user_id": 10, "customer_name": "Ali", "phone": "+998901234567",
         "address": "Chilonzor 5", "status": "pending", "total": 50000,
         "delivery_method": "self", "payment_method": "cash",
         "items": [{"product_id": 1, "name": "Chia", "quantity": 1, "price": 50000, "unit": "piece"}]}


class CardTest(unittest.TestCase):
    def test_new_order_card_says_where_from(self):
        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_location = AsyncMock()
        data = {"customer_name": "Ali", "phone": "+998901234567", "total": 50000, "user_id": 10,
                "username": "ali", "address": "Chilonzor 5", "delivery_method": "self",
                "payment_method": "cash", "status": "pending", "placed": "app"}
        record = AsyncMock(return_value={"placed": "app", "ai": "bot"})
        with patch.object(cart, "ADMIN_IDS", [1]), patch.object(cart, "ORDER_WATCHER_IDS", []), \
             patch.object(cart, "get_order", AsyncMock(return_value=dict(ORDER))), \
             patch.object(cart, "get_user_language", AsyncMock(return_value="uz")), \
             patch.object(cart, "order_history_block", AsyncMock(return_value="")), \
             patch.object(oo, "record", record):
            run(cart._notify_sellers(bot, 5, ORDER["items"], data, "uz"))
        record.assert_awaited_once_with(5, 10, "app")
        text = bot.send_message.await_args_list[0].kwargs["text"]
        self.assertTrue(text.startswith("🔔 <b>Yangi buyurtma #5</b>\n"
                                        "🧭 Qayerdan: 📱 Ilovadan · 🤖 AI bilan gaplashgan (botda)\n"), text)

    def test_bot_is_the_default_and_a_failure_keeps_the_card(self):
        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_location = AsyncMock()
        data = {"customer_name": "Ali", "phone": "+998901234567", "total": 50000, "user_id": 10,
                "address": "Chilonzor 5", "delivery_method": "self", "payment_method": "cash"}
        record = AsyncMock(return_value=None)                     # lookup failed
        with patch.object(cart, "ADMIN_IDS", [1]), patch.object(cart, "ORDER_WATCHER_IDS", []), \
             patch.object(cart, "get_order", AsyncMock(return_value=dict(ORDER))), \
             patch.object(cart, "get_user_language", AsyncMock(return_value="uz")), \
             patch.object(cart, "order_history_block", AsyncMock(return_value="")), \
             patch.object(oo, "record", record):
            run(cart._notify_sellers(bot, 5, ORDER["items"], data, "uz"))
        record.assert_awaited_once_with(5, 10, "bot")
        text = bot.send_message.await_args_list[0].kwargs["text"]
        self.assertNotIn("Qayerdan", text)
        self.assertIn("Chia", text)

    def test_status_cards_keep_the_line(self):
        order = dict(ORDER, origin=json.dumps({"placed": "webapp", "touch": {"kind": "referral"}}))
        card = order_admin_feed.build_card(order, "uz", title="status_title", by="Admin",
                                           old_status="pending", new_status="confirmed")
        self.assertIn("🧭 Qayerdan: 🌐 Saytdan · 👥 Do'st taklifi", card)
        self.assertNotIn("Qayerdan", order_admin_feed.build_card(ORDER, "uz", title="status_title", by="A"))

    def test_checkout_routes_pass_where_the_order_was_placed(self):
        src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "webapp_server.py"), encoding="utf-8").read()
        self.assertEqual(src.count('"placed": "app" if request.get("app_session") else "webapp"'), 3)

    def test_instagram_links_are_tracked(self):
        import comment_ai
        import shop_links
        self.assertIn("instagram", dict(shop_links.DEFAULTS))
        if not os.getenv("META_COMMENTS_SHOP_LINK"):
            self.assertTrue(comment_ai.SHOP_LINK.endswith("/shop?startapp=instagram"))


PG_URL = os.getenv("ORDER_ORIGIN_PG_URL")


@unittest.skipUnless(PG_URL, "ORDER_ORIGIN_PG_URL not set")
class PostgresTest(unittest.TestCase):
    """The real SQL, in a throw-away schema."""

    def setUp(self):
        import asyncpg
        self.schema = "oo_" + uuid.uuid4().hex[:8]
        self.loop = asyncio.new_event_loop()          # one loop: the pool lives on it
        run = self.loop.run_until_complete

        async def setup():
            admin = await asyncpg.connect(PG_URL)
            await admin.execute(f"CREATE SCHEMA {self.schema}")
            await admin.close()
            pool = await asyncpg.create_pool(PG_URL, min_size=1, max_size=2,
                                             server_settings={"search_path": self.schema})
            async with pool.acquire() as c:
                await c.execute("""
                    CREATE TABLE orders (id SERIAL PRIMARY KEY, user_id BIGINT, total DOUBLE PRECISION,
                        status TEXT, source TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                    CREATE TABLE ai_conversations (id SERIAL PRIMARY KEY, user_id BIGINT, channel TEXT,
                        last_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'));
                    CREATE TABLE shop_links (code TEXT PRIMARY KEY, name TEXT NOT NULL);
                    CREATE TABLE shop_link_opens (code TEXT, user_id BIGINT, auth_date BIGINT,
                        opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                    CREATE TABLE ad_referrals (user_id BIGINT PRIMARY KEY, source TEXT);
                    CREATE TABLE bloggers (id SERIAL PRIMARY KEY, name TEXT);
                    CREATE TABLE blogger_referrals (blogger_id INT, user_id BIGINT);
                    CREATE TABLE referrals (referred_user_id BIGINT, referrer_user_id BIGINT);
                    INSERT INTO shop_links VALUES ('instagram', 'Instagram'), ('kepak', 'Kepak');
                    INSERT INTO shop_link_opens (code, user_id, auth_date) VALUES ('instagram', 1, 1);
                    INSERT INTO shop_link_opens (code, user_id, auth_date, opened_at)
                        VALUES ('kepak', 2, 1, LOCALTIMESTAMP - interval '40 days');
                    INSERT INTO ad_referrals VALUES (2, 'ig_eritritol1');
                    INSERT INTO bloggers (name) VALUES ('Malika');
                    INSERT INTO blogger_referrals VALUES (1, 3);
                    INSERT INTO referrals VALUES (4, 1);
                    INSERT INTO ai_conversations (user_id, channel) VALUES (1, 'site');
                    INSERT INTO ai_conversations (user_id, channel, last_at)
                        VALUES (2, 'bot', (NOW() AT TIME ZONE 'UTC') - interval '3 days');
                    INSERT INTO orders (user_id, total, status) VALUES
                        (1, 100000, 'pending'), (2, 50000, 'pending'), (3, 70000, 'cancelled'),
                        (4, 30000, 'delivered'), (5, 10000, 'pending');
                    INSERT INTO orders (user_id, total, status, source) VALUES (6, 999, 'pending', 'manual');
                """)
            return pool

        self.pool = run(setup())
        self.patches = [patch.object(database, "pool", self.pool), patch.object(oo, "_ready", False),
                        patch.object(oo, "ADMIN_IDS", [])]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

        async def drop():
            await self.pool.close()
            import asyncpg
            admin = await asyncpg.connect(PG_URL)
            await admin.execute(f"DROP SCHEMA {self.schema} CASCADE")
            await admin.close()
        self.loop.run_until_complete(drop())
        self.loop.close()

    def test_detect_record_and_count(self):
        async def go():
            got = {uid: await oo.record(uid, uid, p) for uid, p in
                   ((1, "webapp"), (2, "bot"), (3, "app"), (4, "app"), (5, "bot"))}
            again = await oo.record(1, 1, "bot")                       # the first record stays
            return got, again, await oo.counts(30)

        run = self.loop.run_until_complete
        got, again, c = run(go())
        self.assertEqual(got[1], {"placed": "webapp", "ai": "site", "touch": {"kind": "instagram"}})
        self.assertEqual(got[2], {"placed": "bot", "touch": {"kind": "ad", "source": "ig_eritritol1"}})  # old link, old AI chat
        self.assertEqual(got[3], {"placed": "app", "touch": {"kind": "blogger", "name": "Malika"}})
        self.assertEqual(got[4], {"placed": "app", "touch": {"kind": "referral"}})
        self.assertEqual(got[5], {"placed": "bot"})
        self.assertEqual(again["placed"], "webapp")
        self.assertEqual(c["orders"], 4)                               # cancelled and manual left out
        self.assertEqual(dict(c["placed"]), {"webapp": 1, "bot": 2, "app": 1})
        self.assertEqual((c["ai"], c["ai_sum"]), (1, 100000.0))
        self.assertEqual(c["touches"]["📸 Instagram (izoh / Direct havolasi)"], 1)
        text = run(oo.report_text("30"))
        self.assertIn("🌐 Saytdan: <b>1 ta</b> (25%) · 100 000 so'm", text)
        self.assertIn("💬 Botdan: <b>2 ta</b> (50%)", text)


if __name__ == "__main__":
    unittest.main()
