"""Trip brief content: packing list from forecast + paste-ready map links. No push required."""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote_plus


@dataclass
class DayForecast:
    date: str
    high_c: float
    low_c: float
    precip_prob: float     # 0-100
    wind_kph: float
    summary: str


def maps_links(origin: str, destination: str) -> dict[str, str]:
    o, d = quote_plus(origin), quote_plus(destination)
    return {
        "apple": f"https://maps.apple.com/?saddr={o}&daddr={d}&dirflg=d",
        "google": f"https://www.google.com/maps/dir/?api=1&origin={o}&destination={d}&travelmode=driving",
        "google_transit": f"https://www.google.com/maps/dir/?api=1&origin={o}&destination={d}&travelmode=transit",
    }


def packing_list(days: list[DayForecast], flying: bool = True) -> list[str]:
    items: list[str] = ["Phone charger + cable", "ID / passport", "Wallet, cards you plan to use"]
    if flying:
        items += ["Boarding pass saved offline", "Headphones", "Empty water bottle (fill after security)"]
    if not days:
        return items
    lo = min(d.low_c for d in days)
    hi = max(d.high_c for d in days)
    rain = max(d.precip_prob for d in days)
    wind = max(d.wind_kph for d in days)
    if lo < 0:
        items += ["Heavy coat", "Gloves + hat", "Thermal layer"]
    elif lo < 10:
        items += ["Warm jacket", "Light layers"]
    elif lo < 18:
        items += ["Light jacket / hoodie"]
    if hi > 28:
        items += ["Sunscreen", "Sunglasses", "Breathable clothes"]
    if rain >= 40:
        items += ["Umbrella or rain shell"]
    if wind >= 35:
        items += ["Windbreaker"]
    return items


def summarise(days: list[DayForecast]) -> str:
    if not days:
        return "Forecast unavailable."
    parts = [f"{d.date}: {d.summary}, {d.low_c:.0f}–{d.high_c:.0f}°C, rain {d.precip_prob:.0f}%" for d in days[:3]]
    return "\n".join(parts)
