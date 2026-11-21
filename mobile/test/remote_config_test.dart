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

  test('self-update needs a real hash and an https link', () {
    final hash = 'ab' * 32;
    final c = RemoteConfig.fromJson({'update_url': 'https://keto.standart-eko.uz/app/download/ketoshop-3.apk',
                                     'apk_sha256': hash, 'apk_size': 100});
    expect((c.selfUpdate, c.apkSha256, c.apkSize), (true, hash, 100));
    expect(RemoteConfig.fromJson({'update_url': 'https://t.me/x', 'apk_sha256': 'nothex'}).selfUpdate, isFalse);
  });

  test('server paths stay on our host', () {
    expect(RemoteConfig.fromJson({'shop_path': '/?game=quiz', 'shim_path': '/app/v2/shim.js'}).shopPath, '/?game=quiz');
    final bad = RemoteConfig.fromJson({'shop_path': '//evil.example/', 'shim_path': 'https://evil.example/x.js'});
    expect((bad.shopPath, bad.shimPath), ('/', '/app/v1/shim.js'));
  });

  test('the Oferta edition in force', () {
    expect(RemoteConfig.fromJson({'terms_version': '2026-11-17'}).termsVersion, '2026-11-17');
    expect(RemoteConfig.fromJson(const {}).termsVersion, '');
  });
}
