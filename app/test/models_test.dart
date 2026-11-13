import 'package:clawback/core/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('alert parses payload and money', () {
    final a = Alert.fromJson({
      'id': 7, 'kind': 'trip_brief', 'title': 'Tomorrow', 'body': 'b', 'money_at_stake': 12.5,
      'created_at': '2026-11-13T18:00:00', 'read_at': null, 'action_url': '',
      'payload': {'maps': {'apple': 'https://maps.apple.com/?saddr=a&daddr=b'}},
    });
    expect(a.money, 12.5);
    expect(a.read, isFalse);
    expect((a.payload['maps'] as Map)['apple'], startsWith('https://maps.apple.com'));
  });

  test('purchase parses countdown fields', () {
    final p = Purchase.fromJson({
      'id': 1, 'retailer': 'bestbuy', 'order_id': 'BBY01-1', 'item_name': 'TV', 'sku': '', 'price': '899.99',
      'purchased_on': '2026-11-01', 'delivered_on': null, 'returned': false, 'deadline': '2027-01-14',
      'days_left': 62, 'urgency': 'ok', 'rule': 'holiday', 'is_holiday_extension': true,
    });
    expect(p.daysLeft, 62);
    expect(p.holiday, isTrue);
    expect(p.price, 899.99);
  });

  test('health parses jobs map', () {
    final h = Health.fromJson({'version': '0.1.0', 'apns_configured': false, 'connectors': [
      {'name': 'bestbuy', 'configured': false, 'official': true, 'note': 'n'}
    ], 'jobs': {'return_windows': {'at': '2026-11-13T08:00:00', 'ok': true, 'detail': 'alerts=1'}, 'push': null}});
    expect(h.jobs.length, 2);
    expect(h.jobs.firstWhere((j) => j.name == 'push').ok, isNull);
    expect(h.connectors.single.configured, isFalse);
  });
}
