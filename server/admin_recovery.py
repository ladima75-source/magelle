"""Owner-only password recovery using the existing private MaGelle Orders Telegram bot.

A one-time code is delivered only to the configured private Telegram chat.
No password or code is stored in plaintext in the database, repository, logs,
or ChatGPT. The existing Owner password becomes invalid after successful reset.
"""
from __future__ import annotations

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


class RecoveryError(Exception):
    def __init__(self, code: str, status: int = 400):
        self.code = code
        self.status = status


def _digest(secret: str, code: str) -> str:
    return hmac.new(secret.encode("utf-8"), ("magelle-owner-recovery:" + code).encode("ascii"),
                    hashlib.sha256).hexdigest()


def _valid_origin(environ: dict) -> None:
    host = environ.get("HTTP_HOST", "")
    origin = environ.get("HTTP_ORIGIN", "")
    # The reset procedure is available only via the actual HTTPS Admin site.
    if host != "api.magelle.com.ua" or origin != "https://api.magelle.com.ua":
        raise RecoveryError("invalid_origin", 403)


def _private_bot_chat() -> tuple[str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    # A private Telegram chat ID is a positive integer. Never send reset codes
    # to group/channel chats, where unintended recipients could see them.
    if not token or not chat.isdigit() or int(chat) < 1:
        raise RecoveryError("private_orders_bot_required", 503)
    return token, chat


def _send_code(token: str, chat: str, code: str) -> None:
    message = (
        "🔐 MaGelle Admin · відновлення доступу\n"
        "Ваш одноразовий код: " + code + "\n"
        "Діє 10 хвилин. Нікому не повідомляйте код.\n"
        "Якщо ви не запитували відновлення, ігноруйте це повідомлення."
    )
    payload = urllib.parse.urlencode({
        "chat_id": chat, "text": message, "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.telegram.org/bot" + token + "/sendMessage",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        if resp.status != 200:
            raise OSError("telegram_delivery_failed")
        confirmation = json.load(resp)
        if confirmation.get("ok") is not True:
            raise OSError("telegram_delivery_failed")


def request_code(db, secret: str) -> dict:
    token, chat = _private_bot_chat()
    code = f"{secrets.randbelow(100000000):08d}"
    now = int(time.time())
    with db() as con:
        row = con.execute(
            "SELECT requested_at FROM admin_recovery WHERE id=1"
        ).fetchone()
        if row and now - int(row["requested_at"]) < CODE_COOLDOWN_SECONDS:
            raise RecoveryError("retry_later", 429)
        con.execute(
            "INSERT OR REPLACE INTO admin_recovery"
            "(id,code_hash,requested_at,expires_at,attempts) VALUES(1,?,?,?,0)",
            (_digest(secret, code), now, now + CODE_TTL_SECONDS),
        )
    try:
        _send_code(token, chat, code)
    except Exception:
        # Failed delivery must not leave a valid reset code behind.
        with db() as con:
            con.execute(
                "UPDATE admin_recovery SET code_hash='' WHERE id=1 AND code_hash=?",
                (_digest(secret, code),),
            )
        logging.warning("MaGelle owner recovery code delivery unavailable; no secret logged")
        raise RecoveryError("code_delivery_failed", 503)
    return {"ok": True, "method": "private_telegram_bot", "ttl_seconds": CODE_TTL_SECONDS}


def complete_reset(db, secret: str, data: dict) -> dict:
    code = str(data.get("code", "")).strip()
    password = data.get("new_password", "")
    if not re.fullmatch(r"[0-9]{8}", code) or not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise RecoveryError("invalid_code_or_password")
    now = int(time.time())
    with db() as con:
        row = con.execute(
            "SELECT code_hash,expires_at,attempts FROM admin_recovery WHERE id=1"
        ).fetchone()
        if not row or not row["code_hash"] or now > row["expires_at"] or row["attempts"] >= MAX_ATTEMPTS:
            raise RecoveryError("code_expired_or_locked", 403)
        if not hmac.compare_digest(row["code_hash"], _digest(secret, code)):
            con.execute("UPDATE admin_recovery SET attempts=attempts+1 WHERE id=1")
            raise RecoveryError("invalid_code", 403)
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
    return {"ok": True, "message": "password_changed"}


def handle(environ: dict, db, secret: str, body_json) -> tuple[int, dict, list]:
    _valid_origin(environ)
    if environ["REQUEST_METHOD"] != "POST":
        raise RecoveryError("method_not_allowed", 405)
    path = environ.get("PATH_INFO", "")
    data = body_json(environ)
    if path == "/api/admin/recovery/request":
        return 200, request_code(db, secret), []
    if path == "/api/admin/recovery/complete":
        return 200, complete_reset(db, secret, data), []
    raise RecoveryError("not_found", 404)
