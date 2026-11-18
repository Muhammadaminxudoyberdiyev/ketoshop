"""Saytdagi fon musiqasi: qushlar (sintez) va klassik musiqa — 2026-11-15 dan
haqiqiy, erkin litsenziyali yozuvlar (site_music.py). Birdsong moduli node'da
soxta DOM, <audio> va Web Audio bilan ishga tushiriladi (tests/music_check.js) —
hech qanday ovoz chiqmaydi."""
import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import site_music  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class SiteMusicTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(ROOT / "tests" / "music_check.js")],
                             capture_output=True, text=True, check=True, cwd=ROOT).stdout
        cls.r = json.loads(out)

    def test_starts_at_once_where_the_phone_allows_it(self):
        # Egasi, 2026-11-15: "musiqa saytga kirgan zahoti boshlansin, qo'l tekkizganda emas".
        self.assertTrue(self.r["playsWithoutTap"])
        self.assertEqual(self.r["firstPiece"], "0")
        self.assertEqual(self.r["firstSrc"], "/music/moonlight.mp3")
        self.assertTrue(self.r["fadedIn"])                    # background level, faded in

    def test_waits_for_the_first_tap_where_the_phone_requires_it(self):
        self.assertTrue(self.r["waitsForTap"])
        self.assertTrue(self.r["triesBeforeTap"])
        self.assertTrue(self.r["playsAfterTap"])

    def test_iphone_volume_goes_through_web_audio(self):
        self.assertTrue(self.r["iosRouted"])
        self.assertTrue(self.r["iosPlays"])

    def test_music_comes_back_after_the_phone_stopped_it(self):
        # Egasi, 2026-11-18: "musiqa o'zidan o'zi o'chib qolyapti".
        self.assertTrue(self.r["backAfterSystemPause"])
        self.assertTrue(self.r["waitsAfterRefusal"])
        self.assertTrue(self.r["touchBringsItBack"])        # any touch, not only the first one
        self.assertTrue(self.r["retriedWithoutTouch"])      # asked again after ~10 s
        self.assertTrue(self.r["stallMovesOn"])             # a stalled download → the next piece

    def test_rests_on_the_ordering_screens(self):
        self.assertTrue(self.r["silentAtCheckout"])
        self.assertTrue(self.r["backAfterCheckout"])

    def test_off_and_on_again_moves_to_the_next_piece(self):
        self.assertTrue(self.r["silentWhenOff"])
        self.assertEqual(self.r["offToast"], "OFF")
        self.assertEqual(self.r["pieceAfterToggle"], "1")
        self.assertIn("Debyussi", self.r["onToast"])
        self.assertTrue(self.r["playingAfterToggle"])

    def test_one_piece_follows_another(self):
        self.assertTrue(self.r["autoAdvanced"])
        self.assertEqual(self.r["srcAfterEnd"], "/music/bach-prelude.mp3")

    def test_falls_back_to_wikimedia_when_our_copy_fails(self):
        self.assertEqual(self.r["srcAfterError"], "https://upload.wikimedia.org/x/bach-prelude.mp3")


class FakeContent:
    def __init__(self, data):
        self.data = data

    async def iter_chunked(self, n):
        for i in range(0, len(self.data), n):
            yield self.data[i:i + n]


class FakeResp:
    def __init__(self, status, data=b""):
        self.status, self.content = status, FakeContent(data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class FakeSession:
    def __init__(self, status=200, data=b"ID3fakeaudio"):
        self.status, self.data, self.calls = status, data, []

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, headers))
        return FakeResp(self.status, self.data)

    async def close(self):
        pass


