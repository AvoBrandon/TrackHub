import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api.dart';
import '../core/models.dart';
import '../core/providers.dart';
import 'widgets.dart';

class ReturnsPage extends ConsumerStatefulWidget {
  const ReturnsPage({super.key});
  @override
  ConsumerState<ReturnsPage> createState() => _ReturnsPageState();
}

class _ReturnsPageState extends ConsumerState<ReturnsPage> {
  bool showClosed = false;

  @override
  Widget build(BuildContext context) {
    final purchases = ref.watch(purchasesProvider(showClosed));
    return Scaffold(
      appBar: AppBar(title: const Text('Return windows'), actions: [
        IconButton(
          tooltip: showClosed ? 'Hide closed' : 'Show closed',
          onPressed: () => setState(() => showClosed = !showClosed),
          icon: Icon(showClosed ? Icons.visibility_off : Icons.history),
        ),
        IconButton(onPressed: () => ref.invalidate(purchasesProvider), icon: const Icon(Icons.refresh)),
      ]),
      floatingActionButton: FloatingActionButton.extended(onPressed: () => _add(context), icon: const Icon(Icons.add), label: const Text('Purchase')),
      body: purchases.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorRetry(describeError(e), onRetry: () => ref.invalidate(purchasesProvider)),
        data: (list) => list.isEmpty
            ? const EmptyState(icon: Icons.assignment_return, title: 'No open return windows.', hint: 'Connect Gmail on the server to import Amazon, Best Buy and eBay orders automatically, or add one with +.')
            : RefreshIndicator(
                onRefresh: () async => ref.invalidate(purchasesProvider),
                child: ListView.builder(
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 90),
                  itemCount: list.length,
                  itemBuilder: (_, i) => _PurchaseTile(list[i]),
                ),
              ),
      ),
    );
  }

  Future<void> _add(BuildContext context) async {
    final name = TextEditingController(), price = TextEditingController(), order = TextEditingController();
    final bought = TextEditingController(text: DateTime.now().toIso8601String().substring(0, 10));
    final delivered = TextEditingController(), sku = TextEditingController(), card = TextEditingController();
    String retailer = 'amazon', category = '', membership = '';
    await showFormSheet(context, title: 'Add a purchase', fields: [
      StatefulBuilder(
        builder: (ctx, setS) => Column(children: [
          DropdownButtonFormField<String>(
            initialValue: retailer,
            decoration: const InputDecoration(labelText: 'Retailer', border: OutlineInputBorder(), isDense: true),
            items: const [
              DropdownMenuItem(value: 'amazon', child: Text('Amazon')),
              DropdownMenuItem(value: 'bestbuy', child: Text('Best Buy')),
              DropdownMenuItem(value: 'ebay', child: Text('eBay')),
              DropdownMenuItem(value: 'other', child: Text('Other')),
            ],
            onChanged: (v) => setS(() => retailer = v ?? 'amazon'),
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            initialValue: category,
            decoration: const InputDecoration(labelText: 'Category (affects the rule)', border: OutlineInputBorder(), isDense: true),
            items: const [
              DropdownMenuItem(value: '', child: Text('General')),
              DropdownMenuItem(value: 'apple', child: Text('Apple product')),
              DropdownMenuItem(value: 'phone', child: Text('Phone / activatable device')),
              DropdownMenuItem(value: 'appliance', child: Text('Major appliance')),
            ],
            onChanged: (v) => setS(() => category = v ?? ''),
          ),
          const SizedBox(height: 10),
          if (retailer == 'bestbuy')
            DropdownButtonFormField<String>(
              initialValue: membership,
              decoration: const InputDecoration(labelText: 'My Best Buy membership', border: OutlineInputBorder(), isDense: true),
              items: const [
                DropdownMenuItem(value: '', child: Text('None (15 days)')),
                DropdownMenuItem(value: 'plus', child: Text('Plus (60 days)')),
                DropdownMenuItem(value: 'total', child: Text('Total (60 days)')),
              ],
              onChanged: (v) => setS(() => membership = v ?? ''),
            ),
          if (retailer == 'bestbuy') const SizedBox(height: 10),
        ]),
      ),
      Field('Item', name, required: true),
      Field('Price', price, keyboard: const TextInputType.numberWithOptions(decimal: true), required: true),
      Field('Order number', order, required: true),
      Field('Purchased on (YYYY-MM-DD)', bought, required: true),
      Field('Delivered on (optional)', delivered, hint: 'YYYY-MM-DD'),
      Field('SKU / ASIN (optional, enables price-drop checks)', sku),
      Field('Card used (optional, e.g. Capital One Venture X World Elite)', card),
    ], onSave: () async {
      await ref.read(apiProvider).addPurchase({
        'retailer': retailer,
        'order_id': order.text.trim(),
        'item_name': name.text.trim(),
        'price': double.parse(price.text.replaceAll(RegExp(r'[^0-9.]'), '')),
        'purchased_on': bought.text.trim(),
        if (delivered.text.trim().isNotEmpty) 'delivered_on': delivered.text.trim(),
        'sku': sku.text.trim(),
        'category': category,
        'bestbuy_membership': membership,
        'card_product': card.text.trim(),
      });
      ref.invalidate(purchasesProvider);
    });
  }
}

class _PurchaseTile extends ConsumerWidget {
  const _PurchaseTile(this.p);
  final Purchase p;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: ListTile(
        leading: CountdownChip(daysLeft: p.daysLeft, urgency: p.urgency),
        title: Text(p.itemName, maxLines: 2, overflow: TextOverflow.ellipsis),
        subtitle: Text([
          '${money.format(p.price)} · ${p.retailer == 'bestbuy' ? 'Best Buy' : p.retailer[0].toUpperCase() + p.retailer.substring(1)}',
          if (p.deadline != null) 'Return by ${shortDate.format(p.deadline!)}${p.holiday ? ' (holiday extension)' : ''}',
        ].join('\n')),
        isThreeLine: p.deadline != null,
        trailing: PopupMenuButton<String>(
          onSelected: (v) async {
            final api = ref.read(apiProvider);
            if (v == 'returned') await api.markReturned(p.id);
            if (v == 'delete') await api.deletePurchase(p.id);
            if (v == 'rule' && context.mounted) {
              showDialog(context: context, builder: (_) => AlertDialog(title: const Text('Why this deadline'), content: Text(p.rule), actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('OK'))]));
              return;
            }
            ref.invalidate(purchasesProvider);
          },
          itemBuilder: (_) => const [
            PopupMenuItem(value: 'rule', child: Text('Why this deadline?')),
            PopupMenuItem(value: 'returned', child: Text('Mark returned')),
            PopupMenuItem(value: 'delete', child: Text('Delete')),
          ],
        ),
      ),
    );
  }
}
