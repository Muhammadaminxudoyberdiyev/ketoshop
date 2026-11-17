import 'dart:convert';

import '../platform/native_bridge.dart';

class Session {
  const Session({
    required this.accessToken,
    required this.refreshToken,
    required this.accessExpiresAt,
    required this.userId,
    required this.firstName,
  });

  final String accessToken;
  final String refreshToken;
  final DateTime accessExpiresAt;
  final int userId;
  final String firstName;

  Session rotated({required String access, required String refresh, required int expiresInSeconds}) => Session(
        accessToken: access,
        refreshToken: refresh,
        accessExpiresAt: DateTime.now().add(Duration(seconds: expiresInSeconds)),
        userId: userId,
        firstName: firstName,
      );

  Map<String, Object> toJson() => {
        'a': accessToken,
        'r': refreshToken,
        'e': accessExpiresAt.millisecondsSinceEpoch,
        'u': userId,
        'n': firstName,
      };

  static Session? fromJson(Object? raw) {
    if (raw is! Map) return null;
    final a = raw['a'], r = raw['r'], e = raw['e'], u = raw['u'];
    if (a is! String || r is! String || e is! int || u is! int) return null;
    return Session(
      accessToken: a,
      refreshToken: r,
      accessExpiresAt: DateTime.fromMillisecondsSinceEpoch(e),
      userId: u,
      firstName: (raw['n'] as String?) ?? '',
    );
  }
}

/// Tokens live only in memory and in the Keystore-encrypted box; they are
/// worthless on another phone anyway (every request is signed by this one).
class SessionStore {
  SessionStore(this._native);

  static const _key = 'session.v1';
  final NativeBridge _native;
  Session? _current;

  Session? get current => _current;

  Future<void> load() async {
    try {
      final raw = await _native.boxGet(_key);
      _current = raw == null ? null : Session.fromJson(jsonDecode(raw));
    } catch (_) {
      // Unreadable (key wiped by a restore, OS upgrade gone wrong): log in again.
      _current = null;
      await _native.boxClear();
    }
  }

  Future<void> save(Session session) async {
    _current = session;
    await _native.boxPut(_key, jsonEncode(session.toJson()));
  }

  Future<void> clear() async {
    _current = null;
    await _native.boxPut(_key, null);
  }
}
