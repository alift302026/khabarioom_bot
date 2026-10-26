"""Shared test helpers: fake Telegram objects, fake HTTP responses, factories."""

from __future__ import annotations

import asyncio

import pytest

from config import get_settings


def run(coro):
    return asyncio.run(coro)


class FakeResponse:
    """Minimal httpx.Response stand-in."""

    def __init__(self, content=b"", text=None, status_code=200, json_data=None):
        if text is not None and isinstance(text, str) and not content:
            content = text.encode("utf-8")
        self.content = content
        self.text = text if text is not None else content.decode("utf-8", "replace")
        self.status_code = status_code
        self._json = json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP status {self.status_code}")

    def json(self):
        if self._json is None:
            raise ValueError("no JSON body in this fake response")
        return self._json


class FakeMessage:
    def __init__(self, message_id: int):
        self.message_id = message_id


class FakeBot:
    """Records calls; can be told to fail specific sends."""

    def __init__(self, chat_id="@khabarioom"):
        self.chat_id = chat_id
        self.sent_messages: list[str] = []
        self.sent_ids: list[int] = []
        self.sent_photos: list[tuple[str, str]] = []  # (image_url, caption)
        self.pinned: list[int] = []
        self._next_id = 100
        self.fail_photo: Exception | None = None
        self.fail_message_substrings: list[str] = []

    async def send_message(self, chat_id, text, parse_mode=None, **kwargs):
        for marker in self.fail_message_substrings:
            if marker in text:
                raise RuntimeError(f"forced failure for {marker!r}")
        self._next_id += 1
        self.sent_messages.append(text)
        self.sent_ids.append(self._next_id)
        return FakeMessage(self._next_id)

    async def send_photo(self, chat_id, photo, caption=None, parse_mode=None, **kwargs):
        if self.fail_photo is not None:
            raise self.fail_photo
        self._next_id += 1
        self.sent_photos.append((photo, caption or ""))
        self.sent_ids.append(self._next_id)
        return FakeMessage(self._next_id)

    async def pin_chat_message(self, chat_id, message_id, **kwargs):
        self.pinned.append(message_id)


class FakeUser:
    def __init__(self, user_id):
        self.id = user_id


class FakeChat:
    def __init__(self, chat_id):
        self.id = chat_id


class FakeEffectiveMessage:
    def __init__(self):
        self.replies: list[str] = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)
        return FakeMessage(1)


class FakeUpdate:
    def __init__(self, user_id=None):
        self.effective_user = FakeUser(user_id) if user_id is not None else None
        self.effective_message = FakeEffectiveMessage()


class FakeApplication:
    def __init__(self, bot_data):
        self.bot_data = bot_data


class FakeContext:
    def __init__(self, bot_data, args=None):
        self.application = FakeApplication(bot_data)
        self.bot = bot_data.get("bot")
        self.args = args or []


def make_settings(tmp_path, **overrides):
    """Build Settings from env overrides, isolated from the host environment."""
    import os

    from config import REPO_ROOT

    env = {
        "TELEGRAM_BOT_TOKEN": "123:TEST_TOKEN",
        "CHANNEL_ID": "@khabarioom",
        "ADMIN_USER_IDS": "111,222",
        "FETCH_INTERVAL_MINUTES": "30",
        "PROMO_EVERY_N_POSTS": "20",
        "PIN_COOLDOWN_HOURS": "10",
        "MAX_SOURCES_PER_CYCLE": "50",
        "MAX_ARTICLES_PER_SOURCE": "5",
        "COPY_FULL_ARTICLE": "false",
        "MAX_TELEGRAM_MESSAGE_CHARS": "3900",
        "SIGNATURE": "@khabarioom",
        "ADD_SOURCE_LINK": "false",
        "SEND_IMAGES": "true",
        "DATABASE_PATH": str(tmp_path / "test.sqlite3"),
        "REQUEST_TIMEOUT_SECONDS": "25",
        "USER_AGENT": "KhabarioomNewsBot/1.0",
        "TIMEZONE": "Asia/Tehran",
        "SOURCES_FILE": str(REPO_ROOT / "sources.yaml"),
        "ARZHAAM_API_KEY": "",
    }
    env.update(overrides)
    for name in list(os.environ):
        if name in env or name.startswith("ARZHAAM"):
            del os.environ[name]
    for name, value in env.items():
        os.environ[name] = value
    return get_settings()


@pytest.fixture()
def settings(tmp_path, monkeypatch):
    return make_settings(tmp_path)
