"""Instagram Direct AI javoblari (ig_direct.py) — Meta, OpenAI, Telegram va
bazasiz: _graph, AI, bot va jadval soxta, hech narsa yuborilmaydi. Ismlar,
id lar va matnlar o'ylab topilgan (haqiqiy mijoz ma'lumoti emas).

Haqiqiy PostgreSQL da (ixtiyoriy, CI da o'tkazib yuboriladi):
    IG_DM_PG_URL=postgresql://postgres@127.0.0.1:55432/postgres \\
        python -m unittest tests.test_ig_direct
Test o'z sxemasini yaratadi va oxirida o'chiradi.
"""
import asyncio
import os
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://unused/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import comment_ai  # noqa: E402
import database  # noqa: E402
import ig_direct as d  # noqa: E402
import meta_comments as mc  # noqa: E402
from config import ADMIN_IDS  # noqa: E402

NOW = datetime(2026, 11, 16, 10, 0, 0)
IG_ID = "17840000000000001"
IDENT = {"page_token": "PAGE-TOKEN", "page_name": "Test sahifa", "ig_id": IG_ID, "ig_username": "shop.test"}
CUSTOMER = ("5550001", "mijoz_test")

PRODUCTS = [
    {"id": 1, "name": "Kokos uni 500gr", "name_ru": "Кокосовая мука 500г", "category": "coconut",
     "price": 60000, "discount_percent": 20, "discount_until": None, "quantity": 10},
    {"id": 2, "name": "Bodom uni 500gr", "name_ru": None, "category": "keto_flour",
     "price": 120000, "discount_percent": 0, "discount_until": None, "quantity": 5},
    {"id": 3, "name": "Eritritol 500gr", "name_ru": None, "category": "sweeteners",
     "price": 70000, "discount_percent": 10, "discount_until": datetime(2020, 1, 1), "quantity": 3},   # muddati o'tgan
    {"id": 4, "name": "Optom un", "category": "keto_flour", "price": 1000, "discount_percent": 50,
     "discount_until": None, "quantity": 100, "b2b_only": True},
    {"id": 5, "name": "Chia urug'i", "category": "seeds", "price": 40000, "discount_percent": 15,
     "discount_until": None, "quantity": 0},                                                          # tugagan
]
NO_SALE = [dict(p, discount_percent=0) for p in PRODUCTS]


