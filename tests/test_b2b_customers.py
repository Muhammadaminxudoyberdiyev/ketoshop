"""B2B mijozlar (egasi, 2026-11-15): optom buyurtma kiritishda saqlangan
mijozlar tugma bo'lib chiqadi, «➕ Yangi mijoz» ism va raqam bilan saqlanadi."""
import asyncio
import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import database  # noqa: E402
import handlers.admin as admin  # noqa: E402

ADMIN = 4242
CUSTOMERS = [{"id": 1, "name": "Shirin Non MCHJ", "phone": "+998901112233", "address": "Toshkent, Yunusobod"},
             {"id": 2, "name": "Ali aka", "phone": "+998935556677", "address": None}]


class FakeState:
    def __init__(self, **data):
        self.data, self.state = dict(data), None

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kw):
        self.data.update(kw)

    async def set_state(self, s):
        self.state = s

    async def clear(self):
        self.data, self.state = {}, None


def message(text=""):
    return NS(text=text, from_user=NS(id=ADMIN), answer=AsyncMock(), edit_text=AsyncMock(),
              chat=NS(id=ADMIN))


def callback(data):
    msg = message()
    return NS(data=data, from_user=NS(id=ADMIN), message=msg, answer=AsyncMock(), bot=NS())


def run(coro):
    return asyncio.run(coro)


class KeyboardTest(unittest.TestCase):
    def test_names_as_buttons_and_new_customer(self):
        kb = admin.b2b_customer_keyboard(CUSTOMERS, "uz")
        datas = [b.callback_data for row in kb.inline_keyboard for b in row]
        texts = [b.text for row in kb.inline_keyboard for b in row]
        self.assertEqual(datas[:2], ["b2bc:pick:1", "b2bc:pick:2"])
        self.assertIn("👤 Shirin Non MCHJ", texts)
        self.assertIn("b2bc:new", datas)
        self.assertIn("➕ Yangi mijoz", texts)
        self.assertIn("admin_panel", datas)

    def test_pages_of_twenty(self):
        many = [{"id": i, "name": f"Mijoz {i}"} for i in range(1, 46)]
        first = [b.callback_data for row in admin.b2b_customer_keyboard(many, "uz", 0).inline_keyboard for b in row]
        self.assertEqual(sum(d.startswith("b2bc:pick:") for d in first), 20)
        self.assertIn("b2bc:page:1", first)
        last = [b.callback_data for row in admin.b2b_customer_keyboard(many, "uz", 2).inline_keyboard for b in row]
        self.assertEqual(sum(d.startswith("b2bc:pick:") for d in last), 5)
        self.assertIn("b2bc:page:1", last)
        self.assertNotIn("b2bc:page:3", last)


