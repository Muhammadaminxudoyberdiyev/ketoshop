"""GET /admin/api/ai-dialogs — AI suhbatlarini ko'rib chiqish (egasi, 2026-11-21)."""
import asyncio
import os
import unittest
import uuid
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import admin_web
import ai_dialog
import database


class RouteTest(unittest.TestCase):
    def test_route_is_registered_and_guarded(self):
        from aiohttp import web
        app = web.Application()
        admin_web.setup_admin_routes(app)
        paths = {r.resource.canonical for r in app.router.routes() if r.resource}
        self.assertIn("/admin/api/ai-dialogs", paths)

    def test_needs_login(self):
        from aiohttp.test_utils import make_mocked_request
        req = make_mocked_request("GET", "/admin/api/ai-dialogs")
        with patch.object(admin_web, "ADMIN_WEB_PASSWORD", "x"):
            resp = asyncio.run(admin_web.api_ai_dialogs(req))
        self.assertEqual(resp.status, 401)


PG_URL = os.getenv("GAMES_PG_URL")


@unittest.skipUnless(PG_URL, "GAMES_PG_URL not set")
class PostgresTest(unittest.TestCase):
    def test_newest_first_staff_out_paged(self):
        import asyncpg
        schema = "dl_" + uuid.uuid4().hex[:8]
        loop = asyncio.new_event_loop()

        async def go():
            admin = await asyncpg.connect(PG_URL)
            await admin.execute(f"CREATE SCHEMA {schema}")
            await admin.close()
            pool = await asyncpg.create_pool(PG_URL, min_size=1, max_size=2, server_settings={"search_path": schema})
            try:
                async with pool.acquire() as c:
                    await c.execute("CREATE TABLE users (user_id BIGINT PRIMARY KEY, full_name TEXT, username TEXT);"
                                    "INSERT INTO users VALUES (1, 'Ali', 'ali'), (9, 'Admin', NULL);")
                with patch.object(database, "pool", pool), patch.object(ai_dialog, "_table_ready", False):
                    for uid, q in ((1, "salom"), (9, "test"), (1, "narxi?")):
                        await ai_dialog.record(uid, "bot", q, "javob")
                    first = await ai_dialog.review_page(1, None, [9])
                    second = await ai_dialog.review_page(5, first[-1]["id"], [9])
                return first, second
            finally:
                await pool.close()
                admin = await asyncpg.connect(PG_URL)
                await admin.execute(f"DROP SCHEMA {schema} CASCADE")
                await admin.close()

        first, second = loop.run_until_complete(go())
        loop.close()
        self.assertEqual([r["question"] for r in first], ["narxi?"])
        self.assertEqual(first[0]["full_name"], "Ali")
        self.assertEqual([r["question"] for r in second], ["salom"])


if __name__ == "__main__":
    unittest.main()
