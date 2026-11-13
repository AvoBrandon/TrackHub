import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api.dart';
import '../core/models.dart';
import '../core/providers.dart';
import 'widgets.dart';

class TravelPage extends ConsumerWidget {
  const TravelPage({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Travel'),
          bottom: const TabBar(tabs: [Tab(text: 'Flights'), Tab(text: 'Hotels'), Tab(text: 'Trips')]),
          actions: [IconButton(onPressed: () => refreshAll(ref), icon: const Icon(Icons.refresh))],
        ),
        body: const TabBarView(children: [_Flights(), _Hotels(), _Trips()]),
      ),
    );
  }
}

// ------------------------------------------------------------------ flights
class _Flights extends ConsumerWidget {
  const _Flights();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final flights = ref.watch(flightsProvider);
    return Scaffold(
      floatingActionButton: FloatingActionButton.small(onPressed: () => _add(context, ref), child: const Icon(Icons.add)),
      body: flights.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorRetry(describeError(e), onRetry: () => ref.invalidate(flightsProvider)),
        data: (list) => list.isEmpty
            ? const EmptyState(icon: Icons.flight, title: 'No flights tracked.', hint: 'Airline confirmation emails are imported automatically from Gmail. Delays and cancellations are checked every 15 minutes on travel day.')
            : ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 80), children: [for (final f in list) _FlightCard(f)]),
      ),
    );
  }

  Future<void> _add(BuildContext context, WidgetRef ref) async {
    final conf = TextEditingController(), num = TextEditingController(), from = TextEditingController(), to = TextEditingController();
    final dep = TextEditingController(), arr = TextEditingController(), fare = TextEditingController();
    final fromC = TextEditingController(text: 'US'), toC = TextEditingController(text: 'US'), alC = TextEditingController(text: 'US');
    await showFormSheet(context, title: 'Track a flight', fields: [
      Field('Confirmation code', conf, required: true),
      Field('Flight number', num, required: true, hint: 'DL1234'),
      Field('From (IATA)', from, required: true, hint: 'JFK'),
      Field('To (IATA)', to, required: true, hint: 'CDG'),
      Field('Departs (YYYY-MM-DDTHH:MM local)', dep, required: true),
      Field('Arrives (YYYY-MM-DDTHH:MM local)', arr, required: true),
      Field('Fare paid', fare, keyboard: const TextInputType.numberWithOptions(decimal: true)),
      Row(children: [
        Expanded(child: Field('Origin country', fromC)),
        const SizedBox(width: 8),
        Expanded(child: Field('Dest. country', toC)),
        const SizedBox(width: 8),
        Expanded(child: Field('Airline country', alC)),
      ]),
    ], onSave: () async {
      final fn = num.text.trim().toUpperCase().replaceAll(' ', '');
      await ref.read(apiProvider).addFlight({
        'confirmation': conf.text.trim().toUpperCase(),
        'airline_iata': fn.substring(0, 2),
        'flight_number': fn,
        'origin': from.text.trim().toUpperCase(),
        'destination': to.text.trim().toUpperCase(),
        'scheduled_departure': dep.text.trim(),
        'scheduled_arrival': arr.text.trim(),
        if (fare.text.trim().isNotEmpty) 'fare_paid': double.parse(fare.text.replaceAll(RegExp(r'[^0-9.]'), '')),
        'origin_country': fromC.text.trim().toUpperCase(),
        'destination_country': toC.text.trim().toUpperCase(),
        'airline_country': alC.text.trim().toUpperCase(),
      });
      ref.invalidate(flightsProvider);
      ref.invalidate(tripsProvider);
    });
  }
}

