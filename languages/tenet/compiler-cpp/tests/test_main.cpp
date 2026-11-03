// Tenet compiler-cpp 测试套件：镜像 compiler-rs 的测试，并补充 struct v1 / S3a / array v1 / S3b / S3c-1 / S3c-2 / S3c-3a / S3c-3b-1 / S3c-3b-2 / S3c-3c v1/v2 / S3c-3b-3 / S3c-3b-4 / S3c-3d / S3d（struct 固定数组字段）/ print aggregate 用例。
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

static std::string module_ir(const std::string& src) {
    auto c = Codegen::compile(Parser::parse(src));
    std::string ir;
    llvm::raw_string_ostream os(ir);
    c.mod->print(os, nullptr);
    os.flush();
    return ir;
}

/// 统计 IR 文本里某个子串出现的次数（descriptor alloca / 清空槽位断言用）。
static unsigned count_text(const std::string& hay, const std::string& needle) {
    if (needle.empty()) return 0;
    unsigned count = 0;
    size_t pos = 0;
    while ((pos = hay.find(needle, pos)) != std::string::npos) {
        ++count;
        pos += needle.size();
    }
    return count;
}

static unsigned count_array_allocas_in(const std::string& src, const std::string& fname,
                                       uint64_t len, const std::string& elem_ll) {
    auto c = Codegen::compile(Parser::parse(src));
    auto* f = c.mod->getFunction(fname);
    if (!f) return 0;
    unsigned count = 0;
    for (auto& bb : *f) {
        for (auto& i : bb) {
            auto* al = llvm::dyn_cast<llvm::AllocaInst>(&i);
            if (!al) continue;
            auto* at = llvm::dyn_cast<llvm::ArrayType>(al->getAllocatedType());
            if (!at || at->getNumElements() != len) continue;
            auto* et = at->getElementType();
            if (elem_ll == "i64" && et->isIntegerTy(64)) ++count;
            if (elem_ll == "double" && et->isDoubleTy()) ++count;
            if (elem_ll == "i1" && et->isIntegerTy(1)) ++count;
        }
    }
    return count;
}

static unsigned count_array_allocas(const std::string& src, uint64_t len,
                                    const std::string& elem_ll) {
    return count_array_allocas_in(src, "main", len, elem_ll);
}

/// 统计函数内指定标量类型的 alloca 数（struct 扁平字段槽位断言用）。
static unsigned count_scalar_allocas(const std::string& src, const std::string& fname,
                                     const std::string& ll) {
    auto c = Codegen::compile(Parser::parse(src));
    auto* f = c.mod->getFunction(fname);
    if (!f) return 0;
    unsigned count = 0;
    for (auto& bb : *f) {
        for (auto& i : bb) {
            auto* al = llvm::dyn_cast<llvm::AllocaInst>(&i);
            if (!al) continue;
            auto* at = al->getAllocatedType();
            if (ll == "i64" && at->isIntegerTy(64)) ++count;
            if (ll == "double" && at->isDoubleTy()) ++count;
            if (ll == "i1" && at->isIntegerTy(1)) ++count;
        }
    }
    return count;
}

static bool function_calls(const std::string& src, const std::string& fname,
                           const std::string& callee) {
    auto c = Codegen::compile(Parser::parse(src));
    auto* f = c.mod->getFunction(fname);
    if (!f) return false;
    for (auto& bb : *f) {
        for (auto& i : bb) {
            auto* call = llvm::dyn_cast<llvm::CallInst>(&i);
            if (call && call->getCalledFunction() &&
                call->getCalledFunction()->getName() == callee) {
                return true;
            }
        }
    }
    return false;
}

/// 统计函数内对某函数的调用次数（动态数组 malloc/free 断言用）。
static unsigned count_calls_in(const std::string& src, const std::string& fname,
                               const std::string& callee) {
    auto c = Codegen::compile(Parser::parse(src));
    auto* f = c.mod->getFunction(fname);
    if (!f) return 0;
    unsigned count = 0;
    for (auto& bb : *f) {
        for (auto& i : bb) {
            auto* call = llvm::dyn_cast<llvm::CallInst>(&i);
            if (call && call->getCalledFunction() &&
                call->getCalledFunction()->getName() == callee) {
                ++count;
            }
        }
    }
    return count;
}

/// 统计函数内名字以 prefix 开头的基本块数（LLVM 对重名块自动追加数字后缀，
/// 因此前缀匹配能同时覆盖 `pr.cond` / `pr.cond12` 这类重命名块）。
static unsigned count_blocks_named(const std::string& src, const std::string& fname,
                                   const std::string& prefix) {
    auto c = Codegen::compile(Parser::parse(src));
    auto* f = c.mod->getFunction(fname);
    if (!f) return 0;
    unsigned count = 0;
    for (auto& bb : *f) {
        if (std::string(bb.getName()).rfind(prefix, 0) == 0) ++count;
    }
    return count;
}

/// S3c-1 动态数组会生成较多基本块：用 LLVM verifier 确认生成的模块结构合法。
static bool module_verifies(const std::string& src) {
    auto c = Codegen::compile(Parser::parse(src));
    std::string err;
    llvm::raw_string_ostream os(err);
    bool broken = llvm::verifyModule(*c.mod, &os);
    os.flush();
    return !broken;
}

/// printf 调用的可变参数里是否有指定 i64 常量（用于验证 len 是编译期常量）。
static bool printf_has_int_constant(const std::string& src, int64_t value) {
    auto c = Codegen::compile(Parser::parse(src));
    auto* f = c.mod->getFunction("main");
    if (!f) return false;
    for (auto& bb : *f) {
        for (auto& i : bb) {
            auto* call = llvm::dyn_cast<llvm::CallInst>(&i);
            if (!call || !call->getCalledFunction() ||
                call->getCalledFunction()->getName() != "printf") {
                continue;
            }
            for (unsigned a = 1; a < call->arg_size(); ++a) {
                auto* ci = llvm::dyn_cast<llvm::ConstantInt>(call->getArgOperand(a));
                if (ci && ci->getSExtValue() == value) return true;
            }
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

    toks = Lexer::tokenize("struct Point { x: int; } p.x");
    CHECK(toks[0].kind == Kind::Struct);
    CHECK(toks[1].kind == Kind::Ident && toks[1].str_val == "Point");
    CHECK(toks[8].kind == Kind::Ident && toks[8].str_val == "p");
    CHECK(toks[9].kind == Kind::Dot);
    CHECK(toks[10].kind == Kind::Ident && toks[10].str_val == "x");
    CHECK(toks[11].kind == Kind::Eof);

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
    CHECK(a->kind == Expr::Kind::Assign);
    CHECK(a->lhs->kind == Expr::Kind::Var && a->lhs->name == "x");
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

    // ---- 混合类型（string × 非 string）：前端报错，带 [行:列] ----

    {
        // 隐式标注：推断阶段报混合类型错误
        bool threw = false;
        try {
            Codegen::compile(Parser::parse("let a: string = \"x\";\nlet b = a + 1;"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.message == "运算符 `+` 不能作用于 string 和 int");
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 9);
        }
        CHECK(threw);
    }
    {
        // 显式标注：代码生成阶段同样报混合类型错误（不再漏出 LLVM 验证器）
        bool threw = false;
        try {
            Codegen::compile(Parser::parse("let a: string = \"x\";\nlet b: int = a + 1;"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.message == "运算符 `+` 不能作用于 string 和 int");
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 14);
        }
        CHECK(threw);
    }
    CHECK_THROWS(Codegen::compile(Parser::parse("let a: string = \"x\";\nlet b = a < 1;")),
                 "运算符 `<` 不能作用于 string 和 int");

    // ---- bool 不能参与数值/比较运算 ----

    CHECK_THROWS(Codegen::compile(Parser::parse("let b = true + 1;")),
                 "运算符 `+` 不能作用于 bool 和 int");
    CHECK_THROWS(Codegen::compile(Parser::parse("let b = 1 && true;")),
                 "运算符 `&&` 只能作用于 bool，实际为 int");
    CHECK_THROWS(Codegen::compile(Parser::parse("let b = !5;")),
                 "运算符 `!` 只能作用于 bool，实际为 int");
    CHECK_THROWS(Codegen::compile(Parser::parse("let b = 5.5 % 2;")), "运算符 `%` 只能作用于 int");
    CHECK_THROWS(Codegen::compile(Parser::parse("if (1) { print(1); }")), "条件表达式需要 bool");

    // ---- 声明 / 赋值 / 调用 / 返回类型核对 ----

    CHECK_THROWS(Codegen::compile(Parser::parse("let b: int = \"x\";")),
                 "`b` 初始化类型不匹配：标注 int，实际 string");
    CHECK_THROWS(Codegen::compile(Parser::parse("let b: int = 1;\nb = \"x\";")),
                 "赋值类型不匹配：`b` 是 int，右侧是 string");
    CHECK_THROWS(Codegen::compile(Parser::parse("fn f(x: int) -> int { return x; }\nf(\"s\");")),
                 "函数 `f` 参数 0 类型不匹配：期望 int，实际 string");
    CHECK_THROWS(Codegen::compile(Parser::parse("fn f(x: int) -> int { return x; }\nf(1, 2);")),
                 "函数 `f` 需要 1 个参数，实际传入 2 个");
    CHECK_THROWS(Codegen::compile(Parser::parse("fn f() -> int { return \"s\"; }")),
                 "函数 `f` 返回类型不匹配：声明 int，实际 string");
    CHECK_THROWS(Codegen::compile(Parser::parse("fn f() { return 1; }")),
                 "函数 `f` 没有返回类型，不能 return 值");
}

// ---- struct v1 ----

static void test_struct() {
    // 语法：struct 声明 / 字面量 / 字段访问 / 字段赋值
    auto prog = Parser::parse(
        "struct Point { x: int; y: float; }\n"
        "let p: Point = Point { x: 1, y: 2.0 };\n"
        "let q = p;\n"
        "p.x = p.x + 1;");
    CHECK(prog.stmts.size() == 4);
    CHECK(prog.stmts[0]->kind == Stmt::Kind::StructDecl && prog.stmts[0]->name == "Point");
    CHECK(prog.stmts[0]->fields.size() == 2);
    CHECK(prog.stmts[0]->fields[0].first == "x" && prog.stmts[0]->fields[0].second == T_INT);
    CHECK(prog.stmts[0]->fields[1].first == "y" && prog.stmts[0]->fields[1].second == T_FLOAT);
    CHECK(prog.stmts[1]->kind == Stmt::Kind::Let && prog.stmts[1]->name == "p");
    CHECK(prog.stmts[1]->ty.has_value() && *prog.stmts[1]->ty == "Point");
    CHECK(prog.stmts[1]->value->kind == Expr::Kind::StructLit);
    CHECK(prog.stmts[1]->value->name == "Point" && prog.stmts[1]->value->init_fields.size() == 2);
    CHECK(prog.stmts[1]->value->init_fields[0].first == "x");
    CHECK(prog.stmts[1]->value->init_fields[1].first == "y");
    CHECK(prog.stmts[2]->value->kind == Expr::Kind::Var && prog.stmts[2]->value->name == "p");
    auto* assign = prog.stmts[3]->expr.get();
    CHECK(assign->kind == Expr::Kind::Assign);
    CHECK(assign->lhs->kind == Expr::Kind::Field && assign->lhs->field == "x");
    CHECK(assign->lhs->base->kind == Expr::Kind::Var && assign->lhs->base->name == "p");
    CHECK(assign->value->kind == Expr::Kind::Binary);
    CHECK(assign->value->lhs->kind == Expr::Kind::Field && assign->value->lhs->field == "x");

    CHECK_THROWS(Parser::parse("1 = 2;"), "赋值左侧必须是变量或字段");
    CHECK_THROWS(Parser::parse("(a + b) = 1;"), "赋值左侧必须是变量或字段");

    // 代码生成：字段扁平化为独立 alloca，字段读写正常
    {
        auto c = Codegen::compile(Parser::parse(
            "struct Point { x: int; y: int; }\n"
            "let p: Point = Point { x: 1, y: 2 };\n"
            "p.x = p.x + 1;\n"
            "p = Point { x: 3, y: 4 };\n"
            "print(p.x, p.y);"));
        auto* main = c.mod->getFunction("main");
        CHECK(main != nullptr);
        unsigned int_alloca = 0, loads = 0, stores = 0, adds = 0;
        for (auto& bb : *main) {
            for (auto& i : bb) {
                if (auto* al = llvm::dyn_cast<llvm::AllocaInst>(&i)) {
                    if (al->getAllocatedType()->isIntegerTy(64)) ++int_alloca;
                }
                if (i.getOpcode() == llvm::Instruction::Load) ++loads;
                if (i.getOpcode() == llvm::Instruction::Store) ++stores;
                if (i.getOpcode() == llvm::Instruction::Add) ++adds;
            }
        }
        CHECK(int_alloca >= 2);
        CHECK(loads >= 3);
        CHECK(stores >= 2);
        CHECK(adds >= 1);
    }

    // 类型推断 + struct 变量整体赋值（逐字段拷贝）
    {
        auto c = Codegen::compile(Parser::parse(
            "struct Point { x: int; y: int; }\n"
            "let p = Point { x: 1, y: 2 };\n"
            "let q = Point { x: 0, y: 0 };\n"
            "q = p;\n"
            "print(q.x, q.y);"));
        auto* main = c.mod->getFunction("main");
        CHECK(main != nullptr);
        unsigned loads = 0, stores = 0;
        for (auto& bb : *main) {
            for (auto& i : bb) {
                if (i.getOpcode() == llvm::Instruction::Load) ++loads;
                if (i.getOpcode() == llvm::Instruction::Store) ++stores;
            }
        }
        CHECK(loads >= 4);
        CHECK(stores >= 6);
    }

    // 值拷贝：p/q 各有一组 x/y 槽位（int + double）
    {
        auto c = Codegen::compile(Parser::parse(
            "struct Point { x: int; y: float; }\n"
            "let p: Point = Point { x: 1, y: 2.0 };\n"
            "let q = p;\n"
            "q.x = 9;\n"
            "print(p.x, q.x, p.y, q.y);"));
        auto* main = c.mod->getFunction("main");
        CHECK(main != nullptr);
        unsigned int_alloca = 0, double_alloca = 0;
        for (auto& bb : *main) {
            for (auto& i : bb) {
                if (auto* al = llvm::dyn_cast<llvm::AllocaInst>(&i)) {
                    if (al->getAllocatedType()->isIntegerTy(64)) ++int_alloca;
                    if (al->getAllocatedType()->isDoubleTy()) ++double_alloca;
                }
            }
        }
        CHECK(int_alloca >= 2);
        CHECK(double_alloca >= 2);
    }

    // 错误：缺字段 / 未知字段 / 重复字段 / 字段类型不匹配 / 未知 struct
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; y: int; }\nlet p: Point = Point { x: 1 };")),
        "struct `Point` 缺少字段 `y`");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nlet p: Point = Point { x: 1, z: 2 };")),
        "struct `Point` 没有字段 `z`");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nlet p: Point = Point { x: 1, x: 2 };")),
        "字段 `x` 重复初始化");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nlet p: Point = Point { x: \"s\" };")),
        "struct `Point` 字段 `x` 类型不匹配：需要 int，实际 string");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nlet p = Nope { x: 1 };")),
        "未定义的 struct `Nope`");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct A { x: int; }\nstruct B { y: int; }\nlet p: A = B { y: 1 };")),
        "`p` 标注为 A，但字面量是 B");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nlet p: Point = Point { x: 1 };\np.z = 1;")),
        "struct `Point` 没有字段 `z`");

    // S3a：struct 参数/返回值改为指针 ABI（详细用例见 test_struct_s3a）
    {
        auto ir = module_ir(
            "struct Point { x: int; }\nfn f(p: Point) -> int { return p.x; }");
        CHECK(ir.find("define i64 @f(ptr %p0)") != std::string::npos);
    }
    {
        auto ir = module_ir(
            "struct Point { x: int; }\nfn f() -> Point { return Point { x: 1 }; }");
        CHECK(ir.find("define void @f(ptr %sret)") != std::string::npos);
    }
    // print(struct) 已支持（详细用例见 test_print_aggregate）
    CHECK(module_verifies(
        "struct Point { x: int; }\nlet p: Point = Point { x: 1 };\nprint(p);"));
    CHECK_THROWS(
        Codegen::compile(Parser::parse("let x: int = 1;\nx.y = 2;")),
        "`x` 不是 struct，不能写字段 `y`");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\nlet p = P { x: 1 };\n"
            "let b: int = (p = P { x: 2 }) + 1;")),
        "运算符 `+` 不能作用于 struct 值");

    // 错误：struct 声明本身（字段类型 / 空 struct / 重复字段 / 重复定义）
    CHECK_THROWS(Codegen::compile(Parser::parse("struct Bad { s: string; }")),
                 "只支持 int/float/bool");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct Empty { }")), "至少需要一个字段");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct P { x: int; x: int; }")), "字段 `x` 重复");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct P { x: int; }\nstruct P { y: int; }")),
                 "struct `P` 重复定义");
    // S3a：嵌套 struct 声明合法（字段类型可以是另一个 struct）
    {
        auto prog = Parser::parse("struct Inner { x: int; }\nstruct Outer { i: Inner; }");
        CHECK(prog.stmts.size() == 2 && prog.stmts[1]->name == "Outer" &&
              prog.stmts[1]->fields.size() == 1 &&
              prog.stmts[1]->fields[0].second == "Inner");
    }
    CHECK_THROWS(Parser::parse("struct int { x: int; }"), "期望 struct 名");

    // 错误带 [行:列]
    {
        bool threw = false;
        try {
            Codegen::compile(Parser::parse(
                "struct Point { x: int; }\nlet p: Point = Point { x: \"s\" };"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value());
            CHECK(e.pos->line == 2);
            CHECK(e.str().rfind("[2:", 0) == 0);
            CHECK(e.message.find("字段 `x` 类型不匹配") != std::string::npos);
        }
        CHECK(threw);
    }
}

// ---- S3a：嵌套 struct + struct 参数/返回值 ----

