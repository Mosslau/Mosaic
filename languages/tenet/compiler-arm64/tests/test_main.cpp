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

/// 只看用户代码生成部分（去掉内嵌运行时；运行时 _tenet_concat 里也有 bl _malloc）。
static std::string code_only(const std::string& asm_text) {
    size_t pos = asm_text.find("_tenet_strcmp:");
    return pos == std::string::npos ? asm_text : asm_text.substr(0, pos);
}

static int count_substr(const std::string& hay, const std::string& needle) {
    int n = 0;
    size_t pos = 0;
    while ((pos = hay.find(needle, pos)) != std::string::npos) {
        ++n;
        pos += needle.size();
    }
    return n;
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

    // print 变参：≤7 个用 x9-x15；8/9 个额外借用并保存 callee-saved x19/x20；>9 报错
    {
        std::string b = asm_of("print(1, 2, 3, 4, 5, 6, 7);");
        CHECK(b.find("stp x19, x20, [sp, #-16]!") == std::string::npos);
        std::string a = asm_of("print(1, 2, 3, 4, 5, 6, 7, 8, 9);");
        CHECK(a.find("stp x19, x20, [sp, #-16]!") != std::string::npos);
        CHECK(a.find("ldp x19, x20, [sp], #16") != std::string::npos);
        CHECK(count_substr(code_only(a), "%lld") == 9);
    }
    CHECK_THROWS(asm_of("print(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);"),
                 "print 暂不支持超过 9 个参数");

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
    // S3a：struct 参数按指针 ABI 传入，入口逐字段拷贝到本地扁平槽
    {
        std::string a = asm_of(
            "struct Point { x: int; }\nfn f(p: Point) -> int { return p.x; }");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #0]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
    }
    // S3a：struct 返回值走隐藏 sret 指针（x0），函数返回 void
    {
        std::string a = asm_of(
            "struct Point { x: int; }\nfn f() -> Point { return Point { x: 1 }; }");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x15, #0]") != std::string::npos);
    }
    {
        std::string a =
            asm_of("struct Point { x: int; }\nlet p = Point { x: 1 };\nprint(p);");
        CHECK(a.find(".asciz \"Point { \"") != std::string::npos);
        CHECK(a.find(".asciz \"x: \"") != std::string::npos);
    }
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
            asm_of("struct Ok { x: int; }\nstruct Point { x: Point; }");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 1);
            CHECK(e.str().find("[2:1]") != std::string::npos);
        }
        CHECK(threw);
    }
}

// ---- S3a：嵌套 struct + struct 参数/返回值 ----

