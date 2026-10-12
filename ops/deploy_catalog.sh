#!/usr/bin/env bash
# Existing installation only. Does not reset a checkout, credentials, or database.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root'; exit 1; }
target=${1:?Expected reviewed commit SHA}
[[ "$target" =~ ^[0-9a-f]{40}$ ]] || { echo 'Full commit SHA required'; exit 1; }
cd /opt/magelle
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo 'Tracked changes: stop'; exit 1; }
[[ -f /var/lib/magelle/admin.db && -f /etc/magelle-admin.env ]] || { echo 'Existing production installation required'; exit 1; }
previous=$(git rev-parse HEAD)
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_dir=/var/backups/magelle
install -d -m 700 "$backup_dir"
python3 - "$backup_dir/pre-catalog-$stamp.db" <<'PY'
import sqlite3,sys
source=sqlite3.connect('/var/lib/magelle/admin.db')
destination=sqlite3.connect(sys.argv[1]);source.backup(destination)
destination.close();source.close()
PY
chmod 600 "$backup_dir/pre-catalog-$stamp.db"
printf '%s\n' "$previous" > "$backup_dir/pre-catalog-$stamp.commit"
git fetch origin main
git merge-base --is-ancestor HEAD "$target"
git merge --ff-only "$target"
python3 -m unittest discover -s server -p test_catalog.py
python3 server/import_catalog.py --db /var/lib/magelle/admin.db
python3 server/import_catalog.py --db /var/lib/magelle/admin.db --apply --enable --backup "$backup_dir/catalog-$stamp.db"
chmod 600 "$backup_dir/catalog-$stamp.db"
systemctl restart magelle-admin
systemctl is-active --quiet magelle-admin
for attempt in {1..10}; do
  if curl -fsS http://127.0.0.1:8787/api/health; then break; fi
  sleep 1
done
curl -fsS http://127.0.0.1:8787/api/catalog | python3 -c 'import json,sys; c=json.load(sys.stdin); assert c["enabled"]; print("designs:",len(c["designs"]),"public products:",len(c["products"]))'
echo "Backup: $backup_dir/pre-catalog-$stamp.db; previous commit: $previous"
