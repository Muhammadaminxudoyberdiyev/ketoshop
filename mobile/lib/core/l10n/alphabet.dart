/// Old Uzbek Latin → the 2026 alphabet (oʻ gʻ sh ch → ö ğ ş ç): a port of
/// translit.to_new_latin on the server, checked against it by
/// test/alphabet_test.dart (vectors generated from the Python original).
/// Links, @handles, /commands, {tokens}, tags and the shop's name stay as
/// they are.
String toNewLatin(String text) {
  if (text.isEmpty || !_hasCandidate.hasMatch(text)) return text;
  final store = <String>[];
  String stash(String input, RegExp pattern) => input.replaceAllMapped(pattern, (m) {
        store.add(m[0]!);
        return '${store.length - 1}';
      });

  var t = stash(text, _htmlTag);
  t = stash(t, _fmtToken);
  t = stash(t, _handleOrLink);
  t = stash(t, _botCommand);
  t = stash(t, _keep);

  final quotes = <(String, String)>[];
  t = t.replaceAllMapped(_singleQuoted, (m) {
    final whole = m[0]!;
    quotes.add((whole[0], whole[whole.length - 1]));
    return '${m[1]}';
  });
  t = t.replaceAllMapped(_sHSplit, (m) => '${m[1]}${m[2]}');
  t = t.replaceAllMapped(_og, (m) => _newOg[m[1]]!);
  t = t.replaceAllMapped(_shCh, (m) {
    final first = m[1]!;
    final letter = (first == 's' || first == 'S') ? 'ş' : 'ç';
    return first == first.toUpperCase() ? letter.toUpperCase() : letter;
  });
  t = t.replaceAll('', '‌');
  for (final (open, close) in quotes) {
    t = t.replaceFirst('', open).replaceFirst('', close);
  }
  for (var i = store.length - 1; i >= 0; i--) {
    t = t.replaceAll('$i', store[i]);
  }
  return t;
}

const _apostrophes = "'ʻ‘’`ʼ";
final _hasCandidate = RegExp('[oOgGsScC]');
final _htmlTag = RegExp('<[^>]+>');
final _fmtToken = RegExp(r'\{[^{}]*\}');
final _handleOrLink = RegExp(r'@[A-Za-z0-9_]{3,}|(?:https?://|t\.me/|www\.)\S+');
final _botCommand = RegExp(r'(?<![A-Za-z0-9])/[a-zA-Z][a-zA-Z0-9_]*');
final _keep = RegExp(r'keto\s?shop|charged', caseSensitive: false);
// Python's [^\W_] is "a letter or a digit" in any script.
final _singleQuoted =
    RegExp(r"(?<![\p{L}\p{N}])['‘]([^'‘’\n]{1,60})['’](?![\p{L}\p{N}])", unicode: true);
final _sHSplit = RegExp('([sScC])[$_apostrophes]([hH])');
final _og = RegExp('([oOgG])[$_apostrophes]');
final _shCh = RegExp('([sScC])([hH])');
const _newOg = {'o': 'ö', 'O': 'Ö', 'g': 'ğ', 'G': 'Ğ'};
