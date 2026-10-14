"""Catalog v2: additive schema, transactional writes, stable identities and snapshots."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from contextlib import contextmanager
from urllib.parse import urlsplit, unquote
from pathlib import Path

STATES = {'draft', 'active', 'hidden', 'archived', 'deleted'}
STATUSES = {'hidden', 'stock', 'preorder'}
CODE = re.compile(r'^[A-Z0-9]{2,12}$')
SKU = re.compile(r'^MG(?:-[A-Z0-9]{2,12}){3,5}$')
ROLES = {'owner': 3, 'editor': 2, 'viewer': 1}

class ApiError(Exception):
    def __init__(self, code, status=400):
        self.code, self.status = code, status

def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

def migrate(con):
    """Never overwrite existing commercial or order data. Safe on repeated startup."""
    con.execute('BEGIN IMMEDIATE')
    try:
        additions = {
            'products': {'product_id': 'TEXT', 'design_id': 'TEXT', 'color_code': 'TEXT',
                         'lifecycle': "TEXT NOT NULL DEFAULT 'active'", 'version': 'INTEGER NOT NULL DEFAULT 1'},
            'order_items': {'product_id': 'TEXT', 'snapshot_json': 'TEXT'},
            'orders': {'ga4_client_id': 'TEXT', 'ga4_purchase_sent_at': 'TEXT',
                       'ga4_purchase_claimed_at': 'TEXT'},
        }
        for table, fields in additions.items():
            present = {r['name'] for r in con.execute('PRAGMA table_info(' + table + ')')}
            for name, kind in fields.items():
                if name not in present:
                    con.execute('ALTER TABLE ' + table + ' ADD COLUMN ' + name + ' ' + kind)
                    if name == 'lifecycle':
                        con.execute("UPDATE products SET lifecycle='hidden' WHERE status='hidden'")
        for r in con.execute('SELECT sku FROM products WHERE product_id IS NULL').fetchall():
            con.execute('UPDATE products SET product_id=? WHERE sku=?', (str(uuid.uuid4()), r['sku']))
        schema='''
        CREATE UNIQUE INDEX IF NOT EXISTS products_identity ON products(product_id);
        CREATE UNIQUE INDEX IF NOT EXISTS product_variant ON products(design_id,size_code,color_code) WHERE design_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS designs(
          id TEXT PRIMARY KEY, code TEXT NOT NULL, family_code TEXT NOT NULL, series TEXT NOT NULL,
          title_ua TEXT NOT NULL, size_code TEXT NOT NULL, size_name TEXT NOT NULL,
          collection TEXT NOT NULL, pdp_url TEXT NOT NULL DEFAULT '', description_ua TEXT NOT NULL DEFAULT '',
          composition TEXT NOT NULL DEFAULT '', dimensions TEXT NOT NULL DEFAULT '',
          source_photo_urls TEXT NOT NULL DEFAULT '[]', source_color TEXT NOT NULL DEFAULT '',
          default_color TEXT NOT NULL DEFAULT '', lifecycle TEXT NOT NULL DEFAULT 'draft',
          sort_order INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(family_code,code,size_code)
        );
        CREATE TABLE IF NOT EXISTS colors(code TEXT PRIMARY KEY, title_ua TEXT NOT NULL,
          hex TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sku_aliases(sku TEXT PRIMARY KEY, product_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS catalog_meta(id INTEGER PRIMARY KEY CHECK(id=1),
          version INTEGER NOT NULL DEFAULT 1, enabled INTEGER NOT NULL DEFAULT 0);
        INSERT OR IGNORE INTO catalog_meta(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS catalog_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, actor TEXT NOT NULL, action TEXT NOT NULL,
          entity TEXT NOT NULL, before_json TEXT, after_json TEXT);
        CREATE TABLE IF NOT EXISTS login_attempts(ip TEXT PRIMARY KEY, count INTEGER NOT NULL, started REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS media_assets(source_url TEXT PRIMARY KEY, public_url TEXT NOT NULL,
          sha256 TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        '''
        for statement in schema.split(';'):
            if statement.strip(): con.execute(statement)
        for code, title, color in [('GRA','Графіт','#202020'),('MLK','Молочний','#EEE7D4'),
                                   ('WHT','Білий','#FFFFFF'),('SND','Пісочний','#C2B29A'),('CHO','Шоколад','#1D0E07')]:
            con.execute('INSERT OR IGNORE INTO colors(code,title_ua,hex) VALUES(?,?,?)', (code,title,color))
        con.commit()
    except Exception:
        con.rollback()
        raise

@contextmanager
def transaction(db):
    con = db()
    try:
        con.execute('BEGIN IMMEDIATE')
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def decoded(row, design=False):
    if row is None:
        return None
    result = dict(row)
    key = 'source_photo_urls' if design else 'photo_urls'
    if key in result:
        result[key] = json.loads(result[key] or '[]')
    return result

def audit(con, actor, action, entity, before, after):
    con.execute('INSERT INTO catalog_audit(actor,action,entity,before_json,after_json) VALUES(?,?,?,?,?)',
                (actor, action, entity, dumps(before), dumps(after)))
    con.execute('UPDATE catalog_meta SET version=version+1 WHERE id=1')

def revision(data, row):
    if data.get('version') != row['version']:
        raise ApiError('conflict_reload', 409)

def text(data, key, limit=300, required=False):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value) > limit:
        raise ApiError('invalid_' + key)
    value = value.strip()
    if required and not value:
        raise ApiError('required_' + key)
    return value

def integer(value, name, maximum=10000000, nullable=False):
    if value is None and nullable:
        return None
    if type(value) is not int or not 0 <= value <= maximum:
        raise ApiError('invalid_' + name)
    return value

def media(value):
    if not isinstance(value, list) or len(value) > 40:
        raise ApiError('invalid_media')
    for url in value:
        if not isinstance(url, str) or len(url) > 2000:
            raise ApiError('invalid_media_url')
        p = urlsplit(url)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or any(c in url for c in '\r\n'):
            raise ApiError('media_https_required')
    return list(dict.fromkeys(value))

def validate_product(con, data, current=None):
    p = decoded(current) if current else {}
    allowed = {'sku','series','size_name','size_code','color','color_code','design_id','title_ua',
               'description_ua','composition','dimensions','price_uah','old_price_uah','status',
               'lead_time_days','photo_urls','sort_order','lifecycle','version'}
    if set(data) - allowed:
        raise ApiError('unknown_fields')
    p.update(data)
    p['sku'] = text(p,'sku',80,True)
    if not SKU.fullmatch(p['sku']):
        raise ApiError('invalid_sku')
    for key in ('series','size_name','size_code','title_ua'):
        p[key] = text(p,key,300,True)
    for key in ('description_ua','composition','dimensions'):
        p[key] = text(p,key,10000)
    if not re.fullmatch(r'[A-Z0-9]{1,12}',p['size_code']):
        raise ApiError('invalid_size_code')
    p['design_id'] = p.get('design_id') or None
    if p['design_id']:
        d = con.execute('SELECT * FROM designs WHERE id=?', (p['design_id'],)).fetchone()
        if not d or d['lifecycle'] == 'deleted':
            raise ApiError('invalid_design')
        if d['series'] != p['series'] or d['size_code'] != p['size_code']:
            raise ApiError('design_variant_mismatch')
    p['color_code'] = text({'color_code':p.get('color_code') or ''},'color_code',12)
    if p['color_code']:
        color = con.execute('SELECT * FROM colors WHERE code=?', (p['color_code'],)).fetchone()
        if not color:
            raise ApiError('invalid_color')
        p['color'] = color['title_ua']
    else:
        p['color'] = text(p,'color',100)
    p['lifecycle'] = p.get('lifecycle', 'draft')
    p['status'] = p.get('status', 'hidden')
    if p['lifecycle'] not in STATES or p['status'] not in STATUSES:
        raise ApiError('invalid_status')
    for key in ('price_uah','old_price_uah'):
        p[key] = integer(p.get(key),key,nullable=True)
    p['lead_time_days'] = integer(p.get('lead_time_days'),'lead_time_days',365,True)
    p['sort_order'] = integer(p.get('sort_order',0),'sort_order')
    p['photo_urls'] = media(p.get('photo_urls',[]))
    if p['old_price_uah'] is not None and (p['price_uah'] is None or p['old_price_uah'] < p['price_uah']):
        raise ApiError('old_price_below_price')
    if p['lifecycle'] == 'active' and p['status'] != 'hidden' and not p['price_uah']:
        raise ApiError('publish_price_required')
    if p['lifecycle'] != 'active':
        p['status'] = 'hidden'
    if current and current['sku'] != p['sku']:
        if con.execute('SELECT 1 FROM sku_aliases WHERE sku=?',(p['sku'],)).fetchone():
            raise ApiError('sku_reserved',409)
    elif not current and con.execute('SELECT 1 FROM sku_aliases WHERE sku=?',(p['sku'],)).fetchone():
        raise ApiError('sku_reserved',409)
    return {k:p[k] for k in allowed - {'version'}}

def validate_design(con, data, current=None):
    p = decoded(current,True) if current else {}
    allowed = {'code','family_code','series','title_ua','size_code','size_name','collection',
               'pdp_url','description_ua','composition','dimensions','source_photo_urls',
               'source_color','default_color','lifecycle','sort_order','version'}
    if set(data)-allowed:
        raise ApiError('unknown_fields')
    p.update(data)
    for key in ('code','family_code','size_code'):
        p[key] = text(p,key,12,True)
        if not CODE.fullmatch(p[key]):
            raise ApiError('invalid_'+key)
    for key in ('series','title_ua','size_name','collection'):
        p[key] = text(p,key,300,True)
    if not re.fullmatch(r'[a-z0-9-]+',p['collection']):
        raise ApiError('invalid_collection')
    p['pdp_url'] = text(p,'pdp_url',300)
    if p['pdp_url'] and not re.fullmatch(r'/[a-z0-9-]+\.html',p['pdp_url']):
        raise ApiError('invalid_pdp_url')
    for key in ('description_ua','composition','dimensions'):
        p[key] = text(p,key,10000)
    for key in ('source_color','default_color'):
        p[key] = text(p,key,12)
        if p[key] and not con.execute('SELECT 1 FROM colors WHERE code=?',(p[key],)).fetchone():
            raise ApiError('invalid_color')
    p['source_photo_urls'] = media(p.get('source_photo_urls',[]))
    p['lifecycle'] = p.get('lifecycle','draft')
    if p['lifecycle'] not in STATES:
        raise ApiError('invalid_status')
    p['sort_order'] = integer(p.get('sort_order',0),'sort_order')
    if current and any(p[k] != current[k] for k in ('series','size_code')):
        if con.execute('SELECT 1 FROM products WHERE design_id=?',(current['id'],)).fetchone():
            raise ApiError('design_identity_has_variants')
    return {k:p[k] for k in allowed-{'version'}}

def write_record(con, table, key, identity, fields, create=False):
    serial = {k:dumps(v) if isinstance(v,list) else v for k,v in fields.items()}
    if create:
        serial[key] = identity
        con.execute('INSERT INTO '+table+' ('+','.join(serial)+') VALUES('+','.join('?' for _ in serial)+')', tuple(serial.values()))
    else:
        con.execute('UPDATE '+table+' SET '+','.join(k+'=?' for k in serial)+',version=version+1'+
                    (',updated_at=CURRENT_TIMESTAMP' if table != 'colors' else '')+' WHERE '+key+'=?',
                    (*serial.values(),identity))

def resolve(con, sku):
    return con.execute('SELECT * FROM products WHERE sku=? OR product_id=(SELECT product_id FROM sku_aliases WHERE sku=?)',(sku,sku)).fetchone()

def available(con, p):
    if not p or p['lifecycle'] != 'active' or p['status'] not in ('stock','preorder') or not p['price_uah']:
        return False
    if p['design_id']:
        d = con.execute('SELECT lifecycle FROM designs WHERE id=?',(p['design_id'],)).fetchone()
        return bool(d and d['lifecycle']=='active')
    return True

def catalog(con, public=False):
    meta = dict(con.execute('SELECT * FROM catalog_meta WHERE id=1').fetchone())
    designs = [decoded(x,True) for x in con.execute('SELECT * FROM designs ORDER BY sort_order,id')]
    products = [decoded(x) for x in con.execute('SELECT * FROM products ORDER BY sort_order,sku')]
    assets = {r['source_url']:r['public_url'] for r in con.execute('SELECT * FROM media_assets')}
    for p in products:
        p['display_photo_urls'] = [assets.get(url,url) for url in p['photo_urls']]
    for d in designs:
        d['display_source_photo_urls'] = [assets.get(url,url) for url in d['source_photo_urls']]
    if public:
        designs = [d for d in designs if d['lifecycle']=='active']
        ids = {d['id'] for d in designs}
        products = [p for p in products if p['lifecycle']=='active' and p['status']!='hidden' and (not p['design_id'] or p['design_id'] in ids)]
        aliases={}
        for alias in con.execute('SELECT sku,product_id FROM sku_aliases'):
            aliases.setdefault(alias['product_id'],[]).append(alias['sku'])
        for p in products: p['aliases']=aliases.get(p['product_id'],[])
        # Original links stay in storage/audit; public clients receive stable identical media.
        for p in products: p['photo_urls']=p.pop('display_photo_urls')
        for d in designs: d['source_photo_urls']=d.pop('display_source_photo_urls')
    return {'enabled':bool(meta['enabled']), 'version':meta['version'],'designs':designs,'products':products,
            'colors':[dict(x) for x in con.execute('SELECT * FROM colors ORDER BY rowid')]}

def secret_sign(secret, value):
    return hmac.new(secret.encode(),value.encode(),hashlib.sha256).hexdigest()

def users(admin_password):
    # Optional named users, hashes only: {"anna":{"role":"editor","salt":"...","hash":"..."}}.
    return json.loads(os.getenv('MAGELLE_ADMIN_USERS','{}'))

def actor_for(environ, secret, admin_password):
    cookies = dict(part.strip().split('=',1) for part in environ.get('HTTP_COOKIE','').split(';') if '=' in part)
    value = cookies.get('magelle_admin','')
    if '.' not in value:
        return None
    payload, signature = value.rsplit('.',1)
    if not hmac.compare_digest(secret_sign(secret,payload),signature):
        return None
    try:
        if payload.isdigit():
            ts, name, role = int(payload),'owner','owner'
        else:
            details = json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
            ts,name,role = details['ts'],details['user'],details['role']
            if name != 'owner' and users(admin_password).get(name,{}).get('role') != role:
                return None
        if not 0 <= time.time()-ts <= 86400 or role not in ROLES:
            return None
    except (ValueError,KeyError,TypeError):
        return None
    return {'user':name,'role':role,'csrf':secret_sign(secret,'csrf:'+value)}

def require_write(environ, actor, secret, level=2):
    if ROLES[actor['role']] < level:
        raise ApiError('forbidden',403)
    if not hmac.compare_digest(environ.get('HTTP_X_CSRF_TOKEN',''),actor['csrf']):
        raise ApiError('csrf_required',403)
    origin = environ.get('HTTP_ORIGIN','')
    host = environ.get('HTTP_HOST','')
    if origin and urlsplit(origin).netloc != host:
        raise ApiError('invalid_origin',403)

def route(environ, db, secret, admin_password, body_json, notify):
    method,path = environ['REQUEST_METHOD'],unquote(environ.get('PATH_INFO','/'))
    if path == '/api/catalog' and method == 'GET':
        with transaction(db) as con:
            return 200,catalog(con,True),[]
    if path == '/api/products' and method == 'GET':
        with transaction(db) as con:
            return 200,catalog(con,True)['products'],[]
    if path == '/api/health':
        return 200,{'ok':True,'service':'magelle-admin','version':'2.0.0'},[]
    if path == '/api/orders' and method == 'POST':
        data=body_json(environ)
        name=text(data,'customer_name',200,True); phone=text(data,'phone',40,True)
        client_id=str(data.get('analytics_client_id') or '')[:120]
        if not re.fullmatch(r'[0-9]{1,30}\.[0-9]{1,30}',client_id): client_id=''
        items=data.get('items')
        if not isinstance(items,list) or not 1<=len(items)<=20:
            raise ApiError('empty_or_too_large_order')
        with transaction(db) as con:
            total=0; clean=[]
            for it in items:
                if not isinstance(it,dict): raise ApiError('invalid_item')
                item_sku=text(it,'sku',80,True)
                p=resolve(con,item_sku)
                if not available(con,p): raise ApiError('unavailable_product')
                qty=integer(it.get('qty',1),'quantity',20)
                if qty<1: raise ApiError('invalid_quantity')
                d=con.execute('SELECT * FROM designs WHERE id=?',(p['design_id'],)).fetchone() if p['design_id'] else None
                snapshot={'sku':item_sku,'title_ua':p['title_ua'],'series':p['series'],'design':d['title_ua'] if d else '',
                          'size_name':p['size_name'],'color':p['color'],'price_uah':p['price_uah'],'photo_urls':json.loads(p['photo_urls'])}
                clean.append((item_sku,qty,p['price_uah'],p['series'],snapshot['design'],p['size_name'],p['color'],p['sku'],p['product_id'],dumps(snapshot)))
                total+=qty*p['price_uah']
            cur=con.execute('INSERT INTO orders(customer_name,phone,email,delivery,comment,total_uah,ga4_client_id) VALUES(?,?,?,?,?,?,?)',
                            (name,phone,text(data,'email',300),text(data,'delivery',3000),text(data,'comment',3000),total,client_id))
            oid=cur.lastrowid
            con.executemany('INSERT INTO order_items(order_id,sku,qty,price_uah,family,design,size,vase_color,base_sku,product_id,snapshot_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',[(oid,*x) for x in clean])
        notify(oid)
        return 201,{'ok':True,'order_id':oid,'total_uah':total},[]
    if path == '/api/admin/login' and method == 'POST':
        data=body_json(environ); name=data.get('username') or 'owner'; password=data.get('password','')
        if not isinstance(name,str) or not isinstance(password,str) or len(password)>1000: raise ApiError('invalid_credentials',401)
        # Nginx must overwrite X-Forwarded-For; REMOTE_ADDR is safe without that contract.
        ip=environ.get('REMOTE_ADDR','unknown')
        with transaction(db) as con:
            attempt=con.execute('SELECT * FROM login_attempts WHERE ip=?',(ip,)).fetchone()
            if attempt and time.time()-attempt['started']<300 and attempt['count']>=10:
                raise ApiError('try_later',429)
            role='owner'; valid=bool(name=='owner' and admin_password and hmac.compare_digest(password,admin_password))
            u=users(admin_password).get(name)
            if u:
                role=u.get('role','viewer')
                digest=hashlib.scrypt(password.encode(),salt=bytes.fromhex(u['salt']),n=16384,r=8,p=1).hex()
                valid=role in ROLES and hmac.compare_digest(digest,u['hash'])
            if not valid:
                count=attempt['count']+1 if attempt and time.time()-attempt['started']<300 else 1
                started=attempt['started'] if count>1 else time.time()
                con.execute('INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)',(ip,count,started))
            else: con.execute('DELETE FROM login_attempts WHERE ip=?',(ip,))
        if not valid: raise ApiError('invalid_credentials',401)
        payload=base64.urlsafe_b64encode(dumps({'ts':int(time.time()),'user':name,'role':role,'nonce':secrets.token_hex(16)}).encode()).decode().rstrip('=')
        cookie='magelle_admin='+payload+'.'+secret_sign(secret,payload)+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=86400'
        return 200,{'ok':True},[('Set-Cookie',cookie)]
    if not path.startswith('/api/admin/'):
        return None
    actor=actor_for(environ,secret,admin_password)
    if not actor: raise ApiError('unauthorized',401)
    if path == '/api/admin/session' and method == 'GET': return 200,actor,[]
    if method not in ('GET','HEAD'):
        require_write(environ,actor,secret,1 if path.endswith('/logout') else 2)
    if path=='/api/admin/media' and method=='POST':
        length=int(environ.get('CONTENT_LENGTH') or 0)
        if not 1<=length<=12*1024*1024: raise ApiError('media_max_12mb',413)
        raw=environ['wsgi.input'].read(length)
        content_type=environ.get('CONTENT_TYPE','').split(';')[0]
        valid={'image/png':raw.startswith(b'\x89PNG\r\n\x1a\n'),
               'image/jpeg':raw.startswith(b'\xff\xd8\xff'),
               'image/webp':raw[:4]==b'RIFF' and raw[8:12]==b'WEBP'}
        if not valid.get(content_type) or len(raw)!=length: raise ApiError('invalid_image')
        extension={'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp'}[content_type]
        with transaction(db) as con:
            directory=Path(con.execute('PRAGMA database_list').fetchone()['file']).parent/'media'
            directory.mkdir(parents=True,exist_ok=True)
            filename=secrets.token_hex(24)+extension
            destination=directory/filename
            with destination.open('xb') as f: f.write(raw)
            host=environ.get('HTTP_HOST','api.magelle.com.ua')
            scheme='http' if host.startswith(('localhost:','127.0.0.1:')) else 'https'
            url=scheme+'://'+host+'/uploads/'+filename
            audit(con,actor['user'],'upload','media:'+filename,None,{'url':url,'bytes':length,'sha256':hashlib.sha256(raw).hexdigest()})
        return 201,{'url':url},[]
    if path == '/api/admin/logout' and method == 'POST':
        return 200,{'ok':True},[('Set-Cookie','magelle_admin=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0')]
    with transaction(db) as con:
        if path == '/api/admin/catalog' and method == 'GET': return 200,catalog(con),[]
        if path == '/api/admin/products' and method == 'GET': return 200,catalog(con)['products'],[]
        if path == '/api/admin/audit' and method == 'GET':
            if actor['role']!='owner': raise ApiError('forbidden',403)
            return 200,[dict(x) for x in con.execute('SELECT * FROM catalog_audit ORDER BY id DESC LIMIT 200')],[]
        if path == '/api/admin/reorder' and method == 'PUT':
            data=body_json(environ); meta=con.execute('SELECT * FROM catalog_meta WHERE id=1').fetchone(); revision(data,meta)
            ids=data.get('ids'); before=[r['id'] for r in con.execute('SELECT id FROM designs ORDER BY sort_order,id')]
            if not isinstance(ids,list) or len(ids)!=len(before) or len(set(ids))!=len(ids) or set(ids)!=set(before): raise ApiError('invalid_order')
            for i,identity in enumerate(ids): con.execute('UPDATE designs SET sort_order=?,version=version+1 WHERE id=?',(i,identity))
            audit(con,actor['user'],'reorder','catalog',before,ids)
            return 200,{'ok':True},[]
        for noun,table,key,validator in [('products','products','product_id',validate_product),('designs','designs','id',validate_design)]:
            root='/api/admin/'+noun
            if path==root and method=='POST':
                data=body_json(environ); fields=validator(con,data); identity=str(uuid.uuid4())
                if fields.get('lifecycle')=='deleted': raise ApiError('cannot_create_deleted')
                if table=='products': fields['product_id']=identity
                write_record(con,table,key,identity,fields,True)
                after=decoded(con.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(identity,)).fetchone(),table=='designs')
                audit(con,actor['user'],'create',noun+':'+identity,None,after)
                return 201,after,[]
            if path.startswith(root+'/') and method in ('PUT','DELETE'):
                identity=path[len(root)+1:]
                row=con.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(identity,)).fetchone()
                if not row: raise ApiError('not_found',404)
                data=body_json(environ); revision(data,row); before=decoded(row,table=='designs')
                if method=='DELETE':
                    require_write(environ,actor,secret,3)
                    if data.get('confirm')!=row['sku' if table=='products' else 'title_ua']: raise ApiError('confirmation_required')
                    if table=='products':
                        aliases=[row['sku']]+[r['sku'] for r in con.execute('SELECT sku FROM sku_aliases WHERE product_id=?',(identity,))]
                        used=con.execute('SELECT 1 FROM order_items WHERE product_id=? OR sku IN ('+','.join('?' for _ in aliases)+') OR base_sku IN ('+','.join('?' for _ in aliases)+') LIMIT 1',(identity,*aliases,*aliases)).fetchone()
                    else:
                        used=con.execute("SELECT 1 FROM products WHERE design_id=? AND lifecycle!='deleted' LIMIT 1",(identity,)).fetchone()
                    if used: raise ApiError('archive_required_has_history_or_variants',409)
                    fields={'lifecycle':'deleted'}
                    if table=='products': fields['status']='hidden'
                else:
                    if data.get('lifecycle')=='deleted': raise ApiError('use_delete_action')
                    fields=validator(con,data,row)
                    if table=='products' and fields['sku']!=row['sku']:
                        con.execute('INSERT INTO sku_aliases(sku,product_id) VALUES(?,?)',(row['sku'],identity))
                write_record(con,table,key,identity,fields)
                after=decoded(con.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(identity,)).fetchone(),table=='designs')
                audit(con,actor['user'],'delete' if method=='DELETE' else 'update',noun+':'+identity,before,after)
                return 200,after,[]
        if path=='/api/admin/colors' and method=='POST':
            data=body_json(environ); code=text(data,'code',12,True)
            if not CODE.fullmatch(code): raise ApiError('invalid_color_code')
            fields={'title_ua':text(data,'title_ua',100,True),'hex':text(data,'hex',7,True)}
            if not re.fullmatch(r'#[A-Fa-f0-9]{6}',fields['hex']): raise ApiError('invalid_hex')
            write_record(con,'colors','code',code,fields,True); audit(con,actor['user'],'create','color:'+code,None,fields)
            return 201,{'code':code,**fields},[]
        if path.startswith('/api/admin/colors/') and method=='PUT':
            code=path.rsplit('/',1)[-1]; row=con.execute('SELECT * FROM colors WHERE code=?',(code,)).fetchone()
            if not row: raise ApiError('not_found',404)
            data=body_json(environ); revision(data,row)
            fields={'title_ua':text(data,'title_ua',100,True),'hex':text(data,'hex',7,True)}
            if not re.fullmatch(r'#[A-Fa-f0-9]{6}',fields['hex']): raise ApiError('invalid_hex')
            write_record(con,'colors','code',code,fields)
            # Denormalized label is refreshed without changing historical order snapshots.
            con.execute('UPDATE products SET color=?,version=version+1 WHERE color_code=?',(fields['title_ua'],code))
            audit(con,actor['user'],'update','color:'+code,dict(row),fields)
            return 200,{'ok':True},[]
        if path=='/api/admin/orders' and method=='GET':
            orders=[dict(x) for x in con.execute('SELECT * FROM orders ORDER BY id DESC')]
            assets={r['source_url']:r['public_url'] for r in con.execute('SELECT source_url,public_url FROM media_assets')}
            for o in orders:
                o['items']=[]
                for row in con.execute('SELECT * FROM order_items WHERE order_id=?',(o['id'],)):
                    item=dict(row)
                    try: item['snapshot']=json.loads(item.get('snapshot_json') or '{}')
                    except (TypeError,json.JSONDecodeError): item['snapshot']={}
                    urls=item['snapshot'].get('photo_urls') or []
                    item['display_photo_urls']=[assets.get(url,url) for url in urls]
                    item.pop('snapshot_json',None)
                    o['items'].append(item)
            return 200,orders,[]
        if path.startswith('/api/admin/orders/') and method=='PUT':
            oid=path.rsplit('/',1)[-1]; row=con.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
            if not row: raise ApiError('not_found',404)
            data=body_json(environ); fields={}
            for field,allowed in [('status',{'new','confirmed','production','shipped','done','cancelled'}),('payment_status',{'unpaid','paid','refunded'})]:
                if field in data:
                    if data[field] not in allowed: raise ApiError('invalid_'+field)
                    fields[field]=data[field]
            if not fields: raise ApiError('no_fields')
            if data.get('expected')!={k:row[k] for k in fields}: raise ApiError('conflict_reload',409)
            con.execute('UPDATE orders SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),oid))
            audit(con,actor['user'],'order_status','order:'+oid,{k:row[k] for k in fields},fields)
            return 200,{'ok':True},[]
    raise ApiError('not_found',404)
