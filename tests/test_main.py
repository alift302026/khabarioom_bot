"""Tests for the publish flow, quiet hours, pin/promo logic and admin commands."""

import datetime as dt

import main as main_module
from database import Database
from models import Article

from conftest import FakeBot, FakeContext, FakeUpdate, make_settings, run


class StubEnricher:
    """Replace network enrichment with a no-op during tests."""

    def __enter__(self):
        self.original = main_module.enrich

        async def fake_enrich(article, settings):
            return article

        main_module.enrich = fake_enrich
        return self

    def __exit__(self, *args):
        main_module.enrich = self.original


def set_quiet_hours(active: bool):
    """Context manager forcing is_quiet_hours to a fixed value."""

    class Ctx:
        def __enter__(self):
            self.original = main_module.is_quiet_hours
            main_module.is_quiet_hours = lambda s, now=None: active  # noqa: E731
            return self

        def __exit__(self, *args):
            main_module.is_quiet_hours = self.original

    return Ctx()


def make_db(tmp_path):
    db = Database(str(tmp_path / "main.sqlite3"))
    run(db.init())
    return db


def make_job_context(settings, db, bot, manager):
    class FakeJobContext:
        pass

    context = FakeJobContext()
    context.bot = bot
    context.application = type("App", (), {})()
    context.application.bot_data = {
        "settings": settings,
        "db": db,
        "manager": manager,
    }
    return context


def test_is_quiet_hours_boundaries(tmp_path):
    settings = make_settings(tmp_path)
    tz = main_module.ZoneInfo(settings.timezone)

    def at(hour, minute=0):
        return dt.datetime(2026, 10, 25, hour, minute, tzinfo=tz)

    assert main_module.is_quiet_hours(settings, at(1, 0)) is True
    assert main_module.is_quiet_hours(settings, at(6, 59)) is True
    assert main_module.is_quiet_hours(settings, at(7, 0)) is False
    assert main_module.is_quiet_hours(settings, at(0, 59)) is False
    assert main_module.is_quiet_hours(settings, at(12, 0)) is False


def test_publish_sends_message_and_saves(tmp_path):
    settings = make_settings(tmp_path, SEND_IMAGES="false")
    db, bot = make_db(tmp_path), FakeBot()
    article = Article("منبع", "تیتر خبر عادی", "https://example.com/1", "متن خبر")
    with StubEnricher(), set_quiet_hours(False):
        assert run(main_module.publish(bot, db, settings, article)) is True
    assert len(bot.sent_messages) == 1
    assert run(db.count_posts()) == 1
    assert run(db.seen("https://example.com/1")) is True


def test_publish_skips_duplicates(tmp_path):
    settings = make_settings(tmp_path)
    db, bot = make_db(tmp_path), FakeBot()
    with StubEnricher(), set_quiet_hours(False):
        run(main_module.publish(bot, db, settings, Article("s", "تیتر", "https://example.com/1", "متن")))
    bot.sent_messages.clear()
    with StubEnricher(), set_quiet_hours(False):
        assert run(
            main_module.publish(bot, db, settings, Article("s", "تیتر", "https://example.com/1", "متن"))
        ) is False
    assert bot.sent_messages == []


def test_publish_matches_normalized_duplicates(tmp_path):
    settings = make_settings(tmp_path)
    db, bot = make_db(tmp_path), FakeBot()
    with StubEnricher(), set_quiet_hours(False):
        run(
            main_module.publish(
                bot, db, settings,
                Article("s", "تیتر", "https://example.com/1?utm_source=tg", "متن"),
            )
        )
    bot.sent_messages.clear()
    with StubEnricher(), set_quiet_hours(False):
        assert run(
            main_module.publish(bot, db, settings, Article("s", "تیتر", "https://EXAMPLE.com/1", "متن"))
        ) is False


def test_quiet_hours_skip_non_priority(tmp_path):
    settings = make_settings(tmp_path)
    db, bot = make_db(tmp_path), FakeBot()
    with StubEnricher(), set_quiet_hours(True):
        result = run(
            main_module.publish(bot, db, settings, Article("s", "خبر عادی", "https://example.com/q", "متن"))
        )
    assert result is False
    assert bot.sent_messages == []
    assert run(db.count_posts()) == 0  # not saved, retried after quiet hours


def test_quiet_hours_allows_priority(tmp_path):
    settings = make_settings(tmp_path)
    db, bot = make_db(tmp_path), FakeBot()
    with StubEnricher(), set_quiet_hours(True):
        result = run(
            main_module.publish(
                bot, db, settings, Article("s", "توافق هسته‌ای حاصل شد", "https://example.com/p", "متن")
            )
        )
    assert result is True
    assert len(bot.sent_messages) == 1


