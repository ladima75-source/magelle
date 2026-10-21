#!/usr/bin/env python3
"""Build MaGelle Google Merchant RSS from live Admin 2.0 catalog data.

Admission is catalog-driven and fail-closed:
- managed design variant only;
- lifecycle=active, status=stock, positive UAH price;
- exact first-party image served by api.magelle.com.ua;
- valid design PDP route from /api/catalog.

Every design lands on its single base-color canonical PDP. Non-base variants use
?color=CODE deep links on that PDP. Merchant generation never rewrites storefront HTML.
"""
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from site_contract import CANONICAL_DESIGNS

PRODUCTS_SOURCE = os.environ.get(
    "MAGELLE_PRODUCTS_API", "https://api.magelle.com.ua/api/products"
)
CATALOG_SOURCE = os.environ.get(
    "MAGELLE_CATALOG_API", "https://api.magelle.com.ua/api/catalog"
)
OUTPUT = Path(os.environ.get("MAGELLE_MERCHANT_FEED", "merchant.xml"))
SITE = "https://magelle.com.ua"
G = "http://base.google.com/ns/1.0"
ET.register_namespace("g", G)

SELLABLE_DESIGNS = {
    "design-OF-MED-VYR", "design-OF-PER-VYR", "design-OF-KAR-VYR", "design-OF-GNT-VYR", "design-OF-DIM-VYR",
    "design-OF-BOR-DEL", "design-OF-TER-DEL", "design-OF-LON-DEL", "design-OF-PUD-DEL", "design-OF-OLI-DEL",
    "design-AS-VRT-VYR", "design-AS-MON-VYR", "design-AS-CNT-DEL", "design-AS-RIT-DEL",
    "design-SF-KOR-VYR", "design-SF-BUR-VYR",
}
EXACT_IMAGE_OVERRIDES = {
    "MG-OF-PER-VYR-GRA": SITE + "/media/exact/MG-OF-PER-VYR-GRA.webp",
    "MG-OF-PER-VYR-WHT": SITE + "/media/exact/MG-OF-PER-VYR-WHT.webp",
    "MG-OF-PER-VYR-SND": SITE + "/media/exact/MG-OF-PER-VYR-SND.webp",
    "MG-OF-PER-VYR-CHO": SITE + "/media/exact/MG-OF-PER-VYR-CHO.webp",
    "MG-OF-GNT-VYR-MLK": SITE + "/media/exact/MG-OF-GNT-VYR-MLK.webp",
    "MG-OF-GNT-VYR-WHT": SITE + "/media/exact/MG-OF-GNT-VYR-WHT.webp",
    "MG-OF-GNT-VYR-SND": SITE + "/media/exact/MG-OF-GNT-VYR-SND.webp",
    "MG-OF-GNT-VYR-CHO": SITE + "/media/exact/MG-OF-GNT-VYR-CHO.webp",
    "MG-SF-BUR-VYR-CHO": SITE + "/media/burshtyn-cho/MG-SF-BUR-VYR-CHO_01_MAIN-w1600.webp",
}

COLOR_LABELS = {
    "GRA": "Графіт",
    "MLK": "Молочний",
    "WHT": "Білий",
    "SND": "Пісочний",
    "CHO": "Шоколад",
}

