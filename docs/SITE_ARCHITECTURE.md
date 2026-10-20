# MaGelle storefront architecture

Audit snapshot: 2026-10-20.

## Sources of truth

- Product/design/price/availability/media state: Admin 2.0 / Catalog API.
- Public catalog entry point: `catalog.html`.
- Production Google Merchant feed: `merchant.xml`.
- Global frontend versions and legacy URL contracts: `scripts/site_contract.py`.
- Global navigation and shared asset normalization: `scripts/sync_global_navigation.py`.

Static HTML must not become a second independent catalog database.

## Public catalog

Current storefront architecture:
- 15 public design cards.
- Organic Flare: 10 designs.
- Architectural Step: 4 designs.
- Sculptural Fold: 1 public design (Koral).

Audit snapshot of Merchant:
- 56 admitted exact-SKU items.
- 45 Organic Flare.
- 8 Architectural Step.
- 3 Sculptural Fold.
- Karamel is not admitted while exact Merchant media requirements remain unmet.

Counts are audit snapshots, not hard-coded business rules. Admission is defined by the Merchant generator.

## Shared frontend contract

All normal storefront pages use:
- `styles.css?v=4.5`
- `app.js?v=5.3`
- exactly one `site-menu.css?v=2`
- one global header/navigation.

The sync workflow repairs drift automatically. Catalog safety runs `scripts/audit_static_site.py` and fails on contract violations.

## Legacy URLs

Historical PDP URLs are preserved only as lightweight `noindex` redirect stubs. They must:
- never re-enter sitemap;
- never be linked from primary storefront pages;
- never contain a second copy of live PDP logic.

Mappings live in `scripts/site_contract.py`.

## SEO contract

- Sitemap contains only canonical, indexable public pages.
- Every sitemap URL has one self-canonical.
- Generic `product.html` is `noindex`.
- Draft/hidden Burshtyn remains `noindex` and outside sitemap.
- Product/Offer JSON-LD is normalized at runtime from selected Admin SKU data.

## Media contract

- Google Drive may be a source archive, not the preferred storefront/Merchant delivery layer.
- Merchant images must be first-party `magelle.com.ua` or `api.magelle.com.ua`.
- A design's approved base/source-color gallery must never be deleted, shortened, or replaced by a single image.
- Exact-color images for other colors are separate SKU media.

Media audit closure:
- Sculptural Fold Koral base SND gallery is fully first-party. The four historical Drive URLs were mapped against the already-existing Admin uploads and replaced with exact matching api.magelle.com.ua copies; base gallery count and identity remain unchanged.
- Storefront HTML is CI-blocked if a Google Drive URL reappears.

CSS maintenance:
- 2026-10-20 removed cascade-dead mobile header/PDP/color-control overrides while preserving computed mobile layout; shared stylesheet version advanced to 4.5.

## CI / regression protection

`Catalog safety` checks:
- backend Catalog tests;
- static storefront architecture audit;
- JavaScript syntax.

`Merchant feed sync` independently rebuilds and verifies the production feed against live Admin 2.0.

`Keep MaGelle navigation identical` synchronizes global nav and shared frontend asset versions after storefront changes.

## Base-color gallery marker

Storefront color selectors automatically mark the design source/base color when its approved source gallery has 2+ photos. The marker is derived only from Admin `source_color` + unique `source_photo_urls`: PDP shows “Галерея · N фото”; compact catalog/mobile controls show “N фото”. No per-product manual labels are allowed.
