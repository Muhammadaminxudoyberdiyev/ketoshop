import 'package:flutter/foundation.dart';

import '../net/api_client.dart';
import '../platform/native_bridge.dart';
import 'session_store.dart';

enum AuthStatus { unknown, unsafeDevice, signedOut, signedIn }

class LoginTicket {
  const LoginTicket({
    required this.requestId,
    required this.botUrl,
    required this.matchCode,
    required this.expiresAt,
    this.termsVersion = '',
  });
  final String requestId;
  final String botUrl;
  final int matchCode;
  final DateTime expiresAt;

  /// The Oferta edition shown on the login screen; logging in accepts it.
  final String termsVersion;
}

enum PollOutcome { pending, approved, rejected, expired }

/// Who is using the app. The login itself (see app_auth.py on the server):
/// start → buyer taps the number in the bot → poll until approved.
class AuthController extends ChangeNotifier {
  AuthController({required NativeBridge native, required SessionStore sessions, required ApiClient api})
      : _native = native,
        _sessions = sessions,
        _api = api {
    _api.onSessionEnded = _onSessionEnded;
  }

  final NativeBridge _native;
  final SessionStore _sessions;
  final ApiClient _api;

  AuthStatus _status = AuthStatus.unknown;
  AuthStatus get status => _status;

  /// Why the user was signed out last (shown once on the login screen).
  String? lastEndReason;

  /// Told which Oferta edition a successful login accepted.
  Future<void> Function(String version)? onTermsAccepted;

  /// Runs before a logout (the phone's push token is forgotten).
  Future<void> Function()? beforeLogout;

  Session? get session => _sessions.current;

  Future<void> bootstrap() async {
    final env = await _native.checkEnvironment();
    if (env.compromised && kReleaseMode) {
      _set(AuthStatus.unsafeDevice);
      return;
    }
    await _sessions.load();
    _set(_sessions.current == null ? AuthStatus.signedOut : AuthStatus.signedIn);
  }

  Future<LoginTicket> startLogin({String termsVersion = ''}) async {
    final env = await _native.checkEnvironment();
    final json = await _api.postUnauthenticated('/app/v1/auth/start', {
      'device_key': await _native.devicePublicKey(),
      'device_name': env.deviceName,
      'env': env.toJson(),
      if (termsVersion.isNotEmpty) 'terms_version': termsVersion,
    });
    final m = json! as Map<String, Object?>;
    return LoginTicket(
      requestId: m['request_id']! as String,
      botUrl: m['bot_url']! as String,
      matchCode: (m['match_code']! as num).toInt(),
      expiresAt: DateTime.now().add(Duration(seconds: (m['expires_in']! as num).toInt())),
      termsVersion: termsVersion,
    );
  }

  Future<PollOutcome> poll(LoginTicket ticket) async {
    final Object? json;
    try {
      json = await _api.postUnauthenticated('/app/v1/auth/poll', {'request_id': ticket.requestId});
    } on ApiException catch (e) {
      if (e.status == 410) return e.body['status'] == 'rejected' ? PollOutcome.rejected : PollOutcome.expired;
      if (e.status == 429) return PollOutcome.pending;
      rethrow;
    }
    final m = json! as Map<String, Object?>;
    if (m['status'] != 'approved') return PollOutcome.pending;
    final user = (m['user'] as Map?) ?? const {};
    await _sessions.save(Session(
      accessToken: m['access_token']! as String,
      refreshToken: m['refresh_token']! as String,
      accessExpiresAt: DateTime.now().add(Duration(seconds: (m['access_expires_in']! as num).toInt())),
      userId: (user['id'] as num?)?.toInt() ?? 0,
      firstName: (user['first_name'] as String?) ?? '',
    ));
    lastEndReason = null;
    if (ticket.termsVersion.isNotEmpty) await onTermsAccepted?.call(ticket.termsVersion);
    _set(AuthStatus.signedIn);
    return PollOutcome.approved;
  }

  Future<void> logout() async {
    await beforeLogout?.call();
    try {
      await _api.post('/app/v1/auth/logout');
    } on Object {
      // Signed out locally either way; the server session expires on its own.
    }
    await _sessions.clear();
    await _native.resetDeviceKey();
    _set(AuthStatus.signedOut);
  }

  void _onSessionEnded(String reason) {
    lastEndReason = reason;
    _set(AuthStatus.signedOut);
  }

  void _set(AuthStatus status) {
    if (_status == status) return;
    _status = status;
    notifyListeners();
  }
}
