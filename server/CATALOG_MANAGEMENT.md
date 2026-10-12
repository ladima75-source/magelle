# Catalog Management 2.0

The existing SQLite database is the catalog source for admin, API, storefront, PDP,
cart and server-priced orders. There is no SKU count limit.

## Safe migration

`ops/deploy_catalog.sh REVIEWED_SHA` requires a clean tracked checkout and an existing
installation, takes a SQLite online backup, updates only by fast-forward, runs the
safety tests, then dry-runs and applies the importer with a second backup.
`server/import_catalog.py --db PATH` runs entirely against an in-memory copy. Apply
requires `--apply --backup NEW_PATH`; an existing backup is never overwritten.

The additive schema keeps the original 16 product records, their complete commercial
fields and media, and all existing orders/items byte-equivalent at field level.
The importer verifies a SHA-256 preservation fingerprint. It imports the 16 existing
designs and 64 exact design/color variants from approved storefront markup, using
existing base-color prices/statuses. Variants without prices stay draft/unavailable.
Original galleries are assigned only to their known color. Repeat import adds nothing
and never overwrites later edits. No hard-delete or destructive SQL migration exists.

## Changes and history

Product UUIDs stay stable when SKU is renamed. The former SKU remains a reserved
alias, including for existing carts. Old order rows stay untouched. New order items
contain product identity and a server-built snapshot of SKU, design, price and media.
The server rejects unavailable items, unknown SKUs and client price/metadata overrides.

Hidden/archived designs disappear from public catalog and block orders for their
variants. Soft-delete requires owner + exact typed name/SKU and refuses products
referenced by orders or designs with remaining variants. Deleted records can be
restored. Individual product restoration requires a price and availability choice.

Every write has a record revision (409 on concurrent changes), CSRF protection,
role enforcement and before/after audit. Full reorder is atomic and revision checked.
Drag by the handle on desktop, or use arrows/touch drag on mobile. Save errors keep
the editor open. Leaving a dirty editor requires confirmation.

## Roles

Existing owner access is preserved. Owner can edit, soft-delete and inspect audit;
editor can maintain catalog/media/orders; viewer can read but cannot mutate.
Optional `MAGELLE_ADMIN_USERS` in the existing root-only environment file supports
named users: JSON keyed by username, each with role, salt (hex) and scrypt hash (hex).
Hashes use Python hashlib.scrypt(password, salt, n=16384, r=8, p=1). Passwords and
credentials are never committed. Named sessions check current role on every request.
The existing owner credential is changed only by its owner. Login attempts are limited
to 10 failures per five minutes per server-observed address; sessions expire in 24h.

## Media

Upload PNG/JPEG/WebP up to 12 MB; HTTPS links, gallery order and removal are editable.
Uploads use random filenames, fixed MIME and nosniff. Files live beside the DB in media/.
Nginx `client_max_body_size 12m` must be enabled in the existing API virtual host.
`cache_approved_media.py --db PATH` accepts an approved transfer manifest on stdin,
verifies the exact original SHA-256, and creates a public cache mapping. Original
stored links remain unchanged. Temporary authenticated download links must never be
logged or committed. Back up the database and its media directory together.

## Rollback

Prefer reverting application code while retaining the additive schema and all orders.
Disable catalog_meta.enabled before restoring the former storefront code. Do not
restore a database backup over any orders received after migration. A backup restore
requires a maintenance window, reconciliation of newer orders and explicit approval.
The deployment script records the former commit beside the pre-migration backup.

## Validation

Run `python -m unittest discover -s server -p test_catalog.py -v` and
`node --check app.js`, `node --check server/static/admin2.js`. The GitHub workflow
runs the same checks. Browser QA covers creation, upload, preview, hide/restore,
reordering, generic PDP, color/price selection, cart, checkout and mobile layout.
Live verification must include health, preserved data fingerprint, counts, media,
authenticated admin, storefront and cart; no test customer order is required in live DB.
