"""语法分析器（Parser）：递归下降 + 优先级爬升，把 Token 流变成 AST。

与 Rust 版 impl-rs/src/parser.rs 语义一致。

优先级（低 → 高）：
    ||  <  &&  <  == !=  <  < <= > >=  <  + -  <  * / %  <  一元 - !
"""

from __future__ import annotations

from . import ast
from . import token as tk
from .error import TenetError
from .lexer import Lexer

# 二元运算符优先级表：op -> (ast操作符, 优先级)
_BINARY_PREC = [
    (tk.OR, ast.OP_OR, 1),
    (tk.AND, ast.OP_AND, 2),
    (tk.EQ, ast.OP_EQ, 3),
    (tk.NEQ, ast.OP_NEQ, 3),
    (tk.LT, ast.OP_LT, 4),
    (tk.LTE, ast.OP_LTE, 4),
    (tk.GT, ast.OP_GT, 4),
    (tk.GTE, ast.OP_GTE, 4),
    (tk.PLUS, ast.OP_ADD, 5),
    (tk.MINUS, ast.OP_SUB, 5),
    (tk.STAR, ast.OP_MUL, 6),
    (tk.SLASH, ast.OP_DIV, 6),
    (tk.PERCENT, ast.OP_MOD, 6),
]
_BINARY_INFO = {kind: (op, prec) for kind, op, prec in _BINARY_PREC}

_TYPE_TOKENS = {
    tk.INT_TYPE: ast.T_INT,
    tk.FLOAT_TYPE: ast.T_FLOAT,
    tk.BOOL_TYPE: ast.T_BOOL,
    tk.STR_TYPE: ast.T_STR,
}


