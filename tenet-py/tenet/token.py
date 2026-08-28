"""词法单元（Token）定义。

与 Rust 版 tenet-rs/src/token.rs 对应。Python 版的 TokenKind 用
字符串常量表示，字面量载荷放在 Token.value 里。

Token = (kind, value, pos)
  - kind：种类常量（见下方）
  - value：载荷——Int/Float/Str 的字面量值，Ident 的名字，其余为 None
  - pos：Position（行列号）
"""

from __future__ import annotations

from .error import Position

# ---- 字面量 ----
INT = "int"
FLOAT = "float"
STR = "str"
IDENT = "ident"

# ---- 关键字 ----
LET = "let"
FN = "fn"
IF = "if"
ELSE = "else"
WHILE = "while"
RETURN = "return"
BREAK = "break"
TRUE = "true"
FALSE = "false"
INT_TYPE = "type:int"
FLOAT_TYPE = "type:float"
BOOL_TYPE = "type:bool"
STR_TYPE = "type:string"

# ---- 符号 ----
LPAREN = "("
RPAREN = ")"
LBRACE = "{"
RBRACE = "}"
COMMA = ","
COLON = ":"
SEMI = ";"
ARROW = "->"
ASSIGN = "="
PLUS = "+"
MINUS = "-"
STAR = "*"
SLASH = "/"
PERCENT = "%"
EQ = "=="
NEQ = "!="
LT = "<"
LTE = "<="
GT = ">"
GTE = ">="
AND = "&&"
OR = "||"
NOT = "!"

EOF = "eof"


class Token:
    __slots__ = ("kind", "value", "pos")

    def __init__(self, kind: str, value=None, pos: Position | None = None):
        self.kind = kind
        self.value = value
        self.pos = pos

    def __repr__(self) -> str:
        return f"Token({self.kind}, {self.value!r}, {self.pos})"


def describe(kind: str, value=None) -> str:
    """人类可读的名字，用于错误信息（如 "expected `;`, found `}`"）。"""
    if kind == INT:
        return "整数"
    if kind == FLOAT:
        return "浮点数"
    if kind == STR:
        return "字符串"
    if kind == IDENT:
        return f"标识符 `{value}`"
    if kind == LET:
        return "`let`"
    if kind == FN:
        return "`fn`"
    if kind == IF:
        return "`if`"
    if kind == ELSE:
        return "`else`"
    if kind == WHILE:
        return "`while`"
    if kind == RETURN:
        return "`return`"
    if kind == BREAK:
        return "`break`"
    if kind == TRUE:
        return "`true`"
    if kind == FALSE:
        return "`false`"
    if kind == INT_TYPE:
        return "类型 `int`"
    if kind == FLOAT_TYPE:
        return "类型 `float`"
    if kind == BOOL_TYPE:
        return "类型 `bool`"
    if kind == STR_TYPE:
        return "类型 `string`"
    if kind == LPAREN:
        return "`(`"
    if kind == RPAREN:
        return "`)`"
    if kind == LBRACE:
        return "`{`"
    if kind == RBRACE:
        return "`}`"
    if kind == COMMA:
        return "`,`"
    if kind == COLON:
        return "`:`"
    if kind == SEMI:
        return "`;`"
    if kind == ARROW:
        return "`->`"
    if kind == ASSIGN:
        return "`=`"
    if kind == PLUS:
        return "`+`"
    if kind == MINUS:
        return "`-`"
    if kind == STAR:
        return "`*`"
    if kind == SLASH:
        return "`/`"
    if kind == PERCENT:
        return "`%`"
    if kind == EQ:
        return "`==`"
    if kind == NEQ:
        return "`!=`"
    if kind == LT:
        return "`<`"
    if kind == LTE:
        return "`<=`"
    if kind == GT:
        return "`>`"
    if kind == GTE:
        return "`>=`"
    if kind == AND:
        return "`&&`"
    if kind == OR:
        return "`||`"
    if kind == NOT:
        return "`!`"
    if kind == EOF:
        return "文件末尾"
    return f"`{kind}`"
