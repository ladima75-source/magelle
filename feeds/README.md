# MaGelle feeds

## Production

The production Google Merchant Center source is **/merchant.xml**.

It is generated from live Admin 2.0 by:
- `scripts/build_merchant_feed.py`
- `scripts/verify_merchant_feed.py`
- `.github/workflows/merchant-feed.yml`

Do not configure Merchant Center to any other feed file in this repository.

## Legacy snapshots

- `feeds/google-merchant-products.xml` — historical 3-item Google feed snapshot. Not production.
- `feeds/chatgpt-products.jsonl` — historical 3-item AI-shopping snapshot. Not a current catalog source of truth.

They are retained only as historical artifacts until their external-consumer status is explicitly confirmed. New integrations must use Admin 2.0/catalog data, not these snapshots.

## ROZETKA

`/rozetka.xml` is separate from Google Merchant. It belongs to a safety-disabled three-item ROZETKA experiment controlled by `ops/rozetka_import_first3.sh`. It is not a storefront or Merchant source of truth.
