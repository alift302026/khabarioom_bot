# راهنمای راه‌اندازی Khabarioom

## 1. ساخت ربات
در تلگرام به `@BotFather` بروید، `/newbot` را اجرا کنید و Token را بگیرید. Token را فقط در Railway Variables بگذارید.

## 2. ادمین کانال
ربات را در `@khabarioom` ادمین کنید و حداقل دسترسی Post Messages و Pin Messages را بدهید.

## 3. متغیرهای Railway
این موارد را تنظیم کنید:

`TELEGRAM_BOT_TOKEN=توکن`

`CHANNEL_ID=@khabarioom`

`ADMIN_USER_IDS=آیدی عددی مدیر`

`FETCH_INTERVAL_MINUTES=45`

`PROMO_EVERY_N_POSTS=20`

`PIN_COOLDOWN_HOURS=10`

`COPY_FULL_ARTICLE=true`

`SIGNATURE=@khabarioom`

`DATABASE_PATH=data/khabarioom.sqlite3`

`TIMEZONE=Asia/Tehran`

## 4. منابع سایت‌ها
در `sources.yaml` منابع RSS/HTML قرار دارند. اگر RSS یک سایت تغییر کرده باشد، URL آن را اصلاح کنید. برای سایت بدون RSS از `type: website` استفاده کنید.

## 5. کانال‌های تلگرام
برای کانال عمومی:

```yaml
telegram_channels:
  - name: نام کانال
    type: telegram
    username: channel_username
    enabled: true
```

روش بالا از `t.me/s/channel_username` استفاده می‌کند و برای کانال عمومی است. برای کانال خصوصی یا کانالی که Web Preview آن در دسترس نیست، نسخه MTProto با حساب کاربری لازم است.

## 6. رفتار ربات
هر 45 دقیقه منابع را بررسی می‌کند؛ URL تکراری را منتشر نمی‌کند؛ تصویر و متن را استخراج می‌کند؛ دو هشتگ می‌گذارد؛ `@khabarioom` را درج می‌کند؛ لینک منبع را می‌گذارد؛ بعد از هر 20 خبر پست معرفی می‌فرستد؛ و برای کلیدواژه‌های جنگ، تحریم و توافق با فاصله حداقل 10 ساعت امکان پین دارد.

## 7. دستورات
`/status` وضعیت

`/sources` منابع

`/search تحریم` جست‌وجو

## 8. Railway
Repository را به GitHub بدهید، در Railway از GitHub Deploy کنید، Variables را وارد کنید و Deploy کنید. برای SQLite در محیط ابری بهتر است Volume پایدار داشته باشید؛ برای مقیاس بالاتر PostgreSQL مناسب‌تر است.

## 9. حق نشر
انتشار کامل متن خبرهای منابع دیگر ممکن است تابع قوانین حق نشر و شرایط همان منبع باشد. تنظیم `COPY_FULL_ARTICLE=true` طبق نیاز فعلی شماست؛ مسئولیت مجوز انتشار با صاحب کانال است.