static void test_struct_s3a() {
    // 语法：struct 字段类型可以是另一个 struct；链式字段 / 嵌套字面量
    {
        auto prog = Parser::parse(
            "struct Point { x: int; y: int; }\n"
            "struct Line { a: Point; b: Point; }\n"
            "let l: Line = Line { a: Point { x: 1, y: 2 }, b: Point { x: 3, y: 4 } };\n"
            "print(l.a.x);");
        CHECK(prog.stmts.size() == 4);
        CHECK(prog.stmts[1]->kind == Stmt::Kind::StructDecl);
        CHECK(prog.stmts[1]->fields.size() == 2);
        CHECK(prog.stmts[1]->fields[0].second == "Point");
        CHECK(prog.stmts[2]->value->kind == Expr::Kind::StructLit);
        CHECK(prog.stmts[2]->value->fields[0].second->kind == Expr::Kind::StructLit);
        CHECK(prog.stmts[2]->value->fields[0].second->name == "Point");
        auto* chain = prog.stmts[3]->expr->args[0].get();
        CHECK(chain->kind == Expr::Kind::Field && chain->name == "x");
        CHECK(chain->lhs->kind == Expr::Kind::Field && chain->lhs->name == "a");
        CHECK(chain->lhs->lhs->kind == Expr::Kind::Var && chain->lhs->lhs->name == "l");
    }

    // 嵌套扁平槽 + 字面量 + 整体拷贝：Line l/m 各 4 槽，深度优先声明顺序
    {
        std::string a = asm_of(
            "struct Point { x: int; y: int; }\n"
            "struct Line { a: Point; b: Point; }\n"
            "let l: Line = Line { a: Point { x: 1, y: 2 }, b: Point { x: 3, y: 4 } };\n"
            "let m = l;\n"
            "m.a.x = 99;\n"
            "print(l.a.x, m.a.x, l.b.y);");
        CHECK(a.find("sub sp, sp, #64") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);   // l.a.x
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);  // l.a.y
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);  // l.b.x
        CHECK(a.find("str x9, [x29, #-32]") != std::string::npos);  // l.b.y
        CHECK(a.find("str x9, [x29, #-40]") != std::string::npos);  // m.a.x（拷贝/改写）
        CHECK(a.find("str x9, [x29, #-64]") != std::string::npos);  // m.b.y
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-32]") != std::string::npos);
    }

    // struct 参数 ABI：调用方传扁平槽首地址（x 寄存器），入口逐字段拷贝到本地槽
    {
        std::string a = asm_of(
            "struct Point { x: int; y: int; }\n"
            "fn f(p: Point) -> int { return p.x; }");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #0]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
    }

    // 参数值拷贝：入口先拷贝，再把 p.x 改成 9；调用方只传指针
    {
        std::string a = asm_of(
            "struct Point { x: int; y: int; }\n"
            "fn bump(p: Point) -> int { p.x = 9; return p.x; }\n"
            "let p: Point = Point { x: 1, y: 2 };\n"
            "let r: int = bump(p);\n"
            "print(p.x, r);");
        size_t copy_x = a.find("ldr x9, [x0, #0]");
        size_t write9 = a.find("mov x9, #9");
        CHECK(copy_x != std::string::npos);
        CHECK(write9 != std::string::npos);
        CHECK(copy_x < write9);  // 拷贝发生在函数体修改之前
        CHECK(a.find("sub x9, x29, #8") != std::string::npos);  // 传 &p 而非拷贝
        CHECK(a.find("ldp x0, xzr, [sp], #16") != std::string::npos);
        CHECK(a.find("bl _bump") != std::string::npos);
    }

    // struct 返回值 sret ABI：隐藏 x0、void 返回、写回调用方缓冲
    {
        std::string a = asm_of(
            "struct Point { x: int; y: int; }\n"
            "fn make() -> Point { return Point { x: 7, y: 8 }; }\n"
            "let p = make();\n"
            "print(p.x);");
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);  // 保存 sret 指针
        CHECK(a.find("str x9, [x15, #0]") != std::string::npos);
        CHECK(a.find("str x9, [x15, #-8]") != std::string::npos);
        CHECK(a.find("sub x0, x29, #") != std::string::npos);      // 调用方传返回缓冲
        CHECK(a.find("bl _make") != std::string::npos);
    }

    // 嵌套 struct 参数 + struct 返回值：sret 占 x0，struct 指针占 x1
    {
        std::string a = asm_of(
            "struct Point { x: int; y: int; }\n"
            "struct Line { a: Point; b: Point; }\n"
            "fn mid(l: Line) -> Point { return Point { x: l.a.x, y: l.b.y }; }\n"
            "let l: Line = Line { a: Point { x: 1, y: 2 }, b: Point { x: 3, y: 4 } };\n"
            "let m: Point = mid(l);\n"
            "print(m.x, m.y, l.a.x);");
        CHECK(a.find("_mid:") != std::string::npos);
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x1, #0]") != std::string::npos);
        CHECK(a.find("ldr x9, [x1, #-8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x1, #-16]") != std::string::npos);
        CHECK(a.find("ldr x9, [x1, #-24]") != std::string::npos);
        CHECK(a.find("ldp x1, xzr, [sp], #16") != std::string::npos);  // struct 指针进 x1
        CHECK(a.find("sub x0, x29, #") != std::string::npos);          // sret 指针进 x0
        CHECK(a.find("bl _mid") != std::string::npos);
    }

    // 多个 struct 参数：分别用 x0/x1 传地址，入口各自拷贝
    {
        std::string a = asm_of(
            "struct Point { x: int; y: int; }\n"
            "fn add(a: Point, b: Point) -> int { return a.x + b.x; }\n"
            "let p = Point { x: 1, y: 2 };\n"
            "print(add(p, p));");
        CHECK(a.find("_add:") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #0]") != std::string::npos);
        CHECK(a.find("ldr x9, [x1, #0]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);   // a.x
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);  // a.y
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);  // b.x
        CHECK(a.find("str x9, [x29, #-32]") != std::string::npos);  // b.y
        CHECK(a.find("bl _add") != std::string::npos);
    }

    // 8 个参数位（含 struct 指针）刚好可用；超出明确报错
    {
        std::string a = asm_of(
            "struct P { x: int; }\n"
            "fn f(p: P, a: int, b: int, c: int, d: int, e: int, g: int, h: int) -> int {\n"
            "  return p.x + a + b + c + d + e + g + h;\n"
            "}\n"
            "let p = P { x: 1 };\n"
            "print(f(p, 2, 3, 4, 5, 6, 7, 8));");
        CHECK(a.find("bl _f") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #0]") != std::string::npos);
    }
    {
        std::string a = asm_of(
            "fn f(a: int, b: int, c: int, d: int, e: int, g: int, h: int, i: int) -> int {\n"
            "  return a + b + c + d + e + g + h + i;\n"
            "}\n"
            "print(f(1, 2, 3, 4, 5, 6, 7, 8));");
        CHECK(a.find("_f:") != std::string::npos);
    }
    CHECK_THROWS(asm_of(
                     "struct P { x: int; }\n"
                     "fn f(p: P, a: int, b: int, c: int, d: int, e: int, g: int, h: int) -> P {\n"
                     "  return p;\n"
                     "}"),
                 "参数位超过 8");

    // 字面量 / 返回 struct 的调用都可以作实参
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn get(p: P) -> int { return p.x; }\n"
            "print(get(P { x: 1, y: 2 }));");
        CHECK(a.find("_get:") != std::string::npos);
        CHECK(a.find("sub sp, sp, #16") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("bl _get") != std::string::npos);
    }
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn mk() -> P { return P { x: 1, y: 2 }; }\n"
            "fn get(p: P) -> int { return p.x; }\n"
            "print(get(mk()));");
        CHECK(a.find("bl _mk") != std::string::npos);
        CHECK(a.find("bl _get") != std::string::npos);
    }

    // struct 返回值可用于 let / 整体赋值 / return（变量、字面量、调用三种来源）
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn mk() -> P { return P { x: 1, y: 2 }; }\n"
            "fn id(p: P) -> P { return p; }\n"
            "fn chain() -> P { return mk(); }\n"
            "let p = mk();\n"
            "let q: P = P { x: 0, y: 0 };\n"
            "q = mk();\n"
            "q = p;\n"
            "let z = chain();\n"
            "print(q.x, z.x);");
        CHECK(a.find("_id:") != std::string::npos);
        CHECK(a.find("_chain:") != std::string::npos);
        CHECK(a.find("bl _mk") != std::string::npos);
        CHECK(a.find("bl _id") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, #0]") != std::string::npos);
    }

    // float / bool 字段跨参数/返回值仍按 8 字节槽（float 用位模式）
    {
        std::string a = asm_of(
            "struct S { f: float; b: bool; }\n"
            "fn mk() -> S { return S { f: 1.5, b: true }; }\n"
            "fn id(s: S) -> S { return s; }\n"
            "let s = mk();\n"
            "let t = id(s);\n"
            "print(t.f, t.b);");
        CHECK(a.find("fmov x9, d9") != std::string::npos);
        CHECK(a.find("ldr x9, [x1, #0]") != std::string::npos);  // sret 占 x0，struct 参数在 x1
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
    }

    // S3e：struct 支持动态 array<标量> 字段；动态 array<struct> 与动态嵌套字段仍拒绝。
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct S { a: array<P>; }"),
                 "不支持 array");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct S { a: array<P>; }"),
                 "array<struct>");
    {
        std::string a = asm_of("struct S { a: array<int>; x: int; }\n"
                               "let s: S = S { a: [1, 2], x: 3 };\nprint(len(s.a));");
        CHECK(a.find("bl _malloc") != std::string::npos);
    }
    {
        std::string a = asm_of("struct P { x: int; }\nlet a: array<P> = [P { x: 1 }];");
        CHECK(a.find("bl _malloc") != std::string::npos);
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);
    }
    {
        std::string a = asm_of("struct P { x: int; }\nfn f(a: array<P>) -> int { return 0; }");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("L.dyn.param.copy.") != std::string::npos);
    }
    // S3c-3d：固定 array<struct, N> 参数也走指针 ABI（入口按 N*slots 拷贝）。
    {
        std::string a = asm_of("struct P { x: int; y: int; }\n"
                               "fn f(a: array<P, 3>) -> int { return a[0].x; }");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #40]") != std::string::npos);   // 3 元素 × 2 字段 = 6 槽
        CHECK(a.find("str x9, [x29, #-48]") != std::string::npos);  // 本地槽 0
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);   // 本地槽 5
    }

    // 循环嵌套（含自引用）/ 未定义字段类型
    CHECK_THROWS(asm_of("struct A { b: B; }\nstruct B { a: A; }"), "循环嵌套");
    CHECK_THROWS(asm_of("struct A { b: A; }"), "循环嵌套");
    CHECK_THROWS(asm_of("struct A { b: Nope; }"), "类型 `Nope` 未定义");

    // 嵌套字面量错误
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct L { a: P; b: P; }\n"
                        "let l = L { a: P { x: 1 } };"),
                 "缺少字段 `b`");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct L { a: P; b: P; }\n"
                        "let l = L { a: P { x: 1 }, b: P { z: 2 } };"),
                 "没有字段 `z`");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct L { a: P; b: P; }\n"
                        "let l = L { a: P { x: 1 }, b: 3 };"),
                 "需要 P 字面量");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct Q { y: int; }\nstruct L { a: P; b: P; }\n"
                        "let l = L { a: P { x: 1 }, b: Q { y: 2 } };"),
                 "实际字面量是 Q");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct L { a: P; b: P; }\n"
                        "let l = L { a: P { x: \"s\" }, b: P { x: 2 } };"),
                 "类型不匹配");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct L { a: P; b: P; }\n"
                        "let l = L { a: P { x: 1 }, b: P { x: 2 } };\nl.a.x.y = 1;"),
                 "只支持对 struct 变量写字段");

    // 可直接 print struct 变量；嵌套 struct 字段需继续访问到标量
    {
        std::string a = asm_of("struct P { x: int; }\nlet p = P { x: 1 };\nprint(p);");
        CHECK(a.find(".asciz \"P { \"") != std::string::npos);
    }
    CHECK_THROWS(asm_of("struct P { x: int; }\nfn mk() -> P { return P { x: 1 }; }\nprint(mk());"),
                 "print 不支持该类型的值");
    CHECK_THROWS(asm_of("struct P { x: int; }\nprint(P { x: 1 });"),
                 "struct 字面量只能用于");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct L { a: P; b: P; }\n"
                        "let l = L { a: P { x: 1 }, b: P { x: 2 } };\nprint(l.a);"),
                 "是 struct");
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

    // 语法：array<T, N> 类型 / 字面量 / 下标 / 下标赋值
    {
        auto prog = Parser::parse(
            "let a: array<int, 3> = [1, 2, 3];\n"
            "let n = len(a);\n"
            "a[0] = a[1];");
        CHECK(prog.stmts.size() == 3);
        CHECK(prog.stmts[0]->kind == Stmt::Kind::Let);
        CHECK(prog.stmts[0]->ty.has_value() && *prog.stmts[0]->ty == "array<int,3>");
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
            "let a: array<int, 3> = [3, 1, 2];\n"
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

    // 字面量推断为 array<T, N>：省略标注时长度仍是类型的一部分，可与显式定长数组互操作
    {
        std::string a = asm_of(
            "let a = [1, 2, 3];\n"
            "let b: array<int, 3> = a;\n"
            "b[0] = 9;\n"
            "print(a[0], b[0], len(a));");
        CHECK(a.find("sub sp, sp, #48") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-48]") != std::string::npos);  // b[0]
        CHECK(a.find("mov x9, #3") != std::string::npos);
    }
    // 推断结果带长度：错误信息里的类型是 array<T, N>
    CHECK_THROWS(asm_of("let a = [1, 2];\nlet b = [1.5, 2.5];\na = b;"),
                 "需要 array<int,2>，右侧是 array<float,2>");

    // S3c：局部 array<T> 是动态数组（堆缓冲 + data/len/cap 三槽），不再是占位报错
    {
        std::string a = asm_of("let a: array<int> = [1, 2];\nprint(a[0], len(a));");
        CHECK(a.find("bl _malloc") != std::string::npos);
        CHECK(a.find("bl _free") != std::string::npos);           // main 结束 drop
        CHECK(a.find("mov x0, #32") != std::string::npos);        // cap = max(2,4) * 8
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);  // data
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos); // len 运行时读取
    }
    {
        std::string a = asm_of(
            "let a: array<int> = [1, 2];\n"
            "let b: array<int> = a;\n"
            "print(b[0]);");
        CHECK(a.find("bl _malloc") != std::string::npos);
        CHECK(a.find("dyn.copy") != std::string::npos);  // 深拷贝循环
    }
    {
        std::string a = asm_of(
            "let a: array<float> = [1.5];\n"
            "push(a, 2.5);\n"
            "print(a[1]);");
        CHECK(a.find("fmov x11, d9") != std::string::npos);  // push float 位模式
        CHECK(a.find("ldr d9, [x14, x10, lsl #3]") != std::string::npos);
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
            "let f: array<float, 2> = [1.5, 2.5];\n"
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
            "let t: array<bool, 2> = [true, false];\n"
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
            "  let a: array<int, 3> = [x, x + 1, x + 2];\n"
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
    CHECK_THROWS(asm_of("let a: array<int, 2> = [1, 2.0];"),
                 "数组元素 1 类型不匹配：需要 int，实际 float");
    CHECK_THROWS(asm_of("let a = [1];\na[0] = 1.5;"),
                 "数组元素赋值类型不匹配：需要 int，实际 float");
    CHECK_THROWS(asm_of("let a = [1, 2.0];"), "数组元素类型不一致");
    CHECK_THROWS(asm_of("let a: array<float, 2> = [1.5, 2.5];\na[0] = 1;"),
                 "数组元素赋值类型不匹配：需要 float，实际 int");
    CHECK_THROWS(asm_of("let a: array<bool, 1> = [true];\na[0] = 1;"),
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
                 "数组赋值类型不匹配：需要 array<int,1>，右侧是 array<float,1>");
    CHECK_THROWS(asm_of("let a = [1];\nlet b: array<float, 1> = a;"),
                 "`b` 需要 array<float,1>，但 `a` 是 array<int,1>");
    CHECK_THROWS(asm_of("let a = [1];\na = 1;"),
                 "数组赋值必须是同类型数组变量或同长度字面量");

    // 非数组 / 非变量下标
    CHECK_THROWS(asm_of("let x: int = 1;\nprint(x[0]);"), "`x` 不是数组，不能取下标");
    CHECK_THROWS(asm_of("let x: int = 1;\nx[0] = 2;"), "`x` 不是数组，不能写下标");
    CHECK_THROWS(asm_of("let a = [1];\nprint(a[0][0]);"),
                 "不是嵌套数组（需要 `array<array<T, N>, M>`）");
    CHECK_THROWS(asm_of("fn f() -> int { return 1; }\nprint(f()[0]);"),
                 "v1 只支持对数组变量取下标");

    // 数组不能直接取值，但可以直接 print；S3c-2 允许 array<T> 作参数/返回值（descriptor/sret ABI）
    {
        std::string a = asm_of("let a = [1, 2];\nprint(a);");
        CHECK(a.find(".asciz \"[\"") != std::string::npos);
        CHECK(a.find(".asciz \"]\"") != std::string::npos);
    }
    CHECK_THROWS(asm_of("let a = [1, 2];\nlet x: int = a;"), "数组变量 `a` 不能直接取值");
    CHECK_THROWS(asm_of("print([1, 2]);"), "数组字面量只能用于 let 初始化或整体赋值");
    CHECK_THROWS(asm_of("let a = [1, 2];\nlet b: int = [1];"),
                 "数组字面量只能用于 let 初始化或整体赋值");
    {
        std::string a = asm_of(
            "fn sum(a: array<int>) -> int { return len(a); }\n"
            "let x: array<int> = [1, 2];\nprint(sum(x));");
        CHECK(a.find("bl _malloc") != std::string::npos);  // 参数入口深拷贝
        CHECK(a.find("dyn.param.copy") != std::string::npos);
    }
    // S3c-3a：动态数组 return 支持字面量/调用；其他表达式（数字等）报错
    CHECK_THROWS(asm_of("fn f() -> array<int> { return 1; }"),
                 "动态数组 return 只支持变量、字面量或返回动态数组的调用");

    // 空数组 / 非标量元素 / 嵌套 / struct 字段
    CHECK_THROWS(asm_of("let a: array<int, 1> = [];"), "v1 不支持空数组字面量");
    CHECK_THROWS(asm_of("let a = [];"), "v1 不支持空数组字面量");
    CHECK_THROWS(asm_of("let a: array<string, 1> = [\"x\"];"),
                 "v1 数组元素只支持 int/float/bool");
    CHECK_THROWS(asm_of("let a: array<array<bool, 1>, 1> = [[true]];"),
                 "嵌套数组内层暂不支持 bool");
    CHECK_THROWS(asm_of("struct S { a: array<string>; }"), "只支持 int/float/bool");

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

// ---- S3b：定长 array<T, N> 参数/返回值（指针 + sret ABI）----

static void test_array_s3b() {
    // 语法：array<T, N>（函数参数/返回值 + 局部变量）
    {
        auto prog = Parser::parse(
            "fn f(a: array<int, 3>) -> array<float, 2> { return [1.5, 2.5]; }");
        CHECK(prog.stmts[0]->kind == Stmt::Kind::FnDecl);
        CHECK(prog.stmts[0]->params.size() == 1);
        CHECK(prog.stmts[0]->params[0].first == "a");
        CHECK(prog.stmts[0]->params[0].second == "array<int,3>");
        CHECK(prog.stmts[0]->ret.has_value() && *prog.stmts[0]->ret == "array<float,2>");
    }
    {
        auto prog = Parser::parse("let a: array<bool, 4> = [true, false, true, false];");
        CHECK(prog.stmts[0]->ty.has_value() && *prog.stmts[0]->ty == "array<bool,4>");
        CHECK(prog.stmts[0]->value->kind == Expr::Kind::Array);
        CHECK(prog.stmts[0]->value->args.size() == 4);
    }
    // N 必须是正整数字面量
    CHECK_THROWS(Parser::parse("let a: array<int, 0> = [1];"), "正整数");
    CHECK_THROWS(Parser::parse("let a: array<int, -1> = [1];"), "正整数");
    CHECK_THROWS(Parser::parse("let a: array<int, n> = [1];"), "正整数");

    // 数组参数：x 寄存器传指针，入口逐元素拷贝到本地 [N x T] 槽
    {
        std::string a = asm_of(
            "fn sum(a: array<int, 3>) -> int {\n"
            "  return a[0] + a[1] + a[2];\n"
            "}");
        CHECK(a.find("_sum:") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #0]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #8]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #16]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
    }

    // 参数值拷贝：入口先拷贝，函数体再改 a[0]；调用方只传 &a
    {
        std::string a = asm_of(
            "fn bump(a: array<int, 2>) -> int {\n"
            "  a[0] = 9;\n"
            "  return a[0];\n"
            "}\n"
            "let a: array<int, 2> = [1, 2];\n"
            "let r: int = bump(a);\n"
            "print(a[0], r);");
        size_t copy = a.find("ldr x9, [x0, #0]");
        size_t write9 = a.find("mov x9, #9");
        CHECK(copy != std::string::npos);
        CHECK(write9 != std::string::npos);
        CHECK(copy < write9);  // 拷贝发生在函数体修改之前
        CHECK(a.find("sub x9, x29, #16") != std::string::npos);  // 传 &a（2 槽）
        CHECK(a.find("ldp x0, xzr, [sp], #16") != std::string::npos);
        CHECK(a.find("bl _bump") != std::string::npos);
    }

    // 数组返回值：隐藏 sret 指针（x0）+ void 返回；调用方分配缓冲、调用后解包
    {
        std::string a = asm_of(
            "fn make() -> array<int, 3> { return [7, 8, 9]; }\n"
            "let b: array<int, 3> = make();\n"
            "print(b[0], b[1], b[2]);");
        CHECK(a.find("_make:") != std::string::npos);
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);  // 保存 sret
        CHECK(a.find("str x9, [x15, #0]") != std::string::npos);
        CHECK(a.find("str x9, [x15, #8]") != std::string::npos);
        CHECK(a.find("str x9, [x15, #16]") != std::string::npos);
        CHECK(a.find("sub x0, x29, #") != std::string::npos);  // 调用方传返回缓冲
        CHECK(a.find("bl _make") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, #0]") != std::string::npos);  // 返回缓冲解包
        CHECK(a.find("ldr x9, [x10, #16]") != std::string::npos);
    }

    // 数组参数 + 数组返回值：sret 占 x0，数组参数指针占 x1
    {
        std::string a = asm_of(
            "fn id(a: array<int, 3>) -> array<int, 3> { return a; }\n"
            "let a = [1, 2, 3];\n"
            "let b = id(a);\n"
            "print(b[0]);");
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x1, #0]") != std::string::npos);
        CHECK(a.find("ldr x9, [x1, #8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x1, #16]") != std::string::npos);
        CHECK(a.find("ldp x1, xzr, [sp], #16") != std::string::npos);
        CHECK(a.find("bl _id") != std::string::npos);
    }

    // 数组实参三种来源：变量 / 同长度字面量 / 返回数组的调用
    {
        std::string a = asm_of(
            "fn sum(a: array<int, 3>) -> int { return a[0] + a[1] + a[2]; }\n"
            "fn make() -> array<int, 3> { return [1, 2, 3]; }\n"
            "print(sum([1, 2, 3]));\n"
            "print(sum(make()));");
        CHECK(a.find("bl _sum") != std::string::npos);
        CHECK(a.find("sub x9, x29, #") != std::string::npos);  // 字面量打包缓冲
        CHECK(a.find("bl _make") != std::string::npos);
    }

    // 数组返回值用于 let / 整体赋值 / return
    {
        std::string a = asm_of(
            "fn mk() -> array<int, 3> { return [1, 2, 3]; }\n"
            "fn chain() -> array<int, 3> { return mk(); }\n"
            "let a = mk();\n"
            "let b: array<int, 3> = [0, 0, 0];\n"
            "b = mk();\n"
            "let c = chain();\n"
            "print(a[0], b[1], c[2]);");
        CHECK(a.find("_chain:") != std::string::npos);
        CHECK(a.find("bl _mk") != std::string::npos);
        CHECK(a.find("bl _chain") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, #0]") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, #8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, #16]") != std::string::npos);
        CHECK(a.find("sub x0, x29, #") != std::string::npos);
    }

    // float / bool 元素：仍按 8 字节位模式槽打包/拷贝
    {
        std::string a = asm_of(
            "fn sumf(a: array<float, 2>) -> float { return a[0] + a[1]; }\n"
            "fn mkf() -> array<float, 2> { return [1.5, 2.5]; }\n"
            "fn mkb() -> array<bool, 2> { return [true, false]; }\n"
            "let f = mkf();\n"
            "let b = mkb();\n"
            "print(sumf(f), b[0], b[1], len(f));");
        CHECK(a.find("_sumf:") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #0]") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #8]") != std::string::npos);
        CHECK(a.find("fmov x9, d9") != std::string::npos);  // float 字面量按位打包
        CHECK(a.find("_mkf:") != std::string::npos);
        CHECK(a.find("_mkb:") != std::string::npos);
        CHECK(a.find("str x9, [x15, #0]") != std::string::npos);
        CHECK(a.find("str x9, [x15, #8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, #8]") != std::string::npos);
    }

    // 局部数组写 array<T, N> 或省略标注由字面量推断；显式 N 校验来源长度
    {
        std::string a = asm_of(
            "let a: array<int, 3> = [1, 2, 3];\n"
            "let b: array<int, 3> = a;\n"
            "b[0] = 9;\n"
            "print(a[0], b[0], len(a), len(b));");
        CHECK(a.find("sub sp, sp, #48") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-24]") != std::string::npos);  // a[0]
        CHECK(a.find("str x9, [x29, #-48]") != std::string::npos);  // b[0]
        CHECK(a.find("mov x9, #3") != std::string::npos);           // len 编译期常量
    }
    CHECK_THROWS(asm_of("let a: array<int, 3> = [1, 2];"),
                 "数组初始化长度不匹配：需要 3，实际 2");
    CHECK_THROWS(asm_of("let a: array<int, 3> = [1, 2, 3, 4];"),
                 "数组初始化长度不匹配：需要 3，实际 4");
    CHECK_THROWS(asm_of("let a = [1, 2];\nlet b: array<int, 3> = a;"),
                 "数组初始化长度不匹配：需要 3，实际 2");
    CHECK_THROWS(asm_of("let a: array<int, 3> = [1, 2, 3];\n"
                        "let b: array<int, 2> = [1, 2];\na = b;"),
                 "数组赋值长度不匹配：需要 3，实际 2");

    // 参数长度不匹配：变量长度 / 字面量长度 / 调用返回长度
    CHECK_THROWS(asm_of(
                     "fn sum(a: array<int, 3>) -> int { return a[0]; }\n"
                     "let b: array<int, 2> = [1, 2];\n"
                     "print(sum(b));"),
                 "数组实参长度不匹配：需要 3，实际 2");
    CHECK_THROWS(asm_of(
                     "fn sum(a: array<int, 3>) -> int { return a[0]; }\n"
                     "print(sum([1, 2]));"),
                 "数组长度不匹配：需要 3，实际 2");
    CHECK_THROWS(asm_of(
                     "fn sum(a: array<int, 3>) -> int { return a[0]; }\n"
                     "fn mk() -> array<int, 2> { return [1, 2]; }\n"
                     "print(sum(mk()));"),
                 "数组实参类型不匹配");

    // S3c-2：array<T>（无长度）参数不再报错，改走描述符指针 ABI（详见 test_dynamic_abi）
    {
        std::string a = asm_of("fn f(a: array<int>) -> int { return a[0]; }");
        CHECK(a.find("dyn.param.copy") != std::string::npos);  // 入口深拷贝
        CHECK(a.find("bl _malloc") != std::string::npos);
    }

    // 数组参数 / sret 指针也占参数位：8 个参数 + 数组返回值 = 9 位 → 明确报错
    CHECK_THROWS(asm_of(
                     "fn f(a: array<int, 2>, b: int, c: int, d: int, e: int, g: int, h: int, i: int)\n"
                     "    -> array<int, 2> { return a; }"),
                 "参数位超过 8");

    // len(数组参数) 仍是编译期常量
    {
        std::string a = asm_of("fn n(a: array<int, 4>) -> int { return len(a); }");
        CHECK(a.find("mov x9, #4") != std::string::npos);
        CHECK(a.find("_len") == std::string::npos);
    }

    // 错误定位：参数长度不匹配指向实参 `b`；签名元素类型错误指向 fn 声明
    {
        bool threw = false;
        try {
            asm_of("fn sum(a: array<int, 3>) -> int { return a[0]; }\n"
                   "let b: array<int, 2> = [1, 2];\n"
                   "print(sum(b));");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 3 && e.pos->col == 11);
            CHECK(e.str().find("[3:11]") != std::string::npos);
        }
        CHECK(threw);
    }
    {
        bool threw = false;
        try {
            asm_of("fn f(a: array<string>) -> int { return 0; }");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 1 && e.pos->col == 1);
            CHECK(e.str().find("[1:1]") != std::string::npos);
        }
        CHECK(threw);
    }

    // 数组参数可以直接 print（按值拷贝后的本地槽展开）
    {
        std::string a = asm_of("fn f(a: array<int, 2>) { print(a); }");
        CHECK(a.find(".asciz \"[\"") != std::string::npos);
    }
}

// ---- S3c：局部动态数组 array<T>（堆、push、len、下标、深拷贝、drop）----

static void test_array_s3c() {
    // 语法：局部 array<T>（无长度）/ 空字面量 / push 调用
    {
        auto prog = Parser::parse(
            "let a: array<int> = [1, 2];\n"
            "let e: array<int> = [];\n"
            "push(a, 3);");
        CHECK(prog.stmts.size() == 3);
        CHECK(prog.stmts[0]->ty.has_value() && *prog.stmts[0]->ty == "array<int>");
        CHECK(prog.stmts[0]->value->kind == Expr::Kind::Array);
        CHECK(prog.stmts[0]->value->args.size() == 2);
        CHECK(prog.stmts[1]->ty.has_value() && *prog.stmts[1]->ty == "array<int>");
        CHECK(prog.stmts[1]->value->kind == Expr::Kind::Array);
        CHECK(prog.stmts[1]->value->args.empty());
        CHECK(prog.stmts[2]->expr->kind == Expr::Kind::Call);
        CHECK(prog.stmts[2]->expr->name == "push");
        CHECK(prog.stmts[2]->expr->args.size() == 2);
    }

    // 描述符三槽：data / len / cap；字面量 cap=max(n,4) 字节数 = cap*8
    {
        std::string a = asm_of("let a: array<int> = [1, 2];\nprint(a[1], len(a));");
        CHECK(a.find("sub sp, sp, #32") != std::string::npos);   // 3 个描述符槽
        CHECK(a.find("mov x0, #32") != std::string::npos);       // cap=4 → 32 字节
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);   // data
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);  // len=2
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);  // cap=4
        CHECK(a.find("ldr x14, [x29, #-8]") != std::string::npos);  // 元素写堆缓冲
        CHECK(a.find("str x9, [x14, #0]") != std::string::npos);
        CHECK(a.find("str x9, [x14, #8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos);  // len 运行时读取
    }

    // 空数组字面量：cap=4、len=0，可 push
    {
        std::string a = asm_of("let e: array<int> = [];\npush(e, 7);\nprint(len(e), e[0]);");
        CHECK(a.find("mov x0, #32") != std::string::npos);
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x11, [x14, x9, lsl #3]") != std::string::npos);  // push 写 data[len]
    }

    // push：容量足够直接写 data[len]；满时 cap*2 + malloc/copy/free
    {
        std::string a = asm_of("let a: array<int> = [1];\npush(a, 2);\nprint(len(a));");
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos);   // len
        CHECK(a.find("ldr x10, [x29, #-24]") != std::string::npos);  // cap
        CHECK(a.find("cmp x9, x10") != std::string::npos);
        CHECK(a.find("b.eq L.dyn.grow.") != std::string::npos);
        CHECK(a.find("str x11, [x14, x9, lsl #3]") != std::string::npos);
        CHECK(a.find("add x9, x9, #1") != std::string::npos);
    }
    {
        std::string a = asm_of(
            "let a: array<int> = [1, 2, 3, 4];\n"
            "push(a, 5);\n"
            "print(len(a));");
        CHECK(a.find("add x12, x10, x10") != std::string::npos);       // newcap = cap*2
        CHECK(a.find("csel x12, x13, x12, eq") != std::string::npos);  // cap==0 保底 4
        CHECK(a.find("lsl x0, x12, #3") != std::string::npos);         // newcap*8
        CHECK(a.find("bl _malloc") != std::string::npos);
        CHECK(a.find("ldr x10, [x15, x13, lsl #3]") != std::string::npos);  // 拷旧元素
        CHECK(a.find("str x10, [x14, x13, lsl #3]") != std::string::npos);
        CHECK(a.find("str x11, [x14, x9, lsl #3]") != std::string::npos);   // 写新元素
        CHECK(a.find("mov x0, x15") != std::string::npos);
        CHECK(a.find("bl _free") != std::string::npos);                // free 旧缓冲
        CHECK(a.find("str x12, [x29, #-24]") != std::string::npos);    // 更新 cap
    }

    // 下标：运行时边界检查（定长数组的动态下标也走这里，但长度是运行时的）
    {
        std::string a = asm_of(
            "let a: array<int> = [1, 2];\n"
            "let i: int = 1;\n"
            "print(a[i]);\n"
            "a[i] = 3;");
        CHECK(a.find("ldr x11, [x29, #-16]") != std::string::npos);  // 运行时 len
        CHECK(a.find("cmp x10, x11") != std::string::npos);
        CHECK(a.find("b.hs L.dbounds.fail.") != std::string::npos);
        CHECK(a.find("bl _tenet_bounds_fail") != std::string::npos);
        CHECK(a.find("ldr x14, [x29, #-8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x14, x10, lsl #3]") != std::string::npos);
        CHECK(a.find("str x9, [x14, x10, lsl #3]") != std::string::npos);
    }
    // 动态数组的常量下标也不做编译期越界报错（长度只有运行时知道）
    {
        bool threw = false;
        try {
            asm_of("let a: array<int> = [1];\nprint(a[2]);");
        } catch (const TenetError&) {
            threw = true;
        }
        CHECK(!threw);
        std::string a = asm_of("let a: array<int> = [1];\nprint(a[2]);");
        CHECK(a.find("bl _tenet_bounds_fail") != std::string::npos);
    }

    // 深拷贝：let b = a / let b: array<T> = a（各自独立堆缓冲）
    {
        std::string a = asm_of(
            "let a: array<int> = [1, 2];\n"
            "let b = a;\n"
            "push(b, 3);\n"
            "print(b[0], len(b));");
        CHECK(a.find("sub sp, sp, #48") != std::string::npos);  // a/b 各 3 个描述符槽
        CHECK(a.find("str x0, [x29, #-32]") != std::string::npos);  // b.data
        CHECK(a.find("dyn.copy") != std::string::npos);
        CHECK(a.find("ldr x11, [x14, x13, lsl #3]") != std::string::npos);
        CHECK(a.find("str x11, [x15, x13, lsl #3]") != std::string::npos);
        CHECK(count_substr(code_only(a), "bl _malloc") >= 2);  // a 与 b 各一块
    }
    // 整体赋值 b = a：先构造临时，再 drop 旧 b，最后搬描述符（深拷贝）
    {
        std::string a = asm_of(
            "let a: array<int> = [1, 2];\n"
            "let b: array<int> = [3];\n"
            "b = a;\n"
            "print(b[0]);");
        CHECK(a.find("sub sp, sp, #80") != std::string::npos);  // 6 槽 + 赋值临时 3 槽
        CHECK(a.find("str x0, [x29, #-56]") != std::string::npos);  // 临时 data
        CHECK(a.find("ldr x0, [x29, #-32]") != std::string::npos);  // drop 旧 b
        CHECK(a.find("bl _free") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-56]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-32]") != std::string::npos);  // 临时 → b.data
        CHECK(count_substr(code_only(a), "bl _malloc") >= 3);  // a / b / 赋值临时
    }
    // b = b 无操作
    {
        std::string a = asm_of("let b: array<int> = [1];\nb = b;\nprint(len(b));");
        CHECK(count_substr(code_only(a), "bl _malloc") == 1);
        CHECK(a.find("dyn.copy") == std::string::npos);
    }
    // 整体赋值为字面量：drop 旧值后换成新缓冲
    {
        std::string a = asm_of("let a: array<int> = [1];\na = [2, 3, 4];\nprint(len(a));");
        CHECK(count_substr(code_only(a), "bl _malloc") == 2);
        CHECK(a.find("dyn.copy") == std::string::npos);  // 字面量直接分配，无需拷贝
        CHECK(a.find("mov x0, #32") != std::string::npos);  // 新 cap = max(3,4) = 4
    }

    // 作用域 drop：while 每轮结束 / if 分支结束 / 函数自然落回
    {
        std::string a = asm_of(
            "let i: int = 0;\n"
            "while (i < 3) {\n"
            "  let a: array<int> = [1, 2];\n"
            "  push(a, 3);\n"
            "  print(len(a));\n"
            "  i = i + 1;\n"
            "}\n"
            "print(i);");
        CHECK(count_substr(a, "bl _free") >= 2);  // 每轮 drop + main 结束 drop
    }
    {
        std::string a = asm_of(
            "let n: int = 1;\n"
            "if (n > 0) { let a: array<int> = [1]; print(len(a)); }\n"
            "else { let b: array<int> = [2]; print(len(b)); }");
        CHECK(count_substr(a, "bl _free") == 2);  // then / else 各 drop 一次
    }
    {
        std::string a = asm_of(
            "fn f() {\n"
            "  let a: array<int> = [1];\n"
            "  print(len(a));\n"
            "}\n"
            "f();");
        size_t free = a.find("bl _free");
        size_t ret = a.find("L.f.ret");
        CHECK(free != std::string::npos && ret != std::string::npos && free < ret);
    }

    // return 前 drop（含嵌套作用域）
    {
        std::string a = asm_of(
            "fn f() -> int {\n"
            "  let a: array<int> = [1, 2];\n"
            "  push(a, 3);\n"
            "  return len(a);\n"
            "}\n"
            "print(f());");
        size_t free = a.find("bl _free");
        size_t ret = a.find("b L.f.ret");
        CHECK(free != std::string::npos && ret != std::string::npos && free < ret);
    }
    {
        std::string a = asm_of(
            "fn f(c: int) -> int {\n"
            "  let a: array<int> = [1];\n"
            "  if (c > 0) { let b: array<int> = [2]; return len(a) + len(b); }\n"
            "  return len(a);\n"
            "}\n"
            "print(f(1));");
        CHECK(count_substr(a, "bl _free") >= 4);  // 两个 return 分别 drop 2/1 个 + 死代码
    }

    // break 退出循环前 drop 循环体作用域
    {
        std::string a = asm_of(
            "let i: int = 0;\n"
            "while (i < 3) {\n"
            "  let a: array<int> = [1];\n"
            "  i = i + 1;\n"
            "  if (i == 2) { break; }\n"
            "}\n"
            "print(i);");
        size_t free = a.find("bl _free");
        size_t br = a.find("b L.exit.");
        CHECK(free != std::string::npos && br != std::string::npos && free < br);
    }

    // float / bool 元素：仍按 8 字节槽存堆上（float 用位模式）
    {
        std::string a = asm_of(
            "let f: array<float> = [1.5, 2.5];\n"
            "push(f, 3.5);\n"
            "f[0] = 9.5;\n"
            "let b: array<bool> = [true];\n"
            "push(b, false);\n"
            "print(f[0], b[0], len(b));");
        CHECK(a.find("fmov x9, d9") != std::string::npos);   // float 字面量按位存堆
        CHECK(a.find("fmov x11, d9") != std::string::npos);  // push float
        CHECK(a.find("str x9, [x14, #0]") != std::string::npos);
        CHECK(a.find("ldr d9, [x14, x10, lsl #3]") != std::string::npos);
        CHECK(a.find("str d9, [x14, x10, lsl #3]") != std::string::npos);
        CHECK(a.find("str x11, [x14, x9, lsl #3]") != std::string::npos);  // bool push
    }

    // push 限制：仅动态数组变量、参数个数/类型
    CHECK_THROWS(asm_of("let a = [1];\npush(a, 2);"), "不能 push");
    CHECK_THROWS(asm_of("let a: array<int> = [1];\npush(a);"), "需要两个参数");
    CHECK_THROWS(asm_of("let a: array<int> = [1];\npush([2], 3);"),
                 "第一个参数必须是动态数组变量");
    CHECK_THROWS(asm_of("let a: array<int> = [1];\npush(a, 1.5);"),
                 "push 值类型不匹配：需要 int，实际 float");
    CHECK_THROWS(asm_of("let x: int = 1;\npush(x, 2);"), "不是数组，不能 push");
    CHECK_THROWS(asm_of("let a: array<int> = [1];\npush(a, true);"),
                 "push 值类型不匹配：需要 int，实际 bool");

    // 动态数组与定长数组不能隐式互转
    CHECK_THROWS(asm_of("let a = [1];\nlet b: array<int> = a;"),
                 "动态数组初始化需要同类型 `array<T>` 变量");
    CHECK_THROWS(asm_of("let a: array<int> = [1];\nlet f = [1.5];\na = f;"),
                 "动态数组初始化需要同类型 `array<T>` 变量");
    CHECK_THROWS(asm_of("let a: array<int> = [1];\nlet f: array<float> = [1.5];\na = f;"),
                 "动态数组类型不匹配：需要 array<int>");
    CHECK_THROWS(asm_of("let a: array<int> = [1];\nlet b = [2, 3];\nb = a;"),
                 "不能整体赋值为动态数组");
    CHECK_THROWS(asm_of("let a: array<int> = [1, 2];\nlet b: array<int, 2> = a;"),
                 "不能用动态数组");

    // 元素类型 / 下标类型 / 直接取值
    CHECK_THROWS(asm_of("let a: array<string> = [];"), "v1 数组元素只支持 int/float/bool");
    {
        // S3c-3e：动态嵌套空外层合法：cap=4 → malloc(4*24)。
        std::string a = asm_of("let a: array<array<int>> = [];\nprint(len(a));");
        CHECK(a.find("mov x0, #96") != std::string::npos);
        CHECK(a.find("bl _malloc") != std::string::npos);
    }
    CHECK_THROWS(asm_of("let a: array<int> = [1, 2.0];"),
                 "数组元素 1 类型不匹配：需要 int，实际 float");
    CHECK_THROWS(asm_of("let a: array<int> = [1];\nprint(a[true]);"),
                 "数组下标必须是 int，实际为 bool");
    {
        std::string a = asm_of("let a: array<int> = [1];\nprint(a);");
        CHECK(a.find("L.print.cond.") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, x9, lsl #3]") != std::string::npos);
    }
    CHECK_THROWS(asm_of("let a: array<int> = [1];\nlet x: int = a;"),
                 "数组变量 `a` 不能直接取值");
    CHECK_THROWS(asm_of("let a: array<int> = [1];\nlet b: array<int> = a[0];"),
                 "`array<T>` 初始化必须是");

    // 调用初始化只支持返回同类型动态数组的调用（S3c-2 v1）
    CHECK_THROWS(asm_of("fn make() -> array<int, 2> { return [1, 2]; }\n"
                        "let a: array<int> = make();"),
                 "不能用返回 array<int,2> 的调用初始化");
    // 签名里的 array<T> 已允许，但元素仍限标量
    CHECK_THROWS(asm_of("fn f(a: array<string>) -> int { return 0; }"),
                 "v1 数组元素只支持 int/float/bool");
    CHECK_THROWS(asm_of("fn f() -> array<array<int>> { return [1]; }"),
                 "嵌套数组第 0 个元素必须是内层数组字面量");
    CHECK_THROWS(asm_of("struct S { a: array<array<int>>; }"), "不支持 array");

    // 错误定位：push 值类型错误指向第二个实参
    {
        bool threw = false;
        try {
            asm_of("let a: array<int> = [1];\npush(a, 1.5);");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 2);
            CHECK(e.str().find("[2:") != std::string::npos);
        }
        CHECK(threw);
    }
}

