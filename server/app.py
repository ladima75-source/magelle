import os, json, sqlite3, hmac, hashlib, time, urllib.request, urllib.parse
from pathlib import Path
from urllib.parse import parse_qs

BASE=Path(__file__).resolve().parent
DB=Path(os.getenv("MAGELLE_DB","/var/lib/magelle/admin.db"))
SECRET=os.getenv("MAGELLE_SESSION_SECRET","change-me")
ADMIN_PASSWORD=os.getenv("MAGELLE_ADMIN_PASSWORD","")
ALLOWED_ORIGIN=os.getenv("MAGELLE_ORIGIN","https://magelle.com.ua")
STATIC=BASE/"static"

def db():
    DB.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row
    return con

def init_db():
    con=db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS products(
      sku TEXT PRIMARY KEY, series TEXT NOT NULL, size_name TEXT, size_code TEXT, color TEXT,
      title_ua TEXT, description_ua TEXT, composition TEXT, dimensions TEXT,
      price_uah INTEGER, old_price_uah INTEGER, status TEXT NOT NULL DEFAULT 'hidden',
      lead_time_days INTEGER, photo_urls TEXT NOT NULL DEFAULT '[]', sort_order INTEGER DEFAULT 0,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS orders(
      id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      customer_name TEXT, phone TEXT, email TEXT, delivery TEXT, comment TEXT,
      total_uah INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'new',
      payment_status TEXT NOT NULL DEFAULT 'unpaid'
    );
    CREATE TABLE IF NOT EXISTS order_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, sku TEXT NOT NULL,
      qty INTEGER NOT NULL DEFAULT 1, price_uah INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY(order_id) REFERENCES orders(id)
    );
    """)
    count=con.execute("SELECT COUNT(*) n FROM products").fetchone()["n"]
    if count==0:
        seed=json.loads((BASE/"seed.json").read_text("utf-8"))
        for p in seed["products"]:
            con.execute("""INSERT INTO products
            (sku,series,size_name,size_code,color,title_ua,description_ua,composition,dimensions,price_uah,old_price_uah,status,lead_time_days,photo_urls,sort_order)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
              p["sku"],p["series"],p.get("size_name"),p.get("size_code"),p.get("color"),
              p.get("title_ua"),p.get("description_ua",""),p.get("composition",""),p.get("dimensions",""),
              p.get("price_uah"),p.get("old_price_uah"),p.get("status","hidden"),p.get("lead_time_days"),
              json.dumps(p.get("photo_urls",[]),ensure_ascii=False),p.get("sort_order",0)))
        con.commit()
    con.close()

init_db()

def jdump(obj): return json.dumps(obj,ensure_ascii=False).encode("utf-8")
def headers(extra=None,ctype="application/json; charset=utf-8"):
    h=[("Content-Type",ctype),("Cache-Control","no-store")]
    if extra: h.extend(extra)
    return h
def body_json(environ):
    n=int(environ.get("CONTENT_LENGTH") or 0)
    raw=environ["wsgi.input"].read(n) if n else b"{}"
    return json.loads(raw.decode("utf-8") or "{}")

def sign(ts):
    return hmac.new(SECRET.encode(),str(ts).encode(),hashlib.sha256).hexdigest()
def auth_ok(environ):
    cookies={}
    for part in environ.get("HTTP_COOKIE","").split(";"):
        if "=" in part:
            k,v=part.strip().split("=",1); cookies[k]=v
    val=cookies.get("magelle_admin","")
    if "." not in val:return False
    ts_s,sig=val.split(".",1)
    try: ts=int(ts_s)
    except:return False
    if time.time()-ts>86400:return False
    return hmac.compare_digest(sig,sign(ts))

def cors(environ):
    origin=environ.get("HTTP_ORIGIN","")
    return [("Access-Control-Allow-Origin",origin if origin==ALLOWED_ORIGIN else ALLOWED_ORIGIN),
            ("Access-Control-Allow-Credentials","true"),
            ("Access-Control-Allow-Headers","Content-Type"),
            ("Access-Control-Allow-Methods","GET,POST,PUT,OPTIONS")]

def product_dict(r):
    d=dict(r)
    try:d["photo_urls"]=json.loads(d.get("photo_urls") or "[]")
    except:d["photo_urls"]=[]
    return d

