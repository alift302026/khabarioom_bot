from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from telegram.ext import Application, CommandHandler

from config import get_settings
from database import Database
from sources import SourceManager
from extractor import enrich
from publisher import build_caption, split_text, is_priority

PROMO = (
    "📣 <b>Khabarioom</b>\n\n"
    "اگر این کانال برایتان مفید است، آن را به دوستانتان معرفی کنید "
    "تا خبرهای تازه را سریع‌تر دنبال کنند. 📰✨\n\n@khabarioom"
)


def is_quiet_hours(settings):
    """Quiet period is 01:00–07:00 Tehran time."""
    now = datetime.now(ZoneInfo(settings.timezone))
    return 1 <= now.hour < 7


async def publish(bot, db, settings, article):
    if not article.url or await db.seen(article.url):
        return False

    priority = is_priority(article)
    # This is a keyword heuristic, not independent verification of breaking news.
    if is_quiet_hours(settings) and not priority:
        return False

    article = await enrich(article, settings)
    parts = split_text(build_caption(article, settings), settings.max_message_chars)
    try:
        sent = None
        if settings.send_images and article.image_url:
            try:
                caption = parts[0]
                if len(caption) > 1024:
                    sent = await bot.send_message(
                        settings.channel_id, caption, parse_mode="HTML"
                    )
                else:
                    sent = await bot.send_photo(
                        settings.channel_id, article.image_url,
                        caption=caption, parse_mode="HTML"
                    )
            except Exception as exc:
                print("[PHOTO ERROR; sending text]", article.url, exc)
        if sent is None:
            sent = await bot.send_message(
                settings.channel_id, parts[0], parse_mode="HTML"
            )
        for part in parts[1:]:
            await bot.send_message(settings.channel_id, part, parse_mode="HTML")

        await db.save_article(article, sent.message_id)
        if priority:
            last = await db.get_state("last_priority_pin")
            can_pin = True
            if last:
                try:
                    previous = datetime.fromisoformat(last)
                    can_pin = datetime.now(timezone.utc) - previous >= timedelta(
                        hours=settings.pin_cooldown_hours
                    )
                except (ValueError, TypeError):
                    can_pin = True
            if can_pin:
                try:
                    await bot.pin_chat_message(
                        settings.channel_id, sent.message_id,
                        disable_notification=True
                    )
                    await db.set_state(
                        "last_priority_pin", datetime.now(timezone.utc).isoformat()
                    )
                except Exception as exc:
                    print("[PIN ERROR]", exc)

        count = await db.count_posts()
        if settings.promo_every_n_posts and count % settings.promo_every_n_posts == 0:
            await bot.send_message(settings.channel_id, PROMO, parse_mode="HTML")
        return True
    except Exception as exc:
        print("[PUBLISH ERROR]", article.url, exc)
        return False


async def cycle(context):
    settings = context.application.bot_data["settings"]
    db = context.application.bot_data["db"]
    manager = context.application.bot_data["manager"]
    items = await manager.collect()
    seen_this_cycle = set()
    for article in items:
        if article.url in seen_this_cycle:
            continue
        seen_this_cycle.add(article.url)
        await publish(context.bot, db, settings, article)


async def status(update, context):
    settings = context.application.bot_data["settings"]
    if not update.effective_user or update.effective_user.id not in settings.admin_user_ids:
        return
    count = await context.application.bot_data["db"].count_posts()
    await update.message.reply_text(
        f"📊 خبرهای منتشرشده: {count}\n"
        f"⏱ بررسی: هر {settings.fetch_interval_minutes} دقیقه"
    )


async def search(update, context):
    settings = context.application.bot_data["settings"]
    if not update.effective_user or update.effective_user.id not in settings.admin_user_ids:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("مثال: /search تحریم")
        return
    rows = await context.application.bot_data["db"].search(query)
    message = "\n\n".join(
        f"📰 {title}\n📌 {source}\n🔗 {url}"
        for title, source, url, _ in rows
    ) or "نتیجه‌ای پیدا نشد."
    await update.message.reply_text(message[:3900], disable_web_page_preview=True)


async def test_post(update, context):
    settings = context.application.bot_data["settings"]
    if not update.effective_user or update.effective_user.id not in settings.admin_user_ids:
        return
    try:
        sent = await context.bot.send_message(
            settings.channel_id,
            "🧪 <b>آزمون ربات خبریوم</b>\n\n"
            "ارسال پیام به کانال موفق است. این پیام آزمایشی است و خبر واقعی نیست.\n\n"
            "#آزمایش #خبریوم\n@khabarioom",
            parse_mode="HTML",
        )
        await update.message.reply_text(
            f"پیام آزمایشی به کانال ارسال شد. شناسه پیام: {sent.message_id}"
        )
    except Exception as exc:
        await update.message.reply_text(
            "ارسال آزمایشی ناموفق بود. دسترسی ادمین/ارسال پیام کانال و CHANNEL_ID را بررسی کنید."
        )
        print("[TEST POST ERROR]", exc)


async def sources(update, context):
    settings = context.application.bot_data["settings"]
    if not update.effective_user or update.effective_user.id not in settings.admin_user_ids:
        return
    cfg = context.application.bot_data["manager"].load_sources()
    names = [item.get("name") for item in cfg.get("sources", []) if item.get("enabled", True)]
    channels = [
        item.get("name") for item in cfg.get("telegram_channels", [])
        if item.get("enabled", True)
    ]
    await update.message.reply_text(
        "🌐 سایت‌ها:\n" + ("\n".join("• " + name for name in names) or "موردی ثبت نشده")
        + "\n\n📣 تلگرام:\n"
        + ("\n".join("• " + name for name in channels) or "موردی ثبت نشده")
    )


async def post_init(app):
    settings = get_settings()
    db = Database(settings.database_path)
    await db.init()
    app.bot_data.update(
        settings=settings, db=db, manager=SourceManager(settings)
    )


def main():
    settings = get_settings()
    if not settings.bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing")
    app = Application.builder().token(settings.bot_token).post_init(post_init).build()
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("sources", sources))
    app.add_handler(CommandHandler("test", test_post))
    app.job_queue.run_repeating(
        cycle, interval=settings.fetch_interval_minutes * 60, first=settings.fetch_interval_minutes * 60
    )
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
