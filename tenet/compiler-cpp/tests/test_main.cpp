// Tenet compiler-cpp 测试套件：镜像 compiler-rs 的 22 个测试。
// 词法/语法用文本断言；代码生成用 LLVM Module 结构断言。
#include <iostream>
#include <string>
#include <vector>

#include "codegen.hpp"
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

// ---- 辅助 ----

static std::vector<llvm::Function*> functions_of(const std::string& src) {
    auto c = Codegen::compile(Parser::parse(src));
    std::vector<llvm::Function*> out;
    for (auto& f : c.mod->functions()) out.push_back(&f);
    return out;
}

static bool function_has_inst(const std::string& src, const std::string& fname,
                              unsigned op) {
    auto c = Codegen::compile(Parser::parse(src));
    auto* f = c.mod->getFunction(fname);
    if (!f) return false;
    for (auto& bb : *f) {
        for (auto& i : bb) {
            if (i.getOpcode() == op) return true;
        }
    }
    return false;
}

// ---- 词法 ----

static void test_lexer() {
    auto toks = Lexer::tokenize("42 3.14 \"hi\" true false");
    CHECK(toks.size() == 6);
    CHECK(toks[0].kind == Kind::Int && toks[0].int_val == 42);
    CHECK(toks[1].kind == Kind::Float && toks[1].float_val == 3.14);
    CHECK(toks[2].kind == Kind::Str && toks[2].str_val == "hi");
    CHECK(toks[3].kind == Kind::True);
    CHECK(toks[4].kind == Kind::False);

    toks = Lexer::tokenize("== != <= >= && || -> = < > !");
    CHECK(toks.size() == 12);  // 11 个运算符 + EOF
    CHECK(toks[0].kind == Kind::Eq && toks[1].kind == Kind::Neq);
    CHECK(toks[2].kind == Kind::Lte && toks[3].kind == Kind::Gte);
    CHECK(toks[4].kind == Kind::And && toks[5].kind == Kind::Or);
    CHECK(toks[6].kind == Kind::Arrow && toks[7].kind == Kind::Assign);
    CHECK(toks[8].kind == Kind::Lt && toks[9].kind == Kind::Gt && toks[10].kind == Kind::Not);

    toks = Lexer::tokenize("let x: int = 1;");
    CHECK(toks[0].kind == Kind::Let && toks[1].kind == Kind::Ident);
    CHECK(toks[3].kind == Kind::IntType && toks[5].kind == Kind::Int);

    toks = Lexer::tokenize("1 // line\n + /* block */ 2");
    CHECK(toks.size() == 4 && toks[1].kind == Kind::Plus);

    toks = Lexer::tokenize("\"a\\nb\\t\\\"c\\\\\"");
    CHECK(toks[0].kind == Kind::Str && toks[0].str_val == "a\nb\t\"c\\");

    toks = Lexer::tokenize("1 +\n2");
    CHECK(toks[0].pos == Position(1, 1) && toks[1].pos == Position(1, 3));
    CHECK(toks[2].pos == Position(2, 1));

    CHECK_THROWS(Lexer::tokenize("\"abc"), "未闭合");
    CHECK_THROWS(Lexer::tokenize("1 @ 2"), "无法识别");
}

// ---- 语法 ----

static void test_parser() {
    auto prog = Parser::parse("let x: int = 42;");
    CHECK(prog.stmts.size() == 1);
    CHECK(prog.stmts[0]->kind == Stmt::Kind::Let);
    CHECK(prog.stmts[0]->name == "x");
    CHECK(prog.stmts[0]->ty.has_value() && *prog.stmts[0]->ty == T_INT);

    prog = Parser::parse("let x: int = 1 + 2 * 3;");
    auto* v = prog.stmts[0]->value.get();
    CHECK(v->kind == Expr::Kind::Binary && v->op == OP_ADD);
    CHECK(v->rhs->kind == Expr::Kind::Binary && v->rhs->op == OP_MUL);

    prog = Parser::parse("fn add(a: int, b: int) -> int { return a + b; }");
    CHECK(prog.stmts[0]->kind == Stmt::Kind::FnDecl);
    CHECK(prog.stmts[0]->name == "add");
    CHECK(prog.stmts[0]->params.size() == 2);
    CHECK(prog.stmts[0]->ret.has_value() && *prog.stmts[0]->ret == T_INT);

    prog = Parser::parse("if (x > 0) { print(1); } else if (x < 0) { print(-1); } else { print(0); }");
    CHECK(prog.stmts[0]->kind == Stmt::Kind::If);
    CHECK(prog.stmts[0]->else_branch.size() == 1);
    CHECK(prog.stmts[0]->else_branch[0]->kind == Stmt::Kind::If);

    prog = Parser::parse("x = f(1, 2);");
    auto* a = prog.stmts[0]->expr.get();
    CHECK(a->kind == Expr::Kind::Assign && a->name == "x");
    CHECK(a->value->kind == Expr::Kind::Call && a->value->name == "f");
    CHECK(a->value->args.size() == 2);

    CHECK_THROWS(Parser::parse("let x: int = 1"), "`;`");
    CHECK_THROWS(Parser::parse("if x > 0 { }"), "`(`");
}

