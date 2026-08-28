// Tenet 测试套件：镜像 tenet-rs/src/*.rs 的 48 个测试 + 增强项。
//
//   make test   # 构建并运行
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "codegen.hpp"
#include "error.hpp"
#include "interpreter.hpp"
#include "lexer.hpp"
#include "parser.hpp"

using namespace tenet;

static int failures = 0;
static int checks = 0;

#define CHECK(cond)                                                          \
    do {                                                                     \
        ++checks;                                                            \
        if (!(cond)) {                                                       \
            std::cerr << "FAIL " << __FILE__ << ":" << __LINE__ << ": " #cond \
                      << "\n";                                               \
            ++failures;                                                      \
        }                                                                    \
    } while (0)

#define CHECK_THROWS(expr, substr)                                            \
    do {                                                                      \
        ++checks;                                                             \
        bool threw = false;                                                   \
        try {                                                                 \
            (void)(expr);                                                     \
        } catch (const TenetError& e) {                                       \
            threw = true;                                                     \
            if (std::string(e.message).find(substr) == std::string::npos) {   \
                std::cerr << "FAIL " << __FILE__ << ":" << __LINE__           \
                          << ": 错误信息缺少 '" << substr << "': " << e.str() \
                          << "\n";                                            \
                ++failures;                                                   \
            }                                                                 \
        }                                                                     \
        if (!threw) {                                                         \
            std::cerr << "FAIL " << __FILE__ << ":" << __LINE__               \
                      << ": 期望抛出错误: " #expr "\n";                       \
            ++failures;                                                       \
        }                                                                     \
    } while (0)

// ---- 辅助 ----

/// 执行源码，返回 stdout（错误则向上抛）。
static std::string run_capture(const std::string& src) {
    std::stringstream ss;
    std::streambuf* old = std::cout.rdbuf(ss.rdbuf());
    try {
        Program p = Parser::parse(src);
        Interpreter::run(p);
    } catch (...) {
        std::cout.rdbuf(old);
        throw;
    }
    std::cout.rdbuf(old);
    return ss.str();
}

/// 执行源码，把 stdout 按行切开（去掉末尾空行）。
static std::vector<std::string> run_lines(const std::string& src) {
    std::string out = run_capture(src);
    std::vector<std::string> lines;
    std::string cur;
    for (char c : out) {
        if (c == '\n') {
            if (!cur.empty()) lines.push_back(cur);
            cur.clear();
        } else {
            cur.push_back(c);
        }
    }
    if (!cur.empty()) lines.push_back(cur);
    return lines;
}

static std::string codegen(const std::string& src) {
    Program p = Parser::parse(src);
    return GoCodegen::generate(p);
}

// ---- 词法分析器 ----

