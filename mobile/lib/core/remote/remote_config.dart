import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../config.dart';
import '../l10n/locale_controller.dart';
import '../net/api_client.dart';
import '../platform/native_bridge.dart';

typedef Json = Map<String, Object?>;

/// One block of the server-driven home area (app_config.py). Only the types
/// this build knows are kept; a type added later is skipped, never a crash.
class HomeBlock {
  const HomeBlock(this.type, this.id, this.data);

  static const known = {'banner', 'notice', 'link', 'category', 'products'};

  final String type;
  final String id;
  final Json data;

  String text(String key) => (data[key] as String?) ?? '';
  String? optional(String key) {
    final v = data[key];
    return v is String && v.isNotEmpty ? v : null;
  }

  List<int> get productIds => (data['product_ids'] as List?)?.whereType<num>().map((n) => n.toInt()).toList() ?? const [];
}

/// What the server decides about the app without a new APK.
class RemoteConfig {
  const RemoteConfig({
    required this.latestVersion,
    required this.latestBuild,
    required this.minBuild,
    required this.updateUrl,
    required this.updateNotes,
    required this.features,
    required this.tashkentMethods,
    required this.regionMethods,
    required this.home,
    this.termsVersion = '',
  });

  /// Built-in values: the app works offline and before the first answer.
  static const fallback = RemoteConfig(
    latestVersion: AppConfig.appVersion,
    latestBuild: AppConfig.appBuild,
    minBuild: 0,
    updateUrl: '',
    updateNotes: '',
    features: {},
    tashkentMethods: ['self', 'yandex_taxi'],
    regionMethods: ['uzpost', 'bts', 'emu'],
    home: [],
  );

  final String latestVersion;
  final int latestBuild;
  final int minBuild;
  final String updateUrl;
  final String updateNotes;
  final Map<String, bool> features;
  final List<String> tashkentMethods;
  final List<String> regionMethods;
  final List<HomeBlock> home;

  /// The Oferta edition in force (app_terms.VERSION).
  final String termsVersion;

  /// A switch the server can flip; unknown switches keep their default.
  bool enabled(String feature, {bool orElse = true}) => features[feature] ?? orElse;

  bool get mustUpdate => AppConfig.appBuild < minBuild && updateUrl.isNotEmpty;
  bool get updateAvailable => AppConfig.appBuild < latestBuild && updateUrl.isNotEmpty;

  static const _deliveryMethods = {'self', 'yandex_taxi', 'uzpost', 'bts', 'emu'};

  factory RemoteConfig.fromJson(Json j) {
    List<String> methods(Object? v, List<String> orElse) {
      final list = (v as List?)?.whereType<String>().where(_deliveryMethods.contains).toList();
      return list == null || list.isEmpty ? orElse : list;
    }

    final delivery = (j['delivery'] as Map?) ?? const {};
    final features = <String, bool>{};
    ((j['features'] as Map?) ?? const {}).forEach((k, v) {
      if (k is String && v is bool) features[k] = v;
    });
    return RemoteConfig(
      latestVersion: (j['latest_version'] as String?) ?? AppConfig.appVersion,
      latestBuild: (j['latest_build'] as num?)?.toInt() ?? AppConfig.appBuild,
      minBuild: (j['min_build'] as num?)?.toInt() ?? 0,
      updateUrl: _safeUrl(j['update_url']),
      updateNotes: (j['update_notes'] as String?) ?? '',
      features: features,
      tashkentMethods: methods(delivery['tashkent'], fallback.tashkentMethods),
      regionMethods: methods(delivery['regions'], fallback.regionMethods),
      termsVersion: (j['terms_version'] as String?) ?? '',
      home: [
        for (final b in (j['home'] as List?) ?? const [])
          if (b is Json && HomeBlock.known.contains(b['type']))
            HomeBlock(b['type']! as String, (b['id'] as String?) ?? '', b),
      ],
    );
  }

  static String _safeUrl(Object? v) {
    final uri = v is String ? Uri.tryParse(v) : null;
    return uri != null && (uri.scheme == 'https' || uri.scheme == 'tg') ? v! as String : '';
  }
}

/// Reads /app/v1/config on start, on return to the app (at most every 30
/// min) and when the language changes; keeps the last answer encrypted on
/// the phone so the home area shows instantly and offline.
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
