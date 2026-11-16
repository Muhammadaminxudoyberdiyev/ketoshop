/// Plain, immutable shapes of what /api/* returns. Parsing is defensive:
/// a missing or oddly typed field becomes a neutral value, never a crash.
typedef Json = Map<String, Object?>;
typedef Display = String Function(String);

num _num(Object? v) => v is num ? v : (v is String ? num.tryParse(v) ?? 0 : 0);
int _int(Object? v) => _num(v).toInt();
String _str(Object? v) => v is String ? v : (v == null ? '' : '$v');
String? _strOrNull(Object? v) => v is String && v.isNotEmpty ? v : null;
bool _bool(Object? v) => v == true;
List<Json> _list(Object? v) => v is List ? v.whereType<Json>().toList() : const [];

class Category {
  const Category({required this.key, required this.name, this.count = 0, this.photoUrl});
  final String key;
  final String name;
  final int count;
  final String? photoUrl;
}

class Product {
  const Product({
    required this.id,
    required this.name,
    required this.price,
    required this.originalPrice,
    required this.discountPercent,
    required this.unit,
    required this.category,
    required this.outOfStock,
    required this.heldOut,
    required this.isSet,
    this.photoUrl,
    this.bonus,
    this.description = '',
    this.near = false,
  });

  final int id;
  final String name;
  final num price;
  final num originalPrice;
  final num discountPercent;
  final String unit;
  final String category;
  final bool outOfStock;
  final bool heldOut;
  final bool isSet;
  final String? photoUrl;
  final String? bonus;
  final String description;

  /// A search suggestion, not a match.
  final bool near;

  bool get discounted => discountPercent > 0 && originalPrice > price;

  factory Product.fromJson(Json j, Display d) => Product(
        id: _int(j['id']),
        name: d(_str(j['name'])),
        price: _num(j['price']),
        originalPrice: _num(j['original_price'] ?? j['price']),
        discountPercent: _num(j['discount_percent']),
        unit: d(_str(j['unit'])),
        category: _str(j['category']),
        outOfStock: _bool(j['out_of_stock']),
        heldOut: _bool(j['held_out']),
        isSet: _bool(j['is_set']),
        photoUrl: _strOrNull(j['photo_url']),
        bonus: _strOrNull(j['bonus']) == null ? null : d(_str(j['bonus'])),
        description: d(_str(j['description'])),
        near: _bool(j['near']),
      );
}

class SetItem {
  const SetItem(this.name, this.quantity, this.unit, this.outOfStock);
  final String name;
  final num quantity;
  final String unit;
  final bool outOfStock;
}

class ProductDetail {
  const ProductDetail({
    required this.product,
    required this.media,
    required this.description,
    required this.composition,
    required this.rating,
    required this.reviewCount,
    required this.restockWaiting,
    required this.setItems,
    this.tip,
  });

  final Product product;
  final List<String> media;
  final String description;
  final String composition;
  final num rating;
  final int reviewCount;
  final bool restockWaiting;
  final String? tip;
  final List<SetItem> setItems;

  factory ProductDetail.fromJson(Json j, Display d) {
    final product = Product.fromJson(j, d);
    final media = [
      for (final m in _list(j['media']))
        if (_str(m['type']) == 'photo' || _str(m['type']).isEmpty) _str(m['url']),
    ].where((u) => u.isNotEmpty).toList();
    final tip = j['tip'];
    return ProductDetail(
      product: product,
      media: media.isEmpty && product.photoUrl != null ? [product.photoUrl!] : media,
      description: d(_str(j['description'])),
      composition: d(_str(j['composition'])),
      rating: _num(j['rating']),
      reviewCount: _int(j['review_count']),
      restockWaiting: _bool(j['restock_waiting']),
      tip: tip is String && tip.isNotEmpty ? d(tip) : (tip is Json ? _strOrNull(tip['text']) : null),
      setItems: [
        for (final i in _list(j['items']))
          SetItem(d(_str(i['name'])), _num(i['quantity']), d(_str(i['unit'])), _bool(i['out_of_stock'])),
      ],
    );
  }
}

