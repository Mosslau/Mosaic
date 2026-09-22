"""test_report.py —— 报表输出：CSV 行数/内容、文本汇总内容（tmp_path 落盘核对）。"""

from pathlib import Path

from telemetry_stats.parser import TelemetryRow
from telemetry_stats.report import write_csv_report, write_summary
from telemetry_stats.stats import per_vehicle_stats


def test_write_csv_report_row_count(sample_rows: list[TelemetryRow], tmp_path: Path) -> None:
    stats = per_vehicle_stats(sample_rows)
    out = tmp_path / "report.csv"
    lines = write_csv_report(stats, out)
    assert lines == 3  # 表头 + 2 辆车
    assert len(out.read_text(encoding="utf-8").splitlines()) == 3


def test_write_csv_report_content(sample_rows: list[TelemetryRow], tmp_path: Path) -> None:
    stats = per_vehicle_stats(sample_rows)
    out = tmp_path / "report.csv"
    write_csv_report(stats, out)
    text = out.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0].startswith("vehicle_id,count,speed_min")
    assert lines[1].startswith("EV-001,3,42.0,60.0,52.33")


def test_write_summary_counts(sample_rows: list[TelemetryRow], tmp_path: Path) -> None:
    stats = per_vehicle_stats(sample_rows)
    out = tmp_path / "summary.txt"
    write_summary(sample_rows, invalid=2, stats=stats, out=out, source="sample.csv")
    text = out.read_text(encoding="utf-8")
    assert "source: sample.csv" in text
    assert "valid_rows: 5" in text
    assert "invalid_rows: 2" in text
    assert "vehicles: 2" in text
    assert "EV-001: count=3 speed=[42.0, 60.0] avg=52.33" in text


def test_write_summary_deterministic_except_timestamp(
    sample_rows: list[TelemetryRow], tmp_path: Path
) -> None:
    """除 generated_at 随运行时刻变化外，汇总内容确定性——这是报表可审计的保证。"""
    stats = per_vehicle_stats(sample_rows)
    out1 = tmp_path / "a.txt"
    out2 = tmp_path / "b.txt"
    write_summary(sample_rows, 0, stats, out1)
    write_summary(sample_rows, 0, stats, out2)
    body1 = "\n".join(
        line
        for line in out1.read_text(encoding="utf-8").splitlines()
        if not line.startswith("generated_at:")
    )
    body2 = "\n".join(
        line
        for line in out2.read_text(encoding="utf-8").splitlines()
        if not line.startswith("generated_at:")
    )
    assert body1 == body2