// ---- S3c-2：动态数组 array<T> 参数/返回值（descriptor 指针 + sret 转移）----

static void test_dynamic_abi() {
    // 语法：array<T>（无长度）出现在函数签名里
    {
        auto prog = Parser::parse(
            "fn clone(a: array<int>) -> array<int> { return a; }");
        CHECK(prog.stmts[0]->kind == Stmt::Kind::FnDecl);
        CHECK(prog.stmts[0]->params.size() == 1);
        CHECK(prog.stmts[0]->params[0].second == "array<int>");
        CHECK(prog.stmts[0]->ret.has_value() && *prog.stmts[0]->ret == "array<int>");
    }

    // 参数 ABI：调用方传 3 槽描述符指针；被调函数入口 malloc + 深拷贝
    {
        std::string a = asm_of(
            "fn sum(a: array<int>) -> int {\n"
            "  let s: int = 0;\n"
            "  let i: int = 0;\n"
            "  while (i < len(a)) { s = s + a[i]; i = i + 1; }\n"
            "  return s;\n"
            "}\n"
            "let x: array<int> = [1, 2];\n"
            "print(sum(x));");
        CHECK(a.find("_sum:") != std::string::npos);
        CHECK(a.find("ldr x11, [x10, #0]") != std::string::npos);   // 描述符 data
        CHECK(a.find("ldr x12, [x10, #8]") != std::string::npos);   // 描述符 len
        CHECK(a.find("ldr x13, [x10, #16]") != std::string::npos);  // 描述符 cap
        CHECK(a.find("lsl x0, x13, #3") != std::string::npos);      // cap*8 → malloc
        CHECK(a.find("dyn.param.copy") != std::string::npos);       // 深拷贝循环
        CHECK(count_substr(code_only(a), "bl _malloc") >= 2);       // x 字面量 + 参数副本
        CHECK(count_substr(code_only(a), "bl _free") >= 2);         // 参数副本 + main x
    }

    // 参数值语义：函数内 push/改元素后，调用方数组保留（编译期断言 + 手工运行验证）
    {
        std::string a = asm_of(
            "fn bump(a: array<int>) -> int { push(a, 9); a[0] = 42; return len(a); }\n"
            "let x: array<int> = [1];\n"
            "let n: int = bump(x);\n"
            "print(len(x), n, x[0]);");
        CHECK(a.find("bl _bump") != std::string::npos);
        // bump 内部的 push 作用于本地副本的 data/len/cap 槽
        CHECK(a.find("dyn.grow.after") != std::string::npos);
        // 调用方 x 的 drop 仍有且只在 main 尾部
        size_t free_x = a.rfind("bl _free");
        size_t ret_main = a.find("L.main.ret");
        CHECK(free_x != std::string::npos && ret_main != std::string::npos && free_x < ret_main);
    }

    // 多参数：动态数组参数与 int/float 参数混排；入口先全部落槽再深拷贝
    {
        std::string a = asm_of(
            "fn f(x: int, a: array<int>, y: float, b: array<int>) -> int {\n"
            "  return x + len(a) + len(b);\n"
            "}\n"
            "let a: array<int> = [1];\n"
            "let b: array<int> = [2, 3];\n"
            "print(f(1, a, 2.5, b));");
        CHECK(count_substr(code_only(a), "dyn.param.copy") >= 2);
        CHECK(count_substr(code_only(a), "bl _malloc") >= 4);  // a/b 字面量 + 两份参数副本
    }

    // 返回值 ABI：隐藏 sret 指针（x0）指向 3 槽描述符；return 变量转移 data/len/cap
    {
        std::string a = asm_of(
            "fn clone(a: array<int>) -> array<int> { return a; }\n"
            "let a: array<int> = [1];\n"
            "let b: array<int> = clone(a);\n"
            "print(len(b));");
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);   // 保存 sret
        CHECK(a.find("str x9, [x15, #0]") != std::string::npos);    // data → sret
        CHECK(a.find("str x9, [x15, #8]") != std::string::npos);    // len  → sret
        CHECK(a.find("str x9, [x15, #16]") != std::string::npos);   // cap  → sret
        // 转移后清空本地描述符：函数退出 drop 只 free(NULL)，不会 double free
        CHECK(a.find("str xzr, [x29, #-16]") != std::string::npos);
        CHECK(a.find("str xzr, [x29, #-24]") != std::string::npos);
        CHECK(a.find("str xzr, [x29, #-32]") != std::string::npos);
        // 调用方接管描述符：读回 data/len/cap 并清零临时描述符
        CHECK(a.find("ldr x14, [x10, #0]") != std::string::npos);
        CHECK(a.find("ldr x14, [x10, #8]") != std::string::npos);
        CHECK(a.find("ldr x14, [x10, #16]") != std::string::npos);
        CHECK(a.find("str xzr, [x10, #8]") != std::string::npos);
    }

    // 返回局部变量：先写 sret，再 drop 其他局部，最后跳 epilogue
    {
        std::string a = asm_of(
            "fn make() -> array<int> {\n"
            "  let a: array<int> = [1];\n"
            "  let junk: array<int> = [9];\n"
            "  return a;\n"
            "}\n"
            "let b: array<int> = make();\n"
            "print(len(b));");
        size_t sret_store = a.find("str x9, [x15, #0]");
        size_t free_other = a.find("bl _free");
        size_t ret = a.find("b L.make.ret");
        CHECK(sret_store != std::string::npos);
        CHECK(free_other != std::string::npos);
        CHECK(ret != std::string::npos);
        CHECK(sret_store < free_other && free_other < ret);
    }

    // let 接管：隐式推断 / 显式标注都从调用结果接管；assign 也支持
    {
        std::string a = asm_of(
            "fn make() -> array<int> { let a: array<int> = [1, 2]; push(a, 3); return a; }\n"
            "let x = make();\n"
            "let y: array<int> = make();\n"
            "x = make();\n"
            "print(len(x), len(y), y[2]);");
        CHECK(count_substr(code_only(a), "\tbl _make") == 3);
        CHECK(count_substr(code_only(a), "dyn.param.copy") == 0);
        CHECK(a.find("bl _free") != std::string::npos);  // 赋值前 drop 旧 x
    }

    // float / bool 元素同样走 descriptor/sret，按 8 字节位模式深拷贝
    {
        std::string a = asm_of(
            "fn idf(a: array<float>) -> array<float> { return a; }\n"
            "fn idb(a: array<bool>) -> array<bool> { return a; }\n"
            "let f: array<float> = [1.5];\n"
            "let g: array<float> = idf(f);\n"
            "push(g, 2.5);\n"
            "let b: array<bool> = [true];\n"
            "let c: array<bool> = idb(b);\n"
            "print(g[1], c[0]);");
        CHECK(count_substr(code_only(a), "cmp x16, x17") == 2);  // idf/idb 各一次深拷贝
        CHECK(a.find("ldr x9, [x15, x16, lsl #3]") != std::string::npos);
        CHECK(a.find("str x9, [x14, x16, lsl #3]") != std::string::npos);
        CHECK(a.find("bl _idf") != std::string::npos);
        CHECK(a.find("bl _idb") != std::string::npos);
    }

    // S3c-3a：动态数组 return 支持字面量/返回动态数组的调用（详见 test_dynamic_expr_s3c3a）
    {
        std::string a = asm_of("fn f() -> array<int> { return [1, 2]; }");
        CHECK(a.find("bl _malloc") != std::string::npos);
        CHECK(a.find("str x9, [x15, #0]") != std::string::npos);
    }
    {
        std::string a = asm_of(
            "fn g() -> array<int> { let a: array<int> = [1]; return a; }\n"
            "fn f() -> array<int> { return g(); }");
        CHECK(a.find("bl _g") != std::string::npos);
        CHECK(a.find("str xzr, [x10, #0]") != std::string::npos);  // 内层临时描述符清零
    }
    // S3c-3a：动态数组实参支持字面量/返回动态数组的调用（保留变量语义）
    {
        std::string a = asm_of(
            "fn sum(a: array<int>) -> int { return len(a); }\n"
            "print(sum([1, 2]));");
        CHECK(a.find("bl _sum") != std::string::npos);
        CHECK(a.find("bl _free") != std::string::npos);  // 调用返回后 free 临时堆缓冲
    }
    {
        std::string a = asm_of(
            "fn make() -> array<int> { let a: array<int> = [1]; return a; }\n"
            "fn sum(a: array<int>) -> int { return len(a); }\n"
            "print(sum(make()));");
        CHECK(a.find("bl _make") != std::string::npos);
        CHECK(a.find("bl _sum") != std::string::npos);
    }

    // 类型一致性：实参必须同类型；return 值也必须同类型
    CHECK_THROWS(asm_of(
                     "fn sum(a: array<int>) -> int { return len(a); }\n"
                     "let b = [1, 2];\nprint(sum(b));"),
                 "参数类型不匹配：需要 array<int>，实际 array<int,2>");
    CHECK_THROWS(asm_of("fn f(a: array<int>) -> array<float> { return a; }"),
                 "返回类型不匹配");
    CHECK_THROWS(asm_of(
                     "fn f(a: array<int>) -> array<int> {\n"
                     "  let b: array<float> = [1.5];\n"
                     "  return b;\n"
                     "}"),
                 "返回类型不匹配");
    // 定长数组变量不能当动态数组返回
    CHECK_THROWS(asm_of(
                     "fn f() -> array<int> {\n"
                     "  let b: array<int, 2> = [1, 2];\n"
                     "  return b;\n"
                     "}"),
                 "返回类型不匹配");

    // 动态/定长数组不能隐式互转（调用结果 / 形参）
    CHECK_THROWS(asm_of("fn make() -> array<int, 2> { return [1, 2]; }\n"
                        "let a: array<int> = make();"),
                 "不能用返回 array<int,2> 的调用初始化");
    CHECK_THROWS(asm_of(
                     "fn sum(a: array<int>) -> int { return 0; }\n"
                     "fn make() -> array<int, 2> { return [1, 2]; }\n"
                     "print(sum(make()));"),
                 "参数类型不匹配：需要 array<int>，调用返回 array<int,2>");

    // 参数位：sret 与动态数组/struct 指针同样占位（x0-x7）
    CHECK_THROWS(asm_of(
                     "fn f(a: array<int>, b: int, c: int, d: int, e: int, g: int, h: int, i: int)\n"
                     "    -> array<int> {\n"
                     "  let z: array<int> = [1];\n"
                     "  return z;\n"
                     "}"),
                 "参数位超过 8");

    // 错误定位：不支持的 return 表达式 / 不支持的动态实参表达式
    {
        bool threw = false;
        try {
            asm_of("fn f() -> array<int> {\n  return 1;\n}");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 2);
            CHECK(e.str().find("[2:") != std::string::npos);
        }
        CHECK(threw);
    }
    {
        bool threw = false;
        try {
            asm_of("fn sum(a: array<int>) -> int { return 0; }\nprint(sum(1));");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 2);
            CHECK(e.str().find("[2:") != std::string::npos);
        }
        CHECK(threw);
    }

    // 回归：以 return 结束的函数之后，后续函数的循环体不能被 terminated_ 截断
    {
        std::string a = asm_of(
            "fn first() -> int { return 1; }\n"
            "fn second(a: array<int>) -> int {\n"
            "  let s: int = 0;\n"
            "  let i: int = 0;\n"
            "  while (i < len(a)) {\n"
            "    s = s + a[i];\n"
            "    i = i + 1;\n"
            "  }\n"
            "  return s;\n"
            "}\n"
            "let x: array<int> = [1, 2];\n"
            "print(second(x));");
        // 循环标签 + 回跳分支都在（被截断时只剩标签，回跳缺失）
        CHECK(count_substr(a, "L.cond.") == 2);
    }
}

// ---- S3c-3a：动态字面量/调用结果作实参，return 字面量/调用 ----

