"""Retseptlar navbati (2026-11-13): yangi retseptlar 15.11 dan tartib bilan,
har slotda bittadan; rasmi yo'q retsept saytga ham, kanalga ham chiqmaydi —
o'sha kuni takroriy retsept chiqadi, adminga esa «takroriy» deyiladi.
Yangi 15 retsept kontenti: uz + ru to'liq, har bir do'kon masallig'i faol
mahsulotga bog'lanadi, kirillchasi toza. Bazaga va Telegram'ga ulanmasdan."""
import asyncio
import os
import re
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import database
import recipe_channel
import recipes
from recipes_content import RECIPES
from translit import lat_to_cyr

LEGACY = RECIPES[:recipes.LEGACY_COUNT]
NEW = RECIPES[recipes.LEGACY_COUNT:]
Q = recipes.QUEUE_START                          # 15.11 — the first slot of the queue
SLOT = timedelta(days=recipes.EVERY_DAYS)
LEGACY_SLUGS = {r["slug"] for r in LEGACY}


def run(coro):
    return asyncio.run(coro)


def legacy_photos_only(recipe):
    """Today's state: the 15 new recipes have no photo yet."""
    return recipe["slug"] in LEGACY_SLUGS


def all_photos(recipe):
    return True


def simulate(until, photo_on):
    """What the bot writes down: every slot from QUEUE_START, decided the
    first time it is looked at (on its first day), with the photos there on
    that day — exactly what recipes.sync() does. → ({day: slug}, [plans])."""
    slots, plans, d = {}, [], Q
    while d <= until:
        photo = photo_on(d)
        if d not in slots:
            slots[d] = recipes.plan(d, slots, photo)["recipe"]["slug"]
        plans.append(recipes.plan(d, slots, photo))
        d += SLOT
    return slots, plans


