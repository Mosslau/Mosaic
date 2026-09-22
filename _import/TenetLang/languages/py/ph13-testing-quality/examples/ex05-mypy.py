#!/usr/bin/env python3
# examples/ex05-mypy.py —— 类型注解 + mypy 静态检查（主文档 3.5）
# 验证环境：Python 3.13.9 + mypy 1.17.1（本机已装并实测）
# 运行：python3 ex05-mypy.py（离线可跑，已验证）
#      类型检查：mypy ex05-mypy.py（已验证：Success，no issues found）
# 验证状态：已验证 —— 运行输出 3 行；mypy 0 错误
from dataclasses import dataclass
from typing import Protocol


@dataclass
class VehicleTelemetry:
    """一行遥测数据：车辆、速度、电量。"""
    vehicle_id: str
    speed: float
    battery: float


class Formatter(Protocol):
    """结构类型（Protocol）：任何带 format(VehicleTelemetry) -> str 的对象都可被接受。"""

    def format(self, t: VehicleTelemetry) -> str: ...


class SimpleFormatter:
    def format(self, t: VehicleTelemetry) -> str:
        return f"{t.vehicle_id}: {t.speed:.1f} km/h"


def format_row(t: VehicleTelemetry) -> str:
    return f"{t.vehicle_id},{t.speed:.1f},{t.battery:.1f}"


def avg_speed_by_vehicle(rows: list[VehicleTelemetry]) -> dict[str, float]:
    """按车辆分组求平均速度；空输入返回空 dict。"""
    speeds: dict[str, list[float]] = {}
    for r in rows:
        speeds.setdefault(r.vehicle_id, []).append(r.speed)
    return {vid: sum(v) / len(v) for vid, v in speeds.items()}


def find_vehicle(rows: list[VehicleTelemetry], vehicle_id: str) -> VehicleTelemetry | None:
    """找指定车辆的第一条记录；找不到返回 None（联合类型显式声明）。"""
    for r in rows:
        if r.vehicle_id == vehicle_id:
            return r
    return None


def render_all(rows: list[VehicleTelemetry], fmt: Formatter) -> list[str]:
    return [fmt.format(r) for r in rows]


def main() -> None:
    rows = [
        VehicleTelemetry("EV-001", 42.0, 88.0),
        VehicleTelemetry("EV-001", 55.0, 86.5),
        VehicleTelemetry("EV-002", 30.0, 91.0),
    ]
    print(format_row(rows[0]))
    print(avg_speed_by_vehicle(rows))
    hit = find_vehicle(rows, "EV-001")
    print(render_all([hit] if hit else [], SimpleFormatter()))


if __name__ == "__main__":
    main()
