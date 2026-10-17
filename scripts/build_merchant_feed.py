#!/usr/bin/env python3
"""Build the existing MaGelle Google Merchant RSS using Admin 2.0 exact SKU data.

The Merchant set is a controlled exact-SKU identity contract (SKU, name,
size, vase color, canonical PDP). The original three approved pilot items
remain unchanged; additional items are admitted only after exact-photo/PDP
preflight. Image, price and availability come from live Admin 2.0. Any
mismatch FAILS publishing instead of silently swapping compositions, colors
or dropping a product from the feed.
"""
import html
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

SOURCE = os.environ.get('MAGELLE_PRODUCTS_API', 'https://api.magelle.com.ua/api/products')
OUTPUT = Path(os.environ.get('MAGELLE_MERCHANT_FEED', 'merchant.xml'))
SITE = 'https://magelle.com.ua'
G = 'http://base.google.com/ns/1.0'
ET.register_namespace('g', G)

APPROVED = {
    'MG-OF-MED-VYR-GRA': {
        'path': '/organic-flare-med-vyraznyi-hrafit.html',
        'title_ua': 'Organic Flare «Мед» — Виразний, Графіт',
        'color': 'Графіт', 'color_code': 'GRA', 'design_id': 'design-OF-MED-VYR',
    },
    'MG-OF-PER-VYR-MLK': {
        'path': '/organic-flare-vyraznyi-molochnyi.html',
        'title_ua': 'Organic Flare «Перлина» — Виразний, Молочний',
        'color': 'Молочний', 'color_code': 'MLK', 'design_id': 'design-OF-PER-VYR',
    },
    'MG-OF-OLI-DEL-CHO': {
        'path': '/organic-flare-delikatnyi-shokolad.html',
        'title_ua': 'Organic Flare «Олива» — Делікатний, Шоколад',
        'color': 'Шоколад', 'color_code': 'CHO', 'design_id': 'design-OF-OLI-DEL',
    },
    'MG-OF-DIM-VYR-GRA': {
        'path': '/organic-flare-dym-vyraznyi-hrafit.html',
        'title_ua': 'Organic Flare «Дим» — Виразний, Графіт',
        'color': 'Графіт', 'color_code': 'GRA', 'design_id': 'design-OF-DIM-VYR',
    },
    'MG-OF-BOR-DEL-CHO': {
        'path': '/organic-flare-bordo-delikatnyi-shokolad.html',
        'title_ua': 'Organic Flare «Бордо» — Делікатний, Шоколад',
        'color': 'Шоколад', 'color_code': 'CHO', 'design_id': 'design-OF-BOR-DEL',
    },
    'MG-OF-TER-DEL-GRA': {
        'path': '/organic-flare-tera-delikatnyi-hrafit.html',
        'title_ua': 'Organic Flare «Тера» — Делікатний, Графіт',
        'color': 'Графіт', 'color_code': 'GRA', 'design_id': 'design-OF-TER-DEL',
    },
    'MG-OF-LON-DEL-GRA': {
        'path': '/organic-flare-lon-delikatnyi-hrafit.html',
        'title_ua': 'Organic Flare «Льон» — Делікатний, Графіт',
        'color': 'Графіт', 'color_code': 'GRA', 'design_id': 'design-OF-LON-DEL',
    },
    'MG-OF-PUD-DEL-GRA': {
        'path': '/organic-flare-pudra-delikatnyi-hrafit.html',
        'title_ua': 'Organic Flare «Пудра» — Делікатний, Графіт',
        'color': 'Графіт', 'color_code': 'GRA', 'design_id': 'design-OF-PUD-DEL',
    },
    'MG-AS-VRT-VYR-CHO': {
        'path': '/architectural-step-vertikal-vyraznyi-shokolad.html',
        'title_ua': 'Architectural Step «Вертикаль» — Виразний, Шоколад',
        'color': 'Шоколад', 'color_code': 'CHO', 'design_id': 'design-AS-VRT-VYR',
    },
    'MG-AS-MON-VYR-CHO': {
        'path': '/architectural-step-monolit-vyraznyi-shokolad.html',
        'title_ua': 'Architectural Step «Моноліт» — Виразний, Шоколад',
        'color': 'Шоколад', 'color_code': 'CHO', 'design_id': 'design-AS-MON-VYR',
    },
    'MG-AS-CNT-DEL-CHO': {
        'path': '/architectural-step-kontur-delikatnyi-shokolad.html',
        'title_ua': 'Architectural Step «Контур» — Делікатний, Шоколад',
        'color': 'Шоколад', 'color_code': 'CHO', 'design_id': 'design-AS-CNT-DEL',
    },
    'MG-AS-RIT-DEL-GRA': {
        'path': '/architectural-step-ritm-delikatnyi-hrafit.html',
        'title_ua': 'Architectural Step «Ритм» — Делікатний, Графіт',
        'color': 'Графіт', 'color_code': 'GRA', 'design_id': 'design-AS-RIT-DEL',
    },
}


