"""报表输出：CSV 报表（确定性覆盖写）+ 文本汇总（带生成时间，可审计）。"""

import csv
from datetime import datetime
from pathlib import Path

from .parser import TelemetryRow
from .stats import DeviceStats

CSV_HEADER = [
    "device_id",
    "count",
    "speed_min",
    "speed_max",
    "speed_avg",
    "component_min",
    "component_max",
    "component_avg",
]


def write_csv_report(stats: list[DeviceStats], out: Path) -> int:
    """写 per-device CSV 报表（覆盖写，可安全重跑）；返回含表头的总行数。"""
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for s in stats:
            writer.writerow(
                [
                    s.device_id,
                    s.count,
                    s.speed_min,
                    s.speed_max,
                    s.speed_avg,
                    s.component_min,
                    s.component_max,
                    s.component_avg,
                ]
            )
    return len(stats) + 1


def write_summary(
    rows: list[TelemetryRow],
    invalid: int,
    stats: list[DeviceStats],
    out: Path,
    source: str = "",
) -> None:
    """写文本汇总：输入来源、生成时间、有效/无效行数、逐设备明细（可审计）。"""
    lines = [
        f"source: {source}",
        f"generated_at: {datetime.now().isoformat(timespec='seconds')}",
        f"valid_rows: {len(rows)}",
        f"invalid_rows: {invalid}",
        f"devices: {len(stats)}",
    ]
    for s in stats:
        lines.append(
            f"{s.device_id}: count={s.count} "
            f"speed=[{s.speed_min}, {s.speed_max}] avg={s.speed_avg} "
            f"component=[{s.component_min}, {s.component_max}] avg={s.component_avg}"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
