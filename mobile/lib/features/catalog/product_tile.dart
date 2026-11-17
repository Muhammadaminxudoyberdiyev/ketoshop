import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../data/cart_controller.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';
import 'product_screen.dart';

/// Puts one piece in the cart and says what happened (all, part, held by
/// other carts, sold out, a set's missing part).
Future<void> addToCart(BuildContext context, Product product) async {
  final result = await runGuarded(context, () => context.services.cart.add(product));
  if (result == null || !context.mounted) return;
  final message = switch (result) {
    Added() => context.t('added'),
    AddedPartly(:final added) => context.t('add_partial', {'n': added}),
    HeldByOthers() => context.t('add_held'),
    SoldOut() => context.t('add_oos'),
    SetPartMissing(:final names) => context.t('set_missing', {'names': names.join(', ')}),
  };
  showSnack(context, message, error: result is! Added);
}

void openProduct(BuildContext context, Product product) =>
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => ProductScreen(product: product)));

class ProductTile extends StatelessWidget {
  const ProductTile({super.key, required this.product});
  final Product product;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final p = product;
    final unavailable = p.outOfStock || p.heldOut;
    return Card(
      child: InkWell(
        onTap: () => openProduct(context, p),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          AspectRatio(
            aspectRatio: 1,
            child: Stack(fit: StackFit.expand, children: [
              NetPhoto(url: p.photoUrl, decodeWidth: 400),
              if (p.discounted)
                Positioned(left: 8, top: 8, child: _Badge(text: '−${p.discountPercent.round()}%', color: Tokens.sale)),
              if (p.bonus != null) const Positioned(right: 8, top: 8, child: _Badge(text: '🎁', color: Tokens.accent)),
              if (unavailable)
                ColoredBox(
                  color: theme.colorScheme.surface.withValues(alpha: 0.55),
                  child: Center(
                    child: _Badge(
                      text: p.heldOut ? context.t('held_out') : context.t('out_of_stock'),
                      color: theme.colorScheme.inverseSurface,
                    ),
                  ),
                ),
            ]),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(10, 8, 10, 4),
              child: Text(p.name, maxLines: 2, overflow: TextOverflow.ellipsis, style: theme.textTheme.bodyMedium),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 0, 4, 6),
            child: Row(children: [
              Expanded(child: PriceText(price: p.price, original: p.discounted ? p.originalPrice : null)),
              IconButton.filledTonal(
                visualDensity: VisualDensity.compact,
                onPressed: unavailable ? null : () => addToCart(context, p),
                icon: const Icon(Icons.add_shopping_cart_rounded, size: 20),
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.text, required this.color});
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) => DecoratedBox(
        decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(8)),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          child: Text(text, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 12)),
        ),
      );
}
