import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../core/format.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';
import '../checkout/checkout_screen.dart';

class OrdersScreen extends StatefulWidget {
  const OrdersScreen({super.key});

  @override
  State<OrdersScreen> createState() => OrdersScreenState();
}

class OrdersScreenState extends State<OrdersScreen> {
  late Future<List<Order>> _orders = context.services.orders.orders();

  Future<void> reload() async {
    final next = context.services.orders.orders();
    setState(() => _orders = next);
    try {
      await next;
    } on Object {
      // shown in the list
    }
  }

  Future<void> _cancel(Order order) async {
    if (!await confirm(context, context.t('order_cancel_q', {'id': order.id})) || !mounted) return;
    final services = context.services;
    final done = await runGuarded(context, () async {
      await services.orders.cancel(order.id);
      return true;
    });
    if (done == true && mounted) {
      showSnack(context, context.t('order_cancelled_ok'));
      services.catalog.invalidate();
      await reload();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(context.t('nav_orders'))),
      body: RefreshIndicator(
        onRefresh: reload,
        child: FutureBuilder<List<Order>>(
          future: _orders,
          builder: (context, snap) {
            if (snap.hasError) {
              showErrorOnce(context, snap.error!);
              return ListView(children: [
                SizedBox(height: 360, child: ErrorPanel(message: errorText(context, snap.error!), onRetry: reload)),
              ]);
            }
            if (!snap.hasData) return const Center(child: CircularProgressIndicator());
            final orders = snap.data!;
            if (orders.isEmpty) {
              return ListView(children: [
                SizedBox(height: 360, child: EmptyPanel(icon: Icons.receipt_long_outlined, title: context.t('orders_empty'))),
              ]);
            }
            return ListView.separated(
              padding: const EdgeInsets.all(Tokens.pad),
              itemCount: orders.length,
              separatorBuilder: (_, __) => const SizedBox(height: Tokens.gap),
              itemBuilder: (context, i) => _OrderCard(order: orders[i], onCancel: () => _cancel(orders[i])),
            );
          },
        ),
      ),
    );
  }
}

/// The gate answer arrives as an error from the list call too.
void showErrorOnce(BuildContext context, Object error) {
  WidgetsBinding.instance.addPostFrameCallback((_) {
    if (context.mounted) showError(context, error);
  });
}

class _OrderCard extends StatelessWidget {
  const _OrderCard({required this.order, required this.onCancel});
  final Order order;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final o = order;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(Tokens.pad),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Text('#${o.id}', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(width: Tokens.gap),
            Text(orderDateText(o.createdAt), style: theme.textTheme.bodySmall),
            const Spacer(),
            _StatusChip(status: o.status, pickup: o.deliveryMethod == 'pickup'),
          ]),
          const SizedBox(height: Tokens.gap),
          for (final item in o.items)
            Text('• ${item.name} — ${quantityText(item.quantity)} ${item.unit}', style: theme.textTheme.bodyMedium),
          const SizedBox(height: Tokens.gap),
          Text('${deliveryLabel(context, o.deliveryMethod)} · ${o.paymentMethod == 'cash' ? context.t('pay_cash') : context.t('pay_online')}',
              style: theme.textTheme.bodySmall),
          if (o.address.isNotEmpty) Text(o.address, style: theme.textTheme.bodySmall, maxLines: 2, overflow: TextOverflow.ellipsis),
          const SizedBox(height: Tokens.gap),
          Row(children: [
            Expanded(child: PriceText(price: o.total)),
            if (o.pickupMapUrl != null)
              TextButton(
                onPressed: () => context.services.native.openUrl(o.pickupMapUrl!),
                child: Text(context.t('open_map')),
              ),
            if (o.cancellable) TextButton(onPressed: onCancel, child: Text(context.t('order_cancel'))),
          ]),
        ]),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status, required this.pickup});
  final String status;
  final bool pickup;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (key, color) = switch (status) {
      'pending' => ('status_pending', Tokens.accent),
      'confirmed' => ('status_confirmed', scheme.primary),
      'ready' || 'preparing' => ('status_ready', scheme.primary),
      'shipped' => ('status_shipped', scheme.tertiary),
      'delivered' => (pickup ? 'status_picked' : 'status_delivered', Tokens.success),
      'cancelled' => ('status_cancelled', scheme.error),
      _ => ('', scheme.outline),
    };
    return DecoratedBox(
      decoration: BoxDecoration(color: color.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        child: Text(key.isEmpty ? status : context.t(key), style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 12)),
      ),
    );
  }
}
