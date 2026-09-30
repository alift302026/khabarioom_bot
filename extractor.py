import httpx,trafilatura
from bs4 import BeautifulSoup
from urllib.parse import urljoin
async def enrich(article,settings):
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout,headers={'User-Agent':settings.user_agent},follow_redirects=True) as c:
            r=await c.get(article.url); r.raise_for_status()
        html=r.text; text=trafilatura.extract(html,include_comments=False,include_tables=False,favor_precision=False,output_format='txt') or article.text
        soup=BeautifulSoup(html,'lxml')
        if not article.image_url:
            og=soup.find('meta',property='og:image')
            if og and og.get('content'): article.image_url=urljoin(article.url,og['content'])
            else:
                img=soup.find('img')
                if img and img.get('src'): article.image_url=urljoin(article.url,img['src'])
        article.text=(text or article.text or '').strip()
    except Exception as e: print('[EXTRACT ERROR]',article.url,e)
    return article
