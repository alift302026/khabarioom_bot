"""Khabarioom Telegram news bot — entry point, scheduling and admin commands."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from telegram.ext import Application, CommandHandler

from config import get_settings
from database import Database, normalize_url
from daily_reports import send_market, send_weather, send_wisdom
from extractor import enrich
from publisher import build_message_parts, is_priority
from sources import SourceManager

LOGGER = logging.getLogger("khabarioom")

PROMO = (
    "📣 <b>Khabarioom</b>\n\n"
    "اگر این کانال برایتان مفید است، آن را به دوستانتان معرفی کنید "
    "تا خبرهای تازه را سریع‌تر دنبال کنند. 📰✨\n\n@khabarioom"
)

LAST_PRIORITY_PIN_KEY = "last_priority_pin"


def is_quiet_hours(settings, now: datetime | None = None) -> bool:
    """Quiet period is 01:00–07:00 in the configured (Tehran) timezone."""
    now = now or datetime.now(ZoneInfo(settings.timezone))
    return 1 <= now.hour < 7


def is_admin(update, settings) -> bool:
    user = update.effective_user
    return bool(user and user.id in settings.admin_user_ids)


async def _maybe_pin(bot, db, settings, message_id: int) -> None:
    """Pin a priority message, respecting the configured cooldown.

    Pin failures (for example missing pin permission) are logged and never
    interrupt the bot.
    """
    last = await db.get_state(LAST_PRIORITY_PIN_KEY)
    can_pin = True
    if last:
        try:
            previous = datetime.fromisoformat(last)
            can_pin = (
                datetime.now(timezone.utc) - previous
                >= timedelta(hours=settings.pin_cooldown_hours)
            )
        except (ValueError, TypeError):
            can_pin = True
    if not can_pin:
        return
    try:
        await bot.pin_chat_message(
            settings.channel_id, message_id, disable_notification=True
        )
        await db.set_state(
            LAST_PRIORITY_PIN_KEY, datetime.now(timezone.utc).isoformat()
        )
    except Exception as exc:
        LOGGER.warning("Pin failed (continuing without pin): %s", exc)


async def _maybe_promo(bot, db, settings) -> None:
    if not settings.promo_every_n_posts:
        return
    try:
        count = await db.count_posts()
        if count % settings.promo_every_n_posts == 0:
            await bot.send_message(
                settings.channel_id, PROMO, parse_mode="HTML"
            )
    except Exception as exc:
        LOGGER.warning("Promo message failed: %s", exc)


async def publish(bot, db, settings, article) -> bool:
    """Publish one article to the channel. Returns True when it was sent."""
    if not article.url:
        return False
    url = normalize_url(article.url) or article.url.strip()
    if await db.seen(url):
        return False
    article.url = url

    # Keyword heuristic only — not independent verification of breaking news.
    pre_priority = is_priority(article)
    if is_quiet_hours(settings) and not pre_priority:
        LOGGER.info("Skipped during quiet hours: %s", url)
        return False

    article = await enrich(article, settings)
    priority = pre_priority or is_priority(article)
    parts = build_message_parts(
        article,
        settings,
        first_part_limit=1024
        if (settings.send_images and article.image_url)
        else None,
    )

    try:
        sent = None
        if settings.send_images and article.image_url:
            try:
                sent = await bot.send_photo(
                    settings.channel_id,
                    article.image_url,
                    caption=parts[0],
                    parse_mode="HTML",
                )
            except Exception as exc:
                LOGGER.warning(
                    "Photo send failed for %s, falling back to text: %s", url, exc
                )
        if sent is None:
            sent = await bot.send_message(
                settings.channel_id, parts[0], parse_mode="HTML"
            )
        # Record the article as soon as the first part is out, so a failure in
        # later parts cannot cause a duplicate post on the next cycle.
        await db.save_article(article, sent.message_id)
        for part in parts[1:]:
            try:
                await bot.send_message(
                    settings.channel_id, part, parse_mode="HTML"
                )
            except Exception as exc:
                LOGGER.error("Continuation part failed for %s: %s", url, exc)
    except Exception as exc:
        LOGGER.error("Publish failed for %s: %s", url, exc)
        return False

    if priority:
        await _maybe_pin(bot, db, settings, sent.message_id)
    await _maybe_promo(bot, db, settings)
    return True


async def cycle(context):
    data = context.application.bot_data
    settings, db, manager = data["settings"], data["db"], data["manager"]
    try:
        items = await manager.collect()
    except Exception as exc:
        LOGGER.error("Source collection failed: %s", exc)
        return
    seen_this_cycle: set[str] = set()
    for article in items:
        key = normalize_url(article.url) if article.url else ""
        if not key or key in seen_this_cycle:
            continue
        seen_this_cycle.add(key)
        try:
            await publish(context.bot, db, settings, article)
        except Exception as exc:
            LOGGER.error("Unexpected publish error for %s: %s", key, exc)


async def status(update, context):
    settings = context.application.bot_data["settings"]
    message = update.effective_message
    if not is_admin(update, settings) or message is None:
        return
    count = await context.application.bot_data["db"].count_posts()
    await message.reply_text(
        f"📊 خبرهای منتشرشده: {count}\n"
        f"⏱ بررسی: هر {settings.fetch_interval_minutes} دقیقه"
    )


async def search(update, context):
    settings = context.application.bot_data["settings"]
    message = update.effective_message
    if not is_admin(update, settings) or message is None:
        return
    query = " ".join(context.args).strip()
    if not query:
        await message.reply_text("مثال: /search تحریم")
        return
    rows = await context.application.bot_data["db"].search(query)
    body = "\n\n".join(
        f"📰 {title}\n📌 {source}\n🔗 {url}" for title, source, url, _ in rows
    )
    await message.reply_text(
        (body or "نتیجه‌ای پیدا نشد.")[:3900], disable_web_page_preview=True
    )


async def test_post(update, context):
    settings = context.application.bot_data["settings"]
    message = update.effective_message
    if not is_admin(update, settings) or message is None:
        return
    try:
        sent = await context.bot.send_message(
            settings.channel_id,
            "🧪 <b>آزمون ربات خبریوم</b>\n\n"
            "ارسال پیام به کانال موفق است. این پیام آزمایشی است و خبر واقعی نیست.\n\n"
            "#آزمایش #خبریوم\n@khabarioom",
            parse_mode="HTML",
        )
        await message.reply_text(
            f"پیام آزمایشی به کانال ارسال شد. شناسه پیام: {sent.message_id}"
        )
    except Exception as exc:
        await message.reply_text(
            "ارسال آزمایشی ناموفق بود. دسترسی ادمین/ارسال پیام کانال و CHANNEL_ID را بررسی کنید."
        )
        LOGGER.error("Test post failed: %s", exc)


async def sources(update, context):
    settings = context.application.bot_data["settings"]
    message = update.effective_message
    if not is_admin(update, settings) or message is None:
        return
    try:
        cfg = context.application.bot_data["manager"].load_sources()
    except Exception as exc:
        await message.reply_text("خواندن فایل منابع ناموفق بود.")
        LOGGER.error("Sources command failed: %s", exc)
        return
    names = [
        item.get("name") for item in cfg.get("sources", []) if item.get("enabled", True)
    ]
    channels = [
        item.get("name")
        for item in cfg.get("telegram_channels", [])
        if item.get("enabled", True)
    ]
    await message.reply_text(
        "🌐 سایت‌ها:\n"
        + ("\n".join("• " + name for name in names) or "موردی ثبت نشده")
        + "\n\n📣 تلگرام:\n"
        + ("\n".join("• " + name for name in channels) or "موردی ثبت نشده")
    )


async def on_error(update, context):
    LOGGER.error("Update handling error: %s", context.error)


async def post_init(app):
    settings = get_settings()
    db = Database(settings.database_path)
    await db.init()
    app.bot_data.update(settings=settings, db=db, manager=SourceManager(settings))


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()
    if not settings.bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing")
    app = (
        Application.builder()
        .token(settings.bot_token)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("sources", sources))
    app.add_handler(CommandHandler("test", test_post))
    app.add_error_handler(on_error)
    app.job_queue.run_repeating(
        cycle,
        interval=settings.fetch_interval_minutes * 60,
        first=settings.fetch_interval_minutes * 60,
    )
    report_tz = ZoneInfo(settings.timezone)
    app.job_queue.run_daily(
        send_weather,
        time=datetime.strptime("07:15", "%H:%M").time().replace(tzinfo=report_tz),
    )
    app.job_queue.run_daily(
        send_market,
        time=datetime.strptime("08:00", "%H:%M").time().replace(tzinfo=report_tz),
    )
    app.job_queue.run_daily(
        send_wisdom,
        time=datetime.strptime("09:00", "%H:%M").time().replace(tzinfo=report_tz),
    )
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
