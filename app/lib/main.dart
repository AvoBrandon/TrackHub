import 'dart:io' show Platform;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tray_manager/tray_manager.dart';
import 'package:window_manager/window_manager.dart';

import 'core/notifications.dart';
import 'core/providers.dart';
import 'ui/shell.dart';

/// iOS: the native side (ios/Runner/AppDelegate.swift) hands us the APNs device token here.
const _apnsChannel = MethodChannel('clawback/apns');

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Notifications.init();
  if (Platform.isWindows) {
    await windowManager.ensureInitialized();
    await windowManager.setPreventClose(true); // close -> hide to tray so the poller keeps running
    await windowManager.setMinimumSize(const Size(420, 600));
  }
  runApp(const ProviderScope(child: ClawbackApp()));
}

class ClawbackApp extends ConsumerStatefulWidget {
  const ClawbackApp({super.key});
  @override
  ConsumerState<ClawbackApp> createState() => _ClawbackAppState();
}

class _ClawbackAppState extends ConsumerState<ClawbackApp> with WindowListener, TrayListener {
  @override
  void initState() {
    super.initState();
    ref.read(alertPollerProvider); // start polling as soon as settings load
    if (Platform.isWindows) {
      windowManager.addListener(this);
      trayManager.addListener(this);
      _setupTray();
    }
    if (Platform.isIOS) {
      _apnsChannel.setMethodCallHandler((call) async {
        if (call.method == 'token') {
          final token = call.arguments as String;
          final s = ref.read(settingsProvider);
          if (s.configured) await ref.read(apiProvider).registerDevice('ios', token, 'iPhone');
        }
      });
    }
  }

  Future<void> _setupTray() async {
    try {
      await trayManager.setIcon('windows/runner/resources/app_icon.ico');
      await trayManager.setToolTip('Clawback – watching for money');
      await trayManager.setContextMenu(Menu(items: [
        MenuItem(key: 'show', label: 'Open'),
        MenuItem.separator(),
        MenuItem(key: 'quit', label: 'Quit'),
      ]));
    } catch (_) {}
  }

  @override
  void onTrayIconMouseDown() => windowManager.show();

  @override
  void onTrayMenuItemClick(MenuItem item) async {
    if (item.key == 'show') await windowManager.show();
    if (item.key == 'quit') {
      await windowManager.setPreventClose(false);
      await windowManager.close();
    }
  }

  @override
  void onWindowClose() async => windowManager.hide();

  @override
  void dispose() {
    if (Platform.isWindows) {
      windowManager.removeListener(this);
      trayManager.removeListener(this);
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final seed = const Color(0xFF1B7F5A);
    return MaterialApp(
      title: 'Clawback',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: seed, useMaterial3: true, brightness: Brightness.light),
      darkTheme: ThemeData(colorSchemeSeed: seed, useMaterial3: true, brightness: Brightness.dark),
      home: const Shell(),
    );
  }
}
