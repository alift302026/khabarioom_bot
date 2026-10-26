"""Offline tests for the report-sending tool (tools/send_report.py)."""

import importlib.util
from pathlib import Path

import pytest

from conftest import FakeBot, make_settings, run

TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "send_report.py"
_spec = importlib.util.spec_from_file_location("send_report", TOOL_PATH)
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)


def test_missing_token_exits_with_message(tmp_path, monkeypatch):
    make_settings(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    with pytest.raises(SystemExit) as excinfo:
        run(tool.run_once(["wisdom"]))
    assert "TELEGRAM_BOT_TOKEN" in str(excinfo.value)


def test_wisdom_dry_run_works_offline_without_token(tmp_path, monkeypatch):
    make_settings(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    result = run(tool.run_once(["wisdom", "--dry-run"]))
    assert result.startswith("DRY-RUN")
    assert "اندیشهٔ روز" in result


def test_real_send_uses_html_parse_mode(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    bot = FakeBot()
    monkeypatch.setattr("telegram.Bot", lambda token: bot)
    result = run(tool.run_once(["wisdom"]))
    assert result.startswith("SENT report(s): wisdom")
    assert len(bot.sent_messages) == 1
    assert "اندیشهٔ روز" in bot.sent_messages[0]


def test_all_sends_three_reports(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)

    class MultiBot(FakeBot):
        async def send_message(self, chat_id, text, parse_mode=None, **kwargs):
            # 'all' also covers weather/market which need network; stub the
            # network-dependent builders so the test stays offline.
            return await super().send_message(
                chat_id, text, parse_mode=parse_mode, **kwargs
            )

    async def fake_weather():
        return "🌤 <b>آب‌وهوای تهران | تست</b>"

    async def fake_market():
        return "📊 <b>گزارش روزانهٔ بازار | تست</b>"

    monkeypatch.setattr(tool.dr, "weather_report", fake_weather)
    monkeypatch.setattr(tool.dr, "market_report", fake_market)
    bot = MultiBot()
    monkeypatch.setattr("telegram.Bot", lambda token: bot)

    result = run(tool.run_once(["all"]))
    assert result.startswith("SENT report(s): weather, market, wisdom")
    assert len(bot.sent_messages) == 3
