"""🔥 O'yin seriyasi eslatmasi (game_reminder.py, egasi 2026-11-18). Telegram'ga
ulanmaydi; SQL qismi GAMES_PG_URL berilsa haqiqiy Postgres'da (o'z sxemasida)."""
import asyncio
import json
import os
import re
import unittest
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import database
import game_reminder as gr
import games

D = date(2026, 11, 18)          # a Wednesday; its week starts 2026-11-16


def run(coro):
    return asyncio.run(coro)


class PlanTest(unittest.TestCase):
    def test_streak_alive_from_yesterday(self):
        self.assertEqual(gr.plan_for({"clue_last": "2026-11-17", "streak": 4}, D), {"streak": 4})

    def test_missed_one_day_with_the_week_forgiveness_left(self):
        self.assertEqual(gr.plan_for({"clue_last": "2026-11-16", "streak": 4}, D),
                         {"streak": 4, "last_chance": True})
        # the week's forgiven day already used — the streak is gone, nothing to keep
        self.assertIsNone(gr.plan_for({"clue_last": "2026-11-16", "streak": 4, "freeze_week": "2026-11-16"}, D))
        self.assertIsNone(gr.plan_for({"clue_last": "2026-11-12", "streak": 9}, D))

    def test_nothing_when_already_played_or_switched_off_or_ignored(self):
        self.assertIsNone(gr.plan_for({"clue_last": "2026-11-18", "streak": 5}, D))
        self.assertIsNone(gr.plan_for({"clue_last": "2026-11-17", "streak": 4, "remind_off": True}, D))
        self.assertIsNone(gr.plan_for({"clue_last": "2026-11-17", "streak": 4, "remind_ignored": 3}, D))
        self.assertEqual(gr.plan_for({"clue_last": "2026-11-17", "streak": 4, "remind_ignored": 2}, D), {"streak": 4})

    def test_story_and_map_steps_opened_today(self):
        st = {"story_done": 5, "story_day": "2026-11-17", "map_done": 2, "map_day": "2026-11-16"}
        self.assertEqual(gr.plan_for(st, D), {"chapter": 6, "station": 3})
        self.assertIsNone(gr.plan_for({"story_done": 5, "story_day": "2026-11-10"}, D))      # gone quiet
        self.assertIsNone(gr.plan_for({"story_done": 5, "story_day": "2026-11-18"}, D))      # already read today
        self.assertIsNone(gr.plan_for({"story_done": 30, "story_day": "2026-11-17"}, D))     # finished
        self.assertIsNone(gr.plan_for({}, D))


class TextTest(unittest.TestCase):
    def test_every_language(self):
        plan = {"streak": 4, "chapter": 6, "station": 3}
        uz = gr.message_text(plan, "uz")
        self.assertIn("Seriyangiz: <b>4 kun</b>", uz)
        self.assertIn("<b>5</b> bo'ladi", uz)
        self.assertIn("<b>6-bob</b>", uz)
        self.assertIn("<b>3-bekat</b>", uz)
        self.assertIn("15 Keto", uz)
        self.assertIn("Серия", gr.message_text(plan, "ru").replace("серия", "Серия"))
        self.assertIn("Сериянгиз", gr.message_text(plan, "uz_cyr"))
        for lang in ("uz", "uz_cyr", "ru"):
            text = gr.message_text(plan, lang)
            self.assertEqual(text.count("<b>"), text.count("</b>"))
            self.assertNotIn("{", text)

    def test_honest_last_chance_and_no_pressure(self):
        text = gr.message_text({"streak": 9, "last_chance": True}, "uz")
        self.assertIn("haftada bitta o'tkazib yuborilgan kun kechiriladi", text)
        for lang in ("uz", "ru"):
            low = gr.message_text({"streak": 9, "last_chance": True}, lang).lower()
            for word in ("shoshiling", "oxirgi imkoniyat", "успейте", "последний шанс", "только сегодня"):
                self.assertNotIn(word, low)

    def test_no_keto_promise_when_the_program_is_off_or_no_puzzle(self):
        self.assertNotIn("Keto", gr.message_text({"streak": 3}, "uz", keto_on=False))
        self.assertNotIn("15 Keto", gr.message_text({"chapter": 2}, "uz"))

    def test_buttons_open_the_right_game_and_switch_off(self):
        with patch.object(gr, "WEBAPP_URL", "https://keto.example/"):
            kb = gr.keyboard({"streak": 2}, "uz")
            self.assertEqual(kb.inline_keyboard[0][0].web_app.url, "https://keto.example/?game=clue")
            self.assertEqual(kb.inline_keyboard[1][0].callback_data, "g2rem:off:clue")
            kb = gr.keyboard({"chapter": 2}, "ru", off=True)
            self.assertEqual(kb.inline_keyboard[0][0].web_app.url, "https://keto.example/?game=story")
            self.assertEqual(kb.inline_keyboard[1][0].callback_data, "g2rem:on:story")
            self.assertTrue(gr.keyboard({"station": 1}, "uz").inline_keyboard[0][0].web_app.url.endswith("?game=map"))


