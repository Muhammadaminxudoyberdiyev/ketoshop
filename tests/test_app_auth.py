"""📱 Android ilovasi: Telegram orqali kirish va har bir so'rov imzosi (app_auth.py).

Telegram mock — hech qanday haqiqiy xabar yuborilmaydi. Bazali qism faqat
APP_AUTH_PG_DSN berilganda ishlaydi: bo'sh, sinov uchun ochilgan Postgres
(jadvallar har testda qayta yaratiladi). CI'da u qism o'tkazib yuboriladi."""
import asyncio
import os
import secrets
import time
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request
from aiogram.types import CallbackQuery, Chat, Message, User
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

import app_auth

PG_DSN = os.getenv("APP_AUTH_PG_DSN", "").strip()


class Device:
    """What the phone's Keystore does: a P-256 key that signs requests."""

    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        der = self.key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        self.public = app_auth.b64u(der)

    def sign_headers(self, method: str, target: str, body: bytes = b"",
                     ts: int | None = None, nonce: str | None = None) -> dict:
        ts = int(time.time() * 1000) if ts is None else ts
        nonce = nonce or app_auth.b64u(secrets.token_bytes(16))
        signature = self.key.sign(app_auth.canonical(method, target, ts, nonce, body),
                                  ec.ECDSA(hashes.SHA256()))
        return {app_auth.H_TS: str(ts), app_auth.H_NONCE: nonce,
                app_auth.H_SIG: app_auth.b64u(signature)}


class SignatureTest(unittest.TestCase):
    def setUp(self):
        app_auth._nonces = app_auth.NonceCache(ttl_s=240)
        self.device = Device()

    def request(self, method="POST", target="/api/cart/add?x=1", headers=None):
        return make_mocked_request(method, target, headers=headers or {})

    def test_signed_request_passes(self):
        body = b'{"product_id": 5}'
        req = self.request(headers=self.device.sign_headers("POST", "/api/cart/add?x=1", body))
        self.assertIsNone(app_auth.check_signature(req, body, self.device.public, "s1"))

    def test_same_nonce_twice_is_a_replay(self):
        headers = self.device.sign_headers("POST", "/api/cart/add?x=1", b"")
        self.assertIsNone(app_auth.check_signature(self.request(headers=headers), b"", self.device.public, "s1"))
        failure = app_auth.check_signature(self.request(headers=headers), b"", self.device.public, "s1")
        self.assertEqual(failure.status, 401)
        self.assertIn(b"replayed", failure.body)

    def test_changed_body_path_or_method_fails(self):
        headers = self.device.sign_headers("POST", "/api/cart/add?x=1", b'{"quantity": 1}')
        self.assertEqual(app_auth.check_signature(
            self.request(headers=headers), b'{"quantity": 99}', self.device.public, "s1").status, 401)
        self.assertEqual(app_auth.check_signature(
            self.request(target="/api/cart/add?x=2", headers=headers), b'{"quantity": 1}',
            self.device.public, "s1").status, 401)
        self.assertEqual(app_auth.check_signature(
            self.request(method="PUT", headers=headers), b'{"quantity": 1}', self.device.public, "s1").status, 401)

    def test_another_phones_key_fails(self):
        other = Device()
        headers = other.sign_headers("POST", "/api/cart/add?x=1", b"")
        self.assertIn(b"bad_signature",
                      app_auth.check_signature(self.request(headers=headers), b"", self.device.public, "s1").body)

    def test_old_timestamp_answers_with_server_time(self):
        headers = self.device.sign_headers("POST", "/api/cart/add?x=1", b"", ts=int(time.time() * 1000) - 600_000)
        failure = app_auth.check_signature(self.request(headers=headers), b"", self.device.public, "s1")
        self.assertEqual(failure.status, 401)
        self.assertIn(b"clock_skew", failure.body)
        self.assertIn(b"server_time", failure.body)

    def test_missing_or_malformed_headers(self):
        self.assertEqual(app_auth.check_signature(self.request(), b"", self.device.public, "s1").status, 401)
        headers = self.device.sign_headers("POST", "/api/cart/add?x=1", b"")
        headers[app_auth.H_NONCE] = "short"
        self.assertEqual(app_auth.check_signature(self.request(headers=headers), b"", self.device.public, "s1").status, 401)

    def test_nonce_is_per_signer(self):
        cache = app_auth.NonceCache(ttl_s=10)
        self.assertTrue(cache.add("s1", "n" * 22, 100.0))
        self.assertTrue(cache.add("s2", "n" * 22, 100.0))
        self.assertFalse(cache.add("s1", "n" * 22, 105.0))
        self.assertTrue(cache.add("s1", "n" * 22, 111.0))    # outside the window

    def test_only_p256_public_keys(self):
        self.assertTrue(app_auth.valid_device_key(self.device.public))
        p384 = ec.generate_private_key(ec.SECP384R1()).public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        for bad in (app_auth.b64u(p384), app_auth.b64u(rsa_key), "", "not base64!", None, 42, "A" * 90):
            self.assertFalse(app_auth.valid_device_key(bad), bad)


