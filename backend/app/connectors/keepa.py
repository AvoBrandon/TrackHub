"""Amazon prices via Keepa (keepa.com/#!api). Amazon has no public price API; Keepa is the reliable
paid route (~EUR 19/mo for the smallest plan). Needs KEEPA_API_KEY.

GET https://api.keepa.com/product?key=..&domain=1&asin=..&stats=1
Prices in the csv arrays are integer cents; -1 means no offer.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import get_settings
from .base import Connector, ConnectorError

URL = "https://api.keepa.com/product"


@dataclass
class AmazonPrice:
    asin: str
    title: str
    amazon_price: float | None     # sold by Amazon
    new_3p_price: float | None     # lowest 3rd-party new
    used_price: float | None
    warehouse_price: float | None  # Amazon Warehouse (their open-box equivalent)
    url: str

    @property
    def best_new(self) -> float | None:
        c = [p for p in (self.amazon_price, self.new_3p_price) if p]
        return min(c) if c else None


class Keepa(Connector):
    name = "keepa"
    note = "Paid third-party Amazon price API. Without it, Amazon price checks are manual."

    def __init__(self, key: str | None = None):
        self.key = key if key is not None else get_settings().keepa_api_key

    def configured(self) -> bool:
        return bool(self.key)

    async def product(self, asin: str) -> AmazonPrice:
        if not self.configured():
            raise ConnectorError("Keepa API key not configured")
        r = await self._get(URL, params={"key": self.key, "domain": 1, "asin": asin, "stats": 1})
        return parse_product(r.json())


def _cents(v) -> float | None:
    return None if v is None or v < 0 else round(v / 100, 2)


def parse_product(payload: dict) -> AmazonPrice:
    prods = payload.get("products") or []
    if not prods:
        raise ConnectorError("keepa: no product in response")
    p = prods[0]
    cur = (p.get("stats") or {}).get("current") or []
    get = lambda i: _cents(cur[i]) if len(cur) > i else None  # noqa: E731
    # Keepa csv indexes: 0 AMAZON, 1 NEW, 2 USED, 9 WAREHOUSE
    return AmazonPrice(p.get("asin", ""), p.get("title", ""), get(0), get(1), get(2), get(9),
                       f"https://www.amazon.com/dp/{p.get('asin', '')}")
