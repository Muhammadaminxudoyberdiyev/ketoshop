import 'package:flutter/material.dart';

/// Design tokens — the one place to change when the app is redesigned.
/// Screens use Theme.of(context) and these constants, never raw colors or
/// sizes of their own.
abstract final class Tokens {
  static const Color brand = Color(0xFF2E7D32);
  static const Color accent = Color(0xFFFFA000);
  static const Color sale = Color(0xFFD84315);
  static const Color success = Color(0xFF2E7D32);

  static const double gap = 8;
  static const double pad = 16;
  static const double radius = 16;
  static const double radiusSmall = 10;
  static const double tileAspect = 0.66;

  static const Duration fast = Duration(milliseconds: 180);
}

ThemeData buildTheme(Brightness brightness) {
  final scheme = ColorScheme.fromSeed(seedColor: Tokens.brand, brightness: brightness);
  final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(Tokens.radius));
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: scheme.surface,
    appBarTheme: AppBarTheme(centerTitle: false, backgroundColor: scheme.surface, scrolledUnderElevation: 1),
    cardTheme: CardThemeData(shape: shape, margin: EdgeInsets.zero, clipBehavior: Clip.antiAlias, elevation: 0,
        color: scheme.surfaceContainerLow),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Tokens.radiusSmall)),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Tokens.radiusSmall)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(Tokens.radiusSmall), borderSide: BorderSide.none),
    ),
    chipTheme: ChipThemeData(shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20))),
    snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
    pageTransitionsTheme: const PageTransitionsTheme(builders: {
      TargetPlatform.android: PredictiveBackPageTransitionsBuilder(),
    }),
  );
}
