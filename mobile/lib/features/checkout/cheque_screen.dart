import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../core/config.dart';
import '../../core/format.dart';
import '../../core/net/api_client.dart';
import '../../core/platform/native_bridge.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';
import 'checkout_screen.dart';

/// Card payment: the order is only created when the cheque arrives
/// (/api/checkout/cheque). If Telegram refuses the file after the order was
/// made, the retry attaches to that same order instead of placing another.
class ChequeScreen extends StatefulWidget {
  const ChequeScreen({super.key, required this.checkout});
  final CheckoutResult checkout;

  @override
  State<ChequeScreen> createState() => _ChequeScreenState();
}

class _ChequeScreenState extends State<ChequeScreen> {
  PickedFile? _file;
  int? _orderId;
  bool _busy = false;

  /// The last upload got no answer: the order may exist already.
  bool _uncertain = false;

  Future<void> _pick() async {
    try {
      final file = await context.services.native.pickCheque();
      if (file != null && mounted) setState(() => _file = file);
    } on FileTooLarge {
      if (mounted) showSnack(context, context.t('cheque_too_large'), error: true);
    } on Object catch (e) {
      if (mounted) showError(context, e);
    }
  }

  Future<void> _send() async {
    final file = _file;
    if (file == null) return;
    final services = context.services;
    setState(() => _busy = true);
    try {
      final orderId = _orderId;
      if (orderId == null) {
        _orderId = await services.orders.sendPendingCheque(file);
      } else {
        await services.orders.sendOrderCheque(orderId, file);
      }
      await services.cart.refresh();
      if (!mounted) return;
      await showOrderDone(context, _orderId, widget.checkout.expectedKeto);
    } on ApiException catch (e) {
      if (!mounted) return;
      final made = e.body['order_id'];
      if (made is num) _orderId = made.toInt(); // order exists, the file did not go through
      switch (e.code) {
        case 'no_pending_checkout' when _uncertain:
          // The earlier upload went through after all: the pending checkout
          // became an order. Never ask for a second checkout here.
          await services.cart.refresh();
          if (mounted) await showOrderDone(context, null, widget.checkout.expectedKeto);
        case 'no_pending_checkout':
          showSnack(context, context.t('cheque_no_pending'), error: true);
          Navigator.of(context).pop();
        case 'file_too_large':
          showSnack(context, context.t('cheque_too_large'), error: true);
        case 'stock_gone':
          await services.cart.refresh();
          if (!mounted) return;
          showSnack(context, context.t('err_stock_gone', {
            'name': (e.body['name'] as String?) ?? '',
            'n': quantityText((e.body['available'] as num?) ?? 0),
          }), error: true);
        default:
          showError(context, e);
      }
    } on NetworkException catch (e) {
      _uncertain = true;
      if (mounted) showError(context, e);
    } on Object catch (e) {
      if (mounted) showError(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _payInChat() async {
    final services = context.services;
    final done = await runGuarded(context, () async {
      await services.orders.payInChat();
      return true;
    }, busy: (b) => setState(() => _busy = b));
    if (done != true || !mounted) return;
    showSnack(context, context.t('cheque_pay_in_chat_done'));
    await services.native.openUrl('https://t.me/${AppConfig.botUsername}');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final c = widget.checkout;
    final card = c.paymentCard ?? '—';
    return SecureScreen(
      child: Scaffold(
        appBar: AppBar(title: Text(context.t('cheque_title'))),
        body: ListView(padding: const EdgeInsets.all(Tokens.pad), children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(Tokens.pad),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(context.t('cheque_total'), style: theme.textTheme.bodyMedium),
                Text('${groupThousands(c.total)} ${context.t('soum')}',
                    style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
                const Divider(height: Tokens.pad * 2),
                Text(context.t('cheque_card'), style: theme.textTheme.bodyMedium),
                Row(children: [
                  Expanded(child: SelectableText(card, style: theme.textTheme.titleLarge?.copyWith(letterSpacing: 1.5))),
                  IconButton(
                    icon: const Icon(Icons.copy_rounded),
                    onPressed: () async {
                      await Clipboard.setData(ClipboardData(text: card.replaceAll(' ', '')));
                      if (context.mounted) showSnack(context, context.t('copied'));
                    },
                  ),
                ]),
                const SizedBox(height: Tokens.gap),
                Text(context.t('cheque_recipient'), style: theme.textTheme.bodyMedium),
                Text(c.paymentRecipient ?? '—', style: theme.textTheme.titleMedium),
              ]),
            ),
          ),
          const SizedBox(height: Tokens.pad),
          Text(context.t('cheque_hint')),
          const SizedBox(height: Tokens.pad),
          OutlinedButton.icon(
            onPressed: _busy ? null : _pick,
            icon: Icon(_file == null ? Icons.attach_file : Icons.check_circle, color: _file == null ? null : Tokens.success),
            label: Text(_file == null
                ? context.t('cheque_pick')
                : '${_file!.name} · ${(_file!.bytes.length / 1024).ceil()} KB'),
          ),
          const SizedBox(height: Tokens.gap),
          FilledButton(
            onPressed: _busy || _file == null ? null : _send,
            child: _busy
                ? const SizedBox.square(dimension: 22, child: CircularProgressIndicator(strokeWidth: 2))
                : Text(context.t('cheque_send')),
          ),
          const SizedBox(height: Tokens.gap),
          if (_orderId == null)
            TextButton(onPressed: _busy ? null : _payInChat, child: Text(context.t('cheque_pay_in_chat'))),
        ]),
      ),
    );
  }
}
