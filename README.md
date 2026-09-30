# Khabarioom Telegram News Bot

ربات خبری Khabarioom برای کانال `@khabarioom`.

امکانات: دریافت خبر از RSS/HTML، دریافت پست از کانال‌های عمومی تلگرام، بررسی هر 45 دقیقه، حذف تکراری، تصویر، متن کامل، دو هشتگ، امضای @khabarioom، جست‌وجوی مدیر، پین خودکار موضوعات حساس با فاصله 10 ساعت، پست معرفی بعد از هر 20 خبر، SQLite و Docker/Railway.

> انتشار کامل متن خبرهای دیگران ممکن است تابع حق نشر و شرایط استفاده منبع باشد. لینک منبع همیشه درج می‌شود و `COPY_FULL_ARTICLE` قابل تنظیم است.

## اجرا
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

## Railway
Repo را به GitHub منتقل کنید، در Railway از GitHub deploy کنید و متغیرهای `.env.example` را وارد کنید.
