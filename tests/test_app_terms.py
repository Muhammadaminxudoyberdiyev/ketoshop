"""📄 Ilovadagi «Oferta shartlari» (app_terms.py): matn, tillar, tahrir."""
import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import app_terms


class TermsTest(unittest.TestCase):
    def test_every_item_in_both_languages(self):
        for section in app_terms.SECTIONS:
            self.assertTrue(section["title"]["uz"] and section["title"]["ru"])
            for item in section["items"]:
                self.assertTrue(item["uz"].strip() and item["ru"].strip(), item)

    def test_render_languages(self):
        uz, ru, cyr = (app_terms.render(lang) for lang in ("uz", "ru", "uz_cyr"))
        self.assertEqual(uz["version"], app_terms.VERSION)
        self.assertEqual(len(uz["sections"]), len(ru["sections"]))
        self.assertIn("168-modda", " ".join(" ".join(s["items"]) for s in uz["sections"]))
        self.assertIn("статье 168", " ".join(" ".join(s["items"]) for s in ru["sections"]))
        self.assertTrue(any("Ѐ" <= ch <= "ӿ" for ch in cyr["title"]))
        self.assertEqual(app_terms.render("xx")["title"], uz["title"])

    def test_liability_clause_present(self):
        text = " ".join(" ".join(s["items"]) for s in app_terms.render("uz")["sections"])
        for phrase in ("soxta deb topiladi", "huquqni muhofaza qiluvchi organlarga", "278²-modda", "O'RQ-547"):
            self.assertIn(phrase, text)

    def test_seller_shown_only_when_filled(self):
        self.assertNotEqual(app_terms.render("uz")["sections"][0]["title"], "Sotuvchi")
        with patch.dict(app_terms.SELLER, {"name": "Ketoshop MChJ", "tin": "123456789", "address": "Toshkent"}):
            first = app_terms.render("uz")["sections"][0]
        self.assertEqual(first["title"], "Sotuvchi")
        self.assertEqual(first["items"], ["Ketoshop MChJ, STIR 123456789, Toshkent"])

    def test_version_format(self):
        self.assertEqual(app_terms.clean_version("2026-11-17"), "2026-11-17")
        for bad in ("2026-11-17; DROP", "", None, 20261117, "x" * 40):
            self.assertIsNone(app_terms.clean_version(bad))

    def test_public_handler(self):
        import asyncio
        from aiohttp.test_utils import make_mocked_request
        response = asyncio.run(app_terms.handle_terms(make_mocked_request("GET", "/app/v1/terms?lang=ru")))
        self.assertEqual(json.loads(response.text)["version"], app_terms.VERSION)


if __name__ == "__main__":
    unittest.main()
