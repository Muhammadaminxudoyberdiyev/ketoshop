"""🎮 O'yinlar markazi (games.py): the rules, and the real SQL when
GAMES_PG_URL points at a throw-away Postgres (own schema). No Telegram."""
import asyncio
import os
import unittest
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import database
import games as g

D = date(2026, 11, 18)          # a Wednesday


class RulesTest(unittest.TestCase):
    def test_streak_grows_and_forgives_one_missed_day_a_week(self):
        self.assertEqual(g.streak_after({}, D), (1, False))
        self.assertEqual(g.streak_after({"clue_last": "2026-11-17", "streak": 4}, D), (5, False))
        self.assertEqual(g.streak_after({"clue_last": "2026-11-16", "streak": 4}, D), (5, True))     # freeze used
        self.assertEqual(g.streak_after({"clue_last": "2026-11-16", "streak": 4, "freeze_week": "2026-11-16"}, D), (1, False))
        self.assertEqual(g.streak_after({"clue_last": "2026-11-10", "streak": 9}, D), (1, False))
        self.assertEqual(g.streak_after({"clue_last": "2026-11-18", "streak": 3}, D), (3, False))

    def test_one_new_chapter_and_station_a_day(self):
        self.assertEqual(g.story_open({}, D), 1)
        self.assertEqual(g.story_open({"story_done": 4, "story_day": "2026-11-17"}, D), 5)
        self.assertEqual(g.story_open({"story_done": 4, "story_day": "2026-11-18"}, D), 4)       # tomorrow
        self.assertEqual(g.story_open({"story_done": 30}, D), 0)
        self.assertEqual(g.map_open({"map_done": 2, "map_day": "2026-11-18"}, D), 2)
        self.assertEqual(g.map_open({"map_done": 10}, D), 0)

    def test_daily_tasks(self):
        t = g.tasks_of({"clue_last": "2026-11-18", "story_day": "2026-11-18"}, D, {"clue", "story", "swap"})
        self.assertEqual((t["clue"], t["journey"], t["game"], t["done"]), (True, True, True, 3))
        self.assertEqual(g.tasks_of({}, D, {"clue"})["done"], 0)

    def test_points_are_capped_and_passing_needs_half(self):
        self.assertEqual(g.clamp_points("clue", 9), 3)
        self.assertEqual(g.clamp_points("swap", -4), 0)
        self.assertEqual(g.clamp_points("swap", "x"), 0)
        self.assertTrue(g.passed("swap", 4, 7))
        self.assertFalse(g.passed("swap", 3, 7))
        self.assertTrue(g.passed("duel", 1, None))

    def test_puzzle_index_matches_the_page(self):
        # games2.js: (seed * 7 + 3) % length, seed = date.toordinal()
        self.assertEqual(g.clue_index(D, 30), (D.toordinal() * 7 + 3) % 30)
        self.assertNotEqual(g.clue_index(D, 30), g.clue_index(D + timedelta(days=1), 30))

    def test_board_names_are_short(self):
        self.assertEqual(g._name("Dilnoza Karimova", 5), "Dilnoza K.")
        self.assertEqual(g._name("", 12345), "O'yinchi 345")


PG_URL = os.getenv("GAMES_PG_URL")
NOW = datetime(2026, 11, 18, 7, 0)            # 12:00 in Tashkent


