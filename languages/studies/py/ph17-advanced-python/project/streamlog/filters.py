# project/streamlog/filters.py —— 横切与过滤层（主文档 3.3 的应用）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行/测试/lint：见 project/README.md（python3 -m pytest / ruff check .）
# 验证状态：已验证（Python 3.13.9 本机实测：project/tests 全绿、ruff 全绿）
"""streamlog.filters —— 横切与过滤层（主文档 3.3）。

Counted 装饰器把「产出计数 + 总耗时」从管线业务里横切出来——业务函数
（read_lines/parse_lines）保持纯净，统计由装饰器注入，这正是
「装饰器适合横切逻辑」（roadmap 必会概念）在真实工具里的落点。
"""

from __future__ import annotations

import functools
import re
import time
from collections.abc import Callable, Iterator
from typing import Any

from streamlog.parser import LogRecord


class Counted:
    """装饰「返回迭代器」的函数：每次调用重置计数，消费时累加产出条数与耗时。

    用法（实例即装饰器）：
        stage = Counted(read_lines)
        for line in stage(path): ...
        stage.summary("read")      # "read: 1200 条 / 0.012s"
    """

    def __init__(self, func: Callable[..., Iterator[Any]]) -> None:
        functools.update_wrapper(self, func)  # 保持函数身份（可被工具链识别）
        self.func = func
        self.count = 0
        self.elapsed = 0.0

    def __call__(self, *args: Any, **kwargs: Any) -> Iterator[Any]:
        self.count = 0
        self.elapsed = 0.0
        start = time.perf_counter()
        try:
            for item in self.func(*args, **kwargs):
                self.count += 1
                yield item
        finally:
            self.elapsed = time.perf_counter() - start

    def summary(self, label: str) -> str:
        """横切统计的可读报告（由 cli 在 --stats 时拼进 stderr）。"""
        return f"{label}: {self.count} 条 / {self.elapsed:.3f}s"


def by_level(records: Iterator[LogRecord], levels: set[str]) -> Iterator[LogRecord]:
    """只放行指定级别的记录（过滤也是惰性生成器，链上的一环）。"""
    for record in records:
        if record.level in levels:
            yield record


def by_pattern(records: Iterator[LogRecord], pattern: str) -> Iterator[LogRecord]:
    """只放行 message 匹配正则的记录；pattern 非法时抛 re.error（调用方处理）。"""
    regex = re.compile(pattern)
    for record in records:
        if regex.search(record.message):
            yield record
