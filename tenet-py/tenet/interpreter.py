"""树遍历解释器（Tree-walking Interpreter）。

与 Rust 版 tenet-rs/src/interpreter.rs 语义一致：

- 表达式递归求值返回值；语句递归执行产生副作用
- 控制流（return / break）通过 Flow 信号向上传播
- 短路求值：&& / || 右侧只在需要时求值
- 函数以名字存放在全局函数表；调用时新建参数作用域（父=全局）
- 作用域只在块、if / while 分支、函数调用处创建；顶层不建
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ast
from . import value as val
from .env import Env
from .error import TenetError

# 控制流信号常量
FLOW_NORMAL = 0
FLOW_BREAK = 1
FLOW_RETURN = 2


@dataclass
class Function:
    name: str
    params: list = field(default_factory=list)  # [(参数名, 类型), ...]
    ret: str | None = None
    body: list = field(default_factory=list)


class Interpreter:
    def __init__(self):
        self.functions: dict[str, Function] = {}
        self.global_env = Env.global_()

    @classmethod
    def run(cls, program: ast.Program) -> None:
        """顶层入口：执行整个程序。"""
        Interpreter().run_program(program)

    def run_program(self, program: ast.Program) -> None:
        """在当前实例上执行程序（REPL 复用同一实例，保留函数表）。"""
        self.exec_block(program.stmts, self.global_env)

    def eval_expr(self, expr: ast.Expr):
        """在全局环境中求值单个表达式（REPL 回显用）。"""
        return self.eval(expr, self.global_env)

    # ---- 语句执行 ----

    def exec_block(self, stmts: list, env: Env):
        """执行语句序列：**不**新建作用域，直接在给定环境中执行。"""
        for stmt in stmts:
            flow = self.exec_stmt(stmt, env)
            if flow != FLOW_NORMAL:
                return flow
        return FLOW_NORMAL

    def exec_stmt(self, stmt: ast.Stmt, env: Env):
        if isinstance(stmt, ast.Let):
            v = self.eval(stmt.value, env)
            env.define(stmt.name, v)
            return FLOW_NORMAL

        if isinstance(stmt, ast.ExprStmt):
            self.eval(stmt.expr, env)
            return FLOW_NORMAL

        if isinstance(stmt, ast.If):
            cond = val.expect_bool(self.eval(stmt.cond, env))
            branch = stmt.then_branch if cond else (stmt.else_branch or [])
            # if 分支自身就是一个块：新建作用域
            branch_env = Env.child(env)
            return self.exec_block(branch, branch_env)

        if isinstance(stmt, ast.While):
            flow = FLOW_NORMAL
            while True:
                if not val.expect_bool(self.eval(stmt.cond, env)):
                    break
                body_env = Env.child(env)
                flow = self.exec_block(stmt.body, body_env)
                if flow == FLOW_BREAK:
                    return FLOW_NORMAL
                if isinstance(flow, tuple):  # Return 信号（FLOW_RETURN, value）
                    return flow
            return flow

        if isinstance(stmt, ast.Return):
            v = self.eval(stmt.expr, env) if stmt.expr is not None else None
            return (FLOW_RETURN, v)

        if isinstance(stmt, ast.Break):
            return FLOW_BREAK

        if isinstance(stmt, ast.Block):
            child = Env.child(env)
            return self.exec_block(stmt.stmts, child)

        if isinstance(stmt, ast.FnDecl):
            self.functions[stmt.name] = Function(
                stmt.name, list(stmt.params), stmt.ret, list(stmt.body)
            )
            return FLOW_NORMAL

        raise TenetError(f"未知的语句类型: {type(stmt).__name__}")

    # ---- 表达式求值 ----

    def eval(self, expr: ast.Expr, env: Env):
        if isinstance(expr, ast.IntLit):
            return expr.value
        if isinstance(expr, ast.FloatLit):
            return expr.value
        if isinstance(expr, ast.StrLit):
            return expr.value
        if isinstance(expr, ast.BoolLit):
            return expr.value
        if isinstance(expr, ast.Var):
            return env.get(expr.name)
        if isinstance(expr, ast.Assign):
            v = self.eval(expr.value, env)
            env.assign(expr.name, v)
            return v
        if isinstance(expr, ast.Unary):
            v = self.eval(expr.expr, env)
            return val.apply_unary(v, expr.op)
        if isinstance(expr, ast.Binary):
            # && / || 短路求值：右侧只在需要时求值
            if expr.op in (ast.OP_AND, ast.OP_OR):
                l = val.expect_bool(self.eval(expr.lhs, env))
                if expr.op == ast.OP_AND and not l:
                    return False
                if expr.op == ast.OP_OR and l:
                    return True
                r = val.expect_bool(self.eval(expr.rhs, env))
                return r
            l = self.eval(expr.lhs, env)
            r = self.eval(expr.rhs, env)
            return val.apply_binary(l, expr.op, r)
        if isinstance(expr, ast.Call):
            return self.call(expr.callee, expr.args, env)
        raise TenetError(f"未知的表达式类型: {type(expr).__name__}")

    # ---- 函数调用 ----

    def call(self, callee: str, args: list, env: Env):
        # 内建函数
        if callee == "print":
            values = [self.eval(a, env) for a in args]
            print(" ".join(val.display(v) for v in values))
            return None

        # 用户函数
        f = self.functions.get(callee)
        if f is None:
            raise TenetError(f"未定义的函数 `{callee}`")
        if len(f.params) != len(args):
            raise TenetError(
                f"函数 `{callee}` 需要 {len(f.params)} 个参数，实际传入 {len(args)} 个"
            )

        # 参数作用域：父为全局环境（函数之间共享全局变量，但不捕获调用方局部变量）
        call_env = Env.child(self.global_env)
        for (pname, pty), arg in zip(f.params, args):
            v = self.eval(arg, env)
            if not val.matches(v, pty):
                raise TenetError(
                    f"参数 `{pname}` 期望类型 {pty}，实际传入 {val.type_name(v)}"
                )
            call_env.define(pname, v)

        flow = self.exec_block(f.body, call_env)
        if isinstance(flow, tuple):  # Return 信号
            _, v = flow
            if f.ret is not None and not val.matches(v, f.ret) and v is not None:
                raise TenetError(
                    f"函数 `{callee}` 返回类型期望 {f.ret}，实际返回 {val.type_name(v)}"
                )
            return v
        if flow == FLOW_BREAK:
            raise TenetError(f"`break` 出现在函数 `{callee}` 的循环之外")
        # FLOW_NORMAL
        if f.ret is not None:
            raise TenetError(f"函数 `{callee}` 声明了返回类型，但没有返回值")
        return None
