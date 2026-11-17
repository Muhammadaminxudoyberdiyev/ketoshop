import 'package:flutter_test/flutter_test.dart';
import 'package:ketoshop/core/remote/remote_config.dart';
import 'package:ketoshop/data/terms_repository.dart';

String same(String s) => s;

void main() {
  test('terms document from the server', () {
    final doc = TermsDoc.fromJson({
      'version': '2026-11-17',
      'title': 'Oferta shartlari',
      'sections': [
        {'title': '5. Javobgarlik', 'items': ['Soxta buyurtmalar bekor qilinadi.', 7, null]},
        'junk',
      ],
    }, same);
    expect(doc.version, '2026-11-17');
    expect(doc.sections.single.$1, '5. Javobgarlik');
    expect(doc.sections.single.$2, ['Soxta buyurtmalar bekor qilinadi.']);
  });

  test('remote config carries the edition in force', () {
    expect(RemoteConfig.fromJson({'terms_version': '2026-11-17'}).termsVersion, '2026-11-17');
    expect(RemoteConfig.fromJson(const {}).termsVersion, '');
  });
}
