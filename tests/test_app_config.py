"""📱 Ilovaning versiya va yangilanish sozlamasi (app_config.py)."""
import asyncio
import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import app_config
import app_terms


class ConfigTest(unittest.TestCase):
    def test_shape(self):
        data = app_config.build("uz")
        self.assertEqual(set(data), {"latest_version", "latest_build", "min_build", "update_url",
                                     "update_notes", "terms_version"})
        self.assertLessEqual(data["min_build"], data["latest_build"])
        self.assertEqual(data["terms_version"], app_terms.VERSION)
        self.assertTrue(data["update_url"].startswith("https://"))

    def test_languages(self):
        self.assertIn("версия", app_config.build("ru")["update_notes"])
        self.assertTrue(any("Ѐ" <= ch <= "ӿ" for ch in app_config.build("uz_cyr")["update_notes"]))
        self.assertEqual(app_config.build("xx")["update_notes"], app_config.build("uz")["update_notes"])

    def test_env_overrides_and_min_never_above_latest(self):
        with patch.dict(os.environ, {"APP_LATEST_BUILD": "5", "APP_MIN_BUILD": "9",
                                     "APP_APK_URL": "https://example.uz/k.apk"}):
            data = app_config.build("ru")
        self.assertEqual((data["latest_build"], data["min_build"]), (5, 5))
        self.assertEqual(data["update_url"], "https://example.uz/k.apk")

    def test_handler_is_public_json(self):
        from aiohttp.test_utils import make_mocked_request
        response = asyncio.run(app_config.handle_config(make_mocked_request("GET", "/app/v1/config?lang=ru")))
        body = json.loads(response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("server_time", body)


if __name__ == "__main__":
    unittest.main()
