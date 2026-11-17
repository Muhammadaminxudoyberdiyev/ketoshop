import 'dart:async';

import 'package:flutter/material.dart';

import '../app/scope.dart';
import '../app/theme.dart';
import '../core/format.dart';
import '../core/images/net_image.dart';
import '../core/net/api_client.dart';
import '../data/account_repository.dart';

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

/// Shows the failure — or the channel/bot gate when that is what it was.
void showError(BuildContext context, Object error) {
  if (error is GateRequired) {
    context.services.gate.value = GateState.fromJson(error.gate);
    return;
  }
  if (error is SessionEnded) return; // the app already went back to login
  showSnack(context, errorText(context, error), error: true);
}

void showSnack(BuildContext context, String text, {bool error = false}) {
  final messenger = ScaffoldMessenger.maybeOf(context);
  if (messenger == null) return;
  final scheme = Theme.of(context).colorScheme;
  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Text(text),
      backgroundColor: error ? scheme.error : null,
    ));
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
  late Future<T> _future = _run();

  Future<T> _run() => widget.load().catchError((Object e) {
        if (e is GateRequired && mounted) context.services.gate.value = GateState.fromJson(e.gate);
        throw e;
      });

  Future<void> _reload() async {
    final next = _run();
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

class EmptyPanel extends StatelessWidget {
  const EmptyPanel({super.key, required this.icon, required this.title, this.subtitle, this.action});
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(Tokens.pad * 2),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 56, color: theme.colorScheme.outline),
          const SizedBox(height: Tokens.pad),
          Text(title, style: theme.textTheme.titleMedium, textAlign: TextAlign.center),
          if (subtitle != null) ...[
            const SizedBox(height: Tokens.gap),
            Text(subtitle!, style: theme.textTheme.bodyMedium, textAlign: TextAlign.center),
          ],
          if (action != null) ...[const SizedBox(height: Tokens.pad), action!],
        ]),
      ),
    );
  }
}

/// "123 000 so'm", with the shelf price struck through when discounted.
class PriceText extends StatelessWidget {
  const PriceText({super.key, required this.price, this.original, this.large = false});
  final num price;
  final num? original;
  final bool large;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final style = (large ? theme.textTheme.headlineSmall : theme.textTheme.titleSmall)
        ?.copyWith(fontWeight: FontWeight.w700, color: original != null ? Tokens.sale : null);
    final money = '${groupThousands(price)} ${context.t('soum')}';
    if (original == null || original! <= price) return Text(money, style: style);
    return Wrap(crossAxisAlignment: WrapCrossAlignment.center, spacing: 6, children: [
      Text(money, style: style),
      Text(groupThousands(original!),
          style: theme.textTheme.bodySmall?.copyWith(
              decoration: TextDecoration.lineThrough, color: theme.colorScheme.outline)),
    ]);
  }
}

/// A product picture from our host, decoded at the size it is drawn.
class NetPhoto extends StatelessWidget {
  const NetPhoto({super.key, required this.url, this.fit = BoxFit.cover, this.decodeWidth = 480});
  final String? url;
  final BoxFit fit;
  final int decodeWidth;

  @override
  Widget build(BuildContext context) {
    final placeholder = ColoredBox(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Center(child: Icon(Icons.eco_outlined, color: Theme.of(context).colorScheme.outline)),
    );
    if (url == null) return placeholder;
    return Image(
      image: ResizeImage(StoreImage(url!, context.services.images), width: decodeWidth, policy: ResizeImagePolicy.fit),
      fit: fit,
      gaplessPlayback: true,
      errorBuilder: (_, __, ___) => placeholder,
      frameBuilder: (_, child, frame, sync) => sync || frame != null
          ? child
          : placeholder,
    );
  }
}

class QuantityStepper extends StatelessWidget {
  const QuantityStepper({super.key, required this.quantity, required this.onChanged, this.busy = false});
  final num quantity;
  final ValueChanged<num> onChanged;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(color: scheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(24)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        IconButton(
          visualDensity: VisualDensity.compact,
          onPressed: busy ? null : () => onChanged(quantity - 1),
          icon: Icon(quantity <= 1 ? Icons.delete_outline : Icons.remove),
        ),
        SizedBox(
          width: 32,
          child: busy
              ? const Center(child: SizedBox.square(dimension: 16, child: CircularProgressIndicator(strokeWidth: 2)))
              : Text(quantityText(quantity), textAlign: TextAlign.center, style: const TextStyle(fontWeight: FontWeight.w600)),
        ),
        IconButton(
          visualDensity: VisualDensity.compact,
          onPressed: busy ? null : () => onChanged(quantity + 1),
          icon: const Icon(Icons.add),
        ),
      ]),
    );
  }
}

/// Wrap a pushed screen that shows personal or payment data: no screenshots
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

/// Debounce for search-as-you-type.
class Debouncer {
  Debouncer(this.delay);
  final Duration delay;
  Timer? _timer;

  void call(VoidCallback action) {
    _timer?.cancel();
    _timer = Timer(delay, action);
  }

  void dispose() => _timer?.cancel();
}
