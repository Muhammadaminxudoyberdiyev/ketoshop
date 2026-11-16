import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../core/config.dart';
import '../../core/format.dart';
import '../../core/l10n/locale_controller.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  late Future<KetoStatus> _keto = context.services.orders.ketoStatus();
  late Future<List<DeviceSession>> _devices = context.services.account.sessions();

  Future<void> _reload() async {
    final s = context.services;
    setState(() {
      _keto = s.orders.ketoStatus();
      _devices = s.account.sessions();
    });
  }

  Future<void> _setLanguage(String lang) async {
    await runGuarded(context, () => context.services.account.setLanguage(lang));
  }

  Future<void> _logoutOthers() async {
    final n = await runGuarded(context, context.services.account.logoutOtherDevices);
    if (n == null || !mounted) return;
    showSnack(context, context.t('others_logged_out', {'n': n}));
    await _reload();
  }

  Future<void> _logout() async {
    if (!await confirm(context, context.t('profile_logout_q')) || !mounted) return;
    await context.services.auth.logout();
  }

  @override
  Widget build(BuildContext context) {
    final services = context.services;
    final theme = Theme.of(context);
    final name = services.auth.session?.firstName ?? '';
    return Scaffold(
      appBar: AppBar(title: Text(context.t('nav_profile'))),
      body: RefreshIndicator(
        onRefresh: _reload,
        child: ListView(padding: const EdgeInsets.all(Tokens.pad), children: [
          if (name.isNotEmpty) Text(services.locale.display(name), style: theme.textTheme.headlineSmall),
          const SizedBox(height: Tokens.pad),
          FutureBuilder<KetoStatus>(
            future: _keto,
            builder: (context, snap) {
              final keto = snap.data;
              return Card(
                child: ListTile(
                  leading: const Icon(Icons.savings_outlined),
                  title: Text(context.t('profile_keto')),
                  subtitle: keto == null || keto.rate <= 0 ? null : Text(context.t('profile_cashback', {'n': keto.rate})),
                  trailing: keto == null || !keto.enabled
                      ? null
                      : Text(groupThousands(keto.balance), style: theme.textTheme.titleLarge),
                ),
              );
            },
          ),
          const SizedBox(height: Tokens.pad),
          Text(context.t('profile_lang'), style: theme.textTheme.titleSmall),
          const SizedBox(height: Tokens.gap),
          SegmentedButton<String>(
            segments: [
              for (final lang in LocaleController.languages)
                ButtonSegment(value: lang, label: Text(LocaleController.languageNames[lang]!)),
            ],
            selected: {services.locale.lang},
            onSelectionChanged: (s) => _setLanguage(s.first),
          ),
          const SizedBox(height: Tokens.pad * 1.5),
          Text(context.t('profile_devices'), style: theme.textTheme.titleSmall),
          const SizedBox(height: Tokens.gap),
          FutureBuilder<List<DeviceSession>>(
            future: _devices,
            builder: (context, snap) => Card(
              child: Column(children: [
                for (final d in snap.data ?? const <DeviceSession>[])
                  ListTile(
                    leading: Icon(d.current ? Icons.smartphone : Icons.devices_other),
                    title: Text(d.deviceName),
                    subtitle: Text(d.current ? context.t('profile_this_device') : orderDateText(d.lastSeen)),
                  ),
                if ((snap.data?.length ?? 0) > 1)
                  Padding(
                    padding: const EdgeInsets.all(Tokens.gap),
                    child: OutlinedButton(onPressed: _logoutOthers, child: Text(context.t('profile_logout_others'))),
                  ),
              ]),
            ),
          ),
          const SizedBox(height: Tokens.gap),
          Text('🔐 ${context.t('security_note')}', style: theme.textTheme.bodySmall),
          const SizedBox(height: Tokens.pad),
          Card(
            child: Column(children: [
              ListTile(
                leading: const Icon(Icons.support_agent),
                title: Text(context.t('profile_support')),
                onTap: () => services.native.openUrl('https://t.me/${AppConfig.supportUsername}'),
              ),
              ListTile(
                leading: Icon(Icons.logout, color: theme.colorScheme.error),
                title: Text(context.t('profile_logout'), style: TextStyle(color: theme.colorScheme.error)),
                onTap: _logout,
              ),
            ]),
          ),
          const SizedBox(height: Tokens.pad),
          Center(child: Text(context.t('profile_version', {'v': AppConfig.appVersion}), style: theme.textTheme.bodySmall)),
        ]),
      ),
    );
  }
}
