from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from ..models import Retailer


class PurchaseIn(BaseModel):
    retailer: Retailer
    order_id: str
    item_name: str
    price: float
    purchased_on: date
    delivered_on: Optional[date] = None
    sku: str = ""
    category: str = ""
    bestbuy_membership: str = ""
    card_product: str = ""
    is_marketplace_seller: bool = False


class PurchaseOut(BaseModel):
    id: int
    retailer: Retailer
    order_id: str
    item_name: str
    sku: str
    price: float
    purchased_on: date
    delivered_on: Optional[date]
    returned: bool
    deadline: Optional[date]
    days_left: Optional[int]
    urgency: str
    rule: str
    is_holiday_extension: bool


class WatchIn(BaseModel):
    label: str
    bestbuy_sku: str = ""
    amazon_asin: str = ""
    ebay_query: str = ""
    target_price: Optional[float] = None
    want_open_box: bool = True


class FlightIn(BaseModel):
    confirmation: str
    airline_iata: str
    flight_number: str
    origin: str
    destination: str
    scheduled_departure: datetime
    scheduled_arrival: datetime
    fare_paid: Optional[float] = None
    distance_km: Optional[float] = None
    origin_country: str = "US"
    destination_country: str = "US"
    airline_country: str = "US"


class HotelIn(BaseModel):
    confirmation: str
    hotel_name: str
    city: str = ""
    check_in: date
    check_out: date
    total_price: float
    free_cancel_until: Optional[datetime] = None
    provider: str = ""
    provider_hotel_id: str = ""


class TripIn(BaseModel):
    label: str
    travel_date: date
    origin_address: str
    destination_address: str
    destination_city: str
    flight_id: Optional[int] = None


class DeviceIn(BaseModel):
    platform: str
    token: str
    name: str = ""


class TransactionIn(BaseModel):
    merchant: str
    amount: float
    posted_on: date
    card_last4: str = ""
