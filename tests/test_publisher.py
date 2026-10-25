"""Tests for caption building, HTML escaping, splitting and priority flags."""

from publisher import (
    MESSAGE_LIMIT,
    PHOTO_CAPTION_LIMIT,
    build_caption,
    build_message_parts,
    is_priority,
    split_text,
)

from models import Article


class FakeSettings:
    def __init__(self, **overrides):
        self.max_message_chars = 3900
        self.copy_full_article = False
        self.signature = "@khabarioom"
        self.add_source_link = False
        for key, value in overrides.items():
            setattr(self, key, value)


def make_article(**overrides):
    defaults = dict(
        source="منبع",
        title="عنوان خبر",
        url="https://example.com/a",
        text="پاراگراف اول خبر.\nپاراگراف دوم خبر.",
    )
    defaults.update(overrides)
    return Article(**defaults)


def test_caption_escapes_html_from_feed_content():
    article = make_article(title='خبر <b>مهم</b> & "نقل"', text="متن & نمونه")
    caption = build_caption(article, FakeSettings())
    assert "&lt;b&gt;مهم&lt;/b&gt;" in caption
    assert "متن &amp; نمونه" in caption
    assert "خبر <b>مهم</b>" not in caption  # raw feed markup must not survive


def test_title_is_truncated_to_bound_length():
    article = make_article(title="کلمه " * 200)
    parts = build_message_parts(article, FakeSettings(max_message_chars=3900))
    assert len(parts) == 1
    assert len(parts[0]) < 3900
    assert "…" in parts[0]


def test_single_part_when_short():
    article = make_article()
    parts = build_message_parts(article, FakeSettings())
    assert len(parts) == 1
    assert parts[0].startswith("📰 <b>عنوان خبر</b>")
    assert parts[0].endswith("@khabarioom")
    assert "#خبر" in parts[0]  # default hashtags present


def test_source_link_included_only_when_enabled():
    article = make_article(url="https://example.com/a?x=1&y=2")
    without = build_caption(article, FakeSettings(add_source_link=False))
    with_link = build_caption(article, FakeSettings(add_source_link=True))
    assert "منبع" not in without
    assert "🔗 منبع: https://example.com/a?x=1&amp;y=2" in with_link


def test_first_part_respects_photo_caption_limit():
    article = make_article(text="کلمه " * 400)
    settings = FakeSettings(max_message_chars=3900)
    parts = build_message_parts(article, settings, first_part_limit=PHOTO_CAPTION_LIMIT)
    assert len(parts) > 1
    assert all(len(part) <= 3900 for part in parts)
    assert len(parts[0]) <= PHOTO_CAPTION_LIMIT
    assert all(part.endswith("@khabarioom") for part in parts)


def test_all_parts_remain_valid_standalone_html():
    article = make_article(text="پاراگراف تست.\n" + "جملهٔ نمونه برای بدنه خبر. " * 300)
    parts = build_message_parts(
        article, FakeSettings(max_message_chars=500), first_part_limit=PHOTO_CAPTION_LIMIT
    )
    assert len(parts) > 3
    for part in parts:
        if "<b>" in part:  # only the first part carries the title markup
            assert part.count("<b>") == part.count("</b>")
            body_after_header = part.split("</b>", 1)[1]
            assert "<" not in body_after_header.split("@khabarioom")[0]
        else:
            # continuation parts contain escaped text only, never raw tags
            assert "<" not in part


def test_no_content_lost_when_copying_full_article():
    article = make_article(text="شروع " + "کلمه " * 900 + " پایان")
    settings = FakeSettings(max_message_chars=600, copy_full_article=True)
    parts = build_message_parts(article, settings)
    assert "شروع" in parts[0]
    assert "پایان" in parts[-1]
    # every word of the original text survives the split
    joined = " ".join(
        part.split("\n\n@khabarioom")[0] for part in parts
    ).replace("📰 <b>عنوان خبر</b>", "")
    for word in ("کلمه", "پایان", "شروع"):
        assert word in joined


def test_excerpt_mode_bounds_the_body():
    article = make_article(text="شروع " + "کلمه " * 900 + " پایان")
    parts = build_message_parts(article, FakeSettings(max_message_chars=600))
    # default (COPY_FULL_ARTICLE=false) keeps only a bounded excerpt
    assert all("پایان" not in part for part in parts)


def test_split_text_basic():
    chunks = split_text("aaaa bbbb cccc dddd", 10)
    assert all(len(chunk) <= 10 for chunk in chunks)
    assert " ".join(chunks) == "aaaa bbbb cccc dddd"


def test_split_text_empty_returns_empty_list():
    assert split_text("", 100) == []


def test_split_text_tiny_limit_does_not_hang():
    chunks = split_text("abcdef", 2)
    assert "".join(chunks) == "abcdef"


def test_priority_word_boundary():
    assert is_priority(make_article(title="جنگ و صلح")) is True
    assert is_priority(make_article(title="توافق هسته‌ای reached")) is True
    assert is_priority(make_article(title="تحریم.")) is True
    assert is_priority(make_article(title="جنگل در شمال کشور")) is False
    assert is_priority(make_article(title="خبر ورزشی")) is False


def test_priority_checks_title_and_text():
    assert is_priority(make_article(title="خبر عادی", text="متن دربارهٔ برجام")) is True


def test_copy_full_article_uses_whole_text():
    article = make_article(text="خط یک\nخط دو\nخط سه")
    caption = build_caption(article, FakeSettings(copy_full_article=True))
    assert "خط یک" in caption and "خط سه" in caption
    short = build_caption(article, FakeSettings(copy_full_article=False))
    assert "خط سه" not in short


def test_short_text_is_not_trimmed_by_excerpt_logic():
    article = make_article(text="متن کوتاه")
    caption = build_caption(article, FakeSettings())
    assert "متن کوتاه" in caption


def test_message_limit_matches_telegram_bound():
    assert PHOTO_CAPTION_LIMIT == 1024
    assert MESSAGE_LIMIT == 4096
