"""Eritritol sovg'asi: 17.11 da tugadi, 3 kun pauza, 20.11 09:00 da yana 40 kun —
hammaga va kanalga e'lon (egasi, 2026-11-17; oldin 18.10 da 30 kun). Telegram
va bazaga ulanmasdan: hech kimga haqiqiy xabar ketmaydi."""
import asyncio
import os
import re
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://unused/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import database
import gift_campaign as g

UNTIL = datetime(2026, 12, 30, 9, 0)
ENDED = {"key": g.CAMPAIGN_KEY, "announced_at": datetime(2026, 9, 17, 4, 0),
         "ends_at": datetime(2026, 11, 17, 4, 0), "ended_notified_at": datetime(2026, 11, 17, 4, 5)}
DAY = datetime(2026, 11, 20, 9, 3)                  # the comeback, 3 days after 17.11
PROD = {"id": 9, "name": "Eritritol 100gr", "quantity": 120, "photo_id": "PHOTO"}


def run(coro):
    return asyncio.run(coro)


class TextTest(unittest.TestCase):
    def test_opens_with_by_popular_demand_in_every_language(self):
        self.assertTrue(g.extension_text("uz", UNTIL).startswith(
            "🎉 <b>Talab va takliflaringizga binoan — sovg'a aksiyasi davom etadi!</b>"))
        self.assertTrue(g.extension_text("uz_cyr", UNTIL).startswith(
            "🎉 <b>Талаб ва таклифларингизга биноан — совға акцияси давом этади!</b>"))
        self.assertTrue(g.extension_text("ru", UNTIL).startswith(
            "🎉 <b>По вашим просьбам и пожеланиям — акция с подарком продолжается!</b>"))

    def test_facts_and_caption_size(self):
        for lang in ("uz", "uz_cyr", "ru"):
            for channel in (False, True):
                text = g.extension_text(lang, UNTIL, channel=channel)
                self.assertIn("30.12.2026", text)
                self.assertIn("40 kun" if lang == "uz" else ("40 кун" if lang == "uz_cyr" else "40 дней"), text)
                self.assertLess(len(re.sub(r"<[^>]+>", "", text)), 1024)     # photo caption
                self.assertEqual(text.count("<b>"), text.count("</b>"))
                self.assertNotIn("{", text)

    def test_channel_copy_links_the_bot_even_in_cyrillic(self):
        text = g.extension_text("uz_cyr", UNTIL, channel=True)
        self.assertIn('🛒 Буюртма бериш: <a href="https://t.me/ketoshopbot">@ketoshopbot</a>', text)
        self.assertNotIn("Hoziroq", text)
        self.assertNotIn("t.me", g.extension_text("uz", UNTIL))            # the bot copy has the button

    def test_no_pressure_words(self):
        for lang in ("uz", "ru"):
            low = g.extension_text(lang, UNTIL).lower()
            for word in ("faqat bugun", "shoshiling", "только сегодня", "успейте", "последний шанс"):
                self.assertNotIn(word, low)


class TickTest(unittest.TestCase):
    def tick(self, now, row=ENDED, prod=PROD, claimed=True):
        bot = MagicMock()
        # The extended campaign must still be running: _active_row compares
        # with the real clock, so a fixed date (it was 17.11.2026 04:00 UTC)
        # turned this into the "campaign over" path once that hour passed.
        extended = dict(row, ends_at=datetime.utcnow() + timedelta(days=30), ended_notified_at=None)
        states = iter([row, extended, extended, extended])
        with patch.object(g, "_now_tk", lambda: now), \
             patch.object(g, "_state", AsyncMock(side_effect=lambda force=False: next(states))), \
             patch.object(g, "gift_product", AsyncMock(return_value=prod)), \
             patch.object(g, "book_delivered_gifts", AsyncMock(return_value=(0, 0.0))), \
             patch.object(g, "announce_extension", AsyncMock(return_value={
                 "sent": 10, "failed": 1, "channel": True, "until": UNTIL})) as announce, \
             patch.object(g, "_notify_admins", AsyncMock()) as notify, \
             patch.object(database, "claim_release_notes", AsyncMock(side_effect=lambda key: claimed and key == g.EXTEND_KEY)) as claim, \
             patch.object(database, "claim_gift_stock_alert", AsyncMock(return_value=True)) as alert, \
             patch.object(database, "extend_gift_campaign", AsyncMock()) as extend, \
             patch.object(database, "get_gift_campaign_stats", AsyncMock(return_value={})), \
             patch.object(database, "mark_gift_ended_notified", AsyncMock()):
            run(g._tick(bot))
        return announce, notify, claim, alert, extend

    def test_switches_back_on_and_announces_at_nine_on_the_20th(self):
        self.assertEqual((g.EXTEND_KEY, g.EXTEND_FROM, g.EXTEND_DAYS),
                         ("gift-extend-2026-11-20", DAY.date(), 40))
        announce, notify, claim, _, extend = self.tick(DAY)
        self.assertIn(g.EXTEND_KEY, [c.args[0] for c in claim.await_args_list])
        extend.assert_awaited_once_with(g.CAMPAIGN_KEY, 40)
        announce.assert_awaited_once()
        admin = notify.await_args.args[1]
        self.assertIn("yana 40 kunga uzaytirildi", admin)
        self.assertIn("30.12.2026", admin)
        self.assertIn("✅ 10 ta", admin)
        self.assertIn("Kanal: ✅ chiqdi", admin)

    def test_paused_three_days_not_before_nine_not_after_noon_not_twice(self):
        for now in (datetime(2026, 11, 17, 10, 0), datetime(2026, 11, 18, 9, 3),
                    datetime(2026, 11, 19, 9, 3), datetime(2026, 11, 20, 8, 59),
                    datetime(2026, 11, 20, 12, 0)):
            announce, _, _, _, extend = self.tick(now)
            announce.assert_not_awaited()
            extend.assert_not_awaited()
        announce, _, _, _, extend = self.tick(DAY, claimed=False)
        announce.assert_not_awaited()
        extend.assert_not_awaited()

    def test_not_while_the_campaign_is_running_or_long_after(self):
        live = dict(ENDED, ends_at=datetime(2030, 1, 1))
        for row, now in ((live, DAY), (ENDED, datetime(2026, 11, 23, 9, 3))):
            announce, _, claim, _, extend = self.tick(now, row=row)
            announce.assert_not_awaited()
            extend.assert_not_awaited()

    def test_missing_gift_product_waits_and_tells_the_admins(self):
        announce, notify, claim, alert, extend = self.tick(DAY, prod=None)
        announce.assert_not_awaited()
        extend.assert_not_awaited()
        self.assertNotIn(g.EXTEND_KEY, [c.args[0] for c in claim.await_args_list])
        alert.assert_awaited_once()
        self.assertIn("uzaytirilmadi", notify.await_args.args[1])


