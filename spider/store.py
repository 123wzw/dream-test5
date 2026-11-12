"""落盘与去重。"""

import json
from pathlib import Path


def save(items: list[dict], out_path: str) -> int:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = sorted(items, key=lambda row: row["id"])
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)
