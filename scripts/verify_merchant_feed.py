#!/usr/bin/env python3
"""Verify scalable Merchant admission and exact variant landing contracts."""
import html
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from sync_product_seo import product_schema_nodes

from build_merchant_feed import (
    COLOR_LABELS,
    ORIGINAL_PILOT,
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
    "merchant-static-schema')?(info.dataset.defaultColor||d.default_color)",
):
    assert required in app, "Variant deep-link runtime contract missing: " + required

for item in rows:
    sku = item.findtext("g:id", namespaces=NS)
    product = selected[sku]
    landing = landing_spec(sku, product, routes)
    expected_name = "MaGelle " + product["title_ua"]
    expected_price = f"{product['price_uah']:.2f} UAH"
    image = product["_merchant_image"]

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

    schemas = product_schema_nodes(doc)
    assert len(schemas) == 1, sku + ": duplicate/missing product schemas"
    group = schemas[0][1]
    base_canonical = SITE + landing["path"]
    assert group.get("@context") == "https://schema.org", sku + ": bad schema context"
    assert group.get("@type") == "ProductGroup", sku + ": ProductGroup missing"
    assert group.get("@id") == base_canonical + "#product-group", sku + ": group id wrong"
    assert group.get("url") == base_canonical, sku + ": group canonical wrong"
    assert group.get("productGroupID") == product["design_id"], sku + ": group id wrong"
    assert group.get("variesBy") == ["https://schema.org/color"], sku + ": group variesBy wrong"
    variants = [p for p in group.get("hasVariant", []) if p.get("sku") == sku]
    assert len(variants) == 1, sku + ": exact Product variant missing/duplicated"
    schema = variants[0]
    assert schema.get("@type") == "Product", sku + ": variant Product missing"
    assert schema.get("@id") == landing["url"] + "#product", sku + ": variant @id wrong"
    assert schema.get("isVariantOf") == {"@id": group["@id"]}, sku + ": group relationship wrong"
    assert schema.get("name") == expected_name, sku + ": schema title mismatch"
    assert schema.get("color") == product["color"], sku + ": schema color mismatch"
    assert schema.get("image") == [image], sku + ": schema image mismatch"
    assert schema.get("url") == landing["url"], sku + ": schema URL mismatch"
    assert schema.get("brand", {}).get("name") == "MaGelle", sku + ": schema brand mismatch"
    expected_group_skus = {p["sku"] for p in selected.values() if p["design_id"] == product["design_id"]}
    assert {p.get("sku") for p in group.get("hasVariant", [])} == expected_group_skus, sku + ": group SKU set differs from feed"
    offer = schema.get("offers") or {}
    assert offer.get("@type") == "Offer", sku + ": Offer missing"
    assert offer.get("url") == landing["url"], sku + ": Offer URL mismatch"
    assert offer.get("priceCurrency") == "UAH", sku + ": Offer currency mismatch"
    assert abs(float(offer.get("price") or 0) - float(product["price_uah"])) < 0.005, sku + ": Offer price mismatch"
    assert offer.get("availability") == "https://schema.org/InStock", sku + ": Offer stock mismatch"
    assert offer.get("itemCondition") == "https://schema.org/NewCondition", sku + ": Offer condition missing"

    if not landing["dynamic"]:
        canonical = landing["url"]
        base_color = landing["design"]["base_color"]
        assert product["color_code"] == base_color, sku + ": clean landing must be the base color"
        assert f'<link rel="canonical" href="{canonical}">' in doc, sku + ": canonical wrong"
        assert f'data-selected-sku="{sku}"' in doc, sku + ": canonical initial SKU mismatch"
        assert f'data-default-color="{base_color}"' in doc, sku + ": canonical default color mismatch"
        assert f'data-selected-color="{product["color"]}"' in doc, sku + ": canonical selected color mismatch"

        hero = re.search(r'<img\b[^>]*\bid="product-main-image"[^>]*>', doc)
        assert hero, sku + ": canonical hero missing"
        hero_tag = hero.group(0)
        hero_src = re.search(r'\bsrc="([^"]+)"', hero_tag)
        hero_alt = re.search(r'\balt="([^"]*)"', hero_tag)
        assert hero_src, sku + ": canonical hero src missing"
        assert hero_alt, sku + ": canonical hero alt missing"
        assert html.unescape(hero_src.group(1)) == image, sku + ": canonical hero != image_link"
        assert product["color"] in html.unescape(hero_alt.group(1)), sku + ": canonical hero alt color mismatch"

        og = re.search(r'<meta property="og:image" content="([^"]+)">', doc)
        assert og and html.unescape(og.group(1)) == image, sku + ": canonical OG image mismatch"

        src = re.search(
            r'data-variant-' + product["color_code"].lower() + r'="([^"]+)"',
            doc,
        )
        assert src and html.unescape(src.group(1)) == image, sku + ": canonical picker image mismatch"

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

    image_path = urlsplit(image).path
    local_image = Path(image_path.lstrip("/")) if urlsplit(image).netloc == "magelle.com.ua" else None
    if local_image and local_image.is_file():
        magic = local_image.read_bytes()[:16]
        assert magic.startswith((b"\x89PNG", b"\xff\xd8\xff", b"RIFF")), sku + ": local image asset invalid"
    else:
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
        "dynamic" if landing["dynamic"] else "canonical",
    )

reason_counts = {}
for reason in excluded.values():
    reason_counts[reason] = reason_counts.get(reason, 0) + 1

print(
    f"Merchant scalable QA PASS: {len(rows)} admitted exact SKU; "
    f"{len(excluded)} managed variants excluded; reasons={reason_counts}"
)
