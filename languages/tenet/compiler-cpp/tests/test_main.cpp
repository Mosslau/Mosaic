// Tenet compiler-cpp 测试套件：镜像 compiler-rs 的测试，并补充 struct v1 / array v1 用例。
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

static unsigned count_array_allocas(const std::string& src, uint64_t len,
                                    const std::string& elem_ll) {
    auto c = Codegen::compile(Parser::parse(src));
    auto* f = c.mod->getFunction("main");
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

    // 错误：struct 参数 / 返回值 / 直接 print
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nfn f(p: Point) -> int { return p.x; }")),
        "v1 不支持 struct 参数");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nfn f() -> Point { return Point { x: 1 }; }")),
        "v1 不支持 struct 返回值");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Point { x: int; }\nlet p: Point = Point { x: 1 };\nprint(p);")),
        "struct 变量 `p` 不能直接取值");
    CHECK_THROWS(
        Codegen::compile(Parser::parse("let x: int = 1;\nx.y = 2;")),
        "`x` 不是 struct，不能写字段 `y`");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct P { x: int; }\nlet p = P { x: 1 };\n"
            "let b: int = (p = P { x: 2 }) + 1;")),
        "运算符 `+` 不能作用于 struct 值");

    // 错误：struct 声明本身（字段类型 / 空 struct / 重复字段 / 重复定义 / 嵌套 struct）
    CHECK_THROWS(Codegen::compile(Parser::parse("struct Bad { s: string; }")),
                 "只支持 int/float/bool");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct Empty { }")), "至少需要一个字段");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct P { x: int; x: int; }")), "字段 `x` 重复");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct P { x: int; }\nstruct P { y: int; }")),
                 "struct `P` 重复定义");
    CHECK_THROWS(
        Codegen::compile(Parser::parse(
            "struct Inner { x: int; }\nstruct Outer { i: Inner; }")),
        "只支持 int/float/bool");
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

// ---- array v1 ----

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

    // 语法：array<T> 类型、字面量、下标读、下标写
    {
        auto prog = Parser::parse(
            "let a: array<int> = [1, 2, 3];\n"
            "let n = len(a);\n"
            "a[0] = a[1];");
        CHECK(prog.stmts.size() == 3);
        CHECK(prog.stmts[0]->ty.has_value() && *prog.stmts[0]->ty == "array<int>");
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
            "let a: array<int> = [1, 2, 3];\n"
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
        CHECK(count_array_allocas("let f: array<float> = [1.5, 2.5];\nprint(f[0], f[1]);", 2,
                                  "double") == 1);
        CHECK(count_array_allocas("let b: array<bool> = [true, false];\nprint(b[0], b[1]);", 2,
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
            "let a: array<int> = [1, 2];\n"
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
    CHECK_THROWS(Codegen::compile(Parser::parse("let a: array<int> = [1, 2.0];")),
                 "数组元素 1 类型不匹配");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2.0];")),
                 "数组元素类型不一致");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [\"x\"];")),
                 "只支持 int/float/bool");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [true, 1];")),
                 "数组元素类型不一致");

    // 空数组 / 嵌套 array / array<struct> / struct 字段 array
    CHECK_THROWS(Codegen::compile(Parser::parse("let a: array<int> = [];")), "空数组");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [];")), "空数组");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a: array<array<int>> = [[1]];")),
                 "只支持 int/float/bool");
    CHECK_THROWS(
        Codegen::compile(Parser::parse("struct P { x: int; }\nlet a: array<P> = [1];")),
        "只支持 int/float/bool");
    CHECK_THROWS(Codegen::compile(Parser::parse("struct S { a: array<int>; }")),
                 "只支持 int/float/bool");

    // array 不能作参数 / 返回值；不能直接 print(a)
    CHECK_THROWS(
        Codegen::compile(Parser::parse("fn f(a: array<int>) -> int { return 0; }")),
        "v1 不支持 array 参数");
    CHECK_THROWS(Codegen::compile(Parser::parse("fn f() -> array<int> { return [1]; }")),
                 "v1 不支持 array 返回值");
    CHECK_THROWS(Codegen::compile(Parser::parse("let a = [1, 2];\nprint(a);")),
                 "数组变量 `a` 不能直接取值");
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

int main() {
    test_lexer();
    test_parser();
    test_codegen();
    test_struct();
    test_array();

    std::cout << "通过 " << (checks - failures) << " / " << checks << " 项检查";
    if (failures > 0) {
        std::cout << "，失败 " << failures << " 项\n";
        return 1;
    }
    std::cout << "\n";
    return 0;
}
