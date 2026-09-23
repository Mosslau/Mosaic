"""按设备分组统计：每组的速度/电量 min / max / avg（保留两位小数）。"""

from dataclasses import dataclass

from .parser import TelemetryRow


@dataclass
class DeviceStats:
    """单台设备的统计结果。"""

    device_id: str
    count: int
    speed_min: float
    speed_max: float
    speed_avg: float
    component_min: float
    component_max: float
    component_avg: float


def _round2(value: float) -> float:
    return round(value, 2)


def per_device_stats(rows: list[TelemetryRow]) -> list[DeviceStats]:
    """按 device_id 分组统计，结果按设备名排序；空输入返回空列表。"""
    groups: dict[str, list[TelemetryRow]] = {}
    for row in rows:
        groups.setdefault(row.device_id, []).append(row)

    result: list[DeviceStats] = []
    for vid in sorted(groups):
        group = groups[vid]
        speeds = [r.speed for r in group]
        batteries = [r.component for r in group]
        result.append(
            DeviceStats(
                device_id=vid,
                count=len(group),
                speed_min=_round2(min(speeds)),
                speed_max=_round2(max(speeds)),
                speed_avg=_round2(sum(speeds) / len(speeds)),
                component_min=_round2(min(batteries)),
                component_max=_round2(max(batteries)),
                component_avg=_round2(sum(batteries) / len(batteries)),
            )
        )
    return result


def filter_device(rows: list[TelemetryRow], device_id: str) -> list[TelemetryRow]:
    """只保留指定设备的行；其余设备不进入后续统计。"""
    return [r for r in rows if r.device_id == device_id]
