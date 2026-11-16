"""Mijoz portreti (customer_portrait.py, name_gender.py) — Telegram va
bazasiz. Hech qanday xabar haqiqatan yuborilmaydi; ismlar — keng tarqalgan
umumiy ismlar, haqiqiy mijoz ma'lumoti emas.

Haqiqiy PostgreSQL da tekshirish (ixtiyoriy, CI da o'tkazib yuboriladi):
    PORTRAIT_PG_URL=postgresql://postgres@127.0.0.1:55432/postgres \
        python -m unittest tests.test_customer_portrait
Test o'z sxemasini yaratadi va oxirida o'chiradi.
"""
import asyncio
import os
import re
import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-used")

import ai_memory
import ai_sales
import customer_portrait as cp
import database
import name_gender
import subscription_gate
from ai_provider import ToolCall, Turn
from config import ADMIN_IDS


def run(coro):
    return asyncio.run(coro)


# ───────────────────────────── ismdan jins ──────────────────────────────────

# Ro'yxatdagi va qo'shimchadan topiladigan keng tarqalgan ismlar.
FEMALE = """Dilnoza Malika Nigora Gulnora Oysha Mohinur Kamola Zarina Feruza Shahnoza Madina Laylo
Nilufar Sevara Nodira Dildora Umida Zilola Hilola Ezoza Diyora Gulchehra Durdona Marjona Sitora
Maftuna Iroda Barno Lobar Yulduz Asal Shirin Ra'no Gulbahor Mehribon Zebo Shahlo Komila Jamila
Robiya Xadicha Fotima Zaynab Maryam Ruxsora Muxlisa Mohira Nozima Gavhar Oydin Sabina Saida
Saidaxon Robiyaxon Malikajon Tursunoy Barchinoy Mehriniso Shahribonu Nodirabegim Oygul Gulsanam
Anna Mariya Olga Elena Yelena Natalya Tatyana Irina Svetlana Ekaterina Yuliya Anastasiya Oksana
Lyudmila Galina Lyubov Asel Aigul Viktoriya Kristina Alina Polina Darya Sofiya Diana Karina
Дилноза Шахноза Мохинур Гулнора Мария Наталья Юлия Любовь Ольга Камила Гулчехра Нигора Феруза""".split()

MALE = """Aziz Sardor Jasur Bobur Otabek Nodir Akmal Anvar Rustam Jamshid Sherzod Bekzod Farrux
Shoxrux Ulug'bek Doniyor Javohir Islom Ibrohim Abdulla Muhammad Alisher Temur Farhod Dilshod
Ravshan Zafar Botir Bahodir Ilhom Komil Laziz Mansur Umid Xurshid Yusuf Jahongir Shavkat Davron
Abbos Hasan Nodirjon Akbarjon Azizxon Ilhomxon Sardorbek Asilbek Ozodbek Nuriddin Kamoliddin
Jaloliddin Hikmatullo Ne'matulla Toshboy Eshqul Elyor Diyor Bahtiyor Eldor Behzod Shahzod
Muhammadali Nurali Shoxjahon Hamza Musa Mustafo Yahyo Toha Isa Ilyos Aleksandr Aleksey Andrey
Anton Artyom Dmitriy Sergey Nikolay Igor Ivan Kirill Maksim Mikhail Oleg Pavel Roman Ruslan
Nikita Ilya Yevgeniy Vladimir Denis Timur Marat Damir
Жасур Шерзод Улуғбек Ҳасан Хуршид Мухаммад Сергей Дмитрий Илья Никита Алексей Отабек Ўткир""".split()

# Ikkalasida ham bo'ladigan yoki ism emas — taxmin qilinmasin.
UNKNOWN = "Sasha Zhenya Iqbol Navro'z Mijoz Admin Keto 😊 John 12345".split()

# Ro'yxatlarda YO'Q ismlar — faqat qo'shimcha qoidasi ishlaydi. Bu yerda
# "noma'lum" qabul qilinadi (taxmin qilmagani yaxshi), xato — yo'q.
HELD_OUT_F = """Mavluda Dilfuza Nasiba Matluba Gulnoza Shoira Sayyora Nargiza Xurshida Dilshoda Ozoda
Ziyoda Zamira Nafisa Gulmira Yorqinoy Kumushoy Ra'noxon Charosxon Shaxzoda Sarvinoz Latofat
Mehrinoz Muqaddam Gulasal Madinabonu Sarvara Muattarxon Oydinoy Shodiyona Mubina Munisa Nigina
Farangiz Mahliyo Gulzoda Dilbarxon Rohila Sabrina Aziza Xilola Nozanin Komilaxon Moxinur Elina
Veronika Zulfiya Gulsara""".split()
HELD_OUT_M = """Islombek Fazliddin Sirojiddin Zikrillo Xayrullo Jamoliddin Begzod Mirshod Dostonbek
Jonibek Ozodjon Hayrulla Ibrohimjon Elmurod Bekmurod Ergashboy Rustambek Asadbek Sanjarbek
Shermuhammad Abdusattor Mirjalol Nurmuhammad Abduqodir Abdulhamid Shohjahon Muhammadyusuf
Bekhruz Javlonbek Sarvarbek Lazizjon Otabekjon Xondamir Shukurullo Nurillo Saidmurod Ulugbek
Jasurbek Mironshoh Ixtiyor Shahriyor Sirojbek Dmitri Arslan Bahrom Akobir Abdurashid Muslimbek
Sobirjon""".split()