# Active products of the shop, 2026-11-13 (admin export: is_active = 1).
# Names exactly as the shop writes them; no stock figures in a public repo.
ACTIVE_PRODUCTS = (
    'Zomin tog‘ asali 700 gr',
    "Chia urug'i 300gr",
    "zig'ir urug'lari 300gr",
    "Rastaropsha urug'i 300gr",
    'Psillium uni 300gr',
    'Yashil grechka uni 500gr',
    'Bodom uni 1000gr',
    'Himalay tuz 500gr',
    'Toza Steviya 20gr',
    "Yeryong'oq pasta 200gr",
    'Табиий ҳамиртуруш— закваска',
    "Kepakli bug'doy uni",
    'Bodom uni 500gr',
    'kokos uni 1000gr',
    "oq zig'ir uni 1000gr",
    "Chia urug'i 600gr",
    "Rastaropsha urug'i 600gr",
    'Himalay tuz 1000gr',
    'bulgur guruchi 1000gr',
    'Tabiiy GHEE 1000ml',
    'Olma sirkasi (Toshkent) 250gr',
    "Uy kuvi saryog'i 800gr",
    'Lasos baliq tushonkasi 700ml',
    '2-nav un',
    'Xandonpista pastasi 200gr',
    'Polba uni',
    'Arpa uni 1kg',
    'Qora fermentlangan Solod 1kg',
    "Makkajo'xori uni",
    'Kepak. -o‘rtacha kattalikda (sredniy)',
    'Javdar uni 1kg',
    'Ksantan kamedi 100g',
    'Ksantan kamedi 500g',
    'Зайтун ёғи совуқ сиқим- Extra vergin',
    'Bodom uni 200gr',
    "Oq zig'ir uni 500gr",
    "Zig'ir uni 1000gr",
    "Zig'ir uni 500gr",
    "Zig'ir uni 300gr",
    "No'xat uni 1kg",
    'Ovsyanka uni',
    'Grechka uni',
    'Guruch uni',
    'Yashil grechka uni 1000gr',
    'Kokos uni 500gr',
    'Kokos uni 200gr',
    'Kokos shakari 250gr',
    'Kokos qirindisi 200gr',
    'Qora fermentlangan Solod 500g',
    'Psillium sheluxa 150gr',
    'Kokos yog‘i 400 gr extra vergin',
    'Zaytun yog‘i Rossiya (5 l, qovurish uchun)',
    'Zaytun yog‘i Ispaniya (5 l, qovurish uchun)',
    "Pista mag'zi 500gr",
    'Qora kunjut 600gr',
    'Qora kunjut 300gr',
    'Oq kunjut 600gr',
    'Oq kunjut 300gr',
    'Yashil grechka doni 1000gr',
    'Yashil grechka doni 500gr',
    "Zig'ir urug'lari 600gr",
    'Qora sedana 200gr',
    'Arpabodiyon (fenxel) 100gr',
    'Qora guruch 500gr',
    "Qizil guruch (Devzira) (bo'yalmagan, yog'lanmagan) 1000gr",
    "Qizil guruch (Devzira) (bo'yalmagan, yog'lanmagan) 500gr",
    'Basmati guruch (mayda, oq) 1000gr',
    'Basmati guruch Premium Besta 900gr',
    'Alluloza +Steviya 200gr',
    'Qovoq urugʻi 150g',
    'Rastaropsha uni 1000gr',
    'Rastaropsha uni 500gr',
    'Qora guruch 1kg Tayland',
    'Kakao nibs 200gr',
    'Ksantan kamedi 200gr',
    'Toza Steviya 40gr',
    'Eritritol 100gr',
    'Eritritol 500gr',
    'Eritrtitol 1000gr',
    "Zaytun yog'i(qovurish uchun) 1000ml",
    'Alluloza 200gr',
    'Alluloza 500gr',
    'Alluloza 1000gr',
    'Stevia 200gr',
    'Fistashka uni 1000gr',
    'Oq kunjut 1000g',
    "Makkajo'xori uni 500g «Кудесница»",
    'Guruch uni 500g «Кудесница»',
    'Grechka uni 400g «Кудесница»',
    "Kepakli bug'doy uni 500g «Кудесница»",
    'Javdar uni 400g «Кудесница»',
    "Zig'ir uni 400g «Кудесница»",
    'Ovsyanka uni 400g «Кудесница»',
    'Шоколад Победа 57%',
    '«Победа» Charged 100% no sugar',
    '«Победа» 72% Dark горький',
    '«Победа» 100% Charged с цельным фундуком',
    'Stevia 500g',
    'Stevia 1000g',
    "zig'ir uru'gi 1 kg",
    'Qora shokolad granula (shakarsiz) 1000g',
    'Kokos slivka 400ml',
    'TOZA STEVIA 1000G',
    'Kokos chipsi 100g',
    'Qora shokolad granula 300g',
    'Qora shokolad granula 500g',
    'Olma sirkasi (Toshkent) 5% 500ml',
    "Kokos yog'i Extra Virgin 450ml",
    'Olma sirkasi (Turkiya) 5% 500ml',
    'Dolchin (Koritsa) 70g',
    'Ksantan kamed 1kg',
    'Chia urugʻi 1000g',
    'Qovoq urugʻi 1000g',
    'Soya uni',
    'Suli yormasi',
    'Psillium 1kg',
    'Oq Solod 500g',
    'Qora kunjut 1000g',
    'Bodom uni po‘stlog‘i billan',
    'Kepakli un makaroni "Barilla"',
    'Kepakli un makaron vermishel 500g',
    'Ismaloqli makaron vermishel 500g',
    'Grechka unli vermishel makaron 500g',
    'Kokos shakari 1000g',
    'Suvtegirmon uni 1000gr',
    'Lyupin',
    'Psheno uni',
    'Dos bros',
    'Kakos yogʻi',
    '🫒 Zaytun yog‘i — PICASSO Extra Virgin Olive Oil',
    'Guletensiz makaron barilla',
    'Barilla spagetti Kepakli undan',
    'Glyutensez spagetti Barilla',
    'Kofe sikoriy Elza 100gr',
    'Marmalad shokalad',
    "Mulberry quritilgan o'rik+tut batonchiklari",
    'Eko vitamin sok',
    'Eko vitamon sok malina taʼmli',
    'Qovoq uni',
    'BODOM UNIDAN PECHENIY',
)
SNAPSHOT = [{"id": n, "name": name, "price": 1, "quantity": 1}
            for n, name in enumerate(ACTIVE_PRODUCTS, 1)]


