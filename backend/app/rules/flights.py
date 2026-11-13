"""Flight delay / cancellation money rules.

Regimes implemented (Nov 2026):
  EU261   : departs EU, or arrives EU on an EU carrier. Delay >=3h at arrival (or cancellation <14 days
            notice): EUR 250 (<=1500 km), 400 (1500-3500 km, or intra-EU >1500 km), 600 (>3500 km;
            halved to 300 if arrival delay 3-4h). Not for extraordinary circumstances.
  UK261   : same shape in GBP: 220 / 350 / 520 (260 when 3-4h on the long band).
  Canada APPR (large carrier, within-carrier-control, not safety): arrival delay 3-6h CAD 400,
            6-9h CAD 700, 9h+ CAD 1000.
  US DOT  : NO cash compensation for delays. Automatic refund of the unused ticket if cancelled or
            "significantly" changed/delayed (>=3h domestic, >=6h international) and you do not accept
            the alternative. Airlines' own dashboards (meals, hotel) for controllable delays.
  Montreal Convention: damages for delay up to ~5,346 SDR on international itineraries (claim-based).

Everything here is pure: pass a Flight and get Claim objects with amount, regime and next step.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from ..models import Flight

EU = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV",
      "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "IS", "NO", "CH"}
UK = {"GB", "UK"}
CA = {"CA"}
US = {"US"}


@dataclass(frozen=True)
class Claim:
    regime: str
    amount: float
    currency: str
    confidence: str           # "likely" | "possible"
    reason: str
    next_step: str


def arrival_delay(f: Flight) -> Optional[timedelta]:
    if f.actual_arrival is None:
        return None
    return f.actual_arrival - f.scheduled_arrival


def _eu_band(distance_km: float, intra_eu: bool) -> int:
    if distance_km <= 1500:
        return 1
    if distance_km <= 3500 or intra_eu:
        return 2
    return 3


def evaluate(f: Flight) -> list[Claim]:
    claims: list[Claim] = []
    delay = arrival_delay(f)
    hours = delay.total_seconds() / 3600 if delay else 0.0
    dist = f.distance_km or 0.0
    oc, dc, ac = f.origin_country.upper(), f.destination_country.upper(), f.airline_country.upper()
    is_international = oc != dc
    disrupted = f.cancelled or hours >= 3

    # ---- EU261 ----
    eu_applies = oc in EU or (dc in EU and ac in EU)
    if eu_applies and disrupted:
        band = _eu_band(dist, oc in EU and dc in EU)
        amt = {1: 250, 2: 400, 3: 600}[band]
        if band == 3 and not f.cancelled and hours < 4:
            amt = 300
        claims.append(Claim(
            "EU261", amt, "EUR", "likely" if (f.cancelled or hours >= 3) else "possible",
            f"{'Cancelled' if f.cancelled else f'Arrived {hours:.1f}h late'} on a flight covered by EU261 ({dist:.0f} km).",
            "File with the airline's EU261 form (search '<airline> EU261 claim'). Airline must pay unless it proves extraordinary circumstances (weather, ATC, strikes outside its control).",
        ))

    # ---- UK261 ----
    uk_applies = oc in UK or (dc in UK and ac in UK)
    if uk_applies and disrupted and not eu_applies:
        band = _eu_band(dist, False)
        amt = {1: 220, 2: 350, 3: 520}[band]
        if band == 3 and not f.cancelled and hours < 4:
            amt = 260
        claims.append(Claim("UK261", amt, "GBP", "likely", f"UK261 applies; disruption {hours:.1f}h / cancelled={f.cancelled}.",
                            "Claim via the airline; escalate to CEDR/AviationADR if refused."))

    # ---- Canada APPR ----
    if (oc in CA or dc in CA) and hours >= 3 and not f.cancelled:
        amt = 400 if hours < 6 else 700 if hours < 9 else 1000
        claims.append(Claim("Canada APPR", amt, "CAD", "possible",
                            f"Arrived {hours:.1f}h late on a flight to/from Canada.",
                            "Owed only if the delay was within the carrier's control and not safety-related. Submit the airline's APPR claim form within 1 year; escalate to the CTA."))

    # ---- US DOT automatic refund ----
    if (oc in US or dc in US) and (f.cancelled or hours >= (6 if is_international else 3)):
        amt = f.fare_paid or 0.0
        claims.append(Claim(
            "US DOT refund", amt, "USD", "likely" if f.cancelled else "possible",
            "US rule: cancelled or significantly delayed (3h domestic / 6h international) flights earn an automatic cash refund if you decline rebooking.",
            "If you did NOT fly the replacement, demand a cash refund (not a voucher) within 7 business days. Also check the airline's DOT dashboard commitments for meals/hotel on controllable delays.",
        ))

    # ---- Montreal Convention (claim-based damages) ----
    if is_international and hours >= 3 and not claims:
        claims.append(Claim("Montreal Convention", 0.0, "SDR", "possible",
                            "International delay; actual provable expenses (hotel, meals, missed connections) are recoverable.",
                            "Keep receipts; write to the airline within 21 days of arrival citing Article 19."))
    return claims


def total_at_stake(claims: list[Claim]) -> float:
    return round(sum(c.amount for c in claims), 2)
