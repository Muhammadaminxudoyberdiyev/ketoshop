import 'package:flutter_test/flutter_test.dart';
import 'package:ketoshop/core/config.dart';
import 'package:ketoshop/core/remote/remote_config.dart';

void main() {
  test('blocks this build does not know are skipped, never a crash', () {
    final c = RemoteConfig.fromJson({
      'home': [
        {'type': 'banner', 'id': 'a', 'title': 'Aksiya'},
        {'type': 'hologram', 'id': 'future'},
        'junk',
        {'type': 'products', 'id': 'p', 'product_ids': [1, '2', 3.0]},
      ],
    });
    expect(c.home.map((b) => b.type), ['banner', 'products']);
    expect(c.home.last.productIds, [1, 3]);
  });

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
  });

  test('only https/tg update links; never an update without a link', () {
    final c = RemoteConfig.fromJson({'min_build': 999, 'update_url': 'javascript:alert(1)'});
    expect(c.updateUrl, '');
    expect(c.mustUpdate, isFalse);
  });

  test('features and delivery methods with safe defaults', () {
    final c = RemoteConfig.fromJson({
      'features': {'search': false, 'weird': 'yes'},
      'delivery': {'tashkent': ['self', 'teleport'], 'regions': <String>[]},
    });
    expect(c.enabled('search'), isFalse);
    expect(c.enabled('weird'), isTrue);
    expect(c.enabled('new_thing', orElse: false), isFalse);
    expect(c.tashkentMethods, ['self']);
    expect(c.regionMethods, RemoteConfig.fallback.regionMethods);
  });
}
