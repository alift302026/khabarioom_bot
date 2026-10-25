import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()
def csv_ints(v): return [int(x.strip()) for x in (v or '').split(',') if x.strip().isdigit()]
@dataclass(frozen=True)
class Settings:
    bot_token:str; channel_id:str; admin_user_ids:list[int]; fetch_interval_minutes:int; promo_every_n_posts:int; pin_cooldown_hours:int; max_sources_per_cycle:int; max_articles_per_source:int; copy_full_article:bool; max_message_chars:int; signature:str; add_source_link:bool; send_images:bool; database_path:str; request_timeout:int; user_agent:str; timezone:str

def get_settings():
    return Settings(os.getenv('TELEGRAM_BOT_TOKEN',''),os.getenv('CHANNEL_ID','@khabarioom'),csv_ints(os.getenv('ADMIN_USER_IDS','')),int(os.getenv('FETCH_INTERVAL_MINUTES','30')),int(os.getenv('PROMO_EVERY_N_POSTS','20')),int(os.getenv('PIN_COOLDOWN_HOURS','10')),int(os.getenv('MAX_SOURCES_PER_CYCLE','50')),int(os.getenv('MAX_ARTICLES_PER_SOURCE','5')),os.getenv('COPY_FULL_ARTICLE','false').lower()=='true',int(os.getenv('MAX_TELEGRAM_MESSAGE_CHARS','3900')),os.getenv('SIGNATURE','@khabarioom'),os.getenv('ADD_SOURCE_LINK','false').lower()=='true',os.getenv('SEND_IMAGES','true').lower()=='true',os.getenv('DATABASE_PATH','data/khabarioom.sqlite3'),int(os.getenv('REQUEST_TIMEOUT_SECONDS','25')),os.getenv('USER_AGENT','KhabarioomNewsBot/1.0'),os.getenv('TIMEZONE','Asia/Tehran'))
