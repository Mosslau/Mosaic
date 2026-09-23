"""test_parser.py —— 解析与清洗：参数化覆盖字段数、数值、范围三类非法输入。"""

from pathlib import Path

import pytest

from telemetry_stats.parser import parse_csv, parse_row


def test_parse_row_valid() -> None:
    row = parse_row("2026-09-01 10:00:00,EV-001,42.0,88.0")
    assert row is not None
    assert row.device_id == "EV-001"
    assert row.speed == 42.0
    assert row.component == 88.0


@pytest.mark.parametrize(
    "line",
    [
        "a,b,c",  # 字段数不足
        "a,b,c,d,e",  # 字段数过多
        "t,v,not-a-number,88.0",  # 速度非数值
        "t,v,42.0,abc",  # 电量非数值
        "t,v,-1.0,88.0",  # 负速度
        "t,v,42.0,101.0",  # 电量越界（>100）
    ],
)
def test_parse_row_invalid(line: str) -> None:
    assert parse_row(line) is None


def test_parse_csv_counts(sample_csv: Path) -> None:
    rows, invalid = parse_csv(sample_csv)
    assert len(rows) == 3  # 有效 3 行（EV-001×2 + EV-002×1）
    assert invalid == 2  # 无效 2 行（bad,line 字段数错 + 负速度越界）


def test_parse_csv_skips_header_and_blank(tmp_path: Path) -> None:
    f = tmp_path / "blank.csv"
    f.write_text("ts,device,speed,component\n\nEV-001,42.0,88.0,extra\n", encoding="utf-8")
    rows, invalid = parse_csv(f)
    assert rows == []  # 表头与空行都被跳过，剩下 1 行非法
    assert invalid == 1


def test_parse_csv_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "empty.csv"
    f.write_text("", encoding="utf-8")
    rows, invalid = parse_csv(f)
    assert rows == []
    assert invalid == 0
