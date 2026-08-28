"""交互式 REPL：逐行读取、执行、打印结果。

与 Rust 版 tenet-rs/src/repl.rs 行为一致：

- 花括号不闭合时继续读取下一行（简易多行支持）
- 缺分号时自动补 `;` 重试（REPL 习惯）
- 单条非 print 表达式 → 求值并回显
- `exit` / `quit` 或 Ctrl-D 退出
- 复用同一个 Interpreter 实例 → 跨行记住变量与函数
"""

from __future__ import annotations

import sys

from . import ast
from .error import TenetError
from .interpreter import Interpreter
from .parser import Parser

BANNER = """
🏛 Tenet REPL — 万语归宗，探语言之本源
输入 Tenet 语句，`exit` 或 Ctrl-D 退出。
"""


def run() -> None:
    interp = Interpreter()
    buffer = ""

    sys.stdout.write(BANNER)
    while True:
        prompt = "tenet> " if buffer == "" else "     > "
        sys.stdout.write(prompt)
        sys.stdout.flush()

        line = sys.stdin.readline()
        if line == "":
            # EOF
            sys.stdout.write("\n")
            break
        if line.strip() in ("exit", "quit"):
            break
        buffer += line

        # 括号未配平 → 继续收集输入
        if not balanced(buffer):
            continue

        src = buffer
        buffer = ""
        try:
            program = Parser.parse(src)
            _run_parsed(interp, program)
        except TenetError as e:
            # REPL 习惯不写分号：若错误只是「期望 `;` 但遇到 EOF」，补上分号重试
            trimmed = src.rstrip()
            if (
                "`;`" in e.message
                and e.pos is not None
                and e.pos.line >= src.count("\n") + 1
                and not trimmed.endswith(";")
            ):
                try:
                    program = Parser.parse(src + ";")
                    _run_parsed(interp, program)
                    continue
                except TenetError:
                    pass
            sys.stderr.write(f"{e}\n")


def _run_parsed(interp: Interpreter, program: ast.Program) -> None:
    """执行解析结果：单条非 print 表达式 → 求值回显；否则作为程序执行。"""
    if len(program.stmts) == 1:
        stmt = program.stmts[0]
        if isinstance(stmt, ast.ExprStmt):
            expr = stmt.expr
            is_print = isinstance(expr, ast.Call) and expr.callee == "print"
            if not is_print:
                v = interp.eval_expr(expr)
                if v is not None:
                    from . import value as val

                    sys.stdout.write(val.display(v) + "\n")
                return
    interp.run_program(program)


def balanced(src: str) -> bool:
    """粗略判断花括号 / 括号 / 方括号是否配平（忽略字符串与注释内的括号）。"""
    stack = []
    in_str = False
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if in_str:
            if c == "\\":
                i += 1  # 跳过转义的下一个字符
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
        elif c in "({[":
            stack.append(c)
        elif c in ")}]":
            open_c = {"}": "{", ")": "(", "]": "["}[c]
            if not stack or stack.pop() != open_c:
                return True  # 配不上，交给 parser 报错
        i += 1
    return not in_str and not stack
