# Shared storefront chrome is one source of truth.
from pathlib import Path
import re

STYLE_VERSION = "4.4"
APP_VERSION = "5.3"
MENU_VERSION = "2"

nav_pattern = re.compile(r'<nav class="site-nav" id="nav">[\s\S]*?</nav>')
master = nav_pattern.search(Path("index.html").read_text(encoding="utf-8"))
if not master:
    raise RuntimeError("Home navigation missing")

menu_pattern = re.compile(r'<link rel="stylesheet" href="/site-menu\.css\?v=[^"]+">')
style_pattern = re.compile(r'/styles\.css\?v=[^"]+')
app_pattern = re.compile(r'/app\.js\?v=[^"]+')
menu_css = f'<link rel="stylesheet" href="/site-menu.css?v={MENU_VERSION}">'

count = 0
for page in Path(".").glob("*.html"):
    raw = page.read_bytes().decode("utf-8")
    new = raw
    nav = nav_pattern.search(new)
    if nav:
        new = new[:nav.start()] + master.group(0) + new[nav.end():]

        # Exactly one shared menu stylesheet on every page with the global nav.
        new = menu_pattern.sub("", new)
        if "</head>" not in new:
            raise RuntimeError("Missing head on " + str(page))
        new = new.replace("</head>", menu_css + "</head>", 1)

    # Existing global assets must never drift between pages.
    new = style_pattern.sub(f"/styles.css?v={STYLE_VERSION}", new)
    new = app_pattern.sub(f"/app.js?v={APP_VERSION}", new)

    if new != raw:
        page.write_bytes(new.encode("utf-8"))
        count += 1

print("Synchronized global storefront chrome/assets in", count, "pages")