def get_products():
    with urlopen(Request(SOURCE, headers={'User-Agent': 'MaGelle-Merchant-Feed/2.0',
                                           'Accept': 'application/json'}), timeout=30) as response:
        result = json.load(response)
    if not isinstance(result, list):
        raise ValueError('Admin products response must be a JSON array')
    return result


def acceptable_photo(url):
    if not isinstance(url, str) or not url:
        return False
    p = urlsplit(url)
    return (p.scheme == 'https'
            and p.netloc == 'api.magelle.com.ua'
            and (p.path.startswith('/uploads/') or p.path.startswith('/media/'))
            and p.path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')))


def validated_products(products):
    by_sku = {}
    for product in products:
        if isinstance(product, dict) and product.get('sku'):
            if product['sku'] in by_sku:
                raise ValueError('Duplicate SKU in Admin 2.0: ' + product['sku'])
            by_sku[product['sku']] = product
    selected = {}
    for sku, spec in APPROVED.items():
        p = by_sku.get(sku)
        if not p:
            raise ValueError('Approved Merchant SKU missing in Admin 2.0: ' + sku)
        for field in ('title_ua', 'color', 'color_code', 'design_id'):
            if p.get(field) != spec[field]:
                raise ValueError(f'{sku}: {field} mismatch: Admin {p.get(field)!r}, approved {spec[field]!r}')
        if p.get('lifecycle') not in ('active', None):
            raise ValueError(sku + ': lifecycle not active')
        if p.get('status') not in ('stock', 'preorder', 'hidden'):
            raise ValueError(sku + ': unsupported stock status')
        if isinstance(p.get('price_uah'), bool) or not isinstance(p.get('price_uah'), (int, float)) or p['price_uah'] <= 0:
            raise ValueError(sku + ': missing positive price')
        photos = p.get('photo_urls')
        if not isinstance(photos, list) or not photos or not acceptable_photo(photos[0]):
            raise ValueError(sku + ': exact first-party photo missing')
        selected[sku] = p
    return selected


def availability(product):
    # "preorder" has no reliable availability date in the Admin API; do not
    # send Google's preorder/backorder attribute without one.
    return 'in_stock' if product['status'] == 'stock' else 'out_of_stock'


def add_text(parent, tag, value):
    ET.SubElement(parent, tag).text = str(value)


def add_google(parent, tag, value):
    add_text(parent, '{%s}%s' % (G, tag), value)


def build(products):
    chosen = validated_products(products)
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')
    add_text(channel, 'title', 'MaGelle — товарний фід')
    add_text(channel, 'link', SITE + '/')
    add_text(channel, 'description', 'Підтверджені SKU MaGelle з Admin 2.0')
    for sku, spec in APPROVED.items():
        p = chosen[sku]
        item = ET.SubElement(channel, 'item')
        add_google(item, 'id', sku)
        add_text(item, 'title', 'MaGelle ' + p['title_ua'])
        add_text(item, 'description', p.get('description_ua') or 'Інтер’єрна композиція із сухоцвітів та стабілізованих рослин у дизайнерській вазі MaGelle.')
        add_text(item, 'link', SITE + spec['path'])
        add_google(item, 'image_link', p['photo_urls'][0])
        add_google(item, 'availability', availability(p))
        add_google(item, 'price', f"{p['price_uah']:.2f} UAH")
        add_google(item, 'condition', 'new')
        add_google(item, 'brand', 'MaGelle')
        add_google(item, 'identifier_exists', 'no')
        add_google(item, 'color', p['color'])
        add_google(item, 'item_group_id', p['design_id'])
    ET.indent(rss, space='  ')
    return ET.tostring(rss, encoding='unicode', xml_declaration=True), len(chosen)


def sync_pdp_schema(products):
    chosen = validated_products(products)
    for sku, spec in APPROVED.items():
        p = chosen[sku]
        path = Path(spec['path'].lstrip('/'))
        if not path.is_file():
            raise RuntimeError('Approved landing page missing: ' + spec['path'])
        body = path.read_text(encoding='utf-8')
        url = SITE + spec['path']
        schema_pattern = r'<script id="merchant-static-schema" type="application/ld\+json">[\s\S]*?</script>'
        schema_matches = re.findall(schema_pattern, body)
        if len(schema_matches) > 1:
            raise RuntimeError(sku + ': duplicate static Product JSON-LD')
        if not schema_matches:
            body = body.replace('</head>', '<script id="merchant-static-schema" type="application/ld+json">{}</script></head>', 1)
        for pattern, reason in [
            (r'<link rel="canonical" href="' + re.escape(url) + r'">', 'canonical'),
            (r'data-selected-sku="' + re.escape(sku) + r'"', 'selected SKU'),
            (r'data-default-color="' + spec['color_code'] + r'"', 'default vase color'),
            (r'data-design-gallery', 'gallery'),
        ]:
            if not re.search(pattern, body):
                raise RuntimeError(sku + ': landing page has wrong/missing ' + reason)
        pic = p['photo_urls'][0]
        data = {
            '@context': 'https://schema.org',
            '@type': 'Product',
            'sku': sku,
            'name': 'MaGelle ' + p['title_ua'],
            'description': p.get('description_ua') or 'Інтер’єрна композиція MaGelle із сухоцвітів та стабілізованих рослин.',
            'brand': {'@type': 'Brand', 'name': 'MaGelle'},
            'color': p['color'],
            'image': [pic],
            'url': url,
            'offers': {
                '@type': 'Offer', 'url': url, 'price': p['price_uah'],
                'priceCurrency': 'UAH',
                'availability': 'https://schema.org/InStock' if p['status'] == 'stock' else 'https://schema.org/OutOfStock',
                'itemCondition': 'https://schema.org/NewCondition',
            }
        }
        encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
        schema = '<script id="merchant-static-schema" type="application/ld+json">' + encoded + '</script>'
        body = re.sub(schema_pattern, lambda _: schema, body, count=1)
        # Google sees precisely the same default physical variant in the
        # rendered first product photo and Product/Offer image.
        hero_pattern = r'(<img id="product-main-image" src=")[^"]+(" alt=")[^"]*(")'
        body, count = re.subn(hero_pattern, lambda m: m.group(1) + html.escape(pic, quote=True)
                              + m.group(2) + html.escape(p['title_ua'] + ' — MaGelle', quote=True) + m.group(3),
                              body, count=1)
        if count != 1:
            raise RuntimeError(sku + ': hero image missing')
        attr = 'data-variant-' + spec['color_code'].lower()
        if not re.search(attr + r'="[^"]*"', body):
            raise RuntimeError(sku + ': default vase photo map missing')
        body = re.sub(attr + r'="[^"]*"', lambda _: attr + '="' + html.escape(pic, quote=True) + '"', body, count=1)
        og_pattern = r'<meta property="og:image" content="[^"]*">'
        og_tag = '<meta property="og:image" content="' + html.escape(pic, quote=True) + '">'
        if re.search(og_pattern, body):
            body = re.sub(og_pattern, lambda _: og_tag, body, count=1)
        else:
            body = body.replace('</head>', og_tag + '</head>', 1)
        if body != path.read_text(encoding='utf-8'):
            path.write_text(body, encoding='utf-8')


if __name__ == '__main__':
    source = get_products()
    xml, count = build(source)
    sync_pdp_schema(source)
    if count != len(APPROVED):
        raise AssertionError('Incomplete Merchant exact-SKU set')
    OUTPUT.write_text(xml + '\n', encoding='utf-8')
    print(f'Merchant feed: validated exact identity of all {count} Admin 2.0 SKU')
