"""Saytda faol vaqt uchun Keto (egasi, 2026-11-15: "saytda qancha ko'p vaqt
o'tkazsa, shuncha ko'p Keto tanga berilsin"; "firibgarlik va sun'iy
qurilmalar ishlamasin — saytdan haqiqiy odam foydalanayotgan bo'lsin").

No database and no Telegram: the site_time row, the ledger and the switches
are in-memory fakes; credit_keto's unique index is a set."""
import asyncio
import json
import os
import shutil
import subprocess
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://unused/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

from aiohttp.test_utils import make_mocked_request

import database
import gamification
import keyboards
import site_time as st
import webapp_server

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "webapp" / "index.html").read_text(encoding="utf-8")
T0 = datetime(2026, 11, 15, 6, 0)     # 11:00 Tashkent
USER = 777001


class FixedRng:
    """randint → the low end, so the presence check comes after exactly 20 min."""
    def randint(self, a, b):
        return a


def beat(n=3, gaps=(800, 1500), sid="sess0001"):
    return {"sid": sid, "n": n, "gaps": list(gaps)}


def fresh():
    return {"active_seconds": 0, "paid_through": -1, "last_beat_at": None, "day_date": None,
            "day_seconds": 0, "check_at": None, "check_token": None, "check_issued_at": None,
            "pattern": None, "pattern_seconds": 0, "flagged_sid": None, "flags": 0, "flagged_at": None}


class LadderTest(unittest.TestCase):
    def total(self, seconds):
        return sum(a for _, a, _ in st.milestones_up_to(seconds))

    def test_owner_totals(self):
        # The owner's cumulative totals, plus the 5 Keto of the first visit.
        cases = {60: 10, 600: 60, 1800: 160, 3600: 360, 2 * 3600: 610, 3 * 3600: 910,
                 10 * 3600: 4410, 11 * 3600: 4910, 20 * 3600: 9410}
        for seconds, expected in cases.items():
            self.assertEqual(self.total(seconds) - 5, expected, seconds)
        self.assertEqual(self.total(0), 5)          # the first visit alone
        self.assertEqual(self.total(59), 5)

    def test_hours_three_to_ten_grow_by_fifty(self):
        steps = dict((s, a) for s, a, _ in st.milestones_up_to(10 * 3600))
        for h in range(4, 11):
            self.assertEqual(steps[h * 3600] - steps[(h - 1) * 3600], 50, h)
        self.assertEqual([a for s, a, _ in st.milestones_up_to(13 * 3600) if s > 10 * 3600], [500, 500, 500])

    def test_keys_are_unique(self):
        keys = [k for _, _, k in st.milestones_up_to(30 * 3600)]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(keys[:3], ["site_time:0", "site_time:60", "site_time:600"])

    def test_next(self):
        self.assertEqual(st.next_milestone(0), {"seconds": 60, "amount": 10, "left": 60})
        self.assertEqual(st.next_milestone(61), {"seconds": 600, "amount": 50, "left": 539})
        self.assertEqual(st.next_milestone(10 * 3600)["seconds"], 11 * 3600)
        self.assertEqual(st.next_milestone(11 * 3600 + 5), {"seconds": 12 * 3600, "amount": 500, "left": 3595})


