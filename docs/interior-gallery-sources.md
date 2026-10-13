# MaGelle — Interior Solutions, source registry (13.10.2026)

Live section: https://magelle.com.ua/#interior

This editorial section uses **existing, already-published Instagram interior visualizations**, not newly generated replacement products. Static WebP media are hosted at `/media/interiors/` and can be displayed without signing into Instagram. Concept renderings are labelled as visualizations; exact product photos and offer data remain on the catalogue / PDP pages.

| Website media | Original MaGelle Instagram carousel |
|---|---|
| organic-graphite-evening.webp | https://www.instagram.com/magelle_flowers/p/DeOcC01CJC7/ |
| organic-milk-soft-light.webp | https://www.instagram.com/magelle_flowers/p/DeOcd4lCFmR/ |
| step-vertical-interior.webp | https://www.instagram.com/magelle_flowers/p/DeOb4xXCIcG/ |
| organic-wine-interior.webp | https://www.instagram.com/magelle_flowers/p/DeOcUXDiGBy/ |
| organic-milk-dining.webp | https://www.instagram.com/magelle_flowers/p/DeOdBZTiNGa/ |
| step-pair-interior.webp | https://www.instagram.com/magelle_flowers/p/DeOcyZoiCNO/ |
| organic-coral-wood.webp | https://www.instagram.com/magelle_flowers/p/DeOcooyiAXQ/ |

An additional Sculptural Fold «Корал» interior source is stored at `/media/koral_interior.webp` (from the MaGelle/KORAL_GALLERY approved interior set).

Header navigation is synchronized from the homepage as a single source of truth on all root storefront HTML pages via `scripts/sync_global_navigation.py` and `.github/workflows/global-menu.yml`:
**Головна → Каталог → Інтер'єрні рішення → Про бренд → Доставка → Оплата → Контакти**.
Responsive desktop adjustments use `/site-menu.css`.

On publication, verify links, 8 visualizations, no unexpected clipping/overflow and identical navigation on /catalog.html, /organic-flare.html, /payment.html, /checkout.html and representative PDPs.