static void test_lexer() {
    // 空源码
    auto toks = Lexer::tokenize("");
    CHECK(toks.size() == 1 && toks[0].kind == Kind::Eof);

    // 字面量
    toks = Lexer::tokenize("42 3.14 \"hi\" true false");
    CHECK(toks.size() == 6);
    CHECK(toks[0].kind == Kind::Int && toks[0].int_val == 42);
    CHECK(toks[1].kind == Kind::Float && toks[1].float_val == 3.14);
    CHECK(toks[2].kind == Kind::Str && toks[2].str_val == "hi");
    CHECK(toks[3].kind == Kind::True);
    CHECK(toks[4].kind == Kind::False);
    CHECK(toks[5].kind == Kind::Eof);

    // 尾点浮点
    toks = Lexer::tokenize("3.");
    CHECK(toks[0].kind == Kind::Float && toks[0].float_val == 3.0);

    // 运算符最长匹配
    toks = Lexer::tokenize("== != <= >= && || -> = < > ! + - * / %");
    CHECK(toks.size() == 17);
    CHECK(toks[0].kind == Kind::Eq);
    CHECK(toks[1].kind == Kind::Neq);
    CHECK(toks[2].kind == Kind::Lte);
    CHECK(toks[3].kind == Kind::Gte);
    CHECK(toks[4].kind == Kind::And);
    CHECK(toks[5].kind == Kind::Or);
    CHECK(toks[6].kind == Kind::Arrow);
    CHECK(toks[7].kind == Kind::Assign);
    CHECK(toks[8].kind == Kind::Lt);
    CHECK(toks[9].kind == Kind::Gt);
    CHECK(toks[10].kind == Kind::Not);
    CHECK(toks[11].kind == Kind::Plus);
    CHECK(toks[12].kind == Kind::Minus);
    CHECK(toks[13].kind == Kind::Star);
    CHECK(toks[14].kind == Kind::Slash);
    CHECK(toks[15].kind == Kind::Percent);
    CHECK(toks[16].kind == Kind::Eof);

    // 关键字与标识符
    toks = Lexer::tokenize("let x: int = 1;");
    CHECK(toks[0].kind == Kind::Let);
    CHECK(toks[1].kind == Kind::Ident && toks[1].str_val == "x");
    CHECK(toks[2].kind == Kind::Colon);
    CHECK(toks[3].kind == Kind::IntType);
    CHECK(toks[4].kind == Kind::Assign);
    CHECK(toks[5].kind == Kind::Int);
    CHECK(toks[6].kind == Kind::Semi);

    // 注释跳过
    toks = Lexer::tokenize("1 // line\n + /* block\ncomment */ 2");
    CHECK(toks.size() == 4);
    CHECK(toks[0].kind == Kind::Int);
    CHECK(toks[1].kind == Kind::Plus);
    CHECK(toks[2].kind == Kind::Int);
    CHECK(toks[3].kind == Kind::Eof);

    // 字符串转义
    toks = Lexer::tokenize("\"a\\nb\\t\\\"c\\\\\"");
    CHECK(toks[0].kind == Kind::Str);
    CHECK(toks[0].str_val == "a\nb\t\"c\\");

    // 位置追踪
    toks = Lexer::tokenize("1 +\n2");
    CHECK(toks[0].pos == Position(1, 1));
    CHECK(toks[1].pos == Position(1, 3));
    CHECK(toks[2].pos == Position(2, 1));

    // i64 范围检查
    CHECK_THROWS(Lexer::tokenize("99999999999999999999999999"), "i64 范围");

    // 未闭合字符串
    CHECK_THROWS(Lexer::tokenize("\"abc"), "未闭合");

    // 非法字符
    CHECK_THROWS(Lexer::tokenize("1 @ 2"), "无法识别");
}

// ---- 语法分析器 ----

static void test_parser() {
    // let 声明
    Program p = Parser::parse("let x: int = 42;");
    CHECK(p.stmts.size() == 1);
    CHECK(p.stmts[0]->kind == Stmt::Kind::Let);
    CHECK(p.stmts[0]->name == "x");
    CHECK(p.stmts[0]->ty.has_value() && *p.stmts[0]->ty == T_INT);
    CHECK(p.stmts[0]->value->kind == Expr::Kind::Int);
    CHECK(p.stmts[0]->value->int_val == 42);

    // let 无类型
    p = Parser::parse("let x = 3.14;");
    CHECK(!p.stmts[0]->ty.has_value());

    // 优先级：1 + 2 * 3
    p = Parser::parse("let x: int = 1 + 2 * 3;");
    auto* bin = p.stmts[0]->value.get();
    CHECK(bin->kind == Expr::Kind::Binary);
    CHECK(bin->op == OP_ADD);
    CHECK(bin->lhs->kind == Expr::Kind::Int);
    CHECK(bin->rhs->kind == Expr::Kind::Binary);
    CHECK(bin->rhs->op == OP_MUL);

    // 比较链
    p = Parser::parse("let x: bool = 2 < 3 < 4;");
    CHECK(p.stmts[0]->value->kind == Expr::Kind::Binary);
    CHECK(p.stmts[0]->value->op == OP_LT);

    // 一元负号
    p = Parser::parse("let x: int = -5;");
    CHECK(p.stmts[0]->value->kind == Expr::Kind::Unary);
    CHECK(p.stmts[0]->value->op == OP_NEG);
    CHECK(p.stmts[0]->value->value->kind == Expr::Kind::Int);

    // 函数声明
    p = Parser::parse("fn add(a: int, b: int) -> int { return a + b; }");
    CHECK(p.stmts[0]->kind == Stmt::Kind::FnDecl);
    CHECK(p.stmts[0]->name == "add");
    CHECK(p.stmts[0]->params.size() == 2);
    CHECK(p.stmts[0]->params[0] == std::make_pair(std::string("a"), std::string(T_INT)));
    CHECK(p.stmts[0]->ret.has_value() && *p.stmts[0]->ret == T_INT);
    CHECK(p.stmts[0]->body.size() == 1);

    // else if 链
    p = Parser::parse(
        "if (x > 0) { print(1); } else if (x < 0) { print(-1); } else { print(0); }");
    CHECK(p.stmts[0]->kind == Stmt::Kind::If);
    CHECK(p.stmts[0]->else_branch.size() == 1);
    CHECK(p.stmts[0]->else_branch[0]->kind == Stmt::Kind::If);

    // 调用与赋值
    p = Parser::parse("x = f(1, 2);");
    CHECK(p.stmts[0]->kind == Stmt::Kind::Expr);
    auto* assign = p.stmts[0]->expr.get();
    CHECK(assign->kind == Expr::Kind::Assign);
    CHECK(assign->name == "x");
    CHECK(assign->value->kind == Expr::Kind::Call);
    CHECK(assign->value->name == "f");
    CHECK(assign->value->args.size() == 2);

    // 语法错误
    CHECK_THROWS(Parser::parse("let x: int = 1"), "`;`");
    CHECK_THROWS(Parser::parse("if x > 0 { }"), "`(`");
    CHECK_THROWS(Parser::parse("let 1: int = 2;"), "变量名");
}

