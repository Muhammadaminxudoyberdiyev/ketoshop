"""📱 Ilovani server boshqaradigan qism (app_config.py): versiya, funksiyalar,
bosh sahifa bloklari. Bazaga va Telegram'ga murojaat yo'q (mock)."""
import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import app_config


def run(coro):
    return asyncio.run(coro)


class ConfigTest(unittest.TestCase):
    def setUp(self):
        app_config._cache.clear()
        self.patches = [
            patch("promotions.get_active", AsyncMock(return_value=None)),
            patch("bot_discount.site_banner", AsyncMock(return_value=None)),
            patch("mystery_gift.card_line", return_value=""),
            patch("mystery_gift.free_delivery_card_line", return_value=""),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        app_config._cache.clear()

    def test_shape(self):
        data = run(app_config.build("uz"))
        for key in ("latest_version", "latest_build", "min_build", "update_url", "features", "delivery", "home"):
            self.assertIn(key, data)
        self.assertLessEqual(data["min_build"], data["latest_build"])
        self.assertEqual(data["delivery"]["tashkent"][0], "self")
        self.assertTrue(data["update_url"].startswith("https://"))

    def test_env_overrides_and_min_never_above_latest(self):
        with patch.dict(os.environ, {"APP_LATEST_BUILD": "5", "APP_MIN_BUILD": "9", "APP_APK_URL": "https://example.uz/k.apk"}):
            data = run(app_config.build("ru"))
        self.assertEqual((data["latest_build"], data["min_build"]), (5, 5))
        self.assertEqual(data["update_url"], "https://example.uz/k.apk")

    def test_live_blocks_and_manual_blocks(self):
        promo = {"id": 3, "name": "Kuzgi aksiya", "conditions": "<b>2 ta</b> oling", "image_url": "AgACfile", "ends_at": None}
        manual = [
            {"type": "notice", "id": "n1", "text": {"uz": "Yangi bo'lim ochildi", "ru": "Открылся новый раздел"}},
            {"type": "products", "id": "p1", "title": {"uz": "Tavsiya"}, "product_ids": ["4", 5]},
            {"type": "hologram", "id": "future"},
        ]
        with patch("promotions.get_active", AsyncMock(return_value=promo)), \
                patch.object(app_config, "EXTRA_BLOCKS", manual):
            blocks = run(app_config.home_blocks("uz_cyr"))
        kinds = [b["type"] for b in blocks]
        self.assertEqual(kinds, ["banner", "notice", "products"])   # unknown type dropped
        self.assertEqual(blocks[0]["image_url"], "/api/photo/AgACfile")
        self.assertNotIn("<b>", blocks[0]["text"])
        self.assertTrue(any("Ѐ" <= ch <= "ӿ" for ch in blocks[1]["text"]))   # uz_cyr
        self.assertEqual(blocks[2]["product_ids"], [4, 5])

    def test_a_failing_source_never_breaks_the_list(self):
        with patch("promotions.get_active", AsyncMock(side_effect=RuntimeError("db down"))):
            self.assertEqual(run(app_config.home_blocks("uz")), [])

    def test_handler_is_public_json(self):
        from aiohttp.test_utils import make_mocked_request
        response = run(app_config.handle_config(make_mocked_request("GET", "/app/v1/config?lang=ru")))
        body = json.loads(response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("server_time", body)


if __name__ == "__main__":
    unittest.main()
