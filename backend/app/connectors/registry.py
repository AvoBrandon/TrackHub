from __future__ import annotations

from .aeroapi import AeroAPI
from .base import ConnectorStatus
from .bestbuy import BestBuy
from .ebay import Ebay
from .hotels import GenericHotelAPI
from .keepa import Keepa
from .tsa import TSA
from .weather import Weather


def all_connectors():
    return [BestBuy(), Ebay(), Keepa(), AeroAPI(), TSA(), Weather(), GenericHotelAPI()]


def statuses() -> list[ConnectorStatus]:
    return [c.status() for c in all_connectors()]
