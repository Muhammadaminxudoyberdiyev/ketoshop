# Ketoshop Android — xavfsizlik modeli

Bu hujjat ilova nimadan himoyalanganini, qanday himoyalanganini va nimalar
hali qilinmaganini aytadi. Kod: `lib/core/`, `android/app/src/main/kotlin/`,
serverda `app_auth.py`.

## Asosiy tamoyillar

1. **Server hech qachon ilovaga ishonmaydi.** Narx, chegirma, yetkazish
   haqi, Keto, ombor qoldig'i, buyurtma egasi — hammasini server o'zi
   hisoblaydi va tekshiradi. Ilova faqat tanlovni yuboradi. Ilovani butunlay
   buzib, o'zgartirgan odam ham boshqaning buyurtmasini ko'ra olmaydi yoki
   narxni o'zgartira olmaydi.
2. **Kalit telefondan chiqmaydi.** Har bir so'rov Android Keystore ichida
   (TEE) yaratilgan P-256 kalit bilan imzolanadi. Serverda faqat ochiq kalit
   saqlanadi. Token o'g'irlansa ham (log, zaxira nusxa, tarmoq), boshqa
   qurilmada ishlamaydi.
3. **Uchinchi tomon kodi yo'q.** Ilovada birorta tashqi Dart paketi yoki
   Android plagini yo'q — faqat Flutter SDK va o'zimizning kod. Ta'minot
   zanjiri hujumi uchun eshik yo'q.

## Tahdidlar va to'siqlar

