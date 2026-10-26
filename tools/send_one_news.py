"""Send exactly one fresh news item to the channel, then exit.

This uses the exact same pipeline as the bot (sources -> dedup -> enrich ->
caption -> publish), but runs once instead of continuously.

Run on the machine where the real TELEGRAM_BOT_TOKEN is configured in .env:

    python tools/send_one_news.py             # send the first unseen article
    python tools/send_one_news.py --dry-run   # preview the caption, send nothing
    python tools/send_one_news.py --force     # ignore Tehran quiet hours (01-07)

Note: running it without --dry-run posts a REAL message to CHANNEL_ID.
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
        description="Send one fresh news item to the channel (or preview it)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print the message without contacting Telegram.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore quiet hours (01:00-07:00 Tehran) for this one send.",
    )
    return parser


async def run_once(argv: list[str] | None = None) -> str:
    """Run one fetch/send pass. Returns a human-readable result."""
    args = build_arg_parser().parse_args(argv)
    settings = get_settings()
    if not settings.bot_token:
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
        for article in items:
            url = normalize_url(article.url)
            if not url or await db.seen(url):
                continue
            article.url = url
            article = await enrich(article, settings)
            parts = build_message_parts(
                article,
                settings,
                first_part_limit=PHOTO_CAPTION_LIMIT
                if (settings.send_images and article.image_url)
                else None,
            )
            if args.dry_run:
                preview = "\n---\n".join(parts)
                return f"DRY-RUN: {len(parts)} message part(s) would be sent:\n\n{preview}"
            # Lazy import so --dry-run never even constructs a Bot object.
            from telegram import Bot

            sent = await main_module.publish(
                Bot(settings.bot_token), db, settings, article
            )
            if sent:
                return f"SENT: {article.url}"
        return (
            "NO_NEW_ARTICLE: no fresh, publishable item was found"
            " (all seen, filtered, or skipped)."
        )
    finally:
        if force_was_set:
            main_module.is_quiet_hours = original_quiet


def main() -> None:
    print(asyncio.run(run_once()))


if __name__ == "__main__":
    main()
