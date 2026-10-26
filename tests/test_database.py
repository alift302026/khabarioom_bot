"""Tests for SQLite storage and URL de-duplication."""

from database import Database, dedup_key, normalize_url

from conftest import run


class Article:
    def __init__(self, url, title="t", source="s"):
        self.url = url
        self.title = title
        self.source = source
        self.published_at = None
        self.text = ""


def make_db(tmp_path):
    db = Database(str(tmp_path / "db.sqlite3"))
    run(db.init())
    return db


def test_normalize_url_basic():
    assert normalize_url("https://Example.com:443/a/?x=1#frag") == "https://example.com/a?x=1"
    assert normalize_url("http://example.com:80/x/") == "http://example.com/x"
    assert normalize_url("https://example.com") == "https://example.com/"
    assert normalize_url("  https://example.com/a  ") == "https://example.com/a"
    assert normalize_url("") == ""
    assert normalize_url(None) == ""


def test_normalize_url_drops_tracking_params():
    url = "https://news.ir/item/123?utm_source=telegram&id=77&fbclid=abc"
    assert normalize_url(url) == "https://news.ir/item/123?id=77"


def test_normalize_url_keeps_meaningful_query():
    url = "https://news.ir/item?id=77&lang=fa"
    assert normalize_url(url) == "https://news.ir/item?id=77&lang=fa"


def test_normalize_url_scheme_relative():
    assert normalize_url("//example.com/a") == "https://example.com/a"


def test_normalize_url_non_absolute_kept_as_is():
    assert normalize_url("t.me/s/channel") == "t.me/s/channel"


def test_dedup_key_falls_back_to_stripped_input():
    assert dedup_key("t.me/s/channel ") == "t.me/s/channel"


def test_save_and_seen(tmp_path):
    db = make_db(tmp_path)
    run(db.save_article(Article("https://example.com/a"), 10))
    assert run(db.seen("https://example.com/a")) is True
    assert run(db.seen("https://example.com/a")) is True


def test_seen_matches_normalized_variants(tmp_path):
    db = make_db(tmp_path)
    run(db.save_article(Article("https://example.com/a?utm_source=tg"), 10))
    assert run(db.seen("HTTPS://EXAMPLE.COM/a")) is True
    assert run(db.seen("https://example.com/a#top")) is True


def test_duplicate_insert_is_ignored(tmp_path):
    db = make_db(tmp_path)
    run(db.save_article(Article("https://example.com/a"), 10))
    run(db.save_article(Article("https://example.com/a"), 99))
    assert run(db.count_posts()) == 1


def test_count_and_search(tmp_path):
    db = make_db(tmp_path)
    run(db.save_article(Article("https://example.com/1", title="تحریم بانک"), 1))
    run(db.save_article(Article("https://example.com/2", title="ورزش"), 2))
    assert run(db.count_posts()) == 2
    rows = run(db.search("تحریم"))
    assert len(rows) == 1
    assert rows[0][0] == "تحریم بانک"


def test_state_roundtrip(tmp_path):
    db = make_db(tmp_path)
    assert run(db.get_state("missing")) is None
    run(db.set_state("key", "2026-01-01T00:00:00+00:00"))
    run(db.set_state("key", "2026-01-02T00:00:00+00:00"))
    assert run(db.get_state("key")) == "2026-01-02T00:00:00+00:00"


def test_init_creates_parent_directories(tmp_path):
    db_path = tmp_path / "nested" / "dir" / "db.sqlite3"
    db = Database(str(db_path))
    run(db.init())
    assert db_path.exists()
