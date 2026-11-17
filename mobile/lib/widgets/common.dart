import 'package:flutter/material.dart';

import '../app/scope.dart';
import '../app/theme.dart';
import '../core/net/api_client.dart';

/// The buyer-facing sentence for any failure.
String errorText(BuildContext context, Object error) {
  if (error is NetworkException) return context.t('error_network');
  if (error is SessionEnded) return context.t('session_ended');
  if (error is ApiException) {
    if (error.status == 429) return context.t('error_rate');
    if (error.status >= 500) return context.t('error_server');
  }
  return context.t('error_generic');
}

void showError(BuildContext context, Object error) {
  if (error is SessionEnded) return; // the app already went back to login
  showSnack(context, errorText(context, error), error: true);
}

void showSnack(BuildContext context, String text, {bool error = false}) {
  final messenger = ScaffoldMessenger.maybeOf(context);
  if (messenger == null) return;
  final scheme = Theme.of(context).colorScheme;
  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(text), backgroundColor: error ? scheme.error : null));
}

/// Loads `load()` once, shows a spinner, an error with retry, or the data.
class AsyncView<T> extends StatefulWidget {
  const AsyncView({super.key, required this.load, required this.builder});

  final Future<T> Function() load;
  final Widget Function(BuildContext context, T data, Future<void> Function() reload) builder;

  @override
  State<AsyncView<T>> createState() => _AsyncViewState<T>();
}

class _AsyncViewState<T> extends State<AsyncView<T>> {
  late Future<T> _future = widget.load();

  Future<void> _reload() async {
    final next = widget.load();
    setState(() => _future = next);
    try {
      await next;
    } on Object {
      // shown by the builder
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<T>(
        future: _future,
        builder: (context, snap) {
          if (snap.hasData) return widget.builder(context, snap.data as T, _reload);
          if (snap.hasError) return ErrorPanel(message: errorText(context, snap.error!), onRetry: _reload);
          return const Center(child: CircularProgressIndicator());
        },
      );
}

class ErrorPanel extends StatelessWidget {
  const ErrorPanel({super.key, required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(Tokens.pad * 2),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.cloud_off_rounded, size: 48, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: Tokens.pad),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: Tokens.pad),
            OutlinedButton(onPressed: onRetry, child: Text(context.t('retry'))),
          ]),
        ),
      );
}

/// Wrap a screen that shows a login code or account data: no screenshots
/// or screen recording while it is open.
class SecureScreen extends StatefulWidget {
  const SecureScreen({super.key, required this.child});
  final Widget child;

  @override
  State<SecureScreen> createState() => _SecureScreenState();
}

class _SecureScreenState extends State<SecureScreen> {
  late final _secure = context.services.secure;

  @override
  void initState() {
    super.initState();
    _secure.push();
  }

  @override
  void dispose() {
    _secure.pop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}

/// Runs `action` with a busy flag, showing any error; returns its result.
Future<T?> runGuarded<T>(BuildContext context, Future<T> Function() action, {ValueChanged<bool>? busy}) async {
  busy?.call(true);
  try {
    return await action();
  } on Object catch (e) {
    if (context.mounted) showError(context, e);
    return null;
  } finally {
    busy?.call(false);
  }
}

Future<bool> confirm(BuildContext context, String question) async =>
    await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        content: Text(question),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(context.t('no'))),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(context.t('yes'))),
        ],
      ),
    ) ??
    false;
