"""运行时值系统。

与 Rust 版 impl-rs/src/value.rs 语义一致。Python 直接用原生类型
表示 Tenet 的值：int → int，float → float，bool → bool，str → string，
None → nil。

关键对齐点：
- int/int 除法是**向零截断**（Rust 语义），不是 Python 的向下取整
- 负数取模同理（Rust: -7 % 2 == -1；Python 默认: -7 % 2 == 1）
- int 与 float 比较互通（1 == 1.0 → true）
- 浮点打印对齐 Rust f64 Display（3.0 显示为 "3"，不用科学计数法）
"""

from __future__ import annotations

from . import ast
from .error import TenetError

_OP_NAMES = {
    ast.OP_ADD: "+",
    ast.OP_SUB: "-",
    ast.OP_MUL: "*",
    ast.OP_DIV: "/",
    ast.OP_MOD: "%",
    ast.OP_EQ: "==",
    ast.OP_NEQ: "!=",
    ast.OP_LT: "<",
    ast.OP_LTE: "<=",
    ast.OP_GT: ">",
    ast.OP_GTE: ">=",
    ast.OP_AND: "&&",
    ast.OP_OR: "||",
}


def type_name(v) -> str:
    """值的类型名（用于错误信息）。"""
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "string"
    return type(v).__name__


def as_type(v) -> str | None:
    """值在类型系统中的类别（None 对应 nil，没有标注类型）。"""
    if v is None:
        return None
    if isinstance(v, bool):
        return ast.T_BOOL
    if isinstance(v, int):
        return ast.T_INT
    if isinstance(v, float):
        return ast.T_FLOAT
    if isinstance(v, str):
        return ast.T_STR
    return None


def matches(v, ty: str) -> bool:
    """值与给定标注类型是否匹配。"""
    return as_type(v) == ty


def fmt_float(v: float) -> str:
    """把浮点格式化为 Rust f64 Display 的形式（最短表示，不用科学计数法）。"""
    s = repr(v)
    if "e" in s or "E" in s:
        # 展开科学计数法：Rust 的 Display 永远是十进制展开
        s = format(v, ".17f")
        if "." in s:
            s = s.rstrip("0").rstrip(".")
    if s.endswith(".0"):
        s = s[:-2]
    return s


def display(v) -> str:
    """值的人类可读输出（print / REPL 用）。"""
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return fmt_float(v)
    return str(v)


def trunc_div(a: int, b: int) -> int:
    """向零截断的整数除法（Rust / Go 语义）。"""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def trunc_mod(a: int, b: int) -> int:
    """与向零截断除法配套的取模（Rust / Go 语义）。"""
    return a - trunc_div(a, b) * b


def apply_binary(a, op: str, b) -> object:
    """二元运算。规则与 Rust 版 value.rs 完全一致。"""
    # ---- 整数 × 整数 ----
    if isinstance(a, int) and isinstance(b, int):
        if op == ast.OP_ADD:
            return a + b
        if op == ast.OP_SUB:
            return a - b
        if op == ast.OP_MUL:
            return a * b
        if op == ast.OP_DIV:
            if b == 0:
                raise TenetError("整数除以零")
            return trunc_div(a, b)
        if op == ast.OP_MOD:
            if b == 0:
                raise TenetError("整数取模零")
            return trunc_mod(a, b)
        if op == ast.OP_EQ:
            return a == b
        if op == ast.OP_NEQ:
            return a != b
        if op == ast.OP_LT:
            return a < b
        if op == ast.OP_LTE:
            return a <= b
        if op == ast.OP_GT:
            return a > b
        if op == ast.OP_GTE:
            return a >= b
        raise _type_err(op, a, b)

    # ---- 数值混合（int × float / float × int / float × float）----
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        x, y = float(a), float(b)
        if op == ast.OP_ADD:
            return x + y
        if op == ast.OP_SUB:
            return x - y
        if op == ast.OP_MUL:
            return x * y
        if op == ast.OP_DIV:
            if y == 0.0:
                raise TenetError("浮点除以零")
            return x / y
        if op == ast.OP_EQ:
            return x == y
        if op == ast.OP_NEQ:
            return x != y
        if op == ast.OP_LT:
            return x < y
        if op == ast.OP_LTE:
            return x <= y
        if op == ast.OP_GT:
            return x > y
        if op == ast.OP_GTE:
            return x >= y
        # `%` 只支持 int：镜像 Rust 的 numeric_float
        raise TenetError(f"运算符 `{_OP_NAMES[op]}` 不能作用于 float")

    # ---- 字符串 × 字符串 ----
    if isinstance(a, str) and isinstance(b, str):
        if op == ast.OP_ADD:
            return a + b
        if op == ast.OP_EQ:
            return a == b
        if op == ast.OP_NEQ:
            return a != b
        if op == ast.OP_LT:
            return a < b
        if op == ast.OP_LTE:
            return a <= b
        if op == ast.OP_GT:
            return a > b
        if op == ast.OP_GTE:
            return a >= b
        raise _type_err(op, a, b)

    # ---- 布尔 × 布尔（仅 == / !=）----
    if isinstance(a, bool) and isinstance(b, bool):
        if op == ast.OP_EQ:
            return a == b
        if op == ast.OP_NEQ:
            return a != b
        raise _type_err(op, a, b)

    raise _type_err(op, a, b)


def apply_unary(v, op: str) -> object:
    """一元运算：`-` 数值取负，`!` 布尔取反。"""
    if op == ast.OP_NEG:
        if isinstance(v, int):
            return -v
        if isinstance(v, float):
            return -v
        raise TenetError(f"一元运算符 `-` 不能作用于 {type_name(v)}")
    if op == ast.OP_NOT:
        if isinstance(v, bool):
            return not v
        raise TenetError(f"一元运算符 `!` 不能作用于 {type_name(v)}")
    raise TenetError(f"未知的一元运算符 `{op}`")


def expect_bool(v) -> bool:
    """把值解释为条件（必须是真的 bool）。"""
    if isinstance(v, bool):
        return v
    raise TenetError(f"条件表达式需要 bool，实际为 {type_name(v)}")


def _type_err(op: str, a, b) -> TenetError:
    return TenetError(
        f"运算符 `{_OP_NAMES[op]}` 不能作用于 {type_name(a)} 和 {type_name(b)}"
    )
