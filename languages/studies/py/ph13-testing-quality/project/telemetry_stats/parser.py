"""CSV 解析与清洗：逐行校验，无效行单独计数（不静默吞掉、不崩溃）。"""

from dataclasses import dataclass
from pathlib import Path

# 表头行的 ts 前缀：解析时跳过表头与空行
HEADER_MARK = "ts,"


@dataclass
class TelemetryRow:
    """一条有效遥测记录：时间、车辆、速度（km/h）、电量（%）。"""

    ts: str
    vehicle_id: str
    speed: float
    battery: float


def parse_row(line: str) -> TelemetryRow | None:
    """解析 'ts,vehicle,speed,battery' 一行；字段数不对或数值非法返回 None。"""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 4:
        return None
    ts, vehicle_id, speed_s, battery_s = parts
    try:
        speed = float(speed_s)
        battery = float(battery_s)
    except ValueError:
        return None
    if speed < 0 or battery < 0 or battery > 100:
        return None
    return TelemetryRow(ts, vehicle_id, speed, battery)


def parse_csv(path: Path) -> tuple[list[TelemetryRow], int]:
    """读取遥测 CSV，返回 (有效行列表, 无效行数)。

    跳过空行与表头（以 ``ts,`` 开头的行为约定表头）；无效行计数但不中断。
    """
    rows: list[TelemetryRow] = []
    invalid = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(HEADER_MARK):
            continue
        row = parse_row(stripped)
        if row is None:
            invalid += 1
        else:
            rows.append(row)
    return rows, invalid
