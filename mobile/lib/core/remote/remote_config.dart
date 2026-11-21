import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../config.dart';
import '../l10n/locale_controller.dart';
import '../net/api_client.dart';
import '../platform/native_bridge.dart';

typedef Json = Map<String, Object?>;

/// What the server decides about the app's own native part (app_config.py).
/// The shop is the site itself, so everything in it already changes without
/// a new APK; this is only about the app: its version and the Oferta edition.
class RemoteConfig {
  const RemoteConfig({
    required this.latestVersion,
    required this.latestBuild,
    required this.minBuild,
    required this.updateUrl,
    required this.updateNotes,
    this.termsVersion = '',
    this.apkSha256 = '',
    this.apkSize = 0,
    this.shopPath = '/',
    this.shimPath = '/app/v1/shim.js',
  });

  /// Built-in values: the app works offline and before the first answer.
  static const fallback = RemoteConfig(
    latestVersion: AppConfig.appVersion,
    latestBuild: AppConfig.appBuild,
    minBuild: 0,
    updateUrl: '',
    updateNotes: '',
  );

  final String latestVersion;
  final int latestBuild;
  final int minBuild;
  final String updateUrl;
  final String updateNotes;

  /// The Oferta edition in force (app_terms.VERSION).
  final String termsVersion;

  /// Set when the new APK sits on our server (app_release.py): the app
  /// downloads it itself, checks this hash and opens the installer.
  final String apkSha256;
  final int apkSize;
  bool get selfUpdate => apkSha256.length == 64 && updateUrl.startsWith('https://');

  /// Where the shop opens, and the bridge script's path — both on our host.
  final String shopPath;
  final String shimPath;

  bool get mustUpdate => AppConfig.appBuild < minBuild && updateUrl.isNotEmpty;
  bool get updateAvailable => AppConfig.appBuild < latestBuild && updateUrl.isNotEmpty;

  factory RemoteConfig.fromJson(Json j) => RemoteConfig(
        latestVersion: (j['latest_version'] as String?) ?? AppConfig.appVersion,
        latestBuild: (j['latest_build'] as num?)?.toInt() ?? AppConfig.appBuild,
        minBuild: (j['min_build'] as num?)?.toInt() ?? 0,
        updateUrl: _safeUrl(j['update_url']),
        updateNotes: (j['update_notes'] as String?) ?? '',
        termsVersion: (j['terms_version'] as String?) ?? '',
        apkSha256: RegExp(r'^[0-9a-f]{64}$').hasMatch((j['apk_sha256'] as String?) ?? '') ? j['apk_sha256']! as String : '',
        apkSize: (j['apk_size'] as num?)?.toInt() ?? 0,
        shopPath: _path(j['shop_path'], '/'),
        shimPath: _path(j['shim_path'], '/app/v1/shim.js'),
      );

  /// A path on our own host ("/", "/?x=1") — never "//other.host".
  static String _path(Object? v, String fallback) =>
      v is String && v.startsWith('/') && !v.startsWith('//') && !v.contains(RegExp(r'[\s\\]')) ? v : fallback;

  static String _safeUrl(Object? v) {
    final uri = v is String ? Uri.tryParse(v) : null;
    return uri != null && (uri.scheme == 'https' || uri.scheme == 'tg') ? v! as String : '';
  }
}

/// Reads /app/v1/config on start, on return to the app (at most every 30
/// min) and when the language changes; keeps the last answer encrypted on
/// the phone so the app decides instantly, offline too.
class RemoteConfigController extends ChangeNotifier {
  RemoteConfigController(this._api, this._native, this._locale);

  final ApiClient _api;
  final NativeBridge _native;
  final LocaleController _locale;

  static const _key = 'config.v1';
  static const _every = Duration(minutes: 30);

  RemoteConfig _config = RemoteConfig.fallback;
  RemoteConfig get config => _config;
  DateTime _fetchedAt = DateTime.fromMillisecondsSinceEpoch(0);
  Future<void>? _inflight;

  Future<void> loadCached() async {
    try {
      final raw = await _native.boxGet(_key);
      if (raw != null) _set(RemoteConfig.fromJson(jsonDecode(raw) as Json));
    } on Object {
      // a bad cache is simply ignored
    }
  }

  Future<void> refresh({bool force = false}) {
    if (!force && DateTime.now().difference(_fetchedAt) < _every) return Future.value();
    return _inflight ??= _fetch().whenComplete(() => _inflight = null);
  }

  Future<void> _fetch() async {
    try {
      final json = await _api.getPublic('/app/v1/config', query: {
        'lang': _locale.lang,
        'build': '${AppConfig.appBuild}',
      });
      if (json is! Json) return;
      _fetchedAt = DateTime.now();
      _set(RemoteConfig.fromJson(json));
      unawaited(_native.boxPut(_key, jsonEncode(json)));
    } on Object {
      // offline: keep the last known config
    }
  }

  void _set(RemoteConfig config) {
    _config = config;
    notifyListeners();
  }
}
