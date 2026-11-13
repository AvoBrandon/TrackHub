# Clawback

*Working title. Rename freely; the code does not care.*

A personal "money you are owed" watcher for travel and shopping. One always-on server does the
watching; a native iPhone app and a native Windows app show you what to do and when.

| # | Feature | How it works | Needs |
|---|---------|--------------|-------|
| 1 | **Delay compensation claimer** | Flights imported from Gmail; tracked every 15 min on travel day; EU261 / UK261 / Canada APPR / US DOT refund rules compute what you are owed and the exact next step | FlightAware AeroAPI key (free personal tier) |
| 2 | **Rebook-after-booking hotel watcher** | Nightly re-price of every booked hotel; tells you "book new rate first, then cancel conf. X before the free-cancel deadline" | Any hotel-offers API you have access to; without one, you get a weekly one-tap manual check with the exact dates pre-filled |
| 3 | **TSA wait times** | The morning of a flight, latest checkpoint wait for your departure airport, with the airport's live page as fallback | nothing (unofficial feed, best-effort, says so when unavailable) |
| 4 | **Trip brief** | Evening before travel: weather, auto packing list, **Apple Maps / Google Maps directions ready to tap or copy** (no push required, it is waiting in the app) | nothing (Open-Meteo is free) |
| 11 | **Return window alarm** | Amazon, Best Buy, eBay orders parsed from Gmail; countdown per item; alerts at 7, 3, 1, 0 days; 2026 holiday extensions and exclusions built in | Gmail read-only connection |
| 12 | **Price adjustment claimer** | Daily price check of recent purchases; Best Buy price-match and Amazon return-and-rebuy routes with deadline | Best Buy API key (free); Keepa for Amazon (paid) |
| 14 | **Open-box watcher** | Watch any item across Best Buy open-box, Amazon Warehouse, eBay; alert the moment one appears or hits your target | Best Buy key, eBay developer keys (free), Keepa |
| 20 | **Card price protection** | Flags when a drop falls inside your card's price-protection window and cap | you tell it which card you used |
| 29 | **Subscription creep** | Recurring-charge detection over receipts + any bank CSV; monthly report with yearly cost | Gmail and/or a CSV export |

Everything else is in `docs/`:

* `docs/SETUP.md` – step by step: server, Gmail, API keys, iPhone build, Windows build.
* `docs/ARCHITECTURE.md` – how the pieces fit and why it is built this way.
* `docs/LIMITS.md` – what cannot be fully automated in 2026 and what the app does instead. Read this.
* `docs/SOURCES.md` – where every policy date and rule came from.

## Status (Nov 13 2026)

* Backend: complete, 47 automated tests passing, boots and runs its schedule.
* Flutter app: complete UI for all nine features; `flutter analyze` clean; Dart tests pass.
  Native iOS and Windows builds have not been compiled yet because that needs a Mac with Xcode
  and a Windows machine with Visual Studio respectively (see SETUP).

## Layout

```
backend/   FastAPI + APScheduler service (Python 3.12+)
app/       Flutter app (iOS + Windows from one codebase)
deploy/    docker-compose, systemd unit, Windows service installer
docs/      setup, architecture, limits, sources
```
