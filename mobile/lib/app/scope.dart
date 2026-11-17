import 'package:flutter/widgets.dart';

import '../core/l10n/locale_controller.dart';
import 'services.dart';

/// Hands AppServices to the tree. Widgets that read strings through
/// context.t rebuild when the language changes; reading services does not
/// subscribe to anything.
class AppScope extends InheritedNotifier<LocaleController> {
  AppScope({super.key, required this.services, required super.child}) : super(notifier: services.locale);

  final AppServices services;

  static AppScope _of(BuildContext context, {required bool listen}) {
    final scope = listen
        ? context.dependOnInheritedWidgetOfExactType<AppScope>()
        : context.getInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope missing above this widget');
    return scope!;
  }
}

extension AppContext on BuildContext {
  AppServices get services => AppScope._of(this, listen: false).services;

  /// A UI string in the buyer's language.
  String t(String key, [Map<String, Object?> args = const {}]) =>
      AppScope._of(this, listen: true).services.locale.t(key, args);
}
