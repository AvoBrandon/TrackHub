"""Parsers are tested against captured payload shapes so a key is not needed to run the suite."""
from app.connectors.aeroapi import parse_status
from app.connectors.bestbuy import parse_open_box
from app.connectors.ebay import parse_search
from app.connectors.keepa import parse_product
from app.connectors.tsa import parse_legacy
from app.connectors.weather import parse_forecast
from app.connectors.hotels import manual_check_links
from datetime import date


def test_bestbuy_open_box_parse():
    payload = {"results": [{"sku": 6418599, "names": {"title": "Sony WH-1000XM5"}, "links": {"web": "https://bby/x"},
                            "offers": [{"condition": "excellent", "prices": {"current": 249.99, "regular": 399.99}},
                                       {"condition": "fair", "prices": {"current": 199.99}}]}]}
    offers = parse_open_box(payload)
    assert len(offers) == 2 and offers[0].condition == "open-box-excellent" and offers[1].price == 199.99


def test_ebay_parse_sorts_by_landed_price():
    payload = {"itemSummaries": [
        {"itemId": "1", "title": "A", "price": {"value": "100.00", "currency": "USD"}, "condition": "New",
         "itemWebUrl": "u1", "shippingOptions": [{"shippingCost": {"value": "25.00"}}], "buyingOptions": ["FIXED_PRICE"]},
        {"itemId": "2", "title": "B", "price": {"value": "110.00", "currency": "USD"}, "condition": "New",
         "itemWebUrl": "u2", "shippingOptions": [{"shippingCost": {"value": "0.00"}}], "buyingOptions": ["FIXED_PRICE"]},
    ]}
    ls = parse_search(payload)
    assert [l.item_id for l in ls] == ["2", "1"] and ls[0].landed == 110.0


def test_keepa_parse_cents():
    p = parse_product({"products": [{"asin": "B0TEST", "title": "Thing", "stats": {"current": [19999, 18950, 15000, -1, -1, -1, -1, -1, -1, 17000]}}]})
    assert p.amazon_price == 199.99 and p.best_new == 189.5 and p.warehouse_price == 170.0


def test_aeroapi_parse_delay():
    f = parse_status({"flights": [{"ident": "DAL123", "status": "Arrived / Delayed", "cancelled": False,
                                   "scheduled_in": "2026-11-01T16:00:00Z", "actual_in": "2026-11-01T19:30:00Z",
                                   "route_distance": 2475, "origin": {"code_iata": "JFK"}, "destination": {"code_iata": "LAX"}}]})
    assert f.arrival_delay.total_seconds() == 3.5 * 3600 and f.distance_km == 3983.1


def test_tsa_legacy_parse():
    rows = parse_legacy("JFK", {"WaitTimes": [{"CheckpointIndex": "4", "WaitTime": "3", "Created_Datetime": "11/13/2026 06:10:00 AM"},
                                              {"CheckpointIndex": "1", "WaitTime": "1", "Created_Datetime": "11/13/2026 06:40:00 AM"}]})
    assert rows[0].checkpoint == "1" and rows[0].minutes == 10 and rows[1].minutes == 30


def test_weather_parse():
    d = parse_forecast({"daily": {"time": ["2026-12-01"], "weather_code": [73], "temperature_2m_max": [1.2],
                                  "temperature_2m_min": [-5.0], "precipitation_probability_max": [80], "wind_speed_10m_max": [30]}})
    assert d[0].summary == "Snow" and d[0].low_c == -5.0


def test_hotel_manual_links():
    l = manual_check_links("Hilton Midtown", "New York", date(2026, 12, 20), date(2026, 12, 23))
    assert "checkin=2026-12-20" in l["google_hotels"] and "booking.com" in l["booking"]
