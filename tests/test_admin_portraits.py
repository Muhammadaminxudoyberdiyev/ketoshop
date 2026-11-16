"""Admin «🧑‍🤝‍🧑 Mijozlar» — /admin/api/portraits (portrait_web.py).

Bazasiz: soxta ulanish SQL va argumentlarni yozib boradi. Ismlar — keng
tarqalgan umumiy ismlar, ID lar o'ylab topilgan; haqiqiy mijoz ma'lumoti yo'q.

Haqiqiy PostgreSQL da tekshirish (ixtiyoriy, CI da o'tkazib yuboriladi):
    PORTRAIT_PG_URL=postgresql://postgres@127.0.0.1:55432/postgres \
        python -m unittest tests.test_admin_portraits
Test o'z sxemasini yaratadi va oxirida o'chiradi.
"""
import asyncio
import json
import os
import unittest
from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

from aiohttp import web

import admin_web
import ai_memory
import ai_stats
import customer_portrait
import database
import portrait_web
from config import ADMIN_IDS

INTERNAL = sorted(database.LEADERBOARD_EXCLUDED_USER_IDS)[0]


def run(coro):
    return asyncio.run(coro)


def _row(user_id, **kw):
    base = {"user_id": user_id, "first_ai_at": datetime(2026, 11, 10, 9, 0),
            "last_ai_at": datetime(2026, 11, 16, 8, 30), "conversations": 3, "messages": 9,
            "channels": ["bot"], "full_name": "Dilnoza Test", "username": "dilnoza_t",
            "display_name": None, "age": None, "age_group": None, "gender": "unknown",
            "gender_source": None, "gender_confidence": None, "goals": [],
            "opted_out": False, "has_portrait": False, "orders": 0, "spent": 0.0, "last_order_at": None}
    base.update(kw)
    return base


ROWS = [
    _row(5001, display_name="Dilnoza", age=28, age_group="25–34", gender="f", gender_source="name",
         gender_confidence=0.9312, goals=["ozish", "keto"], has_portrait=True, orders=2, spent=350000.0,
         channels=["bot", "site"]),
    # Ma'lumotini o'chirgan: bazada nimadir qolgan bo'lsa ham chiqmasligi kerak.
    _row(5002, full_name="Sardor Test", username="", display_name="Sardor", age=40, gender="m",
         gender_source="name", goals=["sport"], opted_out=True, has_portrait=False),
    _row(5003, full_name="", username="", conversations=1, messages=1),
]

STATS = {"talked": 3, "portraits": 1, "with_name": 1, "with_age": 1, "female": 1, "male": 0,
         "with_goals": 1, "opted_out": 1, "with_orders": 1}


class FakeConn:
    def __init__(self, rows=ROWS, total=None, card_row=None, user=None):
        self.rows, self.total = rows, len(rows) if total is None else total
        self.card_row, self.user = card_row, user
        self.calls = []

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        if "AS talked" in sql:
            return STATS
        if "FROM people WHERE user_id = $3" in sql:
            return self.card_row
        if "FROM users WHERE user_id" in sql:
            return self.user
        raise AssertionError(sql)

    async def fetchval(self, sql, *args):
        self.calls.append(("fetchval", sql, args))
        assert "SELECT COUNT(*) FROM people" in sql, sql
        return self.total

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        if "unnest(goals)" in sql:
            return [{"goal": "ozish", "n": 1}, {"goal": "keto", "n": 1}]
        if "unnest(c.topics)" in sql:
            return [{"user_id": uid, "topic": t, "n": n} for uid in args[1]
                    for t, n in (("narx", 3), ("keto", 2), ("yetkazish", 1), ("tolov", 1))]
        if "ORDER BY last_ai_at DESC" in sql:
            return self.rows
        raise AssertionError(sql)

    def find(self, needle):
        return [c for c in self.calls if needle in c[1]]


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False
        return _Ctx()


class NoPool:
    def acquire(self):
        raise AssertionError("bazaga murojaat bo'lmasligi kerak")


class _PoolCase(unittest.TestCase):
    def use(self, conn):
        saved = database.pool, ai_stats._table_ready, customer_portrait._table_ready
        database.pool = conn if isinstance(conn, NoPool) else FakePool(conn)
        ai_stats._table_ready = customer_portrait._table_ready = True
        self.addCleanup(self._restore, saved)
        return conn

    @staticmethod
    def _restore(saved):
        database.pool, ai_stats._table_ready, customer_portrait._table_ready = saved


