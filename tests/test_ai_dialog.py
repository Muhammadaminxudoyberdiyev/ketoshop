"""ai_dialog — bot, sayt va guruhdagi oxirgi suhbatlar (egasi, 2026-11-16:
"bitta mijoz guruhda gaplashadimi, chatdami, botdami farqi yo'q").
Bazaga ulanmaydi."""
import asyncio
import os
import unittest
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import ai_dialog  # noqa: E402
import database  # noqa: E402

TURNS = [
    {"id": 1, "channel": "bot", "question": "raqamim +998 90 123-45-67, manzil Chilonzor",
     "answer": "Buyurtma №5003 qabul qilindi, 178 000 so'm", "created_at": datetime(2026, 11, 16, 12, 0)},
    {"id": 2, "channel": "site", "question": "steviya bormi", "answer": "Bor, 33 000 so'm",
     "created_at": datetime(2026, 11, 16, 13, 0)},
    {"id": 3, "channel": "group", "question": "allulozani ham zarari bormi",
     "answer": "Me'yorida ishlatilsa zarari yo'q.", "created_at": datetime(2026, 11, 16, 17, 42)},
]


class ContextBlockTest(unittest.TestCase):
    def test_private_block_has_every_channel_and_answer(self):
        block = ai_dialog.context_block(TURNS)
        for text in ("botda", "saytda", "kanal guruhida", "Buyurtma №5003", "Bor, 33 000 so'm",
                     "Me'yorida ishlatilsa zarari yo'q.", "22:42"):          # 17:42 UTC = 22:42 Toshkent
            self.assertIn(text, block)
        self.assertLess(block.index("raqamim"), block.index("allulozani"))  # eskisidan yangisiga

    def test_group_block_keeps_private_answers_and_phones_out(self):
        block = ai_dialog.context_block(TURNS, public=True)
        self.assertIn("allulozani ham zarari bormi", block)
        self.assertIn("Me'yorida ishlatilsa zarari yo'q.", block)          # guruhdagi javob ochiq
        self.assertIn("steviya bormi", block)                               # mavzu bor
        self.assertNotIn("33 000", block)                                   # saytdagi javob yo'q
        self.assertNotIn("5003", block)                                     # botdagi javob yo'q
        self.assertNotIn("123-45-67", block)                                # telefon yashirin
        self.assertIn("SHAXSIY", block)

    def test_nothing_to_say(self):
        self.assertEqual(ai_dialog.context_block([]), "")


class NoDatabaseTest(unittest.TestCase):
    def test_without_a_pool_nothing_raises(self):
        saved = database.pool
        database.pool = None
        try:
            run = asyncio.new_event_loop().run_until_complete
            self.assertIsNone(run(ai_dialog.record(1, "bot", "salom", "Salom!")))
            self.assertEqual(run(ai_dialog.recent(1)), [])
            self.assertEqual(run(ai_dialog.forget(1)), 0)
        finally:
            database.pool = saved


class _Conn:
    """SQL ni yozib boradi; hech kim opt-out qilmagan, takror eslatma yo'q."""

    def __init__(self):
        self.sql = []

    async def execute(self, sql, *args):
        self.sql.append((" ".join(sql.split()), args))
        return "INSERT 0 1"

    async def fetchval(self, sql, *args):
        self.sql.append((" ".join(sql.split()), args))
        return None


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self):
                return pool.conn

            async def __aexit__(self, *exc):
                return False
        return _Ctx()


class KeepEverythingTest(unittest.TestCase):
    """Egasi, 2026-11-17: "biz hammasini cheksiz saqlashimiz kerak"."""

    def setUp(self):
        self.saved = database.pool
        self.conn = _Conn()
        database.pool = _Pool(self.conn)
        self.run = asyncio.new_event_loop().run_until_complete

    def tearDown(self):
        database.pool = self.saved

    def test_dialog_keeps_the_full_text_and_deletes_nothing(self):
        long_question = "bodom uni haqida " * 100                       # 1 700 belgi
        self.run(ai_dialog.record(1, "bot", long_question, "Javob " * 200))
        inserts = [args for sql, args in self.conn.sql if sql.startswith("INSERT INTO ai_dialog")]
        self.assertEqual(len(inserts), 1)
        self.assertEqual(inserts[0][2], long_question.strip())          # qisqartirilmagan
        self.assertEqual(inserts[0][3], ("Javob " * 200).strip())
        self.assertFalse([sql for sql, _ in self.conn.sql if sql.startswith("DELETE")])

    def test_memory_notes_are_not_trimmed_either(self):
        import ai_memory
        self.assertTrue(self.run(ai_memory.remember(1, "qiziqish", "keto non pishirmoqchi")))
        self.assertFalse([sql for sql, _ in self.conn.sql if sql.startswith("DELETE")])


if __name__ == "__main__":
    unittest.main()
