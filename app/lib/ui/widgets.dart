import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

final money = NumberFormat.currency(symbol: '\$');
final shortDate = DateFormat('EEE, MMM d');
final dateTime = DateFormat('MMM d, h:mm a');

class MoneyChip extends StatelessWidget {
  const MoneyChip(this.amount, {super.key});
  final double amount;
  @override
  Widget build(BuildContext context) {
    if (amount <= 0) return const SizedBox.shrink();
    final c = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: c.primaryContainer, borderRadius: BorderRadius.circular(999)),
      child: Text(money.format(amount), style: TextStyle(color: c.onPrimaryContainer, fontWeight: FontWeight.w700)),
    );
  }
}

Color urgencyColor(BuildContext context, String urgency) {
  final c = Theme.of(context).colorScheme;
  switch (urgency) {
    case 'critical':
      return c.error;
    case 'soon':
      return Colors.orange.shade700;
    case 'closed':
      return c.outline;
    default:
      return Colors.green.shade600;
  }
}

class CountdownChip extends StatelessWidget {
  const CountdownChip({super.key, required this.daysLeft, required this.urgency});
  final int? daysLeft;
  final String urgency;
  @override
  Widget build(BuildContext context) {
    final color = urgencyColor(context, urgency);
    final text = daysLeft == null
        ? 'no returns'
        : daysLeft! < 0
            ? 'closed'
            : daysLeft == 0
                ? 'TODAY'
                : '$daysLeft day${daysLeft == 1 ? '' : 's'}';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(color: color.withValues(alpha: .14), borderRadius: BorderRadius.circular(8), border: Border.all(color: color)),
      child: Text(text, style: TextStyle(color: color, fontWeight: FontWeight.w800, letterSpacing: .3)),
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.icon, required this.title, this.hint});
  final IconData icon;
  final String title;
  final String? hint;
  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 56, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleMedium, textAlign: TextAlign.center),
            if (hint != null) ...[const SizedBox(height: 6), Text(hint!, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall)],
          ]),
        ),
      );
}

class ErrorRetry extends StatelessWidget {
  const ErrorRetry(this.message, {super.key, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.cloud_off, size: 48, color: Theme.of(context).colorScheme.error),
            const SizedBox(height: 10),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh), label: const Text('Retry')),
          ]),
        ),
      );
}

Future<void> openUrl(BuildContext context, String url) async {
  if (url.isEmpty) return;
  final ok = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  if (!ok && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not open $url')));
  }
}

Future<void> copyText(BuildContext context, String text, {String label = 'Copied'}) async {
  await Clipboard.setData(ClipboardData(text: text));
  if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(label), duration: const Duration(seconds: 1)));
}

void toast(BuildContext context, String msg) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

/// Simple labelled text field used by the "add" sheets.
class Field extends StatelessWidget {
  const Field(this.label, this.controller, {super.key, this.hint, this.keyboard, this.required = false});
  final String label;
  final String? hint;
  final TextEditingController controller;
  final TextInputType? keyboard;
  final bool required;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: TextFormField(
          controller: controller,
          keyboardType: keyboard,
          decoration: InputDecoration(labelText: label, hintText: hint, border: const OutlineInputBorder(), isDense: true),
          validator: required ? (v) => (v == null || v.trim().isEmpty) ? 'Required' : null : null,
        ),
      );
}

Future<void> showFormSheet(BuildContext context, {required String title, required List<Widget> fields, required Future<void> Function() onSave}) {
  final formKey = GlobalKey<FormState>();
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (ctx) => Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, MediaQuery.of(ctx).viewInsets.bottom + 20),
      child: Form(
        key: formKey,
        child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text(title, style: Theme.of(ctx).textTheme.titleLarge),
            const SizedBox(height: 14),
            ...fields,
            FilledButton(
              onPressed: () async {
                if (!(formKey.currentState?.validate() ?? false)) return;
                try {
                  await onSave();
                  if (ctx.mounted) Navigator.pop(ctx);
                } catch (e) {
                  if (ctx.mounted) toast(ctx, e.toString());
                }
              },
              child: const Text('Save'),
            ),
          ]),
        ),
      ),
    ),
  );
}
