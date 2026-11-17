"""📄 Ilova ichidagi «Oferta shartlari» — matn serverda, yangi APK'siz o'zgaradi.

GET  /app/v1/terms?lang=uz      ochiq: shartlar matni va tahrir (VERSION)
POST /app/v1/terms/accept       imzolangan sessiya: shu tahrirni qabul qildi

Qabul qilish ham qayd etiladi: kirishda ilova o'qigan tahrirni yuboradi
(app_auth: app_login_requests / app_sessions.terms_version), keyingi tahrir
chiqsa — ilova uni ko'rsatib, «Qabul qilaman» bosilganda shu yerga yozadi.

Matn o'zgarsa VERSION ni yangilang (sana): ilova hamma xaridorlardan
yangi tahrirni qayta qabul qilishni so'raydi.

Huquqiy havolalar lex.uz va rasmiy manbalarga ko'ra tekshirildi (17.11.2026);
muhim tahrirlarni yurist bilan tasdiqlang.
"""
from __future__ import annotations

import re

from aiohttp import web

VERSION = "2026-11-17"

# Sotuvchi rekvizitlari — egasi to'ldiradi (yuridik nom, STIR, manzil).
# Bo'sh bo'lsa, shartlarda faqat Telegram aloqasi ko'rsatiladi.
SELLER = {"name": "", "tin": "", "address": ""}

_TITLE = {"uz": "Oferta shartlari", "ru": "Условия оферты"}

