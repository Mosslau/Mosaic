"""解释器测试（镜像 tenet-rs/src/interpreter.rs 的测试，并捕获 stdout 断言真实输出）。"""

import contextlib
import io
import unittest

from tenet import run_source
from tenet.error import TenetError


def run_capture(src):
    """执行源码，返回 (stdout, None) 或 (None, TenetError)。"""
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            run_source(src)
    except TenetError as e:
        return None, e
    return out.getvalue(), None


def run_lines(src):
    out, err = run_capture(src)
    if err is not None:
        raise err
    return out.strip().split("\n")


class TestInterpreter(unittest.TestCase):
    def test_arithmetic_and_precedence(self):
        self.assertEqual(run_lines("print(1 + 2 * 3);"), ["7"])
        self.assertEqual(run_lines("print(1 + 2.5);"), ["3.5"])
        self.assertEqual(run_lines("print(10 / 3);"), ["3"])
        self.assertEqual(run_lines("print(10 / 3.0);"), ["3.3333333333333335"])

    def test_integer_division_and_mod(self):
        self.assertEqual(run_lines("print(7 / 2); print(7 % 2);"), ["3", "1"])
        # 向零截断（Rust 语义，非 Python 的向下取整）
        self.assertEqual(run_lines("print(-7 / 2); print(-7 % 2);"), ["-3", "-1"])

    def test_string_concat(self):
        self.assertEqual(run_lines('print("a" + "b" + "c");'), ["abc"])

    def test_comparison_and_logic(self):
        self.assertEqual(
            run_lines("print(1 < 2); print(1 == 1.0); print(true && !false);"),
            ["true", "true", "true"],
        )

    def test_short_circuit_or(self):
        # || 短路：右侧 1/0 不会求值，因此不报除零错
        out, err = run_capture("let x: bool = true || (1 / 0 == 1); print(x);")
        self.assertIsNone(err)
        self.assertEqual(out.strip(), "true")

    def test_short_circuit_and(self):
        out, err = run_capture("let x: bool = false && (1 / 0 == 1); print(x);")
        self.assertIsNone(err)
        self.assertEqual(out.strip(), "false")

    def test_assignment_updates_outer_scope(self):
        self.assertEqual(run_lines("let x: int = 1; { x = 2; } print(x);"), ["2"])

    def test_block_scoping_shadows(self):
        self.assertEqual(
            run_lines("let x: int = 1; { let x: int = 2; print(x); } print(x);"),
            ["2", "1"],
        )

    def test_if_else_and_while(self):
        src = """
        let n: int = 10;
        let acc: int = 0;
        while (n > 0) {
            if (n % 2 == 0) { acc = acc + n; }
            n = n - 1;
        }
        print(acc);
        """
        # 2 + 4 + 6 + 8 + 10 = 30
        self.assertEqual(run_lines(src), ["30"])

    def test_break_exits_loop(self):
        src = """
        let i: int = 0;
        while (true) {
            i = i + 1;
            if (i >= 5) { break; }
        }
        print(i);
        """
        self.assertEqual(run_lines(src), ["5"])

    def test_recursion_fib(self):
        src = """
        fn fib(n: int) -> int {
            if (n < 2) { return n; }
            return fib(n - 1) + fib(n - 2);
        }
        print(fib(10));
        """
        self.assertEqual(run_lines(src), ["55"])

    def test_function_type_mismatch_errors(self):
        _, err = run_capture("fn f(a: int) -> int { return a; } f(true);")
        self.assertIsNotNone(err)
        self.assertIn("参数", err.message)

    def test_undefined_variable_errors(self):
        _, err = run_capture("print(unknown_var);")
        self.assertIsNotNone(err)
        self.assertIn("未定义的变量", err.message)

    def test_undefined_function_errors(self):
        _, err = run_capture("no_such_fn(1);")
        self.assertIsNotNone(err)
        self.assertIn("未定义的函数", err.message)

    def test_divide_by_zero_errors(self):
        _, err = run_capture("let x: int = 1 / 0;")
        self.assertIsNotNone(err)
        self.assertIn("除以零", err.message)

    def test_error_positions(self):
        _, err = run_capture("let x: int = 1 / 0;")
        self.assertIsNotNone(err)
        # 运行时错误不带位置（与 Rust 版一致，TenetError.pos 为 None）
        self.assertIsNone(err.pos)


if __name__ == "__main__":
    unittest.main()
