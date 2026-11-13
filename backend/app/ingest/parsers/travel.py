"""Airline + hotel confirmation emails -> Flight / HotelBooking rows. JSON-LD first, regex fallback."""
from __future__ import annotations

import re
from datetime import datetime

from ...models import Flight, HotelBooking
from .common import RawEmail, jsonld_of_type, money, to_date, to_datetime

CONF = re.compile(r"\b(?:confirmation|record locator|booking reference|PNR|confirmation code|confirmation number)\s*[:#]?\s*([A-Z0-9]{5,8})\b", re.I)
FLIGHT = re.compile(r"\b([A-Z]{2})\s?(\d{1,4})\b")
IATA_PAIR = re.compile(r"\b([A-Z]{3})\s*(?:to|-|–|→|>)\s*([A-Z]{3})\b")
AIRLINE_WORDS = ("airlines", "airways", "flight", "itinerary", "boarding", "e-ticket", "eticket")
HOTEL_WORDS = ("hotel", "reservation", "check-in", "check in", "stay", "booking.com", "hotels.com", "expedia", "marriott", "hilton", "hyatt", "ihg", "airbnb")

COUNTRY_BY_IATA = {  # tiny seed; extend in data/airports.csv for everything else
    "JFK": "US", "EWR": "US", "LGA": "US", "LAX": "US", "SFO": "US", "ORD": "US", "ATL": "US", "MIA": "US", "MCO": "US",
    "DFW": "US", "DEN": "US", "SEA": "US", "BOS": "US", "IAD": "US", "DCA": "US", "PHL": "US", "LAS": "US", "PHX": "US",
    "LHR": "GB", "LGW": "GB", "MAN": "GB", "CDG": "FR", "ORY": "FR", "AMS": "NL", "FRA": "DE", "MUC": "DE", "MAD": "ES",
    "BCN": "ES", "FCO": "IT", "MXP": "IT", "DUB": "IE", "LIS": "PT", "ZRH": "CH", "VIE": "AT", "CPH": "DK", "ARN": "SE",
    "OSL": "NO", "HEL": "FI", "BRU": "BE", "YYZ": "CA", "YVR": "CA", "YUL": "CA", "YYC": "CA", "MEX": "MX", "CUN": "MX",
    "NRT": "JP", "HND": "JP", "ICN": "KR", "SIN": "SG", "DXB": "AE", "DOH": "QA", "SYD": "AU", "GRU": "BR", "BOG": "CO",
}
AIRLINE_COUNTRY = {"DL": "US", "UA": "US", "AA": "US", "WN": "US", "B6": "US", "AS": "US", "NK": "US", "F9": "US",
                   "BA": "GB", "VS": "GB", "AF": "FR", "KL": "NL", "LH": "DE", "IB": "ES", "AZ": "IT", "EI": "IE",
                   "TP": "PT", "LX": "CH", "OS": "AT", "SK": "DK", "AY": "FI", "SN": "BE", "AC": "CA", "WS": "CA",
                   "AM": "MX", "JL": "JP", "NH": "JP", "KE": "KR", "SQ": "SG", "EK": "AE", "QR": "QA", "QF": "AU"}


def looks_like_flight(e: RawEmail) -> bool:
    s = f"{e.sender} {e.subject}".lower()
    return any(w in s for w in AIRLINE_WORDS) or bool(jsonld_of_type(e.jsonld, "FlightReservation"))


def looks_like_hotel(e: RawEmail) -> bool:
    s = f"{e.sender} {e.subject}".lower()
    return any(w in s for w in HOTEL_WORDS) or bool(jsonld_of_type(e.jsonld, "LodgingReservation"))


