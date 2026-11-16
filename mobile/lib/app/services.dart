import 'dart:async';

import 'package:flutter/foundation.dart';

import '../core/auth/auth_controller.dart';
import '../core/auth/session_store.dart';
import '../core/images/net_image.dart';
import '../core/l10n/locale_controller.dart';
import '../core/net/api_client.dart';
import '../core/net/signing.dart';
import '../core/net/tls.dart';
import '../core/platform/native_bridge.dart';
import '../data/account_repository.dart';
import '../data/cart_controller.dart';
import '../data/catalog_repository.dart';
import '../data/order_repository.dart';

/// FLAG_SECURE is on while any sensitive screen is visible: the tab the
/// shell shows, plus every pushed screen that asked for it.
class SecureScreenController {
  SecureScreenController(this._native);

  final NativeBridge _native;
  int _routes = 0;
  bool _tab = false;
  bool? _applied;

  void setTab(bool secure) {
    _tab = secure;
    _apply();
  }

  void push() {
    _routes++;
    _apply();
  }

  void pop() {
    if (_routes > 0) _routes--;
    _apply();
  }

  void _apply() {
    final on = _tab || _routes > 0;
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
    required this.images,
    required this.catalog,
    required this.cart,
    required this.orders,
    required this.account,
    required this.secure,
  });

  final NativeBridge native;
  final LocaleController locale;
  final AuthController auth;
  final ApiClient api;
  final ImageStore images;
  final CatalogRepository catalog;
  final CartController cart;
  final OrderRepository orders;
  final AccountRepository account;
  final SecureScreenController secure;

  /// Set when the server answers "join the channel / start the bot first".
  final ValueNotifier<GateState?> gate = ValueNotifier(null);

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
      images: ImageStore(api, await native.cacheDir()),
      catalog: CatalogRepository(api, locale),
      cart: CartController(api, locale),
      orders: OrderRepository(api, locale),
      account: AccountRepository(api, locale),
      secure: SecureScreenController(native),
    );
    // Server-made text is localized by the server: a new language means
    // fresh catalog and cart.
    locale.addListener(() {
      services.catalog.invalidate();
      if (services.auth.status == AuthStatus.signedIn) services.cart.refresh().ignore();
    });
    return services;
  }
}
