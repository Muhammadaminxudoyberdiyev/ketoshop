import 'package:flutter_test/flutter_test.dart';
import 'package:ketoshop/core/auth/session_store.dart';
import 'package:ketoshop/data/models.dart';

String same(String s) => s;

void main() {
  test('cart: an admin preview discount is not taken off', () {
    final base = {
      'items': [
        {'cart_id': 1, 'product_id': 7, 'name': 'Bodom uni', 'price': 90000, 'original_price': 100000,
          'discount_percent': 10, 'quantity': 2, 'unit': 'dona', 'available': 5, 'total': 180000},
      ],
      'total': 180000,
      'bonuses': [
        {'name': 'Eritritol', 'amount': '100', 'unit': 'g', 'value': 15000},
      ],
      'gift_hint': '',
      'mystery_hint': "Yana 220 000 so'm — sovg'a",
    };
    final applied = Cart.fromJson({...base, 'bot_discount': {'amount': 18000, 'pay_total': 162000, 'label': '-10%', 'preview': false}}, same);
    expect(applied.payTotal, 162000);
    expect(applied.discountAmount, 18000);
    final preview = Cart.fromJson({...base, 'bot_discount': {'amount': 18000, 'pay_total': 162000, 'preview': true}}, same);
    expect(preview.payTotal, 180000);
    expect(preview.discountAmount, 0);
    expect(applied.hints, ["Yana 220 000 so'm — sovg'a"]);
    expect(applied.quantityOf(7), 2);
    expect(applied.bonuses.single.value, 15000);
  });

  test('odd or missing fields never throw', () {
    final p = Product.fromJson({'id': '12', 'price': '1500', 'name': null, 'is_set': 'yes'}, same);
    expect(p.id, 12);
    expect(p.price, 1500);
    expect(p.name, '');
    expect(p.isSet, isFalse);
    expect(Cart.fromJson(const {}, same).lines, isEmpty);
    expect(Order.fromJson({'items': 'junk'}, same).items, isEmpty);
  });

  test('checkout body: pickup sends no location', () {
    const pickup = CheckoutRequest(phone: '+998901234567', deliveryMethod: 'pickup', paymentMethod: 'cash');
    expect(pickup.toJson()['latitude'], isNull);
    expect(pickup.toJson()['address'], '');
    const courier = CheckoutRequest(
        phone: '+998901234567', deliveryMethod: 'self', paymentMethod: 'online', lat: 41.3111, lng: 69.2797, ketoRedeem: 500);
    final json = courier.toJson();
    expect(json['address'], '📍 41.311100, 69.279700');
    expect(json['keto_redeem'], 500);
  });

  test('session survives storage', () {
    final s = Session(
      accessToken: 'ksa_x',
      refreshToken: 'ksr_y',
      accessExpiresAt: DateTime.fromMillisecondsSinceEpoch(1700000000000),
      userId: 42,
      firstName: 'Ali',
    );
    final back = Session.fromJson(s.toJson())!;
    expect((back.accessToken, back.refreshToken, back.userId, back.firstName), ('ksa_x', 'ksr_y', 42, 'Ali'));
    expect(Session.fromJson({'a': 1}), isNull);
  });
}
