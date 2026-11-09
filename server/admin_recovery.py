"""MaGelle owner recovery: one-time PIN sent only to verified Telegram OWNER in DM.

The configured Telegram destination is the existing orders GROUP/CHANNEL.
A Telegram account may reset the password only after:
1. manually opening this bot privately via a random one-use deep-link,
2. being verified as the group/channel creator through getChatAdministrators,
3. receiving a short-lived PIN in that same private Telegram chat.

Never deliver password reset codes to the orders group/channel or public APIs.
No passwords, PINs, bot tokens, or chat contents are logged.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
import urllib.parse
import urllib.request


CODE_TTL_SECONDS = 600
CODE_COOLDOWN_SECONDS = 90
MAX_ATTEMPTS = 5
BOT_HANDLE = "MaGelleOrdersBot"


class RecoveryError(Exception):
    def __init__(self, code: str, status: int = 400):
        self.code = code
        self.status = status


def _digest(secret: str, code: str) -> str:
    return hmac.new(secret.encode("utf-8"), ("magelle-owner-recovery:" + code).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _valid_origin(environ: dict) -> None:
    if environ.get("HTTP_HOST") != "api.magelle.com.ua" or \
            environ.get("HTTP_ORIGIN") != "https://api.magelle.com.ua":
        raise RecoveryError("invalid_origin", 403)


def _telegram_config() -> tuple[str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not re.fullmatch(r"-?[0-9]{1,20}", chat):
        raise RecoveryError("orders_bot_not_configured", 503)
    return token, chat


def _telegram(token: str, method: str, payload: dict) -> dict:
    req = urllib.request.Request(
        "https://api.telegram.org/bot" + token + "/" + method,
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        if resp.status != 200:
            raise OSError("telegram_api_error")
        response = json.load(resp)
    if response.get("ok") is not True:
        raise OSError("telegram_api_error")
    return response


def _authorized_telegram_user(token: str, orders_chat: str, sender_id: int) -> bool:
    """Only the creator of the existing orders group/channel may reset Owner.

    Optional MAGELLE_OWNER_TELEGRAM_USER_ID may identify a specific administrator
    after secure initial operator configuration. Never trust a user-supplied id.
    """
    result = _telegram(token, "getChatAdministrators", {"chat_id": orders_chat})
    admins = result.get("result")
    if not isinstance(admins, list):
        return False
    configured = os.getenv("MAGELLE_OWNER_TELEGRAM_USER_ID", "").strip()
    for member in admins:
        user = member.get("user", {})
        if user.get("is_bot") or user.get("id") != sender_id:
            continue
        if configured and configured.isdigit():
            return int(configured) == sender_id and member.get("status") in ("creator", "administrator")
        return member.get("status") == "creator"
    return False


def request_link(db, secret: str) -> dict:
    _telegram_config()
    nonce = secrets.token_urlsafe(24)
    now = int(time.time())
    with closing(db()) as con, con:
        previous = con.execute(
            "SELECT requested_at FROM admin_recovery WHERE id=1"
        ).fetchone()
        if previous and now - int(previous["requested_at"]) < CODE_COOLDOWN_SECONDS:
            raise RecoveryError("retry_later", 429)
        con.execute(
            "INSERT OR REPLACE INTO admin_recovery"
            "(id,code_hash,requested_at,expires_at,attempts,link_nonce_hash,verified_user_id)"
            " VALUES(1,'',?,?,0,?,NULL)",
            (now, now + CODE_TTL_SECONDS, _digest(secret, nonce)),
        )
    return {
        "ok": True,
        "method": "telegram_owner_dm",
        "bot_link": "https://t.me/" + BOT_HANDLE + "?start=mgreset_" + nonce,
        "request_token": nonce,
        "ttl_seconds": CODE_TTL_SECONDS,
    }


def check_link(db, secret: str, request_token: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{25,45}", request_token):
        raise RecoveryError("invalid_recovery_request", 400)
    token, chat = _telegram_config()
    with closing(db()) as con:
        state = con.execute(
            "SELECT requested_at,expires_at,link_nonce_hash,code_hash FROM admin_recovery WHERE id=1"
        ).fetchone()
    if not state or state["expires_at"] < int(time.time()) or \
            not state["link_nonce_hash"] or \
            not hmac.compare_digest(state["link_nonce_hash"], _digest(secret, request_token)):
        raise RecoveryError("recovery_request_expired", 403)
    if state["code_hash"]:
        return {"ok": True, "pin_sent": True}

    try:
        # The bot currently sends orders but has no inbound webhook/handler.
        response = _telegram(token, "getUpdates", {"timeout": 0, "limit": 100, "allowed_updates": '["message"]'})
    except Exception:
        logging.warning("MaGelle recovery Telegram incoming update polling unavailable")
        raise RecoveryError("telegram_poll_unavailable", 503)

    updates = response.get("result") or []
    for item in updates:
        m = item.get("message") or {}
        sender = m.get("from") or {}
        conversation = m.get("chat") or {}
        if conversation.get("type") != "private" or not isinstance(sender.get("id"), int):
            continue
        if (m.get("text") or "").strip() != "/start mgreset_" + request_token:
            continue
        if int(m.get("date") or 0) + 30 < state["requested_at"]:
            continue
        try:
            authorized = _authorized_telegram_user(token, chat, sender["id"])
        except Exception:
            logging.warning("MaGelle recovery Telegram owner verification unavailable")
            raise RecoveryError("telegram_owner_verification_unavailable", 503)
        if not authorized:
            return {"ok": True, "pin_sent": False, "not_owner": True}

        code = f"{secrets.randbelow(100000000):08d}"
        msg = (
            "🔐 MaGelle Admin · відновлення доступу\n"
            "Ваш одноразовий код: " + code + "\n"
            "Діє 10 хвилин. Не передавайте його нікому."
        )
        try:
            _telegram(token, "sendMessage", {
                "chat_id": str(sender["id"]),
                "text": msg,
                "disable_web_page_preview": "true",
            })
        except Exception:
            logging.warning("MaGelle recovery private Telegram delivery unavailable")
            raise RecoveryError("code_delivery_failed", 503)

        with closing(db()) as con, con:
            # Atomic update: do not overwrite another later pending reset request.
            cur = con.execute(
                "UPDATE admin_recovery SET code_hash=?,link_nonce_hash='',verified_user_id=? "
                "WHERE id=1 AND link_nonce_hash=? AND expires_at>=?",
                (_digest(secret, code), sender["id"], _digest(secret, request_token), int(time.time())),
            )
            if cur.rowcount != 1:
                raise RecoveryError("recovery_request_expired", 403)
        # Acknowledge the /start message to avoid repeated bot update processing.
        # Do not modify group messages or existing order notifications.
        try:
            _telegram(token, "getUpdates", {
                "offset": item["update_id"] + 1, "timeout": 0, "limit": 1,
                "allowed_updates": '["message"]',
            })
        except Exception:
            pass
        return {"ok": True, "pin_sent": True}
    return {"ok": True, "pin_sent": False}


def complete_reset(db, secret: str, data: dict) -> dict:
    code = str(data.get("code", "")).strip()
    password = data.get("new_password", "")
    if not re.fullmatch(r"[0-9]{8}", code) or not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise RecoveryError("invalid_code_or_password")
    now = int(time.time())
    with closing(db()) as con, con:
        row = con.execute(
            "SELECT code_hash,expires_at,attempts,verified_user_id FROM admin_recovery WHERE id=1"
        ).fetchone()
        if not row or not row["code_hash"] or not row["verified_user_id"] or \
                now > row["expires_at"] or row["attempts"] >= MAX_ATTEMPTS:
            raise RecoveryError("code_expired_or_locked", 403)
        invalid_code = not hmac.compare_digest(row["code_hash"], _digest(secret, code))
        if invalid_code:
            con.execute("UPDATE admin_recovery SET attempts=attempts+1 WHERE id=1")
        else:
            salt = secrets.token_bytes(16)
            password_hash = hashlib.scrypt(
                password.encode("utf-8"), salt=salt, n=16384, r=8, p=1
            ).hex()
            con.execute(
                "INSERT OR REPLACE INTO owner_password(id,salt,password_hash,changed_at)"
                " VALUES(1,?,?,?)",
                (salt.hex(), password_hash, now),
            )
            con.execute("DELETE FROM admin_recovery WHERE id=1")
    if invalid_code:
        raise RecoveryError("invalid_code", 403)
    return {"ok": True, "message": "password_changed"}


def handle(environ: dict, db, secret: str, body_json) -> tuple[int, dict, list]:
    _valid_origin(environ)
    if environ["REQUEST_METHOD"] != "POST":
        raise RecoveryError("method_not_allowed", 405)
    path = environ.get("PATH_INFO", "")
    data = body_json(environ)
    if path == "/api/admin/recovery/request":
        return 200, request_link(db, secret), []
    if path == "/api/admin/recovery/poll":
        return 200, check_link(db, secret, str(data.get("request_token") or "")), []
    if path == "/api/admin/recovery/complete":
        return 200, complete_reset(db, secret, data), []
    raise RecoveryError("not_found", 404)
