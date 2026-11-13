"""Amazon / Best Buy / eBay order emails -> Purchase rows."""
from __future__ import annotations

import re

from ...models import Purchase, Retailer
from .common import RawEmail, jsonld_of_type, money, to_date

AMZ_ORDER = re.compile(r"\b(\d{3}-\d{7}-\d{7})\b")
BBY_ORDER = re.compile(r"\b(BBY01-\d{12})\b")
EBAY_ORDER = re.compile(r"\b(\d{2}-\d{5}-\d{5})\b")
PRICE_LINE = re.compile(r"^(?P<name>.{6,140}?)[ \t]+\$\s?(?P<price>[0-9,]+\.\d{2})[ \t]*$", re.M)
QTY_PRICE_LINE = re.compile(r"^(?P<name>.{6,140}?)\n(?:Qty|Quantity)[:\s]+\d+\n\$\s?(?P<price>[0-9,]+\.\d{2})", re.M)
APPLE_WORDS = re.compile(r"\b(iphone|ipad|macbook|apple watch|airpods|imac|mac mini|apple tv)\b", re.I)
PHONE_WORDS = re.compile(r"\b(iphone|galaxy s\d|pixel \d|unlocked phone|smartphone)\b", re.I)
APPLIANCE_WORDS = re.compile(r"\b(refrigerator|washer|dryer|dishwasher|range|oven|freezer)\b", re.I)


def classify_retailer(e: RawEmail) -> Retailer | None:
    s = f"{e.sender} {e.subject}".lower()
    if "amazon" in s:
        return Retailer.amazon
    if "bestbuy" in s or "best buy" in s:
        return Retailer.bestbuy
    if "ebay" in s:
        return Retailer.ebay
    return None


def is_order_email(e: RawEmail) -> bool:
    s = e.subject.lower()
    return any(k in s for k in ("order", "shipped", "delivered", "your purchase", "thanks for your", "receipt", "confirmation"))


def category_for(name: str) -> str:
    if PHONE_WORDS.search(name):
        return "phone"
    if APPLE_WORDS.search(name):
        return "apple"
    if APPLIANCE_WORDS.search(name):
        return "appliance"
    return ""


def _from_jsonld(e: RawEmail, retailer: Retailer) -> list[Purchase]:
    out: list[Purchase] = []
    for order in jsonld_of_type(e.jsonld, "Order"):
        oid = str(order.get("orderNumber", ""))
        items = order.get("acceptedOffer") or []
        if isinstance(items, dict):
            items = [items]
        for off in items:
            item = off.get("itemOffered") or {}
            name = item.get("name") or off.get("name") or ""
            price = money(off.get("price"))
            if not name or price is None:
                continue
            out.append(Purchase(retailer=retailer, order_id=oid or "unknown", item_name=name[:200],
                                sku=str(item.get("sku") or item.get("productID") or ""), price=price,
                                purchased_on=to_date(order.get("orderDate"), e.received.date()),
                                category=category_for(name), source_message_id=e.message_id))
    return out


def _from_text(e: RawEmail, retailer: Retailer) -> list[Purchase]:
    text = e.plain()
    pat = {Retailer.amazon: AMZ_ORDER, Retailer.bestbuy: BBY_ORDER, Retailer.ebay: EBAY_ORDER}[retailer]
    m = pat.search(text) or pat.search(e.subject)
    oid = m.group(1) if m else "unknown"
    out: list[Purchase] = []
    seen = set()
    for rx in (QTY_PRICE_LINE, PRICE_LINE):
        for mm in rx.finditer(text):
            name = " ".join(mm.group("name").split())
            low = name.lower()
            if any(k in low for k in ("total", "subtotal", "shipping", "tax", "gift card", "promotion", "estimated", "discount", "savings", "balance")):
                continue
            if name in seen:
                continue
            seen.add(name)
            price = float(mm.group("price").replace(",", ""))
            out.append(Purchase(retailer=retailer, order_id=oid, item_name=name[:200], price=price,
                                purchased_on=e.received.date(), category=category_for(name),
                                source_message_id=e.message_id))
    return out


def parse_order(e: RawEmail) -> list[Purchase]:
    retailer = classify_retailer(e)
    if not retailer or not is_order_email(e):
        return []
    rows = _from_jsonld(e, retailer) or _from_text(e, retailer)
    low = e.plain().lower()
    for r in rows:
        if retailer == Retailer.bestbuy:
            if "open-box" in r.item_name.lower() or "open box" in r.item_name.lower():
                r.is_open_box = True
            if "my best buy total" in low:
                r.bestbuy_membership = "total"
            elif "my best buy plus" in low:
                r.bestbuy_membership = "plus"
        if retailer == Retailer.amazon and ("sold by" in low and "amazon.com" not in low.split("sold by", 1)[1][:60]):
            r.is_marketplace_seller = True
    return rows


def delivery_date_update(e: RawEmail) -> tuple[str, "date"] | None:
    """'Delivered: your package...' emails -> (order_id, delivered_on) so return clocks start right."""
    s = e.subject.lower()
    if "delivered" not in s:
        return None
    text = e.plain()
    for rx in (AMZ_ORDER, BBY_ORDER, EBAY_ORDER):
        m = rx.search(text) or rx.search(e.subject)
        if m:
            return m.group(1), e.received.date()
    return None
