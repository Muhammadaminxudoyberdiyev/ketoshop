"""
Ismdan jinsni taxmin qilish — mijoz portreti uchun (customer_portrait.py).

Egasi, 2026-11-15: "ismidan erkak yoki ayol ekanini aniqlasin". Model emas,
oddiy, takrorlanadigan qoida: o'zbek va rus ismlari ro'yxati + qo'shimchalar.

  infer("Dilnoza")          -> ("f", 0.97)
  infer("Sardorbek")        -> ("m", 0.95)
  infer("Sasha")            -> ("unknown", 0.0)   # ikkalasida ham bor

Tartib:
  1. Murojaat so'zi ism yonida bo'lsa (aka, opa, xola, brat...) — o'sha.
  2. Har bir so'z navbat bilan: aniq ro'yxat (ayol / erkak / ikkalasi),
     keyin qo'shimcha: -bek, -jon, -boy, -ullo, -iddin, -zod, -yor → erkak;
     -xon, -gul, -oy, -niso, -bonu, -begim → ayol; -a / -ya → ayol
     (Nikita, Ilya, Hamza, Muso kabi istisnolar ro'yxatda).
     -jon / -xon oldidagi asos ham tekshiriladi: "Azizxon" — erkak,
     "Saidaxon" — ayol.
  3. Familiya / otasining ismi: -ova, -ovna, qizi → ayol; -ov, -ovich,
     o'g'li → erkak.
  Hech biri aniq bo'lmasa — "unknown". Ishonch MIN_CONFIDENCE dan past
  bo'lsa ham "unknown".

Natija mijozga hech qachon aytilmaydi va murojaatda ishlatilmaydi — faqat
adminlar ko'radigan portret va hisobot uchun.
"""
import re

MIN_CONFIDENCE = 0.7

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "қ": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "ў": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ҳ": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "",
    "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ә": "a", "ө": "o", "ү": "u",
    "ң": "n", "і": "i",
}


def normalize(word: str) -> str:
    """Bitta so'z -> solishtirish kaliti: kichik lotin harflar, tutuq belgisisiz,
    x/h, q/k, kh/x, dj/j bir xil, qo'sh harf bitta ("Shahnoza" = "Шахноза" =
    "Shaxnoza", "Abdulla" = "Abdula")."""
    text = "".join(_CYR.get(ch, ch) for ch in (word or "").lower())
    text = re.sub(r"[ʻʼ‘’'`´\-]", "", text)
    text = re.sub(r"[^a-z]", "", text)
    text = text.replace("kh", "x").replace("zh", "j").replace("dj", "j")
    text = re.sub(r"(?<![scz])h", "x", text)
    text = text.replace("q", "k").replace("w", "v")
    if text.startswith("ye"):
        text = text[1:]
    return re.sub(r"(.)\1+", r"\1", text)


def _keys(names: str) -> set[str]:
    return {normalize(n) for n in names.split()}


# ───────────────────────────── ro'yxatlar ───────────────────────────────────
# Ko'pi qo'shimcha qoidasidan ham to'g'ri chiqadi — ro'yxat undosh bilan
# tugaydigan ismlar va istisnolar uchun kerak.

FEMALE = _keys("""
    Nilufar Gulshan Yulduz Asal Shirin Dilorom Lobar Muattar Gavhar Hulkar Oydin
    Bahor Sanobar Dilbar Gulbahor Mehribon Zarnigor Gulnigor Nigor Mohinur Gulnur
    Charos Kumush Rayhon Malohat Sevinch Saodat Muhabbat Inobat Xosiyat Maryam
    Zaynab Gulruh Mehrangiz Parizod Dilafruz Gulandom Gulsanam Sabohat Mukarram
    Muazzam Musharraf Laylo Shahlo Zuhro Barno Rano Ra'no Zebo Dilrabo Marhabo
    Gulchiroy Mehri Pari Gulbadan Gulnoz Shahnoz Sitorabonu Oysuluv Sadoqat
    Lyubov Asel Nelli Natali Ainur Aynur Gulnaz Gulya Diloram Nigoraxon
""")

