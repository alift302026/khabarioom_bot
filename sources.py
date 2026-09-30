import feedparser,httpx,yaml,re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from .models import Article
class SourceManager:
    def __init__(self,settings): self.s=settings; self.headers={'User-Agent':settings.user_agent}
    def load_sources(self,path='sources.yaml'):
        with open(path,encoding='utf-8') as f: return yaml.safe_load(f) or {}
    async def rss(self,src):
        async with httpx.AsyncClient(timeout=self.s.request_timeout,headers=self.headers,follow_redirects=True) as c:
            r=await c.get(src['url']); r.raise_for_status()
        feed=feedparser.parse(r.content); out=[]
        for e in feed.entries[:self.s.max_articles_per_source]:
            link=e.get('link'); title=(e.get('title') or '').strip()
            if link and title: out.append(Article(src['name'],title,link,e.get('summary',''),(e.get('media_content') or [{}])[0].get('url'),e.get('published')))
        return out
    async def website(self,src):
        async with httpx.AsyncClient(timeout=self.s.request_timeout,headers=self.headers,follow_redirects=True) as c:
            r=await c.get(src['url']); r.raise_for_status()
        soup=BeautifulSoup(r.text,'lxml'); out=[]; seen=set()
        for a in soup.find_all('a',href=True):
            title=' '.join(a.get_text(' ',strip=True).split()); href=urljoin(src['url'],a['href'])
            if len(title)>=25 and href.startswith('http') and href not in seen:
                seen.add(href); out.append(Article(src['name'],title,href))
            if len(out)>=self.s.max_articles_per_source: break
        return out
    async def telegram_public(self,src):
        username=src['username'].lstrip('@'); url=f'https://t.me/s/{username}'
        async with httpx.AsyncClient(timeout=self.s.request_timeout,headers=self.headers,follow_redirects=True) as c:
            r=await c.get(url); r.raise_for_status()
        soup=BeautifulSoup(r.text,'lxml'); out=[]
        for msg in soup.select('.tgme_widget_message')[-self.s.max_articles_per_source:]:
            text=msg.select_one('.tgme_widget_message_text'); body=(text.get_text(' ',strip=True) if text else '').strip()
            if not body: continue
            a=msg.select_one('a.tgme_widget_message_date'); link=a.get('href') if a else url; img=None
            media=msg.select_one('.tgme_widget_message_photo_wrap')
            if media:
                m=re.search(r"url\(['\"]?([^)'\"]+)",media.get('style',''))
                if m: img=m.group(1)
            out.append(Article(src['name'],body[:300],link,body,img))
        return out
    async def collect(self):
        cfg=self.load_sources(); results=[]
        for src in cfg.get('sources',[])+cfg.get('telegram_channels',[]):
            if not src.get('enabled',True): continue
            try:
                if src['type']=='rss': results += await self.rss(src)
                elif src['type']=='website': results += await self.website(src)
                elif src['type']=='telegram': results += await self.telegram_public(src)
            except Exception as e: print('[SOURCE ERROR]',src.get('name'),e)
        return results