// ---- 解释器 ----

static void test_interpreter() {
    // 算术与优先级
    CHECK(run_lines("print(1 + 2 * 3);") == std::vector<std::string>{"7"});
    CHECK(run_lines("print(1 + 2.5);") == std::vector<std::string>{"3.5"});
    CHECK(run_lines("print(10 / 3);") == std::vector<std::string>{"3"});
    CHECK(run_lines("print(10 / 3.0);") ==
          std::vector<std::string>{"3.3333333333333335"});

    // 整除与取模（含向零截断）
    CHECK(run_lines("print(7 / 2); print(7 % 2);") ==
          std::vector<std::string>({"3", "1"}));
    CHECK(run_lines("print(-7 / 2); print(-7 % 2);") ==
          std::vector<std::string>({"-3", "-1"}));

    // 字符串拼接
    CHECK(run_lines("print(\"a\" + \"b\" + \"c\");") ==
          std::vector<std::string>{"abc"});

    // 比较与逻辑
    CHECK(run_lines("print(1 < 2); print(1 == 1.0); print(true && !false);") ==
          std::vector<std::string>({"true", "true", "true"}));

    // 短路 ||（右侧 1/0 不求值）
    CHECK(run_lines("let x: bool = true || (1 / 0 == 1); print(x);") ==
          std::vector<std::string>{"true"});
    // 短路 &&
    CHECK(run_lines("let x: bool = false && (1 / 0 == 1); print(x);") ==
          std::vector<std::string>{"false"});

    // 赋值修改外层
    CHECK(run_lines("let x: int = 1; { x = 2; } print(x);") ==
          std::vector<std::string>{"2"});

    // 块作用域遮蔽
    CHECK(run_lines("let x: int = 1; { let x: int = 2; print(x); } print(x);") ==
          std::vector<std::string>({"2", "1"}));

    // if / while：偶数和
    CHECK(run_lines(
              "let n: int = 10; let acc: int = 0;"
              "while (n > 0) { if (n % 2 == 0) { acc = acc + n; } n = n - 1; }"
              "print(acc);") == std::vector<std::string>{"30"});

    // break
    CHECK(run_lines(
              "let i: int = 0; while (true) { i = i + 1;"
              "if (i >= 5) { break; } } print(i);") == std::vector<std::string>{"5"});

    // 递归斐波那契
    CHECK(run_lines(
              "fn fib(n: int) -> int { if (n < 2) { return n; }"
              "return fib(n - 1) + fib(n - 2); } print(fib(10));") ==
          std::vector<std::string>{"55"});

    // 运行时错误
    CHECK_THROWS(run_capture("fn f(a: int) -> int { return a; } f(true);"), "参数");
    CHECK_THROWS(run_capture("print(unknown_var);"), "未定义的变量");
    CHECK_THROWS(run_capture("no_such_fn(1);"), "未定义的函数");
    CHECK_THROWS(run_capture("let x: int = 1 / 0;"), "除以零");
}

