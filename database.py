"""SQLite storage and URL de-duplication helpers."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import aiosqlite

# Query parameters commonly used for campaign/attribution tracking. Dropping
# them lets equivalent article URLs collapse to the same de-duplication key.
TRACKING_QUERY_PARAMS = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "dclid", "igshid", "mkt_tok", "mc_cid", "mc_eid",
        "ref", "ref_src", "ref_url", "oref",
    }
)

_ABSOLUTE_URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def normalize_url(url: object) -> str:
    """Return a canonical form of ``url`` used as the de-duplication key.

    * scheme and host are lower-cased; default ports are removed;
    * fragments and common tracking query parameters are dropped;
    * a redundant trailing slash is removed.

    Values that are not absolute URLs are returned stripped (so they still
    de-duplicate against themselves) and unusable input yields "".
    """
    if not url:
        return ""
    cleaned = str(url).strip()
    if not cleaned:
        return ""
    if cleaned.startswith("//"):
        cleaned = "https:" + cleaned
    if not _ABSOLUTE_URL_RE.match(cleaned):
        return cleaned
    try:
        parts = urlparse(cleaned)
    except ValueError:
        return cleaned

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    userinfo, sep, host = netloc.rpartition("@")
    host = host.rstrip(".")
    if (scheme == "http" and host.endswith(":80")) or (
        scheme == "https" and host.endswith(":443")
    ):
        host = host.rsplit(":", 1)[0]
    netloc = host if not sep else f"{userinfo}@{host}"

    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_PARAMS
    ]
    return urlunparse((scheme, netloc, path, parts.params, urlencode(query), ""))


def dedup_key(url: object) -> str:
    """Normalized URL for storage/lookup, or the stripped input as fallback."""
    return normalize_url(url) or str(url or "").strip()


class Database:
    def __init__(self, path: str):
        self.path = path

    async def init(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS articles(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE,
                    title TEXT,
                    source TEXT,
                    published_at TEXT,
                    posted_at TEXT,
                    telegram_message_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
                CREATE INDEX IF NOT EXISTS idx_articles_title ON articles(title);
                """
            )
            await db.commit()

    async def seen(self, url: str) -> bool:
        key = dedup_key(url)
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT 1 FROM articles WHERE url=?", (key,))
            return await cur.fetchone() is not None

    async def save_article(self, article, message_id: int | None) -> None:
        key = dedup_key(article.url)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO articles(url,title,source,published_at,posted_at,telegram_message_id)"
                " VALUES(?,?,?,?,?,?)",
                (
                    key,
                    article.title,
                    article.source,
                    article.published_at,
                    datetime.now(timezone.utc).isoformat(),
                    message_id,
                ),
            )
            await db.commit()

    async def count_posts(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM articles")
            return (await cur.fetchone())[0]

    async def search(self, query: str, limit: int = 10):
        pattern = f"%{query}%"
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT title,source,url,posted_at FROM articles"
                " WHERE title LIKE ? OR source LIKE ? ORDER BY id DESC LIMIT ?",
                (pattern, pattern, limit),
            )
            return await cur.fetchall()

    async def get_state(self, key: str):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT value FROM state WHERE key=?", (key,))
            row = await cur.fetchone()
            return row[0] if row else None

    async def set_state(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO state(key,value) VALUES(?,?)", (key, value)
            )
            await db.commit()
