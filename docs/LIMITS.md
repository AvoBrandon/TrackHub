# What cannot be fully automated (and what the app does instead)

You asked for no failures. The honest way to get there is to not pretend. These are the places
where the outside world does not offer a reliable hook, and how the app handles each.

| Area | Reality in Nov 2026 | What Clawback does |
|------|---------------------|--------------------|
| **TSA wait times** | There is no official public API. The old MyTSA web service still answers for many airports but TSA does not promise it, and during 2026 staffing problems it was reported stale. TSA has a real-time wait-time program in rulemaking. | Uses the legacy feed best-effort and, if it fails or is stale, the morning alert says so and links the airport's own live wait-time page. It never invents a number. |
| **Amazon prices** | Amazon has no public price API. | Keepa (paid, ~€19/mo) gives reliable Amazon + Warehouse prices. Without it, Amazon return windows still work; price-drop checks for Amazon are skipped and shown as "not configured". |
| **Amazon price adjustments** | Amazon stopped adjusting prices in 2016. | The app tells you the only real route: reorder at the new price and return the original inside the window, with the deadline. |
| **Best Buy API keys** | Free, but Best Buy approves keys manually and may not issue them to free-mail addresses. | Apply with a non-Gmail address if you have one. Until then open-box and price checks for Best Buy show as "not configured". |
| **Hotel re-pricing** | No free public API gives live rates. | If you have access to any offers API (wholesale, affiliate), point `HOTEL_API_BASE` at it. Otherwise you get a weekly one-tap alert with Google Hotels / Booking / Hotels.com pre-filled for the exact dates: a 10-second manual check that still catches drops. |
| **Credit-card price protection** | Nearly every US issuer dropped it. A few Mastercard World Elite products, some Capital One cards, UBS Visa Infinite, HSBC Premier WE still have it per 2026 benefit guides. | A small editable table (`rules/price_adjust.py`, `CARD_PROTECTION`). The alert says "worth a claim, verify in your Guide to Benefits", never "guaranteed". Put the card you used on each purchase so the rule can fire. |
| **US flight delay cash** | US law gives no cash compensation for delays, only an automatic cash refund if the flight is cancelled or significantly delayed (3h domestic / 6h international) and you do not fly. EU/UK/Canada do pay cash. | Computes each regime separately and labels confidence "likely" vs "possible". |
| **iPhone install** | Apple requires a Mac with Xcode and an Apple Developer account ($99/yr) to install on your own phone for more than 7 days and to use push notifications. | Documented in SETUP. The Windows app has no such requirement. |
| **Gmail parsing** | Receipt emails change format without notice. | Structured data (schema.org JSON-LD) is used first, regex second, and anything missed can be added by hand in the app in 20 seconds. Deliveries update the return clock when the "Delivered" email arrives. |
| **Live calls from this build environment** | The sandbox used to build this blocked outbound calls to Open-Meteo and the TSA feed. | Parsers are unit-tested against real payload shapes; first live run happens on your server. |