class Parser:
    def __init__(self, tokens: list[tk.Token]):
        self.tokens = tokens
        self.pos = 0

    @classmethod
    def parse(cls, source: str) -> ast.Program:
        tokens = Lexer.tokenize(source)
        return cls(tokens).parse_program()

    # ---- 底层 ----

    def peek(self) -> tk.Token:
        return self.tokens[self.pos]

    def advance(self) -> tk.Token:
        tok = self.tokens[self.pos]
        if self.pos + 1 < len(self.tokens):
            self.pos += 1
        return tok

    def check(self, kind: str) -> bool:
        return self.peek().kind == kind

    def expect(self, kind: str, what: str) -> tk.Token:
        if self.check(kind):
            return self.advance()
        raise self.error(f"期望 {what}，但遇到 {tk.describe(self.peek().kind, self.peek().value)}")

    def error(self, message: str) -> TenetError:
        pos = self.peek().pos
        return TenetError.at_pos(message, pos)

    # ---- 程序 ----

    def parse_program(self) -> ast.Program:
        stmts = []
        while not self.check(tk.EOF):
            stmts.append(self.parse_stmt())
        return ast.Program(stmts)

    # ---- 语句 ----

    def parse_stmt(self) -> ast.Stmt:
        kind = self.peek().kind
        if kind == tk.LET:
            return self.parse_let()
        if kind == tk.FN:
            return self.parse_fn_decl()
        if kind == tk.IF:
            return self.parse_if()
        if kind == tk.WHILE:
            return self.parse_while()
        if kind == tk.RETURN:
            return self.parse_return()
        if kind == tk.BREAK:
            self.advance()
            self.expect(tk.SEMI, "`;`")
            return ast.Break()
        if kind == tk.LBRACE:
            return ast.Block(self.parse_block())
        expr = self.parse_expr()
        self.expect(tk.SEMI, "`;`")
        return ast.ExprStmt(expr)

    def parse_let(self) -> ast.Stmt:
        self.advance()  # let
        name = self.expect_ident("变量名")
        ty = None
        if self.check(tk.COLON):
            self.advance()
            ty = self.parse_type()
        self.expect(tk.ASSIGN, "`=`")
        value = self.parse_expr()
        self.expect(tk.SEMI, "`;`")
        return ast.Let(name, ty, value)

    def parse_fn_decl(self) -> ast.Stmt:
        self.advance()  # fn
        name = self.expect_ident("函数名")
        self.expect(tk.LPAREN, "`(`")
        params = []
        if not self.check(tk.RPAREN):
            while True:
                pname = self.expect_ident("参数名")
                self.expect(tk.COLON, "`:`")
                pty = self.parse_type()
                params.append((pname, pty))
                if not self.check(tk.COMMA):
                    break
                self.advance()
        self.expect(tk.RPAREN, "`)`")
        ret = None
        if self.check(tk.ARROW):
            self.advance()
            ret = self.parse_type()
        body = self.parse_block()
        return ast.FnDecl(name, params, ret, body)

    def parse_if(self) -> ast.Stmt:
        self.advance()  # if
        self.expect(tk.LPAREN, "`(`")
        cond = self.parse_expr()
        self.expect(tk.RPAREN, "`)`")
        then_branch = self.parse_block()
        else_branch = None
        if self.check(tk.ELSE):
            self.advance()
            if self.check(tk.IF):
                # else if 链：嵌套一个 if 语句
                nested = self.parse_if()
                else_branch = [nested]
            else:
                else_branch = self.parse_block()
        return ast.If(cond, then_branch, else_branch)

    def parse_while(self) -> ast.Stmt:
        self.advance()  # while
        self.expect(tk.LPAREN, "`(`")
        cond = self.parse_expr()
        self.expect(tk.RPAREN, "`)`")
        body = self.parse_block()
        return ast.While(cond, body)

    def parse_return(self) -> ast.Stmt:
        self.advance()  # return
        if self.check(tk.SEMI):
            self.advance()
            return ast.Return(None)
        expr = self.parse_expr()
        self.expect(tk.SEMI, "`;`")
        return ast.Return(expr)

    def parse_block(self) -> list[ast.Stmt]:
        self.expect(tk.LBRACE, "`{`")
        stmts = []
        while not self.check(tk.RBRACE) and not self.check(tk.EOF):
            stmts.append(self.parse_stmt())
        self.expect(tk.RBRACE, "`}`")
        return stmts

    def parse_type(self) -> str:
        kind = self.peek().kind
        ty = _TYPE_TOKENS.get(kind)
        if ty is None:
            raise self.error(
                f"期望类型 `int` / `float` / `bool` / `string`，但遇到 "
                f"{tk.describe(kind, self.peek().value)}"
            )
        self.advance()
        return ty

    def expect_ident(self, what: str) -> str:
        tok = self.peek()
        if tok.kind == tk.IDENT:
            self.advance()
            return tok.value
        raise self.error(f"期望 {what}，但遇到 {tk.describe(tok.kind, tok.value)}")

    # ---- 表达式（优先级爬升）----

    def parse_expr(self) -> ast.Expr:
        return self.parse_binary(0)

    def parse_binary(self, min_prec: int) -> ast.Expr:
        lhs = self.parse_unary()
        while True:
            info = _BINARY_INFO.get(self.peek().kind)
            if info is None:
                break
            op, prec = info
            if prec < min_prec:
                break
            self.advance()
            rhs = self.parse_binary(prec + 1)
            lhs = ast.Binary(op, lhs, rhs)
        return lhs

    def parse_unary(self) -> ast.Expr:
        kind = self.peek().kind
        if kind == tk.MINUS:
            self.advance()
            return ast.Unary(ast.OP_NEG, self.parse_unary())
        if kind == tk.NOT:
            self.advance()
            return ast.Unary(ast.OP_NOT, self.parse_unary())
        return self.parse_primary()

    def parse_primary(self) -> ast.Expr:
        tok = self.peek()
        kind = tok.kind
        if kind == tk.INT:
            self.advance()
            return ast.IntLit(tok.value)
        if kind == tk.FLOAT:
            self.advance()
            return ast.FloatLit(tok.value)
        if kind == tk.STR:
            self.advance()
            return ast.StrLit(tok.value)
        if kind == tk.TRUE:
            self.advance()
            return ast.BoolLit(True)
        if kind == tk.FALSE:
            self.advance()
            return ast.BoolLit(False)
        if kind == tk.IDENT:
            self.advance()
            if self.check(tk.LPAREN):
                return self.parse_call_args(tok.value)
            if self.check(tk.ASSIGN):
                self.advance()
                value = self.parse_expr()
                return ast.Assign(tok.value, value)
            return ast.Var(tok.value)
        if kind == tk.LPAREN:
            self.advance()
            expr = self.parse_expr()
            self.expect(tk.RPAREN, "`)`")
            return expr
        raise self.error(f"期望一个表达式，但遇到 {tk.describe(kind, tok.value)}")

    def parse_call_args(self, callee: str) -> ast.Expr:
        self.advance()  # (
        args = []
        if not self.check(tk.RPAREN):
            while True:
                args.append(self.parse_expr())
                if not self.check(tk.COMMA):
                    break
                self.advance()
        self.expect(tk.RPAREN, "`)`")
        return ast.Call(callee, args)