static void test_dynamic_expr_s3c3a() {
    // 字面量实参：调用方构造临时动态数组并传描述符指针；调用返回后只 free 临时堆缓冲
    {
        std::string a = asm_of(
            "fn sum(a: array<int>) -> int { return len(a); }\n"
            "print(sum([1, 2]));");
        CHECK(a.find("bl _sum") != std::string::npos);
        size_t call = a.find("bl _sum");
        size_t free_after = a.find("bl _free", call);
        CHECK(call != std::string::npos && free_after != std::string::npos);
        // 临时字面量 + 被调函数入口深拷贝各一次 malloc；free 临时缓冲 + 入参副本
        CHECK(count_substr(code_only(a), "bl _malloc") == 2);
        CHECK(count_substr(code_only(a), "bl _free") == 2);
        // 清空临时描述符：free 后紧跟 mov/str 清零，重复 drop 只会 free(NULL)
        size_t clear = a.find("mov x9, #0", free_after);
        CHECK(clear != std::string::npos);
        CHECK(a.find("str x9, [x29, #-24]", free_after) != std::string::npos);
    }

    // 调用实参：内层调用结果搬进临时描述符后清空内层描述符，外层返回后 free 临时
    {
        std::string a = asm_of(
            "fn make() -> array<int> { let a: array<int> = [1]; return a; }\n"
            "fn sum(a: array<int>) -> int { return len(a); }\n"
            "print(sum(make()));");
        CHECK(a.find("bl _make") != std::string::npos);
        CHECK(a.find("bl _sum") != std::string::npos);
        // 内层 sret 描述符复制到临时描述符后清零：不会再被任何 drop 重复 free
        CHECK(a.find("str xzr, [x10, #0]") != std::string::npos);
        CHECK(a.find("str xzr, [x10, #8]") != std::string::npos);
        CHECK(a.find("str xzr, [x10, #16]") != std::string::npos);
        size_t call = a.find("bl _sum");
        CHECK(call != std::string::npos && a.find("bl _free", call) != std::string::npos);
    }

    // return 字面量：构造临时动态数组 → data/len/cap 转移进 sret，不 free（所有权给调用方）
    {
        std::string a = asm_of(
            "fn lit() -> array<int> { return [3, 4]; }\n"
            "let c: array<int> = lit();\n"
            "print(len(c), c[1]);");
        size_t start = a.find("_lit:");
        size_t ret = a.find("L.lit.ret:");
        CHECK(start != std::string::npos && ret != std::string::npos && start < ret);
        std::string lit = a.substr(start, ret - start);
        CHECK(count_substr(lit, "bl _malloc") == 1);  // 字面量缓冲
        CHECK(count_substr(lit, "bl _free") == 0);    // 转移所有权，不 free
        CHECK(lit.find("str x9, [x15, #0]") != std::string::npos);   // data → sret
        CHECK(lit.find("str x9, [x15, #8]") != std::string::npos);   // len  → sret
        CHECK(lit.find("str x9, [x15, #16]") != std::string::npos);  // cap  → sret
        // 转移后清空临时描述符三槽：退出路径不会 double free
        CHECK(count_substr(lit, "str xzr, [x29, #") == 3);
    }

    // return 调用：内层 sret 描述符搬进本函数 sret，清空内层；本函数不 malloc/free
    {
        std::string a = asm_of(
            "fn make() -> array<int> { return [3, 4]; }\n"
            "fn chain() -> array<int> { return make(); }\n"
            "let d: array<int> = chain();\n"
            "print(len(d), d[0]);");
        size_t start = a.find("_chain:");
        size_t end = a.find("L.chain.ret:", start);
        CHECK(start != std::string::npos && end != std::string::npos && start < end);
        std::string chain = a.substr(start, end - start);
        CHECK(chain.find("bl _make") != std::string::npos);
        CHECK(count_substr(chain, "bl _malloc") == 0);
        CHECK(count_substr(chain, "bl _free") == 0);
        CHECK(chain.find("str xzr, [x10, #0]") != std::string::npos);
        CHECK(chain.find("str xzr, [x10, #8]") != std::string::npos);
        CHECK(chain.find("str xzr, [x10, #16]") != std::string::npos);
    }

    // 链式调用 id(id([1, 2]))：两层临时描述符各自清理，无 double-free
    {
        std::string a = asm_of(
            "fn id(a: array<int>) -> array<int> { return a; }\n"
            "let a: array<int> = id(id([1, 2]));\n"
            "print(len(a), a[1]);");
        CHECK(count_substr(code_only(a), "\tbl _id") == 2);
        CHECK(count_substr(code_only(a), "bl _malloc") == 2);  // main 字面量 + id 入参深拷贝
        // id 入参副本 drop + 两层临时缓冲 free + main 接管后的 drop
        CHECK(count_substr(code_only(a), "bl _free") == 4);
        CHECK(a.find("str xzr, [x10, #0]") != std::string::npos);
        CHECK(a.find("str xzr, [x10, #8]") != std::string::npos);
        CHECK(a.find("str xzr, [x10, #16]") != std::string::npos);
    }

    // float / bool 元素：字面量实参与字面量 return 同样按 8 字节位模式走 descriptor/sret
    {
        std::string a = asm_of(
            "fn idf(a: array<float>) -> array<float> { return a; }\n"
            "fn idb(a: array<bool>) -> array<bool> { return a; }\n"
            "fn retf() -> array<float> { return [1.5, 2.5]; }\n"
            "let f: array<float> = idf([3.5]);\n"
            "let g: array<float> = retf();\n"
            "let b: array<bool> = idb([true]);\n"
            "print(f[0], g[1], b[0]);");
        CHECK(a.find("bl _idf") != std::string::npos);
        CHECK(a.find("bl _idb") != std::string::npos);
        CHECK(a.find("bl _retf") != std::string::npos);
        CHECK(count_substr(code_only(a), "fmov x9, d9") >= 3);  // 三个 float 字面量元素打包
        CHECK(count_substr(code_only(a), "bl _malloc") == 5);
        CHECK(count_substr(code_only(a), "bl _free") == 7);
    }

    // 变量实参保持原语义：调用点不复制、不 drop，只有被调函数入口深拷贝
    {
        std::string a = asm_of(
            "fn sum(a: array<int>) -> int { return len(a); }\n"
            "let x: array<int> = [1, 2];\n"
            "print(sum(x));");
        CHECK(count_substr(code_only(a), "bl _malloc") == 2);  // x 字面量 + 入参副本
        CHECK(count_substr(code_only(a), "bl _free") == 2);    // 入参副本 + main x
    }

    // 错误只对不支持的表达式（数字 / struct 等）报错
    CHECK_THROWS(asm_of("fn f() -> array<int> { return 1; }"),
                 "动态数组 return 只支持变量、字面量或返回动态数组的调用");
    CHECK_THROWS(asm_of(
                     "fn sum(a: array<int>) -> int { return 0; }\n"
                     "print(sum(1));"),
                 "动态数组实参只支持变量、字面量或返回动态数组的调用");
    CHECK_THROWS(asm_of(
                     "struct P { x: int; }\n"
                     "fn sum(a: array<int>) -> int { return 0; }\n"
                     "let p = P { x: 1 };\n"
                     "print(sum(p));"),
                 "参数类型不匹配：需要 array<int>，实际 P");
    CHECK_THROWS(asm_of("fn f() -> array<int> { return [1.5]; }"),
                 "数组元素 0 类型不匹配：需要 int，实际 float");
    CHECK_THROWS(asm_of(
                     "fn sum(a: array<int>) -> int { return 0; }\n"
                     "print(sum([1.5]));"),
                 "数组元素 0 类型不匹配：需要 int，实际 float");
}

// ---- S3c-3b-1：固定长度 array<struct, N> 局部数组 ----

static void test_array_struct_s3c3b1() {
    // 语法：array<struct, N> 类型、struct 字面量数组、字段链与元素整体赋值
    {
        auto prog = Parser::parse(
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "a[0].x = 9;\n"
            "a[1] = P { x: 7, y: 8 };");
        CHECK(prog.stmts.size() == 4);
        CHECK(prog.stmts[1]->kind == Stmt::Kind::Let);
        CHECK(prog.stmts[1]->ty.has_value() && *prog.stmts[1]->ty == "array<P,2>");
        CHECK(prog.stmts[1]->value->kind == Expr::Kind::Array);
        CHECK(prog.stmts[1]->value->args.size() == 2);
        CHECK(prog.stmts[1]->value->args[0]->kind == Expr::Kind::StructLit);
        auto* fassign = prog.stmts[2]->expr.get();
        CHECK(fassign->kind == Expr::Kind::Assign);
        CHECK(fassign->lhs->kind == Expr::Kind::Field && fassign->lhs->name == "x");
        CHECK(fassign->lhs->lhs->kind == Expr::Kind::Index);
        CHECK(fassign->lhs->lhs->lhs->kind == Expr::Kind::Var &&
              fassign->lhs->lhs->lhs->name == "a");
        CHECK(fassign->lhs->lhs->rhs->kind == Expr::Kind::Int &&
              fassign->lhs->lhs->rhs->int_val == 0);
        auto* eassign = prog.stmts[3]->expr.get();
        CHECK(eassign->kind == Expr::Kind::Assign);
        CHECK(eassign->lhs->kind == Expr::Kind::Index);
        CHECK(eassign->lhs->rhs->kind == Expr::Kind::Int &&
              eassign->lhs->rhs->int_val == 1);
        CHECK(eassign->value->kind == Expr::Kind::StructLit);
    }

    // 字面量初始化：元素按扁平字段连续存放（P 2 字段 × 2 元素 = 4 槽），
    // a[0].x/-32、a[0].y/-24、a[1].x/-16、a[1].y/-8；常量字段读直接 ldr。
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "print(a[0].x, a[0].y, a[1].x, a[1].y, len(a));");
        CHECK(a.find("sub sp, sp, #48") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-32]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-32]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-24]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("mov x9, #2") != std::string::npos);  // len 是编译期常量
        CHECK(a.find("_len") == std::string::npos);
    }

    // 省略标注：由 struct 字面量推断为固定 array<P, N>
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "print(a[1].y, len(a));");
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("mov x9, #2") != std::string::npos);
    }

    // 常量下标字段写：a[0].y = 9 直接写扁平槽 -24
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "a[0].y = 9;\n"
            "print(a[0].y);");
        size_t mov = a.find("mov x9, #9");
        CHECK(mov != std::string::npos);
        CHECK(a.find("str x9, [x29, #-24]", mov) != std::string::npos);
    }

    // 动态下标字段读写：先无符号边界检查，再按 idx*slots + field 计算槽；
    // P 两字段 → slots=2，用 lsl；读/写都用 [x14, x17, lsl #3]。
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "let i: int = 1;\n"
            "print(a[i].y);\n"
            "a[i].x = 5;");
        CHECK(a.find("sub sp, sp, #64") != std::string::npos);
        CHECK(a.find("cmp x10, #2") != std::string::npos);
        CHECK(a.find("b.hs L.bounds.fail.") != std::string::npos);
        CHECK(a.find("bl _tenet_bounds_fail") != std::string::npos);
        CHECK(a.find("sub x14, x29, #32") != std::string::npos);
        CHECK(a.find("lsl x17, x10, #1") != std::string::npos);
        CHECK(a.find("add x17, x17, #1") != std::string::npos);  // y 是字段 1
        CHECK(a.find("ldr x9, [x14, x17, lsl #3]") != std::string::npos);
        CHECK(a.find("str x9, [x14, x17, lsl #3]") != std::string::npos);
    }

    // 嵌套 struct 路径 q[i].p.y：Q 扁平为 p.x/p.y/z 三槽，元素 stride=3*8；
    // slots=3 非 2 的幂，用 mov x15,#3 + mul 计算。
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "struct Q { p: P; z: int; }\n"
            "let q: array<Q, 2> = [Q { p: P { x: 1, y: 2 }, z: 3 }, "
            "Q { p: P { x: 4, y: 5 }, z: 6 }];\n"
            "q[0].p.x = 9;\n"
            "let j: int = 1;\n"
            "print(q[j].p.y, q[0].z);");
        CHECK(a.find("sub sp, sp, #80") != std::string::npos);
        size_t mov = a.find("mov x9, #9");
        CHECK(mov != std::string::npos);
        CHECK(a.find("str x9, [x29, #-48]", mov) != std::string::npos);  // q[0].p.x
        CHECK(a.find("ldr x9, [x29, #-32]") != std::string::npos);      // q[0].z
        CHECK(a.find("sub x14, x29, #48") != std::string::npos);
        CHECK(a.find("mov x15, #3") != std::string::npos);
        CHECK(a.find("mul x17, x10, x15") != std::string::npos);
        CHECK(a.find("add x17, x17, #1") != std::string::npos);  // p.y
        CHECK(a.find("ldr x9, [x14, x17, lsl #3]") != std::string::npos);
    }

    // 元素整体赋值：a[1] = P { ... }（常量下标）与 a[i] = p（动态下标）
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "let p = P { x: 5, y: 6 };\n"
            "let i: int = 0;\n"
            "a[i] = p;\n"
            "a[1] = P { x: 7, y: 8 };");
        CHECK(a.find("sub sp, sp, #112") != std::string::npos);
        CHECK(a.find("sub x14, x29, #32") != std::string::npos);
        CHECK(a.find("lsl x17, x10, #1") != std::string::npos);
        CHECK(a.find("add x14, x14, x17, lsl #3") != std::string::npos);
        CHECK(a.find("str x9, [x14, #0]") != std::string::npos);  // 元素字段 0
        CHECK(a.find("str x9, [x14, #8]") != std::string::npos);  // 元素字段 1
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);  // a[1].x
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);   // a[1].y
    }

    // 深拷贝 let b = a：逐槽 ldr/str（a 占 -32..-8，b 占 -64..-40），互不影响
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "let b = a;\n"
            "b[0].y = 9;\n"
            "print(a[0].y, b[0].y, len(b));");
        CHECK(a.find("sub sp, sp, #80") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-32]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-64]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-40]") != std::string::npos);
        size_t mov = a.find("mov x9, #9");
        CHECK(mov != std::string::npos);
        CHECK(a.find("str x9, [x29, #-56]", mov) != std::string::npos);  // b[0].y
        CHECK(a.find("ldr x9, [x29, #-24]") != std::string::npos);       // a[0].y
        CHECK(a.find("mov x9, #2") != std::string::npos);
    }

    // 整体数组赋值 b = a 同样是逐槽值拷贝
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "let b: array<P, 2> = [P { x: 0, y: 0 }, P { x: 0, y: 0 }];\n"
            "b = a;\n"
            "print(b[0].x, b[1].y);");
        CHECK(a.find("ldr x9, [x29, #-32]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-64]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-40]") != std::string::npos);
    }

    // float/bool 字段仍占 8 字节槽；float 读用 d9，动态下标同样 lsl 后 ldr d9
    {
        std::string a = asm_of(
            "struct F { a: float; b: bool; }\n"
            "let f: array<F, 1> = [F { a: 1.5, b: true }];\n"
            "let i: int = 0;\n"
            "print(f[0].a, f[0].b, f[i].a);");
        CHECK(a.find("sub sp, sp, #48") != std::string::npos);
        CHECK(a.find("fmov x9, d9") != std::string::npos);  // 字面量按位模式打包
        CHECK(a.find("ldr d9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("lsl x17, x10, #1") != std::string::npos);
        CHECK(a.find("ldr d9, [x14, x17, lsl #3]") != std::string::npos);
    }

    // 函数内局部 struct 数组：帧规划按 len*slots 占槽
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn first(a: int) -> int {\n"
            "  let p: array<P, 2> = [P { x: a, y: a + 1 }, P { x: a + 2, y: a + 3 }];\n"
            "  p[1].x = p[0].x + 10;\n"
            "  return p[1].x;\n"
            "}\n"
            "print(first(1));");
        CHECK(a.find("_first:") != std::string::npos);
        CHECK(a.find("bl _first") != std::string::npos);
        CHECK(a.find("sub sp, sp, #64") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);  // p[1].x
        CHECK(a.find("ldr x9, [x29, #-40]") != std::string::npos);  // p[0].x
    }

    // 常量越界：读 / 写都编译期报错；错误定位指向下标
    {
        bool threw = false;
        try {
            asm_of("struct P { x: int; }\n"
                   "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
                   "print(a[2].x);");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.message == "数组下标 2 越界（长度 2）");
            CHECK(e.pos.has_value() && e.pos->line == 3 && e.pos->col == 9);
            CHECK(e.str().find("[3:9]") != std::string::npos);
        }
        CHECK(threw);
    }
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
                        "a[-1].x = 9;"),
                 "数组下标 -1 越界（长度 2）");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P, 1> = [P { x: 1 }];\n"
                        "a[1] = P { x: 2 };"),
                 "数组下标 1 越界（长度 1）");

    // 边界检查是运行时无符号比较（负数/过大都走失败块）
    {
        std::string a = asm_of(
            "struct P { x: int; }\n"
            "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
            "let i: int = 2;\n"
            "print(a[i].x);");
        CHECK(a.find("cmp x10, #2") != std::string::npos);
        CHECK(a.find("b.hs L.bounds.fail.") != std::string::npos);
        CHECK(a.find("bl _tenet_bounds_fail") != std::string::npos);
    }

    // 初始化长度 / 元素类型 / 变量来源类型与长度
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P, 2> = [P { x: 1 }];"),
                 "数组初始化长度不匹配：需要 2，实际 1");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct Q { y: int; }\n"
                        "let a: array<P, 1> = [Q { y: 1 }];"),
                 "数组元素 0 类型不匹配：需要 P，字面量是 Q");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct Q { y: int; }\n"
                        "let a: array<P, 1> = [P { x: 1 }];\n"
                        "let b: array<Q, 1> = a;"),
                 "`b` 需要 array<Q,1>，但 `a` 是 array<P,1>");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P, 1> = [P { x: 1 }];\n"
                        "let b: array<P, 2> = a;"),
                 "数组初始化长度不匹配：需要 2，实际 1");

    // 字段类型 / 未知字段 / 路径只到 struct / 整体读取元素 / 整体 print
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P, 1> = [P { x: 1 }];\n"
                        "a[0].x = 1.5;"),
                 "字段 `x` 类型不匹配：需要 int，实际 float");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P, 1> = [P { x: 1 }];\n"
                        "print(a[0].q);"),
                 "struct `P` 没有字段 `q`");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct Q { p: P; }\n"
                        "let q: array<Q, 1> = [Q { p: P { x: 1 } }];\n"
                        "print(q[0].p);"),
                 "字段 `p` 是 struct，请继续访问到标量字段");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P, 1> = [P { x: 1 }];\n"
                        "print(a[0]);"),
                 "array<struct> 元素不能整体读取为 struct 值");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P, 1> = [P { x: 1 }];\n"
                        "let p: P = a[0];"),
                 "array<struct> 元素不能整体读取为 struct 值");
    {
        std::string a = asm_of("struct P { x: int; }\n"
                               "let a: array<P, 1> = [P { x: 1 }];\n"
                               "print(a);");
        CHECK(a.find(".asciz \"P { \"") != std::string::npos);
    }

    // 下标必须是 int；元素整体赋值类型检查
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P, 1> = [P { x: 1 }];\n"
                        "print(a[true].x);"),
                 "数组下标必须是 int，实际为 bool");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct Q { y: int; }\n"
                        "let a: array<P, 1> = [P { x: 1 }];\n"
                        "a[0] = Q { y: 2 };"),
                 "数组元素赋值类型不匹配：需要 P，字面量是 Q");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct Q { y: int; }\n"
                        "let a: array<P, 1> = [P { x: 1 }];\n"
                        "let q = Q { y: 2 };\n"
                        "a[0] = q;"),
                 "数组元素赋值类型不匹配：需要 P，实际 Q");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P, 1> = [P { x: 1 }];\n"
                        "a[0] = 1;"),
                 "`P` 值必须是字面量");

    // 动态 array<struct> / 参数 / 返回值已支持（详见 test_dynamic_struct_array_s3c3b2）；
    // S3c-3d 起固定 array<struct, N> 参数/返回值也支持（指针 + sret，入口按 N*slots 拷贝）；
    // struct 字段 array、嵌套数组内层 struct 仍拒绝。
    {
        std::string a = asm_of("struct P { x: int; y: int; }\n"
                               "fn f(a: array<P, 2>) -> int { return a[0].x; }");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #24]") != std::string::npos);  // 2 元素 × 2 字段 = 4 槽
    }
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn f() -> array<P, 2> { return [P { x: 1, y: 2 }, P { x: 3, y: 4 }]; }");
        CHECK(a.find("str x9, [x15, #24]") != std::string::npos);  // sret 打包 4 槽
    }
    {
        std::string a = asm_of("struct P { x: int; }\n"
                               "fn f() -> array<P> { return [P { x: 1 }, P { x: 2 }]; }");
        CHECK(a.find("_f:") != std::string::npos);
    }
    // S3d：固定数组字段已支持；这里改为正向断言（动态 array 字段仍拒绝，见下）。
    {
        std::string a = asm_of("struct P { x: int; }\n"
                               "struct S { a: array<P, 2>; }\n"
                               "let s: S = S { a: [P { x: 1 }, P { x: 2 }] };");
        CHECK(a.find("_main:") != std::string::npos);
    }
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<array<P, 1>, 1> = [[P { x: 1 }]];"),
                 "嵌套数组内层只支持 int/float");
}

// ---- S3c-3b-2：动态 array<struct> ----