| Tahdid | To'siq | Qayerda |
|---|---|---|
| Tarmoqda tinglash / almashtirish (MITM), soxta Wi-Fi | Faqat HTTPS; faqat Let's Encrypt ildizlari (ISRG Root X1/X2) ishonchli — telefon do'koni va foydalanuvchi o'rnatgan sertifikatlar emas; proxy e'tiborga olinmaydi; redirect kuzatilmaydi | `lib/core/net/tls.dart`, `network_security_config.xml` |
| Telefonga "xavfsizlik sertifikati" o'rnatishga ko'ndirish | Yuqoridagi pinning: o'rnatilgan CA bilan ham trafik ochilmaydi | o'sha |
| Token o'g'irlash | Har so'rov qurilma kaliti bilan imzolanadi; tokenlar serverda faqat SHA-256 xeshi bilan saqlanadi; access 15 daqiqa | `app_auth.py`, `DeviceKey.kt` |
| So'rovni qayta yuborish (replay) | Imzoda vaqt (±2 daqiqa) va bir martalik nonce; server nonce'ni eslab qoladi | `app_auth.check_signature` |
| So'rovni yo'lda o'zgartirish | Imzo method, yo'l, query, vaqt, nonce va body SHA-256 ni qamraydi | o'sha |
| Refresh token nusxasi | Har ishlatilganda almashadi; eski token 60 soniyadan keyin kelsa — sessiya o'chiriladi | `handle_refresh` |
| Kirish havolasini boshqaga yuborib, uning hisobini olish (fishing) | Raqam moslash: ilova 2 xonali raqam ko'rsatadi, botda 3 tadan to'g'risini bosish kerak; noto'g'ri bosish so'rovni o'ldiradi; "Men emasman" tugmasi; 5 daqiqa muddat; so'rovni faqat uni boshlagan qurilma (kalit egasi) yig'ib oladi | `app_auth.py` (bot qismi) |
| Hisobga bildirmasdan kirish | Har yangi qurilma kirganda botda xabar + «🚫 Chiqarib yuborish» tugmasi; ilovada qurilmalar ro'yxati va «Boshqa qurilmalardan chiqish» | `_notify_new_device`, Profil |
| Ko'p sessiya to'plash | Bir odamga ko'pi bilan 10 ta faol sessiya, eskisi o'chadi; sessiya umri ko'pi bilan 90 kun | `_issue` |
| Kirish so'rovlari bilan bazani to'ldirish | IP bo'yicha va umumiy tezlik chegarasi; eski so'rovlar o'chiriladi | `RateLimit` |
| Boshqa xaridorning savatini o'chirish (IDOR) | `/api/cart/remove` endi savat qatori egasini tekshiradi (avval tekshirmasdi — Mini App uchun ham tuzatildi) | `webapp_server.api_cart_remove` |
| Telefondagi ma'lumotni o'g'irlash | Tokenlar AES-256-GCM bilan, kaliti Keystore'da; zaxira nusxa va telefondan-telefonga ko'chirish o'chirilgan | `SecureBox.kt`, `data_extraction_rules.xml` |
| Ekran rasmi / yozib olish, "so'nggi ilovalar" oynasi | Login, checkout, chek, buyurtmalar va profilda FLAG_SECURE | `SecureScreenController` |
| Ilova ustidan yolg'on oyna (tapjacking) | Ustida boshqa ilova chizganda bosishlar qabul qilinmaydi | `MainActivity.onCreate` |
| Boshqa ilova bizning Activity'ni o'g'irlashi (task hijacking) | `taskAffinity=""`, faqat launcher activity eksport qilingan | `AndroidManifest.xml` |
| Zararli havola ochish | Faqat `https://` va `tg://`; `intent:`, `file:`, `content:`, `javascript:` yo'q | `MainActivity.openUrl` |
| Chek o'rnida zararli fayl | Fayl turi birinchi baytlardan aniqlanadi (JPEG/PNG/WEBP/HEIC/PDF), ≤10 MB; serverda ham 10 MB chegarasi | `MainActivity.readCheque`, `app_auth.read_body` |
| APK'ni ochib, o'zgartirib qayta tarqatish | R8 obfuskatsiya + Dart `--obfuscate`; imzo sertifikati tekshiriladi; Frida/Xposed/debugger topilsa ilova ishlamaydi; holat serverga yuboriladi (`APP_REQUIRE_CLEAN=1` bo'lsa server rad etadi) | `Integrity.kt`, `AuthController.bootstrap` |
| Logga sir tushishi | Release'da `debugPrint` va `android.util.Log` o'chirilgan; native xatolarda xabar matni qaytarilmaydi | `main.dart`, `proguard-rules.pro` |

## Kirish oqimi

```
Ilova                         Server                       Bot (Telegram)
  | Keystore: P-256 kalit
  |-- POST /app/v1/auth/start (ochiq kalit, imzolangan) -->|
  |<-- request_id, bot havolasi, raqam (masalan 47) -------|
  |-- t.me/ketoshopbot?start=applogin_<id> ------------------------------>|
  |                                                         |<-- 3 ta raqam
  |                                       xaridor 47 ni bosadi ---------->|
  |                                                     approved (user_id)
  |-- POST /app/v1/auth/poll (imzolangan) ----------------->|
  |<-- access (15 daq) + refresh (30 kun) -----------------|
  |                                      botda: "yangi qurilmadan kirildi"
```

## Imzo formati

```
KS1\nMETHOD\n/path?query\ntimestamp_ms\nnonce\nbase64url(sha256(body))
```
Sarlavhalar: `X-KS-Timestamp`, `X-KS-Nonce`, `X-KS-Signature` (DER, base64url).
Ikkala tomon bir xil test vektori bilan qotirilgan:
`tests/test_app_auth.py::test_canonical_matches_the_app` va
`mobile/test/signing_test.dart`.

## Sozlamalar (server, env)

- `APP_REQUIRE_CLEAN=1` — ilova o'zini hook/debug/emulyator/qayta imzolangan
  deb ko'rsatsa, kirish va refresh rad etiladi. Standart: o'chiq (faqat log).
  Root qilingan telefon bloklanmaydi.
- `APP_TRUST_PROXY=1` — server o'z reverse-proxy'si orqasida bo'lsa,
  IP chegarasi `X-Forwarded-For` ning oxirgi qiymatini oladi.

## Hali qilinmagan (keyingi bosqich)

- **Play Integrity / Key Attestation.** Ilova Google Play'ga chiqqach,
  serverda Play Integrity tokenini tekshirish — soxta yoki o'zgartirilgan
  APK'ni kriptografik jihatdan rad etishning yagona ishonchli yo'li.
  Hozirgi `Integrity.kt` tekshiruvlari faqat narxni oshiradi, isbot emas.
- **Sertifikat almashsa.** Server Let's Encrypt'dan boshqa CA'ga o'tsa,
  avval yangi ildizni `tls.dart` ga qo'shib ilovani yangilash kerak, keyin
  sertifikatni almashtirish. Aks holda ilova ulana olmaydi.
- **Imzo kaliti.** Release kaliti (`*.jks`) repoda yo'q va bo'lmasligi
  kerak. U yo'qolsa, ilovani yangilab bo'lmaydi — zaxira nusxasini xavfsiz
  joyda saqlang.
