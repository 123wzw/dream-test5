"""本地 mock 站点：商品列表，3 页，第 2 页首次请求返回 429。"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ITEMS = [
    {"id": f"sku{i:03d}", "title": f"商品{i:03d}", "price": 9900 + i, "original": 19900 + i}
    for i in range(1, 13)
]
PAGE_SIZE = 4
PORT = 8765


def total_pages() -> int:
    return (len(ITEMS) + PAGE_SIZE - 1) // PAGE_SIZE


def render_page(page: int) -> str:
    chunk = ITEMS[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
    rows = []
    for item in chunk:
        rows.append(
            f'<div class="item" data-id="{item["id"]}" data-price="{item["price"]}">'
            f'<span class="title"> {item["title"]} </span>'
            f'<span class="price-original">¥{item["original"] / 100:.2f}</span>'
            f'<span class="price">¥{item["price"] / 100:.2f}</span>'
            f"</div>"
        )
    return (
        "<html><body>"
        f"<p>共 {total_pages()} 页</p>"
        + "".join(rows)
        + "</body></html>"
    )


class Handler(BaseHTTPRequestHandler):
    hits: dict[int, int] = {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/list":
            self.send_error(404)
            return
        page = int(parse_qs(parsed.query).get("page", ["1"])[0])
        Handler.hits[page] = Handler.hits.get(page, 0) + 1
        if page == 3 and Handler.hits[page] == 1:
            body = b"too many requests"
            self.send_response(429)
            self.send_header("Retry-After", "0")
            self.send_header("content-type", "text/plain; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if page < 1 or page > total_pages():
            self.send_error(404)
            return
        body = render_page(page).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"mock site on http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
