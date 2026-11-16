import '../core/l10n/locale_controller.dart';
import '../core/net/api_client.dart';
import 'models.dart';

/// Catalog reads. The whole product list comes in one go (≤200 per page)
/// and is filtered on the phone — the same "one request + client filter"
/// the Mini App uses — and kept for two minutes.
class CatalogRepository {
  CatalogRepository(this._api, this._locale);

  final ApiClient _api;
  final LocaleController _locale;

  static const _ttl = Duration(minutes: 2);
  List<Product>? _all;
  DateTime _allAt = DateTime.fromMillisecondsSinceEpoch(0);
  Future<List<Product>>? _allLoading;
  List<Category>? _categories;

  void invalidate() {
    _all = null;
    _categories = null;
  }

  Future<List<Category>> categories({bool force = false}) async {
    if (!force && _categories != null) return _categories!;
    final results = await Future.wait([_api.get('/api/categories'), _api.get('/api/category-tiles')]);
    final names = (results[0] as List?)?.whereType<Json>() ?? const <Json>[];
    final tiles = (results[1] as Json?) ?? const {};
    final perCategory = (tiles['categories'] as Json?) ?? const {};
    final discounts = (tiles['discounts'] as Json?) ?? const {};
    Category build(String key, String name, Json? tile) => Category(
          key: key,
          name: _locale.display(name),
          count: (tile?['count'] as num?)?.toInt() ?? 0,
          photoUrl: tile?['photo_url'] as String?,
        );
    return _categories = [
      if (((discounts['count'] as num?) ?? 0) > 0) build('discounts', _locale.t('cat_discounts'), discounts),
      for (final c in names)
        if ((((perCategory[c['key']] as Json?)?['count'] as num?) ?? 1) > 0)
          build(c['key']! as String, (c['name'] as String?) ?? '', perCategory[c['key']] as Json?),
    ];
  }

  Future<List<Product>> allProducts({bool force = false}) {
    final fresh = _all != null && DateTime.now().difference(_allAt) < _ttl;
    if (!force && fresh) return Future.value(_all!);
    return _allLoading ??= _loadAll().whenComplete(() => _allLoading = null);
  }

  Future<List<Product>> _loadAll() async {
    final out = <Product>[];
    for (var page = 0; page < 50; page++) {
      final j = (await _api.get('/api/products', query: {'page': '$page', 'per_page': '200'}))! as Json;
      out.addAll(((j['products'] as List?) ?? const []).whereType<Json>().map((p) => Product.fromJson(p, _locale.display)));
      if (page + 1 >= ((j['pages'] as num?) ?? 0)) break;
    }
    _allAt = DateTime.now();
    return _all = out;
  }

  /// '' = everything; 'discounts' and 'sets' are server-side pseudo-categories.
  Future<List<Product>> productsIn(String category, {bool force = false}) async {
    if (category == 'discounts' || category == 'sets') {
      final j = (await _api.get('/api/products', query: {'category': category, 'per_page': '200'}))! as Json;
      return ((j['products'] as List?) ?? const []).whereType<Json>().map((p) => Product.fromJson(p, _locale.display)).toList();
    }
    final all = await allProducts(force: force);
    return category.isEmpty ? all : all.where((p) => p.category == category).toList();
  }

  Future<ProductDetail> detail(Product p) async {
    final j = (await _api.get(p.isSet ? '/api/set/${p.id}' : '/api/product/${p.id}'))! as Json;
    return ProductDetail.fromJson({...j, if (p.isSet) 'is_set': true}, _locale.display);
  }

  Future<List<Product>> search(String query) async {
    final j = await _api.get('/api/search', query: {'q': query});
    return ((j as List?) ?? const []).whereType<Json>().map((p) => Product.fromJson(p, _locale.display)).toList();
  }

  /// 'added' | 'already' | 'in_stock'
  Future<String> waitForRestock(Product p) async {
    final j = (await _api.post('/api/restock-wait', json: p.isSet ? {'set_id': p.id} : {'product_id': p.id}))! as Json;
    return (j['status'] as String?) ?? 'added';
  }
}
