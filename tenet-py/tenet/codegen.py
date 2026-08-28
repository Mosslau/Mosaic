"""代码生成器（Codegen）：把 Tenet AST 编译成 Go 源码。

与 Rust 版 tenet-rs/src/codegen.rs 完全对应——生成结果**逐字节一致**：

| Tenet | Go |
|-------|----|
| `int` / `float` / `bool` / `string` | `int64` / `float64` / `bool` / `string` |
| `let x: T = v;` | `var x T = v;` |
| `while (c) { }` | `for (c) { }`（Go 没有 while） |
| `print(...)` | `fmt.Println(...)` |
| `fn f(a: int) -> int { }` | `func f(a int64) int64 { }` |

`let` 省略类型标注时由 `infer_type` 静态推断，规则与解释器语义一致。
"""

from __future__ import annotations

from . import ast
from . import value as val
from .error import TenetError

_GO_TYPE = {
    ast.T_INT: "int64",
    ast.T_FLOAT: "float64",
    ast.T_BOOL: "bool",
    ast.T_STR: "string",
}


def go_type(t: str) -> str:
    return _GO_TYPE[t]


def go_binop(op: str) -> str:
    return op  # Tenet 与 Go 的运算符符号完全一致


class GoCodegen:
    def __init__(self):
        self.out: list[str] = []
        self.indent = 0
        # 当前作用域内可见的变量类型
        self.symbols: dict[str, str] = {}
        # 全局函数签名表：name -> (返回类型或 None)
        self.functions: dict[str, str | None] = {}

    @classmethod
    def generate(cls, program: ast.Program) -> str:
        gen = cls()
        gen.collect_signatures(program)
        gen.emit_program(program)
        return "".join(gen.out)

    # ---- 输出辅助（与 Rust push 行为一致）----

    def push(self, line: str) -> None:
        if line == "":
            self.out.append("\n")
            return
        self.out.append("\t" * self.indent + line + "\n")

    # ---- 预处理 ----

    def collect_signatures(self, program: ast.Program) -> None:
        for stmt in program.stmts:
            if isinstance(stmt, ast.FnDecl):
                if stmt.name in self.functions:
                    raise TenetError(f"函数 `{stmt.name}` 重复定义")
                self.functions[stmt.name] = stmt.ret

    # ---- 顶层 ----

    def emit_program(self, program: ast.Program) -> None:
        self.push("package main")
        self.push("")

        if program_uses_print(program):
            self.push('import "fmt"')
            self.push("")

        # 函数声明 → 包级 func
        for stmt in program.stmts:
            if isinstance(stmt, ast.FnDecl):
                self.emit_stmt(stmt)
                self.push("")

        # 其余顶层语句 → main
        self.push("func main() {")
        self.indent += 1
        for stmt in program.stmts:
            if not isinstance(stmt, ast.FnDecl):
                self.emit_stmt(stmt)
        self.indent -= 1
        self.push("}")

    # ---- 语句 ----

    def emit_stmt(self, stmt: ast.Stmt) -> None:
        if isinstance(stmt, ast.Let):
            t = stmt.ty
            if t is None:
                t = self.infer_type(stmt.value)
                if t is None:
                    raise TenetError(f"无法推断 `{stmt.name}` 的类型，请显式标注")
            self.symbols[stmt.name] = t
            v = self.emit_expr(stmt.value)
            self.push(f"var {stmt.name} {go_type(t)} = {v};")
            return

        if isinstance(stmt, ast.ExprStmt):
            expr = stmt.expr
            if isinstance(expr, ast.Call):
                args = ", ".join(self.emit_expr(a) for a in expr.args)
                if expr.callee == "print":
                    self.push(f"fmt.Println({args});")
                else:
                    self.push(f"{expr.callee}({args});")
                return
            if isinstance(expr, ast.Assign):
                v = self.emit_expr(expr.value)
                self.push(f"{expr.name} = {v};")
                return
            raise TenetError("语句必须是函数调用或赋值")

        if isinstance(stmt, ast.If):
            self.emit_if(stmt.cond, stmt.then_branch, stmt.else_branch, "")
            return

        if isinstance(stmt, ast.While):
            c = self.emit_expr(stmt.cond)
            self.push(f"for {c} {{")
            self.indent += 1
            for s in stmt.body:
                self.emit_stmt(s)
            self.indent -= 1
            self.push("}")
            return

        if isinstance(stmt, ast.Return):
            if stmt.expr is not None:
                v = self.emit_expr(stmt.expr)
                self.push(f"return {v};")
            else:
                self.push("return;")
            return

        if isinstance(stmt, ast.Break):
            self.push("break;")
            return

        if isinstance(stmt, ast.Block):
            self.push("{")
            self.indent += 1
            for s in stmt.stmts:
                self.emit_stmt(s)
            self.indent -= 1
            self.push("}")
            return

        if isinstance(stmt, ast.FnDecl):
            sig_params = ", ".join(f"{n} {go_type(t)}" for n, t in stmt.params)
            ret = go_type(stmt.ret) if stmt.ret else ""
            if ret:
                sig = f"{stmt.name}({sig_params}) {ret}"
            else:
                sig = f"{stmt.name}({sig_params})"
            self.push(f"func {sig} {{")
            self.indent += 1
            # 参数进入符号表（函数体结束后恢复）
            saved = dict(self.symbols)
            for n, t in stmt.params:
                self.symbols[n] = t
            for s in stmt.body:
                self.emit_stmt(s)
            self.indent -= 1
            self.push("}")
            self.symbols = saved
            return

        raise TenetError(f"未知的语句类型: {type(stmt).__name__}")

    def emit_if(self, cond, then_branch, else_branch, prefix: str) -> None:
        c = self.emit_expr(cond)
        self.push(f"{prefix}if {c} {{")
        self.indent += 1
        for s in then_branch:
            self.emit_stmt(s)
        self.indent -= 1
        if else_branch is not None:
            # else if 链：单条 if 语句的 else 分支 → Go 的 `} else if ...`
            if len(else_branch) == 1 and isinstance(else_branch[0], ast.If):
                nested = else_branch[0]
                self.emit_if(nested.cond, nested.then_branch, nested.else_branch, "} else ")
            else:
                self.push("} else {")
                self.indent += 1
                for s in else_branch:
                    self.emit_stmt(s)
                self.indent -= 1
                self.push("}")
        else:
            self.push("}")

    # ---- 表达式 ----

    def emit_expr(self, expr: ast.Expr) -> str:
        if isinstance(expr, ast.IntLit):
            return str(expr.value)
        if isinstance(expr, ast.FloatLit):
            # Rust 的 f64 Display 会把 2.0 打印成 "2"，需要补回小数点，
            # 否则 Go 里 7 / 2.0 会变成整数除法 7 / 2
            s = val.fmt_float(expr.value)
            if "." not in s:
                s += ".0"
            return s
        if isinstance(expr, ast.StrLit):
            return go_string(expr.value)
        if isinstance(expr, ast.BoolLit):
            return "true" if expr.value else "false"
        if isinstance(expr, ast.Var):
            return expr.name
        if isinstance(expr, ast.Assign):
            return f"{expr.name} = {self.emit_expr(expr.value)}"
        if isinstance(expr, ast.Unary):
            inner = self.emit_expr(expr.expr)
            return f"-{inner}" if expr.op == ast.OP_NEG else f"!{inner}"
        if isinstance(expr, ast.Binary):
            l = self.emit_expr(expr.lhs)
            r = self.emit_expr(expr.rhs)
            return f"({l} {go_binop(expr.op)} {r})"
        if isinstance(expr, ast.Call):
            args = ", ".join(self.emit_expr(a) for a in expr.args)
            if expr.callee == "print":
                return f"fmt.Println({args})"
            return f"{expr.callee}({args})"
        raise TenetError(f"未知的表达式类型: {type(expr).__name__}")

    # ---- 类型推断（与解释器语义对齐）----

    def infer_type(self, expr: ast.Expr) -> str | None:
        if isinstance(expr, ast.IntLit):
            return ast.T_INT
        if isinstance(expr, ast.FloatLit):
            return ast.T_FLOAT
        if isinstance(expr, ast.StrLit):
            return ast.T_STR
        if isinstance(expr, ast.BoolLit):
            return ast.T_BOOL
        if isinstance(expr, ast.Var):
            return self.symbols.get(expr.name)
        if isinstance(expr, ast.Assign):
            return self.symbols.get(expr.name)
        if isinstance(expr, ast.Unary):
            if expr.op == ast.OP_NOT:
                return ast.T_BOOL
            t = self.infer_type(expr.expr)
            if t in (ast.T_INT, ast.T_FLOAT):
                return t
            return None
        if isinstance(expr, ast.Binary):
            lt = self.infer_type(expr.lhs)
            rt = self.infer_type(expr.rhs)
            op = expr.op
            if op in (ast.OP_AND, ast.OP_OR):
                return ast.T_BOOL
            if op in (ast.OP_EQ, ast.OP_NEQ, ast.OP_LT, ast.OP_LTE, ast.OP_GT, ast.OP_GTE):
                return ast.T_BOOL
            if op == ast.OP_MOD:
                return ast.T_INT if lt == ast.T_INT and rt == ast.T_INT else None
            if op == ast.OP_ADD:
                if lt == ast.T_STR and rt == ast.T_STR:
                    return ast.T_STR
                if lt == ast.T_FLOAT or rt == ast.T_FLOAT:
                    return ast.T_FLOAT
                if lt == ast.T_INT and rt == ast.T_INT:
                    return ast.T_INT
                return None
            # Sub / Mul / Div
            if lt == ast.T_FLOAT or rt == ast.T_FLOAT:
                return ast.T_FLOAT
            if lt == ast.T_INT and rt == ast.T_INT:
                return ast.T_INT
            return None
        if isinstance(expr, ast.Call):
            return self.functions.get(expr.callee)
        return None


