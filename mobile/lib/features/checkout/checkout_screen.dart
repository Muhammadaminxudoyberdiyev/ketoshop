import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../core/config.dart';
import '../../core/format.dart';
import '../../core/net/api_client.dart';
import '../../core/platform/native_bridge.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';
import 'cheque_screen.dart';

/// Delivery method → label key. 'yandex_market' only appears on old orders.
String deliveryLabel(BuildContext context, String method) => switch (method) {
      'self' => context.t('del_self'),
      'yandex_taxi' => context.t('del_yandex_taxi'),
      'uzpost' => context.t('del_uzpost'),
      'bts' => context.t('del_bts'),
      'emu' => context.t('del_emu'),
      'pickup' => context.t('mode_pickup'),
      'yandex_market' => 'Yandex Market',
      _ => method,
    };

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({super.key});

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  final _phone = TextEditingController();
  final _note = TextEditingController();
  String? _phoneError;

  bool _pickup = false;
  PickupConfig? _pickupConfig;
  GeoPoint? _point;
  String _address = '';
  bool _locating = false;
  String? _method;
  String _payment = 'online';
  KetoStatus? _keto;
  bool _useKeto = false;
  UzpostQuote? _quote;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    unawaited(_prefill());
  }

  @override
  void dispose() {
    _phone.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _prefill() async {
    final orders = context.services.orders;
    final results = await Future.wait<Object?>([
      orders.knownPhone().catchError((Object _) => ''),
      orders.pickupConfig().then<Object?>((v) => v).catchError((Object _) => null),
      orders.ketoStatus().then<Object?>((v) => v).catchError((Object _) => null),
    ]);
    if (!mounted) return;
    setState(() {
      if (_phone.text.isEmpty) _phone.text = results[0]! as String;
      _pickupConfig = results[1] as PickupConfig?;
      _keto = results[2] as KetoStatus?;
    });
  }

  List<String> get _methods {
    final p = _point;
    if (p == null) return const [];
    return AppConfig.inTashkent(p.lat, p.lng) ? const ['self', 'yandex_taxi'] : const ['uzpost', 'bts', 'emu'];
  }

  bool get _cashAllowed => _pickup || _method == 'self';

  Future<void> _locate() async {
    final services = context.services;
    setState(() => _locating = true);
    try {
      final point = await services.native.currentLocation();
      if (!mounted) return;
      setState(() {
        _point = point;
        _address = '';
        _method = _methods.first;
        _quote = null;
        if (!_cashAllowed) _payment = 'online';
      });
      final address = await services.orders.addressOf(point);
      if (mounted) setState(() => _address = address);
      await _loadQuote();
    } on LocationFailure catch (e) {
      if (!mounted) return;
      final key = switch (e.code) {
        'denied' => 'location_denied',
        'disabled' => 'location_off',
        _ => 'location_failed',
      };
      showSnack(context, context.t(key), error: true);
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  Future<void> _loadQuote() async {
    final point = _point;
    if (_method != 'uzpost' || point == null) return;
    final quote = await context.services.orders.uzpostQuote(point);
    if (mounted) setState(() => _quote = quote);
  }

  /// What delivery adds to the bill; null when it is paid to the courier.
  int? _fee(Cart cart) {
    if (_pickup) return 0;
    return switch (_method) {
      'self' => cart.total >= AppConfig.freeDeliveryFrom ? 0 : AppConfig.selfDeliveryFee,
      'uzpost' => _quote?.fee ?? 0,
      null => 0,
      _ => null,
    };
  }

  int _ketoRedeem(Cart cart) {
    final keto = _keto;
    if (!_useKeto || keto == null || !keto.enabled) return 0;
    return min(keto.balance, (cart.payTotal + (_fee(cart) ?? 0)).floor());
  }

  Future<void> _submit() async {
    final services = context.services;
    final cart = services.cart.cart;
    final phone = normalizeUzPhone(_phone.text);
    setState(() => _phoneError = phone == null ? context.t('phone_invalid') : null);
    if (phone == null) return;
    if (!_pickup && _point == null) return showSnack(context, context.t('err_location_required'), error: true);
    if (!_pickup && _method == null) return showSnack(context, context.t('err_delivery_method'), error: true);

    final request = CheckoutRequest(
      phone: phone,
      deliveryMethod: _pickup ? 'pickup' : _method!,
      paymentMethod: _payment,
      lat: _point?.lat,
      lng: _point?.lng,
      addressNote: _note.text.trim().isEmpty ? null : _note.text.trim(),
      ketoRedeem: _ketoRedeem(cart),
    );
    setState(() => _submitting = true);
    try {
      final result = await services.orders.checkout(request);
      services.catalog.invalidate();
      if (!mounted) return;
      if (result.awaitingCheque) {
        await Navigator.of(context).pushReplacement(MaterialPageRoute<void>(builder: (_) => ChequeScreen(checkout: result)));
        return;
      }
      await services.cart.refresh();
      if (!mounted) return;
      await showOrderDone(context, result.orderId, result.expectedKeto);
    } on ApiException catch (e) {
      if (mounted) await _explain(e);
    } on Object catch (e) {
      if (mounted) showError(context, e);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _explain(ApiException e) async {
    final services = context.services;
    switch (e.code) {
      case 'invalid_phone':
        setState(() => _phoneError = context.t('phone_invalid'));
      case 'invalid_location' || 'outside_uzbekistan':
        setState(() => _point = null);
        showSnack(context, context.t(e.code == 'outside_uzbekistan' ? 'err_outside_uz' : 'err_location_required'), error: true);
      case 'invalid_delivery_method':
        showSnack(context, context.t('err_delivery_method'), error: true);
      case 'cash_not_available':
        setState(() => _payment = 'online');
        showSnack(context, context.t('cash_only_courier'), error: true);
      case 'stock_gone':
        await services.cart.refresh();
        if (!mounted) return;
        showSnack(context, context.t('err_stock_gone', {
          'name': (e.body['name'] as String?) ?? '',
          'n': quantityText((e.body['available'] as num?) ?? 0),
        }), error: true);
        Navigator.of(context).pop();
      case 'keto_balance_changed':
        final keto = await services.orders.ketoStatus();
        if (!mounted) return;
        setState(() => _keto = keto);
        showSnack(context, context.t('err_keto_changed'), error: true);
      case 'pickup_unavailable':
        setState(() => _pickup = false);
        showSnack(context, context.t('err_pickup_off'), error: true);
      case 'cart_empty':
        showSnack(context, context.t('cart_empty'), error: true);
        Navigator.of(context).pop();
      default:
        showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final services = context.services;
    final theme = Theme.of(context);
    return SecureScreen(
      child: Scaffold(
        appBar: AppBar(title: Text(context.t('checkout_title'))),
        body: ListenableBuilder(
          listenable: services.cart,
          builder: (context, _) {
            final cart = services.cart.cart;
            final fee = _fee(cart);
            final keto = _ketoRedeem(cart);
            final toPay = cart.payTotal + (fee ?? 0) - keto;
            String money(num v) => '${groupThousands(v)} ${context.t('soum')}';
            return ListView(padding: const EdgeInsets.all(Tokens.pad), children: [
              TextField(
                controller: _phone,
                keyboardType: TextInputType.phone,
                autofillHints: const [AutofillHints.telephoneNumber],
                decoration: InputDecoration(
                  labelText: context.t('phone'),
                  hintText: '+998 90 123 45 67',
                  errorText: _phoneError,
                  prefixIcon: const Icon(Icons.phone_outlined),
                ),
              ),
              const SizedBox(height: Tokens.pad),
              if (_pickupConfig?.enabled ?? false) ...[
                SegmentedButton<bool>(
                  segments: [
                    ButtonSegment(value: false, label: Text(context.t('mode_delivery')), icon: const Icon(Icons.local_shipping_outlined)),
                    ButtonSegment(value: true, label: Text(context.t('mode_pickup')), icon: const Icon(Icons.storefront_outlined)),
                  ],
                  selected: {_pickup},
                  onSelectionChanged: (s) => setState(() {
                    _pickup = s.first;
                    if (!_cashAllowed) _payment = 'online';
                  }),
                ),
                const SizedBox(height: Tokens.pad),
              ],
              if (_pickup)
                _PickupCard(config: _pickupConfig!)
              else ...[
                Text(context.t('location'), style: theme.textTheme.titleSmall),
                const SizedBox(height: Tokens.gap),
                OutlinedButton.icon(
                  onPressed: _locating ? null : _locate,
                  icon: _locating
                      ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.my_location),
                  label: Text(context.t(_point == null ? 'location_button' : 'location_again')),
                ),
                if (_point != null) ...[
                  const SizedBox(height: Tokens.gap),
                  Text(_address.isEmpty
                      ? '📍 ${_point!.lat.toStringAsFixed(5)}, ${_point!.lng.toStringAsFixed(5)}'
                      : '📍 $_address'),
                  const SizedBox(height: Tokens.gap),
                  TextField(
                    controller: _note,
                    maxLength: 500,
                    maxLines: 2,
                    decoration: InputDecoration(labelText: context.t('address_note')),
                  ),
                  Text(context.t('delivery'), style: theme.textTheme.titleSmall),
                  const SizedBox(height: Tokens.gap),
                  Wrap(spacing: Tokens.gap, runSpacing: Tokens.gap, children: [
                    for (final m in _methods)
                      ChoiceChip(
                        label: Text(deliveryLabel(context, m)),
                        selected: _method == m,
                        onSelected: (_) {
                          setState(() {
                            _method = m;
                            if (!_cashAllowed) _payment = 'online';
                          });
                          unawaited(_loadQuote());
                        },
                      ),
                  ]),
                  if (_method == 'uzpost' && _quote?.officeName != null) ...[
                    const SizedBox(height: Tokens.gap),
                    Text('${context.t('uzpost_office')}: ${_quote!.officeName}${_quote!.officeAddress == null ? '' : ', ${_quote!.officeAddress}'}',
                        style: theme.textTheme.bodySmall),
                  ],
                ],
              ],
              const SizedBox(height: Tokens.pad),
              Text(context.t('payment'), style: theme.textTheme.titleSmall),
              const SizedBox(height: Tokens.gap),
              SegmentedButton<String>(
                segments: [
                  ButtonSegment(value: 'online', label: Text(context.t('pay_online'))),
                  ButtonSegment(value: 'cash', label: Text(context.t('pay_cash')), enabled: _cashAllowed),
                ],
                selected: {_payment},
                onSelectionChanged: (s) => setState(() => _payment = s.first),
              ),
              if (!_cashAllowed)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(context.t('cash_only_courier'), style: theme.textTheme.bodySmall),
                ),
              if ((_keto?.enabled ?? false) && _keto!.balance > 0)
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  value: _useKeto,
                  onChanged: (v) => setState(() => _useKeto = v),
                  title: Text(context.t('keto_use', {'n': groupThousands(_keto!.balance)})),
                ),
              const Divider(height: Tokens.pad * 2),
              _line(context.t('cart_total'), money(cart.payTotal)),
              _line(context.t('delivery_fee'),
                  fee == null ? context.t('paid_to_courier') : (fee == 0 ? context.t('free') : money(fee))),
              if (keto > 0) _line('Keto', '−${money(keto)}'),
              _line(context.t('to_pay'), money(toPay), bold: true),
              const SizedBox(height: Tokens.pad),
              FilledButton(
                onPressed: _submitting || cart.lines.isEmpty ? null : _submit,
                child: _submitting
                    ? const SizedBox.square(dimension: 22, child: CircularProgressIndicator(strokeWidth: 2))
                    : Text(context.t('submit_order')),
              ),
            ]);
          },
        ),
      ),
    );
  }

  Widget _line(String label, String value, {bool bold = false}) {
    final style = bold ? Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700) : null;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(children: [Expanded(child: Text(label, style: style)), Text(value, style: style)]),
    );
  }
}

class _PickupCard extends StatelessWidget {
  const _PickupCard({required this.config});
  final PickupConfig config;

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          leading: const Icon(Icons.storefront_outlined),
          title: Text(context.t('pickup_address')),
          subtitle: Text(config.address),
          trailing: config.mapUrl.isEmpty
              ? null
              : TextButton(
                  onPressed: () => context.services.native.openUrl(config.mapUrl),
                  child: Text(context.t('open_map')),
                ),
        ),
      );
}

/// "Order accepted" — then back to the shop's first screen.
Future<void> showOrderDone(BuildContext context, int? orderId, int expectedKeto) async {
  await showDialog<void>(
    context: context,
    builder: (context) => AlertDialog(
      icon: const Icon(Icons.check_circle_rounded, color: Tokens.success, size: 48),
      title: Text(context.t('order_done_title')),
      content: Text([
        if (orderId != null) context.t('order_done_body', {'id': orderId}),
        if (expectedKeto > 0) context.t('keto_will_earn', {'n': expectedKeto}),
      ].join('\n\n')),
      actions: [FilledButton(onPressed: () => Navigator.pop(context), child: Text(context.t('close')))],
    ),
  );
  if (context.mounted) Navigator.of(context).popUntil((route) => route.isFirst);
}
