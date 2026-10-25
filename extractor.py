"""Fetch the article page and try to extract full text and an image."""

from __future__ import annotations

import logging

import httpx
import trafilatura
from bs4 import BeautifulSoup
from urllib.parse import urljoin

LOGGER = logging.getLogger("khabarioom.extractor")


async def enrich(article, settings):
    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        ) as client:
            response = await client.get(article.url)
            response.raise_for_status()
        page_html = response.text
        text = (
            trafilatura.extract(
                page_html,
                include_comments=False,
                include_tables=False,
                favor_precision=False,
                output_format="txt",
            )
            or article.text
        )
        soup = BeautifulSoup(page_html, "lxml")
        if not article.image_url:
            og = soup.find("meta", property="og:image")
            if og and og.get("content"):
                article.image_url = urljoin(article.url, og["content"])
            else:
                img = soup.find("img")
                if img and img.get("src"):
                    article.image_url = urljoin(article.url, img["src"])
        article.text = (text or article.text or "").strip()
    except Exception as exc:
        LOGGER.warning("Extraction failed for %s: %s", article.url, exc)
    return article
