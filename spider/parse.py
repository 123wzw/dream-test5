"""HTML 解析。"""

import re
from html.parser import HTMLParser

ITEM_RE = re.compile(r'<div class="item".*?</div>', re.S)
ID_RE = re.compile(r'data-id="([^"]+)"')
TITLE_RE = re.compile(r'<span class="title">(.*?)</span>', re.S)
PRICE_RE = re.compile(r'data-price="([^"]+)"')
TOTAL_RE = re.compile(r"共\s*(\d+)\s*页")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts).strip()


def _text_of(fragment: str) -> str:
    parser = _TextExtractor()
    parser.feed(fragment)
    return parser.text()


def total_pages(html: str) -> int:
    match = TOTAL_RE.search(html)
    return int(match.group(1)) if match else 1


def parse_items(html: str) -> list[dict]:
    items = []
    for block in ITEM_RE.findall(html):
        id_match = ID_RE.search(block)
        title_match = TITLE_RE.search(block)
        price_match = PRICE_RE.search(block)
        if not (id_match and title_match and price_match):
            continue
        items.append(
            {
                "id": id_match.group(1),
                "title": _text_of(title_match.group(1)),
                # 口径 §2：折后价取 data-price，站点给出的就是整数分，直接按整数解析，
                # 不得抓页面文本里的第一个金额（那是原价），也不得做浮点运算。
                "price_cents": int(price_match.group(1)),
            }
        )
    return items
