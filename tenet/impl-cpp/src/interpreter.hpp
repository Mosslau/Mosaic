// 树遍历解释器（Tree-walking Interpreter）。
// 与 tenet-rs/src/interpreter.rs、tenet-py/tenet/interpreter.py 语义一致。
//
// - 表达式递归求值返回值；语句递归执行产生副作用
// - 控制流（return / break）通过 Flow 信号向上传播
// - 短路求值：&& / || 右侧只在需要时求值
// - 函数以名字存放在全局函数表；调用时新建参数作用域（父=全局）
// - 作用域只在块、if / while 分支、函数调用处创建；顶层不建
#pragma once

#include <cstdint>
#include <iostream>
#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "ast.hpp"
#include "env.hpp"
#include "error.hpp"
#include "value.hpp"

namespace tenet {

/// 控制流信号：Normal / Break / Return(value)。
struct Flow {
    enum Kind { Normal, Break, Return } kind;
    Value value;  // Return 时携带返回值

    static Flow normal() { return {Normal, v_nil()}; }
    static Flow brk() { return {Break, v_nil()}; }
    static Flow ret(Value v) { return {Return, std::move(v)}; }
};

/// 用户自定义函数。
struct Function {
    std::string name;
    std::vector<std::pair<std::string, std::string>> params;
    std::optional<std::string> ret;
    std::vector<StmtPtr> body;
};

class Interpreter {
public:
    Interpreter() : global_env_(Env::global()) {}

    /// 顶层入口：执行整个程序。
    static void run(const Program& program) { Interpreter().run_program(program); }

    /// 在当前实例上执行程序（REPL 复用同一实例，保留函数表）。
    void run_program(const Program& program) { exec_block(program.stmts, global_env_); }

    /// 在全局环境中求值单个表达式（REPL 回显用）。
    Value eval_expr(const ExprPtr& expr) { return eval(expr, global_env_); }

private:
    std::unordered_map<std::string, Function> functions_;
    EnvPtr global_env_;

    // ---- 语句执行 ----

    Flow exec_block(const std::vector<StmtPtr>& stmts, const EnvPtr& env) {
        for (const auto& stmt : stmts) {
            Flow flow = exec_stmt(stmt, env);
            if (flow.kind != Flow::Normal) return flow;
        }
        return Flow::normal();
    }

    Flow exec_stmt(const StmtPtr& stmt, const EnvPtr& env) {
        switch (stmt->kind) {
            case Stmt::Kind::Let: {
                Value v = eval(stmt->value, env);
                env->define(stmt->name, std::move(v));
                return Flow::normal();
            }
            case Stmt::Kind::Expr: {
                eval(stmt->expr, env);
                return Flow::normal();
            }
            case Stmt::Kind::If: {
                bool cond = expect_bool(eval(stmt->cond, env));
                const std::vector<StmtPtr>& branch =
                    cond ? stmt->then_branch : stmt->else_branch;
                // if 分支自身就是一个块：新建作用域
                EnvPtr branch_env = Env::child(env);
                return exec_block(branch, branch_env);
            }
            case Stmt::Kind::While: {
                Flow flow = Flow::normal();
                while (true) {
                    if (!expect_bool(eval(stmt->cond, env))) break;
                    EnvPtr body_env = Env::child(env);
                    flow = exec_block(stmt->body, body_env);
                    if (flow.kind == Flow::Break) return Flow::normal();
                    if (flow.kind == Flow::Return) return flow;
                }
                return flow;
            }
            case Stmt::Kind::Return: {
                Value v = stmt->expr ? eval(stmt->expr, env) : v_nil();
                return Flow::ret(std::move(v));
            }
            case Stmt::Kind::Break:
                return Flow::brk();
            case Stmt::Kind::Block: {
                EnvPtr child = Env::child(env);
                return exec_block(stmt->stmts, child);
            }
            case Stmt::Kind::FnDecl: {
                Function f;
                f.name = stmt->name;
                f.params = stmt->params;
                f.ret = stmt->ret;
                f.body = stmt->body;  // shared_ptr 拷贝，共享同一棵树
                functions_[stmt->name] = std::move(f);
                return Flow::normal();
            }
        }
        throw TenetError("未知的语句类型");
    }