class LegacyHandOverTest(unittest.TestCase):
    """Up to 13.11 the old rule; 15.11 continues its cycle while nothing new
    is ready — the site doesn't jump when this ships."""

    def test_old_rule_kept_until_the_queue(self):
        self.assertEqual(recipes.plan(date(2026, 11, 5))["recipe"]["slug"], "keto-bulochka")
        last = recipes.plan(date(2026, 11, 13), {}, legacy_photos_only)
        self.assertEqual(last["recipe"]["slug"], RECIPES[3]["slug"])     # 4th time round
        self.assertFalse(last["is_new"])
        self.assertTrue(recipes.plan(date(2026, 11, 5))["is_new"])

    def test_first_queue_slot_without_photos_is_the_next_repeat(self):
        p = recipes.plan(Q, {}, legacy_photos_only)
        self.assertEqual(p["recipe"]["slug"], RECIPES[4]["slug"])        # what the old rule shows on 15.11
        self.assertFalse(p["is_new"])
        self.assertEqual(p["next_at"], date(2026, 11, 17))
        self.assertEqual(recipes.plan(Q + timedelta(days=1), {}, legacy_photos_only)["next_at"],
                         date(2026, 11, 17))


class QueueOrderTest(unittest.TestCase):
    def test_new_ones_in_library_order_one_per_slot_none_skipped(self):
        _, plans = simulate(Q + SLOT * 16, lambda d: all_photos)
        out = [(p["day"], p["recipe"]["slug"], p["is_new"]) for p in plans]
        self.assertEqual([s for _, s, new in out if new], [r["slug"] for r in NEW])
        self.assertTrue(all(new for _, _, new in out[:len(NEW)]))       # back to back from 15.11
        self.assertEqual(out[0][:2], (date(2026, 11, 15), "keto-somsa"))
        self.assertEqual(out[len(NEW) - 1][0], date(2026, 12, 13))
        self.assertFalse(out[len(NEW)][2])                               # then repeats
        self.assertFalse(out[len(NEW) + 1][2])

    def test_earlier_list_and_next_date(self):
        slots, _ = simulate(Q + SLOT * 2, lambda d: all_photos)
        p = recipes.plan(Q + SLOT * 2 + timedelta(days=1), slots, all_photos)
        self.assertEqual(p["recipe"]["slug"], NEW[2]["slug"])
        self.assertEqual([r["slug"] for r in p["earlier"][:2]], [NEW[1]["slug"], NEW[0]["slug"]])
        self.assertEqual(len(p["earlier"]), len(LEGACY) + 2)
        self.assertEqual(p["next_at"], Q + SLOT * 3)
        self.assertNotIn(NEW[3]["slug"], {r["slug"] for r in p["earlier"]})   # no future ones

    def test_repeats_never_twice_in_a_row(self):
        _, plans = simulate(Q + SLOT * 40, lambda d: legacy_photos_only)
        slugs = [p["recipe"]["slug"] for p in plans]
        self.assertTrue(all(a != b for a, b in zip(slugs, slugs[1:])), slugs)
        self.assertTrue(set(slugs) <= LEGACY_SLUGS)

    def test_after_the_last_new_one_no_immediate_repeat_of_it(self):
        _, plans = simulate(Q + SLOT * 80, lambda d: all_photos)
        slugs = [p["recipe"]["slug"] for p in plans]
        self.assertTrue(all(a != b for a, b in zip(slugs, slugs[1:])))