# ─────────────────────────────── ro'yxat ────────────────────────────────────

class ListTest(_PoolCase):
    def test_counters_rows_and_paging(self):
        conn = self.use(FakeConn(total=61))
        data = run(portrait_web.list_page("", 1, "all"))
        self.assertEqual(data["stats"], STATS)
        self.assertEqual(data["goals"], [{"goal": "ozish", "label": "ozish", "n": 1},
                                         {"goal": "keto", "label": "keto", "n": 1}])
        self.assertEqual((data["total"], data["page"], data["pages"], data["per_page"]), (61, 1, 3, 30))
        self.assertEqual([r["user_id"] for r in data["rows"]], [5001, 5002, 5003])
        first = data["rows"][0]
        self.assertEqual({k: first[k] for k in ("display_name", "age", "age_group", "gender", "gender_source",
                                                 "gender_confidence", "goals", "goal_labels", "orders", "spent",
                                                 "conversations", "channels", "opted_out", "has_portrait")},
                         {"display_name": "Dilnoza", "age": 28, "age_group": "25–34", "gender": "f",
                          "gender_source": "name", "gender_confidence": 0.93, "goals": ["ozish", "keto"],
                          "goal_labels": ["ozish", "keto"], "orders": 2, "spent": 350000.0,
                          "conversations": 3, "channels": ["bot", "site"], "opted_out": False,
                          "has_portrait": True})
        # Eng ko'p 3 ta mavzu, nomi bilan.
        self.assertEqual([t["key"] for t in first["topics"]], ["narx", "keto", "yetkazish"])
        self.assertEqual(first["topics"][0]["title"], ai_stats.TOPIC_TITLES["narx"])
        # Faqat bot va sayt kanallari, adminlar va ichki akkauntlarsiz.
        _, sql, args = conn.find("ORDER BY last_ai_at DESC")[0]
        self.assertEqual(args[0], ["bot", "site"])
        self.assertTrue(set(ADMIN_IDS) | database.LEADERBOARD_EXCLUDED_USER_IDS <= set(args[1]))
        self.assertEqual(args[4:], (30, 0))
        json.dumps(data, default=str)                     # admin_web._json bilan chiqadi

    def test_second_page_offset(self):
        conn = self.use(FakeConn(total=31))
        data = run(portrait_web.list_page("", 2, "all"))
        self.assertEqual((data["page"], data["pages"]), (2, 2))
        self.assertEqual(conn.find("ORDER BY last_ai_at DESC")[0][2][4:], (30, 30))
        run(portrait_web.list_page("", 0, "all"))
        self.assertEqual(conn.find("ORDER BY last_ai_at DESC")[-1][2][4:], (30, 0))

    def test_search_by_name_username_and_id(self):
        conn = self.use(FakeConn())
        data = run(portrait_web.list_page("  @Dil_noza% ", 1, "all"))
        self.assertEqual(data["q"], "@Dil_noza%")
        args = conn.find("ORDER BY last_ai_at DESC")[0][2]
        self.assertEqual(args[2:4], ("", "%Dil\\_noza\\%%"))      # LIKE belgilari so'zma-so'z
        run(portrait_web.list_page("5001", 1, "all"))
        self.assertEqual(conn.find("ORDER BY last_ai_at DESC")[-1][2][2:4], ("5001", "%5001%"))
        run(portrait_web.list_page("", 1, "all"))
        self.assertEqual(conn.find("ORDER BY last_ai_at DESC")[-1][2][2:4], ("", ""))
        _, sql, _ = conn.find("ORDER BY last_ai_at DESC")[-1]
        self.assertIn("user_id::text = $3", sql)
        self.assertIn("(NOT opted_out AND display_name ILIKE $4)", sql)

    def test_filters_reach_the_query(self):
        conn = self.use(FakeConn())
        for flt, needle in (("portrait", "(has_portrait) AND"), ("no_portrait", "(NOT has_portrait) AND"),
                            ("orders", "(orders > 0) AND"), ("bogus", "(TRUE) AND")):
            data = run(portrait_web.list_page("", 1, flt))
            self.assertEqual(data["filter"], flt if flt != "bogus" else "all")
            for kind in ("fetchval", "fetch"):
                sql = [c for c in conn.calls if c[0] == kind and "FROM people WHERE" in c[1]][-1][1]
                self.assertIn(needle, sql)

    def test_opted_out_shows_nothing_of_the_portrait(self):
        conn = self.use(FakeConn())
        data = run(portrait_web.list_page("", 1, "all"))
        gone = data["rows"][1]
        self.assertTrue(gone["opted_out"])
        self.assertEqual((gone["display_name"], gone["age"], gone["age_group"], gone["gender"], gone["gender_source"],
                          gone["goals"], gone["goal_labels"], gone["topics"], gone["has_portrait"]),
                         (None, None, None, "unknown", None, [], [], [], False))
        # Uning mavzulari bazadan so'ralmaydi ham.
        _, _, args = conn.find("unnest(c.topics)")[0]
        self.assertEqual(args[1], [5001, 5003])
        # Tozalangan ism bo'yicha qidiruv faqat o'chirmaganlarda.
        self.assertIn("NOT opted_out AND display_name ILIKE", conn.find("ORDER BY last_ai_at DESC")[0][1])

    def test_empty_page_skips_topics(self):
        conn = self.use(FakeConn(rows=[], total=0))
        data = run(portrait_web.list_page("yo'q", 1, "all"))
        self.assertEqual((data["rows"], data["total"], data["pages"]), ([], 0, 1))
        self.assertEqual(conn.find("unnest(c.topics)"), [])