static void test_struct_s3a() {
    // 语法：嵌套字段类型 / 嵌套字面量 / 链式字段 / struct 参数与返回类型
    {
        auto prog = Parser::parse(
            "struct Point { x: int; y: int; }\n"
            "struct Line { a: Point; b: Point; }\n"
            "let l: Line = Line { a: Point { x: 1, y: 2 }, b: Point { x: 3, y: 4 } };\n"
            "let z = l.a.x;");
        CHECK(prog.stmts.size() == 4);
        CHECK(prog.stmts[1]->fields.size() == 2 && prog.stmts[1]->fields[0].second == "Point" &&
              prog.stmts[1]->fields[1].second == "Point");
        auto* lit = prog.stmts[2]->value.get();
        CHECK(lit->kind == Expr::Kind::StructLit && lit->name == "Line");
        CHECK(lit->init_fields.size() == 2 &&
              lit->init_fields[0].second->kind == Expr::Kind::StructLit &&
              lit->init_fields[0].second->name == "Point");
        auto* field = prog.stmts[3]->value.get();
        CHECK(field->kind == Expr::Kind::Field && field->field == "x");
        CHECK(field->base->kind == Expr::Kind::Field && field->base->field == "a");
        CHECK(field->base->base->kind == Expr::Kind::Var && field->base->base->name == "l");

        prog = Parser::parse(
            "struct Point { x: int; }\nstruct Line { a: Point; b: Point; }\n"
            "fn mid(l: Line) -> Point { return Point { x: l.a.x }; }");
        auto* fn = prog.stmts[2].get();
        CHECK(fn->kind == Stmt::Kind::FnDecl && fn->params.size() == 1 &&
              fn->params[0].first == "l" && fn->params[0].second == "Line");
        CHECK(fn->ret.has_value() && *fn->ret == "Point");
    }

    // 扁平布局：嵌套字段 a.x / a.y / b.x / b.y 是四个独立 i64 槽位；链式读写正常
    {
        auto src =
            "struct Point { x: int; y: int; }\n"
            "struct Line { a: Point; b: Point; }\n"
            "let l: Line = Line { a: Point { x: 1, y: 2 }, b: Point { x: 3, y: 4 } };\n"
            "l.a.x = 9;\n"
            "l.b.y = l.b.y + 1;\n"
            "print(l.a.x, l.b.y);";
        auto ir = module_ir(src);
        CHECK(count_scalar_allocas(src, "main", "i64") == 4);
        CHECK(ir.find("alloca i64") != std::string::npos);
        CHECK(ir.find("load i64") != std::string::npos);
        CHECK(ir.find("store i64") != std::string::npos);
        // struct 不生成 LLVM 聚合类型，只有扁平字段槽 + [N x i64] ABI 缓冲
        CHECK(ir.find("%Line =") == std::string::npos);
        CHECK(ir.find("%Point =") == std::string::npos);
    }

    // 嵌套 struct 整体拷贝：l / m 各四个槽位，m.a.x = 99 只写 m 的槽
    {
        auto src =
            "struct Point { x: int; y: int; }\n"
            "struct Line { a: Point; b: Point; }\n"
            "let l: Line = Line { a: Point { x: 1, y: 2 }, b: Point { x: 3, y: 4 } };\n"
            "let m = l;\n"
            "m.a.x = 99;\n"
            "print(l.a.x, m.a.x);";
        CHECK(count_scalar_allocas(src, "main", "i64") == 8);
        auto ir = module_ir(src);
        CHECK(ir.find("store i64 99") != std::string::npos);
    }

    // struct 参数 ABI：指针参数 + 入口逐字段拷贝到本地槽位（参数按值拷贝）
    {
        auto src =
            "struct Point { x: int; y: int; }\n"
            "fn bump(p: Point) -> int { p.x = 9; return p.x; }\n"
            "let p: Point = Point { x: 1, y: 2 };\n"
            "let r: int = bump(p);\n"
            "print(p.x, r);";
        auto ir = module_ir(src);
        CHECK(ir.find("define i64 @bump(ptr %p0)") != std::string::npos);
        CHECK(count_scalar_allocas(src, "bump", "i64") == 2);
        CHECK(ir.find("getelementptr [2 x i64], ptr %p0") != std::string::npos);
        CHECK(ir.find("store i64 9, ptr %x") != std::string::npos);
    }

    // struct 返回值 ABI：隐藏 ptr %sret 第一参数 + 函数返回 void + 调用方结果缓冲
    {
        auto src =
            "struct Point { x: int; y: int; }\n"
            "fn make() -> Point { return Point { x: 7, y: 8 }; }\n"
            "let p = make();\n"
            "print(p.x, p.y);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @make(ptr %sret)") != std::string::npos);
        CHECK(ir.find("alloca [2 x i64]") != std::string::npos);
        CHECK(ir.find("call void @make(ptr %make.sret)") != std::string::npos);
        CHECK(function_calls(src, "main", "make"));
    }

    // 嵌套 struct 参数 + struct 返回值（sret 在参数最前）
    {
        auto src =
            "struct Point { x: int; y: int; }\n"
            "struct Line { a: Point; b: Point; }\n"
            "fn mid(l: Line) -> Point {\n"
            "    return Point { x: (l.a.x + l.b.x) / 2, y: (l.a.y + l.b.y) / 2 };\n"
            "}\n"
            "let l: Line = Line { a: Point { x: 0, y: 0 }, b: Point { x: 10, y: 20 } };\n"
            "let m: Point = mid(l);\n"
            "print(m.x, m.y);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @mid(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(ir.find("call void @mid(ptr %mid.sret, ptr %mid.arg0)") != std::string::npos);
        CHECK(function_calls(src, "main", "mid"));
    }

    // 多 struct 参数：指针/标量按声明顺序混合
    {
        auto src =
            "struct Point { x: int; }\n"
            "struct Line { a: Point; b: Point; }\n"
            "fn f(a: Point, n: int, b: Line) -> int { return a.x + n + b.a.x + b.b.x; }";
        auto ir = module_ir(src);
        CHECK(ir.find("define i64 @f(ptr %p0, i64 %p1, ptr %p2)") != std::string::npos);
        CHECK(count_scalar_allocas(src, "f", "i64") == 4);
    }

    // struct 返回值可用于 let / 整体赋值 / 嵌套调用 / 返回
    {
        auto src =
            "struct Point { x: int; }\n"
            "fn make() -> Point { return Point { x: 5 }; }\n"
            "fn id(p: Point) -> Point { return p; }\n"
            "fn wrap() -> Point { return id(Point { x: 6 }); }\n"
            "let a: Point = make();\n"
            "let b = wrap();\n"
            "a = make();\n"
            "print(a.x, b.x);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @id(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(ir.find("define void @wrap(ptr %sret)") != std::string::npos);
        CHECK(function_calls(src, "main", "make"));
        CHECK(function_calls(src, "wrap", "id"));
    }

    // 嵌套字面量直接作为 struct 实参
    {
        auto src =
            "struct Point { x: int; y: int; }\n"
            "struct Line { a: Point; b: Point; }\n"
            "fn mid(l: Line) -> Point { return Point { x: l.a.x, y: l.b.y }; }\n"
            "let p = mid(Line { a: Point { x: 1, y: 2 }, b: Point { x: 3, y: 4 } });\n"
            "print(p.x, p.y);";
        auto ir = module_ir(src);
        CHECK(ir.find("call void @mid(ptr %mid.sret, ptr %mid.arg0)") != std::string::npos);
    }

    // float / bool 字段按布局打包：float bitcast，bool zext/trunc
    {
        auto src =
            "struct S { f: float; b: bool; }\n"
            "fn id(s: S) -> S { return s; }\n"
            "let s = S { f: 2.5, b: true };\n"
            "let t = id(s);\n"
            "print(t.f, t.b);";
        auto ir = module_ir(src);
        CHECK(count_scalar_allocas(src, "id", "double") == 1);
        CHECK(count_scalar_allocas(src, "id", "i1") == 1);
        CHECK(ir.find("bitcast i64") != std::string::npos);
        CHECK(ir.find("trunc i64") != std::string::npos);
    }

    // struct 声明允许前向引用（先收集再校验）
    {
        auto src =
            "struct Outer { inner: Inner; }\n"
            "struct Inner { x: int; }\n"
            "let o = Outer { inner: Inner { x: 1 } };\n"
            "print(o.inner.x);";
        auto ir = module_ir(src);
        CHECK(count_scalar_allocas(src, "main", "i64") == 1);
        CHECK(ir.find("define") != std::string::npos);
    }

    // 错误：循环嵌套（直接 / 间接），带 [行:列]
    CHECK_THROWS(Codegen::compile(Parser::parse("struct A { a: A; }")), "struct 循环嵌套");
    CHECK_THROWS(
        Codegen::compile(Parser::parse("struct A { b: B; }\nstruct B { a: A; }")),
        "A -> B -> A");
    {
        bool threw = false;
        try {
            Codegen::compile(Parser::parse("struct A { b: B; }\nstruct B { a: A; }"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 1);
            CHECK(e.str().rfind("[1:", 0) == 0);
        }
        CHECK(threw);
    }

    // 错误：array 字段 / 未定义字段类型
    CHECK_THROWS(Codegen::compile(Parser::parse("struct S { a: array<int>; }")),
                 "只支持 int/float/bool");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct S { a: Nope; }")), "未定义");

    // 错误：中间 struct 字段不能直接读取/赋值，必须访问到标量叶子
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nstruct Line { a: Point; b: Point; }\n"
            "let l = Line { a: Point { x: 1 }, b: Point { x: 2 } };\nprint(l.a);")),
        "请继续访问到标量字段");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nstruct Line { a: Point; b: Point; }\n"
            "let l = Line { a: Point { x: 1 }, b: Point { x: 2 } };\n"
            "l.a = Point { x: 3 };")),
        "请继续访问到标量字段");

    // 错误：嵌套字段不存在 / 嵌套字面量缺字段 / 嵌套字面量类型不符
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nstruct Line { a: Point; b: Point; }\n"
            "let l = Line { a: Point { x: 1 }, b: Point { x: 2 } };\nprint(l.a.z);")),
        "struct `Point` 没有字段 `z`");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; y: int; }\nstruct Line { a: Point; b: Point; }\n"
            "let l = Line { a: Point { x: 1 }, b: Point { x: 1, y: 2 } };")),
        "struct `Point` 缺少字段 `y`");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nstruct Other { z: int; }\n"
            "struct Line { a: Point; b: Point; }\n"
            "let l = Line { a: Other { z: 1 }, b: Point { x: 2 } };")),
        "字段 `a` 需要 `Point`，实际字面量是 `Other`");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nstruct Line { a: Point; b: Point; }\n"
            "let l = Line { a: Point { x: \"s\" }, b: Point { x: 2 } };")),
        "字段 `a.x` 类型不匹配：需要 int，实际 string");

    // 错误：aggregate 表达式（调用结果）仍不能直接 print；变量已支持。
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\n"
            "fn make() -> Point { return Point { x: 1 }; }\nprint(make());")),
        "print 不支持 struct");
    // 其他 struct 变量可直接 print（详细用例见 test_print_aggregate）
    CHECK(module_verifies(
        "struct Point { x: int; }\nlet p = Point { x: 1 };\nprint(p);"));

    // 错误：struct 实参类型不符（变量 / 字面量）
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nstruct Other { y: int; }\n"
            "fn f(p: Point) -> int { return p.x; }\n"
            "let q = Other { y: 1 };\nf(q);")),
        "需要 Point，实际是 Other");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nstruct Other { y: int; }\n"
            "fn f(p: Point) -> int { return p.x; }\nf(Other { y: 1 });")),
        "需要 Point，字面量是 Other");

    // 错误：返回/初始化类型不匹配，以及 return 缺值
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\n"
            "fn make() -> Point { return Point { x: 1 }; }\n"
            "fn g() -> int { return make(); }")),
        "返回类型不匹配：声明 int，实际 Point");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\n"
            "fn make() -> Point { return Point { x: 1 }; }\n"
            "let x: int = make();")),
        "初始化类型不匹配：标注 int，实际 Point");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nfn f() -> Point { return; }")),
        "return 必须带值");
}



static void test_array() {
    // 词法：array 关键字 + 方括号
    {
        auto toks = Lexer::tokenize("array<int> a = [1, 2];");
        CHECK(toks[0].kind == Kind::ArrayType);
        CHECK(toks[1].kind == Kind::Lt);
        CHECK(toks[3].kind == Kind::Gt);
        CHECK(toks[6].kind == Kind::LBracket);
        CHECK(toks[10].kind == Kind::RBracket);
    }

    // 语法：array<T, N> 类型、字面量、下标读、下标写
    {
        auto prog = Parser::parse(
            "let a: array<int, 3> = [1, 2, 3];\n"
            "let n = len(a);\n"
            "a[0] = a[1];");
        CHECK(prog.stmts.size() == 3);
        CHECK(prog.stmts[0]->ty.has_value() && *prog.stmts[0]->ty == "array<int,3>");
        CHECK(prog.stmts[0]->value->kind == Expr::Kind::Array);
        CHECK(prog.stmts[0]->value->args.size() == 3);
        CHECK(prog.stmts[1]->value->kind == Expr::Kind::Call);
        CHECK(prog.stmts[1]->value->name == "len");
        auto* assign = prog.stmts[2]->expr.get();
        CHECK(assign->kind == Expr::Kind::Assign);
        CHECK(assign->lhs->kind == Expr::Kind::Index);
        CHECK(assign->lhs->base->kind == Expr::Kind::Var && assign->lhs->base->name == "a");
        CHECK(assign->lhs->index->kind == Expr::Kind::Int && assign->lhs->index->int_val == 0);
        CHECK(assign->value->kind == Expr::Kind::Index);
    }

    // 代码生成：定长 alloca [3 x i64] + GEP + load/store
    {
        auto src =
            "let a: array<int, 3> = [1, 2, 3];\n"
            "a[0] = a[1] + 1;\n"
            "print(a[0], len(a));";
        auto c = Codegen::compile(Parser::parse(src));
        auto* main = c.mod->getFunction("main");
        CHECK(main != nullptr);
        bool has_gep = false;
        unsigned loads = 0, stores = 0;
        for (auto& bb : *main) {
            for (auto& i : bb) {
                if (i.getOpcode() == llvm::Instruction::GetElementPtr) has_gep = true;
                if (i.getOpcode() == llvm::Instruction::Load) ++loads;
                if (i.getOpcode() == llvm::Instruction::Store) ++stores;
            }
        }
        CHECK(count_array_allocas(src, 3, "i64") == 1);
        CHECK(has_gep);
        CHECK(loads >= 2);
        CHECK(stores >= 4);
    }

    // 逐元素值拷贝：let b = a / b = a
    {
        auto src =
            "let a = [1, 2];\n"
            "let b = a;\n"
            "a[0] = 9;\n"
            "b = a;\n"
            "print(a[0], b[0]);";
        CHECK(count_array_allocas(src, 2, "i64") == 2);
        auto c = Codegen::compile(Parser::parse(src));
        auto* main = c.mod->getFunction("main");
        unsigned loads = 0, stores = 0;
        for (auto& bb : *main) {
            for (auto& i : bb) {
                if (i.getOpcode() == llvm::Instruction::Load) ++loads;
                if (i.getOpcode() == llvm::Instruction::Store) ++stores;
            }
        }
        CHECK(loads >= 6);
        CHECK(stores >= 7);
    }

    // len 是编译期 int 常量
    {
        CHECK(printf_has_int_constant("let a = [1, 2, 3];\nprint(len(a));", 3));
        auto ir = module_ir("let a = [1, 2, 3];\nlet n: int = len(a);\nprint(n);");
        CHECK(ir.find("array") == std::string::npos);
    }

    // float / bool 元素
    {
        CHECK(count_array_allocas("let f: array<float, 2> = [1.5, 2.5];\nprint(f[0], f[1]);", 2,
                                  "double") == 1);
        CHECK(count_array_allocas("let b: array<bool, 2> = [true, false];\nprint(b[0], b[1]);", 2,
                                  "i1") == 1);
    }

    // 常量下标越界：编译期报错（含 [行:列]）
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2];\nprint(a[2]);")),
                 "数组下标 2 越界");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2];\na[2] = 3;")),
                 "数组下标 2 越界");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2];\nprint(a[-1]);")),
                 "数组下标 -1 越界");
    {
        bool threw = false;
        try {
            Codegen::compile(Parser::parse("let a = [1, 2];\nprint(a[2]);"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 9);
            CHECK(e.str().rfind("[2:", 0) == 0);
        }
        CHECK(threw);
    }

    // 动态下标：生成 bounds check，越界调用 tenet_bounds_fail
    {
        auto src =
            "let a: array<int, 2> = [1, 2];\n"
            "let i: int = 2;\n"
            "print(a[i]);";
        CHECK(function_calls(src, "main", "tenet_bounds_fail"));
        auto c = Codegen::compile(Parser::parse(src));
        auto* main = c.mod->getFunction("main");
        bool has_uge = false;
        for (auto& bb : *main) {
            for (auto& i : bb) {
                auto* cmp = llvm::dyn_cast<llvm::ICmpInst>(&i);
                if (cmp && cmp->getPredicate() == llvm::CmpInst::ICMP_UGE) has_uge = true;
            }
        }
        CHECK(has_uge);
    }

    // 下标类型 / 非数组取下标 / 字面量直接取下标
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2];\nprint(a[1.5]);")),
                 "数组下标必须是 int");
    CHECK_THROWS(Codegen::compile(Parser::parse("let x: int = 1;\nprint(x[0]);")),
                 "不是数组，不能取下标");
    CHECK_THROWS(Codegen::compile(Parser::parse("print([1, 2][0]);")),
                 "只支持对数组变量取下标");

    // 元素类型错误 / 混合元素
    CHECK_THROWS(Codegen::compile(Parser::parse("let a: array<int, 2> = [1, 2.0];")),
                 "数组元素 1 类型不匹配");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2.0];")),
                 "数组元素类型不一致");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [\"x\"];")),
                 "只支持 int/float/bool");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [true, 1];")),
                 "数组元素类型不一致");

    // 空数组 / 嵌套 array / array<struct> 元素类型 / struct 字段 array
    CHECK_THROWS(Codegen::compile(Parser::parse("let a: array<int, 1> = [];")), "空数组");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [];")), "空数组");
    // S3c-3c v1：固定嵌套数组字面量已开放（详细用例见 test_nested_array_s3c3c1）。
    CHECK(module_verifies("let a: array<array<int, 1>, 1> = [[1]];"));
    CHECK_THROWS(
        Codegen::compile(Parser::parse("struct P { x: int; }\nlet a: array<P, 1> = [1];")),
        "值必须是字面量、同类型变量或返回 P 的函数调用");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct S { a: array<int>; }")),
                 "只支持 int/float/bool");

    // S3c-2/S3c-3a：array<T> 签名是动态数组（descriptor ABI），参数 / 返回字面量合法；
    // print(array) 已支持（详细用例见 test_print_aggregate）。
    CHECK(module_ir("fn f(a: array<int>) -> int { return len(a); }")
              .find("define i64 @f(ptr %p0)") != std::string::npos);
    CHECK(module_ir("fn f() -> array<int> { return [1]; }")
              .find("define void @f(ptr %sret)") != std::string::npos);
    CHECK(module_verifies("let a = [1, 2];\nprint(a);"));
    CHECK_THROWS(Codegen::compile(Parser::parse("fn f(a: int) -> int { return a; }\nf([1]);")),
                 "数组字面量只能用于");

    // 整体赋值：长度/类型核对
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2];\na = [1, 2, 3];")),
                 "数组赋值长度不匹配");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2];\nlet b = [1.0, 2.0];\na = b;")),
                 "数组赋值类型不匹配");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2];\na = 1;")),
                 "数组赋值必须是");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2];\na = [1.0, 2.0];")),
                 "数组元素 0 类型不匹配");

    // len 参数核对
    CHECK_THROWS(Codegen::compile(Parser::parse("let x = 1;\nprint(len(x));")),
                 "不是数组，不能取 len");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2];\nprint(len(a[0]));")),
                 "`len` 参数必须是数组变量");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2];\nprint(len(a, a));")),
                 "`len` 需要且只需要一个数组参数");
    CHECK_THROWS(Codegen::compile(Parser::parse("fn f(a: int) { }\nlet x = len([1, 2]);")),
                 "`len` 参数必须是数组变量");

    // 运行时库函数名保留
    CHECK_THROWS(Codegen::compile(Parser::parse("fn tenet_bounds_fail(a: int) { }")), "保留");
}

