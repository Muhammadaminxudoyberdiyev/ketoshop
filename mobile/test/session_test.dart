import 'package:flutter_test/flutter_test.dart';
import 'package:ketoshop/core/auth/session_store.dart';

void main() {
  test('session survives storage', () {
    final s = Session(
      accessToken: 'ksa_x',
      refreshToken: 'ksr_y',
      accessExpiresAt: DateTime.fromMillisecondsSinceEpoch(1700000000000),
      userId: 42,
      firstName: 'Ali',
    );
    final back = Session.fromJson(s.toJson())!;
    expect((back.accessToken, back.refreshToken, back.userId, back.firstName), ('ksa_x', 'ksr_y', 42, 'Ali'));
    expect(back.accessExpiresAt, s.accessExpiresAt);
    expect(Session.fromJson({'a': 1}), isNull);
    expect(Session.fromJson('junk'), isNull);
  });

  test('rotation keeps who, replaces tokens', () {
    final s = Session(
      accessToken: 'ksa_old',
      refreshToken: 'ksr_old',
      accessExpiresAt: DateTime(2000),
      userId: 7,
      firstName: 'Vali',
    );
    final r = s.rotated(access: 'ksa_new', refresh: 'ksr_new', expiresInSeconds: 900);
    expect((r.accessToken, r.refreshToken, r.userId, r.firstName), ('ksa_new', 'ksr_new', 7, 'Vali'));
    expect(r.accessExpiresAt.isAfter(DateTime.now()), isTrue);
  });
}