class NameGenderTest(unittest.TestCase):
    def test_common_names(self):
        wrong = [(n, exp, name_gender.infer(n)) for exp, names in (("f", FEMALE), ("m", MALE))
                 for n in names if name_gender.infer(n)[0] != exp]
        self.assertEqual(wrong, [])

    def test_ambiguous_and_non_names_stay_unknown(self):
        for name in UNKNOWN:
            self.assertEqual(name_gender.infer(name), ("unknown", 0.0), name)
        self.assertEqual(name_gender.infer(""), ("unknown", 0.0))
        self.assertEqual(name_gender.infer(None), ("unknown", 0.0))

    def test_names_outside_the_lists_are_never_guessed_wrong(self):
        decided = wrong = 0
        for expected, names in (("f", HELD_OUT_F), ("m", HELD_OUT_M)):
            for name in names:
                got, _ = name_gender.infer(name)
                if got == "unknown":
                    continue
                decided += 1
                if got != expected:
                    wrong += 1
        self.assertEqual(wrong, 0)
        self.assertGreaterEqual(decided / (len(HELD_OUT_F) + len(HELD_OUT_M)), 0.8)

    def test_suffix_base_honorific_and_surname(self):
        self.assertEqual(name_gender.infer("Azizxon")[0], "m")         # asosi — Aziz
        self.assertEqual(name_gender.infer("Saidaxon")[0], "f")        # asosi — Saida
        self.assertEqual(name_gender.infer("Shoxjahon")[0], "m")       # -jahon, -xon emas
        self.assertEqual(name_gender.infer("Aziz aka"), ("m", 0.95))
        self.assertEqual(name_gender.infer("Dilnoza opa"), ("f", 0.95))
        self.assertEqual(name_gender.infer("Karimov Aziz")[0], "m")
        self.assertEqual(name_gender.infer("Sasha Ivanova")[0], "f")   # ism noaniq — familiyadan
        self.assertEqual(name_gender.infer("Malika Anvar qizi")[0], "f")
        self.assertEqual(name_gender.infer("Ivan Petrovich")[0], "m")
        self.assertEqual(name_gender.infer("ДИЛНОЗА")[0], "f")
        self.assertEqual(name_gender.infer("Shahnoza")[0], name_gender.infer("Шахноза")[0])

    def test_first_word_only(self):
        self.assertEqual(name_gender.first_word("  Dilnoza Karimova "), "Dilnoza")
        self.assertEqual(name_gender.first_word(""), "")


# ─────────────────────────── qiymat va reja ─────────────────────────────────

NOW = datetime(2026, 11, 15, 10, 0)


class ValuesTest(unittest.TestCase):
    def test_clean_name(self):
        self.assertEqual(cp.clean_name("  «Dilnoza» "), "Dilnoza")
        for bad in ("", "998901234567", "@user", "https://x.uz", "bir ikki uch tort", "!!!"):
            with self.assertRaises(cp.Invalid, msg=bad):
                cp.clean_name(bad)

    def test_age_and_group(self):
        self.assertEqual(cp.clean_age("28"), 28)
        for bad in ("yigirma", 5, 140, None):
            with self.assertRaises(cp.Invalid):
                cp.clean_age(bad)
        self.assertEqual([cp.age_group(a) for a in (16, 18, 28, 40, 50, 60, 70)],
                         ["18 gacha", "18–24", "25–34", "35–44", "45–54", "55–64", "65+"])

    def test_goals_only_from_the_list(self):
        self.assertEqual(cp.clean_goals(["ozish", "diabet", "Keto", "ozish"]), ["ozish", "keto"])
        self.assertEqual(cp.clean_goals("sport"), ["sport"])


class PlanChangesTest(unittest.TestCase):
    def test_name_sets_collected_at_and_infers_gender_from_it(self):
        out = cp.plan_changes({}, name="Dilnoza", now=NOW)
        self.assertEqual(out["display_name"], "Dilnoza")
        self.assertEqual(out["name_collected_at"], NOW)
        self.assertEqual((out["gender"], out["gender_source"]), ("f", "name"))
        self.assertEqual(out["gender_collected_at"], NOW)
        self.assertGreaterEqual(out["gender_confidence"], 0.7)

    def test_telegram_name_is_the_fallback_for_gender(self):
        out = cp.plan_changes({}, age=34, telegram_name="Sardor Aliyev", now=NOW)
        self.assertEqual((out["age"], out["age_group"], out["gender"]), (34, "25–34", "m"))
        self.assertNotIn("display_name", out)

    def test_nothing_new_means_nothing_written(self):
        current = {"display_name": "Dilnoza", "age": 28, "goals": ["ozish"], "gender": "f",
                   "gender_source": "name"}
        self.assertEqual(cp.plan_changes(current, name="Dilnoza", age=28, goals=["ozish"], now=NOW), {})

    def test_goals_are_merged(self):
        out = cp.plan_changes({"goals": ["keto"], "gender": "f"}, goals=["ozish", "keto"], now=NOW)
        self.assertEqual(out["goals"], ["ozish", "keto"])
        self.assertEqual(out["goals_collected_at"], NOW)

    def test_stated_gender_wins_and_is_not_overwritten_by_a_name(self):
        out = cp.plan_changes({}, stated_gender="m", now=NOW)
        self.assertEqual((out["gender"], out["gender_source"], out["gender_confidence"]), ("m", "stated", 1.0))
        later = cp.plan_changes({"gender": "m", "gender_source": "stated"}, name="Malika", now=NOW)
        self.assertNotIn("gender", later)

    def test_ambiguous_name_keeps_gender_unknown(self):
        out = cp.plan_changes({}, name="Sasha", now=NOW)
        self.assertNotIn("gender", out)