class PhotoGateTest(unittest.TestCase):
    def test_no_photo_no_new_recipe_only_repeats(self):
        _, plans = simulate(Q + SLOT * 10, lambda d: legacy_photos_only)
        self.assertFalse(any(p["is_new"] for p in plans))
        for p in plans:
            self.assertIn(p["recipe"]["slug"], LEGACY_SLUGS)
            self.assertTrue(all(r["slug"] in LEGACY_SLUGS for r in p["earlier"]))

    def test_photo_arriving_mid_slot_takes_the_next_slot(self):
        arrival = date(2026, 11, 20)                     # deploy inside the 19.11 slot
        slots, plans = simulate(Q + SLOT * 6, lambda d: all_photos if d >= arrival else legacy_photos_only)
        by_day = {p["day"]: p for p in plans}
        for day in (Q, Q + SLOT, Q + SLOT * 2):          # 15, 17, 19.11 — repeats, kept as written
            self.assertFalse(by_day[day]["is_new"], day)
        # after the deploy the 19.11 slot stays the repeat it was written as
        self.assertFalse(recipes.plan(arrival, slots, all_photos)["is_new"])
        self.assertEqual([by_day[Q + SLOT * k]["recipe"]["slug"] for k in (3, 4, 5, 6)],
                         [r["slug"] for r in NEW[:4]])   # 21.11 on: first, second, … none skipped

    def test_a_missing_photo_holds_back_only_its_own_recipe(self):
        late = NEW[1]["slug"]
        arrival = Q + SLOT * 3
        def photo_on(d):
            return lambda r: r["slug"] != late or d >= arrival
        _, plans = simulate(Q + SLOT * 4, photo_on)
        self.assertEqual([p["recipe"]["slug"] for p in plans],
                         [NEW[0]["slug"], NEW[2]["slug"], NEW[3]["slug"], late, NEW[4]["slug"]])
        self.assertTrue(all(p["is_new"] for p in plans))

    def test_a_written_recipe_whose_photo_is_gone_is_not_shown(self):
        slots = {Q: NEW[0]["slug"]}
        p = recipes.plan(Q, slots, legacy_photos_only)
        self.assertNotEqual(p["recipe"]["slug"], NEW[0]["slug"])
        self.assertIsNone(recipes_find(NEW[0]["slug"], Q, slots, legacy_photos_only))

    def test_unwritten_past_slots_never_burn_a_recipe(self):
        # The bot was down 15–18.11: those slots count as repeats, the first
        # new recipe comes on the first slot somebody actually sees.
        p = recipes.plan(Q + SLOT * 2, {}, all_photos)
        self.assertEqual(p["recipe"]["slug"], NEW[0]["slug"])
        self.assertTrue(p["is_new"])

    def test_waiting_counts(self):
        w = recipes.waiting(Q, {}, legacy_photos_only)
        self.assertEqual(len(w["no_photo"]), len(NEW))
        self.assertEqual(w["ready"], [])
        slots, _ = simulate(Q + SLOT, lambda d: all_photos)
        w = recipes.waiting(Q + SLOT, slots, all_photos)
        self.assertEqual((len(w["no_photo"]), len(w["ready"])), (0, len(NEW) - 2))


def recipes_find(slug, today, slots, photo):
    current, earlier, _ = recipes.schedule(today, slots, photo)
    return next((r for r in [current, *earlier] if r["slug"] == slug), None)


class SlotLogTest(unittest.TestCase):
    """sync(): each slot's recipe written once in release_notes_sent."""

    def setUp(self):
        saved = dict(recipes._slot_log)
        recipes._slot_log.update(slots={}, day=None)
        self.addCleanup(lambda: (recipes._slot_log.clear(), recipes._slot_log.update(saved)))
        pool = patch.object(database, "pool", MagicMock())
        pool.start()
        self.addCleanup(pool.stop)

    def sync(self, today, logs, photo=legacy_photos_only, claim_ok=True):
        load = AsyncMock(side_effect=logs)
        claim = AsyncMock(return_value=claim_ok)
        with patch.object(recipes, "_load_slots", load), \
             patch.object(recipes, "has_photo", photo), \
             patch.object(database, "claim_release_notes", claim):
            ok = run(recipes.sync(today))
        return ok, load, claim

    def test_first_look_writes_the_slot_then_it_is_cached(self):
        ok, load, claim = self.sync(Q, [{}, {Q: "tovuq-nuggets"}])
        self.assertTrue(ok)
        claim.assert_awaited_once_with("recipe-slot-2026-11-15:tovuq-nuggets")
        self.assertEqual(recipes._slot_log["slots"], {Q: "tovuq-nuggets"})
        _, load, claim = self.sync(Q + timedelta(days=1), [])         # same slot, next day
        load.assert_not_awaited()
        claim.assert_not_awaited()

    def test_with_photos_the_slot_gets_the_first_new_recipe(self):
        _, _, claim = self.sync(Q, [{}, {Q: "keto-somsa"}], photo=all_photos)
        claim.assert_awaited_once_with("recipe-slot-2026-11-15:keto-somsa")

    def test_an_already_written_slot_is_not_rewritten(self):
        _, load, claim = self.sync(Q, [{Q: "tovuq-nuggets"}], photo=all_photos)
        claim.assert_not_awaited()
        self.assertEqual(recipes.plan(Q, photo=all_photos)["recipe"]["slug"], "tovuq-nuggets")

    def test_database_trouble_says_false_and_writes_nothing(self):
        ok, _, claim = self.sync(Q, RuntimeError("db down"))
        self.assertFalse(ok)
        claim.assert_not_awaited()
        self.assertIsNone(recipes._slot_log["day"])

    def test_no_database_and_before_the_queue(self):
        with patch.object(database, "pool", None):
            self.assertFalse(run(recipes.sync(Q)))
            self.assertTrue(run(recipes.sync(date(2026, 11, 13))))      # old rule, nothing to write

    def test_parse_keys_first_entry_of_a_day_wins(self):
        self.assertEqual(recipes.parse_slots([
            "recipe-slot-2026-11-15:tovuq-nuggets", "recipe-slot-2026-11-15:keto-somsa",
            "recipe-slot-2026-11-17:keto-pitsa", "recipe-slot-xx:keto-pitsa", "recipe-slot-2026-11-19:",
        ]), {date(2026, 11, 15): "tovuq-nuggets", date(2026, 11, 17): "keto-pitsa"})