// ---- S3b：定长 array<T, N> 参数 / 返回值 ----

static void test_array_s3b() {
    // 语法：array<T, N>（逗号 + 正整数字面量），AST 保存归一化类型字符串
    {
        auto prog = Parser::parse(
            "let a: array<int, 3> = [1, 2, 3];\n"
            "fn sum(a: array<int, 3>) -> int { return a[0]; }\n"
            "fn make() -> array<float, 2> { return [1.5, 2.5]; }");
        CHECK(prog.stmts[0]->ty.has_value() && *prog.stmts[0]->ty == "array<int,3>");
        CHECK(prog.stmts[1]->params.size() == 1 &&
              prog.stmts[1]->params[0].second == "array<int,3>");
        CHECK(prog.stmts[2]->ret.has_value() && *prog.stmts[2]->ret == "array<float,2>");
        prog = Parser::parse("let a: array<bool,2> = [true, false];");
        CHECK(prog.stmts[0]->ty.has_value() && *prog.stmts[0]->ty == "array<bool,2>");
    }

    // 语法错误：N 必须是正整数（0 / 负数 / 非整数），带 [行:列]
    CHECK_THROWS(Parser::parse("let a: array<int, 0> = [1];"), "必须是正整数");
    CHECK_THROWS(Parser::parse("let a: array<int, -1> = [1];"), "必须是正整数");
    CHECK_THROWS(Parser::parse("let a: array<int, x> = [1];"), "必须是正整数");
    {
        bool threw = false;
        try {
            Parser::parse("let a: array<int, 0> = [1];");
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 1 && e.pos->col == 19);
            CHECK(e.str().rfind("[1:19]", 0) == 0);
        }
        CHECK(threw);
    }

    // 参数 ABI：数组参数传 ptr；返回值用隐藏 ptr %sret、函数返回 void
    {
        auto ir = module_ir("fn sum(a: array<int, 3>) -> int { return a[0]; }");
        CHECK(ir.find("define i64 @sum(ptr %p0)") != std::string::npos);
    }
    {
        auto ir = module_ir("fn make() -> array<int, 3> { return [1, 2, 3]; }");
        CHECK(ir.find("define void @make(ptr %sret)") != std::string::npos);
    }
    {
        auto ir = module_ir(
            "fn mix(a: array<float, 2>, n: int, b: array<bool, 1>) -> array<int, 2> {"
            " return [n, n]; }");
        CHECK(ir.find("define void @mix(ptr %sret, ptr %p0, i64 %p1, ptr %p2)") !=
              std::string::npos);
    }

    // 参数按值传递：入口逐元素拷贝到本地 [N x T]，函数内改元素不影响调用方
    {
        auto src =
            "fn bump(a: array<int, 2>) -> int { a[0] = 9; return a[0]; }\n"
            "let a: array<int, 2> = [1, 2];\n"
            "let r: int = bump(a);\n"
            "print(a[0], r);";
        CHECK(count_array_allocas_in(src, "bump", 2, "i64") == 1);
        auto ir = module_ir(src);
        CHECK(ir.find("getelementptr [2 x i64], ptr %p0") != std::string::npos);
        CHECK(ir.find("getelementptr [2 x i64], ptr %a,") != std::string::npos);
        CHECK(ir.find("store i64 9") != std::string::npos);
        CHECK(ir.find("call i64 @bump(ptr %bump.arg0)") != std::string::npos);
    }

    // sret 返回：调用方分配 [N x T] 结果缓冲，调用 void 函数
    {
        auto src =
            "fn make() -> array<int, 3> { return [7, 8, 9]; }\n"
            "let a = make();\n"
            "print(a[0], a[1], a[2]);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @make(ptr %sret)") != std::string::npos);
        CHECK(ir.find("alloca [3 x i64]") != std::string::npos);
        CHECK(ir.find("call void @make(ptr %make.sret)") != std::string::npos);
        CHECK(function_calls(src, "main", "make"));
    }

    // 返回值可用于 let / 整体赋值 / return（链式）
    {
        auto src =
            "fn make() -> array<int, 3> { return [1, 2, 3]; }\n"
            "fn wrap() -> array<int, 3> { return make(); }\n"
            "let a: array<int, 3> = make();\n"
            "a = make();\n"
            "let b: array<int, 3> = wrap();\n"
            "print(a[0], b[2]);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @wrap(ptr %sret)") != std::string::npos);
        CHECK(function_calls(src, "main", "make"));
        CHECK(function_calls(src, "main", "wrap"));
        CHECK(function_calls(src, "wrap", "make"));
    }

    // 实参：同类型数组变量 / 同长度字面量 / 返回同类型数组的调用
    {
        auto src =
            "fn sum(a: array<int, 3>) -> int { return a[0] + a[1] + a[2]; }\n"
            "fn make() -> array<int, 3> { return [4, 5, 6]; }\n"
            "let a: array<int, 3> = [1, 2, 3];\n"
            "let s1: int = sum(a);\n"
            "let s2: int = sum([7, 8, 9]);\n"
            "let s3: int = sum(make());\n"
            "print(s1, s2, s3);";
        CHECK(function_calls(src, "main", "sum"));
        auto ir = module_ir(src);
        CHECK(ir.find("call i64 @sum(") != std::string::npos);
        CHECK(ir.find("alloca [3 x i64]") != std::string::npos);
        // 参数在函数内是定长数组：len 仍是编译期常量；动态下标仍做越界检查
        auto ir2 = module_ir("fn f(a: array<int, 3>) -> int { return len(a); }");
        CHECK(ir2.find("ret i64 3") != std::string::npos);
        CHECK(function_calls("fn f(a: array<int, 3>, i: int) -> int { return a[i]; }",
                             "f", "tenet_bounds_fail"));
    }

    // 局部变量：array<T, N> 定长标注，可按元素+长度与函数签名匹配
    {
        auto src =
            "fn sum(a: array<int, 3>) -> int { return a[0] + a[1] + a[2]; }\n"
            "let a: array<int, 3> = [1, 2, 3];\n"
            "let b: array<int, 3> = a;\n"
            "let s: int = sum(a);\n"
            "print(s, b[0], len(b));";
        CHECK(module_ir(src).find("call i64 @sum(") != std::string::npos);
    }

    // 字面量推断：`let a = [1, 2, 3]` 的类型是 array<int,3>（长度是类型的一部分）
    {
        auto src =
            "let a = [1, 2, 3];\n"
            "let b: array<int, 3> = a;\n"
            "b[0] = 9;\n"
            "print(a[0], b[0], len(a));";
        CHECK(count_array_allocas(src, 3, "i64") == 2);
        CHECK(printf_has_int_constant(src, 3));
        // 长度不同即类型不匹配：推断出的 array<int,2> 不能初始化 array<int,3>
        CHECK_THROWS(Codegen::compile(Parser::parse(
                         "let a = [1, 2];\nlet b: array<int, 3> = a;")),
                     "长度不匹配");
    }

    // S3c-1：`array<T>` 局部显式标注现在是动态数组（占位报错改为动态数组成功测试）
    {
        auto src = "let a: array<int> = [1, 2];\npush(a, 3);\nprint(len(a), a[2]);";
        CHECK(function_calls(src, "main", "malloc"));
        CHECK(function_calls(src, "main", "free"));
        CHECK(module_verifies(src));
        CHECK(function_calls(
            "let a: array<float> = [1.5];\npush(a, 2.5);\nprint(len(a), a[1]);", "main",
            "malloc"));
    }

    // float / bool 元素数组的参数与返回值
    {
        auto src =
            "fn makef() -> array<float, 2> { return [1.5, 2.5]; }\n"
            "fn idb(b: array<bool, 2>) -> array<bool, 2> { return b; }\n"
            "let f = makef();\n"
            "let b = idb([true, false]);\n"
            "print(f[0], f[1], b[0], b[1]);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @makef(ptr %sret)") != std::string::npos);
        CHECK(ir.find("define void @idb(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(count_array_allocas_in(src, "idb", 2, "i1") == 1);
        CHECK(ir.find("alloca [2 x double]") != std::string::npos);
    }

    // 长度不匹配：声明 / 实参 / 返回值 / 整体赋值
    CHECK_THROWS(Codegen::compile(Parser::parse("let a: array<int, 3> = [1, 2];")),
                 "长度不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn sum(a: array<int, 3>) -> int { return a[0]; }\n"
            "let b: array<int, 2> = [1, 2];\nprint(sum(b));")),
        "长度不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn make2() -> array<int, 2> { return [1, 2]; }\n"
            "fn f() -> array<int, 3> { return make2(); }")),
        "长度不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn make2() -> array<int, 2> { return [1, 2]; }\n"
            "let a: array<int, 3> = make2();")),
        "长度不匹配");
    CHECK_THROWS(Codegen::compile(Parser::parse(
                     "let a: array<int, 3> = [1, 2, 3];\na = [1, 2];")),
                 "数组赋值长度不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<int, 3> = [1, 2, 3];\n"
            "let b: array<int, 2> = [1, 2];\na = b;")),
        "数组赋值长度不匹配");

    // 元素类型不匹配（同长度、不同元素类型）
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn sum(a: array<float, 3>) -> float { return a[0]; }\n"
            "let a: array<int, 3> = [1, 2, 3];\nprint(sum(a));")),
        "数组类型不匹配");

    // S3c-2/S3c-3a：`array<T>` 签名是动态数组 descriptor ABI；return 字面量已支持。
    CHECK(module_ir("fn f(a: array<int>) -> array<int> { return a; }")
              .find("define void @f(ptr %sret, ptr %p0)") != std::string::npos);
    CHECK(module_ir("fn f() -> array<int> { return [1]; }")
              .find("define void @f(ptr %sret)") != std::string::npos);

    // 错误定位：实参长度不匹配落在实参表达式位置 [行:列]
    {
        bool threw = false;
        try {
            Codegen::compile(Parser::parse(
                "fn sum(a: array<int, 3>) -> int {\n    return a[0];\n}\n"
                "let b: array<int, 2> = [1, 2];\nprint(sum(b));"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 5 && e.pos->col == 11);
            CHECK(e.str().rfind("[5:11]", 0) == 0);
            CHECK(e.message.find("长度不匹配") != std::string::npos);
        }
        CHECK(threw);
    }

    // S3c-3b-3 / S3c-3c v2：固定 array<struct, N> 与固定嵌套数组参数/返回值
    // 都走 ptr + sret 扁平槽 ABI（不再是“尚未支持”错误）。
    CHECK(module_ir("struct P { x: int; }\n"
                    "fn f(a: array<P, 2>) -> int { return 0; }")
              .find("define i64 @f(ptr %p0)") != std::string::npos);
    CHECK(module_ir("struct P { x: int; }\n"
                    "fn f() -> array<P, 2> { return [P { x: 1 }, P { x: 2 }]; }")
              .find("define void @f(ptr %sret)") != std::string::npos);
    CHECK(module_ir("fn f(a: array<array<int, 3>, 2>) -> int { return 0; }")
              .find("define i64 @f(ptr %p0)") != std::string::npos);
    // 动态数组字段仍拒绝（固定长度数组字段 v1 已支持，见 test_struct_array_field）；
    // aggregate 表达式（调用结果）不能直接 print，变量形式已支持（见 test_print_aggregate）。
    CHECK_THROWS(Codegen::compile(Parser::parse("struct S { a: array<int>; }")),
                 "只支持 int/float/bool");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn make() -> array<int, 3> { return [1, 2, 3]; }\nprint(make());")),
        "print 不支持");

    // 返回值缺失
    CHECK_THROWS(Codegen::compile(Parser::parse("fn f() -> array<int, 3> { return; }")),
                 "return 必须带值");
}

// ---- S3c-1：局部动态数组 array<T>（堆 / push / len / 下标 / 深拷贝 / drop）----

static void test_dynamic_array_s3c1() {
    // 语法：`array<T>` 局部标注（省略长度，动态）；字面量仍推断定长 `array<T,N>`
    {
        auto prog = Parser::parse(
            "let a: array<int> = [1, 2];\n"
            "let b: array<float> = [];\n"
            "let c = [1, 2];");
        CHECK(prog.stmts[0]->ty.has_value() && *prog.stmts[0]->ty == "array<int>");
        CHECK(prog.stmts[1]->ty.has_value() && *prog.stmts[1]->ty == "array<float>");
        CHECK(prog.stmts[1]->value->kind == Expr::Kind::Array);
        CHECK(prog.stmts[1]->value->args.empty());
        CHECK(prog.stmts[2]->ty.has_value() == false);  // 省略标注 → 由字面量推断
    }

    // 字面量初始化：malloc + 三个 descriptor 栈槽（data/len/cap）；空数组 cap=4（32 字节）
    {
        auto src = "let a: array<int> = [1, 2];\nprint(len(a), a[0], a[1]);";
        auto ir = module_ir(src);
        CHECK(function_calls(src, "main", "malloc"));
        CHECK(ir.find("call ptr @malloc(i64 32)") != std::string::npos);
        CHECK(ir.find("alloca ptr") != std::string::npos);
        CHECK(count_scalar_allocas(src, "main", "i64") >= 2);
        CHECK(module_verifies(src));

        auto empty = "let a: array<int> = [];\nprint(len(a));";
        CHECK(function_calls(empty, "main", "malloc"));
        CHECK(module_ir(empty).find("call ptr @malloc(i64 32)") != std::string::npos);
        CHECK(!printf_has_int_constant(empty, 0));  // len 运行时读取，不是常量
        CHECK(module_verifies(empty));
    }

    // push：容量不足时 cap*2，malloc 新缓冲区 + 拷贝 + free 旧缓冲区
    {
        auto src =
            "let a: array<int> = [1, 2];\n"
            "push(a, 3);\n"
            "print(len(a), a[0], a[1], a[2]);";
        auto ir = module_ir(src);
        CHECK(ir.find("icmp eq i64") != std::string::npos);   // len == cap 判断
        CHECK(ir.find("mul i64") != std::string::npos);       // cap*2 / bytes
        CHECK(ir.find("getelementptr i64") != std::string::npos);  // 8 字节元素槽
        CHECK(count_calls_in(src, "main", "malloc") >= 2);    // 初始化 + 扩容分支
        CHECK(count_calls_in(src, "main", "free") >= 2);      // 扩容旧缓冲 + 作用域 drop
        CHECK(module_verifies(src));
    }

    // len：动态数组运行时读取；定长数组仍是编译期常量
    {
        CHECK(!printf_has_int_constant("let a: array<int> = [1, 2];\nprint(len(a));", 2));
        CHECK(printf_has_int_constant("let a = [1, 2];\nprint(len(a));", 2));
    }

    // 下标读写 + 运行时越界检查（tenet_bounds_fail）
    {
        auto src =
            "let a: array<int> = [1, 2];\n"
            "a[0] = 9;\n"
            "let i: int = 1;\n"
            "print(a[0], a[i]);";
        CHECK(function_calls(src, "main", "tenet_bounds_fail"));
        CHECK(module_verifies(src));
        auto c = Codegen::compile(Parser::parse(src));
        auto* main = c.mod->getFunction("main");
        bool has_uge = false;
        for (auto& bb : *main) {
            for (auto& i : bb) {
                auto* cmp = llvm::dyn_cast<llvm::ICmpInst>(&i);
                if (cmp && cmp->getPredicate() == llvm::CmpInst::ICMP_UGE) has_uge = true;
            }
        }
        CHECK(has_uge);
    }

    // 深拷贝：`let b = a` 独立缓冲区，修改 b 不影响 a（源类型推断为动态数组）
    {
        auto src =
            "let a: array<int> = [1, 2];\n"
            "let b = a;\n"
            "push(b, 3);\n"
            "a[0] = 9;\n"
            "print(a[0], b[0], len(a), len(b));";
        CHECK(count_calls_in(src, "main", "malloc") >= 3);  // a 初始化 + b 拷贝 + push 扩容
        CHECK(count_calls_in(src, "main", "free") >= 2);    // 作用域 drop a/b
        CHECK(module_verifies(src));
        // b 由 a 推断出 `array<int>`（动态），不是定长 array<int,2>
        auto prog = Parser::parse("let a: array<int> = [1, 2];\nlet b = a;");
        CHECK(prog.stmts[1]->ty.has_value() == false);
        CHECK(count_scalar_allocas(src, "main", "i64") >= 4);  // a/b 各有 len+cap 槽
    }

    // 整体赋值深拷贝：`b = a` 先 drop 旧 b 再接管新缓冲区
    {
        auto src =
            "let a: array<int> = [1, 2];\n"
            "let b: array<int> = [3];\n"
            "b = a;\n"
            "push(b, 4);\n"
            "print(b[0], b[1], b[2], len(b), a[0]);";
        CHECK(function_calls(src, "main", "free"));
        CHECK(count_calls_in(src, "main", "malloc") >= 3);
        CHECK(module_verifies(src));
        // 自赋值编译通过且不生成额外 drop
        CHECK(module_verifies(
            "let a: array<int> = [1];\na = a;\nprint(len(a), a[0]);"));
    }

    // 作用域 drop：while 每轮结束 / if 块结束都 free
    {
        auto src =
            "let i: int = 0;\n"
            "while (i < 3) {\n"
            "    let a: array<int> = [1, 2];\n"
            "    push(a, 3);\n"
            "    print(len(a));\n"
            "    i = i + 1;\n"
            "}\n"
            "print(i);";
        CHECK(function_calls(src, "main", "free"));
        CHECK(module_verifies(src));
        auto ifsrc =
            "let ok: bool = true;\n"
            "if (ok) {\n"
            "    let a: array<int> = [1];\n"
            "    print(len(a));\n"
            "}";
        CHECK(function_calls(ifsrc, "main", "free"));
        CHECK(module_verifies(ifsrc));
    }

    // break 退出循环：先 drop 循环体（含内层 if 块）的动态数组再跳转
    {
        auto src =
            "let i: int = 0;\n"
            "while (i < 5) {\n"
            "    let a: array<int> = [1];\n"
            "    push(a, 2);\n"
            "    if (i == 2) { break; }\n"
            "    i = i + 1;\n"
            "}\n"
            "print(i);";
        CHECK(function_calls(src, "main", "free"));
        CHECK(module_verifies(src));
    }

    // return 前 drop：函数 return 前 free（含在 if 内 return 时 drop 外层作用域）
    {
        auto src =
            "fn f() -> int {\n"
            "    let a: array<int> = [1, 2];\n"
            "    push(a, 3);\n"
            "    return len(a);\n"
            "}\n"
            "print(f());";
        CHECK(function_calls(src, "f", "free"));
        CHECK(module_verifies(src));
        auto nested =
            "fn g(x: int) -> int {\n"
            "    let a: array<int> = [1];\n"
            "    if (x > 0) { return len(a); }\n"
            "    push(a, 2);\n"
            "    return len(a);\n"
            "}\n"
            "print(g(1), g(0));";
        CHECK(function_calls(nested, "g", "free"));
        CHECK(module_verifies(nested));
    }

    // float / bool 元素：float bitcast、bool zext/trunc 到 8 字节槽
    {
        // 用变量初始化，避免常量折叠掉 bitcast/zext 指令
        auto fsrc =
            "let x: float = 1.5;\n"
            "let f: array<float> = [x];\n"
            "push(f, 2.5);\n"
            "print(f[0], f[1], len(f));";
        auto ir = module_ir(fsrc);
        CHECK(ir.find("bitcast double") != std::string::npos);  // double → i64 打包
        CHECK(ir.find("bitcast i64") != std::string::npos);     // i64 → double 解包
        CHECK(function_calls(fsrc, "main", "malloc"));
        CHECK(module_verifies(fsrc));

        auto bsrc =
            "let t: bool = true;\n"
            "let b: array<bool> = [t];\n"
            "push(b, false);\n"
            "print(b[0], b[1], len(b));";
        auto bir = module_ir(bsrc);
        CHECK(bir.find("zext i1") != std::string::npos);
        CHECK(bir.find("trunc i64") != std::string::npos);
        CHECK(module_verifies(bsrc));
    }

    // 空动态数组 + push：cap=4 起步，push 后 len=1
    {
        auto src = "let a: array<int> = [];\npush(a, 7);\nprint(len(a), a[0]);";
        CHECK(function_calls(src, "main", "malloc"));
        CHECK(!printf_has_int_constant(src, 1));
        CHECK(module_verifies(src));
    }

    // S3c-2/S3c-3a 起：动态数组参数 / 返回值合法（descriptor / sret ABI），
    // return 字面量也合法；详细用例见 test_dynamic_array_s3c2 / s3c3a。
    CHECK(module_ir("fn f(a: array<int>) -> int { return len(a); }")
              .find("define i64 @f(ptr %p0)") != std::string::npos);
    CHECK(module_ir("fn f() -> array<int> { return [1]; }")
              .find("define void @f(ptr %sret)") != std::string::npos);

    // 类型 / 用法错误
    CHECK_THROWS(Codegen::compile(Parser::parse("let a: array<int> = [1, 2.0];")),
                 "数组元素 1 类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<int> = [1];\nlet b: array<float> = [1.0];\na = b;")),
        "数组赋值类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse("let a: array<int> = [1];\nlet b: array<float> = a;")),
        "需要 array<float>");
    // 动态数组变量可直接 print（详细用例见 test_print_aggregate）
    CHECK(module_verifies("let a: array<int> = [1];\nprint(a);"));
    CHECK_THROWS(
        Codegen::compile(Parser::parse("let a: array<int, 2> = [1, 2];\npush(a, 3);")),
        "不是动态数组，不能 push");
    CHECK_THROWS(Codegen::compile(Parser::parse("push([1], 2);")),
                 "`push` 第一个参数必须是动态数组变量");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a: array<int> = [1];\npush(a, 1.5);")),
                 "push 值类型不匹配");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a: array<int> = [1];\npush(a);")),
                 "`push` 需要两个参数");
    CHECK_THROWS(
        Codegen::compile(Parser::parse("let a: array<int> = [];\nlet b: array<int> = 1;")),
        "动态数组初始化必须是");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2];\nlet b: array<int> = a;")),
                 "不是动态数组");
    // 空数组字面量仍只能用于显式动态数组标注
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [];")), "空数组");
}

