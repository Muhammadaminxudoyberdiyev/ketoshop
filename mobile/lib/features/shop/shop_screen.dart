import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/scope.dart';
import '../../core/config.dart';
import '../../widgets/common.dart';
import '../settings/settings_screen.dart';
import '../terms/terms_screen.dart';
import '../update/update_views.dart';

/// The shop: the site itself (webapp/index.html — catalog, games, AI
/// helper, recipes, cart, checkout with the map) in a native WebView
/// (ShopWebView.kt). Whatever is added to the site shows here at once.
///
/// It signs in with initData minted for this app session; a fresh one is
/// fetched when the app comes back after long enough that it could expire.
class ShopScreen extends StatefulWidget {
  const ShopScreen({super.key});

  @override
  State<ShopScreen> createState() => _ShopScreenState();
}

class _ShopScreenState extends State<ShopScreen> with WidgetsBindingObserver {
  static const _remintAfter = Duration(hours: 6);

  String? _initData;
  DateTime _mintedAt = DateTime.fromMillisecondsSinceEpoch(0);
  Object? _sessionError;
  MethodChannel? _view;
  int _generation = 0;
  bool _loading = true;
  int _progress = 0;
  bool _offline = false;
  Color? _header;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_mint());
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      await askToAcceptNewTerms(context);
      if (mounted) unawaited(offerUpdate(context));
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _view?.setMethodCallHandler(null);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && DateTime.now().difference(_mintedAt) > _remintAfter) {
      unawaited(_mint(reload: true));
    }
  }

  Future<void> _mint({bool reload = false}) async {
    try {
      final initData = await context.services.account.shopSession();
      if (!mounted) return;
      _mintedAt = DateTime.now();
      if (reload && _view != null) {
        await _view!.invokeMethod<void>('reload', {'initData': initData});
        _initData = initData;
      } else {
        setState(() {
          _initData = initData;
          _sessionError = null;
        });
      }
    } on Object catch (e) {
      if (!mounted) return;
      setState(() => _sessionError = e);
    }
  }

  void _attach(int id) {
    _view = MethodChannel('uz.ketoshop/webview_$id')..setMethodCallHandler(_onEvent);
  }

  Future<Object?> _onEvent(MethodCall call) async {
    if (!mounted) return null;
    switch (call.method) {
      case 'loading':
        setState(() {
          _loading = call.arguments == true;
          if (_loading) _offline = false;
        });
      case 'progress':
        setState(() => _progress = (call.arguments as int?) ?? 0);
      case 'error':
        setState(() => _offline = true);
      case 'crashed':
        setState(() => _generation++);
      case 'header_color':
        setState(() => _header = _parseColor(call.arguments as String?));
      case 'settings':
        await Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const SettingsScreen()));
      case 'back_visible':
        break; // the back key asks the page itself (see _back)
    }
    return null;
  }

  static Color? _parseColor(String? css) {
    final m = RegExp(r'^#([0-9a-fA-F]{6})$').firstMatch(css ?? '');
    return m == null ? null : Color(0xFF000000 | int.parse(m[1]!, radix: 16));
  }

  /// Android back: the page's own back button, then its history, then out.
  Future<void> _back() async {
    final handled = await _view?.invokeMethod<bool>('back') ?? false;
    if (!handled) await SystemNavigator.pop();
  }

  Future<void> _retry() async {
    setState(() => _offline = false);
    if (_initData == null) return _mint();
    await _view?.invokeMethod<void>('reload', {'initData': _initData});
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final header = _header ?? scheme.surface;
    final darkHeader = ThemeData.estimateBrightnessForColor(header) == Brightness.dark;
    final initData = _initData;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) unawaited(_back());
      },
      child: AnnotatedRegion<SystemUiOverlayStyle>(
        value: (darkHeader ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark)
            .copyWith(statusBarColor: Colors.transparent),
        child: Scaffold(
          backgroundColor: header,
          body: SafeArea(
            child: initData == null
                ? (_sessionError != null
                    ? ErrorPanel(message: errorText(context, _sessionError!), onRetry: _retry)
                    : const Center(child: CircularProgressIndicator()))
                : Stack(children: [
                    Positioned.fill(
                      child: AndroidView(
                        key: ValueKey(_generation),
                        viewType: 'uz.ketoshop/webview',
                        layoutDirection: TextDirection.ltr,
                        creationParams: {
                          'url': '${AppConfig.baseUri}/?app=android',
                          'host': AppConfig.host,
                          'bot': AppConfig.botUsername,
                          'initData': initData,
                        },
                        creationParamsCodec: const StandardMessageCodec(),
                        onPlatformViewCreated: _attach,
                      ),
                    ),
                    if (_loading)
                      Positioned(
                        top: 0,
                        left: 0,
                        right: 0,
                        child: LinearProgressIndicator(value: _progress > 0 && _progress < 100 ? _progress / 100 : null),
                      ),
                    if (_offline)
                      Positioned.fill(
                        child: ColoredBox(
                          color: scheme.surface,
                          child: ErrorPanel(message: context.t('error_network'), onRetry: _retry),
                        ),
                      ),
                  ]),
          ),
        ),
      ),
    );
  }
}