class TracksTest(unittest.TestCase):
    def test_only_free_licences_and_wikimedia_sources(self):
        self.assertGreaterEqual(len(site_music.TRACKS), 5)
        for name, (url, uz, ru, licence) in site_music.TRACKS.items():
            self.assertTrue(url.startswith("https://upload.wikimedia.org/wikipedia/commons/"), name)
            self.assertTrue(url.endswith(".mp3"), name)
            self.assertTrue(licence.startswith(("Public domain", "CC0")), (name, licence))
            self.assertTrue(uz and ru)

    def test_playlist_for_the_page(self):
        pl = site_music.playlist()
        self.assertEqual(pl[0]["id"], "moonlight")
        self.assertIn("Бетховен", pl[0]["ru"])
        self.assertTrue(all(x["remote"].startswith("https://upload.wikimedia.org/") for x in pl))


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        for p in (patch.object(site_music, "CACHE_DIR", self.dir),
                  patch.object(site_music, "CONTACT", "https://example.org/music-contact")):
            p.start()
            self.addCleanup(p.stop)
        site_music._locks.clear()
        site_music._failed.clear()

    def test_downloads_once_then_serves_from_cache(self):
        session = FakeSession()
        path = asyncio.run(site_music.ensure("gymnopedie", session))
        self.assertEqual(path.read_bytes(), b"ID3fakeaudio")
        self.assertIn("(https://example.org/music-contact)", session.calls[0][1]["User-Agent"])
        again = asyncio.run(site_music.ensure("gymnopedie", session))
        self.assertEqual(again, path)
        self.assertEqual(len(session.calls), 1)

    def test_unknown_name_and_failed_download(self):
        self.assertIsNone(asyncio.run(site_music.ensure("../etc/passwd", FakeSession())))
        self.assertIsNone(asyncio.run(site_music.ensure("moonlight", FakeSession(status=403))))
        self.assertFalse(site_music.path_for("moonlight").exists())
        self.assertFalse(list(self.dir.glob("*.part")))
        again = FakeSession()
        self.assertIsNone(asyncio.run(site_music.ensure("moonlight", again)))     # no retry for an hour
        self.assertEqual(again.calls, [])

    def test_without_a_contact_the_server_never_calls_wikimedia(self):
        session = FakeSession()
        with patch.object(site_music, "CONTACT", ""):
            self.assertIsNone(asyncio.run(site_music.ensure("moonlight", session)))
            pl = site_music.playlist()
        self.assertEqual(session.calls, [])
        self.assertTrue(pl[0]["src"].startswith("https://upload.wikimedia.org/"))   # phones load it directly
        self.assertEqual(site_music.playlist()[0]["src"], "/music/moonlight.mp3")   # with the contact: our copy


class PageTest(unittest.TestCase):
    def test_page_reads_the_playlist_and_server_fills_it(self):
        page = (ROOT / "webapp" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="music-playlist">{{MUSIC_PLAYLIST}}</script>', page)
        self.assertIn("musicTimer = setInterval(musicTick, 500);", page)
        self.assertNotIn("function pianoNote", page)                      # no synthesised piano any more
        server = (ROOT / "webapp_server.py").read_text(encoding="utf-8")
        self.assertIn('html.replace("{{MUSIC_PLAYLIST}}", json.dumps(site_music.playlist()', server)
        self.assertIn("site_music.setup_routes(app)", server)



class BirdClipsTest(unittest.TestCase):
    """Haqiqiy qush ovozlari (egasi, 2026-11-18): seven short clips, each named,
    each credited (CC BY-SA) on the page and in webapp/birds/CREDITS.md."""

    def test_clips_names_and_credits_match(self):
        import re
        birds = ROOT / "webapp" / "birds"
        html = (ROOT / "webapp" / "index.html").read_text(encoding="utf-8")
        start = html.index("const BIRDS = [")
        ids = re.findall(r"\{ id: '([a-z]+)', uz: '[^']+'|\{ id: '([a-z]+)', uz: \"", html[start:html.index("];", start)])
        ids = [a or b for a, b in ids]
        self.assertEqual(len(ids), 7)
        credits = (birds / "CREDITS.md").read_text(encoding="utf-8")
        for bird in ids:
            clip = birds / f"{bird}.mp3"
            self.assertTrue(clip.exists(), bird)
            self.assertLess(clip.stat().st_size, 120_000, bird)          # ~11 s, fetched one at a time
            self.assertIn(f"| {bird}.mp3 |", credits)
            self.assertEqual(clip.read_bytes()[:3], b"ID3")
        self.assertIn("CC BY-SA", credits)
        self.assertIn('id="sound-credits"', html)

    def test_the_bird_waits_for_its_clip_and_falls_back_to_the_whistles(self):
        html = (ROOT / "webapp" / "index.html").read_text(encoding="utf-8")
        sing = html[html.index("  function sing() {"):html.index("  function whistle() {")]
        self.assertIn("fetchBird(b)", sing)
        self.assertIn("whistle()", sing)


if __name__ == "__main__":
    unittest.main()
