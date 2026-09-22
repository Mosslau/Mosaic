"""test_cli.py —— 命令行入口：离线演示自检、缺失输入、端到端跑通。"""

from pathlib import Path

from cli import main


def test_demo_exit_zero(capsys) -> None:
    assert main(["--demo"]) == 0
    captured = capsys.readouterr().out
    assert "自检通过" in captured
    assert "有效 4 | 无效 1 | 车辆 2" in captured


def test_missing_input_returns_2(capsys) -> None:
    assert main([]) == 2
    assert "需要 --input 或 --demo" in capsys.readouterr().err


def test_nonexistent_input_returns_2(capsys) -> None:
    assert main(["--input", "/no/such/file.csv"]) == 2
    assert "输入文件不存在" in capsys.readouterr().err


def test_end_to_end(tmp_path: Path, capsys) -> None:
    source = tmp_path / "in.csv"
    source.write_text(
        "ts,vehicle,speed,battery\n"
        "2026-09-01 10:00:00,EV-001,42.0,88.0\n"
        "2026-09-01 10:01:00,EV-001,55.0,86.5\n",
        encoding="utf-8",
    )
    out = tmp_path / "reports"
    assert main(["--input", str(source), "--output-dir", str(out)]) == 0
    assert (out / "telemetry_report.csv").exists()
    assert (out / "summary.txt").exists()
    assert "完成: 有效 2 行, 无效 0 行, 1 辆车" in capsys.readouterr().out


def test_end_to_end_with_filter(tmp_path: Path, capsys) -> None:
    source = tmp_path / "in2.csv"
    source.write_text(
        "ts,vehicle,speed,battery\n"
        "2026-09-01 10:00:00,EV-001,42.0,88.0\n"
        "2026-09-01 10:02:00,EV-002,30.0,91.0\n",
        encoding="utf-8",
    )
    out = tmp_path / "reports2"
    argv = ["--input", str(source), "--output-dir", str(out), "--filter-vehicle", "EV-001"]
    assert main(argv) == 0
    report = (out / "telemetry_report.csv").read_text(encoding="utf-8")
    assert "EV-002" not in report
    assert "EV-001,1" in report
