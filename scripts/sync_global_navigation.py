# One source of truth: the homepage header menu.
from pathlib import Path
import re
pattern=re.compile(r'<nav class="site-nav" id="nav">[\s\S]*?</nav>')
master=pattern.search(Path("index.html").read_text(encoding="utf-8"))
if not master: raise RuntimeError("Home navigation missing")
count=0
for page in Path(".").glob("*.html"):
    raw=page.read_bytes().decode("utf-8")
    nav=pattern.search(raw)
    if not nav: continue
    new=raw[:nav.start()]+master.group(0)+raw[nav.end():]
    if new!=raw:
        page.write_bytes(new.encode("utf-8"))
        count+=1
print("Synchronized site navigation in",count,"pages")
