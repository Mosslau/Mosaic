# project/streamlog/parser.py —— 解析层：行 → dataclass 结构化记录（主文档 3.2/3.8 的应用）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行/测试/lint：见 project/README.md（python3 -m pytest / ruff check .）
# 验证状态：已验证（Python 3.13.9 本机实测：project/tests 全绿、ruff 全绿）
"""streamlog.parser —— 解析层：把原始行解析为结构化 LogRecord（dataclass）。

默认行语法（可扩展点：想支持时间戳/方括号前缀，改 _LINE_RE 并加测试即可）：

    LEVEL message

LEVEL ∈ {DEBUG, INFO, WARN, ERROR, CRITICAL}；不匹配的行 parse_line 返回 None，
由调用方决定忽略或计数（cli 汇总为 skipped）。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARN", "ERROR", "CRITICAL")

_LINE_RE = re.compile(
    r"^(?P<level>DEBUG|INFO|WARN|ERROR|CRITICAL)"
    r"(?:\s+(?P<message>.*))?$"  # message 可省略（如仅「INFO」级别行）
)


@dataclass(frozen=True, slots=True)
class LogRecord:
    """一行日志的结构化形态。slots 省内存：流式处理海量行时每实例都省。"""

    line_no: int
    level: str
    message: str
    raw: str


def parse_line(line_no: int, raw: str) -> LogRecord | None:
    """单行解析：命中语法产出 LogRecord，否则 None（静默跳过语义由调用方决定）。"""
    match = _LINE_RE.match(raw)
    if match is None:
        return None
    return LogRecord(
        line_no=line_no,
        level=match.group("level"),
        message=match.group("message") or "",  # 无 message 时留空串
        raw=raw,
    )


def parse_lines(lines: Iterator[str], start: int = 1) -> Iterator[LogRecord]:
    """带行号逐行解析的生成器：惰性、一次一行，不落中间大结构。"""
    for line_no, raw in enumerate(lines, start):
        record = parse_line(line_no, raw)
        if record is not None:
            yield record