class CartLine {
  const CartLine({
    required this.cartId,
    required this.productId,
    required this.name,
    required this.price,
    required this.originalPrice,
    required this.discountPercent,
    required this.quantity,
    required this.unit,
    required this.available,
    required this.total,
    this.photoUrl,
  });

  final int cartId;
  final int? productId;
  final String name;
  final num price;
  final num originalPrice;
  final num discountPercent;
  final num quantity;
  final String unit;
  final num available;
  final num total;
  final String? photoUrl;

  factory CartLine.fromJson(Json j, Display d) => CartLine(
        cartId: _int(j['cart_id']),
        productId: j['product_id'] == null ? null : _int(j['product_id']),
        name: d(_str(j['name'])),
        price: _num(j['price']),
        originalPrice: _num(j['original_price'] ?? j['price']),
        discountPercent: _num(j['discount_percent']),
        quantity: _num(j['quantity']),
        unit: d(_str(j['unit'])),
        available: _num(j['available']),
        total: _num(j['total']),
        photoUrl: _strOrNull(j['photo_url']),
      );
}

class CartBonus {
  const CartBonus(this.name, this.amount, this.unit, this.value, this.photoUrl);
  final String name;
  final String amount;
  final String unit;
  final num value;
  final String? photoUrl;
}

class Cart {
  const Cart({
    required this.lines,
    required this.total,
    required this.payTotal,
    required this.discountAmount,
    required this.discountLabel,
    required this.bonuses,
    required this.hints,
  });

  static const empty = Cart(lines: [], total: 0, payTotal: 0, discountAmount: 0, discountLabel: '', bonuses: [], hints: []);

  final List<CartLine> lines;

  /// Shelf sum — free delivery is measured on this (server rule).
  final num total;

  /// What the goods cost after the bot/site discount.
  final num payTotal;
  final num discountAmount;
  final String discountLabel;
  final List<CartBonus> bonuses;

  /// Gift / surprise / free-delivery nudges, plain text from the server.
  final List<String> hints;

  int get count => lines.length;

  num quantityOf(int productId) =>
      lines.where((l) => l.productId == productId).fold<num>(0, (sum, l) => sum + l.quantity);

  factory Cart.fromJson(Json j, Display d) {
    final total = _num(j['total']);
    final discount = j['bot_discount'];
    final applied = discount is Json && !_bool(discount['preview']);
    return Cart(
      lines: [for (final l in _list(j['items'])) CartLine.fromJson(l, d)],
      total: total,
      payTotal: applied ? _num(discount['pay_total']) : total,
      discountAmount: applied ? _num(discount['amount']) : 0,
      discountLabel: applied ? d(_str(discount['label'])) : '',
      bonuses: [
        for (final b in _list(j['bonuses']))
          CartBonus(d(_str(b['name'])), _str(b['amount']), d(_str(b['unit'])), _num(b['value']),
              _strOrNull(b['photo_url'])),
      ],
      hints: [
        for (final key in const ['gift_hint', 'mystery_hint', 'delivery_hint'])
          if (_strOrNull(j[key]) != null) d(_str(j[key])),
      ],
    );
  }
}

class OrderItem {
  const OrderItem(this.name, this.quantity, this.unit, this.price);
  final String name;
  final num quantity;
  final String unit;
  final num price;
}

class Order {
  const Order({
    required this.id,
    required this.status,
    required this.total,
    required this.createdAt,
    required this.deliveryMethod,
    required this.paymentMethod,
    required this.address,
    required this.items,
    this.pickupMapUrl,
  });

  final int id;
  final String status;
  final num total;
  final String? createdAt;
  final String deliveryMethod;
  final String paymentMethod;
  final String address;
  final List<OrderItem> items;
  final String? pickupMapUrl;

  bool get cancellable => status == 'pending' || status == 'confirmed';
  bool get awaitsCheque => paymentMethod == 'online' && cancellable;

