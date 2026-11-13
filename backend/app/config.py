"""Settings. Every external key is optional; the app degrades per-connector, never crashes.

Copy backend/.env.example to backend/.env and fill in what you have.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # --- core ---
    app_name: str = "Clawback"
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'clawback.db'}"
    api_token: str = Field(default="change-me", description="Shared secret the phone/desktop apps send as a bearer token.")
    timezone: str = "America/New_York"
    home_airport: str = "JFK"
    home_address: str = ""              # used as the start point for trip-brief directions
    log_level: str = "INFO"
    scheduler_enabled: bool = True

    # --- Gmail (receipt ingestion) ---
    gmail_client_secret_file: str = str(BASE_DIR / "secrets" / "gmail_client_secret.json")
    gmail_token_file: str = str(BASE_DIR / "secrets" / "gmail_token.json")
    gmail_lookback_days: int = 120

    # --- retailers / marketplaces ---
    bestbuy_api_key: str = ""           # developer.bestbuy.com
    ebay_client_id: str = ""            # developer.ebay.com (Browse API, client-credentials)
    ebay_client_secret: str = ""
    ebay_marketplace: str = "EBAY_US"
    keepa_api_key: str = ""             # keepa.com (Amazon price history; paid)

    # --- flights ---
    aeroapi_key: str = ""               # flightaware.com/aeroapi
    flight_status_poll_minutes: int = 15

    # --- TSA (unofficial MyTSA feed; may be stale/unavailable) ---
    tsa_enabled: bool = True
    tsa_morning_hour: int = 6

    # --- hotels ---
    hotel_recheck_hour: int = 2          # nightly
    hotel_api_base: str = ""            # your wholesale/affiliate API base URL
    hotel_api_key: str = ""

    # --- Apple push (iPhone) ---
    apns_team_id: str = ""
    apns_key_id: str = ""
    apns_key_file: str = str(BASE_DIR / "secrets" / "AuthKey.p8")
    apns_bundle_id: str = "com.example.clawback"
    apns_use_sandbox: bool = True

    # --- feature toggles ---
    trip_brief_hour: int = 18           # the evening before travel

    @property
    def data_dir(self) -> Path:
        p = BASE_DIR / "data"
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
