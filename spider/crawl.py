"""采集主循环。"""

import argparse

from spider import fetch, parse, store


def crawl(out_path: str = "data/items.jsonl") -> dict:
    first_html = fetch.fetch_page(1)
    total = parse.total_pages(first_html)

    collected = parse.parse_items(first_html)
    for page in range(2, total + 1):
        html = fetch.fetch_page(page)
        collected.extend(parse.parse_items(html))

    written = store.save(collected, out_path)
    return {"pages": total, "collected": len(collected), "written": written}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/items.jsonl")
    args = parser.parse_args()
    result = crawl(args.out)
    print(f"共 {result['pages']} 页，采集 {result['collected']} 条，输出 {result['written']} 行")


if __name__ == "__main__":
    main()
