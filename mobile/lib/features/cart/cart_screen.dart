import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../core/format.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';
import '../checkout/checkout_screen.dart';
import '../shell/home_shell.dart';

class CartScreen extends StatefulWidget {
  const CartScreen({super.key});

  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  Object? _error;
  final _busyLines = <int>{};

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
  }

  Future<void> _refresh() async {
    try {
      await context.services.cart.refresh();
      if (mounted && _error != null) setState(() => _error = null);
    } on Object catch (e) {
      if (!mounted) return;
      showError(context, e);
      setState(() => _error = e);
    }
  }

  Future<void> _change(CartLine line, num quantity) async {
    final cart = context.services.cart;
    setState(() => _busyLines.add(line.cartId));
    await runGuarded(context, () async {
      if (quantity <= 0) return cart.remove(line);
      final limit = await cart.setQuantity(line, quantity);
      if (limit != null && mounted) showSnack(context, context.t('exceeds_stock', {'n': quantityText(limit)}), error: true);
    });
    if (mounted) setState(() => _busyLines.remove(line.cartId));
  }

  Future<void> _clear() async {
    if (!await confirm(context, context.t('cart_clear_q')) || !mounted) return;
    await runGuarded(context, context.services.cart.clear);
  }

  @override
  Widget build(BuildContext context) {
    final controller = context.services.cart;
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final cart = controller.cart;
        return Scaffold(
          appBar: AppBar(title: Text(context.t('nav_cart')), actions: [
            if (cart.lines.isNotEmpty)
              IconButton(tooltip: context.t('cart_clear'), onPressed: _clear, icon: const Icon(Icons.delete_sweep_outlined)),
          ]),
          body: !controller.loaded
              ? (_error != null
                  ? ErrorPanel(message: errorText(context, _error!), onRetry: _refresh)
                  : const Center(child: CircularProgressIndicator()))
              : cart.lines.isEmpty
                  ? EmptyPanel(
                      icon: Icons.shopping_cart_outlined,
                      title: context.t('cart_empty'),
                      subtitle: context.t('cart_empty_hint'),
                      action: OutlinedButton(
                        onPressed: () => HomeShell.go(context, HomeTab.catalog),
                        child: Text(context.t('cart_go_catalog')),
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _refresh,
                      child: ListView(padding: const EdgeInsets.all(Tokens.pad), children: [
                        for (final line in cart.lines) ...[
                          _LineCard(line: line, busy: _busyLines.contains(line.cartId), onChange: (q) => _change(line, q)),
                          const SizedBox(height: Tokens.gap),
                        ],
                        if (cart.bonuses.isNotEmpty) _Bonuses(bonuses: cart.bonuses),
                        for (final hint in cart.hints)
                          Padding(
                            padding: const EdgeInsets.only(top: Tokens.gap),
                            child: Text(hint, style: Theme.of(context).textTheme.bodySmall),
                          ),
                        const SizedBox(height: Tokens.pad),
                        _Totals(cart: cart),
                      ]),
                    ),
          bottomNavigationBar: controller.loaded && cart.lines.isNotEmpty
              ? SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(Tokens.pad, 0, Tokens.pad, Tokens.gap),
                    child: FilledButton(
                      onPressed: () => Navigator.of(context)
                          .push(MaterialPageRoute<void>(builder: (_) => const CheckoutScreen())),
                      child: Text('${context.t('cart_checkout')} · ${groupThousands(cart.payTotal)} ${context.t('soum')}'),
                    ),
                  ),
                )
              : null,
        );
      },
    );
  }
}

class _LineCard extends StatelessWidget {
  const _LineCard({required this.line, required this.busy, required this.onChange});
  final CartLine line;
  final bool busy;
  final ValueChanged<num> onChange;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Row(children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(Tokens.radiusSmall),
            child: SizedBox.square(dimension: 64, child: NetPhoto(url: line.photoUrl, decodeWidth: 200)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(line.name, maxLines: 2, overflow: TextOverflow.ellipsis, style: theme.textTheme.bodyMedium),
              const SizedBox(height: 4),
              PriceText(price: line.total, original: line.originalPrice > line.price ? line.originalPrice * line.quantity : null),
              Text('${groupThousands(line.price)} × ${quantityText(line.quantity)} ${line.unit}', style: theme.textTheme.bodySmall),
            ]),
          ),
          QuantityStepper(quantity: line.quantity, busy: busy, onChanged: onChange),
        ]),
      ),
    );
  }
}

class _Bonuses extends StatelessWidget {
  const _Bonuses({required this.bonuses});
  final List<CartBonus> bonuses;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(Tokens.pad),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(context.t('cart_bonuses'), style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: Tokens.gap),
            for (final b in bonuses)
              Text('• ${b.amount} ${b.unit} ${b.name}${b.value > 0 ? ' (${groupThousands(b.value)} ${context.t('soum')})' : ''}'),
          ]),
        ),
      );
}

class _Totals extends StatelessWidget {
  const _Totals({required this.cart});
  final Cart cart;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    String money(num v) => '${groupThousands(v)} ${context.t('soum')}';
    return Column(children: [
      _row(context.t('cart_total'), money(cart.total), theme.textTheme.bodyLarge),
      if (cart.discountAmount > 0)
        _row(cart.discountLabel.isEmpty ? context.t('discount_line') : cart.discountLabel, '−${money(cart.discountAmount)}',
            theme.textTheme.bodyLarge?.copyWith(color: Tokens.sale)),
      const Divider(),
      _row(context.t('to_pay'), money(cart.payTotal), theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
    ]);
  }

  Widget _row(String label, String value, TextStyle? style) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(children: [Expanded(child: Text(label, style: style)), Text(value, style: style)]),
      );
}
