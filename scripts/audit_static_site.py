#!/usr/bin/env python3
"""Fail CI when static storefront structure drifts from MaGelle's public contract."""
from pathlib import Path
from urllib.parse import urlsplit
import re
import sys
import xml.etree.ElementTree as ET

from site_contract import (
    APP_VERSION,
    EXPECTED_CATALOG_DESIGNS,
    LEGACY_PATHS,
    LEGACY_REDIRECTS,
    MENU_VERSION,
    SITE_URL,
    STYLE_VERSION,
)

ROOT = Path(".")
errors = []
warnings = []


def fail(message):
    errors.append(message)


def warn(message):
    warnings.append(message)


def canonical_of(raw):
    m = re.findall(r'<link rel="canonical" href="([^"]+)">', raw)
    if len(m) > 1:
        return None, len(m)
    return (m[0] if m else ""), len(m)


def robots_of(raw):
    m = re.search(r'<meta name="robots" content="([^"]+)">', raw)
    return m.group(1).lower() if m else ""


pages = [p for p in ROOT.glob("*.html") if not p.name.startswith("google")]
for page in pages:
    raw = page.read_text(encoding="utf-8")

    styles = re.findall(r'/styles\.css\?v=([^"]+)', raw)
    if len(styles) != 1 or styles[0] != STYLE_VERSION:
        fail(f"{page}: styles.css contract {styles!r}, expected [{STYLE_VERSION!r}]")

    apps = re.findall(r'/app\.js\?v=([^"]+)', raw)
    if apps and (len(apps) != 1 or apps[0] != APP_VERSION):
        fail(f"{page}: app.js contract {apps!r}, expected [{APP_VERSION!r}]")

    has_nav = '<nav class="site-nav" id="nav">' in raw
    if has_nav:
        if raw.count('<header class="site-header"') != 1:
            fail(f"{page}: expected exactly one site header")
        if raw.count('<nav class="site-nav" id="nav">') != 1:
            fail(f"{page}: expected exactly one site nav")
        menu_refs = re.findall(r'/site-menu\.css\?v=([^"]+)', raw)
        if menu_refs != [MENU_VERSION]:
            fail(f"{page}: site-menu.css contract {menu_refs!r}, expected [{MENU_VERSION!r}]")
        if apps != [APP_VERSION]:
            fail(f"{page}: global-nav page must load app.js?v={APP_VERSION}")

    _, canonical_count = canonical_of(raw)
    if canonical_count > 1:
        fail(f"{page}: duplicate canonical tags")

    if raw.count('id="merchant-static-schema"') > 1:
        fail(f"{page}: duplicate merchant-static-schema id")

    if "drive.google.com" in raw:
        fail(f"{page}: Google Drive URL is forbidden in storefront HTML")

    for href in re.findall(r'href="/([^"#?]+\.html)(?:\?[^"]*)?"', raw):
        if not (ROOT / href).is_file():
            fail(f"{page}: broken local HTML link -> /{href}")

# Primary navigation/content must never point buyers back to legacy PDPs.
for name in ("index.html", "catalog.html", "organic-flare.html", "architectural-step.html", "sculptural-fold.html"):
    raw = (ROOT / name).read_text(encoding="utf-8")
    for legacy in sorted(LEGACY_PATHS):
        if f'/{legacy}' in raw:
            fail(f"{name}: primary page links to legacy URL /{legacy}")

# Legacy URLs are compatibility redirects only, never duplicate PDP implementations.
for legacy, spec in LEGACY_REDIRECTS.items():
    raw = (ROOT / legacy).read_text(encoding="utf-8")
    if "noindex" not in robots_of(raw):
        fail(f"{legacy}: legacy page must be noindex")
    refresh = re.search(r'<meta http-equiv="refresh" content="0;url=([^"]+)">', raw, re.I)
    if not refresh or refresh.group(1) != spec["target"]:
        fail(f"{legacy}: redirect target mismatch")
    canonical, count = canonical_of(raw)
    if count != 1 or canonical != spec["canonical"]:
        fail(f"{legacy}: canonical mismatch {canonical!r}")

# Generic dynamic product template must stay out of search.
product = (ROOT / "product.html").read_text(encoding="utf-8")
if "noindex" not in robots_of(product):
    fail("product.html: generic template must be noindex")

# Catalog model count is a public architecture contract.
catalog = (ROOT / "catalog.html").read_text(encoding="utf-8")
cards = re.findall(r'<article class="[^"]*design-variant-card[^"]*"[^>]*>', catalog)
codes = []
for card in cards:
    m = re.search(r'data-design-code="([^"]+)"', card)
    if m:
        codes.append(m.group(1))
if len(cards) != EXPECTED_CATALOG_DESIGNS:
    fail(f"catalog.html: {len(cards)} design cards, expected {EXPECTED_CATALOG_DESIGNS}")
if len(set(codes)) != EXPECTED_CATALOG_DESIGNS:
    fail(f"catalog.html: design codes are not {EXPECTED_CATALOG_DESIGNS} unique values: {codes!r}")

# Sitemap may contain only canonical, indexable, non-legacy HTML.
tree = ET.parse(ROOT / "sitemap.xml")
ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
locs = [n.text.strip() for n in tree.findall(".//s:loc", ns) if n.text]
if len(locs) != len(set(locs)):
    fail("sitemap.xml: duplicate URLs")

for loc in locs:
    parsed = urlsplit(loc)
    if parsed.scheme != "https" or parsed.netloc != "magelle.com.ua":
        fail(f"sitemap.xml: unexpected host/scheme {loc}")
        continue
    rel = parsed.path.lstrip("/") or "index.html"
    if rel in LEGACY_PATHS:
        fail(f"sitemap.xml: legacy URL present {loc}")
    page = ROOT / rel
    if not page.is_file():
        fail(f"sitemap.xml: missing file for {loc}")
        continue
    raw = page.read_text(encoding="utf-8")
    if "noindex" in robots_of(raw):
        fail(f"sitemap.xml: noindex page present {loc}")
    if re.search(r'http-equiv="refresh"', raw, re.I):
        fail(f"sitemap.xml: redirect page present {loc}")
    canonical, count = canonical_of(raw)
    expected = SITE_URL + ("/" if rel == "index.html" else "/" + rel)
    if count != 1 or canonical != expected:
        fail(f"{rel}: sitemap canonical {canonical!r}, expected {expected!r}")

print(f"Static site audit: {len(pages)} HTML pages, {len(locs)} sitemap URLs")
for item in warnings:
    print("WARN:", item)
if errors:
    for item in errors:
        print("ERROR:", item)
    print(f"Static site audit FAILED: {len(errors)} errors, {len(warnings)} warnings")
    sys.exit(1)
print(f"Static site audit PASS: 0 errors, {len(warnings)} warnings")
