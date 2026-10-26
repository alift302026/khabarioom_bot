"""Caption/message building with safe HTML formatting.

Every dynamic string (title, body, URL) is HTML-escaped before it is embedded
into the caption, so feed content can neither break Telegram's HTML parser nor
inject markup. Messages are split at whitespace boundaries only, which keeps
every part valid standalone HTML because escaped body text contains no tags of
its own.
"""

from __future__ import annotations

import html
import re

from hashtags import make_hashtags

# Persian/Arabic script letter ranges, used for keyword boundary detection.
_LETTER_CLASS = "\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF"
_MAX_TITLE_CHARS = 200

# Message length limits imposed by Telegram Bot API.
PHOTO_CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096

# Priority keywords are a heuristic, not independent verification of breaking
# news. They must match on word boundaries so that e.g. "جنگل" (forest) does
# not trigger the "جنگ" (war) keyword.
PIN_KEYWORDS = [
    "جنگ ایران", "جنگ", "حمله به ایران", "حمله ایران", "تحریم ایران",
    "تحریم", "توافق هسته‌ای", "توافق هسته ای", "مذاکرات هسته‌ای",
    "مذاکرات هسته ای", "برجام", "آتش‌بس", "آتش بس",
]

_KEYWORD_PATTERNS = [
    re.compile(
        rf"(?:^|[^\{_LETTER_CLASS}]){re.escape(keyword)}(?:[^\{_LETTER_CLASS}]|$)"
    )
    for keyword in PIN_KEYWORDS
]


def clean_text(text: str | None) -> str:
    return "\n".join(
        line.strip() for line in (text or "").splitlines() if line.strip()
    )


def is_priority(article) -> bool:
    text = f"{article.title} {article.text}"
    return any(pattern.search(text) for pattern in _KEYWORD_PATTERNS)


def _two_paragraphs(text: str | None) -> str:
    normalized = clean_text(text)
    if not normalized:
        return ""
    paragraphs = [p.strip() for p in normalized.split("\n") if p.strip()]
    if len(paragraphs) > 1:
        return "\n\n".join(paragraphs[:2])
    # If extraction returned one large block, keep a bounded excerpt rather
    # than publishing an entire scraped article verbatim.
    single = paragraphs[0]
    if len(single) > 1800:
        single = single[:1800].rsplit(" ", 1)[0]
    return single


def split_text(text: str, max_chars: int) -> list[str]:
    """Split plain (already escaped) text at whitespace, never mid-word.

    Returns a list of chunks each at most ``max_chars`` long, or an empty
    list when ``text`` is empty.
    """
    if not text:
        return []
    max_chars = max(1, int(max_chars))
    chunks: list[str] = []
    remaining = text.strip()
    while len(remaining) > max_chars:
        cut = remaining.rfind("\n", 0, max_chars)
        if cut < max_chars // 2:
            cut = remaining.rfind(" ", 0, max_chars)
        if cut < max_chars // 2:
            cut = max_chars
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def build_caption(article, settings) -> str:
    """Single-part caption (kept for compatibility and simple previews)."""
    parts = build_message_parts(article, settings, forced_single=True)
    return parts[0]


def build_message_parts(
    article, settings, first_part_limit: int | None = None, forced_single: bool = False
) -> list[str]:
    """Return one or more standalone, HTML-valid message parts.

    ``first_part_limit`` should be ``PHOTO_CAPTION_LIMIT`` when the first part
    is going to be attached to a photo. The title, body and source URL are
    escaped, and the body is split only at whitespace, so no part can contain
    a broken tag.
    """
    max_chars = max(1, min(int(settings.max_message_chars), MESSAGE_LIMIT))
    first_limit = max(1, min(first_part_limit or max_chars, max_chars))

    raw_title = clean_text(article.title)
    if len(raw_title) > _MAX_TITLE_CHARS:
        raw_title = raw_title[: _MAX_TITLE_CHARS - 1].rstrip() + "…"
    title = html.escape(raw_title, quote=False)
    if settings.copy_full_article:
        body_source = clean_text(article.text)
    else:
        body_source = _two_paragraphs(article.text)
    body = html.escape(body_source, quote=False) or title

    hashtags = make_hashtags(article.title, body_source)
    signature = settings.signature
    source_link = (
        f"\n\n🔗 منبع: {html.escape(str(article.url), quote=False)}"
        if settings.add_source_link and article.url
        else ""
    )
    header = f"📰 <b>{title}</b>\n\n"
    first_footer = f"\n\n{hashtags}\n{signature}{source_link}"
    next_footer = f"\n\n{signature}"

    if forced_single:
        return [header + body + first_footer]
    if len(header + body + first_footer) <= first_limit:
        return [header + body + first_footer]

    first_budget = max(64, first_limit - len(header) - len(first_footer))
    next_budget = max(64, max_chars - len(next_footer))

    body_chunks: list[str] = []
    rest = body
    while rest.strip():
        budget = first_budget if not body_chunks else next_budget
        chunks = split_text(rest, budget)
        if not chunks:
            break
        body_chunks.append(chunks[0])
        # split_text strips each chunk, so consume exactly that prefix and
        # then skip the separator whitespace before the next chunk.
        rest = rest[len(chunks[0]) :].lstrip()
    if not body_chunks:
        body_chunks = [body[:first_budget]]

    parts = [header + body_chunks[0] + first_footer]
    parts.extend(chunk + next_footer for chunk in body_chunks[1:])
    return parts
