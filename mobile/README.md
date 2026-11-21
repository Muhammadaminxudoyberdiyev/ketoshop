# Ketoshop — Android ilovasi (xaridorlar uchun)

Ilova = **xavfsiz native qobiq + do'konning o'zi (sayt)**.

- Native (Flutter + Kotlin): Telegram bot orqali kirish, qurilma kaliti
  (Android Keystore), sessiya, Oferta shartlari, «Ilova va xavfsizlik»
  (qurilmalar, chiqish), yangilanish.
- Do'kon: Mini App sahifasining o'zi (`webapp/index.html`) ilova ichidagi
  WebView'da — dizayn, katalog, rasmlar, 4 ta keto o'yini, AI yordamchi,
  retseptlar, sevimlilar, savat, xarita bilan joylashuv, chek. **Saytga
  qo'shilgan har narsa ilovada darhol chiqadi — yangi APK'siz.**

Xavfsizlik: [SECURITY.md](SECURITY.md).

## Arxitektura

```
lib/
  main.dart                 ishga tushirish
  app/                      kompozitsiya ildizi (services.dart), mavzu, AppScope
  core/
    config.dart             host, bot, vaqtlar
    net/                    pinned TLS, so'rov imzosi, ApiClient (refresh, qayta urinish)
    auth/                   sessiya (Keystore'da shifrlangan), kirish oqimi
    platform/               Kotlin bilan kanal (NativeBridge)
    remote/                 serverdagi versiya va Oferta tahriri
    l10n/                   matnlar (generatsiya), yangi alifbo
  data/                     hisob (sayt sessiyasi, qurilmalar), Oferta
  features/
    auth/                   kirish, xavfsiz bo'lmagan qurilma ekrani
    shop/                   do'kon — sayt WebView'da
    settings/               «Ilova va xavfsizlik»
    terms/ update/          Oferta, yangilanish oynalari
  widgets/                  umumiy vidjetlar
android/app/src/main/
  kotlin/uz/ketoshop/app/
    MainActivity.kt         kanal; joylashuv ruxsati; chek uchun fayl tanlash
    ShopWebView.kt          do'kon WebView'i va uning himoya qoidalari
    LocationFetcher.kt      telefon joylashuvi (fused / tarmoq / GPS)
    security/               DeviceKey (Keystore imzo), SecureBox (AES-GCM),
                            Integrity (root/hook/debug/imzo)
  assets/ks_telegram_shim.js  saytga Telegram o'rnini bosuvchi JS
  res/mipmap-*              ilova belgisi (tool/gen_icons.py yasaydi)
```

Sayt ilova ichida qanday ishlaydi:
1. Ilova kirgan sessiya uchun serverdan sayt sessiyasini oladi
   (`POST /app/v1/web-session`): Telegram initData formatida, 12 soatlik,
   sessiya bekor qilinsa darhol o'chadi.
2. Sayt `telegram.org/js/telegram-web-app.js` ni so'raydi — ilova unga
   `ks_telegram_shim.js` ni beradi: `Telegram.WebApp` (initData, orqaga
   tugmasi, tebranish, havolalar, `LocationManager`, yozish ruxsati).
3. Sayt `tma <initData>` bilan odatdagidek ishlaydi. Profilda faqat
   ilovada ko'rinadigan «Ilova va xavfsizlik» bandi bor.

Qoidalar:
- Barcha servislar `AppServices.create()` da bir marta yaratiladi.
- Native ekranlar dizayni `app/theme.dart` tokenlari orqali.
- Matnlar `l10n/uz.json`, `l10n/ru.json`; kirill va yangi alifbo
  serverning `translit.py` si bilan: `python mobile/tool/gen_l10n.py`.
- Ilova belgisi (ikona) va kirish ekranidagi logo do'kon logosidan
  (`assets/brand/ketoshop_logo.jpg`, @ketoshop_uz avatari) yasaladi:
  `python mobile/tool/gen_icons.py` (Pillow kerak). Sifatliroq logo
  (≥ 1024 px) bo'lsa, shu faylni almashtirib qayta ishga tushiring.
