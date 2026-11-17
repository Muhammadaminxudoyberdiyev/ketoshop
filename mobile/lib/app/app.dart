import 'dart:async';

import 'package:flutter/material.dart';

import '../core/auth/auth_controller.dart';
import '../features/auth/login_screen.dart';
import '../features/auth/unsafe_screen.dart';
import '../features/shop/shop_screen.dart';
import '../features/update/update_views.dart';
import 'scope.dart';
import 'theme.dart';

class KetoshopApp extends StatefulWidget {
  const KetoshopApp({super.key});

  @override
  State<KetoshopApp> createState() => _KetoshopAppState();
}

class _KetoshopAppState extends State<KetoshopApp> with WidgetsBindingObserver {
  final _navigator = GlobalKey<NavigatorState>();
  late final _auth = context.services.auth;
  late final _remote = context.services.remote;

  @override
  void initState() {
    super.initState();
    _auth.addListener(_onAuthChanged);
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _auth.removeListener(_onAuthChanged);
    super.dispose();
  }

  /// Back in the app: pick up what the server changed (at most every 30 min).
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) unawaited(_remote.refresh());
  }

  /// Signing in or out drops every screen pushed for the previous state.
  void _onAuthChanged() => _navigator.currentState?.popUntil((route) => route.isFirst);

  @override
  Widget build(BuildContext context) => MaterialApp(
        navigatorKey: _navigator,
        title: 'Ketoshop',
        debugShowCheckedModeBanner: false,
        theme: buildTheme(Brightness.light),
        darkTheme: buildTheme(Brightness.dark),
        home: const _RootView(),
      );
}

/// Which world the user is in: checking, refused, must update, signed out,
/// or the shop.
class _RootView extends StatelessWidget {
  const _RootView();

  @override
  Widget build(BuildContext context) {
    final auth = context.services.auth;
    final remote = context.services.remote;
    return ListenableBuilder(
      listenable: Listenable.merge([auth, remote]),
      builder: (context, _) => AnimatedSwitcher(
        duration: Tokens.fast,
        child: remote.config.mustUpdate && auth.status != AuthStatus.unsafeDevice
            ? UpdateRequiredScreen(key: const ValueKey('update'), config: remote.config)
            : switch (auth.status) {
                AuthStatus.unknown => const Scaffold(key: ValueKey('splash'), body: Center(child: CircularProgressIndicator())),
                AuthStatus.unsafeDevice => const UnsafeScreen(key: ValueKey('unsafe')),
                AuthStatus.signedOut => const LoginScreen(key: ValueKey('login')),
                AuthStatus.signedIn => const _SignedIn(key: ValueKey('shop')),
              },
      ),
    );
  }
}

class _SignedIn extends StatefulWidget {
  const _SignedIn({super.key});

  @override
  State<_SignedIn> createState() => _SignedInState();
}

class _SignedInState extends State<_SignedIn> {
  @override
  void initState() {
    super.initState();
    // The app's own screens speak the language the bot and the shop use.
    unawaited(context.services.account.syncLanguage().catchError((Object _) {}));
  }

  @override
  Widget build(BuildContext context) => const ShopScreen();
}
