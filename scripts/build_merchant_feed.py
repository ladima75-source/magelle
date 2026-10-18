#!/usr/bin/env python3
"""Build MaGelle Google Merchant RSS from live Admin 2.0 catalog data.

Admission is catalog-driven and fail-closed:
- managed design variant only;
- lifecycle=active, status=stock, positive UAH price;
- exact first-party image served by api.magelle.com.ua;
- valid design PDP route from /api/catalog.

The existing 12 published Merchant items keep their established landing URLs.
The original three approved pilot items therefore remain byte-for-byte stable
at the identity/link level while newly eligible variants use ?color=CODE deep
links on the design PDP.
"""
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

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
    "design-AS-VRT-VYR", "design-AS-MON-VYR", "design-AS-CNT-DEL", "design-AS-RIT-DEL",
    "design-SF-KOR-VYR",
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
}

COLOR_LABELS = {
    "GRA": "Графіт",
    "MLK": "Молочний",
    "WHT": "Білий",
    "SND": "Пісочний",
    "CHO": "Шоколад",
}

# Stable landing contracts already published in Merchant Center.
# Keep order so the existing 12 remain first and unchanged in the feed.
PINNED = {
    "MG-OF-MED-VYR-GRA": {"path": "/organic-flare-med-vyraznyi-hrafit.html", "title_ua": "Organic Flare «Мед» — Виразний, Графіт", "color": "Графіт", "color_code": "GRA", "design_id": "design-OF-MED-VYR"},
    "MG-OF-PER-VYR-MLK": {"path": "/organic-flare-vyraznyi-molochnyi.html", "title_ua": "Organic Flare «Перлина» — Виразний, Молочний", "color": "Молочний", "color_code": "MLK", "design_id": "design-OF-PER-VYR"},
    "MG-OF-DIM-VYR-GRA": {"path": "/organic-flare-dym-vyraznyi-hrafit.html", "title_ua": "Organic Flare «Дим» — Виразний, Графіт", "color": "Графіт", "color_code": "GRA", "design_id": "design-OF-DIM-VYR"},
    "MG-AS-VRT-VYR-CHO": {"path": "/architectural-step-vertikal-vyraznyi-shokolad.html", "title_ua": "Architectural Step «Вертикаль» — Виразний, Шоколад", "color": "Шоколад", "color_code": "CHO", "design_id": "design-AS-VRT-VYR"},
    "MG-AS-MON-VYR-CHO": {"path": "/architectural-step-monolit-vyraznyi-shokolad.html", "title_ua": "Architectural Step «Моноліт» — Виразний, Шоколад", "color": "Шоколад", "color_code": "CHO", "design_id": "design-AS-MON-VYR"},
    "MG-AS-CNT-DEL-CHO": {"path": "/architectural-step-kontur-delikatnyi-shokolad.html", "title_ua": "Architectural Step «Контур» — Делікатний, Шоколад", "color": "Шоколад", "color_code": "CHO", "design_id": "design-AS-CNT-DEL"},
    "MG-AS-RIT-DEL-GRA": {"path": "/architectural-step-ritm-delikatnyi-hrafit.html", "title_ua": "Architectural Step «Ритм» — Делікатний, Графіт", "color": "Графіт", "color_code": "GRA", "design_id": "design-AS-RIT-DEL"},
}
RETAINED_BASELINE = ("MG-OF-MED-VYR-GRA", "MG-OF-PER-VYR-MLK")
PINNED_DESIGN_PATH = {spec["design_id"]: spec["path"] for spec in PINNED.values()}


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
        path = safe_pdp_path(design.get("pdp_url"))
        if not path:
            continue
        routes[design["id"]] = {**design, "pdp_path": path}
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
    if sku in PINNED:
        spec = PINNED[sku]
        return {
            "path": spec["path"],
            "url": SITE + spec["path"],
            "dynamic": False,
            "design": routes[product["design_id"]],
        }
    route = routes[product["design_id"]]
    path = PINNED_DESIGN_PATH.get(product["design_id"], route["pdp_path"])
    code = product["color_code"]
    return {
        "path": path,
        "url": SITE + path + "?color=" + code,
        "dynamic": True,
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


def sync_pinned_pdp_schema(products, catalog):
    selected, _, routes = admitted_products(products, catalog)
    for sku, spec in PINNED.items():
        p = selected[sku]
        path = Path(spec["path"].lstrip("/"))
        if not path.is_file():
            raise RuntimeError("Pinned landing page missing: " + spec["path"])
        original = path.read_text(encoding="utf-8")
        body = original
        url = SITE + spec["path"]
        schema_pattern = r'<script id="merchant-static-schema" type="application/ld\+json">[\s\S]*?</script>'
        matches = re.findall(schema_pattern, body)
        if len(matches) > 1:
            raise RuntimeError(sku + ": duplicate static Product JSON-LD")
        if not matches:
            body = body.replace(
                "</head>",
                '<script id="merchant-static-schema" type="application/ld+json">{}</script></head>',
                1,
            )

        for pattern, reason in [
            (r'<link rel="canonical" href="' + re.escape(url) + r'">', "canonical"),
            (r'data-selected-sku="' + re.escape(sku) + r'"', "selected SKU"),
            (r'data-default-color="' + spec["color_code"] + r'"', "default vase color"),
            (r'data-design-gallery', "gallery"),
        ]:
            if not re.search(pattern, body):
                raise RuntimeError(sku + ": landing page has wrong/missing " + reason)

        pic = p["_merchant_image"]
        data = {
            "@context": "https://schema.org",
            "@type": "Product",
            "sku": sku,
            "name": "MaGelle " + p["title_ua"],
            "description": p.get("description_ua")
            or "Інтер’єрна композиція MaGelle із сухоцвітів та стабілізованих рослин.",
            "brand": {"@type": "Brand", "name": "MaGelle"},
            "color": p["color"],
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
        schema = (
            '<script id="merchant-static-schema" type="application/ld+json">'
            + encoded
            + "</script>"
        )
        body = re.sub(schema_pattern, lambda _: schema, body, count=1)

        hero_pattern = r'(<img id="product-main-image" src=")[^"]+(" alt=")[^"]*(")'
        body, count = re.subn(
            hero_pattern,
            lambda m: m.group(1)
            + html.escape(pic, quote=True)
            + m.group(2)
            + html.escape(p["title_ua"] + " — MaGelle", quote=True)
            + m.group(3),
            body,
            count=1,
        )
        if count != 1:
            raise RuntimeError(sku + ": hero image missing")

        attr = "data-variant-" + spec["color_code"].lower()
        if not re.search(attr + r'="[^"]*"', body):
            raise RuntimeError(sku + ": default vase photo map missing")
        body = re.sub(
            attr + r'="[^"]*"',
            lambda _: attr + '="' + html.escape(pic, quote=True) + '"',
            body,
            count=1,
        )

        og_pattern = r'<meta property="og:image" content="[^"]*">'
        og_tag = '<meta property="og:image" content="' + html.escape(pic, quote=True) + '">'
        body = (
            re.sub(og_pattern, lambda _: og_tag, body, count=1)
            if re.search(og_pattern, body)
            else body.replace("</head>", og_tag + "</head>", 1)
        )

        # Keep the non-JS first paint consistent with the pinned Merchant variant.
        body = re.sub(
            r'(<span id="design-pdp-color-label">)[^<]*(</span>)',
            lambda m: m.group(1) + spec["color"] + m.group(2),
            body,
            count=1,
        )
        body = re.sub(
            r'(<dd id="design-spec-color">)[^<]*(</dd>)',
            lambda m: m.group(1) + spec["color"] + m.group(2),
            body,
            count=1,
        )
        body = re.sub(
            r'(<strong id="design-selected-sku">)[^<]*(</strong>)',
            lambda m: m.group(1) + sku + m.group(2),
            body,
            count=1,
        )

        if body != original:
            path.write_text(body, encoding="utf-8")


if __name__ == "__main__":
    source = get_products()
    catalog = get_catalog()
    xml, selected, excluded, _ = build(source, catalog)
    sync_pinned_pdp_schema(source, catalog)
    OUTPUT.write_text(xml + "\n", encoding="utf-8")
    reasons = {}
    for reason in excluded.values():
        reasons[reason] = reasons.get(reason, 0) + 1
    print(
        "Merchant feed: "
        f"{len(selected)} admitted exact SKU; "
        f"{len(excluded)} managed variants excluded; reasons={reasons}"
    )
