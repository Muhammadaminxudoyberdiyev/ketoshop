/// ISO time from the server (UTC, usually without a zone) → the phone's
/// local "16.11.2026 14:05".
String dateText(String? iso) {
  if (iso == null || iso.isEmpty) return '';
  final zoned = iso.endsWith('Z') || RegExp(r'[+-]\d\d:?\d\d$').hasMatch(iso) ? iso : '${iso}Z';
  final d = DateTime.tryParse(zoned)?.toLocal();
  if (d == null) return '';
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(d.day)}.${two(d.month)}.${d.year} ${two(d.hour)}:${two(d.minute)}';
}