class _FlightCard extends StatelessWidget {
  const _FlightCard(this.f);
  final Flight f;
  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Text('${f.flightNumber}  ${f.origin} → ${f.destination}', style: Theme.of(context).textTheme.titleMedium),
            const Spacer(),
            MoneyChip(f.atStake),
          ]),
          const SizedBox(height: 4),
          Text('${dateTime.format(f.departure)} · ${f.cancelled ? 'CANCELLED' : f.status} · conf ${f.confirmation}', style: Theme.of(context).textTheme.bodySmall),
          for (final cl in f.claims) ...[
            const Divider(height: 18),
            Row(children: [
              Icon(cl.confidence == 'likely' ? Icons.verified : Icons.help_outline, size: 18, color: cl.confidence == 'likely' ? Colors.green : c.outline),
              const SizedBox(width: 6),
              Text('${cl.regime}: ${cl.amount > 0 ? '${cl.amount.toStringAsFixed(0)} ${cl.currency}' : 'expenses'}', style: const TextStyle(fontWeight: FontWeight.w700)),
            ]),
            const SizedBox(height: 4),
            Text(cl.reason, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 2),
            Text(cl.nextStep),
          ],
        ]),
      ),
    );
  }
}

// ------------------------------------------------------------------ hotels
class _Hotels extends ConsumerWidget {
  const _Hotels();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final hotels = ref.watch(hotelsProvider);
    return Scaffold(
      floatingActionButton: FloatingActionButton.small(onPressed: () => _add(context, ref), child: const Icon(Icons.add)),
      body: hotels.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorRetry(describeError(e), onRetry: () => ref.invalidate(hotelsProvider)),
        data: (list) => list.isEmpty
            ? const EmptyState(icon: Icons.hotel, title: 'No hotel bookings.', hint: 'Booked hotels are re-priced nightly. If the same room drops, you get told exactly what to cancel and rebook.')
            : ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 80), children: [
                for (final h in list)
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.hotel),
                      title: Text(h.name),
                      subtitle: Text('${shortDate.format(h.checkIn)} – ${shortDate.format(h.checkOut)} · paid ${money.format(h.total)}'
                          '${h.bestSeen != null ? '\nLowest seen since: ${money.format(h.bestSeen)}' : ''}'
                          '${h.freeCancelUntil != null ? '\nFree cancel until ${dateTime.format(h.freeCancelUntil!)}' : ''}'),
                      isThreeLine: true,
                    ),
                  ),
              ]),
      ),
    );
  }

  Future<void> _add(BuildContext context, WidgetRef ref) async {
    final conf = TextEditingController(), name = TextEditingController(), city = TextEditingController();
    final ci = TextEditingController(), co = TextEditingController(), total = TextEditingController(), cancel = TextEditingController();
    await showFormSheet(context, title: 'Add a hotel booking', fields: [
      Field('Confirmation', conf, required: true),
      Field('Hotel', name, required: true),
      Field('City', city, required: true),
      Field('Check-in (YYYY-MM-DD)', ci, required: true),
      Field('Check-out (YYYY-MM-DD)', co, required: true),
      Field('Total paid', total, required: true, keyboard: const TextInputType.numberWithOptions(decimal: true)),
      Field('Free cancellation until (YYYY-MM-DDTHH:MM, optional)', cancel),
    ], onSave: () async {
      await ref.read(apiProvider).addHotel({
        'confirmation': conf.text.trim(),
        'hotel_name': name.text.trim(),
        'city': city.text.trim(),
        'check_in': ci.text.trim(),
        'check_out': co.text.trim(),
        'total_price': double.parse(total.text.replaceAll(RegExp(r'[^0-9.]'), '')),
        if (cancel.text.trim().isNotEmpty) 'free_cancel_until': cancel.text.trim(),
      });
      ref.invalidate(hotelsProvider);
    });
  }
}

