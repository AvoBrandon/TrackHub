import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api.dart';
import '../core/models.dart';
import '../core/providers.dart';
import 'widgets.dart';

const kindIcon = {
  'return_window': Icons.assignment_return,
  'price_adjust': Icons.price_change,
  'card_protection': Icons.credit_card,
  'open_box': Icons.inventory_2,
  'price_watch': Icons.trending_down,
  'flight_comp': Icons.flight,
  'hotel_rebook': Icons.hotel,
  'tsa_wait': Icons.security,
  'trip_brief': Icons.luggage,
  'subscriptions': Icons.autorenew,
  'system': Icons.info,
};

class InboxPage extends ConsumerWidget {
  const InboxPage({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final alerts = ref.watch(alertsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Inbox'), actions: [
        IconButton(onPressed: () => ref.invalidate(alertsProvider), icon: const Icon(Icons.refresh)),
      ]),
      body: alerts.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorRetry(describeError(e), onRetry: () => ref.invalidate(alertsProvider)),
        data: (list) {
          if (list.isEmpty) {
            return const EmptyState(icon: Icons.inbox, title: 'Nothing owed, nothing expiring.', hint: 'Watchers run on the server around the clock. New money shows up here.');
          }
          final total = list.fold<double>(0, (s, a) => s + a.money);
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(alertsProvider),
            child: ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 24), children: [
              if (total > 0)
                Card(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  child: ListTile(
                    leading: const Icon(Icons.savings),
                    title: Text(money.format(total), style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
                    subtitle: const Text('on the table right now'),
                  ),
                ),
              for (final a in list) _AlertCard(a),
            ]),
          );
        },
      ),
    );
  }
}

class _AlertCard extends ConsumerWidget {
  const _AlertCard(this.a);
  final Alert a;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.read(apiProvider);
    final maps = (a.payload['maps'] as Map?)?.cast<String, dynamic>();
    final links = (a.payload['links'] as Map?)?.cast<String, dynamic>();
    return Dismissible(
      key: ValueKey('alert-${a.id}'),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        decoration: BoxDecoration(color: Theme.of(context).colorScheme.errorContainer, borderRadius: BorderRadius.circular(12)),
        child: const Icon(Icons.delete_outline),
      ),
      onDismissed: (_) async {
        await api.alertDismiss(a.id);
        ref.invalidate(alertsProvider);
      },
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () async {
            if (!a.read) {
              await api.alertRead(a.id);
              ref.invalidate(alertsProvider);
            }
            if (context.mounted) _showDetail(context, ref);
          },
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Icon(kindIcon[a.kind] ?? Icons.notifications, color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 10),
                Expanded(child: Text(a.title, style: TextStyle(fontWeight: a.read ? FontWeight.w500 : FontWeight.w800))),
                MoneyChip(a.money),
              ]),
              const SizedBox(height: 6),
              Text(a.body, maxLines: 3, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodyMedium),
              const SizedBox(height: 6),
              Row(children: [
                Text(dateTime.format(a.createdAt.toLocal()), style: Theme.of(context).textTheme.labelSmall),
                const Spacer(),
                if (maps != null) ...[
                  TextButton.icon(onPressed: () => openUrl(context, maps['apple']), icon: const Icon(Icons.map, size: 18), label: const Text('Apple Maps')),
                  TextButton.icon(onPressed: () => openUrl(context, maps['google']), icon: const Icon(Icons.map_outlined, size: 18), label: const Text('Google')),
                ] else if (links != null)
                  TextButton.icon(onPressed: () => openUrl(context, links.values.first), icon: const Icon(Icons.open_in_new, size: 18), label: const Text('Check price'))
                else if (a.actionUrl.isNotEmpty)
                  TextButton.icon(onPressed: () => openUrl(context, a.actionUrl), icon: const Icon(Icons.open_in_new, size: 18), label: const Text('Open')),
              ]),
            ]),
          ),
        ),
      ),
    );
  }

  void _showDetail(BuildContext context, WidgetRef ref) {
    final maps = (a.payload['maps'] as Map?)?.cast<String, dynamic>();
    final packing = (a.payload['packing'] as List?)?.cast<String>();
    final links = (a.payload['links'] as Map?)?.cast<String, dynamic>();
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (ctx) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: .7,
        builder: (_, ctrl) => ListView(controller: ctrl, padding: const EdgeInsets.fromLTRB(20, 0, 20, 30), children: [
          Row(children: [Expanded(child: Text(a.title, style: Theme.of(ctx).textTheme.titleLarge)), MoneyChip(a.money)]),
          const SizedBox(height: 12),
          SelectableText(a.body),
          if (packing != null) ...[
            const SizedBox(height: 16),
            Text('Packing list', style: Theme.of(ctx).textTheme.titleMedium),
            for (final p in packing) CheckboxListTile(value: false, onChanged: (_) {}, dense: true, title: Text(p), controlAffinity: ListTileControlAffinity.leading),
          ],
          if (maps != null) ...[
            const SizedBox(height: 16),
            Text('Directions (ready to paste)', style: Theme.of(ctx).textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8, children: [
              FilledButton.icon(onPressed: () => openUrl(ctx, maps['apple']), icon: const Icon(Icons.map), label: const Text('Open in Apple Maps')),
              FilledButton.tonalIcon(onPressed: () => openUrl(ctx, maps['google']), icon: const Icon(Icons.map_outlined), label: const Text('Open in Google Maps')),
              OutlinedButton.icon(onPressed: () => copyText(ctx, maps['apple'], label: 'Apple Maps link copied'), icon: const Icon(Icons.copy), label: const Text('Copy Apple link')),
              OutlinedButton.icon(onPressed: () => copyText(ctx, maps['google'], label: 'Google Maps link copied'), icon: const Icon(Icons.copy), label: const Text('Copy Google link')),
            ]),
          ],
          if (links != null) ...[
            const SizedBox(height: 16),
            Text('Compare the same dates', style: Theme.of(ctx).textTheme.titleMedium),
            for (final e in links.entries) ListTile(dense: true, leading: const Icon(Icons.open_in_new), title: Text(e.key.replaceAll('_', ' ')), onTap: () => openUrl(ctx, e.value)),
          ],
          if (a.actionUrl.isNotEmpty && maps == null && links == null) ...[
            const SizedBox(height: 16),
            FilledButton.icon(onPressed: () => openUrl(ctx, a.actionUrl), icon: const Icon(Icons.open_in_new), label: const Text('Open')),
          ],
          const SizedBox(height: 16),
          TextButton.icon(
            onPressed: () async {
              await ref.read(apiProvider).alertDismiss(a.id);
              ref.invalidate(alertsProvider);
              if (ctx.mounted) Navigator.pop(ctx);
            },
            icon: const Icon(Icons.check),
            label: const Text('Done, dismiss'),
          ),
        ]),
      ),
    );
  }
}
