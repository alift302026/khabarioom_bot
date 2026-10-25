"""Tests for source fetching (RSS/website/Telegram) and error isolation."""

import yaml

import sources as sources_module
from sources import SourceManager, strip_html

from conftest import FakeResponse, make_settings, run

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title>
<item>
  <title>تیتر اول خبر</title>
  <link>https://example.com/news/1?utm_source=rss</link>
  <description>&lt;p&gt;خلاصهٔ خبر &amp; متن&lt;/p&gt;</description>
  <media:content xmlns:media="http://search.yahoo.com/mrss/" url="https://img.example.com/1.jpg"/>
  <pubDate>Sat, 24 Oct 2026 10:00:00 +0330</pubDate>
</item>
<item>
  <title></title>
  <link>https://example.com/news/2</link>
</item>
<item>
  <title>خبر بدون لینک</title>
</item>
<item>
  <title>تیتر سوم</title>
  <link>https://example.com/news/3</link>
  <media:content xmlns:media="http://search.yahoo.com/mrss/" url="https://img.example.com/3.jpg"/>
</item>
</channel></rss>""".encode("utf-8")

WEBSITE_FIXTURE = """
<html><body>
<a href="/relative/1">این تیتر به اندازهٔ کافی بلند است برای پذیرش</a>
<a href="https://example.com/2">تیتر دوم که طولانی است و پذیرفته می‌شود</a>
<a href="https://example.com/3">کوتاه</a>
<a href="javascript:void(0)">این هم تیتر بلند اما اسکریپتی است</a>
</body></html>
"""

TELEGRAM_FIXTURE = """
<html><body>
<div class="tgme_widget_message">
  <div class="tgme_widget_message_text">متن پیام اول کانال</div>
  <a class="tgme_widget_message_date" href="https://t.me/channel/11">۱۱</a>
  <div class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn.t.me/photo1.jpg')"></div>
</div>
<div class="tgme_widget_message">
  <div class="tgme_widget_message_text">پیام دوم</div>
