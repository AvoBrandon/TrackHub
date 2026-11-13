"""Shared helpers: schema.org JSON-LD extraction (the most reliable signal; Amazon, most airlines,
Booking/Hotels/Expedia and Best Buy embed it), HTML -> text, money and date parsing."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

from bs4 import BeautifulSoup
from dateutil import parser as dtp

MONEY = re.compile(r"(?:US)?\$\s?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)")


@dataclass
class RawEmail:
    message_id: str
    sender: str
    subject: str
    received: datetime
    html: str = ""
    text: str = ""
    jsonld: list[dict[str, Any]] = field(default_factory=list)

    def plain(self) -> str:
        if self.text:
            return self.text
        return html_to_text(self.html)


def html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    txt = soup.get_text("\n")
    return re.sub(r"\n{2,}", "\n", re.sub(r"[ \t]+", " ", txt)).strip()


def extract_jsonld(html: str) -> list[dict[str, Any]]:
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out: list[dict[str, Any]] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        out.extend(data if isinstance(data, list) else [data])
    return out


def jsonld_of_type(items: Iterable[dict], *types: str) -> list[dict]:
    want = {t.lower() for t in types}
    found = []
    for it in items:
        t = it.get("@type", "")
        ts = {x.lower() for x in (t if isinstance(t, list) else [t])}
        if ts & want:
            found.append(it)
    return found


def money(s: str | float | int | None) -> float | None:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = MONEY.search(str(s))
    if m:
        return float(m.group(1).replace(",", ""))
    try:
        return float(str(s).replace(",", ""))
    except ValueError:
        return None


def to_date(v: Any, default: date | None = None) -> date | None:
    if not v:
        return default
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return dtp.parse(str(v), fuzzy=True).date()
    except (ValueError, OverflowError):
        return default


def to_datetime(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        d = dtp.parse(str(v), fuzzy=True)
        return d.replace(tzinfo=None)
    except (ValueError, OverflowError):
        return None