def test_priority_article_is_pinned(tmp_path):
    settings = make_settings(tmp_path, PIN_COOLDOWN_HOURS="10")
    db, bot = make_db(tmp_path), FakeBot()
    with StubEnricher(), set_quiet_hours(False):
        run(main_module.publish(bot, db, settings, Article("s", "جنگ و تحریم", "https://example.com/pr", "متن")))
    assert bot.pinned == [bot.sent_ids[0]]  # first sent message is pinned
    assert run(db.get_state("last_priority_pin")) is not None


def test_pin_respects_cooldown(tmp_path):
    settings = make_settings(tmp_path, PIN_COOLDOWN_HOURS="10")
    db, bot = make_db(tmp_path), FakeBot()
    recent = dt.datetime.now(dt.timezone.utc).isoformat()
    run(db.set_state("last_priority_pin", recent))
    with StubEnricher(), set_quiet_hours(False):
        run(main_module.publish(bot, db, settings, Article("s", "تحریم تازه", "https://example.com/c1", "متن")))
    assert bot.pinned == []  # pinned recently -> cooldown active


def test_pin_failure_does_not_break_publish(tmp_path):
    settings = make_settings(tmp_path)
    db = make_db(tmp_path)
    bot = FakeBot()

    async def fail_pin(chat_id, message_id, **kwargs):
        raise RuntimeError("no pin permission")

    bot.pin_chat_message = fail_pin
    with StubEnricher(), set_quiet_hours(False):
        assert run(
            main_module.publish(bot, db, settings, Article("s", "برجام", "https://example.com/pin", "متن"))
        ) is True
    assert len(bot.sent_messages) == 1
    assert run(db.count_posts()) == 1


def test_photo_failure_falls_back_to_text(tmp_path):
    settings = make_settings(tmp_path)
    db = make_db(tmp_path)
    bot = FakeBot()
    bot.fail_photo = RuntimeError("bad image url")
    with StubEnricher(), set_quiet_hours(False):
        ok = run(
            main_module.publish(
                bot, db, settings,
                Article(
                    "s", "تیتر خبر", "https://example.com/img", "متن",
                    image_url="https://img.example.com/x.jpg",
                ),
            )
        )
    assert ok is True
    assert bot.sent_photos == []
    assert len(bot.sent_messages) == 1
    assert run(db.count_posts()) == 1


def test_photo_success_uses_caption_limit(tmp_path):
    settings = make_settings(tmp_path)
    db = make_db(tmp_path)
    bot = FakeBot()
    long_text = "جملهٔ آزمایشی برای بدنهٔ خبر. " * 200
    with StubEnricher(), set_quiet_hours(False):
        run(
            main_module.publish(
                bot, db, settings,
                Article("s", "تیتر", "https://example.com/photo", long_text, image_url="https://img/1.jpg"),
            )
        )
    assert len(bot.sent_photos) == 1
    assert len(bot.sent_photos[0][1]) <= 1024  # photo caption fits Telegram limit
    assert len(bot.sent_messages) >= 1  # continuation parts sent as text
    assert run(db.count_posts()) == 1


def test_multipart_failure_still_records_article(tmp_path):
    settings = make_settings(
        tmp_path, MAX_TELEGRAM_MESSAGE_CHARS="250", SEND_IMAGES="false"
    )
    db = make_db(tmp_path)
    bot = FakeBot()
    sent_state = {"first_done": False}
    original_send = bot.send_message

    async def send_once(chat_id, text, parse_mode=None, **kwargs):
        if sent_state["first_done"]:
            raise RuntimeError("network down")
        sent_state["first_done"] = True
        return await original_send(chat_id, text, parse_mode=parse_mode, **kwargs)

    bot.send_message = send_once
    long_text = "\n\n".join(f"پاراگراف شمارهٔ {i} با متن آزمونی طولانی." for i in range(40))
    with StubEnricher(), set_quiet_hours(False):
        ok = run(
            main_module.publish(bot, db, settings, Article("s", "تیتر", "https://example.com/multi", long_text))
        )
    assert ok is True
    assert sent_state["first_done"] is True
    assert run(db.seen("https://example.com/multi")) is True  # no duplicate next cycle


def test_promo_after_n_posts(tmp_path):
    settings = make_settings(tmp_path, PROMO_EVERY_N_POSTS="1", SEND_IMAGES="false")
    db, bot = make_db(tmp_path), FakeBot()
    with StubEnricher(), set_quiet_hours(False):
        run(main_module.publish(bot, db, settings, Article("s", "تیتر", "https://example.com/promo", "متن")))
    assert any("Khabarioom" in message for message in bot.sent_messages[1:])


