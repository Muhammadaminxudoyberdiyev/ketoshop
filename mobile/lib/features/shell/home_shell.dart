import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../cart/cart_screen.dart';
import '../catalog/catalog_screen.dart';
import '../orders/orders_screen.dart';
import '../profile/profile_screen.dart';
import '../search/search_screen.dart';
import '../terms/terms_screen.dart';
import '../update/update_views.dart';

enum HomeTab { catalog, search, cart, orders, profile }

/// The shop's tabs. A tab is built the first time it is opened and then kept
/// alive, so switching back is instant and keeps its scroll position. Which
/// tabs exist can be switched on the server (app_config.FEATURES).
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  static void go(BuildContext context, HomeTab tab) =>
      context.findAncestorStateOfType<_HomeShellState>()?._select(tab);

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  HomeTab _current = HomeTab.catalog;
  final _built = <HomeTab>{HomeTab.catalog};
  final _ordersKey = GlobalKey<OrdersScreenState>();
  late final _secure = context.services.secure;

  /// Orders and profile show personal data: no screenshots there.
  static const _secureTabs = {HomeTab.orders, HomeTab.profile};

  @override
  void initState() {
    super.initState();
    _secure.setTab(false);
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      await askToAcceptNewTerms(context);
      if (mounted) unawaited(offerUpdate(context));
    });
  }

  @override
  void dispose() {
    _secure.setTab(false);
    super.dispose();
  }

  List<HomeTab> _visible() {
    final config = context.services.remote.config;
    return [for (final tab in HomeTab.values) if (tab != HomeTab.search || config.enabled('search')) tab];
  }

  void _select(HomeTab tab) {
    final orders = _ordersKey.currentState;
    if (tab == HomeTab.orders && orders != null) unawaited(orders.reload());
    setState(() {
      _current = tab;
      _built.add(tab);
    });
    _secure.setTab(_secureTabs.contains(tab));
  }

  Widget _screen(HomeTab tab) => switch (tab) {
        HomeTab.catalog => const CatalogScreen(),
        HomeTab.search => const SearchScreen(),
        HomeTab.cart => const CartScreen(),
        HomeTab.orders => OrdersScreen(key: _ordersKey),
        HomeTab.profile => const ProfileScreen(),
      };

  NavigationDestination _destination(HomeTab tab, int cartCount) => switch (tab) {
        HomeTab.catalog => NavigationDestination(
            icon: const Icon(Icons.storefront_outlined), selectedIcon: const Icon(Icons.storefront), label: context.t('nav_catalog')),
        HomeTab.search => NavigationDestination(icon: const Icon(Icons.search), label: context.t('nav_search')),
        HomeTab.cart => NavigationDestination(
            icon: Badge(isLabelVisible: cartCount > 0, label: Text('$cartCount'), child: const Icon(Icons.shopping_cart_outlined)),
            selectedIcon: const Icon(Icons.shopping_cart),
            label: context.t('nav_cart'),
          ),
        HomeTab.orders => NavigationDestination(
            icon: const Icon(Icons.receipt_long_outlined), selectedIcon: const Icon(Icons.receipt_long), label: context.t('nav_orders')),
        HomeTab.profile => NavigationDestination(
            icon: const Icon(Icons.person_outline), selectedIcon: const Icon(Icons.person), label: context.t('nav_profile')),
      };

  @override
  Widget build(BuildContext context) {
    final services = context.services;
    return ListenableBuilder(
      listenable: Listenable.merge([services.cart, services.remote]),
      builder: (context, _) {
        final tabs = _visible();
        final current = tabs.contains(_current) ? _current : HomeTab.catalog;
        return Scaffold(
          body: IndexedStack(
            index: tabs.indexOf(current),
            children: [for (final tab in tabs) _built.contains(tab) ? _screen(tab) : const SizedBox()],
          ),
          bottomNavigationBar: NavigationBar(
            selectedIndex: tabs.indexOf(current),
            onDestinationSelected: (i) => _select(tabs[i]),
            destinations: [for (final tab in tabs) _destination(tab, services.cart.cart.count)],
          ),
        );
      },
    );
  }
}
