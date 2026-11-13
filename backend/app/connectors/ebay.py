"""eBay Browse API (developer.ebay.com). Needs EBAY_CLIENT_ID / EBAY_CLIENT_SECRET.

Flow: client-credentials OAuth -> https://api.ebay.com/identity/v1/oauth2/token
      search              -> https://api.ebay.com/buy/browse/v1/item_summary/search?q=..&filter=..
Free tier is rate-limited (~5k calls/day); we poll each watch a few times a day at most.
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass

import httpx

from ..config import get_settings
from .base import Connector, ConnectorError

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"


@dataclass
class Listing:
    item_id: str
    title: str
    price: float
    currency: str
    condition: str
    url: str
    shipping: float
    buy_it_now: bool

    @property
    def landed(self) -> float:
        return round(self.price + self.shipping, 2)


class Ebay(Connector):
    name = "ebay"
    note = "Official Browse API. Free developer account; production access to Buy APIs needs a one-time approval."

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        s = get_settings()
        self.client_id = client_id if client_id is not None else s.ebay_client_id
        self.client_secret = client_secret if client_secret is not None else s.ebay_client_secret
        self.marketplace = s.ebay_marketplace
        self._token = ""
        self._exp = 0.0

    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def _access_token(self) -> str:
        if self._token and time.time() < self._exp - 60:
            return self._token
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(TOKEN_URL, headers={"Authorization": f"Basic {basic}",
                                                  "Content-Type": "application/x-www-form-urlencoded"},
                             data={"grant_type": "client_credentials", "scope": SCOPE})
        if r.status_code != 200:
            raise ConnectorError(f"ebay token: HTTP {r.status_code} {r.text[:200]}")
        d = r.json()
        self._token, self._exp = d["access_token"], time.time() + int(d.get("expires_in", 7200))
        return self._token

    async def search(self, query: str, *, max_price: float | None = None, new_only: bool = False,
                     buy_it_now: bool = True, limit: int = 20) -> list[Listing]:
        if not self.configured():
            raise ConnectorError("eBay credentials not configured")
        tok = await self._access_token()
        filters = []
        if buy_it_now:
            filters.append("buyingOptions:{FIXED_PRICE}")
        if new_only:
            filters.append("conditions:{NEW}")
        if max_price:
            filters.append(f"price:[..{max_price:.2f}],priceCurrency:USD")
        params = {"q": query, "limit": str(limit), "sort": "price"}
        if filters:
            params["filter"] = ",".join(filters)
        r = await self._get(SEARCH_URL, params=params,
                            headers={"Authorization": f"Bearer {tok}", "X-EBAY-C-MARKETPLACE-ID": self.marketplace})
        return parse_search(r.json())


def parse_search(payload: dict) -> list[Listing]:
    out: list[Listing] = []
    for it in payload.get("itemSummaries", []):
        price = it.get("price") or {}
        ship = 0.0
        for opt in it.get("shippingOptions", []) or []:
            cost = (opt.get("shippingCost") or {}).get("value")
            if cost is not None:
                ship = float(cost)
                break
        out.append(Listing(
            it.get("itemId", ""), it.get("title", ""), float(price.get("value", 0) or 0),
            price.get("currency", "USD"), it.get("condition", ""), it.get("itemWebUrl", ""), ship,
            "FIXED_PRICE" in (it.get("buyingOptions") or []),
        ))
    return sorted(out, key=lambda l: l.landed)
