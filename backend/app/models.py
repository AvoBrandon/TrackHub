"""Persistent records. Keep these flat and boring; the rules engines are pure functions over them."""
from __future__ import annotations

from datetime import date, datetime, timezone

from pydantic import NaiveDatetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Retailer(str, Enum):
    amazon = "amazon"
    bestbuy = "bestbuy"
    ebay = "ebay"
    other = "other"


class Purchase(SQLModel, table=True):
    """One line item from a receipt."""

    id: Optional[int] = Field(default=None, primary_key=True)
    retailer: Retailer
    order_id: str = Field(index=True)
    item_name: str
    sku: str = ""                 # Best Buy SKU / Amazon ASIN / eBay item id when known
    price: float
    currency: str = "USD"
    purchased_on: date
    delivered_on: Optional[date] = None
    is_open_box: bool = False
    is_marketplace_seller: bool = False
    category: str = ""            # "appliance", "phone", "apple", ... used by return-rule exclusions
    bestbuy_membership: str = ""  # "", "plus", "total"
    card_last4: str = ""
    card_product: str = ""        # e.g. "Capital One Venture X", used by card price protection
    source_message_id: str = Field(default="", index=True)
    returned: bool = False
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class PriceObservation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    purchase_id: Optional[int] = Field(default=None, foreign_key="purchase.id", index=True)
    watch_id: Optional[int] = Field(default=None, foreign_key="watch.id", index=True)
    source: str                   # bestbuy | ebay | keepa | manual
    price: float
    condition: str = "new"        # new | open-box-excellent | open-box-satisfactory | used
    url: str = ""
    seen_at: NaiveDatetime = Field(default_factory=utcnow)


class Watch(SQLModel, table=True):
    """Something you WANT to buy (open-box watcher / cross-market price watch)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    label: str
    bestbuy_sku: str = ""
    amazon_asin: str = ""
    ebay_query: str = ""
    target_price: Optional[float] = None
    want_open_box: bool = True
    active: bool = True
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class Flight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    confirmation: str = Field(index=True)
    airline_iata: str              # "DL"
    flight_number: str             # "DL123"
    origin: str                    # IATA
    destination: str
    scheduled_departure: NaiveDatetime  # local time at origin, naive
    scheduled_arrival: NaiveDatetime
    actual_departure: Optional[NaiveDatetime] = None
    actual_arrival: Optional[NaiveDatetime] = None
    status: str = "scheduled"      # scheduled|delayed|cancelled|landed|diverted
    cancelled: bool = False
    distance_km: Optional[float] = None
    fare_paid: Optional[float] = None
    origin_country: str = "US"
    destination_country: str = "US"
    airline_country: str = "US"
    source_message_id: str = Field(default="", index=True)
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class HotelBooking(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    confirmation: str = Field(index=True)
    hotel_name: str
    city: str = ""
    check_in: date
    check_out: date
    total_price: float
    currency: str = "USD"
    free_cancel_until: Optional[NaiveDatetime] = None
    room_type: str = ""
    provider: str = ""             # booking.com, hotels.com, direct, ...
    provider_hotel_id: str = ""    # id in the re-check API
    best_seen_price: Optional[float] = None
    best_seen_at: Optional[NaiveDatetime] = None
    source_message_id: str = Field(default="", index=True)
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class Trip(SQLModel, table=True):
    """A travel day we should brief you on the evening before."""

    id: Optional[int] = Field(default=None, primary_key=True)
    label: str
    travel_date: date
    origin_address: str            # home / hotel address
    destination_address: str       # airport terminal / venue
    destination_city: str
    destination_lat: Optional[float] = None
    destination_lon: Optional[float] = None
    flight_id: Optional[int] = Field(default=None, foreign_key="flight.id")
    brief_sent_at: Optional[NaiveDatetime] = None
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class Transaction(SQLModel, table=True):
    """A charge seen on a card/bank statement or a receipt email. Feeds subscription detection."""

    id: Optional[int] = Field(default=None, primary_key=True)
    merchant: str = Field(index=True)
    amount: float
    currency: str = "USD"
    posted_on: date
    card_last4: str = ""
    source: str = "email"          # email | csv | plaid
    source_ref: str = Field(default="", index=True)


class Subscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    merchant: str = Field(index=True)
    amount: float
    cadence: str                   # monthly | yearly | weekly
    last_charged: date
    next_expected: date
    confidence: float
    acknowledged: bool = False     # you said "yes I know, keep it"
    flagged_cancel: bool = False   # you said "remind me to cancel"
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class AlertKind(str, Enum):
    return_window = "return_window"
    price_adjust = "price_adjust"
    card_protection = "card_protection"
    open_box = "open_box"
    price_watch = "price_watch"
    flight_comp = "flight_comp"
    hotel_rebook = "hotel_rebook"
    tsa_wait = "tsa_wait"
    trip_brief = "trip_brief"
    subscriptions = "subscriptions"
    system = "system"


class Alert(SQLModel, table=True):
    """Outbox. The apps pull these; iPhone additionally gets an APNs push."""

    id: Optional[int] = Field(default=None, primary_key=True)
    kind: AlertKind = Field(index=True)
    title: str
    body: str
    dedupe_key: str = Field(index=True, unique=True)
    payload_json: str = "{}"
    money_at_stake: float = 0.0
    action_url: str = ""
    created_at: NaiveDatetime = Field(default_factory=utcnow)
    pushed_at: Optional[NaiveDatetime] = None
    read_at: Optional[NaiveDatetime] = None
    dismissed_at: Optional[NaiveDatetime] = None


class Device(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    platform: str                  # ios | windows
    token: str = Field(index=True, unique=True)   # APNs token, or a random id for Windows pollers
    name: str = ""
    last_seen: NaiveDatetime = Field(default_factory=utcnow)


class JobRun(SQLModel, table=True):
    """Every scheduled job writes a row so the app can show 'last ran / last error' per watcher."""

    id: Optional[int] = Field(default=None, primary_key=True)
    job: str = Field(index=True)
    started_at: NaiveDatetime = Field(default_factory=utcnow)
    finished_at: Optional[NaiveDatetime] = None
    ok: bool = True
    detail: str = ""
