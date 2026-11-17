import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';
import '../../data/terms_repository.dart';
import '../../widgets/common.dart';

void openTerms(BuildContext context) =>
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const TermsScreen()));

class TermsScreen extends StatelessWidget {
  const TermsScreen({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(context.t('terms_title'))),
        body: AsyncView<TermsDoc>(
          load: context.services.terms.load,
          builder: (context, doc, _) => _TermsBody(doc: doc),
        ),
      );
}

class _TermsBody extends StatelessWidget {
  const _TermsBody({required this.doc});
  final TermsDoc doc;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(padding: const EdgeInsets.all(Tokens.pad), children: [
      Text(doc.title, style: theme.textTheme.headlineSmall),
      Text(context.t('terms_edition', {'v': doc.version}), style: theme.textTheme.bodySmall),
      for (final (title, items) in doc.sections) ...[
        const SizedBox(height: Tokens.pad * 1.25),
        Text(title, style: theme.textTheme.titleMedium),
        const SizedBox(height: Tokens.gap),
        for (final item in items)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('•  '),
              Expanded(child: SelectableText(item, style: theme.textTheme.bodyMedium)),
            ]),
          ),
      ],
      const SizedBox(height: Tokens.pad * 2),
    ]);
  }
}

bool _askedThisRun = false;

/// The Oferta has a new edition since this phone accepted one: show it and
/// record the acceptance on the server (once per app start until accepted).
Future<void> askToAcceptNewTerms(BuildContext context) async {
  final services = context.services;
  final current = services.remote.config.termsVersion;
  if (current.isEmpty || _askedThisRun) return;
  final accepted = await services.terms.acceptedVersion();
  if (accepted == current || !context.mounted) return;
  _askedThisRun = true;
  final agree = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (context) => AlertDialog(
      icon: const Icon(Icons.gavel_rounded, size: 36),
      title: Text(context.t('terms_updated_title')),
      content: Text(context.t('terms_updated_body')),
      actions: [
        TextButton(onPressed: () => openTerms(context), child: Text(context.t('terms_read'))),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(context.t('terms_accept'))),
      ],
    ),
  );
  if (agree == true && context.mounted) {
    unawaited(runGuarded(context, () => services.terms.accept(current)));
  }
}
