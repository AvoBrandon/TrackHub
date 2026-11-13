"""Return-window rules.

Dates verified Nov 2026 against public reporting (see docs/SOURCES.md). Each rule returns a
ReturnWindow with the deadline AND the rule text, so the app can show *why* you have until that day.

Standing policies:
  Amazon     : 30 days from delivery (receipt). Holiday: bought Nov 1 - Dec 31 -> return through Jan 31
               next year; Apple-brand items through Jan 15.
  Best Buy   : 15 days (standard), 60 days (My Best Buy Plus / Total) from purchase/delivery.
               Activatable devices (phones, cellular tablets/watches): 14 days.
               Holiday: bought Oct 27 - Dec 31 -> return through Jan 14 next year (not phones/appliances).
  eBay       : seller-defined. Default assumption 30 days from delivery; 0 when seller says no returns.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from ..models import Purchase, Retailer

# Best Buy's standard return period is counted from the date you receive the item. We prefer the
# delivery date; fall back to purchase date when we never saw a delivery email.


@dataclass(frozen=True)
class ReturnWindow:
    deadline: Optional[date]           # None == not returnable / unknown
    rule: str                          # human sentence
    days_left: Optional[int]
    is_holiday_extension: bool = False

    @property
    def urgency(self) -> str:
        if self.days_left is None:
            return "none"
        if self.days_left < 0:
            return "closed"
        if self.days_left <= 2:
            return "critical"
        if self.days_left <= 7:
            return "soon"
        return "ok"


def _anchor(p: Purchase) -> date:
    return p.delivered_on or p.purchased_on


def amazon_window(p: Purchase, today: date) -> ReturnWindow:
    anchor = _anchor(p)
    standard = anchor + timedelta(days=30)
    deadline = standard
    rule = "Amazon: 30 days from delivery."
    holiday = False
    y = p.purchased_on.year
    if date(y, 11, 1) <= p.purchased_on <= date(y, 12, 31):
        if p.category.lower() == "apple":
            ext = date(y + 1, 1, 15)
            txt = "Amazon holiday policy: Apple-brand items bought Nov 1-Dec 31 returnable through Jan 15."
        else:
            ext = date(y + 1, 1, 31)
            txt = "Amazon holiday policy: items bought Nov 1-Dec 31 returnable through Jan 31."
        if ext > deadline:
            deadline, rule, holiday = ext, txt, True
    return ReturnWindow(deadline, rule, (deadline - today).days, holiday)


def bestbuy_window(p: Purchase, today: date) -> ReturnWindow:
    anchor = _anchor(p)
    cat = p.category.lower()
    activatable = cat in {"phone", "cellular", "activatable", "smartwatch-cellular"}
    if activatable:
        days, rule = 14, "Best Buy: activatable devices (phones, cellular devices) 14 days."
    elif p.bestbuy_membership in {"plus", "total"}:
        days, rule = 60, f"Best Buy: My Best Buy {p.bestbuy_membership.title()} members get 60 days."
    else:
        days, rule = 15, "Best Buy: standard 15-day return window."
    deadline = anchor + timedelta(days=days)
    holiday = False
    y = p.purchased_on.year
    excluded = activatable or cat in {"appliance", "major-appliance"}
    if not excluded and date(y, 10, 27) <= p.purchased_on <= date(y, 12, 31):
        ext = date(y + 1, 1, 14)
        if ext > deadline:
            deadline, holiday = ext, True
            rule = "Best Buy holiday policy: purchases Oct 27-Dec 31 returnable through Jan 14 (excludes phones, major appliances)."
    return ReturnWindow(deadline, rule, (deadline - today).days, holiday)


def ebay_window(p: Purchase, today: date, seller_return_days: Optional[int] = 30) -> ReturnWindow:
    if not seller_return_days:
        return ReturnWindow(None, "eBay: seller does not accept returns (Money Back Guarantee still covers not-as-described).", None)
    anchor = _anchor(p)
    deadline = anchor + timedelta(days=seller_return_days)
    return ReturnWindow(deadline, f"eBay: seller allows {seller_return_days}-day returns from delivery.", (deadline - today).days)


def return_window(p: Purchase, today: Optional[date] = None, **kw) -> ReturnWindow:
    today = today or date.today()
    if p.retailer == Retailer.amazon:
        return amazon_window(p, today)
    if p.retailer == Retailer.bestbuy:
        return bestbuy_window(p, today)
    if p.retailer == Retailer.ebay:
        return ebay_window(p, today, **kw)
    deadline = _anchor(p) + timedelta(days=30)
    return ReturnWindow(deadline, "Assumed 30-day policy; check the retailer.", (deadline - today).days)


# Alert thresholds: we warn at 7, 3, and 1 day(s) left, and the morning of.
ALERT_DAYS = (7, 3, 1, 0)