def gtime(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S+0000")


def raw_conv(cid: str, msgs: list[tuple], customer=CUSTOMER) -> dict:
    """msgs: (mid, ours, matn, necha_soniya_oldin) — eskidan yangiga. Graph
    xabarlarni yangidan eskiga beradi — shunday qaytaramiz."""
    data = []
    for mid, ours, text, ago in reversed(msgs):
        who = {"id": IG_ID, "username": "shop.test"} if ours else {"id": customer[0], "username": customer[1]}
        data.append({"id": mid, "from": who, "message": text, "created_time": gtime(NOW - timedelta(seconds=ago))})
    return {"id": cid, "updated_time": gtime(NOW - timedelta(seconds=min(m[3] for m in msgs))),
            "participants": {"data": [{"id": IG_ID, "username": "shop.test"},
                                      {"id": customer[0], "username": customer[1]}]},
            "messages": {"data": data}}


def ai(reply="Kokos uni bizda bor 🌿", intent="mahsulot", human=False, catalog=False, discounts=False,
       end=False, lang="uz") -> dict:
    return {"reply": reply, "intent": intent, "needs_human": human, "send_catalog": catalog,
            "send_discounts": discounts, "end": end, "lang": lang}


class FakeStore:
    """ig_dm_messages / ig_dm_state o'rnida — xotirada."""

    NAMES = ("store_messages", "statuses", "mark", "replies_since", "catalog_recent", "had_reply",
             "get_state", "note_poll")

    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.state = {"enabled": True}

    async def store_messages(self, cid, rows):
        for r in rows:
            self.rows.setdefault(r["message_id"], dict(r, conversation_id=cid, status=r.get("status") or "new",
                                                       replied_at=None, claimed_at=None, catalog_sent=False))

    async def statuses(self, ids):
        return {i: dict(self.rows[i]) for i in ids if i in self.rows}

    async def mark(self, ids, status, from_statuses, **fields):
        done = []
        for i in ids:
            r = self.rows.get(i)
            if r and r["status"] in from_statuses:
                r.update(fields, status=status)
                done.append(i)
        return done

    async def replies_since(self, cid, since):
        return len({r["replied_at"] for r in self.rows.values() if r["conversation_id"] == cid
                    and r["status"] in ("replied", "held") and r["replied_at"] and r["replied_at"] > since})

    async def catalog_recent(self, cid, since):
        return any(r["conversation_id"] == cid and r["catalog_sent"] and r["replied_at"] and r["replied_at"] > since
                   for r in self.rows.values())

    async def had_reply(self, cid):
        return any(r["conversation_id"] == cid and r["status"] in ("replied", "held", "human")
                   for r in self.rows.values())

    async def get_state(self):
        return dict(self.state)

    async def note_poll(self, error=None):
        self.state["last_error"] = error

    def status(self, mid):
        return self.rows[mid]["status"]


class FakeGraph:
    """mc._graph o'rnida: yozib boradi, hech qayerga ulanmaydi."""

    def __init__(self, convs=None, perms=d.DM_PERMISSIONS):
        self.calls, self.convs, self.perms = [], list(convs or []), perms
        self.send_errors: list[Exception] = []
        self.read_error: Exception | None = None
        self.pages: list[dict] | None = None

    async def __call__(self, session, method, path, token, params=None, body=None):
        self.calls.append((method, path, dict(params or {}), body))
        if method == "POST":
            if self.send_errors:
                raise self.send_errors.pop(0)
            return {"recipient_id": body["recipient"]["id"], "message_id": f"sent{len(self.calls)}"}
        if path == mc.PAGE_ID:
            return {"name": "Test sahifa", "access_token": "PAGE-TOKEN",
                    "instagram_business_account": {"id": IG_ID, "username": "shop.test"}}
        if path == "me/permissions":
            return {"data": [{"permission": p, "status": "granted"} for p in self.perms]}
        if path.endswith("/conversations"):
            if self.read_error:
                raise self.read_error
            if self.pages is not None:
                return self.pages.pop(0)
            return {"data": self.convs, "paging": {}}
        raise AssertionError(f"kutilmagan so'rov: {method} {path}")

    @property
    def sent(self) -> list[str]:
        return [c[3]["message"]["text"] for c in self.calls if c[0] == "POST"]

    @property
    def posts(self) -> list[tuple]:
        return [c for c in self.calls if c[0] == "POST"]


class FakeBot:
    def __init__(self):
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


class Base(unittest.IsolatedAsyncioTestCase):
    products = PRODUCTS

    async def asyncSetUp(self):
        self.store, self.graph, self.bot = FakeStore(), FakeGraph(), FakeBot()
        self.ai = AsyncMock(return_value=ai())
        patches = [patch.object(d, n, getattr(self.store, n)) for n in FakeStore.NAMES] + [
            patch.object(mc, "_graph", self.graph),
            patch.object(mc, "_identity", {}),
            patch.object(mc, "_db_token", "SYSTEM-TOKEN"),
            patch.object(mc, "load_token", AsyncMock()),
            patch.object(d, "ask_ai", self.ai),
            patch.object(d, "PAUSE", (0, 0)),
            patch.object(d, "_offers", AsyncMock(return_value="")),
            patch.object(comment_ai, "provider", AsyncMock(return_value="openai")),
            patch.object(comment_ai, "catalog_text", AsyncMock(return_value="- Kokos uni 500gr — 48 000 so'm")),
            patch.object(database, "admin_list_products", AsyncMock(return_value=self.products)),
            patch.object(database, "get_meta_comments_state", AsyncMock(return_value={"kb": {}})),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        d._backoff.update(until=None, n=0)
        d._failures.clear()
        d._throttle_noted.clear()
        d._errors.clear()

    async def handle(self, raw, now=NOW):
        return await d.handle_conversation(self.bot, None, IDENT, d.parse_conversation(raw, IDENT), now)


# ───────────────────────────── o'qish (polling) ─────────────────────────────

class ParseTest(Base):
    async def test_graph_json_newest_first_and_ours(self):
        raw = raw_conv("c1", [("m1", False, "Salom", 600), ("m2", True, "Assalomu alaykum!", 500),
                              ("m3", False, "Kokos uni bormi?", 90), ("m4", False, "Narxi?", 80)])
        conv = d.parse_conversation(raw, IDENT)
        self.assertEqual([m["message_id"] for m in conv["messages"]], ["m1", "m2", "m3", "m4"])
        self.assertEqual([m["ours"] for m in conv["messages"]], [False, True, False, False])
        self.assertEqual((conv["customer_id"], conv["username"]), CUSTOMER)
        self.assertEqual(conv["updated_at"], NOW - timedelta(seconds=80))
        earlier, trailing = d.split_turns(conv)
        self.assertEqual([m["message_id"] for m in earlier], ["m1"])
        self.assertEqual([m["message_id"] for m in trailing], ["m3", "m4"])

    async def test_our_account_by_username_too(self):
        raw = raw_conv("c1", [("m1", False, "Salom", 100)])
        raw["messages"]["data"].insert(0, {"id": "m2", "from": {"id": "other-id", "username": "Shop.Test"},
                                           "message": "Javob", "created_time": gtime(NOW - timedelta(seconds=50))})
        conv = d.parse_conversation(raw, IDENT)
        self.assertTrue(conv["messages"][-1]["ours"])
        self.assertEqual(d.split_turns(conv)[1], [])

    async def test_fetch_pages_and_stops_at_old_conversations(self):
        fresh = raw_conv("c1", [("m1", False, "Salom", 60)])
        old = raw_conv("c2", [("m2", False, "Salom", 30 * 3600)])
        self.graph.pages = [{"data": [fresh], "paging": {"next": "https://x/next", "cursors": {"after": "CUR1"}}},
                            {"data": [old], "paging": {"next": "https://x/next2", "cursors": {"after": "CUR2"}}}]
        convs = await d.fetch_conversations(None, IDENT, NOW)
        self.assertEqual([c["conversation_id"] for c in convs], ["c1"])
        reads = [c for c in self.graph.calls if c[1].endswith("/conversations")]
        self.assertEqual(len(reads), 2)
        self.assertEqual(reads[0][1], f"{mc.PAGE_ID}/conversations")
        self.assertEqual(reads[0][2]["platform"], "instagram")
        self.assertIn("messages.limit(10){id,from,to,message,created_time}", reads[0][2]["fields"])
        self.assertEqual(reads[1][2]["after"], "CUR1")
        self.assertEqual(self.graph.posts, [])


# ───────────────────────────── 24 soatlik oyna ──────────────────────────────

class WindowTest(Base):
    def test_in_window(self):
        msg = lambda ago: [{"created_at": NOW - ago}]  # noqa: E731
        self.assertTrue(d.in_window(msg(timedelta(hours=23)), NOW))
        self.assertFalse(d.in_window(msg(timedelta(hours=23, minutes=45)), NOW))
        self.assertFalse(d.in_window(msg(timedelta(hours=25)), NOW))

    async def test_outside_window_never_sends_and_tells_admins(self):
        raw = raw_conv("c1", [("m1", False, "Narxi qancha?", 23 * 3600 + 50 * 60)])
        self.assertEqual(await self.handle(raw), "expired")
        self.assertEqual(self.graph.posts, [])
        self.ai.assert_not_called()
        self.assertEqual(self.store.status("m1"), "expired")
        self.assertEqual(len(self.bot.sent), len(ADMIN_IDS))
        self.assertIn("24 soatlik oyna", self.bot.sent[0][1])
        # Qayta ko'rilsa — ikkinchi kartochka yo'q.
        self.assertEqual(await self.handle(raw), "none")
        self.assertEqual(len(self.bot.sent), len(ADMIN_IDS))

    async def test_send_refused_outside_window_is_marked(self):
        self.graph.send_errors = [mc.GraphError(10, "(#10) This message is sent outside of allowed window.")]
        raw = raw_conv("c1", [("m1", False, "Salom", 120)])
        self.assertEqual(await self.handle(raw), "unavailable")
        self.assertEqual(self.store.status("m1"), "unavailable")
        self.assertIn("ruxsat bermadi", self.bot.sent[0][1])
        self.assertEqual(await self.handle(raw), "none")
        self.assertEqual(len(self.graph.posts), 1)


# ───────────────────────────── takror yo'q, yig'ish ──────────────────────────

class DedupeBatchTest(Base):
    async def test_quick_messages_one_reply_and_never_twice(self):
        raw = raw_conv("c1", [("m1", False, "Salom", 50), ("m2", False, "Kokos uni bormi?", 40)])
        self.assertEqual(await self.handle(raw), "replied")
        self.assertEqual(self.ai.await_count, 1)
        prompt = self.ai.call_args[0][1]
        self.assertIn("Salom   ← JAVOB KERAK", prompt)
        self.assertIn("Kokos uni bormi?   ← JAVOB KERAK", prompt)
        self.assertEqual(len(self.graph.posts), 1)
        method, path, _, body = self.graph.posts[0]
        self.assertEqual(path, f"{mc.PAGE_ID}/messages")
        self.assertEqual(body["recipient"], {"id": CUSTOMER[0]})
        self.assertEqual(body["messaging_type"], "RESPONSE")
        self.assertEqual(self.store.status("m1"), "replied")
        self.assertEqual(self.store.rows["m1"]["replied_at"], self.store.rows["m2"]["replied_at"])
        # Javobimiz hali ko'rinmasa ham (yoki qayta ishga tushsa) — qayta javob yo'q.
        self.assertEqual(await self.handle(raw, NOW + timedelta(minutes=1)), "none")
        self.assertEqual((self.ai.await_count, len(self.graph.posts)), (1, 1))

    async def test_waits_while_customer_is_still_typing(self):
        raw = raw_conv("c1", [("m1", False, "Salom", 10)])
        self.assertEqual(await self.handle(raw), "wait")
        self.ai.assert_not_called()
        self.assertEqual(self.store.status("m1"), "new")
        self.assertEqual(await self.handle(raw, NOW + timedelta(seconds=30)), "replied")

    async def test_staff_answered_in_instagram(self):
        await self.handle(raw_conv("c1", [("m1", False, "Salom", 10)]))       # hali kutyapti
        raw = raw_conv("c1", [("m1", False, "Salom", 70), ("m2", True, "Assalomu alaykum!", 20)])
        self.assertEqual(await self.handle(raw, NOW), "none")
        self.assertEqual(self.store.status("m1"), "human")
        self.assertEqual(self.graph.posts, [])

    async def test_stale_claim_after_restart_is_answered(self):
        await self.store.store_messages("c1", [{"message_id": "m1", "text": "Salom", "status": "sending"}])
        self.store.rows["m1"]["claimed_at"] = NOW - timedelta(minutes=30)
        self.assertEqual(await self.handle(raw_conv("c1", [("m1", False, "Salom", 40 * 60)])), "replied")
        self.assertEqual(len(self.graph.posts), 1)

    async def test_fresh_claim_is_left_alone(self):
        await self.store.store_messages("c1", [{"message_id": "m1", "text": "Salom", "status": "sending"}])
        self.store.rows["m1"]["claimed_at"] = NOW - timedelta(seconds=20)
        self.assertEqual(await self.handle(raw_conv("c1", [("m1", False, "Salom", 60)])), "none")
        self.assertEqual(self.graph.posts, [])

    async def test_no_reply_to_spam(self):
        raw = raw_conv("c1", [("m1", False, "Buy real followers cheap!!! promote your page", 60)])
        self.assertEqual(await self.handle(raw), "spam")
        self.ai.assert_not_called()
        self.ai.return_value = ai(reply="", intent="spam")
        self.assertEqual(await self.handle(raw_conv("c2", [("m2", False, "Kanalimga obuna bo'l", 60)])), "spam")
        self.assertEqual((self.graph.posts, self.bot.sent), ([], []))


# ───────────────────────────── 1000 belgi ───────────────────────────────────

class SplitTest(unittest.TestCase):
    def test_short_text_unchanged(self):
        self.assertEqual(d.split_text("Salom 🌿"), ["Salom 🌿"])
        self.assertEqual(d.split_text("  "), [])

    def test_long_text_splits_on_sentences_under_the_limit(self):
        text = " ".join(f"Bu {i}-gap, keto haqida qisqa maslahat 🌿." for i in range(120))
        parts = d.split_text(text)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(d._ulen(p) <= 1000 for p in parts))
        self.assertTrue(all(p.endswith(".") for p in parts))
        self.assertEqual(" ".join(parts).split(), text.split())

    def test_paragraphs_first(self):
        text = "A" * 600 + "\n\n" + "B" * 600
        self.assertEqual(d.split_text(text), ["A" * 600, "B" * 600])

    def test_one_huge_word_is_cut(self):
        parts = d.split_text("x" * 2500)
        self.assertEqual([len(p) for p in parts], [1000, 1000, 500])

    def test_emoji_counted_as_two(self):
        self.assertEqual(d._ulen("🌿"), 2)
        parts = d.split_text("🌿" * 600)
        self.assertTrue(all(d._ulen(p) <= 1000 for p in parts))

    def test_assemble_keeps_lists_and_max_three(self):
        reply = "A" * 900 + "\n\n" + "B" * 900 + "\n\n" + "C" * 900
        self.assertEqual(len(d.assemble(reply, [])), 3)
        out = d.assemble(reply, ["RO'YXAT", "CHEGIRMA"])
        self.assertEqual(out, ["A" * 900, "RO'YXAT", "CHEGIRMA"])
        self.assertEqual(d.assemble("Salom", ["RO'YXAT", ""]), ["Salom", "RO'YXAT"])


# ───────────────────────────── ro'yxat va chegirma ──────────────────────────

class ListsTest(Base):
    def test_catalog_message_categories_and_link(self):
        text = d.catalog_message(PRODUCTS, "uz")
        self.assertTrue(text.startswith("🛒 Keto shop'da hozir 3 xil mahsulot bor"))   # tugagan va optom yo'q
        self.assertIn("— 1 xil", text)
        self.assertTrue(text.rstrip().endswith("👉 https://t.me/ketoshopbot/shop"))
        self.assertNotIn("Chia", text)
        self.assertLessEqual(d._ulen(text), 1000)

    def test_discount_message_is_old_to_new(self):
        text = d.discount_message(d.discounted(PRODUCTS), "uz")
        self.assertIn("🔥 Hozir chegirmada:", text)
        self.assertIn("• Kokos uni 500gr — 60 000 → 48 000 so'm (−20%)", text)
        self.assertNotIn("Eritritol", text)       # chegirma muddati o'tgan
        self.assertNotIn("Chia", text)            # tugagan
        self.assertNotIn("Optom", text)           # faqat optom
        self.assertEqual(d.discount_message([], "uz"), "")

    def test_discount_message_russian_and_cyrillic(self):
        ru = d.discount_message(d.discounted(PRODUCTS), "ru")
        self.assertIn("• Кокосовая мука 500г — 60 000 → 48 000 сум (−20%)", ru)
        cyr = d.discount_message(d.discounted(PRODUCTS), "uz_cyr")
        self.assertIn("сўм", cyr)
        self.assertIn("https://t.me/ketoshopbot/shop", cyr)

    def test_long_discount_list_fits_one_message(self):
        many = [dict(PRODUCTS[0], id=i, name=f"Mahsulot raqami {i} juda uzun nom bilan 500gr") for i in range(80)]
        text = d.discount_message(d.discounted(many), "uz")
        self.assertLessEqual(d._ulen(text), 1000)
        self.assertIn("… va yana", text)

    async def test_catalog_request_sends_list_and_discounts_separately(self):
        self.ai.return_value = ai(reply="Assalomu alaykum! Bo'limlar ro'yxatini quyida yubordik 🌿",
                                  intent="katalog", catalog=True)
        self.assertEqual(await self.handle(raw_conv("c1", [("m1", False, "Nimalar bor?", 60)])), "replied")
        sent = self.graph.sent
        self.assertEqual(len(sent), 3)
        self.assertIn("quyida yubordik", sent[0])
        self.assertTrue(sent[1].startswith("🛒 Keto shop'da"))
        self.assertTrue(sent[2].startswith("🔥 Hozir chegirmada:"))
        self.assertTrue(self.store.rows["m1"]["catalog_sent"])
        # 6 soat ichida yana so'rasa — ro'yxat qayta yuborilmaydi.
        self.assertEqual(await self.handle(raw_conv("c1", [("m1", False, "Nimalar bor?", 3600),
                                                           ("x", True, "...", 3500),
                                                           ("m2", False, "Yana nima bor?", 60)])), "replied")
        self.assertEqual(len(self.graph.sent), 4)

    async def test_simple_question_gets_no_list(self):
        self.ai.return_value = ai(reply="Kokos uni 500gr — 48 000 so'm 🌿")
        await self.handle(raw_conv("c1", [("m1", False, "Kokos uni narxi?", 60)]))
        self.assertEqual(len(self.graph.sent), 1)


class NoDiscountTest(Base):
    products = NO_SALE

    async def test_no_discount_message_when_none_active(self):
        self.ai.return_value = ai(reply="Salom! Ro'yxatni quyida yubordik", intent="katalog", catalog=True)
        await self.handle(raw_conv("c1", [("m1", False, "Prays bormi?", 60)]))
        self.assertEqual(len(self.graph.sent), 2)
        self.assertTrue(self.graph.sent[1].startswith("🛒"))
        self.assertIn("hozir yo'q", self.ai.call_args[0][0])      # AI chegirma o'ylab topmasin


# ───────────────────────────── odam kerak ───────────────────────────────────

class HoldingTest(Base):
    async def test_complaint_gets_warm_reply_and_admin_card(self):
        self.ai.return_value = ai(reply="Kechirasiz, noqulaylik uchun 🙏 Mutaxassisimiz tez orada shu yerda "
                                        "javob beradi. Shoshilinch bo'lsa: Telegram botimiz @ketoshopbot",
                                  intent="shikoyat", human=True)
        raw = raw_conv("c1", [("m1", False, "Buyurtmam kelmadi, 3 kun bo'ldi", 60)])
        self.assertEqual(await self.handle(raw), "held")
        self.assertEqual(self.store.status("m1"), "held")
        self.assertIn("Telegram botimiz: https://t.me/ketoshopbot", self.graph.sent[0])
        self.assertEqual(len(self.bot.sent), len(ADMIN_IDS))
        card = self.bot.sent[0][1]
        self.assertIn("odam kerak", card)
        self.assertIn("Shikoyat", card)
        self.assertIn("Buyurtmam kelmadi", card)
        self.assertIn("Biz yozdik", card)

    async def test_no_list_with_a_human_reply(self):
        self.ai.return_value = ai(reply="Tushunamiz, shifokor bilan maslahatlashing", intent="salomatlik",
                                  human=True, catalog=True)
        await self.handle(raw_conv("c1", [("m1", False, "Diabetga mumkinmi?", 60)]))
        self.assertEqual(len(self.graph.sent), 1)

    async def test_ai_down_waits_then_holding_reply(self):
        self.ai.return_value = None
        raw = raw_conv("c1", [("m1", False, "Yetkazib berasizlarmi?", 60)])
        self.assertEqual(await self.handle(raw), "retry")
        self.assertEqual((self.graph.posts, self.bot.sent), ([], []))
        self.assertEqual(await self.handle(raw, NOW + timedelta(minutes=10)), "held")
        self.assertIn("Assalomu alaykum!", self.graph.sent[0])
        self.assertIn("https://t.me/ketoshopbot", self.graph.sent[0])
        self.assertIn("+998", self.graph.sent[0])
        self.assertIn("AI javob bera olmadi", self.bot.sent[0][1])

    async def test_no_ai_key_holding_at_once(self):
        with patch.object(comment_ai, "provider", AsyncMock(return_value="")):
            self.assertEqual(await self.handle(raw_conv("c1", [("m1", False, "Привет, сколько стоит?", 60)])), "held")
        self.assertTrue(self.graph.sent[0].startswith("Здравствуйте!"))
        self.ai.assert_not_called()

    async def test_photo_or_voice_gets_holding_reply(self):
        self.assertEqual(await self.handle(raw_conv("c1", [("m1", False, "", 60)])), "held")
        self.assertIn("Matnsiz xabar", self.bot.sent[0][1])
        self.ai.assert_not_called()

    async def test_thumbs_up_after_our_answer_closes(self):
        self.ai.return_value = ai(reply="", intent="rahmat", end=True)
        raw = raw_conv("c1", [("m1", False, "Narxi?", 600), ("m2", True, "48 000 so'm", 500), ("m3", False, "👍", 60)])
        self.assertEqual(await self.handle(raw), "closed")
        self.assertEqual(self.graph.posts, [])


# ───────────────────────────── cheklovlar ───────────────────────────────────

class ThrottleTest(Base):
    def test_classify(self):
        g = mc.GraphError
        self.assertEqual(d.classify(g(10, "(#10) This message is sent outside of allowed window.")), "closed")
        self.assertEqual(d.classify(g(551, "This person isn't available right now.")), "closed")
        self.assertEqual(d.classify(g(4, "Application request limit reached")), "rate")
        self.assertEqual(d.classify(g(613, "Calls to this api have exceeded the rate limit.")), "rate")
        self.assertEqual(d.classify(g(10, "Application does not have permission for this action")), "fatal")
        self.assertEqual(d.classify(g(190, "Error validating access token")), "fatal")
        self.assertEqual(d.classify(g(3, "Application does not have the capability")), "fatal")
        self.assertEqual(d.classify(g(9999, "something odd")), "unknown")

    async def tick(self, raw, now=NOW):
        self.graph.convs = [raw]
        return await d.tick(self.bot, now)

    async def test_rate_limit_backs_off_without_marking(self):
        self.graph.send_errors = [mc.GraphError(4, "Application request limit reached")]
        raw = raw_conv("c1", [("m1", False, "Salom", 60)])
        stats = await self.tick(raw)
        self.assertEqual(stats.get("error"), 1)
        self.assertEqual(self.store.status("m1"), "new")
        self.assertIsNotNone(d._backoff["until"])
        self.assertEqual(await self.tick(raw, NOW + timedelta(minutes=1)), {"backoff": 1})
        stats = await self.tick(raw, NOW + timedelta(minutes=3))
        self.assertEqual(stats.get("replied"), 1)
        self.assertEqual(self.store.status("m1"), "replied")
        self.assertIsNone(d._backoff["until"])

    async def test_permission_error_keeps_messages_for_later(self):
        self.graph.send_errors = [mc.GraphError(10, "Application does not have permission for this action")]
        raw = raw_conv("c1", [("m1", False, "Salom", 60)])
        self.assertEqual((await self.tick(raw)).get("error"), 1)
        self.assertEqual(self.store.status("m1"), "new")
        self.assertIn("permission", d._errors[-1][1])

    async def test_unknown_error_gives_up_after_three(self):
        self.graph.send_errors = [mc.GraphError(9999, "odd")] * 3
        raw = raw_conv("c1", [("m1", False, "Salom", 60)])
        self.assertEqual(await self.handle(raw), "retry")
        self.assertEqual(await self.handle(raw), "retry")
        self.assertEqual(await self.handle(raw), "unavailable")
        self.assertIn("Yuborib bo'lmadi", self.bot.sent[0][1])

    async def test_hourly_cap_per_conversation(self):
        for i in range(d.PER_HOUR):
            await self.store.store_messages("c1", [{"message_id": f"old{i}", "text": "?", "status": "replied"}])
            self.store.rows[f"old{i}"]["replied_at"] = NOW - timedelta(minutes=50 - i)
        raw = raw_conv("c1", [("m1", False, "Yana savol", 60)])
        self.assertEqual(await self.handle(raw), "throttled")
        self.ai.assert_not_called()
        self.assertEqual(self.graph.posts, [])
        self.assertEqual(len(self.bot.sent), len(ADMIN_IDS))
        self.assertEqual(await self.handle(raw, NOW + timedelta(minutes=1)), "throttled")
        self.assertEqual(len(self.bot.sent), len(ADMIN_IDS))                 # kartochka bir marta
        self.assertEqual(await self.handle(raw, NOW + timedelta(minutes=55)), "replied")

    async def test_tick_lock_and_off_switch(self):
        async with d._lock:
            self.assertEqual(await d.tick(self.bot, NOW), {"busy": 1})
        self.store.state["enabled"] = False
        self.assertEqual(await d.tick(self.bot, NOW), {"off": 1})


# ───────────────────────────── /ig_direct test ──────────────────────────────

class AdminTestCommandTest(Base):
    async def test_reads_conversations_and_sends_nothing(self):
        self.graph.convs = [raw_conv("c1", [("m1", False, "Salom", 60)])]
        text = await d.test_text()
        self.assertIn("✅ Direct suhbatlarini o'qiyapti: oxirgi 1 ta", text)
        self.assertIn("@shop.test", text)
        self.assertEqual(self.graph.posts, [])

    async def test_exact_meta_error_and_what_to_enable(self):
        self.graph.read_error = mc.GraphError(3, "Application does not have the capability to make this API call.")
        self.graph.perms = ("pages_show_list", "instagram_basic")
        text = await d.test_text()
        self.assertIn("[3] Application does not have the capability to make this API call.", text)
        self.assertIn("Allow access to messages", text)
        self.assertIn("instagram_manage_messages", text)
        self.assertIn("pages_messaging", text)
        self.assertEqual(self.graph.posts, [])

    async def test_no_token(self):
        with patch.object(mc, "_db_token", ""), patch.object(mc, "ENV_TOKEN", ""):
            text = await d.test_text()
        self.assertIn("/izoh_token", text)
        self.assertEqual(self.graph.calls, [])

    async def test_command_is_published(self):
        import keyboards
        self.assertIn("ig_direct", [c.command for c in keyboards.ADMIN_COMMANDS])


# ───────────────────────────── matn qoidalari ───────────────────────────────

class TextRulesTest(unittest.TestCase):
    def test_telegram_handles_become_links(self):
        self.assertEqual(d.telegram_links("Telegram botimiz @ketoshopbot orqali"),
                         "Telegram botimiz: https://t.me/ketoshopbot orqali")
        self.assertEqual(d.telegram_links("Retseptlar @ketoshop_uz da, buyurtma @ketoshopbot"),
                         "Retseptlar https://t.me/ketoshop_uz da, buyurtma https://t.me/ketoshopbot")
        self.assertEqual(d.telegram_links("Telegram kanalimiz @ketoshop_uz"),
                         "Telegram kanalimiz: https://t.me/ketoshop_uz")
        self.assertEqual(d.telegram_links("do'kon: t.me/ketoshopbot/shop"), "do'kon: https://t.me/ketoshopbot/shop")
        self.assertEqual(d.telegram_links("https://t.me/ketoshopbot/shop"), "https://t.me/ketoshopbot/shop")

    def test_finalize_dm(self):
        out = d.finalize_dm("Kokos uni bormi", "**Ha, bor!** Buyurtma Telegram botimiz @ketoshopbot da", "uz")
        self.assertEqual(out, "Bor! Buyurtma Telegram botimiz: https://t.me/ketoshopbot da")
        self.assertNotIn("@ketoshop", d.finalize_dm("x", "@ketoshopbot va @ketoshop_uz", "uz"))
        cyr = d.finalize_dm("Нархи канча", "Narxi 48 000 so'm. Telegram botimiz @ketoshopbot", "uz_cyr")
        self.assertEqual(cyr, "Нархи 48 000 сўм. Telegram ботимиз: https://t.me/ketoshopbot")

    def test_detect_lang(self):
        self.assertEqual(d.detect_lang("Assalomu alaykum, narxi qancha?"), "uz")
        self.assertEqual(d.detect_lang("Нархи канча?"), "uz_cyr")
        self.assertEqual(d.detect_lang("Қанча туради"), "uz_cyr")
        self.assertEqual(d.detect_lang("Здравствуйте, сколько стоит?"), "ru")

    def test_holding_text_has_links_not_handles(self):
        for lang in d.LANGS:
            text = d.holding_text(lang)
            self.assertIn("https://t.me/ketoshopbot", text)
            self.assertNotIn("@ketoshopbot", text)

    def test_rules_advice_first_and_full_links(self):
        r = d.rules()
        for must in ("AVVAL FOYDA", "faqat sotuvga yo'naltiraverma", "keto yoki PP bo'yicha tavsiya",
                     "shakar o'rniga eritritol", "bodom uni", "FAQAT haqiqatan yordam bersa",
                     "ko'pi bilan bitta yumshoq taklif", "mahsulotsiz va havolasiz", "Bosim yo'q",
                     "har xabarda EMAS", "https://t.me/ketoshopbot/shop", "Telegram botimiz: https://t.me/ketoshopbot",
                     "https://t.me/ketoshop_uz", "deb YOZMA", '"Ha," bilan boshlama', "agar sir bo'lmasa",
                     "Tibbiy va'da berma"):
            self.assertIn(must, r)
        self.assertNotIn("{", r)


# ───────────────────────────── webhook va hisobot ───────────────────────────

class WebhookAndReportTest(unittest.TestCase):
    def test_webhook_messages(self):
        msg = {"object": "instagram", "entry": [{"id": IG_ID, "messaging": [
            {"sender": {"id": "5550001"}, "recipient": {"id": IG_ID}, "message": {"mid": "x", "text": "Salom"}}]}]}
        echo = {"object": "instagram", "entry": [{"messaging": [{"message": {"mid": "y", "is_echo": True}}]}]}
        comment = {"object": "instagram", "entry": [{"changes": [{"field": "comments", "value": {"id": "1"}}]}]}
        self.assertTrue(d.webhook_has_messages(msg))
        self.assertFalse(d.webhook_has_messages(echo))
        self.assertFalse(d.webhook_has_messages(comment))
        self.assertFalse(d.webhook_has_messages({"object": "page", "entry": msg["entry"]}))
        d._kick.clear()
        d.on_webhook(msg)
        self.assertTrue(d._kick.is_set())
        d._kick.clear()

    def test_summary_line_and_daily_report(self):
        self.assertIsNone(d.summary_line({}))
        s = {"received": 9, "conversations": 5, "replies": 7, "to_human": 2, "spam": 1, "missed": 0, "pending": 0}
        line = d.summary_line(s)
        self.assertEqual(line, "📩 <b>Instagram Direct: bugun 5 ta suhbatga javob berildi</b> (7 ta javob) · "
                               "👤 odamga topshirildi: 2 ta")
        import targets
        snap = {"date": date(2026, 11, 16), "observed_at": datetime(2026, 11, 16, 20, 0), "sales": 9,
                "daily_target": 10, "sales_left": 1, "day_revenue": 0, "day_booked_value": 0,
                "day_delivered_revenue": 0, "day_profit": 0, "month_profit_usd": 100, "monthly_target_usd": 1000,
                "month_profit": 1_250_000, "monthly_target_uzs": 12_500_000, "usd_rate": 12500,
                "usd_rate_date": "16.11.2026", "remaining_uzs": 11_250_000, "remaining_usd": 900, "days_left": 14,
                "needed_per_day_usd": 47, "month_orders": 120, "month_booked_value": 0, "month_revenue": 0,
                "ig_direct": s}
        with patch("ai_sales.is_enabled", return_value=False):
            self.assertIn("Instagram Direct: bugun 5 ta suhbatga", targets.build_message(snap, 20))
            self.assertNotIn("Instagram Direct", targets.build_message(snap, 13))


# ───────────────────────── haqiqiy PostgreSQL (ixtiyoriy) ───────────────────

PG_URL = os.getenv("IG_DM_PG_URL", "").strip()


@unittest.skipUnless(PG_URL, "IG_DM_PG_URL berilmagan — haqiqiy Postgres tekshiruvi o'tkazildi")
class PostgresTest(unittest.TestCase):
    def test_round_trip(self):
        asyncio.run(self._round_trip())

    async def _round_trip(self):
        import asyncpg
        schema = f"igdm_test_{os.getpid()}"
        admin = await asyncpg.connect(PG_URL)
        await admin.execute(f"CREATE SCHEMA {schema}")
        saved = database.pool, d._table_ready
        pool = await asyncpg.create_pool(PG_URL, min_size=1, max_size=2, server_settings={"search_path": schema})
        database.pool, d._table_ready = pool, False
        try:
            now = d._utcnow().replace(microsecond=0)
            self.assertTrue((await d.get_state())["enabled"])
            await d.set_enabled(False)
            self.assertFalse((await d.get_state())["enabled"])
            await d.set_enabled(True)
            await d.note_poll("[4] limit")
            await d.note_poll()
            st = await d.get_state()
            self.assertEqual(st["last_error"], "[4] limit")
            self.assertIsNotNone(st["last_ok_at"])

            rows = [{"message_id": "m1", "from_id": "u1", "username": "a", "text": "Salom", "created_at": now},
                    {"message_id": "m2", "from_id": "u1", "username": "a", "text": "Narxi?", "created_at": now}]
            await d.store_messages("c1", rows)
            await d.store_messages("c1", [dict(rows[0], text="o'zgardi", status="human")])   # takror — tegilmaydi
            got = await d.statuses(["m1", "m2", "nope"])
            self.assertEqual({k: v["status"] for k, v in got.items()}, {"m1": "new", "m2": "new"})
            self.assertEqual(sorted(await d.mark(["m1", "m2"], "sending", ("new",), claimed_at=now)), ["m1", "m2"])
            self.assertEqual(await d.mark(["m1", "m2"], "sending", ("new",)), [])               # ikkinchi egallash yo'q
            self.assertEqual(sorted(await d.mark(["m1", "m2"], "replied", ("sending",), reply_text="Javob",
                                                 replied_at=now, intent="salom", catalog_sent=True)), ["m1", "m2"])
            self.assertEqual(await d.replies_since("c1", now - timedelta(hours=1)), 1)
            self.assertTrue(await d.catalog_recent("c1", now - timedelta(hours=6)))
            self.assertFalse(await d.catalog_recent("c1", now + timedelta(minutes=1)))
            self.assertTrue(await d.had_reply("c1"))
            self.assertFalse(await d.had_reply("c2"))
            await d.store_messages("c2", [{"message_id": "m3", "text": "Spam", "created_at": now}])
            await d.mark(["m3"], "held", ("new",), replied_at=now + timedelta(seconds=1))
            await d.store_messages("c3", [{"message_id": "m4", "text": "?", "created_at": now}])
            s = await d.day_stats()
            self.assertEqual((s["received"], s["conversations"], s["replies"], s["to_human"], s["pending"]),
                             (4, 2, 2, 1, 1))
            recent = await d.recent_replies(5)
            self.assertEqual(len(recent), 2)
            self.assertEqual(recent[0]["status"], "held")
        finally:
            await pool.close()
            database.pool, d._table_ready = saved
            await admin.execute(f"DROP SCHEMA {schema} CASCADE")
            await admin.close()


if __name__ == "__main__":
    unittest.main()