class FlowTest(unittest.TestCase):
    def setUp(self):
        for p in (patch.object(admin, "is_admin", lambda uid: True),
                  patch.object(admin, "get_user_language", AsyncMock(return_value="uz")),
                  patch.object(database, "list_b2b_customers", AsyncMock(return_value=CUSTOMERS)),
                  patch.object(database, "get_b2b_customer",
                               AsyncMock(side_effect=lambda cid: next((c for c in CUSTOMERS if c["id"] == cid), None))),
                  patch.object(admin, "_show_manual_category_picker", AsyncMock())):
            p.start()
            self.addCleanup(p.stop)

    def test_b2b_order_starts_with_the_customer_list(self):
        state, cb = FakeState(), callback("admin:b2b_order")
        run(admin.b2b_order_start(cb, state))
        self.assertEqual(state.state, admin.AdminStates.b2b_pick_customer)
        text = cb.message.edit_text.await_args.args[0]
        self.assertIn("Mijozni tanlang", text)
        kb = cb.message.edit_text.await_args.kwargs["reply_markup"]
        self.assertIn("b2bc:pick:1", [b.callback_data for row in kb.inline_keyboard for b in row])

    def test_picking_a_saved_customer_goes_to_products_with_name_and_phone(self):
        state = FakeState(lang="uz", order_type="b2b")
        run(admin.b2b_customer_pick(callback("b2bc:pick:1"), state))
        self.assertEqual((state.data["name"], state.data["phone"], state.data["b2b_customer_id"]),
                         ("Shirin Non MCHJ", "+998901112233", 1))
        self.assertEqual(state.state, admin.AdminStates.manual_pick_category)
        self.assertEqual(state.data["items"], [])
        admin._show_manual_category_picker.assert_awaited()

    def test_eritritol_with_saved_address_skips_to_quantity(self):
        state = FakeState(lang="uz", order_type="b2b_eritritol")
        cb = callback("b2bc:pick:1")
        run(admin.b2b_customer_pick(cb, state))
        self.assertEqual(state.state, admin.AdminStates.b2b_eritritol_quantity)
        self.assertIn("Yunusobod", cb.message.answer.await_args.args[0])

    def test_eritritol_without_address_asks_it_once_and_saves_it(self):
        state = FakeState(lang="uz", order_type="b2b_eritritol")
        run(admin.b2b_customer_pick(callback("b2bc:pick:2"), state))
        self.assertEqual(state.state, admin.AdminStates.b2b_eritritol_address)
        saved = AsyncMock()
        with patch.object(database, "set_b2b_customer_address", saved):
            run(admin.b2b_eritritol_address(message("Chilonzor 9"), state))
        saved.assert_awaited_once_with(2, "Chilonzor 9")
        self.assertEqual(state.state, admin.AdminStates.b2b_eritritol_quantity)   # phone known — not asked

    def test_new_customer_name_then_phone_is_saved(self):
        state = FakeState(lang="uz", order_type="b2b")
        cb = callback("b2bc:new")
        run(admin.b2b_customer_new(cb, state))
        self.assertEqual(state.state, admin.AdminStates.b2b_company)
        run(admin.b2b_company_name(message("Yangi Firma"), state))
        self.assertEqual(state.state, admin.AdminStates.b2b_new_phone)
        bad = message("123")
        run(admin.b2b_customer_phone(bad, state))
        self.assertIn("Raqam noto'g'ri", bad.answer.await_args.args[0])
        self.assertEqual(state.state, admin.AdminStates.b2b_new_phone)
        save = AsyncMock(return_value={"id": 9, "name": "Yangi Firma", "phone": "+998901234567", "address": None})
        with patch.object(database, "save_b2b_customer", save):
            run(admin.b2b_customer_phone(message("90 123 45 67"), state))
        save.assert_awaited_once_with("Yangi Firma", "+998901234567", None, ADMIN)
        self.assertEqual(state.data["b2b_customer_id"], 9)
        self.assertEqual(state.state, admin.AdminStates.manual_pick_category)

    def test_saving_links_the_order_to_the_customer(self):
        state = FakeState(lang="uz", order_type="b2b", name="Shirin Non MCHJ", phone="+998901112233",
                          b2b_customer_id=1, items=[{"name": "Bodom uni", "quantity": 2, "price": 90000}])
        add = AsyncMock(return_value=700)
        with patch.object(admin, "add_b2b_order", add), patch("order_admin_feed.manual_created", lambda *a, **k: None):
            run(admin.b2b_save(callback("b2bconfirm:yes"), state))
        kw = add.await_args.kwargs
        self.assertEqual((kw["phone"], kw["b2b_customer_id"], kw["company_name"]),
                         ("+998901112233", 1, "Shirin Non MCHJ"))

    def test_eritritol_save_keeps_the_customer_name(self):
        state = FakeState(lang="uz", order_type="b2b_eritritol", name="Ali aka", phone="+998935556677",
                          address="Chilonzor 9", b2b_customer_id=2, quantity=10, total=1_000_000, cost_per_kg=60000)
        add = AsyncMock(return_value=701)
        with patch.object(admin, "add_b2b_eritritol_order", add):
            run(admin.b2b_eritritol_confirm(callback("b2beritritol:yes"), state))
        kw = add.await_args.kwargs
        self.assertEqual((kw["customer_name"], kw["b2b_customer_id"]), ("Ali aka", 2))


if __name__ == "__main__":
    unittest.main()