// ---- S3c-2：动态数组参数 / 返回值（descriptor ABI / sret 转移 / 接管）----

static void test_dynamic_array_s3c2() {
    // 签名 ABI：动态参数传 descriptor 指针；动态返回值加隐藏前置 sret 指针、返回 void
    {
        auto ir = module_ir("fn sum(a: array<int>) -> int { return len(a); }");
        CHECK(ir.find("define i64 @sum(ptr %p0)") != std::string::npos);
        ir = module_ir("fn clone(a: array<int>) -> array<int> { return a; }");
        CHECK(ir.find("define void @clone(ptr %sret, ptr %p0)") != std::string::npos);
        ir = module_ir(
            "fn mix(a: array<float>, n: int, b: array<bool>) -> int { return n; }");
        CHECK(ir.find("define i64 @mix(ptr %p0, i64 %p1, ptr %p2)") !=
              std::string::npos);
        // 固定 array<T, N> 仍是原来的指针 / sret ABI
        ir = module_ir("fn fixed(a: array<int, 2>) -> array<int, 2> { return a; }");
        CHECK(ir.find("define void @fixed(ptr %sret, ptr %p0)") != std::string::npos);
    }

    // 调用方动态实参：分配 [3 x i64] descriptor，写入 data/len/cap，传指针
    {
        auto src =
            "fn sum(a: array<int>) -> int { return len(a); }\n"
            "let a: array<int> = [1, 2];\n"
            "print(sum(a));";
        auto ir = module_ir(src);
        CHECK(ir.find("call i64 @sum(ptr %sum.arg0)") != std::string::npos);
        CHECK(ir.find("alloca [3 x i64]") != std::string::npos);
        CHECK(ir.find("getelementptr [3 x i64], ptr %sum.arg0") != std::string::npos);
        CHECK(ir.find("store ptr %desc.data, ptr %desc.slot") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 被调函数入口：按 descriptor 的 data/len/cap 深拷贝到本地动态数组（值语义）
    {
        auto src = "fn id(a: array<int>) -> array<int> { return a; }";
        auto ir = module_ir(src);
        CHECK(ir.find("getelementptr [3 x i64], ptr %p0") != std::string::npos);
        CHECK(ir.find("call ptr @malloc") != std::string::npos);
        CHECK(ir.find("dyn.copy") != std::string::npos);  // 逐槽拷贝循环
        CHECK(count_calls_in(src, "id", "malloc") == 1);  // 入口深拷贝一次
        CHECK(count_calls_in(src, "id", "free") == 1);    // 参数副本退出 drop
    }

    // 参数值语义：函数内 push / 改元素不影响调用方；参数副本在函数退出 drop
    {
        auto src =
            "fn bump(a: array<int>) -> int {\n"
            "    push(a, 9);\n"
            "    a[0] = 7;\n"
            "    return len(a);\n"
            "}\n"
            "let a: array<int> = [1];\n"
            "let n: int = bump(a);\n"
            "print(len(a), n, a[0]);";
        CHECK(count_calls_in(src, "bump", "malloc") == 2);  // 入口拷贝 + push 扩容
        CHECK(count_calls_in(src, "bump", "free") == 2);    // 扩容旧缓冲 + 参数副本
        CHECK(count_calls_in(src, "main", "free") == 1);    // 调用方 a 自己 drop
        CHECK(module_verifies(src));
        auto ir = module_ir(src);
        CHECK(ir.find("call i64 @bump(ptr %bump.arg0)") != std::string::npos);
    }

    // 动态返回：本地变量 transfer 到 sret descriptor，随后清空本地槽位再 drop
    {
        auto src =
            "fn make() -> array<int> {\n"
            "    let a: array<int> = [1, 2];\n"
            "    return a;\n"
            "}\n"
            "let b: array<int> = make();\n"
            "print(len(b), b[0]);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @make(ptr %sret)") != std::string::npos);
        CHECK(ir.find("call void @make(ptr %make.sret)") != std::string::npos);
        CHECK(ir.find("alloca [3 x i64]") != std::string::npos);
        CHECK(count_calls_in(src, "make", "malloc") == 1);
        CHECK(count_calls_in(src, "make", "free") == 1);  // IR 里只有一处 drop
        // 转移顺序：先写 sret，再清空本地 data，最后才可能走到 free 分支。
        size_t transfer = ir.find("store ptr %desc.data, ptr %desc.slot");
        size_t clear = ir.find("store ptr null, ptr %a.data", transfer);
        size_t free_call = ir.find("call void @free", transfer);
        CHECK(transfer != std::string::npos);
        CHECK(clear != std::string::npos);
        CHECK(free_call != std::string::npos);
        CHECK(transfer < clear && clear < free_call);
        CHECK(module_verifies(src));
    }

    // let 接管调用结果：sret descriptor 清空，堆缓冲区归 b；调用方不再 free 临时 descriptor
    {
        auto src =
            "fn clone(a: array<int>) -> array<int> { return a; }\n"
            "let a: array<int> = [1];\n"
            "let b = clone(a);\n"
            "print(len(b), b[0]);";
        auto ir = module_ir(src);
        CHECK(ir.find("call void @clone(ptr %clone.sret, ptr %clone.arg0)") !=
              std::string::npos);
        // 接管后 descriptor 被清空（避免调用方或后续路径再次 free 同一缓冲区）
        size_t call = ir.find("call void @clone(");
        CHECK(call != std::string::npos);
        CHECK(ir.find("store ptr null, ptr %desc.slot", call) != std::string::npos);
        // main 只有 a 初始化一次 malloc；free 是 a 与 b 各一次（临时 descriptor 不 free）
        CHECK(count_calls_in(src, "main", "malloc") == 1);
        CHECK(count_calls_in(src, "main", "free") == 2);
        CHECK(module_verifies(src));
        // 省略标注时，let b = clone(a) 推断为动态数组 array<int>
        auto prog = Parser::parse(
            "fn clone(a: array<int>) -> array<int> { return a; }\n"
            "let a: array<int> = [1];\n"
            "let b = clone(a);");
        CHECK(prog.stmts[2]->ty.has_value() == false);
    }

    // 整体赋值 `b = make()`：drop 旧缓冲区后接管新缓冲区
    {
        auto src =
            "fn make() -> array<int> {\n"
            "    let a: array<int> = [1, 2];\n"
            "    return a;\n"
            "}\n"
            "let b: array<int> = [9, 9, 9];\n"
            "b = make();\n"
            "print(len(b), b[0]);";
        CHECK(count_calls_in(src, "main", "malloc") == 1);  // 旧 b 初始化
        CHECK(count_calls_in(src, "main", "free") == 2);    // 赋值时 drop 旧 b + 退出 drop 新 b
        CHECK(module_verifies(src));
    }

    // 浮点 / bool 元素的动态参数与返回值
    {
        auto src =
            "fn clonef(a: array<float>) -> array<float> {\n"
            "    push(a, 3.5);\n"
            "    return a;\n"
            "}\n"
            "let f: array<float> = [1.5];\n"
            "let g: array<float> = clonef(f);\n"
            "print(len(f), g[1]);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @clonef(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(module_verifies(src));

        auto bsrc =
            "fn cloneb(a: array<bool>) -> array<bool> { return a; }\n"
            "let t: bool = true;\n"
            "let b: array<bool> = [t];\n"
            "let c: array<bool> = cloneb(b);\n"
            "print(len(c), c[0]);";
        CHECK(module_verifies(bsrc));
        CHECK(count_calls_in(bsrc, "cloneb", "malloc") == 1);
    }

    // return 参数（入口深拷贝）与 return 局部变量（所有权转移）都只保留一份缓冲区
    {
        auto src =
            "fn clone(a: array<int>) -> array<int> { return a; }\n"
            "fn make() -> array<int> {\n"
            "    let a: array<int> = [1];\n"
            "    return a;\n"
            "}";
        CHECK(count_calls_in(src, "clone", "malloc") == 1);
        CHECK(count_calls_in(src, "clone", "free") == 1);
        CHECK(count_calls_in(src, "make", "malloc") == 1);
        CHECK(count_calls_in(src, "make", "free") == 1);
        CHECK(module_verifies(src));
    }

    // 完整链路：参数深拷贝 + 返回转移 + push + let 接管（/tmp/dynparam.tenet 同构）
    {
        auto src =
            "fn sum(a: array<int>) -> int {\n"
            "    let s: int = 0;\n"
            "    let i: int = 0;\n"
            "    while (i < len(a)) {\n"
            "        s = s + a[i];\n"
            "        i = i + 1;\n"
            "    }\n"
            "    return s;\n"
            "}\n"
            "fn clone(a: array<int>) -> array<int> {\n"
            "    return a;\n"
            "}\n"
            "let a: array<int> = [1, 2];\n"
            "let s: int = sum(a);\n"
            "let b: array<int> = clone(a);\n"
            "push(b, 3);\n"
            "a[0] = 9;\n"
            "print(s, len(a), a[0], len(b), b[0], b[2]);";
        CHECK(module_verifies(src));
        CHECK(function_calls(src, "main", "sum"));
        CHECK(function_calls(src, "main", "clone"));
        CHECK(count_calls_in(src, "sum", "malloc") == 1);
        CHECK(count_calls_in(src, "sum", "free") == 1);
        CHECK(count_calls_in(src, "main", "free") == 3);  // a、b、push 扩容旧缓冲
    }

    // void 函数落到底：动态参数副本同样 drop
    {
        auto src =
            "fn show(a: array<int>) {\n"
            "    push(a, 99);\n"
            "    print(len(a));\n"
            "}\n"
            "let a: array<int> = [1];\n"
            "show(a);";
        CHECK(count_calls_in(src, "show", "free") >= 2);  // push 扩容 + 退出 drop
        CHECK(module_verifies(src));
    }

    // S3c-3a：return 字面量 / 调用结果、动态实参字面量 / 调用结果均已支持
    // （详细 ABI / 临时缓冲清理断言见 test_dynamic_array_s3c3a）。
    CHECK(module_ir("fn f() -> array<int> { return [1, 2]; }")
              .find("define void @f(ptr %sret)") != std::string::npos);
    CHECK(module_ir(
              "fn make() -> array<int> {\n"
              "    let a: array<int> = [1];\n"
              "    return a;\n"
              "}\n"
              "fn g() -> array<int> { return make(); }")
              .find("call void @make(ptr %make.sret)") != std::string::npos);
    CHECK(module_ir(
              "fn f(a: array<int>) -> int { return len(a); }\n"
              "f([1, 2]);")
              .find("call i64 @f(ptr %f.arg0)") != std::string::npos);
    CHECK(module_ir(
              "fn make() -> array<int> {\n"
              "    let a: array<int> = [1];\n"
              "    return a;\n"
              "}\n"
              "fn f(a: array<int>) -> int { return len(a); }\n"
              "f(make());")
              .find("call i64 @f(ptr %f.arg0)") != std::string::npos);

    // 类型核对：动态实参不能传定长数组；return 变量元素类型必须一致
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f(a: array<int>) -> int { return len(a); }\n"
            "let x: array<int, 2> = [1, 2];\n"
            "f(x);")),
        "类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f() -> array<int> {\n"
            "    let a: array<float> = [1.0];\n"
            "    return a;\n"
            "}")),
        "返回类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn make() -> array<int> {\n"
            "    let a: array<int> = [1];\n"
            "    return a;\n"
            "}\n"
            "let x: array<int, 3> = make();")),
        "需要 array<int,3>");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn sum(a: array<int, 3>) -> int { return len(a); }\n"
            "let a: array<int> = [1];\n"
            "print(sum(a));")),
        "数组类型不匹配");

    // S3c-3b-2：动态 array<struct> 参数已开放（descriptor ABI）；
    // 动态嵌套数组仍明确拒绝（固定嵌套数组参数/返回值见 S3c-3c v2）。
    CHECK(module_ir(
              "struct P { x: int; }\n"
              "fn f(a: array<P>) -> int { return len(a); }")
              .find("define i64 @f(ptr %p0)") != std::string::npos);
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f(a: array<array<int, 2>>) -> int { return len(a); }")),
        "动态嵌套数组尚未支持");

    // 错误定位：return 数字 / 动态实参数字 / return 类型不匹配都落在表达式位置
    {
        bool threw = false;
        try {
            Codegen::compile(Parser::parse(
                "fn f() -> array<int> {\n    return 1;\n}"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 12);
            CHECK(e.str().rfind("[2:12]", 0) == 0);
            CHECK(e.message.find("动态数组 return 只支持变量、字面量或返回动态数组的调用") !=
                  std::string::npos);
        }
        CHECK(threw);
    }
    {
        bool threw = false;
        try {
            Codegen::compile(Parser::parse(
                "fn sum(a: array<int>) -> int {\n"
                "    return len(a);\n"
                "}\n"
                "let a: array<int> = [1];\n"
                "print(sum(1));"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 5 && e.pos->col == 11);
            CHECK(e.str().rfind("[5:11]", 0) == 0);
            CHECK(e.message.find("动态数组实参只支持变量、字面量或返回动态数组的调用") !=
                  std::string::npos);
        }
        CHECK(threw);
    }
    {
        bool threw = false;
        try {
            Codegen::compile(Parser::parse(
                "fn f() -> array<int> {\n"
                "    let a: array<float> = [1.0];\n"
                "    return a;\n"
                "}"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 3 && e.pos->col == 12);
            CHECK(e.str().rfind("[3:12]", 0) == 0);
            CHECK(e.message.find("返回类型不匹配") != std::string::npos);
        }
        CHECK(threw);
    }

    // descriptor 结构断言：只分配 3 槽（不多不少），且用 [3 x i64]
    {
        auto ir = module_ir(
            "fn clone(a: array<int>) -> array<int> { return a; }\n"
            "let a: array<int> = [1];\n"
            "let b: array<int> = clone(a);");
        CHECK(count_text(ir, "alloca [3 x i64]") == 2);  // 调用方 sret + 实参 descriptor
        CHECK(ir.find("getelementptr [3 x i64], ptr %clone.sret, i64 0, i64 0") !=
              std::string::npos);
    }
}

// ---- S3c-3a：动态字面量 / 调用结果作实参，return 字面量 / 调用 ----

static void test_dynamic_array_s3c3a() {
    // 字面量实参：构造临时 descriptor，调用返回后 free 临时缓冲区（被调函数入口已深拷贝）
    {
        auto src =
            "fn sum(a: array<int>) -> int { return len(a); }\n"
            "print(sum([1, 2]));";
        auto ir = module_ir(src);
        CHECK(ir.find("call i64 @sum(ptr %sum.arg0)") != std::string::npos);
        CHECK(ir.find("store ptr %desc.data, ptr %desc.slot") != std::string::npos);
        // 只有实参 descriptor（返回 int，无 sret）；字面量临时数组是 3 个标量槽
        CHECK(count_text(ir, "alloca [3 x i64]") == 1);
        CHECK(count_calls_in(src, "main", "malloc") == 1);  // 字面量临时缓冲区
        CHECK(count_calls_in(src, "main", "free") == 1);    // 调用返回后清理临时缓冲区
        size_t call = ir.find("call i64 @sum(");
        size_t free_call = ir.find("call void @free", call);
        CHECK(call != std::string::npos);
        CHECK(free_call != std::string::npos);
        CHECK(call < free_call);  // 先调用，后 free
        CHECK(module_verifies(src));
    }

    // 调用结果实参：复制其 sret descriptor，调用返回后只 free 数据（不 free 栈槽）
    {
        auto src =
            "fn make() -> array<int> {\n"
            "    let a: array<int> = [1, 2];\n"
            "    return a;\n"
            "}\n"
            "fn sum(a: array<int>) -> int { return len(a); }\n"
            "print(sum(make()));";
        auto ir = module_ir(src);
        CHECK(ir.find("call void @make(ptr %make.sret)") != std::string::npos);
        CHECK(ir.find("call i64 @sum(ptr %sum.arg0)") != std::string::npos);
        CHECK(count_text(ir, "alloca [3 x i64]") == 2);  // make.sret + sum.arg0
        CHECK(count_calls_in(src, "main", "malloc") == 0);  // 缓冲区由 make 分配
        CHECK(count_calls_in(src, "main", "free") == 1);    // 临时 descriptor 的 data
        CHECK(count_calls_in(src, "make", "malloc") == 1);
        size_t call = ir.find("call i64 @sum(");
        size_t free_call = ir.find("call void @free", call);
        CHECK(call != std::string::npos);
        CHECK(free_call != std::string::npos);
        CHECK(call < free_call);
        CHECK(module_verifies(src));
    }

    // return 字面量：临时动态数组的 data/len/cap 转移进 sret，不 free（所有权给调用方）
    {
        auto src =
            "fn lit() -> array<int> {\n"
            "    return [3, 4];\n"
            "}\n"
            "let c: array<int> = lit();\n"
            "print(len(c), c[0], c[1]);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @lit(ptr %sret)") != std::string::npos);
        CHECK(ir.find("call void @lit(ptr %lit.sret)") != std::string::npos);
        CHECK(count_calls_in(src, "lit", "malloc") == 1);
        CHECK(count_calls_in(src, "lit", "free") == 0);   // 不 free 已转移的缓冲区
        CHECK(count_calls_in(src, "main", "free") == 1);  // 只在 c 退出时 free
        size_t transfer = ir.find("store ptr %desc.data, ptr %desc.slot");
        size_t clear = ir.find("store ptr null, ptr %__ret_tmp.data", transfer);
        CHECK(transfer != std::string::npos);
        CHECK(clear != std::string::npos);  // 转移后清空临时槽位，避免误 drop
        CHECK(count_text(ir, "call void @free") == 1);
        CHECK(module_verifies(src));
    }

    // return 调用结果：内层 descriptor 转移进 sret 并清空，不 free
    {
        auto src =
            "fn make() -> array<int> {\n"
            "    let a: array<int> = [1, 2];\n"
            "    return a;\n"
            "}\n"
            "fn chain() -> array<int> { return make(); }\n"
            "let d: array<int> = chain();\n"
            "print(len(d), d[1]);";
        auto ir = module_ir(src);
        CHECK(ir.find("call void @make(ptr %make.sret)") != std::string::npos);
        CHECK(count_calls_in(src, "chain", "malloc") == 0);
        CHECK(count_calls_in(src, "chain", "free") == 0);
        CHECK(count_calls_in(src, "make", "malloc") == 1);
        CHECK(count_calls_in(src, "main", "free") == 1);
        // 复制后清空内层 descriptor（store ptr null 到 make.sret 的槽 0）
        size_t call = ir.find("call void @make(ptr %make.sret)");
        CHECK(call != std::string::npos);
        CHECK(ir.find("store ptr null, ptr %desc.slot", call) != std::string::npos);
        CHECK(module_verifies(src));
    }

    // /tmp/dynexpr.tenet 同构：字面量/调用实参 + return 字面量/调用 + 链式调用
    {
        auto src =
            "fn id(a: array<int>) -> array<int> {\n"
            "    return a;\n"
            "}\n"
            "fn make() -> array<int> {\n"
            "    let a: array<int> = [1, 2];\n"
            "    return a;\n"
            "}\n"
            "fn lit() -> array<int> {\n"
            "    return [3, 4];\n"
            "}\n"
            "fn chain() -> array<int> {\n"
            "    return make();\n"
            "}\n"
            "let a: array<int> = id([1, 2]);\n"
            "let b: array<int> = id(make());\n"
            "let c: array<int> = lit();\n"
            "let d: array<int> = chain();\n"
            "push(d, 5);\n"
            "print(len(a), a[0], a[1], len(b), b[1], len(c), c[1], len(d), d[2]);";
        auto ir = module_ir(src);
        CHECK(count_calls_in(src, "id", "malloc") == 1);  // 入口深拷贝
        CHECK(count_calls_in(src, "id", "free") == 1);    // 参数副本 drop 槽（转移后为空）
        CHECK(count_calls_in(src, "lit", "malloc") == 1);
        CHECK(count_calls_in(src, "lit", "free") == 0);
        CHECK(count_calls_in(src, "chain", "malloc") == 0);
        CHECK(count_calls_in(src, "chain", "free") == 0);
        CHECK(count_calls_in(src, "main", "malloc") == 2);  // id 字面量临时 + push 扩容
        // 字面量临时 + make 调用结果临时 + 扩容旧缓冲 + a/b/c/d 退出 drop
        CHECK(count_calls_in(src, "main", "free") == 7);
        CHECK(ir.find("call void @id(ptr %id.sret, ptr %id.arg0)") != std::string::npos);
        CHECK(count_text(ir, "alloca [3 x i64]") == 8);  // main 7 + chain 1
        CHECK(module_verifies(src));
    }

    // 嵌套调用：内层调用结果作外层实参，临时 descriptor 逐层清理，无 double free
    {
        auto src =
            "fn id(a: array<int>) -> array<int> { return a; }\n"
            "let a: array<int> = id(id([1, 2]));\n"
            "print(len(a), a[1]);";
        CHECK(module_verifies(src));
        CHECK(count_calls_in(src, "main", "malloc") == 1);  // 仅字面量临时缓冲区
        CHECK(count_calls_in(src, "main", "free") == 3);  // 字面量临时 + 内层 sret + a
        CHECK(count_calls_in(src, "id", "malloc") == 1);    // 函数体入口深拷贝只有一处
        CHECK(count_calls_in(src, "id", "free") == 1);      // 参数副本的 drop 槽只有一处
    }

    // 空字面量作实参 / return 值
    {
        auto src =
            "fn sum(a: array<int>) -> int { return len(a); }\n"
            "fn empty() -> array<int> { return []; }\n"
            "let e: array<int> = empty();\n"
            "print(sum([]), len(e));";
        CHECK(count_calls_in(src, "main", "free") == 2);  // 实参临时 + e 退出
        CHECK(module_verifies(src));
    }

    // float / bool 元素：字面量 / 调用结果作实参 + return 字面量 / 调用
    {
        auto src =
            "fn takef(a: array<float>) -> float { return a[1]; }\n"
            "fn makef() -> array<float> { return [1.5, 2.5]; }\n"
            "print(takef(makef()), takef([3.5, 4.5]));";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @makef(ptr %sret)") != std::string::npos);
        CHECK(ir.find("call double @takef(ptr %takef.arg0)") != std::string::npos);
        CHECK(count_calls_in(src, "makef", "malloc") == 1);
        CHECK(count_calls_in(src, "makef", "free") == 0);
        CHECK(count_calls_in(src, "main", "malloc") == 1);  // [3.5, 4.5]
        CHECK(count_calls_in(src, "main", "free") == 2);    // 两个临时实参
        CHECK(module_verifies(src));

        auto bsrc =
            "fn takeb(a: array<bool>) -> bool { return a[0]; }\n"
            "fn makeb() -> array<bool> { return [true, false]; }\n"
            "print(takeb(makeb()), takeb([false]));";
        CHECK(module_verifies(bsrc));
        CHECK(count_calls_in(bsrc, "makeb", "malloc") == 1);
        CHECK(count_calls_in(bsrc, "makeb", "free") == 0);
        CHECK(count_calls_in(bsrc, "main", "free") == 2);
    }

    // 变量实参保持原语义：不复制、不 drop 调用方变量（缓冲区仍由变量自己的 drop 释放）
    {
        auto src =
            "fn sum(a: array<int>) -> int { return len(a); }\n"
            "let a: array<int> = [1, 2];\n"
            "print(sum(a));";
        CHECK(count_calls_in(src, "main", "malloc") == 1);  // 只有 a 的初始化
        CHECK(count_calls_in(src, "main", "free") == 1);    // 只有 a 退出时的 drop
        CHECK(module_verifies(src));
    }

    // 不支持表达式：数字 / struct 字面量作为动态实参或 return 值报错
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f(a: array<int>) -> int { return len(a); }\n"
            "f(1);")),
        "动态数组实参只支持变量、字面量或返回动态数组的调用");
    CHECK_THROWS(Codegen::compile(Parser::parse("fn f() -> array<int> { return 1; }")),
                 "动态数组 return 只支持变量、字面量或返回动态数组的调用");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "fn f(a: array<int>) -> int { return len(a); }\n"
            "f(P { x: 1 });")),
        "动态数组实参只支持变量、字面量或返回动态数组的调用");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "fn f() -> array<int> { return P { x: 1 }; }")),
        "动态数组 return 只支持变量、字面量或返回动态数组的调用");

    // 元素 / 调用返回类型核对
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f(a: array<int>) -> int { return len(a); }\n"
            "f([1.0]);")),
        "数组元素 0 类型不匹配");
    CHECK_THROWS(Codegen::compile(Parser::parse("fn f() -> array<int> { return [1.0]; }")),
                 "数组元素 0 类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn makef() -> array<float> { return [1.5]; }\n"
            "fn f(a: array<int>) -> int { return len(a); }\n"
            "f(makef());")),
        "参数类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn makef() -> array<float> { return [1.5]; }\n"
            "fn f() -> array<int> { return makef(); }")),
        "返回类型不匹配");

    // 错误定位：不支持表达式落在表达式位置 [行:列]
    {
        bool threw = false;
        try {
            Codegen::compile(Parser::parse(
                "fn f() -> array<int> {\n"
                "    return \"x\";\n"
                "}"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 12);
            CHECK(e.str().rfind("[2:12]", 0) == 0);
            CHECK(e.message.find("动态数组 return 只支持变量、字面量或返回动态数组的调用") !=
                  std::string::npos);
        }
        CHECK(threw);
    }
    {
        bool threw = false;
        try {
            Codegen::compile(Parser::parse(
                "fn sum(a: array<int>) -> int {\n"
                "    return len(a);\n"
                "}\n"
                "print(sum(true));"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 4 && e.pos->col == 11);
            CHECK(e.str().rfind("[4:11]", 0) == 0);
            CHECK(e.message.find("动态数组实参只支持变量、字面量或返回动态数组的调用") !=
                  std::string::npos);
        }
        CHECK(threw);
    }
}

// ---- S3c-3b-1：固定 array<struct, N>（局部扁平槽布局 / 字段路径 / 元素赋值 / 深拷贝）----

static void test_array_struct_s3c3b1() {
    // 语法：`array<P, N>` 类型字符串归一化（parser 已支持 struct 元素，无需大改）
    {
        auto prog = Parser::parse(
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];");
        CHECK(prog.stmts.size() == 2);
        CHECK(prog.stmts[1]->ty.has_value() && *prog.stmts[1]->ty == "array<P,2>");
    }

    // 字面量初始化 + a[i].field 读写 + a[i] = struct 整体元素赋值
    // （与 /tmp/structarr.tenet 同构，输出 9 2 7 8）
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "a[0].x = 9;\n"
            "a[1] = P { x: 7, y: 8 };\n"
            "print(a[0].x, a[0].y, a[1].x, a[1].y);";
        auto ir = module_ir(src);
        // 2 个元素 × 2 个标量字段 = 4 个连续 8 字节槽
        CHECK(ir.find("alloca [4 x i64]") != std::string::npos);
        CHECK(count_text(ir, "alloca [4 x i64]") == 1);
        // 元素 stride = 2 槽：第 2 个元素从槽 2 开始
        CHECK(ir.find("getelementptr [4 x i64], ptr %a, i64 0, i64 2") !=
              std::string::npos);
        // 字段写入/整体元素写入按槽落位（x→槽 0，y→槽 1）
        CHECK(ir.find("store i64 9") != std::string::npos);
        CHECK(ir.find("store i64 7") != std::string::npos);
        CHECK(ir.find("store i64 8") != std::string::npos);
        CHECK(ir.find("getelementptr i64, ptr") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 嵌套 struct 字段路径 q[0].p.x / q[1] = Q { ... }（与 /tmp/structarr2.tenet 同构）
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "struct Q { p: P; z: int; }\n"
            "let q: array<Q, 2> = [Q { p: P { x: 1, y: 2 }, z: 3 },"
            " Q { p: P { x: 4, y: 5 }, z: 6 }];\n"
            "q[0].p.x = 9;\n"
            "q[1] = Q { p: P { x: 7, y: 8 }, z: 10 };\n"
            "print(q[0].p.x, q[0].z, q[1].p.y, q[1].z);";
        auto ir = module_ir(src);
        // 2 个元素 ×（P 的 2 个叶子 + z）= 6 个槽
        CHECK(ir.find("alloca [6 x i64]") != std::string::npos);
        CHECK(ir.find("getelementptr [6 x i64], ptr %q, i64 0, i64 3") !=
              std::string::npos);
        // q[0].p.x 槽 0、q[0].z 槽 2、q[1].p.y 槽 1、q[1].z 槽 2
        CHECK(ir.find("getelementptr i64, ptr") != std::string::npos);
        CHECK(ir.find(", i64 2") != std::string::npos);
        CHECK(ir.find("store i64 9") != std::string::npos);
        CHECK(ir.find("store i64 7") != std::string::npos);
        CHECK(ir.find("store i64 8") != std::string::npos);
        CHECK(ir.find("store i64 10") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 动态下标 a[i].field：运行时边界检查（icmp uge + tenet_bounds_fail）
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "let i: int = 1;\n"
            "a[i].x = 42;\n"
            "print(a[i].x, a[i].y);";
        auto ir = module_ir(src);
        CHECK(ir.find("icmp uge i64") != std::string::npos);
        CHECK(ir.find("call void @tenet_bounds_fail") != std::string::npos);
        CHECK(ir.find("mul i64") != std::string::npos);  // idx * slots
        CHECK(module_verifies(src));
    }

    // 整体元素赋值支持同类型 struct 变量与返回 struct 的函数调用
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "fn mk(x: int) -> P { return P { x: x, y: x + 1 }; }\n"
            "let p: P = P { x: 2, y: 3 };\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "a[0] = mk(5);\n"
            "a[1] = p;\n"
            "print(a[0].y, a[1].x);";
        auto ir = module_ir(src);
        CHECK(ir.find("call void @mk(ptr") != std::string::npos);
        CHECK(ir.find("alloca [4 x i64]") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // let b = a 深拷贝（逐槽复制，修改 b 不影响 a）；显式标注拷贝同样支持
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "let b = a;\n"
            "let c: array<P, 2> = b;\n"
            "c[0].x = 100;\n"
            "print(a[0].x, b[0].x, c[0].x, len(a), len(b), len(c));";
        auto ir = module_ir(src);
        CHECK(count_text(ir, "alloca [4 x i64]") == 3);  // a / b / c 各自独立
        CHECK(ir.find("%b = alloca [4 x i64]") != std::string::npos);
        CHECK(ir.find("%c = alloca [4 x i64]") != std::string::npos);
        CHECK(ir.find("store i64 100") != std::string::npos);
        CHECK(printf_has_int_constant(src, 2));  // len 是编译期常量
        CHECK(module_verifies(src));
    }

    // 无标注数组字面量推断为 array<struct, N>；len 保持
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "let a = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "print(len(a), a[1].y);";
        auto ir = module_ir(src);
        CHECK(ir.find("alloca [4 x i64]") != std::string::npos);
        CHECK(printf_has_int_constant(src, 2));
        CHECK(module_verifies(src));
    }

    // float / bool 字段按 8 字节槽打包/解包（double↔i64 bitcast、i1↔i64 zext/trunc）
    {
        auto src =
            "struct F { a: float; b: bool; }\n"
            "let half: float = 0.5;\n"
            "let flag: bool = true;\n"
            "let f: array<F, 2> = [F { a: 1.5, b: true },"
            " F { a: 2.5, b: false }];\n"
            "f[1].a = half;\n"
            "f[1].b = flag;\n"
            "print(f[0].a, f[1].b, f[0].b, len(f));";
        auto ir = module_ir(src);
        CHECK(ir.find("alloca [4 x i64]") != std::string::npos);
        CHECK(ir.find("bitcast double") != std::string::npos);
        CHECK(ir.find("zext i1") != std::string::npos);
        CHECK(ir.find("trunc i64") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 边界：常量下标编译期越界报错；动态下标生成运行时检查
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
            "a[2].x = 1;")),
        "越界");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
            "print(a[-1].x);")),
        "越界");
    {
        auto src =
            "struct P { x: int; }\n"
            "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
            "let i: int = 2;\n"
            "print(a[i].x);";
        auto ir = module_ir(src);
        CHECK(ir.find("call void @tenet_bounds_fail") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // S3c-3b-2：动态 array<struct> 局部数组、参数、返回值已开放（详细用例见
    // test_dynamic_struct_array_s3c3b2）；S3c-3b-3：固定 array<struct, N> 参数/返回值
    // 走 ptr + sret 扁平槽 ABI（详细用例见 test_fixed_array_abi_s3c3b3）。
    CHECK(module_ir(
              "struct P { x: int; }\n"
              "let a: array<P> = [P { x: 1 }];")
              .find("call ptr @malloc") != std::string::npos);
    CHECK(module_ir(
              "struct P { x: int; }\n"
              "fn f(a: array<P>) -> int { return len(a); }")
              .find("define i64 @f(ptr %p0)") != std::string::npos);
    CHECK(module_ir(
              "struct P { x: int; }\n"
              "fn f() -> array<P> { return [P { x: 1 }]; }")
              .find("define void @f(ptr %sret)") != std::string::npos);
    CHECK(module_ir(
              "struct P { x: int; }\n"
              "fn f(a: array<P, 2>) -> int { return a[0].x; }")
              .find("define i64 @f(ptr %p0)") != std::string::npos);
    CHECK(module_ir(
              "struct P { x: int; }\n"
              "fn f() -> array<P, 2> { return [P { x: 1 }, P { x: 2 }]; }")
              .find("define void @f(ptr %sret)") != std::string::npos);
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
            "print(a[0]);")),
        "不支持整体读取 array<struct> 元素");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
            "let p: P = a[0];")),
        "不支持整体读取 array<struct> 元素");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
            "let b: array<P, 3> = [P { x: 1 }, P { x: 2 }, P { x: 3 }];\n"
            "a = b;")),
        "数组参数类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
            "a = 1;")),
        "固定数组实参必须是");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
            "a = [P { x: 1 }];")),
        "数组长度不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
            "a = [[1, 2], [3]];")),
        "内层数组长度不匹配");
    // 固定 array<struct, N> 可直接 print（详细用例见 test_print_aggregate）
    CHECK(module_verifies(
        "struct P { x: int; }\n"
        "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
        "print(a);"));
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
            "push(a, P { x: 3 });")),
        "不是动态数组，不能 push");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "struct S { a: array<P>; }")),
        "动态数组");

    // 类型错误：元素赋值 / 字段赋值 / 初始化长度与元素类型
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "a[0] = 1;")),
        "值必须是字面量、同类型变量或返回 P 的函数调用");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; y: int; }\n"
            "struct Q { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "a[0] = Q { x: 1, y: 2 };")),
        "字面量是 Q");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; y: int; }\n"
            "struct Q { x: int; y: int; }\n"
            "let q: Q = Q { x: 1, y: 2 };\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "a[0] = q;")),
        "实际是 Q");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "a[0].x = 1.5;")),
        "字段 `x` 类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "print(a[0].z);")),
        "没有字段 `z`");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "struct Q { p: P; z: int; }\n"
            "let q: array<Q, 2> = [Q { p: P { x: 1 }, z: 2 },"
            " Q { p: P { x: 3 }, z: 4 }];\n"
            "q[0].p = P { x: 9 };")),
        "请继续访问到标量字段");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; y: int; }\n"
            "let a: array<P, 2> = [P { x: 1 } , P { x: 2, y: 3 }];")),
        "缺少字段 `y`");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P, 2> = [P { x: 1 }];")),
        "数组长度不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let c: array<P, 3> = [P { x: 1 }, P { x: 2 }, P { x: 3 }];\n"
            "let b: array<P, 2> = c;")),
        "需要 array<P,2>");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let p: P = P { x: 1 };\n"
            "let b: array<P, 2> = p;")),
        "不是固定数组");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let b: array<P, 2> = P { x: 1 };")),
        "初始化必须是字面量、同类型数组变量或返回数组的调用");

    // 错误定位：动态 array<struct> 初始化错误落在 let 语句，整体读取落在下标表达式
    {
        bool threw = false;
        try {
            Codegen::compile(Parser::parse(
                "struct P { x: int; }\n"
                "let a: array<P> = 1;"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 2 && e.pos->col == 19);
            CHECK(e.str().rfind("[2:19]", 0) == 0);
            CHECK(e.message.find("array<struct> 初始化必须是") != std::string::npos);
        }
        CHECK(threw);
    }
    {
        bool threw = false;
        try {
            Codegen::compile(Parser::parse(
                "struct P { x: int; }\n"
                "let a: array<P, 2> = [P { x: 1 }, P { x: 2 }];\n"
                "a[0];"));
        } catch (const TenetError& e) {
            threw = true;
            CHECK(e.pos.has_value() && e.pos->line == 3 && e.pos->col == 1);
            CHECK(e.str().rfind("[3:1]", 0) == 0);
            CHECK(e.message.find("不支持整体读取 array<struct> 元素") != std::string::npos);
        }
        CHECK(threw);
    }
}