static void test_dynamic_struct_array_s3c3b2() {
    // 语法：array<S>（不带长度）是动态数组，字面量/字段/整体元素赋值
    {
        auto prog = Parser::parse(
            "struct P { x: int; y: int; }\n"
            "let a: array<P> = [P { x: 1, y: 2 }];\n"
            "push(a, P { x: 3, y: 4 });\n"
            "a[0].x = 9;\n"
            "a[0] = P { x: 7, y: 8 };");
        CHECK(prog.stmts[1]->ty.has_value() && *prog.stmts[1]->ty == "array<P>");
        CHECK(prog.stmts[1]->value->kind == Expr::Kind::Array);
        CHECK(prog.stmts[3]->expr->kind == Expr::Kind::Assign);
        CHECK(prog.stmts[3]->expr->lhs->kind == Expr::Kind::Field);
        CHECK(prog.stmts[4]->expr->lhs->kind == Expr::Kind::Index);
        CHECK(prog.stmts[4]->expr->value->kind == Expr::Kind::StructLit);
    }

    // 字面量初始化：cap = max(n,4) = 4，堆字节 = cap*slots*8 = 64；
    // 描述符 data/len/cap 三槽先清零，元素按 stride=slots*8 铺进堆缓冲
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "print(len(a), a[0].x);");
        CHECK(a.find("str xzr, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str xzr, [x29, #-16]") != std::string::npos);
        CHECK(a.find("str xzr, [x29, #-24]") != std::string::npos);
        CHECK(a.find("mov x0, #64") != std::string::npos);  // 4 * 2槽 * 8
        CHECK(a.find("bl _malloc") != std::string::npos);
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);   // data
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);  // len = 2
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);  // cap = 4
        CHECK(a.find("str x9, [x14, #0]") != std::string::npos);    // P0.x
        CHECK(a.find("str x9, [x14, #8]") != std::string::npos);    // P0.y
        CHECK(a.find("str x9, [x14, #16]") != std::string::npos);   // P1.x
        CHECK(a.find("str x9, [x14, #24]") != std::string::npos);   // P1.y
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos);  // len 运行时读取
    }

    // 空字面量：len=0、cap=4；push 后仍可写
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P> = [];\n"
            "push(a, P { x: 1, y: 2 });");
        CHECK(a.find("mov x0, #64") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);  // len = 0
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);  // cap = 4
    }

    // 动态下标字段读写：len 槽运行时边界检查 + idx*slots*8 寻址
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "let i: int = 1;\n"
            "a[i].y = 5;\n"
            "print(a[i].x);");
        CHECK(a.find("ldr x11, [x29, #-16]") != std::string::npos);  // 运行时 len
        CHECK(a.find("cmp x10, x11") != std::string::npos);
        CHECK(a.find("b.hs L.dbounds.fail.") != std::string::npos);
        CHECK(a.find("bl _tenet_bounds_fail") != std::string::npos);
        CHECK(a.find("lsl x17, x10, #1") != std::string::npos);  // slots=2 用 lsl
        CHECK(a.find("add x17, x17, #1") != std::string::npos);  // y 是字段 1
        CHECK(a.find("str x9, [x14, x17, lsl #3]") != std::string::npos);
        CHECK(a.find("ldr x9, [x14, x17, lsl #3]") != std::string::npos);
    }

    // 常量下标也保留运行时边界检查（动态数组长度未知）
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P> = [P { x: 1, y: 2 }];\n"
            "a[0].y = 9;\n"
            "print(a[0].x);");
        CHECK(a.find("ldr x14, [x29, #-8]") != std::string::npos);
        CHECK(a.find("ldr x11, [x29, #-16]") != std::string::npos);
        CHECK(a.find("cmp x10, x11") != std::string::npos);
        CHECK(a.find("add x17, x17, #1") != std::string::npos);
    }

    // 嵌套字段路径 q[i].p.y：Q 扁平 3 槽 → mov x15,#3 + mul；float/bool 字段占一槽
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "struct Q { p: P; z: int; }\n"
            "let q: array<Q> = [Q { p: P { x: 1, y: 2 }, z: 3 }];\n"
            "let i: int = 0;\n"
            "q[i].p.y = 9;\n"
            "print(q[0].z);");
        CHECK(a.find("mov x15, #3") != std::string::npos);
        CHECK(a.find("mul x17, x10, x15") != std::string::npos);
        CHECK(a.find("add x17, x17, #1") != std::string::npos);
    }
    {
        std::string a = asm_of(
            "struct F { a: float; b: bool; }\n"
            "let f: array<F> = [F { a: 1.5, b: true }];\n"
            "push(f, F { a: 2.5, b: false });\n"
            "let i: int = 0;\n"
            "print(f[i].a, f[0].b);\n"
            "f[0].a = 9.25;");
        CHECK(a.find("fmov x9, d9") != std::string::npos);  // 字面量按位模式打包
        CHECK(a.find("ldr d9, [x14, x17, lsl #3]") != std::string::npos);
        CHECK(a.find("str d9, [x14, x17, lsl #3]") != std::string::npos);
    }

    // push struct 字面量/变量：slots 槽追加；扩容按 newcap*slots*8 字节并搬 len*slots 槽
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P> = [P { x: 1, y: 2 }];\n"
            "push(a, P { x: 3, y: 4 });\n"
            "let p = P { x: 5, y: 6 };\n"
            "push(a, p);");
        CHECK(a.find("lsl x15, x9, #1") != std::string::npos);  // 容量足够：data[len*slots]
        CHECK(a.find("L.dyn.grow.") != std::string::npos);
        CHECK(a.find("mul x0, x12, x0") != std::string::npos);   // newcap*slots
        CHECK(a.find("lsl x0, x0, #3") != std::string::npos);    // *8 字节
        CHECK(a.find("L.copy.words.") != std::string::npos);     // 搬 len*slots 个槽
        CHECK(a.find("str x12, [x14, #8]") != std::string::npos);  // 追加 P.y
        CHECK(a.find("bl _free") != std::string::npos);            // 扩容后 free 旧缓冲
    }
    // slots=3 时扩容字节数与搬运都用 mul
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "struct Q { p: P; z: int; }\n"
            "let q: array<Q> = [Q { p: P { x: 1, y: 2 }, z: 3 }];\n"
            "push(q, Q { p: P { x: 4, y: 5 }, z: 6 });");
        CHECK(a.find("mov x15, #3") != std::string::npos);
        CHECK(a.find("mul x15, x9, x15") != std::string::npos);   // len*slots
        CHECK(a.find("mul x0, x12, x0") != std::string::npos);    // newcap*slots
        CHECK(a.find("mul x10, x9, x10") != std::string::npos);   // len*slots（搬运）
    }

    // 元素整体赋值：a[1] = P{...}（常量）与 a[i] = p（动态）
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "let p = P { x: 5, y: 6 };\n"
            "let i: int = 0;\n"
            "a[i] = p;\n"
            "a[1] = P { x: 7, y: 8 };");
        CHECK(a.find("ldr x11, [x29, #-16]") != std::string::npos);
        CHECK(a.find("cmp x10, x11") != std::string::npos);
        CHECK(count_substr(code_only(a), "L.dbounds.fail.") >= 2);  // 常量下标也运行时检查
        CHECK(a.find("lsl x17, x10, #1") != std::string::npos);
        CHECK(a.find("add x14, x14, x17, lsl #3") != std::string::npos);
        CHECK(a.find("str x9, [x14, #0]") != std::string::npos);
        CHECK(a.find("str x9, [x14, #8]") != std::string::npos);
    }

    // 深拷贝：let b = a / b = a 都按 slots 重新 malloc 并搬 len*slots 槽
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "let a: array<P> = [P { x: 1, y: 2 }];\n"
            "let b = a;\n"
            "b = a;\n"
            "print(len(b), b[0].x, a[0].y);");
        CHECK(a.find("mov x0, #2") != std::string::npos);  // cap*slots
        CHECK(a.find("mul x0, x10, x0") != std::string::npos);
        CHECK(a.find("mul x10, x9, x10") != std::string::npos);  // len*slots 搬运
        CHECK(a.find("L.copy.words.") != std::string::npos);
        CHECK(a.find("bl _free") != std::string::npos);  // b = a 前先 drop 旧 b
    }

    // 参数 ABI：3 槽描述符指针 + 入口按 slots 深拷贝 len*slots 槽（参数值语义）
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn first(a: array<P>) -> int {\n"
            "  a[0].x = 99;\n"
            "  return a[1].x;\n"
            "}\n"
            "let a: array<P> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "print(first(a), a[0].x);");
        CHECK(a.find("_first:") != std::string::npos);
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);  // 参数描述符指针
        CHECK(a.find("ldr x10, [x29, #-8]") != std::string::npos);
        CHECK(a.find("ldr x11, [x10, #0]") != std::string::npos);
        CHECK(a.find("ldr x13, [x10, #16]") != std::string::npos);
        CHECK(a.find("mul x0, x13, x0") != std::string::npos);  // cap*slots
        CHECK(a.find("lsl x0, x0, #3") != std::string::npos);
        CHECK(a.find("L.dyn.param.copy.") != std::string::npos);
        CHECK(a.find("mul x17, x12, x16") != std::string::npos);  // len*slots
        CHECK(a.find("bl _first") != std::string::npos);
    }

    // 返回值 ABI：sret 描述符 + data/len/cap 转移 + 清空临时描述符 + 调用方接管
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn clone(a: array<P>) -> array<P> { return a; }\n"
            "let a: array<P> = [P { x: 1, y: 2 }];\n"
            "let b: array<P> = clone(a);\n"
            "print(len(b), b[0].x);");
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);   // 保存 sret
        CHECK(a.find("str x9, [x15, #0]") != std::string::npos);    // data → sret
        CHECK(a.find("str x9, [x15, #8]") != std::string::npos);    // len → sret
        CHECK(a.find("str x9, [x15, #16]") != std::string::npos);   // cap → sret
        CHECK(a.find("str xzr, [x29, #-16]") != std::string::npos); // 转移后清空
        CHECK(a.find("str xzr, [x29, #-24]") != std::string::npos);
        CHECK(a.find("str xzr, [x29, #-32]") != std::string::npos);
        CHECK(a.find("ldr x14, [x10, #0]") != std::string::npos);   // 调用方接管
        CHECK(a.find("str xzr, [x10, #8]") != std::string::npos);
    }
    // 返回字面量 / 返回调用：同样走 sret 描述符并转移所有权
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn make(n: int) -> array<P> { return [P { x: n, y: n }]; }\n"
            "let b = make(3);\n"
            "print(len(b), b[0].x);");
        CHECK(a.find("_make:") != std::string::npos);
        CHECK(a.find("str x9, [x15, #0]") != std::string::npos);
        CHECK(a.find("str xzr, [x29, #-16]") != std::string::npos);
    }

    // S3c-3d：固定 array<S, N> 参数/返回值与动态 array<S> 一样放行（指针 + 入口拷贝 / sret）
    {
        std::string a = asm_of("struct P { x: int; }\n"
                               "fn f(a: array<P, 2>) -> int { return a[0].x; }");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #8]") != std::string::npos);  // 2 槽入口拷贝
    }
    {
        std::string a = asm_of("struct P { x: int; }\n"
                               "fn f() -> array<P, 2> { return [P { x: 7 }, P { x: 8 }]; }");
        CHECK(a.find("str x9, [x15, #8]") != std::string::npos);  // sret 打包 2 槽
    }
    {
        std::string a = asm_of("struct P { x: int; y: int; }\n"
                               "fn f(a: array<P>) -> array<P> { return a; }");
        CHECK(a.find("_f:") != std::string::npos);
    }

    // struct 字段仍不能是 array（含动态 array<struct>）
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct S { a: array<P>; }"),
                 "struct 字段不支持 array");
    // struct 元素整体读取仍拒绝（只能访问标量字段）
    CHECK_THROWS(asm_of("struct P { x: int; y: int; }\n"
                        "let a: array<P> = [P { x: 1, y: 2 }];\n"
                        "print(a[0]);"),
                 "array<struct> 元素不能整体读取为 struct 值");
    CHECK_THROWS(asm_of("struct P { x: int; y: int; }\n"
                        "let a: array<P> = [P { x: 1, y: 2 }];\n"
                        "let p: P = a[0];"),
                 "array<struct> 元素不能整体读取为 struct 值");
    {
        std::string a = asm_of("struct P { x: int; }\n"
                               "let a: array<P> = [P { x: 1 }];\n"
                               "print(a);");
        CHECK(a.find("L.print.cond.") != std::string::npos);
        CHECK(a.find("add x10, x10, x9, lsl #3") != std::string::npos);
    }

    // 类型不匹配：初始化来源 / push 值 / 元素整体赋值
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct Q { y: int; }\n"
                        "let a: array<P> = [P { x: 1 }];\n"
                        "let b: array<Q> = a;"),
                 "动态数组类型不匹配：需要 array<Q>，`a` 是 array<P>");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct Q { y: int; }\n"
                        "let a: array<P> = [P { x: 1 }];\n"
                        "push(a, Q { y: 2 });"),
                 "push 值类型不匹配：需要 P，字面量是 Q");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct Q { y: int; }\n"
                        "let a: array<P> = [P { x: 1 }];\n"
                        "a[0] = Q { y: 2 };"),
                 "数组元素赋值类型不匹配：需要 P，字面量是 Q");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P> = [P { x: 1 }];\n"
                        "push(a, 1);"),
                 "`P` 值必须是字面量");
    CHECK_THROWS(asm_of("struct P { x: int; }\nlet a: array<P> = 1;"),
                 "`array<P>` 初始化必须是");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P> = [P { x: 1 }];\n"
                        "a = 1;"),
                 "`array<P>` 初始化必须是");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P> = [P { x: 1 }];\n"
                        "let b = a;\n"
                        "b[true].x = 1;"),
                 "数组下标必须是 int，实际为 bool");
}

// ---- S3c-3c：固定嵌套数组 array<array<T, N>, M> ----

