/// Build-time settings. Override with --dart-define for a staging server,
/// e.g. `flutter run --dart-define=KS_HOST=staging.example.uz`; the host
/// must still present a Let's Encrypt certificate (core/net/tls.dart).
abstract final class AppConfig {
  static const String host = String.fromEnvironment('KS_HOST', defaultValue: 'keto.standart-eko.uz');
  static const String appVersion = String.fromEnvironment('KS_VERSION', defaultValue: '1.0.0');
  static const String supportUsername = 'keto_market';
  static const String botUsername = String.fromEnvironment('KS_BOT', defaultValue: 'ketoshopbot');

  static Uri get baseUri => Uri(scheme: 'https', host: host);

  static const Duration connectTimeout = Duration(seconds: 10);
  static const Duration requestTimeout = Duration(seconds: 25);
  static const Duration uploadTimeout = Duration(seconds: 90);

  /// Refresh the access token this long before it runs out.
  static const Duration refreshMargin = Duration(seconds: 45);
  static const Duration loginPollEvery = Duration(seconds: 2);

  static const int maxChequeBytes = 10 * 1024 * 1024;

  /// Ketoshop's own courier works inside this box (handlers/cart.py
  /// TASHKENT_BOUNDS); outside it the regional services are offered.
  static bool inTashkent(double lat, double lng) =>
      lat >= 41.10 && lat <= 41.50 && lng >= 69.04 && lng <= 69.51;

  /// handlers/cart.py SELF_DELIVERY_FEE / FREE_DELIVERY_FROM — shown before
  /// the order; the server prices the order itself.
  static const int selfDeliveryFee = 25000;
  static const int freeDeliveryFrom = 800000;
}