SECTIONS: list[dict] = [
    {
        "title": {"uz": "1. Ommaviy oferta va uni qabul qilish", "ru": "1. Публичная оферта и её принятие"},
        "items": [
            {"uz": "Ushbu shartlar Ketoshop (keyingi o'rinlarda — Do'kon) Telegram bot (@ketoshopbot), Mini App va "
                   "Android ilova orqali mahsulot sotishi bo'yicha ommaviy oferta hisoblanadi (O'zbekiston "
                   "Respublikasi Fuqarolik kodeksining 369-moddasi).",
             "ru": "Настоящие условия являются публичной офертой Ketoshop (далее — Магазин) о продаже товаров через "
                   "Telegram-бот (@ketoshopbot), Mini App и Android-приложение (статья 369 Гражданского кодекса "
                   "Республики Узбекистан)."},
            {"uz": "Ilovaga Telegram orqali kirish yoki buyurtma berish shartlarni to'liq qabul qilish (aksept) "
                   "hisoblanadi (Fuqarolik kodeksining 370-moddasi). Qaysi tahrir qachon qabul qilingani qayd etiladi.",
             "ru": "Вход в приложение через Telegram или оформление заказа означает полное принятие условий "
                   "(акцепт, статья 370 Гражданского кодекса). Какая редакция и когда принята — фиксируется."},
        ],
    },
    {
        "title": {"uz": "2. Buyurtma, narx va to'lov", "ru": "2. Заказ, цена и оплата"},
        "items": [
            {"uz": "Narx, chegirma, sovg'alar, yetkazib berish haqi va Keto bonuslari faqat Do'kon tizimida "
                   "hisoblanadi. Buyurtma tasdiqlangan summa yakuniy hisoblanadi.",
             "ru": "Цена, скидки, подарки, стоимость доставки и бонусы Keto рассчитываются только системой "
                   "Магазина. Итоговой считается сумма подтверждённого заказа."},
            {"uz": "Karta orqali to'lovda buyurtma to'lov cheki qabul qilingandan keyin yaratiladi; chekni "
                   "administrator tekshiradi. Naqd to'lov faqat Do'kon kuryeri va olib ketishda qabul qilinadi.",
             "ru": "При оплате картой заказ создаётся после получения чека об оплате; чек проверяет "
                   "администратор. Наличные принимаются только курьером Магазина и при самовывозе."},
            {"uz": "Buyurtmani «Kutilmoqda» yoki «Tasdiqlangan» holatida bekor qilish mumkin. Mahsulotni qaytarish "
                   "va almashtirish iste'molchilar huquqlarini himoya qilish to'g'risidagi qonunchilikka muvofiq amalga "
                   "oshiriladi.",
             "ru": "Заказ можно отменить в статусе «В ожидании» или «Подтверждён». Возврат и обмен товара — в "
                   "соответствии с законодательством о защите прав потребителей."},
            {"uz": "Yandex Taxi, UzPost, BTS va EMU orqali yetkazishda narx va muddat shu xizmatlar tariflariga ko'ra.",
             "ru": "При доставке через Yandex Taxi, UzPost, BTS и EMU цена и сроки — по тарифам этих служб."},
        ],
    },
    {
        "title": {"uz": "3. Shaxsiy ma'lumotlar", "ru": "3. Персональные данные"},
        "items": [
            {"uz": "Qayta ishlanadi: Telegram ID, ism va username, telefon raqami, yetkazish joylashuvi va manzil "
                   "izohi, buyurtmalar tarixi, Keto balansi, ilovaga kirilgan qurilma nomi, kirish vaqti va IP-manzil, "
                   "ilovaning xavfsizlik tekshiruvi natijalari.",
             "ru": "Обрабатываются: Telegram ID, имя и username, номер телефона, геолокация доставки и комментарий "
                   "к адресу, история заказов, баланс Keto, название устройства, время входа и IP-адрес, результаты "
                   "проверки безопасности приложения."},
            {"uz": "Maqsad: buyurtmani bajarish va yetkazish, bot orqali buyurtma holati haqida xabar berish, "
                   "Keto bonuslari, firibgarlikning oldini olish va xavfsizlik.",
             "ru": "Цели: выполнение и доставка заказа, уведомления о статусе заказа в боте, бонусы Keto, "
                   "предотвращение мошенничества и безопасность."},
            {"uz": "Yetkazib berish xizmatiga faqat yetkazish uchun zarur ma'lumot (ism, telefon, manzil) beriladi; "
                   "vakolatli davlat organlariga — faqat qonunda belgilangan hollarda.",
             "ru": "Службе доставки передаются только данные, нужные для доставки (имя, телефон, адрес); "
                   "уполномоченным государственным органам — только в случаях, предусмотренных законом."},
            {"uz": "Saqlangan ma'lumotlarni ko'rish va o'chirishni botda /malumotlarim buyrug'i bilan so'rashingiz "
                   "mumkin. Asos: «Shaxsga doir ma'lumotlar to'g'risida»gi O'zbekiston Respublikasi Qonuni "
                   "(02.07.2019, O'RQ-547).",
             "ru": "Посмотреть и запросить удаление сохранённых данных можно командой /malumotlarim в боте. "
                   "Основание: Закон Республики Узбекистан «О персональных данных» (02.07.2019, ЗРУ-547)."},
        ],
    },
    {
        "title": {"uz": "4. Xavfsizlik: taqiqlangan harakatlar", "ru": "4. Безопасность: запрещённые действия"},
        "items": [
            {"uz": "Ilovani buzish, dekompilyatsiya qilish, o'zgartirish yoki qayta imzolab tarqatish.",
             "ru": "Взлом, декомпиляция, изменение приложения или его распространение с другой подписью."},
            {"uz": "Ilova so'rovlarini ushlab qolish, soxtalashtirish yoki qayta yuborish; bot, skript va boshqa "
                   "avtomatlashtirilgan vositalar bilan buyurtma berish.",
             "ru": "Перехват, подделка или повторная отправка запросов приложения; оформление заказов ботами, "
                   "скриптами и другими автоматизированными средствами."},
            {"uz": "Boshqa shaxsning Telegram hisobi, qurilmasi yoki kirish kodidan foydalanish; kirish so'rovini "
                   "aldov yo'li bilan boshqa odamga tasdiqlatish.",
             "ru": "Использование чужого аккаунта Telegram, устройства или кода входа; подтверждение запроса на "
                   "вход другим человеком путём обмана."},
            {"uz": "Do'kon serverlariga ruxsatsiz kirish yoki kirishga urinish, soxta to'lov cheki yuborish.",
             "ru": "Несанкционированный доступ или попытка доступа к серверам Магазина, отправка поддельного чека."},
        ],
    },
    {
        "title": {"uz": "5. Buzib kirish va soxta buyurtmalar uchun javobgarlik",
                  "ru": "5. Ответственность за взлом и поддельные заказы"},
        "items": [
            {"uz": "4-bo'limdagi harakatlar orqali shakllantirilgan buyurtmalar soxta deb topiladi va bekor qilinadi; "
                   "ular bo'yicha Do'konda hech qanday majburiyat yuzaga kelmaydi.",
             "ru": "Заказы, сформированные действиями из раздела 4, признаются поддельными и отменяются; "
                   "обязательств Магазина по ним не возникает."},
            {"uz": "Hisobga va undagi barcha qurilmalarga kirish to'xtatiladi, noqonuniy olingan Keto bonuslari "
                   "bekor qilinadi.",
             "ru": "Доступ к аккаунту и всем его устройствам прекращается, незаконно полученные бонусы Keto "
                   "аннулируются."},
            {"uz": "Tizim qayd etgan ma'lumotlar — vaqt, qurilma, IP-manzil, Telegram hisobi va harakatlar jurnali — "
                   "dalil sifatida saqlanadi va huquqni muhofaza qiluvchi organlarga topshiriladi.",
             "ru": "Зафиксированные системой данные — время, устройство, IP-адрес, аккаунт Telegram и журнал "
                   "действий — сохраняются как доказательства и передаются в правоохранительные органы."},
            {"uz": "Aybdorlar O'zbekiston Respublikasi qonunchiligiga muvofiq javobgarlikka tortiladi, jumladan "
                   "Jinoyat kodeksining 168-moddasi (firibgarlik) va XX¹ bobi — axborot texnologiyalari sohasidagi "
                   "jinoyatlar (jumladan 278²-modda — kompyuter axborotidan qonunga xilof ravishda foydalanish), "
                   "shuningdek Ma'muriy javobgarlik to'g'risidagi kodeks bo'yicha. Yetkazilgan zarar Fuqarolik "
                   "kodeksiga muvofiq undiriladi.",
             "ru": "Виновные привлекаются к ответственности по законодательству Республики Узбекистан, в том числе "
                   "по статье 168 Уголовного кодекса (мошенничество) и главе XX¹ — преступления в сфере "
                   "информационных технологий (в том числе статья 278² — незаконный доступ к компьютерной "
                   "информации), а также по Кодексу об административной ответственности. Причинённый ущерб "
                   "взыскивается в соответствии с Гражданским кодексом."},
            {"uz": "Zaiflik topgan bo'lsangiz, uni ishlatmasdan @keto_market ga xabar bering — vijdonan xabar "
                   "berganlarga nisbatan da'vo qilinmaydi.",
             "ru": "Нашли уязвимость — не используйте её и сообщите @keto_market: к добросовестно сообщившим "
                   "претензий не будет."},
        ],
    },
    {
        "title": {"uz": "6. Nizolar va shartlarning o'zgarishi", "ru": "6. Споры и изменение условий"},
        "items": [
            {"uz": "Nizolar muzokara yo'li bilan, kelishilmasa — O'zbekiston Respublikasi qonunchiligiga muvofiq "
                   "sudda hal qilinadi.",
             "ru": "Споры решаются переговорами, а при недостижении согласия — в суде по законодательству "
                   "Республики Узбекистан."},
            {"uz": "Do'kon shartlarni o'zgartirishi mumkin. Yangi tahrir ilovada e'lon qilinadi va qabul "
                   "qilingandan keyin amal qiladi.",
             "ru": "Магазин может изменять условия. Новая редакция публикуется в приложении и действует после "
                   "её принятия."},
            {"uz": "Aloqa: Telegram @keto_market, bot @ketoshopbot.",
             "ru": "Контакты: Telegram @keto_market, бот @ketoshopbot."},
        ],
    },
]

