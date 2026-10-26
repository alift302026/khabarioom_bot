"""Application settings loaded from environment variables.

All values come from the process environment (optionally populated from a
local ``.env`` file by python-dotenv). Secrets such as ``TELEGRAM_BOT_TOKEN``
must only be provided through the environment and never committed to Git.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCES_FILE = str(REPO_ROOT / "sources.yaml")


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value is not None else default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_ints(name: str) -> list[int]:
    value = os.getenv(name, "") or ""
    return [int(item.strip()) for item in value.split(",") if item.strip().isdigit()]


@dataclass(frozen=True)
class Settings:
    bot_token: str
    channel_id: str
    admin_user_ids: list[int]
    fetch_interval_minutes: int
    promo_every_n_posts: int
    pin_cooldown_hours: int
    max_sources_per_cycle: int
    max_articles_per_source: int
    copy_full_article: bool
    max_message_chars: int
    signature: str
    add_source_link: bool
    send_images: bool
    database_path: str
    request_timeout: int
    user_agent: str
    timezone: str
    sources_file: str


def get_settings() -> Settings:
    """Build a Settings instance from the environment.

    Invalid numeric values silently fall back to their documented defaults so
    a single typo cannot crash the bot at import time.
    """
    return Settings(
        bot_token=_get_str("TELEGRAM_BOT_TOKEN", ""),
        channel_id=_get_str("CHANNEL_ID", "@khabarioom"),
        admin_user_ids=_csv_ints("ADMIN_USER_IDS"),
        fetch_interval_minutes=_get_int("FETCH_INTERVAL_MINUTES", 30),
        promo_every_n_posts=_get_int("PROMO_EVERY_N_POSTS", 20),
        pin_cooldown_hours=_get_int("PIN_COOLDOWN_HOURS", 10),
        max_sources_per_cycle=_get_int("MAX_SOURCES_PER_CYCLE", 50),
        max_articles_per_source=_get_int("MAX_ARTICLES_PER_SOURCE", 5),
        copy_full_article=_get_bool("COPY_FULL_ARTICLE", False),
        max_message_chars=_get_int("MAX_TELEGRAM_MESSAGE_CHARS", 3900),
        signature=_get_str("SIGNATURE", "@khabarioom"),
        add_source_link=_get_bool("ADD_SOURCE_LINK", False),
        send_images=_get_bool("SEND_IMAGES", True),
        database_path=_get_str("DATABASE_PATH", "data/khabarioom.sqlite3"),
        request_timeout=_get_int("REQUEST_TIMEOUT_SECONDS", 25),
        user_agent=_get_str("USER_AGENT", "KhabarioomNewsBot/1.0"),
        timezone=_get_str("TIMEZONE", "Asia/Tehran"),
        sources_file=_get_str("SOURCES_FILE", DEFAULT_SOURCES_FILE),
    )
