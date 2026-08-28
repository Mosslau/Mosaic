// 代码生成器（Codegen）：把 Tenet AST 编译成 Go 源码。
// 与 tenet-rs/src/codegen.rs、tenet-py/tenet/codegen.py 完全对应——
// 生成结果**逐字节一致**。
#pragma once

#include <cstdio>
#include <optional>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#include "ast.hpp"
#include "error.hpp"
#include "value.hpp"

namespace tenet {

// ---- 映射辅助 ----

inline std::string go_type(const std::string& t) {
    if (t == T_INT) return "int64";
    if (t == T_FLOAT) return "float64";
    if (t == T_BOOL) return "bool";
    if (t == T_STR) return "string";
    throw TenetError("未知的类型 `" + t + "`");
}

/// 把 Tenet 字符串转成 Go 字符串字面量。
inline std::string go_string(const std::string& s) {
    std::string out = "\"";
    for (char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\t': out += "\\t"; break;
            case '\r': out += "\\r"; break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\x%02x", static_cast<unsigned char>(c));
                    out += buf;
                } else {
                    out += c;
                }
        }
    }
    out += "\"";
    return out;
}

/// 扫描整个程序是否调用 `print`（决定是否生成 `import "fmt"`）。
inline bool program_uses_print(const Program& program) {
    auto expr_uses_print = [](const ExprPtr& e, auto&& self) -> bool {
        switch (e->kind) {
            case Expr::Kind::Call:
                if (e->name == "print") return true;
                for (const auto& a : e->args) {
                    if (self(a, self)) return true;
                }
                return false;
            case Expr::Kind::Assign: return self(e->value, self);
            case Expr::Kind::Unary: return self(e->value, self);
            case Expr::Kind::Binary:
                return self(e->lhs, self) || self(e->rhs, self);
            default: return false;
        }
    };
    auto stmt_uses_print = [&](const StmtPtr& s, auto&& self) -> bool {
        switch (s->kind) {
            case Stmt::Kind::Expr: return expr_uses_print(s->expr, expr_uses_print);
            case Stmt::Kind::Let: return expr_uses_print(s->value, expr_uses_print);
            case Stmt::Kind::Return:
                return s->expr && expr_uses_print(s->expr, expr_uses_print);
            case Stmt::Kind::If:
                if (expr_uses_print(s->cond, expr_uses_print)) return true;
                for (const auto& x : s->then_branch) {
                    if (self(x, self)) return true;
                }
                for (const auto& x : s->else_branch) {
                    if (self(x, self)) return true;
                }
                return false;
            case Stmt::Kind::While:
                if (expr_uses_print(s->cond, expr_uses_print)) return true;
                for (const auto& x : s->body) {
                    if (self(x, self)) return true;
                }
                return false;
            case Stmt::Kind::FnDecl:
                for (const auto& x : s->body) {
                    if (self(x, self)) return true;
                }
                return false;
            case Stmt::Kind::Block:
                for (const auto& x : s->stmts) {
                    if (self(x, self)) return true;
                }
                return false;
            default: return false;
        }
    };
    for (const auto& stmt : program.stmts) {
        if (stmt_uses_print(stmt, stmt_uses_print)) return true;
    }
    return false;
}

class GoCodegen {
public:
    /// 顶层入口：整个程序 → Go 源码字符串。
    static std::string generate(const Program& program) {
        GoCodegen gen;
        gen.collect_signatures(program);
        gen.emit_program(program);
        return gen.out_.str();
    }

private:
    std::ostringstream out_;
    int indent_ = 0;
    // 当前作用域内可见的变量类型
    std::unordered_map<std::string, std::string> symbols_;
    // 全局函数签名表：name -> 返回类型（或 nullopt）
    std::unordered_map<std::string, std::optional<std::string>> functions_;

    // ---- 输出辅助（与 Rust push 行为一致）----

    void push(const std::string& line) {
        if (line.empty()) {
            out_ << "\n";
            return;
        }
        for (int i = 0; i < indent_; ++i) out_ << "\t";
        out_ << line << "\n";
    }

    // ---- 预处理 ----

    void collect_signatures(const Program& program) {
        for (const auto& stmt : program.stmts) {
            if (stmt->kind == Stmt::Kind::FnDecl) {
                if (functions_.count(stmt->name) > 0) {
                    throw TenetError("函数 `" + stmt->name + "` 重复定义");
                }
                functions_[stmt->name] = stmt->ret;
            }
        }
    }

