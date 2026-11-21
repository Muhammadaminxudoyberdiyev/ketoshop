import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../core/remote/remote_config.dart';
import '../../widgets/common.dart';

/// This build is below the server's minimum: it may no longer talk to the
/// server correctly, so the only way on is the update.
class UpdateRequiredScreen extends StatelessWidget {
  const UpdateRequiredScreen({super.key, required this.config});
  final RemoteConfig config;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(Tokens.pad * 2),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Icon(Icons.system_update_rounded, size: 72, color: theme.colorScheme.primary),
            const SizedBox(height: Tokens.pad),
            Text(context.t('update_required_title'), style: theme.textTheme.headlineSmall, textAlign: TextAlign.center),
            const SizedBox(height: Tokens.gap),
            Text(config.updateNotes.isEmpty ? context.t('update_required_body') : config.updateNotes,
                textAlign: TextAlign.center),
            const SizedBox(height: Tokens.pad * 1.5),
            FilledButton(
              onPressed: () => runUpdate(context, config),
              child: Text(context.t('update_button', {'v': config.latestVersion})),
            ),
          ]),
        ),
      ),
    );
  }
}

int _offeredBuild = 0;

/// "A new version is out" — once per app start for each new build.
Future<void> offerUpdate(BuildContext context) async {
  final config = context.services.remote.config;
  if (!config.updateAvailable || _offeredBuild == config.latestBuild) return;
  _offeredBuild = config.latestBuild;
  final update = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      icon: const Icon(Icons.system_update_rounded, size: 40),
      title: Text(context.t('update_available_title')),
      content: Text(config.updateNotes),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: Text(context.t('later'))),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: Text(context.t('update_button', {'v': config.latestVersion})),
        ),
      ],
    ),
  );
  if (update == true && context.mounted) await runUpdate(context, config);
}

/// «Yangilash»: when the APK is on our server the app downloads it itself,
/// checks its SHA-256 and opens Android's installer; otherwise the link
/// (the channel) opens.
Future<void> runUpdate(BuildContext context, RemoteConfig config) async {
  final services = context.services;
  if (!config.selfUpdate) {
    await services.native.openUrl(config.updateUrl);
    return;
  }
  final progress = services.push.updateProgress..value = 0;
  final job = services.native.startUpdate(config.updateUrl, config.apkSha256);
  final navigator = Navigator.of(context, rootNavigator: true);
  var open = true;
  // ignore: unawaited_futures — closed below when the job ends.
  showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (context) => PopScope(
      canPop: false,
      child: AlertDialog(
        title: Text(context.t('update_downloading')),
        content: ValueListenableBuilder<int>(
          valueListenable: progress,
          builder: (context, pct, _) => Column(mainAxisSize: MainAxisSize.min, children: [
            LinearProgressIndicator(value: pct > 0 ? pct / 100 : null),
            const SizedBox(height: Tokens.gap),
            Text(pct > 0 ? '$pct%' : ''),
          ]),
        ),
      ),
    ),
  ).whenComplete(() => open = false);
  String result;
  try {
    result = await job;
  } on Object {
    result = 'error';
  }
  if (open) navigator.pop();
  if (!context.mounted) return;
  switch (result) {
    case 'installing':
      break;
    case 'need_permission':
      showSnack(context, context.t('update_allow_install'));
    default:
      showSnack(context, context.t('update_failed'), error: true);
  }
}
