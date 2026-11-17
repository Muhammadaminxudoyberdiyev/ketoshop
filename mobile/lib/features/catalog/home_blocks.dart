import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../core/remote/remote_config.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';
import 'product_tile.dart';

/// The server-driven top of the catalog (app_config.py): aksiya, discount
/// and delivery notices, and whatever the shop adds — no APK update needed.
class HomeBlocksView extends StatelessWidget {
  const HomeBlocksView({super.key, required this.blocks, required this.onCategory});
  final List<HomeBlock> blocks;
  final ValueChanged<String> onCategory;

  @override
  Widget build(BuildContext context) {
    if (blocks.isEmpty) return const SizedBox.shrink();
    final display = context.services.locale.display;
    return Padding(
      padding: const EdgeInsets.fromLTRB(Tokens.pad, Tokens.gap, Tokens.pad, 0),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        for (final b in blocks)
          Padding(
            padding: const EdgeInsets.only(bottom: Tokens.gap),
            child: switch (b.type) {
              'banner' => _Banner(block: b, display: display),
              'notice' => _Notice(block: b, display: display),
              'link' => OutlinedButton.icon(
                  onPressed: () => context.services.native.openUrl(b.text('url')),
                  icon: const Icon(Icons.open_in_new),
                  label: Text(display(b.text('text'))),
                ),
              'category' => Align(
                  alignment: Alignment.centerLeft,
                  child: ActionChip(
                    avatar: const Icon(Icons.grid_view_rounded, size: 18),
                    label: Text(display(b.text('text'))),
                    onPressed: () => onCategory(b.text('category')),
                  ),
                ),
              'products' => _ProductRow(block: b, display: display),
              _ => const SizedBox.shrink(),
            },
          ),
      ]),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.block, required this.display});
  final HomeBlock block;
  final String Function(String) display;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final link = block.optional('link');
    final image = block.optional('image_url');
    final badge = block.optional('badge');
    return Card(
      color: theme.colorScheme.primaryContainer,
      child: InkWell(
        onTap: link == null ? null : () => context.services.native.openUrl(link),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (image != null) AspectRatio(aspectRatio: 2.2, child: NetPhoto(url: image, decodeWidth: 900)),
          Padding(
            padding: const EdgeInsets.all(Tokens.pad),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text(display(block.text('title')), style: theme.textTheme.titleMedium)),
                if (badge != null) Chip(label: Text(badge), visualDensity: VisualDensity.compact),
              ]),
              if (block.text('text').isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(display(block.text('text'))),
              ],
            ]),
          ),
        ]),
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  const _Notice({required this.block, required this.display});
  final HomeBlock block;
  final String Function(String) display;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final color = switch (block.text('tone')) {
      'success' => Tokens.success,
      'warning' => Tokens.accent,
      _ => scheme.primary,
    };
    return DecoratedBox(
      decoration: BoxDecoration(color: color.withValues(alpha: 0.10), borderRadius: BorderRadius.circular(Tokens.radiusSmall)),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: Tokens.pad, vertical: 10),
        child: Text(display(block.text('text'))),
      ),
    );
  }
}

class _ProductRow extends StatefulWidget {
  const _ProductRow({required this.block, required this.display});
  final HomeBlock block;
  final String Function(String) display;

  @override
  State<_ProductRow> createState() => _ProductRowState();
}

class _ProductRowState extends State<_ProductRow> {
  late final Future<List<Product>> _all = context.services.catalog.allProducts();

  @override
  Widget build(BuildContext context) {
    final block = widget.block;
    final display = widget.display;
    final ids = block.productIds;
    return FutureBuilder<List<Product>>(
      future: _all,
      builder: (context, snap) {
        final byId = {for (final p in snap.data ?? const <Product>[]) p.id: p};
        final products = [for (final id in ids) if (byId[id] != null) byId[id]!];
        if (products.isEmpty) return const SizedBox.shrink();
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (block.text('title').isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: Tokens.gap),
              child: Text(display(block.text('title')), style: Theme.of(context).textTheme.titleMedium),
            ),
          SizedBox(
            height: 280,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: products.length,
              separatorBuilder: (_, __) => const SizedBox(width: Tokens.gap),
              itemBuilder: (context, i) => SizedBox(width: 170, child: ProductTile(product: products[i])),
            ),
          ),
        ]);
      },
    );
  }
}