    // ---- 顶层 ----

    void emit_program(const Program& program) {
        push("package main");
        push("");

        if (program_uses_print(program)) {
            push("import \"fmt\"");
            push("");
        }

        // 函数声明 → 包级 func
        for (const auto& stmt : program.stmts) {
            if (stmt->kind == Stmt::Kind::FnDecl) {
                emit_stmt(stmt);
                push("");
            }
        }

        // 其余顶层语句 → main
        push("func main() {");
        ++indent_;
        for (const auto& stmt : program.stmts) {
            if (stmt->kind != Stmt::Kind::FnDecl) {
                emit_stmt(stmt);
            }
        }
        --indent_;
        push("}");
    }

    // ---- 语句 ----

    void emit_stmt(const StmtPtr& stmt) {
        switch (stmt->kind) {
            case Stmt::Kind::Let: {
                std::string t;
                if (stmt->ty.has_value()) {
                    t = *stmt->ty;
                } else {
                    auto inf = infer_type(stmt->value);
                    if (!inf.has_value()) {
                        throw TenetError("无法推断 `" + stmt->name + "` 的类型，请显式标注");
                    }
                    t = *inf;
                }
                symbols_[stmt->name] = t;
                std::string v = emit_expr(stmt->value);
                push("var " + stmt->name + " " + go_type(t) + " = " + v + ";");
                return;
            }
            case Stmt::Kind::Expr: {
                const ExprPtr& e = stmt->expr;
                if (e->kind == Expr::Kind::Call) {
                    std::string args = emit_args(e->args);
                    if (e->name == "print") {
                        push("fmt.Println(" + args + ");");
                    } else {
                        push(e->name + "(" + args + ");");
                    }
                    return;
                }
                if (e->kind == Expr::Kind::Assign) {
                    std::string v = emit_expr(e->value);
                    push(e->name + " = " + v + ";");
                    return;
                }
                throw TenetError("语句必须是函数调用或赋值");
            }
            case Stmt::Kind::If:
                emit_if(stmt->cond, stmt->then_branch, stmt->else_branch, "");
                return;
            case Stmt::Kind::While: {
                std::string c = emit_expr(stmt->cond);
                push("for " + c + " {");
                ++indent_;
                for (const auto& s : stmt->body) emit_stmt(s);
                --indent_;
                push("}");
                return;
            }
            case Stmt::Kind::Return: {
                if (stmt->expr) {
                    push("return " + emit_expr(stmt->expr) + ";");
                } else {
                    push("return;");
                }
                return;
            }
            case Stmt::Kind::Break:
                push("break;");
                return;
            case Stmt::Kind::Block: {
                push("{");
                ++indent_;
                for (const auto& s : stmt->stmts) emit_stmt(s);
                --indent_;
                push("}");
                return;
            }
            case Stmt::Kind::FnDecl: {
                std::string sig_params;
                for (size_t i = 0; i < stmt->params.size(); ++i) {
                    if (i > 0) sig_params += ", ";
                    sig_params += stmt->params[i].first + " " + go_type(stmt->params[i].second);
                }
                std::string sig;
                if (stmt->ret.has_value()) {
                    sig = stmt->name + "(" + sig_params + ") " + go_type(*stmt->ret);
                } else {
                    sig = stmt->name + "(" + sig_params + ")";
                }
                push("func " + sig + " {");
                ++indent_;
                // 参数进入符号表（函数体结束后恢复）
                auto saved = symbols_;
                for (const auto& [n, t] : stmt->params) symbols_[n] = t;
                for (const auto& s : stmt->body) emit_stmt(s);
                --indent_;
                push("}");
                symbols_ = std::move(saved);
                return;
            }
        }
        throw TenetError("未知的语句类型");
    }

