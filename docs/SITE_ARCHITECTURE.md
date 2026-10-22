# MaGelle storefront architecture

Audit snapshot: 2026-10-22. Counts are snapshots; the catalog API and admission pipeline determine current availability.

## Sources of truth

- Product/design/price/availability state: Admin 2.0 / Catalog API.
- Reviewed exact-color storefront media: the static first-party media mapping; approved base galleries are preserved.
- Public catalog entry point: `catalog.html`.
- Production Google Merchant feed: `merchant.xml`.
- Canonical routes, frontend versions, and legacy redirects: `scripts/site_contract.py`.
- Global navigation and asset normalization: `scripts/sync_global_navigation.py`.
- ProductGroup generation: `scripts/sync_product_seo.py` reads the production Merchant feed, without editing catalog data, galleries, or product identities.

## Public catalog

The current public catalog has 16 designs and 64 managed color variants:
- Organic Flare: 10 designs × 5 colors = 50 variants.
- Architectural Step: 4 designs × 2 colors = 8 variants.
- Sculptural Fold: Koral and Rubin, 3 colors each = 6 variants.

Rubin retains internal design code `BUR`, SKU prefix `MG-SF-BUR-VYR-`, and the existing `burshtyn` URL/media paths for compatibility. These identifiers do not change the public name «Рубін».

Merchant admission requires an active managed SKU, positive UAH price, stock status, an exact first-party image, and a valid canonical design route. Explicit reviewed media overrides admit the additional Karamel and Rubin colors even when older Admin photo fields lag behind the published storefront. Feed counts are verified from generated output, never inferred from past project notes.

## Single-page color variants and canonical URLs

Each design has one indexable product page, anchored to its approved base/source vase color. This is the single-page variant model:
- Catalog cards and collection pages use the canonical design route.
- The base color opens on the clean URL.
- Other colors use the same page with `?color=CODE`; these deep links preselect the exact SKU, photo, price, and cart item.
- Every color variant keeps the same clean base canonical, before and after JavaScript hydration.
- Product and Offer URLs retain the exact color deep link. Canonical consolidation does not remove a SKU or prevent a direct Merchant landing.
- Historical color-named pages are lightweight `noindex` redirects and never re-enter the sitemap.
- Generic `product.html` remains `noindex`.

This follows Google's [URL guidance for ecommerce variants](https://developers.google.com/search/docs/specialty/ecommerce/designing-a-url-structure-for-ecommerce-sites) and [single-page ProductGroup examples](https://developers.google.com/search/docs/appearance/structured-data/product-variants).

## Sitemap and Merchant serve different purposes

`sitemap.xml` lists 28 clean canonical pages: 16 product pages and 12 other public pages. Color query URLs are excluded because they canonicalize to their design page. The static audit rejects query strings, fragments, duplicate URLs, legacy redirects, missing files, and noncanonical or noindex pages.

`merchant.xml` lists every admitted exact SKU, including non-base color deep links. It is not a search sitemap. All 64 current variants can therefore be represented in Merchant and ProductGroup while the sitemap contains 16 product pages. Sitemap inclusion is not evidence of Google indexing or approval.

## ProductGroup structured data

Each canonical product page contains exactly one `merchant-static-schema` script with:
- `ProductGroup`, a stable `@id`, clean canonical `url`, `productGroupID`, and `variesBy: ["https://schema.org/color"]`.
- A full `Product` entry in `hasVariant` for every admitted exact SKU, with unique URL-based `@id`, exact name, color, reviewed image, and `isVariantOf` group reference.
- One exact `Offer` per variant, with its landing URL, UAH price, condition, and availability.

The generator removes obsolete standalone Product scripts, including the historical duplicate Ritm SKU, and escapes `<` in JSON-LD. Runtime updates the same group rather than replacing it with an unrelated single Product or changing the canonical. Live SKU status and price remain authoritative at runtime.

`python scripts/sync_product_seo.py` regenerates markup after Merchant changes. `--check` validates freshness without writing files. The static audit compares every SKU/color/image/price/stock field against the feed. The Merchant verifier separately compares the feed and every embedded variant with live Admin admission results.

## Media and frontend contracts

- Google Drive is a source archive, not a storefront delivery URL.
- Exact Merchant images use `magelle.com.ua` or `api.magelle.com.ua`.
- A design's approved base/source gallery must not be deleted, shortened, or replaced with a single alternate-color image.
- First-party responsive WebP references require complete w360/w900/w1600 families.
- `scripts/site_contract.py` defines the current styles/app/menu versions; shared navigation sync normalizes every root storefront page.
- Base colors with 2+ source photos receive the gallery marker from the catalog's source color and unique source photo URLs.

## CI and deployment

Catalog safety runs backend catalog tests, the static storefront audit, generated-schema freshness checks, variant runtime regressions, and JavaScript syntax checks. Runtime regressions exercise supported and unsupported colors while preserving canonical URLs and exact variant data. Merchant feed sync rebuilds the feed, regenerates ProductGroup markup, verifies exact-SKU admission, then commits only reviewed generated outputs. GitHub Pages publishes the storefront; successful workflow status and public HTML/browser checks are required before reporting a deployment verified.

Search Console metrics, Google-selected canonical URLs, indexing status, and Merchant approvals require access to the corresponding MaGelle property. Local/static/browser checks cannot establish those Google-side states.
