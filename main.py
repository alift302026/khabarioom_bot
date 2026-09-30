from datetime import datetime,timezone,timedelta
from telegram.ext import Application,CommandHandler
from .config import get_settings
from .database import Database
from .sources import SourceManager
from .extractor import enrich
from .publisher import build_caption,split_text,is_priority
PROMO='📣 <b>Khabarioom</b>\n\nاگر این کانال برایتان مفید است، آن را به دوستانتان معرفی کنید تا خبرهای تازه را سریع‌تر دنبال کنند. 📰✨\n\n@khabarioom'
async def publish(bot,db,s,a):
    if not a.url or await db.seen(a.url): return False
    a=await enrich(a,s); parts=split_text(build_caption(a,s),s.max_message_chars)
    try:
        if s.send_images and a.image_url:
            try: sent=await bot.send_photo(s.channel_id,a.image_url,caption=parts[0],parse_mode='HTML')
            except Exception: sent=await bot.send_message(s.channel_id,parts[0],parse_mode='HTML')
        else: sent=await bot.send_message(s.channel_id,parts[0],parse_mode='HTML')
        for p in parts[1:]: await bot.send_message(s.channel_id,p,parse_mode='HTML')
        await db.save_article(a,sent.message_id)
        if is_priority(a):
            last=await db.get_state('last_priority_pin'); ok=True
            if last:
                try: ok=datetime.now(timezone.utc)-datetime.fromisoformat(last)>=timedelta(hours=s.pin_cooldown_hours)
                except Exception: pass
            if ok:
                try: await bot.pin_chat_message(s.channel_id,sent.message_id,disable_notification=True); await db.set_state('last_priority_pin',datetime.now(timezone.utc).isoformat())
                except Exception as e: print('[PIN ERROR]',e)
        n=await db.count_posts()
        if s.promo_every_n_posts and n%s.promo_every_n_posts==0: await bot.send_message(s.channel_id,PROMO,parse_mode='HTML')
        return True
    except Exception as e: print('[PUBLISH ERROR]',a.url,e); return False
async def cycle(context):
    s=context.application.bot_data['settings']; db=context.application.bot_data['db']; mgr=context.application.bot_data['manager']
    items=await mgr.collect(); seen=set()
    for a in items:
        if a.url in seen: continue
        seen.add(a.url); await publish(context.bot,db,s,a)
async def status(update,context):
    s=context.application.bot_data['settings']
    if update.effective_user.id not in s.admin_user_ids:return
    await update.message.reply_text(f'📊 خبرهای منتشرشده: {await context.application.bot_data["db"].count_posts()}\n⏱ بررسی: هر {s.fetch_interval_minutes} دقیقه')
async def search(update,context):
    if update.effective_user.id not in context.application.bot_data['settings'].admin_user_ids:return
    q=' '.join(context.args).strip()
    if not q:return await update.message.reply_text('مثال: /search تحریم')
    rows=await context.application.bot_data['db'].search(q); msg='\n\n'.join(f'📰 {t}\n📌 {src}\n🔗 {url}' for t,src,url,_ in rows) or 'نتیجه‌ای پیدا نشد.'
    await update.message.reply_text(msg[:3900],disable_web_page_preview=True)
async def sources(update,context):
    if update.effective_user.id not in context.application.bot_data['settings'].admin_user_ids:return
    cfg=context.application.bot_data['manager'].load_sources(); names=[x.get('name') for x in cfg.get('sources',[]) if x.get('enabled',True)]; tg=[x.get('name') for x in cfg.get('telegram_channels',[]) if x.get('enabled',True)]
    await update.message.reply_text('🌐 سایت‌ها:\n'+'\n'.join('• '+x for x in names)+'\n\n📣 تلگرام:\n'+'\n'.join('• '+x for x in tg))
async def post_init(app):
    s=get_settings(); db=Database(s.database_path); await db.init(); app.bot_data.update(settings=s,db=db,manager=SourceManager(s))
    await cycle(type('C',(),{'application':app,'bot':app.bot})())
def main():
    s=get_settings()
    if not s.bot_token: raise SystemExit('TELEGRAM_BOT_TOKEN is missing')
    app=Application.builder().token(s.bot_token).post_init(post_init).build(); app.add_handler(CommandHandler('status',status)); app.add_handler(CommandHandler('search',search)); app.add_handler(CommandHandler('sources',sources)); app.job_queue.run_repeating(cycle,interval=s.fetch_interval_minutes*60,first=s.fetch_interval_minutes*60); app.run_polling(allowed_updates=['message'])
if __name__=='__main__': main()
