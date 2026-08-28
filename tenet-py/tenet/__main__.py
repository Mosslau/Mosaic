"""Tenet 命令行入口（与 Rust 版 tenet-rs/src/main.rs 行为一致）。

    python3 -m tenet run <file>      # 解释执行 Tenet 源码
    python3 -m tenet codegen <file>  # 编译为 Go 源码（打印到 stdout）
    python3 -m tenet repl            # 交互式 REPL
"""

from __future__ import annotations

import sys

from . import codegen_source, run_source
from .error import TenetError

USAGE = (
    "用法:\n"
    "  tenet run <file>     解释执行\n"
    "  tenet codegen <file> 生成 Go 源码\n"
    "  tenet repl           交互式 REPL"
)


def usage() -> None:
    sys.stderr.write(USAGE + "\n")
    sys.exit(2)


def main() -> None:
    args = sys.argv[1:]
    if not args:
        usage()
    cmd = args[0]

    if cmd == "repl":
        if len(args) != 1:
            usage()
        from . import repl

        repl.run()
        return

    if cmd in ("run", "codegen"):
        if len(args) != 2:
            usage()
        path = args[1]
        try:
            with open(path, encoding="utf-8") as f:
                src = f.read()
        except OSError as e:
            sys.stderr.write(f"无法读取文件 {path}: {e}\n")
            sys.exit(1)
        try:
            if cmd == "run":
                run_source(src)
            else:
                sys.stdout.write(codegen_source(src))
        except TenetError as e:
            sys.stderr.write(f"{e}\n")
            sys.exit(1)
        return

    usage()


if __name__ == "__main__":
    main()