# ─────────────────── qachon so'rash mumkin (kodda) ──────────────────────────

class AskRulesTest(unittest.TestCase):
    def test_name_first_then_age_each_only_once(self):
        self.assertEqual(cp.pick_question(None), "name")
        self.assertEqual(cp.pick_question({"asked_name_at": NOW}), "age")        # javob bermadi — qayta yo'q
        self.assertEqual(cp.pick_question({"display_name": "Aziz"}), "age")
        self.assertIsNone(cp.pick_question({"asked_name_at": NOW, "asked_age_at": NOW}))
        self.assertIsNone(cp.pick_question({"display_name": "Aziz", "age": 30}))
        self.assertIsNone(cp.pick_question({"opted_out_at": NOW}))

    def test_never_in_the_first_reply_and_spaced_out(self):
        self.assertFalse(cp.ask_allowed({"turns": 1}))
        self.assertTrue(cp.ask_allowed({"turns": 2}))
        self.assertFalse(cp.ask_allowed({"turns": 3, "portrait_asked_turn": 2}))
        self.assertTrue(cp.ask_allowed({"turns": 2 + cp.ASK_GAP_TURNS, "portrait_asked_turn": 2}))
        self.assertFalse(cp.ask_allowed({"turns": 5, "portrait_done": True}))

    def test_not_during_checkout(self):
        for busy in ({"card": True}, {"keyboard": "location"}, {"awaiting_cheque": 123}):
            self.assertFalse(cp.ask_allowed({"turns": 4, **busy}), busy)

    def test_switch(self):
        with patch.object(cp, "ASK_ENABLED", False):
            self.assertFalse(cp.ask_allowed({"turns": 4}))

    def test_hint_is_one_question_and_never_says_it_is_required(self):
        for field in cp.FIELDS:
            hint = cp.ask_hint(field)
            self.assertIn("BITTA", hint)
            self.assertIn("kerak dema", hint)
            self.assertNotIn("jins", hint.lower())


# Egasi, 2026-11-16: "agar sir bo'lmasa -> bunday shubhali gaplar yozmasin".
BANNED = ("agar sir bo'lmasa", "agar qarshi bo'lmasangiz", "majburiy emas", "ma'lumotlaringiz xavfsiz",
          "shaxsiy ma'lumot", "ixtiyoriy")


class NaturalToneTest(unittest.TestCase):
    def _texts(self):
        yield "prompt", ai_sales._sales_rules()
        for field in cp.FIELDS:
            yield f"hint:{field}", cp.ask_hint(field)
        yield "tool", next(t for t in ai_sales._TOOL_SPECS if t["name"] == "portret_yoz")["description"]
        yield "profile", "\n".join(cp.profile_lines({"display_name": "Aziz", "age": 30, "goals": ["keto"]}))

    def test_prompt_and_hints_have_no_suspicious_phrases(self):
        for where, text in self._texts():
            low = text.lower().replace("ʻ", "'").replace("’", "'")
            for phrase in BANNED:
                self.assertNotIn(phrase, low, where)

    def test_examples_in_the_prompt_are_plain_questions(self):
        rules = ai_sales._sales_rules()
        self.assertIn("Sizga qanday murojaat qilaylik?", rules)
        self.assertIn("Yoshingizni bilsak, sizga mosrog'ini tavsiya qila olamiz 😊", rules)
        self.assertIn("Если подскажете ваш возраст, сможем посоветовать то, что подойдёт лучше 😊", rules)
        self.assertIn("so'zma-so'z takrorlama", rules)
        self.assertIn("Kim uchun olyapsiz — o'zingizgami yoki oilagami?", rules)
        self.assertIn("Yoshingizni bilsak", cp.ask_hint("age"))

    def test_hedges_are_cut_from_the_reply(self):
        self.assertEqual(cp.plain_tone("Yoshingiz nechada, agar sir bo'lmasa?"), "Yoshingiz nechada?")
        self.assertEqual(cp.plain_tone("Agar qarshi bo'lmasangiz, ismingiz nima?"), "Ismingiz nima?")
        self.assertEqual(cp.plain_tone("Сколько вам лет, если не секрет?"), "Сколько вам лет?")
        self.assertEqual(cp.plain_tone("Bodom uni bor 😊\nShaxsiy ma'lumotlaringiz xavfsiz. Yana nima kerak?"),
                         "Bodom uni bor 😊\nYana nima kerak?")

    def test_disclaimer_dropped_only_next_to_a_profile_question(self):
        asked = cp.drop_profile_questions("Bor 😊\nYoshingiz nechada (majburiy emas)? Bu ixtiyoriy.", "age")
        self.assertEqual(asked, "Bor 😊\nYoshingiz nechada?")
        plain = "Keto tangachalarni ishlatish majburiy emas."
        self.assertEqual(cp.drop_profile_questions(plain, None), plain)


