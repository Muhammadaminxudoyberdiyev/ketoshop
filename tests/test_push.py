"""📲 Push (push.py) and the app's own updates (app_release.py, app_config)."""
import asyncio
import base64
import io
import json
import os
import unittest
import zipfile
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import app_config
import app_release
import push


def _service_account() -> dict:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    return {"type": "service_account", "project_id": "ketoshop-test", "private_key": pem,
            "client_email": "fcm@ketoshop-test.iam.gserviceaccount.com",
            "token_uri": "https://oauth2.googleapis.com/token"}, key


class KeyTest(unittest.TestCase):
    def test_accepts_raw_and_base64(self):
        sa, _ = _service_account()
        raw = json.dumps(sa)
        self.assertEqual(push.parse_service_account(raw)["project_id"], "ketoshop-test")
        self.assertEqual(push.parse_service_account(base64.b64encode(raw.encode()).decode())["project_id"],
                         "ketoshop-test")

    def test_rejects_the_wrong_file(self):
        with self.assertRaisesRegex(ValueError, "service account"):
            push.parse_service_account(json.dumps({"project_info": {"project_id": "x"}}))  # google-services.json
        with self.assertRaises(ValueError):
            push.parse_service_account("not json")
        sa, _ = _service_account()
        with self.assertRaisesRegex(ValueError, "private_key"):
            push.parse_service_account(json.dumps(dict(sa, private_key="-----BEGIN PRIVATE KEY-----\nxx\n")))

    def test_assertion_is_a_valid_rs256_jwt(self):
        sa, key = _service_account()
        jwt = push.make_assertion(sa, now=1_800_000_000)
        header, claims, sig = jwt.split(".")
        pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
        body = json.loads(base64.urlsafe_b64decode(pad(claims)))
        self.assertEqual((body["iss"], body["aud"], body["exp"] - body["iat"]),
                         (sa["client_email"], sa["token_uri"], 3600))
        self.assertIn("firebase.messaging", body["scope"])
        key.public_key().verify(base64.urlsafe_b64decode(pad(sig)), f"{header}.{claims}".encode(),
                                padding.PKCS1v15(), hashes.SHA256())


class MessageTest(unittest.TestCase):
    def setUp(self):
        patcher = patch("config.WEBAPP_URL", "https://keto.example.uz")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_urls_stay_on_our_site(self):
        self.assertEqual(push.clean_url("/?product=12"), "/?product=12")
        self.assertEqual(push.clean_url("https://keto.example.uz/?game=quiz"), "/?game=quiz")
        for bad in ("https://evil.example/x", "//evil.example", "javascript:alert(1)", "/a b"):
            self.assertEqual(push.clean_url(bad), "", bad)

    def test_images_only_from_our_host(self):
        self.assertEqual(push.clean_image("/img/7"), "https://keto.example.uz/img/7")
        self.assertEqual(push.clean_image("https://keto.example.uz/img/7"), "https://keto.example.uz/img/7")
        self.assertEqual(push.clean_image("https://evil.example/x.png"), "")
        self.assertEqual(push.clean_image("//evil.example/x.png"), "")

    def test_data_message(self):
        texts = push.Texts({"uz": "Yangi mahsulot: Shirinlik", "ru": "Новинка"}, {"uz": "Bosing", "ru": "Нажмите"})
        with patch("alphabet.is_on", return_value=False):
            uz = push.build_data("yangi_mahsulot", "uz", texts, "/?product=3", "/img/2", 9, 42)
            cyr = push.build_data("yangi_mahsulot", "uz_cyr", texts, "/?product=3", "", 9, 42)
            ru = push.build_data("nomalum", "ru", texts, "", "", 9, 42)
        self.assertTrue(all(isinstance(v, str) for v in uz.values()))
        self.assertEqual((uz["ch"], uz["ch_name"], uz["url"], uz["image"], uz["uid"]),
                         ("yangi_mahsulot", "Yangi mahsulotlar", "/?product=3", "https://keto.example.uz/img/2", "42"))
        self.assertTrue(any("Ѐ" <= c <= "ӿ" for c in cyr["title"]))
        self.assertEqual((ru["title"], ru["ch"], ru["ch_name"]), ("Новинка", push.DEFAULT_KIND, "Новости"))

    def test_new_alphabet_for_latin_readers(self):
        texts = push.Texts({"uz": "Shirinlik"}, {"uz": "Ko'rish"})
        with patch("alphabet.is_on", return_value=True):
            data = push.build_data("aksiya", "uz", texts, "", "", 1, 1)
        self.assertEqual(data["title"], "Şirinlik")


