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

    toks = Lexer::tokenize("struct Point { x: int; }");
    CHECK(toks[0].kind == Kind::Struct);
    CHECK(toks[1].kind == Kind::Ident && toks[1].str_val == "Point");

    toks = Lexer::tokenize("p.x");
    CHECK(toks.size() == 4);  // p . x EOF
    CHECK(toks[1].kind == Kind::Dot && toks[1].pos == Position(1, 2));

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

    // struct 声明 / 字面量 / 字段读写
    prog = Parser::parse(
        "struct Point { x: int; y: int; }\n"
        "let p: Point = Point { x: 1, y: 2 };\n"
        "p.x = p.y;");
    CHECK(prog.stmts.size() == 3);
    CHECK(prog.stmts[0]->kind == Stmt::Kind::StructDecl);
    CHECK(prog.stmts[0]->name == "Point");
    CHECK(prog.stmts[0]->fields.size() == 2);
    CHECK(prog.stmts[0]->fields[0].first == "x" && prog.stmts[0]->fields[0].second == T_INT);
    CHECK(prog.stmts[1]->kind == Stmt::Kind::Let);
    CHECK(prog.stmts[1]->ty.has_value() && *prog.stmts[1]->ty == "Point");
    CHECK(prog.stmts[1]->value->kind == Expr::Kind::StructLit);
    CHECK(prog.stmts[1]->value->fields.size() == 2);
    auto* field_assign = prog.stmts[2]->expr.get();
    CHECK(field_assign->kind == Expr::Kind::Assign);
    CHECK(field_assign->lhs->kind == Expr::Kind::Field && field_assign->lhs->name == "x");
    CHECK(field_assign->lhs->lhs->kind == Expr::Kind::Var &&
          field_assign->lhs->lhs->name == "p");
    CHECK(field_assign->value->kind == Expr::Kind::Field && field_assign->value->name == "y");

    prog = Parser::parse("let y = p.x;");
    auto* field_read = prog.stmts[0]->value.get();
    CHECK(field_read->kind == Expr::Kind::Field && field_read->name == "x");
    CHECK(field_read->lhs->kind == Expr::Kind::Var && field_read->lhs->name == "p");

    // 赋值重构后仍是右结合、右侧可含二元表达式
    prog = Parser::parse("x = y = 1 + 2;");
    auto* assign = prog.stmts[0]->expr.get();
    CHECK(assign->kind == Expr::Kind::Assign && assign->lhs->kind == Expr::Kind::Var);
    CHECK(assign->value->kind == Expr::Kind::Assign);

    CHECK_THROWS(Parser::parse("let x: int = 1"), "`;`");
    CHECK_THROWS(Parser::parse("if x > 0 { }"), "`(`");
    CHECK_THROWS(Parser::parse("struct int { x: int; }"), "不能与标量类型重名");
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

    // ---- struct v1 ----

    // 字段读写 + 字面量
    {
        std::string a = asm_of(
            "struct Point { x: int; y: int; }\n"
            "let p: Point = Point { x: 1, y: 2 };\n"
            "p.x = p.x + 1;\n"
            "print(p.x, p.y);");
        CHECK(a.find("_main:") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
    }

    // 值拷贝：p/q 各 2 个字段槽（4 槽 → 32 字节帧），拷贝逐字段 load/store
    {
        std::string a = asm_of(
            "struct Point { x: int; y: int; }\n"
            "let p = Point { x: 1, y: 2 };\n"
            "let q = p;\n"
            "q.x = 9;\n"
            "print(p.x, q.x);");
        CHECK(a.find("sub sp, sp, #32") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-32]") != std::string::npos);
    }

    // 整体赋值（字面量 / 同类型变量）
    {
        std::string a = asm_of(
            "struct Point { x: int; y: int; }\n"
            "let p = Point { x: 1, y: 2 };\n"
            "let q = Point { x: 3, y: 4 };\n"
            "p = q;\n"
            "p = Point { x: 5, y: 6 };\n"
            "print(p.x, p.y);");
        CHECK(a.find("sub sp, sp, #32") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
    }

    // 字段可以是 float / bool
    {
        std::string a = asm_of(
            "struct S { f: float; b: bool; }\n"
            "let s: S = S { f: 1.5, b: true };\n"
            "s.f = s.f * 2.0;\n"
            "print(s.f, s.b);");
        CHECK(a.find("str d9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("ldr d9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("fmul") != std::string::npos);
    }

    // struct 错误路径
    CHECK_THROWS(asm_of("struct Point { x: int; y: int; }\nlet p: Point = Point { x: 1 };"),
                 "缺少字段 `y`");
    CHECK_THROWS(asm_of("struct Point { x: int; y: int; }\nlet p: Point = Point { x: 1, y: 2, z: 3 };"),
                 "没有字段 `z`");
    CHECK_THROWS(asm_of("struct Point { x: int; }\nlet p: Point = Point { x: \"s\" };"),
                 "字段 `x` 类型不匹配");
    CHECK_THROWS(asm_of("struct Point { x: int; }\nfn f(p: Point) -> int { return p.x; }"),
                 "不支持 struct 参数");
    CHECK_THROWS(asm_of("struct Point { x: int; }\nfn f() -> Point { return Point { x: 1 }; }"),
                 "不支持 struct 返回值");
    CHECK_THROWS(asm_of("struct Point { x: int; }\nlet p = Point { x: 1 };\nprint(p);"),
                 "不能直接取值");
    CHECK_THROWS(asm_of("struct Point { x: int; }\nlet p = Point { x: 1 };\nprint(p.z);"),
                 "没有字段 `z`");
    CHECK_THROWS(asm_of("struct Point { x: int; }\nlet p = Point { x: 1 };\np.z = 1;"),
                 "没有字段 `z`");
    CHECK_THROWS(asm_of("struct Point { x: int; }\nlet p = Point { x: 1 };\np.x = \"s\";"),
                 "字段 `x` 类型不匹配");
    CHECK_THROWS(asm_of("let p: Nope = Nope { x: 1 };"), "未定义的 struct `Nope`");
    CHECK_THROWS(asm_of("struct Point { x: int; x: int; }"), "字段 `x` 重复");
    CHECK_THROWS(asm_of("struct Point { x: int; }\nstruct Point { y: int; }"), "重复定义");
    CHECK_THROWS(asm_of("struct Empty { }"), "至少需要一个字段");
    CHECK_THROWS(asm_of("struct Point { s: string; }"), "只支持 int/float/bool");
    CHECK_THROWS(asm_of("struct Point { x: Point; }"), "只支持 int/float/bool");
    CHECK_THROWS(asm_of("struct Point { x: int; }\nlet p = Point { x: 1, x: 2 };"),
                 "重复初始化");
    CHECK_THROWS(asm_of("struct A { x: int; }\nstruct B { y: int; }\n"
                        "let a = A { x: 1 };\nlet b = B { y: 2 };\na = b;"),
                 "赋值类型不匹配");
    CHECK_THROWS(asm_of("let x: int = 1;\nprint(x.y);"), "不是 struct");
    CHECK_THROWS(asm_of("struct Point { x: int; }\nlet p = Point { x: 1 };\nprint(p.x.y);"),
                 "只支持对 struct 变量取字段");
    CHECK_THROWS(asm_of("struct Point { x: int; }\nlet x: int = Point { x: 1 };"),
                 "struct 字面量只能用于");

    // struct 错误也带 `[行:列]`
    {
        bool threw = false;
        try {
            asm_of("struct Point { x: int; y: int; }\nlet p: Point = Point { x: 1 };");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 16);
            CHECK(e.str().find("[2:16]") != std::string::npos);
        }
        CHECK(threw);
    }
    {
        bool threw = false;
        try {
            asm_of("struct Point { x: int; }\nfn f(p: Point) -> int { return p.x; }");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 1);
        }
        CHECK(threw);
    }
}