// ---- S3c-3b-2：动态 array<struct>（堆 stride=slots*8 / push / descriptor ABI）----

static void test_dynamic_struct_array_s3c3b2() {
    // 类型：显式标注 `array<P>`（无长度）是动态数组；字面量仍推断定长 `array<P, N>`
    {
        auto prog = Parser::parse(
            "struct P { x: int; y: int; }\n"
            "let a: array<P> = [P { x: 1, y: 2 }];");
        CHECK(prog.stmts[1]->ty.has_value() && *prog.stmts[1]->ty == "array<P>");
        auto inferred = Parser::parse(
            "struct P { x: int; y: int; }\n"
            "let a = [P { x: 1, y: 2 }];");
        CHECK(inferred.stmts[1]->ty.has_value() == false);
    }

    // 字面量 + a[i].field 读写 + a[i] = struct + push struct
    // （与 /tmp/dynstruct.tenet 同构，输出 3 9 2 7 8 5 6）
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "let a: array<P> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "push(a, P { x: 5, y: 6 });\n"
            "a[0].x = 9;\n"
            "a[1] = P { x: 7, y: 8 };\n"
            "print(len(a), a[0].x, a[0].y, a[1].x, a[1].y, a[2].x, a[2].y);";
        auto ir = module_ir(src);
        // 2 个元素 × 2 槽，cap 从 4 起步 → 4*2*8 = 64 字节
        CHECK(ir.find("call ptr @malloc(i64 64)") != std::string::npos);
        // push 先把 struct 打包进 [slots x i64] 临时缓冲
        CHECK(ir.find("alloca [2 x i64]") != std::string::npos);
        // 元素 stride = slots：第二个元素从槽 2 开始
        CHECK(ir.find("ptr %dyn.data, i64 2") != std::string::npos);
        CHECK(ir.find("getelementptr i64, ptr") != std::string::npos);
        CHECK(ir.find("mul i64") != std::string::npos);  // idx * slots / cap * slots
        CHECK(function_calls(src, "main", "malloc"));
        CHECK(count_calls_in(src, "main", "malloc") >= 2);  // 字面量 + push 扩容分支
        CHECK(count_calls_in(src, "main", "free") >= 2);    // 扩容旧缓冲 + 作用域 drop
        CHECK(module_verifies(src));
    }

    // push struct 变量 / 返回 struct 的调用；容量增长按 slots 计算字节数
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "fn mk(x: int) -> P { return P { x: x, y: x + 1 }; }\n"
            "let p: P = P { x: 7, y: 8 };\n"
            "let a: array<P> = [P { x: 1, y: 2 }];\n"
            "push(a, p);\n"
            "push(a, mk(5));\n"
            "print(len(a), a[1].x, a[2].y);";
        auto ir = module_ir(src);
        CHECK(function_calls(src, "main", "mk"));
        CHECK(ir.find("call void @mk(ptr") != std::string::npos);
        CHECK(ir.find("mul i64 %dyn.newcap") != std::string::npos);
        CHECK(ir.find(", 16") != std::string::npos);  // slots*8 = 16
        CHECK(count_calls_in(src, "main", "malloc") >= 3);
        CHECK(count_calls_in(src, "main", "free") >= 3);
        CHECK(module_verifies(src));
    }

    // let b = a 深拷贝：独立堆缓冲区；a[i] 元素赋值支持 struct 变量
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "let a: array<P> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "let b = a;\n"
            "b[0].x = 9;\n"
            "let p: P = P { x: 7, y: 8 };\n"
            "b[1] = p;\n"
            "print(a[0].x, b[0].x, b[1].y, len(a), len(b));";
        auto ir = module_ir(src);
        CHECK(count_text(ir, "alloca ptr") >= 2);  // a / b 各自的 data 槽
        CHECK(ir.find("dyn.copy.data") != std::string::npos);
        CHECK(ir.find("store i64 9") != std::string::npos);
        CHECK(count_calls_in(src, "main", "malloc") >= 2);  // a 初始化 + b 深拷贝
        CHECK(module_verifies(src));
    }

    // 参数 / 返回值 ABI：descriptor + 入口深拷贝；sret descriptor + 转移
    // （与 /tmp/dynstructabi.tenet 同构，输出 3 1 6 3 9）
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "fn clone(a: array<P>) -> array<P> { return a; }\n"
            "fn firstx(a: array<P>) -> int {\n"
            "    a[0].x = 99;\n"
            "    return a[1].x;\n"
            "}\n"
            "let a: array<P> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "let b: array<P> = clone(a);\n"
            "push(b, P { x: 5, y: 6 });\n"
            "a[0].x = 9;\n"
            "let n: int = firstx(a);\n"
            "print(len(b), b[0].x, b[2].y, n, a[0].x);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @clone(ptr %sret, ptr %p0)") !=
              std::string::npos);
        CHECK(ir.find("define i64 @firstx(ptr %p0)") != std::string::npos);
        // 入口深拷贝（值语义）：被调函数各 1 次 malloc / 退出 1 次 free
        CHECK(count_calls_in(src, "clone", "malloc") == 1);
        CHECK(count_calls_in(src, "clone", "free") == 1);
        CHECK(count_calls_in(src, "firstx", "malloc") == 1);
        CHECK(count_calls_in(src, "firstx", "free") == 1);
        CHECK(count_calls_in(src, "main", "malloc") >= 2);  // a 字面量 + push 扩容
        CHECK(count_calls_in(src, "main", "free") >= 3);    // 扩容旧缓冲 + a / b drop
        CHECK(module_verifies(src));
    }

    // return 字面量 / 调用结果：所有权转移进 sret，不 free
    {
        auto src2 =
            "struct P { x: int; y: int; }\n"
            "fn make() -> array<P> { return [P { x: 1, y: 2 }]; }\n"
            "fn g() -> array<P> { return make(); }\n"
            "let a: array<P> = g();\n"
            "print(len(a), a[0].x);";
        auto ir = module_ir(src2);
        CHECK(ir.find("define void @make(ptr %sret)") != std::string::npos);
        CHECK(ir.find("define void @g(ptr %sret)") != std::string::npos);
        CHECK(function_calls(src2, "g", "make"));
        CHECK(count_calls_in(src2, "make", "free") == 0);  // 字面量转移，不释放
        CHECK(module_verifies(src2));
    }

    // drop 只 free 堆缓冲一次（struct 不含 array，不逐元素释放）
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "fn f() {\n"
            "    let a: array<P> = [P { x: 1, y: 2 }];\n"
            "    print(len(a));\n"
            "}";
        CHECK(count_calls_in(src, "f", "malloc") == 1);
        CHECK(count_calls_in(src, "f", "free") == 1);
        CHECK(module_verifies(src));
    }

    // 错误：初始化 / push / 元素赋值 / 整体读取 / print
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P> = 1;")),
        "array<struct> 初始化必须是字面量、同类型动态数组或返回数组的调用");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P> = [P { x: 1 }];\n"
            "push(a, 1);")),
        "P 值必须是字面量、同类型变量或返回 P 的函数调用");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P> = [P { x: 1 }];\n"
            "a[0] = 1;")),
        "P 值必须是字面量、同类型变量或返回 P 的函数调用");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P> = [P { x: 1 }];\n"
            "let p: P = a[0];")),
        "不支持整体读取 array<struct> 元素");
    // 动态 array<struct> 可直接 print（详细用例见 test_print_aggregate）
    CHECK(module_verifies(
        "struct P { x: int; }\n"
        "let a: array<P> = [P { x: 1 }];\n"
        "print(a);"));
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "struct Q { x: int; }\n"
            "let q: Q = Q { x: 1 };\n"
            "let a: array<P> = [P { x: 1 }];\n"
            "push(a, q);")),
        "需要 P，实际是 Q");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "struct Q { x: int; }\n"
            "let a: array<P> = [P { x: 1 }];\n"
            "let b: array<Q> = a;")),
        "需要 array<Q>");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P> = [P { x: 1 }];\n"
            "let b: array<P, 1> = a;")),
        "不是固定数组");
}

