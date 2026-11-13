"""Hotel re-check. Hotel pricing has no free public API; we define one small interface and ship two
implementations:

  * GenericHotelAPI  - points at any JSON endpoint you have access to (wholesale/affiliate feed) via
                       HOTEL_API_BASE / HOTEL_API_KEY. Expects GET {base}/offers?hotel_id=&check_in=&check_out=
                       returning {"offers":[{"total": 412.50, "currency":"USD", "refundable": true, "url": ".."}]}.
  * ManualHotelAPI   - no key: the nightly job instead creates a one-tap "re-check" alert with deep links
                       to the same dates on Google Hotels / Booking so a 10-second manual check still happens.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from urllib.parse import quote_plus

from ..config import get_settings
from .base import Connector, ConnectorError


@dataclass
class HotelOffer:
    total: float
    currency: str
    refundable: bool
    url: str
    room_type: str = ""


class GenericHotelAPI(Connector):
    name = "hotel-api"
    note = "Any JSON offers endpoint you have access to (wholesale/affiliate)."

    def __init__(self):
        s = get_settings()
        self.base, self.key = s.hotel_api_base.rstrip("/"), s.hotel_api_key

    def configured(self) -> bool:
        return bool(self.base)

    async def offers(self, hotel_id: str, check_in: date, check_out: date) -> list[HotelOffer]:
        if not self.configured():
            raise ConnectorError("hotel API not configured")
        r = await self._get(f"{self.base}/offers", params={"hotel_id": hotel_id, "check_in": check_in.isoformat(),
                                                           "check_out": check_out.isoformat()},
                            headers={"Authorization": f"Bearer {self.key}"} if self.key else {})
        return [HotelOffer(float(o["total"]), o.get("currency", "USD"), bool(o.get("refundable", False)),
                           o.get("url", ""), o.get("room_type", "")) for o in r.json().get("offers", [])]


def manual_check_links(hotel_name: str, city: str, check_in: date, check_out: date) -> dict[str, str]:
    q = quote_plus(f"{hotel_name} {city}")
    return {
        "google_hotels": f"https://www.google.com/travel/hotels?q={q}&checkin={check_in:%Y-%m-%d}&checkout={check_out:%Y-%m-%d}",
        "booking": f"https://www.booking.com/searchresults.html?ss={q}&checkin={check_in:%Y-%m-%d}&checkout={check_out:%Y-%m-%d}",
        "hotels_com": f"https://www.hotels.com/Hotel-Search?destination={q}&startDate={check_in:%Y-%m-%d}&endDate={check_out:%Y-%m-%d}",
    }