class DropQuestionsTest(unittest.TestCase):
    def test_question_without_permission_is_removed(self):
        reply = "Bodom uni bor, 89 000 so'm 😊\nAytgancha, sizga qanday murojaat qilaylik?"
        self.assertEqual(cp.drop_profile_questions(reply, None), "Bodom uni bor, 89 000 so'm 😊")
        self.assertEqual(cp.drop_profile_questions(reply, "name"), reply)

    def test_only_one_question_and_only_the_allowed_one(self):
        reply = ("Psillium bor 😊\nSizga qanday murojaat qilaylik? Yoshingiz nechada?\n"
                 "Ismingiz nima?")
        self.assertEqual(cp.drop_profile_questions(reply, "name"),
                         "Psillium bor 😊\nSizga qanday murojaat qilaylik?")
        self.assertEqual(cp.drop_profile_questions(reply, "age"), "Psillium bor 😊\nYoshingiz nechada?")

    def test_soft_statement_ask_counts_as_a_question(self):
        soft = "Bodom uni bor 😊\nYoshingizni bilsak, sizga mosrog'ini tavsiya qila olamiz 😊"
        self.assertEqual(cp.drop_profile_questions(soft, "age"), soft)
        self.assertEqual(cp.drop_profile_questions(soft, None), "Bodom uni bor 😊")
        ru = "Есть 😊\nЕсли подскажете ваш возраст, сможем посоветовать то, что подойдёт лучше 😊"
        self.assertEqual(cp.drop_profile_questions(ru, "name"), "Есть 😊")
        plain = "Yoshingizga mos keladi, bemalol ishlatavering."
        self.assertEqual(cp.drop_profile_questions(plain, None), plain)

    def test_other_questions_and_order_lines_are_untouched(self):
        reply = "Bolangiz necha yoshda? Shunga qarab tavsiya qilamiz.\nIsm: Bobur"
        self.assertEqual(cp.drop_profile_questions(reply, None), reply)
        self.assertEqual(cp.drop_profile_questions("Как к вам обращаться?", "age"), "Как к вам обращаться?")


# ─────────────────────── baza (soxta ulanish bilan) ─────────────────────────

class _Tx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, row=None, flag=None):
        self.row = row
        self.flag = flag
        self.calls = []

    def transaction(self):
        return _Tx()

    async def execute(self, sql, *args):
        self.calls.append((" ".join(sql.split()), args))
        return "DELETE 0"

    async def fetchrow(self, sql, *args):
        self.calls.append((" ".join(sql.split()), args))
        return self.row

    async def fetchval(self, sql, *args):
        self.calls.append((" ".join(sql.split()), args))
        return self.flag

    async def fetch(self, sql, *args):
        self.calls.append((" ".join(sql.split()), args))
        return []


class _FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False
        return _Ctx()


class _PoolCase(unittest.TestCase):
    def use(self, conn):
        saved = database.pool, cp._table_ready, ai_memory._table_ready
        database.pool = _FakePool(conn)
        cp._table_ready = ai_memory._table_ready = True
        self.addCleanup(self._restore, saved)
        return conn

    @staticmethod
    def _restore(saved):
        database.pool, cp._table_ready, ai_memory._table_ready = saved

    @staticmethod
    def writes(conn):
        return [c for c in conn.calls if c[0].startswith(("INSERT", "UPDATE", "DELETE"))]


class StorageTest(_PoolCase):
    def test_save_new_portrait_upserts_only_changed_columns(self):
        conn = self.use(_FakeConn(row=None))
        result = run(cp.save(5, name="Dilnoza", age=28, goals=["ozish"], telegram_name="X"))
        self.assertEqual(result, {"saved": ["name", "age", "goals", "gender"], "opted_out": False})
        sql, args = self.writes(conn)[0]
        self.assertIn("ON CONFLICT (user_id) DO UPDATE SET display_name = EXCLUDED.display_name", sql)
        self.assertEqual(args[0], 5)
        self.assertIn("Dilnoza", args)
        self.assertIn(28, args)
        self.assertIn("f", args)

    def test_opted_out_customer_is_never_written(self):
        conn = self.use(_FakeConn(row={"opted_out_at": NOW}))
        self.assertEqual(run(cp.save(5, name="Dilnoza")), {"saved": [], "opted_out": True})
        self.assertEqual(self.writes(conn), [])

    def test_invalid_values_raise_before_the_database(self):
        conn = self.use(_FakeConn())
        with self.assertRaises(cp.Invalid):
            run(cp.save(5, age=300))
        with self.assertRaises(cp.Invalid):
            run(cp.save(5))
        self.assertEqual(conn.calls, [])

    def test_claim_marks_the_question_asked_at_once(self):
        conn = self.use(_FakeConn(row=None))
        self.assertEqual(run(cp.claim_question(5)), "name")
        sql, args = self.writes(conn)[0]
        self.assertIn("asked_name_at", sql)
        self.assertIn("COALESCE(customer_portrait.asked_name_at", sql)
        conn.row = {"asked_name_at": NOW}
        self.assertEqual(run(cp.claim_question(5)), "age")
        conn.row = {"asked_name_at": NOW, "asked_age_at": NOW}
        conn.calls.clear()
        self.assertIsNone(run(cp.claim_question(5)))
        self.assertEqual(self.writes(conn), [])

    def test_forget_clears_fields_opts_out_and_drops_ai_notes(self):
        conn = self.use(_FakeConn())
        with patch.object(ai_memory, "forget", AsyncMock(return_value=3)) as forget:
            self.assertEqual(run(cp.forget(5)), {"notes": 3})
        forget.assert_awaited_once_with(5)
        sql, args = self.writes(conn)[0]
        self.assertIn("display_name = NULL", sql)
        self.assertIn("goals = '{}'", sql)
        self.assertIn("opted_out_at = EXCLUDED.opted_out_at", sql)

    def test_memory_note_is_not_written_after_opt_out(self):
        conn = self.use(_FakeConn(flag=1))
        self.assertFalse(run(ai_memory.remember(5, "qiziqish", "Bodom uni")))
        self.assertEqual(self.writes(conn), [])
        conn.flag = None
        self.assertTrue(run(ai_memory.remember(5, "qiziqish", "Bodom uni")))
        self.assertTrue(any(c[0].startswith("INSERT INTO ai_customer_notes") for c in conn.calls))


