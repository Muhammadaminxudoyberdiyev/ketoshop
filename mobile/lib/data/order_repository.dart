import '../core/config.dart';
import '../core/l10n/locale_controller.dart';
import '../core/net/api_client.dart';
import '../core/platform/native_bridge.dart';
import 'models.dart';

/// Checkout, cheques and the buyer's orders. Prices, fees, Keto and stock
/// are always decided by the server; the app only sends choices.
class OrderRepository {
  OrderRepository(this._api, this._locale);

  final ApiClient _api;
  final LocaleController _locale;

  Future<List<Order>> orders() async {
    final j = await _api.get('/api/orders');
    return ((j as List?) ?? const []).whereType<Json>().map((o) => Order.fromJson(o, _locale.display)).toList();
  }

  Future<void> cancel(int orderId) => _api.post('/api/orders/$orderId/cancel');

  Future<String> knownPhone() async {
    try {
      final j = (await _api.get('/api/checkout/phone'))! as Json;
      return (j['phone'] as String?) ?? '';
    } on ApiException {
      return '';
    }
  }

  Future<PickupConfig> pickupConfig() async =>
      PickupConfig.fromJson((await _api.get('/api/pickup-config'))! as Json, _locale.display);

  Future<KetoStatus> ketoStatus() async => KetoStatus.fromJson((await _api.get('/api/keto/status'))! as Json);

  Future<UzpostQuote?> uzpostQuote(GeoPoint p) async {
    try {
      final j = (await _api.get('/api/uzpost/quote', query: {'lat': '${p.lat}', 'lng': '${p.lng}'}))! as Json;
      return UzpostQuote.fromJson(j, _locale.display);
    } on ApiException {
      return null;
    }
  }

  Future<String> addressOf(GeoPoint p) async {
    try {
      final j = (await _api.get('/api/geocode', query: {'lat': '${p.lat}', 'lng': '${p.lng}'}))! as Json;
      return _locale.display((j['address'] as String?) ?? '');
    } on Object {
      return '';
    }
  }

  Future<CheckoutResult> checkout(CheckoutRequest request) async =>
      CheckoutResult.fromJson((await _api.post('/api/checkout', json: request.toJson()))! as Json);

  /// The cheque for the online checkout just made; the order is created by
  /// this upload. Returns the new order's id.
  Future<int> sendPendingCheque(PickedFile file) async {
    final j = (await _upload('/api/checkout/cheque', file))! as Json;
    return (j['order_id'] as num).toInt();
  }

  Future<void> sendOrderCheque(int orderId, PickedFile file) => _upload('/api/orders/$orderId/cheque', file);

  /// "I'll pay from the chat": the bot posts the card details there.
  Future<void> payInChat() => _api.post('/api/checkout/pay-in-chat');

  Future<Object?> _upload(String path, PickedFile file) => _api.post(
        path,
        raw: file.bytes,
        contentType: file.mime,
        headers: {'X-File-Name': file.name},
        timeout: AppConfig.uploadTimeout,
      );
}
