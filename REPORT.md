# 采集器口径修复报告

依据：`docs/CRAWL_SPEC.md`（口径唯一权威定义，本次未改动）。
验证：`.venv\Scripts\python -m pytest -q` → **12 passed**（`tests/test_spec.py` 9 个 + `tests/test_functional.py` 3 个）。
约束遵守：未改动 `docs/`、`mock_site/`、`tests/test_functional.py`；全程只用 Python 标准库。

---

## 问题 1：漏采最后一页，条数比站点实际少

- **违反口径**：§1 覆盖范围——「必须采集全部页，一页都不能漏」；§6——「输出条数等于站点商品总数」。
- **代码位置**：`spider/crawl.py:13`
- **当前行为**：翻页循环写成 `for page in range(2, total)`，`range` 右端点不含 `total`，首页之外只抓到第 2 页至第 total−1 页。mock 站点共 3 页时只采 2 页，输出 8/12 条。
- **正确行为**：第 2 页到第 total 页（含）逐页采集，输出条数等于站点商品总数（mock 站为 12 条）。
- **修复方式**：改为 `for page in range(2, total + 1)`。
- **测试用例**：`tests/test_spec.py::test_crawl_covers_every_page`（修复前断言 12 条失败，实际只有 8 条）。

## 问题 2：价格抓成原价，不是折后价

- **违反口径**：§2 字段——「`price_cents` 必须取 `data-price` 属性，不得从页面文本里抓第一个金额（页面上原价与折后价同时存在，文本里的第一个是原价）」。
- **代码位置**：`spider/parse.py:9`（`PRICE_TEXT_RE` 正则）、`spider/parse.py:41`（用它匹配）、`spider/parse.py:48`（取值）
- **当前行为**：用 `¥\s*([0-9]+(?:\.[0-9]+)?)` 在商品块里匹配第一个金额，而页面 HTML 中原价 `<span class="price-original">` 排在折后价 `<span class="price">` 前面，第一个命中的是原价。mock 站 sku001 输出 `19901`，正确折后价应为 `9901`。
- **正确行为**：解析商品节点上的 `data-price` 属性，输出折后价。
- **修复方式**：删除文本金额正则，新增 `PRICE_RE = re.compile(r'data-price="([^"]+)"')`，从属性取值。
- **测试用例**：`tests/test_spec.py::test_price_uses_data_price_attribute`（修复前实际输出 `19901`，断言 `9901` 失败）。

## 问题 3：价格经浮点运算，产生错误整数分

- **违反口径**：§2——「折后价，整数，单位分」「不得输出浮点数」；§5 输出要求的隐含前提是分值精确。
- **代码位置**：`spider/parse.py:48`，原表达式 `int(float(price_match.group(1)) * 100)`
- **当前行为**：把文本金额先转 `float` 再乘 100 截断，二进制浮点误差导致丢分，例如 `0.29 * 100 = 28.999999999999996`，`int(...)` 得 28 分（正确 29 分）；`2.07` 同理得 206 分（正确 207 分）。
- **正确行为**：`data-price` 本身就是整数分，直接 `int(...)` 解析，全程不出现浮点数。
- **修复方式**：随问题 2 一并改为 `"price_cents": int(price_match.group(1))`，代码中不再有任何 `float` 转换。
- **测试用例**：`tests/test_spec.py::test_price_cents_is_integer_without_float_rounding`（修复前 sku002 得 28 分、sku003 得 206 分，且原链路根本不读 `data-price`，用例失败）；端到端 `test_repeated_crawl_produces_identical_bytes_without_bom` 另断言所有 `price_cents` 均为 `int`。

## 问题 4：遇到 429/5xx 没有退避重试，任务被限流直接打断

