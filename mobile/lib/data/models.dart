/// Shapes the native screens read from the server. The shop itself is the
/// site (ShopScreen), so only the app's own data lives here.
typedef Json = Map<String, Object?>;
typedef Display = String Function(String);

/// One signed-in device (/app/v1/sessions).
class DeviceSession {
  const DeviceSession(this.id, this.deviceName, this.lastSeen, this.current);
  final int id;
  final String deviceName;
  final String lastSeen;
  final bool current;

  factory DeviceSession.fromJson(Json j) => DeviceSession(
        (j['id'] as num?)?.toInt() ?? 0,
        (j['device_name'] as String?) ?? '',
        (j['last_seen'] as String?) ?? '',
        j['current'] == true,
      );
}
