from datetime import date

from app.models import Purchase, Retailer
from app.rules.price_adjust import opportunities


def test_bestbuy_price_match_inside_window():
    p = Purchase(retailer=Retailer.bestbuy, order_id="BBY1", item_name="TV", price=899.99, purchased_on=date(2026, 11, 1))
    ops = opportunities(p, 749.99, today=date(2026, 11, 10))
    assert [o.route for o in ops] == ["bestbuy_price_match"]
    assert ops[0].refund == 150.0


def test_amazon_return_and_rebuy_only():
    p = Purchase(retailer=Retailer.amazon, order_id="A1", item_name="Vacuum", price=300, purchased_on=date(2026, 11, 1))
    ops = opportunities(p, 250, today=date(2026, 11, 10))
    assert [o.route for o in ops] == ["amazon_return_rebuy"]


def test_card_protection_adds_route_and_caps():
    p = Purchase(retailer=Retailer.amazon, order_id="A2", item_name="Laptop", price=2000, purchased_on=date(2026, 9, 1),
                 card_product="Capital One Venture X World Elite Mastercard")
    ops = opportunities(p, 1500, today=date(2026, 10, 15))  # Amazon window closed; card still open (60d)
    assert [o.route for o in ops] == ["card_price_protection"]
    assert ops[0].refund == 250.0


def test_tiny_drop_ignored():
    p = Purchase(retailer=Retailer.bestbuy, order_id="B", item_name="x", price=50, purchased_on=date(2026, 11, 1))
    assert opportunities(p, 49.5, today=date(2026, 11, 2)) == []
