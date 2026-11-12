"""HTTP 请求。"""

import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8765"

# 口径 §3：429 与 5xx 退避后重试，最多 3 次，间隔 0.2 秒。
MAX_RETRIES = 3
RETRY_INTERVAL = 0.2


def fetch_page(page: int) -> str:
    url = f"{BASE_URL}/list?page={page}"
    req = urllib.request.Request(url)
    attempts = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            # 429（限流）与 5xx（服务端错误）可重试；其余 4xx 直接失败，不得重试。
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempts >= MAX_RETRIES:
                raise
            attempts += 1
            time.sleep(RETRY_INTERVAL)
