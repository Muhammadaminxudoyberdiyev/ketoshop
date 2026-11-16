import 'package:flutter/services.dart';

/// What the phone itself reports about its safety (SecurityChannel.kt).
class DeviceEnv {
  const DeviceEnv({
    required this.rooted,
    required this.hooked,
    required this.debugged,
    required this.emulator,
    required this.tampered,
    required this.deviceName,
  });

  final bool rooted;
  final bool hooked;
  final bool debugged;
  final bool emulator;
  final bool tampered;
  final String deviceName;

  /// Hooking, a debugger or a re-signed APK means someone is inside the app
  /// itself; the app refuses to run. A rooted phone is only reported.
  bool get compromised => hooked || debugged || tampered;

  Map<String, bool> toJson() => {
        'rooted': rooted,
        'hooked': hooked,
        'debugged': debugged,
        'emulator': emulator,
        'tampered': tampered,
      };
}

class PickedFile {
  const PickedFile(this.bytes, this.mime, this.name);
  final Uint8List bytes;
  final String mime;
  final String name;
}

class GeoPoint {
  const GeoPoint(this.lat, this.lng);
  final double lat;
  final double lng;
}

class LocationFailure implements Exception {
  const LocationFailure(this.code);

  /// denied | disabled | timeout | unavailable
  final String code;
}

class FileTooLarge implements Exception {
  const FileTooLarge();
}

/// The only door to Android: Keystore keys, encrypted storage, integrity
/// checks, location, file picking and opening links. Everything here is
/// implemented in the app's own Kotlin (android/app/src/main/kotlin) — no
/// third-party plugins.
class NativeBridge {
  NativeBridge([MethodChannel? channel]) : _channel = channel ?? const MethodChannel('uz.ketoshop/secure');

  final MethodChannel _channel;

  /// Public half (base64url SubjectPublicKeyInfo) of the P-256 key kept in
  /// the Android Keystore; created on first use, never leaves the chip.
  Future<String> devicePublicKey() async => (await _channel.invokeMethod<String>('key.public'))!;

  /// ECDSA-SHA256 over `prefix + base64url(sha256(body))`, DER, base64url.
  Future<String> sign(String prefix, Uint8List body) async =>
      (await _channel.invokeMethod<String>('key.sign', {'prefix': prefix, 'body': body}))!;

  /// Forget the device key (logout) — the next login makes a new one.
  Future<void> resetDeviceKey() => _channel.invokeMethod('key.reset');

  /// AES-256-GCM with a Keystore key; `null` deletes.
  Future<void> boxPut(String key, String? value) => _channel.invokeMethod('box.put', {'key': key, 'value': value});

  Future<String?> boxGet(String key) => _channel.invokeMethod<String>('box.get', {'key': key});

  Future<void> boxClear() => _channel.invokeMethod('box.clear');

  Future<DeviceEnv> checkEnvironment() async {
    final m = (await _channel.invokeMapMethod<String, Object?>('env.check'))!;
    bool b(String k) => m[k] == true;
    return DeviceEnv(
      rooted: b('rooted'),
      hooked: b('hooked'),
      debugged: b('debugged'),
      emulator: b('emulator'),
      tampered: b('tampered'),
      deviceName: (m['deviceName'] as String?) ?? 'Android',
    );
  }

  /// FLAG_SECURE: no screenshots, screen recording or recent-apps preview.
  Future<void> setSecureScreen(bool on) => _channel.invokeMethod('ui.secure', {'on': on});

  /// Opens https:// and tg:// links only (checked again natively).
  Future<bool> openUrl(String url) async => (await _channel.invokeMethod<bool>('open.url', {'url': url})) ?? false;

  Future<String> cacheDir() async => (await _channel.invokeMethod<String>('fs.cacheDir'))!;

  Future<GeoPoint> currentLocation() async {
    try {
      final m = (await _channel.invokeMapMethod<String, Object?>('location.current'))!;
      return GeoPoint((m['lat'] as num).toDouble(), (m['lng'] as num).toDouble());
    } on PlatformException catch (e) {
      throw LocationFailure(e.code);
    }
  }

  /// Photo or PDF for the payment cheque; `null` when the buyer backs out.
  Future<PickedFile?> pickCheque() async {
    try {
      final m = await _channel.invokeMapMethod<String, Object?>('file.pickCheque');
      if (m == null) return null;
      return PickedFile(m['bytes']! as Uint8List, m['mime']! as String, (m['name'] as String?) ?? 'chek');
    } on PlatformException catch (e) {
      if (e.code == 'too_large') throw const FileTooLarge();
      rethrow;
    }
  }
}
