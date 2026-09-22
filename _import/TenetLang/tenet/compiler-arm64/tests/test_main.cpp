// Tenet compiler-arm64 测试套件：镜像 compiler-rs / compiler-cpp 的测试。
// 词法/语法用文本断言；代码生成用汇编模式断言。
#include <iostream>
#include <string>
#include <vector>

#include "backend.hpp"
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
        }                                                                     \
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
                std::cerr << "FAIL: 错误信息缺少 '" << substr << "': " << e.str() \
                          << "\n";                                            \
                ++failures;                                                   \
            }                                                                 \
        }                                                                     \
        if (!threw) {                                                         \
            std::cerr << "FAIL: 期望抛出错误: " #expr "\n";                    \
            ++failures;                                                       \
        }                                                                     \
    } while (0)

static std::string asm_of(const std::string& src) {
    return Backend::generate(Parser::parse(src));
}

// ---- 词法 ----

static void test_lexer() {
    auto toks = Lexer::tokenize("42 3.14 \"hi\" true false");
    CHECK(toks.size() == 6);
    CHECK(toks[0].kind == Kind::Int && toks[0].int_val == 42);
    CHECK(toks[1].kind == Kind::Float && toks[1].float_val == 3.14);
    CHECK(toks[2].kind == Kind::Str && toks[2].str_val == "hi");

    toks = Lexer::tokenize("== != <= >= && || -> = < > !");
    CHECK(toks.size() == 12);  // 11 运算符 + EOF
    CHECK(toks[0].kind == Kind::Eq && toks[6].kind == Kind::Arrow);

    toks = Lexer::tokenize("let x: int = 1;");
    CHECK(toks[0].kind == Kind::Let && toks[3].kind == Kind::IntType);

    toks = Lexer::tokenize("\"a\\nb\\t\\\"c\\\\\"");
    CHECK(toks[0].kind == Kind::Str && toks[0].str_val == "a\nb\t\"c\\");

    toks = Lexer::tokenize("1 +\n2");
    CHECK(toks[0].pos == Position(1, 1) && toks[2].pos == Position(2, 1));

    CHECK_THROWS(Lexer::tokenize("\"abc"), "未闭合");
    CHECK_THROWS(Lexer::tokenize("1 @ 2"), "无法识别");
}

// ---- 语法 ----

static void test_parser() {
    auto prog = Parser::parse("let x: int = 42;");
    CHECK(prog.stmts[0]->kind == Stmt::Kind::Let);
    CHECK(prog.stmts[0]->name == "x");
    CHECK(prog.stmts[0]->ty.has_value() && *prog.stmts[0]->ty == T_INT);

    prog = Parser::parse("let x: int = 1 + 2 * 3;");
    auto* v = prog.stmts[0]->value.get();
    CHECK(v->kind == Expr::Kind::Binary && v->op == OP_ADD);
    CHECK(v->rhs->kind == Expr::Kind::Binary && v->rhs->op == OP_MUL);

    prog = Parser::parse("fn add(a: int, b: int) -> int { return a + b; }");
    CHECK(prog.stmts[0]->kind == Stmt::Kind::FnDecl);
    CHECK(prog.stmts[0]->params.size() == 2);

    prog = Parser::parse("if (x > 0) { print(1); } else if (x < 0) { print(-1); } else { print(0); }");
    CHECK(prog.stmts[0]->kind == Stmt::Kind::If);
    CHECK(prog.stmts[0]->else_branch.size() == 1);
    CHECK(prog.stmts[0]->else_branch[0]->kind == Stmt::Kind::If);

    CHECK_THROWS(Parser::parse("let x: int = 1"), "`;`");
    CHECK_THROWS(Parser::parse("if x > 0 { }"), "`(`");
}

// ---- 代码生成（汇编模式断言）----

