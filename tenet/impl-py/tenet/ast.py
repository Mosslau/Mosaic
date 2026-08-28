"""抽象语法树（AST）：语法分析器的输出，解释器与代码生成器的共同输入。

与 Rust 版 impl-rs/src/ast.rs 对应。类型直接用字符串常量表示：
"int" / "float" / "bool" / "string"。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 类型常量
T_INT = "int"
T_FLOAT = "float"
T_BOOL = "bool"
T_STR = "string"

# 运算符常量（与 token 模块的符号一致）
OP_ADD = "+"
OP_SUB = "-"
OP_MUL = "*"
OP_DIV = "/"
OP_MOD = "%"
OP_EQ = "=="
OP_NEQ = "!="
OP_LT = "<"
OP_LTE = "<="
OP_GT = ">"
OP_GTE = ">="
OP_AND = "&&"
OP_OR = "||"
OP_NEG = "-"  # 一元取负
OP_NOT = "!"  # 一元取反


# ---- 表达式 ----

class Expr:
    pass


@dataclass
class IntLit(Expr):
    value: int


@dataclass
class FloatLit(Expr):
    value: float


@dataclass
class StrLit(Expr):
    value: str


@dataclass
class BoolLit(Expr):
    value: bool


@dataclass
class Var(Expr):
    name: str


@dataclass
class Assign(Expr):
    name: str
    value: Expr


@dataclass
class Unary(Expr):
    op: str
    expr: Expr


@dataclass
class Binary(Expr):
    op: str
    lhs: Expr
    rhs: Expr


@dataclass
class Call(Expr):
    callee: str
    args: list = field(default_factory=list)


# ---- 语句 ----

class Stmt:
    pass


@dataclass
class Let(Stmt):
    name: str
    ty: str | None
    value: Expr


@dataclass
class ExprStmt(Stmt):
    expr: Expr


@dataclass
class If(Stmt):
    cond: Expr
    then_branch: list = field(default_factory=list)
    else_branch: list | None = None


@dataclass
class While(Stmt):
    cond: Expr
    body: list = field(default_factory=list)


@dataclass
class Return(Stmt):
    expr: Expr | None = None


@dataclass
class Break(Stmt):
    pass


@dataclass
class Block(Stmt):
    stmts: list = field(default_factory=list)


@dataclass
class FnDecl(Stmt):
    name: str
    params: list = field(default_factory=list)  # [(参数名, 类型), ...]
    ret: str | None = None
    body: list = field(default_factory=list)


# ---- 程序 ----

@dataclass
class Program:
    stmts: list = field(default_factory=list)