// ---- array v1 ----

static void test_array() {
    // 词法：array 关键字、[ ]
    {
        auto toks = Lexer::tokenize("array<int> = [1, 2]");
        CHECK(toks.size() == 11);  // array < int > = [ 1 , 2 ] EOF
        CHECK(toks[0].kind == Kind::ArrayType);
        CHECK(toks[1].kind == Kind::Lt && toks[3].kind == Kind::Gt);
        CHECK(toks[5].kind == Kind::LBracket && toks[5].pos == Position(1, 14));
        CHECK(toks[9].kind == Kind::RBracket && toks[9].pos == Position(1, 19));
    }

    // 语法：array<T> 类型 / 字面量 / 下标 / 下标赋值
    {
        auto prog = Parser::parse(
            "let a: array<int> = [1, 2, 3];\n"
            "let n = len(a);\n"
            "a[0] = a[1];");
        CHECK(prog.stmts.size() == 3);
        CHECK(prog.stmts[0]->kind == Stmt::Kind::Let);
        CHECK(prog.stmts[0]->ty.has_value() && *prog.stmts[0]->ty == "array<int>");
        CHECK(prog.stmts[0]->value->kind == Expr::Kind::Array);
        CHECK(prog.stmts[0]->value->args.size() == 3);
        CHECK(prog.stmts[0]->value->args[2]->kind == Expr::Kind::Int);
        CHECK(prog.stmts[1]->value->kind == Expr::Kind::Call &&
              prog.stmts[1]->value->name == "len");
        auto* assign = prog.stmts[2]->expr.get();
        CHECK(assign->kind == Expr::Kind::Assign);
        CHECK(assign->lhs->kind == Expr::Kind::Index);
        CHECK(assign->lhs->lhs->kind == Expr::Kind::Var && assign->lhs->lhs->name == "a");
        CHECK(assign->lhs->rhs->kind == Expr::Kind::Int && assign->lhs->rhs->int_val == 0);
        CHECK(assign->value->kind == Expr::Kind::Index);
        CHECK(assign->value->rhs->kind == Expr::Kind::Int && assign->value->rhs->int_val == 1);
    }

    // 字面量初始化：3 个 8 字节槽（帧 24 → 32），元素 0 在最低地址
    {
        std::string a = asm_of(
            "let a: array<int> = [3, 1, 2];\n"
            "print(a[0], a[1], a[2], len(a));");
        CHECK(a.find("sub sp, sp, #32") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-24]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("mov x9, #3") != std::string::npos);
    }

    // 动态下标：边界检查（无符号比较）+ 寄存器偏移寻址 + 运行时失败调用
    {
        std::string a = asm_of(
            "let a = [1, 2];\n"
            "let i: int = 1;\n"
            "print(a[i]);\n"
            "a[i] = a[0];");
        CHECK(a.find("cmp x10, #2") != std::string::npos);
        CHECK(a.find("b.hs L.bounds.fail.") != std::string::npos);
        CHECK(a.find("bl _tenet_bounds_fail") != std::string::npos);
        CHECK(a.find("ldr x9, [x16, x10, lsl #3]") != std::string::npos);
        CHECK(a.find("str x9, [x16, x10, lsl #3]") != std::string::npos);
        CHECK(a.find("_tenet_bounds_fail:") != std::string::npos);
        CHECK(a.find("Tenet runtime error: array index %lld out of bounds for length %lld") !=
              std::string::npos);
    }

    // 常量下标：编译期检查 + 直接槽位寻址（不生成边界检查）
    {
        std::string a = asm_of("let a = [1, 2, 3];\nprint(a[2]);");
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("bl _tenet_bounds_fail") == std::string::npos);
    }

    // len 是编译期常量
    {
        std::string a = asm_of("let a = [1, 2, 3];\nprint(len(a));");
        CHECK(a.find("mov x9, #3") != std::string::npos);
        CHECK(a.find("_len") == std::string::npos);
    }

    // 值拷贝：a[2 槽] 与 b[2 槽] 各占独立槽，逐元素 ldr/str
    {
        std::string a = asm_of(
            "let a = [1, 2];\n"
            "let b = a;\n"
            "a[0] = 9;\n"
            "b = a;\n"
            "print(a[0], b[0], len(a));");
        CHECK(a.find("sub sp, sp, #32") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-32]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);
        CHECK(a.find("mov x9, #2") != std::string::npos);
    }

    // float 元素用 d 寄存器与 8 字节槽
    {
        std::string a = asm_of(
            "let f: array<float> = [1.5, 2.5];\n"
            "print(f[0], f[1], len(f));");
        CHECK(a.find("str d9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("str d9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("ldr d9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("ldr d9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("mov x9, #2") != std::string::npos);
    }

    // bool 元素仍占 8 字节槽
    {
        std::string a = asm_of(
            "let t: array<bool> = [true, false];\n"
            "print(t[0], t[1], len(t));");
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("mov x9, #2") != std::string::npos);
    }

    // 整体赋值为同长度字面量
    {
        std::string a = asm_of("let a = [1, 2];\na = [3, 4];\nprint(a[0], a[1]);");
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
    }

    // 局部数组可出现在函数体内（循环 + 动态下标）
    {
        std::string a = asm_of(
            "fn sum3(x: int) -> int {\n"
            "  let a: array<int> = [x, x + 1, x + 2];\n"
            "  let s: int = 0;\n"
            "  let i: int = 0;\n"
            "  while (i < len(a)) { s = s + a[i]; i = i + 1; }\n"
            "  return s;\n"
            "}\n"
            "print(sum3(1));");
        CHECK(a.find("_sum3:") != std::string::npos);
        CHECK(a.find("bl _sum3") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);
        CHECK(a.find("ldr x9, [x16, x10, lsl #3]") != std::string::npos);
    }

    // struct 与 array 的槽位互不覆盖
    {
        std::string a = asm_of(
            "struct Point { x: int; y: int; }\n"
            "let p = Point { x: 1, y: 2 };\n"
            "let a = [3, 4];\n"
            "print(p.x, a[0]);");
        CHECK(a.find("sub sp, sp, #32") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);   // p.x
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);  // p.y
        CHECK(a.find("str x9, [x29, #-32]") != std::string::npos);  // a[0]
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);  // a[1]
    }

    // 常量越界：编译期报错，带 [行:列]
    {
        bool threw = false;
        try {
            asm_of("let a = [1, 2];\nprint(a[2]);");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.message == "数组下标 2 越界（长度 2）");
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 9);
            CHECK(e.str().find("[2:9]") != std::string::npos);
        }
        CHECK(threw);
    }
    CHECK_THROWS(asm_of("let a = [1, 2];\nprint(a[-1]);"), "数组下标 -1 越界（长度 2）");
    CHECK_THROWS(asm_of("let a = [1];\na[1] = 2;"), "数组下标 1 越界（长度 1）");

    // 元素类型
    CHECK_THROWS(asm_of("let a: array<int> = [1, 2.0];"),
                 "数组元素 1 类型不匹配：需要 int，实际 float");
    CHECK_THROWS(asm_of("let a = [1];\na[0] = 1.5;"),
                 "数组元素赋值类型不匹配：需要 int，实际 float");
    CHECK_THROWS(asm_of("let a = [1, 2.0];"), "数组元素类型不一致");
    CHECK_THROWS(asm_of("let a: array<float> = [1.5, 2.5];\na[0] = 1;"),
                 "数组元素赋值类型不匹配：需要 float，实际 int");
    CHECK_THROWS(asm_of("let a: array<bool> = [true];\na[0] = 1;"),
                 "数组元素赋值类型不匹配：需要 bool，实际 int");

    // 下标必须 int
    CHECK_THROWS(asm_of("let a = [1, 2];\nprint(a[true]);"),
                 "数组下标必须是 int，实际为 bool");
    CHECK_THROWS(asm_of("let a = [1.5];\nlet i = 1.5;\nprint(a[i]);"),
                 "数组下标必须是 int，实际为 float");

    // 整体赋值：长度 / 类型
    CHECK_THROWS(asm_of("let a = [1, 2];\na = [3, 4, 5];"),
                 "数组赋值长度不匹配：需要 2，实际 3");
    CHECK_THROWS(asm_of("let a = [1];\nlet f = [1.5];\na = f;"),
                 "数组赋值类型不匹配：需要 array<int>，右侧是 array<float>");
    CHECK_THROWS(asm_of("let a = [1];\nlet b: array<float> = a;"),
                 "`b` 需要 array<float>，但 `a` 是 array<int>");
    CHECK_THROWS(asm_of("let a = [1];\na = 1;"),
                 "数组赋值必须是同类型数组变量或同长度字面量");

    // 非数组 / 非变量下标
    CHECK_THROWS(asm_of("let x: int = 1;\nprint(x[0]);"), "`x` 不是数组，不能取下标");
    CHECK_THROWS(asm_of("let x: int = 1;\nx[0] = 2;"), "`x` 不是数组，不能写下标");
    CHECK_THROWS(asm_of("let a = [1];\nprint(a[0][0]);"), "v1 只支持对数组变量取下标");
    CHECK_THROWS(asm_of("fn f() -> int { return 1; }\nprint(f()[0]);"),
                 "v1 只支持对数组变量取下标");

    // 数组不能直接取值 / 打印 / 作参数 / 返回值
    CHECK_THROWS(asm_of("let a = [1, 2];\nprint(a);"), "数组变量 `a` 不能直接取值");
    CHECK_THROWS(asm_of("let a = [1, 2];\nlet x: int = a;"), "数组变量 `a` 不能直接取值");
    CHECK_THROWS(asm_of("print([1, 2]);"), "数组字面量只能用于 let 初始化或整体赋值");
    CHECK_THROWS(asm_of("let a = [1, 2];\nlet b: int = [1];"),
                 "数组字面量只能用于 let 初始化或整体赋值");
    CHECK_THROWS(asm_of("fn f(a: array<int>) -> int { return 0; }"),
                 "v1 不支持 array 参数：`f` 的参数 `a` 是 `array<int>`");
    CHECK_THROWS(asm_of("fn f() -> array<int> { return [1]; }"),
                 "v1 不支持 array 返回值：`f` 返回 `array<int>`");

    // 空数组 / 非标量元素 / 嵌套 / struct 字段
    CHECK_THROWS(asm_of("let a: array<int> = [];"), "v1 不支持空数组字面量");
    CHECK_THROWS(asm_of("let a = [];"), "v1 不支持空数组字面量");
    CHECK_THROWS(asm_of("let a: array<string> = [\"x\"];"),
                 "v1 数组元素只支持 int/float/bool");
    CHECK_THROWS(asm_of("let a: array<array<int>> = [[1]];"),
                 "v1 数组元素只支持 int/float/bool");
    CHECK_THROWS(asm_of("struct S { a: array<int>; }"), "只支持 int/float/bool");

    // len 的错误路径
    CHECK_THROWS(asm_of("let n = 1;\nlet m = len(n);"), "`len` 参数必须是数组");
    CHECK_THROWS(asm_of("let n = 1;\nprint(len(n));"), "不是数组，不能取 len");
    CHECK_THROWS(asm_of("let a = [1];\nprint(len(a, a));"),
                 "`len` 需要且只需要一个数组参数");
    CHECK_THROWS(asm_of("let a = [1];\nprint(len(a[0]));"), "`len` 参数必须是数组变量");

    // array 错误也带 [行:列]
    {
        bool threw = false;
        try {
            asm_of("let a = [1];\na[3] = 2;");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 3);
            CHECK(e.str().find("[2:3]") != std::string::npos);
        }
        CHECK(threw);
    }
}

int main() {
    test_lexer();
    test_parser();
    test_backend();
    test_array();

    std::cout << "通过 " << (checks - failures) << " / " << checks << " 项检查";
    if (failures > 0) {
        std::cout << "，失败 " << failures << " 项\n";
        return 1;
    }
    std::cout << "\n";
    return 0;
}