# Historical pilot SKU order is kept stable in the feed.
# URL routing no longer comes from these historical pins: every design uses
# its single canonical base-color PDP from site_contract.CANONICAL_DESIGNS.
PINNED = {
    "MG-OF-MED-VYR-GRA": {"path": "/organic-flare-med-vyraznyi-hrafit.html", "title_ua": "Organic Flare «Мед» — Виразний, Графіт", "color": "Графіт", "color_code": "GRA", "design_id": "design-OF-MED-VYR"},
    "MG-OF-PER-VYR-MLK": {"path": "/organic-flare-vyraznyi-molochnyi.html", "title_ua": "Organic Flare «Перлина» — Виразний, Молочний", "color": "Молочний", "color_code": "MLK", "design_id": "design-OF-PER-VYR"},
    "MG-OF-OLI-DEL-CHO": {"path": "/organic-flare-delikatnyi-shokolad.html", "title_ua": "Organic Flare «Олива» — Делікатний, Шоколад", "color": "Шоколад", "color_code": "CHO", "design_id": "design-OF-OLI-DEL"},
    "MG-OF-DIM-VYR-GRA": {"path": "/organic-flare-dym-vyraznyi-hrafit.html", "title_ua": "Organic Flare «Дим» — Виразний, Графіт", "color": "Графіт", "color_code": "GRA", "design_id": "design-OF-DIM-VYR"},
    "MG-OF-BOR-DEL-CHO": {"path": "/organic-flare-bordo-delikatnyi-shokolad.html", "title_ua": "Organic Flare «Бордо» — Делікатний, Шоколад", "color": "Шоколад", "color_code": "CHO", "design_id": "design-OF-BOR-DEL"},
    "MG-OF-TER-DEL-GRA": {"path": "/organic-flare-tera-delikatnyi-hrafit.html", "title_ua": "Organic Flare «Тера» — Делікатний, Графіт", "color": "Графіт", "color_code": "GRA", "design_id": "design-OF-TER-DEL"},
    "MG-OF-LON-DEL-GRA": {"path": "/organic-flare-lon-delikatnyi-hrafit.html", "title_ua": "Organic Flare «Льон» — Делікатний, Графіт", "color": "Графіт", "color_code": "GRA", "design_id": "design-OF-LON-DEL"},
    "MG-OF-PUD-DEL-GRA": {"path": "/organic-flare-pudra-delikatnyi-hrafit.html", "title_ua": "Organic Flare «Пудра» — Делікатний, Графіт", "color": "Графіт", "color_code": "GRA", "design_id": "design-OF-PUD-DEL"},
    "MG-AS-VRT-VYR-CHO": {"path": "/architectural-step-vertikal-vyraznyi-shokolad.html", "title_ua": "Architectural Step «Вертикаль» — Виразний, Шоколад", "color": "Шоколад", "color_code": "CHO", "design_id": "design-AS-VRT-VYR"},
    "MG-AS-MON-VYR-CHO": {"path": "/architectural-step-monolit-vyraznyi-shokolad.html", "title_ua": "Architectural Step «Моноліт» — Виразний, Шоколад", "color": "Шоколад", "color_code": "CHO", "design_id": "design-AS-MON-VYR"},
    "MG-AS-CNT-DEL-CHO": {"path": "/architectural-step-kontur-delikatnyi-shokolad.html", "title_ua": "Architectural Step «Контур» — Делікатний, Шоколад", "color": "Шоколад", "color_code": "CHO", "design_id": "design-AS-CNT-DEL"},
    "MG-AS-RIT-DEL-GRA": {"path": "/architectural-step-ritm-delikatnyi-hrafit.html", "title_ua": "Architectural Step «Ритм» — Делікатний, Графіт", "color": "Графіт", "color_code": "GRA", "design_id": "design-AS-RIT-DEL"},
}
ORIGINAL_PILOT = ("MG-OF-MED-VYR-GRA", "MG-OF-PER-VYR-MLK", "MG-OF-OLI-DEL-CHO")


def get_json(url, agent):
    with urlopen(
        Request(url, headers={"User-Agent": agent, "Accept": "application/json"}),
        timeout=35,
    ) as response:
        value = json.load(response)
    return value


def get_products():
    result = get_json(PRODUCTS_SOURCE, "MaGelle-Merchant-Feed/3.0")
    if not isinstance(result, list):
        raise ValueError("Admin products response must be a JSON array")
    return result


def get_catalog():
    result = get_json(CATALOG_SOURCE, "MaGelle-Merchant-Catalog/3.0")
    if not isinstance(result, dict) or not result.get("enabled"):
        raise ValueError("Catalog Management 2.0 response is not enabled")
    if not isinstance(result.get("designs"), list):
        raise ValueError("Catalog response must contain designs")
    return result


def acceptable_photo(url):
    if not isinstance(url, str) or not url:
        return False
    p = urlsplit(url)
    return (p.scheme == "https" and p.netloc in ("api.magelle.com.ua", "magelle.com.ua")
            and p.path.startswith(("/uploads/", "/media/"))
            and p.path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))