class HelpersTest(unittest.TestCase):
    def test_canonical_matches_the_app(self):
        # The same vector is asserted in mobile/test/signing_test.dart: the
        # phone and the server must build byte-identical strings.
        message = app_auth.canonical("POST", "/api/cart/add?x=1&q=a%20b", 1700000000000,
                                     "bm9uY2Utbm9uY2Utbm9uY2U", b'{"product_id":5,"quantity":1}')
        self.assertEqual(message.decode(), "KS1\nPOST\n/api/cart/add?x=1&q=a%20b\n1700000000000\n"
                                           "bm9uY2Utbm9uY2Utbm9uY2U\nRMefhrxnb88ZBTmmcoPHGTS_f_nUOtcsUCzo9sXAKOw")

    def test_tokens(self):
        access, refresh = app_auth.new_token("a"), app_auth.new_token("r")
        self.assertRegex(access, app_auth._TOKEN_RE)
        self.assertTrue(access.startswith("ksa_") and refresh.startswith("ksr_"))
        self.assertNotEqual(access, app_auth.new_token("a"))
        self.assertEqual(len(app_auth.token_hash(access)), 32)

    def test_rate_limit_refills(self):
        limit = app_auth.RateLimit(per_minute=60, burst=2)
        self.assertTrue(limit.allow("ip", 0.0))
        self.assertTrue(limit.allow("ip", 0.0))
        self.assertFalse(limit.allow("ip", 0.1))
        self.assertTrue(limit.allow("other", 0.1))
        self.assertTrue(limit.allow("ip", 1.2))

    def test_device_name_is_cleaned(self):
        self.assertEqual(app_auth.clean_device_name("Pixel‮ 8\x00\n"), "Pixel 8")
        self.assertEqual(app_auth.clean_device_name(""), "Android")
        self.assertEqual(len(app_auth.clean_device_name("x" * 500)), 60)

    def test_env_flags(self):
        self.assertEqual(app_auth.clean_env({"rooted": 1, "evil": True, "hooked": 0}),
                         {"rooted": True, "hooked": False})
        self.assertFalse(app_auth.env_is_dirty({"rooted": True}))
        self.assertTrue(app_auth.env_is_dirty({"tampered": True}))
        self.assertEqual(app_auth.clean_env("junk"), {})

    def test_texts_in_every_language(self):
        for key in app_auth._TEXTS["uz"]:
            self.assertIn(key, app_auth._TEXTS["ru"])
        cyr = app_auth.text("approved", "uz_cyr")
        self.assertTrue(any("Ѐ" <= ch <= "ӿ" for ch in cyr), cyr)
        self.assertIn("&lt;b&gt;", app_auth.text("confirm", "uz", device="&lt;b&gt;"))

    def test_login_events_skip_the_channel_gate(self):
        user = User(id=1, is_bot=False, first_name="A")
        chat = Chat(id=1, type="private")

        def msg(text):
            return Message(message_id=1, date=datetime.now(), chat=chat, from_user=user, text=text)

        self.assertTrue(app_auth.is_app_login_event(msg("/start applogin_" + "a" * 22)))
        self.assertFalse(app_auth.is_app_login_event(msg("/start sayt")))
        cb = CallbackQuery(id="1", from_user=user, chat_instance="c", data="applogin:x:12")
        self.assertTrue(app_auth.is_app_login_event(cb))
        self.assertFalse(app_auth.is_app_login_event(
            CallbackQuery(id="1", from_user=user, chat_instance="c", data="main_menu")))

    def test_cheque_from_raw_body(self):
        import webapp_server as ws
        req = make_mocked_request("POST", "/api/checkout/cheque",
                                  headers={"Content-Type": "image/jpeg", "X-File-Name": "../../chek 1.jpg"})
        req["raw_body"] = b"\xff\xd8jpeg"
        data, ctype, name = asyncio.run(ws._read_cheque_upload(req))
        self.assertEqual((data, ctype, name), (b"\xff\xd8jpeg", "image/jpeg", "....chek1.jpg"))
        req["raw_body"] = b""
        self.assertEqual(asyncio.run(ws._read_cheque_upload(req))["error"], "empty_file")