_VERSION_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def clean_version(value) -> str | None:
    """A terms version as the app reports it, or None."""
    return value if isinstance(value, str) and _VERSION_RE.fullmatch(value) else None


def _text(value: dict, lang: str) -> str:
    text = value.get("ru" if lang == "ru" else "uz") or value.get("uz") or ""
    if lang == "uz_cyr":
        import translit
        text = translit.lat_to_cyr(text)
    return text


def render(lang: str) -> dict:
    lang = lang if lang in ("uz", "uz_cyr", "ru") else "uz"
    sections = [{"title": _text(s["title"], lang), "items": [_text(i, lang) for i in s["items"]]}
                for s in SECTIONS]
    seller = [v for v in (SELLER.get("name"), SELLER.get("tin") and f"STIR {SELLER['tin']}", SELLER.get("address")) if v]
    if seller:
        title = {"uz": "Sotuvchi", "ru": "Продавец"}
        sections.insert(0, {"title": _text(title, lang), "items": [", ".join(seller)]})
    return {"version": VERSION, "title": _text(_TITLE, lang), "sections": sections}


async def handle_terms(request: web.Request) -> web.Response:
    return web.json_response(render(request.query.get("lang", "uz")), headers={"Cache-Control": "no-store"})


async def handle_accept(request: web.Request) -> web.Response:
    """The signed-in app accepted the current terms."""
    import app_auth
    import database
    session = await app_auth.authenticate(request)
    if isinstance(session, web.Response):
        return session
    try:
        data = await request.json()
    except ValueError:
        data = {}
    if clean_version((data or {}).get("version")) != VERSION:
        return web.json_response({"error": "stale_version", "version": VERSION}, status=409)
    async with database.pool.acquire() as conn:
        await conn.execute(
            "UPDATE app_sessions SET terms_version = $2, terms_accepted_at = now() WHERE id = $1",
            session.id, VERSION)
    return web.json_response({"ok": True, "version": VERSION}, headers={"Cache-Control": "no-store"})


def add_routes(app: web.Application) -> None:
    app.router.add_get("/app/v1/terms", handle_terms)
    app.router.add_post("/app/v1/terms/accept", handle_accept)