MALE = _keys("""
    Aziz Sardor Jasur Bobur Nodir Akmal Anvar Rustam Jamshid Sherzod Bekzod Farrux
    Shoxrux Shohruh Doniyor Javohir Islom Ibrohim Muhammad Muhammadali Alisher Temur
    Timur Farhod Dilshod Ravshan Zafar Shuhrat Botir Bahodir Ilhom Komil Laziz Mansur
    Umid Xurshid Yusuf Jahongir Shavkat Davron Abbos Hasan Husan Kamron Azamat Rahim
    Karim Salim Firdavs Behruz Ozod Sanjar Abror Asror Akbar Asad Bahrom Baxtiyor
    Erkin Hamid Ikrom Ilyos Jalol Jamol Kamol Lochin Mahmud Murod Odil Olim Orif
    Po'lat Qodir Rasul Said Sobir Tohir Toxir Umar Usmon Yorqin Zokir Zohid Akrom
    Ergash Eshmat Toshmat G'ayrat G'ulom Ismoil Qahramon Rahmat Hikmat Ne'mat Tolib
    O'ktam Uktam O'tkir Yunus Ziyod Doston Bunyod Jahon Shoxjahon Mirjahon Ali Vali
    Mustafo Mustafa Murtazo Murtaza Muso Musa Iso Isa Yahyo Yahya Zakariyo Zakariya
    Hamza Toha Mirzo Sherali Nurali Alibek Abdulaziz Abdurahmon Abdurrahmon Fayz
    Aleksandr Aleksey Alexey Alexander Andrey Anton Artyom Artem Artur Boris Vadim
    Viktor Vladimir Vladislav Dmitriy Dmitry Dmitrii Denis Yevgeniy Evgeniy Igor Ivan
    Kirill Konstantin Maksim Maxim Mikhail Nikolay Oleg Pavel Roman Ruslan Sergey
    Stanislav Yuriy Yuri Vyacheslav Eduard Rinat Marat Damir Ildar Ilnur Ilya Nikita
    Daniil Danil Egor Yegor Gleb Fyodor Leonid Lev Mark Matvey Pyotr Petr Semyon
    Stepan Valeriy Vitaliy Anatoliy Gennadiy Arkadiy Grigoriy Georgiy Rafael Robert
    Albert Emil Edgar Renat Ramil Ravil Azat Aydar Misha Dima Kostya Vanya Pasha
    Lyosha Tolya Vitya Petya Grisha Danila Kuzma Foma Savva Lyova Seryoja Seryozha
""")

# Ikkalasida ham uchraydi — taxmin qilinmaydi.
BOTH = _keys("""
    Sasha Zhenya Jenya Valya Shura Slava Iqbol Navro'z Navruz Hayot Nur Dilnur
    Hurmat Saxovat Ulug' Sevar Dildor Nurislom Bakht Baxt Omon
""")

# Ism yonida turgan murojaat so'zi — o'zi aytgan bo'lsa, kuchli belgi.
HONORIFIC_M = _keys("aka akajon akam aka-jon uka ukajon brat bratan amaki tog'a pochcha xo'ja hoji "
                    "ota otajon bobo bobojon")
HONORIFIC_F = _keys("opa opajon opam opa-jon apa apajon singil singlim xola xolajon amma ammajon "
                    "kelin yanga kelinoy ona onajon buvi buvijon momo")

# (qo'shimcha, jins, ishonch) — birinchi mos kelgani olinadi, tartib muhim
# (-boy -oy dan oldin).
_SUFFIXES = [
    ("begim", "f", 0.95), ("bonu", "f", 0.95), ("banu", "f", 0.95), ("niso", "f", 0.95),
    ("nisa", "f", 0.95), ("gul", "f", 0.9), ("noz", "f", 0.85),
    ("bek", "m", 0.95), ("mirzo", "m", 0.95), ("mirza", "m", 0.95), ("muxamad", "m", 0.95),
    # -illa ataylab yo'q: Komila, Jamila, Kamila, Adila — ayol ismlari.
    ("jaxon", "m", 0.9), ("ula", "m", 0.95), ("ulo", "m", 0.95), ("ulox", "m", 0.95),
    ("ilo", "m", 0.95), ("idin", "m", 0.95), ("udin", "m", 0.95),
    ("adin", "m", 0.95), ("murod", "m", 0.95), ("boy", "m", 0.9), ("bay", "m", 0.9),
    ("zod", "m", 0.9), ("shod", "m", 0.9), ("yor", "m", 0.85), ("dor", "m", 0.85),
    ("kul", "m", 0.85), ("ali", "m", 0.8), ("iy", "m", 0.85), ("ey", "m", 0.85),
    ("oy", "f", 0.8),
]

