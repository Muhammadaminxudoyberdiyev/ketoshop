import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';
import '../catalog/product_tile.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _controller = TextEditingController();
  final _debounce = Debouncer(const Duration(milliseconds: 350));
  Future<List<Product>>? _results;
  String _query = '';

  @override
  void dispose() {
    _debounce.dispose();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String text) {
    final q = text.trim();
    _debounce(() {
      if (!mounted || q == _query) return;
      setState(() {
        _query = q;
        _results = q.length < 2 ? null : context.services.catalog.search(q);
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: TextField(
          controller: _controller,
          onChanged: _onChanged,
          textInputAction: TextInputAction.search,
          decoration: InputDecoration(
            hintText: context.t('search_hint'),
            prefixIcon: const Icon(Icons.search),
            isDense: true,
          ),
        ),
      ),
      body: _results == null
          ? EmptyPanel(icon: Icons.search, title: context.t('search_min'))
          : FutureBuilder<List<Product>>(
              future: _results,
              builder: (context, snap) {
                if (snap.hasError) {
                  return ErrorPanel(
                    message: errorText(context, snap.error!),
                    onRetry: () => setState(() => _results = context.services.catalog.search(_query)),
                  );
                }
                if (!snap.hasData) return const Center(child: CircularProgressIndicator());
                final items = snap.data!;
                if (items.isEmpty) return EmptyPanel(icon: Icons.search_off, title: context.t('search_none'));
                final near = items.every((p) => p.near);
                return ListView.separated(
                  padding: const EdgeInsets.all(Tokens.pad),
                  itemCount: items.length + (near ? 1 : 0),
                  separatorBuilder: (_, __) => const SizedBox(height: Tokens.gap),
                  itemBuilder: (context, i) {
                    if (near && i == 0) return Text(context.t('search_near'), style: Theme.of(context).textTheme.titleSmall);
                    final p = items[near ? i - 1 : i];
                    return Card(
                      child: ListTile(
                        leading: ClipRRect(
                          borderRadius: BorderRadius.circular(Tokens.radiusSmall),
                          child: SizedBox.square(dimension: 52, child: NetPhoto(url: p.photoUrl, decodeWidth: 160)),
                        ),
                        title: Text(p.name, maxLines: 2, overflow: TextOverflow.ellipsis),
                        subtitle: PriceText(price: p.price, original: p.discounted ? p.originalPrice : null),
                        onTap: () => openProduct(context, p),
                      ),
                    );
                  },
                );
              },
            ),
    );
  }
}
