import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api.dart';
import '../core/providers.dart';
import 'widgets.dart';

class SubscriptionsPage extends ConsumerWidget {
  const SubscriptionsPage({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final subs = ref.watch(subscriptionsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Subscriptions'), actions: [
        IconButton(tooltip: 'Import bank CSV', onPressed: () => _import(context, ref), icon: const Icon(Icons.upload_file)),
        IconButton(onPressed: () => ref.invalidate(subscriptionsProvider), icon: const Icon(Icons.refresh)),
      ]),
      body: subs.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorRetry(describeError(e), onRetry: () => ref.invalidate(subscriptionsProvider)),
        data: (d) {
          final (monthly, items) = d;
          if (items.isEmpty) {
            return EmptyState(
              icon: Icons.autorenew,
              title: 'No recurring charges found yet.',
              hint: 'Receipts from Gmail feed this automatically. For the full picture, export a CSV from your bank or card and import it here.',
            );
          }
          return ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 24), children: [
            Card(
              color: Theme.of(context).colorScheme.tertiaryContainer,
              child: ListTile(
                leading: const Icon(Icons.autorenew),
                title: Text('${money.format(monthly)} / month', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
                subtitle: Text('${items.length} recurring charges · ${money.format(monthly * 12)} a year'),
              ),
            ),
            for (final s in items)
              Card(
                child: ListTile(
                  leading: Icon(s.flaggedCancel ? Icons.cancel_schedule_send : s.acknowledged ? Icons.check_circle : Icons.help_outline,
                      color: s.flaggedCancel ? Theme.of(context).colorScheme.error : s.acknowledged ? Colors.green : null),
                  title: Text(s.merchant.split(' ').map((w) => w.isEmpty ? w : w[0].toUpperCase() + w.substring(1)).join(' ')),
                  subtitle: Text('${money.format(s.amount)} ${s.cadence} · next ~${shortDate.format(s.nextExpected)} · ${(s.confidence * 100).round()}% sure'),
                  trailing: PopupMenuButton<String>(
                    onSelected: (v) async {
                      final api = ref.read(apiProvider);
                      if (v == 'ack') await api.subAck(s.id);
                      if (v == 'cancel') await api.subFlag(s.id);
                      ref.invalidate(subscriptionsProvider);
                    },
                    itemBuilder: (_) => const [
                      PopupMenuItem(value: 'ack', child: Text('Keep it (I know about this)')),
                      PopupMenuItem(value: 'cancel', child: Text('Remind me to cancel')),
                    ],
                  ),
                ),
              ),
          ]);
        },
      ),
    );
  }

  Future<void> _import(BuildContext context, WidgetRef ref) async {
    const group = XTypeGroup(label: 'CSV', extensions: ['csv']);
    final file = await openFile(acceptedTypeGroups: [group]);
    if (file == null) return;
    try {
      final n = await ref.read(apiProvider).importCsv(file.name, await file.readAsBytes());
      await ref.read(apiProvider).runJob('subscriptions');
      ref.invalidate(subscriptionsProvider);
      ref.invalidate(alertsProvider);
      if (context.mounted) toast(context, 'Imported $n transactions and re-ran detection.');
    } catch (e) {
      if (context.mounted) toast(context, describeError(e));
    }
  }
}
