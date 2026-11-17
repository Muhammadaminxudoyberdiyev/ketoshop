import 'package:flutter_test/flutter_test.dart';
import 'package:ketoshop/core/config.dart';
import 'package:ketoshop/core/remote/remote_config.dart';

void main() {
  test('update offers and requirements follow the build number', () {
    final newer = RemoteConfig.fromJson({
      'latest_build': AppConfig.appBuild + 1,
      'min_build': 0,
      'latest_version': '9.9.9',
      'update_url': 'https://t.me/ketoshop_uz',
    });
    expect(newer.updateAvailable, isTrue);
    expect(newer.mustUpdate, isFalse);
    final required = RemoteConfig.fromJson({'min_build': AppConfig.appBuild + 1, 'update_url': 'https://t.me/x'});
    expect(required.mustUpdate, isTrue);
    expect(RemoteConfig.fallback.mustUpdate, isFalse);
    expect(RemoteConfig.fallback.updateAvailable, isFalse);
  });

  test('only https/tg update links; never an update without a link', () {
    final c = RemoteConfig.fromJson({'min_build': 999, 'update_url': 'javascript:alert(1)'});
    expect(c.updateUrl, '');
    expect(c.mustUpdate, isFalse);
  });

  test('the Oferta edition in force', () {
    expect(RemoteConfig.fromJson({'terms_version': '2026-11-17'}).termsVersion, '2026-11-17');
    expect(RemoteConfig.fromJson(const {}).termsVersion, '');
  });
}
