# راهنمای استقرار ۲۴/۷ خبریوم

ربات برای کار کردن وقتی سیستم شما خاموش است باید روی یک **سرور همیشه‌روشن** اجرا شود. سه راه در پیش رو دارید:

| گزینه | هزینه | کیفیت | مناسب برای |
|---|---|---|---|
| ۱. Railway | رایگان/ارزان | کامل (ربات دائمی + دستورات + گزارش‌ها) | **پیشنهادی** |
| ۲. VPS (سرور مجازی) | ماهانه | کامل + کنترل کامل | کسی که سرور دارد |
| ۳. GitHub Actions | رایگان | محدود (خبری هر ۳۰ دقیقه + گزارش‌ها؛ بدون دستورات) | شروع بدون هزینه |

قبل از هر کدام: ربات باید در کانال `@khabarioom` **ادمین** با دسترسی Post Messages (و برای پین، Pin Messages) باشد.

---

## گزینهٔ ۱ — Railway (پیشنهادی)

ربات به‌صورت یک فرایند دائمی اجرا می‌شود؛ همهٔ امکانات (دستورات `/status` و `/test` و…، ساعات سکوت، پین، گزارش‌های روزانه با ساعت تهران) فعال است.

1. در [railway.com](https://railway.com) وارد شوید (با GitHub).
2. **New Project → Deploy from GitHub repo** و ریپو `alift302026/khabarioom_bot` را انتخاب کنید (فایل‌های `Dockerfile` و `railway.toml` آماده‌اند؛ پایهٔ Docker: python:3.12-slim).
3. در تب **Variables** این متغیرها را بسازید:
   - `TELEGRAM_BOT_TOKEN` = توکن BotFather (به‌عنوان Secret نگه داشته می‌شود)
   - `CHANNEL_ID` = `@khabarioom`
   - `ADMIN_USER_IDS` = آیدی عددی شما
   - بقیه اختیاری‌اند (پیش‌فرض‌های `.env.example` خوب‌اند).
4. برای ماندگاری دیتابیس: در تب **Settings → Volumes** یک Volume بسازید و نقطهٔ اتصال (mount path) را `/data` بگذارید، سپس متغیر زیر را اضافه کنید:
   - `DATABASE_PATH` = `/data/khabarioom.sqlite3`

   بدون Volume، با هر استقرار مجدد، تاریخچهٔ خبرهای منتشرشده پاک می‌شود و خبرهای تکراری می‌روند.
5. **Deploy** بزنید و در تب Deployments لاگ را ببینید. خطای `TELEGRAM_BOT_TOKEN is missing` یعنی متغیرها ناقص‌اند.
6. در تلگرام به ربات `/test` بدهید؛ پاسخ «پیام آزمایشی به کانال ارسال شد» یعنی چرخهٔ کامل واقعاً کار می‌کند. سپس چند دقیقه تا نوبت اولین چرخهٔ خبر صبر کنید.

پس از هر push به `main`، Railway خودکار دوباره مستقر می‌شود.

---

## گزینهٔ ۲ — سرور مجازی (VPS) با systemd

```bash
# به‌عنوان کاربر دارای sudo:
sudo adduser --disabled-password --gecos "" khabarioom
sudo apt update && sudo apt install -y python3-venv git
sudo git clone https://github.com/alift302026/khabarioom_bot /opt/khabarioom
cd /opt/khabarioom
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt
sudo cp .env.example .env
sudo nano .env        # TELEGRAM_BOT_TOKEN و ADMIN_USER_IDS و بقیه را وارد کنید
```

فایل سرویس آماده در `deploy/khabarioom.service` قرار دارد:

```bash
sudo cp deploy/khabarioom.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now khabarioom
journalctl -u khabarioom -f        # مشاهدهٔ لاگ زنده
```

سرویس با `Restart=always` در صورت خطا خودش دوباره بالا می‌آید. برای به‌روزرسانی: `git pull` و سپس `sudo systemctl restart khabarioom`.

---

## گزینهٔ ۳ — GitHub Actions (رایگان، محدود)

به‌جای ربات دائمی، هر ۳۰ دقیقه یک اجرای موقت، خبرهای تازه را می‌فرستد و سه گزارش روزانه هم در ساعت خودشان ارسال می‌شوند. **محدودیت‌ها را بدانید:**

- دستورات مدیریتی (`/status`، `/test`، …) کار نمی‌کنند چون ربات شنونده نیست.
- تاریخچهٔ «خبرهای منتشرشده» در کش Actions نگه داشته می‌شود؛ best-effort است و در شرایط نادر ممکن است یک خبر دوباره ارسال شود.
- اگر ۶۰ روز هیچ commit جدیدی به ریپو داده نشود، GitHub زمان‌بندی را غیرفعال می‌کند (یک commit خالی آن را برمی‌گرداند).
- ساعتهای گزارش‌ها بر مبنای UTC+3:30 تنظیم‌اند (ایران از ۱۴۰۱ ساعت تابستانی ندارد)؛ اگر این تغییر کند باید cronها اصلاح شوند.

**راه‌اندازی (۵ دقیقه):**

1. فایل‌های پوشهٔ `deploy/github-actions/` را **به‌دست خودتان** داخل پوشهٔ `.github/workflows/` ریپو کپی و commit کنید (توکن ایجنت اجازهٔ commit روی workflows ندارد):
   - `news-cron.yml` → خبرها هر ۳۰ دقیقه
   - `report-weather.yml` / `report-market.yml` / `report-wisdom.yml` → گزارش‌های روزانه
2. در GitHub: **Settings → Secrets and variables → Actions**
   - Secret بسازید: `TELEGRAM_BOT_TOKEN`
   - در بخش Variables (اختیاری): `CHANNEL_ID` و `ARZHAAM_API_KEY` (کلید پولی بازار را بهتر است Secret بگذارید و در `report-market.yml` مقدار env آن را به `secrets.ARZHAAM_API_KEY` تغییر دهید).
3. تب **Actions** را باز کنید و اجرای دستی `workflow_dispatch` را تست کنید.

توکن فقط در Secrets می‌ماند و هرگز در کد/لاگ ظاهر نمی‌شود.

---

## چک‌لیست بعد از استقرار (هر گزینه)

- [ ] لاگ بدون خطای مکرر است.
- [ ] `/test` (در حالت ربات دائمی) پیام آزمایشی را تأیید کرد.
- [ ] اولین خبر واقعی در کانال ظاهر شد و ۳۰ دقیقه بعد تکراری نفرستاد.
- [ ] در حالت Railway/VPS یک خبر کلیدواژه‌دار(تحریم/جنگ/…) را برای تست پین زیر نظر بگیرید (حداکثر هر ۱۰ ساعت پین می‌زند).
- [ ] ساعت گزارش‌ها را یک روز صبح چک کردید (۰۷:۱۵ / ۰۸:۰۰ / ۰۹:۰۰ تهران).

## وضعیت صادقانه

هیچ‌یک از این استقرارها توسط ایجنت انجام نشده است: سندباکس ایجنت به تلگرام و میزبان‌های ابری دسترسی ندارد و طبق قوانین پروژه، استقرار production و اولین ارسال واقعی نیازمند تأیید و اقدام مالک است. این سند فقط مسیر را آماده می‌کند.
