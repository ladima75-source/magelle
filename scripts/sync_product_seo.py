#!/usr/bin/env python3
"""Keep single-page ProductGroup markup aligned with the exact-SKU Merchant feed.

The feed supplies reviewed SKU media and commerce data. This script never changes
product identities, galleries, titles, canonical links, or the catalog database.
"""
import argparse
import html
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from site_contract import CANONICAL_DESIGNS, SITE_URL

NS = {"g": "http://base.google.com/ns/1.0"}
SCHEMA_PATTERN = re.compile(
    r'<script\b(?=[^>]*\btype=["\']application/ld\+json["\'])[^>]*>([\s\S]*?)</script>',
    re.I,
)


def feed_groups(path=Path("merchant.xml")):
    groups = {}
    seen = set()
    for item in ET.parse(path).getroot().findall("./channel/item"):
        def field(name):
            return item.findtext(name, default="", namespaces=NS)
        sku = field("g:id")
        design_id = field("g:item_group_id")
        if not sku or sku in seen:
            raise ValueError("Missing or duplicate feed SKU: " + sku)
        seen.add(sku)
        spec = CANONICAL_DESIGNS.get(design_id)
        if not spec:
            raise ValueError("Feed design has no canonical contract: " + design_id)
        url = field("link")
        color_code = sku.rsplit("-", 1)[-1]
        expected_url = SITE_URL + spec["path"]
        if color_code != spec["base_color"]:
            expected_url += "?color=" + color_code
        if url != expected_url:
            raise ValueError(sku + ": feed URL differs from exact canonical/color landing")
        price, currency = field("g:price").split()
        stock = {
            "in_stock": "InStock", "out_of_stock": "OutOfStock",
            "preorder": "PreOrder", "backorder": "BackOrder",
        }.get(field("g:availability"))
        if not stock or currency != "UAH" or float(price) <= 0:
            raise ValueError(sku + ": invalid price/currency/availability")
        product = {
            "@type": "Product", "@id": url + "#product", "sku": sku,
            "isVariantOf": {"@id": SITE_URL + spec["path"] + "#product-group"},
            "name": field("title"), "description": field("description"),
            "brand": {"@type": "Brand", "name": field("g:brand")},
            "color": field("g:color"), "image": [field("g:image_link")], "url": url,
            "offers": {
                "@type": "Offer", "url": url, "price": float(price),
                "priceCurrency": currency,
                "availability": "https://schema.org/" + stock,
                "itemCondition": "https://schema.org/NewCondition",
            },
        }
        groups.setdefault(design_id, []).append(product)
    return groups


def product_schema_nodes(raw):
    """Return top-level product schemas; malformed JSON fails closed."""
    found = []
    for match in SCHEMA_PATTERN.finditer(raw):
        value = json.loads(match.group(1))
        nodes = value if isinstance(value, list) else value.get("@graph", [value])
        if any(node.get("@type") in ("Product", "ProductGroup") for node in nodes):
            found.append((match, value))
    return found


def build_group(design_id, raw, variants):
    spec = CANONICAL_DESIGNS[design_id]
    canonical = SITE_URL + spec["path"]
    canonicals = re.findall(r'<link rel="canonical" href="([^"]+)">', raw)
    if canonicals != [canonical]:
        raise ValueError(design_id + ": HTML canonical differs from clean design contract")
    info = re.search(r'<div class="product-info[^>]*design-variant-pdp[^>]*>', raw)
    if not info:
        raise ValueError(design_id + ": product info missing")
    def attr(name):
        match = re.search(r'data-' + re.escape(name) + r'="([^"]*)"', info.group(0))
        return html.unescape(match.group(1)) if match else ""
    description = re.search(r'<p class="product-description">([\s\S]*?)</p>', raw)
    description = html.unescape(re.sub(r'<[^>]+>', '', description.group(1))).strip() if description else ""
    return {
        "@context": "https://schema.org", "@type": "ProductGroup",
        "@id": canonical + "#product-group", "url": canonical,
        "name": f'MaGelle {attr("family")} «{attr("design")}» — {attr("variant-size")}',
        "description": description, "brand": {"@type": "Brand", "name": "MaGelle"},
        "productGroupID": design_id, "variesBy": ["https://schema.org/color"],
        "hasVariant": variants,
    }


def render_schema(group):
    encoded = json.dumps(group, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return '<script id="merchant-static-schema" type="application/ld+json">' + encoded + '</script>'


def sync(check=False):
    groups = feed_groups()
    changed = []
    for design_id, spec in CANONICAL_DESIGNS.items():
        variants = groups.get(design_id, [])
        path = Path(spec["path"].lstrip("/"))
        raw = path.read_text(encoding="utf-8")
        product_matches = [match.span() for match, _ in product_schema_nodes(raw)]
        replacement = render_schema(build_group(design_id, raw, variants)) if variants else ""
        # Preserve the first product script's position so global navigation sync
        # can independently normalize the end of <head> without perpetual drift.
        body = SCHEMA_PATTERN.sub(
            lambda match: (replacement if match.span() == product_matches[0] else "")
            if match.span() in product_matches else match.group(0), raw,
        ) if product_matches else raw.replace("</head>", replacement + "</head>", 1)
        if body != raw:
            changed.append(path.name)
            if not check:
                path.write_text(body, encoding="utf-8")
    print(f"Product SEO {'check' if check else 'sync'}: {len(groups)} groups, "
          f"{sum(map(len, groups.values()))} exact variants, {len(changed)} changed pages")
    if check and changed:
        raise SystemExit("Stale ProductGroup markup: " + ", ".join(changed))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail on stale markup without writing files")
    sync(parser.parse_args().check)
