#!/usr/bin/env python3
"""Verify scalable Merchant admission and exact variant landing contracts."""
import html
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from build_merchant_feed import (
    COLOR_LABELS,
    ORIGINAL_PILOT,
    PINNED,
    SITE,
    acceptable_photo,
    admitted_products,
    availability,
    get_catalog,
    get_products,
    landing_spec,
    ordered_admitted,
)

ROOT = ET.parse("merchant.xml").getroot()
NS = {"g": "http://base.google.com/ns/1.0"}
rows = ROOT.findall("./channel/item")
ids = [row.findtext("g:id", namespaces=NS) for row in rows]
assert len(set(ids)) == len(ids), "Duplicate Merchant SKU"

products = get_products()
catalog = get_catalog()
selected, excluded, routes = admitted_products(products, catalog)
expected_ids = ordered_admitted(selected)
assert ids == expected_ids, (
    "Feed must contain every and only currently admissible managed variant. "
    f"expected={expected_ids!r} actual={ids!r}"
)
assert all(sku in ids for sku in ORIGINAL_PILOT), "Original approved pilot must remain present"

by_sku = {p["sku"]: p for p in products if isinstance(p, dict) and p.get("sku")}
app = Path("app.js").read_text(encoding="utf-8")
for required in (
    "searchParams.get('color')",
    "selectDesignPdp(initial,false",
    "updateExactSchema(variant,code,info)",
    "canonical.href=url.href",
    "requestedColor&&COLORS[requestedColor]",
    "merchant-static-schema')?(info.dataset.defaultColor||d.default_color)",
):
    assert required in app, "Variant deep-link runtime contract missing: " + required

