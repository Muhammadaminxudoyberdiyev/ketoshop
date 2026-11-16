import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../cart/cart_screen.dart';
import '../catalog/catalog_screen.dart';
import '../orders/orders_screen.dart';
import '../profile/profile_screen.dart';
import '../search/search_screen.dart';

enum HomeTab { catalog, search, cart, orders, profile }

/// The five tabs. A tab is built the first time it is opened and then kept
/// alive, so switching back is instant and keeps its scroll position.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  static void go(BuildContext context, HomeTab tab) =>
      context.findAncestorStateOfType<_HomeShellState>()?._select(tab.index);

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;
  final _built = <int>{0};
  final _ordersKey = GlobalKey<OrdersScreenState>();

  /// Orders and profile show personal data: no screenshots there.
  static const _secureTabs = {3, 4};

  late final _secure = context.services.secure;

  @override
  void initState() {
    super.initState();
    _secure.setTab(false);
  }

  @override
  void dispose() {
    _secure.setTab(false);
    super.dispose();
  }

  void _select(int index) {
    final orders = _ordersKey.currentState;
    if (index == HomeTab.orders.index && orders != null) unawaited(orders.reload());
    setState(() {
      _index = index;
      _built.add(index);
    });
    _secure.setTab(_secureTabs.contains(index));
  }

  Widget _tab(int index) => switch (HomeTab.values[index]) {
        HomeTab.catalog => const CatalogScreen(),
        HomeTab.search => const SearchScreen(),
        HomeTab.cart => const CartScreen(),
        HomeTab.orders => OrdersScreen(key: _ordersKey),
        HomeTab.profile => const ProfileScreen(),
      };

  @override
  Widget build(BuildContext context) {
    final cart = context.services.cart;
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: [for (var i = 0; i < HomeTab.values.length; i++) _built.contains(i) ? _tab(i) : const SizedBox()],
      ),
      bottomNavigationBar: ListenableBuilder(
        listenable: cart,
        builder: (context, _) => NavigationBar(
          selectedIndex: _index,
          onDestinationSelected: _select,
          destinations: [
            NavigationDestination(icon: const Icon(Icons.storefront_outlined), selectedIcon: const Icon(Icons.storefront),
                label: context.t('nav_catalog')),
            NavigationDestination(icon: const Icon(Icons.search), label: context.t('nav_search')),
            NavigationDestination(
              icon: Badge(
                isLabelVisible: cart.cart.count > 0,
                label: Text('${cart.cart.count}'),
                child: const Icon(Icons.shopping_cart_outlined),
              ),
              selectedIcon: const Icon(Icons.shopping_cart),
              label: context.t('nav_cart'),
            ),
            NavigationDestination(icon: const Icon(Icons.receipt_long_outlined), selectedIcon: const Icon(Icons.receipt_long),
                label: context.t('nav_orders')),
            NavigationDestination(icon: const Icon(Icons.person_outline), selectedIcon: const Icon(Icons.person),
                label: context.t('nav_profile')),
          ],
        ),
      ),
    );
  }
}
