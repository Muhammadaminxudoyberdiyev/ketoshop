import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../app/theme.dart';

/// Shown instead of the shop when the app finds itself hooked, debugged or
/// re-signed (release builds only). There is nothing to tap: whoever is
/// inside the app must not get a session out of it.
class UnsafeScreen extends StatelessWidget {
  const UnsafeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(Tokens.pad * 2),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Icon(Icons.gpp_bad_rounded, size: 72, color: theme.colorScheme.error),
            const SizedBox(height: Tokens.pad),
            Text(context.t('unsafe_title'), style: theme.textTheme.headlineSmall, textAlign: TextAlign.center),
            const SizedBox(height: Tokens.gap),
            Text(context.t('unsafe_body'), textAlign: TextAlign.center),
          ]),
        ),
      ),
    );
  }
}
