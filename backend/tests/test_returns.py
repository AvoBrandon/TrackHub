from datetime import date

from app.models import Purchase, Retailer
from app.rules.returns import return_window


def mk(retailer, bought, delivered=None, **kw):
    return Purchase(retailer=retailer, order_id="X", item_name="thing", price=100.0,
                    purchased_on=bought, delivered_on=delivered, **kw)


def test_amazon_standard_30_days_from_delivery():
    p = mk(Retailer.amazon, date(2026, 9, 1), date(2026, 9, 4))
    rw = return_window(p, today=date(2026, 9, 10))
    assert rw.deadline == date(2026, 10, 4)
    assert rw.days_left == 24
    assert not rw.is_holiday_extension


def test_amazon_holiday_extends_to_jan_31():
    p = mk(Retailer.amazon, date(2026, 11, 20), date(2026, 11, 23))
    rw = return_window(p, today=date(2026, 12, 1))
    assert rw.deadline == date(2027, 1, 31)
    assert rw.is_holiday_extension


def test_amazon_holiday_apple_items_jan_15():
    p = mk(Retailer.amazon, date(2026, 12, 10), category="apple")
    rw = return_window(p, today=date(2026, 12, 11))
    assert rw.deadline == date(2027, 1, 15)


def test_amazon_late_december_standard_may_beat_holiday():
    # bought Dec 31, delivered Jan 5 -> 30 days = Feb 4 > Jan 31
    p = mk(Retailer.amazon, date(2026, 12, 31), date(2027, 1, 5))
    rw = return_window(p, today=date(2027, 1, 6))
    assert rw.deadline == date(2027, 2, 4)
    assert not rw.is_holiday_extension


def test_bestbuy_standard_15_days():
    p = mk(Retailer.bestbuy, date(2026, 6, 1), date(2026, 6, 3))
    rw = return_window(p, today=date(2026, 6, 10))
    assert rw.deadline == date(2026, 6, 18)


def test_bestbuy_member_60_days():
    p = mk(Retailer.bestbuy, date(2026, 6, 1), bestbuy_membership="total")
    assert return_window(p, today=date(2026, 6, 2)).deadline == date(2026, 7, 31)


def test_bestbuy_phone_14_days_no_holiday_extension():
    p = mk(Retailer.bestbuy, date(2026, 11, 28), category="phone")
    rw = return_window(p, today=date(2026, 11, 29))
    assert rw.deadline == date(2026, 12, 12)
    assert not rw.is_holiday_extension


def test_bestbuy_holiday_extension():
    p = mk(Retailer.bestbuy, date(2026, 10, 27))
    rw = return_window(p, today=date(2026, 10, 28))
    assert rw.deadline == date(2027, 1, 14)
    assert rw.is_holiday_extension


def test_bestbuy_appliance_excluded_from_holiday():
    p = mk(Retailer.bestbuy, date(2026, 11, 28), category="appliance")
    assert return_window(p, today=date(2026, 11, 29)).deadline == date(2026, 12, 13)


def test_ebay_no_returns():
    p = mk(Retailer.ebay, date(2026, 5, 1))
    rw = return_window(p, today=date(2026, 5, 2), seller_return_days=0)
    assert rw.deadline is None and rw.urgency == "none"


def test_urgency_bands():
    p = mk(Retailer.bestbuy, date(2026, 6, 1))
    assert return_window(p, today=date(2026, 6, 15)).urgency == "critical"
    assert return_window(p, today=date(2026, 6, 10)).urgency == "soon"
    assert return_window(p, today=date(2026, 6, 20)).urgency == "closed"
