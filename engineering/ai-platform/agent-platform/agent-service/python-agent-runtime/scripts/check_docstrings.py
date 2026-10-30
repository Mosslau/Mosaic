#!/usr/bin/env python3
"""检查 Runtime 源码、示例和测试的模块、类、函数中文文档覆盖率。

该脚本只检查静态 AST，不导入项目代码，也不会触发 Redis、模型、MCP 或 Sandbox 连接。
它作为代码评审和持续集成的轻量文档质量门禁，避免新增公共协议对象或运行时入口时遗漏说明。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def contains_chinese(value: str | None) -> bool:
    """判断文档字符串是否包含中文说明。"""
    return bool(value and any("\u4e00" <= char <= "\u9fff" for char in value))


def check_file(path: Path) -> list[str]:
    """检查单个 Python 文件的模块、类和函数文档字符串。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems: list[str] = []
    if not contains_chinese(ast.get_docstring(tree)):
        problems.append(f"{path}: 模块缺少中文文档字符串")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            kind = "类"
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "函数"
        else:
            continue
        if not contains_chinese(ast.get_docstring(node)):
            problems.append(f"{path}:{node.lineno}: {kind} {node.name} 缺少中文文档字符串")
    return problems


def main() -> int:
    """检查指定目录并在发现缺失文档时返回非零状态码。"""
    roots = [Path(item) for item in sys.argv[1:]] or [
        Path("src"),
        Path("examples"),
        Path("tests"),
    ]
    files = [path for root in roots for path in root.rglob("*.py")]
    problems = [problem for path in sorted(files) for problem in check_file(path)]
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(f"文档检查通过：{len(files)} 个 Python 文件的模块、类和函数均有中文说明。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
