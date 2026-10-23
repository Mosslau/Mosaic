"""让各实验目录可以一起被 pytest 收集。

实验测试统一叫 `test_impl.py`，且用 `from impl import ...` 导入同目录实现；
pytest 默认的 prepend 模式会把它们当成同一个顶层模块。这里在收集每个测试文件前
把其目录放到 sys.path 前面，并清掉同名实验模块，配合 `--import-mode=importlib`
即可逐文件隔离；单独跑某个目录时行为不变。
"""

from __future__ import annotations

import sys
from pathlib import Path

_LOCAL_MODULES = {"impl", "demo", "framework", "baseline"}


def _activate(file_path: Path) -> None:
    sys.path.insert(0, str(file_path.parent))
    for name in _LOCAL_MODULES:
        sys.modules.pop(name, None)


def pytest_collect_file(file_path: Path, parent):
    if file_path.name.startswith("test_") and file_path.suffix == ".py":
        _activate(file_path)
    return None


def pytest_runtest_setup(item):
    # 测试函数内部可能延迟 import framework/impl；执行前再切回本目录。
    _activate(item.path)