class SiteGateTest(unittest.TestCase):
    """The Mini App API shows only recipes whose photo is there."""

    def call(self, handler, slug=None, slots=None, photo=legacy_photos_only):
        import webapp_server
        request = MagicMock()
        request.match_info = {"slug": slug}
        request.get = lambda key, default=None: "uz" if key == "user_lang" else default
        with patch.object(recipes, "today_tk", lambda: Q), \
             patch.object(recipes, "sync", AsyncMock(return_value=True)), \
             patch.object(recipes, "_slot_log", {"slots": slots or {}, "day": Q}), \
             patch.object(recipes, "has_photo", photo), \
             patch.object(recipes, "view", AsyncMock(side_effect=lambda r, lang: {"slug": r["slug"]})):
            return run(handler(request))

    def test_today_is_a_repeat_while_photos_are_missing(self):
        import webapp_server
        res = self.call(webapp_server.api_recipes)
        self.assertIn(b'"tovuq-nuggets"', res.body)
        self.assertIn(b'"17.11"', res.body)                                   # next one
        self.assertEqual(self.call(webapp_server.api_recipe_one, "keto-somsa").status, 404)
        self.assertEqual(self.call(webapp_server.api_recipe_one, "bodom-noni").status, 200)

    def test_with_its_photo_and_its_slot_it_opens(self):
        import webapp_server
        slots = {Q: "keto-somsa"}
        self.assertIn(b'"keto-somsa"', self.call(webapp_server.api_recipes, slots=slots, photo=all_photos).body)
        self.assertEqual(self.call(webapp_server.api_recipe_one, "keto-somsa", slots, all_photos).status, 200)
        self.assertEqual(self.call(webapp_server.api_recipe_one, "tungi-suli-botqa", slots, all_photos).status,
                         404)                                                 # its day hasn't come


class ChannelTickTest(unittest.TestCase):
    def tick(self, now, slots, photo, synced=True):
        bot = MagicMock()
        with patch.object(recipe_channel, "_now_tk", lambda: now), \
             patch.object(recipes, "sync", AsyncMock(return_value=synced)), \
             patch.object(recipes, "_slot_log", {"slots": slots, "day": recipes.slot_day(now.date())}), \
             patch.object(recipes, "has_photo", photo), \
             patch.object(database, "claim_release_notes", AsyncMock(return_value=True)) as claim, \
             patch.object(database, "release_release_notes", AsyncMock()), \
             patch.object(recipe_channel, "post_to_channel", AsyncMock(return_value=True)) as post, \
             patch.object(recipe_channel, "_notify_admins", AsyncMock()) as notify:
            run(recipe_channel._tick(bot))
        return claim, post, notify

    def test_without_photos_the_channel_gets_a_repeat_and_admins_hear_so(self):
        claim, post, notify = self.tick(datetime(2026, 11, 15, 11, 5), {Q: "tovuq-nuggets"}, legacy_photos_only)
        self.assertEqual(post.await_args.args[1]["slug"], "tovuq-nuggets")
        self.assertEqual(claim.await_args.args[0], "recipe-channel-tovuq-nuggets-2026-11-15")
        text = notify.await_args.args[1]
        self.assertIn("takroriy", text)
        self.assertNotIn("yangi retsept", text.lower())
        self.assertIn(f"{len(NEW)} ta", text)                                  # how many wait for a photo

    def test_a_recipe_without_photo_is_never_posted(self):
        # Even if a slot were written for it, no photo → not that recipe.
        _, post, _ = self.tick(datetime(2026, 11, 15, 11, 5), {Q: "keto-somsa"}, legacy_photos_only)
        self.assertNotEqual(post.await_args.args[1]["slug"], "keto-somsa")
        self.assertIn(post.await_args.args[1]["slug"], LEGACY_SLUGS)

    def test_new_recipe_day(self):
        _, post, notify = self.tick(datetime(2026, 11, 15, 11, 5), {Q: "keto-somsa"}, all_photos)
        self.assertEqual(post.await_args.args[1]["slug"], "keto-somsa")
        self.assertIn("Kanalga yangi retsept e'lon qilindi", notify.await_args.args[1])

    def test_unknown_slot_log_posts_nothing(self):
        claim, post, _ = self.tick(datetime(2026, 11, 15, 11, 5), {}, all_photos, synced=False)
        claim.assert_not_awaited()
        post.assert_not_awaited()