def parse_flights(e: RawEmail) -> list[Flight]:
    out: list[Flight] = []
    for r in jsonld_of_type(e.jsonld, "FlightReservation"):
        f = r.get("reservationFor") or {}
        airline = (f.get("airline") or {}).get("iataCode", "") or ""
        num = str(f.get("flightNumber", ""))
        dep = (f.get("departureAirport") or {}).get("iataCode", "")
        arr = (f.get("arrivalAirport") or {}).get("iataCode", "")
        sd, sa = to_datetime(f.get("departureTime")), to_datetime(f.get("arrivalTime"))
        if not (airline and num and dep and arr and sd and sa):
            continue
        out.append(Flight(confirmation=str(r.get("reservationNumber", "")), airline_iata=airline,
                          flight_number=f"{airline}{num}", origin=dep, destination=arr,
                          scheduled_departure=sd, scheduled_arrival=sa,
                          fare_paid=money((r.get("totalPrice") or r.get("price"))),
                          origin_country=COUNTRY_BY_IATA.get(dep, "US"), destination_country=COUNTRY_BY_IATA.get(arr, "US"),
                          airline_country=AIRLINE_COUNTRY.get(airline, "US"), source_message_id=e.message_id))
    if out or not looks_like_flight(e):
        return out
    # regex fallback: one segment per "XX123 ... AAA to BBB" group near a date
    text = e.plain()
    conf = CONF.search(text)
    confirmation = conf.group(1) if conf else "unknown"
    for pair in IATA_PAIR.finditer(text):
        dep, arr = pair.group(1), pair.group(2)
        if dep not in COUNTRY_BY_IATA and arr not in COUNTRY_BY_IATA:
            continue
        window = text[max(0, pair.start() - 300): pair.end() + 300]
        fm = next((m for m in FLIGHT.finditer(window) if m.group(1) in AIRLINE_COUNTRY), None)
        if not fm:
            continue
        when = to_datetime(_first_date(window)) or e.received
        out.append(Flight(confirmation=confirmation, airline_iata=fm.group(1), flight_number=f"{fm.group(1)}{fm.group(2)}",
                          origin=dep, destination=arr, scheduled_departure=when, scheduled_arrival=when,
                          origin_country=COUNTRY_BY_IATA.get(dep, "US"), destination_country=COUNTRY_BY_IATA.get(arr, "US"),
                          airline_country=AIRLINE_COUNTRY.get(fm.group(1), "US"), source_message_id=e.message_id))
    return _dedupe(out)


_DATE_RX = re.compile(r"\b((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+)?((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,?\s+\d{4})?(?:,?\s+\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)?)")


def _first_date(s: str) -> str | None:
    m = _DATE_RX.search(s)
    return m.group(2) if m else None


def _dedupe(fl: list[Flight]) -> list[Flight]:
    seen, out = set(), []
    for f in fl:
        k = (f.flight_number, f.origin, f.destination, f.scheduled_departure.date())
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def parse_hotels(e: RawEmail) -> list[HotelBooking]:
    out: list[HotelBooking] = []
    for r in jsonld_of_type(e.jsonld, "LodgingReservation"):
        h = r.get("reservationFor") or {}
        ci, co = to_date(r.get("checkinDate") or r.get("checkinTime")), to_date(r.get("checkoutDate") or r.get("checkoutTime"))
        if not (ci and co):
            continue
        addr = h.get("address") or {}
        city = addr.get("addressLocality", "") if isinstance(addr, dict) else ""
        out.append(HotelBooking(confirmation=str(r.get("reservationNumber", "unknown")), hotel_name=h.get("name", "Hotel"),
                                city=city, check_in=ci, check_out=co, total_price=money(r.get("totalPrice")) or 0.0,
                                provider=(r.get("provider") or {}).get("name", "") if isinstance(r.get("provider"), dict) else "",
                                source_message_id=e.message_id))
    if out or not looks_like_hotel(e):
        return out
    text = e.plain()
    ci = re.search(r"check[- ]?in[:\s]+([A-Za-z]{3,9},?\s+[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
    co = re.search(r"check[- ]?out[:\s]+([A-Za-z]{3,9},?\s+[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
    total = re.search(r"(?:total(?: price| cost| charged)?|amount)\D{0,20}\$\s?([0-9,]+\.\d{2})", text, re.I)
    if not (ci and co):
        return out
    conf = CONF.search(text)
    name_m = re.search(r"^(.{0,80}?(?:Hotel|Inn|Suites|Resort|Lodge|Marriott|Hilton|Hyatt).{0,40})$", text, re.M | re.I)
    out.append(HotelBooking(confirmation=conf.group(1) if conf else "unknown",
                            hotel_name=(name_m.group(1).strip() if name_m else e.subject[:80]),
                            check_in=to_date(ci.group(1)), check_out=to_date(co.group(1)),
                            total_price=float(total.group(1).replace(",", "")) if total else 0.0,
                            source_message_id=e.message_id))
    return out
