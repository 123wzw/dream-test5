"""CRAWL_SPEC 口径复现测试。

每个用例对应 docs/CRAWL_SPEC.md 中的一条口径；修复前这些用例应当失败
（test_fetch_fails_fast_on_4xx 是口径守护用例，验证 429 以外的 4xx 不重试）。
"""

import json
import os
import tempfile
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mock_site import server as mock_server
from spider import crawl, fetch, parse, store

PORT = 8765
_TMP = tempfile.mkdtemp(prefix="spider-spec-")


def _start(handler_cls):
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), handler_cls)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    return srv


def _stop(srv):
    srv.shutdown()
    srv.server_close()  # 关闭监听 socket，避免同端口重绑后连接被旧 socket 吸走


def _start_mock():
    mock_server.Handler.hits.clear()
    return _start(mock_server.Handler)


def _read_rows(out):
    with open(out, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# --- §1 覆盖范围：必须采集全部页，输出条数等于站点商品总数 -----------------

def test_crawl_covers_every_page():
    srv = _start_mock()
    try:
        out = os.path.join(_TMP, "all_pages.jsonl")
        result = crawl.crawl(out)
        rows = _read_rows(out)
        assert result["collected"] == len(mock_server.ITEMS)
        assert len(rows) == len(mock_server.ITEMS)
    finally:
        _stop(srv)


# --- §2 字段：price_cents 取 data-price（折后价），不得抓文本第一个金额 ----

def test_price_uses_data_price_attribute():
    html = (
        '<div class="item" data-id="sku001" data-price="9901">'
        '<span class="title"> 商品001 </span>'
        '<span class="price-original">¥199.01</span>'
        '<span class="price">¥99.01</span>'
        "</div>"
    )
    items = parse.parse_items(html)
    assert items == [{"id": "sku001", "title": "商品001", "price_cents": 9901}]


def test_price_cents_is_integer_without_float_rounding():
    # 0.29 与 2.07 走 float * 100 分别会变成 28、206 分，整数分必须直接解析
    html = (
        '<div class="item" data-id="sku002" data-price="29">'
        '<span class="title">商品002</span>'
        '<span class="price-original">¥1.29</span>'
        '<span class="price">¥0.29</span>'
        "</div>"
        '<div class="item" data-id="sku003" data-price="207">'
        '<span class="title">商品003</span>'
        '<span class="price-original">¥3.07</span>'
        '<span class="price">¥2.07</span>'
        "</div>"
    )
    items = {row["id"]: row for row in parse.parse_items(html)}
    assert isinstance(items["sku002"]["price_cents"], int)
    assert items["sku002"]["price_cents"] == 29
    assert isinstance(items["sku003"]["price_cents"], int)
    assert items["sku003"]["price_cents"] == 207


# --- §3 限流：429 / 5xx 退避重试，最多 3 次；其他 4xx 直接失败 -------------

class _Flaky429(BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self):  # noqa: N802
        type(self).hits += 1
        if type(self).hits == 1:
            self.send_response(429)
            self.send_header("Retry-After", "0")
            self.send_header("content-length", "0")
            self.end_headers()
            return
        body = b"<html>retry ok</html>"
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _Flaky500(BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self):  # noqa: N802
        type(self).hits += 1
        if type(self).hits == 1:
            self.send_response(500)
            self.send_header("content-length", "0")
            self.end_headers()
            return
        body = b"<html>retry ok</html>"
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _Always429(BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self):  # noqa: N802
        type(self).hits += 1
        self.send_response(429)
        self.send_header("Retry-After", "0")
        self.send_header("content-length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


class _Always404(BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self):  # noqa: N802
        type(self).hits += 1
        self.send_response(404)
        self.send_header("content-length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


def test_fetch_retries_on_429_and_succeeds():
    _Flaky429.hits = 0
    srv = _start(_Flaky429)
    try:
        html = fetch.fetch_page(1)
        assert "retry ok" in html
        assert _Flaky429.hits == 2
    finally:
        _stop(srv)


def test_fetch_retries_on_5xx_and_succeeds():
    _Flaky500.hits = 0
    srv = _start(_Flaky500)
    try:
        html = fetch.fetch_page(1)
        assert "retry ok" in html
        assert _Flaky500.hits == 2
    finally:
        _stop(srv)


def test_fetch_gives_up_after_three_retries_on_429():
    _Always429.hits = 0
    srv = _start(_Always429)
    try:
        try:
            fetch.fetch_page(1)
        except urllib.error.HTTPError as exc:
            assert exc.code == 429
        else:
            raise AssertionError("持续 429 应当在重试 3 次后抛出")
        assert _Always429.hits == 4  # 首次请求 + 3 次重试
    finally:
        _stop(srv)


def test_fetch_fails_fast_on_4xx_other_than_429():
    _Always404.hits = 0
    srv = _start(_Always404)
    try:
        try:
            fetch.fetch_page(1)
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("404 应当直接失败")
        assert _Always404.hits == 1  # 4xx（除 429）不得重试
    finally:
        _stop(srv)


# --- §4 去重与幂等：同一 id 只一行，重复执行输出不变 ------------------------

def test_save_dedupes_by_id_and_overwrites_instead_of_appending():
    out = os.path.join(_TMP, "dedupe.jsonl")
    rows = [
        {"id": "sku002", "title": "b", "price_cents": 200},
        {"id": "sku001", "title": "a", "price_cents": 100},
    ]
    store.save(rows, out)
    store.save(rows, out)  # 重跑不得追加
    assert _read_rows(out) == [
        {"id": "sku001", "title": "a", "price_cents": 100},
        {"id": "sku002", "title": "b", "price_cents": 200},
    ]

    store.save(rows + rows, out)  # 同批次内重复 id 也只保留一行
    rerun_rows = _read_rows(out)
    assert [row["id"] for row in rerun_rows] == ["sku001", "sku002"]


def test_repeated_crawl_produces_identical_bytes_without_bom():
    srv = _start_mock()
    try:
        out = os.path.join(_TMP, "idempotent.jsonl")
        crawl.crawl(out)
        with open(out, "rb") as fh:
            first = fh.read()
        crawl.crawl(out)
        with open(out, "rb") as fh:
            second = fh.read()

        assert not first.startswith(b"\xef\xbb\xbf"), "UTF-8 输出不得带 BOM"
        assert first == second, "重复执行输出文件的字节内容必须完全一致"
        rows = [json.loads(line) for line in first.decode("utf-8").splitlines() if line.strip()]
        assert len(rows) == len(mock_server.ITEMS)
        assert len({row["id"] for row in rows}) == len(rows)
        assert all(isinstance(row["price_cents"], int) for row in rows)
    finally:
        _stop(srv)
