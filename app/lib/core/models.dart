/// Plain data classes mirroring the backend's JSON. Kept hand-written (no codegen) so the project
/// builds with nothing but `flutter pub get`.
library;

double _d(dynamic v) => v == null ? 0 : (v is num ? v.toDouble() : double.tryParse('$v') ?? 0);
int? _i(dynamic v) => v == null ? null : (v is num ? v.toInt() : int.tryParse('$v'));
DateTime? _dt(dynamic v) => v == null ? null : DateTime.tryParse('$v');

class Alert {
  final int id;
  final String kind, title, body, actionUrl;
  final double money;
  final DateTime createdAt;
  final bool read;
  final Map<String, dynamic> payload;
  Alert.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        kind = j['kind'] ?? 'system',
        title = j['title'] ?? '',
        body = j['body'] ?? '',
        actionUrl = j['action_url'] ?? '',
        money = _d(j['money_at_stake']),
        createdAt = _dt(j['created_at']) ?? DateTime.now(),
        read = j['read_at'] != null,
        payload = (j['payload'] as Map?)?.cast<String, dynamic>() ?? const {};
}

class Purchase {
  final int id;
  final String retailer, orderId, itemName, sku, urgency, rule;
  final double price;
  final DateTime purchasedOn;
  final DateTime? deliveredOn, deadline;
  final int? daysLeft;
  final bool returned, holiday;
  Purchase.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        retailer = j['retailer'],
        orderId = j['order_id'] ?? '',
        itemName = j['item_name'] ?? '',
        sku = j['sku'] ?? '',
        urgency = j['urgency'] ?? 'none',
        rule = j['rule'] ?? '',
        price = _d(j['price']),
        purchasedOn = _dt(j['purchased_on']) ?? DateTime.now(),
        deliveredOn = _dt(j['delivered_on']),
        deadline = _dt(j['deadline']),
        daysLeft = _i(j['days_left']),
        returned = j['returned'] == true,
        holiday = j['is_holiday_extension'] == true;
}

class Watch {
  final int id;
  final String label, bestbuySku, amazonAsin, ebayQuery;
  final double? targetPrice;
  final bool wantOpenBox;
  Watch.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        label = j['label'] ?? '',
        bestbuySku = j['bestbuy_sku'] ?? '',
        amazonAsin = j['amazon_asin'] ?? '',
        ebayQuery = j['ebay_query'] ?? '',
        targetPrice = j['target_price'] == null ? null : _d(j['target_price']),
        wantOpenBox = j['want_open_box'] == true;
}

class Claim {
  final String regime, currency, confidence, reason, nextStep;
  final double amount;
  Claim.fromJson(Map<String, dynamic> j)
      : regime = j['regime'] ?? '',
        currency = j['currency'] ?? '',
        confidence = j['confidence'] ?? '',
        reason = j['reason'] ?? '',
        nextStep = j['next_step'] ?? '',
        amount = _d(j['amount']);
}

class Flight {
  final int id;
  final String confirmation, flightNumber, origin, destination, status;
  final DateTime departure, arrival;
  final bool cancelled;
  final double atStake;
  final List<Claim> claims;
  Flight.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        confirmation = j['confirmation'] ?? '',
        flightNumber = j['flight_number'] ?? '',
        origin = j['origin'] ?? '',
        destination = j['destination'] ?? '',
        status = j['status'] ?? '',
        departure = _dt(j['scheduled_departure']) ?? DateTime.now(),
        arrival = _dt(j['scheduled_arrival']) ?? DateTime.now(),
        cancelled = j['cancelled'] == true,
        atStake = _d(j['at_stake']),
        claims = ((j['claims'] as List?) ?? const []).map((c) => Claim.fromJson(c)).toList();
}

class Hotel {
  final int id;
  final String confirmation, name, city;
  final DateTime checkIn, checkOut;
  final DateTime? freeCancelUntil;
  final double total;
  final double? bestSeen;
  Hotel.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        confirmation = j['confirmation'] ?? '',
        name = j['hotel_name'] ?? '',
        city = j['city'] ?? '',
        checkIn = _dt(j['check_in']) ?? DateTime.now(),
        checkOut = _dt(j['check_out']) ?? DateTime.now(),
        freeCancelUntil = _dt(j['free_cancel_until']),
        total = _d(j['total_price']),
        bestSeen = j['best_seen_price'] == null ? null : _d(j['best_seen_price']);
}

class Trip {
  final int id;
  final String label, originAddress, destinationAddress, city;
  final DateTime travelDate;
  final int? flightId;
  Trip.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        label = j['label'] ?? '',
        originAddress = j['origin_address'] ?? '',
        destinationAddress = j['destination_address'] ?? '',
        city = j['destination_city'] ?? '',
        travelDate = _dt(j['travel_date']) ?? DateTime.now(),
        flightId = _i(j['flight_id']);
}

class Brief {
  final String? flight;
  final String weather;
  final List<String> packing;
  final Map<String, String> maps;
  Brief.fromJson(Map<String, dynamic> j)
      : flight = j['flight'],
        weather = j['weather'] ?? '',
        packing = ((j['packing'] as List?) ?? const []).cast<String>(),
        maps = ((j['maps'] as Map?) ?? const {}).cast<String, String>();
}

class Subscription {
  final int id;
  final String merchant, cadence;
  final double amount, confidence;
  final DateTime nextExpected;
  final bool acknowledged, flaggedCancel;
  Subscription.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        merchant = j['merchant'] ?? '',
        cadence = j['cadence'] ?? 'monthly',
        amount = _d(j['amount']),
        confidence = _d(j['confidence']),
        nextExpected = _dt(j['next_expected']) ?? DateTime.now(),
        acknowledged = j['acknowledged'] == true,
        flaggedCancel = j['flagged_cancel'] == true;
}

class ConnectorStatus {
  final String name, note;
  final bool configured, official;
  ConnectorStatus.fromJson(Map<String, dynamic> j)
      : name = j['name'] ?? '',
        note = j['note'] ?? '',
        configured = j['configured'] == true,
        official = j['official'] != false;
}

class JobStatus {
  final String name, detail;
  final DateTime? at;
  final bool? ok;
  JobStatus(this.name, Map<String, dynamic>? j)
      : detail = j?['detail'] ?? '',
        at = _dt(j?['at']),
        ok = j == null ? null : j['ok'] == true;
}

class Health {
  final String version;
  final bool apns;
  final List<ConnectorStatus> connectors;
  final List<JobStatus> jobs;
  Health.fromJson(Map<String, dynamic> j)
      : version = j['version'] ?? '',
        apns = j['apns_configured'] == true,
        connectors = ((j['connectors'] as List?) ?? const []).map((c) => ConnectorStatus.fromJson(c)).toList(),
        jobs = ((j['jobs'] as Map?) ?? const {}).entries.map((e) => JobStatus(e.key, (e.value as Map?)?.cast<String, dynamic>())).toList();
}
