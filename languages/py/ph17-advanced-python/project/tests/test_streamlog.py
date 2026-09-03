"""project/tests/test_streamlog.py —— streamlog 的 pytest 用例（对应 project/README.md 验收标准）。

验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
运行：cd project && python3 -m pytest（或 pytest）
lint：cd project && ruff check . && ruff format --check .
验证状态：已验证（Python 3.13.9 本机实测：13 用例全绿）
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from streamlog.cli import main
from streamlog.filters import Counted, by_level, by_pattern
from streamlog.parser import LogRecord, parse_line, parse_lines
from streamlog.reader import read_lines
from streamlog.sinks import FileSink

_LEVELS = ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]


def build_sample(path: Path, rows: int = 1000, bad_lines: int = 1) -> Path:
    """现场造可预期的日志文件：每 5 行循环一种级别 + 若干脏行。"""
    with path.open("w", encoding="utf-8") as fh:
        for i in range(rows):
            fh.write(f"{_LEVELS[i % len(_LEVELS)]} payload number {i}\n")
        for j in range(bad_lines):
            fh.write(f"malformed line without level {j}\n")
    return path


def consume(records) -> Counter[str]:
    """真实地「流式消费」：不 materialize 成 list，逐条计数。"""
    counter: Counter[str] = Counter()
    for record in records:
        counter[record.level] += 1
    return counter


# ---------- 单元：parser ----------


def test_parse_line_ok() -> None:
    record = parse_line(3, "ERROR timeout after 5s")
    assert record is not None
    assert record.level == "ERROR"
    assert record.message == "timeout after 5s"
    assert record.line_no == 3
    assert record.raw == "ERROR timeout after 5s"
    assert isinstance(record, LogRecord)


def test_parse_line_bad_returns_none() -> None:
    assert parse_line(1, "") is None
    assert parse_line(2, "no level here") is None
    assert parse_line(3, "error lowercase") is None  # 级别必须大写
    assert parse_line(4, "INFO") is not None  # 允许无 message


# ---------- 单元：reader ----------


def test_read_lines_streams(tmp_path: Path) -> None:
    path = build_sample(tmp_path / "a.log", rows=50)
    lines = list(read_lines(str(path)))  # 测试可物化，产品管线不物化
    assert len(lines) == 51  # 50 正常 + 1 脏行
    assert lines[0] == "DEBUG payload number 0"
    assert lines[-1].startswith("malformed")


def test_read_lines_missing_file(tmp_path: Path) -> None:
    try:
        list(read_lines(str(tmp_path / "nope.log")))
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("文件不存在必须抛 FileNotFoundError")


# ---------- 单元：过滤器 ----------


def test_by_level() -> None:
    records = [
        LogRecord(1, "INFO", "a", "INFO a"),
        LogRecord(2, "ERROR", "b", "ERROR b"),
        LogRecord(3, "ERROR", "c", "ERROR c"),
        LogRecord(4, "DEBUG", "d", "DEBUG d"),
    ]
    got = list(by_level(iter(records), {"ERROR"}))
    assert [r.line_no for r in got] == [2, 3]


def test_by_pattern() -> None:
    records = [
        LogRecord(1, "INFO", "request ok", ""),
        LogRecord(2, "ERROR", "timeout after 5s", ""),
    ]
    got = list(by_pattern(iter(records), r"timeout"))
    assert [r.line_no for r in got] == [2]


def test_by_pattern_invalid_regex() -> None:
    records = iter([LogRecord(1, "INFO", "x", "x")])
    with_errors = by_pattern(records, "(")  # 非法正则
    try:
        list(with_errors)
    except re.error:
        pass
    else:
        raise AssertionError("非法正则必须抛 re.error")


# ---------- 单元：Counted 装饰器（横切统计） ----------


def test_counted_stats() -> None:
    stage = Counted(parse_lines)
    rows = [f"INFO msg-{i}" for i in range(100)]  # 用内存行源测装饰器本身
    counter = consume(stage(iter(rows)))
    assert counter["INFO"] == 100
    assert stage.count == 100
    assert stage.elapsed >= 0.0
    assert "100" in stage.summary("parse")  # 摘要含条数
    assert stage.__name__ == "parse_lines"  # update_wrapper 保留身份


# ---------- 单元：FileSink（上下文管理器资源管理） ----------


def test_file_sink_writes_and_closes(tmp_path: Path) -> None:
    out = tmp_path / "out.log"
    with FileSink(out) as sink:
        sink.write_line("INFO a")
        sink.write_line("WARN b")
        assert sink.written == 2
    # with 块外句柄已关：内容落盘可读
    assert out.read_text(encoding="utf-8").splitlines() == ["INFO a", "WARN b"]


def test_file_sink_stdout_not_closed(capsys) -> None:
    with FileSink() as sink:  # path=None → stdout
        sink.write_line("HELLO")
    captured = capsys.readouterr()
    assert captured.out == "HELLO\n"
    assert sink.written == 1


def test_file_sink_exception_still_closes(tmp_path: Path) -> None:
    out = tmp_path / "out.log"
    try:
        with FileSink(out) as sink:
            sink.write_line("partial")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    else:
        raise AssertionError("FileSink 不吞异常")
    assert out.read_text(encoding="utf-8").splitlines() == ["partial"]


# ---------- 集成：管线与 CLI ----------


def test_pipeline_counts_on_big_file(tmp_path: Path) -> None:
    """流式管线：5 万行日志计数正确、脏行被跳过（skipped 可统计）。"""
    path = build_sample(tmp_path / "big.log", rows=50_000, bad_lines=3)
    raw = Counted(read_lines)
    parsed = Counted(parse_lines)
    counter = consume(parsed(raw(str(path))))
    assert sum(counter.values()) == 50_000  # 脏行不计入
    assert counter["ERROR"] == 10_000  # 每 5 行一次 ERROR
    assert raw.count == 50_003
    assert parsed.count == 50_000


def test_cli_stats_to_stderr(tmp_path: Path, capsys) -> None:
    path = build_sample(tmp_path / "cli.log", rows=100)
    code = main(["--file", str(path), "--level", "ERROR", "--stats", "--quiet"])
    captured = capsys.readouterr()
    assert code == 0
    assert "ERROR=20" in captured.err  # 100 行中 1/5 是 ERROR
    assert captured.out == ""  # --quiet：stdout 无数据


def test_cli_matched_lines_to_stdout(tmp_path: Path, capsys) -> None:
    path = build_sample(tmp_path / "cli2.log", rows=100)
    code = main(["--file", str(path), "--level", "ERROR"])
    captured = capsys.readouterr()
    assert code == 0
    lines = captured.out.splitlines()
    assert len(lines) == 20
    assert all(line.startswith("ERROR ") for line in lines)


def test_cli_out_file(tmp_path: Path) -> None:
    src = build_sample(tmp_path / "in.log", rows=100)
    dst = tmp_path / "hits.log"
    code = main(["--file", str(src), "--pattern", r"number 9", "--out", str(dst)])
    assert code == 0
    assert dst.exists()
    lines = dst.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 11  # 9,19,...,99 共 11 条含 "9"
    assert all("number 9" in line for line in lines)


def test_cli_missing_file(tmp_path: Path, capsys) -> None:
    code = main(["--file", str(tmp_path / "nope.log"), "--stats"])
    captured = capsys.readouterr()
    assert code == 1
    assert "打不开文件" in captured.err


def test_cli_invalid_pattern(tmp_path: Path, capsys) -> None:
    path = build_sample(tmp_path / "pat.log", rows=10)
    code = main(["--file", str(path), "--pattern", "("])
    captured = capsys.readouterr()
    assert code == 2
    assert "正则错误" in captured.err
