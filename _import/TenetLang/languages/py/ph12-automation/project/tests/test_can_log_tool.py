# project/tests/test_can_log_tool.py —— CAN 日志批处理工具测试（pytest，离线）
# 验证环境：Python 3.13.9 + pytest 8.4.2；全部用标准库 + pytest tmp_path，不依赖网络
import csv
import logging

import pytest

from can_log_tool import (
    analyze,
    filter_id_frames,
    generate_sample_log,
    main,
    parse_line,
    parse_log,
    stats_by_id,
)


def make_log(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_parse_line_valid(tmp_path):
    f = parse_line("(1629946800.123456) can0 123#1E00000000000000")
    assert f is not None
    assert f.can_id == 0x123
    assert f.data[0] == 0x1E
    assert f.data == bytes.fromhex("1E00000000000000")


def test_parse_line_invalid():
    assert parse_line("garbage") is None
    assert parse_line("") is None
    assert parse_line("(1629946800.1) can0") is None  # 缺 ID#负载


def test_parse_line_empty_payload():
    f = parse_line("(1629946800.123456) can0 123#")
    assert f is not None and f.data == b""


def test_parse_log_counts(tmp_path):
    log = make_log(tmp_path / "can.log", [
        "(1629946800.123456) can0 123#1E00000000000000",
        "(1629946800.300000) can0 245#6480000000000000",
        "broken",
    ])
    frames, invalid = parse_log(log)
    assert len(frames) == 2
    assert invalid == 1


def test_stats_by_id_values(tmp_path):
    log = make_log(tmp_path / "can.log", [
        "(1.0) can0 123#1E00000000000000",  # 30
        "(1.2) can0 123#3C00000000000000",  # 60
        "(1.4) can0 123#2A00000000000000",  # 42
        "(1.6) can0 245#6480000000000000",  # 100
    ])
    frames, _ = parse_log(log)
    stats = stats_by_id(frames)
    assert stats[0x123].count == 3
    assert (stats[0x123].min, stats[0x123].max) == (30, 60)
    assert stats[0x123].avg == 44.0  # (30+60+42)/3
    assert stats[0x245].count == 1


def test_filter_id_frames():
    frames = [
        parse_line("(1.0) can0 123#1E00000000000000"),
        parse_line("(1.1) can0 245#6480000000000000"),
    ]
    filtered = filter_id_frames([f for f in frames if f is not None], 0x123)
    assert len(filtered) == 1
    assert filtered[0].can_id == 0x123


def test_analyze_generates_reports(tmp_path):
    log_path = tmp_path / "sample.log"
    generate_sample_log(log_path)
    out_dir = tmp_path / "reports"
    report = analyze(log_path, out_dir, filter_id=None, logger=logging.getLogger("t1"))
    assert report.total == 12
    assert report.invalid == 1
    assert report.stats[0x123].avg == 45.0
    rows = list(csv.reader((out_dir / "can_report.csv").open(encoding="utf-8")))
    assert len(rows) == 4  # 表头 + 3 个 ID
    assert rows[0] == ["can_id", "信号", "条数", "min", "max", "avg"]
    summary = (out_dir / "summary.txt").read_text(encoding="utf-8")
    assert "总帧数: 12 | 无效行: 1" in summary
    assert "0x123 车速: 6 条 [30, 60] avg 45.0" in summary


def test_analyze_filter_id(tmp_path):
    log_path = tmp_path / "sample.log"
    generate_sample_log(log_path)
    out_dir = tmp_path / "filtered"
    report = analyze(log_path, out_dir, filter_id=0x123, logger=logging.getLogger("t2"))
    assert report.total == 6
    assert list(report.stats) == [0x123]
    rows = list(csv.reader((out_dir / "can_report.csv").open(encoding="utf-8")))
    assert len(rows) == 2  # 表头 + 仅 0x123


def test_analyze_idempotent(tmp_path):
    log_path = tmp_path / "sample.log"
    generate_sample_log(log_path)
    out_dir = tmp_path / "r"
    logger = logging.getLogger("t3")
    analyze(log_path, out_dir, None, logger)
    first_csv = (out_dir / "can_report.csv").read_bytes()
    analyze(log_path, out_dir, None, logger)  # 再次运行：报表被确定性覆盖，无副作用
    assert (out_dir / "can_report.csv").read_bytes() == first_csv
    assert "总帧数: 12" in (out_dir / "summary.txt").read_text(encoding="utf-8")
    assert len(list(out_dir.iterdir())) == 2  # 稳定为两个报表文件


def test_cli_demo_returns_zero():
    assert main(["--demo"]) == 0


def test_cli_requires_input():
    with pytest.raises(SystemExit):
        main([])


def test_cli_filter_flag(tmp_path):
    log_path = tmp_path / "sample.log"
    generate_sample_log(log_path)
    out_dir = tmp_path / "out"
    rc = main(["--input", str(log_path), "--output-dir", str(out_dir), "--filter-id", "0x123"])
    assert rc == 0
    rows = list(csv.reader((out_dir / "can_report.csv").open(encoding="utf-8")))
    assert len(rows) == 2  # 只统计 0x123
