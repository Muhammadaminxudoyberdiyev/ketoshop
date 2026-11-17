import 'package:flutter/foundation.dart';

import '../core/l10n/locale_controller.dart';
import '../core/net/api_client.dart';
import 'models.dart';

sealed class AddResult {
  const AddResult();
}

class Added extends AddResult {
  const Added();
}

class AddedPartly extends AddResult {
  const AddedPartly(this.added);
  final num added;
}

/// The rest sits in other buyers' carts (Savat broni); the server put the
/// buyer on its waitlist.
class HeldByOthers extends AddResult {
  const HeldByOthers();
}

class SoldOut extends AddResult {
  const SoldOut();
}

class SetPartMissing extends AddResult {
  const SetPartMissing(this.names);
  final List<String> names;
}

/// The cart is server state (it holds stock for the buyer); this mirrors it
/// and re-reads it after every change so prices and gifts are the server's.
class CartController extends ChangeNotifier {
  CartController(this._api, this._locale);

  final ApiClient _api;
  final LocaleController _locale;

  Cart _cart = Cart.empty;
  Cart get cart => _cart;
  bool _loaded = false;
  bool get loaded => _loaded;

  Future<void> refresh() async {
    final j = (await _api.get('/api/cart'))! as Json;
    _cart = Cart.fromJson(j, _locale.display);
    _loaded = true;
    notifyListeners();
  }

  void reset() {
    _cart = Cart.empty;
    _loaded = false;
    notifyListeners();
  }

  Future<AddResult> add(Product p, {num quantity = 1}) async {
    try {
      final j = (await _api.post('/api/cart/add', json: {
        if (p.isSet) 'set_id': p.id else 'product_id': p.id,
        'quantity': quantity,
      }))! as Json;
      await refresh();
      return j['partial'] == true ? AddedPartly((j['added'] as num?) ?? 0) : const Added();
    } on ApiException catch (e) {
      if (e.status != 409 && e.code != 'out_of_stock') rethrow;
      final missing = (e.body['missing'] as List?)?.whereType<String>().map(_locale.display).toList();
      if (missing != null && missing.isNotEmpty) return SetPartMissing(missing);
      return e.code == 'held' ? const HeldByOthers() : const SoldOut();
    }
  }

  /// null when it went through; otherwise how many may be taken.
  Future<num?> setQuantity(CartLine line, num quantity) async {
    try {
      final j = (await _api.post('/api/cart/update', json: {'cart_id': line.cartId, 'quantity': quantity}))! as Json;
      await refresh();
      final got = j['quantity'] as num?;
      return got != null && got < quantity ? got : null;
    } on ApiException catch (e) {
      if (e.status == 400 && (e.code == 'exceeds_stock' || e.code == 'held')) {
        await refresh();
        return (e.body['available'] as num?) ?? 0;
      }
      rethrow;
    }
  }

  Future<void> remove(CartLine line) async {
    await _api.post('/api/cart/remove', json: {'cart_id': line.cartId});
    await refresh();
  }

  Future<void> clear() async {
    await _api.post('/api/cart/clear');
    await refresh();
  }
}
