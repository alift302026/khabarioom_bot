"""Fetch articles from RSS feeds, websites and public Telegram channels.

Every source is processed independently: a failure in one source is logged
and never aborts the collection cycle.
"""

from __future__ import annotations

import logging
import re

import feedparser
import httpx
import yaml
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from models import Article

LOGGER = logging.getLogger("khabarioom.sources")


def strip_html(text: object) -> str:
    """Convert a possibly-HTML fragment into single-spaced plain text."""
    if not text:
        return ""
    return " ".join(
        BeautifulSoup(str(text), "html.parser").get_text(" ", strip=True).split()
    )


class SourceManager:
    def __init__(self, settings):
        self.s = settings
        self.headers = {"User-Agent": settings.user_agent}
        self._offset = 0

    def load_sources(self, path: str | None = None) -> dict:
        path = path or self.s.sources_file
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    async def _get(self, url: str) -> httpx.Response:
        async with httpx.AsyncClient(
            timeout=self.s.request_timeout,
            headers=self.headers,
            follow_redirects=True,
        ) as client:
            return await client.get(url)

    def _active_sources(self, cfg: dict) -> list[dict]:
        combined = list(cfg.get("sources", [])) + list(
            cfg.get("telegram_channels", [])
        )
        return [src for src in combined if src.get("enabled", True)]

    def _select_sources(self, cfg: dict) -> list[dict]:
        """Round-robin over active sources, at most ``max_sources_per_cycle``.

        With the default limit (>= number of sources) all active sources are
        returned every cycle in their declared order.
        """
        active = self._active_sources(cfg)
        limit = int(self.s.max_sources_per_cycle)
        if limit <= 0 or len(active) <= limit:
            return active
        rotated = active[self._offset :] + active[: self._offset]
        self._offset = (self._offset + limit) % len(active)
        return rotated[:limit]

    async def rss(self, src: dict) -> list[Article]:
        response = await self._get(src["url"])
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        out: list[Article] = []
        for entry in feed.entries[: self.s.max_articles_per_source]:
            title = strip_html(entry.get("title"))
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue
            image = None
            media_items = list(entry.get("media_content") or []) + list(
                entry.get("media_thumbnail") or []
            )
            for media in media_items:
                if isinstance(media, dict) and media.get("url"):
                    image = media["url"]
                    break
            out.append(
                Article(
                    src["name"],
                    title,
                    link,
                    strip_html(entry.get("summary")),
                    image,
                    entry.get("published"),
                )
            )
        return out

    async def website(self, src: dict) -> list[Article]:
        response = await self._get(src["url"])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        out: list[Article] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            title = " ".join(anchor.get_text(" ", strip=True).split())
            href = urljoin(src["url"], anchor["href"])
            if len(title) >= 25 and href.startswith("http") and href not in seen:
                seen.add(href)
                out.append(Article(src["name"], title, href))
            if len(out) >= self.s.max_articles_per_source:
                break
        return out

    async def telegram_public(self, src: dict) -> list[Article]:
        username = str(src["username"]).lstrip("@")
        url = f"https://t.me/s/{username}"
        response = await self._get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        out: list[Article] = []
        for message in soup.select(".tgme_widget_message")[
            -self.s.max_articles_per_source :
        ]:
            text_node = message.select_one(".tgme_widget_message_text")
            body = (
                text_node.get_text(" ", strip=True) if text_node else ""
            ).strip()
            if not body:
                continue
            anchor = message.select_one("a.tgme_widget_message_date")
            link = anchor.get("href") if anchor else url
            image = None
            media = message.select_one(".tgme_widget_message_photo_wrap")
            if media:
                match = re.search(
                    r"url\(['\"]?([^)'\"]+)", media.get("style", "")
                )
                if match:
                    image = match.group(1)
            out.append(Article(src["name"], body[:300], link, body, image))
        return out

    async def collect(self) -> list[Article]:
        try:
            cfg = self.load_sources()
        except (OSError, yaml.YAMLError) as exc:
            LOGGER.error("Cannot read sources configuration: %s", exc)
            return []
        results: list[Article] = []
        for src in self._select_sources(cfg):
            try:
                source_type = src.get("type")
                if source_type == "rss":
                    results += await self.rss(src)
                elif source_type == "website":
                    results += await self.website(src)
                elif source_type == "telegram":
                    results += await self.telegram_public(src)
                else:
                    LOGGER.warning(
                        "Unknown type %r for source %s",
                        source_type,
                        src.get("name"),
                    )
            except Exception as exc:
                LOGGER.warning("Source error (%s): %s", src.get("name"), exc)
        return results
