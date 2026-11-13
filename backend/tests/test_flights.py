from datetime import datetime, timedelta

from app.models import Flight
from app.rules.flights import evaluate, total_at_stake


def mk(**kw):
    base = dict(confirmation="ABC", airline_iata="DL", flight_number="DL1", origin="JFK", destination="LAX",
                scheduled_departure=datetime(2026, 11, 1, 8), scheduled_arrival=datetime(2026, 11, 1, 11),
                distance_km=4000, fare_paid=350.0)
    base.update(kw)
    return Flight(**base)


def test_us_domestic_delay_3h_refund_only():
    f = mk(actual_arrival=datetime(2026, 11, 1, 14, 5))
    c = evaluate(f)
    assert [x.regime for x in c] == ["US DOT refund"]
    assert c[0].amount == 350.0


def test_us_domestic_2h_nothing():
    assert evaluate(mk(actual_arrival=datetime(2026, 11, 1, 13))) == []


def test_eu261_long_haul_cancelled_600():
    f = mk(origin="CDG", destination="JFK", origin_country="FR", destination_country="US", airline_country="FR",
           cancelled=True, distance_km=5800)
    c = evaluate(f)
    regimes = {x.regime: x for x in c}
    assert regimes["EU261"].amount == 600
    assert "US DOT refund" in regimes  # arrives in US, cancelled


def test_eu261_long_haul_3_to_4h_halved():
    f = mk(origin="FRA", destination="JFK", origin_country="DE", destination_country="US", airline_country="DE",
           distance_km=6200, actual_arrival=datetime(2026, 11, 1, 14, 30))
    eu = [x for x in evaluate(f) if x.regime == "EU261"][0]
    assert eu.amount == 300


def test_eu_inbound_on_us_carrier_not_covered():
    f = mk(origin="JFK", destination="CDG", origin_country="US", destination_country="FR", airline_country="US",
           distance_km=5800, actual_arrival=datetime(2026, 11, 1, 15))
    assert all(x.regime != "EU261" for x in evaluate(f))


def test_uk261_short():
    f = mk(origin="LHR", destination="DUB", origin_country="GB", destination_country="IE", airline_country="GB",
           distance_km=450, actual_arrival=datetime(2026, 11, 1, 14, 30))
    uk = [x for x in evaluate(f) if x.regime == "UK261"][0]
    assert uk.amount == 220


def test_canada_appr_bands():
    f = mk(origin="YYZ", destination="YVR", origin_country="CA", destination_country="CA", airline_country="CA",
           actual_arrival=datetime(2026, 11, 1, 18, 30))  # 7.5h
    ca = [x for x in evaluate(f) if x.regime == "Canada APPR"][0]
    assert ca.amount == 700
    assert total_at_stake(evaluate(f)) == 700
