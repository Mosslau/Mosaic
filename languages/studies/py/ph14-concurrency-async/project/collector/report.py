"""CSV 报表输出：确定性覆盖写，可安全重跑。"""

from __future__ import annotations

import csv
from pathlib import Path

from collector.fetcher import FetchResult


def write_csv(results: list[FetchResult], path: Path) -> Path:
    """把采集结果写成 CSV（每台设备一行），覆盖写、按 device_id 排序。

    返回写入的路径；写入前自动创建父目录。失败行的 speed/component 留空。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["device_id", "ok", "status", "attempts", "elapsed_ms", "speed", "component"]
        )
        for r in sorted(results, key=lambda x: x.device_id):
            writer.writerow(
                [
                    r.device_id,
                    "ok" if r.ok else "fail",
                    r.status if r.status is not None else "",
                    r.attempts,
                    r.elapsed_ms,
                    r.speed if r.speed is not None else "",
                    r.component if r.component is not None else "",
                ]
            )
    return path