# ─────────────────────────────── karta ──────────────────────────────────────

NOTES = [
    {"id": 1, "kind": "interest", "text": "Bodom uni", "product_id": 3, "created_at": datetime(2026, 11, 10)},
    {"id": 2, "kind": "asked", "text": "Eritritol", "product_id": 4, "created_at": datetime(2026, 11, 11)},
    {"id": 3, "kind": "recipe", "text": "Keto non", "product_id": 3, "created_at": datetime(2026, 11, 12)},
    {"id": 4, "kind": "feedback", "text": "Eritritol — ta'mi yoqdi", "product_id": 4,
     "created_at": datetime(2026, 11, 13)},
    {"id": 5, "kind": "note", "text": "oilasi uchun oladi", "product_id": None, "created_at": datetime(2026, 11, 14)},
]


def _orders():
    items = json.dumps([{"product_id": 3, "name": "Bodom uni 500gr", "quantity": 2, "unit": "dona", "price": 95000},
                        {"product_id": 9, "name": "Eritritol 100gr", "quantity": 1, "price": 0, "is_gift": True}])
    rows = [{"id": 100 + i, "created_at": datetime(2026, 11, 15 - i), "status": "delivered", "total": 190000.0,
             "items": items, "source": "bot", "delivery_method": "courier"} for i in range(6)]
    rows.insert(1, {"id": 99, "created_at": datetime(2026, 11, 14), "status": "pending", "total": 1.0,
                    "items": "[]", "source": "b2b"})
    return rows


USER = {"user_id": 5001, "language": "uz_cyr", "created_at": datetime(2026, 9, 1, 7, 0),
        "keto_balance": 140, "keto_lifetime": 320, "full_name": "Dilnoza Test", "username": "dilnoza_t"}


