import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

import 'app/app.dart';
import 'app/scope.dart';
import 'app/services.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (kReleaseMode) {
    // Nothing the app knows ends up in logcat in a release build.
    debugPrint = (String? message, {int? wrapWidth}) {};
  }
  final services = await AppServices.create();
  unawaited(services.auth.bootstrap());
  runApp(AppScope(services: services, child: const KetoshopApp()));
}
