#!/usr/bin/env bash
set -euo pipefail

ROOT=/opt/magelle-rozetka
FEED_URL="https://raw.githubusercontent.com/ladima75-source/magelle/main/rozetka.xml"
EXPECTED=("MG-OF-DEL-CHO" "MG-OF-VYR-MLK" "MG-AS-DEL-CHO")

cd "$ROOT"

python3 - <<'PY'
import os, re, sys, json, time, urllib.request, urllib.error
from pathlib import Path
from xml.etree import ElementTree as ET

root = Path("/opt/magelle-rozetka")
env_path = root / ".env"
feed_url = "https://raw.githubusercontent.com/ladima75-source/magelle/main/rozetka.xml"
expected = {"MG-OF-DEL-CHO", "MG-OF-VYR-MLK", "MG-AS-DEL-CHO"}

def load_env(path):
    env = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env

env = load_env(env_path)
token = env.get("ROZETKA_CONTENT_TOKEN", "")
if not token:
    raise SystemExit("ERROR: ROZETKA_CONTENT_TOKEN not found in .env")

# Persistent connector write switches must stay OFF for this one-shot import.
for key in ("ALLOW_WRITES", "AUTO_IMPORT"):
    val = env.get(key, "").lower()
    if val not in ("false", "0", "off", "no", ""):
        raise SystemExit(f"ERROR: safety check failed: {key}={env.get(key)} (expected false)")

print("=== PRECHECK FEED ===")
req = urllib.request.Request(feed_url, headers={"User-Agent":"MaGelle-ROZETKA-one-shot/1.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    xml_bytes = r.read()

print("feed_bytes =", len(xml_bytes))
doc = ET.fromstring(xml_bytes)
offers = doc.findall(".//offer")
ids = {o.attrib.get("id") for o in offers}
print("offer_count =", len(offers))
print("offer_ids   =", ", ".join(sorted(ids)))

if len(offers) != 3 or ids != expected:
    raise SystemExit(f"ERROR: feed must contain exactly {sorted(expected)}")

for offer in offers:
    if offer.attrib.get("available", "").lower() != "false":
        raise SystemExit(f"ERROR: {offer.attrib.get('id')} available is not false")

print("safety      = PASS (3 exact SKUs, all available=false, persistent writes remain OFF)")

base = "https://api.seller.rozetka.com.ua"
headers = {
    "Authorization": "Bearer " + token,
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "MaGelle-ROZETKA-one-shot/1.0",
}

payload = json.dumps({
    "file_name": "",
    "place": "url",
    "place_address": feed_url,
}).encode("utf-8")

print()
print("=== CREATE IMPORT ===")
create_req = urllib.request.Request(
    base + "/item-price-updates/create",
    data=payload,
    headers=headers,
    method="POST",
)
try:
    with urllib.request.urlopen(create_req, timeout=30) as r:
        create_data = json.loads(r.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    raise SystemExit(f"HTTP ERROR {e.code}: {body}")

print(json.dumps(create_data, ensure_ascii=False, indent=2))

if create_data.get("success") is not True:
    raise SystemExit("ERROR: ROZETKA rejected import request")

content = create_data.get("content") or {}
import_id = content.get("id")
if not import_id:
    raise SystemExit("ERROR: import id missing")

print()
print("IMPORT_ID =", import_id)
print()
print("=== IMPORT STATUS ===")

last = None
for attempt in range(1, 13):
    search_req = urllib.request.Request(
        base + "/item-price-updates/search?page=1&pageSize=20",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "User-Agent": "MaGelle-ROZETKA-one-shot/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(search_req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))

    content = data.get("content") or {}
    rows = content.get("uploaderLogXmls") if isinstance(content, dict) else content
    if rows is None:
        rows = []
    if isinstance(rows, dict):
        rows = [rows]

    hit = None
    for row in rows:
        try:
            if int(row.get("id")) == int(import_id):
                hit = row
                break
        except Exception:
            pass

    if hit:
        compact = {
            "id": hit.get("id"),
            "status": hit.get("status"),
            "place": hit.get("place"),
            "place_address": hit.get("place_address"),
            "report": hit.get("report"),
            "created_at": hit.get("created_at"),
        }
        if compact != last:
            print(json.dumps(compact, ensure_ascii=False, indent=2))
            last = compact
        # We deliberately do not guess undocumented status meanings.
        report = hit.get("report")
        if report:
            break
    else:
        print(f"attempt {attempt}: import {import_id} not visible in first page yet")

    if attempt < 12:
        time.sleep(5)

print()
print("=== DONE ===")
print("Three-card import request was sent.")
print("Connector .env was NOT changed; ALLOW_WRITES and AUTO_IMPORT remain false.")
print("Review the three cards in ROZETKA Seller cabinet before enabling sales.")
PY
