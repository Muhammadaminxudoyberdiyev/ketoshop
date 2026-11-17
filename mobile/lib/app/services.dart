import 'dart:async';

import '../core/auth/auth_controller.dart';
import '../core/auth/session_store.dart';
import '../core/l10n/locale_controller.dart';
import '../core/net/api_client.dart';
import '../core/net/signing.dart';
import '../core/net/tls.dart';
import '../core/platform/native_bridge.dart';
import '../core/remote/remote_config.dart';
import '../data/account_repository.dart';
import '../data/terms_repository.dart';

/// FLAG_SECURE is on while any screen that asked for it is open (login,
/// app settings). The shop page itself can be screenshotted, as in Telegram.
class SecureScreenController {
  SecureScreenController(this._native);

  final NativeBridge _native;
  int _routes = 0;
  bool? _applied;

  void push() {
    _routes++;
    _apply();
  }

  void pop() {
    if (_routes > 0) _routes--;
    _apply();
  }

  void _apply() {
    final on = _routes > 0;
    if (on == _applied) return;
    _applied = on;
    unawaited(_native.setSecureScreen(on));
  }
}

/// The composition root: every long-lived object is made here, once, and
/// handed down through AppScope. Nothing else constructs services.
class AppServices {
  AppServices._({
    required this.native,
    required this.locale,
    required this.auth,
    required this.api,
    required this.account,
    required this.secure,
    required this.remote,
    required this.terms,
  });

  final NativeBridge native;
  final LocaleController locale;
  final AuthController auth;
  final ApiClient api;
  final AccountRepository account;
  final SecureScreenController secure;

  /// The app's version and the Oferta edition, decided by the server.
  final RemoteConfigController remote;

  /// «Oferta shartlari»: the text and which edition this phone accepted.
  final TermsRepository terms;

  static Future<AppServices> create() async {
    final native = NativeBridge();
    final sessions = SessionStore(native);
    final api = ApiClient(http: createPinnedHttpClient(), native: native, sessions: sessions, clock: ServerClock());
    final locale = LocaleController(native);
    await locale.load();
    final services = AppServices._(
      native: native,
      locale: locale,
      auth: AuthController(native: native, sessions: sessions, api: api),
      api: api,
      account: AccountRepository(api, locale),
      secure: SecureScreenController(native),
      remote: RemoteConfigController(api, native, locale),
      terms: TermsRepository(api, native, locale),
    );
    services.auth.onTermsAccepted = services.terms.rememberAccepted;
    await services.remote.loadCached();
    unawaited(services.remote.refresh(force: true));
    locale.addListener(() => unawaited(services.remote.refresh(force: true)));
    return services;
  }
}
