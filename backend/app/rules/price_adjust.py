"""Price-adjustment and credit-card price-protection rules.

Retailer policies (Nov 2026):
  Best Buy : Price Match Guarantee covers its OWN price drops for the length of your return window
             (15 days standard / 60 days member). Request in store or chat; refund to original card.
  Amazon   : no price adjustments (ended 2016). The only play is return-and-rebuy inside the window.
  eBay     : none.

Card price protection has been dropped by almost every US issuer. The table below is what still
exists as of Nov 2026 per public benefit guides; the app surfaces it as "worth checking your
benefits guide", never as a guarantee. Edit CARD_PROTECTION to match your actual cards.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from ..models import Purchase, Retailer
from .returns import return_window


@dataclass(frozen=True)
class CardPolicy:
    name: str
    window_days: int
    per_item_cap: float
    per_year_cap: float
    note: str


CARD_PROTECTION: dict[str, CardPolicy] = {
    # key = lowercase substring matched against Purchase.card_product
    "world elite mastercard": CardPolicy("Mastercard World Elite (issuer-dependent)", 60, 250, 1000, "Mastercard-level benefit; verify in your Guide to Benefits."),
    "capital one": CardPolicy("Capital One (select World Elite / business)", 60, 250, 1000, "Only some Capital One cards still carry it."),
    "ubs visa infinite": CardPolicy("UBS Visa Infinite", 90, 1000, 2500, "Among the richest surviving policies."),
    "hsbc premier world elite": CardPolicy("HSBC Premier World Elite Mastercard", 60, 500, 2500, ""),
    "bilt palladium": CardPolicy("Bilt Palladium", 90, 500, 1500, "Reported by benefit guides; verify."),
    "wells fargo visa signature": CardPolicy("Wells Fargo Visa Signature (select)", 60, 500, 1500, "Reported by benefit guides; verify."),
}


def card_policy_for(card_product: str) -> Optional[CardPolicy]:
    cp = (card_product or "").lower()
    for key, pol in CARD_PROTECTION.items():
        if key in cp:
            return pol
    return None


@dataclass(frozen=True)
class AdjustmentOpportunity:
    route: str              # "bestbuy_price_match" | "amazon_return_rebuy" | "card_price_protection"
    refund: float
    deadline: Optional[date]
    how: str


def opportunities(p: Purchase, current_price: float, today: Optional[date] = None) -> list[AdjustmentOpportunity]:
    """Given a purchase and the price seen today for the same new item, list every way to get money back."""
    today = today or date.today()
    out: list[AdjustmentOpportunity] = []
    diff = round(p.price - current_price, 2)
    if diff < 1.0 or p.returned:
        return out

    rw = return_window(p, today)
    if p.retailer == Retailer.bestbuy and rw.deadline and rw.deadline >= today and not p.is_marketplace_seller:
        out.append(AdjustmentOpportunity(
            "bestbuy_price_match", diff, rw.deadline,
            f"Best Buy price-matches its own drops inside your return window. Chat or visit a store with order {p.order_id}; refund goes to your card.",
        ))
    if p.retailer == Retailer.amazon and rw.deadline and rw.deadline >= today:
        out.append(AdjustmentOpportunity(
            "amazon_return_rebuy", diff, rw.deadline,
            "Amazon does not adjust prices. Reorder at the new price, then return the original under order "
            f"{p.order_id} before {rw.deadline:%b %d}.",
        ))
    pol = card_policy_for(p.card_product)
    if pol:
        deadline = p.purchased_on + timedelta(days=pol.window_days)
        if deadline >= today:
            out.append(AdjustmentOpportunity(
                "card_price_protection", min(diff, pol.per_item_cap), deadline,
                f"{pol.name}: file a price-protection claim with the original receipt and the lower advertised price "
                f"(cap ${pol.per_item_cap:.0f}/item). {pol.note}".strip(),
            ))
    return out
