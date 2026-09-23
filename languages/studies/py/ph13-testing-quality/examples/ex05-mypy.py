#!/usr/bin/env python3
# examples/ex05-mypy.py —— 类型注解 + mypy 静态检查（主文档 3.5）
# 验证环境：Python 3.13.9 + mypy 1.17.1（本机已装并实测）
# 运行：python3 ex05-mypy.py（离线可跑，已验证）
#      类型检查：mypy ex05-mypy.py（已验证：Success，no issues found）
# 验证状态：已验证 —— 运行输出 3 行；mypy 0 错误
from dataclasses import dataclass
from typing import Protocol


@dataclass
class DeviceTelemetry:
    """一行遥测数据：设备、速度、电量。"""
    device_id: str
    speed: float
    component: float


class Formatter(Protocol):
    """结构类型（Protocol）：任何带 format(DeviceTelemetry) -> str 的对象都可被接受。"""

    def format(self, t: DeviceTelemetry) -> str: ...


class SimpleFormatter:
    def format(self, t: DeviceTelemetry) -> str:
        return f"{t.device_id}: {t.speed:.1f} km/h"


def format_row(t: DeviceTelemetry) -> str:
    return f"{t.device_id},{t.speed:.1f},{t.component:.1f}"


def avg_speed_by_device(rows: list[DeviceTelemetry]) -> dict[str, float]:
    """按设备分组求平均速度；空输入返回空 dict。"""
    speeds: dict[str, list[float]] = {}
    for r in rows:
        speeds.setdefault(r.device_id, []).append(r.speed)
    return {vid: sum(v) / len(v) for vid, v in speeds.items()}


def find_device(rows: list[DeviceTelemetry], device_id: str) -> DeviceTelemetry | None:
    """找指定设备的第一条记录；找不到返回 None（联合类型显式声明）。"""
    for r in rows:
        if r.device_id == device_id:
            return r
    return None


def render_all(rows: list[DeviceTelemetry], fmt: Formatter) -> list[str]:
    return [fmt.format(r) for r in rows]


def main() -> None:
    rows = [
        DeviceTelemetry("EV-001", 42.0, 88.0),
        DeviceTelemetry("EV-001", 55.0, 86.5),
        DeviceTelemetry("EV-002", 30.0, 91.0),
    ]
    print(format_row(rows[0]))
    print(avg_speed_by_device(rows))
    hit = find_device(rows, "EV-001")
    print(render_all([hit] if hit else [], SimpleFormatter()))


if __name__ == "__main__":
    main()