@unittest.skipUnless(PG_DSN, "APP_AUTH_PG_DSN not set — database flow skipped")
class LoginFlowTest(unittest.IsolatedAsyncioTestCase):
    USER = 777_000_111

    async def asyncSetUp(self):
        import asyncpg
        import database
        import webapp_server as ws
        self._old_pool = database.pool
        self.pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=4)
        database.pool = self.pool
        async with self.pool.acquire() as conn:
            await conn.execute("DROP TABLE IF EXISTS app_sessions, app_login_requests")
        app_auth._ready = False
        await app_auth.ensure_schema()
        app_auth._nonces = app_auth.NonceCache(ttl_s=240)
        app_auth._start_per_ip = app_auth.RateLimit(per_minute=6000, burst=1000)
        app_auth._refresh_per_session = app_auth.RateLimit(per_minute=6000, burst=1000)

        async def echo(request):
            # Like the real handlers: request.json() after app_auth already
            # read the body for its signature (aiohttp keeps it).
            body = await request.json() if request.method == "POST" else None
            return web.json_response({"user_id": request["user_id"],
                                      "name": request["telegram_user"].get("first_name"),
                                      "json": body, "pad": "x" * 2000})

        async def upload(request):
            return web.json_response({"size": len(request["raw_body"])})

        app = web.Application(middlewares=[ws.auth_middleware])
        app["bot"] = None
        app["bot_token"] = "1:test"
        app_auth.add_routes(app)
        app.router.add_get("/api/echo", echo)
        app.router.add_post("/api/echo", echo)
        app.router.add_post("/api/upload", upload)
        self.patches = [patch("webapp_server.get_user_language", AsyncMock(return_value="uz")),
                        patch("webapp_server.site_gate", AsyncMock(return_value={"ok": True}))]
        for p in self.patches:
            p.start()
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        import database
        await self.client.close()
        for p in self.patches:
            p.stop()
        await self.pool.close()
        database.pool = self._old_pool

    async def call(self, method, path, device, payload=None, token=None, raw=None, ctype=None, headers=None):
        import json
        body = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else b"")
        sent = dict(headers) if headers is not None else device.sign_headers(method, path, body)
        if body:
            sent["Content-Type"] = ctype or "application/json"
        if token:
            sent["Authorization"] = f"Bearer {token}"
        return await self.client.request(method, path, data=body or None, headers=sent)

    async def start_login(self, device):
        r = await self.call("POST", "/app/v1/auth/start", device,
                            {"device_key": device.public, "device_name": "Pixel 8", "env": {"rooted": False}})
        self.assertEqual(r.status, 200, await r.text())
        return await r.json()

    async def choose(self, login_id, number, user_id=None):
        tg = SimpleNamespace(id=user_id or self.USER, first_name="Ali", last_name="Valiyev",
                             username="ali", language_code="uz")
        cb = SimpleNamespace(data=f"applogin:{login_id}:{number}", from_user=tg, answer=AsyncMock(),
                             message=SimpleNamespace(edit_text=AsyncMock()), bot=AsyncMock())
        with patch("handlers.start.ensure_registered", AsyncMock()) as registered, \
                patch("app_auth._buyer_lang", AsyncMock(return_value="uz")):
            await app_auth.on_login_choice(cb)
        return cb, registered

    async def poll(self, device, login_id):
        return await self.call("POST", "/app/v1/auth/poll", device, {"request_id": login_id})

    async def login(self, device, user_id=None):
        start = await self.start_login(device)
        await self.choose(start["request_id"], start["match_code"], user_id)
        r = await self.poll(device, start["request_id"])
        self.assertEqual(r.status, 200, await r.text())
        return await r.json()

    async def test_login_then_signed_api_call(self):
        device = Device()
        start = await self.start_login(device)
        self.assertTrue(start["bot_url"].endswith("?start=applogin_" + start["request_id"]))
        self.assertTrue(10 <= start["match_code"] <= 99)
        self.assertEqual((await self.poll(device, start["request_id"])).status, 202)

        cb, registered = await self.choose(start["request_id"], start["match_code"])
        registered.assert_awaited_once()
        self.assertIn("Tasdiqlandi", cb.message.edit_text.await_args.args[0])

        r = await self.poll(device, start["request_id"])
        tokens = await r.json()
        self.assertEqual(tokens["user"], {"id": self.USER, "first_name": "Ali"})
        # The login is single use.
        self.assertEqual((await self.poll(device, start["request_id"])).status, 410)

        r = await self.call("GET", "/api/echo?q=a%20b&n=1", device, token=tokens["access_token"],
                            headers=None)
        self.assertEqual(r.status, 200, await r.text())
        self.assertEqual((await r.json())["user_id"], self.USER)
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        self.assertEqual(r.headers.get("Content-Encoding"), "gzip")

        r = await self.call("POST", "/api/echo", device, {"product_id": 3}, token=tokens["access_token"])
        self.assertEqual((await r.json())["json"], {"product_id": 3})

    async def test_wrong_number_kills_the_login(self):
        device = Device()
        start = await self.start_login(device)
        wrong = 10 if start["match_code"] != 10 else 11
        cb, registered = await self.choose(start["request_id"], wrong)
        registered.assert_not_awaited()
        self.assertIn("mos kelmadi", cb.message.edit_text.await_args.args[0])
        r = await self.poll(device, start["request_id"])
        self.assertEqual((r.status, (await r.json())["status"]), (410, "rejected"))
        # The right number afterwards no longer helps.
        cb, _ = await self.choose(start["request_id"], start["match_code"])
        self.assertIn("eskirgan", cb.message.edit_text.await_args.args[0])

    async def test_not_me_button(self):
        device = Device()
        start = await self.start_login(device)
        cb, _ = await self.choose(start["request_id"], 0)
        self.assertIn("bekor qilindi", cb.message.edit_text.await_args.args[0])
        self.assertEqual((await self.poll(device, start["request_id"])).status, 410)

    async def test_another_phone_cannot_collect_the_session(self):
        device, thief = Device(), Device()
        start = await self.start_login(device)
        await self.choose(start["request_id"], start["match_code"])
        r = await self.poll(thief, start["request_id"])
        self.assertEqual(r.status, 401)
        self.assertEqual((await self.poll(device, start["request_id"])).status, 200)

    async def test_stolen_token_is_useless_without_the_phone(self):
        device, thief = Device(), Device()
        tokens = await self.login(device)
        r = await self.call("GET", "/api/echo", thief, token=tokens["access_token"])
        self.assertEqual(r.status, 401)
        r = await self.call("POST", "/app/v1/auth/refresh", thief, {"refresh_token": tokens["refresh_token"]})
        self.assertEqual(r.status, 401)

    async def test_replay_and_tampering(self):
        device = Device()
        tokens = await self.login(device)
        headers = device.sign_headers("POST", "/api/echo", b'{"quantity": 1}')
        ok = await self.call("POST", "/api/echo", device, raw=b'{"quantity": 1}', token=tokens["access_token"],
                             headers=headers)
        self.assertEqual(ok.status, 200)
        again = await self.call("POST", "/api/echo", device, raw=b'{"quantity": 1}', token=tokens["access_token"],
                                headers=headers)
        self.assertEqual((again.status, (await again.json())["error"]), (401, "replayed"))
        headers = device.sign_headers("POST", "/api/echo", b'{"quantity": 1}')
        forged = await self.call("POST", "/api/echo", device, raw=b'{"quantity": 50}', token=tokens["access_token"],
                                 headers=headers)
        self.assertEqual((forged.status, (await forged.json())["error"]), (401, "bad_signature"))
        unsigned = await self.client.get("/api/echo", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        self.assertEqual(unsigned.status, 401)

    async def test_refresh_rotates_and_detects_reuse(self):
        device = Device()
        first = await self.login(device)
        r = await self.call("POST", "/app/v1/auth/refresh", device, {"refresh_token": first["refresh_token"]})
        second = await r.json()
        self.assertEqual(r.status, 200, second)
        self.assertEqual((await self.call("GET", "/api/echo", device, token=first["access_token"])).status, 401)
        self.assertEqual((await self.call("GET", "/api/echo", device, token=second["access_token"])).status, 200)

        # The reply got lost: the phone retries with the old refresh token.
        r = await self.call("POST", "/app/v1/auth/refresh", device, {"refresh_token": first["refresh_token"]})
        third = await r.json()
        self.assertEqual(r.status, 200, third)

        # Long after rotation an old token means a copy exists: session ends.
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE app_sessions SET rotated_at = now() - interval '10 minutes'")
        r = await self.call("POST", "/app/v1/auth/refresh", device, {"refresh_token": second["refresh_token"]})
        self.assertEqual(r.status, 401)
        self.assertEqual((await self.call("GET", "/api/echo", device, token=third["access_token"])).status, 401)

    async def test_expired_access_token(self):
        device = Device()
        tokens = await self.login(device)
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE app_sessions SET access_expires = now() - interval '1 second'")
        r = await self.call("GET", "/api/echo", device, token=tokens["access_token"])
        self.assertEqual((r.status, (await r.json())["error"]), (401, "token_expired"))

    async def test_logout_and_other_devices(self):
        phone, tablet = Device(), Device()
        a = await self.login(phone)
        b = await self.login(tablet)
        r = await self.call("GET", "/app/v1/sessions", phone, token=a["access_token"])
        sessions = (await r.json())["sessions"]
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sum(s["current"] for s in sessions), 1)
        r = await self.call("POST", "/app/v1/sessions/revoke-others", phone, token=a["access_token"])
        self.assertEqual((await r.json())["revoked"], 1)
        self.assertEqual((await self.call("GET", "/api/echo", tablet, token=b["access_token"])).status, 401)
        self.assertEqual((await self.call("POST", "/app/v1/auth/logout", phone, token=a["access_token"])).status, 200)
        self.assertEqual((await self.call("GET", "/api/echo", phone, token=a["access_token"])).status, 401)

    async def test_session_cap_drops_the_oldest(self):
        device = Device()
        logins = [await self.login(device) for _ in range(app_auth.MAX_SESSIONS_PER_USER + 1)]
        self.assertEqual((await self.call("GET", "/api/echo", device, token=logins[0]["access_token"])).status, 401)
        self.assertEqual((await self.call("GET", "/api/echo", device, token=logins[-1]["access_token"])).status, 200)

    async def test_kick_button_only_for_the_owner(self):
        device = Device()
        tokens = await self.login(device)
        async with self.pool.acquire() as conn:
            session_id = await conn.fetchval("SELECT id FROM app_sessions")

        def press(user_id):
            return SimpleNamespace(data=f"appsess:off:{session_id}", answer=AsyncMock(),
                                   from_user=SimpleNamespace(id=user_id, language_code="uz"),
                                   message=SimpleNamespace(edit_reply_markup=AsyncMock()))

        with patch("app_auth._buyer_lang", AsyncMock(return_value="uz")):
            await app_auth.on_kick_device(press(self.USER + 1))
            self.assertEqual((await self.call("GET", "/api/echo", device, token=tokens["access_token"])).status, 200)
            await app_auth.on_kick_device(press(self.USER))
        self.assertEqual((await self.call("GET", "/api/echo", device, token=tokens["access_token"])).status, 401)

    async def test_cheque_upload_body(self):
        device = Device()
        tokens = await self.login(device)
        photo = secrets.token_bytes(300_000)
        r = await self.call("POST", "/api/upload", device, raw=photo, ctype="image/jpeg", token=tokens["access_token"])
        self.assertEqual((await r.json())["size"], len(photo))
        big = b"\0" * (app_auth.MAX_UPLOAD + 1)
        import warnings
        warnings.simplefilter("ignore", ResourceWarning)
        r = await self.call("POST", "/api/upload", device, raw=big, ctype="image/jpeg", token=tokens["access_token"])
        self.assertEqual(r.status, 413)

    async def test_bad_start_requests(self):
        device = Device()
        r = await self.call("POST", "/app/v1/auth/start", device, {"device_key": "nope"})
        self.assertEqual(r.status, 400)
        other = Device()
        payload = {"device_key": device.public}
        import json
        body = json.dumps(payload).encode()
        r = await self.call("POST", "/app/v1/auth/start", device, raw=body,
                            headers=other.sign_headers("POST", "/app/v1/auth/start", body))
        self.assertEqual(r.status, 401)


