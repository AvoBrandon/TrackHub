# Setup

Three parts: (1) run the server, (2) connect data sources, (3) install the apps.
Do them in order; the apps are useless without the server.

---

## 1. Run the server (15 minutes)

Pick one. The server needs Python 3.12+ and to be on 24/7.

### Option A – your Windows tower as a service (free)
1. Install Python 3.12+ from python.org (tick "Add to PATH").
2. Download NSSM from https://nssm.cc and put `nssm.exe` somewhere on PATH.
3. Open PowerShell **as Administrator** in this folder and run
   ```powershell
   .\deploy\install-windows-service.ps1
   ```
4. Edit `backend\.env` (created from `.env.example`): set `API_TOKEN` to a long random string,
   `TIMEZONE`, `HOME_AIRPORT`, `HOME_ADDRESS`. Re-run the script (or `nssm restart Clawback`).
5. Open http://localhost:8787/health in a browser. You should see JSON with `"ok": true`.
6. For the iPhone to reach it away from home you need either a static hostname + port forward
   with HTTPS, or (simplest) Tailscale on the tower and the phone. Tailscale gives you a stable
   `http://tower-name:8787` from anywhere with zero port forwarding.

Caveat: if the tower sleeps, watchers pause. Set Power Options to never sleep, or use Option B.

### Option B – a small Linux VPS (~$5/month, most reliable)
```bash
git clone <this repo> /opt/clawback && cd /opt/clawback/backend
python3 -m venv .venv && .venv/bin/pip install -e .
cp .env.example .env && nano .env
sudo cp ../deploy/clawback.service /etc/systemd/system/ && sudo systemctl enable --now clawback
```
Put Caddy or nginx in front for HTTPS (`caddy reverse-proxy --from clawback.yourdomain.com --to :8787`).

### Option C – Docker anywhere
```bash
cp backend/.env.example backend/.env && nano backend/.env
docker compose -f deploy/docker-compose.yml up -d --build
```

---

## 2. Connect data sources

Everything is optional; the app shows each one as ready / not configured under **Server**.

### Gmail (powers return windows, flights, hotels, subscriptions) – free
1. https://console.cloud.google.com → new project → APIs & Services → enable **Gmail API**.
2. OAuth consent screen: External, add yourself as a test user.
3. Credentials → Create → OAuth client ID → **Desktop app** → download JSON →
   save as `backend/secrets/gmail_client_secret.json`.
4. On the server, run once interactively to sign in (opens a browser; grants **read-only**):
   ```bash
   cd backend && .venv/bin/python -c "from app.ingest.gmail import _service; _service(); print('Gmail connected')"
   ```
   On a headless VPS do this step on your laptop, then copy `backend/secrets/gmail_token.json` to the server.
5. Restart the service. The `ingest_gmail` watcher runs every 30 minutes and backfills 120 days.

### Best Buy (price match + open-box) – free
Apply at https://developer.bestbuy.com. Keys are approved manually; use a non-free-mail address if
possible. Put the key in `BESTBUY_API_KEY`.

### eBay (open-box / cross-market watch) – free
https://developer.ebay.com → create an app → Production keys → `EBAY_CLIENT_ID` and
`EBAY_CLIENT_SECRET`. The Browse API needs a one-time "Buy API production access" approval in the portal.

### Keepa (Amazon prices incl. Warehouse) – paid, optional
https://keepa.com/#!api → smallest plan → `KEEPA_API_KEY`. Skip it if you do not want to pay;
Amazon return windows work without it.

### FlightAware AeroAPI (delay tracking) – free personal tier
https://www.flightaware.com/aeroapi → Personal plan → `AEROAPI_KEY`. Flights are polled only on
travel day, every 15 minutes, which fits in the free allowance.

### Hotels – optional
If you have access to any hotel offers API, set `HOTEL_API_BASE` / `HOTEL_API_KEY` and implement
the small `offers` adapter in `backend/app/connectors/hotels.py` for its response shape. Otherwise
the weekly manual-check alert works out of the box.

### Bank / card CSV (subscriptions)
Export transactions as CSV from your bank or card site and import from the **Subs** tab
(upload icon). Columns named Date / Description / Amount are detected automatically.

---

## 3. Install the apps

### Windows
Requires Visual Studio 2022 with "Desktop development with C++" and the Flutter SDK.
```powershell
cd app
flutter build windows --release
```
The exe is in `app\build\windows\x64\runner\Release\`. Copy that whole folder anywhere; make a
shortcut to `clawback.exe` in `shell:startup` so it launches at login. It lives in the tray, polls the
server every minute, and shows a Windows toast for every new alert.

First launch: go to **Server**, enter the URL and the `API_TOKEN`, press **Save & test**.

### iPhone
Apple's rules, not ours: you need a Mac with Xcode and an Apple Developer account ($99/yr) for an
app that stays installed and receives push notifications.
1. On the Mac: install Flutter, `cd app && flutter pub get && open ios/Runner.xcworkspace`.
2. In Xcode → Runner target → Signing & Capabilities: pick your team, set a unique bundle id
   (e.g. `com.yourname.clawback`), add **Push Notifications** and **Background Modes → Remote
   notifications**. `Runner.entitlements` is already in the project.
3. https://developer.apple.com → Keys → new key with **APNs** enabled → download `AuthKey_XXXX.p8`.
   On the server: save it as `backend/secrets/AuthKey.p8`, set `APNS_TEAM_ID`, `APNS_KEY_ID`,
   `APNS_BUNDLE_ID` (same as step 2), `APNS_USE_SANDBOX=true` for Xcode builds / `false` for
   TestFlight. Restart the service.
4. Plug in the iPhone, `flutter run --release` (or Product → Run in Xcode). Allow notifications.
5. In the app → **Server** → enter URL + token → Save. The APNs token registers automatically;
   `/health` will show `apns_configured: true` and alerts arrive as pushes even when the app is closed.
For a long-lived install without re-signing every week, upload to TestFlight (Xcode → Archive →
Distribute) and install from the TestFlight app.

---

## 4. Verify it end to end
1. **Server** tab shows green "Connected" and the connectors you configured as ready.
2. Press ▶ next to `ingest_gmail`; the Returns tab fills with recent orders and countdowns.
3. Press ▶ next to `return_windows`; anything inside 7 days appears in Inbox (Windows: a toast).
4. Add a trip for tomorrow in Travel → Trips, press ▶ next to `trip_brief`: the Inbox card has
   Apple Maps / Google Maps buttons and copy-link buttons.
