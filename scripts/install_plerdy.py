#!/usr/bin/env python3
"""Install the owner-provided Plerdy site tracker into all public HTML pages.

Run from the repository root. Idempotent: never duplicates the snippet.
Admin pages under server/static are intentionally excluded.
"""
from pathlib import Path

TRACKER = """<!-- НАЧАЛО КОДА ПЛЕРДИ -->
<script data-plerdy_code='1'>
(function(w,d){
  if(w.__plerdyCode)return;
  w.__plerdyCode=1;
  w._protocol=w.location.protocol=="https:"?"https://":"http://";
  w._site_hash_code="eb396657f6341014bb79ec99f478fecf";
  w._suid=81873;
  var s=d.createElement("script");
  s.async=true;
  s.referrerPolicy="strict-origin-when-cross-origin";
  s.src="https://a.plerdy.com/public/js/click/main.js?v="+Math.random();
  d.head.appendChild(s);
})(window,document);
</script>
<!-- КОНЕЦ КОДА ПЛЕРДИ -->"""

pages = sorted(Path('.').glob('*.html'))
updated = []
for path in pages:
    original = path.read_text(encoding='utf-8')
    if '</body>' not in original:
        raise RuntimeError(f'No body closing tag: {path}')
    if 'data-plerdy_code=' in original or 'eb396657f6341014bb79ec99f478fecf' in original:
        continue
    changed = original.replace('</body>', '\n' + TRACKER + '\n</body>', 1)
    path.write_text(changed, encoding='utf-8', newline='')
    updated.append(path.name)

for path in pages:
    html = path.read_text(encoding='utf-8')
    if html.count('eb396657f6341014bb79ec99f478fecf') != 1:
        raise RuntimeError(f'Plerdy tracker missing or duplicate: {path}')

print('PLERDY INSTALL PASS:', len(pages), 'public pages,', len(updated), 'changed')
for name in updated:
    print('INSTALLED', name)
