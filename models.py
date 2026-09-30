from dataclasses import dataclass
from typing import Optional
@dataclass
class Article:
    source:str; title:str; url:str; text:str=''; image_url:Optional[str]=None; published_at:Optional[str]=None; external_id:Optional[str]=None
