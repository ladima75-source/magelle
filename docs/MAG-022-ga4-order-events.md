# MAG-022 — GA4 purchase vs order-request tracking
Audit: 2026-10-14 · Owner: 04 (site), 05 (GA4 validation and conversion definitions), Admin 2.0/server deploy.

## Business semantics — authoritative
An order request created by `POST /api/orders` is **not a confirmed purchase**.
The backend persists it with `status=new` and `payment_status=unpaid`.
Receiving HTTP 201 + `{ok:true, order_id:...}` means the lead/order request exists, not that it was paid.

- `view_item`: on an actual product detail page, after exact Admin SKU and positive UAH price are loaded; repeat only after selected SKU changes.
- `add_to_cart`: successful add to cart of actual saleable SKU; real price (UAH) and `quantity:1`.
- `begin_checkout`: only after a valid nonempty cart and real Admin price/availability; once per checkout page view.
- `generate_lead`: ONLY successful accepted order request, HTTP 201 and valid server-generated `order_id`; NOT on failed POST; never include buyer contact details.
- `purchase`: ONLY server-side when the stored order status is one of `confirmed,production,shipped,done` AND `payment_status=paid`. Never fire it from checkout or on `status=new`. Deduplicate via stored `ga4_purchase_sent_at` and `transaction_id=MG-<order_id>`.

GA4 site Measurement ID currently used in `app.js`: `G-1RM1S55BZW`.
The public site code sends browser events using `gtag('event',...)` with `send_to` and no PII. No page-visit to `checkout.html` sends purchase.

## Code paths
- `app.js`: event builders, exact SKU, UAH price, first-party GA client ID, add-to-cart.
- `checkout.html`: checkout event and mocked testable 201 vs error semantics. Sends pseudonymous `analytics_client_id` to server, never a GA4 API secret.
- `server/catalog.py`: additive schema fields `orders.ga4_client_id`, `ga4_purchase_sent_at`, `ga4_purchase_claimed_at`; persists client ID only if valid.
- `server/ga4_orders.py`: builds GA4 Measurement Protocol purchase only for paid+confirmed orders; HTTP POST with secret only on server, stable transaction ID and idempotent sent marker.
- `server/app.py`: calls server-side purchase sync only after successful, committed authorized Admin order status update.
- `server/test_catalog.py`: tests unpaid/new is not a purchase; only confirmed+paid generates one event; cancelled+paid not a purchase; failed MP delivery can retry.

## Actual QA 14 October 2026
Desktop Commander / Chrome headless 430px (real magelle.com.ua):
- `organic-flare-delikatnyi-shokolad.html` loaded `app.js?v=4.3` and `gtag.js?id=G-1RM1S55BZW`.
- `MG-OF-OLI-DEL-CHO`, 2600 UAH: `view_item` observed with correct SKU and value 2600.
- One click `Додати в кошик`: `add_to_cart` observed once, value 2600.
- Navigating to `checkout.html` with one item: `begin_checkout` observed, value 2600, SKU correct. No `purchase`, no `generate_lead`.
- Empty cart checkout: no `begin_checkout`, no `purchase`.
- Mocked HTTP 201 (no real order sent): `generate_lead` observed, no `purchase`.
- Mocked HTTP 400: no `generate_lead` or `purchase`.
- `Catalog safety` CI: SUCCESS including server GA4 tests.
No real production order was submitted for QA; browser payload observation does **not** prove GA4 reports received events.

## Backend deployment / real purchase — OPEN
Current changes are committed in GitHub but backend VPS deployment has **not** been verified. API service uses `/etc/magelle-admin.env`; the server must be updated with the verified GA4 commit using the approved deployment procedure and migration/backup.
A **GA4 Measurement Protocol API secret** must be created for the site's own GA4 web data stream and injected server-side as `GA4_API_SECRET` into `/etc/magelle-admin.env`, with restricted permissions. **Never add it to GitHub, HTML, or client JavaScript.**
Without the API secret, `purchase` is deliberately NOT sent; accepted order requests can still produce `generate_lead`.
For a paid+confirmed order with no GA4 client ID (tracking blocked), purchase is also withheld to avoid attributing it to the admin's browser.
After deploying server and configuring the secret, perform a controlled real status transition on a non-revenue test order, verify request with GA4 DebugView/Realtime (and then remove test pollution per 05's policy), check duplicate behavior. Do NOT make the live customer test order without coordination.
05 must confirm G-1RM1S55BZW belongs to MaGelle, set `generate_lead` vs `purchase` conversions appropriately and ensure checkout page views are NOT imported as Purchases in Google Ads.
No Ads launched or settings changed in GA4/Google Ads.