- Uchinchi tomon paketlari qo'shilmaydi.

## APK'siz o'zgaradigan hamma narsa

Egasi: "apkni yangilashga deyarli 99.99% zarurat bo'lmasin". Shuning uchun:

- **Do'kon** — saytning o'zi; saytdagi har o'zgarish darhol.
- **Ko'prik** (`webapp/app_shim.js`, `/app/v1/shim.js`) — saytga Telegram
  o'rnini bosuvchi qism serverdan keladi; APK ichidagisi faqat zaxira.
  Native imkoniyatlar (BRIDGE_VERSION 2): joylashuv, ulashish, nusxa olish,
  yuklab olish, kamera/fayl, bildirishnoma ruxsati, tebranish, havola,
  ilova sozlamalari. Sayt ulardan `window.KsApp` orqali foydalanadi.
- **Push** (`push.py`) — turlar, telefon bo'limlari, matn, rasm, bosilganda
  ochiladigan sahifa — hammasi serverda. Admin panel → «📲 Ilova».
- **Yangi APK** — admin panel → «📲 Ilova» → APK yuklash. O'rnatilgan
  ilovalar «Yangilash» bosilganda uni serverdan o'zi yuklab, SHA-256 ni
  tekshirib, o'rnatish oynasini ochadi (`app_release.py`).

Yangi APK faqat: domen o'zgarsa yoki telefonning mutlaqo yangi imkoniyati
(masalan NFC) kerak bo'lsa. Unda `tool\build_release.ps1 -Version X -Build N`
va APK'ni admin panelga yuklash kifoya.

## Firebase (push) sozlash

1. Firebase'da `uz.ketoshop.app` Android ilovasi → `google-services.json`
   → `mobile/android/app/google-services.json` (maxfiy emas; repoda).
2. Service accounts → private key (MAXFIY) → admin panel → «📲 Ilova» →
   «Firebase kaliti». Repoga hech qachon qo'yilmaydi.

## Yig'ish (Windows)

```powershell
# bir marta: JDK 17, Flutter, Android SDK -> D:\dev (checksum tekshiriladi)
powershell -ExecutionPolicy Bypass -File mobile\tool\setup_windows.ps1

# har safar yangi oynada
. mobile\tool\env.ps1
cd mobile
flutter test

# mijozlarga beriladigan APK (imzolangan, obfuskatsiyalangan)
powershell -ExecutionPolicy Bypass -File tool\build_release.ps1 -Version 1.1.0 -Build 2
```

Natija: `mobile/build/app/outputs/flutter-apk/` —
`app-arm64-v8a-release.apk` (zamonaviy telefonlar, eng kichik),
`app-armeabi-v7a-release.apk` (eski telefonlar), `app-release.apk`
(hammasiga mos, kattaroq). `build/symbols/` — obfuskatsiya xaritasi.

## Imzo kaliti

Release kaliti repoda yo'q: `D:\projects\Ketoshop-keys\`. **Zaxiralang** —
kalit yo'qolsa, o'rnatilgan ilovani yangilab bo'lmaydi. Kalit almashsa,
`android/gradle.properties` dagi `ketoshop.signingCertSha256` ni yangilang.

## Serverga ta'siri

- Jadvallar: `app_login_requests`, `app_sessions`.
- Yo'llar: `/app/v1/auth/{start,poll,refresh,logout}`, `/app/v1/web-session`,
  `/app/v1/sessions(+/revoke-others)`, `/app/v1/config`, `/app/v1/terms(+/accept)`.
- `/api/*`: `Authorization: Bearer` + imzo (native) yoki `tma` initData;
  ilova chiqargan initData (`ks_sid`) faqat do'kon API'sida va sessiya
  tirik bo'lsa qabul qilinadi — kuryer doskasi va admin uni rad etadi.
- Bot: `/start applogin_<id>` va tugmalari.
