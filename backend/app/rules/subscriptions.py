"""Recurring-charge detection over Transaction rows (bank CSV, Plaid, or receipt emails).

Heuristic: group by normalised merchant; a merchant with >=2 charges whose gaps cluster around
7/30/365 days and whose amounts are within 15% is a subscription. Confidence rises with count and
regularity. Pure function; the monthly job turns the result into one 'Subscription creep' alert.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Iterable

from ..models import Transaction

_NOISE = re.compile(r"(\*|#|\d{3,}|pos|debit|purchase|recurring|payment|www\.|\.com|inc\.?|llc)", re.I)


def normalise_merchant(name: str) -> str:
    n = _NOISE.sub(" ", name.lower())
    n = re.sub(r"[^a-z ]", " ", n)
    return " ".join(n.split())[:40]


CADENCES = {"weekly": 7, "monthly": 30, "yearly": 365}


@dataclass(frozen=True)
class Recurring:
    merchant: str
    amount: float
    cadence: str
    last_charged: date
    next_expected: date
    confidence: float
    count: int

    @property
    def yearly_cost(self) -> float:
        return round(self.amount * {"weekly": 52, "monthly": 12, "yearly": 1}[self.cadence], 2)


def detect(transactions: Iterable[Transaction], today: date | None = None) -> list[Recurring]:
    today = today or date.today()
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in transactions:
        if t.amount <= 0:
            continue
        groups[normalise_merchant(t.merchant)].append(t)

    found: list[Recurring] = []
    for merchant, txs in groups.items():
        if len(txs) < 2:
            continue
        txs.sort(key=lambda t: t.posted_on)
        amounts = [t.amount for t in txs]
        med_amt = median(amounts)
        if any(abs(a - med_amt) / med_amt > 0.15 for a in amounts):
            continue
        gaps = [(b.posted_on - a.posted_on).days for a, b in zip(txs, txs[1:])]
        med_gap = median(gaps)
        cadence = min(CADENCES, key=lambda c: abs(CADENCES[c] - med_gap))
        tol = {"weekly": 2, "monthly": 5, "yearly": 20}[cadence]
        if abs(CADENCES[cadence] - med_gap) > tol:
            continue
        regular = sum(1 for g in gaps if abs(g - CADENCES[cadence]) <= tol) / len(gaps)
        confidence = min(0.99, 0.5 + 0.1 * len(txs) + 0.3 * regular)
        last = txs[-1].posted_on
        nxt = last + timedelta(days=CADENCES[cadence])
        # dead subscriptions (no charge for 2 cycles) are dropped
        if (today - last).days > CADENCES[cadence] * 2 + tol:
            continue
        found.append(Recurring(merchant, round(med_amt, 2), cadence, last, nxt, round(confidence, 2), len(txs)))
    found.sort(key=lambda r: -r.yearly_cost)
    return found


def monthly_report(recs: list[Recurring]) -> str:
    if not recs:
        return "No recurring charges detected."
    total_m = sum(r.yearly_cost for r in recs) / 12
    lines = [f"{len(recs)} recurring charges ~ ${total_m:,.2f}/month (${total_m*12:,.0f}/yr)", ""]
    for r in recs:
        lines.append(f"• {r.merchant.title()} — ${r.amount:.2f} {r.cadence}, next ~{r.next_expected:%b %d}")
    return "\n".join(lines)