  factory Order.fromJson(Json j, Display d) => Order(
        id: _int(j['id']),
        status: _str(j['status']),
        total: _num(j['total']),
        createdAt: _strOrNull(j['created_at']),
        deliveryMethod: _str(j['delivery_method']),
        paymentMethod: _str(j['payment_method']),
        address: _str(j['address']),
        pickupMapUrl: _strOrNull(j['pickup_map_url']),
        items: [
          for (final i in _list(j['items']))
            OrderItem(d(_str(i['name'])), _num(i['quantity']), d(_str(i['unit'])), _num(i['price'])),
        ],
      );
}

class KetoStatus {
  const KetoStatus({required this.enabled, required this.balance, required this.rate});
  final bool enabled;
  final int balance;
  final num rate;

  factory KetoStatus.fromJson(Json j) =>
      KetoStatus(enabled: _bool(j['enabled']), balance: _int(j['balance']), rate: _num(j['rate']));
}

class PickupConfig {
  const PickupConfig({required this.enabled, required this.address, required this.mapUrl});
  final bool enabled;
  final String address;
  final String mapUrl;

  factory PickupConfig.fromJson(Json j, Display d) =>
      PickupConfig(enabled: _bool(j['enabled']), address: d(_str(j['address'])), mapUrl: _str(j['map_url']));
}

class UzpostQuote {
  const UzpostQuote({required this.fee, required this.kgText, this.officeName, this.officeAddress, this.mapUrl});
  final int fee;
  final String kgText;
  final String? officeName;
  final String? officeAddress;
  final String? mapUrl;

  factory UzpostQuote.fromJson(Json j, Display d) {
    final office = j['office'];
    final o = office is Json ? office : const <String, Object?>{};
    return UzpostQuote(
      fee: _int(j['fee']),
      kgText: _str(j['kg_text']),
      officeName: _strOrNull(o['name']) == null ? null : d(_str(o['name'])),
      officeAddress: _strOrNull(o['address']) == null ? null : d(_str(o['address'])),
      mapUrl: _strOrNull(o['map_url']),
    );
  }
}

class CheckoutRequest {
  const CheckoutRequest({
    required this.phone,
    required this.deliveryMethod,
    required this.paymentMethod,
    this.lat,
    this.lng,
    this.addressNote,
    this.ketoRedeem = 0,
  });

  final String phone;

  /// self | yandex_taxi | uzpost | bts | emu | pickup
  final String deliveryMethod;

  /// cash | online
  final String paymentMethod;
  final double? lat;
  final double? lng;
  final String? addressNote;
  final int ketoRedeem;

  bool get pickup => deliveryMethod == 'pickup';

  Json toJson() => {
        'phone': phone,
        'address': pickup ? '' : '📍 ${lat!.toStringAsFixed(6)}, ${lng!.toStringAsFixed(6)}',
        'address_note': pickup ? null : addressNote,
        'latitude': pickup ? null : lat,
        'longitude': pickup ? null : lng,
        'payment_method': paymentMethod,
        'delivery_method': deliveryMethod,
        'keto_redeem': ketoRedeem,
      };
}

class CheckoutResult {
  const CheckoutResult({
    required this.awaitingCheque,
    required this.total,
    this.orderId,
    this.paymentCard,
    this.paymentRecipient,
    this.expectedKeto = 0,
  });

  final bool awaitingCheque;
  final num total;
  final int? orderId;
  final String? paymentCard;
  final String? paymentRecipient;
  final int expectedKeto;

  factory CheckoutResult.fromJson(Json j) => CheckoutResult(
        awaitingCheque: _bool(j['awaiting_cheque']),
        total: _num(j['total']),
        orderId: j['order_id'] == null ? null : _int(j['order_id']),
        paymentCard: _strOrNull(j['payment_card']),
        paymentRecipient: _strOrNull(j['payment_recipient']),
        expectedKeto: _int(j['expected_keto']),
      );
}

class DeviceSession {
  const DeviceSession(this.id, this.deviceName, this.lastSeen, this.current);
  final int id;
  final String deviceName;
  final String lastSeen;
  final bool current;

  factory DeviceSession.fromJson(Json j) =>
      DeviceSession(_int(j['id']), _str(j['device_name']), _str(j['last_seen']), _bool(j['current']));
}
