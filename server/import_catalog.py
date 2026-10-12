"""One-time, repeatable import of reviewed storefront metadata. No old row updates."""
import argparse
import hashlib
import json
import re
import html
import sqlite3
import sys
from html.parser import HTMLParser
from pathlib import Path
import catalog

class Markup(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.cards=[]; self.photos=[]; self.info=None; self.gallery_color=''; self.main=''; self.thumb_alt=''; self.in_thumb=False
        self.feed(content)
    def handle_starttag(self, tag, attrs):
        a=dict(attrs); cls=a.get('class','').split()
        if 'design-variant-card' in cls:
            self.cards.append({k[5:].replace('-','_'):v for k,v in a.items() if k.startswith('data-')})
        if 'design-variant-pdp' in cls:
            self.info={k[5:].replace('-','_'):v for k,v in a.items() if k.startswith('data-')}
        if a.get('data-gallery-src'):
            self.photos.append(a['data-gallery-src'])
            self.in_thumb=True
        if tag=='img' and self.in_thumb and not self.thumb_alt:
            self.thumb_alt=a.get('alt','')
        if 'data-design-gallery' in a:
            self.gallery_color=a.get('data-photo-color','')
        if a.get('id')=='product-main-image' and a.get('src'):
            self.main=a['src']
    def handle_endtag(self,tag):
        if tag=='button': self.in_thumb=False

def page_specs(content):
    clean=lambda s: html.unescape(re.sub('<[^>]+>','',s)).strip()
    pairs={clean(k):clean(v) for k,v in re.findall(r'<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>',content,re.S)}
    dims=pairs.get('Габарити') or ' × '.join(pairs[k] for k in ('Висота','Ширина','Глибина') if pairs.get(k))
    composition=pairs.get('Склад') or pairs.get('Основні матеріали') or ''
    description=re.search(r'<p class="product-description"[^>]*>(.*?)</p>',content,re.S)
    return {'dimensions':dims,'composition':composition,'description_ua':clean(description.group(1)) if description else ''}

def legacy_fingerprint(con):
    columns=['sku','series','size_name','size_code','color','title_ua','description_ua','composition','dimensions',
             'price_uah','old_price_uah','status','lead_time_days','photo_urls','sort_order','updated_at']
    values=[tuple(r[k] for k in columns) for r in con.execute('SELECT * FROM products WHERE design_id IS NULL ORDER BY sku')]
    orders=[tuple(r) for r in con.execute('SELECT id,created_at,customer_name,phone,email,delivery,comment,total_uah,status,payment_status FROM orders ORDER BY id')]
    items=[tuple(r) for r in con.execute('SELECT id,order_id,sku,qty,price_uah,family,design,size,vase_color,base_sku FROM order_items ORDER BY id')]
    return hashlib.sha256(catalog.dumps([values,orders,items]).encode()).hexdigest()

def import_rows(con, root):
    parser=Markup((root/'catalog.html').read_text('utf-8'))
    inserted_designs=inserted_variants=0
    for position,c in enumerate(parser.cards):
        family=c.get('family_code') or ('AS' if c['family']=='Architectural Step' else 'OF')
        did='design-'+family+'-'+c['design_code']+'-'+c['size_code']
        pdp=root/c['pdp_url'].lstrip('/')
        content=pdp.read_text('utf-8') if pdp.exists() else ''
        pd=Markup(content) if content else None
        specs=page_specs(content)
        info=pd.info if pd and pd.info else {}
        photo_urls=list(dict.fromkeys(pd.photos if pd else []))
        if not photo_urls and c.get('photo_src'): photo_urls=[c['photo_src']]
        source_color=pd.gallery_color if pd and pd.gallery_color else c.get('photo_color','')
        if pd:
            for code,label in [('SND','Пісочний'),('GRA','Графіт'),('MLK','Молочний'),('WHT','Білий'),('CHO','Шоколад')]:
                if label in pd.thumb_alt: source_color=code; break
        colors=c.get('available_colors','GRA,MLK,WHT,SND,CHO' if family=='OF' else 'GRA,CHO').split(',')
        if not con.execute('SELECT 1 FROM designs WHERE id=?',(did,)).fetchone():
            fields={'code':c['design_code'],'family_code':family,'series':c['family'],'title_ua':c['design'],
                    'size_code':c['size_code'],'size_name':c['variant_size'],'collection':c['collection'],
                    'pdp_url':c['pdp_url'],**specs,
                    'source_photo_urls':photo_urls,'source_color':source_color,
                    'default_color':c.get('default_color',''),'lifecycle':'active','sort_order':position}
            catalog.write_record(con,'designs','id',did,fields,True)
            inserted_designs+=1
        for index,color in enumerate(colors):
            sku=f"MG-{family}-{c['design_code']}-{c['size_code']}-{color}"
            if con.execute('SELECT 1 FROM products WHERE sku=?',(sku,)).fetchone(): continue
            base=f"MG-{family}-{c['size_code']}-{color}"
            old=con.execute('SELECT * FROM products WHERE sku=?',(base,)).fetchone()
            label=con.execute('SELECT title_ua FROM colors WHERE code=?',(color,)).fetchone()
            exact=info.get('variant_'+color.lower()) or c.get('variant_'+color.lower())
            # Keep source gallery separate: never assign another color's photo as exact media.
            photos=photo_urls if color==source_color else []
            if color==c.get('photo_color') and c.get('photo_src'):
                photos=list(dict.fromkeys([c['photo_src']]+photos))
            if exact:
                # A Drive thumbnail at w900 and w1600 is the same photo.
                # Keep the PDP exact variant first, without duplicating it.
                def media_identity(url):
                    from urllib.parse import urlsplit, parse_qs
                    parsed=urlsplit(html.unescape(url))
                    if parsed.hostname == 'drive.google.com' and parsed.path == '/thumbnail':
                        return ('drive',parse_qs(parsed.query).get('id',[''])[0])
                    return ('url',url)
                seen=set()
                photos=[u for u in [exact]+photos
                        if not (media_identity(u) in seen or seen.add(media_identity(u)))]
            fields={
                'sku':sku,'series':c['family'],'size_name':c['variant_size'],'size_code':c['size_code'],
                'color':label['title_ua'],'color_code':color,'design_id':did,
                'title_ua':c['family']+' «'+c['design']+'» — '+c['variant_size']+', '+label['title_ua'],
                **specs,
                'price_uah':old['price_uah'] if old else None,'old_price_uah':old['old_price_uah'] if old else None,
                'status':old['status'] if old else 'hidden','lead_time_days':old['lead_time_days'] if old else None,
                'photo_urls':photos,'sort_order':position*100+index,
                'lifecycle':'active' if old and old['status']!='hidden' and old['price_uah'] else 'draft',
            }
            catalog.write_record(con,'products','product_id','variant-'+sku,fields,True)
            inserted_variants+=1
    return {'designs_added':inserted_designs,'variants_added':inserted_variants,'source_cards':len(parser.cards)}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--db',required=True); p.add_argument('--apply',action='store_true'); p.add_argument('--enable',action='store_true'); p.add_argument('--backup')
    args=p.parse_args(); target=Path(args.db)
    if not target.is_file(): sys.exit('Existing database required; refusing to create production database')
    con=sqlite3.connect(target); con.row_factory=sqlite3.Row
    if args.apply:
        if not args.backup: sys.exit('--backup is required for --apply')
        backup=Path(args.backup)
        if backup.exists(): sys.exit('Backup already exists; refusing to overwrite')
        backup.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(backup) as dest: con.backup(dest)
    else:
        dest=sqlite3.connect(':memory:'); con.backup(dest); con.close(); con=dest; con.row_factory=sqlite3.Row
    catalog.migrate(con)
    before=legacy_fingerprint(con)
    con.execute('BEGIN IMMEDIATE')
    try:
        report=import_rows(con,Path(__file__).resolve().parent.parent)
        after=legacy_fingerprint(con)
        if before!=after: raise RuntimeError('Preservation check failed')
        if args.enable: con.execute('UPDATE catalog_meta SET enabled=1 WHERE id=1')
        catalog.audit(con,'migration','import','catalog',{'fingerprint':before},{**report,'fingerprint':after})
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        con.commit()
    except Exception:
        con.rollback(); raise
    report.update({'legacy_preserved':True,'fingerprint':before,'dry_run':not args.apply,'enabled':bool(args.enable)})
    print(json.dumps(report,ensure_ascii=False,indent=2)); con.close()

if __name__=='__main__': main()