class CartRemoveOwnershipTest(unittest.IsolatedAsyncioTestCase):
    """Cart ids are sequential: /api/cart/remove must only touch the
    caller's own line (it used to delete any id it was given)."""

    class Req(dict):
        def __init__(self, user_id, cart_id):
            super().__init__(user_id=user_id)
            self._cart_id = cart_id

        async def json(self):
            return {"cart_id": self._cart_id}

    async def test_someone_elses_line_is_not_found(self):
        import webapp_server as ws
        with patch("webapp_server.get_cart_item", AsyncMock(return_value={"user_id": 2})), \
                patch("webapp_server.remove_from_cart", AsyncMock()) as removed:
            response = await ws.api_cart_remove(self.Req(user_id=1, cart_id=9))
        self.assertEqual(response.status, 404)
        removed.assert_not_awaited()

    async def test_own_line_is_removed(self):
        import webapp_server as ws
        with patch("webapp_server.get_cart_item", AsyncMock(return_value={"user_id": 1})), \
                patch("webapp_server.remove_from_cart", AsyncMock()) as removed:
            response = await ws.api_cart_remove(self.Req(user_id=1, cart_id=9))
        self.assertEqual(response.status, 200)
        removed.assert_awaited_once_with(9)


class LoginLinkTest(unittest.IsolatedAsyncioTestCase):
    async def test_three_numbers_one_right(self):
        conn = SimpleNamespace(fetchrow=AsyncMock(return_value={"device_name": "<Pixel>", "match_code": 42}))

        class Acquire:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        message = SimpleNamespace(from_user=SimpleNamespace(id=5, language_code="ru"), answer=AsyncMock())
        command = SimpleNamespace(args="applogin_" + "a" * 22)
        with patch("app_auth.ensure_schema", AsyncMock()), \
                patch("app_auth._buyer_lang", AsyncMock(return_value="ru")), \
                patch("database.pool", SimpleNamespace(acquire=lambda: Acquire())):
            await app_auth.on_login_link(message, command)
        text_sent = message.answer.await_args.args[0]
        self.assertIn("&lt;Pixel&gt;", text_sent)
        rows = message.answer.await_args.kwargs["reply_markup"].inline_keyboard
        numbers = [b.text for b in rows[0]]
        self.assertEqual(len(set(numbers)), 3)
        self.assertIn("42", numbers)
        self.assertTrue(rows[1][0].callback_data.endswith(":0"))


if __name__ == "__main__":
    unittest.main()
