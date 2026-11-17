import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../core/config.dart';
import '../../data/account_repository.dart';
import '../../widgets/common.dart';

/// The shop opens for @channel members who started the bot — the same rule
/// as the Mini App (site_gate on the server).
class GateScreen extends StatefulWidget {
  const GateScreen({super.key, required this.gate});
  final GateState gate;

  @override
  State<GateScreen> createState() => _GateScreenState();
}

class _GateScreenState extends State<GateScreen> {
  late GateState _gate = widget.gate;
  bool _busy = false;

  Future<void> _check() async {
    final services = context.services;
    final gate = await runGuarded(context, services.account.gate, busy: (b) => setState(() => _busy = b));
    if (gate == null || !mounted) return;
    if (gate.ok) {
      services.gate.value = null;
      services.cart.refresh().ignore();
    } else {
      setState(() => _gate = gate);
      showSnack(context, context.t('gate_not_yet'), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final native = context.services.native;
    final bot = _gate.bot.isEmpty ? AppConfig.botUsername : _gate.bot;
    return Scaffold(
      appBar: AppBar(title: Text(context.t('gate_title'))),
      body: ListView(padding: const EdgeInsets.all(Tokens.pad), children: [
        _Step(
          done: _gate.subscribed,
          title: context.t('gate_channel', {'channel': _gate.channel}),
          action: context.t('gate_join'),
          onTap: () => native.openUrl('https://t.me/${_gate.channel}'),
        ),
        const SizedBox(height: Tokens.gap),
        _Step(
          done: _gate.started,
          title: context.t('gate_bot'),
          action: context.t('gate_start_bot'),
          onTap: () => native.openUrl('https://t.me/$bot?start=sayt'),
        ),
        const SizedBox(height: Tokens.pad * 1.5),
        FilledButton(
          onPressed: _busy ? null : _check,
          child: _busy
              ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2))
              : Text(context.t('gate_check')),
        ),
      ]),
    );
  }
}

class _Step extends StatelessWidget {
  const _Step({required this.done, required this.title, required this.action, required this.onTap});
  final bool done;
  final String title;
  final String action;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: ListTile(
        leading: Icon(done ? Icons.check_circle_rounded : Icons.radio_button_unchecked,
            color: done ? Tokens.success : scheme.outline),
        title: Text(title),
        trailing: done ? null : TextButton(onPressed: onTap, child: Text(action)),
      ),
    );
  }
}
