"""Open-Meteo: free, no key, no sign-up. Geocoding + 7-day daily forecast."""
from __future__ import annotations

from ..rules.tripbrief import DayForecast
from .base import Connector, ConnectorError

GEO = "https://geocoding-api.open-meteo.com/v1/search"
FC = "https://api.open-meteo.com/v1/forecast"

WMO = {0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog",
       51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
       66: "Freezing rain", 67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
       80: "Showers", 81: "Showers", 82: "Heavy showers", 85: "Snow showers", 86: "Snow showers",
       95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Thunderstorm w/ hail"}


class Weather(Connector):
    name = "open-meteo"
    note = "Free, keyless."

    async def geocode(self, place: str) -> tuple[float, float, str]:
        r = await self._get(GEO, params={"name": place, "count": 1, "language": "en", "format": "json"})
        res = (r.json().get("results") or [])
        if not res:
            raise ConnectorError(f"weather: could not geocode '{place}'")
        g = res[0]
        return float(g["latitude"]), float(g["longitude"]), f"{g.get('name')}, {g.get('admin1', '')} {g.get('country_code', '')}".strip()

    async def forecast(self, lat: float, lon: float, days: int = 5) -> list[DayForecast]:
        r = await self._get(FC, params={
            "latitude": lat, "longitude": lon, "forecast_days": days, "timezone": "auto",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
        })
        return parse_forecast(r.json())


def parse_forecast(payload: dict) -> list[DayForecast]:
    d = payload.get("daily") or {}
    out: list[DayForecast] = []
    for i, day in enumerate(d.get("time", [])):
        code = int((d.get("weather_code") or [0])[i] or 0)
        out.append(DayForecast(
            day, float(d["temperature_2m_max"][i]), float(d["temperature_2m_min"][i]),
            float((d.get("precipitation_probability_max") or [0])[i] or 0),
            float((d.get("wind_speed_10m_max") or [0])[i] or 0), WMO.get(code, "Mixed"),
        ))
    return out
