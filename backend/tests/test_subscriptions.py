from datetime import date, timedelta

from app.models import Transaction
from app.rules.subscriptions import detect, monthly_report


def tx(merchant, amount, d):
    return Transaction(merchant=merchant, amount=amount, posted_on=d)


def test_detects_monthly_and_yearly():
    today = date(2026, 11, 13)
    txs = [tx("NETFLIX.COM *1234", 15.49, today - timedelta(days=30 * k + 3)) for k in range(4)]
    txs += [tx("AMAZON PRIME MEMBERSHIP", 139.0, date(2025, 11, 1)), tx("Amazon Prime Membership", 139.0, date(2026, 11, 1))]
    txs += [tx("Home Depot #221", 44.10, today - timedelta(days=20)), tx("Home Depot #221", 212.0, today - timedelta(days=50))]
    recs = detect(txs, today=today)
    by = {r.merchant: r for r in recs}
    assert "netflix" in by and by["netflix"].cadence == "monthly"
    assert "amazon prime membership" in by and by["amazon prime membership"].cadence == "yearly"
    assert not any("home depot" in m for m in by)
    assert "recurring charges" in monthly_report(recs)


def test_dead_subscription_dropped():
    today = date(2026, 11, 13)
    txs = [tx("Hulu", 17.99, date(2026, 3, 1) - timedelta(days=30 * k)) for k in range(3)]
    assert detect(txs, today=today) == []