</div>
</body></html>
"""


def make_manager(tmp_path, sources_cfg, **overrides):
    sources_file = tmp_path / "sources.yaml"
    sources_file.write_text(
        yaml.safe_dump(sources_cfg, allow_unicode=True), encoding="utf-8"
    )
    settings = make_settings(tmp_path, SOURCES_FILE=str(sources_file), **overrides)
    return SourceManager(settings)


def test_strip_html():
    assert strip_html("<p>سلام &amp; خداحافظ</p>") == "سلام & خداحافظ"
    assert strip_html(None) == ""
    assert strip_html("  متن   پیوسته  ") == "متن پیوسته"


def test_rss_parses_entries_and_media(tmp_path):
    manager = make_manager(
        tmp_path,
        {"sources": [{"name": "آزمون", "type": "rss", "url": "https://rss.test/feed"}]},
    )
    manager._get = lambda url: _async_response(FakeResponse(content=RSS_FIXTURE))
    articles = run(manager.rss({"name": "آزمون", "type": "rss", "url": "https://x"}))
    assert len(articles) == 2  # entry without title and without link are skipped
    first = articles[0]
    assert first.title == "تیتر اول خبر"
    assert first.source == "آزمون"
    assert first.image_url == "https://img.example.com/1.jpg"
    assert "خلاصهٔ خبر & متن" in first.text  # HTML stripped from summary
    assert first.published_at == "Sat, 24 Oct 2026 10:00:00 +0330"


def test_rss_respects_max_articles_per_source(tmp_path):
    manager = make_manager(
        tmp_path,
        {"sources": [{"name": "آزمون", "type": "rss", "url": "https://rss.test/feed"}]},
        MAX_ARTICLES_PER_SOURCE="1",
    )
    manager._get = lambda url: _async_response(FakeResponse(content=RSS_FIXTURE))
    articles = run(manager.rss({"name": "آزمون", "type": "rss", "url": "https://x"}))
    assert len(articles) == 1


def test_website_scraping(tmp_path):
    manager = make_manager(
        tmp_path,
        {"sources": [{"name": "سایت", "type": "website", "url": "https://site.test/"}]},
        MAX_ARTICLES_PER_SOURCE="5",
    )
    manager._get = lambda url: _async_response(FakeResponse(text=WEBSITE_FIXTURE))
    articles = run(
        manager.website({"name": "سایت", "type": "website", "url": "https://site.test/"})
    )
    hrefs = [article.url for article in articles]
    assert "https://site.test/relative/1" in hrefs  # relative link resolved
    assert "https://example.com/2" in hrefs
    assert all(len(article.title) >= 25 for article in articles)


def test_telegram_public_scraping(tmp_path):
    manager = make_manager(
        tmp_path,
        {"telegram_channels": [{"name": "کانال", "type": "telegram", "username": "channel"}]},
    )
    manager._get = lambda url: _async_response(FakeResponse(text=TELEGRAM_FIXTURE))
    articles = run(
        manager.telegram_public({"name": "کانال", "type": "telegram", "username": "@channel"})
    )
    assert len(articles) == 2
    assert articles[0].title.startswith("متن پیام اول")
    assert articles[0].url == "https://t.me/channel/11"
    assert articles[0].image_url == "https://cdn.t.me/photo1.jpg"
    assert articles[1].image_url is None


def test_collect_isolates_failing_source(tmp_path, monkeypatch):
    manager = make_manager(
        tmp_path,
        {
            "sources": [
                {"name": "خراب", "type": "rss", "url": "https://broken.test/rss"},
                {"name": "سالم", "type": "rss", "url": "https://good.test/rss"},
            ]
        },
    )

    async def fake_rss(src):
        if src["name"] == "خراب":
            raise RuntimeError("HTTP 500")
        return ["مقاله سالم"]

    monkeypatch.setattr(manager, "rss", fake_rss)
    results = run(manager.collect())
    assert results == ["مقاله سالم"]  # the broken source did not stop the cycle


def test_collect_skips_disabled_sources(tmp_path, monkeypatch):
    manager = make_manager(
        tmp_path,
        {
            "sources": [
                {"name": "خاموش", "type": "rss", "url": "https://x.test/rss", "enabled": False},
                {"name": "روشن", "type": "rss", "url": "https://y.test/rss"},
            ]
        },
    )
    called = []

    async def fake_rss(src):
        called.append(src["name"])
        return []

    monkeypatch.setattr(manager, "rss", fake_rss)
    run(manager.collect())
    assert called == ["روشن"]


def test_max_sources_per_cycle_rotates(tmp_path, monkeypatch):
    manager = make_manager(
        tmp_path,
        {
            "sources": [
                {"name": f"منبع {i}", "type": "rss", "url": f"https://{i}.test/rss"}
                for i in range(4)
            ]
        },
        MAX_SOURCES_PER_CYCLE="2",
    )
    seen = []

    async def fake_rss(src):
        seen.append(src["name"])
        return []

    monkeypatch.setattr(manager, "rss", fake_rss)
    run(manager.collect())
    run(manager.collect())
    assert sorted(seen) == [f"منبع {i}" for i in range(4)]  # all covered in 2 cycles
    assert len(seen) == 4  # two sources per cycle


def test_collect_with_unreadable_sources_file(tmp_path):
    settings = make_settings(tmp_path, SOURCES_FILE=str(tmp_path / "missing.yaml"))
    manager = SourceManager(settings)
    assert run(manager.collect()) == []


def test_collect_reports_unknown_type(tmp_path, monkeypatch):
    manager = make_manager(
        tmp_path,
        {"sources": [{"name": "ناشناس", "type": "mystery", "url": "https://x.test"}]},
    )
    results = run(manager.collect())  # must not raise
    assert results == []


async def _async_response(response):
    return response