_PATRONYMIC_F = ("ovna", "evna", "ichna", "kizi")
_PATRONYMIC_M = ("ovich", "evich", "ogli", "ugli")
_SURNAME_F = ("ova", "eva", "skaya")
_SURNAME_M = ("ov", "ev", "skiy", "skii", "sky")


def _first_name(key: str, depth: int = 0) -> tuple[str, float] | None:
    """Bitta so'z ism sifatida: (jins, ishonch), "ikkalasi" -> ("unknown", 0),
    hech narsa topilmasa None."""
    if len(key) < 2:
        return None
    if key in BOTH:
        return ("unknown", 0.0)
    if key in FEMALE:
        return ("f", 0.97)
    if key in MALE:
        return ("m", 0.97)
    # -jon / -xon: avval asosi ("Azizxon" -> Aziz, "Saidaxon" -> Saida).
    # "-jahon" (Shoxjahon, Mirjahon) — bu qo'shimcha emas, pastdagi ro'yxatda.
    if depth == 0 and not key.endswith("jaxon"):
        for tail, gender, conf in (("jon", "m", 0.75), ("xon", "f", 0.7)):
            if not key.endswith(tail) or len(key) - len(tail) < 3:
                continue
            found = _first_name(key[:-len(tail)], depth + 1)
            if found is None:
                return (gender, conf)
            if found[0] == "unknown":
                return found
            return (found[0], round(found[1] * 0.97, 2))
    for tail, gender, conf in _SUFFIXES:
        if key.endswith(tail) and len(key) > len(tail) + 1:
            return (gender, conf)
    # Abdu- (Abdusattor, Abduqodir) — erkak; "Abdullayeva" kabi familiya -a da tugaydi.
    if key.startswith("abdu") and len(key) > 5 and not key.endswith("a"):
        return ("m", 0.95)
    if key.endswith("a") and len(key) >= 3:
        return ("f", 0.85)
    return None


def _family_name(key: str) -> tuple[str, float] | None:
    if len(key) < 5:
        return None
    if key.endswith(_PATRONYMIC_F):
        return ("f", 0.95)
    if key.endswith(_PATRONYMIC_M):
        return ("m", 0.95)
    if key.endswith(_SURNAME_F):
        return ("f", 0.85)
    if key.endswith(_SURNAME_M):
        return ("m", 0.8)
    return None


def infer(name: str | None) -> tuple[str, float]:
    """("m" | "f" | "unknown", ishonch 0..1). Bo'sh, emoji yoki taxallus —
    ("unknown", 0.0)."""
    words = [normalize(w) for w in re.split(r"[\s,.;/|()]+", name or "") if w]
    words = [w for w in words if w]
    if not words:
        return ("unknown", 0.0)
    honor = {w for w in words if w in HONORIFIC_M or w in HONORIFIC_F}
    if honor:
        male = any(w in HONORIFIC_M for w in honor)
        female = any(w in HONORIFIC_F for w in honor)
        if male != female:
            return ("m" if male else "f", 0.95)
    names = [w for w in words if w not in honor]
    for key in names:
        found = _first_name(key)
        if found and found[0] != "unknown":
            return _confident(found)
    for key in names:
        found = _family_name(key)
        if found:
            return _confident(found)
    return ("unknown", 0.0)


def _confident(found: tuple[str, float]) -> tuple[str, float]:
    gender, conf = found
    if conf < MIN_CONFIDENCE:
        return ("unknown", 0.0)
    return (gender, conf)


def first_word(name: str | None) -> str:
    """Hisobot misoli uchun faqat birinchi so'z (ism) — familiyasiz."""
    for word in re.split(r"\s+", (name or "").strip()):
        clean = word.strip(",.;:!?()\"'«»")
        if clean:
            return clean[:24]
    return ""
