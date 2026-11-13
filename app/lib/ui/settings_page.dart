import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api.dart';
import '../core/providers.dart';
import 'widgets.dart';

class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});
  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  late final TextEditingController url;
  late final TextEditingController token;
  bool _seeded = false;

  @override
  void initState() {
    super.initState();
    url = TextEditingController();
    token = TextEditingController();
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(settingsProvider);
    if (!_seeded && (s.baseUrl.isNotEmpty || s.token.isNotEmpty)) {
      url.text = s.baseUrl;
      token.text = s.token;
      _seeded = true;
    }
    final health = ref.watch(healthProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Server & health')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text('Your server', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        TextField(controller: url, decoration: const InputDecoration(labelText: 'Server URL', hintText: 'http://192.168.1.20:8787 or https://clawback.yourdomain.com', border: OutlineInputBorder())),
        const SizedBox(height: 10),
        TextField(controller: token, obscureText: true, decoration: const InputDecoration(labelText: 'API token (API_TOKEN in backend/.env)', border: OutlineInputBorder())),
        const SizedBox(height: 10),
        FilledButton.icon(
          onPressed: () async {
            await ref.read(settingsProvider.notifier).save(baseUrl: url.text, token: token.text);
            ref.invalidate(healthProvider);
            refreshAll(ref);
          },
          icon: const Icon(Icons.save),
          label: const Text('Save & test'),
        ),
        const SizedBox(height: 24),
        health.when(
          loading: () => const LinearProgressIndicator(),
          error: (e, _) => Card(color: Theme.of(context).colorScheme.errorContainer, child: ListTile(leading: const Icon(Icons.error), title: const Text('Not connected'), subtitle: Text(describeError(e)))),
          data: (h) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Card(color: Colors.green.withValues(alpha: .15), child: ListTile(leading: const Icon(Icons.check_circle, color: Colors.green), title: Text('Connected · server v${h.version}'), subtitle: Text(h.apns ? 'iPhone push: on' : 'iPhone push: not configured (Windows toasts still work)'))),
            const SizedBox(height: 16),
            Text('Data sources', style: Theme.of(context).textTheme.titleMedium),
            for (final c in h.connectors)
              ListTile(
                dense: true,
                leading: Icon(c.configured ? Icons.check_circle : Icons.radio_button_unchecked, color: c.configured ? Colors.green : Colors.orange),
                title: Text('${c.name}${c.official ? '' : ' (unofficial feed)'}'),
                subtitle: Text(c.configured ? 'ready' : 'not configured · ${c.note}'),
              ),
            const SizedBox(height: 16),
            Text('Watchers', style: Theme.of(context).textTheme.titleMedium),
            for (final j in h.jobs)
              ListTile(
                dense: true,
                leading: Icon(j.ok == null ? Icons.schedule : j.ok! ? Icons.check_circle : Icons.error, color: j.ok == null ? null : j.ok! ? Colors.green : Theme.of(context).colorScheme.error),
                title: Text(j.name.replaceAll('_', ' ')),
                subtitle: Text(j.at == null ? 'has not run yet' : '${dateTime.format(j.at!.toLocal())} · ${j.detail}', maxLines: 2, overflow: TextOverflow.ellipsis),
                trailing: IconButton(
                  tooltip: 'Run now',
                  icon: const Icon(Icons.play_arrow),
                  onPressed: () async {
                    try {
                      final r = await ref.read(apiProvider).runJob(j.name);
                      if (context.mounted) toast(context, '${j.name}: ${r['detail']}');
                      ref.invalidate(healthProvider);
                      refreshAll(ref);
                    } catch (e) {
                      if (context.mounted) toast(context, describeError(e));
                    }
                  },
                ),
              ),
          ]),
        ),
      ]),
    );
  }
}
