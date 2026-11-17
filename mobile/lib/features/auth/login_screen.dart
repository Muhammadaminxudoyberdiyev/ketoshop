import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../core/auth/auth_controller.dart';
import '../../core/config.dart';
import '../../core/l10n/locale_controller.dart';
import '../../widgets/common.dart';
import '../terms/terms_screen.dart';

/// Login through the bot: the app shows a number, the buyer taps the same
/// number among three in Telegram, the app picks the session up by polling.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> with WidgetsBindingObserver {
  LoginTicket? _ticket;
  bool _busy = false;
  String? _notice;
  Timer? _poller;
  Timer? _ticker;
  bool _polling = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    final reason = context.services.auth.lastEndReason;
    if (reason != null) _notice = reason == 'device_untrusted' ? 'device_untrusted' : 'session_ended';
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _stop();
    super.dispose();
  }

  /// Back from Telegram: ask right away instead of waiting for the timer.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _ticket != null) unawaited(_poll());
  }

  void _stop() {
    _poller?.cancel();
    _ticker?.cancel();
  }

  Future<void> _start() async {
    final services = context.services;
    setState(() {
      _busy = true;
      _notice = null;
    });
    try {
      final ticket = await services.auth.startLogin(termsVersion: services.remote.config.termsVersion);
      if (!mounted) return;
      setState(() => _ticket = ticket);
      _poller = Timer.periodic(AppConfig.loginPollEvery, (_) => _poll());
      _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
        if (!mounted) return;
        if (DateTime.now().isAfter(ticket.expiresAt)) {
          _finish('login_expired');
        } else {
          setState(() {});
        }
      });
      await _openTelegram();
    } on Object catch (e) {
      if (mounted) showError(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _openTelegram() async {
    final ticket = _ticket;
    if (ticket == null) return;
    final opened = await context.services.native.openUrl(ticket.botUrl);
    if (!opened && mounted) showSnack(context, context.t('login_no_telegram'), error: true);
  }

  Future<void> _poll() async {
    final ticket = _ticket;
    if (ticket == null || _polling) return;
    _polling = true;
    try {
      final outcome = await context.services.auth.poll(ticket);
      switch (outcome) {
        case PollOutcome.pending:
        case PollOutcome.approved:
          break; // approved: the root view switches to the shop
        case PollOutcome.rejected:
          _finish('login_rejected');
        case PollOutcome.expired:
          _finish('login_expired');
      }
    } on Object {
      // a missed poll is retried by the timer
    } finally {
      _polling = false;
    }
  }

  void _finish(String notice) {
    _stop();
    if (mounted) {
      setState(() {
        _ticket = null;
        _notice = notice;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final ticket = _ticket;
    return SecureScreen(
      child: Scaffold(
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(Tokens.pad * 1.5),
            children: [
              const _LanguagePicker(),
              const SizedBox(height: Tokens.pad * 2),
              Icon(Icons.eco_rounded, size: 72, color: theme.colorScheme.primary),
              const SizedBox(height: Tokens.pad),
              Text('Ketoshop', textAlign: TextAlign.center, style: theme.textTheme.headlineMedium),
              Text(context.t('login_title'), textAlign: TextAlign.center, style: theme.textTheme.titleMedium),
              const SizedBox(height: Tokens.pad * 2),
              if (ticket == null) ...[
                Text(context.t('login_subtitle'), textAlign: TextAlign.center),
                const SizedBox(height: Tokens.pad * 1.5),
                FilledButton.icon(
                  onPressed: _busy ? null : _start,
                  icon: _busy
                      ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.send_rounded),
                  label: Text(context.t('login_button')),
                ),
                const SizedBox(height: Tokens.gap),
                Text(context.t('terms_login_note'), textAlign: TextAlign.center, style: theme.textTheme.bodySmall),
                TextButton(onPressed: () => openTerms(context), child: Text(context.t('terms_title'))),
              ] else
                _CodeCard(ticket: ticket, onOpenTelegram: _openTelegram, onCancel: () => _finish('')),
              if (_notice != null && _notice!.isNotEmpty) ...[
                const SizedBox(height: Tokens.pad),
                Text(context.t(_notice!), textAlign: TextAlign.center, style: TextStyle(color: theme.colorScheme.error)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _CodeCard extends StatelessWidget {
  const _CodeCard({required this.ticket, required this.onOpenTelegram, required this.onCancel});
  final LoginTicket ticket;
  final VoidCallback onOpenTelegram;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final left = ticket.expiresAt.difference(DateTime.now()).inSeconds.clamp(0, 9999);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(Tokens.pad * 1.5),
        child: Column(children: [
          Text(context.t('login_code_title'), style: theme.textTheme.titleMedium, textAlign: TextAlign.center),
          const SizedBox(height: Tokens.pad),
          Text('${ticket.matchCode}',
              style: theme.textTheme.displayLarge?.copyWith(fontWeight: FontWeight.w800, letterSpacing: 4,
                  color: theme.colorScheme.primary)),
          const SizedBox(height: Tokens.gap),
          Text(context.t('login_code_hint'), textAlign: TextAlign.center, style: theme.textTheme.bodySmall),
          const SizedBox(height: Tokens.pad),
          FilledButton.icon(onPressed: onOpenTelegram, icon: const Icon(Icons.open_in_new), label: Text(context.t('login_open_telegram'))),
          const SizedBox(height: Tokens.pad),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            const SizedBox.square(dimension: 16, child: CircularProgressIndicator(strokeWidth: 2)),
            const SizedBox(width: Tokens.gap),
            Text(context.t('login_waiting')),
          ]),
          const SizedBox(height: 4),
          Text(context.t('login_expires', {'s': left}), style: theme.textTheme.bodySmall),
          TextButton(onPressed: onCancel, child: Text(context.t('cancel'))),
        ]),
      ),
    );
  }
}

class _LanguagePicker extends StatelessWidget {
  const _LanguagePicker();

  @override
  Widget build(BuildContext context) {
    final locale = context.services.locale;
    context.t('cancel'); // rebuild with the language
    return Wrap(
      alignment: WrapAlignment.end,
      spacing: Tokens.gap,
      children: [
        for (final lang in LocaleController.languages)
          ChoiceChip(
            label: Text(LocaleController.languageNames[lang]!),
            selected: locale.lang == lang,
            onSelected: (_) => locale.setLocal(lang),
          ),
      ],
    );
  }
}