for item in rows:
    sku = item.findtext("g:id", namespaces=NS)
    product = selected[sku]
    landing = landing_spec(sku, product, routes)
    expected_name = "MaGelle " + product["title_ua"]
    expected_price = f"{product['price_uah']:.2f} UAH"
    image = product["photo_urls"][0]

    assert item.findtext("title") == expected_name, sku + ": RSS title != Admin"
    assert item.findtext("link") == landing["url"], sku + ": RSS variant link wrong"
    assert item.findtext("g:color", namespaces=NS) == product["color"], sku + ": RSS color wrong"
    assert item.findtext("g:image_link", namespaces=NS) == image, sku + ": RSS image wrong"
    assert item.findtext("g:item_group_id", namespaces=NS) == product["design_id"], sku + ": RSS group wrong"
    assert item.findtext("g:price", namespaces=NS) == expected_price, sku + ": RSS price wrong"
    assert item.findtext("g:availability", namespaces=NS) == availability(product), sku + ": RSS stock wrong"
    assert item.findtext("g:brand", namespaces=NS) == "MaGelle", sku + ": wrong brand"
    assert item.findtext("g:condition", namespaces=NS) == "new", sku + ": wrong condition"
    assert acceptable_photo(image), sku + ": first image is not first-party exact media"

    page = Path(landing["path"].lstrip("/"))
    assert page.is_file(), sku + ": landing page file missing"
    doc = page.read_text(encoding="utf-8")
    assert not re.search(r'<meta name="robots" content="noindex', doc), sku + ": PDP noindex"

    if not landing["dynamic"]:
        spec = PINNED[sku]
        canonical = landing["url"]
        assert f'<link rel="canonical" href="{canonical}">' in doc, sku + ": pinned canonical wrong"
        assert f'data-selected-sku="{sku}"' in doc, sku + ": pinned initial SKU mismatch"
        assert f'data-default-color="{spec["color_code"]}"' in doc, sku + ": pinned default color mismatch"
        assert f'data-selected-color="{spec["color"]}"' in doc, sku + ": pinned selected color mismatch"

        marker = re.search(
            r'<script id="merchant-static-schema" type="application/ld\+json">([\s\S]*?)</script>',
            doc,
        )
        assert marker, sku + ": pinned Product schema missing"
        schema = json.loads(marker.group(1))
        assert schema.get("@context") == "https://schema.org", sku + ": bad schema context"
        assert schema.get("@type") == "Product", sku + ": not Product schema"
        assert schema.get("sku") == sku, sku + ": schema SKU mismatch"
        assert schema.get("name") == expected_name, sku + ": schema title mismatch"
        assert schema.get("color") == product["color"], sku + ": schema color mismatch"
        assert schema.get("image") == [image], sku + ": schema image mismatch"
        assert schema.get("url") == canonical, sku + ": schema URL mismatch"
        assert schema.get("brand", {}).get("name") == "MaGelle", sku + ": schema brand mismatch"

        offer = schema.get("offers") or {}
        assert offer.get("@type") == "Offer", sku + ": Offer missing"
        assert offer.get("url") == canonical, sku + ": Offer URL mismatch"
        assert offer.get("priceCurrency") == "UAH", sku + ": Offer currency mismatch"
        assert abs(float(offer.get("price") or 0) - float(product["price_uah"])) < 0.005, sku + ": Offer price mismatch"
        assert offer.get("availability") == "https://schema.org/InStock", sku + ": Offer stock mismatch"
        assert offer.get("itemCondition") == "https://schema.org/NewCondition", sku + ": Offer condition missing"

        hero = re.search(r'<img id="product-main-image" src="([^"]+)" alt="([^"]*)"', doc)
        assert hero, sku + ": pinned hero missing"
        assert html.unescape(hero.group(1)) == image, sku + ": pinned hero != image_link"
        assert product["color"] in html.unescape(hero.group(2)), sku + ": pinned hero alt color mismatch"

        og = re.search(r'<meta property="og:image" content="([^"]+)">', doc)
        assert og and html.unescape(og.group(1)) == image, sku + ": pinned OG image mismatch"

        src = re.search(
            r'data-variant-' + product["color_code"].lower() + r'="([^"]+)"',
            doc,
        )
        assert src and html.unescape(src.group(1)) == image, sku + ": pinned picker image mismatch"

        spec_color = re.search(r'<dd id="design-spec-color">([^<]*)</dd>', doc)
        if spec_color:
            assert spec_color.group(1) == product["color"], sku + ": static specs color mismatch"
    else:
        design = landing["design"]
        base_canonical = SITE + landing["path"]
        assert f'<link rel="canonical" href="{base_canonical}">' in doc, sku + ": base PDP canonical wrong"

        info = re.search(r'<div class="product-info[^>]*design-variant-pdp[^>]*>', doc)
        assert info, sku + ": design variant PDP marker missing"
        tag = info.group(0)
        assert f'data-design-code="{design["code"]}"' in tag, sku + ": design code mismatch"
        assert f'data-size-code="{design["size_code"]}"' in tag, sku + ": size code mismatch"
        if 'data-catalog-design-id="' in tag:
            assert f'data-catalog-design-id="{product["design_id"]}"' in tag, sku + ": catalog design id mismatch"
        assert re.search(
            r'data-variant-color="' + re.escape(product["color_code"]) + r'"',
            doc,
        ), sku + ": requested color button missing"
        assert "/app.js?" in doc or 'src="/app.js"' in doc, sku + ": app.js missing"
        assert landing["url"].endswith("?color=" + product["color_code"]), sku + ": deep-link query missing"

    with urlopen(
        Request(image, headers={"User-Agent": "MaGelle-Merchant-Image-QA/3.0"}),
        timeout=35,
    ) as response:
        assert response.status == 200, sku + ": image GET failed"
        mime = response.headers.get_content_type()
        magic = response.read(16)
        assert mime in ("image/png", "image/jpeg", "image/webp"), sku + ": image MIME wrong: " + mime
        assert magic.startswith((b"\x89PNG", b"\xff\xd8\xff", b"RIFF")), sku + ": image URL not image bytes"

    with urlopen(
        Request(landing["url"], headers={"User-Agent": "MaGelle-Merchant-Landing-QA/3.0"}),
        timeout=35,
    ) as response:
        assert response.status == 200, sku + ": landing GET failed"

    print(
        "PASS",
        sku,
        "|",
        product["color"],
        "|",
        product["price_uah"],
        "UAH |",
        landing["url"],
        "|",
        "dynamic" if landing["dynamic"] else "pinned",
    )

reason_counts = {}
for reason in excluded.values():
    reason_counts[reason] = reason_counts.get(reason, 0) + 1

print(
    f"Merchant scalable QA PASS: {len(rows)} admitted exact SKU; "
    f"{len(excluded)} managed variants excluded; reasons={reason_counts}"
)
