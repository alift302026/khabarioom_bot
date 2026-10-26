"""Offline tests for the one-shot sending tool (tools/send_one_news.py)."""

import importlib.util
from pathlib import Path

import pytest

from conftest import FakeBot, make_settings, run

TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "send_one_news.py"
_spec = importlib.util.spec_from_file_location("send_one_news", TOOL_PATH)
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)

import main as main_module  # noqa: E402
from database import Database  # noqa: E402
from models import Article  # noqa: E402


class StubManager:
    def __init__(self, items):
        self._items = items

    async def collect(self):
        return list(self._items)


def patch_enrich(monkeypatch):
    async def fake_enrich(article, settings):
        return article

    monkeypatch.setattr(main_module, "enrich", fake_enrich)
    monkeypatch.setattr(tool, "enrich", fake_enrich)


def make_db(settings):
    db = Database(settings.database_path)
    run(db.init())
    return db


def test_missing_token_exits_with_message(tmp_path, monkeypatch):
    make_settings(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    with pytest.raises(SystemExit) as excinfo:
        run(tool.run_once(["--dry-run"]))
    assert "TELEGRAM_BOT_TOKEN" in str(excinfo.value)


def test_dry_run_previews_without_saving_or_sending(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    article = Article("منبع", "تیتر خبر آزمایشی", "https://example.com/news-1", "متن خبر")
    monkeypatch.setattr(tool, "SourceManager", lambda s: StubManager([article]))
    patch_enrich(monkeypatch)
    db = make_db(settings)

    result = run(tool.run_once(["--dry-run", "--force"]))

    assert "DRY-RUN" in result
    assert "تیتر خبر آزمایشی" in result
    assert run(db.count_posts()) == 0  # nothing recorded, nothing sent


def test_real_send_publishes_one_article(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    article = Article("منبع", "تیتر خبر آزمایشی", "https://example.com/news-2", "متن خبر")
    monkeypatch.setattr(tool, "SourceManager", lambda s: StubManager([article]))
    patch_enrich(monkeypatch)
    bot = FakeBot()
    monkeypatch.setattr("telegram.Bot", lambda token: bot)
    db = make_db(settings)

    result = run(tool.run_once(["--force"]))

    assert result.startswith("SENT:")
    assert len(bot.sent_messages) == 1
    assert "تیتر خبر آزمایشی" in bot.sent_messages[0]
    assert run(db.count_posts()) == 1
    assert run(db.seen("https://example.com/news-2")) is True


def test_skips_already_seen_and_reports_no_new_article(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    article = Article("منبع", "تیتر تکراری", "https://example.com/news-3", "متن")
    monkeypatch.setattr(tool, "SourceManager", lambda s: StubManager([article]))
    patch_enrich(monkeypatch)
    bot = FakeBot()
    monkeypatch.setattr("telegram.Bot", lambda token: bot)
    db = make_db(settings)
    run(db.save_article(article, 1))

    result = run(tool.run_once(["--force"]))

    assert result.startswith("NO_NEW_ARTICLE")
    assert bot.sent_messages == []
