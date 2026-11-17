import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:isolate';
import 'dart:typed_data';

import '../auth/session_store.dart';
import '../config.dart';
import '../platform/native_bridge.dart';
import 'signing.dart';

/// The server answered with an error the caller may want to show.
class ApiException implements Exception {
  const ApiException(this.status, this.code, [this.body = const {}]);
  final int status;
  final String code;
  final Map<String, Object?> body;

  @override
  String toString() => 'ApiException($status, $code)';
}

/// No answer from the server (offline, timeout, or a TLS certificate that
/// does not chain to the pinned roots).
class NetworkException implements Exception {
  const NetworkException({this.tls = false});
  final bool tls;
}

/// The shop is for channel members who started the bot (site_gate).
class GateRequired implements Exception {
  const GateRequired(this.gate);
  final Map<String, Object?> gate;
}

/// The session can't continue: logged out elsewhere, revoked, expired.
class SessionEnded implements Exception {
  const SessionEnded(this.reason);
  final String reason;
}

class _RawResponse {
  const _RawResponse(this.status, this.json);
  final int status;
  final Object? json;

  Map<String, Object?> get map => json is Map<String, Object?> ? json as Map<String, Object?> : const {};
  String get code => (map['error'] as String?) ?? '';
}

/// Every request to the server goes through here: pinned TLS, the device
/// signature, the access token (refreshed ahead of time, one refresh at a
/// time), clock correction, bounded retries for reads only.
class ApiClient {
  ApiClient({
    required HttpClient http,
    required NativeBridge native,
    required SessionStore sessions,
    required ServerClock clock,
  })  : _http = http,
        _native = native,
        _sessions = sessions,
        _clock = clock,
        _signer = RequestSigner(native, clock);

  final HttpClient _http;
  final NativeBridge _native;
  final SessionStore _sessions;
  final ServerClock _clock;
  final RequestSigner _signer;
  Future<void>? _refreshing;

  /// Called once when the session dies, so the app can show the login.
  void Function(String reason)? onSessionEnded;

  static const _maxResponseBytes = 20 * 1024 * 1024;

  Future<Object?> get(String path, {Map<String, String>? query}) =>
      _request('GET', path, query: query, readRetries: 2);

  Future<Object?> post(String path, {Object? json, Uint8List? raw, String? contentType, Map<String, String>? headers,
          Duration? timeout}) =>
      _request('POST', path, json: json, raw: raw, contentType: contentType, headers: headers, timeout: timeout);

  /// Public reads that work before login (the app's remote config).
  Future<Object?> getPublic(String path, {Map<String, String>? query}) =>
      _request('GET', path, query: query, auth: false, readRetries: 1);

  /// /app/v1/auth/* before there is a session: signed, no token.
  Future<Object?> postUnauthenticated(String path, Object json) => _request('POST', path, json: json, auth: false);

  Future<Object?> _request(
    String method,
    String path, {
    Map<String, String>? query,
    Object? json,
    Uint8List? raw,
    String? contentType,
    Map<String, String>? headers,
    Duration? timeout,
    bool auth = true,
    int readRetries = 0,
  }) async {
    final uri = AppConfig.baseUri.replace(path: path, queryParameters: (query == null || query.isEmpty) ? null : query);
    final body = raw ?? (json == null ? Uint8List(0) : Uint8List.fromList(utf8.encode(jsonEncode(json))));
    final type = raw != null ? contentType : (json == null ? null : 'application/json');
    var clockRetried = false;
    var tokenRetried = false;
    var networkTries = 0;

    while (true) {
      final token = auth ? await _validAccessToken() : null;
      final _RawResponse res;
      try {
        res = await _send(method, uri, body, type, token, headers, timeout ?? AppConfig.requestTimeout);
      } on HandshakeException {
        throw const NetworkException(tls: true);
      } on TlsException {
        throw const NetworkException(tls: true);
      } on Object catch (e) {
        if (e is! SocketException && e is! TimeoutException && e is! HttpException) rethrow;
        if (networkTries++ < readRetries) {
          await Future<void>.delayed(Duration(milliseconds: 400 * networkTries * networkTries));
          continue;
        }
        throw const NetworkException();
      }

      if (res.status == 401) {
        if (res.code == 'clock_skew' && !clockRetried) {
          clockRetried = true;
          _clock.sync(res.map['server_time']);
          continue;
        }
        if (auth && !tokenRetried && (res.code == 'token_expired' || res.code == 'invalid_token')) {
          tokenRetried = true;
          await _refresh();
          continue;
        }
        if (auth) throw _endSession(res.code.isEmpty ? 'unauthorized' : res.code);
      }
      if (res.status == 403 && res.code == 'start_bot') throw GateRequired(res.map);
      if (res.status == 403 && res.code == 'device_untrusted') throw _endSession('device_untrusted');
      if (res.status >= 400) throw ApiException(res.status, res.code, res.map);
      _clock.sync(res.map['server_time']);
      return res.json;
    }
  }

