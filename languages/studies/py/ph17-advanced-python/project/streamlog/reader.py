# project/streamlog/reader.py —— 读取层：逐行流式迭代（主文档 3.1/3.2 的应用）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行/测试/lint：见 project/README.md（python3 -m pytest / ruff check .）
# 验证状态：已验证（Python 3.13.9 本机实测：project/tests 全绿、ruff 全绿）
"""streamlog.reader —— 读取层：把数据源变成逐行迭代器（生成器流式，主文档 3.1/3.2）。"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path


def read_lines(source: str | Path = "-") -> Iterator[str]:
    """逐行产出文本（去掉行尾换行）；`"-"` 表示从标准输入读取。

    流式保证：本函数只迭代文件对象 / sys.stdin，从不调用 read()/readlines()，
    因此内存占用与文件大小无关——管线第一环，见 project/README.md 的管线图。
    """
    if source == "-":
        for line in sys.stdin:
            yield line.rstrip("\n")
        return
    with open(source, encoding="utf-8") as fh:
        for line in fh:
            yield line.rstrip("\n")
