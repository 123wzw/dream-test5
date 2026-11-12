"""HTTP 请求。"""

import urllib.request

BASE_URL = "http://127.0.0.1:8765"


def fetch_page(page: int) -> str:
    url = f"{BASE_URL}/list?page={page}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.read().decode("utf-8", "replace")
