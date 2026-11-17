import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import '../platform/native_bridge.dart';

/// The server's clock as the app last saw it. Signatures carry a timestamp
/// the server accepts within ±2 minutes, and phones are often off by more.
class ServerClock {
  int _offsetMs = 0;

  int nowMs() => DateTime.now().millisecondsSinceEpoch + _offsetMs;

  void sync(Object? serverTimeMs) {
    if (serverTimeMs is num) {
      _offsetMs = serverTimeMs.toInt() - DateTime.now().millisecondsSinceEpoch;
    }
  }
}

String b64u(List<int> bytes) => base64Url.encode(bytes).replaceAll('=', '');

/// Everything signed except the body hash, which the Keystore side appends
/// (so a 10 MB cheque is hashed natively, not in Dart). Must match
/// app_auth.canonical on the server:
///   KS1 \n METHOD \n /path?query \n timestamp_ms \n nonce \n b64url(sha256(body))
String canonicalPrefix(String method, String target, int timestampMs, String nonce) =>
    'KS1\n${method.toUpperCase()}\n$target\n$timestampMs\n$nonce\n';

/// What goes on the request line: path plus the query exactly as encoded.
String requestTarget(Uri uri) => uri.hasQuery ? '${uri.path}?${uri.query}' : uri.path;

class RequestSigner {
  RequestSigner(this._native, this._clock);

  final NativeBridge _native;
  final ServerClock _clock;
  final Random _random = Random.secure();

  Future<Map<String, String>> headers(String method, Uri uri, Uint8List body) async {
    final ts = _clock.nowMs();
    final nonce = b64u(List<int>.generate(16, (_) => _random.nextInt(256)));
    final signature = await _native.sign(canonicalPrefix(method, requestTarget(uri), ts, nonce), body);
    return {
      'X-KS-Timestamp': '$ts',
      'X-KS-Nonce': nonce,
      'X-KS-Signature': signature,
    };
  }
}
