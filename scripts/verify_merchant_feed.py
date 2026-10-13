#!/usr/bin/env python3
"""Validate public Merchant RSS against canonical, crawlable pilot PDP Product/Offer."""
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from build_merchant_feed import APPROVED

ROOT=ET.parse('merchant.xml').getroot()
NS={'g':'http://base.google.com/ns/1.0'}
rows=ROOT.findall('./channel/item')
assert 1<=len(rows)<=len(APPROVED),f'Unexpected Merchant count {len(rows)}'
seen=set()
for row in rows:
    sku=row.findtext('g:id',namespaces=NS)
    assert sku in APPROVED and sku not in seen,sku
    seen.add(sku)
    page=Path(APPROVED[sku].lstrip('/'))
    html=page.read_text(encoding='utf-8')
    assert not re.search(r'<meta name="robots" content="noindex',html),sku+' noindex'
    canonical='https://magelle.com.ua/'+str(page)
    assert f'rel="canonical" href="{canonical}"' in html,sku+' bad canonical'
    m=re.search(r'<script id="merchant-static-schema" type="application/ld\+json">([\s\S]*?)</script>',html)
    assert m,sku+' schema missing'
    data=json.loads(m.group(1))
    assert data.get('@type')=='Product' and data.get('sku')==sku,sku+' SKU mismatch'
    offer=data.get('offers') or {}
    assert offer.get('@type')=='Offer' and offer.get('priceCurrency')=='UAH',sku+' Offer missing'
    assert offer.get('url')==canonical,sku+' Offer link mismatch'
    assert row.findtext('link')==canonical,sku+' RSS link mismatch'
    assert row.findtext('g:availability',namespaces=NS)=='in_stock',sku+' RSS availability'
    assert offer.get('availability')=='https://schema.org/InStock',sku+' schema stock'
    rss_price=row.findtext('g:price',namespaces=NS)
    assert rss_price and rss_price.endswith(' UAH'),sku+' RSS currency'
    assert abs(float(rss_price.split()[0])-float(offer['price']))<0.005,sku+' price mismatch'
    rss_image=row.findtext('g:image_link',namespaces=NS)
    assert rss_image==data['image'][0],sku+' first image mismatch'
    assert rss_image.startswith('https://api.magelle.com.ua/'),sku+' non-first-party media'
    assert row.findtext('g:brand',namespaces=NS)=='MaGelle'
    assert row.findtext('g:condition',namespaces=NS)=='new'
print(f'MAG-022 feed/schema consistency PASS ({len(rows)} SKU): '+', '.join(sorted(seen)))