- **违反口径**：§3 限流——「遇到 429 必须退避后重试，最多 3 次，间隔 0.2 秒；重试成功则继续」「遇到 5xx 同样重试；遇到 4xx（除 429）直接失败，不得重试」。
- **代码位置**：`spider/fetch.py:8-11`（原 `fetch_page` 整个函数只有一次 `urlopen`，无任何异常处理）
- **当前行为**：mock 站第 3 页首次请求返回 429，`urllib` 直接抛 `HTTPError 429`，整个采集中断；5xx 同理。
- **正确行为**：捕获 `HTTPError`，对 429 及 5xx 按固定间隔 0.2 秒退避后重试，最多重试 3 次（即最多 4 次请求），重试成功正常返回；超过 3 次仍失败则把最后一次错误抛出；429 以外的 4xx 不重试、立即失败。
- **修复方式**：重写 `fetch_page` 为重试循环，常量 `MAX_RETRIES = 3`、`RETRY_INTERVAL = 0.2`，仅对 `code == 429 or 500 <= code < 600` 重试，其余错误直接 `raise`。仅用标准库 `urllib.error` / `time`。
- **测试用例**：
  - `tests/test_spec.py::test_fetch_retries_on_429_and_succeeds`（首次 429、二次成功，修复前抛 `HTTPError`）
  - `tests/test_spec.py::test_fetch_retries_on_5xx_and_succeeds`（首次 500、二次成功）
  - `tests/test_spec.py::test_fetch_gives_up_after_three_retries_on_429`（持续 429 时共请求 4 次后抛出，修复前只请求 1 次）
  - 守护用例 `tests/test_spec.py::test_fetch_fails_fast_on_4xx_other_than_429`（404 只请求 1 次、不重试；旧实现恰好满足，修复后仍保持绿色）

## 问题 5：追加写且不去重，重跑数据翻倍、不幂等

- **违反口径**：§4 去重与幂等——「同一 `id` 只允许输出一行」「重复执行采集，输出文件内容必须保持不变（幂等），不得追加重复行」；§6——「连续执行两次，输出文件的字节内容完全一致」。
- **代码位置**：`spider/store.py:12`（`path.open("a", ...)` 追加模式），整个 `save` 无去重逻辑
- **当前行为**：以追加模式打开输出文件，每跑一次就在末尾再加一遍全部行；同批次若出现重复 id 也会全部落盘。重跑一次行数翻倍（12 → 24）。
- **正确行为**：写入前按 `id` 去重（同一 id 只保留一行），以覆盖模式重写整个文件；配合按 `id` 升序，连续两次执行的字节内容完全一致。
- **修复方式**：用 `dict` 以 `id` 为键去重后排序，文件改为 `path.open("w", encoding="utf-8", newline="\n")` 覆盖写；UTF-8 无 BOM（标准库默认不带 BOM）。
- **测试用例**：
  - `tests/test_spec.py::test_save_dedupes_by_id_and_overwrites_instead_of_appending`（修复前重跑后行数翻倍、断言失败）
  - `tests/test_spec.py::test_repeated_crawl_produces_identical_bytes_without_bom`（端到端连跑两次逐字节比对，并校验无 BOM、id 唯一、条数为 12）

---

## 附：核对后无需修改的口径条目

- §2 `title` 去首尾空白：`parse.py` 的 `_TextExtractor.text()` 已 `.strip()`，功能正常。
- §5 按 `id` 升序、每行一个 JSON、UTF-8 无 BOM：排序逻辑原本就有，保留；无 BOM 由标准库文本写入保证，已在 `test_repeated_crawl_produces_identical_bytes_without_bom` 中显式断言。
- §3 4xx（除 429）不重试：旧实现因「一律不重试」而碰巧满足，新实现通过显式分支保留该行为，并有守护用例锁定。

## 联调记录（mock 站点，端口 8765）

1. 起 `python -m mock_site.server`，再跑 `python -m spider.crawl`：第 3 页首次 429 经一次退避重试后成功，输出「共 3 页，采集 12 条，输出 12 行」。
2. 输出 12 行，`price_cents` 全部为 `int`，取值 9901–9912（折后价区间），无 19901–19912 的原价混入。
3. 连续执行两次，`data/items.jsonl` 字节内容完全一致。
