#!/usr/bin/env python3
"""Block Merchant publication on ANY mismatch among 3 exact SKU feed items,
Admin 2.0 variants, crawlable PDP metadata, visible hero, and Product/Offer.
"""
import html
import json
import re
from pathlib import Path
from urllib.request import urlopen, Request
from xml.etree import ElementTree as ET
from build_merchant_feed import APPROVED, SITE, get_products, validated_products, availability, acceptable_photo

ROOT = ET.parse('merchant.xml').getroot()
NS = {'g': 'http://base.google.com/ns/1.0'}
rows = ROOT.findall('./channel/item')
ids = [row.findtext('g:id', namespaces=NS) for row in rows]
assert len(ids) == len(APPROVED) and set(ids) == set(APPROVED), f'Wrong pilot SKU list: {ids!r}'
assert len(set(ids)) == len(ids), 'Duplicate Merchant SKU'
admin = validated_products(get_products())

for item in rows:
    sku = item.findtext('g:id', namespaces=NS)
    spec = APPROVED[sku]
    product = admin[sku]
    canonical = SITE + spec['path']
    image = product['photo_urls'][0]
    expected_name = 'MaGelle ' + product['title_ua']
    expected_price = f"{product['price_uah']:.2f} UAH"
    expected_availability = availability(product)

    assert item.findtext('title') == expected_name, sku + ': RSS name does not match Admin'
    assert item.findtext('link') == canonical, sku + ': RSS link wrong color/URL'
    assert item.findtext('g:color', namespaces=NS) == spec['color'], sku + ': RSS vase color wrong'
    assert item.findtext('g:image_link', namespaces=NS) == image, sku + ': RSS image wrong SKU'
    assert item.findtext('g:item_group_id', namespaces=NS) == spec['design_id'], sku + ': RSS design mismatched'
    assert item.findtext('g:price', namespaces=NS) == expected_price, sku + ': RSS price != Admin 2.0'
    assert item.findtext('g:availability', namespaces=NS) == expected_availability, sku + ': RSS stock != Admin 2.0'
    assert item.findtext('g:brand', namespaces=NS) == 'MaGelle', sku + ': wrong brand'
    assert item.findtext('g:condition', namespaces=NS) == 'new', sku + ': wrong condition'
    assert acceptable_photo(image), sku + ': not an approved first-party image'

    page = Path(spec['path'].lstrip('/'))
    doc = page.read_text(encoding='utf-8')
    assert not re.search(r'<meta name="robots" content="noindex', doc), sku + ': PDP noindex'
    assert f'<link rel="canonical" href="{canonical}">' in doc, sku + ': bad canonical URL'
    assert f'data-selected-sku="{sku}"' in doc, sku + ': initial SKU mismatch'
    assert f'data-default-color="{spec["color_code"]}"' in doc, sku + ': initially selected color mismatch'
    assert f'data-selected-color="{spec["color"]}"' in doc, sku + ': default vase color label mismatch'

    marker = re.search(r'<script id="merchant-static-schema" type="application/ld\+json">([\s\S]*?)</script>', doc)
    assert marker, sku + ': Product schema missing'
    schema = json.loads(marker.group(1))
    assert schema.get('@context') == 'https://schema.org', sku + ': invalid schema context'
    assert schema.get('@type') == 'Product', sku + ': not a Product schema'
    assert schema.get('sku') == sku, sku + ': JSON-LD SKU mismatched'
    assert schema.get('name') == expected_name, sku + ': JSON-LD title mismatched'
    assert schema.get('color') == spec['color'], sku + ': JSON-LD color mismatched'
    assert schema.get('image') == [image], sku + ': JSON-LD first image mismatched'
    assert schema.get('url') == canonical, sku + ': JSON-LD URL mismatched'
    assert schema.get('brand', {}).get('name') == 'MaGelle', sku + ': JSON-LD brand mismatched'

    offer = schema.get('offers') or {}
    assert offer.get('@type') == 'Offer', sku + ': missing Offer'
    assert offer.get('url') == canonical, sku + ': Offer link mismatch'
    assert offer.get('priceCurrency') == 'UAH', sku + ': Offer currency mismatch'
    assert abs(float(offer.get('price') or 0) - float(product['price_uah'])) < .005, sku + ': Offer price mismatch'
    expected_schema_stock = 'https://schema.org/InStock' if expected_availability == 'in_stock' else 'https://schema.org/OutOfStock'
    assert offer.get('availability') == expected_schema_stock, sku + ': Offer stock mismatch'
    assert offer.get('itemCondition') == 'https://schema.org/NewCondition', sku + ': Offer condition missing'

    hero = re.search(r'<img id="product-main-image" src="([^"]+)" alt="([^"]*)"', doc)
    assert hero, sku + ': product main photo not found'
    assert html.unescape(hero.group(1)) == image, sku + ': buyer hero differs from image_link'
    assert spec['color'] in html.unescape(hero.group(2)), sku + ': hero alt has another vase color'
    og = re.search(r'<meta property="og:image" content="([^"]+)">', doc)
    assert og and html.unescape(og.group(1)) == image, sku + ': OG image is inconsistent'
    src = re.search(r'data-variant-' + spec['color_code'].lower() + r'="([^"]+)"', doc)
    assert src and html.unescape(src.group(1)) == image, sku + ': color picker will replace correct hero with another photo'

    with urlopen(Request(image, headers={'User-Agent': 'MaGelle-Merchant-Image-QA/2.0'}), timeout=35) as response:
        assert response.status == 200, sku + ': image GET failed'
        mime = response.headers.get_content_type()
        magic = response.read(16)
        assert mime in ('image/png', 'image/jpeg', 'image/webp'), sku + ': incorrect image MIME: ' + mime
        assert magic.startswith((b'\x89PNG', b'\xff\xd8\xff', b'RIFF')), sku + ': image URL does not serve image bytes'
    print('PASS', sku, '|', spec['color'], '|', product['price_uah'], 'UAH |', canonical, '|', image)

print(f'MAG-022 Merchant identity/image/schema check PASS: all {len(rows)} exact SKU')
