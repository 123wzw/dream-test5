# spider-kit

商品列表采集器，配合仓库内自带的 mock 站点做联调。

## 技术栈

- Python 3.12，纯标准库（urllib / html.parser / json）

## 运行

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt

# 1. 起本地 mock 站点（另开一个窗口）
.venv/Scripts/python -m mock_site.server

# 2. 采集
.venv/Scripts/python -m spider.crawl --out data/items.jsonl
```

mock 站点监听 `127.0.0.1:8765`，共 3 页、每页 4 条商品，第 2 页首次请求会返回 429。

## 目录

```
spider/fetch.py     HTTP 请求
spider/parse.py     HTML 解析
spider/store.py     落盘与去重
spider/crawl.py     采集主循环
mock_site/server.py 本地 mock 站点
docs/CRAWL_SPEC.md  采集口径（唯一权威定义）
```

## 测试

```bash
.venv/Scripts/python -m pytest -q
```

## 已知问题

- 站点改过一版价格展示，把原价和折后价都渲染出来了。
- 采集任务经常被限流打断，重跑之后数据有重复。
