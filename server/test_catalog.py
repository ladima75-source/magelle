import io
import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
import catalog
import import_catalog

TEMP=tempfile.TemporaryDirectory()
os.environ['MAGELLE_DB']=str(Path(TEMP.name)/'template.db')
os.environ['MAGELLE_SESSION_SECRET']='catalog-test-only-secret'
os.environ['MAGELLE_ADMIN_PASSWORD']='catalog-test-only-password'
import app

class ClosingConnection(sqlite3.Connection):
    def __exit__(self,*args):
        try: return super().__exit__(*args)
        finally: self.close()

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(); self.path=Path(self.directory.name)/'admin.db'
        source=sqlite3.connect(os.environ['MAGELLE_DB'])
        target=sqlite3.connect(self.path)
        source.backup(target);target.close()
        source.close()
        with self.db() as con:
            con.execute("UPDATE products SET price_uah=4200,status='stock',lifecycle='active'")
            con.execute("INSERT INTO orders(customer_name,phone,total_uah) VALUES('Existing order','TEST',4200)")
            con.execute("INSERT INTO order_items(order_id,sku,qty,price_uah,base_sku) VALUES(1,'MG-OF-VYR-GRA',1,4200,'MG-OF-VYR-GRA')")
        ts=str(int(time.time())); self.cookie=ts+'.'+catalog.secret_sign(app.SECRET,ts)
        self.csrf=catalog.secret_sign(app.SECRET,'csrf:'+self.cookie)
    def tearDown(self): self.directory.cleanup()
    def db(self):
        con=sqlite3.connect(self.path,factory=ClosingConnection); con.row_factory=sqlite3.Row; con.execute('PRAGMA foreign_keys=ON');return con
    def request(self,path,method='GET',data=None,csrf=True,cookie=True):
        raw=json.dumps(data or {}).encode()
        environ={'PATH_INFO':path,'REQUEST_METHOD':method,'CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw),
                 'HTTP_HOST':'api.magelle.com.ua','HTTP_ORIGIN':'https://api.magelle.com.ua','REMOTE_ADDR':'TEST'}
        if cookie: environ['HTTP_COOKIE']='magelle_admin='+self.cookie
        if csrf: environ['HTTP_X_CSRF_TOKEN']=self.csrf
        try:return catalog.route(environ,self.db,app.SECRET,app.ADMIN_PASSWORD,app.body_json,lambda _:None)
        except catalog.ApiError as e:return e.status,{'error':e.code},[]
    def import_data(self):
        with self.db() as con:
            report=import_catalog.import_rows(con,Path(__file__).parent.parent)
            con.execute('UPDATE catalog_meta SET enabled=1 WHERE id=1')
            return report
    def first_product(self,variant=False):
        with self.db() as con:return catalog.decoded(con.execute('SELECT * FROM products WHERE design_id IS '+('NOT NULL' if variant else 'NULL')+' ORDER BY sku LIMIT 1').fetchone())
    def test_additive_migration_idempotent(self):
        with self.db() as con:
            before=import_catalog.legacy_fingerprint(con);catalog.migrate(con);catalog.migrate(con)
            self.assertEqual(before,import_catalog.legacy_fingerprint(con))
    def test_import_preserves_orders_and_old_products(self):
        with self.db() as con: before=import_catalog.legacy_fingerprint(con)
        self.assertEqual(self.import_data()['variants_added'],64)
        self.assertEqual(self.import_data()['variants_added'],0)
        with self.db() as con:
            self.assertEqual(before,import_catalog.legacy_fingerprint(con));self.assertEqual(con.execute('SELECT count(*) FROM products').fetchone()[0],80)
    def test_source_gallery_not_mapped_to_other_color(self):
        self.import_data()
        with self.db() as con:
            gra=catalog.decoded(con.execute("SELECT * FROM products WHERE sku='MG-OF-MED-VYR-GRA'").fetchone())
            snd=catalog.decoded(con.execute("SELECT * FROM products WHERE sku='MG-OF-MED-VYR-SND'").fetchone())
        self.assertEqual(len(gra['photo_urls']),1); self.assertGreaterEqual(len(snd['photo_urls']),4)
    def test_csrf_and_auth_required(self):
        p=self.first_product(); path='/api/admin/products/'+p['product_id']
        self.assertEqual(self.request(path,'PUT',{'version':1,'price_uah':5000},csrf=False)[0],403)
        self.assertEqual(self.request(path,'PUT',{'version':1,'price_uah':5000},cookie=False)[0],401)
    def test_conflict_does_not_overwrite(self):
        p=self.first_product();path='/api/admin/products/'+p['product_id']
        self.assertEqual(self.request(path,'PUT',{'version':1,'price_uah':5000})[0],200)
        self.assertEqual(self.request(path,'PUT',{'version':1,'price_uah':6000})[0],409)
        self.assertEqual(self.first_product()['price_uah'],5000)
    def test_invalid_price_and_url_rejected(self):
        p=self.first_product();path='/api/admin/products/'+p['product_id']
        for payload in [{'price_uah':-1},{'price_uah':3.5},{'status':'garbage'},{'photo_urls':['javascript:alert(1)']},{'old_price_uah':1}]:
            self.assertEqual(self.request(path,'PUT',{'version':1,**payload})[0],400)
    def test_sku_alias_and_order_history_preserved(self):
        p=self.first_product();path='/api/admin/products/'+p['product_id']
        self.request(path,'PUT',{'version':1,'sku':'MG-AS-TEST-GRA'})
        with self.db() as con:
            self.assertEqual(catalog.resolve(con,p['sku'])['product_id'],p['product_id'])
            self.assertEqual(con.execute('SELECT sku FROM order_items WHERE id=1').fetchone()[0],'MG-OF-VYR-GRA')
        r=self.request('/api/orders','POST',{'customer_name':'QA','phone':'TEST','items':[{'sku':p['sku'],'qty':2}]},cookie=False)
        self.assertEqual(r[1]['total_uah'],8400)
    def test_ordered_product_cannot_be_deleted(self):
        with self.db() as con:p=dict(con.execute("SELECT * FROM products WHERE sku='MG-OF-VYR-GRA'").fetchone())
        r=self.request('/api/admin/products/'+p['product_id'],'DELETE',{'version':1,'confirm':p['sku']})
        self.assertEqual(r[0],409)
        self.assertEqual(self.request('/api/admin/products/'+p['product_id'],'PUT',{'version':1,'lifecycle':'archived'})[0],200)
        with self.db() as con:self.assertEqual(con.execute('SELECT count(*) FROM order_items').fetchone()[0],1)
    def test_soft_delete_can_be_restored(self):
        p=self.first_product();path='/api/admin/products/'+p['product_id']
        self.assertEqual(self.request(path,'DELETE',{'version':1,'confirm':p['sku']})[0],200)
        self.assertEqual(self.request(path,'PUT',{'version':2,'lifecycle':'active','status':'stock'})[0],200)
    def test_order_snapshot_is_server_authoritative(self):
        self.import_data();p=self.first_product(True)
        r=self.request('/api/orders','POST',{'customer_name':'QA','phone':'TEST','items':[{'sku':p['sku'],'qty':2,'price_uah':1,'vase_color':'FAKE','design':'FAKE'}]},cookie=False)
        self.assertEqual(r[0],201);self.assertEqual(r[1]['total_uah'],8400)
        with self.db() as con:
            item=dict(con.execute('SELECT * FROM order_items WHERE order_id=?',(r[1]['order_id'],)).fetchone())
            self.assertNotEqual(item['design'],'FAKE');self.assertNotEqual(item['vase_color'],'FAKE');self.assertEqual(item['price_uah'],4200)
        admin_item=self.request('/api/admin/orders')[1][0]['items'][0]
        self.assertEqual(admin_item['snapshot']['price_uah'],4200)
        self.assertNotIn('snapshot_json',admin_item)
    def test_arbitrary_virtual_sku_cannot_use_cheaper_base(self):
        self.assertEqual(self.request('/api/orders','POST',{'customer_name':'QA','phone':'TEST','items':[{'sku':'MG-OF-FAKE-VYR-GRA','base_sku':'MG-OF-VYR-GRA','qty':1}]},cookie=False)[0],400)
    def test_hidden_design_blocks_api_and_order(self):
        self.import_data();p=self.first_product(True)
        with self.db() as con: d=dict(con.execute('SELECT * FROM designs WHERE id=?',(p['design_id'],)).fetchone())
        self.request('/api/admin/designs/'+d['id'],'PUT',{'version':d['version'],'lifecycle':'hidden'})
        public=self.request('/api/catalog',cookie=False)[1]
        self.assertFalse(any(x['id']==d['id'] for x in public['designs']))
        self.assertFalse(any(x['sku']==p['sku'] for x in public['products']))
        self.assertEqual(self.request('/api/orders','POST',{'customer_name':'QA','phone':'TEST','items':[{'sku':p['sku'],'qty':1}]},cookie=False)[0],400)
    def test_reorder_atomic_and_rejects_partial_list(self):
        self.import_data();model=self.request('/api/admin/catalog')[1];ids=[d['id'] for d in model['designs']]
        self.assertEqual(self.request('/api/admin/reorder','PUT',{'version':model['version'],'ids':ids[:-1]})[0],400)
        self.assertEqual(self.request('/api/admin/reorder','PUT',{'version':model['version'],'ids':ids[::-1]})[0],200)
        self.assertEqual([d['id'] for d in self.request('/api/catalog',cookie=False)[1]['designs']],ids[::-1])
    def test_viewer_cannot_mutate(self):
        payload=__import__('base64').urlsafe_b64encode(catalog.dumps({'ts':int(time.time()),'user':'read','role':'viewer'}).encode()).decode().rstrip('=')
        os.environ['MAGELLE_ADMIN_USERS']=json.dumps({'read':{'role':'viewer'}})
        self.cookie=payload+'.'+catalog.secret_sign(app.SECRET,payload);self.csrf=catalog.secret_sign(app.SECRET,'csrf:'+self.cookie)
        p=self.first_product();self.assertEqual(self.request('/api/admin/products/'+p['product_id'],'PUT',{'version':1,'price_uah':5000})[0],403)
        self.assertEqual(self.request('/api/admin/catalog')[0],200)
        os.environ.pop('MAGELLE_ADMIN_USERS',None)
    def test_editor_cannot_delete(self):
        payload=__import__('base64').urlsafe_b64encode(catalog.dumps({'ts':int(time.time()),'user':'edit','role':'editor'}).encode()).decode().rstrip('=')
        os.environ['MAGELLE_ADMIN_USERS']=json.dumps({'edit':{'role':'editor'}})
        self.cookie=payload+'.'+catalog.secret_sign(app.SECRET,payload);self.csrf=catalog.secret_sign(app.SECRET,'csrf:'+self.cookie)
        p=self.first_product();self.assertEqual(self.request('/api/admin/products/'+p['product_id'],'DELETE',{'version':1,'confirm':p['sku']})[0],403)
        os.environ.pop('MAGELLE_ADMIN_USERS',None)
    def test_audit_records_before_after_and_actor(self):
        p=self.first_product();self.request('/api/admin/products/'+p['product_id'],'PUT',{'version':1,'price_uah':5000})
        entry=self.request('/api/admin/audit')[1][0]
        self.assertEqual(entry['actor'],'owner');self.assertEqual(json.loads(entry['before_json'])['price_uah'],4200);self.assertEqual(json.loads(entry['after_json'])['price_uah'],5000)

    def test_cached_original_keeps_source_links(self):
        p=self.first_product();source='https://drive.google.com/thumbnail?id=approved'
        self.request('/api/admin/products/'+p['product_id'],'PUT',{'version':1,'photo_urls':[source]})
        with self.db() as con: con.execute('INSERT INTO media_assets(source_url,public_url,sha256) VALUES(?,?,?)',(source,'https://api.magelle.com.ua/uploads/original.png','a'*64))
        admin=next(x for x in self.request('/api/admin/catalog')[1]['products'] if x['product_id']==p['product_id'])
        public=next(x for x in self.request('/api/catalog',cookie=False)[1]['products'] if x['product_id']==p['product_id'])
        self.assertEqual(admin['photo_urls'],[source]);self.assertEqual(public['photo_urls'],admin['display_photo_urls'])

    def test_upload_signature_and_digest(self):
        raw=b'\x89PNG\r\n\x1a\n'+b'test-image'
        environ={'PATH_INFO':'/api/admin/media','REQUEST_METHOD':'POST','CONTENT_LENGTH':str(len(raw)),
                 'CONTENT_TYPE':'image/png','wsgi.input':io.BytesIO(raw),'HTTP_HOST':'api.magelle.com.ua',
                 'HTTP_COOKIE':'magelle_admin='+self.cookie,'HTTP_X_CSRF_TOKEN':self.csrf}
        result=catalog.route(environ,self.db,app.SECRET,app.ADMIN_PASSWORD,app.body_json,lambda _:None)
        self.assertEqual(result[0],201)
        filename=result[1]['url'].rsplit('/',1)[1]
        self.assertEqual((self.path.parent/'media'/filename).read_bytes(),raw)
        environ['wsgi.input']=io.BytesIO(b'x'*len(raw))
        with self.assertRaises(catalog.ApiError): catalog.route(environ,self.db,app.SECRET,app.ADMIN_PASSWORD,app.body_json,lambda _:None)

if __name__=='__main__': unittest.main()
