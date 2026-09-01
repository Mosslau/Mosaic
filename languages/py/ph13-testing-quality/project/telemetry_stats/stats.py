"""按车辆分组统计：每组的速度/电量 min / max / avg（保留两位小数）。"""

from dataclasses import dataclass

from .parser import TelemetryRow


@dataclass
class VehicleStats:
    """单辆车的统计结果。"""

    vehicle_id: str
    count: int
    speed_min: float
    speed_max: float
    speed_avg: float
    battery_min: float
    battery_max: float
    battery_avg: float


def _round2(value: float) -> float:
    return round(value, 2)


def per_vehicle_stats(rows: list[TelemetryRow]) -> list[VehicleStats]:
    """按 vehicle_id 分组统计，结果按车名排序；空输入返回空列表。"""
    groups: dict[str, list[TelemetryRow]] = {}
    for row in rows:
        groups.setdefault(row.vehicle_id, []).append(row)

    result: list[VehicleStats] = []
    for vid in sorted(groups):
        group = groups[vid]
        speeds = [r.speed for r in group]
        batteries = [r.battery for r in group]
        result.append(
            VehicleStats(
                vehicle_id=vid,
                count=len(group),
                speed_min=_round2(min(speeds)),
                speed_max=_round2(max(speeds)),
                speed_avg=_round2(sum(speeds) / len(speeds)),
                battery_min=_round2(min(batteries)),
                battery_max=_round2(max(batteries)),
                battery_avg=_round2(sum(batteries) / len(batteries)),
            )
        )
    return result


def filter_vehicle(rows: list[TelemetryRow], vehicle_id: str) -> list[TelemetryRow]:
    """只保留指定车辆的行；其余车辆不进入后续统计。"""
    return [r for r in rows if r.vehicle_id == vehicle_id]
