"""Send fresh news item(s) to the channel, then exit.

This uses the exact same pipeline as the bot (sources -> dedup -> enrich ->
caption -> publish), but runs once instead of continuously. It is meant for:

* a quick owner-run live check on a machine where the real
  TELEGRAM_BOT_TOKEN is configured in .env, and
* serverless deployments (e.g. GitHub Actions cron) that call it on a
  schedule instead of keeping ``main.py`` running.

Examples:

    python tools/send_one_news.py                # send 1 fresh article
    python tools/send_one_news.py --max 5        # send up to 5 fresh articles
    python tools/send_one_news.py --dry-run      # preview only, send nothing
    python tools/send_one_news.py --force        # ignore Tehran quiet hours

Note: running it without --dry-run posts REAL message(s) to CHANNEL_ID.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow running as a plain script from anywhere: add the repo root to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as main_module  # noqa: E402
from config import get_settings  # noqa: E402
from database import Database, normalize_url  # noqa: E402
from extractor import enrich  # noqa: E402
from publisher import PHOTO_CAPTION_LIMIT, build_message_parts  # noqa: E402
from sources import SourceManager  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send fresh news item(s) to the channel (or preview them)."
    )
    parser.add_argument(
        "--max",
        type=int,
        default=1,
        help="Maximum number of fresh articles to send in this run (default 1).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print the first message without contacting Telegram.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore quiet hours (01:00-07:00 Tehran) for this run.",
    )
    return parser


async def run_once(argv: list[str] | None = None) -> str:
    """Run one fetch/send pass. Returns a human-readable result."""
    args = build_arg_parser().parse_args(argv)
    max_posts = max(1, args.max)
    settings = get_settings()
    if not args.dry_run and not settings.bot_token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is missing. Configure it in your local .env first."
        )

    db = Database(settings.database_path)
    await db.init()
    manager = SourceManager(settings)

    force_was_set = False
    if args.force:
        force_was_set = True
        original_quiet = main_module.is_quiet_hours
        main_module.is_quiet_hours = lambda s, now=None: False  # noqa: E731
    try:
        items = await manager.collect()
        fresh: list[tuple[object, str]] = []
        for article in items:
            url = normalize_url(article.url)
            if not url or await db.seen(url):
                continue
            fresh.append((article, url))

        if not fresh:
            return (
                "NO_NEW_ARTICLE: no fresh, publishable item was found"
                " (all seen, filtered, or skipped)."
            )

        if args.dry_run:
            article, url = fresh[0]
            article.url = url
            article = await enrich(article, settings)
            parts = build_message_parts(
                article,
                settings,
                first_part_limit=PHOTO_CAPTION_LIMIT
                if (settings.send_images and article.image_url)
                else None,
            )
            preview = "\n---\n".join(parts)
            return (
                f"DRY-RUN: {len(fresh)} candidate(s) found; the first would be"
                f" sent as {len(parts)} message part(s):\n\n{preview}"
            )

        # Lazy import so --dry-run never even constructs a Bot object.
        from telegram import Bot

        bot = Bot(settings.bot_token)
        sent_urls: list[str] = []
        for article, url in fresh[:max_posts]:
            article.url = url
            article = await enrich(article, settings)
            if await main_module.publish(bot, db, settings, article):
                sent_urls.append(url)
        if not sent_urls:
            return "NOTHING_SENT: candidates existed but publishing all failed."
        if len(sent_urls) == 1:
            return f"SENT: {sent_urls[0]}"
        return f"SENT {len(sent_urls)} article(s): " + ", ".join(sent_urls)
    finally:
        if force_was_set:
            main_module.is_quiet_hours = original_quiet


def main() -> None:
    print(asyncio.run(run_once()))


if __name__ == "__main__":
    main()
