import 'dart:async';

import 'package:flutter/foundation.dart';

import '../platform/native_bridge.dart';
import 'alphabet.dart';
import 'strings.g.dart';

/// The buyer's language — uz (Latin), uz_cyr or ru, the same value the bot
/// keeps in users.language — and whether Latin is shown in the 2026
/// alphabet (the server's switch, alphabet.py).
class LocaleController extends ChangeNotifier {
  LocaleController(this._native);

  static const languages = ['uz', 'uz_cyr', 'ru'];
  static const languageNames = {'uz': "O'zbekcha", 'uz_cyr': 'Ўзбекча', 'ru': 'Русский'};
  static const _key = 'lang.v1';

  final NativeBridge _native;
  String _lang = 'uz';
  bool _newAlphabet = true;

  String get lang => _lang;
  bool get newAlphabet => _newAlphabet;

  Future<void> load() async {
    final saved = await _native.boxGet(_key);
    if (saved != null && languages.contains(saved)) _lang = saved;
  }

  /// From GET /api/lang: the language saved on the server wins, so the bot
  /// and the app always speak the same one.
  void applyServer(String lang, bool newAlphabet) {
    final next = languages.contains(lang) ? lang : _lang;
    if (next == _lang && newAlphabet == _newAlphabet) return;
    _lang = next;
    _newAlphabet = newAlphabet;
    unawaited(_native.boxPut(_key, _lang));
    notifyListeners();
  }

  Future<void> setLocal(String lang) async {
    if (!languages.contains(lang) || lang == _lang) return;
    _lang = lang;
    await _native.boxPut(_key, lang);
    notifyListeners();
  }

  String get _table => _lang == 'uz' && _newAlphabet ? 'uz_new' : _lang;

  /// A UI string, with {placeholders} filled in.
  String t(String key, [Map<String, Object?> args = const {}]) {
    var value = kStrings[_table]?[key] ?? kStrings['uz']![key];
    assert(value != null, 'missing string: $key');
    value ??= key;
    args.forEach((k, v) => value = value!.replaceAll('{$k}', '$v'));
    return value!;
  }

  /// Text that came from the server (product names, hints): already in the
  /// buyer's language; Latin gets the 2026 letters when they are on.
  String display(String text) => _lang == 'uz' && _newAlphabet ? toNewLatin(text) : text;
}
