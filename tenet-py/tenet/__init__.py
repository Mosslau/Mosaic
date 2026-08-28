# Tenet — Python 实现（tenet-py）
#
# 与 tenet-rs/ 一一对应的 Python 移植版：
#   token/lexer → ast/parser → env/interpreter → codegen → repl
#
# 设计原则：
# - 纯标准库，零外部依赖
# - 语义与 Rust 版完全一致（词法、语法、错误信息、运行时行为）
# - 代码生成输出与 Rust 版逐字节一致
#
# 使用：
#   cd tenet-py
#   python3 -m tenet run examples/fib.tenet
#   python3 -m tenet repl
#   python3 -m tenet codegen examples/fib.tenet

from .error import Position, TenetError
from .parser import Parser
from .interpreter import Interpreter


def run_source(src: str) -> None:
    """解释执行一段 Tenet 源码。"""
    program = Parser.parse(src)
    Interpreter().run(program)


def codegen_source(src: str) -> str:
    """把一段 Tenet 源码编译为 Go 源码字符串。"""
    program = Parser.parse(src)
    from .codegen import GoCodegen
    return GoCodegen.generate(program)


__all__ = [
    "Position",
    "TenetError",
    "run_source",
    "codegen_source",
]
