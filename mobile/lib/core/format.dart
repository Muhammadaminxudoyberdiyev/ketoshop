/// 1234567 → "1 234 567".
String groupThousands(num value) {
  final digits = value.round().abs().toString();
  final out = StringBuffer(value < 0 ? '-' : '');
  for (var i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 == 0) out.write(' ');
    out.write(digits[i]);
  }
  return out.toString();
}

/// 1.0 → "1", 0.5 → "0.5".
String quantityText(num value) =>
    value == value.roundToDouble() ? value.round().toString() : value.toString().replaceFirst(RegExp(r'0+$'), '');

const _digitBlocks = [0x0660, 0x06F0, 0xFF10];

/// Same rule as phone_utils.normalize_uz_phone on the server: "+998XXXXXXXXX"
/// or null. Arabic/Persian/full-width digits count; every other character is
/// dropped; 9 local digits, 998…, 00998…, 8…, and a doubled 998 are accepted.
String? normalizeUzPhone(String raw) {
  final buf = StringBuffer();
  for (final rune in raw.runes) {
    var code = rune;
    for (final base in _digitBlocks) {
      if (code >= base && code <= base + 9) code = 0x30 + code - base;
    }
    if (code >= 0x30 && code <= 0x39) buf.writeCharCode(code);
  }
  var digits = buf.toString();
  if (digits.startsWith('00')) digits = digits.substring(2);
  if (digits.length == 15 && digits.startsWith('998998')) digits = digits.substring(3);
  if (digits.length == 9) {
    digits = '998$digits';
  } else if (digits.length == 10 && digits.startsWith('8')) {
    digits = '998${digits.substring(1)}';
  }
  return RegExp(r'^998[2-9][0-9]{8}$').hasMatch(digits) ? '+$digits' : null;
}

/// "+998901234567" → "+998 90 123 45 67"; anything else unchanged.
String formatUzPhone(String phone) {
  final p = normalizeUzPhone(phone);
  if (p == null) return phone;
  return '${p.substring(0, 4)} ${p.substring(4, 6)} ${p.substring(6, 9)} ${p.substring(9, 11)} ${p.substring(11)}';
}

/// ISO time from the server (UTC, usually without a zone) → the phone's
/// local "16.11.2026 14:05".
String orderDateText(String? iso) {
  if (iso == null || iso.isEmpty) return '';
  final zoned = iso.endsWith('Z') || RegExp(r'[+-]\d\d:?\d\d$').hasMatch(iso) ? iso : '${iso}Z';
  final d = DateTime.tryParse(zoned)?.toLocal();
  if (d == null) return '';
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(d.day)}.${two(d.month)}.${d.year} ${two(d.hour)}:${two(d.minute)}';
}