class ComebackMorningTest(unittest.TestCase):
    """20.11: the announcement gets the day's one message (push_cap), so the
    07:45 feedback ask and the 08:00 tip wait a day."""

    def test_comeback_day_is_only_the_20th(self):
        self.assertTrue(g.comeback_day(DAY.date()))
        for d in (17, 18, 19, 21, 22):
            self.assertFalse(g.comeback_day(datetime(2026, 11, d).date()))

    def feedback_tick(self, now):
        import feedback_ask
        with patch.object(feedback_ask, "_now_tk", lambda: now), \
             patch.object(feedback_ask, "enabled", AsyncMock(return_value=True)), \
             patch.object(feedback_ask, "send_round", AsyncMock(return_value=dict.fromkeys(
                 ("sent", "ai", "capped", "nothing", "failed"), 0))) as send, \
             patch.object(database, "claim_release_notes", AsyncMock(return_value=True)):
            run(feedback_ask._tick(MagicMock()))
        return send

    def test_feedback_ask_skips_the_comeback_morning(self):
        self.feedback_tick(datetime(2026, 11, 20, 7, 50)).assert_not_awaited()
        self.feedback_tick(datetime(2026, 11, 22, 7, 50)).assert_awaited_once()     # its next day

    def tip_tick(self, now, last):
        import broadcast
        state = {"enabled": True, "next_index": 0, "last_sent_at": last - broadcast.TZ_OFFSET}
        with patch.object(broadcast, "_now_tk", lambda: now), \
             patch.object(broadcast, "TIPS", ["tip"]), \
             patch.object(broadcast, "_maybe_warn_low_content", AsyncMock()), \
             patch.object(broadcast, "send_next_tip", AsyncMock()) as send, \
             patch.object(database, "get_broadcast_state", AsyncMock(return_value=state)):
            run(broadcast._tick(MagicMock()))
        return send

    def test_tip_waits_until_the_next_morning(self):
        last = datetime(2026, 11, 18, 8, 0)
        self.tip_tick(datetime(2026, 11, 20, 8, 5), last).assert_not_awaited()
        self.tip_tick(datetime(2026, 11, 21, 8, 5), last).assert_awaited_once()
        self.tip_tick(datetime(2026, 11, 19, 8, 5), datetime(2026, 11, 17, 8, 0)).assert_awaited_once()


class AnnounceTest(unittest.TestCase):
    def test_everyone_in_their_language_and_the_channel_without_a_button(self):
        bot = MagicMock()
        sends = []

        async def fake_send_photo(_bot, chat_id, photo, text, markup):
            sends.append((chat_id, photo, text, markup))
            return chat_id != 3                                       # user 3 blocked the bot

        row = dict(ENDED, ends_at=datetime(2026, 12, 30, 4, 0))
        with patch.object(g, "_state", AsyncMock(return_value=row)), \
             patch.object(g, "gift_product", AsyncMock(return_value=PROD)), \
             patch.object(g, "_send_photo", side_effect=fake_send_photo), \
             patch.object(g, "SEND_DELAY", 0), \
             patch("config.REQUIRED_CHANNEL_ID", -100500), \
             patch.object(database, "claim_user_push", AsyncMock(return_value=True)), \
             patch.object(database, "get_all_user_ids", AsyncMock(return_value=[1, 2, 3])), \
             patch.object(database, "get_user_languages", AsyncMock(return_value={1: "uz", 2: "ru", 3: "uz_cyr"})):
            stats = run(g.announce_extension(bot))
        self.assertEqual((stats["sent"], stats["failed"], stats["channel"]), (2, 1, True))
        self.assertEqual(stats["until"], UNTIL)
        channel = sends[0]
        self.assertEqual(channel[0], -100500)
        self.assertIsNone(channel[3])                                 # comments stay open
        self.assertIn("Талаб ва таклифларингизга биноан", channel[2])
        by_user = {s[0]: s for s in sends[1:]}
        self.assertIn("Talab va takliflaringizga binoan", by_user[1][2])
        self.assertIn("По вашим просьбам", by_user[2][2])
        self.assertIsNotNone(by_user[1][3])                           # shop button for bot users
        self.assertTrue(all(s[1] == "PHOTO" for s in sends))


if __name__ == "__main__":
    unittest.main()
