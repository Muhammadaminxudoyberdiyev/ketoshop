import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../core/config.dart';
import '../../core/format.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';
import '../terms/terms_screen.dart';

/// «Ilova va xavfsizlik» — opened from the shop's profile page. What only
/// the app has: the devices logged in to this account, logging out, the
/// Oferta. Everything else (language, orders, Keto, games) is in the shop.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late Future<List<DeviceSession>> _devices = context.services.account.sessions();

  void _reload() => setState(() => _devices = context.services.account.sessions());

  Future<void> _logoutOthers() async {
    final n = await runGuarded(context, context.services.account.logoutOtherDevices);
    if (n == null || !mounted) return;
    showSnack(context, context.t('others_logged_out', {'n': n}));
    _reload();
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
    return SecureScreen(
      child: Scaffold(
        appBar: AppBar(title: Text(context.t('settings_title'))),
        body: RefreshIndicator(
          onRefresh: () async => _reload(),
          child: ListView(padding: const EdgeInsets.all(Tokens.pad), children: [
            if (name.isNotEmpty) Text(services.locale.display(name), style: theme.textTheme.headlineSmall),
            const SizedBox(height: Tokens.pad),
            Text(context.t('profile_devices'), style: theme.textTheme.titleSmall),
            const SizedBox(height: Tokens.gap),
            FutureBuilder<List<DeviceSession>>(
              future: _devices,
              builder: (context, snap) => Card(
                child: Column(children: [
                  if (snap.connectionState != ConnectionState.done)
                    const Padding(padding: EdgeInsets.all(Tokens.pad), child: CircularProgressIndicator()),
                  for (final d in snap.data ?? const <DeviceSession>[])
                    ListTile(
                      leading: Icon(d.current ? Icons.smartphone : Icons.devices_other),
                      title: Text(d.deviceName),
                      subtitle: Text(d.current ? context.t('profile_this_device') : dateText(d.lastSeen)),
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
                  leading: const Icon(Icons.gavel_rounded),
                  title: Text(context.t('terms_title')),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => openTerms(context),
                ),
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
      ),
    );
  }
}