static void test_nested_array_s3c3c() {
    // 语法：嵌套 array 类型 + 嵌套字面量 + 双层下标
    {
        auto prog = Parser::parse(
            "let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\n"
            "a[0][1] = 9;");
        CHECK(prog.stmts[0]->ty.has_value() &&
              *prog.stmts[0]->ty == "array<array<int,2>,3>");
        CHECK(prog.stmts[0]->value->kind == Expr::Kind::Array);
        CHECK(prog.stmts[0]->value->args[0]->kind == Expr::Kind::Array);
        auto* assign = prog.stmts[1]->expr.get();
        CHECK(assign->kind == Expr::Kind::Assign);
        CHECK(assign->lhs->kind == Expr::Kind::Index &&
              assign->lhs->lhs->kind == Expr::Kind::Index);
    }

    // 扁平布局：外层 M=3、内层 N=2 → 6 个连续槽（-48..-8），元素 0 在最低地址
    {
        std::string a = asm_of(
            "let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\n"
            "print(a[0][0], a[0][1], a[1][0], a[1][1], a[2][0], a[2][1], len(a));");
        CHECK(a.find("sub sp, sp, #48") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-48]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-40]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-32]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-48]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-40]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("mov x9, #3") != std::string::npos);  // len(a) 是外层常量
    }

    // 常量下标读写直接按 base + 8*(i*N+j) 寻址（a[0][1] → -40，a[2][0] → -16）
    {
        std::string a = asm_of(
            "let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\n"
            "a[0][1] = 9;\n"
            "a[2][0] = 7;\n"
            "print(a[1][1]);");
        size_t mov = a.find("mov x9, #9");
        CHECK(mov != std::string::npos);
        CHECK(a.find("str x9, [x29, #-40]", mov) != std::string::npos);
        size_t mov7 = a.find("mov x9, #7");
        CHECK(mov7 != std::string::npos);
        CHECK(a.find("str x9, [x29, #-16]", mov7) != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-24]") != std::string::npos);
    }

    // 动态外层+内层下标：先查外层 M，再查内层 N；x17 = outer*N + inner
    {
        std::string a = asm_of(
            "let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\n"
            "let i: int = 1;\n"
            "let j: int = 0;\n"
            "print(a[i][j]);\n"
            "a[i][j] = 42;");
        CHECK(a.find("cmp x10, #3") != std::string::npos);  // 外层
        CHECK(a.find("cmp x10, #2") != std::string::npos);  // 内层
        CHECK(a.find("bl _tenet_bounds_fail") != std::string::npos);
        CHECK(a.find("lsl x17, x11, #1") != std::string::npos);  // outer*N
        CHECK(a.find("add x17, x17, x10") != std::string::npos);
        CHECK(a.find("add x14, x14, x17, lsl #3") != std::string::npos);
        CHECK(a.find("ldr x9, [x14, #0]") != std::string::npos);
        CHECK(a.find("str x9, [x14, #0]") != std::string::npos);
    }
    // 外层动态 + 内层常量：N=3 非 2 的幂 → mov x15,#3 + mul，再加常量 j
    {
        std::string a = asm_of(
            "let a: array<array<int, 3>, 2> = [[1, 2, 3], [4, 5, 6]];\n"
            "let i: int = 1;\n"
            "print(a[i][1]);");
        CHECK(a.find("cmp x10, #2") != std::string::npos);
        CHECK(a.find("mov x15, #3") != std::string::npos);
        CHECK(a.find("mul x17, x10, x15") != std::string::npos);
        CHECK(a.find("add x17, x17, #1") != std::string::npos);
    }

    // 同类型变量深拷贝 let b = a：逐槽复制（a 占 -32..-8，b 占 -64..-40）
    {
        std::string a = asm_of(
            "let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
            "let b = a;\n"
            "b[0][0] = 9;\n"
            "print(a[0][0], b[0][0]);");
        CHECK(a.find("sub sp, sp, #64") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-32]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-64]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-40]") != std::string::npos);
        size_t mov = a.find("mov x9, #9");
        CHECK(mov != std::string::npos);
        CHECK(a.find("str x9, [x29, #-64]", mov) != std::string::npos);  // b[0][0]
        CHECK(a.find("ldr x9, [x29, #-32]") != std::string::npos);       // a[0][0]
    }
    // 整体赋值 a = b（同类型深拷贝）
    {
        std::string a = asm_of(
            "let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
            "let b: array<array<int, 2>, 2> = [[5, 6], [7, 8]];\n"
            "b = a;\n"
            "print(b[0][0]);");
        CHECK(a.find("ldr x9, [x29, #-32]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-64]") != std::string::npos);
    }
    // 推断：let a = [[1,2],[3,4]] 推断为 array<array<int,2>,2>
    {
        std::string a = asm_of(
            "let a = [[1, 2], [3, 4]];\n"
            "print(a[1][1], len(a));");
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("mov x9, #2") != std::string::npos);
    }
    // float 内层：ldr/str d9
    {
        std::string a = asm_of(
            "let a: array<array<float, 2>, 2> = [[1.5, 2.5], [3.5, 4.5]];\n"
            "let i: int = 1;\n"
            "print(a[i][i], a[0][1]);\n"
            "a[0][1] = 9.25;");
        CHECK(a.find("ldr d9, [x29, #-24]") != std::string::npos);   // a[0][1] 常量读
        CHECK(a.find("str d9, [x29, #-24]") != std::string::npos);   // a[0][1] 常量写
        CHECK(a.find("ldr d9, [x14, #0]") != std::string::npos);     // a[i][i] 动态读
    }
    // 元素累加 / 嵌套循环下标
    {
        std::string a = asm_of(
            "let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\n"
            "let i: int = 0;\n"
            "let s: int = 0;\n"
            "while (i < len(a)) {\n"
            "  let j: int = 0;\n"
            "  while (j < 2) {\n"
            "    s = s + a[i][j];\n"
            "    j = j + 1;\n"
            "  }\n"
            "  i = i + 1;\n"
            "}\n"
            "print(s);");
        CHECK(a.find("cmp x10, #3") != std::string::npos);
        CHECK(a.find("cmp x10, #2") != std::string::npos);
        CHECK(a.find("bl _tenet_bounds_fail") != std::string::npos);
    }

    // S3c-3d：嵌套数组参数/返回值已支持（指针 + 入口按 M*N 槽拷贝 / sret）；
    // bool 内层、动态外层/内层、更深嵌套、struct 内层仍拒绝。
    {
        std::string a =
            asm_of("fn f(a: array<array<int, 2>, 2>) -> int { return a[0][0]; }");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #24]") != std::string::npos);  // M*N = 4 槽入口拷贝
    }
    {
        std::string a =
            asm_of("fn f() -> array<array<int, 2>, 2> { return [[1, 2], [3, 4]]; }");
        CHECK(a.find("str x9, [x15, #24]") != std::string::npos);  // sret 打包 M*N 槽
    }
    CHECK_THROWS(asm_of("let a: array<array<bool, 2>, 2> = [[true, false], [false, true]];"),
                 "嵌套数组内层暂不支持 bool");
    CHECK_THROWS(asm_of("let a: array<array<int>> = [[1], 2];"),
                 "嵌套数组第 1 个元素必须是内层数组字面量");
    CHECK_THROWS(asm_of("let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                        "let b: array<array<int>, 2> = [[[1]], [[2]]];"),
                 "嵌套数组内层必须是固定长度");
    CHECK_THROWS(asm_of("let a: array<array<array<int, 2>, 2>, 2> = "
                        "[[[1, 2], [3, 4]], [[5, 6], [7, 8]]];"),
                 "嵌套数组内层只支持 int/float");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<array<P, 2>, 2> = "
                        "[[P { x: 1 }, P { x: 2 }], [P { x: 3 }, P { x: 4 }]];"),
                 "嵌套数组内层只支持 int/float");

    // 长度/类型不匹配
    CHECK_THROWS(asm_of("let a: array<array<int, 2>, 3> = [[1, 2], [3, 4]];"),
                 "数组初始化长度不匹配：需要 3，实际 2");
    CHECK_THROWS(asm_of("let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\n"
                        "let b: array<array<int, 3>, 3> = a;"),
                 "`b` 需要 array<array<int,3>,3>，但 `a` 是 array<array<int,2>,3>");
    CHECK_THROWS(asm_of("let a: array<array<int, 2>, 2> = [[1, 2], [3]];"),
                 "内层数组长度不匹配：需要 2，实际 1");
    CHECK_THROWS(asm_of("let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                        "a = [[1, 2], [3]];"),
                 "内层数组长度不匹配：需要 2，实际 1");
    CHECK_THROWS(asm_of("let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                        "let b: array<array<int, 2>, 3> = a;"),
                 "数组初始化长度不匹配：需要 3，实际 2");

    // 下标错误：常量越界（外层/内层）编译期；动态越界运行时
    CHECK_THROWS(asm_of("let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                        "print(a[2][0]);"),
                 "外层数组下标 2 越界（长度 2）");
    CHECK_THROWS(asm_of("let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                        "print(a[0][2]);"),
                 "内层数组下标 2 越界（长度 2）");
    CHECK_THROWS(asm_of("let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                        "a[-1][0] = 1;"),
                 "外层数组下标 -1 越界（长度 2）");
    {
        std::string a = asm_of(
            "let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
            "let i: int = 2;\n"
            "let j: int = -1;\n"
            "print(a[i][j]);");
        CHECK(a.find("cmp x10, #2") != std::string::npos);
        CHECK(a.find("b.hs L.bounds.fail.") != std::string::npos);
        CHECK(a.find("bl _tenet_bounds_fail") != std::string::npos);
    }

    // 非嵌套数组不能取两层下标；len(a[i]) 暂不支持
    CHECK_THROWS(asm_of("let a = [1, 2];\nprint(a[0][0]);"),
                 "不是嵌套数组（需要 `array<array<T, N>, M>`）");
    CHECK_THROWS(asm_of("let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                        "print(len(a[0]));"),
                 "`len` 参数必须是数组变量");
    CHECK_THROWS(asm_of("print([1, 2][0][0]);"),
                 "v1 只支持对数组变量取下标");
    // 内层数组不能整体取值/赋值（只支持 a[i][j] 标量元素）
    CHECK_THROWS(asm_of("let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                        "print(a[0] == a[1]);"),
                 "嵌套数组元素不能整体取值");
    CHECK_THROWS(asm_of("let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                        "a[0] = [5, 6];"),
                 "嵌套数组元素不能整体赋值");
}

// ---- S3c-3d：固定 array<struct,N> / array<array<T,N>,M> 参数与返回值 ABI ----
//
// 参数：x 寄存器传元素 0 地址，被调函数入口按总槽数（N*slots / M*N）拷贝到本地扁平槽；
// 返回值：隐藏 sret 指针（x0），函数返回 void，return 打包到 sret，调用方逐槽接管。

static void test_fixed_array_abi_s3c3d() {
    // 1) array<struct, N> 参数入口：按 N*slots 逐槽拷贝到本地扁平槽（参数值语义）。
    {
        std::string a = asm_of("struct P { x: int; y: int; }\n"
                               "fn f(a: array<P, 2>) -> int { return a[0].x + a[1].y; }");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #0]") != std::string::npos);   // 元素 0 字段 0
        CHECK(a.find("ldr x9, [x0, #24]") != std::string::npos);  // 元素 1 字段 1
        CHECK(a.find("str x9, [x29, #-32]") != std::string::npos);  // 本地槽 0
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);   // 本地槽 3
    }

    // 2) 参数在函数内就是普通扁平数组：a[i].field 按 slots 步长寻址 + 运行时边界检查。
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn f(a: array<P, 2>, i: int) -> int { return a[i].y; }");
        CHECK(a.find("str x1, [x29, #-40]") != std::string::npos);  // 标量参数落槽
        CHECK(a.find("cmp x10, #2") != std::string::npos);
        CHECK(a.find("b.hs L.bounds.fail.") != std::string::npos);
        CHECK(a.find("lsl x17, x10, #1") != std::string::npos);  // idx * slots(2)
        CHECK(a.find("add x17, x17, #1") != std::string::npos);  // + 字段 y
        CHECK(a.find("ldr x9, [x14, x17, lsl #3]") != std::string::npos);
    }

    // 3) array<struct, N> 返回值：sret 指针落槽、函数返回 void、打包后写回 sret。
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn f() -> array<P, 2> { return [P { x: 1, y: 2 }, P { x: 3, y: 4 }]; }");
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);  // 隐藏 sret 指针
        CHECK(a.find("str x9, [x15, #0]") != std::string::npos);
        CHECK(a.find("str x9, [x15, #24]") != std::string::npos);  // 4 槽写回
    }
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn f(a: array<P, 2>) -> array<P, 2> { return a; }");
        CHECK(a.find("str x9, [x29, #-72]") != std::string::npos);  // 帧尾 4 槽临时缓冲
        CHECK(a.find("str x9, [x15, #24]") != std::string::npos);
    }

    // 4) 调用方：sret 缓冲 + 指针实参；let/赋值从返回缓冲逐槽接管（值语义）。
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn f(a: array<P, 2>) -> array<P, 2> { return a; }\n"
            "let x: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "let y = f(x);\n"
            "print(y[0].x);");
        CHECK(a.find("bl _f") != std::string::npos);
        CHECK(a.find("ldp x1, xzr, [sp], #16") != std::string::npos);  // sret 占 x0，数组指针在 x1
        CHECK(a.find("ldr x9, [x10, #0]") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, #24]") != std::string::npos);  // 接管 4 槽
    }
    {
        std::string a = asm_of(
            "struct P { x: int; }\n"
            "fn f() -> array<P, 2> { return [P { x: 7 }, P { x: 8 }]; }\n"
            "let b: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
            "b = f();\n"
            "print(b[1].x);");
        CHECK(a.find("ldr x9, [x10, #8]") != std::string::npos);
    }

    // 5) 字面量实参：调用方构造临时数组缓冲并把元素 0 地址传进参数寄存器。
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "fn f(a: array<P, 2>) -> int { return a[0].x; }\n"
            "print(f([P { x: 5, y: 6 }, P { x: 7, y: 8 }]));");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("bl _f") != std::string::npos);
        CHECK(a.find("ldp x0, xzr, [sp], #16\n\tbl _f") != std::string::npos);
    }

    // 6) len(固定 struct 数组参数) 仍是编译期常量；Q 的 3 字段元素 stride = 24。
    {
        std::string a = asm_of("struct P { x: int; }\n"
                               "fn f(a: array<P, 2>) -> int { return len(a); }");
        CHECK(a.find("mov x9, #2") != std::string::npos);
    }
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "struct Q { p: P; z: int; }\n"
            "fn f(a: array<Q, 2>) -> int { return a[1].p.y; }");
        CHECK(a.find("ldr x9, [x0, #40]") != std::string::npos);  // 6 槽入口拷贝
        CHECK(a.find("str x9, [x29, #-48]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
    }

    // 7) 嵌套数组参数：M*N 槽入口拷贝；a[i][j] 双边界检查 + outer*N+inner 寻址。
    {
        std::string a =
            asm_of("fn f(a: array<array<int, 2>, 2>) -> int { return a[0][1]; }");
        CHECK(a.find("ldr x9, [x0, #0]") != std::string::npos);
        CHECK(a.find("ldr x9, [x0, #24]") != std::string::npos);  // M*N = 4 槽
        CHECK(a.find("str x9, [x29, #-32]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
    }
    {
        std::string a = asm_of(
            "fn f(a: array<array<int, 2>, 2>, i: int, j: int) -> int { return a[i][j]; }");
        CHECK(a.find("cmp x10, #2") != std::string::npos);
        CHECK(a.find("lsl x17, x11, #1") != std::string::npos);   // outer * N
        CHECK(a.find("add x17, x17, x10") != std::string::npos);  // + inner
        CHECK(a.find("ldr x9, [x14, #0]") != std::string::npos);
    }

    // 8) 嵌套数组返回值：sret + M*N 槽打包；调用方 let 接管。
    {
        std::string a =
            asm_of("fn f() -> array<array<int, 2>, 2> { return [[1, 2], [3, 4]]; }");
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x15, #24]") != std::string::npos);
    }
    {
        std::string a = asm_of(
            "fn f(a: array<array<int, 2>, 2>) -> array<array<int, 2>, 2> { return a; }\n"
            "let n: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
            "let m = f(n);\n"
            "print(m[0][1]);");
        CHECK(a.find("bl _f") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, #24]") != std::string::npos);
    }

    // 9) float 字段 / float 内层：同样按 8 字节槽位模式拷贝。
    {
        std::string a = asm_of(
            "struct P { x: int; y: float; }\n"
            "fn f() -> array<P, 2> { return [P { x: 1, y: 2.5 }, P { x: 3, y: 4.5 }]; }");
        CHECK(a.find("fmov x9, d9") != std::string::npos);  // float 字段按位模式打包
        CHECK(a.find("str x9, [x15, #8]") != std::string::npos);
    }
    {
        std::string a = asm_of(
            "fn f(a: array<array<float, 2>, 2>) -> array<array<float, 2>, 2> { return a; }");
        CHECK(a.find("ldr x9, [x1, #0]") != std::string::npos);   // sret 在 x0，指针在 x1
        CHECK(a.find("ldr x9, [x1, #24]") != std::string::npos);
        CHECK(a.find("str x9, [x15, #24]") != std::string::npos);
    }

    // 10) 错误：实参类型/长度、返回类型、内层限制与动态数组都明确报错。
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "fn f(a: array<P, 2>) -> int { return a[0].x; }\n"
                        "let n: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                        "print(f(n));"),
                 "数组实参类型不匹配");
    CHECK_THROWS(asm_of("struct P { x: int; y: int; }\n"
                        "struct Q { z: int; }\n"
                        "fn f(a: array<P, 2>) -> int { return a[0].x; }\n"
                        "print(f([P { x: 1, y: 2 }, Q { z: 3 }]));"),
                 "数组元素 1 类型不匹配：需要 P，字面量是 Q");
    CHECK_THROWS(asm_of("struct P { x: int; y: int; }\n"
                        "fn f(a: array<P, 2>) -> int { return a[0].x; }\n"
                        "print(f([P { x: 1, y: 2 }]));"),
                 "数组长度不匹配：需要 2，实际 1");
    CHECK_THROWS(asm_of("struct P { x: int; y: int; }\n"
                        "struct Q { z: int; }\n"
                        "fn f() -> array<P, 2> { let q: array<Q, 2> = [Q { z: 1 }, Q { z: 2 }];"
                        " return q; }"),
                 "数组类型不匹配：需要 array<P,2>，实际 array<Q,2>");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "fn f() -> array<P, 2> { return [P { x: 1 }, P { x: 2 }, P { x: 3 }]; }"),
                 "数组长度不匹配：需要 2，实际 3");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "fn f() -> array<P, 2> { return 1; }"),
                 "固定数组值必须是同类型数组变量、字面量或返回数组的调用");
    CHECK_THROWS(asm_of("fn f() -> array<array<int, 2>, 2> { return [[1, 2, 3], [4, 5, 6]]; }"),
                 "内层数组长度不匹配：需要 2，实际 3");
    CHECK_THROWS(asm_of("fn f(a: array<array<bool, 2>, 2>) -> int { return 0; }"),
                 "嵌套数组内层暂不支持 bool");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "fn f(a: array<array<P, 2>, 2>) -> int { return 0; }"),
                 "嵌套数组内层只支持 int/float");
    CHECK_THROWS(asm_of("fn f(a: array<array<int, 2>>) -> int { return 0; }"),
                 "动态嵌套数组的内层必须是动态数组");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "fn f(a: array<P, 2>) -> int { return a[0].x; }\n"
                        "let d: array<P> = [P { x: 1 }];\n"
                        "print(f(d));"),
                 "数组实参类型不匹配");
    CHECK_THROWS(asm_of("fn f(a: array<array<int, 2>, 2>) -> int { return a[0][0]; }\n"
                        "let n: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                        "print(f(n[0]));"),
                 "数组实参必须是同类型数组变量、字面量或返回数组的调用");
}

// ---- print aggregate（struct / 定长数组 / 动态数组 / 嵌套数组）----

static void test_print_aggregate() {
    // 1) struct：`P { x: 1, y: 2.5 }`；扁平字段逐个 printf。
    {
        std::string a = asm_of(
            "struct P { x: int; y: float; }\n"
            "let p: P = P { x: 1, y: 2.5 };\n"
            "print(p);");
        CHECK(a.find(".asciz \"P { \"") != std::string::npos);
        CHECK(a.find(".asciz \"x: \"") != std::string::npos);
        CHECK(a.find(".asciz \"y: \"") != std::string::npos);
        CHECK(a.find(".asciz \" }\"") != std::string::npos);
        CHECK(a.find(".asciz \"%lld\"") != std::string::npos);
        CHECK(a.find(".asciz \"%g\"") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);   // p.x
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos);  // p.y
        CHECK(count_substr(code_only(a), "bl _printf") == 8);
    }

    // 2) 嵌套 struct：字段名用扁平路径（`Q { p.x: 1, p.y: 2, z: 3 }`）。
    {
        std::string a = asm_of(
            "struct P { x: int; y: int; }\n"
            "struct Q { p: P; z: int; }\n"
            "let q: Q = Q { p: P { x: 1, y: 2 }, z: 3 };\n"
            "print(q);");
        CHECK(a.find(".asciz \"Q { \"") != std::string::npos);
        CHECK(a.find(".asciz \"p.x: \"") != std::string::npos);
        CHECK(a.find(".asciz \"p.y: \"") != std::string::npos);
        CHECK(a.find(".asciz \"z: \"") != std::string::npos);
        CHECK(a.find(".asciz \"p: \"") == std::string::npos);
    }

    // 3) 定长标量数组：编译期展开 `[1, 2, 3]`。
    {
        std::string a = asm_of("let a: array<int, 3> = [1, 2, 3];\nprint(a);");
        CHECK(a.find(".asciz \"[\"") != std::string::npos);
        CHECK(a.find(".asciz \"]\"") != std::string::npos);
        CHECK(count_substr(code_only(a), ".asciz \"%lld\"") == 3);
        CHECK(count_substr(code_only(a), ".asciz \", \"") == 2);
        CHECK(a.find("L.print.cond.") == std::string::npos);  // 定长展开，无运行时循环
    }
    {
        std::string a = asm_of("let f: array<float, 2> = [1.5, 2.5];\nprint(f);");
        CHECK(count_substr(code_only(a), ".asciz \"%g\"") == 2);
    }
    {
        std::string a = asm_of("let b: array<bool, 2> = [true, false];\nprint(b);");
        CHECK(a.find(".asciz \"true\"") != std::string::npos);
        CHECK(a.find(".asciz \"false\"") != std::string::npos);
    }

    // 4) 定长 struct 数组：元素 stride = slots*8，字段在元素内按 +8 排列。
    {
        std::string a = asm_of(
            "struct P { x: int; y: float; }\n"
            "let a: array<P, 2> = [P { x: 3, y: 4.5 }, P { x: 5, y: 6.5 }];\n"
            "print(a);");
        CHECK(count_substr(code_only(a), ".asciz \"P { \"") == 2);
        CHECK(a.find("ldr x9, [x29, #-32]") != std::string::npos);  // a[0].x
        CHECK(a.find("ldr x9, [x29, #-24]") != std::string::npos);  // a[0].y
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos);  // a[1].x
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);   // a[1].y
        CHECK(code_only(a).find("bl _malloc") == std::string::npos);  // 不引入堆
    }

    // 5) 动态标量数组：运行时循环（索引存 scratch 槽），len 从描述符读。
    {
        std::string a = asm_of("let d: array<int> = [7, 8];\nprint(d);");
        CHECK(a.find("L.print.cond.") != std::string::npos);
        CHECK(a.find("L.print.sep.") != std::string::npos);
        CHECK(a.find("b.hs L.print.end.") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, x9, lsl #3]") != std::string::npos);
        CHECK(count_substr(code_only(a), ".asciz \"%lld\"") == 1);
    }
    {
        std::string a = asm_of("let f: array<float> = [1.5, 2.5];\nprint(f);");
        CHECK(count_substr(code_only(a), ".asciz \"%g\"") == 1);
    }
    {
        std::string a = asm_of("let b: array<bool> = [true];\nprint(b);");
        CHECK(a.find(".asciz \"true\"") != std::string::npos);
        CHECK(a.find(".asciz \"false\"") != std::string::npos);
    }
    {
        std::string a = asm_of("let e: array<int> = [];\nprint(e);");
        CHECK(a.find("L.print.cond.") != std::string::npos);
        CHECK(a.find(".asciz \"[\"") != std::string::npos);
        CHECK(a.find(".asciz \"]\"") != std::string::npos);
    }

    // 6) 动态 struct 数组：stride = slots*8 取元素。
    {
        std::string a = asm_of(
            "struct P { x: int; y: float; }\n"
            "let d: array<P> = [P { x: 1, y: 1.5 }];\n"
            "print(d);");
        CHECK(a.find("L.print.cond.") != std::string::npos);
        CHECK(a.find("mov x11, #2") != std::string::npos);  // slots = 2
        CHECK(a.find("mul x9, x9, x11") != std::string::npos);
        CHECK(a.find("add x10, x10, x9, lsl #3") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, #0]") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, #8]") != std::string::npos);
        CHECK(count_substr(code_only(a), ".asciz \"P { \"") == 1);  // 循环体复用格式串
    }

    // 7) 定长嵌套数组：外层/内层都展开为 `[[1, 2], [3, 4]]`。
    {
        std::string a = asm_of(
            "let n: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
            "print(n);");
        CHECK(count_substr(code_only(a), ".asciz \"[\"") == 3);
        CHECK(count_substr(code_only(a), ".asciz \"]\"") == 3);
        CHECK(count_substr(code_only(a), ".asciz \"%lld\"") == 4);
        CHECK(count_substr(code_only(a), ".asciz \", \"") == 3);
        CHECK(code_only(a).find("bl _malloc") == std::string::npos);
    }

    // 8) print 多参：aggregate 与标量之间一个空格；结尾换行。
    {
        std::string a = asm_of(
            "struct P { x: int; }\n"
            "let p: P = P { x: 1 };\n"
            "print(p, 2, p);");
        CHECK(count_substr(code_only(a), ".asciz \" \"") == 2);
        CHECK(count_substr(code_only(a), ".asciz \"\\n\"") == 1);
        CHECK(count_substr(code_only(a), ".asciz \"%lld\"") == 3);
    }

    // 9) 纯标量 print 仍走单次 printf（既有行为不变）。
    {
        std::string a = asm_of(
            "let a: array<int, 2> = [1, 2];\n"
            "print(a[0], len(a), \"s\", true, 2.5);");
        CHECK(count_substr(code_only(a), "bl _printf") == 1);
    }

    // 10) aggregate 表达式（不是变量）明确报错。
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "fn mk() -> P { return P { x: 1 }; }\n"
                        "print(mk());"),
                 "print 不支持该类型的值");
    CHECK_THROWS(asm_of("fn mk() -> array<int, 2> { return [1, 2]; }\n"
                        "print(mk());"),
                 "print 不支持该类型的值");
    CHECK_THROWS(asm_of("struct P { x: int; }\nprint(P { x: 1 });"),
                 "struct 字面量只能用于");
    CHECK_THROWS(asm_of("let n: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                        "print(n[0]);"),
                 "嵌套数组元素不能整体取值");
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<P, 1> = [P { x: 1 }];\n"
                        "print(a[0]);"),
                 "array<struct> 元素不能整体读取");
}

// ---- S3c-3e：动态嵌套数组 array<array<T>>（外层/内层均动态，内层标量）----

