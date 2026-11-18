"""Bosh sahifa tezroq (egasi, 2026-11-18): the Mini App's JSON is gzipped too,
versioned /static/ files are kept by the phone, other static files are
revalidated. Real aiohttp app, no database, no Telegram."""
import hashlib
import hmac
import json
import os
import time
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import webapp_server as ws

TOKEN = "1:test"


def init_data(user_id=42):
    fields = {"auth_date": str(int(time.time())),
              "user": json.dumps({"id": user_id, "first_name": "Ali"}, separators=(",", ":"))}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class SpeedTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async def big(request):
            return web.json_response({"products": [{"id": i, "name": "Bodom uni 500gr"} for i in range(200)]})

        async def small(request):
            return web.json_response({"ok": True})

        app = web.Application(middlewares=[ws.auth_middleware])
        app["bot"] = None
        app["bot_token"] = TOKEN
        app.router.add_get("/api/big", big)
        app.router.add_get("/api/small", small)
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app.router.add_static("/static/", path=os.path.join(here, "webapp"), show_index=False)
        app.on_response_prepare.append(ws._static_cache_headers)
        self.patches = [patch("webapp_server.get_user_language", AsyncMock(return_value="uz")),
                        patch("webapp_server.site_gate", AsyncMock(return_value={"ok": True}))]
        for p in self.patches:
            p.start()
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        for p in self.patches:
            p.stop()

    async def get(self, path, **headers):
        return await self.client.get(path, headers={"Authorization": "tma " + init_data(), **headers},
                                     auto_decompress=False)

    async def test_mini_app_json_is_gzipped(self):
        r = await self.get("/api/big", **{"Accept-Encoding": "gzip"})
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers.get("Content-Encoding"), "gzip")
        raw = await r.read()
        import gzip
        self.assertEqual(len(json.loads(gzip.decompress(raw))["products"]), 200)
        self.assertLess(len(raw), 2000)

    async def test_small_or_not_accepted_stays_plain(self):
        r = await self.get("/api/small", **{"Accept-Encoding": "gzip"})
        self.assertIsNone(r.headers.get("Content-Encoding"))
        r = await self.get("/api/big", **{"Accept-Encoding": "identity"})
        self.assertIsNone(r.headers.get("Content-Encoding"))
        self.assertEqual(len((await r.json())["products"]), 200)

    async def test_static_cache_headers(self):
        r = await self.client.get("/static/games2.js?v=20261118")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers["Cache-Control"], "public, max-age=604800, immutable")
        r = await self.client.get("/static/leaflet.js")
        self.assertEqual(r.headers["Cache-Control"], "no-cache")
        last = r.headers.get("Last-Modified") or ""
        r = await self.client.get("/static/leaflet.js", headers={"If-Modified-Since": last})
        self.assertEqual(r.status, 304)                       # revalidated, not downloaded again
        r = await self.client.get("/static/nope.js")
        self.assertEqual(r.status, 404)
        self.assertNotIn("immutable", r.headers.get("Cache-Control", ""))


class PageTest(unittest.TestCase):
    def setUp(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.html = open(os.path.join(here, "webapp", "index.html"), encoding="utf-8").read()

    def test_leaflet_is_not_in_front_of_the_first_paint(self):
        head = self.html.split("<style>", 1)[0]
        self.assertNotIn("leaflet.js", head)
        self.assertIn("function loadLeaflet()", self.html)

    def test_game_content_is_deferred_and_versioned(self):
        self.assertIn('<script src="/static/games2_content.js?v=', self.html)
        self.assertRegex(self.html, r'games2_content\.js\?v=\d+" defer></script>')
        self.assertRegex(self.html, r'<script src="/static/games2\.js\?v=\d+"></script>')

    def test_home_page_no_longer_asks_per_category(self):
        start = self.html.index("async function renderHomePage()")
        body = self.html[start:self.html.index("function buildHomeSection(", start)]
        self.assertNotIn("categories.map(cat =>", body)
        self.assertIn("fetchCatalogList('all')", body)
        self.assertIn("Promise.allSettled", body)


if __name__ == "__main__":
    unittest.main()