class CardTest(_PoolCase):
    def call(self, user_id, card_row, notes=NOTES):
        conn = self.use(FakeConn(card_row=card_row, user=USER))
        with patch.object(ai_memory, "notes", AsyncMock(return_value=notes)) as get_notes, \
             patch.object(database, "get_user_orders", AsyncMock(return_value=_orders())):
            data = run(portrait_web.card(user_id))
        return data, conn, get_notes

    def test_full_card(self):
        data, conn, _ = self.call(5001, ROWS[0])
        self.assertEqual(data["display_name"], "Dilnoza")
        self.assertEqual([n["kind"] for n in data["notes"]], ["note", "feedback", "interest"])   # yangisi oldin
        self.assertEqual(len(data["recent_orders"]), 5)
        self.assertNotIn(99, [o["id"] for o in data["recent_orders"]])                          # B2B emas
        order = data["recent_orders"][0]
        self.assertEqual((order["id"], order["status"], order["total"], order["delivery_method"]),
                         (100, "delivered", 190000.0, "courier"))
        self.assertEqual(order["items"][0], {"name": "Bodom uni 500gr", "quantity": 2, "unit": "dona",
                                             "price": 95000, "gift": False})
        self.assertTrue(order["items"][1]["gift"])
        self.assertEqual((data["keto_balance"], data["keto_lifetime"], data["language"]), (140, 320, "uz_cyr"))
        self.assertEqual((data["tg_link"], data["tme_link"]), ("tg://user?id=5001", "https://t.me/dilnoza_t"))
        self.assertEqual([t["key"] for t in data["topics"]], ["narx", "keto", "yetkazish"])
        self.assertEqual(conn.find("FROM people WHERE user_id = $3")[0][2][2], 5001)

    def test_opted_out_card_has_no_portrait_notes_or_topics(self):
        data, conn, get_notes = self.call(5002, ROWS[1])
        self.assertTrue(data["opted_out"])
        self.assertEqual((data["display_name"], data["age"], data["goals"], data["notes"], data["topics"]),
                         (None, None, [], [], []))
        get_notes.assert_not_awaited()
        self.assertEqual(conn.find("unnest(c.topics)"), [])
        self.assertEqual(data["tme_link"], "")
        self.assertEqual(len(data["recent_orders"]), 5)       # buyurtmalar do'kon hisobi — qoladi

    def test_not_an_ai_customer(self):
        data, _, _ = self.call(5009, None)
        self.assertIsNone(data)

    def test_staff_cards_never_open(self):
        self.use(NoPool())
        for uid in (ADMIN_IDS[0], INTERNAL, 0, 2 ** 63):
            self.assertIsNone(run(portrait_web.card(uid)))


# ─────────────────────────────── API ────────────────────────────────────────

def _req(query=None, user_id=None):
    return NS(query=query or {}, match_info={"user_id": str(user_id)} if user_id is not None else {})


class ApiTest(unittest.TestCase):
    def call(self, handler, request, authed=True, listed=None, card=None):
        with patch.object(admin_web, "ADMIN_WEB_PASSWORD", "secret"), \
             patch.object(admin_web, "_authed", lambda request: authed), \
             patch.object(portrait_web, "list_page", AsyncMock(return_value=listed or {"rows": []})) as lp, \
             patch.object(portrait_web, "card", AsyncMock(return_value=card)) as cd:
            resp = run(handler(request))
        return resp, lp, cd

    def test_needs_the_admin_password(self):
        for handler, request in ((admin_web.api_portraits, _req()), (admin_web.api_portrait_card, _req(user_id=5))):
            resp, lp, cd = self.call(handler, request, authed=False)
            self.assertEqual(resp.status, 401)
            lp.assert_not_awaited()
            cd.assert_not_awaited()

    def test_list_passes_search_page_and_filter(self):
        resp, lp, _ = self.call(admin_web.api_portraits, _req({"q": "dil", "page": "3", "filter": "orders"}),
                                listed={"rows": [], "last": datetime(2026, 11, 16, 8, 0)})
        self.assertEqual(resp.status, 200)
        lp.assert_awaited_once_with("dil", 3, "orders")
        self.assertEqual(json.loads(resp.body)["last"], "2026-11-16T08:00:00")
        _, lp, _ = self.call(admin_web.api_portraits, _req({"page": "x"}))
        lp.assert_awaited_once_with("", 1, "all")

    def test_card_found_and_missing(self):
        resp, _, cd = self.call(admin_web.api_portrait_card, _req(user_id=5001),
                                card={"user_id": 5001, "joined_at": datetime(2026, 9, 1)})
        self.assertEqual(resp.status, 200)
        cd.assert_awaited_once_with(5001)
        self.assertEqual(json.loads(resp.body)["joined_at"], "2026-09-01T00:00:00")
        resp, _, _ = self.call(admin_web.api_portrait_card, _req(user_id=5009), card=None)
        self.assertEqual(resp.status, 404)

    def test_routes_are_registered(self):
        app = web.Application()
        admin_web.setup_admin_routes(app)
        routes = {(r.method, r.resource.canonical) for r in app.router.routes()}
        self.assertIn(("GET", "/admin/api/portraits"), routes)
        self.assertIn(("GET", "/admin/api/portraits/{user_id}"), routes)


