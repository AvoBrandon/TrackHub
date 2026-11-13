import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api.dart';
import '../core/providers.dart';
import 'widgets.dart';

/// Open-box / cross-market watcher. The server checks Best Buy (new + open-box), Amazon (via Keepa,
/// incl. Warehouse) and eBay every 6 hours and alerts into the Inbox.
class DealsPage extends ConsumerWidget {
  const DealsPage({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final watches = ref.watch(watchesProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Price & open-box watch')),
      floatingActionButton: FloatingActionButton.extended(onPressed: () => _add(context, ref), icon: const Icon(Icons.add_alert), label: const Text('Watch')),
      body: watches.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorRetry(describeError(e), onRetry: () => ref.invalidate(watchesProvider)),
        data: (list) => list.isEmpty
            ? const EmptyState(icon: Icons.inventory_2, title: 'Not watching anything yet.', hint: 'Add a Best Buy SKU, Amazon ASIN or eBay search. You get an alert the moment an open-box unit appears or the price hits your target.')
            : ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 90), children: [
                for (final w in list)
                  Card(
                    child: ListTile(
                      leading: Icon(w.wantOpenBox ? Icons.inventory_2 : Icons.trending_down),
                      title: Text(w.label),
                      subtitle: Text([
                        if (w.bestbuySku.isNotEmpty) 'Best Buy ${w.bestbuySku}',
                        if (w.amazonAsin.isNotEmpty) 'Amazon ${w.amazonAsin}',
                        if (w.ebayQuery.isNotEmpty) 'eBay "${w.ebayQuery}"',
                        if (w.targetPrice != null) 'target ${money.format(w.targetPrice)}',
                      ].join(' · ')),
                      trailing: IconButton(
                        icon: const Icon(Icons.delete_outline),
                        onPressed: () async {
                          await ref.read(apiProvider).deleteWatch(w.id);
                          ref.invalidate(watchesProvider);
                        },
                      ),
                    ),
                  ),
              ]),
      ),
    );
  }

  Future<void> _add(BuildContext context, WidgetRef ref) async {
    final label = TextEditingController(), sku = TextEditingController(), asin = TextEditingController();
    final ebay = TextEditingController(), target = TextEditingController();
    bool openBox = true;
    await showFormSheet(context, title: 'Watch an item everywhere', fields: [
      Field('What is it?', label, required: true, hint: 'Sony WH-1000XM5'),
      Field('Best Buy SKU', sku, hint: 'from the product URL, e.g. 6505727'),
      Field('Amazon ASIN', asin, hint: 'B09XS7JWHH (needs Keepa key on server)'),
      Field('eBay search', ebay, hint: 'sony wh-1000xm5 -case -parts'),
      Field('Target price (optional)', target, keyboard: const TextInputType.numberWithOptions(decimal: true)),
      StatefulBuilder(builder: (ctx, setS) => SwitchListTile(value: openBox, onChanged: (v) => setS(() => openBox = v), title: const Text('Alert on any open-box / warehouse unit'))),
    ], onSave: () async {
      await ref.read(apiProvider).addWatch({
        'label': label.text.trim(),
        'bestbuy_sku': sku.text.trim(),
        'amazon_asin': asin.text.trim(),
        'ebay_query': ebay.text.trim(),
        'target_price': target.text.trim().isEmpty ? null : double.parse(target.text.replaceAll(RegExp(r'[^0-9.]'), '')),
        'want_open_box': openBox,
      });
      ref.invalidate(watchesProvider);
    });
  }
}
