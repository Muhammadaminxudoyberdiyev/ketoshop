import 'package:flutter_test/flutter_test.dart';
import 'package:ketoshop/core/format.dart';

void main() {
  test('server times are UTC, shown in the phone\'s zone', () {
    final local = DateTime.utc(2026, 11, 16, 9, 5).toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    final want = '${two(local.day)}.${two(local.month)}.${local.year} ${two(local.hour)}:${two(local.minute)}';
    expect(dateText('2026-11-16T09:05:00'), want);
    expect(dateText('2026-11-16T09:05:00+00:00'), want);
    expect(dateText(null), '');
    expect(dateText('nonsense'), '');
  });
}
