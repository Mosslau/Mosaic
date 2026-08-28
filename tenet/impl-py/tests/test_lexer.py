"""词法分析器测试（镜像 impl-rs/src/lexer.rs 的测试）。"""

import unittest

from tenet import token as tk
from tenet.error import Position, TenetError
from tenet.lexer import Lexer


def kinds(src):
    return [t.kind for t in Lexer.tokenize(src)]


class TestLexer(unittest.TestCase):
    def test_empty_source(self):
        self.assertEqual(kinds(""), [tk.EOF])

    def test_literals(self):
        self.assertEqual(
            kinds('42 3.14 "hi" true false'),
            [tk.INT, tk.FLOAT, tk.STR, tk.TRUE, tk.FALSE, tk.EOF],
        )

    def test_trailing_dot_number(self):
        toks = Lexer.tokenize("3.")
        self.assertEqual(toks[0].kind, tk.FLOAT)
        self.assertEqual(toks[0].value, 3.0)

    def test_operators_longest_match(self):
        self.assertEqual(
            kinds("== != <= >= && || -> = < > ! + - * / %"),
            [
                tk.EQ, tk.NEQ, tk.LTE, tk.GTE, tk.AND, tk.OR, tk.ARROW,
                tk.ASSIGN, tk.LT, tk.GT, tk.NOT,
                tk.PLUS, tk.MINUS, tk.STAR, tk.SLASH, tk.PERCENT, tk.EOF,
            ],
        )

    def test_keywords_and_identifiers(self):
        self.assertEqual(
            kinds("let x: int = 1;"),
            [tk.LET, tk.IDENT, tk.COLON, tk.INT_TYPE, tk.ASSIGN, tk.INT, tk.SEMI, tk.EOF],
        )

    def test_comments_skipped(self):
        self.assertEqual(
            kinds("1 // line comment\n + /* block\ncomment */ 2"),
            [tk.INT, tk.PLUS, tk.INT, tk.EOF],
        )

    def test_string_escapes(self):
        toks = Lexer.tokenize(r'"a\nb\t\"c\\"')
        self.assertEqual(toks[0].kind, tk.STR)
        self.assertEqual(toks[0].value, 'a\nb\t"c\\')

    def test_positions_tracked(self):
        toks = Lexer.tokenize("1 +\n2")
        self.assertEqual(toks[0].pos, Position(1, 1))
        self.assertEqual(toks[1].pos, Position(1, 3))
        self.assertEqual(toks[2].pos, Position(2, 1))

    def test_int64_range_checked(self):
        # 超出 i64 范围 → 报错（与 Rust 版一致）
        with self.assertRaises(TenetError) as ctx:
            Lexer.tokenize("99999999999999999999999999")
        self.assertIn("i64 范围", ctx.exception.message)

    def test_unterminated_string_errors(self):
        with self.assertRaises(TenetError) as ctx:
            Lexer.tokenize('"abc')
        self.assertIn("未闭合", ctx.exception.message)

    def test_bad_character_errors(self):
        with self.assertRaises(TenetError) as ctx:
            Lexer.tokenize("1 @ 2")
        self.assertIn("无法识别", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
