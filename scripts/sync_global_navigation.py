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
    menu_css='<link rel="stylesheet" href="/site-menu.css?v=2">'
    new=new.replace('/site-menu.css?v=1','/site-menu.css?v=2')
    if menu_css not in new:
        if '</head>' not in new: raise RuntimeError('Missing head on '+str(page))
        new=new.replace('</head>',menu_css+'</head>',1)
    if new!=raw:
        page.write_bytes(new.encode("utf-8"))
        count+=1
print("Synchronized site navigation in",count,"pages")
