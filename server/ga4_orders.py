"""GA4 Measurement Protocol purchase: only PAID + merchant-CONFIRMED orders.

Never use checkout visits or accepted/unpaid order requests as purchases.
The buyer GA4 client_id is stored without personal/customer information;
an order-specific sent timestamp and stable transaction_id deduplicate events.
Requires GA4_API_SECRET in server environment (never expose it client-side).
"""
import json
import logging
import os
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MEASUREMENT_ID = "G-1RM1S55BZW"
PURCHASE_STATUSES = {"confirmed", "production", "shipped", "done"}


def eligible(order):
    return (order is not None
            and order["status"] in PURCHASE_STATUSES
            and order["payment_status"] == "paid"
            and bool(order["ga4_client_id"])
            and not order["ga4_purchase_sent_at"]
            and int(order["total_uah"]) > 0)


def build_payload(order, items):
    assert eligible(order), "Cannot create purchase for unconfirmed/unpaid order"
    ga_items = []
    for item in items:
        snapshot = json.loads(item["snapshot_json"] or "{}")
        ga_items.append({
            "item_id": item["sku"],
            "item_name": snapshot.get("title_ua") or item["sku"],
            "item_brand": "MaGelle",
            "item_category": snapshot.get("series") or item["family"] or "",
            "item_variant": snapshot.get("color") or item["vase_color"] or "",
            "price": int(item["price_uah"]),
            "quantity": int(item["qty"]),
        })
    if not ga_items:
        raise ValueError("Confirmed order missing items")
    return {
        "client_id": order["ga4_client_id"],
        "events": [{
            "name": "purchase",
            "params": {
                "transaction_id": "MG-" + str(order["id"]),
                "currency": "UAH",
                "value": int(order["total_uah"]),
                "items": ga_items,
                "engagement_time_msec": 1,
            },
        }],
    }


def _http_send(measurement_id, api_secret, payload):
    url = "https://www.google-analytics.com/mp/collect?" + urlencode({
        "measurement_id": measurement_id, "api_secret": api_secret
    })
    req = Request(url, method="POST", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=6) as response:
        if response.status not in (200, 204):
            raise RuntimeError("Google Analytics rejected measurement request")
    # Measurement Protocol HTTP 204 means accepted for processing, not
    # guaranteed valid / visible in reports.


def sync_paid_purchase(db, order_id, sender=None, api_secret=None):
    secret = api_secret if api_secret is not None else os.environ.get("GA4_API_SECRET", "")
    if not secret:
        return False
    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        # Claim expiry permits a later admin action to retry interrupted sends.
        claimed = row["ga4_purchase_claimed_at"] if row is not None else None
        old_claim = bool(claimed and
                         con.execute("SELECT datetime(?) < datetime('now','-10 minutes')",
                                     (claimed,)).fetchone()[0])
        if not eligible(row) or (claimed and not old_claim):
            con.rollback()
            return False
        con.execute("UPDATE orders SET ga4_purchase_claimed_at=CURRENT_TIMESTAMP WHERE id=?", (order_id,))
        items = con.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id",
                            (order_id,)).fetchall()
        event = build_payload(row, items)
        con.commit()
    finally:
        con.close()

    try:
        (sender or _http_send)(MEASUREMENT_ID, secret, event)
    except Exception:
        logging.exception("GA4 purchase delivery error for order id=%s", order_id)
        con = db()
        try:
            con.execute("UPDATE orders SET ga4_purchase_claimed_at=NULL WHERE id=? "
                        "AND ga4_purchase_sent_at IS NULL", (order_id,))
            con.commit()
        finally:
            con.close()
        return False

    con = db()
    try:
        con.execute("UPDATE orders SET ga4_purchase_sent_at=CURRENT_TIMESTAMP,ga4_purchase_claimed_at=NULL "
                    "WHERE id=? AND ga4_purchase_sent_at IS NULL", (order_id,))
        con.commit()
    finally:
        con.close()
    return True