def optimized_drive_map():
    path = Path("media/optimized-image-map.js")
    if not path.is_file(): return {}
    m = re.search(r"=\s*(\{.*\})\s*;?\s*$", path.read_text(encoding="utf-8"), re.S)
    return json.loads(m.group(1)) if m else {}

OPTIMIZED_DRIVE = optimized_drive_map()

def merchant_image(product):
    sku = product.get("sku")
    if sku in EXACT_IMAGE_OVERRIDES:
        url = EXACT_IMAGE_OVERRIDES[sku]
        return url if Path(urlsplit(url).path.lstrip("/")).is_file() else None
    for url in product.get("photo_urls") or []:
        if acceptable_photo(url): return url
        parsed=urlsplit(url)
        if parsed.netloc=="drive.google.com":
            from urllib.parse import parse_qs
            fid=parse_qs(parsed.query).get("id",[""])[0]
            rel=(OPTIMIZED_DRIVE.get(fid) or {}).get("1600")
            if rel and Path(rel.lstrip("/")).is_file(): return SITE+rel
        if isinstance(url,str) and url.startswith("/media/") and Path(url.lstrip("/")).is_file(): return SITE+url
    return None


def safe_pdp_path(value):
    if not isinstance(value, str) or not value:
        return None
    p = urlsplit(value)
    if p.scheme or p.netloc or p.query or p.fragment:
        return None
    path = p.path
    if not path.startswith("/") or ".." in path or not path.endswith(".html"):
        return None
    return path


def design_routes(catalog):
    routes = {}
    for design in catalog["designs"]:
        if not isinstance(design, dict) or not design.get("id"):
            continue
        contract = CANONICAL_DESIGNS.get(design["id"])
        if not contract:
            continue
        path = safe_pdp_path(contract.get("path"))
        if not path:
            continue
        routes[design["id"]] = {
            **design,
            "pdp_path": path,
            "base_color": contract["base_color"],
        }
    return routes


def index_products(products):
    by_sku = {}
    for product in products:
        if not isinstance(product, dict) or not product.get("sku"):
            continue
        if product["sku"] in by_sku:
            raise ValueError("Duplicate SKU in Admin 2.0: " + product["sku"])
        by_sku[product["sku"]] = product
    return by_sku


def rejection_reason(product, routes):
    if not product.get("design_id"):
        return "legacy_without_design_id"
    if product.get("design_id") not in SELLABLE_DESIGNS:
        return "design_not_sellable"
    if product.get("lifecycle") != "active":
        return "lifecycle_not_active"
    if product.get("status") != "stock":
        return "status_not_stock"
    price = product.get("price_uah")
    if isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
        return "missing_positive_price"
    code = product.get("color_code")
    if code not in COLOR_LABELS:
        return "unsupported_color_code"
    if product.get("color") != COLOR_LABELS[code]:
        return "color_label_mismatch"
    photos = product.get("photo_urls")
    image = merchant_image(product)
    if not image:
        return "exact_photo_missing" if not photos and product.get("sku") not in EXACT_IMAGE_OVERRIDES else "first_party_photo_missing"
    route = routes.get(product["design_id"])
    if not route:
        return "design_pdp_route_missing"
    if not Path(route["pdp_path"].lstrip("/")).is_file():
        return "design_pdp_file_missing"
    return None


def admitted_products(products, catalog):
    by_sku = index_products(products)
    routes = design_routes(catalog)
    selected = {}
    excluded = {}
    for sku, product in by_sku.items():
        if not product.get("design_id"):
            continue
        reason = rejection_reason(product, routes)
        if reason:
            excluded[sku] = reason
        else:
            selected[sku] = dict(product)
            selected[sku]["_merchant_image"] = merchant_image(product)

    for sku, spec in PINNED.items():
        product = by_sku.get(sku)
        if not product:
            raise ValueError("Pinned Merchant SKU missing in Admin 2.0: " + sku)
        if sku not in selected:
            raise ValueError(f"Pinned Merchant SKU is no longer admissible: {sku}: {excluded.get(sku)}")
        for field in ("title_ua", "color", "color_code", "design_id"):
            if product.get(field) != spec[field]:
                raise ValueError(
                    f"{sku}: {field} mismatch: Admin {product.get(field)!r}, pinned {spec[field]!r}"
                )
    return selected, excluded, routes


