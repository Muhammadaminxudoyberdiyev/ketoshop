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


if __name__ == "__main__":
    unittest.main()