  Future<_RawResponse> _send(String method, Uri uri, Uint8List body, String? contentType, String? token,
      Map<String, String>? extra, Duration timeout) async {
    final request = await _http.openUrl(method, uri).timeout(timeout);
    request.followRedirects = false; // a token never follows a redirect anywhere
    request.persistentConnection = true;
    request.headers.set(HttpHeaders.acceptHeader, 'application/json');
    if (contentType != null) request.headers.contentType = ContentType.parse(contentType);
    if (token != null) request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
    extra?.forEach(request.headers.set);
    (await _signer.headers(method, uri, body)).forEach(request.headers.set);
    request.contentLength = body.length;
    if (body.isNotEmpty) request.add(body);
    final response = await request.close().timeout(timeout);

    final builder = BytesBuilder(copy: false);
    await for (final chunk in response.timeout(timeout)) {
      builder.add(chunk);
      if (builder.length > _maxResponseBytes) throw const HttpException('response too large');
    }
    final bytes = builder.takeBytes();
    final isJson = response.headers.contentType?.mimeType == 'application/json';
    Object? decoded;
    if (isJson && bytes.isNotEmpty) {
      decoded = bytes.length > 200 * 1024
          ? await Isolate.run(() => jsonDecode(utf8.decode(bytes)))
          : jsonDecode(utf8.decode(bytes));
    }
    return _RawResponse(response.statusCode, decoded);
  }

  Future<String> _validAccessToken() async {
    var session = _sessions.current;
    if (session == null) throw const SessionEnded('no_session');
    if (session.accessExpiresAt.isBefore(DateTime.now().add(AppConfig.refreshMargin))) {
      await _refresh();
      session = _sessions.current;
      if (session == null) throw const SessionEnded('no_session');
    }
    return session.accessToken;
  }

  Future<void> _refresh() => _refreshing ??= _doRefresh().whenComplete(() => _refreshing = null);

  Future<void> _doRefresh() async {
    final session = _sessions.current;
    if (session == null) throw const SessionEnded('no_session');
    final env = await _native.checkEnvironment();
    final Object? json;
    try {
      json = await _request('POST', '/app/v1/auth/refresh',
          json: {'refresh_token': session.refreshToken, 'env': env.toJson()}, auth: false);
    } on ApiException catch (e) {
      if (e.status == 401 || e.status == 403) throw _endSession(e.code.isEmpty ? 'session_ended' : e.code);
      rethrow;
    }
    final m = json is Map ? json : const <String, Object?>{};
    final access = m['access_token'], refresh = m['refresh_token'], ttl = m['access_expires_in'];
    if (access is! String || refresh is! String || ttl is! int) throw const ApiException(500, 'bad_refresh');
    await _sessions.save(session.rotated(access: access, refresh: refresh, expiresInSeconds: ttl));
  }

  SessionEnded _endSession(String reason) {
    final had = _sessions.current != null;
    unawaited(_sessions.clear());
    if (had) onSessionEnded?.call(reason);
    return SessionEnded(reason);
  }

  /// Bytes of a picture from our own host (product photos). Not signed:
  /// /api/photo and /img are public. Anything on another host is refused.
  Future<Uint8List?> fetchImage(String url) async {
    final uri = AppConfig.baseUri.resolve(url);
    if (uri.scheme != 'https' || uri.host != AppConfig.host) return null;
    try {
      final request = await _http.getUrl(uri).timeout(AppConfig.requestTimeout);
      request.followRedirects = false;
      final response = await request.close().timeout(AppConfig.requestTimeout);
      if (response.statusCode != 200) {
        await response.drain<void>();
        return null;
      }
      final builder = BytesBuilder(copy: false);
      await for (final chunk in response.timeout(AppConfig.requestTimeout)) {
        builder.add(chunk);
        if (builder.length > 8 * 1024 * 1024) return null;
      }
      return builder.takeBytes();
    } on Object {
      return null;
    }
  }
}
