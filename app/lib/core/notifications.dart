import 'dart:io' show Platform;

import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'models.dart';

/// Local notifications: on Windows this is the only channel (the app polls and toasts).
/// On iOS the backend pushes via APNs; local notifications cover the foreground case.
class Notifications {
  static final _plugin = FlutterLocalNotificationsPlugin();
  static bool _ready = false;

  static Future<void> init() async {
    if (_ready) return;
    const ios = DarwinInitializationSettings(requestAlertPermission: true, requestBadgePermission: true, requestSoundPermission: true);
    const windows = WindowsInitializationSettings(
      appName: 'Clawback',
      appUserModelId: 'com.clawback.app',
      guid: '7f3e9b2a-4c1d-4a8e-9f6b-2d5c8e1a3b47',
    );
    const settings = InitializationSettings(iOS: ios, windows: windows);
    try {
      await _plugin.initialize(settings: settings);
      _ready = true;
    } catch (_) {
      _ready = false; // unsupported platform in tests
    }
  }

  static Future<void> show(Alert a) async {
    if (!_ready || !(Platform.isWindows || Platform.isIOS)) return;
    final details = NotificationDetails(
      iOS: const DarwinNotificationDetails(presentAlert: true, presentSound: true),
      windows: WindowsNotificationDetails(),
    );
    final body = a.money > 0 ? '\$${a.money.toStringAsFixed(2)} at stake · ${a.body}' : a.body;
    await _plugin.show(id: a.id, title: a.title, body: body.length > 200 ? '${body.substring(0, 197)}…' : body, notificationDetails: details, payload: '${a.id}');
  }
}
