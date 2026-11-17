import 'package:flutter_test/flutter_test.dart';
import 'package:ketoshop/core/net/signing.dart';

void main() {
  test('the signed string is byte-identical to the server one', () {
    // tests/test_app_auth.py asserts the same vector on the server side;
    // the last line (sha256 of the body) is appended natively.
    const bodyHash = 'RMefhrxnb88ZBTmmcoPHGTS_f_nUOtcsUCzo9sXAKOw';
    final uri = Uri.parse('https://keto.standart-eko.uz/api/cart/add?x=1&q=a%20b');
    final signed = canonicalPrefix('post', requestTarget(uri), 1700000000000, 'bm9uY2Utbm9uY2Utbm9uY2U') + bodyHash;
    expect(
      signed,
      'KS1\nPOST\n/api/cart/add?x=1&q=a%20b\n1700000000000\n'
      'bm9uY2Utbm9uY2Utbm9uY2U\nRMefhrxnb88ZBTmmcoPHGTS_f_nUOtcsUCzo9sXAKOw',
    );
  });

  test('query parameters are signed exactly as Uri encodes them', () {
    final uri = Uri.https('keto.standart-eko.uz', '/api/search', {'q': "o'simlik yog'i"});
    expect(requestTarget(uri), '/api/search?${uri.query}');
    expect(requestTarget(Uri.parse('https://h/api/cart')), '/api/cart');
  });

  test('server clock offset', () {
    final clock = ServerClock();
    final before = clock.nowMs();
    clock.sync(DateTime.now().millisecondsSinceEpoch + 300000);
    expect(clock.nowMs() - before, greaterThan(290000));
    clock.sync('junk');
    expect(clock.nowMs() - before, greaterThan(290000));
  });

  test('base64url without padding', () {
    expect(b64u([0xfb, 0xff]), '-_8');
  });
}
