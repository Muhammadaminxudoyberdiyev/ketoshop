import '../core/l10n/locale_controller.dart';
import '../core/net/api_client.dart';
import 'models.dart';

/// The signed-in buyer's own account: the shop page's session, language,
/// and the devices logged in.
class AccountRepository {
  AccountRepository(this._api, this._locale);

  final ApiClient _api;
  final LocaleController _locale;

  /// Telegram-format initData minted for this app session (app_auth.py) —
  /// what the shop page inside the app authenticates with. Short-lived and
  /// ended by logout or «Chiqarib yuborish».
  Future<String> shopSession() async {
    final j = (await _api.post('/app/v1/web-session'))! as Json;
    final value = j['init_data'];
    if (value is! String || value.isEmpty) throw const ApiException(500, 'bad_web_session');
    return value;
  }

  /// Takes the language saved on the server (the bot's users.language), so
  /// the app's own screens speak the same one as the bot and the shop.
  Future<void> syncLanguage() async {
    final j = (await _api.get('/api/lang'))! as Json;
    _locale.applyServer((j['lang'] as String?) ?? _locale.lang, j['new_alphabet'] != false);
  }

  Future<List<DeviceSession>> sessions() async {
    final j = (await _api.get('/app/v1/sessions'))! as Json;
    return ((j['sessions'] as List?) ?? const []).whereType<Json>().map(DeviceSession.fromJson).toList();
  }

  Future<int> logoutOtherDevices() async {
    final j = (await _api.post('/app/v1/sessions/revoke-others'))! as Json;
    return (j['revoked'] as num?)?.toInt() ?? 0;
  }
}
