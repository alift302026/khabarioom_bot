"""Send one of the daily reports (weather/market/wisdom) to the channel, now.

Useful for:

* a quick owner-run live check of a single report, and
* serverless deployments (e.g. GitHub Actions cron) that trigger reports at
  their scheduled Tehran times instead of keeping ``main.py`` running.

Examples:

    python tools/send_report.py weather          # send the weather report
    python tools/send_report.py market --dry-run # print the report, send nothing
    python tools/send_report.py all              # send all three reports
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Awaitable, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import daily_reports as dr  # noqa: E402

from config import get_settings  # noqa: E402

ReportBuilder = Callable[[], Awaitable[str]]


async def _weather() -> str:
    return await dr.weather_report()


async def _market() -> str:
    return await dr.market_report()


async def _wisdom() -> str:
    return dr.wisdom_report()


REPORTS: dict[str, ReportBuilder] = {
    "weather": _weather,
    "market": _market,
    "wisdom": _wisdom,
}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send a daily report to the channel (or preview it)."
    )
    parser.add_argument(
        "report",
        choices=[*REPORTS.keys(), "all"],
        help="Which report to send ('all' sends the three reports in order).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the report text without contacting Telegram.",
    )
    return parser


async def _build_report(name: str) -> str:
    return await REPORTS[name]()


async def run_once(argv: list[str] | None = None) -> str:
    """Run one report send/preview pass. Returns a human-readable result."""
    args = build_arg_parser().parse_args(argv)
    names = list(REPORTS.keys()) if args.report == "all" else [args.report]
    settings = get_settings()
    if not args.dry_run and not settings.bot_token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is missing. Configure it in your local .env first."
        )

    texts: list[str] = []
    for name in names:
        texts.append(await _build_report(name))

    if args.dry_run:
        header = f"DRY-RUN: {len(texts)} report(s) would be sent:"
        return header + "\n\n" + "\n\n=====\n\n".join(texts)

    # Lazy import so --dry-run never even constructs a Bot object.
    from telegram import Bot

    bot = Bot(settings.bot_token)
    for name, text in zip(names, texts):
        await bot.send_message(
            settings.channel_id, text, parse_mode="HTML"
        )
    return f"SENT report(s): {', '.join(names)}"


def main() -> None:
    print(asyncio.run(run_once()))


if __name__ == "__main__":
    main()
