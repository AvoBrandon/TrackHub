# Architecture

## Why a server plus two thin apps

The complaint with the previous tool was "it only runs when the web page happens to be open".
Phones cannot fix that: iOS suspends background work within seconds and will not wake an app on a
schedule you choose. So the watching is done by a small server that is on 24/7, and the apps are
clients. The server can live on a $5/month VPS, a Raspberry Pi, a NAS, or your Windows tower as a
Windows service (`deploy/install-windows-service.ps1`). A VPS is the most reliable because your
tower may sleep.

```
Gmail (read-only) ─┐
Best Buy API       │          ┌──────────────────────────┐   APNs push    ┌─────────────┐
eBay Browse API    ├─ pull ──▶│  backend (FastAPI)       │ ─────────────▶ │ iPhone app  │
Keepa (Amazon)     │          │  APScheduler jobs        │                └─────────────┘
AeroAPI (flights)  │          │  rules engines           │   REST poll    ┌─────────────┐
Open-Meteo         │          │  SQLite                  │ ◀────────────▶ │ Windows app │
MyTSA (unofficial) ┘          └──────────────────────────┘   + toast      └─────────────┘
```

## Backend (`backend/app`)

* `models.py` – flat SQLModel tables: Purchase, Watch, Flight, HotelBooking, Trip, Transaction,
  Subscription, Alert (the outbox), Device, JobRun, PriceObservation.
* `rules/` – **pure functions, fully unit-tested, no I/O**:
  * `returns.py` – Amazon / Best Buy / eBay return deadlines incl. 2026 holiday extensions.
  * `price_adjust.py` – Best Buy price match, Amazon return-and-rebuy, card price protection table.
  * `flights.py` – EU261, UK261, Canada APPR, US DOT refund, Montreal Convention.
  * `subscriptions.py` – recurring-charge detection over transactions.
  * `hotels.py` – when a lower rate is worth a cancel-and-rebook.
  * `tripbrief.py` – packing list from forecast, Apple/Google Maps deep links.
* `connectors/` – one class per external service behind `Connector`. Every connector reports
  `configured` so a missing key is a visible yellow badge in the app, never a crash. Parsers are
  separated from HTTP so they are tested against captured payload shapes.
* `ingest/` – Gmail reader (read-only scope) and parsers. Parsers try schema.org JSON-LD first
  (Amazon, airlines, hotel chains embed it), regex fallback second.
* `services.py` – the jobs. Each loads rows, calls a connector, runs a rule, emits alerts through
  `notify/outbox.emit`, which is idempotent on a dedupe key, so a job can run twice without
  double-alerting. Every run writes a JobRun row the app shows under "Watchers".
* `scheduler.py` – when each job runs. On boot the daily jobs run once, so a restart never means a
  missed deadline.
* `api/routes.py` – REST for the apps. Bearer token auth. `/health` is public and lists connector
  and job status.

## Apps (`app/`)

One Flutter codebase; `flutter build ios` and `flutter build windows`.

* Riverpod providers wrap the API; every screen has loading / error-with-retry / empty states.
* Inbox is the money view: alerts sorted newest first with the total at stake on top.
* iPhone receives APNs pushes from the server (token-based auth, `notify/apns.py`), registered via a
  tiny Swift method channel in `ios/Runner/AppDelegate.swift`.
* Windows has no server push; the app polls `/alerts` every 60 s, shows a native toast for each new
  one, and hides to the system tray on close so it keeps polling.
* Trip brief: directions are links the app opens or copies; nothing is pushed unless you want it.

## Alert delivery guarantees

* Alerts are rows first, notifications second. If a push fails, the alert is still in the Inbox.
* `dedupe_key` makes every watcher idempotent.
* Jobs never raise out of `run_job`; failures are recorded and shown, and the next tick retries.
