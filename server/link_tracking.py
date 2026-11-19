"""First-party MaGelle B2B short links and privacy-preserving redirect counters.

A redirect records a request, NOT an email open, verified human click or sale.
No IP addresses, full user agents, email addresses, names, or raw referrers
are retained. The private SQLite DB alone maps random slugs to campaign IDs.
"""
from __future__ import annotations

from contextlib import closing
import re
import secrets
import sqlite3
from urllib.parse import urlencode, urlsplit

HOST = "https://api.magelle.com.ua"
SITE = "https://magelle.com.ua"
CAMPAIGN = "magelle_horeca_2026"
ID_FORMAT = re.compile(r"^MG-B2B-[0-9]{3}(?:-(?:IG|F)[0-9]{1,3})?$")
SLUG_FORMAT = re.compile(r"^[A-Za-z0-9_-]{12,22}$")
CHANNELS = {"email", "instagram_direct"}
TARGETS = {
    "catalog": "/catalog.html",
    "organic_flare": "/organic-flare.html",
    "architectural_step": "/architectural-step.html",
    "sculptural_fold": "/sculptural-fold.html",
}
BOT_INDICATORS = (
    "facebookexternalhit", "facebot", "meta-external", "telegrambot",
    "whatsapp", "twitterbot", "linkedinbot", "slackbot", "discordbot",
    "googlebot", "bingbot", "applebot", "yandexbot", "crawler", "spider",
    "urlscan", "url-preview", "preview", "scanner", "security", "bot/",
    "headless", "uptime", "curl/", "python-requests", "mailchimp",
    "proofpoint", "mimecast", "barracuda", "safelinks", "trendmicro",
)
# Seed only non-personal CRM IDs and approved page keys. Random public slugs
# and actual click counts exist *only in private SQLite*, never in GitHub.
SEED_SPECIFICATIONS = (
    ("email", "MG-B2B-034", ("catalog", "organic_flare")),
    ("email", "MG-B2B-038", ("catalog", "organic_flare")),
    ("email", "MG-B2B-039", ("catalog", "architectural_step")),
    ("email", "MG-B2B-041", ("catalog", "sculptural_fold")),
    ("email", "MG-B2B-042", ("catalog", "sculptural_fold")),
    ("instagram_direct", "MG-B2B-010-IG1", ("catalog",)),
    ("instagram_direct", "MG-B2B-031-IG1", ("catalog",)),
    ("instagram_direct", "MG-B2B-032-IG1", ("catalog",)),
    ("instagram_direct", "MG-B2B-033-IG1", ("catalog",)),
    ("instagram_direct", "MG-B2B-043-IG1", ("catalog",)),
    ("instagram_direct", "MG-B2B-044-IG1", ("catalog",)),
    ("instagram_direct", "MG-B2B-045-IG1", ("catalog",)),
)


class TrackingError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code, self.status = code, status


