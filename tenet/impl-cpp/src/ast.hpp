// 抽象语法树（AST）：语法分析器的输出，解释器与代码生成器的共同输入。
// 与 tenet-rs/src/ast.rs 对应。
//
// 用「标签 + 可选载荷」的单一结构表达（C++ 惯用的 tagged struct），
// 等价于 Rust 的 enum：kind 决定哪个字段有意义。
// 子节点用 shared_ptr，便于递归与无拷贝共享。
#pragma once

#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace tenet {

// 类型常量
inline const char* T_INT = "int";
inline const char* T_FLOAT = "float";
inline const char* T_BOOL = "bool";
inline const char* T_STR = "string";

// 运算符常量
inline const char* OP_ADD = "+";
inline const char* OP_SUB = "-";
inline const char* OP_MUL = "*";
inline const char* OP_DIV = "/";
inline const char* OP_MOD = "%";
inline const char* OP_EQ = "==";
inline const char* OP_NEQ = "!=";
inline const char* OP_LT = "<";
inline const char* OP_LTE = "<=";
inline const char* OP_GT = ">";
inline const char* OP_GTE = ">=";
inline const char* OP_AND = "&&";
inline const char* OP_OR = "||";
inline const char* OP_NEG = "-";  // 一元取负
inline const char* OP_NOT = "!";  // 一元取反

// ---- 表达式 ----

struct Expr;
using ExprPtr = std::shared_ptr<Expr>;

struct Expr {
    enum class Kind {
        Int, Float, Str, Bool,      // 字面量
        Var,                        // 变量读取
        Assign,                     // 赋值
        Unary,                      // -x / !x
        Binary,                     // 二元运算
        Call,                       // f(1, 2)
    };

    Kind kind;
    // 字面量载荷
    int64_t int_val = 0;
    double float_val = 0.0;
    bool bool_val = false;
    std::string str_val;
    // Var / Assign / Call 的名字
    std::string name;
    // Unary / Binary 的运算符
    std::string op;
    // 子节点
    ExprPtr value;      // Assign / Unary
    ExprPtr lhs, rhs;   // Binary
    std::vector<ExprPtr> args;  // Call
};

// ---- 语句 ----

struct Stmt;
using StmtPtr = std::shared_ptr<Stmt>;

struct Stmt {
    enum class Kind {
        Let,       // let x: int = 42;
        Expr,      // 表达式语句
        If,        // if (c) { ... } else { ... }
        While,     // while (c) { ... }
        Return,    // return expr;
        Break,     // break;
        Block,     // { ... }
        FnDecl,    // fn f(a: int) -> int { ... }
    };

    Kind kind;
    // Let / FnDecl 的名字
    std::string name;
    // Let 的类型标注（可省略）
    std::optional<std::string> ty;
    // FnDecl 的返回类型（可省略）
    std::optional<std::string> ret;
    // Expr 语句 / If 条件 / Return 值 / Let 值
    ExprPtr expr;
    ExprPtr cond;
    ExprPtr value;
    // 块（语句序列）
    std::vector<StmtPtr> then_branch;    // If
    std::vector<StmtPtr> else_branch;    // If（可空）
    std::vector<StmtPtr> body;           // While / FnDecl
    std::vector<StmtPtr> stmts;          // Block
    // FnDecl 参数：[(参数名, 类型), ...]
    std::vector<std::pair<std::string, std::string>> params;
};

// ---- 程序 ----

struct Program {
    std::vector<StmtPtr> stmts;
};

}  // namespace tenet