# ──────────────────────── AI ga beriladigan profil ──────────────────────────

class ProfileTest(unittest.TestCase):
    PORTRAIT = {"display_name": "Aziz", "age": 30, "age_group": "25–34", "goals": ["keto", "sport"],
                "gender": "m", "gender_source": "name", "gender_confidence": 0.97}

    def test_ai_gets_name_age_goals_but_not_gender(self):
        text = ai_memory.profile_text({"full_name": "Aziz Karimov"}, "uz", [], [], None, None,
                                      portrait=self.PORTRAIT)
        self.assertIn("murojaat ismi «Aziz»", text)
        self.assertIn("yoshi 30 (25–34)", text)
        self.assertIn("maqsadi: keto, sport", text)
        self.assertNotIn("erkak", text)
        self.assertNotIn("jinsi", text)
        self.assertNotIn("ISMI BILAN MUROJAAT QILMA", text)

    def test_admin_card_shows_gender_with_source(self):
        text = ai_memory.profile_text(None, "uz", [], [], None, None, portrait=self.PORTRAIT, admin=True)
        self.assertIn("jinsi: erkak (ismdan, ishonch 0.97)", text)

    def test_without_a_portrait_the_old_rule_stays(self):
        text = ai_memory.profile_text({"full_name": "Aziz"}, "uz", [], [], None, None)
        self.assertIn("ISMI BILAN MUROJAAT QILMA", text)
        self.assertNotIn("PORTRET", text)

    def test_opted_out_tells_the_ai_not_to_ask(self):
        lines = cp.profile_lines({"opted_out_at": NOW})
        self.assertIn("so'rama", lines[0])


# ───────────────────────── AI suhbati bilan birga ───────────────────────────

class _FakeProvider:
    name, model = "fake", "fake-model"

    def __init__(self, turns):
        self._turns = list(turns)
        self.calls = []

    async def step(self, state, rules, catalog, tools, *, user=None, results=None,
                   max_tokens=800, history_limit=40):
        self.calls.append({"user": user, "results": results})
        return self._turns.pop(0)


def _message(user_id=901):
    user = NS(id=user_id, full_name="Test Xaridor", first_name="Test", username=None, is_bot=False)
    return NS(text="", from_user=user, chat=NS(id=user_id, type="private"), bot=None, answer=AsyncMock())


