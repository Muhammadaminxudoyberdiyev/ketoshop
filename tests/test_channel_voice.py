"""Kanal postlari jonli va har xil uzunlikda (channel_voice.py, egasi 2026-11-15) —
faktlar shablondan, biror shart buzilsa shablonning o'zi chiqadi."""
import asyncio
import os
import random
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import channel_voice as cv  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL = ('🍬 <b>Шакар ўрнига нима?</b>\n\nЭритритол 500 гр — 76 000 сўм. Қондаги қандни оширмайди.\n'
            'Батафсил: <a href="https://t.me/ketoshopbot/shop?startapp=erit">Дўкон</a> · @ketoshopbot')
GOOD = ('Чой ширин бўлсин-у, шакарсиз? 😉 Эритритол 500 гр — 76 000 сўм. '
        '<a href="https://t.me/ketoshopbot/shop?startapp=erit">Дўконда</a> бор, @ketoshopbot')


class ProblemsTest(unittest.TestCase):
    def test_a_good_rewrite_passes(self):
        self.assertEqual(cv.problems(ORIGINAL, GOOD, 4096), [])

    def test_lost_link_or_handle(self):
        self.assertTrue(any("havola" in p for p in cv.problems(ORIGINAL, GOOD.replace('href="', 'href="x'), 4096)))
        self.assertTrue(any("@ketoshopbot" in p for p in cv.problems(ORIGINAL, GOOD.replace(", @ketoshopbot", ""), 4096)))

    def test_no_invented_numbers_but_dropping_is_fine(self):
        self.assertTrue(any("yangi raqam" in p for p in cv.problems(ORIGINAL, GOOD.replace("76 000", "69 000"), 4096)))
        shorter = GOOD.replace("Эритритол 500 гр — 76 000 сўм. ", "Эритритол бор. ")
        self.assertEqual(cv.problems(ORIGINAL, shorter, 4096), [])

    def test_html_and_spoiler_and_script(self):
        self.assertIn("HTML teglari", cv.problems(ORIGINAL, GOOD + "<b>", 4096))
        self.assertIn("HTML teglari", cv.problems(ORIGINAL, GOOD + "<script>x</script>", 4096))
        spoiled = ORIGINAL + "\n<tg-spoiler>Жавоб: йўқ</tg-spoiler>"
        self.assertIn("spoiler yo'qoldi", cv.problems(spoiled, GOOD, 4096))
        latin = ('Choy shirin, shakarsiz 😉 Eritritol 500 gr — 76 000 so\'m. '
                 '<a href="https://t.me/ketoshopbot/shop?startapp=erit">Do\'kon</a> @ketoshopbot')
        self.assertIn("yozuv boshqa", cv.problems(ORIGINAL, latin, 4096))

    def test_must_fit_with_room_for_the_footer(self):
        self.assertIn("uzun", cv.problems(ORIGINAL, GOOD + " ҳа" * 400, 1024))


class LengthTest(unittest.TestCase):
    def test_lengths_vary_and_never_exceed_the_template_or_limit(self):
        rng = random.Random(7)
        names = set()
        for _ in range(200):
            name, lo, hi = cv.pick_length("а" * 2000, 1024, rng)
            names.add(name)
            self.assertLessEqual(hi, 1024 - cv.MARGIN)
            self.assertLessEqual(lo, hi)
        self.assertEqual(names, {"qisqa", "o'rta", "uzun"})
        _, lo, hi = cv.pick_length("а" * 150, 4096, rng)
        self.assertLessEqual(hi, 150)


class RewriteTest(unittest.TestCase):
    def run_rewrite(self, answer=None, error=None, on=True):
        ask = AsyncMock(side_effect=error) if error else AsyncMock(return_value=answer)
        with patch.object(cv, "enabled", AsyncMock(return_value=on)), patch.object(cv, "_ask", ask):
            return asyncio.run(cv.rewrite(ORIGINAL, "kontent", 4096)), ask

    def test_good_answer_is_posted(self):
        out, _ = self.run_rewrite(GOOD)
        self.assertEqual(out, GOOD)

    def test_template_when_off_failing_or_unsafe(self):
        out, ask = self.run_rewrite(GOOD, on=False)
        self.assertEqual(out, ORIGINAL)
        ask.assert_not_awaited()
        self.assertEqual(self.run_rewrite(error=RuntimeError("429"))[0], ORIGINAL)
        self.assertEqual(self.run_rewrite(None)[0], ORIGINAL)
        self.assertEqual(self.run_rewrite(GOOD.replace("76 000", "99 000"))[0], ORIGINAL)


class RecipePostTest(unittest.TestCase):
    def test_body_is_rewritten_but_the_full_recipe_cta_never(self):
        # Egasi, 2026-11-15: "to'liq retseptni ko'rish uchun link ustiga bosing deb aniq yozuv ham qo'sh".
        import recipe_channel
        import recipes_content
        r = next(x for x in recipes_content.RECIPES if x["slug"] == "keto-pitsa")
        bot = NS(send_photo=AsyncMock())
        rewrite = AsyncMock(return_value="QAYTA YOZILDI")
        with patch.object(cv, "rewrite", rewrite),                 patch.object(recipe_channel, "main_app_enabled", AsyncMock(return_value=True)),                 patch.object(recipe_channel, "photo", lambda recipe: "PHOTO"):
            self.assertTrue(asyncio.run(recipe_channel.post_to_channel(bot, r, chat_id=1)))
        cap = bot.send_photo.await_args.kwargs["caption"]
        self.assertTrue(cap.startswith("QAYTA YOZILDI"))
        self.assertIn("ТЎЛИҚ РЕЦЕПТНИ САЙТИМИЗ ОРҚАЛИ КЎРИНГ", cap)
        self.assertIn("кўк ёзув устига босинг", cap)
        self.assertNotIn("ТЎЛИҚ РЕЦЕПТНИ", rewrite.await_args.args[0])          # the CTA never goes to the AI


class HooksTest(unittest.TestCase):
    def test_the_four_content_posters_use_it_and_list_posts_dont(self):
        for module, kind in (("channel_posts", '"kontent"'), ("keto_fakt", '"fakt"'),
                             ("recipe_channel", '"retsept"'), ("product_of_day", '"kun_mahsuloti"')):
            src = (ROOT / f"{module}.py").read_text(encoding="utf-8")
            self.assertIn("channel_voice.rewrite(", src, module)
            self.assertIn(kind, src, module)
        for module in ("top20_post", "channel_bestsellers"):
            self.assertNotIn("channel_voice", (ROOT / f"{module}.py").read_text(encoding="utf-8"), module)


if __name__ == "__main__":
    unittest.main()