// ------------------------------------------------------------------ trips
class _Trips extends ConsumerWidget {
  const _Trips();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final trips = ref.watch(tripsProvider);
    return Scaffold(
      floatingActionButton: FloatingActionButton.small(onPressed: () => _add(context, ref), child: const Icon(Icons.add)),
      body: trips.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorRetry(describeError(e), onRetry: () => ref.invalidate(tripsProvider)),
        data: (list) => list.isEmpty
            ? const EmptyState(icon: Icons.luggage, title: 'No upcoming trips.', hint: 'Every tracked flight gets a trip automatically. The evening before, you get weather, a packing list and one-tap directions.')
            : ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 80), children: [for (final t in list) _TripTile(t)]),
      ),
    );
  }

  Future<void> _add(BuildContext context, WidgetRef ref) async {
    final label = TextEditingController(), date = TextEditingController(), from = TextEditingController();
    final to = TextEditingController(), city = TextEditingController();
    await showFormSheet(context, title: 'Add a travel day', fields: [
      Field('Label', label, required: true, hint: 'Orlando weekend'),
      Field('Travel date (YYYY-MM-DD)', date, required: true),
      Field('Leaving from (address)', from, required: true),
      Field('Going to (address / terminal)', to, required: true, hint: 'JFK Terminal 4'),
      Field('Destination city (for weather)', city, required: true),
    ], onSave: () async {
      await ref.read(apiProvider).addTrip({
        'label': label.text.trim(),
        'travel_date': date.text.trim(),
        'origin_address': from.text.trim(),
        'destination_address': to.text.trim(),
        'destination_city': city.text.trim(),
      });
      ref.invalidate(tripsProvider);
    });
  }
}

class _TripTile extends ConsumerWidget {
  const _TripTile(this.t);
  final Trip t;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: ListTile(
        leading: const Icon(Icons.luggage),
        title: Text(t.label),
        subtitle: Text('${shortDate.format(t.travelDate)} · ${t.originAddress} → ${t.destinationAddress}'),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => showModalBottomSheet(
          context: context,
          isScrollControlled: true,
          showDragHandle: true,
          builder: (_) => _BriefSheet(t),
        ),
      ),
    );
  }
}

class _BriefSheet extends ConsumerWidget {
  const _BriefSheet(this.t);
  final Trip t;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final brief = ref.watch(briefProvider(t.id));
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: .75,
      builder: (_, ctrl) => brief.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorRetry(describeError(e), onRetry: () => ref.invalidate(briefProvider(t.id))),
        data: (b) => ListView(controller: ctrl, padding: const EdgeInsets.fromLTRB(20, 0, 20, 30), children: [
          Text(t.label, style: Theme.of(context).textTheme.titleLarge),
          Text(shortDate.format(t.travelDate)),
          if (b.flight != null) ...[const SizedBox(height: 8), Text(b.flight!, style: const TextStyle(fontWeight: FontWeight.w700))],
          const SizedBox(height: 16),
          Text('Directions', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 8, children: [
            FilledButton.icon(onPressed: () => openUrl(context, b.maps['apple'] ?? ''), icon: const Icon(Icons.map), label: const Text('Apple Maps')),
            FilledButton.tonalIcon(onPressed: () => openUrl(context, b.maps['google'] ?? ''), icon: const Icon(Icons.map_outlined), label: const Text('Google Maps')),
            OutlinedButton.icon(onPressed: () => openUrl(context, b.maps['google_transit'] ?? ''), icon: const Icon(Icons.train), label: const Text('Transit')),
            OutlinedButton.icon(onPressed: () => copyText(context, b.maps['apple'] ?? ''), icon: const Icon(Icons.copy), label: const Text('Copy Apple link')),
            OutlinedButton.icon(onPressed: () => copyText(context, b.maps['google'] ?? ''), icon: const Icon(Icons.copy), label: const Text('Copy Google link')),
          ]),
          const SizedBox(height: 16),
          Text('Weather in ${t.city}', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          Text(b.weather),
          const SizedBox(height: 16),
          Text('Pack', style: Theme.of(context).textTheme.titleMedium),
          for (final p in b.packing) ListTile(dense: true, leading: const Icon(Icons.check_box_outline_blank, size: 18), title: Text(p), contentPadding: EdgeInsets.zero),
        ]),
      ),
    );
  }
}