class ConversationTest(unittest.TestCase):
    def setUp(self):
        ai_sales._sessions.clear()
        self.saved = (ai_sales.PROVIDER, ai_sales._catalog_cache, ai_sales._dynamic_block,
                      ai_memory.build_profile, cp.get, cp.claim_question, cp.save)
        ai_sales._catalog_cache = (9e18, "10 | Bodom uni")
        ai_sales._dynamic_block = AsyncMock(return_value="KATALOG")
        ai_memory.build_profile = AsyncMock(return_value="[MIJOZ XOTIRASI]")
        cp.get = AsyncMock(return_value=None)
        cp.claim_question = AsyncMock(return_value="name")
        cp.save = AsyncMock(return_value={"saved": ["name", "gender"], "opted_out": False})

    def tearDown(self):
        (ai_sales.PROVIDER, ai_sales._catalog_cache, ai_sales._dynamic_block,
         ai_memory.build_profile, cp.get, cp.claim_question, cp.save) = self.saved
        ai_sales._sessions.clear()

    def test_first_reply_never_asks_second_may_ask_once(self):
        ai_sales.PROVIDER = provider = _FakeProvider([
            Turn(text="Assalomu alaykum! Bodom uni bor 😊 Sizga qanday murojaat qilaylik?"),
            Turn(text="Ha, bor 😊\nSizga qanday murojaat qilaylik? Yoshingiz nechada?"),
            Turn(text="Albatta 😊"),
        ])
        message = _message()
        first = run(ai_sales._respond(None, message, "bodom uni bormi"))
        self.assertNotIn("murojaat", first)                     # birinchi javobda — yo'q
        cp.claim_question.assert_not_awaited()
        self.assertNotIn("PORTRET", provider.calls[0]["user"])

        second = run(ai_sales._respond(None, message, "narxi qancha"))
        self.assertIn("SO'RASH IMKONI", provider.calls[1]["user"])
        self.assertEqual(second, "Ha, bor 😊\nSizga qanday murojaat qilaylik?")   # yosh savoli olindi

        run(ai_sales._respond(None, message, "rahmat"))         # oraliq to'lmagan — imkon yo'q
        self.assertEqual(cp.claim_question.await_count, 1)
        self.assertNotIn("PORTRET", provider.calls[2]["user"])

    def test_nothing_left_to_ask_stops_asking_the_database(self):
        cp.claim_question = AsyncMock(return_value=None)
        ai_sales.PROVIDER = _FakeProvider([Turn(text="a"), Turn(text="b"), Turn(text="c"),
                                           Turn(text="d"), Turn(text="e")])
        message = _message()
        for text in ("1", "2", "3", "4", "5"):
            run(ai_sales._respond(None, message, text))
        self.assertEqual(cp.claim_question.await_count, 1)

    def test_tool_saves_what_the_customer_said(self):
        ai_sales.PROVIDER = provider = _FakeProvider([
            Turn(text="Salom"),
            Turn(calls=[ToolCall("c1", "portret_yoz", {"ism": "Dilnoza", "maqsadlar": ["ozish"]})]),
            Turn(text="Dilnoza, sizga mosini topamiz 😊"),
        ])
        message = _message()
        run(ai_sales._respond(None, message, "salom"))
        reply = run(ai_sales._respond(None, message, "Dilnoza deb chaqiring, ozmoqchiman"))
        cp.save.assert_awaited_once_with(901, name="Dilnoza", age=None, goals=["ozish"],
                                         stated_gender=None, telegram_name="Test Xaridor")
        self.assertIn("OK: saqlandi", provider.calls[2]["results"][0].output)
        self.assertEqual(ai_sales._sessions[901]["address_name"], "Dilnoza")
        self.assertEqual(reply, "Dilnoza, sizga mosini topamiz 😊")

    def test_tool_rejects_bad_values(self):
        cp.save = AsyncMock(side_effect=cp.Invalid("yosh 10–100 oralig'ida bo'lishi kerak"))
        output = run(ai_sales._tool_portrait(_message(), {"yosh": 300}))
        self.assertTrue(output.startswith("Xato:"))


class AddressTest(unittest.TestCase):
    def test_chosen_name_stays_telegram_name_and_gendered_words_go(self):
        session = {"address_name": "Dilnoza"}
        user = NS(first_name="Dilnoza", full_name="Dilnoza Karimova")
        reply = ai_sales.finish_address("Rahmat, Dilnoza opa 😊 Karimova, buyurtmangiz tayyor.",
                                        user, "bodom uni bormi", session)
        self.assertIn("Dilnoza", reply)
        self.assertNotIn("opa", reply)
        self.assertNotIn("Karimova,", reply)

    def test_without_a_chosen_name_old_rule_applies(self):
        user = NS(first_name="Bobur", full_name="Bobur")
        self.assertEqual(ai_sales.finish_address("Rahmat, Bobur 😊", user, "salom", {}), "Rahmat 😊")

    def test_gendered_address_only_if_the_customer_used_it(self):
        user = NS(first_name="X", full_name="X")
        self.assertEqual(ai_sales.finish_address("Albatta, opa!", user, "salom", {}), "Albatta!")
        self.assertEqual(ai_sales.finish_address("Albatta, aka!", user, "rahmat aka", {}), "Albatta, aka!")


# ───────────────────────────── kunlik hisobot ───────────────────────────────

STATS = {"name_today": 4, "age_today": 2, "gender_name_today": 5, "gender_stated_today": 1,
         "goals_today": 3, "people_today": 6, "asked_name_today": 7, "asked_age_today": 3,
         "portraits": 20, "with_name": 12, "with_age": 6, "female": 11, "male": 7,
         "with_goals": 9, "opted_out": 1}
GOALS = [{"goal": "ozish", "n": 6}, {"goal": "keto", "n": 4}]
EXAMPLES = [
    {"display_name": "Dilnoza Karimova", "age": 28, "gender": "f", "gender_source": "name", "goals": ["ozish"]},
    {"display_name": None, "age": 41, "gender": "m", "gender_source": "stated", "goals": []},
    {"display_name": "Aziz", "age": None, "gender": "m", "gender_source": "name", "goals": ["keto", "sport"]},
]


