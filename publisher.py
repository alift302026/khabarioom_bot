from hashtags import make_hashtags

PIN_KEYWORDS = [
    "جنگ ایران", "جنگ", "حمله به ایران", "حمله ایران", "تحریم ایران",
    "تحریم", "توافق هسته‌ای", "توافق هسته ای", "مذاکرات هسته‌ای",
    "مذاکرات هسته ای", "برجام", "آتش‌بس", "آتش بس",
]


def clean_text(text):
    return "\n".join(line.strip() for line in (text or "").splitlines() if line.strip())


def is_priority(article):
    text = f"{article.title} {article.text}"
    return any(keyword in text for keyword in PIN_KEYWORDS)


def _two_paragraphs(text):
    normalized = clean_text(text)
    if not normalized:
        return ""
    paragraphs = [p.strip() for p in normalized.split("\n") if p.strip()]
    if len(paragraphs) > 1:
        return "\n\n".join(paragraphs[:2])
    # If extraction returned one large block, keep a bounded excerpt rather than
    # publishing an entire scraped article verbatim.
    return paragraphs[0][:1800].rsplit(" ", 1)[0]


def build_caption(article, settings):
    body = clean_text(article.text) if settings.copy_full_article else _two_paragraphs(article.text)
    body = body or article.title
    source_link = f"\n\n🔗 منبع: {article.url}" if settings.add_source_link else ""
    return (
        f"📰 <b>{article.title}</b>\n\n{body}\n\n"
        f"{make_hashtags(article.title, body)}\n{settings.signature}{source_link}"
    )


def split_text(text, max_chars=3900):
    chunks = []
    while len(text) > max_chars:
        cut = text.rfind("\n", 0, max_chars)
        cut = cut if cut >= max_chars // 2 else max_chars
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        chunks.append(text)
    return chunks
