from .hashtags import make_hashtags
PIN_KEYWORDS=['جنگ ایران','جنگ','حمله به ایران','حمله ایران','تحریم ایران','تحریم','توافق هسته‌ای','توافق هسته ای','مذاکرات هسته‌ای','مذاکرات هسته ای','برجام','آتش‌بس','آتش بس']
def clean_text(t): return '\n'.join(x.strip() for x in (t or '').splitlines() if x.strip())
def is_priority(a): return any(k in f'{a.title} {a.text}' for k in PIN_KEYWORDS)
def build_caption(a,s):
    body=clean_text(a.text) if s.copy_full_article else clean_text(a.text)[:1800]
    body=body or a.title; source=f'\n\n🔗 منبع: {a.url}' if s.add_source_link else ''
    return f'📰 <b>{a.title}</b>\n\n{body}\n\n{make_hashtags(a.title,body)}\n{s.signature}{source}'
def split_text(t,n=3900):
    out=[]
    while len(t)>n:
        cut=t.rfind('\n',0,n); cut=cut if cut>=n//2 else n; out.append(t[:cut].strip()); t=t[cut:].strip()
    if t: out.append(t)
    return out
