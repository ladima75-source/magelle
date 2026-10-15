#!/usr/bin/env python3
"""Cache public, exact MaGelle Google Drive photos as first-party responsive WebP.

Safety:
- Only verified downloadable image bytes are replaced.
- Preserve exact Drive file identity and original variants.
- Do not change first-party Merchant pilot images or schema.
- Only change image URLs and lazy-loading hints, not product/color/SKU.
"""
import concurrent.futures as cf
import io
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image, ImageOps

ROOT=Path(".")
OUT=ROOT/"media"/"optimized"
OUT.mkdir(parents=True,exist_ok=True)
PAT=re.compile(r'https://drive\.google\.com/thumbnail\?id=([A-Za-z0-9_-]{16,})(?:&(?:amp;)?sz=w(\d+))?')
SIZES=(360,900,1600)
MAX_ID=175
HTML=list(ROOT.glob("*.html"))
URLS={}
for path in HTML:
    body=path.read_text(encoding="utf-8")
    for mid,_ in PAT.findall(body):
        URLS[mid]=True

# Include current approved Drive photo URLs in Admin 2.0 that are only
# present at runtime, so variant selection can use the same local cache.
try:
    data=requests.get("https://api.magelle.com.ua/api/catalog",timeout=35)
    data.raise_for_status()
    catalog=data.json()
    for d in catalog.get("designs",[]):
        for u in d.get("source_photo_urls") or []:
            for mid,_ in PAT.findall(u): URLS[mid]=True
    for p in catalog.get("products",[]):
        for u in p.get("photo_urls") or []:
            for mid,_ in PAT.findall(u): URLS[mid]=True
except Exception as e:
    print("Catalog API unavailable, use HTML sources:",str(e))

ids=list(URLS)[:MAX_ID]
print("Found",len(ids),"unique Drive image IDs")
session=requests.Session()
session.headers.update({"User-Agent":"Mozilla/5.0 MaGelle/1.0 ImageOptimization"})
def fetch_one(mid):
    url=f"https://drive.google.com/thumbnail?id={mid}&sz=w1600"
    err=""
    for attempt in range(2):
        try:
            response=session.get(url,timeout=(12,45))
            response.raise_for_status()
            if len(response.content)>18_000_000: raise RuntimeError("oversized")
            img=Image.open(io.BytesIO(response.content))
            img.load()
            img=ImageOps.exif_transpose(img)
            if img.width<180 or img.height<180: raise RuntimeError("suspiciously small image")
            img=img.convert("RGBA" if img.mode in ("P","RGBA","LA") and ("A" in img.getbands() or "transparency" in img.info) else "RGB")
            saved={}
            for width in SIZES:
                target=OUT/f"drive-{mid}-w{width}.webp"
                if not target.exists():
                    out=img.copy()
                    if max(out.size)>width: out.thumbnail((width,width),Image.Resampling.LANCZOS)
                    out.save(target,format="WEBP",quality=82,method=4)
                saved[str(width)]=f"/media/optimized/{target.name}"
            return mid,saved,None
        except Exception as e:
            err=str(e)
            time.sleep(.5)
    return mid,None,err

found={}
failed={}
with cf.ThreadPoolExecutor(max_workers=6) as pool:
    for mid,urls,error in pool.map(fetch_one,ids):
        if urls: found[mid]=urls
        else: failed[mid]=error
print("Optimized:",len(found),"failed:",len(failed),list(failed.items())[:15])

# No replacement for any failed image, no broken URL introduced.
def localize(match):
    mid,w=match.group(1),int(match.group(2) or 1600)
    if mid not in found: return match.group(0)
    size=360 if w<=480 else 900 if w<=1200 else 1600
    return found[mid][str(size)]

changed=[]
for path in HTML:
    original=path.read_text(encoding="utf-8")
    body=PAT.sub(localize,original)
    # A small map script must load before deferred app.js, in DOM parse order.
    if 'src="/app.js' in body and 'src="/media/optimized-image-map.js"' not in body:
        body=re.sub(r'(<script src="/app\.js)',r'<script src="/media/optimized-image-map.js" defer></script>\1',body,count=1)
    if path.name in ("catalog.html","organic-flare.html","architectural-step.html","sculptural-fold.html"):
        # The first product image is part of the first screen; don't lazy-load it.
        body=re.sub(r'(<img\b[^>]*\bloading=")lazy(")',r'\1eager\2',body,count=1)
        # Avoid changing other attributes or product identity.
    if body != original:
        path.write_text(body,encoding="utf-8")
        changed.append(path.name)

manifest=("window.MaGelleOptimizedImageMap = "+json.dumps(found,ensure_ascii=True,separators=(",",":"))+";\n")
(ROOT/"media"/"optimized-image-map.js").write_text(manifest,encoding="utf-8")
results={
 "total_originals":len(ids),
 "optimized":len(found),
 "failed":failed,
 "changed_pages":changed,
 "files_written":len(found)*3,
 "total_bytes":sum(p.stat().st_size for p in OUT.glob("*.webp")),
}
(ROOT/"media"/"optimized-image-report.json").write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("Changed pages:",changed)
print("Cache bytes:",results["total_bytes"])
# Fail early rather than publish a collection with no optimization.
if len(found)<6:
    raise SystemExit("Too few approved Drive assets could be downloaded: no publication")
