"""test_stats.py —— 分组统计：数量、极值/均值、空输入、过滤。"""

from telemetry_stats.parser import TelemetryRow
from telemetry_stats.stats import filter_vehicle, per_vehicle_stats


def test_per_vehicle_counts(sample_rows: list[TelemetryRow]) -> None:
    stats = per_vehicle_stats(sample_rows)
    assert [s.vehicle_id for s in stats] == ["EV-001", "EV-002"]  # 按车名排序
    assert stats[0].count == 3
    assert stats[1].count == 2


def test_per_vehicle_values(sample_rows: list[TelemetryRow]) -> None:
    stats = per_vehicle_stats(sample_rows)
    ev1, ev2 = stats
    # EV-001 速度 42/55/60：min 42、max 60、avg (42+55+60)/3=52.33；电量 88/86.5/85 → avg 86.5
    assert (ev1.speed_min, ev1.speed_max, ev1.speed_avg) == (42.0, 60.0, 52.33)
    assert (ev1.battery_min, ev1.battery_max, ev1.battery_avg) == (85.0, 88.0, 86.5)
    # EV-002 速度 30/28.5：avg 29.25；电量 91/90.2 → avg 90.6
    assert (ev2.speed_min, ev2.speed_max, ev2.speed_avg) == (28.5, 30.0, 29.25)
    assert (ev2.battery_min, ev2.battery_max, ev2.battery_avg) == (90.2, 91.0, 90.6)


def test_per_vehicle_empty() -> None:
    assert per_vehicle_stats([]) == []


def test_filter_vehicle(sample_rows: list[TelemetryRow]) -> None:
    filtered = filter_vehicle(sample_rows, "EV-001")
    assert len(filtered) == 3
    assert all(r.vehicle_id == "EV-001" for r in filtered)


def test_filter_vehicle_no_match(sample_rows: list[TelemetryRow]) -> None:
    assert filter_vehicle(sample_rows, "EV-999") == []