static void test_dynamic_nested_array_s3c3e() {
    // 1) 字面量布局：外层 cap=4 → 4*24=96 字节；两行内层各 cap=4 → 32 字节。
    //    外层元素是内层 descriptor [data,len,cap]，stride=24。
    {
        std::string a = asm_of("let a: array<array<int>> = [[1, 2], [3]];");
        CHECK(a.find("mov x0, #96") != std::string::npos);
        CHECK(count_substr(code_only(a), "bl _malloc") == 3);
        CHECK(a.find("add x14, x14, #24") != std::string::npos);  // 第二行 descriptor
        CHECK(a.find("str x9, [x14, #0]") != std::string::npos);   // 内层 data
        CHECK(a.find("str x9, [x14, #8]") != std::string::npos);   // 内层 len
        CHECK(a.find("str x9, [x14, #16]") != std::string::npos);  // 内层 cap
    }

    // 2) 空外层 + push 空内层；len(a[0]) 只检查外层一次，再读内层 len 槽。
    {
        std::string a = asm_of(
            "let a: array<array<int>> = [];\n"
            "push(a, []);\n"
            "print(len(a), len(a[0]));");
        CHECK(a.find("mov x0, #96") != std::string::npos);  // 空外层 cap=4
        CHECK(a.find("mov x0, #32") != std::string::npos);  // 空内层 cap=4
        CHECK(a.find("L.dyn.nested.grow") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, #8]") != std::string::npos);  // len(a[0])
        CHECK(count_substr(code_only(a), "bl _tenet_bounds_fail") == 1);
    }

    // 3) let 深拷贝 + b = a 整体赋值：两次逐内层深拷贝；赋值前 drop 旧 b。
    {
        std::string a = asm_of(
            "let a: array<array<int>> = [[1], [2]];\n"
            "let b: array<array<int>> = a;\n"
            "b = a;\n"
            "a[0][0] = 9;\n"
            "print(b[0][0]);");
        CHECK(count_substr(code_only(a), "L.dnest.copy.") >= 4);  // 两次拷贝各有 loop/end
        CHECK(a.find("L.dnest.drop.loop") != std::string::npos);
        CHECK(a.find("L.dnest.drop.after") != std::string::npos);
        CHECK(a.find("mov x11, #24") != std::string::npos);  // 外层按 24 字节 stride 拷贝
    }

    // 4) push：内层字面量与内层变量都深拷贝后追加；外层容量按 cap*2 扩容。
    {
        std::string a = asm_of(
            "let a: array<array<int>> = [];\n"
            "let r: array<int> = [7];\n"
            "push(a, [1, 2]);\n"
            "push(a, r);\n"
            "r[0] = 9;\n"
            "print(a[1][0]);");
        CHECK(count_substr(code_only(a), "L.dyn.nested.grow") == 8);  // 两次 push 各有 grow/after（引用+标签）
        CHECK(count_substr(code_only(a), "L.dyn.copy.") >= 2);  // 内层变量深拷贝
        CHECK(a.find("L.copy.words") != std::string::npos);     // 外层扩容搬运
        CHECK(count_substr(code_only(a), "bl _malloc") >= 3);
    }

    // 5) float / bool 内层 + print：`[[1.5], [2.5]]` 与 true/false 展开。
    {
        std::string a = asm_of(
            "let f: array<array<float>> = [[1.5], [2.5]];\n"
            "print(f);\n"
            "let b: array<array<bool>> = [[true], [false]];\n"
            "print(b);");
        CHECK(a.find(".asciz \"%g\"") != std::string::npos);
        CHECK(a.find(".asciz \"true\"") != std::string::npos);
        CHECK(a.find(".asciz \"false\"") != std::string::npos);
        CHECK(a.find("L.print.nested.cond") != std::string::npos);
        CHECK(a.find("L.print.inner.cond") != std::string::npos);
        CHECK(a.find("ldr x9, [x10, #0]") != std::string::npos);  // 内层 data
    }

    // 6) print(a)：外层/内层各展开一次 `[` `]`，元素分隔符两处，整行换行一次。
    {
        std::string a = asm_of(
            "let a: array<array<int>> = [[1, 2], [3]];\n"
            "print(a);");
        std::string c = code_only(a);
        CHECK(count_substr(c, ".asciz \"[\"") == 2);
        CHECK(count_substr(c, ".asciz \"]\"") == 2);
        CHECK(count_substr(c, ".asciz \", \"") == 2);
        CHECK(count_substr(c, ".asciz \"%lld\"") == 1);
        CHECK(count_substr(c, ".asciz \"\\n\"") == 1);
    }

    // 7) 参数/返回值：descriptor + 入口逐内层深拷贝；返回值走 sret 转移。
    {
        std::string a = asm_of(
            "fn clone(x: array<array<int>>) -> array<array<int>> { return x; }\n"
            "let a: array<array<int>> = [[1]];\n"
            "let b: array<array<int>> = clone(a);\n"
            "let c: array<array<int>> = clone([[2]]);\n"
            "print(len(b), len(c));");
        CHECK(a.find("\n_clone:\n") != std::string::npos);
        CHECK(count_substr(a, "\tbl _clone") == 2);
        CHECK(a.find("ldr x15, [x29, #-8]") != std::string::npos);  // sret 指针
        CHECK(a.find("str x9, [x15, #0]") != std::string::npos);    // data 转移
        CHECK(a.find("str x9, [x15, #8]") != std::string::npos);    // len 转移
        CHECK(a.find("str x9, [x15, #16]") != std::string::npos);   // cap 转移
        CHECK(a.find("L.dnest.copy.") != std::string::npos);        // 参数入口深拷贝
    }

    // 8) a[i][j] 读写：内外两层各做一次运行时边界检查。
    {
        std::string a = asm_of(
            "let a: array<array<int>> = [[1]];\n"
            "print(a[0][0]);");
        CHECK(count_substr(code_only(a), "bl _tenet_bounds_fail") == 2);
        CHECK(a.find("ldr x14, [x10, #0]") != std::string::npos);  // 内层 data
    }
    {
        std::string a = asm_of(
            "let a: array<array<int>> = [[1]];\n"
            "a[0][0] = 9;");
        CHECK(count_substr(code_only(a), "bl _tenet_bounds_fail") == 2);
        CHECK(a.find("str x9, [x14, x11, lsl #3]") != std::string::npos);
    }
    {
        std::string a = asm_of(
            "let a: array<array<int>> = [[1]];\n"
            "let i: int = 0;\n"
            "let j: int = 0;\n"
            "print(a[i][j]);");
        CHECK(count_substr(code_only(a), "bl _tenet_bounds_fail") == 2);
        CHECK(a.find("add x10, x12, x10") != std::string::npos);  // 外层行地址
    }

    // 9) drop：先逐内层 free(data)，再 free 外层。
    {
        std::string a = asm_of(
            "fn f() {\n"
            "  let a: array<array<int>> = [[1], [2]];\n"
            "  print(len(a));\n"
            "}\n"
            "f();");
        std::string c = code_only(a);
        size_t loop = c.find("L.dnest.drop.loop");
        size_t inner_free = c.find("bl _free", loop == std::string::npos ? 0 : loop);
        size_t after = c.find("L.dnest.drop.after",
                              inner_free == std::string::npos ? 0 : inner_free);
        size_t outer_free = c.find("bl _free", after == std::string::npos ? 0 : after);
        CHECK(loop != std::string::npos && after != std::string::npos);
        CHECK(inner_free != std::string::npos && inner_free < after);
        CHECK(outer_free != std::string::npos && outer_free > after);
        CHECK(c.find("L.dnest.drop.clear") != std::string::npos);
    }

    // 10) 不支持/类型错误：struct 内层、更深嵌套、固定/动态内层混用、整体行取值。
    CHECK_THROWS(asm_of("struct P { x: int; }\n"
                        "let a: array<array<P>> = [[P { x: 1 }]];"),
                 "array<struct>");
    CHECK_THROWS(asm_of("let a: array<array<array<int>>> = [[[1]]];"),
                 "只支持一层");
    CHECK_THROWS(asm_of("let a: array<array<int, 2>> = [[1, 2]];"),
                 "内层必须是动态数组");
    CHECK_THROWS(asm_of("let a: array<array<int>, 2> = [[1], [2]];"),
                 "嵌套数组内层必须是固定长度");
    CHECK_THROWS(asm_of("let a: array<array<string>> = [];"),
                 "只支持 int/float/bool");
    CHECK_THROWS(asm_of("struct S { a: array<array<int>>; }"), "不支持 array");
    CHECK_THROWS(asm_of("let a: array<array<int>> = [[1]];\nprint(a[0]);"),
                 "嵌套数组元素不能整体取值");
    CHECK_THROWS(asm_of("let a: array<array<int>> = [[1]];\na[0] = [2];"),
                 "嵌套数组元素不能整体赋值");
    CHECK_THROWS(asm_of("let a: array<array<int>> = [[1], 2];"),
                 "嵌套数组第 1 个元素必须是内层数组字面量");
    CHECK_THROWS(asm_of("let a: array<array<int>> = [[1], [2.5]];"), "类型不匹配");
    CHECK_THROWS(asm_of("let a: array<array<int>> = [[1]];\npush(a, [1.5]);"),
                 "类型不匹配");
    CHECK_THROWS(asm_of("let a: array<array<int>> = [[1]];\n"
                        "let b: array<array<float>> = a;"),
                 "动态嵌套数组类型不匹配");
    CHECK_THROWS(asm_of("fn f(x: array<array<int>>) -> int { return len(x); }\n"
                        "let a: array<array<float>> = [[1.0]];\n"
                        "print(f(a));"),
                 "参数类型不匹配");
    CHECK_THROWS(asm_of("fn f() -> array<array<int>> { return [[1.5]]; }"),
                 "类型不匹配");
}

// ---- S3d：struct 固定数组字段 v1 ----

static void test_struct_fixed_array_field_s3d() {
    // 语法：字段类型可以是固定数组（含 struct 元素 / 固定嵌套）
    {
        auto prog = Parser::parse(
            "struct S { a: array<int, 3>; x: int; }\n"
            "struct M { m: array<array<int, 2>, 2>; }");
        CHECK(prog.stmts[0]->fields.size() == 2);
        CHECK(prog.stmts[0]->fields[0].second == "array<int,3>");
        CHECK(prog.stmts[0]->fields[1].second == T_INT);
        CHECK(prog.stmts[1]->fields[0].second == "array<array<int,2>,2>");
    }

    // 布局：array<int,3> 占 3 槽 + x 占 1 槽 → 4 槽 / 32 字节；字面量按顺序写槽
    {
        std::string a = asm_of(
            "struct S { a: array<int, 3>; x: int; }\n"
            "let s: S = S { a: [1, 2, 3], x: 9 };\n"
            "s.a[1] = 7;\n"
            "print(s.a[1], s.x);");
        CHECK(a.find("sub sp, sp, #32") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-32]") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos);  // s.a[1]
        CHECK(a.find("ldr x9, [x29, #-32]") != std::string::npos);  // s.x
    }

    // 动态下标：array<int,3> 字段做运行时边界检查（cmp idx, #3）
    {
        std::string a = asm_of(
            "struct S { a: array<int, 3>; x: int; }\n"
            "let s: S = S { a: [1, 2, 3], x: 9 };\n"
            "let i: int = 1;\n"
            "print(s.a[i], s.x);");
        CHECK(a.find("cmp x10, #3") != std::string::npos);
        CHECK(a.find("b.hs L.bounds.fail.") != std::string::npos);
        CHECK(a.find("bl _tenet_bounds_fail") != std::string::npos);
    }

    // 整体赋值/let 拷贝：4 槽逐槽深拷贝（s: -8..-32，t: -40..-64）
    {
        std::string a = asm_of(
            "struct S { a: array<int, 3>; x: int; }\n"
            "let s: S = S { a: [1, 2, 3], x: 9 };\n"
            "let t: S = s;\n"
            "t.a[0] = 5;\n"
            "print(s.a[1], t.a[0]);");
        CHECK(a.find("sub sp, sp, #64") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-24]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-56]") != std::string::npos);
        CHECK(a.find("str x9, [x29, #-40]") != std::string::npos);
    }

    // struct 参数/返回值按总槽数走指针 / sret ABI（4 槽）
    {
        std::string a = asm_of(
            "struct S { a: array<int, 3>; x: int; }\n"
            "fn f(v: S) -> S { v.a[2] = 8; return v; }\n"
            "let s: S = S { a: [1, 2, 3], x: 9 };\n"
            "let u: S = f(s);\n"
            "print(u.a[2], u.x);");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);   // 隐藏 sret
        CHECK(a.find("ldr x9, [x1, #0]") != std::string::npos);     // 参数槽 0
        CHECK(a.find("ldr x9, [x1, #-24]") != std::string::npos);   // 参数槽 3
        CHECK(a.find("str x9, [x15, #-24]") != std::string::npos);  // sret 槽 3
        CHECK(a.find("ldr x9, [x29, #-32]") != std::string::npos);  // v.a[2]
    }

    // 数组字段可由同类型数组变量 / 返回数组的调用初始化；struct 整体赋值深拷贝
    {
        std::string a = asm_of(
            "struct S { a: array<int, 3>; x: int; }\n"
            "fn mk() -> array<int, 3> { return [7, 8, 9]; }\n"
            "let src: array<int, 3> = [1, 2, 3];\n"
            "let s: S = S { a: src, x: 4 };\n"
            "let t: S = S { a: mk(), x: 5 };\n"
            "s = t;\n"
            "print(s.a[0], t.a[2], s.x);");
        CHECK(a.find("_mk:") != std::string::npos);
        CHECK(a.find("bl _mk") != std::string::npos);
        CHECK(a.find("ldr x9, [x29, #-8]") != std::string::npos);
    }

    // 嵌套 struct 字段链中的固定数组：o.i.arr[1] 读写 + print 展开
    {
        std::string a = asm_of(
            "struct Inner { arr: array<int, 2>; }\n"
            "struct Outer { i: Inner; x: int; }\n"
            "let o: Outer = Outer { i: Inner { arr: [10, 20] }, x: 1 };\n"
            "o.i.arr[1] = 30;\n"
            "print(o.i.arr[0], o.i.arr[1], o.x);\n"
            "print(o);");
        CHECK(a.find(".asciz \"i.arr: \"") != std::string::npos);
        CHECK(a.find(".asciz \"x: \"") != std::string::npos);
        CHECK(a.find(".asciz \"[\"") != std::string::npos);
        CHECK(a.find(".asciz \"]\"") != std::string::npos);
    }

    // struct 字段是 array<struct,N>：s.a[i].field / s.a[i] = struct / print
    {
        std::string a = asm_of(
            "struct P { x: int; }\n"
            "struct S { a: array<P, 2>; }\n"
            "let s: S = S { a: [P { x: 1 }, P { x: 2 }] };\n"
            "let i: int = 0;\n"
            "s.a[i].x = 9;\n"
            "s.a[1] = P { x: 7 };\n"
            "print(s.a[0].x, s.a[1].x);\n"
            "print(s);");
        CHECK(a.find(".asciz \"P { \"") != std::string::npos);
        CHECK(a.find(".asciz \"a: \"") != std::string::npos);
        CHECK(a.find("sub x14, x14, x17, lsl #3") != std::string::npos);
    }

    // 固定嵌套数组字段 array<array<int,2>,2>：s.m[i][j] 读写 + print
    {
        std::string a = asm_of(
            "struct M { m: array<array<int, 2>, 2>; z: int; }\n"
            "let m: M = M { m: [[1, 2], [3, 4]], z: 5 };\n"
            "let i: int = 1;\n"
            "m.m[0][1] = 8;\n"
            "m.m[i][0] = 9;\n"
            "print(m.m[0][1], m.m[i][0], m.z);\n"
            "print(m);");
        CHECK(a.find(".asciz \"m: \"") != std::string::npos);
        CHECK(a.find("cmp x10, #2") != std::string::npos);  // 外层/内层边界检查
    }

    // float / bool 固定数组字段：float 按位模式槽、bool 占一槽
    {
        std::string a = asm_of(
            "struct S { f: array<float, 2>; b: array<bool, 2>; }\n"
            "let s: S = S { f: [1.5, 2.5], b: [true, false] };\n"
            "s.f[0] = 9.5;\n"
            "print(s.f[0], s.b[1]);\n"
            "print(s);");
        CHECK(a.find("str d9, [x29, #-8]") != std::string::npos);
        CHECK(a.find(".asciz \"f: \"") != std::string::npos);
        CHECK(a.find(".asciz \"b: \"") != std::string::npos);
    }

    // 深路径：数组元素内的固定数组字段 arr[i].f[j] / s.ps[i].q.f[j]
    {
        std::string a = asm_of(
            "struct P { xs: array<int, 2>; tag: int; }\n"
            "struct S { ps: array<P, 2>; }\n"
            "let s: S = S { ps: [P { xs: [1, 2], tag: 3 }, "
            "P { xs: [4, 5], tag: 6 }] };\n"
            "let i: int = 1;\n"
            "let j: int = 0;\n"
            "s.ps[i].xs[j] = 9;\n"
            "print(s.ps[i].xs[j], s.ps[0].tag);");
        CHECK(a.find("str x9, [x14, #0]") != std::string::npos);
        CHECK(a.find("ldr x9, [x14, #0]") != std::string::npos);
    }

    // 错误：动态 array<struct> 字段、动态嵌套字段、固定数组套动态内层仍拒绝
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct S { a: array<P>; }"),
                 "不支持 array");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct S { a: array<P>; }"),
                 "array<struct>");
    CHECK_THROWS(asm_of("struct S { a: array<array<int>, 2>; }"), "不支持 array");
    CHECK_THROWS(asm_of("struct S { a: array<array<int, 2>>; }"), "不支持 array");
    CHECK_THROWS(asm_of("struct S { a: array<string, 2>; }"), "不支持 string");
    CHECK_THROWS(asm_of("struct S { a: array<Nope, 2>; }"), "类型 `Nope` 未定义");
    CHECK_THROWS(asm_of("struct S { a: array<S, 2>; }"), "循环嵌套");
    CHECK_THROWS(asm_of("struct A { b: array<B, 2>; }\nstruct B { a: A; }"), "循环嵌套");
    CHECK_THROWS(asm_of("struct S { a: array<int, 2>; }\n"
                        "let s: S = S { a: [1, 2, 3] };"),
                 "数组长度不匹配");
    CHECK_THROWS(asm_of("struct S { a: array<int, 2>; }\n"
                        "let s: S = S { a: [1, 2.0] };"),
                 "类型不匹配");
    CHECK_THROWS(asm_of("struct S { a: array<int, 2>; }\n"
                        "let s: S = S { a: [1, 2] };\nprint(s.a);"),
                 "不能整体取值");
    {
        std::string a = asm_of("struct S { a: array<int, 2>; }\n"
                               "let s: S = S { a: [1, 2] };\ns.a = [3, 4];\n"
                               "print(s.a[0]);");
        CHECK(a.find("str x9, [x29, #-8]") != std::string::npos);
    }
    CHECK_THROWS(asm_of("struct S { a: array<int, 2>; }\n"
                        "let s: S = S { a: [1, 2] };\nprint(s.a[2]);"),
                 "越界");
    CHECK_THROWS(asm_of("struct S { a: array<int, 2>; }\n"
                        "let s: S = S { a: [1, 2] };\ns.a[-1] = 3;"),
                 "越界");
    CHECK_THROWS(asm_of("struct S { m: array<array<int, 2>, 2>; }\n"
                        "let s: S = S { m: [[1, 2], [3, 4]] };\nprint(s.m[0][2]);"),
                 "内层数组下标 2 越界");
    CHECK_THROWS(asm_of("struct S { a: array<int, 2>; }\n"
                        "let s: S = S { a: [1, 2] };\n"
                        "let t: array<int, 3> = s.a;"),
                 "数组");
}

// ---- S3e：struct 的动态数组字段 v1 ----

