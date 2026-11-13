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
        r = await self_._get(f"{BASE}/flights/{ident}", params={"start": start, "end": end},
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
