import 'package:dio/dio.dart';

import 'models.dart';

class ApiClient {
  ApiClient(this.baseUrl, this.token)
      : _dio = Dio(BaseOptions(
          baseUrl: baseUrl,
          connectTimeout: const Duration(seconds: 8),
          receiveTimeout: const Duration(seconds: 20),
          headers: {'Authorization': 'Bearer $token'},
        ));
  final String baseUrl, token;
  final Dio _dio;

  bool get isConfigured => baseUrl.isNotEmpty && token.isNotEmpty;

  Future<Health> health() async => Health.fromJson((await _dio.get('/health')).data);

  Future<List<Alert>> alerts({bool unreadOnly = false}) async {
    final r = await _dio.get('/api/alerts', queryParameters: {'unread_only': unreadOnly});
    return (r.data as List).map((j) => Alert.fromJson(j)).toList();
  }

  Future<void> alertRead(int id) => _dio.post('/api/alerts/$id/read');
  Future<void> alertDismiss(int id) => _dio.post('/api/alerts/$id/dismiss');

  Future<List<Purchase>> purchases({bool includeClosed = false}) async {
    final r = await _dio.get('/api/purchases', queryParameters: {'include_closed': includeClosed});
    return (r.data as List).map((j) => Purchase.fromJson(j)).toList();
  }

  Future<void> addPurchase(Map<String, dynamic> body) => _dio.post('/api/purchases', data: body);
  Future<void> markReturned(int id) => _dio.post('/api/purchases/$id/returned');
  Future<void> deletePurchase(int id) => _dio.delete('/api/purchases/$id');

  Future<List<Watch>> watches() async => ((await _dio.get('/api/watches')).data as List).map((j) => Watch.fromJson(j)).toList();
  Future<void> addWatch(Map<String, dynamic> body) => _dio.post('/api/watches', data: body);
  Future<void> deleteWatch(int id) => _dio.delete('/api/watches/$id');

  Future<List<Flight>> flights() async => ((await _dio.get('/api/flights')).data as List).map((j) => Flight.fromJson(j)).toList();
  Future<void> addFlight(Map<String, dynamic> body) => _dio.post('/api/flights', data: body);
  Future<List<Hotel>> hotels() async => ((await _dio.get('/api/hotels')).data as List).map((j) => Hotel.fromJson(j)).toList();
  Future<void> addHotel(Map<String, dynamic> body) => _dio.post('/api/hotels', data: body);
  Future<List<Trip>> trips() async => ((await _dio.get('/api/trips')).data as List).map((j) => Trip.fromJson(j)).toList();
  Future<void> addTrip(Map<String, dynamic> body) => _dio.post('/api/trips', data: body);
  Future<Brief> brief(int tripId) async => Brief.fromJson((await _dio.get('/api/trips/$tripId/brief')).data);

  Future<(double, List<Subscription>)> subscriptions() async {
    final r = await _dio.get('/api/subscriptions');
    return (
      (r.data['monthly_total'] as num).toDouble(),
      (r.data['items'] as List).map((j) => Subscription.fromJson(j)).toList(),
    );
  }

  Future<void> subAck(int id) => _dio.post('/api/subscriptions/$id/ack');
  Future<void> subFlag(int id) => _dio.post('/api/subscriptions/$id/flag-cancel');

  Future<int> importCsv(String filename, List<int> bytes) async {
    final form = FormData.fromMap({'file': MultipartFile.fromBytes(bytes, filename: filename)});
    final r = await _dio.post('/api/transactions/import-csv', data: form);
    return r.data['imported'] as int;
  }

  Future<void> registerDevice(String platform, String token, String name) =>
      _dio.post('/api/devices', data: {'platform': platform, 'token': token, 'name': name});

  Future<Map<String, dynamic>> runJob(String name) async => (await _dio.post('/api/jobs/$name/run')).data;
}

String describeError(Object e) {
  if (e is DioException) {
    if (e.response?.statusCode == 401) return 'Server rejected the token. Check Settings.';
    if (e.type == DioExceptionType.connectionError || e.type == DioExceptionType.connectionTimeout) {
      return 'Cannot reach the server at ${e.requestOptions.baseUrl}. Is it running?';
    }
    return e.response?.data?.toString() ?? e.message ?? 'Network error';
  }
  return e.toString();
}
