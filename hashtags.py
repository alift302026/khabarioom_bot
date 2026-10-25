"""Simple keyword-driven hashtag selection (at most two tags per post)."""

MAP = {
    "جنگ": "#جنگ",
    "ایران": "#ایران",
    "تحریم": "#تحریم",
    "توافق": "#توافق",
    "اقتصاد": "#اقتصاد",
    "دلار": "#دلار",
    "نفت": "#نفت",
    "بورس": "#بورس",
    "انتخابات": "#انتخابات",
    "مجلس": "#مجلس",
    "دولت": "#دولت",
    "آمریکا": "#آمریکا",
    "اسرائیل": "#اسرائیل",
    "غزه": "#غزه",
    "لبنان": "#لبنان",
    "مذاکره": "#مذاکرات",
    "برجام": "#برجام",
}

DEFAULT_HASHTAGS = "#خبر #ایران"


def make_hashtags(title: str, text: str) -> str:
    """Return exactly two hashtags based on keyword matches in the text."""
    combined = f"{title or ''} {text or ''}"
    tags: list[str] = []
    for keyword, tag in MAP.items():
        if keyword in combined and tag not in tags:
            tags.append(tag)
        if len(tags) >= 2:
            break
    if not tags:
        return DEFAULT_HASHTAGS
    if len(tags) == 1:
        return f"{tags[0]} #خبر"
    return " ".join(tags)