def go_string(s: str) -> str:
    """把 Tenet 字符串转成 Go 字符串字面量。"""
    out = ['"']
    for c in s:
        if c == '"':
            out.append('\\"')
        elif c == "\\":
            out.append("\\\\")
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif c == "\r":
            out.append("\\r")
        elif ord(c) < 0x20:
            out.append(f"\\x{ord(c):02x}")
        else:
            out.append(c)
    out.append('"')
    return "".join(out)


def program_uses_print(program: ast.Program) -> bool:
    """扫描整个程序是否调用 `print`（决定是否生成 `import "fmt"`）。"""

    def stmt_uses_print(stmts) -> bool:
        return any(stmt_uses_print_one(s) for s in stmts)

    def stmt_uses_print_one(stmt) -> bool:
        if isinstance(stmt, (ast.ExprStmt, ast.Let, ast.Return)):
            if isinstance(stmt, ast.ExprStmt):
                return expr_uses_print(stmt.expr)
            if isinstance(stmt, ast.Let):
                return expr_uses_print(stmt.value)
            return stmt.expr is not None and expr_uses_print(stmt.expr)
        if isinstance(stmt, ast.If):
            return (
                expr_uses_print(stmt.cond)
                or stmt_uses_print(stmt.then_branch)
                or (stmt.else_branch is not None and stmt_uses_print(stmt.else_branch))
            )
        if isinstance(stmt, ast.While):
            return expr_uses_print(stmt.cond) or stmt_uses_print(stmt.body)
        if isinstance(stmt, ast.FnDecl):
            return stmt_uses_print(stmt.body)
        if isinstance(stmt, ast.Block):
            return stmt_uses_print(stmt.stmts)
        return False

    def expr_uses_print(expr) -> bool:
        if isinstance(expr, ast.Call):
            return expr.callee == "print" or any(expr_uses_print(a) for a in expr.args)
        if isinstance(expr, ast.Assign):
            return expr_uses_print(expr.value)
        if isinstance(expr, ast.Unary):
            return expr_uses_print(expr.expr)
        if isinstance(expr, ast.Binary):
            return expr_uses_print(expr.lhs) or expr_uses_print(expr.rhs)
        return False

    return stmt_uses_print(program.stmts)
