"""TSA checkpoint wait times.

There is NO official public API in 2026. The legacy MyTSA web service still answers for many
airports but TSA does not promise it; a TSA real-time-wait-time program is in rulemaking. We treat
this as best-effort: if the feed fails, the morning alert says so instead of inventing a number,
and links to the airport's own wait-time page.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .base import Connector, ConnectorError

LEGACY_URL = "https://apps.tsa.dhs.gov/MyTSAWebService/GetTSOWaitTimes.ashx"

AIRPORT_PAGES = {  # airports that publish their own live wait times
    "JFK": "https://www.jfkairport.com/at-airport/security-wait-times",
    "EWR": "https://www.newarkairport.com/at-airport/security-wait-times",
    "LGA": "https://www.laguardiaairport.com/at-airport/security-wait-times",
    "ATL": "https://www.atl.com/times/",
    "DEN": "https://www.flydenver.com/security/",
    "SFO": "https://www.flysfo.com/flight-info/security-wait-times",
    "SEA": "https://www.portseattle.org/sea-tac/security-screening",
    "LAX": "https://www.flylax.com/",
    "ORD": "https://www.flychicago.com/ohare/myflight/security/pages/default.aspx",
    "MCO": "https://orlandoairports.net/security/",
}


@dataclass
class WaitTime:
    airport: str
    checkpoint: str
    minutes: int
    reported_at: datetime | None
    source: str


class TSA(Connector):
    name = "tsa"
    official = False
    note = "No official public API exists; uses the legacy MyTSA feed best-effort and falls back to the airport's own page."

    async def wait_times(self, airport: str) -> list[WaitTime]:
        r = await self._get(LEGACY_URL, params={"ap": airport.upper(), "output": "json"}, timeout=15)
        try:
            return parse_legacy(airport.upper(), r.json())
        except ValueError as e:  # not JSON (HTML error page etc.)
            raise ConnectorError(f"tsa: unparseable response for {airport}") from e

    @staticmethod
    def fallback_url(airport: str) -> str:
        return AIRPORT_PAGES.get(airport.upper(), f"https://www.google.com/search?q={airport.upper()}+security+wait+times")


_WAIT_BUCKETS = {  # MyTSA "WaitTime" index -> upper bound in minutes
    "1": 10, "2": 20, "3": 30, "4": 45, "5": 60, "6": 75, "7": 90, "8": 120,
}


def parse_legacy(airport: str, payload: dict) -> list[WaitTime]:
    rows = payload.get("WaitTimes") or payload.get("waitTimes") or []
    out: list[WaitTime] = []
    for row in rows:
        idx = str(row.get("WaitTime", "")).strip()
        minutes = _WAIT_BUCKETS.get(idx)
        if minutes is None:
            try:
                minutes = int(idx)
            except ValueError:
                continue
        ts = row.get("Created_Datetime") or row.get("CreatedDateTime")
        when = None
        if ts:
            try:
                when = datetime.strptime(ts, "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                when = None
        out.append(WaitTime(airport, str(row.get("CheckpointIndex", "")), minutes, when, "mytsa-legacy"))
    out.sort(key=lambda w: w.reported_at or datetime.min, reverse=True)
    return out
