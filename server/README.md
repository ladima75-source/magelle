# MaGelle Admin MVP

Backend: Python WSGI + SQLite. Admin UI is served by the API service.

## Routes

- `/admin/` — admin login and interface
- `/api/health`
- `/api/products` — public active products
- `POST /api/orders` — create order
- `/api/admin/products` — protected product CRUD
- `/api/admin/orders` — protected order management

## Deploy on VPS

Repository is expected at `/opt/magelle`.

```bash
cd /opt/magelle
git fetch origin main
git reset --hard origin/main
chmod +x ops/install_admin.sh
./ops/install_admin.sh
```

The installer asks for the admin password once and creates `/etc/magelle-admin.env`.
Do not commit passwords or Telegram tokens.

After DNS points `api.magelle.com.ua` to the VPS, enable HTTPS using the existing server certificate workflow.

## Product statuses

- `hidden` — not visible on public API/site
- `stock` — in stock
- `preorder` — made to order

The database seeds all 16 approved MaGelle SKU. Known prices are included for:
- MG-OF-VYR-MLK — 4200 UAH
- MG-OF-DEL-CHO — 2600 UAH
- MG-AS-DEL-CHO — 1700 UAH