class AdminNoteTest(unittest.TestCase):
    R = {"title": {"uz": "Bodom noni", "ru": "Хлеб"}, "slug": "x"}

    def test_repeat_says_repeat_and_counts_the_waiting(self):
        text = recipe_channel.admin_note(self.R, False, {"no_photo": NEW[:15], "ready": []})
        self.assertIn("🔁 <b>Kanalga takroriy retsept e'lon qilindi:</b> Bodom noni", text)
        self.assertNotIn("yangi retsept", text.lower())
        self.assertIn("Rasmini kutayotgan retseptlar: 15 ta", text)
        text = recipe_channel.admin_note(self.R, False, {"no_photo": [], "ready": NEW[:3]})
        self.assertIn("navbatini kutayotganlar: 3 ta", text)
        self.assertNotIn("yangi retsept", text.lower())
        text = recipe_channel.admin_note(self.R, False, {"no_photo": [], "ready": []})
        self.assertIn("yangilarini qo'shish kerak", text)

    def test_new_one(self):
        text = recipe_channel.admin_note(self.R, True, {"no_photo": [], "ready": []})
        self.assertIn("📣 <b>Kanalga yangi retsept e'lon qilindi:</b> Bodom noni", text)
        self.assertIn("/retsept_kanal", text)


LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
ALLOWED_LATIN = {"GHEE"}                     # kept Latin on purpose (translit._BRANDS)


def uz_texts(r):
    yield r["title"]["uz"]
    yield r["intro"]["uz"]
    yield r["servings"]["uz"]
    yield r["tip"]["uz"]
    if r.get("rest"):
        yield r["rest"]["uz"]
    for s in r["steps"]:
        yield s["uz"]
    for i in r["ingredients"]:
        yield i["amount"]["uz"]
        yield i["name"]["uz"]
        if i.get("why"):
            yield i["why"]["uz"]


def ru_texts(r):
    yield from (r[k]["ru"] for k in ("title", "intro", "servings", "tip"))
    if r.get("rest"):
        yield r["rest"]["ru"]
    yield from (s["ru"] for s in r["steps"])
    for i in r["ingredients"]:
        yield i["amount"]["ru"]
        yield i["name"]["ru"]
        if i.get("why"):
            yield i["why"]["ru"]


