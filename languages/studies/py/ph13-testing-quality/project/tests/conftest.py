"""conftest.py —— 共享 fixture：样本数据与临时 CSV（练习 2 的 fixture 设计在项目里的落地）。"""

from pathlib import Path

import pytest

from telemetry_stats.parser import TelemetryRow


@pytest.fixture
def sample_rows() -> list[TelemetryRow]:
    """5 条有效遥测：EV-001 × 3、EV-002 × 2（覆盖分组统计与排序）。"""
    return [
        TelemetryRow("2026-09-01 10:00:00", "EV-001", 42.0, 88.0),
        TelemetryRow("2026-09-01 10:01:00", "EV-001", 55.0, 86.5),
        TelemetryRow("2026-09-01 10:02:00", "EV-002", 30.0, 91.0),
        TelemetryRow("2026-09-01 10:03:00", "EV-002", 28.5, 90.2),
        TelemetryRow("2026-09-01 10:04:00", "EV-001", 60.0, 85.0),
    ]


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """CSV 样本：4 有效行 + 2 无效行（"bad,line" 字段数错、负速度越界）。"""
    f = tmp_path / "telemetry.csv"
    f.write_text(
        "ts,device,speed,component\n"
        "2026-09-01 10:00:00,EV-001,42.0,88.0\n"
        "2026-09-01 10:01:00,EV-001,55.0,86.5\n"
        "bad,line\n"
        "2026-09-01 10:02:00,EV-002,30.0,91.0\n"
        "2026-09-01 10:03:00,EV-002,-5.0,90.2\n",
        encoding="utf-8",
    )
    return f
