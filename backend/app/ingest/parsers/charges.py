"""Receipts / 'your payment was received' emails -> Transaction rows for subscription detection."""
from __future__ import annotations

import re

from ...models import Transaction
from .common import RawEmail, money

RECEIPT_WORDS = ("receipt", "payment", "invoice", "renewal", "subscription", "your bill", "has been charged", "membership")
AMOUNT = re.compile(r"(?:total|amount(?: charged| paid| due)?|charged|paid)\D{0,25}\$\s?([0-9,]+\.\d{2})", re.I)


def parse_charge(e: RawEmail) -> Transaction | None:
    s = e.subject.lower()
    if not any(w in s for w in RECEIPT_WORDS):
        return None
    text = e.plain()
    m = AMOUNT.search(text) or AMOUNT.search(e.subject)
    amt = float(m.group(1).replace(",", "")) if m else money(e.subject)
    if not amt:
        return None
    merchant = e.sender.split("<")[0].strip().strip('"') or e.sender
    merchant = re.sub(r"(?i)\b(no-?reply|billing|receipts?|team|support)\b", "", merchant).strip(" -|") or e.sender
    return Transaction(merchant=merchant, amount=amt, posted_on=e.received.date(), source="email", source_ref=e.message_id)