    // ---- 表达式求值 ----

    Value eval(const ExprPtr& expr, const EnvPtr& env) {
        switch (expr->kind) {
            case Expr::Kind::Int: return v_int(expr->int_val);
            case Expr::Kind::Float: return v_float(expr->float_val);
            case Expr::Kind::Str: return v_str(expr->str_val);
            case Expr::Kind::Bool: return v_bool(expr->bool_val);
            case Expr::Kind::Var: return env->get(expr->name);
            case Expr::Kind::Assign: {
                Value v = eval(expr->value, env);
                env->assign(expr->name, v);
                return v;
            }
            case Expr::Kind::Unary: {
                Value v = eval(expr->value, env);
                return apply_unary(v, expr->op);
            }
            case Expr::Kind::Binary: {
                // && / || 短路求值：右侧只在需要时求值
                if (expr->op == OP_AND || expr->op == OP_OR) {
                    bool l = expect_bool(eval(expr->lhs, env));
                    if (expr->op == OP_AND && !l) return v_bool(false);
                    if (expr->op == OP_OR && l) return v_bool(true);
                    bool r = expect_bool(eval(expr->rhs, env));
                    return v_bool(r);
                }
                Value l = eval(expr->lhs, env);
                Value r = eval(expr->rhs, env);
                return apply_binary(l, expr->op, r);
            }
            case Expr::Kind::Call:
                return call(expr->name, expr->args, env);
        }
        throw TenetError("未知的表达式类型");
    }

    // ---- 函数调用 ----

    Value call(const std::string& callee, const std::vector<ExprPtr>& args, const EnvPtr& env) {
        // 内建函数
        if (callee == "print") {
            std::vector<std::string> parts;
            for (const auto& a : args) {
                parts.push_back(display(eval(a, env)));
            }
            std::string line;
            for (size_t i = 0; i < parts.size(); ++i) {
                if (i > 0) line += " ";
                line += parts[i];
            }
            std::cout << line << "\n";
            return v_nil();
        }

        // 用户函数
        auto it = functions_.find(callee);
        if (it == functions_.end()) throw TenetError("未定义的函数 `" + callee + "`");
        const Function& f = it->second;
        if (f.params.size() != args.size()) {
            throw TenetError("函数 `" + callee + "` 需要 " + std::to_string(f.params.size())
                             + " 个参数，实际传入 " + std::to_string(args.size()) + " 个");
        }

        // 参数作用域：父为全局环境（函数之间共享全局变量，但不捕获调用方局部变量）
        EnvPtr call_env = Env::child(global_env_);
        for (size_t i = 0; i < f.params.size(); ++i) {
            const auto& [pname, pty] = f.params[i];
            Value v = eval(args[i], env);
            if (!matches(v, pty)) {
                throw TenetError("参数 `" + pname + "` 期望类型 " + pty + "，实际传入 "
                                 + type_name(v));
            }
            call_env->define(pname, std::move(v));
        }

        Flow flow = exec_block(f.body, call_env);
        if (flow.kind == Flow::Return) {
            Value v = flow.value;
            if (f.ret.has_value() && !matches(v, *f.ret) && !is_nil(v)) {
                throw TenetError("函数 `" + callee + "` 返回类型期望 " + *f.ret
                                 + "，实际返回 " + type_name(v));
            }
            return v;
        }
        if (flow.kind == Flow::Break) {
            throw TenetError("`break` 出现在函数 `" + callee + "` 的循环之外");
        }
        // Normal
        if (f.ret.has_value()) {
            throw TenetError("函数 `" + callee + "` 声明了返回类型，但没有返回值");
        }
        return v_nil();
    }
};

}  // namespace tenet
