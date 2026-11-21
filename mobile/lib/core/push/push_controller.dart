import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../config.dart';
import '../net/api_client.dart';
import '../platform/native_bridge.dart';

/// Push for this phone (server: push.py). The app knows no message kinds:
/// it tells the server its FCM token and whether notifications are on, and
/// opens the page a tapped push names. Everything else is decided on the
/// server, so new kinds of notifications need no new APK.
class PushController {
  PushController(this._native, this._api);

  final NativeBridge _native;
  final ApiClient _api;

  static const _key = 'push.registered.v1';
  static const _every = Duration(hours: 12);

  /// Pages asked for by tapped pushes while the app runs (ShopScreen opens them).
  final opens = StreamController<String>.broadcast();

  /// Update download progress (0..100), from the native side.
  final updateProgress = ValueNotifier<int>(0);

  void attach() {
    _native.onNativeEvent((method, args) async {
      switch (method) {
        case 'push.open':
          if (args is String) opens.add(args);
        case 'update.progress':
          if (args is int) updateProgress.value = args;
      }
      return null;
    });
  }

  /// Signed in and the shop is on screen: ask once (Android 13+), then tell
  /// the server the token. Never throws.
  Future<void> start() async {
    try {
      if (await _native.pushState() == 'ask') await _native.requestPushPermission();
      await sync(force: true);
    } on Object catch (e) {
      debugPrint('push start: $e');
    }
  }

  /// Re-sends the token when it or the on/off state changed, or every 12 h.
  Future<void> sync({bool force = false}) async {
    try {
      final state = await _native.pushState();
      if (state == 'unavailable') return;
      final token = await _native.pushToken();
      if (token == null || token.isEmpty) return;
      final enabled = state == 'on';
      final mark = jsonEncode({'t': token, 'e': enabled});
      final last = await _native.boxGet(_key);
      if (!force && last != null) {
        final saved = jsonDecode(last) as Map<String, Object?>;
        final at = DateTime.fromMillisecondsSinceEpoch((saved['at'] as num?)?.toInt() ?? 0);
        if (saved['m'] == mark && DateTime.now().difference(at) < _every) return;
      }
      await _api.post('/app/v1/push/register', json: {'token': token, 'enabled': enabled, 'build': AppConfig.appBuild});
      await _native.boxPut(_key, jsonEncode({'m': mark, 'at': DateTime.now().millisecondsSinceEpoch}));
    } on Object catch (e) {
      debugPrint('push sync: $e');
    }
  }

  /// Logout: this phone stops getting the account's pushes.
  Future<void> forget() async {
    try {
      await _native.boxPut(_key, null);
      await _native.deletePushToken();
    } on Object {
      // best effort
    }
  }
}
