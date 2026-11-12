"""落盘与去重。"""

import json
from pathlib import Path


def save(items: list[dict], out_path: str) -> int:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 口径 §4：同一 id 只允许输出一行；重复执行整体覆盖写，保证幂等。
    unique: dict[str, dict] = {}
    for row in items:
        unique[row["id"]] = row

    rows = sorted(unique.values(), key=lambda row: row["id"])
    # 口径 §5：UTF-8、无 BOM；用 "w" 覆盖而非追加，重跑不会产生重复行。
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)
