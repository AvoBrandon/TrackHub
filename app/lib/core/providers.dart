import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'models.dart';
import 'notifications.dart';

// ---------------------------------------------------------------- settings
class ServerSettings {
  const ServerSettings({this.baseUrl = '', this.token = '', this.pollSeconds = 60});
  final String baseUrl, token;
  final int pollSeconds;
  bool get configured => baseUrl.isNotEmpty && token.isNotEmpty;
}

class SettingsNotifier extends Notifier<ServerSettings> {
  @override
  ServerSettings build() {
    _load();
    return const ServerSettings();
  }

  Future<void> _load() async {
    final p = await SharedPreferences.getInstance();
    state = ServerSettings(
      baseUrl: p.getString('baseUrl') ?? '',
      token: p.getString('token') ?? '',
      pollSeconds: p.getInt('pollSeconds') ?? 60,
    );
  }

  Future<void> save({required String baseUrl, required String token, int? pollSeconds}) async {
    final p = await SharedPreferences.getInstance();
    final url = baseUrl.trim().replaceAll(RegExp(r'/+$'), '');
    await p.setString('baseUrl', url);
    await p.setString('token', token.trim());
    if (pollSeconds != null) await p.setInt('pollSeconds', pollSeconds);
    state = ServerSettings(baseUrl: url, token: token.trim(), pollSeconds: pollSeconds ?? state.pollSeconds);
  }
}

final settingsProvider = NotifierProvider<SettingsNotifier, ServerSettings>(SettingsNotifier.new);

final apiProvider = Provider<ApiClient>((ref) {
  final s = ref.watch(settingsProvider);
  return ApiClient(s.baseUrl, s.token);
});

// ---------------------------------------------------------------- data
final healthProvider = FutureProvider.autoDispose<Health>((ref) => ref.watch(apiProvider).health());
final alertsProvider = FutureProvider.autoDispose<List<Alert>>((ref) => ref.watch(apiProvider).alerts());
final purchasesProvider = FutureProvider.autoDispose.family<List<Purchase>, bool>(
    (ref, includeClosed) => ref.watch(apiProvider).purchases(includeClosed: includeClosed));
final watchesProvider = FutureProvider.autoDispose<List<Watch>>((ref) => ref.watch(apiProvider).watches());
final flightsProvider = FutureProvider.autoDispose<List<Flight>>((ref) => ref.watch(apiProvider).flights());
final hotelsProvider = FutureProvider.autoDispose<List<Hotel>>((ref) => ref.watch(apiProvider).hotels());
final tripsProvider = FutureProvider.autoDispose<List<Trip>>((ref) => ref.watch(apiProvider).trips());
final briefProvider = FutureProvider.autoDispose.family<Brief, int>((ref, id) => ref.watch(apiProvider).brief(id));
final subscriptionsProvider =
    FutureProvider.autoDispose<(double, List<Subscription>)>((ref) => ref.watch(apiProvider).subscriptions());

/// Refresh everything the current screen might show.
void refreshAll(WidgetRef ref) {
  ref.invalidate(alertsProvider);
  ref.invalidate(purchasesProvider);
  ref.invalidate(watchesProvider);
  ref.invalidate(flightsProvider);
  ref.invalidate(hotelsProvider);
  ref.invalidate(tripsProvider);
  ref.invalidate(subscriptionsProvider);
  ref.invalidate(healthProvider);
}

// ---------------------------------------------------------------- background poller (Windows + iOS foreground)
class AlertPoller extends Notifier<int> {
  Timer? _timer;
  Set<int> _seen = {};
  bool _primed = false;

  @override
  int build() {
    final s = ref.watch(settingsProvider);
    _timer?.cancel();
    if (s.configured) {
      _timer = Timer.periodic(Duration(seconds: s.pollSeconds), (_) => tick());
      Future.microtask(tick);
    }
    ref.onDispose(() => _timer?.cancel());
    return 0;
  }

  Future<void> tick() async {
    try {
      final alerts = await ref.read(apiProvider).alerts(unreadOnly: true);
      final ids = alerts.map((a) => a.id).toSet();
      if (_primed) {
        final fresh = alerts.where((a) => !_seen.contains(a.id));
        // Windows has no server push: toast every new alert. On iOS, APNs already did.
        if (Platform.isWindows) {
          for (final a in fresh) {
            await Notifications.show(a);
          }
        }
        if (fresh.isNotEmpty) ref.invalidate(alertsProvider);
      }
      _seen = ids;
      _primed = true;
      state = alerts.length; // unread badge count
    } catch (_) {
      // server down: keep the old badge, try again next tick
    }
  }
}

final alertPollerProvider = NotifierProvider<AlertPoller, int>(AlertPoller.new);
