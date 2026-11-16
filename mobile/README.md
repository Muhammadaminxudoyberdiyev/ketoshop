# Ketoshop — Android ilovasi (xaridorlar uchun)

Mini App'dagi do'konning o'zi, native ilova sifatida: katalog, qidiruv,
savat, buyurtma (kuryer, Yandex Taxi, UzPost, BTS, EMU, olib ketish), karta
cheki, buyurtmalar tarixi, Keto, uch til (uz / ўз / ru) va yangi alifbo.
Server — o'sha `webapp_server.py` (`/api/*`); ilova uchun qo'shilgani faqat
kirish va so'rov imzosi (`app_auth.py`). Xavfsizlik: [SECURITY.md](SECURITY.md).

## Arxitektura

```
lib/
  main.dart                 ishga tushirish
  app/                      kompozitsiya ildizi (services.dart), mavzu, AppScope
  core/
    config.dart             host, vaqtlar, Toshkent chegarasi
    net/                    pinned TLS, imzo, ApiClient (refresh, qayta urinish)
    auth/                   sessiya (Keystore'da shifrlangan), kirish oqimi
    platform/               Kotlin bilan yagona kanal (NativeBridge)
    l10n/                   matnlar (generatsiya), yangi alifbo
    images/                 rasm keshi (pinned klient orqali)
  data/                     modellar va repozitoriylar (API ↔ ilova)
  features/                 ekranlar: auth, gate, catalog, search, cart,
                            checkout, orders, profile, shell
  widgets/                  umumiy vidjetlar
android/app/src/main/kotlin/uz/ketoshop/app/
  MainActivity.kt           kanal: kalit, quti, joylashuv, fayl, havola
  security/                 DeviceKey (Keystore imzo), SecureBox (AES-GCM),
                            Integrity (root/hook/debug/imzo)
```

Qoidalar:
- Ekran → repozitoriy → `ApiClient`. Ekran HTTP'ni bilmaydi.
- Barcha servislar `AppServices.create()` da bir marta yaratiladi.
- Dizayn faqat `app/theme.dart` dagi tokenlar orqali — qayta dizaynda
  ekran mantiqiga tegmasdan o'zgartiriladi.
- Matnlar `l10n/uz.json` va `l10n/ru.json` da; kirill va yangi alifbo
  varianti serverning `translit.py` si bilan generatsiya qilinadi:
  `python mobile/tool/gen_l10n.py`.
- Uchinchi tomon paketlari qo'shilmaydi (sababi SECURITY.md da).

## Yig'ish (Windows)

```powershell
# bir marta: JDK 17, Flutter, Android SDK -> D:\dev (checksum tekshiriladi)
powershell -ExecutionPolicy Bypass -File mobile\tool\setup_windows.ps1

# har safar yangi oynada
. mobile\tool\env.ps1
cd mobile
flutter test
flutter run                      # ulangan telefon / emulyator

# mijozlarga beriladigan APK (imzolangan, obfuskatsiyalangan)
powershell -ExecutionPolicy Bypass -File tool\build_release.ps1 -Version 1.0.0 -Build 1
```

Natija: `mobile/build/app/outputs/flutter-apk/` —
`app-arm64-v8a-release.apk` (zamonaviy telefonlar, eng kichik),
`app-armeabi-v7a-release.apk` (eski telefonlar), `app-release.apk`
(hammasiga mos, kattaroq). `build/symbols/` — obfuskatsiya xaritasi,
xato hisobotlarini o'qish uchun; har versiya uchun saqlab qo'ying.

## Imzo kaliti

Release kaliti repoda yo'q: `D:\projects\Ketoshop-keys\` (`ketoshop-release.jks`
va parollar `key.properties` da). **Ikkalasini xavfsiz joyga zaxiralang** —
kalit yo'qolsa, o'rnatilgan ilovani yangilab bo'lmaydi. Kalit almashsa,
`android/gradle.properties` dagi `ketoshop.signingCertSha256` ni ham
yangilang (ilova o'z imzosini shu bilan tekshiradi).

## Serverga ta'siri

- Yangi jadvallar: `app_login_requests`, `app_sessions` (ishga tushganda
  `CREATE TABLE IF NOT EXISTS`).
- Yangi yo'llar: `/app/v1/auth/{start,poll,refresh,logout}`,
  `/app/v1/sessions`, `/app/v1/sessions/revoke-others`.
- `/api/*` endi `Authorization: Bearer` + imzoni ham qabul qiladi;
  Mini App'ning `tma` yo'li o'zgarmagan.
- Bot: `/start applogin_<id>` va uning tugmalari (kanal gate'idan ozod).
- Yangi bog'liqlik: `cryptography` (ECDSA tekshiruvi).
