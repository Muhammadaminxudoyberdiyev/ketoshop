import '../core/l10n/locale_controller.dart';
import '../core/net/api_client.dart';
import 'models.dart';

class GateState {
  const GateState({required this.ok, required this.subscribed, required this.started, required this.channel, required this.bot});
  final bool ok;
  final bool subscribed;
  final bool started;
  final String channel;
  final String bot;

  factory GateState.fromJson(Json j) => GateState(
        ok: j['ok'] == true,
        subscribed: j['subscribed'] != false,
        started: j['started'] != false,
        channel: (j['channel'] as String?) ?? '',
        bot: (j['bot'] as String?) ?? '',
      );
}

class AccountRepository {
  AccountRepository(this._api, this._locale);

  final ApiClient _api;
  final LocaleController _locale;

  /// Channel member + bot started? The server's own gate (site_gate).
  Future<GateState> gate() async => GateState.fromJson((await _api.get('/api/bot-access'))! as Json);

  /// Takes the language saved on the server (the bot's users.language).
  Future<void> syncLanguage() async {
    final j = (await _api.get('/api/lang'))! as Json;
    _locale.applyServer((j['lang'] as String?) ?? _locale.lang, j['new_alphabet'] != false);
  }

  Future<void> setLanguage(String lang) async {
    await _api.post('/api/lang', json: {'lang': lang});
    await _locale.setLocal(lang);
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
