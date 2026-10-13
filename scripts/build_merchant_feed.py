#!/usr/bin/env python3
"""Build Google Merchant RSS from the public Admin 2.0 catalog.

No handmade images, prices or stock levels are hard-coded here. The initial
pilot is intentionally limited to 3 reviewed physical SKU/color combinations.
"""
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

SOURCE = os.environ.get('MAGELLE_PRODUCTS_API', 'https://api.magelle.com.ua/api/products')
OUTPUT = Path(os.environ.get('MAGELLE_MERCHANT_FEED', 'merchant.xml'))
SITE = 'https://magelle.com.ua'
G = 'http://base.google.com/ns/1.0'
ET.register_namespace('g', G)

# Each PDP defaults to exactly this color. No other colors are eligible yet.
APPROVED = {
    'MG-OF-MED-VYR-GRA': '/organic-flare-vyraznyi-pisochnyi.html',
    'MG-OF-PER-VYR-MLK': '/organic-flare-vyraznyi-molochnyi.html',
    'MG-OF-OLI-DEL-CHO': '/organic-flare-delikatnyi-shokolad.html',
}

def get_products():
    with urlopen(Request(SOURCE, headers={'User-Agent':'MaGelle-Merchant-Feed/1.0',
                                           'Accept':'application/json'}), timeout=20) as response:
        return json.load(response)

def acceptable_photo(url):
    if not url or not isinstance(url, str):
        return False
    p = urlsplit(url)
    # Do not allow Google Drive thumbnails, placeholders or user supplied hosts.
    return (p.scheme == 'https' and p.netloc == 'api.magelle.com.ua'
            and (p.path.startswith('/uploads/') or p.path.startswith('/media/'))
            and p.path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')))

def add_text(parent, tag, value):
    ET.SubElement(parent, tag).text = str(value)

def add_google(parent, tag, value):
    add_text(parent, '{%s}%s' % (G,tag), value)

def build(products):
    by_sku = {p['sku']:p for p in products if isinstance(p, dict) and p.get('sku')}
    rss = ET.Element('rss', {'version':'2.0'})
    channel = ET.SubElement(rss,'channel')
    add_text(channel,'title','MaGelle — товарний фід')
    add_text(channel,'link',SITE+'/')
    add_text(channel,'description','Підтверджені SKU MaGelle з Admin 2.0')
    count=0
    for sku, path in APPROVED.items():
        p = by_sku.get(sku)
        if not p or p.get('lifecycle') not in ('active', None):
            continue
        if p.get('status') != 'stock':
            continue  # No made-up availability dates for preorder items
        price = p.get('price_uah')
        if not isinstance(price,(int,float)) or price <= 0:
            continue
        pics = p.get('photo_urls')
        main = pics[0] if isinstance(pics,list) and pics else ''
        if not acceptable_photo(main) or not p.get('design_id'):
            continue
        item = ET.SubElement(channel,'item')
        add_google(item,'id',sku)
        add_text(item,'title','MaGelle '+str(p.get('title_ua') or sku))
        add_text(item,'description',p.get('description_ua') or 'Інтер’єрна композиція із сухоцвітів та стабілізованих рослин у дизайнерській вазі MaGelle.')
        add_text(item,'link',SITE+path)
        add_google(item,'image_link',main)
        add_google(item,'availability','in_stock')
        add_google(item,'price',f'{price:.2f} UAH')
        add_google(item,'condition','new')
        add_google(item,'brand','MaGelle')
        add_google(item,'identifier_exists','no')
        add_google(item,'color',p.get('color') or '')
        add_google(item,'item_group_id',p['design_id'])
        count+=1
    if count < 1:
        raise RuntimeError('Refusing to overwrite Merchant feed with zero validated products')
    ET.indent(rss,space='  ')
    return ET.tostring(rss,encoding='unicode',xml_declaration=True),count

def sync_pdp_schema(products):
    """Keep crawlable HTML Offer values aligned with the same Admin data as RSS."""
    import re
    by_sku = {p['sku']:p for p in products if isinstance(p,dict) and p.get('sku')}
    for sku, page in APPROVED.items():
        p=by_sku.get(sku)
        path=Path(page.lstrip('/'))
        if not path.exists():
            raise RuntimeError('Missing PDP: '+page)
        body=path.read_text(encoding='utf-8')
        pattern=r'<script id="merchant-static-schema" type="application/ld\+json">[\s\S]*?</script>'
        if not re.search(pattern,body):
            raise RuntimeError('Merchant schema marker missing: '+page)
        if p and p.get('price_uah') and p.get('photo_urls') and acceptable_photo(p['photo_urls'][0]):
            url=SITE+page
            data={'@context':'https://schema.org','@type':'Product',
                  'sku':sku,'name':'MaGelle '+str(p.get('title_ua') or sku),
                  'description':p.get('description_ua') or 'Інтер’єрна композиція MaGelle із сухоцвітів та стабілізованих рослин.',
                  'brand':{'@type':'Brand','name':'MaGelle'},
                  'color':p.get('color') or '',
                  'image':[p['photo_urls'][0]],'url':url}
            if p.get('status')=='stock':
                data['offers']={'@type':'Offer','url':url,'price':p['price_uah'],
                    'priceCurrency':'UAH','availability':'https://schema.org/InStock',
                    'itemCondition':'https://schema.org/NewCondition'}
            encoded=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
            replacement='<script id="merchant-static-schema" type="application/ld+json">'+encoded+'</script>'
        else:
            # Keep the marker so a later image/stock restoration can be synced.
            replacement='<script id="merchant-static-schema" type="application/ld+json">{}</script>'
        path.write_text(re.sub(pattern,lambda _:replacement,body,count=1),encoding='utf-8')

if __name__=='__main__':
    source=get_products()
    xml, count=build(source)
    sync_pdp_schema(source)
    if count>len(APPROVED):
        raise AssertionError('Pilot cap exceeded')
    OUTPUT.write_text(xml+'\n', encoding='utf-8')
    print(f'Merchant feed updated: {count} validated SKU, source Admin 2.0')
