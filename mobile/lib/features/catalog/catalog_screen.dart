import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';
import 'home_blocks.dart';
import 'product_tile.dart';

class CatalogScreen extends StatefulWidget {
  const CatalogScreen({super.key});

  @override
  State<CatalogScreen> createState() => _CatalogScreenState();
}

class _CatalogScreenState extends State<CatalogScreen> {
  late Future<List<Category>> _categories = context.services.catalog.categories();
  String _category = '';
  late Future<List<Product>> _products = _load();

  Future<List<Product>> _load({bool force = false}) => context.services.catalog.productsIn(_category, force: force);

  void _pick(String key) {
    if (key == _category) return;
    setState(() {
      _category = key;
      _products = _load();
    });
  }

  Future<void> _refresh() async {
    final catalog = context.services.catalog;
    unawaited(context.services.remote.refresh(force: true));
    final products = _load(force: true);
    setState(() {
      _categories = catalog.categories(force: true);
      _products = products;
    });
    try {
      await products;
    } on Object {
      // the grid shows the error
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Ketoshop')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: CustomScrollView(slivers: [
          SliverToBoxAdapter(
            child: ListenableBuilder(
              listenable: context.services.remote,
              builder: (context, _) => HomeBlocksView(
                blocks: context.services.remote.config.home,
                onCategory: _pick,
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: SizedBox(
              height: 56,
              child: FutureBuilder<List<Category>>(
                future: _categories,
                builder: (context, snap) => ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: Tokens.pad, vertical: Tokens.gap),
                  children: [
                    _chip(context.t('cat_all'), ''),
                    for (final c in snap.data ?? const <Category>[]) _chip(c.name, c.key),
                  ],
                ),
              ),
            ),
          ),
          FutureBuilder<List<Product>>(
            future: _products,
            builder: (context, snap) {
              if (snap.hasError) {
                return SliverFillRemaining(
                  hasScrollBody: false,
                  child: ErrorPanel(message: errorText(context, snap.error!), onRetry: _refresh),
                );
              }
              if (!snap.hasData) {
                return const SliverFillRemaining(hasScrollBody: false, child: Center(child: CircularProgressIndicator()));
              }
              final products = snap.data!;
              if (products.isEmpty) {
                return SliverFillRemaining(
                  hasScrollBody: false,
                  child: EmptyPanel(icon: Icons.inventory_2_outlined, title: context.t('empty_catalog')),
                );
              }
              return SliverPadding(
                padding: const EdgeInsets.fromLTRB(Tokens.pad, 0, Tokens.pad, Tokens.pad),
                sliver: SliverGrid.builder(
                  gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                    maxCrossAxisExtent: 220,
                    mainAxisSpacing: Tokens.gap * 1.5,
                    crossAxisSpacing: Tokens.gap * 1.5,
                    childAspectRatio: Tokens.tileAspect,
                  ),
                  itemCount: products.length,
                  itemBuilder: (context, i) => ProductTile(product: products[i]),
                ),
              );
            },
          ),
        ]),
      ),
    );
  }

  Widget _chip(String label, String key) => Padding(
        padding: const EdgeInsets.only(right: Tokens.gap),
        child: ChoiceChip(label: Text(label), selected: _category == key, onSelected: (_) => _pick(key)),
      );
}
