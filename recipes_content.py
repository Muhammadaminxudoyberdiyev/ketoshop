"""
Saytdagi retseptlar — egasi so'rovi 2026-10-08: "har 2 kunda 1 ta retsept
beramiz", rasm, qadamma-qadam va mahsulot tafsilotlari bilan, har retsept
ostida "🛒 Barcha masalliqlarni savatga".

Har bir retsept:
  slug         — rasm nomi ham shu: webapp/recipes/<slug>.jpg (/static/recipes/...)
  title/intro  — uz + ru (kirillcha o'zbekcha uz dan transliteratsiya qilinadi)
  minutes      — umumiy vaqt; `rest` — kutish (tun bo'yi va h.k.), bo'lsa
  servings     — "10 bo'lak", "2 kishilik"
  per_serving  — taxminiy: sof uglevod (g) va kkal, bir porsiya/bo'lakka
  ingredients  — amount + name; `match` bo'lsa — bu Ketoshop mahsuloti:
                 sayt uni katalogdan topib (recipes.resolve), rasm, joriy narx
                 va "savatga" tugmasini qo'shadi; `why` — nega aynan shu
                 mahsulot. `match` yo'q — uydan (tuxum, tovuq, suv).
  steps, tip

`match` — mahsulot NOMIDA qidiriladigan so'zlar guruhlari: guruhdagi hamma
so'z bo'lsa — mos. Lotin va kirill yozuvi ikkalasi beriladi, chunki katalogda
ikkalasi ham uchraydi. Birinchi topilgan guruh ishlatiladi; bir nechta qadoq
bo'lsa (200 g / 500 g / 1 kg) — omborda bor eng hamyonbopi savatga tushadi.

Rasm promptlari (Higgsfield, gpt_image_2_5) retsept matniga mos yozilgan:
rasmda ko'rinadigan narsa (kunjut, kokos, sous...) retseptda ham bor.
2026-11-13 dagi 15 tasining to'liq promptlari — recipes_image_prompts.md.
Rasmi (webapp/recipes/<slug>.jpg) qo'shilmagan retsept saytga ham, kanalga
ham chiqmaydi — navbatini kutadi (recipes.py, «Jadval»).
"""

_ALMOND = [["bodom", "uni"], ["бодом", "уни"]]
_PSYLLIUM_FLOUR = [["psillium", "uni"], ["псиллиум", "уни"]]
_PSYLLIUM_ANY = [["psillium"], ["псиллиум"]]
_SALT = [["himalay"], ["ҳималай"], ["гималай"]]
_VINEGAR = [["olma", "sirka"], ["олма", "сирка"]]
_SESAME_WHITE = [["oq", "kunjut"], ["оқ", "кунжут"]]
_SESAME_BLACK = [["qora", "kunjut"], ["қора", "кунжут"]]
_CHIA = [["chia"], ["чиа"]]
_COCONUT_FLAKES = [["kokos", "qirindi"], ["кокос", "қиринди"], ["kokos", "chips"], ["кокос", "чипс"]]
_NIBS = [["kakao", "nibs"], ["какао", "нибс"]]
_ERYTHRITOL = [["eritritol"], ["эритритол"]]
_GHEE = [["ghee"], ["гхи"]]
_FLAX_SEEDS = [["zig'ir", "urug'"], ["зиғир", "уруғ"]]
_PUMPKIN = [["qovoq", "urug'"], ["қовоқ", "уруғ"]]
_OLIVE = [["zaytun", "virgin"], ["зайтун", "virgin"], ["zaytun", "sovuq"], ["зайтун", "совуқ"]]
# 2026-10-17 recipes
_OLIVE_FRY = [["zaytun", "qovurish"], ["зайтун", "қовуриш"]]
_COCONUT_FLOUR = [["kokos", "uni"], ["кокос", "уни"]]
_FLAX_FLOUR = [["zig'ir", "uni"], ["зиғир", "уни"]]
_GREEN_BUCKWHEAT = [["yashil", "grechka", "don"], ["яшил", "гречка", "дон"]]
_BLACK_RICE = [["qora", "guruch"], ["қора", "гуруч"]]
_PISTACHIO = [["pista", "mag'z"], ["писта", "мағз"]]
# 2026-11-13 recipes — shop products the first 15 did not use
_XANTHAN = [["ksantan"], ["ксантан"]]
_NIGELLA = [["qora", "sedana"], ["қора", "седана"]]
_WHITE_FLAX_FLOUR = [["oq", "zig'ir", "uni"], ["оқ", "зиғир", "уни"]]
_PSYLLIUM_HUSK = [["psillium", "shelux"], ["псиллиум", "шелух"], ["psillium"], ["псиллиум"]]
_BUCKWHEAT_NOODLES = [["grechka", "vermishel"], ["гречка", "вермишел"]]
_DEVZIRA = [["devzira"], ["девзира"]]
_COCONUT_CREAM = [["kokos", "slivka"], ["кокос", "сливк"]]
_COCONUT_OIL = [["kokos", "yog'"], ["kakos", "yog'"], ["кокос", "ёғ"]]
_SALMON = [["lasos"], ["лосос"], ["ласос"]]
_SOY_FLOUR = [["soya", "uni"], ["соя", "уни"]]
_PEANUT_PASTE = [["yeryong'oq", "pasta"], ["ерёнғоқ", "паста"]]
# Plain allulose only: "Alluloza +Steviya" is a sweeter blend, the amounts would be off.
_ALLULOSE = [["alluloza 200"], ["alluloza 500"], ["alluloza 1000"], ["аллюлоза"]]
_CHOCOLATE = [["победа", "no sugar"], ["победа", "100%"]]
_PISTACHIO_PASTE = [["xandonpista", "pasta"], ["хандонписта", "паста"]]
_OAT_FLOUR = [["ovsyanka", "uni"], ["овсянка", "уни"]]
_CINNAMON = [["dolchin"], ["долчин"], ["koritsa"], ["корица"]]
_BUCKWHEAT_FLOUR = [["grechka", "uni"], ["гречка", "уни"]]
# The Stevia 200/500 g blends, not the pure extract ("Toza steviya") — a pinch of that is a whole spoon of these.
_STEVIA = [["stevia", "200"], ["stevia", "500"], ["стевия"]]
_CHICKPEA_FLOUR = [["no'xat", "uni"], ["нўхат", "уни"]]
_OATS = [["suli", "yorma"], ["сули", "ёрма"]]
_MILK_THISTLE = [["rastaropsha", "uni"], ["растаропша", "уни"], ["расторопш"]]
_RYE_FLOUR = [["javdar", "uni"], ["жавдар", "уни"]]
_BRAN_WHEAT_FLOUR = [["kepakli", "bug'doy"], ["кепакли", "буғдой"]]
_MALT = [["qora", "solod"], ["қора", "солод"]]
_CORN_FLOUR = [["makkajo'xori", "uni"], ["маккажўхори", "уни"]]
_BULGUR = [["bulgur"], ["булгур"]]


def _i(amount_uz, amount_ru, name_uz, name_ru, match=None, why_uz=None, why_ru=None):
    item = {"amount": {"uz": amount_uz, "ru": amount_ru}, "name": {"uz": name_uz, "ru": name_ru}}
    if match:
        item["match"] = match
    if why_uz:
        item["why"] = {"uz": why_uz, "ru": why_ru}
    return item


def _s(uz, ru):
    return {"uz": uz, "ru": ru}


