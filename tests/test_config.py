"""Tests for config parsing (env vars, defaults, invalid values)."""

import os

from config import get_settings

from conftest import make_settings

_ALL_SETTINGS_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "CHANNEL_ID",
    "ADMIN_USER_IDS",
    "FETCH_INTERVAL_MINUTES",
    "PROMO_EVERY_N_POSTS",
    "PIN_COOLDOWN_HOURS",
    "MAX_SOURCES_PER_CYCLE",
    "MAX_ARTICLES_PER_SOURCE",
    "COPY_FULL_ARTICLE",
    "MAX_TELEGRAM_MESSAGE_CHARS",
    "SIGNATURE",
    "ADD_SOURCE_LINK",
    "SEND_IMAGES",
    "DATABASE_PATH",
    "REQUEST_TIMEOUT_SECONDS",
    "USER_AGENT",
    "TIMEZONE",
    "SOURCES_FILE",
    "ARZHAAM_API_KEY",
]


def test_documented_defaults_with_empty_environment(tmp_path, monkeypatch):
    for name in _ALL_SETTINGS_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)  # DATABASE_PATH default must not depend on cwd
    s = get_settings()
    assert s.bot_token == ""
    assert s.channel_id == "@khabarioom"
    assert s.admin_user_ids == []
    assert s.fetch_interval_minutes == 30
    assert s.promo_every_n_posts == 20
    assert s.pin_cooldown_hours == 10
    assert s.max_sources_per_cycle == 50
    assert s.max_articles_per_source == 5
    assert s.copy_full_article is False
    assert s.max_message_chars == 3900
    assert s.signature == "@khabarioom"
    assert s.add_source_link is False
    assert s.send_images is True
    assert s.request_timeout == 25
    assert s.timezone == "Asia/Tehran"
    assert s.sources_file.endswith("sources.yaml")
    assert os.path.exists(s.sources_file)


def test_csv_admin_ids(tmp_path):
    s = make_settings(tmp_path, ADMIN_USER_IDS="111, 222 ,abc,333")
    # 'abc' is skipped, valid ints kept
    assert s.admin_user_ids == [111, 222, 333]


def test_invalid_int_falls_back_to_default(tmp_path):
    s = make_settings(tmp_path, FETCH_INTERVAL_MINUTES="not-a-number")
    assert s.fetch_interval_minutes == 30


def test_bool_parsing(tmp_path):
    s = make_settings(
        tmp_path,
        COPY_FULL_ARTICLE="TRUE",
        SEND_IMAGES="0",
        ADD_SOURCE_LINK="on",
    )
    assert s.copy_full_article is True
    assert s.send_images is False
    assert s.add_source_link is True


def test_token_is_read_from_environment(tmp_path):
    s = make_settings(tmp_path, TELEGRAM_BOT_TOKEN="111:AAA")
    assert s.bot_token == "111:AAA"
