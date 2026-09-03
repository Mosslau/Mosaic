#!/usr/bin/env python3
# exercises/sol-04-generator-large-file.py —— 练习 4 参考实现：生成器流式处理大文件
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行：python3 sol-04-generator-large-file.py（main 自检，断言失败退出码非 0）
# 测试：python3 -m pytest sol-04-generator-large-file.py -q（收集 test_* 跑断言）
# lint：ruff check sol-04-generator-large-file.py
# 验证状态：已验证（Python 3.13.9 + pytest 8.4.2 本机实测：自检与 pytest 全绿，ruff 全绿）
"""练习 4 参考实现：生成器逐行解析大日志，内存与文件大小无关。

教学点：for line in f 是流式（内部按块读、逐行产出），readlines()/read()
会整读进内存；生成器链（parse → filter/islice → count）每环都惰性。
"""

from __future__ import annotations

import itertools
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

LINE_PATTERN = re.compile(r"^(?P<level>DEBUG|INFO|WARN|ERROR|CRITICAL)\s+(?P<message>.+)$")


@dataclass(frozen=True)
class LogRecord:
    """一行日志的结构化形态：level + message。"""

    level: str
    message: str


def parse_lines(path: str | Path) -> Iterator[LogRecord]:
    """逐行产出结构化记录：不匹配格式的行跳过（静默），文件不存在抛 FileNotFoundError。

    流式保证：只迭代文件对象本身（内部按行缓冲），从不 readlines()/read()。
    """
    with open(path, encoding="utf-8") as f:
        for line in f:  # 流式：一行一行的迭代
            m = LINE_PATTERN.match(line.strip())
            if m:
                yield LogRecord(level=m.group("level"), message=m.group("message"))


def errors_only(records: Iterator[LogRecord]) -> Iterator[LogRecord]:
    """生成器链的一环：只放行 ERROR/CRITICAL。"""
    for r in records:
        if r.level in ("ERROR", "CRITICAL"):
            yield r


def count_levels(records: Iterator[LogRecord]) -> Counter[str]:
    """消费生成器并统计各级别数量——不落任何中间大结构。"""
    return Counter(r.level for r in records)


def build_sample_log(path: Path, rows: int) -> None:
    """现场造一个可预期的日志文件（含若干不合格式的脏行）。"""
    levels = ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]
    with open(path, "w", encoding="utf-8") as f:
        for i in range(rows):
            f.write(f"{levels[i % len(levels)]} message number {i}\n")
        f.write("this line is malformed, no level prefix\n")  # 脏行：应被跳过
        f.write("info lowercase line\n")  # 第二脏行：级别必须大写才匹配


def test_streaming_counts(tmp_path) -> None:
    """统计结果与逐行手算一致（含脏行被跳过）。"""
    path = tmp_path / "sample.log"
    rows = 1000
    build_sample_log(path, rows)
    counter = count_levels(parse_lines(str(path)))
    total = sum(counter.values())
    assert total == rows  # 脏行不计入
    assert counter["INFO"] == rows // 5  # INFO 是 5 种 level 之一，每 5 行出现一次


def test_no_whole_read() -> None:
    """证明流式（AST 证据 + 正确性互补）：
    计数正确性由 test_streaming_counts 用 pytest 的 tmp_path 覆盖（运行 pytest 时生效）；
    这里用 AST 检查 parse_lines 的函数体从不调用 readlines()/read()——
    这是「不整读」的实现证据（用 AST 而非字符串，避免被 docstring 里的字样干扰）。
    """
    import ast
    import inspect

    src = inspect.getsource(parse_lines)
    tree = ast.parse(src)
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    calls = [
        node
        for node in ast.walk(func)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    banned = {"readlines", "read"}
    invoked = {c.func.attr for c in calls}
    assert not (invoked & banned), f"发现整读调用: {invoked & banned}"
    assert "for line in f" in src  # 逐行迭代才是流式


def test_generator_chain_lazy(tmp_path) -> None:
    """生成器链：errors_only 只产出 ERROR/CRITICAL；islice 提前截断。"""
    path = tmp_path / "sample.log"
    build_sample_log(path, 100)
    errs = errors_only(parse_lines(str(path)))
    first_three = list(itertools.islice(errs, 3))
    assert len(first_three) == 3
    assert all(r.level in ("ERROR", "CRITICAL") for r in first_three)


def test_missing_file_message() -> None:
    """文件不存在：FileNotFoundError 原样抛给调用方（由调用方决定展示方式）。"""
    try:
        list(parse_lines("/no/such/log-file.log"))
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("文件不存在必须抛 FileNotFoundError")


def main() -> None:
    import tempfile

    print("== 练习 4 自检 ==")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sample.log"
        rows = 10_000
        build_sample_log(path, rows)
        counter = count_levels(parse_lines(path))
        print(f"10,000 行样本（含脏行）统计: {dict(counter)}")
        print(f"各级别合计 = {sum(counter.values())}（脏行被跳过）")
        errs = errors_only(parse_lines(path))
        print("只取前 2 条 ERROR/CRITICAL:", [r.level for r in itertools.islice(errs, 2)])
        assert sum(counter.values()) == rows  # 与构建参数一致
        assert counter["INFO"] == rows // 5  # INFO 每 5 行一次
    print("流式演示完成（计数正确性断言通过）✓")


if __name__ == "__main__":
    main()