def notify_telegram(order_id):
    token=os.getenv("TELEGRAM_BOT_TOKEN",""); chat=os.getenv("TELEGRAM_CHAT_ID","")
    if not token or not chat:return
    try:
        data=urllib.parse.urlencode({"chat_id":chat,"text":f"MaGelle: нове замовлення #{order_id}"}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage",data=data,timeout=5)
    except Exception: pass

def application(environ,start_response):
    method=environ["REQUEST_METHOD"]; path=environ.get("PATH_INFO","/")
    if method=="OPTIONS":
        start_response("204 No Content",headers(cors(environ))); return [b""]
    try:
      if path in ("/","/admin","/admin/"):
        data=(STATIC/"admin.html").read_bytes()
        start_response("200 OK",headers(ctype="text/html; charset=utf-8")); return [data]
      if path=="/admin.css":
        start_response("200 OK",headers(ctype="text/css; charset=utf-8")); return [(STATIC/"admin.css").read_bytes()]
      if path=="/admin.js":
        start_response("200 OK",headers(ctype="application/javascript; charset=utf-8")); return [(STATIC/"admin.js").read_bytes()]
      if path=="/api/health":
        start_response("200 OK",headers(cors(environ))); return [jdump({"ok":True,"service":"magelle-admin","version":"0.1.0"})]
      if path=="/api/admin/login" and method=="POST":
        data=body_json(environ)
        if not ADMIN_PASSWORD or not hmac.compare_digest(str(data.get("password","")),ADMIN_PASSWORD):
            start_response("401 Unauthorized",headers(cors(environ))); return [jdump({"ok":False,"error":"invalid_credentials"})]
        ts=int(time.time()); cookie=f"magelle_admin={ts}.{sign(ts)}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=86400"
        start_response("200 OK",headers(cors(environ)+[("Set-Cookie",cookie)])); return [jdump({"ok":True})]
      if path=="/api/admin/logout" and method=="POST":
        start_response("200 OK",headers(cors(environ)+[("Set-Cookie","magelle_admin=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict")]))
        return [jdump({"ok":True})]
      if path=="/api/products" and method=="GET":
        con=db(); rows=con.execute("SELECT * FROM products WHERE status!='hidden' ORDER BY sort_order,sku").fetchall(); con.close()
        start_response("200 OK",headers(cors(environ))); return [jdump([product_dict(x) for x in rows])]
      if path=="/api/orders" and method=="POST":
        data=body_json(environ); items=data.get("items") or []
        if not items: raise ValueError("empty_order")
        con=db(); total=0; clean=[]
        for it in items:
            p=con.execute("SELECT sku,price_uah,status FROM products WHERE sku=?",(it.get("sku"),)).fetchone()
            if not p or p["status"]=="hidden" or p["price_uah"] is None: raise ValueError("unavailable_product")
            qty=max(1,int(it.get("qty",1))); price=int(p["price_uah"]); total+=qty*price; clean.append((p["sku"],qty,price))
        cur=con.execute("""INSERT INTO orders(customer_name,phone,email,delivery,comment,total_uah)
          VALUES(?,?,?,?,?,?)""",(data.get("customer_name",""),data.get("phone",""),data.get("email",""),data.get("delivery",""),data.get("comment",""),total))
        oid=cur.lastrowid
        con.executemany("INSERT INTO order_items(order_id,sku,qty,price_uah) VALUES(?,?,?,?)",[(oid,*x) for x in clean])
        con.commit(); con.close(); notify_telegram(oid)
        start_response("201 Created",headers(cors(environ))); return [jdump({"ok":True,"order_id":oid,"total_uah":total})]
      if path.startswith("/api/admin/"):
        if not auth_ok(environ):
            start_response("401 Unauthorized",headers(cors(environ))); return [jdump({"ok":False,"error":"unauthorized"})]
        if path=="/api/admin/products" and method=="GET":
            con=db(); rows=con.execute("SELECT * FROM products ORDER BY sort_order,sku").fetchall(); con.close()
            start_response("200 OK",headers(cors(environ))); return [jdump([product_dict(x) for x in rows])]
        if path.startswith("/api/admin/products/") and method=="PUT":
            sku=path.rsplit("/",1)[-1]; data=body_json(environ)
            allowed=["title_ua","description_ua","composition","dimensions","price_uah","old_price_uah","status","lead_time_days","photo_urls","sort_order"]
            fields=[]; vals=[]
            for k in allowed:
                if k in data:
                    fields.append(f"{k}=?"); v=data[k]
                    if k=="photo_urls": v=json.dumps(v or [],ensure_ascii=False)
                    vals.append(v)
            if not fields: raise ValueError("no_fields")
            vals += [sku]
            con=db(); con.execute(f"UPDATE products SET {','.join(fields)},updated_at=CURRENT_TIMESTAMP WHERE sku=?",vals); con.commit(); con.close()
            start_response("200 OK",headers(cors(environ))); return [jdump({"ok":True})]
        if path=="/api/admin/orders" and method=="GET":
            con=db(); orders=[dict(x) for x in con.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()]
            for o in orders:o["items"]=[dict(x) for x in con.execute("SELECT sku,qty,price_uah FROM order_items WHERE order_id=?",(o["id"],)).fetchall()]
            con.close(); start_response("200 OK",headers(cors(environ))); return [jdump(orders)]
        if path.startswith("/api/admin/orders/") and method=="PUT":
            oid=int(path.rsplit("/",1)[-1]); data=body_json(environ)
            status=data.get("status"); payment=data.get("payment_status")
            fields=[]; vals=[]
            if status in ("new","confirmed","production","shipped","done","cancelled"): fields.append("status=?"); vals.append(status)
            if payment in ("unpaid","paid","refunded"): fields.append("payment_status=?"); vals.append(payment)
            if not fields: raise ValueError("no_fields")
            vals.append(oid); con=db(); con.execute(f"UPDATE orders SET {','.join(fields)} WHERE id=?",vals); con.commit(); con.close()
            start_response("200 OK",headers(cors(environ))); return [jdump({"ok":True})]
      start_response("404 Not Found",headers(cors(environ))); return [jdump({"ok":False,"error":"not_found"})]
    except ValueError as e:
      start_response("400 Bad Request",headers(cors(environ))); return [jdump({"ok":False,"error":str(e)})]
    except Exception as e:
      start_response("500 Internal Server Error",headers(cors(environ))); return [jdump({"ok":False,"error":"server_error"})]
