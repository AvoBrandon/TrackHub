import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import 'deals_page.dart';
import 'inbox_page.dart';
import 'returns_page.dart';
import 'settings_page.dart';
import 'subscriptions_page.dart';
import 'travel_page.dart';

/// Bottom tabs on phone, navigation rail on a wide Windows window. Same pages either way.
class Shell extends ConsumerStatefulWidget {
  const Shell({super.key});
  @override
  ConsumerState<Shell> createState() => _ShellState();
}

class _ShellState extends ConsumerState<Shell> {
  int index = 0;
  static const pages = [InboxPage(), ReturnsPage(), DealsPage(), TravelPage(), SubscriptionsPage(), SettingsPage()];

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(settingsProvider);
    final unread = ref.watch(alertPollerProvider);
    final wide = MediaQuery.sizeOf(context).width >= 760;
    final dests = [
      _D('Inbox', Icons.inbox_outlined, Icons.inbox, badge: unread),
      const _D('Returns', Icons.assignment_return_outlined, Icons.assignment_return),
      const _D('Deals', Icons.inventory_2_outlined, Icons.inventory_2),
      const _D('Travel', Icons.flight_outlined, Icons.flight),
      const _D('Subs', Icons.autorenew_outlined, Icons.autorenew),
      const _D('Server', Icons.settings_outlined, Icons.settings),
    ];
    final effective = settings.configured ? index : 5; // force Settings until the server is set
    if (wide) {
      return Scaffold(
        body: Row(children: [
          NavigationRail(
            selectedIndex: effective,
            onDestinationSelected: (i) => setState(() => index = i),
            labelType: NavigationRailLabelType.all,
            leading: const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: Icon(Icons.savings, size: 32)),
            destinations: [for (final d in dests) NavigationRailDestination(icon: d.icon(), selectedIcon: Icon(d.selected), label: Text(d.label))],
          ),
          const VerticalDivider(width: 1),
          Expanded(child: pages[effective]),
        ]),
      );
    }
    return Scaffold(
      body: pages[effective],
      bottomNavigationBar: NavigationBar(
        selectedIndex: effective,
        onDestinationSelected: (i) => setState(() => index = i),
        destinations: [for (final d in dests) NavigationDestination(icon: d.icon(), selectedIcon: Icon(d.selected), label: d.label)],
      ),
    );
  }
}

class _D {
  const _D(this.label, this.outlined, this.selected, {this.badge = 0});
  final String label;
  final IconData outlined, selected;
  final int badge;
  Widget icon() => badge > 0 ? Badge.count(count: badge, child: Icon(outlined)) : Icon(outlined);
}