class BroadcastTest(unittest.IsolatedAsyncioTestCase):
    async def test_dead_tokens_are_forgotten_and_counts_add_up(self):
        sa, _ = _service_account()
        results = {"tok-ok-aaaaaaaaaaaaaaaaaaaa": "ok", "tok-gone-aaaaaaaaaaaaaaaaaa": "gone",
                   "tok-err-aaaaaaaaaaaaaaaaaaa": "error"}

        class Conn:
            def __init__(self):
                self.calls = []

            async def execute(self, sql, *args):
                self.calls.append((sql, args))

            async def fetchval(self, *a):
                return 1

        conn = Conn()

        class Pool:
            def acquire(self):
                class Ctx:
                    async def __aenter__(self_):
                        return conn

                    async def __aexit__(self_, *a):
                        return False
                return Ctx()

        sent = []

        async def fake_send(_sa, token, data):
            sent.append(data["uid"])
            return results[token]

        with patch.object(push, "_service_account", AsyncMock(return_value=sa)), \
                patch.object(push, "ensure_schema", AsyncMock()), \
                patch.object(push, "_tokens", AsyncMock(return_value={1: ["tok-ok-aaaaaaaaaaaaaaaaaaaa"],
                                                                      2: ["tok-gone-aaaaaaaaaaaaaaaaaa"],
                                                                      3: ["tok-err-aaaaaaaaaaaaaaaaaaa"]})), \
                patch.object(push, "_send", fake_send), \
                patch("database.pool", Pool(), create=True), \
                patch("database.get_user_languages", AsyncMock(return_value={1: "ru"})), \
                patch("config.WEBAPP_URL", "https://keto.example.uz"):
            result = await push.broadcast([1, 2, 3], "aksiya", push.Texts({"uz": "A"}, {"uz": "B"}), log=False)
        self.assertEqual((result["users"], result["sent"], result["failed"], result["reached"]), (1, 1, 2, {1}))
        forgot = [args for sql, args in conn.calls if "DELETE FROM app_push_devices" in sql]
        self.assertEqual(forgot, [(["tok-gone-aaaaaaaaaaaaaaaaaa"],)])
        self.assertEqual(sorted(sent), ["1", "2", "3"])

    async def test_without_a_key_nothing_is_sent(self):
        with patch.object(push, "_service_account", AsyncMock(return_value=None)):
            self.assertFalse(await push.deliver(1, "aksiya", push.Texts({"uz": "A"}, {"uz": "B"})))
            self.assertEqual(await push.app_user_ids([1, 2]), set())


def _apk() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("AndroidManifest.xml", b"\x03\x00")
        z.writestr("classes.dex", b"dex\n035")
    return buf.getvalue()


class ReleaseTest(unittest.TestCase):
    def test_apk_check(self):
        app_release.check_apk(_apk())
        for bad in (b"", b"not a zip", b"PK\x05\x06" + b"\0" * 18):
            with self.assertRaises(ValueError):
                app_release.check_apk(bad)

    def test_config_announces_the_uploaded_apk(self):
        release = {"build": 7, "version": "1.4.0", "sha256": "ab" * 32, "size": 1234,
                   "notes_uz": "Yangi o'yinlar", "notes_ru": "Новые игры", "min_build": 5}
        with patch("config.WEBAPP_URL", "https://keto.example.uz"):
            data = app_config.build("uz_cyr", release)
            plain = app_config.build("uz", None)
        self.assertEqual((data["latest_build"], data["latest_version"], data["min_build"]), (7, "1.4.0", 5))
        self.assertEqual(data["update_url"], "https://keto.example.uz/app/download/ketoshop-7.apk")
        self.assertEqual((data["apk_sha256"], data["apk_size"]), ("ab" * 32, 1234))
        self.assertTrue(any("Ѐ" <= c <= "ӿ" for c in data["update_notes"]))
        self.assertEqual((plain["apk_sha256"], plain["shim_path"]), ("", "/app/v1/shim.js"))

    def test_shim_is_served(self):
        from aiohttp.test_utils import make_mocked_request
        response = asyncio.run(app_config.handle_shim(make_mocked_request("GET", "/app/v1/shim.js")))
        self.assertIn(b"__KS_BOOT", response.body)
        self.assertEqual(response.content_type, "application/javascript")


if __name__ == "__main__":
    unittest.main()
