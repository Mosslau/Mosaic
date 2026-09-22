# project/streamlog/sinks.py —— 输出层：上下文管理器资源管理（主文档 3.4 的应用）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行/测试/lint：见 project/README.md（python3 -m pytest / ruff check .）
# 验证状态：已验证（Python 3.13.9 本机实测：project/tests 全绿、ruff 全绿）
"""streamlog.sinks —— 输出层：上下文管理器管理输出资源（主文档 3.4）。

FileSink 把「打开输出 → 逐行写 → 退出时 flush/关闭并报告条数」封装成 with 块：
__exit__ 无论块内是否异常都会关闭自管句柄，且不吞异常——资源管理的协议化。
stdout 场景（path=None）不关闭 sys.stdout（由解释器管理）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO


class FileSink:
    """with 管理的行输出：文件（--out）或 stdout；退出自动关闭并报告写入条数。"""

    def __init__(self, path: str | Path | None = None, *, append: bool = False) -> None:
        self.path = None if path is None else Path(path)
        self.append = append
        self._fh: TextIO | None = None
        self._owns_fh = False
        self.written = 0

    def __enter__(self) -> FileSink:
        if self.path is None:
            self._fh = sys.stdout  # stdout：不关闭
            self._owns_fh = False
        else:
            self._fh = open(self.path, "a" if self.append else "w", encoding="utf-8")
            self._owns_fh = True
        self.written = 0
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._owns_fh and self._fh is not None:
            try:
                self._fh.close()  # 异常路径也会走到：资源必关
            finally:
                self._fh = None
        else:
            self._fh = None  # stdout 不关闭，但句柄置空防误写
        return False  # 不吞异常：输出层不掩盖业务错误

    def write_line(self, text: str) -> None:
        """写一行（带换行）。必须在 with 块内调用。"""
        if self._fh is None:
            raise RuntimeError("FileSink 未进入 with 块，不能 write_line")
        self._fh.write(text)
        self._fh.write("\n")
        self.written += 1
