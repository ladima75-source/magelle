#!/usr/bin/env python3
"""Activate the GA4 event implementation on every storefront page with app.js."""
import re
from pathlib import Path

version = '4.3'
updated = []
tested = 0
for path in sorted(Path('.').glob('*.html')):
    src = path.read_text(encoding='utf-8')
    if not re.search(r'/app\.js\?v=[0-9.]+', src):
        continue
    tested += 1
    value = re.sub(r'/app\.js\?v=[0-9.]+', '/app.js?v=' + version, src)
    if src != value:
        path.write_text(value, encoding='utf-8', newline='')
        updated.append(path.name)
for path in sorted(Path('.').glob('*.html')):
    src = path.read_text(encoding='utf-8')
    if '/app.js?v=' in src and '/app.js?v=4.3' not in src:
        raise SystemExit(f'An obsolete GA4 app.js version remains: {path}')
if tested < 20:
    raise SystemExit(f'Expected 20+ pages with app.js; found {tested}')
print(f'GA4 JS activation PASS: {tested} pages checked, {len(updated)} changed')
