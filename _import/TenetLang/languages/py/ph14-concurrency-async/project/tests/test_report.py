"""report 测试：CSV 报表的写入、确定性覆盖写与失败行格式（离线，tmp_path 落盘）。"""

from __future__ import annotations

import csv

from collector.fetcher import FetchResult
from collector.report import write_csv


def _mk(
    vehicle_id: str,
    ok: bool,
    attempts: int = 1,
    elapsed_ms: float = 10.0,
    speed: float | None = 50.0,
    battery: float | None = 80.0,
) -> FetchResult:
    return FetchResult(
        vehicle_id=vehicle_id,
        ok=ok,
        status=200 if ok else None,
        attempts=attempts,
        elapsed_ms=elapsed_ms,
        speed=speed,
        battery=battery,
    )


def _read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_write_csv_header_and_rows(tmp_path):
    results = [
        _mk("EV-002", True, speed=66.0),
        _mk("EV-001", False, attempts=3, speed=None, battery=None),  # 失败行留空
    ]
    out = write_csv(results, tmp_path / "report.csv")
    rows = _read_rows(out)
    assert rows[0] == ["vehicle_id", "ok", "status", "attempts", "elapsed_ms", "speed", "battery"]
    # 按 vehicle_id 排序：EV-001 在前
    assert rows[1] == ["EV-001", "fail", "", "3", "10.0", "", ""]
    assert rows[2][:4] == ["EV-002", "ok", "200", "1"]
    assert len(rows) == 3


def test_write_csv_deterministic_overwrite(tmp_path):
    results = [_mk(f"EV-{i:03d}", ok=True) for i in range(5)]
    out = tmp_path / "report.csv"
    write_csv(results, out)
    first = _read_rows(out)
    write_csv(results, out)  # 覆盖写：内容不变、不追加
    assert _read_rows(out) == first


def test_write_csv_creates_parent_dir(tmp_path):
    nested = tmp_path / "a" / "b" / "report.csv"
    out = write_csv([_mk("EV-001", True)], nested)
    assert out.exists()
