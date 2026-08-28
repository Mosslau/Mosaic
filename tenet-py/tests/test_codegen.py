"""代码生成器测试（镜像 tenet-rs/src/codegen.rs 的测试）。

其中一个 golden 测试把完整预期 Go 源码内联进来，
保证 Python 版输出与 Rust 版逐字节一致。
"""

import unittest
import textwrap

from tenet import codegen_source
from tenet.error import TenetError


def gen(src):
    return codegen_source(src)


class TestCodegen(unittest.TestCase):
    def test_hello_world(self):
        out = gen('print("hello");')
        self.assertIn("package main", out)
        self.assertIn('import "fmt"', out)
        self.assertIn("func main()", out)
        self.assertIn('fmt.Println("hello")', out)

    def test_no_print_no_fmt_import(self):
        out = gen("let x: int = 1;")
        self.assertNotIn("import", out)

    def test_let_with_annotation(self):
        out = gen('let x: int = 42; let s: string = "hi";')
        self.assertIn("var x int64 = 42;", out)
        self.assertIn('var s string = "hi";', out)

    def test_let_type_inference(self):
        out = gen("let x = 1 + 2.5;")
        self.assertIn("var x float64 = (1 + 2.5);", out)

    def test_inference_from_function_return(self):
        out = gen("fn f() -> int { return 1; } let x = f();")
        self.assertIn("var x int64 = f();", out)

    def test_while_becomes_for(self):
        out = gen("while (x < 10) { x = x + 1; }")
        self.assertIn("for (x < 10) {", out)

    def test_function_decl(self):
        out = gen("fn add(a: int, b: int) -> int { return a + b; }")
        self.assertIn("func add(a int64, b int64) int64 {", out)
        self.assertIn("return (a + b);", out)

    def test_void_function(self):
        out = gen('fn greet() { print("hi"); }')
        self.assertIn("func greet() {", out)
        self.assertNotIn("func greet()  {", out)

    def test_else_if_chain(self):
        out = gen(
            "if (x > 0) { print(1); } else if (x < 0) { print(-1); } else { print(0); }"
        )
        self.assertIn("} else if (x < 0) {", out)
        self.assertIn("} else {", out)

    def test_string_escaping(self):
        out = gen('print("a\\n\\"b\\"");')
        self.assertIn('fmt.Println("a\\n\\"b\\"")', out)

    def test_print_inside_function_triggers_import(self):
        out = gen("fn f() { print(1); }")
        self.assertIn('import "fmt"', out)

    def test_float_literal_keeps_decimal_point(self):
        # Rust 的 f64 Display 会把 2.0 打印成 "2"，代码生成必须补回小数点，
        # 否则 Go 里 7 / 2.0 会变成整数除法 7 / 2
        out = gen("print(7 / 2.0);")
        self.assertIn("(7 / 2.0)", out)

    def test_cannot_infer_type_errors(self):
        # 无返回类型的函数调用无法推断类型
        with self.assertRaises(TenetError) as ctx:
            gen("fn f() { } let x = f();")
        self.assertIn("无法推断", ctx.exception.message)

    def test_golden_fib_matches_rust_output(self):
        """golden 测试：fib 的完整 Go 输出必须与 Rust 版逐字节一致。"""
        expected = textwrap.dedent(
            '''\
            package main

            import "fmt"

            func fib(n int64) int64 {
            \tif (n < 2) {
            \t\treturn n;
            \t}
            \treturn (fib((n - 1)) + fib((n - 2)));
            }

            func main() {
            \tvar i int64 = 0;
            \tfor (i <= 10) {
            \t\tfmt.Println("fib(", i, ") =", fib(i));
            \t\ti = (i + 1);
            \t}
            }
            '''
        )
        src = """
        fn fib(n: int) -> int {
            if (n < 2) { return n; }
            return fib(n - 1) + fib(n - 2);
        }
        let i: int = 0;
        while (i <= 10) {
            print("fib(", i, ") =", fib(i));
            i = i + 1;
        }
        """
        self.assertEqual(gen(src), expected)


if __name__ == "__main__":
    unittest.main()
