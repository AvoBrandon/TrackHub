"""Best Buy Products API (developer.bestbuy.com). Needs BESTBUY_API_KEY.

Endpoints used:
  GET https://api.bestbuy.com/v1/products/{sku}.json?apiKey=..&show=sku,name,salePrice,regularPrice,url,onlineAvailability
  GET https://api.bestbuy.com/v1/products/{sku}/openBox?apiKey=..   (Buying Options API: open-box offers)
  GET https://api.bestbuy.com/beta/products/openBox(sku in(..))?apiKey=..  (batch)
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import get_settings
from .base import Connector, ConnectorError

BASE = "https://api.bestbuy.com"


@dataclass
class Offer:
    sku: str
    name: str
    price: float
    condition: str          # new | open-box-excellent-certified | open-box-excellent | open-box-satisfactory | open-box-fair
    url: str
    in_stock: bool


class BestBuy(Connector):
    name = "bestbuy"
    note = "Official Products/Buying Options API. Free key from developer.bestbuy.com."

    def __init__(self, key: str | None = None):
        self.key = key if key is not None else get_settings().bestbuy_api_key

    def configured(self) -> bool:
        return bool(self.key)

    async def product(self, sku: str) -> Offer:
        if not self.configured():
            raise ConnectorError("Best Buy API key not configured")
        r = await self._get(f"{BASE}/v1/products/{sku}.json",
                            params={"apiKey": self.key, "show": "sku,name,salePrice,regularPrice,url,onlineAvailability"})
        d = r.json()
        return Offer(str(d["sku"]), d.get("name", ""), float(d.get("salePrice") or d.get("regularPrice") or 0),
                     "new", d.get("url", ""), bool(d.get("onlineAvailability", False)))

    async def open_box(self, sku: str) -> list[Offer]:
        if not self.configured():
            raise ConnectorError("Best Buy API key not configured")
        r = await self._get(f"{BASE}/beta/products/{sku}/openBox", params={"apiKey": self.key})
        return parse_open_box(r.json())

    async def search(self, query: str, limit: int = 10) -> list[Offer]:
        if not self.configured():
            raise ConnectorError("Best Buy API key not configured")
        q = "&".join(f"search={w}" for w in query.split())
        r = await self._get(f"{BASE}/v1/products(({q}))",
                            params={"apiKey": self.key, "format": "json", "pageSize": limit,
                                    "show": "sku,name,salePrice,regularPrice,url,onlineAvailability"})
        return [Offer(str(p["sku"]), p.get("name", ""), float(p.get("salePrice") or 0), "new", p.get("url", ""),
                      bool(p.get("onlineAvailability"))) for p in r.json().get("products", [])]


def parse_open_box(payload: dict) -> list[Offer]:
    """Buying Options payload -> offers. Tolerates both the single-sku and batch shapes."""
    results = payload.get("results") or ([payload] if "offers" in payload else [])
    out: list[Offer] = []
    for res in results:
        sku = str(res.get("sku", ""))
        name = (res.get("names") or {}).get("title", "") or res.get("name", "")
        links = res.get("links") or {}
        for off in res.get("offers", []):
            cond = off.get("condition", "open-box").lower()
            prices = off.get("prices") or {}
            price = prices.get("current") or off.get("price")
            if price is None:
                continue
            out.append(Offer(sku, name, float(price), f"open-box-{cond}", links.get("web", ""), True))
    return out