def initialize(db):
    with closing(db()) as con, con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS b2b_tracking_links (
            id INTEGER PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            channel TEXT NOT NULL,
            message_tracking_id TEXT NOT NULL,
            link_key TEXT NOT NULL,
            destination_url TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(channel, message_tracking_id, link_key)
        );
        CREATE TABLE IF NOT EXISTS b2b_tracking_hits (
            link_id INTEGER PRIMARY KEY REFERENCES b2b_tracking_links(id),
            total_requests INTEGER NOT NULL DEFAULT 0,
            likely_bot_requests INTEGER NOT NULL DEFAULT 0,
            unclassified_requests INTEGER NOT NULL DEFAULT 0,
            last_seen_at TEXT
        );
        """)
        for channel, message_tracking_id, keys in SEED_SPECIFICATIONS:
            for key in keys:
                _create(con, channel, message_tracking_id, key)


def _utm_url(channel: str, message_tracking_id: str, key: str) -> str:
    source = "b2b_email" if channel == "email" else "b2b_instagram"
    term = key
    return SITE + TARGETS[key] + "?" + urlencode({
        "utm_source": source,
        "utm_medium": "email" if channel == "email" else "direct",
        "utm_campaign": CAMPAIGN,
        "utm_content": message_tracking_id,
        "utm_term": term,
    })


def _validate(channel: str, message_tracking_id: str, key: str):
    if channel not in CHANNELS or not ID_FORMAT.fullmatch(message_tracking_id) or key not in TARGETS:
        raise TrackingError("invalid_tracking_link")
    if channel == "instagram_direct" and "-IG" not in message_tracking_id:
        raise TrackingError("instagram_message_id_required")
    if channel == "email" and "-IG" in message_tracking_id:
        raise TrackingError("email_message_id_required")


def _create(con, channel: str, message_tracking_id: str, key: str) -> dict:
    _validate(channel, message_tracking_id, key)
    destination = _utm_url(channel, message_tracking_id, key)
    existing = con.execute(
        "SELECT * FROM b2b_tracking_links "
        "WHERE channel=? AND message_tracking_id=? AND link_key=?",
        (channel, message_tracking_id, key),
    ).fetchone()
    if existing:
        if existing["destination_url"] != destination:
            raise TrackingError("existing_link_destination_mismatch", 409)
        return _serialize(dict(existing))
    for _ in range(3):
        slug = secrets.token_urlsafe(9)
        try:
            cur = con.execute(
                "INSERT INTO b2b_tracking_links(slug,channel,message_tracking_id,link_key,destination_url) "
                "VALUES(?,?,?,?,?)", (slug,channel,message_tracking_id,key,destination)
            )
            con.execute("INSERT INTO b2b_tracking_hits(link_id) VALUES(?)", (cur.lastrowid,))
            return _serialize(dict(con.execute(
                "SELECT * FROM b2b_tracking_links WHERE id=?", (cur.lastrowid,)
            ).fetchone()))
        except sqlite3.IntegrityError:
            continue
    raise TrackingError("cannot_allocate_slug", 503)


def create_link(db, channel: str, message_tracking_id: str, link_key: str) -> dict:
    with closing(db()) as con, con:
        return _create(con, channel, message_tracking_id, link_key)


def _serialize(record: dict) -> dict:
    return {
        "slug": record["slug"],
        "public_url": HOST + "/r/" + record["slug"],
        "channel": record["channel"],
        "message_tracking_id": record["message_tracking_id"],
        "link_key": record["link_key"],
        "destination_url": record["destination_url"],
        "created_at": record["created_at"],
    }


def list_links(db, limit=100) -> list[dict]:
    with closing(db()) as con:
        rows = con.execute("""
          SELECT l.*, h.total_requests, h.likely_bot_requests, h.unclassified_requests, h.last_seen_at
          FROM b2b_tracking_links l JOIN b2b_tracking_hits h ON h.link_id=l.id
          ORDER BY l.id ASC LIMIT ?
        """, (max(1,min(int(limit),250)),)).fetchall()
        result=[]
        for row in rows:
            item=_serialize(dict(row))
            item.update({
                "total_requests": int(row["total_requests"]),
                "likely_bot_requests": int(row["likely_bot_requests"]),
                "unclassified_requests": int(row["unclassified_requests"]),
                "last_seen_at": row["last_seen_at"],
            })
            result.append(item)
        return result


def redirect(db, slug: str, *, method: str = "GET", user_agent: str = ""):
    if not SLUG_FORMAT.fullmatch(slug) or method not in {"GET","HEAD"}:
        raise TrackingError("not_found", 404)
    with closing(db()) as con, con:
        target=con.execute(
            "SELECT l.id, l.destination_url FROM b2b_tracking_links l WHERE slug=?", (slug,)
        ).fetchone()
        if target is None:
            raise TrackingError("not_found", 404)
        # Do not allow an untrusted external destination even if DB data were corrupted.
        url=urlsplit(target["destination_url"])
        if url.scheme != "https" or url.netloc != "magelle.com.ua" or \
                url.username or url.password or any(x in target["destination_url"] for x in "\r\n"):
            raise TrackingError("invalid_destination", 503)
        if method == "GET":
            is_bot=any(marker in user_agent.lower() for marker in BOT_INDICATORS)
            con.execute(
                "UPDATE b2b_tracking_hits SET total_requests=total_requests+1, "
                "likely_bot_requests=likely_bot_requests+?, "
                "unclassified_requests=unclassified_requests+?, last_seen_at=CURRENT_TIMESTAMP "
                "WHERE link_id=?",
                (int(is_bot), int(not is_bot), target["id"]),
            )
        return target["destination_url"]


def route(environ, db, secret: str, admin_password: str, body_json, catalog):
    method, path = environ["REQUEST_METHOD"], environ.get("PATH_INFO","")
    if path.startswith("/r/"):
        url=redirect(db,path[len("/r/"):],method=method,user_agent=environ.get("HTTP_USER_AGENT",""))
        return 302,{"ok":True},[
            ("Location",url),
            ("Cache-Control","no-store,private"),
            ("Referrer-Policy","no-referrer"),
            ("X-Robots-Tag","noindex,nofollow"),
        ]
    if path not in ("/api/admin/b2b-links", "/api/admin/b2b-links/"):
        return None
    actor=catalog.actor_for(environ,secret,admin_password,db)
    if actor is None:
        raise TrackingError("unauthorized",401)
    if method == "GET":
        return 200,{"ok":True,"links":list_links(db),"note":"GET counts are raw server hits, not verified human clicks."},[]
    if method == "POST":
        catalog.require_write(environ,actor,secret,2)
        data=body_json(environ)
        link=create_link(
            db,
            str(data.get("channel") or ""),
            str(data.get("message_tracking_id") or ""),
            str(data.get("link_key") or ""),
        )
        return 201,{"ok":True,"link":link},[]
    raise TrackingError("method_not_allowed",405)
