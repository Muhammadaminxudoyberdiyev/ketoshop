import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../core/format.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';
import 'product_tile.dart';

class ProductScreen extends StatelessWidget {
  const ProductScreen({super.key, required this.product});
  final Product product;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(product.name, maxLines: 1, overflow: TextOverflow.ellipsis)),
      body: AsyncView<ProductDetail>(
        load: () => context.services.catalog.detail(product),
        builder: (context, detail, reload) => _Body(detail: detail, reload: reload),
      ),
    );
  }
}

class _Body extends StatelessWidget {
  const _Body({required this.detail, required this.reload});
  final ProductDetail detail;
  final Future<void> Function() reload;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final p = detail.product;
    return Column(children: [
      Expanded(
        child: ListView(padding: EdgeInsets.zero, children: [
          _Gallery(urls: detail.media),
          Padding(
            padding: const EdgeInsets.all(Tokens.pad),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(p.name, style: theme.textTheme.titleLarge),
              const SizedBox(height: Tokens.gap),
              Row(children: [
                Expanded(child: PriceText(price: p.price, original: p.discounted ? p.originalPrice : null, large: true)),
                Text('/ ${p.unit}', style: theme.textTheme.bodyMedium),
              ]),
              if (detail.reviewCount > 0) ...[
                const SizedBox(height: 4),
                Text('★ ${detail.rating.toStringAsFixed(1)} · ${context.t('reviews', {'n': detail.reviewCount})}',
                    style: theme.textTheme.bodySmall),
              ],
              if (p.bonus != null) ...[
                const SizedBox(height: Tokens.gap),
                Text('🎁 ${p.bonus}', style: theme.textTheme.bodyMedium?.copyWith(color: Tokens.accent)),
              ],
              if (detail.tip != null) ...[
                const SizedBox(height: Tokens.pad),
                Card(child: Padding(padding: const EdgeInsets.all(Tokens.pad), child: Text('💡 ${detail.tip}'))),
              ],
              if (detail.setItems.isNotEmpty) ...[
                _Heading(context.t('set_items')),
                for (final item in detail.setItems)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Text(
                      '${item.outOfStock ? '❌' : '•'} ${item.name} — ${quantityText(item.quantity)} ${item.unit}',
                      style: item.outOfStock ? TextStyle(color: theme.colorScheme.error) : null,
                    ),
                  ),
              ],
              if (detail.description.isNotEmpty) ...[_Heading(context.t('description')), Text(detail.description)],
              if (detail.composition.isNotEmpty) ...[_Heading(context.t('composition')), Text(detail.composition)],
            ]),
          ),
        ]),
      ),
      SafeArea(
        top: false,
        child: Padding(padding: const EdgeInsets.all(Tokens.pad), child: _BuyBar(detail: detail, reload: reload)),
      ),
    ]);
  }
}

class _Heading extends StatelessWidget {
  const _Heading(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: Tokens.pad * 1.25, bottom: Tokens.gap),
        child: Text(text, style: Theme.of(context).textTheme.titleMedium),
      );
}

class _Gallery extends StatefulWidget {
  const _Gallery({required this.urls});
  final List<String> urls;

  @override
  State<_Gallery> createState() => _GalleryState();
}

class _GalleryState extends State<_Gallery> {
  int _page = 0;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final decode = (width * MediaQuery.devicePixelRatioOf(context)).round().clamp(400, 1440);
    final urls = widget.urls;
    return AspectRatio(
      aspectRatio: 1,
      child: Stack(children: [
        if (urls.isEmpty)
          const Positioned.fill(child: NetPhoto(url: null))
        else
          PageView.builder(
            itemCount: urls.length,
            onPageChanged: (i) => setState(() => _page = i),
            itemBuilder: (context, i) => NetPhoto(url: urls[i], decodeWidth: decode),
          ),
        if (urls.length > 1)
          Positioned(
            bottom: 10,
            left: 0,
            right: 0,
            child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              for (var i = 0; i < urls.length; i++)
                AnimatedContainer(
                  duration: Tokens.fast,
                  margin: const EdgeInsets.symmetric(horizontal: 3),
                  width: i == _page ? 18 : 7,
                  height: 7,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: i == _page ? 0.95 : 0.6),
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
            ]),
          ),
      ]),
    );
  }
}

class _BuyBar extends StatefulWidget {
  const _BuyBar({required this.detail, required this.reload});
  final ProductDetail detail;
  final Future<void> Function() reload;

  @override
  State<_BuyBar> createState() => _BuyBarState();
}

class _BuyBarState extends State<_BuyBar> {
  bool _busy = false;

  Future<void> _waitForRestock() async {
    final status = await runGuarded(context, () => context.services.catalog.waitForRestock(widget.detail.product),
        busy: (b) => setState(() => _busy = b));
    if (status == null || !mounted) return;
    showSnack(context, context.t(status == 'already' ? 'restock_already' : 'restock_added'));
    await widget.reload();
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.detail.product;
    if (p.outOfStock || p.heldOut) {
      if (!context.services.remote.config.enabled('restock_wait')) {
        return FilledButton.tonal(onPressed: null, child: Text(context.t(p.heldOut ? 'held_out' : 'out_of_stock')));
      }
      return FilledButton.tonal(
        onPressed: _busy || widget.detail.restockWaiting ? null : _waitForRestock,
        child: Text(widget.detail.restockWaiting ? context.t('restock_already') : context.t('notify_restock')),
      );
    }
    final cart = context.services.cart;
    return ListenableBuilder(
      listenable: cart,
      builder: (context, _) {
        final lines = p.isSet ? const <CartLine>[] : cart.cart.lines.where((l) => l.productId == p.id).toList();
        if (lines.isEmpty) {
          return FilledButton.icon(
            onPressed: _busy
                ? null
                : () async {
                    setState(() => _busy = true);
                    await addToCart(context, p);
                    if (mounted) setState(() => _busy = false);
                  },
            icon: const Icon(Icons.add_shopping_cart_rounded),
            label: Text(context.t('add_to_cart')),
          );
        }
        final line = lines.first;
        return Row(children: [
          Expanded(child: Text(context.t('in_cart', {'n': quantityText(line.quantity)}),
              style: Theme.of(context).textTheme.titleMedium)),
          QuantityStepper(
            quantity: line.quantity,
            busy: _busy,
            onChanged: (q) => runGuarded(context, () async {
              if (q <= 0) return cart.remove(line);
              final limit = await cart.setQuantity(line, q);
              if (limit != null && context.mounted) {
                showSnack(context, context.t('exceeds_stock', {'n': quantityText(limit)}), error: true);
              }
            }, busy: (b) => setState(() => _busy = b)),
          ),
        ]);
      },
    );
  }
}
