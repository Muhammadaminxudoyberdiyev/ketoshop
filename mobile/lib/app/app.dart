import 'dart:async';

import 'package:flutter/material.dart';

import '../core/auth/auth_controller.dart';
import '../data/account_repository.dart';
import '../features/auth/login_screen.dart';
import '../features/auth/unsafe_screen.dart';
import '../features/gate/gate_screen.dart';
import '../features/shell/home_shell.dart';
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
  void _onAuthChanged() {
    _navigator.currentState?.popUntil((route) => route.isFirst);
    if (_auth.status != AuthStatus.signedIn) {
      final services = context.services;
      services.cart.reset();
      services.catalog.invalidate();
      services.gate.value = null;
    }
  }

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

/// Which world the user is in: checking, refused, signed out, or the shop.
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
  late final Future<void> _ready = _prepare();

  Future<void> _prepare() async {
    final s = context.services;
    try {
      await s.account.syncLanguage();
    } on Object {
      // the saved language keeps working offline
    }
    try {
      final gate = await s.account.gate();
      s.gate.value = gate.ok ? null : gate;
      if (gate.ok) s.cart.refresh().ignore();
    } on Object {
      // network trouble shows up on the first screen that loads data
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<void>(
        future: _ready,
        builder: (context, snap) => snap.connectionState != ConnectionState.done
            ? const Scaffold(body: Center(child: CircularProgressIndicator()))
            : ValueListenableBuilder<GateState?>(
                valueListenable: context.services.gate,
                builder: (context, gate, _) => gate != null && !gate.ok ? GateScreen(gate: gate) : const HomeShell(),
              ),
      );
}