static void test_backend() {
    // 基本结构：main + printf
    {
        std::string a = asm_of("print(\"hello\");");
        CHECK(a.find("_main:") != std::string::npos);
        CHECK(a.find("bl _printf") != std::string::npos);
        CHECK(a.find(".asciz \"hello\"") != std::string::npos);
        CHECK(a.find(".globl _main") != std::string::npos);
    }

    // let + 栈帧
    {
        std::string a = asm_of("let x: int = 42;");
        CHECK(a.find("sub sp, sp, #16") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
    }

    // 函数：递归调用自己
    {
        std::string a = asm_of("fn fib(n: int) -> int { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); }");
        CHECK(a.find("_fib:") != std::string::npos);
        CHECK(a.find("bl _fib") != std::string::npos);
        CHECK(a.find("sdiv") == std::string::npos);
    }

    // while → 条件分支
    {
        std::string a = asm_of("let x: int = 0; while (x < 10) { x = x + 1; }");
        CHECK(a.find("cmp x9, #0") != std::string::npos);
        CHECK(a.find("b.eq") != std::string::npos);
        CHECK(a.find("b.eq") != std::string::npos);  // 条件分支存在
    }

    // 整数除法 sdiv / 取模 msub
    {
        std::string a = asm_of("let x: int = 7 / 2; let y: int = 7 % 2;");
        CHECK(a.find("sdiv") != std::string::npos);
        CHECK(a.find("msub") != std::string::npos);
    }

    // 浮点混合：scvtf 提升
    {
        std::string a = asm_of("let y: int = 7; let x = y / 2.0;");
        CHECK(a.find("scvtf") != std::string::npos);
        CHECK(a.find("fdiv") != std::string::npos);
    }

    // 短路：条件分支（不执行右侧除法）
    {
        std::string a = asm_of("let x: bool = true || (1 / 0 == 1);");
        CHECK(a.find("b.ne") != std::string::npos);
        // 短路路径存在：两个分支标签
        CHECK(a.find("L.short.") != std::string::npos);
    }

    // 字符串拼接 → tenet_concat
    {
        std::string a = asm_of("print(\"a\" + \"b\");");
        CHECK(a.find("bl _tenet_concat") != std::string::npos);
    }

    // 字符串比较 → tenet_strcmp
    {
        std::string a = asm_of("print(\"a\" < \"b\");");
        CHECK(a.find("bl _tenet_strcmp") != std::string::npos);
    }

    // sp 恒 16 对齐：push/pop 用 stp/ldp 16 字节
    {
        std::string a = asm_of("let x: int = 1;");
        CHECK(a.find("stp x9, xzr, [sp, #-16]!") != std::string::npos);
        CHECK(a.find("str x9, [sp, #-8]!") == std::string::npos);
    }

    // 错误路径
    CHECK_THROWS(asm_of("fn f() -> int { let x: int = 1; }"), "末尾没有 return");
    CHECK_THROWS(asm_of("fn main() { }"), "保留");
    CHECK_THROWS(asm_of("print(unknown);"), "未定义的变量");
    CHECK_THROWS(asm_of("fn f() { } let x = f();"), "无法推断");
    CHECK_THROWS(asm_of("break;"), "循环之外");

    // ---- 混合类型（string × 非 string）：前端报错，带 [行:列] ----

    {
        bool threw = false;
        try {
            asm_of("let a: string = \"x\";\nlet b = a + 1;");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.message == "运算符 `+` 不能作用于 string 和 int");
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 9);
        }
        CHECK(threw);
    }
    {
        bool threw = false;
        try {
            asm_of("let a: string = \"x\";\nlet b: int = a + 1;");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.message == "运算符 `+` 不能作用于 string 和 int");
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 14);
        }
        CHECK(threw);
    }
    CHECK_THROWS(asm_of("let a: string = \"x\";\nlet b = a < 1;"), "运算符 `<` 不能作用于 string 和 int");

    // ---- bool 不能参与数值/比较运算 ----

    CHECK_THROWS(asm_of("let b = true + 1;"), "运算符 `+` 不能作用于 bool 和 int");
    CHECK_THROWS(asm_of("let b = 1 && true;"), "运算符 `&&` 只能作用于 bool，实际为 int");
    CHECK_THROWS(asm_of("let b = !5;"), "运算符 `!` 只能作用于 bool，实际为 int");
    CHECK_THROWS(asm_of("let b = 5.5 % 2;"), "运算符 `%` 只能作用于 int");
    CHECK_THROWS(asm_of("if (1) { print(1); }"), "条件表达式需要 bool");

    // ---- 声明 / 赋值 / 调用 / 返回类型核对 ----

    CHECK_THROWS(asm_of("let b: int = \"x\";"), "`b` 初始化类型不匹配：标注 int，实际 string");
    CHECK_THROWS(asm_of("let b: int = 1;\nb = \"x\";"), "赋值类型不匹配：`b` 是 int，右侧是 string");
    CHECK_THROWS(asm_of("fn f(x: int) -> int { return x; }\nf(\"s\");"),
                 "函数 `f` 参数 0 类型不匹配：期望 int，实际 string");
    CHECK_THROWS(asm_of("fn f(x: int) -> int { return x; }\nf(1, 2);"),
                 "函数 `f` 需要 1 个参数，实际传入 2 个");
    CHECK_THROWS(asm_of("fn f() -> int { return \"s\"; }"), "函数 `f` 返回类型不匹配：声明 int，实际 string");
    CHECK_THROWS(asm_of("fn f() { return 1; }"), "函数 `f` 没有返回类型，不能 return 值");
}

int main() {
    test_lexer();
    test_parser();
    test_backend();

    std::cout << "通过 " << (checks - failures) << " / " << checks << " 项检查";
    if (failures > 0) {
        std::cout << "，失败 " << failures << " 项\n";
        return 1;
    }
    std::cout << "\n";
    return 0;
}