class NewRecipesContentTest(unittest.TestCase):
    def test_fifteen_new_ones_with_unique_link_safe_slugs(self):
        self.assertEqual(len(NEW), 15)
        slugs = [r["slug"] for r in RECIPES]
        self.assertEqual(len(slugs), len(set(slugs)))
        for s in slugs:
            self.assertRegex(s, r"^[a-z0-9]+(-[a-z0-9]+)*$")

    def test_every_field_in_both_languages(self):
        for r in NEW:
            with self.subTest(r["slug"]):
                for key in ("title", "intro", "servings", "tip"):
                    self.assertTrue(r[key]["uz"].strip() and r[key]["ru"].strip(), key)
                if "rest" in r:
                    self.assertTrue(r["rest"]["uz"] and r["rest"]["ru"])
                self.assertIsInstance(r["minutes"], int)
                self.assertGreater(r["minutes"], 0)
                self.assertGreater(r["per_serving"]["carbs"], 0)
                self.assertLessEqual(r["per_serving"]["carbs"], 60)
                self.assertGreaterEqual(r["per_serving"]["kcal"], 50)
                self.assertLessEqual(r["per_serving"]["kcal"], 700)
                self.assertGreaterEqual(len(r["steps"]), 5)
                for s in r["steps"]:
                    self.assertTrue(s["uz"].strip() and s["ru"].strip())
                self.assertGreaterEqual(len(r["ingredients"]), 5)
                for i in r["ingredients"]:
                    self.assertTrue(i["amount"]["uz"] and i["amount"]["ru"], i["name"])
                    self.assertTrue(i["name"]["uz"] and i["name"]["ru"])
                    if i.get("match"):
                        self.assertTrue(i["why"]["uz"] and i["why"]["ru"], i["name"]["uz"])
                self.assertGreaterEqual(sum(1 for i in r["ingredients"] if i.get("match")), 1)
                self.assertTrue(r["image_prompt"].strip())

    def test_every_shop_ingredient_finds_an_active_product(self):
        for r in RECIPES:
            for item in r["ingredients"]:
                if item.get("match"):
                    with self.subTest(r["slug"], item=item["name"]["uz"]):
                        self.assertIsNotNone(recipes.match_product(item["match"], SNAPSHOT))
                        # the Latin group (the first) is the one that matches today
                        self.assertIsNotNone(recipes.match_product(item["match"][:1], SNAPSHOT))

    def test_sweeteners_never_land_on_the_strong_blends(self):
        allulose = next(i for r in NEW for i in r["ingredients"] if i["name"]["uz"] == "Alluloza")
        self.assertEqual(recipes.match_product(allulose["match"], SNAPSHOT)["name"], "Alluloza 200gr")
        stevia = next(i for r in NEW for i in r["ingredients"] if i["name"]["uz"] == "Steviya")
        self.assertNotIn("toza", recipes.match_product(stevia["match"], SNAPSHOT)["name"].lower())

    def test_each_new_recipe_features_a_product_of_its_own(self):
        """A shop product the first 15 never used and no other new recipe
        features — every new recipe brings a different product forward."""
        old = {id(i["match"]) for r in LEGACY for i in r["ingredients"] if i.get("match")}
        fresh = [{id(i["match"]) for i in r["ingredients"] if i.get("match") and id(i["match"]) not in old}
                 for r in NEW]
        for n, r in enumerate(NEW):
            others = set().union(*(f for m, f in enumerate(fresh) if m != n))
            with self.subTest(r["slug"]):
                self.assertTrue(fresh[n] - others)

    def test_cyrillic_reads_clean(self):
        for r in NEW:
            for text in uz_texts(r):
                cyr = lat_to_cyr(text)
                with self.subTest(r["slug"], text=text[:50]):
                    self.assertEqual([w for w in LATIN_WORD.findall(cyr) if w not in ALLOWED_LATIN], [])
                    self.assertNotIn("ретсепт", cyr.lower())
                    self.assertNotIn("порсия", cyr.lower())

    def test_russian_has_no_latin_words(self):
        for r in NEW:
            for text in ru_texts(r):
                with self.subTest(r["slug"], text=text[:50]):
                    self.assertEqual(LATIN_WORD.findall(text), [])

    def test_copy_rules(self):
        for r in NEW:
            uz = " ".join(uz_texts(r)).lower()
            ru = " ".join(ru_texts(r)).lower()
            with self.subTest(r["slug"]):
                self.assertNotIn("iltimos", uz)                       # a recipe never pleads
                self.assertNotIn("cho'chqa", uz)                      # copy taboo (piggy bank)
                self.assertNotIn("копилк", ru)
                for word in ("davola", "kasallik", "лечит", "лечение"):   # no medical claims
                    self.assertNotIn(word, uz + " " + ru)

    def test_every_new_recipe_has_its_photo_prompt(self):
        from pathlib import Path
        prompts = (Path(recipes.__file__).parent / "recipes_image_prompts.md").read_text(encoding="utf-8")
        for r in NEW:
            self.assertIn(f"## {r['slug']}", prompts)
            self.assertIn(f"webapp/recipes/{r['slug']}.jpg", prompts)


if __name__ == "__main__":
    unittest.main()
