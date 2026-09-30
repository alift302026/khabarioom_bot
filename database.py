import aiosqlite
from pathlib import Path
from datetime import datetime, timezone
class Database:
    def __init__(self,path): self.path=path
    async def init(self):
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript('''CREATE TABLE IF NOT EXISTS articles(id INTEGER PRIMARY KEY AUTOINCREMENT,url TEXT UNIQUE,title TEXT,source TEXT,published_at TEXT,posted_at TEXT,telegram_message_id INTEGER); CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT); CREATE INDEX IF NOT EXISTS idx_articles_title ON articles(title);'''); await db.commit()
    async def seen(self,url):
        async with aiosqlite.connect(self.path) as db:
            cur=await db.execute('SELECT 1 FROM articles WHERE url=?',(url,)); return await cur.fetchone() is not None
    async def save_article(self,a,message_id):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('INSERT OR IGNORE INTO articles(url,title,source,published_at,posted_at,telegram_message_id) VALUES(?,?,?,?,?,?)',(a.url,a.title,a.source,a.published_at,datetime.now(timezone.utc).isoformat(),message_id)); await db.commit()
    async def count_posts(self):
        async with aiosqlite.connect(self.path) as db:
            cur=await db.execute('SELECT COUNT(*) FROM articles'); return (await cur.fetchone())[0]
    async def search(self,q,limit=10):
        async with aiosqlite.connect(self.path) as db:
            cur=await db.execute('SELECT title,source,url,posted_at FROM articles WHERE title LIKE ? OR source LIKE ? ORDER BY id DESC LIMIT ?',(f'%{q}%',f'%{q}%',limit)); return await cur.fetchall()
    async def get_state(self,key):
        async with aiosqlite.connect(self.path) as db:
            cur=await db.execute('SELECT value FROM state WHERE key=?',(key,)); r=await cur.fetchone(); return r[0] if r else None
    async def set_state(self,key,value):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('INSERT OR REPLACE INTO state(key,value) VALUES(?,?)',(key,value)); await db.commit()
