import 'package:flutter_test/flutter_test.dart';
import 'package:ketoshop/core/l10n/alphabet.dart';

import 'alphabet_vectors.g.dart';

void main() {
  test('matches translit.to_new_latin on the server', () {
    for (final (input, expected) in kAlphabetVectors) {
      expect(toNewLatin(input), expected, reason: input);
    }
  });

  test('idempotent', () {
    for (final (input, _) in kAlphabetVectors) {
      final once = toNewLatin(input);
      expect(toNewLatin(once), once, reason: input);
    }
  });
}
