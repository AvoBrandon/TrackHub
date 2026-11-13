"""End-to-end through the HTTP API with an in-memory DB and the scheduler off."""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app.main import app
from app.services import job_flights, job_return_windows, job_subscriptions, job_trip_brief, run_job

H = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel, create_engine

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(dbmod, "_engine", eng)
    from app import models  # noqa: F401
    SQLModel.metadata.create_all(eng)
    yield


def client():
    return TestClient(app)


def test_auth_required():
    with client() as c:
        assert c.get("/health").status_code == 200
        assert c.get("/api/alerts").status_code == 401


def test_return_window_flow_creates_alert():
    with client() as c:
        today = date.today()
        r = c.post("/api/purchases", headers=H, json={
            "retailer": "bestbuy", "order_id": "BBY01-1", "item_name": "Dishwasher", "price": 399.0, "category": "appliance",
            "purchased_on": (today - timedelta(days=12)).isoformat()})
        assert r.status_code == 200 and r.json()["days_left"] == 3 and r.json()["urgency"] == "soon"
        import asyncio
        jr = asyncio.run(run_job("return_windows", job_return_windows))
        assert jr.ok and "alerts=1" in jr.detail
        alerts = c.get("/api/alerts", headers=H).json()
        assert len(alerts) == 1 and alerts[0]["kind"] == "return_window" and alerts[0]["money_at_stake"] == 399.0
        # idempotent
        asyncio.run(run_job("return_windows", job_return_windows))
        assert len(c.get("/api/alerts", headers=H).json()) == 1
        c.post(f"/api/alerts/{alerts[0]['id']}/dismiss", headers=H)
        assert c.get("/api/alerts", headers=H).json() == []


def test_flight_claim_alert_without_api_key():
    import asyncio
    with client() as c:
        dep = datetime.now().replace(microsecond=0) - timedelta(hours=5)
        r = c.post("/api/flights", headers=H, json={
            "confirmation": "ZZZ111", "airline_iata": "AF", "flight_number": "AF007", "origin": "CDG", "destination": "JFK",
            "scheduled_departure": dep.isoformat(), "scheduled_arrival": (dep + timedelta(hours=8)).isoformat(),
            "fare_paid": 650, "distance_km": 5800, "origin_country": "FR", "destination_country": "US", "airline_country": "FR"})
        assert r.status_code == 200, r.text
        fid = r.json()["id"]
        # simulate what AeroAPI would have written: cancelled
        with dbmod.session() as s:
            from app.models import Flight
            f = s.get(Flight, fid); f.cancelled = True; s.add(f); s.commit()
        jr = asyncio.run(run_job("flights", job_flights))
        assert jr.ok, jr.detail
        al = c.get("/api/alerts", headers=H).json()
        assert al[0]["kind"] == "flight_comp" and al[0]["money_at_stake"] == 650 + 600
        fl = c.get("/api/flights", headers=H).json()[0]
        assert {cl["regime"] for cl in fl["claims"]} == {"EU261", "US DOT refund"}
        # past flights get no auto Trip; a future one does
        assert c.get("/api/trips", headers=H).json() == []
        fut = datetime.now().replace(microsecond=0) + timedelta(days=3)
        c.post("/api/flights", headers=H, json={"confirmation": "FUT1", "airline_iata": "DL", "flight_number": "DL100",
                                                "origin": "JFK", "destination": "MCO", "scheduled_departure": fut.isoformat(),
                                                "scheduled_arrival": (fut + timedelta(hours=3)).isoformat()})
        trips = c.get("/api/trips", headers=H).json()
        assert len(trips) == 1 and trips[0]["destination_address"] == "JFK Airport"


def test_trip_brief_job_offline_still_sends_maps():
    import asyncio
    with client() as c:
        tomorrow = date.today() + timedelta(days=1)
        c.post("/api/trips", headers=H, json={"label": "Orlando", "travel_date": tomorrow.isoformat(),
                                              "origin_address": "1 Main St Brooklyn NY", "destination_address": "JFK Terminal 4",
                                              "destination_city": "Orlando"})
        jr = asyncio.run(run_job("trip_brief", job_trip_brief))
        assert jr.ok, jr.detail
        a = c.get("/api/alerts", headers=H).json()[0]
        assert a["kind"] == "trip_brief" and a["payload"]["maps"]["apple"].startswith("https://maps.apple.com/")
        assert "Phone charger + cable" in a["payload"]["packing"]


def test_csv_import_and_subscription_report():
    import asyncio
    with client() as c:
        rows = ["Date,Description,Amount"]
        for k in range(4):
            rows.append(f"{(date.today() - timedelta(days=30*k+2)).isoformat()},SPOTIFY USA,-11.99")
        rows.append(f"{(date.today() - timedelta(days=9)).isoformat()},TRADER JOES #552,-84.10")
        r = c.post("/api/transactions/import-csv", headers=H, files={"file": ("chase.csv", "\n".join(rows), "text/csv")})
        assert r.json() == {"imported": 5}
        jr = asyncio.run(run_job("subscriptions", job_subscriptions))
        assert jr.ok and "recurring=1" in jr.detail
        subs = c.get("/api/subscriptions", headers=H).json()
        assert subs["monthly_total"] == 11.99 and subs["items"][0]["merchant"] == "spotify usa"
        assert c.get("/api/alerts", headers=H).json()[0]["kind"] == "subscriptions"


def test_health_lists_every_job_and_connector():
    with client() as c:
        h = c.get("/health").json()
        assert set(h["jobs"]) >= {"return_windows", "flights", "hotels", "tsa", "trip_brief", "subscriptions", "watches", "price_adjust"}
        names = {x["name"] for x in h["connectors"]}
        assert {"bestbuy", "ebay", "keepa", "aeroapi", "tsa", "open-meteo"} <= names
        assert all(x["configured"] is False for x in h["connectors"] if x["name"] in ("bestbuy", "ebay", "keepa", "aeroapi"))


def test_manual_job_trigger_endpoint():
    with client() as c:
        r = c.post("/api/jobs/return_windows/run", headers=H)
        assert r.status_code == 200 and r.json()["ok"] is True
        assert c.post("/api/jobs/nope/run", headers=H).status_code == 404
