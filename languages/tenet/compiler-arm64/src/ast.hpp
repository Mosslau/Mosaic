// 抽象语法树（与 compiler-rs/src/ast.rs 对应）：标签结构体。
// 每个节点携带起始位置 `[行:列]`，供代码生成阶段全链路报错。
#pragma once

#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "error.hpp"

namespace tenet {

inline const char* T_INT = "int";
inline const char* T_FLOAT = "float";
inline const char* T_BOOL = "bool";
inline const char* T_STR = "string";

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
inline const char* OP_NEG = "-";
inline const char* OP_NOT = "!";

struct Expr;
using ExprPtr = std::shared_ptr<Expr>;

struct Expr {
    enum class Kind { Int, Float, Str, Bool, Var, Assign, Unary, Binary, Call };
    Position pos;
    Kind kind;
    int64_t int_val = 0;
    double float_val = 0.0;
    bool bool_val = false;
    std::string str_val;
    std::string name;
    std::string op;
    ExprPtr value;
    ExprPtr lhs, rhs;
    std::vector<ExprPtr> args;
};

struct Stmt;
using StmtPtr = std::shared_ptr<Stmt>;

struct Stmt {
    enum class Kind { Let, Expr, If, While, Return, Break, FnDecl };
    Position pos;
    Kind kind;
    std::string name;
    std::optional<std::string> ty;
    std::optional<std::string> ret;
    ExprPtr expr;
    ExprPtr cond;
    ExprPtr value;
    std::vector<StmtPtr> then_branch;
    std::vector<StmtPtr> else_branch;
    std::vector<StmtPtr> body;
    std::vector<std::pair<std::string, std::string>> params;
};

struct Program {
    std::vector<StmtPtr> stmts;
};

}  // namespace tenet