class ParseTest(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(st.parse_beat({"sid": "abcd", "n": 2, "gaps": [5, 6.4]}), {"sid": "abcd", "n": 2, "gaps": [5, 6]})
        for bad in (None, [], {"n": 1}, {"sid": "ab", "n": 1}, {"sid": "abcd", "n": True},
                    {"sid": "abcd", "n": -1}, {"sid": "abcd", "n": 1, "gaps": "1,2"},
                    {"sid": "abcd", "n": 1, "gaps": [-5]}, {"sid": "abcd", "n": 1, "gaps": [True]}):
            self.assertIsNone(st.parse_beat(bad), bad)
        long = st.parse_beat({"sid": "abcd", "n": 99, "gaps": list(range(100))})
        self.assertEqual(len(long["gaps"]), st.MAX_GAPS)


class AccrueTest(unittest.TestCase):
    def setUp(self):
        self.s = fresh()
        self.rng = FixedRng()

    def go(self, at, b=None):
        return st.accrue(self.s, b or beat(), at, self.rng)

    def test_first_beat_has_no_previous_one(self):
        out = self.go(T0, beat(n=0, gaps=()))
        self.assertEqual((out["credited"], out["reason"]), (0, "idle"))
        self.assertEqual(self.s["last_beat_at"], T0)
        self.assertEqual(self.s["check_at"], 20 * 60)

    def test_wall_clock_and_per_beat_caps(self):
        self.go(T0, beat(n=0, gaps=()))
        self.assertEqual(self.go(T0 + timedelta(seconds=60))["credited"], 60)
        self.assertEqual(self.go(T0 + timedelta(seconds=90), beat(gaps=(700, 2100)))["credited"], 30)
        self.assertEqual(self.go(T0 + timedelta(minutes=30), beat(gaps=(400,)))["credited"], 60)   # never more than a minute
        self.assertEqual(self.s["active_seconds"], 150)

    def test_beats_too_close_are_ignored(self):
        self.go(T0, beat(n=0, gaps=()))
        self.go(T0 + timedelta(seconds=60))
        out = self.go(T0 + timedelta(seconds=65))
        self.assertEqual((out["credited"], out["reason"]), (0, "too_soon"))
        self.assertEqual(self.s["last_beat_at"], T0 + timedelta(seconds=60))     # the clock didn't move

    def test_minute_without_interaction_earns_nothing(self):
        self.go(T0, beat(n=0, gaps=()))
        out = self.go(T0 + timedelta(seconds=60), beat(n=0, gaps=()))
        self.assertEqual((out["credited"], out["reason"]), (0, "idle"))
        self.assertEqual(self.s["last_beat_at"], T0 + timedelta(seconds=60))

    def test_daily_cap_in_tashkent_days(self):
        self.s.update(last_beat_at=T0, day_date=(T0 + st.TZ_OFFSET).date(), day_seconds=st.DAILY_CAP - 20,
                      check_at=10 ** 9)
        self.assertEqual(self.go(T0 + timedelta(seconds=60))["credited"], 20)
        out = self.go(T0 + timedelta(seconds=120), beat(gaps=(900,)))
        self.assertEqual((out["credited"], out["reason"]), (0, "daily_cap"))
        # 19:00 UTC is midnight in Tashkent: a new day, a new 8 hours.
        late = datetime(2026, 11, 15, 18, 59)
        self.s["last_beat_at"] = late - timedelta(seconds=60)
        self.assertEqual(self.go(late, beat(gaps=(1100,)))["credited"], 0)
        self.assertEqual(self.go(late + timedelta(seconds=60), beat(gaps=(1300,)))["credited"], 60)
        self.assertEqual(self.s["day_date"], datetime(2026, 11, 16).date())
        self.assertEqual(self.s["day_seconds"], 60)

    def test_presence_check_pauses_until_a_real_answer(self):
        self.go(T0, beat(n=0, gaps=()))
        at = T0
        for i in range(20):                                   # 20 credited minutes
            at += timedelta(seconds=60)
            self.go(at, beat(gaps=(500 + i * 37, 1200 + i)))
        self.assertEqual(self.s["active_seconds"], 20 * 60)
        token = self.s["check_token"]
        self.assertTrue(token)
        out = self.go(at + timedelta(seconds=60), beat(gaps=(999,)))
        self.assertEqual((out["credited"], out["reason"]), (0, "check"))
        self.assertFalse(st.confirm_presence(self.s, "wrong", at + timedelta(seconds=61), self.rng))
        self.assertFalse(st.confirm_presence(self.s, token, self.s["check_issued_at"] + timedelta(seconds=0.1), self.rng))
        self.assertTrue(st.confirm_presence(self.s, token, at + timedelta(seconds=65), self.rng))
        self.assertIsNone(self.s["check_token"])
        self.assertEqual(self.s["check_at"], 40 * 60)        # next one after another 20 credited min
        self.assertEqual(self.go(at + timedelta(seconds=125), beat(gaps=(1234,)))["credited"], 60)

    def test_identical_pattern_for_half_an_hour_stops_the_session(self):
        self.s["check_at"] = 10 ** 9
        self.go(T0, beat(n=0, gaps=()))
        at, credited, flagged_at = T0, 0, None
        for i in range(40):
            at += timedelta(seconds=60)
            jitter = (i % 3) * 7                              # a timer's few-ms wobble
            out = self.go(at, beat(n=4, gaps=(2000 + jitter, 2000, 2000 - jitter)))
            credited += out["credited"]
            if out["flagged"]:
                flagged_at = i
        self.assertEqual(flagged_at, 30)                      # 30 identical minutes after the first
        self.assertEqual(credited, 30 * 60)                   # what a script gets before it is stopped
        self.assertEqual((self.s["flags"], self.s["flagged_sid"]), (1, "sess0001"))
        self.assertIsNotNone(self.s["flagged_at"])
        out = self.go(at + timedelta(seconds=60), beat(n=7, gaps=(300, 900)))
        self.assertEqual((out["credited"], out["reason"]), (0, "flagged"))     # that session earns no more
        out = self.go(at + timedelta(seconds=120), beat(n=7, gaps=(310, 880), sid="sess0002"))
        self.assertEqual(out["credited"], 60)

    def test_a_person_is_not_a_pattern(self):
        self.s["check_at"] = 10 ** 9
        self.go(T0, beat(n=0, gaps=()))
        at = T0
        for i in range(120):
            at += timedelta(seconds=60)
            out = self.go(at, beat(n=1 + i % 5, gaps=[700 + (i * 389) % 4000] * (i % 5)))
            self.assertFalse(out["flagged"])
        self.assertEqual(self.s["active_seconds"], 120 * 60)

    def test_same_pattern(self):
        self.assertTrue(st.same_pattern("3|1000,2000", "3|1100,2030"))
        self.assertFalse(st.same_pattern("3|1000,2000", "3|1000,2300"))
        self.assertFalse(st.same_pattern("3|1000,2000", "2|1000,2000"))
        self.assertFalse(st.same_pattern("3|1000,2000", "3|1000"))
        self.assertFalse(st.same_pattern(None, "1|"))


class FakeDb:
    """site_time rows, keto_ledger's unique (user, note) and the switches."""
    def __init__(self, enabled=True, site_enabled=True):
        self.rows, self.ledger, self.balance = {}, {}, {}
        self.state = {"enabled": enabled, "redemption_enabled": True, "site_time_enabled": site_enabled}
        self.fail_credit = False
        self.calls = 0

    async def update_site_time(self, user_id, change):
        self.calls += 1
        row = self.rows.setdefault(user_id, fresh())
        state = dict(row)
        result = change(state)
        row.update({k: v for k, v in state.items() if k != "paid_through"})
        return result, state

    async def set_site_time_paid_through(self, user_id, seconds):
        row = self.rows[user_id]
        row["paid_through"] = max(row["paid_through"], seconds)

    async def credit_keto(self, user_id, order_id, amount, kind, note=None):
        if self.fail_credit:
            raise RuntimeError("db down")
        if (user_id, kind, note) in self.ledger:
            return False
        self.ledger[(user_id, kind, note)] = amount
        self.balance[user_id] = self.balance.get(user_id, 0) + amount
        return True

    async def get_user(self, user_id):
        return {"user_id": user_id, "keto_balance": self.balance.get(user_id, 0)}

    async def get_gamification_state(self):
        return dict(self.state)

    def patches(self):
        return [patch.object(database, name, getattr(self, name)) for name in
                ("update_site_time", "set_site_time_paid_through", "credit_keto", "get_user", "get_gamification_state")] + [
            patch.object(gamification, "buyer_rate", AsyncMock(return_value=0.005)),
            patch.object(gamification, "is_redemption_enabled", AsyncMock(return_value=True)),
            patch.object(st.random, "randint", lambda a, b: a),
        ]


class HandleBeatTest(unittest.TestCase):
    def run_with(self, db, coro_fn):
        ps = db.patches()
        for p in ps:
            p.start()
        try:
            return asyncio.run(coro_fn())
        finally:
            for p in reversed(ps):
                p.stop()

    def test_first_visit_then_first_minute_each_paid_once(self):
        db = FakeDb()

        async def go():
            hello, _ = await st.handle_beat(USER, {"sid": "abcd1234", "n": 0, "hello": True}, T0)
            again, _ = await st.handle_beat(USER, {"sid": "abcd1234", "n": 0, "hello": True}, T0 + timedelta(seconds=20))
            minute, _ = await st.handle_beat(USER, beat(sid="abcd1234"), T0 + timedelta(seconds=80))
            later, _ = await st.handle_beat(USER, beat(n=2, gaps=(400,), sid="abcd1234"), T0 + timedelta(seconds=140))
            return hello, again, minute, later
        hello, again, minute, later = self.run_with(db, go)
        self.assertEqual(hello["awards"], [{"seconds": 0, "amount": 5}])
        self.assertEqual(set(hello), {"ok", "enabled", "active", "credited", "awards", "balance", "next", "check", "info"})
        self.assertEqual(hello["balance"], 5)
        self.assertEqual(hello["next"], {"seconds": 60, "amount": 10, "left": 60})
        self.assertIsNone(hello["check"])
        info = hello["info"]
        self.assertEqual([round(l["rate"], 3) for l in info["levels"]], [0.005, 0.01, 0.02, 0.03])
        self.assertEqual((info["my_rate"], info["redeem"], info["every_hour_after"]), (0.005, True, 500))
        self.assertEqual(info["ladder"][0], {"seconds": 0, "amount": 5})
        self.assertEqual(again["awards"], [])
        self.assertEqual((minute["credited"], minute["awards"]), (60, [{"seconds": 60, "amount": 10}]))
        self.assertEqual(minute["balance"], 15)
        self.assertIn("info", minute)                          # with an award: what «Batafsil» says
        self.assertEqual((later["credited"], later["awards"]), (60, []))
        self.assertNotIn("info", later)
        self.assertEqual(sum(db.ledger.values()), 15)

    def test_racing_payments_pay_once(self):
        db = FakeDb()
        db.rows[USER] = dict(fresh(), active_seconds=600)

        async def go():
            state = dict(db.rows[USER])
            return await asyncio.gather(st._pay(USER, dict(state)), st._pay(USER, dict(state)))
        first, second = self.run_with(db, go)
        self.assertEqual(sorted(a["seconds"] for a in first + second), [0, 60, 600])
        self.assertEqual(db.balance[USER], 65)

    def test_failed_payment_is_retried(self):
        db = FakeDb()
        db.fail_credit = True

        async def go():
            first, _ = await st.handle_beat(USER, {"sid": "abcd1234", "n": 0}, T0)
            db.fail_credit = False
            second, _ = await st.handle_beat(USER, {"sid": "abcd1234", "n": 0}, T0 + timedelta(seconds=30))
            return first, second
        with self.assertLogs("site_time", "ERROR"):
            first, second = self.run_with(db, go)
        self.assertEqual(first["awards"], [])
        self.assertEqual(second["awards"], [{"seconds": 0, "amount": 5}])

    def test_shop_accounts_never_earn(self):
        db = FakeDb()
        shop = next(iter(database.LEADERBOARD_EXCLUDED_USER_IDS))
        out = self.run_with(db, lambda: st.handle_beat(shop, {"sid": "abcd1234", "n": 0, "hello": True}, T0))
        self.assertEqual(out, ({"ok": True, "enabled": False}, 200))
        self.assertEqual((db.calls, db.ledger), (0, {}))

    def test_admins_earn_like_buyers(self):
        # Only the shop accounts are left out — admins test it on themselves.
        import inspect
        self.assertNotIn("ADMIN_IDS", inspect.getsource(st))
        admin = next((a for a in webapp_server.ADMIN_IDS if a not in database.LEADERBOARD_EXCLUDED_USER_IDS), USER)
        out, _ = self.run_with(FakeDb(), lambda: st.handle_beat(admin, {"sid": "abcd1234", "n": 0}, T0))
        self.assertEqual(out["awards"], [{"seconds": 0, "amount": 5}])

    def test_switched_off(self):
        for db in (FakeDb(enabled=False), FakeDb(site_enabled=False)):
            out = self.run_with(db, lambda: st.handle_beat(USER, {"sid": "abcd1234", "n": 3}, T0))
            self.assertEqual(out, ({"ok": True, "enabled": False}, 200))
            self.assertEqual((db.calls, db.ledger), (0, {}))
            here = self.run_with(db, lambda: st.handle_presence(USER, {"token": "abc"}, T0))
            self.assertEqual(here[0]["ok"], False)

    def test_bad_beat(self):
        db = FakeDb()
        out = self.run_with(db, lambda: st.handle_beat(USER, {"sid": "x", "n": 1}, T0))
        self.assertEqual(out[1], 400)
        self.assertEqual(db.calls, 0)

    def test_suspicious_session_is_logged(self):
        db = FakeDb()
        db.rows[USER] = dict(fresh(), last_beat_at=T0, check_at=10 ** 9, pattern="4|2000,2000",
                             pattern_seconds=st.SAME_PATTERN_LIMIT - 60)

        async def go():
            return await st.handle_beat(USER, beat(n=4, gaps=(2000, 2000), sid="bot00001"), T0 + timedelta(seconds=60))
        with self.assertLogs("site_time", "WARNING") as logs:
            out, _ = self.run_with(db, go)
        self.assertIn("suspicious session", logs.output[0])
        self.assertEqual(out["credited"], 0)
        self.assertEqual(db.rows[USER]["flags"], 1)

    def test_presence_endpoint(self):
        db = FakeDb()
        db.rows[USER] = dict(fresh(), active_seconds=1200, check_at=1200, check_token="tok1",
                             check_issued_at=T0)

        async def go():
            wrong, _ = await st.handle_presence(USER, {"token": "nope"}, T0 + timedelta(seconds=5))
            right, _ = await st.handle_presence(USER, {"token": "tok1"}, T0 + timedelta(seconds=5))
            return wrong, right
        wrong, right = self.run_with(db, go)
        self.assertEqual(wrong, {"ok": False, "check": "tok1"})
        self.assertEqual(right, {"ok": True, "check": None})
        self.assertEqual(db.rows[USER]["check_at"], 1200 + 20 * 60)


class EndpointTest(unittest.TestCase):
    def test_routes(self):
        app = webapp_server.create_webapp(object())  # type: ignore[arg-type]
        found = {}
        for r in app.router.routes():
            found.setdefault(r.resource.canonical, set()).add(r.method)
        self.assertEqual(found["/api/site-time"], {"POST"})
        self.assertEqual(found["/api/site-time/here"], {"POST"})

    def test_bad_json_and_pass_through(self):
        async def call(body, handler="handle_beat"):
            req = make_mocked_request("POST", "/api/site-time")
            req["user_id"] = USER
            req.json = AsyncMock(side_effect=ValueError) if body is None else AsyncMock(return_value=body)
            fn = webapp_server.api_site_time if handler == "handle_beat" else webapp_server.api_site_time_here
            return await fn(req)
        resp = asyncio.run(call(None))
        self.assertEqual(resp.status, 400)
        with patch.object(st, "handle_beat", AsyncMock(return_value=({"ok": True, "enabled": False}, 200))) as h:
            resp = asyncio.run(call({"sid": "abcd", "n": 0}))
        self.assertEqual(json.loads(resp.body), {"ok": True, "enabled": False})
        h.assert_awaited_once_with(USER, {"sid": "abcd", "n": 0})
        with patch.object(st, "handle_beat", AsyncMock(side_effect=RuntimeError("db"))):
            with self.assertLogs("webapp_server", "ERROR"):
                resp = asyncio.run(call({"sid": "abcd", "n": 0}))
        self.assertEqual(resp.status, 500)


class AdminTest(unittest.TestCase):
    def test_commands(self):
        from handlers import broadcast_admin
        self.assertIn("sayt_keto", [c.command for c in keyboards.ADMIN_COMMANDS])
        for name in ("sayt_keto", "sayt_keto_on", "sayt_keto_off"):
            self.assertTrue(callable(getattr(broadcast_admin, name)), name)

    def test_status_text(self):
        stats = {"users": 12, "today_users": 3, "seconds": 7 * 3600 + 120, "today_seconds": 900,
                 "keto": 1234, "flags": 1, "last_flag": datetime(2026, 11, 15, 9, 5)}
        text = st.admin_status_text(True, False, stats)
        self.assertIn("🟢 yoqilgan", text)
        self.assertIn("/keto_on", text)                          # the program itself is off
        self.assertIn("7 soat 2 daq", text)
        self.assertIn("1 234", text)
        self.assertIn("1-tashrif — 5 · 1 daq — 10", text)
        self.assertIn("keyin har soat — 500", text)


class PageTest(unittest.TestCase):
    def block(self):
        return PAGE[PAGE.index("// ===== SAYTDA FAOL VAQT UCHUN KETO"):PAGE.index("// ===== AKSIYA / BONUS =====")]

    def test_only_trusted_interaction_counts(self):
        b = self.block()
        self.assertIn("if (!e || !e.isTrusted) return;", b)
        self.assertIn("if (!e.isTrusted || !token || sending || performance.now() - shownAt < MIN_REPLY_MS) return;", b)
        self.assertNotIn("'scroll'", b)                         # the tiles scroll by themselves

    def test_quiet_for_reduced_motion_and_muted_sound(self):
        b = self.block()
        self.assertIn("prefers-reduced-motion: reduce", b)
        self.assertIn("if (!still) box._stops.push(launchFireworks(", b)
        self.assertIn("if (!still && !soundOff()) Fanfare.play(", b)
        self.assertIn("localStorage.getItem('ketoshop_birds') === 'off'", b)
        self.assertIn("#keto-party.still", PAGE)

    def test_one_party_not_two(self):
        party = PAGE[PAGE.index("function celebrateWelcome("):PAGE.index("function launchFireworks(")]
        self.assertIn("if (KetoParty.joinWelcome(w, endsAt)) return;", party)
        self.assertIn("function showWelcomeParty(w, endsAt)", party)
        hint = PAGE[PAGE.index("const DockHint"):PAGE.index("async maybe()", PAGE.index("const DockHint"))]
        self.assertIn("document.getElementById('keto-party')", hint)

    def test_texts_in_both_languages(self):
        b = self.block()
        for uz, ru in (("🎉 +{n} Keto sovg'a!", "🎉 +{n} Keto в подарок!"),
                       ("Yana {d} — +{n} Keto 🎁", "Ещё {d} — +{n} Keto 🎁"),
                       ("Davom etyapsizmi? ✅", "Вы ещё здесь? ✅"),
                       ("Batafsil ▾", "Подробнее ▾")):
            self.assertIn(uz, b)
            self.assertIn(ru, b)
        self.assertNotIn("cho'chqa", b.lower())                # never the piggy-bank example
        self.assertNotIn("🥑", b)

    def test_started_after_the_gate_and_on_the_profile(self):
        init = PAGE[PAGE.index("(async function init() {"):PAGE.index("// ===== SAVAT BRONI")]
        self.assertLess(init.index("showStartGate(access); return;"), init.index("SiteTime.start();"))
        profile = PAGE[PAGE.index("function renderProfilePage()"):PAGE.index("const SUPPORT_USERNAME")]
        self.assertIn("SiteTime.renderProfile();", profile)
        self.assertIn('<div id="st-profile"></div>', PAGE)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class MiniAppFlowTest(unittest.TestCase):
    def flow(self, scenario):
        out = subprocess.run(["node", str(ROOT / "tests" / "site_time_flow.js"), scenario],
                             capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_beats(self):
        r = self.flow("beats")
        sent = [c for c in r["calls"] if c[0] == "/api/site-time"]
        self.assertEqual(sent[0][1], {"sid": sent[0][1]["sid"], "n": 0, "gaps": [], "hello": True})
        minutes = [c[1] for c in sent[1:]]
        # minute 1: two real taps (a script's click ignored); minute 2: hidden
        # half the time, so it closes later; minute 3: nobody touched — not sent.
        self.assertEqual([m["n"] for m in minutes], [2, 1])
        self.assertEqual(minutes[0]["gaps"], [1500])
        self.assertEqual(r["beatAtSec"], [60, 150])
        self.assertEqual(r["partyAdds"], [[{"seconds": 0, "amount": 5}], [{"seconds": 60, "amount": 10}]])
        self.assertEqual(r["helloDone"], 1)

    def test_presence(self):
        r = self.flow("presence")
        self.assertTrue(r["cardShown"])
        self.assertEqual(r["herePosts"], 1)                     # the 100 ms tap and the script's click were ignored
        self.assertFalse(r["cardAfter"])

    def test_durations(self):
        r = self.flow("durations")
        self.assertEqual(r["uz"], ["1 daqiqa", "9 daqiqa", "1 soat", "1 soat 30 daqiqa", "0 daqiqa", "10 soat"])
        self.assertEqual(r["ru"], ["1 мин", "9 мин", "1 ч", "1 ч 30 мин"])
        self.assertEqual(r["ruLong"], ["1 минуту", "10 минут", "1 час", "2 часа", "22 минуты"])
        self.assertEqual(r["next"], "Yana 9 daqiqa — +50 Keto 🎁")


if __name__ == "__main__":
    unittest.main()
