"""采集器功能回归测试。"""

import json
import os
import tempfile
import threading
import time

from mock_site import server as mock_server
from spider import crawl

_TMP = tempfile.mkdtemp(prefix="spider-test-")
PORT = 8765


def _start_site():
    mock_server.Handler.hits.clear()
    srv = mock_server.ThreadingHTTPServer(("127.0.0.1", PORT), mock_server.Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    return srv


def test_crawl_writes_json_lines():
    srv = _start_site()
    try:
        out = os.path.join(_TMP, "items.jsonl")
        crawl.crawl(out)
        assert os.path.exists(out)
        lines = [l for l in open(out, encoding="utf-8").read().splitlines() if l.strip()]
        assert lines, "输出为空"
        row = json.loads(lines[0])
        assert set(row) == {"id", "title", "price_cents"}
    finally:
        srv.shutdown()


def test_output_is_sorted_by_id():
    srv = _start_site()
    try:
        out = os.path.join(_TMP, "sorted.jsonl")
        crawl.crawl(out)
        ids = [json.loads(l)["id"] for l in open(out, encoding="utf-8") if l.strip()]
        assert ids == sorted(ids)
    finally:
        srv.shutdown()


def test_mock_site_serves_pages():
    srv = _start_site()
    try:
        from spider import fetch

        html = fetch.fetch_page(1)
        assert "共 3 页" in html
        assert "data-price" in html
    finally:
        srv.shutdown()
