import html
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

TEHRAN = ZoneInfo("Asia/Tehran")
TEHRAN_LAT = 35.6892
TEHRAN_LON = 51.3890
TIMEOUT = 15

# Original paraphrases inspired by philosophical traditions; not presented as
# verbatim quotations. Source names are intentionally stated conservatively.
WISDOM = [
    ("رواقی‌گری", "روی آنچه در اختیار توست تمرکز کن؛ باقی را با سنجیدگی بپذیر.", "برداشت آزاد از آموزه‌های اپیکتتوس، «راهنمای زندگی»"),
    ("فلسفهٔ یونان", "پرسش دقیق، آغاز فهم دقیق‌تر است.", "بازنویسی معاصر از سنت گفت‌وگوی سقراطی؛ نه نقل‌قول مستقیم"),
    ("فلسفهٔ شرق", "آرامش، بی‌تفاوتی نیست؛ دیدن روشنِ موقعیت پیش از واکنش است.", "برداشت آزاد از سنت‌های تأملی شرق؛ نه نقل‌قول مستقیم"),
    ("اسطوره و خرد", "قهرمانی فقط پیروزی نیست؛ شناختن حد توان و مسئولیت خویش هم هست.", "برداشت امروزی از مضمون‌های اسطوره‌های یونانی؛ نه نقل‌قول مستقیم"),
    ("فلسفهٔ اخلاق", "پیش از داوری، میان واقعیت، برداشت و شایعه فرق بگذار.", "توصیهٔ تحریریهٔ خبریوم؛ نه نقل‌قول تاریخی"),
]


def _find_assets(payload):
    found = {}
    def walk(node):
        if isinstance(node, dict):
            asset_id = node.get("assetId") or node.get("asset_id") or node.get("id")
            price = node.get("price")
            if asset_id and price is not None:
                found[str(asset_id).lower()] = node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(payload)
    return found


def _fmt_toman(value):
    try:
        return f"{int(float(value)):,}".replace(",", "٬") + " تومان"
    except (ValueError, TypeError):
        return "در دسترس نیست"


async def market_report():
    api_key = os.getenv("ARZHAAM_API_KEY", "").strip()
    values = {}
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
                response = await client.get(
                    "https://arzhaam.ir/api/rates/latest",
                    headers={"X-App-Key": api_key},
                )
                response.raise_for_status()
                assets = _find_assets(response.json())
            for key, aliases in {
                "دلار آزاد": ("usd",),
                "طلای ۱۸ عیار": ("gold_18",),
                "بیت‌کوین": ("btc",),
                "سکه امامی": ("coin_emami",),
                "طلای آب‌شده": ("abshodeh",),
            }.items():
                asset = next((assets[a] for a in aliases if a in assets), None)
                values[key] = _fmt_toman(asset.get("price")) if asset else "در دسترس نیست"
        except Exception as exc:
            print("[MARKET DATA ERROR]", exc)
    else:
        print("[MARKET DATA] ARZHAAM_API_KEY is not configured")

    oil = "در دسترس نیست"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            response = await client.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/CL=F",
                params={"range": "1d", "interval": "1d"},
                headers={"User-Agent": "Mozilla/5.0 KhabarioomBot/1.0"},
            )
            response.raise_for_status()
            chart = response.json()["chart"]["result"][0]
            price = chart["meta"].get("regularMarketPrice")
            if price is not None:
                oil = f"{float(price):,.2f} دلار"
    except Exception as exc:
        print("[OIL DATA ERROR]", exc)

    names = ["دلار آزاد", "طلای ۱۸ عیار", "بیت‌کوین", "نفت خام WTI", "سکه امامی", "طلای آب‌شده"]
    lines = []
    for name in names:
        value = oil if name == "نفت خام WTI" else values.get(name, "دادهٔ قیمت تنظیم نشده")
        lines.append(f"• {name}: {value}")
    stamp = datetime.now(TEHRAN).strftime("%Y/%m/%d - %H:%M")
    return "📊 <b>گزارش روزانهٔ بازار</b>\n\n" + "\n".join(lines) + f"\n\n🕒 به‌روزرسانی: {stamp} به وقت تهران\n@khabarioom"


async def weather_report():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": TEHRAN_LAT,
                "longitude": TEHRAN_LON,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                "timezone": "Asia/Tehran",
                "forecast_days": 1,
            },
        )
        response.raise_for_status()
        data = response.json()
    current = data.get("current", {})
    daily = data.get("daily", {})
    temp = current.get("temperature_2m")
    low = (daily.get("temperature_2m_min") or [None])[0]
    high = (daily.get("temperature_2m_max") or [None])[0]
    humidity = current.get("relative_humidity_2m")
    wind = current.get("wind_speed_10m")
    def value(v, suffix=""):
        return "نامشخص" if v is None else f"{v}{suffix}"
    stamp = datetime.now(TEHRAN).strftime("%Y/%m/%d")
    return (
        f"🌤 <b>آب‌وهوای تهران | {stamp}</b>\n\n"
        f"• دمای فعلی: {value(temp, '°C')}\n"
        f"• کمینه / بیشینهٔ امروز: {value(low, '°C')} / {value(high, '°C')}\n"
        f"• رطوبت: {value(humidity, '%')}\n"
        f"• سرعت باد: {value(wind, ' km/h')}\n\n@khabarioom"
    )


def wisdom_report():
    day = datetime.now(TEHRAN).timetuple().tm_yday
    topic, line, attribution = WISDOM[(day - 1) % len(WISDOM)]
    return (
        f"🧠 <b>اندیشهٔ روز | {html.escape(topic)}</b>\n\n"
        f"«{html.escape(line)}»\n\n"
        f"<i>{html.escape(attribution)}</i>\n\n@khabarioom"
    )


async def send_weather(context):
    try:
        await context.bot.send_message(
            context.application.bot_data["settings"].channel_id,
            await weather_report(),
            parse_mode="HTML",
        )
    except Exception as exc:
        print("[WEATHER REPORT ERROR]", exc)


async def send_market(context):
    try:
        await context.bot.send_message(
            context.application.bot_data["settings"].channel_id,
            await market_report(),
            parse_mode="HTML",
        )
    except Exception as exc:
        print("[MARKET REPORT ERROR]", exc)


async def send_wisdom(context):
    try:
        await context.bot.send_message(
            context.application.bot_data["settings"].channel_id,
            wisdom_report(),
            parse_mode="HTML",
        )
    except Exception as exc:
        print("[WISDOM REPORT ERROR]", exc)