// ---- S3c-3c v1：固定嵌套数组 array<array<T, N>, M>（仅局部）----

static void test_nested_array_s3c3c1() {
    // 语法：嵌套 array 类型归一化
    {
        auto prog = Parser::parse(
            "let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];");
        CHECK(prog.stmts[0]->ty.has_value() &&
              *prog.stmts[0]->ty == "array<array<int,2>,3>");
    }

    // 字面量 + a[i][j] 读写 + 外层/内层运行时边界检查
    // （与 /tmp/nestedarr.tenet 同构，输出 1 9 4 7 6）
    {
        auto src =
            "let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\n"
            "a[0][1] = 9;\n"
            "a[2][0] = 7;\n"
            "print(a[0][0], a[0][1], a[1][1], a[2][0], a[2][1]);";
        auto ir = module_ir(src);
        // 3 个外层元素 × 内层 2 个标量槽 = 6 个连续 8 字节槽
        CHECK(ir.find("alloca [6 x i64]") != std::string::npos);
        CHECK(count_text(ir, "alloca [6 x i64]") == 1);
        // 扁平槽：a[0][1] → 槽 1；a[2][0] → 槽 4
        CHECK(ir.find("getelementptr [6 x i64], ptr %a, i64 0, i64 1") !=
              std::string::npos);
        CHECK(ir.find("getelementptr [6 x i64], ptr %a, i64 0, i64 4") !=
              std::string::npos);
        CHECK(ir.find("store i64 9") != std::string::npos);
        CHECK(ir.find("store i64 7") != std::string::npos);
        // 每次 a[i][j] 访问都生成外层 + 内层两次边界检查
        CHECK(count_text(ir, "call void @tenet_bounds_fail") >= 4);
        CHECK(module_verifies(src));
    }

    // 动态下标：外层与内层都生成运行时 icmp uge / tenet_bounds_fail
    {
        auto src =
            "let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\n"
            "let i: int = 1;\n"
            "let j: int = 1;\n"
            "a[i][j] = 8;\n"
            "print(a[i][j], a[0][1]);";
        auto ir = module_ir(src);
        CHECK(ir.find("icmp uge i64") != std::string::npos);
        CHECK(ir.find("call void @tenet_bounds_fail") != std::string::npos);
        CHECK(ir.find("mul i64") != std::string::npos);  // i*N + j
        CHECK(count_calls_in(src, "main", "tenet_bounds_fail") >= 1);
        CHECK(module_verifies(src));
    }

    // 同类型变量深拷贝：let b = a；显式标注拷贝同样支持
    {
        auto src =
            "let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\n"
            "let b = a;\n"
            "let c: array<array<int, 2>, 3> = b;\n"
            "b[0][0] = 9;\n"
            "print(a[0][0], b[0][0], c[0][0], len(a));";
        auto ir = module_ir(src);
        CHECK(count_text(ir, "alloca [6 x i64]") == 3);  // a / b / c 各自独立
        CHECK(ir.find("%b = alloca [6 x i64]") != std::string::npos);
        CHECK(ir.find("%c = alloca [6 x i64]") != std::string::npos);
        CHECK(ir.find("store i64 9") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 省略标注时由嵌套字面量推断 array<array<int,2>,2>
    {
        auto src =
            "let a = [[1, 2], [3, 4]];\n"
            "a[1][0] = 8;\n"
            "print(a[0][1], a[1][0]);";
        auto ir = module_ir(src);
        CHECK(ir.find("alloca [4 x i64]") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 内层 float：按 8 字节槽 bitcast 打包/解包
    {
        auto src =
            "let x: float = 1.5;\n"
            "let a: array<array<float, 2>, 2> = [[x, 2.5], [3.5, 4.5]];\n"
            "print(a[0][0], a[1][1]);";
        auto ir = module_ir(src);
        CHECK(ir.find("alloca [4 x i64]") != std::string::npos);
        CHECK(ir.find("bitcast double") != std::string::npos);
        CHECK(ir.find("bitcast i64") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // len(a) 仍是外层编译期常量；暂不支持 len(a[i])
    {
        CHECK(printf_has_int_constant(
            "let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\n"
            "print(len(a));",
            3));
        CHECK_THROWS(
            Codegen::compile(Parser::parse(
                "let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\n"
                "print(len(a[0]));")),
            "`len` 参数必须是数组变量");
    }

    // 拒绝：内层 bool / 更深嵌套 / 动态嵌套 / 参数 / 返回值 / 整体读取 / 整体赋值
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<bool, 2>, 2> = [[true, false], [false, true]];")),
        "嵌套数组内层暂不支持 bool");
    CHECK_THROWS(
        Codegen::compile(Parser::parse("let a = [[true], [false]];")),
        "嵌套数组内层暂不支持 bool");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<array<int, 2>, 2>, 2> ="
            " [[[1, 2], [3, 4]], [[5, 6], [7, 8]]];")),
        "嵌套数组元素只支持标量 int/float");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<string, 2>, 2> = [[\"a\", \"b\"], [\"c\", \"d\"]];")),
        "嵌套数组元素只支持标量 int/float");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int, 2>> = [[1, 2]];")),
        "动态嵌套数组尚未支持");
    // S3c-3c v2：固定嵌套数组参数/返回值走 ptr + sret 扁平槽 ABI。
    CHECK(module_ir(
              "fn f(a: array<array<int, 2>, 2>) -> int { return a[0][0]; }")
              .find("define i64 @f(ptr %p0)") != std::string::npos);
    CHECK(module_ir(
              "fn f() -> array<array<int, 2>, 2> {"
              " return [[1, 2], [3, 4]]; }")
              .find("define void @f(ptr %sret)") != std::string::npos);
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
            "print(a[0]);")),
        "不支持整体读取嵌套数组元素");
    // 整体赋值：同类型变量 / 字面量深拷贝（与 let 初始化同一套校验）
    {
        auto src =
            "let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
            "let b: array<array<int, 2>, 2> = [[5, 6], [7, 8]];\n"
            "b = a;\n"
            "a = [[9, 10], [11, 12]];\n"
            "print(a[0][0], b[1][1]);";
        CHECK(module_verifies(src));
        CHECK_THROWS(
            Codegen::compile(Parser::parse(
                "let a: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
                "a = [[1, 2], [3]];")),
            "内层数组长度不匹配");
    }

    // 长度 / 元素形态 / 初始化表达式错误
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int, 2>, 2> = [[1, 2], [3, 4], [5, 6]];")),
        "数组长度不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int, 2>, 2> = [[1], [3, 4]];")),
        "内层数组长度不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int, 2>, 2> = [[1, 2, 3], [3, 4]];")),
        "内层数组长度不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int, 2>, 2> = [[1, 2], 3];")),
        "嵌套数组元素必须是 [ ... ] 字面量");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int, 2>, 2> = [[1, 2], [3, 4.5]];")),
        "数组元素 [1][1] 类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f() -> int { return 0; }\n"
            "let a: array<array<int, 2>, 2> = f();")),
        "调用返回 i64");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let c: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\n"
            "let b: array<array<int, 2>, 2> = c;")),
        "需要 array<array<int,2>,2>");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int, 2>, 2> = [];")),
        "固定数组不支持空字面量");
}

// ---- S3c-3b-3 / S3c-3c v2：固定数组签名 ABI ----
// array<struct, N> / array<array<T, N>, M> 参数传 ptr + 入口按总槽数拷贝到本地
// `[total x i64]`；返回值走隐藏 ptr %sret（函数返回 void），调用方 let b = f() 接管。

