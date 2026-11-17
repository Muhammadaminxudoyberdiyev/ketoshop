import 'dart:convert';

import '../core/l10n/locale_controller.dart';
import '../core/net/api_client.dart';
import '../core/platform/native_bridge.dart';
import 'models.dart';

class TermsDoc {
  const TermsDoc({required this.version, required this.title, required this.sections});
  final String version;
  final String title;
  final List<(String, List<String>)> sections;

  factory TermsDoc.fromJson(Json j, Display d) => TermsDoc(
        version: (j['version'] as String?) ?? '',
        title: d((j['title'] as String?) ?? ''),
        sections: [
          for (final s in (j['sections'] as List?) ?? const [])
            if (s is Json)
              (
                d((s['title'] as String?) ?? ''),
                [for (final i in (s['items'] as List?) ?? const []) if (i is String) d(i)],
              ),
        ],
      );
}

/// «Oferta shartlari» (app_terms.py): the text comes from the server, the
/// last copy is kept for offline reading; which edition this phone accepted
/// is remembered so a new edition is offered once.
class TermsRepository {
  TermsRepository(this._api, this._native, this._locale);

  final ApiClient _api;
  final NativeBridge _native;
  final LocaleController _locale;

  static const _cacheKey = 'terms.cache.v1';
  static const _acceptedKey = 'terms.accepted.v1';

  Future<TermsDoc> load() async {
    try {
      final json = await _api.getPublic('/app/v1/terms', query: {'lang': _locale.lang});
      if (json is Json) {
        await _native.boxPut(_cacheKey, jsonEncode(json));
        return TermsDoc.fromJson(json, _locale.display);
      }
    } on NetworkException {
      final cached = await _native.boxGet(_cacheKey);
      if (cached != null) return TermsDoc.fromJson(jsonDecode(cached) as Json, _locale.display);
      rethrow;
    }
    throw const ApiException(500, 'bad_terms');
  }

  Future<String?> acceptedVersion() => _native.boxGet(_acceptedKey);

  Future<void> rememberAccepted(String version) => _native.boxPut(_acceptedKey, version);

  /// The signed-in buyer accepts `version`; the server records it.
  Future<void> accept(String version) async {
    await _api.post('/app/v1/terms/accept', json: {'version': version});
    await rememberAccepted(version);
  }
}
