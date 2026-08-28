"""语法分析器测试（镜像 tenet-rs/src/parser.rs 的测试）。"""

import unittest

from tenet import ast
from tenet.error import TenetError
from tenet.parser import Parser


class TestParser(unittest.TestCase):
    def parse_ok(self, src):
        return Parser.parse(src)

    def test_let_declaration(self):
        prog = self.parse_ok("let x: int = 42;")
        stmt = prog.stmts[0]
        self.assertIsInstance(stmt, ast.Let)
        self.assertEqual(stmt.name, "x")
        self.assertEqual(stmt.ty, ast.T_INT)
        self.assertEqual(stmt.value, ast.IntLit(42))

    def test_let_without_type(self):
        prog = self.parse_ok("let x = 3.14;")
        stmt = prog.stmts[0]
        self.assertIsInstance(stmt, ast.Let)
        self.assertIsNone(stmt.ty)

    def test_precedence(self):
        prog = self.parse_ok("let x: int = 1 + 2 * 3;")
        value = prog.stmts[0].value
        self.assertIsInstance(value, ast.Binary)
        self.assertEqual(value.op, ast.OP_ADD)
        self.assertEqual(value.lhs, ast.IntLit(1))
        self.assertIsInstance(value.rhs, ast.Binary)
        self.assertEqual(value.rhs.op, ast.OP_MUL)

    def test_comparison_chain(self):
        prog = self.parse_ok("let x: bool = 2 < 3 < 4;")
        value = prog.stmts[0].value
        self.assertIsInstance(value, ast.Binary)
        self.assertEqual(value.op, ast.OP_LT)

    def test_unary_minus(self):
        prog = self.parse_ok("let x: int = -5;")
        value = prog.stmts[0].value
        self.assertEqual(value, ast.Unary(ast.OP_NEG, ast.IntLit(5)))

    def test_function_declaration(self):
        prog = self.parse_ok("fn add(a: int, b: int) -> int { return a + b; }")
        stmt = prog.stmts[0]
        self.assertIsInstance(stmt, ast.FnDecl)
        self.assertEqual(stmt.name, "add")
        self.assertEqual(stmt.params, [("a", ast.T_INT), ("b", ast.T_INT)])
        self.assertEqual(stmt.ret, ast.T_INT)
        self.assertEqual(len(stmt.body), 1)

    def test_if_else_chain(self):
        prog = self.parse_ok(
            "if (x > 0) { print(1); } else if (x < 0) { print(-1); } else { print(0); }"
        )
        stmt = prog.stmts[0]
        self.assertIsInstance(stmt, ast.If)
        self.assertEqual(len(stmt.else_branch), 1)
        self.assertIsInstance(stmt.else_branch[0], ast.If)

    def test_call_and_assignment(self):
        prog = self.parse_ok("x = f(1, 2);")
        stmt = prog.stmts[0]
        self.assertIsInstance(stmt, ast.ExprStmt)
        assign = stmt.expr
        self.assertIsInstance(assign, ast.Assign)
        self.assertEqual(assign.name, "x")
        self.assertIsInstance(assign.value, ast.Call)
        self.assertEqual(assign.value.callee, "f")
        self.assertEqual(len(assign.value.args), 2)

    def test_missing_semicolon_errors(self):
        with self.assertRaises(TenetError) as ctx:
            Parser.parse("let x: int = 1")
        self.assertIn("`;`", ctx.exception.message)

    def test_missing_paren_errors(self):
        with self.assertRaises(TenetError) as ctx:
            Parser.parse("if x > 0 { }")
        self.assertIn("`(`", ctx.exception.message)

    def test_unexpected_token_errors(self):
        with self.assertRaises(TenetError) as ctx:
            Parser.parse("let 1: int = 2;")
        self.assertIn("变量名", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