def landing_spec(sku, product, routes):
    route = routes[product["design_id"]]
    path = route["pdp_path"]
    code = product["color_code"]
    dynamic = code != route["base_color"]
    return {
        "path": path,
        "url": SITE + path + (("?color=" + code) if dynamic else ""),
        "dynamic": dynamic,
        "design": route,
    }


def availability(product):
    return "in_stock"


def add_text(parent, tag, value):
    ET.SubElement(parent, tag).text = str(value)


def add_google(parent, tag, value):
    add_text(parent, "{%s}%s" % (G, tag), value)


def ordered_admitted(selected):
    pinned = [sku for sku in PINNED if sku in selected]
    rest = sorted(
        (sku for sku in selected if sku not in PINNED),
        key=lambda sku: (selected[sku].get("sort_order", 999999), sku),
    )
    return pinned + rest


def build(products, catalog):
    selected, excluded, routes = admitted_products(products, catalog)
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    add_text(channel, "title", "MaGelle — товарний фід")
    add_text(channel, "link", SITE + "/")
    add_text(channel, "description", "Підтверджені exact-SKU MaGelle з Catalog Management 2.0")

    for sku in ordered_admitted(selected):
        p = selected[sku]
        landing = landing_spec(sku, p, routes)
        item = ET.SubElement(channel, "item")
        add_google(item, "id", sku)
        add_text(item, "title", "MaGelle " + p["title_ua"])
        add_text(
            item,
            "description",
            p.get("description_ua")
            or "Інтер’єрна композиція із сухоцвітів та стабілізованих рослин у дизайнерській вазі MaGelle.",
        )
        add_text(item, "link", landing["url"])
        add_google(item, "image_link", p["_merchant_image"])
        add_google(item, "availability", availability(p))
        add_google(item, "price", f"{p['price_uah']:.2f} UAH")
        add_google(item, "condition", "new")
        add_google(item, "brand", "MaGelle")
        add_google(item, "identifier_exists", "no")
        add_google(item, "color", p["color"])
        add_google(item, "item_group_id", p["design_id"])

    ET.indent(rss, space="  ")
    return (
        ET.tostring(rss, encoding="unicode", xml_declaration=True),
        selected,
        excluded,
        routes,
    )


