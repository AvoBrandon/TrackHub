from datetime import datetime

from app.ingest.parsers.charges import parse_charge
from app.ingest.parsers.common import RawEmail, extract_jsonld
from app.ingest.parsers.retail import delivery_date_update, parse_order
from app.ingest.parsers.travel import parse_flights, parse_hotels
from app.models import Retailer


def mk(sender, subject, html="", text="", when=datetime(2026, 11, 10, 9)):
    return RawEmail("m1", sender, subject, when, html=html, text=text, jsonld=extract_jsonld(html))


def test_amazon_jsonld_order():
    html = """<html><script type="application/ld+json">{"@context":"http://schema.org","@type":"Order",
      "orderNumber":"112-1234567-7654321","orderDate":"2026-11-09",
      "acceptedOffer":[{"@type":"Offer","price":"329.00","itemOffered":{"@type":"Product","name":"Apple AirPods Pro 3","sku":"B0CXXXX"}},
                       {"@type":"Offer","price":"49.99","itemOffered":{"@type":"Product","name":"Anker 65W Charger"}}]}</script>
      <p>Sold by: Amazon.com Services LLC</p></html>"""
    rows = parse_order(mk("Amazon.com <auto-confirm@amazon.com>", "Your Amazon.com order #112-1234567-7654321", html=html))
    assert len(rows) == 2 and rows[0].retailer == Retailer.amazon
    assert rows[0].category == "apple" and rows[0].sku == "B0CXXXX" and rows[0].purchased_on.isoformat() == "2026-11-09"


def test_bestbuy_text_order_with_membership():
    text = """Thanks for your order, Brandon!
Order number: BBY01-806512345678
Sony 65" BRAVIA 8 OLED TV
Qty: 1
$1,699.99
My Best Buy Total member benefits applied.
Subtotal $1,699.99
Tax $150.87
Total $1,850.86"""
    rows = parse_order(mk("BestBuyInfo@emailinfo.bestbuy.com", "Thanks for your order", text=text))
    assert len(rows) == 1
    r = rows[0]
    assert r.order_id == "BBY01-806512345678" and r.price == 1699.99 and r.bestbuy_membership == "total"


def test_delivered_email_updates_delivery_date():
    e = mk("Amazon.com <shipment-tracking@amazon.com>", "Delivered: Your Amazon.com order #112-1234567-7654321",
           text="Your package was delivered. Order #112-1234567-7654321", when=datetime(2026, 11, 12, 15))
    assert delivery_date_update(e) == ("112-1234567-7654321", datetime(2026, 11, 12).date())


def test_flight_jsonld():
    html = """<script type="application/ld+json">{"@type":"FlightReservation","reservationNumber":"ABC123",
      "totalPrice":"412.60","reservationFor":{"@type":"Flight","flightNumber":"1234","airline":{"iataCode":"DL"},
      "departureAirport":{"iataCode":"JFK"},"arrivalAirport":{"iataCode":"CDG"},
      "departureTime":"2026-12-20T18:30:00-05:00","arrivalTime":"2026-12-21T07:45:00+01:00"}}</script>"""
    fl = parse_flights(mk("Delta Air Lines <DeltaAirLines@t.delta.com>", "Your Flight Receipt", html=html))
    assert len(fl) == 1 and fl[0].flight_number == "DL1234" and fl[0].destination_country == "FR" and fl[0].fare_paid == 412.6


def test_flight_regex_fallback():
    text = """Confirmation code: QX7LMP
Flight 1 of 2
Sat, Dec 20, 2026 6:30 PM
JFK to LAX
DL 455 Main Cabin"""
    fl = parse_flights(mk("Delta <no-reply@delta.com>", "Your trip itinerary", text=text))
    assert len(fl) == 1 and fl[0].confirmation == "QX7LMP" and fl[0].flight_number == "DL455"
    assert fl[0].scheduled_departure.month == 12 and fl[0].scheduled_departure.day == 20


def test_hotel_regex_fallback():
    text = """Your reservation is confirmed
Confirmation number: 83921745
Hilton New York Midtown
Check-in: Friday, December 19, 2026
Check-out: Monday, December 22, 2026
Total price: $812.40"""
    hs = parse_hotels(mk("Hilton Reservations <reservations@hilton.com>", "Reservation confirmation", text=text))
    assert len(hs) == 1 and hs[0].total_price == 812.4 and hs[0].check_out.day == 22 and "Hilton" in hs[0].hotel_name


def test_charge_receipt():
    t = parse_charge(mk("Netflix <info@account.netflix.com>", "Your Netflix receipt", text="Total: $15.49 charged to Visa ****4242"))
    assert t and t.amount == 15.49 and "netflix" in t.merchant.lower()