RECIPES = [
    {
        "slug": "bodom-noni",
        "title": _s("Glyutensiz bodom noni", "Безглютеновый миндальный хлеб"),
        "intro": _s(
            "Yumshoq, g'ovak va to'yimli — oddiy nonni sog'inmaysiz. Bodom uni va psillium "
            "xamirni ushlab turadi, kunjut esa qobig'iga mazali qarsillash beradi.",
            "Мягкий, пористый и сытный — по обычному хлебу скучать не придётся. Миндальная "
            "мука и псиллиум держат тесто, а кунжут даёт хрустящую корочку."),
        "minutes": 70,
        "servings": _s("10 bo'lak", "10 ломтиков"),
        "per_serving": {"carbs": 2.5, "kcal": 170},
        "ingredients": [
            _i("200 g", "200 г", "Bodom uni", "Миндальная мука", _ALMOND,
               "Asosiy un — past uglevodli, oqsil va sog'lom yog'larga boy.",
               "Основная мука — мало углеводов, много белка и полезных жиров."),
            _i("40 g", "40 г", "Psillium uni", "Псиллиум (мука)", _PSYLLIUM_FLOUR,
               "Glyuten o'rnini bosadi: non ko'tariladi va ushalmaydi.",
               "Заменяет глютен: хлеб поднимается и не крошится."),
            _i("2 osh q.", "2 ст.л.", "Olma sirkasi", "Яблочный уксус", _VINEGAR,
               "Soda bilan birga xamirni ko'pchitadi.",
               "Вместе с содой делает тесто пышным."),
            _i("2 osh q.", "2 ст.л.", "Oq kunjut (ustiga)", "Белый кунжут (сверху)", _SESAME_WHITE,
               "Qobiqqa qarsillash va yong'oqsimon ta'm beradi.",
               "Хрустящая корочка и ореховый вкус."),
            _i("1 ch.q.", "1 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Ta'mni ochadi, foydali minerallarga boy.",
               "Раскрывает вкус, богата минералами."),
            _i("3 ta", "3 шт", "Tuxum", "Яйца"),
            _i("250 ml", "250 мл", "Qaynoq suv", "Кипяток"),
            _i("1 ch.q.", "1 ч.л.", "Soda", "Сода"),
        ],
        "steps": [
            _s("Pechni 180°C ga qizdiring, qolipga pergament to'shang.",
               "Разогрейте духовку до 180°C, застелите форму пергаментом."),
            _s("Bodom uni, psillium uni, soda va tuzni idishda yaxshilab aralashtiring.",
               "Хорошо смешайте миндальную муку, псиллиум, соду и соль."),
            _s("Tuxum va olma sirkasini qo'shib, qoshiq bilan aralashtiring — xamir quyuq bo'ladi.",
               "Добавьте яйца и уксус, перемешайте ложкой — тесто будет густым."),
            _s("Qaynoq suvni quyib, darhol 30 soniya aralashtiring: psillium suvni shimib, "
               "xamir yumshoq loydek bo'ladi.",
               "Влейте кипяток и сразу мешайте 30 секунд: псиллиум впитает воду, тесто станет "
               "мягким, как пластилин."),
            _s("Ho'l qo'l bilan non shaklini bering, qolipga soling va ustiga kunjut seping.",
               "Мокрыми руками сформируйте буханку, выложите в форму и посыпьте кунжутом."),
            _s("50–55 daqiqa pishiring. Tayyor nonning tagiga chertilsa, bo'g'iq ovoz chiqadi.",
               "Выпекайте 50–55 минут. Готовый хлеб глухо звучит, если постучать по донышку."),
            _s("Kesishdan oldin to'liq soviting (kamida 1 soat) — issiqligida ichi yopishqoq bo'ladi.",
               "Перед нарезкой полностью остудите (минимум час) — горячий мякиш липкий."),
        ],
        "tip": _s("Xamirga zig'ir yoki qovoq urug'i qo'shsangiz, yanada to'yimli bo'ladi. "
                  "Muzlatgichda 1 oygacha saqlanadi.",
                  "Добавьте в тесто семена льна или тыквы — станет ещё сытнее. "
                  "В морозилке хранится до месяца."),
        "image_prompt": "gluten-free almond flour and psyllium bread loaf, sesame on top, slices, "
                        "pink salt, apple cider vinegar, light oak board",
    },
    {
        "slug": "chia-puding",
        "title": _s("Kokosli chia pudingi kakao nibs bilan", "Кокосовый пудинг чиа с какао-крупкой"),
        "intro": _s(
            "Kechqurun 5 daqiqada tayyorlab qo'yasiz — ertalab nonushta tayyor turadi. "
            "Shakarsiz, lekin shirin, ustida esa qarsildoq kakao nibs.",
            "Готовится вечером за 5 минут — утром завтрак уже ждёт. Без сахара, но сладкий, "
            "а сверху хрустящая какао-крупка."),
        "minutes": 10,
        "rest": _s("+ muzlatkichda 4 soat yoki tun bo'yi", "+ 4 часа или ночь в холодильнике"),
        "servings": _s("2 kishilik", "2 порции"),
        "per_serving": {"carbs": 6, "kcal": 390},
        "ingredients": [
            _i("50 g", "50 г", "Chia urug'i", "Семена чиа", _CHIA,
               "Tolaga boy: suyuqlikni shimib puding bo'ladi va uzoq to'q tutadi.",
               "Много клетчатки: впитывает жидкость, превращаясь в пудинг, и надолго насыщает."),
            _i("20 g", "20 г", "Kokos qirindisi", "Кокосовая стружка", _COCONUT_FLAKES,
               "Qovurilgach xushbo'y va qarsildoq bo'ladi.",
               "После обжарки — ароматная и хрустящая."),
            _i("15 g", "15 г", "Kakao nibs", "Какао-крупка", _NIBS,
               "Shakarsiz shokolad ta'mi va antioksidantlar.",
               "Шоколадный вкус без сахара и антиоксиданты."),
            _i("1–2 osh q.", "1–2 ст.л.", "Eritritol", "Эритрит", _ERYTHRITOL,
               "Shakar o'rnida — qonda shakarni ko'tarmaydi.",
               "Вместо сахара — не повышает сахар в крови."),
            _i("200 ml", "200 мл", "Kokos suti", "Кокосовое молоко"),
            _i("100 ml", "100 мл", "Suv yoki sut", "Вода или молоко"),
            _i("bir chimdim", "щепотка", "Tuz", "Соль"),
            _i("2–3 barg", "2–3 листика", "Yalpiz (bezash uchun)", "Мята (для подачи)"),
        ],
        "steps": [
            _s("Idishda kokos suti, suv, eritritol va bir chimdim tuzni aralashtiring.",
               "Смешайте кокосовое молоко, воду, эритрит и щепотку соли."),
            _s("Chia urug'ini qo'shib, 1 daqiqa yaxshilab aralashtiring.",
               "Добавьте чиа и хорошо мешайте 1 минуту."),
            _s("10 daqiqadan keyin yana bir bor aralashtiring — chia bir joyga yopishib qolmaydi.",
               "Через 10 минут перемешайте ещё раз — так чиа не слипнется комками."),
            _s("Ikki bankaga bo'lib, muzlatkichda kamida 4 soat yoki tun bo'yi saqlang.",
               "Разлейте по двум баночкам и уберите в холодильник минимум на 4 часа или на ночь."),
            _s("Kokos qirindisini quruq tovada 1–2 daqiqa, och-oltin rangga kelguncha qovuring.",
               "Обжарьте кокосовую стружку на сухой сковороде 1–2 минуты до светло-золотистого цвета."),
            _s("Tortishdan oldin ustiga kokos qirindisi va kakao nibs seping, yalpiz bilan bezang.",
               "Перед подачей посыпьте стружкой и какао-крупкой, украсьте мятой."),
        ],
        "tip": _s("Muzlatkichda 3 kungacha saqlanadi — bir yo'la 3 kunlik nonushta tayyorlab qo'ying.",
                  "Хранится в холодильнике до 3 дней — приготовьте завтраки сразу на три утра."),
        "image_prompt": "two glass jars of coconut chia pudding, toasted coconut flakes, cacao nibs, mint",
    },
    {
        "slug": "kakao-nibs-pechenye",
        "title": _s("Kakao nibsli bodom pechenyesi", "Миндальное печенье с какао-крупкой"),
        "intro": _s(
            "Choyga yumshoq, xushbo'y pechenye — qandsiz va glyutensiz. Bor-yo'g'i 25 daqiqada tayyor.",
            "Мягкое ароматное печенье к чаю — без сахара и глютена. Готово всего за 25 минут."),
        "minutes": 25,
        "servings": _s("12 dona", "12 штук"),
        "per_serving": {"carbs": 1.5, "kcal": 140},
        "ingredients": [
            _i("150 g", "150 г", "Bodom uni", "Миндальная мука", _ALMOND,
               "Pechenyega yumshoqlik va yong'oq ta'mini beradi.",
               "Даёт печенью нежность и ореховый вкус."),
            _i("50 g", "50 г", "Eritritol", "Эритрит", _ERYTHRITOL,
               "Shakarsiz shirinlik — kaloriyasi deyarli nol.",
               "Сладость без сахара и почти без калорий."),
            _i("50 g", "50 г", "Ghee (eritilgan sariyog')", "Гхи (топлёное масло)", _GHEE,
               "Qaymoqli ta'm beradi va pishganda yonmaydi.",
               "Сливочный вкус, не горит при выпечке."),
            _i("30 g", "30 г", "Kakao nibs", "Какао-крупка", _NIBS,
               "Shokolad bo'lakchalari o'rnida — shakarsiz.",
               "Вместо шоколадной крошки — без сахара."),
            _i("1 ta", "1 шт", "Tuxum", "Яйцо"),
            _i("½ ch.q.", "½ ч.л.", "Soda", "Сода"),
            _i("bir chimdim", "щепотка", "Tuz", "Соль"),
        ],
        "steps": [
            _s("Pechni 175°C ga qizdiring, patnisga pergament to'shang.",
               "Разогрейте духовку до 175°C, застелите противень пергаментом."),
            _s("Eritilgan ghee, eritritol va tuxumni silliq bo'lguncha ko'pchiting.",
               "Взбейте растопленное гхи, эритрит и яйцо до однородности."),
            _s("Bodom uni, soda va tuzni qo'shib, yumshoq xamir qoring.",
               "Добавьте миндальную муку, соду и соль, замесите мягкое тесто."),
            _s("Kakao nibsni qo'shib, qoshiq bilan aralashtiring.",
               "Вмешайте ложкой какао-крупку."),
            _s("Xamirdan 12 ta yong'oqdek sharcha yasab, patnisga qo'ying va kaft bilan biroz bosing.",
               "Скатайте 12 шариков размером с грецкий орех, выложите на противень и слегка прижмите."),
            _s("12–14 daqiqa, chetlari oltin rangga kirguncha pishiring.",
               "Выпекайте 12–14 минут, пока края не станут золотистыми."),
            _s("Patnisda 10 daqiqa soviting — issiqligida yumshoq, sovigach shakli o'rnashadi.",
               "Остудите на противне 10 минут — горячее печенье мягкое, остыв, держит форму."),
        ],
        "tip": _s("Eritritol o'rniga allyuloza ishlatsangiz, pechenye yanada yumshoq va karamelli bo'ladi.",
                  "С аллюлозой вместо эритрита печенье получится ещё мягче, с карамельной ноткой."),
        "image_prompt": "golden almond flour cookies with cacao nibs on parchment, one broken, glass of milk",
    },
    {
        "slug": "urugli-kreker",
        "title": _s("Urug'li qarsildoq kreker", "Хрустящие крекеры из семян"),
        "intro": _s(
            "Chipsga sog'lom muqobil: faqat urug'lar, zaytun yog'i va tuz. Bir patnis — "
            "butun hafta uchun gazak.",
            "Полезная замена чипсам: только семена, оливковое масло и соль. Один противень — "
            "перекус на всю неделю."),
        "minutes": 75,
        "servings": _s("~24 dona", "~24 штуки"),
        "per_serving": {"carbs": 0.8, "kcal": 45},
        "ingredients": [
            _i("60 g", "60 г", "Zig'ir urug'i", "Семена льна", _FLAX_SEEDS,
               "Omega-3 va tolaga boy — krekerning asosi.",
               "Богаты омега-3 и клетчаткой — основа крекера."),
            _i("40 g", "40 г", "Chia urug'i", "Семена чиа", _CHIA,
               "Suvni shimib, urug'larni bir-biriga yopishtiradi.",
               "Впитывает воду и склеивает семена между собой."),
            _i("40 g", "40 г", "Oq kunjut", "Белый кунжут", _SESAME_WHITE,
               "Kalsiyga boy, qovurilganda xushbo'y.",
               "Богат кальцием, ароматный после запекания."),
            _i("20 g", "20 г", "Qora kunjut", "Чёрный кунжут", _SESAME_BLACK,
               "Chiroyli ko'rinish va boyroq ta'm.",
               "Красивый вид и более насыщенный вкус."),
            _i("50 g", "50 г", "Qovoq urug'i", "Тыквенные семечки", _PUMPKIN,
               "Magniy va rux manbai, yirik qarsillash beradi.",
               "Источник магния и цинка, крупный хруст."),
            _i("1 osh q.", "1 ст.л.", "Psillium", "Псиллиум", _PSYLLIUM_ANY,
               "Massani bog'laydi — kreker yoyilganda yirtilmaydi.",
               "Связывает массу — пласт не рвётся при раскатке."),
            _i("1 osh q.", "1 ст.л.", "Zaytun yog'i (sovuq siqim)", "Оливковое масло (холодного отжима)", _OLIVE,
               "Sog'lom yog' va yengil ta'm.",
               "Полезный жир и мягкий вкус."),
            _i("½ ch.q.", "½ ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Krekerga kerakli sho'rlikni beradi.",
               "Нужная солоноватость для крекера."),
            _i("250 ml", "250 мл", "Iliq suv", "Тёплая вода"),
            _i("ixtiyoriy", "по желанию", "Quritilgan rayhon, sarimsoq kukuni", "Сушёный базилик, чесночный порошок"),
        ],
        "steps": [
            _s("Barcha urug'lar, psillium va tuzni idishda aralashtiring.",
               "Смешайте все семена, псиллиум и соль."),
            _s("Iliq suv va zaytun yog'ini quyib aralashtiring, 15 daqiqa qoldiring — massa yopishqoq bo'ladi.",
               "Влейте тёплую воду и масло, перемешайте и оставьте на 15 минут — масса станет вязкой."),
            _s("Pechni 160°C ga qizdiring.", "Разогрейте духовку до 160°C."),
            _s("Massani pergamentga solib, ustidan ikkinchi pergament yopib, 3–4 mm qalinlikda yoying.",
               "Выложите массу на пергамент, накройте вторым листом и раскатайте пласт толщиной 3–4 мм."),
            _s("Ustki pergamentni olib, pichoq bilan kvadratlarga chizib chiqing.",
               "Снимите верхний лист и надрежьте пласт ножом на квадраты."),
            _s("40–45 daqiqa pishiring, keyin pechni o'chirib, eshigini qiya ochib yana 15 daqiqa quriting.",
               "Выпекайте 40–45 минут, затем выключите духовку и подсушите ещё 15 минут с приоткрытой дверцей."),
            _s("Sovigach chiziqlar bo'ylab sindiring. O'tli qaymoqli pishloq sousi bilan torting.",
               "Остывший пласт разломайте по надрезам. Подавайте со сливочным сыром с зеленью."),
        ],
        "tip": _s("Germetik bankada 2 haftagacha qarsildoqligicha saqlanadi.",
                  "В герметичной банке остаются хрустящими до 2 недель."),
        "image_prompt": "seed crackers of flax, chia, sesame, pumpkin seeds, herbed cream cheese dip",
    },
    {
        "slug": "tovuq-nuggets",
        "title": _s("Bodom va kunjut qobig'idagi tovuq", "Курица в миндально-кунжутной панировке"),
        "intro": _s(
            "Bolalar ham, kattalar ham sevadigan qarsildoq nuggets — un va non ushog'isiz. "
            "Salat va sarimsoqli sous bilan to'liq kechki ovqat.",
            "Хрустящие наггетсы, которые любят и дети, и взрослые — без муки и сухарей. "
            "С салатом и чесночным соусом — полноценный ужин."),
        "minutes": 30,
        "servings": _s("3 kishilik", "3 порции"),
        "per_serving": {"carbs": 4, "kcal": 420},
        "ingredients": [
            _i("80 g", "80 г", "Bodom uni", "Миндальная мука", _ALMOND,
               "Non ushog'i o'rnida — qarsildoq va past uglevodli.",
               "Вместо сухарей — хрустит и почти без углеводов."),
            _i("30 g", "30 г", "Oq kunjut", "Белый кунжут", _SESAME_WHITE,
               "Qobiqqa qo'shimcha qarsillash beradi.",
               "Дополнительный хруст панировки."),
            _i("3 osh q.", "3 ст.л.", "Ghee (qovurish uchun)", "Гхи (для жарки)", _GHEE,
               "Yuqori haroratga chidamli — tutun chiqarmaydi.",
               "Выдерживает высокую температуру — не дымит."),
            _i("1 ch.q.", "1 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Go'sht ta'mini ochadi.", "Раскрывает вкус мяса."),
            _i("500 g", "500 г", "Tovuq filesi", "Куриное филе"),
            _i("2 ta", "2 шт", "Tuxum", "Яйца"),
            _i("bir chimdim", "по щепотке", "Qora qalampir, paprika", "Чёрный перец, паприка"),
            _i("3 osh q.", "3 ст.л.", "Qaymoq yoki grek yogurti (sous)", "Сметана или греческий йогурт (соус)"),
            _i("1 bo'lak", "1 зубчик", "Sarimsoq, limon sharbati (sous)", "Чеснок, лимонный сок (соус)"),
            _i("1 likop", "1 тарелка", "Bodring, pomidor, ko'katlar (salat)", "Огурец, помидоры, зелень (салат)"),
        ],
        "steps": [
            _s("Tovuq filesini 3–4 sm bo'laklarga kesing, tuz va qalampir seping.",
               "Нарежьте филе кусочками 3–4 см, посолите и поперчите."),
            _s("Bir idishda tuxumni chayqating, ikkinchisida bodom uni, kunjut va paprikani aralashtiring.",
               "В одной миске взбейте яйца, в другой смешайте миндальную муку, кунжут и паприку."),
            _s("Har bir bo'lakni avval tuxumga, keyin bodom-kunjut aralashmasiga botiring.",
               "Обмакните каждый кусочек сначала в яйцо, затем в миндально-кунжутную смесь."),
            _s("Tovada ghee'ni qizdiring va o'rtacha olovda har tomonini 3–4 daqiqadan oltin rangga "
               "kelguncha qovuring.",
               "Разогрейте гхи и обжарьте на среднем огне по 3–4 минуты с каждой стороны до золотистого цвета."),
            _s("Sous uchun qaymoq, maydalangan sarimsoq va limon sharbatini aralashtiring.",
               "Для соуса смешайте сметану, измельчённый чеснок и лимонный сок."),
            _s("Nuggetsni yangi salat, limon bo'lagi va sarimsoqli sous bilan torting.",
               "Подавайте наггетсы со свежим салатом, долькой лимона и чесночным соусом."),
        ],
        "tip": _s("Pechda ham bo'ladi: 200°C da 18–20 daqiqa, o'rtasida bir marta ag'darib.",
                  "Можно в духовке: 200°C, 18–20 минут, один раз перевернув."),
        "image_prompt": "almond flour and sesame crusted chicken nuggets, green salad, garlic sauce, lemon",
    },    # ─── 2026-10-17: 10 more (owner: "saytga yana 10 xil dolzarb va bizdagi
    # masalliqlardan tayyorlash mumkin bo'lgan ketochilar va dietadagilar va
    # ozishni istaganlar va diabetlar orasida dolzarb bo'lgan retseptlar").
    {
        "slug": "keto-pitsa",
        "title": _s("Bodom unidan keto pitsa", "Кето-пицца на миндальной муке"),
        "intro": _s(
            "Pitsani sog'inib yurganlar uchun: asosi bodom uni va pishloqdan, bug'doy unisiz. "
            "Bir bo'lagida atigi ~6 g uglevod, oddiy pitsada esa ~35 g.",
            "Для тех, кто скучает по пицце: основа из миндальной муки и сыра, без пшеничной муки. "
            "В куске всего ~6 г углеводов, в обычной пицце — ~35 г."),
        "minutes": 40,
        "servings": _s("1 ta pitsa (26 sm), 4 bo'lak", "1 пицца (26 см), 4 куска"),
        "per_serving": {"carbs": 6, "kcal": 400},
        "ingredients": [
            _i("100 g", "100 г", "Bodom uni", "Миндальная мука", _ALMOND,
               "Asosning asosi: bug'doy unidan 7 baravar kam uglevod.",
               "Основа теста: в 7 раз меньше углеводов, чем в пшеничной муке."),
            _i("1/2 ch.q.", "1/2 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Xamir va sous ta'mini ochadi.", "Раскрывает вкус теста и соуса."),
            _i("1 osh q.", "1 ст.л.", "Zaytun yog'i", "Оливковое масло", _OLIVE,
               "Qolipni yog'lash va pitsa ustiga.", "Смазать форму и полить пиццу."),
            _i("150 g", "150 г", "Mozzarella (xamirga)", "Моцарелла (в тесто)"),
            _i("100 g", "100 г", "Mozzarella (ustiga)", "Моцарелла (сверху)"),
            _i("1 ta", "1 шт", "Tuxum", "Яйцо"),
            _i("3 osh q.", "3 ст.л.", "Shakarsiz tomat sousi yoki pastasi", "Томатный соус или паста без сахара"),
            _i("100 g", "100 г", "Qaynatilgan tovuq yoki qo'ziqorin", "Варёная курица или грибы"),
            _i("1/2 ch.q.", "1/2 ч.л.", "Quritilgan oregano yoki rayhon", "Сушёный орегано или базилик"),
        ],
        "steps": [
            _s("Pechni 200°C ga qizdiring. Laganga pergament qog'oz to'shab, zaytun yog'i surting.",
               "Разогрейте духовку до 200°C. Застелите противень пергаментом и смажьте оливковым маслом."),
            _s("150 g mozzarellani mayda to'g'rab, mikroto'lqinli pechda 1 daqiqa (yoki suv hammomida) "
               "to'liq eriting va aralashtiring.",
               "Натрите 150 г моцареллы, растопите в микроволновке 1 минуту (или на водяной бане) и перемешайте."),
            _s("Erigan pishloqqa bodom uni, tuxum va tuzni qo'shing va qoshiq bilan, keyin qo'l bilan "
               "bir xil xamir bo'lguncha qoring. Xamir yopishsa, qo'lni ho'llang.",
               "Добавьте к сыру миндальную муку, яйцо и соль и замесите сначала ложкой, затем руками до "
               "однородного теста. Если липнет — смочите руки."),
            _s("Xamirni pergamentga qo'yib, ikkinchi pergament ostidan 26 sm doira qilib, 4–5 mm qalinlikda yoying. "
               "Vilka bilan 8–10 joyini teshib chiqing.",
               "Раскатайте тесто между двумя листами пергамента в круг 26 см толщиной 4–5 мм. "
               "Наколите вилкой в 8–10 местах."),
            _s("Asosni o'zini 200°C da 10 daqiqa, chetlari qizarguncha pishiring.",
               "Выпекайте одну основу 10 минут при 200°C, до румяных краёв."),
            _s("Asos ustiga tomat sousini surting, tovuq (yoki qo'ziqorin) va 100 g mozzarellani tering, "
               "oregano seping.",
               "Смажьте основу томатным соусом, выложите курицу (или грибы) и 100 г моцареллы, посыпьте орегано."),
            _s("Yana 8–10 daqiqa, pishloq erib, qizarguncha pishiring. 3 daqiqa sovutib, 4 bo'lakka kesing.",
               "Выпекайте ещё 8–10 минут, пока сыр не расплавится и не зарумянится. Остудите 3 минуты и "
               "нарежьте на 4 куска."),
        ],
        "tip": _s("Asosni oldindan pishirib muzlatib qo'ysangiz, kechki ovqatga pitsa 10 daqiqada tayyor.",
                  "Испеките основы заранее и заморозьте — пицца к ужину будет готова за 10 минут."),
        "image_prompt": "keto pizza on almond flour crust, melted mozzarella, chicken and mushrooms, basil leaves, "
                        "one slice pulled out, tomato sauce, round wooden board",
    },
    {
        "slug": "kokos-quymoq",
        "title": _s("Kokos unidan keto quymoq", "Кето-панкейки из кокосовой муки"),
        "intro": _s(
            "Yumshoq, momiqdek quymoqlar — shakarsiz va glyutensiz. Dam olish kunining nonushtasi: "
            "15 daqiqada tayyor, bir porsiyada ~6 g uglevod.",
            "Мягкие, пышные панкейки — без сахара и глютена. Завтрак выходного дня: готов за 15 минут, "
            "в порции ~6 г углеводов."),
        "minutes": 20,
        "servings": _s("2 kishilik (8 dona)", "2 порции (8 штук)"),
        "per_serving": {"carbs": 6, "kcal": 305},
        "ingredients": [
            _i("40 g (4 osh q.)", "40 г (4 ст.л.)", "Kokos uni", "Кокосовая мука", _COCONUT_FLOUR,
               "Tolaga juda boy: oz miqdori ham quymoqni to'yimli qiladi.",
               "Очень много клетчатки: даже немного муки делает панкейки сытными."),
            _i("1 osh q.", "1 ст.л.", "Eritritol", "Эритрит", _ERYTHRITOL,
               "Shirinlik beradi, qondagi shakarni oshirmaydi.", "Даёт сладость, не повышая сахар в крови."),
            _i("2 osh q.", "2 ст.л.", "Kokos chipsi (ustiga)", "Кокосовые чипсы (сверху)", _COCONUT_FLAKES,
               "Qarsildoq va xushbo'y bezak.", "Хрустящее ароматное украшение."),
            _i("4 ta", "4 шт", "Tuxum", "Яйца"),
            _i("80 ml", "80 мл", "Sut yoki kokos suti", "Молоко или кокосовое молоко"),
            _i("1/2 ch.q.", "1/2 ч.л.", "Pishirish kukuni (razrixlitel)", "Разрыхлитель"),
            _i("1 chimdim", "щепотка", "Tuz", "Соль"),
            _i("1 osh q.", "1 ст.л.", "Sariyog' yoki kokos yog'i (tova uchun)", "Сливочное или кокосовое масло (для сковороды)"),
        ],
        "steps": [
            _s("Idishda tuxum, sut va eritritolni vilka yoki venchik bilan 1 daqiqa ko'pirtiring.",
               "Взбейте вилкой или венчиком яйца, молоко и эритрит 1 минуту."),
            _s("Kokos uni, pishirish kukuni va tuzni qo'shib, quyruqsiz aralashtiring.",
               "Добавьте кокосовую муку, разрыхлитель и соль и перемешайте без комков."),
            _s("Xamirni 5 daqiqa qo'yib qo'ying — kokos uni suyuqlikni shimib, xamir quyuq qaymoqdek bo'ladi.",
               "Оставьте тесто на 5 минут — кокосовая мука впитает жидкость, и тесто станет как густая сметана."),
            _s("Tovani past-o'rtacha olovda qizdirib, ozgina yog' surting (olov baland bo'lsa, quymoq ichi pishmay kuyadi).",
               "Разогрейте сковороду на слабом-среднем огне и слегка смажьте маслом (на сильном огне подгорит "
               "снаружи и останется сырым внутри)."),
            _s("Har bir quymoq uchun 2 osh qoshiq xamir quying va qoshiq bilan 8 sm doira qilib tekislang.",
               "Выкладывайте по 2 ст. ложки теста на панкейк и разровняйте ложкой в круг 8 см."),
            _s("Sirtida pufakchalar paydo bo'lguncha 2–3 daqiqa pishiring, ehtiyotkorlik bilan ag'darib, yana 2 daqiqa pishiring.",
               "Жарьте 2–3 минуты до появления пузырьков, аккуратно переверните и жарьте ещё 2 минуты."),
            _s("Ustiga kokos chipsi sepib, rezavor yoki shakarsiz qaymoq bilan torting.",
               "Посыпьте кокосовыми чипсами и подавайте с ягодами или несладкой сметаной."),
        ],
        "tip": _s("Kokos unini ko'z bilan ko'paytirmang: bir qoshiq ortiqcha ham quymoqni quruq qiladi.",
                  "Не добавляйте кокосовую муку «на глаз»: даже лишняя ложка делает панкейки сухими."),
        "image_prompt": "stack of fluffy coconut flour pancakes, toasted coconut chips on top, fresh raspberries, "
                        "small jug of cream, breakfast table",
    },
    {
        "slug": "yashil-grechka-palov",
        "title": _s("Yashil grechkadan PP palov", "ПП-плов из зелёной гречки"),
        "intro": _s(
            "Palovni yaxshi ko'rasiz, lekin guruch qondagi shakarni tez ko'taradimi? Yashil grechka "
            "bilan palov ta'mi saqlanadi, glikemik indeksi esa oq guruchdagidan ancha past.",
            "Любите плов, но рис быстро поднимает сахар? С зелёной гречкой вкус плова сохраняется, "
            "а гликемический индекс заметно ниже, чем у белого риса."),
        "minutes": 50,
        "servings": _s("4 kishilik", "4 порции"),
        "per_serving": {"carbs": 36, "kcal": 380},
        "ingredients": [
            _i("200 g", "200 г", "Yashil grechka", "Зелёная гречка", _GREEN_BUCKWHEAT,
               "Qovurilmagan grechka: tola va oqsilga boy, glyutensiz.",
               "Необжаренная гречка: много клетчатки и белка, без глютена."),
            _i("2 osh q.", "2 ст.л.", "Zaytun yog'i (qovurish uchun)", "Оливковое масло (для жарки)", _OLIVE_FRY,
               "Qovurishga chidamli, palov uchun yetarli miqdor.",
               "Подходит для жарки, для плова этого достаточно."),
            _i("1 ch.q.", "1 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Ta'mni ochadi.", "Раскрывает вкус."),
            _i("400 g", "400 г", "Tovuq filesi (yoki yog'siz mol go'shti)", "Куриное филе (или постная говядина)"),
            _i("2 ta (200 g)", "2 шт (200 г)", "Sabzi", "Морковь"),
            _i("1 ta", "1 шт", "Piyoz", "Лук"),
            _i("1 ch.q.", "1 ч.л.", "Zira", "Зира"),
            _i("1 bosh", "1 головка", "Sarimsoq", "Чеснок"),
            _i("450 ml", "450 мл", "Issiq suv", "Горячая вода"),
        ],
        "steps": [
            _s("Grechkani 3 marta, suvi tiniq bo'lguncha yuving va elakda suvini to'kib qo'ying.",
               "Промойте гречку 3 раза до прозрачной воды и откиньте на сито."),
            _s("Tovuqni 3 sm bo'laklarga, piyozni yarim halqa, sabzini somoncha qilib to'g'rang.",
               "Нарежьте курицу кусочками 3 см, лук — полукольцами, морковь — соломкой."),
            _s("Qozonda zaytun yog'ini o'rtacha olovda qizdirib, tovuqni 5–6 daqiqa, oqarguncha qovuring.",
               "Разогрейте масло в казане на среднем огне и обжарьте курицу 5–6 минут, пока не побелеет."),
            _s("Piyozni qo'shib 3 daqiqa, keyin sabzini qo'shib yana 5 daqiqa, yumshaguncha qovuring.",
               "Добавьте лук и жарьте 3 минуты, затем морковь — ещё 5 минут, до мягкости."),
            _s("Tuz va zirani seping, 450 ml issiq suv quying va qaynatib oling.",
               "Посолите, добавьте зиру, влейте 450 мл горячей воды и доведите до кипения."),
            _s("Grechkani tekis yoying (aralashtirmang), o'rtasiga butun sarimsoqni tiqing.",
               "Ровно распределите гречку сверху (не перемешивайте), в центр вдавите целую головку чеснока."),
            _s("Qopqoqni yopib, past olovda 20 daqiqa dimlang — suv to'liq shimilsin.",
               "Накройте крышкой и томите на слабом огне 20 минут, пока вода полностью не впитается."),
            _s("Olovni o'chirib, yana 10 daqiqa dam bering, so'ng aralashtirib torting.",
               "Выключите огонь, дайте постоять ещё 10 минут, затем перемешайте и подавайте."),
        ],
        "tip": _s("Diabet bo'lsa, porsiyani yangi sabzavot salati bilan birga yeng — tola qondagi "
                  "shakarning ko'tarilishini yanada sekinlashtiradi.",
                  "При диабете ешьте порцию вместе с салатом из свежих овощей — клетчатка ещё больше "
                  "замедляет подъём сахара."),
        "image_prompt": "uzbek style pilaf made with green buckwheat instead of rice, chicken pieces, julienned "
                        "carrots, whole garlic head on top, served in a cast iron kazan, fresh tomato salad aside",
    },
    {
        "slug": "shakarsiz-chizkeyk",
        "title": _s("Shakarsiz chizkeyk (bodom uni asosli)", "Чизкейк без сахара на миндальной основе"),
        "intro": _s(
            "Bayram stoliga ham, diabeti borlarga ham: kremdek yumshoq chizkeyk, shakar va bug'doy unisiz. "
            "Bir bo'lakda ~4,5 g uglevod — oddiy chizkeykda ~30 g.",
            "И на праздничный стол, и для тех, у кого диабет: нежный, как крем, чизкейк без сахара и "
            "пшеничной муки. В куске ~4,5 г углеводов — в обычном ~30 г."),
        "minutes": 80,
        "rest": _s("+ muzlatkichda kamida 6 soat", "+ минимум 6 часов в холодильнике"),
        "servings": _s("8 bo'lak (20 sm qolip)", "8 кусков (форма 20 см)"),
        "per_serving": {"carbs": 4.5, "kcal": 395},
        "ingredients": [
            _i("120 g", "120 г", "Bodom uni (asos uchun)", "Миндальная мука (для основы)", _ALMOND,
               "Pechene o'rnidagi asos — qarsildoq va past uglevodli.",
               "Основа вместо печенья — хрустящая и низкоуглеводная."),
            _i("1 osh q. + 80 g", "1 ст.л. + 80 г", "Eritritol (asosga va kremga)", "Эритрит (в основу и крем)", _ERYTHRITOL,
               "Shakar o'rnida: qondagi shakarni ko'tarmaydi.", "Вместо сахара: не повышает сахар в крови."),
            _i("40 g", "40 г", "Sariyog' (eritilgan)", "Сливочное масло (растопленное)"),
            _i("500 g", "500 г", "Krem-pishloq yoki yumshoq yog'li tvorog (9%)", "Сливочный сыр или мягкий жирный творог (9%)"),
            _i("2 ta", "2 шт", "Tuxum (xona haroratida)", "Яйца (комнатной температуры)"),
            _i("100 ml", "100 мл", "Qaymoq (20–33%)", "Сливки (20–33%)"),
            _i("1 osh q.", "1 ст.л.", "Limon sharbati", "Лимонный сок"),
            _i("1 chimdim", "щепотка", "Vanilin", "Ванилин"),
        ],
        "steps": [
            _s("Pechni 160°C ga qizdiring. 20 sm li ajraladigan qolip tubiga pergament to'shang.",
               "Разогрейте духовку до 160°C. Застелите дно разъёмной формы 20 см пергаментом."),
            _s("Asos: bodom uni, 1 osh qoshiq eritritol va eritilgan sariyog'ni aralashtirib, qolip tubiga "
               "qoshiq bilan zich bosib yoying. 10 daqiqa pishirib, sovuting.",
               "Основа: смешайте миндальную муку, 1 ст. ложку эритрита и растопленное масло, плотно утрамбуйте "
               "ложкой по дну формы. Выпекайте 10 минут и остудите."),
            _s("Krem: krem-pishloq (yoki tvorog)ni 80 g eritritol bilan mikserda past tezlikda 1 daqiqa silliq bo'lguncha uring.",
               "Крем: взбейте сливочный сыр (или творог) с 80 г эритрита на низкой скорости 1 минуту до гладкости."),
            _s("Tuxumni birma-bir qo'shing, keyin qaymoq, limon sharbati va vanilinni qo'shib, faqat aralashguncha "
               "uring (ko'p ursangiz, chizkeyk yoriladi).",
               "Добавьте яйца по одному, затем сливки, лимонный сок и ванилин — взбивайте только до "
               "соединения (если перебить, чизкейк треснет)."),
            _s("Kremni asos ustiga quying va tekislang.",
               "Вылейте крем на основу и разровняйте."),
            _s("Pechning pastki qavatiga suvli lagan qo'ying (bug' yorilishdan saqlaydi) va chizkeykni "
               "160°C da 50–55 daqiqa pishiring — o'rtasi biroz titrab turishi kerak.",
               "Поставьте на нижний уровень противень с водой (пар защитит от трещин) и выпекайте "
               "50–55 минут при 160°C — центр должен слегка дрожать."),
            _s("Pechni o'chirib, eshigini qiya ochib, chizkeykni ichida 1 soat sovuting.",
               "Выключите духовку, приоткройте дверцу и оставьте чизкейк внутри на 1 час."),
            _s("Muzlatkichda kamida 6 soat (yaxshisi tun bo'yi) qotiring, keyin 8 bo'lakka kesing.",
               "Уберите в холодильник минимум на 6 часов (лучше на ночь), затем нарежьте на 8 кусков."),
        ],
        "tip": _s("Kesishda pichoqni issiq suvga botirib, har kesgandan keyin artib turing — bo'laklar tekis chiqadi.",
                  "Режьте ножом, окунутым в горячую воду, вытирая после каждого разреза, — куски будут ровными."),
        "image_prompt": "creamy sugar-free cheesecake on almond flour crust, one slice cut out showing smooth "
                        "texture, fresh raspberries and mint on top, light ceramic cake stand",
    },
    {
        "slug": "keto-lavash",
        "title": _s("Psilliumli keto lavash (shaurma uchun)", "Кето-лаваш с псиллиумом (для шаурмы)"),
        "intro": _s(
            "Shaurma, rulet yoki o'rama — endi bug'doy lavashisiz. Yumshoq, egiluvchan va yirtilmaydi; "
            "bitta lavashda atigi ~2 g uglevod.",
            "Шаурма, ролл или врап — теперь без пшеничного лаваша. Мягкий, гибкий и не рвётся; "
            "в одном лаваше всего ~2 г углеводов."),
        "minutes": 30,
        "servings": _s("6 ta lavash (20 sm)", "6 лавашей (20 см)"),
        "per_serving": {"carbs": 2, "kcal": 125},
        "ingredients": [
            _i("100 g", "100 г", "Bodom uni", "Миндальная мука", _ALMOND,
               "Lavashga yumshoqlik va to'yimlilik beradi.", "Даёт лавашу мягкость и сытность."),
            _i("30 g (3 osh q.)", "30 г (3 ст.л.)", "Psillium uni", "Псиллиум (мука)", _PSYLLIUM_FLOUR,
               "Glyuten o'rnini bosadi: xamir egiluvchan bo'ladi va yirtilmaydi.",
               "Заменяет глютен: тесто становится эластичным и не рвётся."),
            _i("1/2 ch.q.", "1/2 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Ta'mni ochadi.", "Раскрывает вкус."),
            _i("1 osh q.", "1 ст.л.", "Zaytun yog'i", "Оливковое масло", _OLIVE,
               "Xamirni yumshoq qiladi.", "Делает тесто мягким."),
            _i("150 ml", "150 мл", "Qaynoq suv", "Кипяток"),
        ],
        "steps": [
            _s("Idishda bodom uni, psillium uni va tuzni aralashtiring.",
               "Смешайте в миске миндальную муку, псиллиум и соль."),
            _s("Zaytun yog'i va qaynoq suvni quyib, qoshiq bilan tez aralashtiring — psillium suvni shimib, "
               "xamir quyuqlashadi.",
               "Влейте масло и кипяток и быстро перемешайте ложкой — псиллиум впитает воду, тесто загустеет."),
            _s("Biroz sovigach, qo'l bilan 1 daqiqa yumshoq xamir qoring va 10 daqiqa dam bering.",
               "Когда немного остынет, вымесите руками 1 минуту до мягкого теста и дайте отдохнуть 10 минут."),
            _s("Xamirni 6 ta teng bo'lakka bo'ling. Har birini ikki pergament orasida 20 sm doira qilib, "
               "1–2 mm qalinlikda yoying.",
               "Разделите тесто на 6 равных частей. Каждую раскатайте между двумя листами пергамента "
               "в круг 20 см толщиной 1–2 мм."),
            _s("Quruq (yog'siz) tovani o'rtacha olovda qizdiring.",
               "Разогрейте сухую (без масла) сковороду на среднем огне."),
            _s("Lavashni ustki pergamentdan ajratib, tovaga ag'daring va har tomonini 1–1,5 daqiqadan, "
               "dog'lar paydo bo'lguncha pishiring.",
               "Снимите верхний пергамент, переверните лаваш на сковороду и жарьте по 1–1,5 минуты "
               "с каждой стороны, до появления пятнышек."),
            _s("Tayyor lavashlarni ustma-ust qo'yib, sochiq bilan yoping — bug'da yumshoq va egiluvchan qoladi.",
               "Складывайте готовые лаваши стопкой и накрывайте полотенцем — в пару они останутся мягкими и гибкими."),
        ],
        "tip": _s("Ichiga: qovurilgan tovuq, bodring, pomidor, karam va qatiq-sarimsoq sousi — uy shaurmasi tayyor.",
                  "Начинка: жареная курица, огурец, помидор, капуста и соус из йогурта с чесноком — домашняя шаурма готова."),
        "image_prompt": "thin keto flatbread wraps made with almond flour and psyllium, one rolled shawarma style "
                        "with grilled chicken, cucumber, tomato and garlic yogurt sauce, stack of wraps aside",
    },
    {
        "slug": "urugli-granola",
        "title": _s("Shakarsiz urug'li granola", "Гранола из семян без сахара"),
        "intro": _s(
            "Do'kon granolasining yarmi shakar. Bu granola urug' va yong'oqdan: qarsildoq, shirin, "
            "lekin qondagi shakarni ko'tarmaydi. Yogurt yoki sut bilan — 3 daqiqalik nonushta.",
            "Половина магазинной гранолы — сахар. Эта — из семян и орехов: хрустящая, сладкая, "
            "но не повышает сахар. С йогуртом или молоком — завтрак за 3 минуты."),
        "minutes": 35,
        "servings": _s("9 porsiya (30 g dan)", "9 порций (по 30 г)"),
        "per_serving": {"carbs": 2, "kcal": 165},
        "ingredients": [
            _i("100 g", "100 г", "Qovoq urug'i", "Тыквенные семечки", _PUMPKIN,
               "Magniy va ruxga boy, granolaning asosi.", "Богаты магнием и цинком — основа гранолы."),
            _i("50 g", "50 г", "Kokos chipsi", "Кокосовые чипсы", _COCONUT_FLAKES,
               "Qarsildoq va tabiiy shirin ta'm.", "Хруст и естественная сладость."),
            _i("50 g", "50 г", "Pista mag'zi", "Фисташки", _PISTACHIO,
               "Oqsil va qarsillash qo'shadi.", "Добавляют белок и хруст."),
            _i("2 osh q.", "2 ст.л.", "Qora kunjut", "Чёрный кунжут", _SESAME_BLACK,
               "Kalsiy va chiroyli rang.", "Кальций и красивый цвет."),
            _i("2 osh q.", "2 ст.л.", "Zig'ir urug'i", "Семена льна", _FLAX_SEEDS,
               "Omega-3 va tola.", "Омега-3 и клетчатка."),
            _i("2 osh q.", "2 ст.л.", "Eritritol", "Эритрит", _ERYTHRITOL,
               "Shakarsiz shirinlik.", "Сладость без сахара."),
            _i("1 ta", "1 шт", "Tuxum oqi", "Яичный белок"),
            _i("1 osh q.", "1 ст.л.", "Kokos yog'i yoki sariyog' (eritilgan)", "Кокосовое или сливочное масло (растопленное)"),
            _i("1 ch.q.", "1 ч.л.", "Dolchin", "Корица"),
            _i("1 chimdim", "щепотка", "Tuz", "Соль"),
        ],
        "steps": [
            _s("Pechni 150°C ga qizdiring. Laganga pergament qog'oz to'shang.",
               "Разогрейте духовку до 150°C. Застелите противень пергаментом."),
            _s("Pista mag'zini pichoq bilan yirik (no'xatdek) to'g'rang.",
               "Крупно (размером с горошину) порубите фисташки ножом."),
            _s("Katta idishda tuxum oqini vilka bilan 30 soniya ko'pirtiring, eritritol, erigan yog', dolchin "
               "va tuzni qo'shib aralashtiring.",
               "В большой миске взбейте белок вилкой 30 секунд, добавьте эритрит, растопленное масло, корицу "
               "и соль, перемешайте."),
            _s("Barcha urug'lar, kokos chipsi va pistani qo'shib, har biri aralashmaga bulanguncha aralashtiring.",
               "Добавьте все семена, кокосовые чипсы и фисташки и перемешайте, чтобы всё покрылось смесью."),
            _s("Laganga 1 sm qalinlikda zich yoying.",
               "Распределите по противню плотным слоем 1 см."),
            _s("150°C da 25 daqiqa pishiring; 12-daqiqada kurakcha bilan ehtiyotkorlik bilan ag'darib chiqing. "
               "Oltinrang bo'lsa — tayyor.",
               "Выпекайте 25 минут при 150°C; на 12-й минуте аккуратно переверните лопаткой. "
               "Стала золотистой — готово."),
            _s("Laganda to'liq soviting (sovigach qotadi), keyin bo'laklarga sindirib, yopiq bankaga soling.",
               "Полностью остудите на противне (застынет при остывании), разломайте и пересыпьте в закрытую банку."),
        ],
        "tip": _s("Bir porsiya — 3 osh qoshiq (30 g) tabiiy yogurt yoki sut bilan. Yopiq bankada 2 hafta saqlanadi.",
                  "Порция — 3 ст. ложки (30 г) с натуральным йогуртом или молоком. В закрытой банке хранится 2 недели."),
        "image_prompt": "homemade sugar-free granola clusters with pumpkin seeds, coconut chips, pistachios and black "
                        "sesame in a glass jar and a bowl of greek yogurt topped with granola",
    },
    {
        "slug": "qora-guruch-salat",
        "title": _s("Qora guruch va tovuqli salat", "Салат с чёрным рисом и курицей"),
        "intro": _s(
            "To'yimli, lekin og'ir emas: ozishni istaganlar uchun ideal tushlik. Qora guruch oddiy "
            "guruchdan tolaga boy va sekin hazm bo'ladi — uzoq to'q tutadi.",
            "Сытно, но не тяжело: идеальный обед для тех, кто худеет. Чёрный рис богаче клетчаткой, "
            "чем обычный, и переваривается медленно — надолго насыщает."),
        "minutes": 45,
        "servings": _s("2 kishilik", "2 порции"),
        "per_serving": {"carbs": 40, "kcal": 480},
        "ingredients": [
            _i("100 g", "100 г", "Qora guruch", "Чёрный рис", _BLACK_RICE,
               "Antotsianlarga boy, tola ko'p — uzoq to'q tutadi.",
               "Богат антоцианами и клетчаткой — надолго насыщает."),
            _i("1 osh q.", "1 ст.л.", "Qora kunjut", "Чёрный кунжут", _SESAME_BLACK,
               "Yong'oqsimon ta'm va kalsiy.", "Ореховый вкус и кальций."),
            _i("2 osh q.", "2 ст.л.", "Zaytun yog'i (sous)", "Оливковое масло (заправка)", _OLIVE,
               "Foydali yog' — sousning asosi.", "Полезный жир — основа заправки."),
            _i("1 osh q.", "1 ст.л.", "Olma sirkasi (sous)", "Яблочный уксус (заправка)", _VINEGAR,
               "Sousga yengil nordonlik beradi.", "Даёт заправке лёгкую кислинку."),
            _i("1/2 ch.q.", "1/2 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Ta'mni ochadi.", "Раскрывает вкус."),
            _i("250 g", "250 г", "Tovuq filesi", "Куриное филе"),
            _i("1 ta", "1 шт", "Bodring", "Огурец"),
            _i("1 ta", "1 шт", "Pomidor", "Помидор"),
            _i("1 bog'", "1 пучок", "Ko'kat (shivit yoki petrushka)", "Зелень (укроп или петрушка)"),
            _i("300 ml", "300 мл", "Suv (guruch uchun)", "Вода (для риса)"),
        ],
        "steps": [
            _s("Guruchni 3 marta yuving. 300 ml suvni qaynatib, guruch va bir chimdim tuz soling.",
               "Промойте рис 3 раза. Вскипятите 300 мл воды, всыпьте рис и щепотку соли."),
            _s("Qopqoq ostida past olovda 35 daqiqa pishiring, ortiqcha suvini to'kib, tekis idishda sovuting.",
               "Варите под крышкой на слабом огне 35 минут, слейте лишнюю воду и остудите на тарелке."),
            _s("Shu vaqtda tovuqni qaynab turgan tuzli suvga solib, 15 daqiqa pishiring va sovutib, tolalarga ajrating.",
               "Тем временем опустите курицу в кипящую подсоленную воду, варите 15 минут, остудите и разберите на волокна."),
            _s("Bodring va pomidorni 1 sm kubik, ko'katni mayda to'g'rang.",
               "Нарежьте огурец и помидор кубиком 1 см, зелень — мелко."),
            _s("Sous: zaytun yog'i, olma sirkasi va qolgan tuzni kichik idishda aralashtiring.",
               "Заправка: смешайте в маленькой миске масло, уксус и оставшуюся соль."),
            _s("Katta idishda guruch, tovuq, sabzavot va ko'katni aralashtiring, sousni quyib, yana aralashtiring.",
               "В большой миске смешайте рис, курицу, овощи и зелень, полейте заправкой и снова перемешайте."),
            _s("Ustiga qora kunjut sepib torting.",
               "Посыпьте чёрным кунжутом и подавайте."),
        ],
        "tip": _s("Guruch va tovuqni kechqurun pishirib qo'ysangiz, ertalab 5 daqiqada ishga tushlik tayyor.",
                  "Если отварить рис и курицу с вечера, утром обед на работу готов за 5 минут."),
        "image_prompt": "black rice salad bowl with shredded chicken, cucumber, tomato, fresh dill, black sesame "
                        "seeds, olive oil dressing, served in a wide ceramic bowl",
    },
    {
        "slug": "pistali-pechene",
        "title": _s("Pistali keto pechene", "Кето-печенье с фисташками"),
        "intro": _s(
            "Choy uchun qarsildoq pechene — shakarsiz va bug'doy unisiz. Pista va bodom uni: "
            "bitta pechenyeda ~2 g uglevod.",
            "Хрустящее печенье к чаю — без сахара и пшеничной муки. Фисташки и миндальная мука: "
            "в одной штуке ~2 г углеводов."),
        "minutes": 30,
        "servings": _s("14 dona", "14 штук"),
        "per_serving": {"carbs": 2, "kcal": 120},
        "ingredients": [
            _i("100 g", "100 г", "Pista mag'zi", "Фисташки", _PISTACHIO,
               "Rang, ta'm va qarsillash — pechenening yulduzi.",
               "Цвет, вкус и хруст — звезда этого печенья."),
            _i("100 g", "100 г", "Bodom uni", "Миндальная мука", _ALMOND,
               "Un o'rnida — past uglevodli asos.", "Вместо муки — низкоуглеводная основа."),
            _i("60 g", "60 г", "Eritritol", "Эритрит", _ERYTHRITOL,
               "Shakarsiz shirinlik.", "Сладость без сахара."),
            _i("60 g", "60 г", "Sariyog' (yumshatilgan)", "Сливочное масло (мягкое)"),
            _i("1 ta", "1 шт", "Tuxum", "Яйцо"),
            _i("1 chimdim", "щепотка", "Tuz", "Соль"),
        ],
        "steps": [
            _s("Pechni 170°C ga qizdiring. Laganga pergament qog'oz to'shang.",
               "Разогрейте духовку до 170°C. Застелите противень пергаментом."),
            _s("Pistaning 70 g ini blender yoki kofe maydalagichda maydalang (un bo'lib ketmasin), 30 g ini "
               "pichoq bilan yirik to'g'rang.",
               "70 г фисташек измельчите в блендере или кофемолке (не в пыль), 30 г крупно порубите ножом."),
            _s("Yumshoq sariyog' va eritritolni mikser yoki vilka bilan 2 daqiqa, oqarguncha uring.",
               "Взбейте мягкое масло с эритритом миксером или вилкой 2 минуты до посветления."),
            _s("Tuxumni qo'shib aralashtiring, keyin bodom uni, maydalangan pista va tuzni qo'shib, yumshoq xamir qoring.",
               "Добавьте яйцо, перемешайте, затем всыпьте миндальную муку, молотые фисташки и соль и замесите мягкое тесто."),
            _s("Xamirdan 14 ta yong'oqdek (25 g) sharcha yasang, laganga 3 sm oraliqda tering va kaft bilan 1 sm gacha bosing.",
               "Скатайте 14 шариков размером с грецкий орех (25 г), выложите на противень на расстоянии 3 см и "
               "приплюсните ладонью до 1 см."),
            _s("Har birining ustiga to'g'ralgan pistani sepib, biroz bosing.",
               "Посыпьте каждое рубленными фисташками и слегка прижмите."),
            _s("170°C da 13–15 daqiqa, chetlari oltinrang bo'lguncha pishiring va laganda 10 daqiqa sovuting.",
               "Выпекайте 13–15 минут при 170°C до золотистых краёв и остудите на противне 10 минут."),
        ],
        "tip": _s("Issiqligida yumshoq bo'ladi — bu normal, sovigach qarsillaydi. Yopiq idishda 1 hafta turadi.",
                  "Горячее печенье мягкое — это нормально, остывая, оно станет хрустящим. В закрытой банке — неделя."),
        "image_prompt": "keto pistachio cookies with chopped pistachios on top, cup of black tea, pistachio kernels "
                        "scattered, cooling rack on light oak table",
    },
    {
        "slug": "kokosli-sirniki",
        "title": _s("Kokos unli sirniki", "Сырники на кокосовой муке"),
        "intro": _s(
            "Oddiy sirnikidek mazali, lekin bug'doy uni va shakarsiz. Oqsilga boy nonushta — "
            "tushgacha ochiqmaysiz, bitta sirnikida ~2 g uglevod.",
            "Вкусные, как обычные сырники, но без пшеничной муки и сахара. Белковый завтрак — до обеда "
            "не проголодаетесь, в одном сырнике ~2 г углеводов."),
        "minutes": 25,
        "servings": _s("8 dona", "8 штук"),
        "per_serving": {"carbs": 2, "kcal": 125},
        "ingredients": [
            _i("2 osh q. (20 g)", "2 ст.л. (20 г)", "Kokos uni", "Кокосовая мука", _COCONUT_FLOUR,
               "Bug'doy uni o'rnida: oz miqdori ham massani ushlab turadi.",
               "Вместо пшеничной муки: даже немного хорошо держит массу."),
            _i("2 osh q.", "2 ст.л.", "Eritritol", "Эритрит", _ERYTHRITOL,
               "Shakarsiz shirinlik.", "Сладость без сахара."),
            _i("400 g", "400 г", "Tvorog (5–9%, quruqroq)", "Творог (5–9%, суховатый)"),
            _i("2 ta", "2 шт", "Tuxum", "Яйца"),
            _i("1 chimdim", "щепотка", "Vanilin", "Ванилин"),
            _i("1 chimdim", "щепотка", "Tuz", "Соль"),
            _i("1 osh q.", "1 ст.л.", "Yog' (qovurish uchun)", "Масло (для жарки)"),
            _i("2 osh q.", "2 ст.л.", "Qaymoq yoki tabiiy yogurt (torting uchun)", "Сметана или натуральный йогурт (для подачи)"),
        ],
        "steps": [
            _s("Tvorogni vilka bilan yaxshilab ezing (donador bo'lsa, elakdan o'tkazing).",
               "Хорошо разомните творог вилкой (если зернистый — протрите через сито)."),
            _s("Tuxum, eritritol, vanilin va tuzni qo'shib aralashtiring.",
               "Добавьте яйца, эритрит, ванилин и соль, перемешайте."),
            _s("Kokos unini qo'shib aralashtiring va 10 daqiqa qo'yib qo'ying — kokos uni namni shimib, massa quyuqlashadi.",
               "Всыпьте кокосовую муку, перемешайте и оставьте на 10 минут — мука впитает влагу, масса загустеет."),
            _s("Ho'l qo'l bilan 8 ta kulcha (1,5 sm qalinlikda, 6 sm diametrda) yasang.",
               "Влажными руками сформуйте 8 сырников толщиной 1,5 см и диаметром 6 см."),
            _s("Tovada yog'ni past-o'rtacha olovda qizdiring.",
               "Разогрейте масло на сковороде на слабом-среднем огне."),
            _s("Sirnikini har tomonini 3–4 daqiqadan, qizarguncha qovuring; oxirida qopqoq ostida 2 daqiqa ushlang.",
               "Обжарьте сырники по 3–4 минуты с каждой стороны до румяности; в конце подержите 2 минуты под крышкой."),
            _s("Qaymoq yoki tabiiy yogurt bilan issiq holda torting.",
               "Подавайте горячими со сметаной или натуральным йогуртом."),
        ],
        "tip": _s("Massa qo'lga yopishsa, yana 1 choy qoshiq kokos uni qo'shing — ko'p emas, aks holda quruq bo'ladi.",
                  "Если масса липнет к рукам, добавьте ещё 1 ч. ложку кокосовой муки — не больше, иначе будут сухими."),
        "image_prompt": "golden pan-fried cottage cheese pancakes syrniki made with coconut flour, sour cream, "
                        "fresh berries, sprinkle of coconut, breakfast plate",
    },
    {
        "slug": "keto-bulochka",
        "title": _s("Zig'ir unidan keto bulochka (burger uchun)", "Кето-булочки из льняной муки (для бургеров)"),
        "intro": _s(
            "Burger, sendvich yoki shunchaki choyga — yumshoq, g'ovak bulochkalar. Zig'ir uni va psillium: "
            "bitta bulochkada ~1,5 g uglevod, oddiy bulochkada ~25 g.",
            "Для бургера, сэндвича или просто к чаю — мягкие пористые булочки. Льняная мука и псиллиум: "
            "в одной ~1,5 г углеводов, в обычной ~25 г."),
        "minutes": 55,
        "servings": _s("4 dona", "4 штуки"),
        "per_serving": {"carbs": 1.5, "kcal": 115},
        "ingredients": [
            _i("100 g", "100 г", "Zig'ir uni", "Льняная мука", _FLAX_FLOUR,
               "Omega-3 va tolaga boy, uglevodi juda kam.", "Много омега-3 и клетчатки, очень мало углеводов."),
            _i("3 osh q. (30 g)", "3 ст.л. (30 г)", "Psillium uni", "Псиллиум (мука)", _PSYLLIUM_FLOUR,
               "Bulochkani ko'taradi va yumshoq qiladi.", "Поднимает булочку и делает её мягкой."),
            _i("1 osh q.", "1 ст.л.", "Olma sirkasi", "Яблочный уксус", _VINEGAR,
               "Soda bilan birga bulochkani g'ovak qiladi.", "Вместе с содой делает булочку пористой."),
            _i("1 osh q.", "1 ст.л.", "Oq kunjut (ustiga)", "Белый кунжут (сверху)", _SESAME_WHITE,
               "Klassik burger ko'rinishi va qarsillash.", "Классический вид бургерной булочки и хруст."),
            _i("1/2 ch.q.", "1/2 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Ta'mni ochadi.", "Раскрывает вкус."),
            _i("3 ta", "3 шт", "Tuxum oqi", "Яичный белок"),
            _i("1 ch.q.", "1 ч.л.", "Soda", "Сода"),
            _i("150 ml", "150 мл", "Qaynoq suv", "Кипяток"),
        ],
        "steps": [
            _s("Pechni 180°C ga qizdiring. Laganga pergament qog'oz to'shang.",
               "Разогрейте духовку до 180°C. Застелите противень пергаментом."),
            _s("Idishda zig'ir uni, psillium uni, soda va tuzni aralashtiring.",
               "Смешайте в миске льняную муку, псиллиум, соду и соль."),
            _s("Tuxum oqi va olma sirkasini qo'shib, qoshiq bilan aralashtiring.",
               "Добавьте белки и уксус, перемешайте ложкой."),
            _s("Qaynoq suvni quyib, darhol 30 soniya tez aralashtiring — psillium bir zumda xamirni bog'laydi.",
               "Влейте кипяток и сразу быстро перемешайте 30 секунд — псиллиум мгновенно свяжет тесто."),
            _s("Ho'l qo'l bilan 4 ta yumaloq bulochka yasang, laganga 5 sm oraliqda tering va ustiga kunjut sepib, biroz bosing.",
               "Влажными руками сформуйте 4 круглые булочки, выложите на противень на расстоянии 5 см, "
               "посыпьте кунжутом и слегка прижмите."),
            _s("180°C da 40–45 daqiqa pishiring. Tagini chertganda bo'g'iq ovoz chiqsa — tayyor.",
               "Выпекайте 40–45 минут при 180°C. Глухой звук при постукивании по дну — готово."),
            _s("Panjarada to'liq sovuting (30 daqiqa), so'ng ikkiga kesing.",
               "Полностью остудите на решётке (30 минут), затем разрежьте пополам."),
        ],
        "tip": _s("Burger uchun: kotlet, pishloq, salat bargi, pomidor va bodring tuzlamasi — hammasi keto.",
                  "Для бургера: котлета, сыр, лист салата, помидор и маринованный огурец — всё кето."),
        "image_prompt": "keto burger buns made from flaxseed flour and psyllium with white sesame on top, one bun "
                        "made into a burger with beef patty, cheese, lettuce and tomato",
    },
    # ─── 2026-11-13: 15 more (owner: new recipes — the library ran out on
    # 05.11 and old ones were repeating). Each features shop products the
    # first 15 did not; they come out from 15.11 in this order, each one
    # only once its photo webapp/recipes/<slug>.jpg is added (recipes.py
    # «Jadval»). Photo prompts: recipes_image_prompts.md.
    {
        "slug": "keto-somsa",
        "title": _s("Go'shtli keto somsa", "Кето-самса с мясом"),
        "intro": _s(
            "Uchburchak, qizarib pishgan, ichi sersuv — xuddi tandir somsasidek, faqat bug'doy unisiz. "
            "Xamiri bodom uni va pishloqdan, ksantan uni egiluvchan qiladi. Bitta somsada ~3 g uglevod.",
            "Треугольная, румяная, сочная внутри — как самса из тандыра, только без пшеничной муки. "
            "Тесто из миндальной муки и сыра, а ксантан делает его эластичным. В одной самсе ~3 г углеводов."),
        "minutes": 60,
        "servings": _s("8 dona", "8 штук"),
        "per_serving": {"carbs": 3, "kcal": 290},
        "ingredients": [
            _i("100 g", "100 г", "Bodom uni", "Миндальная мука", _ALMOND,
               "Xamirning asosi: bug'doy unidan ancha kam uglevodli.",
               "Основа теста: углеводов намного меньше, чем в пшеничной муке."),
            _i("1/2 ch.q.", "1/2 ч.л.", "Ksantan kamedi", "Ксантановая камедь", _XANTHAN,
               "Glyuten o'rnini bosadi: xamir cho'ziladi va buklaganda yorilmaydi.",
               "Заменяет глютен: тесто тянется и не трескается при складывании."),
            _i("1 ch.q.", "1 ч.л.", "Qora sedana (ustiga)", "Чёрный тмин (сверху)", _NIGELLA,
               "Somsaning o'sha tanish hidi va ko'rinishi.",
               "Тот самый знакомый аромат и вид самсы."),
            _i("1 ch.q.", "1 ч.л.", "Oq kunjut (ustiga)", "Белый кунжут (сверху)", _SESAME_WHITE,
               "Qobiqqa qarsillash qo'shadi.", "Добавляет корочке хруста."),
            _i("1 ch.q.", "1 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Ichlik va xamir ta'mini ochadi.", "Раскрывает вкус начинки и теста."),
            _i("150 g", "150 г", "Mozzarella", "Моцарелла"),
            _i("2 ta", "2 шт", "Tuxum (biri xamirga, ikkinchisining sarig'i ustiga)",
               "Яйца (одно в тесто, желток второго — для смазки)"),
            _i("300 g", "300 г", "Qo'y yoki mol go'shti qiymasi", "Фарш из баранины или говядины"),
            _i("40 g", "40 г", "Dumba yog'i", "Курдючный жир"),
            _i("1 ta (100 g)", "1 шт (100 г)", "Piyoz", "Лук"),
            _i("1 ch.q.", "1 ч.л.", "Zira", "Зира"),
            _i("1/2 ch.q.", "1/2 ч.л.", "Qora qalampir", "Чёрный перец"),
        ],
        "steps": [
            _s("Ichlik: piyozni mayda to'g'rang, dumba yog'ini mayda kubik qiling. Qiyma, zira, qora qalampir va "
               "yarim choy qoshiq tuz bilan aralashtiring. 1 osh qoshiq sovuq suv qo'shsangiz, somsa sersuv bo'ladi.",
               "Начинка: мелко нарежьте лук, курдюк — мелким кубиком. Смешайте с фаршем, зирой, чёрным перцем и "
               "половиной ложки соли. Столовая ложка холодной воды сделает самсу сочнее."),
            _s("Mozzarellani qirg'ichdan o'tkazib, mikroto'lqinli pechda 1 daqiqa (yoki suv hammomida) to'liq eriting.",
               "Натрите моцареллу и полностью растопите в микроволновке 1 минуту (или на водяной бане)."),
            _s("Erigan pishloqqa bodom uni, ksantan, 1 ta tuxum va qolgan tuzni qo'shib, avval qoshiq, keyin qo'l "
               "bilan bir xil xamir qoring. Yopishsa, qo'lni ho'llang.",
               "Добавьте к сыру миндальную муку, ксантан, 1 яйцо и оставшуюся соль и замесите сначала ложкой, "
               "затем руками однородное тесто. Если липнет — смочите руки."),
            _s("Pechni 190°C ga qizdiring. Xamirni 8 bo'lakka bo'lib, har birini ikki pergament orasida "
               "12–13 sm kvadrat qilib, 3 mm qalinlikda yoying.",
               "Разогрейте духовку до 190°C. Разделите тесто на 8 частей и раскатайте каждую между двумя листами "
               "пергамента в квадрат 12–13 см толщиной 3 мм."),
            _s("Har bir kvadrat o'rtasiga 2 osh qoshiq ichlik qo'yib, uchburchak qilib buklang va chetlarini qisib "
               "chiqing. Somsalarni choki pastga qaratib, pergament to'shalgan laganga tering.",
               "Положите в центр каждого квадрата 2 ст. ложки начинки, сложите треугольником и защипните края. "
               "Выложите самсу швом вниз на противень с пергаментом."),
            _s("Ustiga tuxum sarig'ini surting, qora sedana va kunjut seping.",
               "Смажьте желтком и посыпьте чёрным тмином и кунжутом."),
            _s("190°C da 25–30 daqiqa pishiring; usti tez qizarsa, oxirgi 10 daqiqada folga bilan yoping. "
               "5 daqiqa tindirib, issiq holda torting.",
               "Выпекайте 25–30 минут при 190°C; если верх быстро румянится, последние 10 минут накройте фольгой. "
               "Дайте постоять 5 минут и подавайте горячей."),
        ],
        "tip": _s("Qo'y go'shti o'rniga tovuq son go'shti ham bo'ladi. Pishmagan somsani muzlatib qo'ysangiz, "
                  "kerak paytda to'g'ridan-to'g'ri pechga qo'yasiz — 5–7 daqiqa ko'proq pishadi.",
                  "Вместо баранины подойдёт мясо куриных бёдер. Сырую самсу можно заморозить и печь прямо из "
                  "морозилки — на 5–7 минут дольше."),
        "image_prompt": "golden triangular keto samsa from almond flour and mozzarella dough, nigella and sesame "
                        "on top, one broken open with juicy minced lamb and onion filling",
    },
    {
        "slug": "tungi-suli-botqa",
        "title": _s("Bankada tungi suli bo'tqasi", "Ленивая овсянка в банке"),
        "intro": _s(
            "Pishirish shart emas: kechqurun 5 daqiqada bankaga solasiz, ertalab nonushta tayyor turadi. "
            "Suli yormasi uzoq to'q tutadi, rastaropsha uni esa tola qo'shadi.",
            "Варить не нужно: вечером за 5 минут сложили всё в банку — утром завтрак уже ждёт. "
            "Овсяные хлопья надолго насыщают, а мука расторопши добавляет клетчатки."),
        "minutes": 5,
        "rest": _s("+ muzlatkichda tun bo'yi", "+ ночь в холодильнике"),
        "servings": _s("2 kishilik", "2 порции"),
        "per_serving": {"carbs": 34, "kcal": 300},
        "ingredients": [
            _i("80 g", "80 г", "Suli yormasi", "Овсяные хлопья", _OATS,
               "Sekin hazm bo'ladi: ertalabdan tushgacha to'q yurasiz.",
               "Медленно усваиваются: сытость до самого обеда."),
            _i("1 osh q.", "1 ст.л.", "Rastaropsha uni", "Мука расторопши", _MILK_THISTLE,
               "Tolaga boy qo'shimcha; bir qoshig'i ta'mni deyarli o'zgartirmaydi.",
               "Добавка, богатая клетчаткой; одна ложка почти не меняет вкус."),
            _i("1 osh q.", "1 ст.л.", "Chia urug'i", "Семена чиа", _CHIA,
               "Suyuqlikni shimib, bo'tqani quyuq va kremdek qiladi.",
               "Впитывает жидкость — каша становится густой и кремовой."),
            _i("ta'bga ko'ra", "по вкусу", "Steviya", "Стевия", _STEVIA,
               "Shakarsiz shirinlik — juda oz ketadi.", "Сладость без сахара — нужно совсем немного."),
            _i("1/2 ch.q.", "1/2 ч.л.", "Dolchin", "Корица", _CINNAMON,
               "Bo'tqaga iliq, shirinroq ta'm beradi.", "Тёплый вкус — каша кажется слаще."),
            _i("200 ml", "200 мл", "Sut", "Молоко"),
            _i("100 g", "100 г", "Tabiiy yogurt yoki qatiq", "Натуральный йогурт или катык"),
            _i("1 hovuch (100 g)", "1 горсть (100 г)", "Rezavor (muzlatilgani ham bo'ladi)",
               "Ягоды (можно замороженные)"),
        ],
        "steps": [
            _s("Ikkita bankaga suli yormasi, rastaropsha uni, chia, dolchin va steviyani teng bo'lib soling va "
               "quruq holda aralashtiring.",
               "Разложите по двум банкам овсяные хлопья, муку расторопши, чиа, корицу и стевию и перемешайте всухую."),
            _s("Sut va yogurtni qo'shib, qoshiq bilan yaxshilab aralashtiring — tagida quruq yorma qolmasin.",
               "Добавьте молоко и йогурт и хорошо перемешайте ложкой, чтобы на дне не осталось сухих хлопьев."),
            _s("Bankalarni yopib muzlatkichga qo'ying; 10 daqiqadan keyin yana bir bor aralashtiring — chia bir "
               "joyga yopishib qolmaydi.",
               "Закройте банки и уберите в холодильник; через 10 минут перемешайте ещё раз — так чиа не слипнется."),
            _s("Tun bo'yi (kamida 6 soat) muzlatkichda qoldiring — yorma yumshaydi, bo'tqa quyuqlashadi.",
               "Оставьте на ночь (минимум на 6 часов) — хлопья размякнут, каша загустеет."),
            _s("Ertalab aralashtiring; juda quyuq bo'lsa, 2–3 osh qoshiq sut qo'shing.",
               "Утром перемешайте; если слишком густо — добавьте 2–3 ст. ложки молока."),
            _s("Ustiga rezavor solib, sovuq holda yoki mikroto'lqinli pechda 1 daqiqa isitib yeng.",
               "Выложите сверху ягоды и ешьте холодной или подогрейте 1 минуту в микроволновке."),
        ],
        "tip": _s("Har kuni boshqacha qiling: bir kun rezavor, ertasiga to'g'ralgan olma va dolchin, keyingi kun "
                  "1 choy qoshiq kakao nibs. Muzlatkichda 3 kungacha turadi.",
                  "Меняйте каждый день: сегодня ягоды, завтра яблоко с корицей, послезавтра ложка какао-крупки. "
                  "В холодильнике хранится до 3 дней."),
        "image_prompt": "two glass jars of overnight oats with a yogurt layer, berries on top, cinnamon and chia",
    },
    {
        "slug": "lasos-kotlet",
        "title": _s("Lasos baliqli keto kotletlar", "Кето-котлеты из лосося"),
        "intro": _s(
            "Baliqni bolalar ham yeydigan qilishning eng oson yo'li: tayyor lasos tushonkasidan 25 daqiqada "
            "kotlet. Un ham, non ushog'i ham yo'q — oqsil va omega-3 esa ko'p.",
            "Самый простой способ, чтобы рыбу ели и дети: котлеты из готовой тушёнки лосося за 25 минут. "
            "Ни муки, ни сухарей — зато много белка и омега-3."),
        "minutes": 25,
        "servings": _s("3 kishilik (9 dona)", "3 порции (9 штук)"),
        "per_serving": {"carbs": 8, "kcal": 450},
        "ingredients": [
            _i("1 banka (700 ml)", "1 банка (700 мл)", "Lasos baliq tushonkasi", "Тушёнка из лосося", _SALMON,
               "Baliq allaqachon pishgan: tozalab, qaynatib o'tirmaysiz — faqat suvini to'kasiz.",
               "Рыба уже готова: не нужно чистить и варить — только слить жидкость."),
            _i("3 osh q. (30 g)", "3 ст.л. (30 г)", "Soya uni", "Соевая мука", _SOY_FLOUR,
               "Massani bog'laydi; bug'doy unidan uglevodi ancha kam, oqsili ko'p.",
               "Связывает массу; углеводов намного меньше, чем в пшеничной муке, а белка больше."),
            _i("2 osh q.", "2 ст.л.", "Zaytun yog'i (qovurish uchun)", "Оливковое масло (для жарки)", _OLIVE_FRY,
               "O'rtacha olovda qovurishga chidamli.", "Подходит для жарки на среднем огне."),
            _i("1/2 ch.q.", "1/2 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Baliq ta'mini ochadi.", "Раскрывает вкус рыбы."),
            _i("2 ta", "2 шт", "Tuxum", "Яйца"),
            _i("1 ta kichik", "1 маленькая", "Piyoz", "Луковица"),
            _i("1/2 bog'", "1/2 пучка", "Shivit", "Укроп"),
            _i("1 ta", "1 шт", "Limon (sharbati va bo'laklari)", "Лимон (сок и дольки)"),
            _i("bir chimdim", "щепотка", "Qora qalampir", "Чёрный перец"),
            _i("150 g", "150 г", "Qatiq yoki suzma (sous)", "Катык или сюзьма (соус)"),
            _i("1 ta", "1 шт", "Bodring (sous va tortish uchun)", "Огурец (для соуса и подачи)"),
            _i("1 tishcha", "1 зубчик", "Sarimsoq (sous)", "Чеснок (соус)"),
        ],
        "steps": [
            _s("Tushonkaning suvini to'kib, baliqni idishga soling va vilka bilan ezing; yirik suyak uchrasa, "
               "olib tashlang.",
               "Слейте жидкость, выложите рыбу в миску и разомните вилкой; крупные косточки уберите."),
            _s("Piyozni juda mayda to'g'rang (yoki qirg'ichdan o'tkazing), shivitni maydalang.",
               "Очень мелко нарежьте лук (или натрите), измельчите укроп."),
            _s("Baliqqa tuxum, piyoz, shivit, soya uni, 1 osh qoshiq limon sharbati, tuz va qalampirni qo'shib "
               "yaxshilab aralashtiring. 10 daqiqa qoldiring — soya uni namni shimib, massa quyuqlashadi.",
               "Добавьте к рыбе яйца, лук, укроп, соевую муку, 1 ст. ложку лимонного сока, соль и перец и хорошо "
               "перемешайте. Оставьте на 10 минут — мука впитает влагу, масса загустеет."),
            _s("Ho'l qo'l bilan 9 ta kotlet yasang (diametri 6 sm, qalinligi 1,5 sm).",
               "Влажными руками сформуйте 9 котлет (диаметр 6 см, толщина 1,5 см)."),
            _s("Tovada yog'ni o'rtacha olovda qizdirib, kotletlarni har tomonini 3–4 daqiqadan, oltinrang "
               "bo'lguncha qovuring. Kurakcha bilan ehtiyotkorlik bilan ag'daring.",
               "Разогрейте масло на среднем огне и обжарьте котлеты по 3–4 минуты с каждой стороны до золотистого "
               "цвета. Переворачивайте аккуратно лопаткой."),
            _s("Sous: qatiqqa mayda to'g'ralgan yarim bodring, ezilgan sarimsoq va bir chimdim tuz qo'shib "
               "aralashtiring.",
               "Соус: смешайте катык с мелко нарезанной половиной огурца, давленым чесноком и щепоткой соли."),
            _s("Kotletlarni sous, qolgan bodring bo'laklari va limon bo'lagi bilan torting.",
               "Подавайте котлеты с соусом, ломтиками оставшегося огурца и долькой лимона."),
        ],
        "tip": _s("Massa suyuqroq chiqsa, yana 1 osh qoshiq soya uni qo'shing. Pechda ham bo'ladi: 200°C da "
                  "15–18 daqiqa, o'rtasida bir marta ag'darib.",
                  "Если масса жидковата, добавьте ещё 1 ст. ложку соевой муки. Можно в духовке: 200°C, "
                  "15–18 минут, один раз перевернув."),
        "image_prompt": "golden pan-fried salmon patties with dill, lemon wedges, yogurt-cucumber-garlic sauce",
    },
    {
        "slug": "dubay-shokolad",
        "title": _s("Uyda shakarsiz «Dubay shokoladi»", "Домашний «дубайский шоколад» без сахара"),
        "intro": _s(
            "Hamma gapirayotgan shokolad — uyda va shakarsiz: qora shokolad qobig'i ichida xandonpista kremi va "
            "qarsildoq qovurilgan kokos. 30 daqiqa ish, qolganini muzlatkich qiladi.",
            "Тот самый шоколад, о котором все говорят, — дома и без сахара: в оболочке из горького шоколада "
            "фисташковый крем и хрустящий обжаренный кокос. 30 минут работы, остальное сделает холодильник."),
        "minutes": 30,
        "rest": _s("+ muzlatkichda 1 soat", "+ 1 час в холодильнике"),
        "servings": _s("1 plitka, 12 bo'lak", "1 плитка, 12 кусочков"),
        "per_serving": {"carbs": 3.5, "kcal": 155},
        "ingredients": [
            _i("150 g", "150 г", "«Pobeda» shakarsiz qora shokoladi", "Горький шоколад «Победа» без сахара",
               _CHOCOLATE,
               "Qobiq uchun: qotgach qattiq va yaltiroq bo'ladi.",
               "Для оболочки: застывает твёрдой и глянцевой."),
            _i("100 g", "100 г", "Xandonpista pastasi", "Фисташковая паста", _PISTACHIO_PASTE,
               "Ichidagi yashil krem — mashhur ta'mning siri.", "Зелёный крем внутри — секрет знаменитого вкуса."),
            _i("40 g", "40 г", "Kokos chipsi yoki qirindisi", "Кокосовые чипсы или стружка", _COCONUT_FLAKES,
               "Asl retseptdagi xamir iplari o'rnida: qovurilgach xuddi shunday qarsillaydi.",
               "Вместо теста катаифи из оригинала: после обжарки хрустит так же."),
            _i("2 osh q.", "2 ст.л.", "Eritritol (kukun qilingan)", "Эритрит (смолотый в пудру)", _ERYTHRITOL,
               "Kremni shirin qiladi; kofe maydalagichda kukun qilsangiz, tishda g'ichirlamaydi.",
               "Подслащивает крем; смолотый в кофемолке, не хрустит на зубах."),
            _i("1 osh q.", "1 ст.л.", "Sariyog'", "Сливочное масло"),
            _i("bir chimdim", "щепотка", "Tuz", "Соль"),
        ],
        "steps": [
            _s("Kokos chipsini sariyog'da past olovda 3–4 daqiqa, oltinrang bo'lguncha qovuring va soviting.",
               "Обжарьте кокосовые чипсы на сливочном масле на слабом огне 3–4 минуты до золотистого цвета и остудите."),
            _s("Xandonpista pastasi, kukun eritritol va bir chimdim tuzni aralashtiring, keyin qovurilgan kokosni "
               "qo'shing — qalin, qarsildoq krem bo'ladi.",
               "Смешайте фисташковую пасту, эритрит-пудру и щепотку соли, затем вмешайте обжаренный кокос — "
               "получится густой хрустящий крем."),
            _s("Shokoladni bo'laklab, suv hammomida (yoki mikroto'lqinli pechda 20 soniyadan, har safar "
               "aralashtirib) eriting. Juda qizdirmang — shokolad oqarib qoladi.",
               "Растопите шоколад кусочками на водяной бане (или в микроволновке по 20 секунд, каждый раз "
               "перемешивая). Не перегревайте — шоколад поседеет."),
            _s("Shokoladning 2/3 qismini silikon qolip (yoki pergament to'shalgan kichik idish) tubi va "
               "devorlariga qoshiq bilan surting va 10 daqiqa muzlatkichda qotiring.",
               "Двумя третями шоколада промажьте ложкой дно и стенки силиконовой формы (или небольшой ёмкости с "
               "пергаментом) и уберите в холодильник на 10 минут."),
            _s("Ichiga pista-kokos kremini zich qilib, tekis yoying.",
               "Плотно и ровно выложите внутрь фисташково-кокосовый крем."),
            _s("Ustidan qolgan shokoladni quyib tekislang va muzlatkichda kamida 1 soat qotiring.",
               "Залейте оставшимся шоколадом, разровняйте и уберите в холодильник минимум на час."),
            _s("Qolipdan chiqarib, issiq pichoq bilan 12 bo'lakka kesing — kesimida yashil krem ko'rinib turadi.",
               "Достаньте из формы и нарежьте горячим ножом на 12 кусочков — на срезе виден зелёный крем."),
        ],
        "tip": _s("Shokolad juda achchiq tuyulsa, eritganda unga ham 1 osh qoshiq kukun eritritol qo'shing. "
                  "Muzlatkichda yopiq idishda 1 haftagacha saqlanadi.",
                  "Если шоколад кажется слишком горьким, добавьте и в него при растапливании 1 ст. ложку "
                  "эритрита-пудры. В холодильнике в закрытой ёмкости хранится до недели."),
        "image_prompt": "homemade sugar-free dubai chocolate bar cut open, green pistachio cream with toasted "
                        "coconut inside a dark chocolate shell",
    },
    {
        "slug": "devzira-mastava",
        "title": _s("Devzira guruchli mastava", "Мастава с рисом девзира"),
        "intro": _s(
            "Onalarimiz pishiradigan mastavaning ta'mi, faqat guruchi — bo'yalmagan, yog'lanmagan qizil devzira. "
            "Go'sht va sabzavot ko'p, guruch oz: yengil, lekin to'yimli sho'rva.",
            "Вкус маставы, как у мамы, только рис — неокрашенная, непромасленная красная девзира. "
            "Мяса и овощей много, риса мало: лёгкий, но сытный суп."),
        "minutes": 75,
        "servings": _s("4 kishilik", "4 порции"),
        "per_serving": {"carbs": 22, "kcal": 290},
        "ingredients": [
            _i("80 g", "80 г", "Qizil guruch (devzira)", "Красный рис девзира", _DEVZIRA,
               "Qaynaganda ham donador qoladi — mastava bo'tqaga aylanib ketmaydi.",
               "Остаётся рассыпчатым даже в супе — мастава не превращается в кашу."),
            _i("1 osh q.", "1 ст.л.", "GHEE", "Гхи", _GHEE,
               "Qovurishda tutun chiqarmaydi va sho'rvaga yumshoq qaymoqli ta'm beradi.",
               "Не дымит при обжарке и даёт супу мягкий сливочный вкус."),
            _i("1 ch.q.", "1 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Ta'mni ochadi.", "Раскрывает вкус."),
            _i("300 g", "300 г", "Mol yoki qo'y go'shti", "Говядина или баранина"),
            _i("1 ta", "1 шт", "Piyoz", "Лук"),
            _i("1 ta", "1 шт", "Sabzi", "Морковь"),
            _i("1 ta", "1 шт", "Bulg'or qalampiri", "Болгарский перец"),
            _i("2 ta", "2 шт", "Pomidor", "Помидоры"),
            _i("2 tishcha", "2 зубчика", "Sarimsoq", "Чеснок"),
            _i("1,5 l", "1,5 л", "Issiq suv", "Горячая вода"),
            _i("1 ch.q.", "1 ч.л.", "Zira", "Зира"),
            _i("4 osh q.", "4 ст.л.", "Qatiq (tortish uchun)", "Катык (для подачи)"),
            _i("1 bog'", "1 пучок", "Shivit va kashnich", "Укроп и кинза"),
        ],
        "steps": [
            _s("Guruchni suvi tiniq bo'lguncha 3–4 marta yuving va 30 daqiqa iliq suvda ivitib qo'ying.",
               "Промойте рис 3–4 раза до прозрачной воды и замочите в тёплой воде на 30 минут."),
            _s("Go'shtni 1,5 sm kubik, piyozni yarim halqa, sabzi va bulg'or qalampirini kubik qilib, pomidorni "
               "mayda to'g'rang.",
               "Нарежьте мясо кубиком 1,5 см, лук — полукольцами, морковь и перец — кубиком, помидоры — мелко."),
            _s("Qozonda GHEE yog'ini qizdirib, go'shtni 7–8 daqiqa qizarguncha qovuring. Piyozni qo'shib 3 daqiqa, "
               "keyin sabzi va qalampirni qo'shib yana 4 daqiqa qovuring.",
               "Разогрейте гхи в казане и обжарьте мясо 7–8 минут до румяности. Добавьте лук — 3 минуты, затем "
               "морковь и перец — ещё 4 минуты."),
            _s("Pomidor va maydalangan sarimsoqni qo'shib 3 daqiqa qovuring. 1,5 l issiq suv quying, tuz va zira "
               "soling, qaynab chiqqach past olovda 25 daqiqa qaynating.",
               "Добавьте помидоры и измельчённый чеснок, жарьте 3 минуты. Влейте 1,5 л горячей воды, добавьте соль "
               "и зиру и после закипания варите на слабом огне 25 минут."),
            _s("Guruchni suvidan olib qozonga soling va yana 25 daqiqa, guruch yumshaguncha pishiring — devzira "
               "oddiy guruchdan sekinroq pishadi.",
               "Откиньте рис, всыпьте в казан и варите ещё 25 минут до мягкости — девзира варится дольше обычного риса."),
            _s("Olovni o'chirib, 5 daqiqa dam bering. Kosalarga quyib, ustiga qatiq va to'g'ralgan ko'kat solib "
               "torting.",
               "Выключите огонь и дайте настояться 5 минут. Разлейте по пиалам, добавьте катык и рубленую зелень."),
        ],
        "tip": _s("Qatiqni qozonga emas, kosaga soling — shunda ivib qolmaydi. Mastava ertasiga quyuqlashadi: "
                  "isitganda ozgina qaynoq suv qo'shing.",
                  "Катык кладите в пиалу, а не в казан — так он не свернётся. Назавтра мастава загустеет: при "
                  "разогреве добавьте немного кипятка."),
        "image_prompt": "uzbek mastava soup with red devzira rice, beef cubes, vegetables, a spoon of qatiq and "
                        "herbs in a ceramic kosa",
    },
    {
        "slug": "javdar-non",
        "title": _s("Javdar unli solodli PP non", "ПП-хлеб из ржаной муки с солодом"),
        "intro": _s(
            "Qoramtir, xushbo'y, qobig'i qarsildoq non — Borodinskiy nonga o'xshaydi, faqat uyda va oq unsiz. "
            "Javdar uni va qora solod uni to'yimli qiladi: bir bo'lagi bilan ham uzoq to'q yurasiz.",
            "Тёмный, ароматный хлеб с хрустящей корочкой — похож на «Бородинский», только домашний и без белой "
            "муки. Ржаная мука и чёрный солод делают его сытным: даже одного ломтика хватает надолго."),
        "minutes": 80,
        "rest": _s("+ 1,5 soat ko'tarilishi va 3 soat sovishi", "+ 1,5 часа на подъём и 3 часа на остывание"),
        "servings": _s("12 bo'lak", "12 ломтиков"),
        "per_serving": {"carbs": 20, "kcal": 130},
        "ingredients": [
            _i("250 g", "250 г", "Javdar uni", "Ржаная мука", _RYE_FLOUR,
               "Tolaga boy: non zich, namli va to'yimli chiqadi.",
               "Много клетчатки: хлеб получается плотным, влажным и сытным."),
            _i("150 g", "150 г", "Kepakli bug'doy uni", "Пшеничная мука с отрубями", _BRAN_WHEAT_FLOUR,
               "Javdar xamirini ko'tarishga yordam beradi — non og'ir bo'lib qolmaydi.",
               "Помогает ржаному тесту подняться — хлеб не будет тяжёлым."),
            _i("2 osh q. (20 g)", "2 ст.л. (20 г)", "Qora fermentlangan solod", "Чёрный ферментированный солод",
               _MALT,
               "To'q rang va o'sha tanish nordon-shirin ta'm beradi.",
               "Тёмный цвет и тот самый кисло-сладкий вкус."),
            _i("1 osh q.", "1 ст.л.", "Olma sirkasi", "Яблочный уксус", _VINEGAR,
               "Javdar xamiriga yoqimli nordonlik beradi.", "Даёт ржаному тесту приятную кислинку."),
            _i("1 ch.q.", "1 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Ta'mni ochadi.", "Раскрывает вкус."),
            _i("1 ch.q. (5 g)", "1 ч.л. (5 г)", "Quruq xamirturush", "Сухие дрожжи"),
            _i("100 ml + 200 ml", "100 мл + 200 мл", "Qaynoq suv (solodga) va iliq suv",
               "Кипяток (для солода) и тёплая вода"),
            _i("1 osh q.", "1 ст.л.", "O'simlik yog'i", "Растительное масло"),
            _i("1 ch.q.", "1 ч.л.", "Kashnich urug'i (ustiga)", "Семена кориандра (сверху)"),
        ],
        "steps": [
            _s("Qora solodni 100 ml qaynoq suvda aralashtirib, 15 daqiqa damlang va iliq bo'lguncha soviting.",
               "Заварите чёрный солод 100 мл кипятка, оставьте на 15 минут и остудите до тёплого."),
            _s("200 ml iliq suvda xamirturushni eritib, 10 daqiqa qo'ying — ustida ko'pik paydo bo'ladi.",
               "Растворите дрожжи в 200 мл тёплой воды и оставьте на 10 минут — появится пенка."),
            _s("Katta idishda javdar uni, kepakli un va tuzni aralashtiring. Solod, xamirturushli suv, olma "
               "sirkasi va yog'ni qo'shing.",
               "В большой миске смешайте ржаную муку, муку с отрубями и соль. Добавьте солод, воду с дрожжами, "
               "уксус и масло."),
            _s("Qoshiq bilan 3–4 daqiqa yaxshilab aralashtiring. Javdar xamiri yopishqoq bo'ladi — bu normal, "
               "un qo'shmang.",
               "Хорошо перемешайте ложкой 3–4 минуты. Ржаное тесто липкое — это нормально, муку не добавляйте."),
            _s("Yog'langan 20×10 sm qolipga solib, ho'l qo'l bilan tekislang va ustiga kashnich urug'ini seping. "
               "Iliq joyda 1–1,5 soat, hajmi 1,5 baravar oshguncha ko'tarilsin.",
               "Переложите в смазанную форму 20×10 см, разровняйте мокрой рукой и посыпьте кориандром. Оставьте "
               "в тепле на 1–1,5 часа, пока объём не увеличится в 1,5 раза."),
            _s("Pechni 200°C ga qizdiring. Nonni 15 daqiqa 200°C da, keyin 180°C da yana 35 daqiqa pishiring.",
               "Разогрейте духовку до 200°C. Выпекайте 15 минут при 200°C, затем ещё 35 минут при 180°C."),
            _s("Qolipdan chiqarib, sochiqqa o'rab to'liq soviting (kamida 3 soat) — javdar noni issiqligida "
               "kesilmaydi.",
               "Достаньте из формы, заверните в полотенце и полностью остудите (минимум 3 часа) — горячим ржаной "
               "хлеб не режут."),
        ],
        "tip": _s("Javdar noni ertasiga yanada mazali bo'ladi. Bo'laklab muzlatib qo'ying — tosterda 2 daqiqada "
                  "yangi yopilgandek bo'ladi.",
                  "Ржаной хлеб на следующий день ещё вкуснее. Нарежьте и заморозьте — в тостере за 2 минуты он "
                  "как свежий."),
        "image_prompt": "dark rye malt bread loaf baked in a tin, crushed coriander seeds on top, dense moist slices",
    },
    {
        "slug": "keto-manti",
        "title": _s("Qovoq va go'shtli keto manti", "Кето-манты с тыквой и мясом"),
        "intro": _s(
            "Manti xamirini bug'doy unisiz qilib bo'lmaydi deysizmi? Oq zig'ir uni va psilliumdan qilingan xamir "
            "yupqa yoyiladi va bug'da yirtilmaydi. Ichida go'sht, qovoq va piyoz — butun oilaga kechki ovqat.",
            "Думаете, тесто для мантов без пшеничной муки не сделать? Тесто из белой льняной муки и псиллиума "
            "тонко раскатывается и не рвётся на пару. Внутри мясо, тыква и лук — ужин для всей семьи."),
        "minutes": 90,
        "servings": _s("4 kishilik (16 dona)", "4 порции (16 штук)"),
        "per_serving": {"carbs": 9, "kcal": 465},
        "ingredients": [
            _i("150 g", "150 г", "Oq zig'ir uni", "Мука из белого льна", _WHITE_FLAX_FLOUR,
               "Xamirning asosi: uglevodi juda kam, rangi och — manti chiroyli chiqadi.",
               "Основа теста: очень мало углеводов, светлый цвет — манты выглядят красиво."),
            _i("2,5 osh q. (25 g)", "2,5 ст.л. (25 г)", "Psillium (sheluxa)", "Псиллиум (шелуха)", _PSYLLIUM_HUSK,
               "Glyuten o'rnini bosadi: xamir cho'ziladi va qisganda yorilmaydi.",
               "Заменяет глютен: тесто тянется и не трескается при защипывании."),
            _i("1 ch.q.", "1 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Xamirga ham, ichlikka ham.", "И в тесто, и в начинку."),
            _i("1 ta", "1 шт", "Tuxum", "Яйцо"),
            _i("150 ml", "150 мл", "Qaynoq suv", "Кипяток"),
            _i("400 g", "400 г", "Mol yoki qo'y go'shti", "Говядина или баранина"),
            _i("150 g", "150 г", "Qovoq (tozalangan)", "Тыква (очищенная)"),
            _i("1 ta katta (120 g)", "1 крупная (120 г)", "Piyoz", "Луковица"),
            _i("30 g", "30 г", "Sariyog'", "Сливочное масло"),
            _i("1 ch.q.", "1 ч.л.", "Zira", "Зира"),
            _i("1/2 ch.q.", "1/2 ч.л.", "Qora qalampir", "Чёрный перец"),
            _i("4 osh q.", "4 ст.л.", "Qatiq yoki qaymoq (tortish uchun)", "Катык или сметана (для подачи)"),
        ],
        "steps": [
            _s("Xamir: oq zig'ir uni, psillium va yarim choy qoshiq tuzni aralashtirib, tuxumni qo'shing.",
               "Тесто: смешайте льняную муку, псиллиум и половину ложки соли, добавьте яйцо."),
            _s("Qaynoq suvni quyib, qoshiq bilan tez aralashtiring. Biroz sovigach qo'l bilan 1–2 daqiqa qoring, "
               "plyonkaga o'rab 15 daqiqa dam bering.",
               "Влейте кипяток и быстро перемешайте ложкой. Когда немного остынет, вымесите руками 1–2 минуты, "
               "заверните в плёнку и оставьте на 15 минут."),
            _s("Ichlik: go'shtni mayda to'g'rang (yoki yirik qiyma qiling), qovoq va piyozni 0,5 sm kubik qiling. "
               "Zira, qalampir, qolgan tuz va mayda to'g'ralgan sariyog'ni qo'shib aralashtiring.",
               "Начинка: мелко нарубите мясо (или прокрутите на крупный фарш), тыкву и лук нарежьте кубиком "
               "0,5 см. Добавьте зиру, перец, оставшуюся соль и мелко нарезанное сливочное масло, перемешайте."),
            _s("Xamirni 2 ga bo'lib, har birini ikki pergament orasida 1,5–2 mm qalinlikda yoying va 10 sm li "
               "kvadratlarga kesing (16 ta chiqadi).",
               "Разделите тесто на 2 части, каждую раскатайте между листами пергамента толщиной 1,5–2 мм и "
               "нарежьте квадратами 10 см (выйдет 16 штук)."),
            _s("Har bir kvadratga 1 osh qoshiq ichlik qo'ying, qarama-qarshi burchaklarini o'rtada birlashtirib, "
               "chetlarini qisib chiqing. Xamir yorilsa, ho'l barmoq bilan yopishtiring.",
               "Положите на каждый квадрат столовую ложку начинки, соедините противоположные углы в центре и "
               "защипните края. Если тесто треснет — залепите мокрым пальцем."),
            _s("Qasqon qavatlarini yog'lab, mantilarni bir-biriga tegmaydigan qilib tering va qaynab turgan suv "
               "ustida 40–45 daqiqa bug'da pishiring.",
               "Смажьте ярусы мантоварки маслом, выложите манты так, чтобы они не касались друг друга, и готовьте "
               "на пару над кипящей водой 40–45 минут."),
            _s("Qatiq yoki qaymoq va bir chimdim qora qalampir bilan issiq holda torting.",
               "Подавайте горячими с катыком или сметаной и щепоткой чёрного перца."),
        ],
        "tip": _s("Pishmagan mantilarni laganga terib muzlating, keyin paketga soling — kerak bo'lganda "
                  "muzlaganicha qasqonga qo'yib, 50 daqiqa pishirasiz.",
                  "Сырые манты заморозьте на подносе, затем пересыпьте в пакет — готовьте прямо из морозилки "
                  "50 минут."),
        "image_prompt": "keto manti dumplings from white flax flour and psyllium dough, one cut open with meat and "
                        "pumpkin filling, bowl of qatiq",
    },
    {
        "slug": "noxat-quymoq",
        "title": _s("No'xat unidan sabzavotli quymoq", "Овощные оладьи из нутовой муки"),
        "intro": _s(
            "Tuxumsiz, lekin oqsilga boy nonushta: no'xat uni, ko'kat va sabzavot. 25 daqiqada tayyor, qatiq "
            "bilan juda mazali. Glyutensiz.",
            "Завтрак без яиц, но с белком: нутовая мука, зелень и овощи. Готово за 25 минут, особенно вкусно "
            "с катыком. Без глютена."),
        "minutes": 25,
        "servings": _s("3 kishilik (9 dona)", "3 порции (9 штук)"),
        "per_serving": {"carbs": 29, "kcal": 320},
        "ingredients": [
            _i("150 g", "150 г", "No'xat uni", "Нутовая мука", _CHICKPEA_FLOUR,
               "O'simlik oqsiliga boy va glyutensiz; tuxumsiz ham xamirni ushlab turadi.",
               "Много растительного белка, без глютена; держит тесто даже без яиц."),
            _i("2 osh q.", "2 ст.л.", "Zaytun yog'i (qovurish uchun)", "Оливковое масло (для жарки)", _OLIVE_FRY,
               "Quymoqlar tovaga yopishmaydi va bir tekis qizaradi.",
               "Оладьи не прилипают и румянятся равномерно."),
            _i("1 ch.q.", "1 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Ta'mni ochadi.", "Раскрывает вкус."),
            _i("200 ml", "200 мл", "Iliq suv", "Тёплая вода"),
            _i("1 ta kichik", "1 маленькая", "Piyoz", "Луковица"),
            _i("1 ta", "1 шт", "Pomidor", "Помидор"),
            _i("1/2 ta", "1/2 шт", "Bulg'or qalampiri", "Болгарский перец"),
            _i("1/2 bog'", "1/2 пучка", "Kashnich yoki shivit", "Кинза или укроп"),
            _i("1/2 ch.q.", "1/2 ч.л.", "Zira va kurkuma", "Зира и куркума"),
            _i("150 g", "150 г", "Qatiq (tortish uchun)", "Катык (для подачи)"),
        ],
        "steps": [
            _s("No'xat uni, tuz, zira va kurkumani idishda aralashtiring.",
               "Смешайте в миске нутовую муку, соль, зиру и куркуму."),
            _s("Iliq suvni asta-sekin quyib, quyuq qaymoqdek silliq xamir qoring va 10 daqiqa dam bering.",
               "Постепенно вливая тёплую воду, замесите гладкое тесто густотой со сметану и оставьте на 10 минут."),
            _s("Piyoz, pomidor va qalampirni mayda kubik qilib to'g'rang, ko'katni maydalang va xamirga qo'shing.",
               "Мелко нарежьте лук, помидор и перец, измельчите зелень и добавьте в тесто."),
            _s("Tovada yog'ni o'rtacha olovda qizdiring. Har bir quymoq uchun 2 osh qoshiq xamir solib, 1 sm "
               "qalinlikda tekislang.",
               "Разогрейте масло на среднем огне. Выкладывайте по 2 ст. ложки теста и разравнивайте до толщины 1 см."),
            _s("Har tomonini 3–4 daqiqadan, oltinrang bo'lguncha qovuring — ichi pishishi uchun olovni baland "
               "qilmang.",
               "Жарьте по 3–4 минуты с каждой стороны до золотистого цвета — огонь не сильный, чтобы середина "
               "пропеклась."),
            _s("Qatiq va ko'kat bilan issiq holda torting.", "Подавайте горячими с катыком и зеленью."),
        ],
        "tip": _s("Xamirga 50 g qirg'ichdan o'tkazilgan pishloq qo'shsangiz, bolalar ham sevib yeydi. Xamirni "
                  "kechqurun qorib qo'ysangiz, muzlatkichda ertalabgacha turadi.",
                  "Добавьте в тесто 50 г тёртого сыра — дети тоже съедят с удовольствием. Тесто можно замесить "
                  "с вечера: в холодильнике оно спокойно дождётся утра."),
        "image_prompt": "golden savory chickpea flour fritters with tomato, onion, pepper and herbs, bowl of qatiq",
    },
    {
        "slug": "yeryongoq-pechenye",
        "title": _s("Yeryong'oq pastali keto pechenye", "Кето-печенье с арахисовой пастой"),
        "intro": _s(
            "Bor-yo'g'i 5 masalliq va 25 daqiqa: yumshoq, yeryong'oq hidi anqib turadigan pechenye. Un ham, shakar "
            "ham yo'q — alluloza shirinligi shakarnikiga juda yaqin.",
            "Всего 5 ингредиентов и 25 минут: мягкое печенье с ярким арахисовым ароматом. Ни муки, ни сахара — "
            "сладость аллюлозы очень близка к сахарной."),
        "minutes": 25,
        "servings": _s("12 dona", "12 штук"),
        "per_serving": {"carbs": 2, "kcal": 105},
        "ingredients": [
            _i("200 g", "200 г", "Yeryong'oq pastasi", "Арахисовая паста", _PEANUT_PASTE,
               "Pechenyening asosi: un ham, yog' ham shu — oqsil va foydali yog'larga boy.",
               "Основа печенья: она и мука, и масло — много белка и полезных жиров."),
            _i("60 g", "60 г", "Alluloza", "Аллюлоза", _ALLULOSE,
               "Shakardek shirin va pishganda chiroyli qizaradi; kaloriyasi deyarli yo'q.",
               "Сладкая, как сахар, красиво румянится при выпечке; калорий почти нет."),
            _i("1 ta", "1 шт", "Tuxum", "Яйцо"),
            _i("1/2 ch.q.", "1/2 ч.л.", "Soda", "Сода"),
            _i("bir chimdim", "щепотка", "Tuz", "Соль"),
        ],
        "steps": [
            _s("Pechni 175°C ga qizdiring, laganga pergament to'shang.",
               "Разогрейте духовку до 175°C, застелите противень пергаментом."),
            _s("Yeryong'oq pastasi, alluloza, tuxum, soda va tuzni qoshiq bilan silliq bo'lguncha aralashtiring. "
               "Pasta qattiq bo'lsa, 10 soniya mikroto'lqinli pechda yumshating.",
               "Перемешайте ложкой арахисовую пасту, аллюлозу, яйцо, соду и соль до однородности. Если паста "
               "густая, размягчите её 10 секунд в микроволновке."),
            _s("Xamirni 10 daqiqa muzlatkichga qo'ying — sharcha yasash osonlashadi.",
               "Уберите тесто в холодильник на 10 минут — шарики будет легче катать."),
            _s("12 ta yong'oqdek sharcha yasab, laganga 4 sm oraliqda tering.",
               "Скатайте 12 шариков размером с грецкий орех и выложите на противень на расстоянии 4 см."),
            _s("Har birini vilka bilan ikki yo'nalishda bosib, to'r naqsh tushiring.",
               "Придавите каждый шарик вилкой крест-накрест, чтобы остался узор-сеточка."),
            _s("175°C da 10–12 daqiqa pishiring: chetlari qizarsa — tayyor, o'rtasi hali yumshoq bo'ladi.",
               "Выпекайте 10–12 минут при 175°C: края подрумянились — готово, середина ещё мягкая."),
            _s("Laganning o'zida 15 daqiqa soviting — sovigach qotadi. Issiqligida ko'chirsangiz, sinib ketadi.",
               "Остудите прямо на противне 15 минут — остыв, печенье затвердеет. Горячим не перекладывайте — "
               "сломается."),
        ],
        "tip": _s("Pishirishdan oldin har biriga bir chimdim tuz sepsangiz, ta'm yanada boyiydi. Yopiq idishda "
                  "5 kungacha saqlanadi.",
                  "Если перед выпечкой посыпать каждое печенье крупинками соли, вкус станет ещё ярче. "
                  "В закрытой банке хранится до 5 дней."),
        "image_prompt": "peanut butter cookies with criss-cross fork pattern on parchment, jar of peanut paste",
    },
    {
        "slug": "qovoq-krem-shorva",
        "title": _s("Kokos slivkali qovoq krem-sho'rvasi", "Тыквенный крем-суп на кокосовых сливках"),
        "intro": _s(
            "Kuzgi qovoqdan bir kosa iliqlik: baxmaldek mayin, kokos slivkasi bilan qaymoqli, ustida qarsildoq "
            "qovoq urug'i. Sut ham, un ham ishlatilmaydi.",
            "Осенняя тыква в тарелке: бархатный суп, сливочный благодаря кокосовым сливкам, сверху хрустящие "
            "тыквенные семечки. Ни молока, ни муки."),
        "minutes": 40,
        "servings": _s("4 kishilik", "4 порции"),
        "per_serving": {"carbs": 13, "kcal": 210},
        "ingredients": [
            _i("200 ml", "200 мл", "Kokos slivkasi", "Кокосовые сливки", _COCONUT_CREAM,
               "Sut va qaymoq o'rnida: sho'rvaga mayinlik va yengil kokos ta'mi beradi.",
               "Вместо молока и сливок: бархатность и лёгкий кокосовый вкус."),
            _i("1 osh q.", "1 ст.л.", "Kokos yog'i", "Кокосовое масло", _COCONUT_OIL,
               "Piyoz va qovoqni shu yog'da qovursangiz, ta'm chuqurlashadi.",
               "Если обжарить на нём лук и тыкву, вкус станет глубже."),
            _i("2 osh q.", "2 ст.л.", "Qovoq urug'i (ustiga)", "Тыквенные семечки (сверху)", _PUMPKIN,
               "Qarsillash qo'shadi, magniyga boy.", "Добавляют хруст, богаты магнием."),
            _i("1 ch.q.", "1 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Qovoqning tabiiy shirinligini ochadi.", "Подчёркивает природную сладость тыквы."),
            _i("600 g", "600 г", "Qovoq (tozalangan)", "Тыква (очищенная)"),
            _i("1 ta", "1 шт", "Piyoz", "Лук"),
            _i("2 tishcha", "2 зубчика", "Sarimsoq", "Чеснок"),
            _i("500 ml", "500 мл", "Issiq suv yoki tovuq sho'rvasi", "Горячая вода или куриный бульон"),
            _i("bir chimdim", "по щепотке", "Muskat yong'og'i, qora qalampir", "Мускатный орех, чёрный перец"),
            _i("bir necha barg", "несколько листиков", "Petrushka (bezash uchun)", "Петрушка (для подачи)"),
        ],
        "steps": [
            _s("Qovoqni 2 sm kubik qilib, piyozni mayda to'g'rang, sarimsoqni maydalang.",
               "Нарежьте тыкву кубиком 2 см, лук — мелко, чеснок измельчите."),
            _s("Qozonda kokos yog'ini eritib, piyozni 4 daqiqa, yumshaguncha qovuring; sarimsoqni qo'shib yana "
               "1 daqiqa qovuring.",
               "Растопите кокосовое масло в кастрюле и обжарьте лук 4 минуты до мягкости, добавьте чеснок и "
               "жарьте ещё минуту."),
            _s("Qovoqni qo'shib 3 daqiqa aralashtirib turing. Issiq suv quyib, tuz soling va qopqoq ostida "
               "20 daqiqa, qovoq butunlay yumshaguncha qaynating.",
               "Добавьте тыкву и помешивайте 3 минуты. Влейте горячую воду, посолите и варите под крышкой "
               "20 минут, пока тыква полностью не размякнет."),
            _s("Olovdan olib, blender bilan silliq pyure qiling.",
               "Снимите с огня и пробейте блендером до гладкости."),
            _s("Slivkaning 2 osh qoshig'ini bezash uchun olib qo'ying, qolganini sho'rvaga quying. Muskat va "
               "qalampir seping va qaynatmasdan 2–3 daqiqa isiting — qaynasa, slivka ajralib qoladi.",
               "Отложите 2 ст. ложки сливок для подачи, остальные влейте в суп. Добавьте мускат и перец и "
               "прогрейте 2–3 минуты, не доводя до кипения, — иначе сливки расслоятся."),
            _s("Qovoq urug'ini quruq tovada 2–3 daqiqa, chirsillaguncha qovuring.",
               "Обжарьте тыквенные семечки на сухой сковороде 2–3 минуты, пока не начнут потрескивать."),
            _s("Sho'rvani kosalarga quyib, ustiga bir qoshiq slivka, qovoq urug'i va petrushka solib torting.",
               "Разлейте суп по тарелкам, добавьте ложку сливок, семечки и петрушку."),
        ],
        "tip": _s("Ta'mi yanada boy bo'lsin desangiz, qovoqni avval pechda 200°C da 25 daqiqa pishirib oling — "
                  "sho'rvaga karamelli ta'm qo'shiladi.",
                  "Для более насыщенного вкуса сначала запеките тыкву 25 минут при 200°C — появится карамельная "
                  "нотка."),
        "image_prompt": "creamy pumpkin soup with a coconut cream swirl, toasted pumpkin seeds and parsley",
    },
    {
        "slug": "grechka-lagmon",
        "title": _s("Grechka vermishelidan PP lag'mon", "ПП-лагман с гречневой вермишелью"),
        "intro": _s(
            "Lag'monning hamma narsasi joyida: go'sht, bulg'or qalampiri, sabzavotli quyuq vaju. Faqat oq un "
            "ugrasi o'rnida grechka unli vermishel — to'yimliroq va ta'mi lag'monga juda mos.",
            "В лагмане всё на месте: мясо, болгарский перец, густая овощная подлива. Только вместо лапши из "
            "белой муки — гречневая вермишель: сытнее, а вкус отлично подходит к лагману."),
        "minutes": 50,
        "servings": _s("4 kishilik", "4 порции"),
        "per_serving": {"carbs": 42, "kcal": 450},
        "ingredients": [
            _i("200 g", "200 г", "Grechka unli vermishel", "Гречневая вермишель", _BUCKWHEAT_NOODLES,
               "Oq un ugrasidan to'yimliroq; yong'oqsimon ta'mi vajuga juda mos.",
               "Сытнее лапши из белой муки; ореховый вкус отлично сочетается с подливой."),
            _i("2 osh q.", "2 ст.л.", "Zaytun yog'i (qovurish uchun)", "Оливковое масло (для жарки)", _OLIVE_FRY,
               "Go'sht va sabzavotni baland olovda qovurishga chidamli.",
               "Выдерживает жарку мяса и овощей на сильном огне."),
            _i("1 ch.q.", "1 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Ta'mni ochadi.", "Раскрывает вкус."),
            _i("400 g", "400 г", "Mol go'shti (yog'siz)", "Постная говядина"),
            _i("1 ta", "1 шт", "Piyoz", "Лук"),
            _i("1 ta kichik", "1 маленькая", "Sabzi", "Морковь"),
            _i("2 ta", "2 шт", "Bulg'or qalampiri (qizil va yashil)", "Болгарский перец (красный и зелёный)"),
            _i("100 g", "100 г", "Ko'k turp", "Зелёная редька"),
            _i("2 ta", "2 шт", "Pomidor", "Помидоры"),
            _i("1 osh q.", "1 ст.л.", "Tomat pastasi", "Томатная паста"),
            _i("3 tishcha", "3 зубчика", "Sarimsoq", "Чеснок"),
            _i("400 ml", "400 мл", "Issiq suv", "Горячая вода"),
            _i("1 ch.q.", "1 ч.л.", "Zira, qora qalampir", "Зира, чёрный перец"),
            _i("1/2 bog'", "1/2 пучка", "Kashnich", "Кинза"),
        ],
        "steps": [
            _s("Go'shtni 4 sm uzunlikda somoncha qilib to'g'rang. Piyoz, qalampir, sabzi va turpni ham somoncha, "
               "pomidorni kubik qilib to'g'rang.",
               "Нарежьте мясо соломкой длиной 4 см. Лук, перец, морковь и редьку — тоже соломкой, помидоры — кубиком."),
            _s("Qozonda yog'ni qizdirib, go'shtni baland olovda 5–6 daqiqa qovuring, keyin piyozni qo'shib yana "
               "3 daqiqa qovuring.",
               "Разогрейте масло в казане и обжарьте мясо на сильном огне 5–6 минут, затем добавьте лук и жарьте "
               "ещё 3 минуты."),
            _s("Sabzi, turp va qalampirni qo'shib 5 daqiqa, so'ng pomidor, tomat pastasi va maydalangan "
               "sarimsoqni qo'shib yana 3 daqiqa qovuring.",
               "Добавьте морковь, редьку и перец — на 5 минут, затем помидоры, томатную пасту и измельчённый "
               "чеснок — ещё на 3 минуты."),
            _s("Tuz, zira va qalampir seping, issiq suv quyib, qopqoq ostida past olovda 20 daqiqa dimlang — "
               "quyuq vaju tayyor.",
               "Посолите, добавьте зиру и перец, влейте горячую воду и тушите под крышкой на слабом огне "
               "20 минут — густая подлива готова."),
            _s("Shu vaqtda vermishelni qaynab turgan tuzli suvda qadoqda yozilganidan 1 daqiqa kam qaynating. "
               "Suvini to'kib, sovuq suvda chaying — bir-biriga yopishmaydi.",
               "Тем временем отварите вермишель в кипящей подсоленной воде на минуту меньше, чем указано на "
               "упаковке. Откиньте и промойте холодной водой — не слипнется."),
            _s("Vermishelni chuqur kosalarga solib, ustidan issiq vaju quying va to'g'ralgan kashnich seping.",
               "Разложите вермишель по глубоким пиалам, залейте горячей подливой и посыпьте рубленой кинзой."),
        ],
        "tip": _s("Vaju muzlatkichda 2 kun turadi: bugun lag'mon, ertasiga xuddi shu vaju bilan qovurma lag'mon "
                  "qiling.",
                  "Подлива хранится в холодильнике 2 дня: сегодня лагман, завтра с той же подливой — жареный "
                  "лагман."),
        "image_prompt": "lagman with buckwheat vermicelli in a deep bowl, beef, bell pepper and tomato sauce, coriander",
    },
    {
        "slug": "olmali-sharlotka",
        "title": _s("Suli unidan olmali PP sharlotka", "ПП-шарлотка с яблоками на овсяной муке"),
        "intro": _s(
            "Bolalikdagi sharlotka — oq un va shakarsiz. Suli uni, olma va dolchin hidi: choyga bir bo'lak — "
            "ko'ngil ham to'ladi, ratsion ham buzilmaydi.",
            "Шарлотка из детства — без белой муки и сахара. Овсяная мука, яблоки и аромат корицы: кусочек к "
            "чаю — и душа довольна, и рацион в порядке."),
        "minutes": 60,
        "servings": _s("8 bo'lak (22 sm qolip)", "8 кусков (форма 22 см)"),
        "per_serving": {"carbs": 18, "kcal": 135},
        "ingredients": [
            _i("150 g", "150 г", "Suli (ovsyanka) uni", "Овсяная мука", _OAT_FLOUR,
               "Oq un o'rnida: tolasi ko'proq, sharlotkaga yengil yong'oqsimon ta'm beradi.",
               "Вместо белой муки: больше клетчатки и лёгкий ореховый вкус."),
            _i("80 g", "80 г", "Eritritol", "Эритрит", _ERYTHRITOL,
               "Shakar o'rnida: shirinlik beradi, kaloriyasi deyarli yo'q.",
               "Вместо сахара: сладость почти без калорий."),
            _i("1 ch.q.", "1 ч.л.", "Dolchin", "Корица", _CINNAMON,
               "Olmaning eng yaxshi hamrohi — shirinlikni kuchaytiradi.",
               "Лучшая пара для яблок — усиливает ощущение сладости."),
            _i("3 ta", "3 шт", "Tuxum", "Яйца"),
            _i("3 ta (450 g)", "3 шт (450 г)", "Nordonroq olma", "Кисловатые яблоки"),
            _i("1 ch.q.", "1 ч.л.", "Pishirish kukuni (razrixlitel)", "Разрыхлитель"),
            _i("1 osh q.", "1 ст.л.", "Limon sharbati", "Лимонный сок"),
            _i("5 g", "5 г", "Sariyog' (qolip uchun)", "Сливочное масло (для формы)"),
        ],
        "steps": [
            _s("Pechni 180°C ga qizdiring. 22 sm li qolipni sariyog' bilan yog'lab, tubiga pergament to'shang.",
               "Разогрейте духовку до 180°C. Смажьте форму 22 см маслом и застелите дно пергаментом."),
            _s("Olmani urug'idan tozalab, yupqa bo'laklarga to'g'rang va limon sharbati hamda yarim choy qoshiq "
               "dolchin bilan aralashtiring — qoraymaydi.",
               "Очистите яблоки от семян, нарежьте тонкими дольками и смешайте с лимонным соком и половиной ложки "
               "корицы — не потемнеют."),
            _s("Tuxum va eritritolni mikserda 5–7 daqiqa, hajmi 2–3 baravar oshib, oqarib ko'pirguncha uring.",
               "Взбейте яйца с эритритом миксером 5–7 минут, пока масса не посветлеет и не увеличится в 2–3 раза."),
            _s("Suli uni, pishirish kukuni va qolgan dolchinni elab qo'shing va kurakcha bilan pastdan yuqoriga "
               "ehtiyotkorlik bilan aralashtiring — ko'pik o'tirib qolmasin.",
               "Просейте овсяную муку, разрыхлитель и оставшуюся корицу и аккуратно вмешайте лопаткой снизу вверх, "
               "чтобы масса не осела."),
            _s("Olmaning yarmini qolipga tering, ustidan xamirni quying va qolgan olmani ustiga tering.",
               "Выложите половину яблок в форму, залейте тестом, сверху выложите оставшиеся яблоки."),
            _s("180°C da 35–40 daqiqa pishiring; dastlabki 25 daqiqada pech eshigini ochmang. Yog'och cho'p quruq "
               "chiqsa — tayyor.",
               "Выпекайте 35–40 минут при 180°C; первые 25 минут не открывайте духовку. Сухая шпажка — готово."),
            _s("Qolipda 15 daqiqa soviting, keyin chiqarib, 8 bo'lakka kesing.",
               "Остудите в форме 15 минут, затем достаньте и нарежьте на 8 кусков."),
        ],
        "tip": _s("Olmaning bir qismini nok bilan almashtirsangiz, ta'mi yanada yumshoq bo'ladi. Sharlotka "
                  "ertasiga yanada nam va xushbo'y bo'ladi.",
                  "Замените часть яблок грушей — вкус станет мягче. На следующий день шарлотка ещё влажнее и "
                  "ароматнее."),
        "image_prompt": "apple charlotte cake made with oat flour, apple slices on top, cinnamon, one slice cut out, tea",
    },
    {
        "slug": "bulgur-salat",
        "title": _s("Bulgurli ko'katli PP salat", "ПП-салат с булгуром и зеленью"),
        "intro": _s(
            "Yengil, yangi va to'yimli: bulgur, pomidor, bodring va ko'p ko'kat, ustidan limon va zaytun yog'i. "
            "Tushlikka alohida taom yoki go'shtga garnir.",
            "Лёгкий, свежий и сытный: булгур, помидоры, огурцы и много зелени, заправка из лимона и оливкового "
            "масла. Отдельное блюдо на обед или гарнир к мясу."),
        "minutes": 35,
        "servings": _s("4 kishilik", "4 порции"),
        "per_serving": {"carbs": 24, "kcal": 225},
        "ingredients": [
            _i("120 g", "120 г", "Bulgur", "Булгур", _BULGUR,
               "Qaynatish shart emas — qaynoq suvda damlanadi; oddiy guruchdan tolaga boy.",
               "Варить не нужно — достаточно запарить кипятком; клетчатки больше, чем в рисе."),
            _i("3 osh q.", "3 ст.л.", "Zaytun yog'i (sovuq siqim)", "Оливковое масло (холодного отжима)", _OLIVE,
               "Sousning asosi: yangi, yengil ta'm.", "Основа заправки: свежий, мягкий вкус."),
            _i("1 ch.q.", "1 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Sabzavot ta'mini ochadi.", "Раскрывает вкус овощей."),
            _i("200 ml", "200 мл", "Qaynoq suv", "Кипяток"),
            _i("3 ta (300 g)", "3 шт (300 г)", "Pomidor", "Помидоры"),
            _i("2 ta (200 g)", "2 шт (200 г)", "Bodring", "Огурцы"),
            _i("1 bog'", "1 пучок", "Petrushka", "Петрушка"),
            _i("1/2 bog'", "1/2 пучка", "Yalpiz", "Мята"),
            _i("3–4 dona", "3–4 шт", "Ko'k piyoz", "Зелёный лук"),
            _i("1 ta", "1 шт", "Limon", "Лимон"),
            _i("bir chimdim", "щепотка", "Qora qalampir", "Чёрный перец"),
        ],
        "steps": [
            _s("Bulgurni yuvib idishga soling, yarim choy qoshiq tuz seping va 200 ml qaynoq suv quying. Yopib, "
               "20 daqiqa damlang.",
               "Промойте булгур, выложите в миску, добавьте половину ложки соли и залейте 200 мл кипятка. Накройте "
               "и оставьте на 20 минут."),
            _s("Shu vaqtda pomidor va bodringni 0,5 sm kubik qilib to'g'rang; pomidorning ortiqcha suvini to'kib "
               "tashlang.",
               "Тем временем нарежьте помидоры и огурцы кубиком 0,5 см; лишний сок помидоров слейте."),
            _s("Petrushka, yalpiz va ko'k piyozni juda mayda to'g'rang — bu salatda ko'kat bulgurdan ko'p bo'ladi.",
               "Очень мелко нарежьте петрушку, мяту и зелёный лук — зелени в этом салате больше, чем булгура."),
            _s("Sous: limon sharbati, zaytun yog'i, qolgan tuz va qora qalampirni aralashtiring.",
               "Заправка: смешайте лимонный сок, оливковое масло, оставшуюся соль и чёрный перец."),
            _s("Damlangan bulgurni vilka bilan aralashtirib, donalarini ajrating va to'liq soviting.",
               "Разрыхлите запаренный булгур вилкой и полностью остудите."),
            _s("Bulgur, sabzavot va ko'katni aralashtiring, sousni quying va 10 daqiqa tindirib, limon bo'lagi "
               "bilan torting.",
               "Смешайте булгур, овощи и зелень, полейте заправкой, дайте постоять 10 минут и подавайте с долькой "
               "лимона."),
        ],
        "tip": _s("Salatni oldindan tayyorlasangiz, pomidorni tortishdan oldin qo'shing — aks holda suv chiqaradi. "
                  "Go'sht yoki baliq bilan to'liq tushlik bo'ladi.",
                  "Если готовите заранее, помидоры добавьте перед подачей — иначе дадут сок. С мясом или рыбой — "
                  "полноценный обед."),
        "image_prompt": "bulgur salad with lots of chopped parsley, mint, tomato and cucumber, lemon and olive oil",
    },
    {
        "slug": "grechka-blinchik",
        "title": _s("Grechka unidan tvorogli blinchiklar", "Гречневые блинчики с творогом"),
        "intro": _s(
            "Yupqa, egiluvchan va yong'oqsimon ta'mli blinchiklar — bug'doy unisiz. Ichida vanilli tvorog: "
            "nonushtaga ham, choyga ham. Glyutensiz.",
            "Тонкие, эластичные блинчики с ореховым вкусом — без пшеничной муки. Внутри ванильный творог: и на "
            "завтрак, и к чаю. Без глютена."),
        "minutes": 45,
        "servings": _s("4 kishilik (12 dona)", "4 порции (12 штук)"),
        "per_serving": {"carbs": 25, "kcal": 375},
        "ingredients": [
            _i("120 g", "120 г", "Grechka uni (oddiy yoki yashil)", "Гречневая мука (обычная или зелёная)",
               _BUCKWHEAT_FLOUR,
               "Glyutensiz va tolaga boy; blinchikka chiroyli rang va yong'oqsimon ta'm beradi.",
               "Без глютена и с клетчаткой; красивый цвет и ореховый вкус."),
            _i("1–2 ch.q. (ta'bga ko'ra)", "1–2 ч.л. (по вкусу)", "Steviya", "Стевия", _STEVIA,
               "Tvorogni shirin qiladi: juda oz ketadi, kaloriyasi yo'q.",
               "Подслащивает творог: нужно совсем немного, калорий нет."),
            _i("1 osh q.", "1 ст.л.", "GHEE (tova uchun)", "Гхи (для сковороды)", _GHEE,
               "Yupqa blinchik yopishmaydi va kuymaydi.", "Тонкие блинчики не прилипают и не подгорают."),
            _i("2 ta", "2 шт", "Tuxum", "Яйца"),
            _i("300 ml", "300 мл", "Sut", "Молоко"),
            _i("1 osh q.", "1 ст.л.", "O'simlik yog'i (xamirga)", "Растительное масло (в тесто)"),
            _i("bir chimdim", "щепотка", "Tuz", "Соль"),
            _i("400 g", "400 г", "Tvorog (5–9%)", "Творог (5–9%)"),
            _i("2 osh q.", "2 ст.л.", "Qaymoq (ichlikka va tortish uchun)", "Сметана (в начинку и для подачи)"),
            _i("bir chimdim", "щепотка", "Vanilin", "Ванилин"),
        ],
        "steps": [
            _s("Tuxum, tuz va sutning yarmini venchik bilan chayqating, grechka unini qo'shib, silliq bo'lguncha "
               "aralashtiring.",
               "Взбейте венчиком яйца, соль и половину молока, всыпьте гречневую муку и перемешайте до гладкости."),
            _s("Qolgan sut va o'simlik yog'ini qo'shib aralashtiring. Xamirni 20 daqiqa dam bering — un suyuqlikni "
               "shimib, blinchik yirtilmaydi.",
               "Добавьте оставшееся молоко и масло, перемешайте. Дайте тесту отдохнуть 20 минут — мука впитает "
               "жидкость, и блинчики не будут рваться."),
            _s("Tovani o'rtacha olovda qizdirib, ozgina GHEE surting. Cho'mich bilan ozgina xamir quyib, tovani "
               "aylantirib yupqa yoying.",
               "Разогрейте сковороду на среднем огне и смажьте гхи. Налейте половником немного теста и, вращая "
               "сковороду, распределите тонким слоем."),
            _s("Har tomonini 1–1,5 daqiqadan pishiring. Birinchi blinchik yirtilsa, xamir quyuq: 2–3 osh qoshiq "
               "sut qo'shing.",
               "Жарьте по 1–1,5 минуты с каждой стороны. Если первый блинчик рвётся — тесто густое: добавьте "
               "2–3 ст. ложки молока."),
            _s("Ichlik: tvorog, 1 osh qoshiq qaymoq, steviya va vanilinni vilka bilan silliq bo'lguncha ezing.",
               "Начинка: разомните вилкой творог с 1 ст. ложкой сметаны, стевией и ванилином до однородности."),
            _s("Har bir blinchikka 1,5 osh qoshiq ichlik qo'yib, konvert qilib o'rang.",
               "Положите на каждый блинчик 1,5 ст. ложки начинки и сверните конвертом."),
            _s("Tovada har tomonini 1 daqiqadan qizartirib, qolgan qaymoq bilan issiq holda torting.",
               "Подрумяньте на сковороде по минуте с каждой стороны и подавайте горячими с оставшейся сметаной."),
        ],
        "tip": _s("Shirin bo'lmagan varianti: tvorog o'rniga piyoz bilan qovurilgan qiyma — tushlikka to'yimli "
                  "blinchik.",
                  "Несладкий вариант: вместо творога — фарш, обжаренный с луком, — сытные блинчики на обед."),
        "image_prompt": "thin buckwheat crepes folded into envelopes with cottage cheese filling, sour cream",
    },
    {
        "slug": "zogora-non",
        "title": _s("Makkajo'xori unidan zog'ora non", "Кукурузная лепёшка зогора-нон"),
        "intro": _s(
            "Buvilarimiz yopgan zog'ora non — glyutensiz va qatiq bilan yumshoq. Uyda pechda cho'yan tovada "
            "pishadi, sho'rva va qatiqqa juda mos.",
            "Зогора-нон, как у наших бабушек: без глютена и мягкая благодаря катыку. Печётся дома в духовке в "
            "чугунной сковороде, отлично подходит к супу и катыку."),
        "minutes": 50,
        "servings": _s("8 bo'lak", "8 кусков"),
        "per_serving": {"carbs": 24, "kcal": 180},
        "ingredients": [
            _i("250 g", "250 г", "Makkajo'xori uni", "Кукурузная мука", _CORN_FLOUR,
               "Zog'oraning asosi: glyutensiz, oltinrang va biroz shirinroq ta'm.",
               "Основа зогоры: без глютена, золотистый цвет и сладковатый вкус."),
            _i("2 osh q.", "2 ст.л.", "GHEE", "Гхи", _GHEE,
               "Xamirga va tovaga: qobig'i qarsildoq, ta'mi qaymoqli bo'ladi.",
               "В тесто и для сковороды: хрустящая корочка и сливочный вкус."),
            _i("1 ch.q.", "1 ч.л.", "Himalay tuzi", "Гималайская соль", _SALT,
               "Ta'mni ochadi.", "Раскрывает вкус."),
            _i("300 ml + tortish uchun", "300 мл + для подачи", "Qatiq", "Катык"),
            _i("2 ta", "2 шт", "Tuxum", "Яйца"),
            _i("1/2 ch.q.", "1/2 ч.л.", "Soda", "Сода"),
        ],
        "steps": [
            _s("Pechni 200°C ga qizdiring. 22–24 sm li cho'yan tova yoki qolipga 1 osh qoshiq GHEE surtib, pechga "
               "qo'yib qizdiring.",
               "Разогрейте духовку до 200°C. Смажьте чугунную сковороду или форму 22–24 см 1 ст. ложкой гхи и "
               "поставьте в духовку прогреться."),
            _s("Makkajo'xori uni, soda va tuzni aralashtiring.",
               "Смешайте кукурузную муку, соду и соль."),
            _s("Boshqa idishda 300 ml qatiq, tuxum va qolgan GHEE yog'ini (eritib) chayqating.",
               "В другой миске взбейте 300 мл катыка, яйца и оставшееся растопленное гхи."),
            _s("Ikkala aralashmani birlashtirib, quyuq qaymoqdek xamir bo'lguncha aralashtiring va 10 daqiqa "
               "qoldiring — un namni shimadi.",
               "Соедините обе смеси, перемешайте до густоты сметаны и оставьте на 10 минут — мука впитает влагу."),
            _s("Qizigan tovaga xamirni quyib tekislang va ustini barmoq uchi bilan bosib, chuqurchalar qiling.",
               "Вылейте тесто в горячую сковороду, разровняйте и сделайте кончиками пальцев ямочки."),
            _s("200°C da 25–30 daqiqa, usti oltinrang bo'lib yorilguncha pishiring.",
               "Выпекайте 25–30 минут при 200°C, пока верх не станет золотистым и не потрескается."),
            _s("10 daqiqa tindirib, 8 bo'lakka kesing va qatiq bilan torting.",
               "Дайте постоять 10 минут, нарежьте на 8 кусков и подавайте с катыком."),
        ],
        "tip": _s("Nonushtaga sho'r zog'ora: xamirga 2 osh qoshiq mayda to'g'ralgan ko'kat va bir chimdim qora "
                  "sedana qo'shing. Ertasiga tovada ikki tomonini isitib olsangiz, yana yumshoq bo'ladi.",
                  "Несладкая зогора к завтраку: добавьте в тесто 2 ст. ложки рубленой зелени и щепотку чёрного "
                  "тмина. Назавтра прогрейте на сковороде с двух сторон — снова станет мягкой."),
        "image_prompt": "uzbek cornbread zogora non in a cast iron skillet, golden cracked dimpled top, wedges, "
                        "bowl of qatiq",
    },
]
