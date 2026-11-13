"""FlightAware AeroAPI v4 (flightaware.com/aeroapi). Needs AEROAPI_KEY. Personal tier includes a
monthly free allowance; we poll each tracked flight every 15 min only on its travel day.

GET https://aeroapi.flightaware.com/aeroapi/flights/{ident}?start=..&end=..
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from dateutil import parser as dtp

from ..config import get_settings
from .base import Connector, ConnectorError

BASE = "https://aeroapi.flightaware.com/aeroapi"

# AeroAPI strongly prefers ICAO idents (DAL1234) over IATA (DL1234) to avoid ambiguity.
IATA_TO_ICAO = {"DL": "DAL", "UA": "UAL", "AA": "AAL", "WN": "SWA", "B6": "JBU", "AS": "ASA", "NK": "NKS",
                "F9": "FFT", "G4": "AAY", "HA": "HAL", "SY": "SCX", "BA": "BAW", "VS": "VIR", "AF": "AFR",
                "KL": "KLM", "LH": "DLH", "IB": "IBE", "AZ": "ITY", "EI": "EIN", "TP": "TAP", "LX": "SWR",
                "OS": "AUA", "SK": "SAS", "AY": "FIN", "SN": "BEL", "AC": "ACA", "WS": "WJA", "AM": "AMX",
                "JL": "JAL", "NH": "ANA", "KE": "KAL", "SQ": "SIA", "EK": "UAE", "QR": "QTR", "QF": "QFA",
                "TK": "THY", "CM": "CMP", "AV": "AVA", "LA": "LAN", "Y4": "VOI", "VB": "VIV"}


def to_icao_ident(flight_number: str) -> str:
    fn = flight_number.strip().upper().replace(" ", "")
    if len(fn) > 2 and fn[:2] in IATA_TO_ICAO and fn[2:].isdigit():
        return IATA_TO_ICAO[fn[:2]] + fn[2:]
    return fn


@dataclass
class FlightStatus:
    ident: str
    status: str
    cancelled: bool
    scheduled_out: datetime | None
    actual_out: datetime | None
    scheduled_in: datetime | None
    actual_in: datetime | None
    estimated_in: datetime | None
    distance_km: float | None
    origin: str
    destination: str

    @property
    def arrival_delay(self) -> timedelta | None:
        arr = self.actual_in or self.estimated_in
        if arr and self.scheduled_in:
            return arr - self.scheduled_in
        return None


class AeroAPI(Connector):
    name = "aeroapi"
    note = "Official FlightAware API; personal tier has a small monthly allowance."

    def __init__(self, key: str | None = None):
        self.key = key if key is not None else get_settings().aeroapi_key

    def configured(self) -> bool:
        return bool(self.key)

    async def flight_status(self_, ident: str, day: datetime) -> FlightStatus:  # noqa: N805
        if not self_.configured():
            raise ConnectorError("AeroAPI key not configured")
        start, end = day.strftime("%Y-%m-%d"), (day + timedelta(days=1)).strftime("%Y-%m-%d")
        r = await self_._get(f"{BASE}/flights/{to_icao_ident(ident)}",
                             params={"start": start, "end": end, "ident_type": "designator"},
                             headers={"x-apikey": self_.key})
        return parse_status(r.json())


def _dt(v):
    return dtp.isoparse(v) if v else None


def parse_status(payload: dict) -> FlightStatus:
    flights = payload.get("flights") or []
    if not flights:
        raise ConnectorError("aeroapi: flight not found")
    f = flights[0]
    miles = f.get("route_distance")
    return FlightStatus(
        f.get("ident", ""), f.get("status", ""), bool(f.get("cancelled")),
        _dt(f.get("scheduled_out")), _dt(f.get("actual_out")), _dt(f.get("scheduled_in")), _dt(f.get("actual_in")),
        _dt(f.get("estimated_in")), round(miles * 1.60934, 1) if miles else None,
        (f.get("origin") or {}).get("code_iata", ""), (f.get("destination") or {}).get("code_iata", ""),
    )