class ReportTest(unittest.TestCase):
    def test_text(self):
        text = cp.report_text(date(2026, 11, 15), STATS, GOALS, EXAMPLES)
        for line in ("Mijoz portreti — 15.11.2026", "👤 Ism — 4", "🎂 Yosh — 2",
                     "🚻 Jins (ismdan) — 5 (+1 o'zi aytgan)", "🎯 Maqsad — 3",
                     "<b>Jami:</b> 20 ta mijozning portreti bor", "👤 Ism — 12 (60%)",
                     "🚻 Jins — 18 (90%): ayol 11 · erkak 7", "🎯 Maqsad — 9 (45%): ozish 6 · keto 4",
                     "🗑 Ma'lumotini o'chirganlar — 1",
                     "• Dilnoza, 28 yosh, ayol (ismdan), maqsad: ozish",
                     "• ismi aytilmagan, 41 yosh, erkak (o'zi aytgan)",
                     "• Aziz, erkak (ismdan), maqsad: keto, sport"):
            self.assertIn(line, text)
        self.assertNotIn("Karimova", text)          # faqat ism, familiyasiz

    def test_empty_day(self):
        zero = {k: 0 for k in STATS}
        text = cp.report_text(date(2026, 11, 15), zero, [], [])
        self.assertIn("<b>Jami:</b> 0 ta", text)
        self.assertIn("Bugun yangi ma'lumot yig'ilmadi.", text)

    def test_schedule_2330_tashkent(self):
        self.assertEqual(cp.seconds_until_report(datetime(2026, 11, 15, 23, 0)), 1800)
        self.assertEqual(cp.seconds_until_report(datetime(2026, 11, 15, 23, 45)), 0)   # qayta ishga tushsa
        self.assertEqual(cp.seconds_until_report(datetime(2026, 11, 16, 0, 0, 5)), 23 * 3600 + 1795)

    def test_sent_once_per_day_to_every_admin(self):
        bot = NS(send_message=AsyncMock())
        claim = AsyncMock(side_effect=[True, False])
        with patch.object(database, "claim_release_notes", claim), \
                patch.object(cp, "collect", AsyncMock(return_value=(STATS, GOALS, EXAMPLES))), \
                patch.object(cp, "SEND_DELAY", 0):
            self.assertTrue(run(cp.send_daily_report(bot, date(2026, 11, 15))))
            self.assertFalse(run(cp.send_daily_report(bot, date(2026, 11, 15))))
        claim.assert_any_await("portrait-report-2026-11-15")
        self.assertEqual(sorted(c.args[0] for c in bot.send_message.await_args_list),
                         sorted(set(ADMIN_IDS)))

    def test_failed_build_gives_the_day_back(self):
        bot = NS(send_message=AsyncMock())
        release = AsyncMock()
        with patch.object(database, "claim_release_notes", AsyncMock(return_value=True)), \
                patch.object(database, "release_release_notes", release), \
                patch.object(cp, "collect", AsyncMock(side_effect=RuntimeError("db"))):
            self.assertFalse(run(cp.send_daily_report(bot, date(2026, 11, 15))))
        release.assert_awaited_once_with("portrait-report-2026-11-15")
        bot.send_message.assert_not_awaited()


# ───────────────────────────── /malumotlarim ────────────────────────────────

PORTRAIT = {"display_name": "Aziz", "age": 30, "age_group": "25–34", "gender": "m",
            "gender_source": "name", "goals": ["keto"]}
NOTES = [{"kind": "interest", "text": "Bodom uni 500gr"}, {"kind": "recipe", "text": "x"},
         {"kind": "note", "text": "keto non <pishiradi>"}]


class MyDataTest(unittest.TestCase):
    def test_text_in_each_language(self):
        uz = cp.my_data_text(PORTRAIT, NOTES, "uz")
        for part in ("Murojaat: Aziz", "Yosh: 30 (25–34)", "Jins: erkak (ismingizdan taxmin)",
                     "Maqsadlar: keto", "• Bodom uni 500gr", "keto non &lt;pishiradi&gt;"):
            self.assertIn(part, uz)
        self.assertNotIn("• x", uz)                       # retsept hisobi ko'rsatilmaydi
        ru = cp.my_data_text(PORTRAIT, NOTES, "ru")
        self.assertIn("Обращение: Aziz", ru)
        self.assertIn("Пол: мужской (предположение по имени)", ru)
        self.assertIn("Цели: кето", ru)
        cyr = cp.my_data_text(PORTRAIT, NOTES, "uz_cyr")
        self.assertIn("Мурожаат", cyr)
        self.assertIsNone(re.search(r"Murojaat|Yosh:", cyr))

    def test_keyboard(self):
        kb = cp.my_data_keyboard(PORTRAIT, NOTES, "uz")
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "mydata:del")
        self.assertIsNone(cp.my_data_keyboard({}, [], "uz"))
        self.assertIn("Hech narsa", cp.my_data_text({}, [], "uz").replace("hech narsa", "Hech narsa"))
        opted = {"opted_out_at": NOW}
        self.assertEqual(cp.my_data_keyboard(opted, [], "uz").inline_keyboard[0][0].callback_data, "mydata:on")
        self.assertIn("o'chirgansiz", cp.my_data_text(opted, [], "uz"))

    def _patches(self):
        return (patch.object(cp, "get", AsyncMock(return_value=PORTRAIT)),
                patch.object(ai_memory, "notes", AsyncMock(return_value=NOTES)),
                patch.object(database, "get_user_language", AsyncMock(return_value="uz")))

    def test_command_shows_data_with_delete_button(self):
        message = NS(from_user=NS(id=901), answer=AsyncMock())
        p1, p2, p3 = self._patches()
        with p1, p2, p3:
            run(cp.cmd_my_data(message))
        text = message.answer.await_args.args[0]
        self.assertIn("Murojaat: Aziz", text)
        markup = message.answer.await_args.kwargs["reply_markup"]
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "mydata:del")

    def test_delete_asks_first_then_forgets(self):
        msg = NS(edit_text=AsyncMock(), answer=AsyncMock())
        callback = NS(from_user=NS(id=901), data="mydata:del", message=msg, answer=AsyncMock())
        forget = AsyncMock(return_value={"notes": 2})
        ai_sales._sessions[901] = {"address_name": "Aziz"}
        self.addCleanup(ai_sales._sessions.clear)
        p1, p2, p3 = self._patches()
        with p1, p2, p3, patch.object(cp, "forget", forget):
            run(cp.cb_my_data(callback))
            forget.assert_not_awaited()
            confirm = msg.edit_text.await_args.kwargs["reply_markup"]
            self.assertEqual(confirm.inline_keyboard[0][0].callback_data, "mydata:del_ok")
            callback.data = "mydata:del_ok"
            run(cp.cb_my_data(callback))
        forget.assert_awaited_once_with(901)
        self.assertIn("O'chirildi", msg.edit_text.await_args.args[0])
        session = ai_sales._sessions[901]
        self.assertNotIn("address_name", session)
        self.assertTrue(session["portrait_done"])
        self.assertIn("o'chirdi", session["note"])

    def test_gate_lets_the_command_through(self):
        self.assertTrue(subscription_gate._is_privacy_request(_tg_message("/malumotlarim")))
        self.assertTrue(subscription_gate._is_privacy_request(_tg_message("/malumotlarim@ketoshopbot")))
        self.assertFalse(subscription_gate._is_privacy_request(_tg_message("/savat")))