def test_cycle_deduplicates_within_cycle(tmp_path):
    settings = make_settings(tmp_path, SEND_IMAGES="false")
    db = make_db(tmp_path)
    bot = FakeBot()

    class StubManager:
        async def collect(self):
            return [
                Article("s", "تیتر یک", "https://example.com/dup", "متن"),
                Article("s", "تیتر یک", "https://example.com/dup", "متن"),
            ]

    context = make_job_context(settings, db, bot, StubManager())
    with StubEnricher(), set_quiet_hours(False):
        run(main_module.cycle(context))
    assert len(bot.sent_messages) == 1


def test_cycle_survives_collect_failure(tmp_path):
    settings = make_settings(tmp_path)
    db = make_db(tmp_path)

    class ExplodingManager:
        async def collect(self):
            raise RuntimeError("sources file broken")

    context = make_job_context(settings, db, FakeBot(), ExplodingManager())
    run(main_module.cycle(context))  # must not raise


# ---------------------------------------------------------------------------
# Admin commands
# ---------------------------------------------------------------------------


def make_command_context(tmp_path, bot=None):
    settings = make_settings(tmp_path)
    db = make_db(tmp_path)
    bot_data = {
        "settings": settings,
        "db": db,
        "bot": bot or FakeBot(),
        "manager": None,
    }
    return settings, db, bot_data


def test_status_requires_admin(tmp_path):
    settings, db, bot_data = make_command_context(tmp_path)
    context = FakeContext(bot_data)
    outsider = FakeUpdate(user_id=999)
    run(main_module.status(outsider, context))
    assert outsider.effective_message.replies == []
    insider = FakeUpdate(user_id=111)
    run(main_module.status(insider, context))
    assert "خبرهای منتشرشده" in insider.effective_message.replies[0]


def test_status_without_user_object_is_ignored(tmp_path):
    settings, db, bot_data = make_command_context(tmp_path)
    update = FakeUpdate(user_id=None)
    run(main_module.status(update, FakeContext(bot_data)))
    assert update.effective_message.replies == []


def test_search_command(tmp_path):
    settings, db, bot_data = make_command_context(tmp_path)
    run(db.save_article(Article("منبع", "خبر تحریم", "https://example.com/s1"), 1))
    context = FakeContext(bot_data, args=["تحریم"])
    update = FakeUpdate(user_id=111)
    run(main_module.search(update, context))
    assert "تحریم" in update.effective_message.replies[0]


def test_search_without_query_shows_usage(tmp_path):
    settings, db, bot_data = make_command_context(tmp_path)
    update = FakeUpdate(user_id=111)
    run(main_module.search(update, FakeContext(bot_data, args=[])))
    assert "مثال" in update.effective_message.replies[0]


def test_sources_command_lists_enabled_names(tmp_path):
    settings, db, bot_data = make_command_context(tmp_path)

    class StubManager:
        def load_sources(self):
            return {
                "sources": [
                    {"name": "ایرنا", "enabled": True},
                    {"name": "خاموش", "enabled": False},
                ],
                "telegram_channels": [],
            }

    bot_data["manager"] = StubManager()
    update = FakeUpdate(user_id=111)
    run(main_module.sources(update, FakeContext(bot_data)))
    reply = update.effective_message.replies[0]
    assert "ایرنا" in reply
    assert "خاموش" not in reply


def test_sources_command_reports_unreadable_file(tmp_path):
    settings, db, bot_data = make_command_context(tmp_path)

    class BrokenManager:
        def load_sources(self):
            raise FileNotFoundError("sources.yaml")

    bot_data["manager"] = BrokenManager()
    update = FakeUpdate(user_id=111)
    run(main_module.sources(update, FakeContext(bot_data)))
    assert "ناموفق" in update.effective_message.replies[0]


def test_test_command_success(tmp_path):
    settings, db, bot_data = make_command_context(tmp_path)
    update = FakeUpdate(user_id=111)
    run(main_module.test_post(update, FakeContext(bot_data)))
    assert "ارسال شد" in update.effective_message.replies[0]
    assert bot_data["bot"].sent_messages  # a test message was prepared


def test_test_command_failure_reports_error(tmp_path):
    settings, db, bot_data = make_command_context(tmp_path)
    failing_bot = FakeBot()
    failing_bot.fail_message_substrings = ["آزمون ربات خبریوم"]
    bot_data["bot"] = failing_bot
    update = FakeUpdate(user_id=111)
    run(main_module.test_post(update, FakeContext(bot_data)))
    assert "ناموفق" in update.effective_message.replies[0]


def test_test_command_requires_admin(tmp_path):
    settings, db, bot_data = make_command_context(tmp_path)
    update = FakeUpdate(user_id=999)
    run(main_module.test_post(update, FakeContext(bot_data)))
    assert update.effective_message.replies == []
    assert bot_data["bot"].sent_messages == []
