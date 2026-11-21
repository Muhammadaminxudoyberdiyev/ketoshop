"""📱 «Saytda nima bor?» kanal rubrikasi (egasi, 2026-11-21)."""
import os
import re
import unittest
from datetime import date

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import channel_features as cf
import keto_fakt


class ScheduleTest(unittest.TestCase):
    def test_every_three_days_and_never_on_a_clash_with_the_slot_of_keto_fakt(self):
        days = [d for d in (date(2026, 11, 22 + i) for i in range(9)) if cf.is_post_day(d)]
        self.assertEqual([d.day for d in days], [22, 25, 28])
        self.assertNotEqual(cf.POST_AT[0], keto_fakt.FACT_HOUR)

    def test_posts_rotate_and_come_back(self):
        first = cf.post_for(date(2026, 11, 22))
        self.assertIs(cf.post_for(date(2026, 11, 25)), cf.POSTS[1])
        from datetime import timedelta
        self.assertIs(cf.post_for(date(2026, 11, 22) + timedelta(days=3 * len(cf.POSTS))), first)


class TextTest(unittest.TestCase):
    def test_every_post_is_cyrillic_linked_and_fits(self):
        for post in cf.POSTS:
            text = cf.post_text(post)
            plain = re.sub(r"<[^>]+>", "", text)
            self.assertLess(len(plain), 1500)
            self.assertIn("t.me/", text)
            self.assertTrue(text.endswith(cf.HASHTAG))
            self.assertEqual(text.count("<b>"), text.count("</b>"))
            latin_words = re.findall(r"\b[a-z]{5,}\b", re.sub(r"<[^>]+>|https?://\S+|@\w+", "", text))
            self.assertEqual(latin_words, [], post[1])

    def test_games_posts_open_the_games(self):
        games = [p for p in cf.POSTS if p[0] == cf.GAMES]
        self.assertGreaterEqual(len(games), 4)
        self.assertIn("startapp=oyin", cf.post_text(games[0]))


if __name__ == "__main__":
    unittest.main()