@unittest.skipUnless(PG_URL, "GAMES_PG_URL not set")
class PostgresTest(unittest.TestCase):
    def setUp(self):
        import asyncpg
        self.schema = "gm_" + uuid.uuid4().hex[:8]
        self.loop = asyncio.new_event_loop()
        run = self.loop.run_until_complete

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
                    INSERT INTO users (user_id, full_name) VALUES (1, 'Dilnoza Karimova'), (2, 'Ali Valiyev'), (425609051, 'Shop');
                """)
            return pool

        self.pool = run(setup())
        self.patches = [patch.object(database, "pool", self.pool), patch.object(g, "_ready", False),
                        patch.object(g, "ADMIN_IDS", [])]
        for p in self.patches:
            p.start()
        self.run = run

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

    def finish(self, uid, body, now=NOW):
        # credit_keto's ledger rows get NOW(); the day's cap is counted from the ledger,
        # so the test runs "today" = the real day for the cap and NOW for game days.
        return self.run(g.finish(uid, body, now))

    def balance(self, uid):
        async def q():
            async with self.pool.acquire() as c:
                return await c.fetchval("SELECT keto_balance FROM users WHERE user_id = $1", uid)
        return self.run(q())

    def test_daily_puzzle_pays_once_by_hints_and_counts_the_streak(self):
        real_now = datetime.utcnow()
        out, status = self.finish(1, {"game": "clue", "points": 3}, real_now)
        self.assertEqual(status, 200)
        self.assertEqual((out["paid"], out["streak"], out["clue_solved"]), (15, 1, True))
        again, _ = self.finish(1, {"game": "clue", "points": 3}, real_now)
        self.assertTrue(again.get("already"))
        self.assertEqual(self.balance(1), 15)
        self.assertEqual(out["solvers_today"], 1)

    def test_daily_cap_and_one_reward_per_game_a_day(self):
        now = datetime.utcnow()
        paid = [self.finish(1, {"game": gm, "points": 10, "total": 10}, now)[0]["paid"]
                for gm in ("swap", "swap", "label", "myth", "quiz", "keto", "duel", "memory", "bazaar")]
        self.assertEqual(paid[:2], [5, 0])                       # the same game pays once a day
        self.assertLessEqual(self.balance(1), g.DAILY_CAP)
        out, _ = self.finish(1, {"game": "clue", "points": 3}, now)
        self.assertLessEqual(self.balance(1), g.DAILY_CAP)       # the cap holds
        self.assertEqual(out["keto_today"], self.balance(1))

    def test_story_and_map_open_one_step_a_day(self):
        now = datetime.utcnow()
        out, status = self.finish(1, {"game": "story", "chapter": 2, "points": 5}, now)
        self.assertEqual(status, 409)                            # chapter 1 first
        out, _ = self.finish(1, {"game": "story", "chapter": 1, "points": 8, "stats": {"natija": 8, "x": 99}}, now)
        self.assertEqual((out["story"]["done"], out["story"]["open"], out["paid"]), (1, 1, 5))
        self.assertEqual(out["story"]["stats"], {"natija": 58})
        _, status = self.finish(1, {"game": "story", "chapter": 2, "points": 5}, now)
        self.assertEqual(status, 409)                            # tomorrow
        tomorrow = now + timedelta(days=1)
        out, _ = self.finish(1, {"game": "story", "chapter": 2, "points": 5}, tomorrow)
        self.assertEqual(out["story"]["done"], 2)
        out, _ = self.finish(1, {"game": "map", "station": 1, "points": 1, "total": 3}, now)
        self.assertEqual(out["map"]["done"], 0)                  # 1 of 3 isn't enough
        out, _ = self.finish(1, {"game": "map", "station": 1, "points": 2, "total": 3}, now)
        self.assertEqual((out["map"]["done"], out["map"]["open"]), (1, 1))

    def test_all_three_tasks_pay_the_bonus_and_the_board_ranks(self):
        now = datetime.utcnow()
        self.finish(1, {"game": "clue", "points": 2}, now)
        self.finish(1, {"game": "story", "chapter": 1, "points": 5}, now)
        out, _ = self.finish(1, {"game": "myth", "points": 9, "total": 10}, now)
        self.assertTrue(any(n["kind"] == "tasks" for n in out["notes"]))
        self.assertTrue(out["tasks"]["bonus_paid"])
        self.finish(2, {"game": "swap", "points": 30, "total": 40}, now)
        self.finish(2, {"game": "swap", "points": 10, "total": 40}, now)      # the day's best counts
        self.finish(425609051, {"game": "swap", "points": 40, "total": 40}, now)
        board = self.run(g.state_for(1, now))["board"]
        names = [(x["name"], x["points"]) for x in board["top"]]
        self.assertEqual(names[0], ("Ali V.", 30))
        self.assertIn(("Dilnoza K.", 16), names)
        self.assertNotIn("Shop", [x["name"] for x in board["top"]])          # the shop's own accounts never show
        self.assertEqual(self.balance(425609051), 0)                         # and never earn

    def test_keto_program_off_means_no_keto_but_the_game_counts(self):
        async def off():
            async with self.pool.acquire() as c:
                await c.execute("UPDATE gamification_state SET enabled = FALSE")
        self.run(off())
        out, _ = self.finish(1, {"game": "swap", "points": 6, "total": 7}, datetime.utcnow())
        self.assertEqual((out["paid"], out["earning"]), (0, False))
        self.assertEqual(out["board"]["me"]["points"], 6)

    def test_unknown_game_is_refused(self):
        self.assertEqual(self.finish(1, {"game": "casino", "points": 9})[1], 400)


if __name__ == "__main__":
    unittest.main()