static void test_struct_dynamic_field_s3e() {
    // 语法/类型：struct 字段可以是动态 array<标量>；与标量字段共存。
    {
        auto prog = Parser::parse(
            "struct S { a: array<int>; x: int; }\n"
            "let s: S = S { a: [1, 2], x: 9 };");
        CHECK(prog.stmts[0]->kind == Stmt::Kind::StructDecl);
        CHECK(prog.stmts[0]->fields.size() == 2);
        CHECK(prog.stmts[0]->fields[0].second == "array<int>");
        CHECK(prog.stmts[1]->ty.has_value() && *prog.stmts[1]->ty == "S");
    }

    // 布局：动态字段占 3 个连续 descriptor 槽（data/len/cap）+ 标量 1 槽；
    // 局部 s/t 各 4 槽，字段向低地址展开（帧尾另有深拷贝临时槽）。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "let s: S = S { a: [1, 2], x: 9 };\n"
            "let t: S = s;\n"
            "print(s.a[0], t.x);");
        CHECK(a.find("str x0, [x29, #-8]") != std::string::npos);   // s.a.data
        CHECK(a.find("str x9, [x29, #-16]") != std::string::npos);  // s.a.len
        CHECK(a.find("str x9, [x29, #-24]") != std::string::npos);  // s.a.cap
        CHECK(a.find("str x9, [x29, #-32]") != std::string::npos);  // s.x
        CHECK(a.find("str x0, [x29, #-40]") != std::string::npos);  // t.a.data
        CHECK(a.find("str x9, [x29, #-56]") != std::string::npos);  // t.a.cap
        CHECK(a.find("str x9, [x29, #-64]") != std::string::npos);  // t.x
        CHECK(a.find("mov x0, #32") != std::string::npos);          // cap=max(2,4)*8
        CHECK(count_substr(code_only(a), "bl _malloc") == 2);       // 字面量 + t 深拷贝
        CHECK(a.find("L.copy.words.") != std::string::npos);        // 深拷贝循环
        CHECK(count_substr(code_only(a), "bl _free") >= 2);         // 作用域结束 drop
    }

    // 入口清零：break/return 跳过 let 时收尾 drop 只能 free(NULL)，
    // 因此函数/main 入口把动态字段的 data/len/cap 三槽清零。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "let s: S = S { a: [1, 2], x: 9 };\n"
            "print(len(s.a), s.x);");
        size_t z = a.find("str xzr, [x29, #-8]");
        size_t m = a.find("bl _malloc", a.find("_main:"));
        CHECK(z != std::string::npos && m != std::string::npos && z < m);
        CHECK(a.find("str xzr, [x29, #-16]") != std::string::npos);
        CHECK(a.find("str xzr, [x29, #-24]") != std::string::npos);
    }
    {
        // break 可能跳过 let：循环体作用域仍按计划 drop（入口已清零，运行期安全）。
        std::string a = asm_of(
            "struct S { a: array<int>; }\n"
            "let i: int = 0;\n"
            "while (i < 2) {\n"
            "  if (i == 0) { i = i + 1; break; }\n"
            "  let s: S = S { a: [1] };\n"
            "  i = i + 1;\n"
            "}\n"
            "print(i);");
        CHECK(a.find("bl _free") != std::string::npos);
        CHECK(a.find("str xzr, [x29, #-16]") != std::string::npos);  // 循环体 s.a.data
    }

    // 读写：s.a[i] 常量/运行时下标都读 len 槽做边界检查；push 走扩容路径。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "let s: S = S { a: [1, 2], x: 9 };\n"
            "s.a[0] = 7;\n"
            "let i: int = 1;\n"
            "s.a[i] = 8;\n"
            "push(s.a, 3);\n"
            "print(len(s.a), s.a[0], s.a[i]);");
        CHECK(a.find("ldr x9, [x29, #-16]") != std::string::npos);  // len 运行时读取
        CHECK(a.find("cmp x10, x11") != std::string::npos);
        CHECK(a.find("b.hs L.dbounds.fail.") != std::string::npos);
        CHECK(a.find("bl _tenet_bounds_fail") != std::string::npos);
        CHECK(a.find("L.dyn.grow.") != std::string::npos);
        CHECK(a.find("L.dyn.grow.copy") != std::string::npos);
        CHECK(a.find("str x11, [x14, x9, lsl #3]") != std::string::npos);  // push 写元素
    }

    // 空动态数组字段：cap 至少 4；push 在 len==cap 时扩容。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; }\n"
            "let s: S = S { a: [] };\n"
            "push(s.a, 1);\n"
            "print(len(s.a), s.a[0]);");
        CHECK(a.find("mov x0, #32") != std::string::npos);  // 空数组 cap=4 * 8
        CHECK(a.find("L.dyn.grow.") != std::string::npos);
        CHECK(a.find("add x12, x10, x10") != std::string::npos);  // newcap = cap*2
    }

    // 深拷贝：let t = s 的每个动态字段独立 malloc；t.a[0] 不影响 s.a[0]。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "let s: S = S { a: [1, 2], x: 9 };\n"
            "let t: S = s;\n"
            "t.a[0] = 5;\n"
            "print(s.a[0], t.a[0]);");
        CHECK(count_substr(code_only(a), "bl _malloc") == 2);
        CHECK(a.find("L.copy.words.") != std::string::npos);
        CHECK(a.find("str x10, [x14, x10, lsl #3]") != std::string::npos ||
              a.find("str x9, [x14, x10, lsl #3]") != std::string::npos);
    }

    // 整体字段赋值 s.a = [..] / s.a = t.a：右侧先构造/深拷贝，再 drop 旧 descriptor。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "let s: S = S { a: [1], x: 2 };\n"
            "s.a = [5, 6];\n"
            "print(len(s.a), s.a[1]);");
        CHECK(count_substr(code_only(a), "bl _malloc") == 2);   // 初始化 + 字段赋值
        CHECK(count_substr(code_only(a), "bl _free") >= 2);     // 旧字段 + 作用域
        CHECK(a.find("L.dyn.grow.") == std::string::npos);
    }
    {
        std::string a = asm_of(
            "struct S { a: array<int>; }\n"
            "let s: S = S { a: [1] };\n"
            "let t: S = S { a: [2, 3] };\n"
            "s.a = t.a;\n"
            "print(len(s.a), s.a[0]);");
        CHECK(count_substr(code_only(a), "bl _malloc") == 3);   // 两个字面量 + 字段拷贝
        CHECK(count_substr(code_only(a), "bl _free") >= 2);
    }

    // 自赋值 no-op：s = s / s.a = s.a 不 drop 自己、不额外 malloc。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; }\n"
            "let s: S = S { a: [1, 2] };\n"
            "s = s;\n"
            "s.a = s.a;\n"
            "print(len(s.a), s.a[0]);");
        CHECK(count_substr(code_only(a), "bl _malloc") == 1);
        CHECK(count_substr(code_only(a), "bl _free") == 1);
    }
    {
        std::string a = asm_of(
            "struct S { a: array<int>; }\n"
            "let arr: array<S, 1> = [S { a: [1, 2] }];\n"
            "arr[0].a = arr[0].a;\n"
            "print(len(arr[0].a));");
        CHECK(count_substr(code_only(a), "bl _malloc") == 1);
    }

    // 整体 struct 赋值 t = S{..} / t = f()：先求值右侧，再 drop 旧动态字段。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "fn mk() -> S { return S { a: [1], x: 2 }; }\n"
            "let t: S = S { a: [3], x: 4 };\n"
            "t = mk();\n"
            "t = S { a: [5], x: 6 };\n"
            "print(t.a[0], t.x);");
        CHECK(a.find("bl _mk") != std::string::npos);
        CHECK(count_substr(code_only(a), "bl _malloc") >= 3);
        CHECK(count_substr(code_only(a), "bl _free") >= 3);
    }

    // 参数 ABI：struct 总槽（4）指针传递；入口动态字段重新 malloc 深拷贝；
    // sret 返回转移 descriptor 并清空本地（避免二次释放）。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "fn f(v: S) -> S { v.a[0] = 8; return v; }\n"
            "let s: S = S { a: [1, 2], x: 9 };\n"
            "let u: S = f(s);\n"
            "print(u.a[0], s.a[0]);");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("bl _f") != std::string::npos);
        size_t fn = a.find("_f:");
        size_t ret = a.find("L.f.ret");
        CHECK(fn != std::string::npos && ret != std::string::npos && fn < ret);
        std::string body = a.substr(fn, ret - fn);
        CHECK(count_substr(body, "bl _malloc") == 1);        // 参数入口深拷贝
        CHECK(body.find("L.copy.words.") != std::string::npos);
        CHECK(count_substr(body, "str xzr, [x29, #") >= 3);  // 转移后清空本地 descriptor
    }

    // 函数自然落底 / 参数副本在 return 前 drop。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; }\n"
            "fn n(v: S) -> int { return len(v.a); }\n"
            "let s: S = S { a: [1, 2] };\n"
            "print(n(s));");
        CHECK(a.find("_n:") != std::string::npos);
        CHECK(count_substr(code_only(a), "bl _malloc") >= 2);  // 字面量 + 参数深拷贝
        CHECK(count_substr(code_only(a), "bl _free") >= 2);    // 参数副本 + main 的 s
    }

    // 作用域 / break drop：while 体内 struct 动态字段先释放再跳出。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "let i: int = 0;\n"
            "while (i < 1) {\n"
            "  let w: S = S { a: [1, 2], x: 1 };\n"
            "  push(w.a, 3);\n"
            "  print(w.a[0]);\n"
            "  break;\n"
            "}\n"
            "print(0);");
        CHECK(a.find("L.dyn.grow.") != std::string::npos);
        size_t free_pos = a.find("bl _free");
        size_t brk = a.find("b L.exit.");
        CHECK(free_pos != std::string::npos);
        CHECK(brk != std::string::npos && free_pos < brk);
    }

    // 返回值来源：字面量直接构造进 sret；调用链转移。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "fn make() -> S { return S { a: [1, 2], x: 3 }; }\n"
            "fn chain() -> S { return make(); }\n"
            "let m: S = chain();\n"
            "print(m.a[0], m.a[1], m.x);");
        CHECK(a.find("_make:") != std::string::npos);
        CHECK(a.find("_chain:") != std::string::npos);
        CHECK(a.find("bl _make") != std::string::npos);
        CHECK(count_substr(code_only(a), "bl _malloc") >= 1);
    }

    // 固定 array<S, N> 元素：arr[i].a[j] / arr[i].a = [..] / push(arr[i].a, x)。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "let arr: array<S, 2> = [S { a: [1], x: 1 }, S { a: [2], x: 2 }];\n"
            "arr[0].a[0] = 7;\n"
            "arr[1].a = [8, 9];\n"
            "push(arr[0].a, 5);\n"
            "print(arr[0].a[0], arr[1].a[1], len(arr[1].a));");
        CHECK(a.find("L.dbounds.fail.") != std::string::npos);  // 动态字段下标检查
        CHECK(a.find("L.dyn.grow.") != std::string::npos);
        CHECK(count_substr(code_only(a), "bl _malloc") >= 4);
        CHECK(count_substr(code_only(a), "bl _free") >= 3);
    }

    // 动态 array<S> 元素：元素 descriptor 深拷贝、递归 drop、字段整体赋值/写回。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "let d: array<S> = [S { a: [3], x: 3 }];\n"
            "d[0].a[0] = 4;\n"
            "d[0].a = [6, 7];\n"
            "push(d[0].a, 8);\n"
            "push(d, S { a: [5], x: 5 });\n"
            "let e: array<S> = d;\n"
            "print(d[0].a[0], len(d), e[0].x);");
        CHECK(count_substr(code_only(a), "L.dyn.elem.copy") >= 1);
        CHECK(a.find("L.dyn.elem.drop") != std::string::npos);
        CHECK(a.find("L.dyn.grow.") != std::string::npos);
    }

    // bool / float 动态字段：按位模式打包，print 用 %g / true/false。
    {
        std::string a = asm_of(
            "struct F { a: array<float>; }\n"
            "struct B { a: array<bool>; }\n"
            "let f: F = F { a: [1.5, 2.5] };\n"
            "let b: B = B { a: [true, false] };\n"
            "print(f);\n"
            "print(b);\n"
            "print(f.a[0], b.a[1]);\n"
            "push(f.a, 3.5);");
        CHECK(a.find(".asciz \"%g\"") != std::string::npos);
        CHECK(a.find("fmov x9, d9") != std::string::npos);
        CHECK(a.find(".asciz \"true\"") != std::string::npos);
        CHECK(a.find(".asciz \"false\"") != std::string::npos);
        CHECK(a.find(".asciz \"F { \"") != std::string::npos);
        CHECK(a.find(".asciz \"B { \"") != std::string::npos);
        CHECK(a.find("L.dyn.grow.") != std::string::npos);
    }

    // print(struct)：动态字段按 [..] 运行时展开；print(s.a) 直接打印字段。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "let s: S = S { a: [1, 2], x: 9 };\n"
            "print(s);\n"
            "print(s.a);");
        CHECK(a.find(".asciz \"S { \"") != std::string::npos);
        CHECK(a.find(".asciz \"a: \"") != std::string::npos);
        CHECK(a.find(".asciz \"x: \"") != std::string::npos);
        CHECK(count_substr(code_only(a), "L.print.cond.") >= 2);
    }

    // 嵌套 struct 路径：o.in.a 读写 / push / 整体字段赋值。
    {
        std::string a = asm_of(
            "struct I { a: array<int>; }\n"
            "struct O { in: I; z: int; }\n"
            "let o: O = O { in: I { a: [1, 2] }, z: 3 };\n"
            "o.in.a[0] = 5;\n"
            "push(o.in.a, 7);\n"
            "o.in.a = [4, 5, 6];\n"
            "print(o.in.a[0], len(o.in.a), o.z);");
        CHECK(a.find("L.dyn.grow.") != std::string::npos);
        CHECK(a.find("L.dbounds.fail.") != std::string::npos);
        CHECK(count_substr(code_only(a), "bl _malloc") >= 2);
    }

    // 固定 array<P, N> / 动态 array<P> 的 struct 参数与返回值（P 含动态字段）。
    {
        std::string a = asm_of(
            "struct P { a: array<int>; }\n"
            "fn id(x: array<P, 2>) -> array<P, 2> { return x; }\n"
            "let xs: array<P, 2> = [P { a: [1] }, P { a: [2] }];\n"
            "let ys: array<P, 2> = id(xs);\n"
            "print(ys[0].a[0], xs[1].a[0]);");
        CHECK(a.find("_id:") != std::string::npos);
        CHECK(count_substr(code_only(a), "bl _malloc") >= 4);  // 2 元素 × (字面量 + 参数深拷贝)
        CHECK(a.find("L.copy.words.") != std::string::npos);  // 元素内标量动态字段深拷贝
    }
    {
        std::string a = asm_of(
            "struct P { a: array<int>; }\n"
            "fn cl(x: array<P>) -> array<P> { return x; }\n"
            "let d: array<P> = [P { a: [1] }];\n"
            "let e: array<P> = cl(d);\n"
            "print(e[0].a[0], len(e));");
        CHECK(a.find("_cl:") != std::string::npos);
        CHECK(a.find("L.dyn.elem.copy") != std::string::npos);  // 元素递归深拷贝
        CHECK(a.find("L.dyn.elem.drop") != std::string::npos);  // 元素递归 drop
    }

    // sret 返回变量 v：descriptor 转移后清空本地，函数收尾 drop 不再释放。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "fn f() -> S { let v: S = S { a: [1], x: 2 }; return v; }\n"
            "let u = f();\n"
            "print(u.a[0], len(u.a));");
        size_t fn = a.find("_f:");
        size_t ret = a.find("L.f.ret");
        CHECK(fn != std::string::npos && ret != std::string::npos && fn < ret);
        std::string body = a.substr(fn, ret - fn);
        CHECK(count_substr(body, "str xzr, [x29, #") >= 3);
    }

    // 表达式上下文：len(s.a) / len(v[0].a) / arr[i].a[j] 可参与二元运算、
    // 函数实参与 print（类型推断覆盖动态字段）。
    {
        std::string a = asm_of(
            "struct S { a: array<int>; x: int; }\n"
            "fn f(v: array<S>) -> int { return len(v[0].a) + len(v); }\n"
            "fn g(s: S) -> int { return len(s.a) + s.x; }\n"
            "let d: array<S> = [S { a: [1, 2], x: 0 }];\n"
            "let s: S = S { a: [3], x: 4 };\n"
            "let n: int = g(s) + f(d);\n"
            "print(n, d[0].a[1], s.a[0] + 1);");
        CHECK(a.find("_f:") != std::string::npos);
        CHECK(a.find("_g:") != std::string::npos);
        CHECK(a.find("bl _f") != std::string::npos);
        CHECK(a.find("bl _g") != std::string::npos);
    }
    {
        std::string a = asm_of(
            "struct S { a: array<int>; }\n"
            "let d: array<S> = [S { a: [1] }];\n"
            "let x: int = d[0].a[0];\n"
            "print(x);");
        CHECK(a.find("L.dbounds.fail.") != std::string::npos);
    }
    {
        // 函数参数是独立副本：函数内 push/写字段不影响调用方（编译通过 + 参数入口深拷贝）。
        std::string a = asm_of(
            "struct S { a: array<int>; }\n"
            "fn grow(v: array<S>) -> int {\n"
            "  push(v[0].a, 7);\n"
            "  push(v, S { a: [8] });\n"
            "  v[1].a[0] = 99;\n"
            "  return len(v[0].a) + len(v);\n"
            "}\n"
            "let d: array<S> = [S { a: [1] }];\n"
            "print(grow(d), len(d));");
        CHECK(a.find("_grow:") != std::string::npos);
        CHECK(count_substr(code_only(a), "L.dyn.elem.copy") >= 1);
        CHECK(count_substr(code_only(a), "bl _malloc") >= 3);
    }

    // 类型/形态错误
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct S { a: array<P>; }"),
                 "不支持 array");
    CHECK_THROWS(asm_of("struct P { x: int; }\nstruct S { a: array<P>; }"),
                 "array<struct>");
    CHECK_THROWS(asm_of("struct S { a: array<array<int>>; }"), "不支持 array");
    CHECK_THROWS(asm_of("struct S { a: array<array<int>, 2>; }"), "不支持 array");
    CHECK_THROWS(asm_of("struct S { a: array<string>; }"),
                 "只支持 int/float/bool");
    CHECK_THROWS(asm_of("struct S { a: array<int>; }\n"
                        "let s: S = S { a: [1] };\ns.a = [1.5];"),
                 "类型不匹配");
    CHECK_THROWS(asm_of("struct S { a: array<int>; }\n"
                        "struct T { a: array<float>; }\n"
                        "let s: S = S { a: [1] };\n"
                        "let t: T = T { a: [1.5] };\n"
                        "s.a = t.a;"),
                 "类型不匹配");
    CHECK_THROWS(asm_of("struct S { a: array<int>; }\n"
                        "let s: S = S { a: [1] };\n"
                        "let d: array<float> = s.a;"),
                 "类型不匹配");
    CHECK_THROWS(asm_of("struct S { a: array<int>; }\n"
                        "let s: S = S { a: [1] };\n"
                        "let x: int = s.a;"),
                 "不能直接取值");
    CHECK_THROWS(asm_of("struct S { a: array<int>; }\n"
                        "let s: S = S { a: [1] };\n"
                        "s.a[0] = 1.5;"),
                 "类型不匹配");
    CHECK_THROWS(asm_of("struct S { a: array<int>; }\n"
                        "let s: S = S { a: [1] };\n"
                        "push(s.a, 1.5);"),
                 "push 值类型不匹配");
    CHECK_THROWS(asm_of("struct S { a: array<int>; }\n"
                        "let s: S = S { a: [1] };\n"
                        "push(s, 1);"),
                 "不是数组");
    CHECK_THROWS(asm_of("struct S { a: array<int>; }\n"
                        "let s: S = S { a: [1] };\n"
                        "print(len(s));"),
                 "不是数组");
    CHECK_THROWS(asm_of("struct S { a: array<int>; }\n"
                        "let s: S = S { a: [1] };\n"
                        "s.a = 1;"),
                 "初始化");
    CHECK_THROWS(asm_of("struct S { a: array<int>; }\n"
                        "let s: S = S { a: [1] };\n"
                        "let n: int = len(s.a[0]);"),
                 "len");
}

int main() {
    test_lexer();
    test_parser();
    test_backend();
    test_struct_s3a();
    test_array();
    test_array_s3b();
    test_array_s3c();
    test_dynamic_abi();
    test_dynamic_expr_s3c3a();
    test_array_struct_s3c3b1();
    test_dynamic_struct_array_s3c3b2();
    test_nested_array_s3c3c();
    test_fixed_array_abi_s3c3d();
    test_print_aggregate();
    test_dynamic_nested_array_s3c3e();
    test_struct_fixed_array_field_s3d();
    test_struct_dynamic_field_s3e();

    std::cout << "通过 " << (checks - failures) << " / " << checks << " 项检查";
    if (failures > 0) {
        std::cout << "，失败 " << failures << " 项\n";
        return 1;
    }
    std::cout << "\n";
    return 0;
}