# ───────────────────── haqiqiy PostgreSQL (ixtiyoriy) ───────────────────────

PG_URL = os.getenv("PORTRAIT_PG_URL", "").strip()


@unittest.skipUnless(PG_URL, "PORTRAIT_PG_URL berilmagan — haqiqiy Postgres tekshiruvi o'tkazildi")
class PostgresTest(unittest.TestCase):
    """Yangi SQL haqiqiy Postgres da: ro'yxat, hisoblagichlar, filtr, qidiruv,
    sahifalash, o'chirgan mijoz va xodimlar."""

    def test_round_trip(self):
        run(self._round_trip())

    async def _round_trip(self):
        import asyncpg
        schema = f"portrait_web_test_{os.getpid()}"
        admin = await asyncpg.connect(PG_URL)
        await admin.execute(f"CREATE SCHEMA {schema}")
        saved = (database.pool, customer_portrait._table_ready, ai_memory._table_ready, ai_stats._table_ready,
                 portrait_web.PER_PAGE)
        pool = await asyncpg.create_pool(PG_URL, min_size=1, max_size=2, server_settings={"search_path": schema})
        database.pool = pool
        customer_portrait._table_ready = ai_memory._table_ready = ai_stats._table_ready = False
        try:
            async with pool.acquire() as conn:
                await conn.execute("""CREATE TABLE users (user_id BIGINT PRIMARY KEY, username TEXT, full_name TEXT,
                                      language TEXT DEFAULT 'uz', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                      keto_balance INTEGER NOT NULL DEFAULT 0, keto_lifetime INTEGER NOT NULL DEFAULT 0)""")
                await conn.execute("""CREATE TABLE orders (id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL,
                                      total DOUBLE PRECISION NOT NULL, status TEXT DEFAULT 'pending', items TEXT,
                                      source TEXT, delivery_method TEXT,
                                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
                await ai_stats._ensure(conn)
                people = [(11, "dilnoza_t", "Test Mijoz"), (12, None, "Sardor"), (13, None, "Gulnora Test"),
                          (14, "bek_14", "Bekzod"), (15, None, "Guruhdagi"), (ADMIN_IDS[0], None, "Admin"),
                          (INTERNAL, None, "Do'kon")]
                await conn.executemany("INSERT INTO users (user_id, username, full_name) VALUES ($1, $2, $3)", people)
                await conn.execute("UPDATE users SET keto_balance = 140, keto_lifetime = 320 WHERE user_id = 11")
                for uid, channel, hours_ago, topics in (
                        (11, "bot", 30, ["narx"]), (11, "site", 2, ["narx", "keto"]), (12, "bot", 5, []),
                        (13, "bot", 1, ["yetkazish"]), (14, "site", 10, ["tolov"]), (15, "group", 0, ["narx"]),
                        (ADMIN_IDS[0], "bot", 0, []), (INTERNAL, "site", 0, [])):
                    await conn.execute(
                        "INSERT INTO ai_conversations (user_id, channel, started_at, last_at, messages, topics) "
                        "VALUES ($1, $2, NOW() AT TIME ZONE 'UTC' - make_interval(hours => $3), "
                        "NOW() AT TIME ZONE 'UTC' - make_interval(hours => $3), 2, $4)",
                        uid, channel, hours_ago, topics)
                items = json.dumps([{"product_id": 3, "name": "Bodom uni", "quantity": 1, "price": 95000}])
                for uid, total, status, source in ((11, 95000, "delivered", "bot"), (11, 50000, "cancelled", "bot"),
                                                   (11, 120000, "pending", "webapp"), (14, 70000, "delivered", None),
                                                   (14, 900000, "delivered", "b2b")):
                    await conn.execute("INSERT INTO orders (user_id, total, status, items, source) "
                                       "VALUES ($1, $2, $3, $4, $5)", uid, total, status, items, source)

            await customer_portrait.save(11, name="Dilnoza", age=28, goals=["ozish"], telegram_name="Test Mijoz")
            await customer_portrait.save(12, age=40, telegram_name="Sardor")
            await customer_portrait.save(13, name="Gulnora", goals=["keto"])
            await customer_portrait.forget(13)
            await customer_portrait.save(ADMIN_IDS[0], name="Admin", age=30)
            await ai_memory.remember(11, "qiziqish", "Bodom uni")
            await ai_memory.remember(11, "fikr", "Eritritol yoqdi")
            await ai_memory.record_recipe(11, 3, "Keto non")
            async with pool.acquire() as conn:     # o'chirgandan keyin qolib ketgan eslatma (eski ma'lumot)
                await conn.execute("INSERT INTO ai_customer_notes (user_id, kind, text) VALUES (13, 'note', 'eski')")

            data = await portrait_web.list_page()
            self.assertEqual([r["user_id"] for r in data["rows"]], [13, 11, 12, 14])   # oxirgi suhbat yangisi oldin
            self.assertEqual(data["stats"], {"talked": 4, "portraits": 2, "with_name": 1, "with_age": 2,
                                             "female": 1, "male": 1, "with_goals": 1, "opted_out": 1,
                                             "with_orders": 2})
            self.assertEqual(data["goals"], [{"goal": "ozish", "label": "ozish", "n": 1}])
            rows = {r["user_id"]: r for r in data["rows"]}
            self.assertEqual((rows[11]["orders"], rows[11]["spent"], rows[11]["conversations"], rows[11]["channels"]),
                             (2, 215000.0, 2, ["bot", "site"]))
            self.assertEqual((rows[14]["orders"], rows[14]["spent"]), (1, 70000.0))          # B2B emas
            self.assertEqual([t["key"] for t in rows[11]["topics"]], ["narx", "keto"])
            self.assertEqual((rows[11]["display_name"], rows[11]["gender"], rows[11]["age_group"]),
                             ("Dilnoza", "f", "25–34"))
            self.assertEqual((rows[12]["gender"], rows[12]["gender_source"]), ("m", "name"))
            self.assertTrue(rows[13]["opted_out"])
            self.assertEqual((rows[13]["display_name"], rows[13]["goals"], rows[13]["topics"]), (None, [], []))

            async def ids(**kw):
                return [r["user_id"] for r in (await portrait_web.list_page(**kw))["rows"]]
            self.assertEqual(await ids(flt="portrait"), [11, 12])
            self.assertEqual(await ids(flt="no_portrait"), [13, 14])
            self.assertEqual(await ids(flt="orders"), [11, 14])
            self.assertEqual(await ids(q="dilnoza"), [11])          # murojaat ismi
            self.assertEqual(await ids(q="@DILNOZA_"), [11])        # username, katta-kichik harfsiz
            self.assertEqual(await ids(q="bekzod"), [14])           # Telegram ismi
            self.assertEqual(await ids(q="14"), [14])               # aniq ID
            self.assertEqual(await ids(q="gulnora"), [13])          # Telegram ismi qoladi …
            self.assertEqual(await ids(q="Gulnora", flt="portrait"), [])   # … portret yo'q
            self.assertEqual(await ids(q="100%"), [])

            portrait_web.PER_PAGE = 3
            page2 = await portrait_web.list_page(page=2)
            self.assertEqual(([r["user_id"] for r in page2["rows"]], page2["total"], page2["pages"]), ([14], 4, 2))
            portrait_web.PER_PAGE = saved[4]

            full = await portrait_web.card(11)
            self.assertEqual([n["kind"] for n in full["notes"]], ["feedback", "interest"])
            self.assertEqual([o["status"] for o in full["recent_orders"]], ["pending", "cancelled", "delivered"])
            self.assertEqual((full["keto_balance"], full["tme_link"]), (140, "https://t.me/dilnoza_t"))
            gone = await portrait_web.card(13)
            self.assertTrue(gone["opted_out"])
            self.assertEqual((gone["notes"], gone["topics"], gone["display_name"]), ([], [], None))
            for uid in (ADMIN_IDS[0], INTERNAL, 15, 999):
                self.assertIsNone(await portrait_web.card(uid))
        finally:
            await pool.close()
            (database.pool, customer_portrait._table_ready, ai_memory._table_ready, ai_stats._table_ready,
             portrait_web.PER_PAGE) = saved
            await admin.execute(f"DROP SCHEMA {schema} CASCADE")
            await admin.close()


if __name__ == "__main__":
    unittest.main()