class TickTest(unittest.TestCase):
    def tick(self, now, claimed=True):
        rnd = AsyncMock(return_value={"due": 0})
        with patch.object(gr, "_now_tk", lambda: now), \
             patch.object(gr, "enabled", AsyncMock(return_value=True)), \
             patch.object(gr, "send_round", rnd), \
             patch.object(database, "claim_release_notes", AsyncMock(return_value=claimed)):
            run(gr._tick(MagicMock()))
        return rnd

    def test_morning_window_once_and_not_on_the_gift_comeback_day(self):
        self.tick(datetime(2026, 11, 18, 7, 31)).assert_awaited_once()
        for now in (datetime(2026, 11, 18, 7, 29), datetime(2026, 11, 18, 11, 0),
                    datetime(2026, 11, 20, 7, 31)):                     # 20.11 — the Eritritol announcement
            self.tick(now).assert_not_awaited()
        self.tick(datetime(2026, 11, 18, 7, 31), claimed=False).assert_not_awaited()
        self.tick(datetime(2026, 11, 21, 7, 31)).assert_awaited_once()

    def test_runs_before_the_other_morning_sends(self):
        import feedback_ask
        import broadcast
        self.assertLess(gr.SEND_AT, feedback_ask.SEND_AT)
        self.assertLess(gr.SEND_AT, (broadcast.SEND_HOUR, 0))


class RoundTest(unittest.TestCase):
    def test_cap_staff_and_counting(self):
        import push_cap
        players = [(1, {"clue_last": "2026-11-17", "streak": 3}),            # sent
                   (2, {"clue_last": "2026-11-17", "streak": 8}),            # capped
                   (3, {"clue_last": "2026-11-18", "streak": 8}),            # already played
                   (425609051, {"clue_last": "2026-11-17", "streak": 8}),    # the shop's own account
                   (5, {"story_done": 2, "story_day": "2026-11-17", "remind_ignored": 1})]   # sent
        bot = MagicMock()
        bot.send_message = AsyncMock()
        update = AsyncMock()
        with patch.object(gr, "_players", AsyncMock(return_value=players)), \
             patch.object(gr, "ADMIN_IDS", []), \
             patch.object(gr, "SEND_DELAY", 0), \
             patch.object(gr, "_keto_on", AsyncMock(return_value=True)), \
             patch.object(gr, "_update_state", update), \
             patch.object(push_cap, "claim", AsyncMock(side_effect=lambda uid, kind: uid != 2)) as claim, \
             patch.object(database, "get_user_languages", AsyncMock(return_value={1: "ru"})):
            stats = run(gr.send_round(bot, D))
        self.assertEqual((stats["due"], stats["sent"], stats["capped"], stats["streaks"]), (3, 2, 1, 1))
        self.assertEqual({c.args[1] for c in claim.await_args_list}, {"oyin"})
        sent = {c.args[0]: c.args[1] for c in bot.send_message.await_args_list}
        self.assertIn("Ваша серия", sent[1])
        self.assertIn("3-bob", sent[5])
        self.assertEqual({c.args[0]: c.kwargs["remind_ignored"] for c in update.await_args_list}, {1: 1, 5: 2})


PG_URL = os.getenv("GAMES_PG_URL")


@unittest.skipUnless(PG_URL, "GAMES_PG_URL not set")
class PostgresTest(unittest.TestCase):
    def setUp(self):
        import asyncpg
        self.schema = "gr_" + uuid.uuid4().hex[:8]
        self.loop = asyncio.new_event_loop()

        async def setup():
            admin = await asyncpg.connect(PG_URL)
            await admin.execute(f"CREATE SCHEMA {self.schema}")
            await admin.close()
            pool = await asyncpg.create_pool(PG_URL, min_size=1, max_size=3, server_settings={"search_path": self.schema})
            async with pool.acquire() as c:
                await c.execute("""
                    CREATE TABLE users (user_id BIGINT PRIMARY KEY, full_name TEXT,
                        keto_balance INT NOT NULL DEFAULT 0, keto_lifetime INT NOT NULL DEFAULT 0);
                    CREATE TABLE keto_ledger (id SERIAL PRIMARY KEY, user_id BIGINT, order_id INT, amount INT,
                        kind TEXT, note TEXT, created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'UTC'));
                    CREATE TABLE gamification_state (id INT PRIMARY KEY DEFAULT 1, enabled BOOLEAN NOT NULL DEFAULT TRUE);
                    INSERT INTO gamification_state (id) VALUES (1);
                    INSERT INTO users (user_id, full_name) VALUES (1, 'Dilnoza');
                """)
            return pool

        self.pool = self.loop.run_until_complete(setup())
        self.patches = [patch.object(database, "pool", self.pool), patch.object(games, "_ready", False),
                        patch.object(games, "ADMIN_IDS", [])]
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

    def test_state_merge_and_playing_resets_the_ignored_count(self):
        run = self.loop.run_until_complete
        run(gr._update_state(1, remind_ignored=2, remind_off=False))
        run(gr._update_state(1, remind_last="2026-11-18"))
        players = dict(run(gr._players()))
        self.assertEqual(players[1], {"remind_ignored": 2, "remind_off": False, "remind_last": "2026-11-18"})
        run(games.finish(1, {"game": "myth", "points": 8, "total": 10}, datetime.utcnow()))
        st = dict(run(gr._players()))[1]
        self.assertEqual(st["remind_ignored"], 0)
        self.assertEqual(st["remind_last"], "2026-11-18")        # games.finish keeps the reminder's keys


if __name__ == "__main__":
    unittest.main()
