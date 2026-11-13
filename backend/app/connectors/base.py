"""Every external service implements `Connector`. `status()` is what the app's Health screen shows,
so a missing key is a visible yellow badge, not a silent failure."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)


@dataclass
class ConnectorStatus:
    name: str
    configured: bool
    official: bool                 # official/documented API vs best-effort unofficial feed
    note: str = ""
    last_ok: str = ""


class ConnectorError(RuntimeError):
    pass


class Connector:
    name = "base"
    official = True
    note = ""

    def configured(self) -> bool:  # pragma: no cover - trivial
        return True

    def status(self) -> ConnectorStatus:
        return ConnectorStatus(self.name, self.configured(), self.official, self.note)

    async def _get(self, url: str, **kw: Any) -> httpx.Response:
        timeout = kw.pop("timeout", 20.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
                r = await c.get(url, **kw)
        except httpx.HTTPError as e:  # network, proxy, timeout -> one exception type for callers
            raise ConnectorError(f"{self.name}: {type(e).__name__}: {e}") from e
        if r.status_code >= 400:
            raise ConnectorError(f"{self.name}: HTTP {r.status_code} for {url[:120]}")
        return r
