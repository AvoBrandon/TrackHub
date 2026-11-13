"""Rebook-after-booking decision: when is a lower price worth cancelling and rebooking?"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..models import HotelBooking, utcnow


@dataclass(frozen=True)
class RebookAdvice:
    should_rebook: bool
    savings: float
    reason: str


def advise(b: HotelBooking, new_total: float, now: Optional[datetime] = None,
           min_savings: float = 20.0, min_pct: float = 0.05) -> RebookAdvice:
    now = now or utcnow()
    savings = round(b.total_price - new_total, 2)
    if b.free_cancel_until and now > b.free_cancel_until:
        return RebookAdvice(False, savings, f"Free-cancellation window closed {b.free_cancel_until:%b %d %H:%M}.")
    if savings < min_savings or savings / b.total_price < min_pct:
        return RebookAdvice(False, savings, "Price difference too small to bother.")
    deadline = f" Cancel before {b.free_cancel_until:%b %d %H:%M}." if b.free_cancel_until else " Confirm your rate is refundable first."
    return RebookAdvice(True, savings,
                        f"Same hotel, same dates now ${new_total:,.2f} vs your ${b.total_price:,.2f}: save ${savings:,.2f}."
                        f" Book the new rate FIRST, then cancel {b.confirmation}.{deadline}")
