import 'package:flutter_test/flutter_test.dart';
import 'package:ketoshop/core/format.dart';

void main() {
  test('phone numbers the way buyers type them (phone_utils.py rule)', () {
    const ok = {
      '+998901234567': '+998901234567',
      '90 123 45 67': '+998901234567',
      '+998 (90) 123-45-67': '+998901234567',
      '8 90 1234567': '+998901234567',
      '00998901234567': '+998901234567',
      '+998 +998 90 123 45 67': '+998901234567',
      '٩٠١٢٣٤٥٦٧': '+998901234567',
      '９０１２３４５６７': '+998901234567',
    };
    ok.forEach((raw, want) => expect(normalizeUzPhone(raw), want, reason: raw));
    for (final bad in ['123456789', '+7 901 234 56 78', '90123', '', '+998 10 123 45 67']) {
      expect(normalizeUzPhone(bad), isNull, reason: bad);
    }
    expect(formatUzPhone('901234567'), '+998 90 123 45 67');
    expect(formatUzPhone('abc'), 'abc');
  });

  test('money and quantities', () {
    expect(groupThousands(0), '0');
    expect(groupThousands(25000), '25 000');
    expect(groupThousands(1234567.4), '1 234 567');
    expect(groupThousands(-800000), '-800 000');
    expect(quantityText(2.0), '2');
    expect(quantityText(0.5), '0.5');
  });

  test('server times are UTC', () {
    final local = DateTime.utc(2026, 11, 16, 9, 5).toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    expect(orderDateText('2026-11-16T09:05:00'),
        '${two(local.day)}.${two(local.month)}.${local.year} ${two(local.hour)}:${two(local.minute)}');
    expect(orderDateText(null), '');
    expect(orderDateText('nonsense'), '');
  });
}