def sync_canonical_pdp_schema(products, catalog):
    selected, _, routes = admitted_products(products, catalog)
    for design_id, route in routes.items():
        base_color = route["base_color"]
        candidates = [
            p for p in selected.values()
            if p.get("design_id") == design_id and p.get("color_code") == base_color
        ]
        if not candidates:
            # Media-gap designs (currently Karamel) intentionally have no Product schema.
            continue
        if len(candidates) != 1:
            raise RuntimeError(design_id + ": expected one canonical base variant")
        p = candidates[0]
        sku = p["sku"]
        path = Path(route["pdp_path"].lstrip("/"))
        if not path.is_file():
            raise RuntimeError("Canonical landing page missing: " + route["pdp_path"])
        original = path.read_text(encoding="utf-8")
        body = original
        url = SITE + route["pdp_path"]
        color = p["color"]

        if re.search(r'<meta name="robots" content="noindex', body):
            raise RuntimeError(sku + ": canonical PDP is noindex")
        body, count = re.subn(
            r'<link rel="canonical" href="[^"]+">',
            '<link rel="canonical" href="' + url + '">',
            body,
            count=1,
        )
        if count != 1:
            raise RuntimeError(sku + ": canonical tag missing")
        if 'data-design-gallery' not in body:
            raise RuntimeError(sku + ": gallery missing")

        def set_data(name, value):
            nonlocal body
            pattern = r'data-' + re.escape(name) + r'="[^"]*"'
            repl = 'data-' + name + '="' + html.escape(str(value), quote=True) + '"'
            if re.search(pattern, body):
                body = re.sub(pattern, lambda _: repl, body, count=1)
            else:
                marker = '<div class="product-info sku-pdp design-variant-pdp"'
                if marker not in body:
                    raise RuntimeError(sku + ": PDP info block missing")
                body = body.replace(marker, marker + ' ' + repl, 1)

        set_data("default-color", base_color)
        set_data("selected-sku", sku)
        set_data("selected-base-sku", sku)
        set_data("selected-color", color)
        set_data("catalog-design-id", design_id)
        set_data("variant-" + base_color.lower(), p["_merchant_image"])
        body = re.sub(
            r'(data-design-gallery[^>]*data-photo-color=")[^"]*(")',
            lambda m: m.group(1) + base_color + m.group(2),
            body,
            count=1,
        )

        pic = p["_merchant_image"]
        data = {
            "@context": "https://schema.org",
            "@type": "Product",
            "sku": sku,
            "name": "MaGelle " + p["title_ua"],
            "description": p.get("description_ua")
            or "Інтер’єрна композиція MaGelle із сухоцвітів та стабілізованих рослин.",
            "brand": {"@type": "Brand", "name": "MaGelle"},
            "color": color,
            "image": [pic],
            "url": url,
            "offers": {
                "@type": "Offer",
                "url": url,
                "price": p["price_uah"],
                "priceCurrency": "UAH",
                "availability": "https://schema.org/InStock",
                "itemCondition": "https://schema.org/NewCondition",
            },
        }
        encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
        schema = '<script id="merchant-static-schema" type="application/ld+json">' + encoded + "</script>"
        schema_pattern = r'<script id="merchant-static-schema" type="application/ld\+json">[\s\S]*?</script>'
        if re.search(schema_pattern, body):
            body = re.sub(schema_pattern, lambda _: schema, body, count=1)
        else:
            body = body.replace("</head>", schema + "</head>", 1)

        hero_pattern = r'(<img id="product-main-image" src=")[^"]+(" alt=")[^"]*(")'
        body, count = re.subn(
            hero_pattern,
            lambda m: m.group(1) + html.escape(pic, quote=True) + m.group(2)
            + html.escape(p["title_ua"] + " — MaGelle", quote=True) + m.group(3),
            body,
            count=1,
        )
        if count != 1:
            raise RuntimeError(sku + ": hero image missing")

        def set_og(prop, value):
            nonlocal body
            pattern = r'<meta property="' + re.escape(prop) + r'" content="[^"]+">'
            tag = '<meta property="' + prop + '" content="' + html.escape(value, quote=True) + '">'
            if re.search(pattern, body):
                body = re.sub(pattern, lambda _: tag, body, count=1)
            else:
                body = body.replace("</head>", tag + "</head>", 1)

        set_og("og:image", pic)
        set_og("og:url", url)

        body = re.sub(
            r'(<span id="design-pdp-color-label">)[^<]*(</span>)',
            lambda m: m.group(1) + color + m.group(2), body, count=1)
        body = re.sub(
            r'(<dd id="design-spec-color">)[^<]*(</dd>)',
            lambda m: m.group(1) + color + m.group(2), body, count=1)
        body = re.sub(
            r'(<strong id="design-selected-sku">)[^<]*(</strong>)',
            lambda m: m.group(1) + sku + m.group(2), body, count=1)

        if body != original:
            path.write_text(body, encoding="utf-8")


if __name__ == "__main__":
    source = get_products()
    catalog = get_catalog()
    xml, selected, excluded, _ = build(source, catalog)
    # Merchant sync is read-only with respect to storefront HTML.
    # Canonical PDP identity is owned by site_contract + static CI.
    OUTPUT.write_text(xml + "\n", encoding="utf-8")
    reasons = {}
    for reason in excluded.values():
        reasons[reason] = reasons.get(reason, 0) + 1
    print(
        "Merchant feed: "
        f"{len(selected)} admitted exact SKU; "
        f"{len(excluded)} managed variants excluded; reasons={reasons}"
    )