def _tg_message(text):
    from aiogram.types import Chat, Message, User
    return Message(message_id=1, date=datetime(2026, 11, 15), text=text,
                   chat=Chat(id=1, type="private"), from_user=User(id=1, is_bot=False, first_name="T"))


# ───────────────────── haqiqiy PostgreSQL (ixtiyoriy) ───────────────────────

PG_URL = os.getenv("PORTRAIT_PG_URL", "").strip()


@unittest.skipUnless(PG_URL, "PORTRAIT_PG_URL berilmagan — haqiqiy Postgres tekshiruvi o'tkazildi")
class PostgresTest(unittest.TestCase):
    """Yangi SQL haqiqiy Postgres da: jadval, upsert, so'rash belgisi,
    o'chirish, eslatmani to'xtatish va kunlik hisobot so'rovlari."""

    def test_round_trip(self):
        run(self._round_trip())

    async def _round_trip(self):
        import asyncpg
        schema = f"portrait_test_{os.getpid()}"
        admin = await asyncpg.connect(PG_URL)
        await admin.execute(f"CREATE SCHEMA {schema}")
        saved = database.pool, cp._table_ready, ai_memory._table_ready
        pool = await asyncpg.create_pool(PG_URL, min_size=1, max_size=2,
                                         server_settings={"search_path": schema})
        database.pool, cp._table_ready, ai_memory._table_ready = pool, False, False
        try:
            self.assertEqual(await cp.claim_question(11), "name")
            self.assertEqual(await cp.claim_question(11), "age")
            self.assertIsNone(await cp.claim_question(11))
            result = await cp.save(11, name="Dilnoza", age=28, goals=["ozish"], telegram_name="X")
            self.assertEqual(result["saved"], ["name", "age", "goals", "gender"])
            row = await cp.get(11)
            self.assertEqual((row["display_name"], row["age"], row["age_group"], row["gender"],
                              row["gender_source"], row["goals"]),
                             ("Dilnoza", 28, "25–34", "f", "name", ["ozish"]))
            await cp.save(11, goals=["keto"])
            self.assertEqual((await cp.get(11))["goals"], ["ozish", "keto"])
            await cp.save(12, age=40, telegram_name="Sardor")
            await cp.save(ADMIN_IDS[0], name="Admin")                     # hisobotga kirmaydi
            today = cp._now_tk().date()
            stats, goals, examples = await cp.collect(today)
            self.assertEqual((stats["portraits"], stats["name_today"], stats["age_today"],
                              stats["gender_name_today"], stats["asked_name_today"]), (2, 1, 2, 2, 1))
            self.assertEqual({g["goal"]: g["n"] for g in goals}, {"ozish": 1, "keto": 1})
            self.assertEqual(len(examples), 2)
            self.assertIn("Dilnoza, 28 yosh, ayol (ismdan), maqsad: ozish, keto",
                          cp.report_text(today, stats, goals, examples))

            await ai_memory.remember(11, "qiziqish", "Bodom uni")
            await cp.forget(11)
            row = await cp.get(11)
            self.assertIsNone(row["display_name"])
            self.assertEqual((row["gender"], row["goals"]), ("unknown", []))
            self.assertIsNotNone(row["opted_out_at"])
            self.assertEqual(await ai_memory.notes(11), [])
            self.assertFalse(await ai_memory.remember(11, "qiziqish", "Eritritol"))
            self.assertEqual((await cp.save(11, name="Dilnoza"))["opted_out"], True)
            self.assertIsNone(await cp.claim_question(11))
            stats, _, _ = await cp.collect(today)
            self.assertEqual((stats["portraits"], stats["opted_out"]), (1, 1))
            await cp.resume(11)
            self.assertIsNone((await cp.get(11))["opted_out_at"])
            await cp.clear(12)
            self.assertIsNone(await cp.get(12))
        finally:
            await pool.close()
            database.pool, cp._table_ready, ai_memory._table_ready = saved
            await admin.execute(f"DROP SCHEMA {schema} CASCADE")
            await admin.close()


if __name__ == "__main__":
    unittest.main()