// ---- 代码生成 ----

static void test_codegen() {
    // hello world
    std::string out = codegen("print(\"hello\");");
    CHECK(out.find("package main") != std::string::npos);
    CHECK(out.find("import \"fmt\"") != std::string::npos);
    CHECK(out.find("func main()") != std::string::npos);
    CHECK(out.find("fmt.Println(\"hello\")") != std::string::npos);

    // 无 print 不 import fmt
    out = codegen("let x: int = 1;");
    CHECK(out.find("import") == std::string::npos);

    // let 带标注
    out = codegen("let x: int = 42; let s: string = \"hi\";");
    CHECK(out.find("var x int64 = 42;") != std::string::npos);
    CHECK(out.find("var s string = \"hi\";") != std::string::npos);

    // 类型推断
    out = codegen("let x = 1 + 2.5;");
    CHECK(out.find("var x float64 = (1 + 2.5);") != std::string::npos);

    // 函数返回类型推断
    out = codegen("fn f() -> int { return 1; } let x = f();");
    CHECK(out.find("var x int64 = f();") != std::string::npos);

    // while → for
    out = codegen("while (x < 10) { x = x + 1; }");
    CHECK(out.find("for (x < 10) {") != std::string::npos);

    // 函数声明
    out = codegen("fn add(a: int, b: int) -> int { return a + b; }");
    CHECK(out.find("func add(a int64, b int64) int64 {") != std::string::npos);
    CHECK(out.find("return (a + b);") != std::string::npos);

    // 无返回类型函数
    out = codegen("fn greet() { print(\"hi\"); }");
    CHECK(out.find("func greet() {") != std::string::npos);
    CHECK(out.find("func greet()  {") == std::string::npos);

    // else if 链
    out = codegen(
        "if (x > 0) { print(1); } else if (x < 0) { print(-1); } else { print(0); }");
    CHECK(out.find("} else if (x < 0) {") != std::string::npos);
    CHECK(out.find("} else {") != std::string::npos);

    // 字符串转义
    out = codegen("print(\"a\\n\\\"b\\\"\");");
    CHECK(out.find("fmt.Println(\"a\\n\\\"b\\\"\")") != std::string::npos);

    // 函数内 print 触发 import
    out = codegen("fn f() { print(1); }");
    CHECK(out.find("import \"fmt\"") != std::string::npos);

    // 浮点保留小数点（7 / 2.0 不能退化成整数除法）
    out = codegen("print(7 / 2.0);");
    CHECK(out.find("(7 / 2.0)") != std::string::npos);

    // 无法推断类型
    CHECK_THROWS(codegen("fn f() { } let x = f();"), "无法推断");

    // golden：fib 完整输出（与 Rust/Python 版逐字节一致）
    std::string expected =
        "package main\n"
        "\n"
        "import \"fmt\"\n"
        "\n"
        "func fib(n int64) int64 {\n"
        "\tif (n < 2) {\n"
        "\t\treturn n;\n"
        "\t}\n"
        "\treturn (fib((n - 1)) + fib((n - 2)));\n"
        "}\n"
        "\n"
        "func main() {\n"
        "\tvar i int64 = 0;\n"
        "\tfor (i <= 10) {\n"
        "\t\tfmt.Println(\"fib(\", i, \") =\", fib(i));\n"
        "\t\ti = (i + 1);\n"
        "\t}\n"
        "}\n";
    std::string src =
        "fn fib(n: int) -> int { if (n < 2) { return n; }"
        "return fib(n - 1) + fib(n - 2); }"
        "let i: int = 0;"
        "while (i <= 10) { print(\"fib(\", i, \") =\", fib(i)); i = i + 1; }";
    CHECK(codegen(src) == expected);
}

int main() {
    test_lexer();
    test_parser();
    test_interpreter();
    test_codegen();

    std::cout << "通过 " << (checks - failures) << " / " << checks << " 项检查";
    if (failures > 0) {
        std::cout << "，失败 " << failures << " 项\n";
        return 1;
    }
    std::cout << "\n";
    return 0;
}
