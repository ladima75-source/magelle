#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/magelle
ENV_FILE=/etc/magelle-admin.env
DB_DIR=/var/lib/magelle

if [[ $EUID -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

cd "$APP_DIR"
git fetch origin main
git reset --hard origin/main

python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/server/requirements.txt"

mkdir -p "$DB_DIR"
chown -R www-data:www-data "$DB_DIR"
chown -R www-data:www-data "$APP_DIR/server"

if [[ ! -f "$ENV_FILE" ]]; then
  read -rsp "MaGelle admin password: " ADMIN_PASSWORD
  echo
  SESSION_SECRET="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
  cat > "$ENV_FILE" <<EOF
MAGELLE_ADMIN_PASSWORD=$ADMIN_PASSWORD
MAGELLE_SESSION_SECRET=$SESSION_SECRET
MAGELLE_DB=/var/lib/magelle/admin.db
MAGELLE_ORIGIN=https://magelle.com.ua
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
EOF
  chmod 600 "$ENV_FILE"
fi

cp "$APP_DIR/server/magelle-admin.service" /etc/systemd/system/magelle-admin.service
cp "$APP_DIR/server/nginx-magelle-admin.conf" /etc/nginx/sites-available/magelle-admin.conf
ln -sfn /etc/nginx/sites-available/magelle-admin.conf /etc/nginx/sites-enabled/magelle-admin.conf

systemctl daemon-reload
systemctl enable --now magelle-admin
nginx -t
systemctl reload nginx

echo
echo "Health:"
curl -fsS http://127.0.0.1:8787/api/health || true
echo
echo "Next: point api.magelle.com.ua DNS to this VPS and issue TLS certificate."