static void test_fixed_array_abi_s3c3b3() {
    // 语法：固定 array<struct, N> 可出现在参数与返回类型位置
    {
        auto prog = Parser::parse(
            "struct P { x: int; y: int; }\n"
            "fn pid(a: array<P, 2>) -> array<P, 2> { return a; }");
        CHECK(prog.stmts[1]->params.size() == 1);
        CHECK(prog.stmts[1]->params[0].second == "array<P,2>");
        CHECK(prog.stmts[1]->ret.has_value() && *prog.stmts[1]->ret == "array<P,2>");
    }

    // array<struct, N> 参数/返回值：ptr + 隐藏 sret；入口/返回都按 N*slots 槽拷贝，
    // 调用方 let b = f() 从 sret 缓冲逐槽接管本地扁平数组。
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "fn pid(a: array<P, 2>) -> array<P, 2> { return a; }\n"
            "let a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\n"
            "let b: array<P, 2> = pid(a);\n"
            "b[0].x = 9;\n"
            "print(b[0].x, b[1].y);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @pid(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(ir.find("call void @pid(ptr %pid.sret, ptr %pid.arg0)") !=
              std::string::npos);
        // pid 本地参数 / main 的 a、实参缓冲、返回缓冲、b 共 5 个 [4 x i64]
        CHECK(count_text(ir, "alloca [4 x i64]") == 5);
        // 入口 4 槽 + sret 4 槽（外加 main 里 a 初始化 / b 接管）
        CHECK(count_text(ir, "store i64") >= 8);
        CHECK(module_verifies(src));
    }

    // 字面量实参 / 调用结果实参 / 返回调用结果（pid(pid(c)) / pid(make())）
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "fn pid(a: array<P, 2>) -> array<P, 2> { return a; }\n"
            "fn make() -> array<P, 2> { return [P { x: 5, y: 6 }, P { x: 7, y: 8 }]; }\n"
            "let c: array<P, 2> = pid([P { x: 1, y: 2 }, P { x: 3, y: 4 }]);\n"
            "let d: array<P, 2> = pid(pid(c));\n"
            "let e: array<P, 2> = pid(make());\n"
            "print(c[0].x, d[1].y, e[0].y);";
        auto ir = module_ir(src);
        CHECK(count_calls_in(src, "main", "pid") == 4);
        CHECK(ir.find("call void @make") != std::string::npos);
        CHECK(ir.find("alloca [4 x i64]") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 元素槽数为 1 的 struct 数组仍走扁平布局（不是标量数组 ABI）
    {
        auto src =
            "struct P { x: int; }\n"
            "fn one(a: array<P, 1>) -> array<P, 1> { return a; }\n"
            "let a: array<P, 1> = [P { x: 1 }];\n"
            "let b: array<P, 1> = one(a);\n"
            "b[0].x = 7;\n"
            "print(a[0].x, b[0].x);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @one(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(ir.find("alloca [1 x i64]") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 固定嵌套 array<array<T, N>, M> 参数/返回值：总槽数 M*N；a[i][j] 本地读写。
    {
        auto src =
            "fn nid(a: array<array<int, 2>, 2>) -> array<array<int, 2>, 2> { return a; }\n"
            "let n: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
            "let m: array<array<int, 2>, 2> = nid(n);\n"
            "m[0][1] = 7;\n"
            "print(n[0][0], m[0][1]);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @nid(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(ir.find("call void @nid(ptr %nid.sret, ptr %nid.arg0)") !=
              std::string::npos);
        // nid 本地参数 / main 的 n、实参缓冲、返回缓冲、m 共 5 个 [4 x i64]
        CHECK(count_text(ir, "alloca [4 x i64]") == 5);
        CHECK(ir.find("call void @tenet_bounds_fail") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 嵌套字面量实参 / 调用结果实参 / 参数内 a[i][j] 读取
    {
        auto src =
            "fn nid(a: array<array<int, 2>, 2>) -> array<array<int, 2>, 2> { return a; }\n"
            "fn sum(a: array<array<int, 2>, 2>) -> int { return a[0][0] + a[1][1]; }\n"
            "let m: array<array<int, 2>, 2> = nid([[5, 6], [7, 8]]);\n"
            "let k: array<array<int, 2>, 2> = nid(nid(m));\n"
            "print(sum(m), k[0][1]);";
        auto ir = module_ir(src);
        CHECK(count_calls_in(src, "main", "nid") == 3);
        CHECK(ir.find("call i64 @sum") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 内层 float：参数/返回值仍按 8 字节槽传递，a[i][j] 读写做 bitcast
    {
        auto src =
            "fn nf(a: array<array<float, 2>, 2>) -> array<array<float, 2>, 2> { return a; }\n"
            "let f: array<array<float, 2>, 2> = [[1.5, 2.5], [3.5, 4.5]];\n"
            "let g: array<array<float, 2>, 2> = nf(f);\n"
            "print(g[1][1]);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @nf(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(ir.find("bitcast i64") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 错误：内层 bool / 动态内层 / 动态嵌套数组 / 实参类型不匹配 / 非法初始化
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f(a: array<array<bool, 2>, 2>) -> int { return 0; }")),
        "嵌套数组内层暂不支持 bool");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f() -> array<array<bool, 2>, 2> {"
            " return [[true, false], [false, true]]; }")),
        "嵌套数组内层暂不支持 bool");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f(a: array<array<int>, 2>) -> int { return 0; }")),
        "嵌套数组内层必须是固定长度 array<T, N>");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f() -> array<array<int, 2>> { return [[1, 2]]; }")),
        "动态嵌套数组尚未支持");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "fn f(a: array<P, 2>) -> int { return 0; }\n"
            "let b: array<P, 3> = [P { x: 1 }, P { x: 2 }, P { x: 3 }];\n"
            "print(f(b));")),
        "数组参数类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P, 2> = 1;")),
        "初始化必须是字面量、同类型数组变量或返回数组的调用");

    // 返回值缺失仍按原规则拒绝
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "fn f() -> array<P, 2> { return; }")),
        "return 必须带值");
}

// ---- S3c-3b-4：固定数组整体赋值 b = a / b = [..] / b = f() ----
// 右侧先按总槽数打包到临时 `[total x i64]` 缓冲，再逐槽覆盖目标；固定数组无堆。

static void test_fixed_array_assign_s3c3b4() {
    // 标量固定数组：原有 b = a / b = [..] / b = f() 路径不受扁平分支影响
    {
        auto src =
            "fn mk() -> array<int, 3> { return [7, 8, 9]; }\n"
            "let a: array<int, 3> = [1, 2, 3];\n"
            "let b: array<int, 3> = [0, 0, 0];\n"
            "b = a;\n"
            "b = [4, 5, 6];\n"
            "b = mk();\n"
            "print(b[0], b[1], b[2]);";
        auto ir = module_ir(src);
        CHECK(ir.find("call void @mk(ptr %mk.sret)") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // array<struct, N>：变量 / 字面量 / 返回数组的调用三种右侧都按 N*slots 槽覆盖
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "fn mk() -> array<P, 2> { return [P { x: 1, y: 2 }, P { x: 3, y: 4 }]; }\n"
            "let a: array<P, 2> = [P { x: 5, y: 6 }, P { x: 7, y: 8 }];\n"
            "let b: array<P, 2> = [P { x: 0, y: 0 }, P { x: 0, y: 0 }];\n"
            "b = a;\n"
            "b = [P { x: 9, y: 10 }, P { x: 11, y: 12 }];\n"
            "b = mk();\n"
            "b[0].x = 42;\n"
            "print(b[0].x, b[1].y);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @mk(ptr %sret)") != std::string::npos);
        CHECK(ir.find("call void @mk(ptr %mk.sret)") != std::string::npos);
        CHECK(ir.find("alloca [4 x i64]") != std::string::npos);
        CHECK(ir.find("store i64 42") != std::string::npos);
        CHECK(count_calls_in(src, "main", "malloc") == 0);  // 固定数组无堆
        CHECK(module_verifies(src));
    }

    // array<P,1>：单字段 struct 数组（slots == 1）仍走扁平路径，b = f() 整体赋值
    // （与 /tmp/bassign.tenet 同构，输出 7 1 2）
    {
        auto src =
            "struct P { x: int; }\n"
            "fn f() -> array<P, 1> { return [P { x: 7 }]; }\n"
            "fn n() -> array<array<int, 1>, 2> { return [[1], [2]]; }\n"
            "let b: array<P, 1> = [P { x: 0 }];\n"
            "b = f();\n"
            "let m: array<array<int, 1>, 2> = [[0], [0]];\n"
            "m = n();\n"
            "print(b[0].x, m[0][0], m[1][0]);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @f(ptr %sret)") != std::string::npos);
        CHECK(ir.find("alloca [1 x i64]") != std::string::npos);
        CHECK(ir.find("call void @f(ptr %f.sret)") != std::string::npos);
        CHECK(ir.find("call void @n(ptr %n.sret)") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 固定嵌套数组：b = a / b = [[..]] / b = f()（内层 1 槽同样支持）
    {
        auto src =
            "fn n() -> array<array<int, 1>, 2> { return [[1], [2]]; }\n"
            "let m: array<array<int, 1>, 2> = [[0], [0]];\n"
            "m = n();\n"
            "m = [[3], [4]];\n"
            "let k: array<array<int, 1>, 2> = [[5], [6]];\n"
            "m = k;\n"
            "print(m[0][0], m[1][0]);";
        auto ir = module_ir(src);
        CHECK(ir.find("call void @n(ptr %n.sret)") != std::string::npos);
        CHECK(ir.find("alloca [2 x i64]") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // array<P,1> 局部 / 参数 / 返回值 / 字段读写 / 元素赋值全链路
    {
        auto src =
            "struct P { x: int; }\n"
            "fn one(a: array<P, 1>) -> array<P, 1> {\n"
            "    a[0].x = a[0].x + 1;\n"
            "    a[0] = P { x: a[0].x + 1 };\n"
            "    return a;\n"
            "}\n"
            "let a: array<P, 1> = [P { x: 1 }];\n"
            "let b: array<P, 1> = one(a);\n"
            "b[0].x = 9;\n"
            "print(a[0].x, b[0].x);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @one(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(ir.find("alloca [1 x i64]") != std::string::npos);
        CHECK(ir.find("call void @one(ptr %one.sret, ptr %one.arg0)") !=
              std::string::npos);
        CHECK(module_verifies(src));
    }

    // array<array<int,1>,M> 局部 / 参数 / 返回值 / 元素读写（内层 1 槽仍走嵌套路径）
    {
        auto src =
            "fn nid(a: array<array<int, 1>, 2>) -> array<array<int, 1>, 2> { return a; }\n"
            "let n: array<array<int, 1>, 2> = [[1], [2]];\n"
            "n[0][0] = 9;\n"
            "let m: array<array<int, 1>, 2> = nid(n);\n"
            "m[1][0] = 7;\n"
            "print(n[0][0], n[1][0], m[0][0], m[1][0]);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @nid(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(ir.find("alloca [2 x i64]") != std::string::npos);
        CHECK(ir.find("call void @tenet_bounds_fail") != std::string::npos);
        CHECK(module_verifies(src));
    }
}

// ---- print aggregate（struct / 定长数组 / 动态数组 / 嵌套数组）----

static void test_print_aggregate() {
    // 1) struct：`P { x: 1, y: 2.5 }`；扁平字段逐个 printf 片段。
    {
        auto src =
            "struct P { x: int; y: float; }\n"
            "let p: P = P { x: 1, y: 2.5 };\n"
            "print(p);";
        auto ir = module_ir(src);
        CHECK(ir.find("c\"P { \\00\"") != std::string::npos);
        CHECK(ir.find("c\"x: \\00\"") != std::string::npos);
        CHECK(ir.find("c\"y: \\00\"") != std::string::npos);
        CHECK(ir.find("c\" }\\00\"") != std::string::npos);
        CHECK(ir.find("c\"%lld\\00\"") != std::string::npos);
        CHECK(ir.find("c\"%g\\00\"") != std::string::npos);
        CHECK(count_calls_in(src, "main", "printf") == 8);
        CHECK(module_verifies(src));
    }

    // 2) 嵌套 struct：字段名用扁平路径（`Q { p.x: 1, p.y: 2, z: 3 }`）。
    {
        auto src =
            "struct P { x: int; y: int; }\n"
            "struct Q { p: P; z: int; }\n"
            "let q: Q = Q { p: P { x: 1, y: 2 }, z: 3 };\n"
            "print(q);";
        auto ir = module_ir(src);
        CHECK(ir.find("c\"p.x: \\00\"") != std::string::npos);
        CHECK(ir.find("c\"p.y: \\00\"") != std::string::npos);
        CHECK(ir.find("c\"z: \\00\"") != std::string::npos);
        CHECK(ir.find("c\"p: \\00\"") == std::string::npos);
        CHECK(module_verifies(src));
    }

    // 3) 定长标量数组：编译期展开 `[1, 2, 3]`，无运行时循环。
    {
        auto src = "let a: array<int, 3> = [1, 2, 3];\nprint(a);";
        auto ir = module_ir(src);
        CHECK(count_text(ir, "c\"%lld\\00\"") == 3);
        CHECK(count_text(ir, "c\", \\00\"") == 2);
        CHECK(ir.find("c\"[\\00\"") != std::string::npos);
        CHECK(ir.find("c\"]\\00\"") != std::string::npos);
        CHECK(ir.find("pr.cond") == std::string::npos);
        CHECK(count_calls_in(src, "main", "printf") == 8);
        CHECK(module_verifies(src));
    }
    {
        auto ir = module_ir("let f: array<float, 2> = [1.5, 2.5];\nprint(f);");
        CHECK(count_text(ir, "c\"%g\\00\"") == 2);
    }
    {
        auto src = "let b: array<bool, 2> = [true, false];\nprint(b);";
        auto ir = module_ir(src);
        CHECK(ir.find("c\"true\\00\"") != std::string::npos);
        CHECK(ir.find("c\"false\\00\"") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 4) 定长 struct 数组：每个元素按 slots 槽步长展开为 `P { ... }`。
    {
        auto src =
            "struct P { x: int; y: float; }\n"
            "let a: array<P, 2> = [P { x: 3, y: 4.5 }, P { x: 5, y: 6.5 }];\n"
            "print(a);";
        auto ir = module_ir(src);
        CHECK(count_text(ir, "c\"P { \\00\"") == 2);
        CHECK(count_text(ir, "c\"%lld\\00\"") == 2);
        CHECK(count_text(ir, "c\"%g\\00\"") == 2);
        CHECK(count_calls_in(src, "main", "malloc") == 0);
        CHECK(count_calls_in(src, "main", "printf") == 18);
        CHECK(module_verifies(src));
    }
    {
        auto src =
            "struct P { x: int; }\n"
            "let a: array<P, 1> = [P { x: 7 }];\n"
            "print(a);";
        auto ir = module_ir(src);
        CHECK(count_text(ir, "c\"P { \\00\"") == 1);
        CHECK(module_verifies(src));
    }

    // 5) 动态标量数组：运行时循环（索引存栈槽），len 从描述符读取。
    {
        auto src = "let d: array<int> = [7, 8];\nprint(d);";
        auto ir = module_ir(src);
        CHECK(ir.find("pr.cond") != std::string::npos);
        CHECK(ir.find("pr.body") != std::string::npos);
        CHECK(ir.find("pr.sep") != std::string::npos);
        CHECK(ir.find("pr.after") != std::string::npos);
        CHECK(ir.find("pr.end") != std::string::npos);
        CHECK(count_text(ir, "c\"%lld\\00\"") == 1);  // 循环体复用格式串
        CHECK(count_calls_in(src, "main", "printf") == 5);
        CHECK(module_verifies(src));
    }
    {
        auto src = "let f: array<float> = [1.5, 2.5];\nprint(f);";
        CHECK(count_text(module_ir(src), "c\"%g\\00\"") == 1);
        CHECK(module_verifies(src));
    }
    {
        auto src = "let b: array<bool> = [true];\nprint(b);";
        auto ir = module_ir(src);
        CHECK(ir.find("c\"true\\00\"") != std::string::npos);
        CHECK(ir.find("c\"false\\00\"") != std::string::npos);
        CHECK(module_verifies(src));
    }
    {
        // 空动态数组输出 `[]`：循环仍生成，运行时零次迭代。
        auto src = "let e: array<int> = [];\nprint(e);";
        auto ir = module_ir(src);
        CHECK(ir.find("pr.cond") != std::string::npos);
        CHECK(ir.find("c\"[\\00\"") != std::string::npos);
        CHECK(ir.find("c\"]\\00\"") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 6) 动态 struct 数组：元素 stride = slots 槽，循环体复用 struct 格式片段。
    {
        auto src =
            "struct P { x: int; y: float; }\n"
            "let d: array<P> = [P { x: 1, y: 1.5 }];\n"
            "print(d);";
        auto ir = module_ir(src);
        CHECK(ir.find("pr.cond") != std::string::npos);
        CHECK(count_text(ir, "c\"P { \\00\"") == 1);
        CHECK(count_text(ir, "c\"%lld\\00\"") == 1);
        CHECK(count_text(ir, "c\"%g\\00\"") == 1);
        CHECK(count_calls_in(src, "main", "printf") == 11);
        CHECK(module_verifies(src));
    }

    // 7) 定长嵌套数组：外层/内层都编译期展开为 `[[1, 2], [3, 4]]`。
    {
        auto src = "let n: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\nprint(n);";
        auto ir = module_ir(src);
        CHECK(count_text(ir, "c\"[\\00\"") == 3);
        CHECK(count_text(ir, "c\"]\\00\"") == 3);
        CHECK(count_text(ir, "c\"%lld\\00\"") == 4);
        CHECK(count_text(ir, "c\", \\00\"") == 3);
        CHECK(ir.find("pr.cond") == std::string::npos);
        CHECK(module_verifies(src));
    }

    // 8) print 多参：aggregate 与标量之间一个空格；结尾换行。
    {
        auto src =
            "struct P { x: int; }\n"
            "let p: P = P { x: 1 };\n"
            "print(p, 2, p);";
        auto ir = module_ir(src);
        CHECK(count_text(ir, "c\" \\00\"") == 2);
        CHECK(count_text(ir, "c\"\\0A\\00\"") == 1);
        CHECK(count_text(ir, "c\"%lld\\00\"") == 3);
        CHECK(count_calls_in(src, "main", "printf") == 12);
        CHECK(module_verifies(src));
    }

    // 9) 纯标量 / 字符串 / 数组元素仍走单次 printf（既有行为不变）。
    {
        auto src =
            "let a: array<int, 2> = [1, 2];\n"
            "print(a[0], len(a), \"s\", true, 2.5);";
        CHECK(count_calls_in(src, "main", "printf") == 1);
        CHECK(count_text(module_ir(src), "c\"%lld %lld %s %s %g\\0A\\00\"") == 1);
        CHECK(module_verifies(src));
    }

    // 10) struct 的 bool 字段：输出 true / false。
    {
        auto src =
            "struct B { b: bool; f: float; }\n"
            "let b: B = B { b: true, f: 1.5 };\n"
            "print(b);";
        auto ir = module_ir(src);
        CHECK(ir.find("c\"true\\00\"") != std::string::npos);
        CHECK(ir.find("c\"false\\00\"") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 11) aggregate 表达式（不是变量）明确报错：调用 / 字面量 / 元素整体读取。
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "fn mk() -> P { return P { x: 1 }; }\n"
            "print(mk());")),
        "print 不支持 struct");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn mk() -> array<int, 2> { return [1, 2]; }\nprint(mk());")),
        "print 不支持该类型的值");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let p = P { x: 1 };\n"
            "fn mk() -> P { return P { x: 2 }; }\n"
            "print(p, mk());")),
        "print 不支持 struct");
    CHECK_THROWS(Codegen::compile(Parser::parse("print([1, 2]);")),
                 "数组字面量只能用于");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct P { x: int; }\nprint(P { x: 1 });")),
                 "struct 字面量只能用于");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<P, 1> = [P { x: 1 }];\n"
            "print(a[0]);")),
        "不支持整体读取 array<struct> 元素");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let n: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\n"
            "print(n[0]);")),
        "不支持整体读取嵌套数组元素");
}

// ---- S3c-3d：动态嵌套数组 array<array<T>> v1 ----
// 外层动态、内层动态标量数组；外层堆元素是内层 descriptor [data,len,cap]
// （3 个 i64 槽，stride = 24 字节）。覆盖字面量 / 深拷贝 / push / 二级下标 /
// drop / 参数与返回值 / print / 双层边界检查 / 明确拒绝的非法形态。