// ---- 代码生成（LLVM Module 结构断言）----

static void test_codegen() {
    // hello：有 main 且调用 printf
    {
        auto c = Codegen::compile(Parser::parse("print(\"hello\");"));
        auto* main = c.mod->getFunction("main");
        CHECK(main != nullptr);
        CHECK(function_has_inst("print(\"hello\");", "main", llvm::Instruction::Call));
    }

    // let int：main 里有 alloca + store
    {
        auto c = Codegen::compile(Parser::parse("let x: int = 42;"));
        auto* main = c.mod->getFunction("main");
        CHECK(main != nullptr);
        bool has_alloca = false, has_store = false;
        for (auto& bb : *main) {
            for (auto& i : bb) {
                if (i.getOpcode() == llvm::Instruction::Alloca) has_alloca = true;
                if (i.getOpcode() == llvm::Instruction::Store) has_store = true;
            }
        }
        CHECK(has_alloca && has_store);
    }

    // 函数声明：add 返回 i64，含 add 指令
    {
        auto c = Codegen::compile(Parser::parse("fn add(a: int, b: int) -> int { return a + b; }"));
        auto* add = c.mod->getFunction("add");
        CHECK(add != nullptr);
        CHECK(add->getReturnType()->isIntegerTy(64));
        CHECK(function_has_inst("fn add(a: int, b: int) -> int { return a + b; }", "add",
                               llvm::Instruction::Add));
    }

    // while → 条件跳转
    {
        auto c = Codegen::compile(Parser::parse("let x: int = 0; while (x < 10) { x = x + 1; }"));
        auto* main = c.mod->getFunction("main");
        CHECK(main != nullptr);
        bool has_cond_br = false, has_icmp = false;
        for (auto& bb : *main) {
            for (auto& i : bb) {
                if (i.getOpcode() == llvm::Instruction::Br) {
                    if (llvm::cast<llvm::BranchInst>(i).isConditional()) has_cond_br = true;
                }
                if (i.getOpcode() == llvm::Instruction::ICmp) has_icmp = true;
            }
        }
        CHECK(has_cond_br && has_icmp);
    }

    // 递归：fib 内部调用 fib
    {
        auto c = Codegen::compile(
            Parser::parse("fn fib(n: int) -> int { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); }"));
        auto* fib = c.mod->getFunction("fib");
        CHECK(fib != nullptr);
        bool calls_fib = false;
        for (auto& bb : *fib) {
            for (auto& i : bb) {
                if (auto* call = llvm::dyn_cast<llvm::CallInst>(&i)) {
                    if (call->getCalledFunction() == fib) calls_fib = true;
                }
            }
        }
        CHECK(calls_fib);
    }

    // 混合数值：sitofp 提升
    // 用变量防止编译期常量折叠（常量会被 LLVM 直接算掉，这是优化成功）
    CHECK(function_has_inst("let y: int = 7; let x = y / 2.0;", "main", llvm::Instruction::SIToFP));

    // 短路：main 里有 phi（&& 结果）
    {
        auto c = Codegen::compile(Parser::parse("let x: bool = true || (1 / 0 == 1);"));
        auto* main = c.mod->getFunction("main");
        CHECK(main != nullptr);
        bool has_phi = false;
        for (auto& bb : *main) {
            for (auto& i : bb) {
                if (i.getOpcode() == llvm::Instruction::PHI) has_phi = true;
            }
        }
        CHECK(has_phi);
    }

    // 错误：缺 return
    CHECK_THROWS(Codegen::compile(Parser::parse("fn f() -> int { let x: int = 1; }")), "末尾没有 return");
    // 错误：保留函数名
    CHECK_THROWS(Codegen::compile(Parser::parse("fn main() { }")), "保留");
    // 错误：未定义变量
    CHECK_THROWS(Codegen::compile(Parser::parse("print(unknown);")), "未定义的变量");
    // 错误：无法推断类型
    CHECK_THROWS(Codegen::compile(Parser::parse("fn f() { } let x = f();")), "无法推断");
}

int main() {
    test_lexer();
    test_parser();
    test_codegen();

    std::cout << "通过 " << (checks - failures) << " / " << checks << " 项检查";
    if (failures > 0) {
        std::cout << "，失败 " << failures << " 项\n";
        return 1;
    }
    std::cout << "\n";
    return 0;
}