    void emit_if(const ExprPtr& cond, const std::vector<StmtPtr>& then_branch,
                 const std::vector<StmtPtr>& else_branch, const std::string& prefix) {
        std::string c = emit_expr(cond);
        push(prefix + "if " + c + " {");
        ++indent_;
        for (const auto& s : then_branch) emit_stmt(s);
        --indent_;
        if (!else_branch.empty()) {
            // else if 链：单条 if 语句的 else 分支 → Go 的 `} else if ...`
            if (else_branch.size() == 1 && else_branch[0]->kind == Stmt::Kind::If) {
                const auto& nested = else_branch[0];
                emit_if(nested->cond, nested->then_branch, nested->else_branch, "} else ");
            } else {
                push("} else {");
                ++indent_;
                for (const auto& s : else_branch) emit_stmt(s);
                --indent_;
                push("}");
            }
        } else {
            push("}");
        }
    }

    // ---- 表达式 ----

    std::string emit_expr(const ExprPtr& e) {
        switch (e->kind) {
            case Expr::Kind::Int: return std::to_string(e->int_val);
            case Expr::Kind::Float: {
                // 必须保留小数点，否则 Go 里 7 / 2.0 会变成整数除法 7 / 2
                std::string s = fmt_float(e->float_val);
                if (s.find('.') == std::string::npos) s += ".0";
                return s;
            }
            case Expr::Kind::Str: return go_string(e->str_val);
            case Expr::Kind::Bool: return e->bool_val ? "true" : "false";
            case Expr::Kind::Var: return e->name;
            case Expr::Kind::Assign:
                return e->name + " = " + emit_expr(e->value);
            case Expr::Kind::Unary:
                return (e->op == OP_NEG ? "-" : "!") + emit_expr(e->value);
            case Expr::Kind::Binary:
                return "(" + emit_expr(e->lhs) + " " + e->op + " " + emit_expr(e->rhs) + ")";
            case Expr::Kind::Call: {
                std::string args = emit_args(e->args);
                if (e->name == "print") return "fmt.Println(" + args + ")";
                return e->name + "(" + args + ")";
            }
        }
        throw TenetError("未知的表达式类型");
    }

    std::string emit_args(const std::vector<ExprPtr>& args) {
        std::string out;
        for (size_t i = 0; i < args.size(); ++i) {
            if (i > 0) out += ", ";
            out += emit_expr(args[i]);
        }
        return out;
    }

    // ---- 类型推断（与解释器语义对齐）----

    std::optional<std::string> infer_type(const ExprPtr& e) {
        switch (e->kind) {
            case Expr::Kind::Int: return T_INT;
            case Expr::Kind::Float: return T_FLOAT;
            case Expr::Kind::Str: return T_STR;
            case Expr::Kind::Bool: return T_BOOL;
            case Expr::Kind::Var: {
                auto it = symbols_.find(e->name);
                return it == symbols_.end() ? std::nullopt
                                            : std::optional<std::string>(it->second);
            }
            case Expr::Kind::Assign: {
                auto it = symbols_.find(e->name);
                return it == symbols_.end() ? std::nullopt
                                            : std::optional<std::string>(it->second);
            }
            case Expr::Kind::Unary: {
                if (e->op == OP_NOT) return T_BOOL;
                auto t = infer_type(e->value);
                if (t == T_INT || t == T_FLOAT) return t;
                return std::nullopt;
            }
            case Expr::Kind::Binary: {
                auto lt = infer_type(e->lhs);
                auto rt = infer_type(e->rhs);
                const std::string& op = e->op;
                if (op == OP_AND || op == OP_OR) return T_BOOL;
                if (op == OP_EQ || op == OP_NEQ || op == OP_LT || op == OP_LTE || op == OP_GT
                    || op == OP_GTE) {
                    return T_BOOL;
                }
                if (op == OP_MOD) {
                    return (lt == T_INT && rt == T_INT)
                               ? std::optional<std::string>(T_INT)
                               : std::nullopt;
                }
                if (op == OP_ADD) {
                    if (lt == T_STR && rt == T_STR) return T_STR;
                    if (lt == T_FLOAT || rt == T_FLOAT) return T_FLOAT;
                    if (lt == T_INT && rt == T_INT) return T_INT;
                    return std::nullopt;
                }
                // Sub / Mul / Div
                if (lt == T_FLOAT || rt == T_FLOAT) return T_FLOAT;
                if (lt == T_INT && rt == T_INT) return T_INT;
                return std::nullopt;
            }
            case Expr::Kind::Call: {
                auto it = functions_.find(e->name);
                return it == functions_.end() ? std::nullopt : it->second;
            }
        }
        return std::nullopt;
    }
};

}  // namespace tenet