static void test_dynamic_nested_array_s3c3d() {
    // 语法：`array<array<int>>` 类型归一化；参数/返回位置接受动态嵌套数组。
    {
        auto prog = Parser::parse(
            "let a: array<array<int>> = [[1, 2], [3]];\n"
            "fn clone(x: array<array<int>>) -> array<array<int>> { return x; }");
        CHECK(prog.stmts[0]->ty.has_value() &&
              *prog.stmts[0]->ty == "array<array<int>>");
        CHECK(prog.stmts[1]->params.size() == 1);
        CHECK(prog.stmts[1]->params[0].second == "array<array<int>>");
        CHECK(prog.stmts[1]->ret.has_value() &&
              *prog.stmts[1]->ret == "array<array<int>>");
    }

    // 字面量布局：外层 cap = max(2,4) = 4 → 4*3*8 = 96 字节；两行内层各 cap=4
    // → 32 字节；外层元素按 [data,len,cap] 三槽访问（getelementptr [3 x i64]）。
    {
        auto src =
            "let a: array<array<int>> = [[1, 2], [3]];\n"
            "print(a);";
        auto ir = module_ir(src);
        CHECK(ir.find("call ptr @malloc(i64 96)") != std::string::npos);
        CHECK(count_text(ir, "call ptr @malloc(i64 32)") == 2);
        CHECK(count_calls_in(src, "main", "malloc") == 3);  // 外层 + 两行内层
        CHECK(count_calls_in(src, "main", "free") == 2);    // 内层循环 free + 外层 free
        CHECK(ir.find("getelementptr [3 x i64]") != std::string::npos);
        CHECK(count_blocks_named(src, "main", "dyn.drop.inner.free") == 1);
        CHECK(module_verifies(src));
    }

    // 空字面量 + push：外层 96 字节；push 内层空数组时临时内层 32 字节，
    // 容量不足走 cap*2（新外层字节数按 24 字节/元素计算）。
    {
        auto src =
            "let a: array<array<int>> = [];\n"
            "push(a, []);\n"
            "print(len(a), len(a[0]));";
        auto ir = module_ir(src);
        CHECK(ir.find("call ptr @malloc(i64 96)") != std::string::npos);
        CHECK(ir.find("call ptr @malloc(i64 32)") != std::string::npos);
        CHECK(ir.find("mul i64 %dyn.cap, 2") != std::string::npos);   // 外层 cap*2
        CHECK(ir.find("mul i64 %dyn.newcap, 24") != std::string::npos);
        CHECK(ir.find("mul i64 %dyn.len, 3") != std::string::npos);   // 外层元素 stride=3
        CHECK(count_blocks_named(src, "main", "dyn.grow.after") == 1);
        // len(a[0]) 只做外层一次边界检查（内层 len 直接读 descriptor 槽）。
        CHECK(count_calls_in(src, "main", "tenet_bounds_fail") == 1);
        // len(a) 是运行时读取，不是编译期常量 1。
        CHECK(!printf_has_int_constant(src, 1));
        CHECK(module_verifies(src));
    }

    // 用户程序（与 /tmp/dynnest.tenet 同构）：字面量 + push + 深拷贝 +
    // 二级下标写 + len/元素 print + 参数入口深拷贝 + sret 转移。
    {
        auto src =
            "let a: array<array<int>> = [[1, 2], [3]];\n"
            "push(a, [4, 5]);\n"
            "let b: array<array<int>> = a;\n"
            "a[0][0] = 9;\n"
            "print(len(a), a[0][0], a[1][0], b[0][0]);\n"
            "fn clone(x: array<array<int>>) -> array<array<int>> { return x; }\n"
            "let c: array<array<int>> = clone(b);\n"
            "print(len(c), c[0][1]);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @clone(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(count_calls_in(src, "main", "clone") == 1);
        CHECK(count_calls_in(src, "main", "malloc") == 7);
        CHECK(count_calls_in(src, "main", "free") == 7);
        // a[0][0] / a[1][0] / b[0][0] / c[0][1] 各两层 + 写 a[0][0] 两层。
        CHECK(count_calls_in(src, "main", "tenet_bounds_fail") >= 8);
        CHECK(count_blocks_named(src, "main", "nested.copy.cond") == 1);  // let b = a
        CHECK(count_blocks_named(src, "clone", "nested.copy.cond") == 1); // 参数入口
        CHECK(count_blocks_named(src, "main", "dyn.grow.after") == 1);    // push
        CHECK(count_blocks_named(src, "main", "dyn.drop.inner.free") == 3);
        CHECK(module_verifies(src));
    }

    // 深拷贝：`let b = a` 与 `b = a` 都逐内层复制，互不影响；整体赋值前先 drop 旧值。
    {
        auto src =
            "let a: array<array<int>> = [[1], [2]];\n"
            "let b: array<array<int>> = a;\n"
            "b = a;\n"
            "a[0][0] = 9;\n"
            "print(b[0][0]);";
        CHECK(count_blocks_named(src, "main", "nested.copy.cond") == 2);
        CHECK(count_blocks_named(src, "main", "dyn.drop.inner.free") == 3);
        CHECK(count_calls_in(src, "main", "malloc") == 7);
        CHECK(count_calls_in(src, "main", "free") == 6);
        CHECK(module_verifies(src));
    }

    // push 内层变量 / 内层字面量：变量先深拷贝再追加，后续修改 r 不影响 a。
    {
        auto src =
            "let a: array<array<int>> = [];\n"
            "let r: array<int> = [7];\n"
            "push(a, [1, 2]);\n"
            "push(a, r);\n"
            "r[0] = 9;\n"
            "print(a[1][0]);";
        CHECK(count_blocks_named(src, "main", "dyn.grow.after") == 2);
        CHECK(count_calls_in(src, "main", "malloc") == 6);
        CHECK(count_calls_in(src, "main", "free") == 5);
        CHECK(count_calls_in(src, "main", "tenet_bounds_fail") == 3);
        CHECK(module_verifies(src));
    }

    // push 返回内层数组的调用：调用结果 descriptor 转移进外层元素（不重复 malloc）。
    {
        auto src =
            "fn mk() -> array<int> { return [9]; }\n"
            "let a: array<array<int>> = [];\n"
            "push(a, mk());\n"
            "print(a[0][0]);";
        CHECK(count_blocks_named(src, "main", "dyn.grow.after") == 1);
        CHECK(count_calls_in(src, "main", "malloc") == 2);  // 外层 + 扩容
        CHECK(count_calls_in(src, "main", "free") == 3);    // 扩容旧外层 + 内层 + 外层
        CHECK(count_calls_in(src, "main", "tenet_bounds_fail") == 2);
        CHECK(module_verifies(src));
    }

    // 内层 float / bool：8 字节槽 bitcast / zext·trunc；print 走内层行循环。
    {
        auto src =
            "let x: float = 1.5;\n"
            "let f: array<array<float>> = [[x], [2.5]];\n"
            "print(f);\n"
            "let b: array<array<bool>> = [[true], [false]];\n"
            "print(b);";
        auto ir = module_ir(src);
        CHECK(ir.find("bitcast double") != std::string::npos);
        CHECK(ir.find("bitcast i64") != std::string::npos);
        CHECK(ir.find("trunc i64") != std::string::npos);
        CHECK(ir.find("select i1") != std::string::npos);
        CHECK(ir.find("c\"%g\\00\"") != std::string::npos);
        CHECK(count_blocks_named(src, "main", "pnr.cond") == 2);
        CHECK(count_calls_in(src, "main", "printf") == 16);
        CHECK(module_verifies(src));
    }

    // 参数入口逐内层深拷贝：`clone(x)` 入口 malloc 外层 + 内层；调用方 let 接管 sret。
    {
        auto src =
            "fn clone(x: array<array<int>>) -> array<array<int>> { return x; }\n"
            "let a: array<array<int>> = [[1]];\n"
            "let b: array<array<int>> = clone(a);\n"
            "let c: array<array<int>> = clone([[2]]);\n"
            "print(len(b), len(c));";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @clone(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(count_calls_in(src, "main", "clone") == 2);
        CHECK(count_blocks_named(src, "clone", "nested.copy.cond") == 1);
        CHECK(count_calls_in(src, "clone", "malloc") == 2);
        CHECK(count_calls_in(src, "main", "malloc") == 4);
        CHECK(count_calls_in(src, "main", "free") == 8);
        CHECK(module_verifies(src));
    }

    // return 字面量：函数内构造动态嵌套数组后把 data/len/cap 转移进 sret（不 free）。
    {
        auto src =
            "fn f() -> array<array<int>> { return [[1], [2]]; }\n"
            "let a: array<array<int>> = f();\n"
            "print(len(a));";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @f(ptr %sret)") != std::string::npos);
        CHECK(count_calls_in(src, "f", "malloc") == 3);
        CHECK(count_calls_in(src, "f", "free") == 0);
        CHECK(count_calls_in(src, "main", "malloc") == 0);
        CHECK(count_calls_in(src, "main", "free") == 2);
        CHECK(module_verifies(src));
    }

    // 双层边界检查：a[i][j] 两次；len(a[i]) 只有外层一次。
    {
        auto src = "let a: array<array<int>> = [[1]];\nprint(a[0][0]);";
        CHECK(count_calls_in(src, "main", "tenet_bounds_fail") == 2);
        CHECK(module_verifies(src));
        auto lsrc = "let a: array<array<int>> = [[1]];\nprint(len(a[0]));";
        auto lir = module_ir(lsrc);
        CHECK(count_calls_in(lsrc, "main", "tenet_bounds_fail") == 1);
        CHECK(lir.find("getelementptr [3 x i64]") != std::string::npos);
        CHECK(module_verifies(lsrc));
    }

    // 作用域 drop：先逐内层 free(data)，再 free 外层（循环体每轮 / 函数退出）。
    {
        auto src =
            "let i: int = 0;\n"
            "while (i < 1) {\n"
            "    let a: array<array<int>> = [[1], [2]];\n"
            "    i = i + 1;\n"
            "}";
        CHECK(count_blocks_named(src, "main", "dyn.drop.inner.free") == 1);
        CHECK(count_blocks_named(src, "main", "dyn.drop.rows") == 1);
        CHECK(count_calls_in(src, "main", "free") == 2);
        CHECK(module_verifies(src));
    }

    // 整体读取 / 整体赋值内层数组：明确拒绝（只支持 a[i][j]）。
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int>> = [[1]];\nprint(a[0]);")),
        "整体读取");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int>> = [[1]];\na[0] = [2];")),
        "整体赋值");

    // 不支持的类型形态：array<struct> 内层 / 更深嵌套 / 固定内层。
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "let a: array<array<P>> = [[P { x: 1 }]];")),
        "不支持 array<struct>");
    CHECK_THROWS(
        Codegen::compile(Parser::parse("let a: array<array<array<int>>> = [[[1]]];")),
        "只支持一层");
    CHECK_THROWS(
        Codegen::compile(Parser::parse("let a: array<array<int, 2>> = [[1, 2]];")),
        "内层必须是动态数组");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f(a: array<array<int, 2>>) -> int { return len(a); }")),
        "内层必须是动态数组");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f() -> array<array<int, 2>> { return [[1, 2]]; }")),
        "内层必须是动态数组");

    // 元素类型 / 初始化 / push / 参数类型错误。
    CHECK_THROWS(
        Codegen::compile(Parser::parse("let a: array<array<int>> = [[1], 2];")),
        "嵌套数组第");
    CHECK_THROWS(
        Codegen::compile(Parser::parse("let a: array<array<int>> = [[1], [2.5]];")),
        "类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int>> = [[1]];\npush(a, [1.5]);")),
        "类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int>> = [[1]];\npush(a, 1);")),
        "push 的嵌套数组值必须");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a: array<array<int>> = 1;")),
                 "动态嵌套数组初始化必须是");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "fn f(x: array<array<int>>) -> int { return len(x); }\n"
            "let a: array<array<float>> = [[1.0]];\n"
            "print(f(a));")),
        "类型不匹配：期望 array<array<int>>");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let a: array<array<int>> = [[1]];\n"
            "let b: array<array<float>> = a;")),
        "需要 array<array<float>>");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "let r: array<int> = [1];\n"
            "let b: array<array<int>> = [[r]];")),
        "不能直接取值");
}

// ---- S3d：struct 的固定数组字段 v1 ----

static void test_struct_array_field_s3d() {
    // 布局：array<int,3> 字段占 3 个 i64 槽，x 占 1 槽；总槽数 = 4。
    {
        auto src =
            "struct S { a: array<int, 3>; x: int; }\n"
            "let s: S = S { a: [1, 2, 3], x: 9 };\n"
            "s.a[1] = 7;\n"
            "print(s.a[1], s.x);";
        auto ir = module_ir(src);
        CHECK(ir.find("alloca [3 x i64]") != std::string::npos);
        CHECK(count_scalar_allocas(src, "main", "i64") == 1);  // 仅 x 一个标量槽
        CHECK(ir.find("store i64 7") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 字面量 / 整体深拷贝 / 参数 / 返回值（按总槽数指针 + sret ABI）。
    {
        auto src =
            "struct S { a: array<int, 3>; x: int; }\n"
            "let s: S = S { a: [1, 2, 3], x: 9 };\n"
            "let t: S = s;\n"
            "t.a[0] = 5;\n"
            "fn f(v: S) -> S { v.a[2] = 8; return v; }\n"
            "let u: S = f(s);\n"
            "print(s.a[1], t.a[0], s.x);\n"
            "print(u.a[2], s.a[2]);\n"
            "print(s);\n"
            "print(u);";
        auto ir = module_ir(src);
        CHECK(ir.find("define void @f(ptr %sret, ptr %p0)") != std::string::npos);
        CHECK(ir.find("alloca [4 x i64]") != std::string::npos);
        CHECK(ir.find("store i64 5") != std::string::npos);  // t.a[0] = 5 深拷贝后写
        CHECK(ir.find("a: ") != std::string::npos);          // print 展开数组字段
        CHECK(module_verifies(src));
    }

    // array<struct> 字段：s.a[i].x 读写与 print 展开 `[P { x: .. }]`。
    {
        auto src =
            "struct P { x: int; }\n"
            "struct S { a: array<P, 2>; }\n"
            "let s: S = S { a: [P { x: 1 }, P { x: 2 }] };\n"
            "s.a[0].x = 9;\n"
            "print(s.a[0].x, s.a[1].x);\n"
            "print(s);";
        auto ir = module_ir(src);
        CHECK(ir.find("alloca [2 x i64]") != std::string::npos);
        CHECK(ir.find("P { ") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 固定嵌套数组字段：array<array<int,2>,3> 占 6 槽，s.m[i][j] 读写。
    {
        auto src =
            "struct N { m: array<array<int, 2>, 3>; }\n"
            "let n: N = N { m: [[1, 2], [3, 4], [5, 6]] };\n"
            "n.m[1][0] = 8;\n"
            "print(n.m[0][1], n.m[1][0], n.m[2][1]);\n"
            "print(n);";
        auto ir = module_ir(src);
        CHECK(ir.find("alloca [6 x i64]") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // array<float,N> / array<bool,N> 字段：float bitcast、bool zext/trunc。
    {
        auto src =
            "struct B { f: array<float, 2>; b: array<bool, 2>; }\n"
            "let x: B = B { f: [1.5, 2.5], b: [true, false] };\n"
            "x.f[0] = 3.5;\n"
            "x.b[1] = true;\n"
            "print(x.f[0], x.b[1]);\n"
            "print(x);";
        auto ir = module_ir(src);
        CHECK(ir.find("bitcast i64") != std::string::npos);
        CHECK(ir.find("trunc i64") != std::string::npos);
        // 数组字段元素按扁平 i64 槽读写，不能直接 store double / i1。
        CHECK(ir.find("store double") == std::string::npos);
        CHECK(ir.find("store i1") == std::string::npos);
        CHECK(module_verifies(src));
    }

    // 嵌套 struct 字段里的数组：o.i.a[1] 读写。
    {
        auto src =
            "struct I { a: array<int, 2>; b: float; }\n"
            "struct O { i: I; x: int; }\n"
            "let o: O = O { i: I { a: [1, 2], b: 2.5 }, x: 7 };\n"
            "o.i.a[1] = 9;\n"
            "print(o.i.a[0], o.i.a[1], o.x);\n"
            "print(o);";
        auto ir = module_ir(src);
        CHECK(ir.find("alloca [2 x i64]") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 固定 array<struct> 元素本身带数组字段：arr[0].a[0] 读写与 print。
    {
        auto src =
            "struct P { a: array<int, 2>; x: int; }\n"
            "let arr: array<P, 2> = [P { a: [1, 2], x: 3 }, P { a: [4, 5], x: 6 }];\n"
            "arr[0].a[0] = 9;\n"
            "arr[1].x = 8;\n"
            "print(arr[0].a[0], arr[0].a[1], arr[1].x);\n"
            "print(arr);";
        auto ir = module_ir(src);
        // P 的槽数 = array<int,2> 字段 2 槽 + x 1 槽 = 3；array<P,2> = 6 槽。
        CHECK(ir.find("alloca [6 x i64]") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // struct 的数组字段整体赋值 / 从另一个 struct 数组字段拷贝。
    {
        auto src =
            "struct S { a: array<int, 3>; x: int; }\n"
            "let s: S = S { a: [1, 2, 3], x: 9 };\n"
            "s.a = [4, 5, 6];\n"
            "s.a = s.a;\n"
            "let t: S = S { a: s.a, x: s.x };\n"
            "print(s.a[0], t.a[0]);";
        auto ir = module_ir(src);
        CHECK(ir.find("store i64 6") != std::string::npos);
        CHECK(module_verifies(src));
    }

    // 运行时下标进入 struct 数组字段：生成 tenet_bounds_fail 检查。
    {
        auto src =
            "struct S { a: array<int, 2>; }\n"
            "let s: S = S { a: [1, 2] };\n"
            "let i: int = 1;\n"
            "print(s.a[i]);";
        CHECK(function_calls(src, "main", "tenet_bounds_fail"));
        CHECK(module_verifies(src));
    }

    // 错误：动态数组字段 / 嵌套动态内层 / string 元素 / 数组字段循环嵌套。
    CHECK_THROWS(Codegen::compile(Parser::parse("struct S { a: array<int>; }")),
                 "不支持动态数组");
    CHECK_THROWS(
        Codegen::compile(Parser::parse("struct S { a: array<array<int>, 2>; }")),
        "不支持动态数组");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct S { a: array<string, 2>; }")),
                 "不支持 string");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct A { a: array<A, 2>; }")),
                 "循环嵌套");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct S { a: array<array<A, 2>, 2>; }")),
                 "数组元素类型 `A` 未定义");

    // 错误：字面量长度 / 元素类型 / 嵌套元素不是数组 / 缺字段。
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct S { a: array<int, 3>; x: int; }\n"
            "let s: S = S { a: [1, 2], x: 9 };")),
        "数组长度不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct S { a: array<int, 3>; x: int; }\n"
            "let s: S = S { a: [1, 2.0, 3], x: 9 };")),
        "数组元素 1 类型不匹配");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct N { m: array<array<int, 2>, 2>; }\n"
            "let n: N = N { m: [[1, 2], 3] };")),
        "嵌套数组元素必须是");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct S { a: array<int, 3>; x: int; }\n"
            "let s: S = S { x: 9 };")),
        "缺少字段 `a`");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct S { a: array<int, 3>; x: int; }\n"
            "let s: S = S { a: 1, x: 9 };")),
        "初始化必须是同类型数组字面量");

    // 错误：直接读取整个数组字段 / 整体读取 array<struct> 元素。
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct S { a: array<int, 2>; }\n"
            "let s: S = S { a: [1, 2] };\n"
            "print(s.a);")),
        "不能直接取值");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\n"
            "struct S { a: array<P, 2>; }\n"
            "let s: S = S { a: [P { x: 1 }, P { x: 2 }] };\n"
            "let p = s.a[0];")),
        "不支持整体读取 array<struct>");
}

int main() {
    test_lexer();
    test_parser();
    test_codegen();
    test_struct();
    test_struct_s3a();
    test_array();
    test_array_s3b();
    test_dynamic_array_s3c1();
    test_dynamic_array_s3c2();
    test_dynamic_array_s3c3a();
    test_array_struct_s3c3b1();
    test_dynamic_struct_array_s3c3b2();
    test_nested_array_s3c3c1();
    test_fixed_array_abi_s3c3b3();
    test_fixed_array_assign_s3c3b4();
    test_print_aggregate();
    test_dynamic_nested_array_s3c3d();
    test_struct_array_field_s3d();

    std::cout << "通过 " << (checks - failures) << " / " << checks << " 项检查";
    if (failures > 0) {
        std::cout << "，失败 " << failures << " 项\n";
        return 1;
    }
    std::cout << "\n";
    return 0;
}
