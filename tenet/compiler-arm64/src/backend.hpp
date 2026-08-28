// AArch64 汇编后端：AST → arm64 汇编文本（.s）。
//
// 完全不用 LLVM/clang 做代码生成——指令选择、寄存器使用、栈帧、调用约定
// 全部自己写（类似 TCC / 早期 GCC 的做法）：
//   .tenet → 本编译器 → .s → 系统 as 汇编 → ld 链接 → 原生二进制
//
// 设计：
// - 变量：栈帧槽位（x29 相对寻址），每槽 8 字节；槽位与类型在规划阶段分配
// - 表达式：栈式求值（push/pop 到 [sp]），临时寄存器 x9/x10/d9/d10
// - 调用：用户函数按 AAPCS（x0-x7 / d0-d7）；print 走 Apple 变参规则
//   （固定参数 fmt 在 x0，变参全部压栈，实测与 clang 一致）
// - 字符串：.data 常量 + adrp/add 取址；拼接/比较调用 libc（strlen/malloc/memcpy/strcmp）
// - 控制流：if/while/break/短路全部翻译为标签 + 条件分支
#pragma once

#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

#include "ast.hpp"
#include "error.hpp"

namespace tenet {

class Backend {
public:
    /// 完整编译：Program → AArch64 汇编文本（含内嵌运行时）。
    static std::string generate(const Program& program) {
        Backend b;
        b.collect_signatures(program);
        b.emit_program(program);
        std::string out = b.text_;
        out += "\n";
        out += RUNTIME_ASM;
        return out;
    }

    /// 内嵌运行时（arm64 汇编）：字符串拼接与比较，经 libc 实现。
    static constexpr const char* RUNTIME_ASM =
        "\t.text\n"
        "\t.p2align 2\n"
        "_tenet_strcmp:\n"
        "\tb _strcmp\n"
        "\t.p2align 2\n"
        "_tenet_concat:\n"
        "\tstp x29, x30, [sp, #-16]!\n"
        "\tmov x29, sp\n"
        "\tsub sp, sp, #48\n"
        "\tstp x19, x20, [sp]\n"
        "\tstp x21, x22, [sp, #16]\n"
        "\tstr x23, [sp, #32]\n"
        "\tmov x19, x0\n"
        "\tmov x20, x1\n"
        "\tbl _strlen\n"
        "\tmov x21, x0\n"
        "\tmov x0, x20\n"
        "\tbl _strlen\n"
        "\tmov x22, x0\n"
        "\tadd x0, x21, x22\n"
        "\tadd x0, x0, #1\n"
        "\tbl _malloc\n"
        "\tmov x23, x0\n"
        "\tmov x1, x19\n"
        "\tmov x2, x21\n"
        "\tbl _memcpy\n"
        "\tadd x0, x23, x21\n"
        "\tmov x1, x20\n"
        "\tadd x2, x22, #1\n"
        "\tbl _memcpy\n"
        "\tmov x0, x23\n"
        "\tldr x23, [sp, #32]\n"
        "\tldp x21, x22, [sp, #16]\n"
        "\tldp x19, x20, [sp]\n"
        "\tadd sp, sp, #48\n"
        "\tldp x29, x30, [sp], #16\n"
        "\tret\n";

private:
    struct FnSig {
        std::vector<std::string> params;
        std::optional<std::string> ret;
    };

    std::string text_;
    std::string data_;
    int str_c_ = 0, flt_c_ = 0, label_c_ = 0;
    std::unordered_map<std::string, FnSig> functions_;

    // 当前函数状态
    std::string fn_;
    std::vector<std::unordered_map<std::string, int>> flat_maps_;  // 所有块作用域的槽位表
    std::vector<int> scope_stack_;                                 // 当前作用域链（索引）
    std::vector<int> scope_queue_;                                 // 预计算的块索引（按遍历序）
    size_t scope_cursor_ = 0;                                      // 消费 scope_queue_
    std::unordered_map<std::string, std::string> types_;           // name → Tenet 类型
    int frame_ = 0;
    int pushes_ = 0;
    std::vector<std::string> break_stack_;

    // ---- 辅助 ----

    void emit(const std::string& line) {
        if (!line.empty()) text_ += "\t" + line + "\n";
    }

    void label(const std::string& name) { text_ += name + ":\n"; }

    std::string new_label(const std::string& base) {
        return "L." + base + "." + std::to_string(++label_c_);
    }

    bool is_float(const std::string& t) const { return t == T_FLOAT; }

    /// Apple Silicon 要求 sp 恒 16 字节对齐：push/pop 用 16 字节单位。
    /// 占位寄存器：x 类用 xzr，d 类用 d31（FP 零寄存器）。
    std::string zero_reg(const std::string& reg) const {
        return !reg.empty() && reg[0] == 'd' ? "d31" : "xzr";
    }

    void push_reg(const std::string& reg) {
        emit("stp " + reg + ", " + zero_reg(reg) + ", [sp, #-16]!");
        ++pushes_;
    }

    void pop_reg(const std::string& reg) {
        emit("ldp " + reg + ", " + zero_reg(reg) + ", [sp], #16");
        --pushes_;
    }

    void data_string(const std::string& s, const std::string& name) {
        data_ += ".section __TEXT,__cstring\n";
        data_ += name + ":\n";
        data_ += "\t.asciz \"" + as_escape(s) + "\"\n";
    }

    static std::string as_escape(const std::string& s) {
        std::string out;
        for (char c : s) {
            switch (c) {
                case '"': out += "\\\""; break;
                case '\\': out += "\\\\"; break;
                case '\n': out += "\\n"; break;
                case '\t': out += "\\t"; break;
                case '\r': out += "\\r"; break;
                default: out += c;
            }
        }
        return out;
    }

    /// 取字符串常量地址到 x9。
    void load_string(const std::string& s) {
        std::string name = "L.str." + std::to_string(str_c_++);
        data_string(s, name);
        emit("adrp x9, " + name + "@PAGE");
        emit("add x9, x9, " + name + "@PAGEOFF");
    }

    // ---- 预处理 ----

    void collect_signatures(const Program& program) {
        for (const auto& stmt : program.stmts) {
            if (stmt->kind != Stmt::Kind::FnDecl) continue;
            const auto& name = stmt->name;
            if (name == "main" || name == "printf" || name == "tenet_concat" || name == "tenet_strcmp") {
                throw TenetError("函数名 `" + name + "` 为编译器保留");
            }
            if (functions_.count(name)) throw TenetError("函数 `" + name + "` 重复定义");
            std::vector<std::string> params;
            for (const auto& [pn, pt] : stmt->params) {
                (void)pn;
                params.push_back(pt);
            }
            functions_[name] = {params, stmt->ret};
        }
    }

    // ---- 程序 ----

    void emit_program(const Program& program) {
        for (const auto& stmt : program.stmts) {
            if (stmt->kind == Stmt::Kind::FnDecl) emit_fn(stmt);
        }
        emit_main(program);
        if (!data_.empty()) {
            text_ += "\n";
            text_ += data_;
        }
    }

    // ---- 函数帧规划 ----

    /// 遍历语句分配变量槽位（let 按出现顺序；遮蔽用不同槽）。
    /// 每个块（fn/if-then/if-else/while）在 flat_maps_ 里占一个表，
    /// 索引按遍历序压入 scope_queue_，发射时按同序消费——槽位不丢失。
    void plan_stmts(const std::vector<StmtPtr>& stmts, int& next_slot) {
        for (const auto& s : stmts) {
            switch (s->kind) {
                case Stmt::Kind::Let: {
                    flat_maps_[scope_stack_.back()][s->name] = -(8 * (next_slot + 1));
                    ++next_slot;
                    if (s->ty.has_value()) types_[s->name] = *s->ty;
                    break;
                }
                case Stmt::Kind::If: {
                    flat_maps_.push_back({});
                    scope_queue_.push_back((int)flat_maps_.size() - 1);
                    scope_stack_.push_back((int)flat_maps_.size() - 1);
                    plan_stmts(s->then_branch, next_slot);
                    scope_stack_.pop_back();
                    if (!s->else_branch.empty()) {
                        flat_maps_.push_back({});
                        scope_queue_.push_back((int)flat_maps_.size() - 1);
                        scope_stack_.push_back((int)flat_maps_.size() - 1);
                        plan_stmts(s->else_branch, next_slot);
                        scope_stack_.pop_back();
                    }
                    break;
                }
                case Stmt::Kind::While: {
                    flat_maps_.push_back({});
                    scope_queue_.push_back((int)flat_maps_.size() - 1);
                    scope_stack_.push_back((int)flat_maps_.size() - 1);
                    plan_stmts(s->body, next_slot);
                    scope_stack_.pop_back();
                    break;
                }
                default:
                    break;
            }
        }
    }

    // ---- 函数发射 ----

    void emit_fn(const StmtPtr& stmt) {
        const auto& name = stmt->name;
        if (stmt->ret.has_value() && !stmt->body.empty() &&
            stmt->body.back()->kind != Stmt::Kind::Return) {
            throw TenetError("函数 `" + name + "` 声明了返回类型，但函数末尾没有 return");
        }
        // 规划：参数槽 + 局部槽（作用域索引按遍历序进队列）
        flat_maps_.clear();
        scope_queue_.clear();
        scope_cursor_ = 0;
        scope_stack_.clear();
        flat_maps_.push_back({});
        scope_queue_.push_back(0);
        scope_stack_.push_back(0);
        int next_slot = (int)stmt->params.size();
        for (int i = 0; i < (int)stmt->params.size(); ++i) {
            flat_maps_[0][stmt->params[i].first] = -(8 * (i + 1));
            types_[stmt->params[i].first] = stmt->params[i].second;
        }
        plan_stmts(stmt->body, next_slot);
        scope_stack_.pop_back();
        frame_ = ((next_slot * 8) + 15) / 16 * 16;

        fn_ = name;
        scope_stack_.clear();
        scope_stack_.push_back(0);
        scope_cursor_ = 1;  // 0 号块（fn body）已进入
        pushes_ = 0;
        break_stack_.clear();

        text_ += "\n.p2align 2\n";
        text_ += "\t.globl _" + name + "\n";
        label("_" + name);
        emit("stp x29, x30, [sp, #-16]!");
        emit("mov x29, sp");
        if (frame_ > 0) emit("sub sp, sp, #" + std::to_string(frame_));
        // 参数入槽
        for (size_t i = 0; i < stmt->params.size(); ++i) {
            const auto& [pn, pt] = stmt->params[i];
            int off = flat_maps_[0][pn];
            emit("str " + std::string(is_float(pt) ? "d" : "x") + std::to_string(i) +
                 ", [x29, #" + std::to_string(off) + "]");
        }
        for (const auto& s : stmt->body) emit_stmt(s);
        // 函数 epilogue（return 跳转到此；void 函数自然落回）
        label("L." + name + ".ret");
        emit("add sp, sp, #" + std::to_string(frame_));
        emit("ldp x29, x30, [sp], #16");
        emit("ret");
        fn_.clear();
    }

    void emit_main(const Program& program) {
        fn_ = "main";
        int next_slot = 0;
        std::vector<StmtPtr> body;
        for (const auto& s : program.stmts) {
            if (s->kind == Stmt::Kind::FnDecl) continue;
            if (s->kind == Stmt::Kind::Return) {
                throw TenetError("顶层不能使用 `return`（main 自动返回 0）");
            }
            body.push_back(s);
        }
        flat_maps_.clear();
        scope_queue_.clear();
        scope_cursor_ = 0;
        scope_stack_.clear();
        flat_maps_.push_back({});
        scope_queue_.push_back(0);
        scope_stack_.push_back(0);
        plan_stmts(body, next_slot);
        scope_stack_.pop_back();
        frame_ = ((next_slot * 8) + 15) / 16 * 16;
        scope_stack_.clear();
        scope_stack_.push_back(0);
        scope_cursor_ = 1;
        pushes_ = 0;
        break_stack_.clear();

        text_ += "\n.p2align 2\n";
        text_ += "\t.globl _main\n";
        label("_main");
        emit("stp x29, x30, [sp, #-16]!");
        emit("mov x29, sp");
        if (frame_ > 0) emit("sub sp, sp, #" + std::to_string(frame_));
        for (const auto& s : body) emit_stmt(s);
        label("L.main.ret");
        emit("mov x0, #0");
        emit("add sp, sp, #" + std::to_string(frame_));
        emit("ldp x29, x30, [sp], #16");
        emit("ret");
        fn_.clear();
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
                    if (!inf.has_value())
                        throw TenetError("无法推断 `" + stmt->name + "` 的类型，请显式标注");
                    t = *inf;
                }
                types_[stmt->name] = t;
                gen_expr(stmt->value);
                int off = lookup_slot(stmt->name);
                pop_reg(is_float(t) ? "d9" : "x9");
                emit("str " + std::string(is_float(t) ? "d9" : "x9") + ", [x29, #" +
                     std::to_string(off) + "]");
                return;
            }
            case Stmt::Kind::Expr: {
                std::string t = gen_expr(stmt->expr);
                if (t != "void") pop_reg("x9");  // 丢弃结果
                return;
            }
            case Stmt::Kind::If: {
                gen_expr(stmt->cond);
                pop_reg("x9");
                emit("cmp x9, #0");
                auto else_l = new_label("else");
                auto merge_l = new_label("merge");
                emit("b.eq " + else_l);
                enter_scope();
                for (const auto& s : stmt->then_branch) emit_stmt(s);
                exit_scope();
                emit("b " + merge_l);
                label(else_l);
                if (!stmt->else_branch.empty()) {
                    enter_scope();
                    for (const auto& s : stmt->else_branch) emit_stmt(s);
                    exit_scope();
                }
                label(merge_l);
                return;
            }
            case Stmt::Kind::While: {
                auto cond_l = new_label("cond");
                auto exit_l = new_label("exit");
                label(cond_l);
                gen_expr(stmt->cond);
                pop_reg("x9");
                emit("cmp x9, #0");
                emit("b.eq " + exit_l);
                enter_scope();
                break_stack_.push_back(exit_l);
                for (const auto& s : stmt->body) emit_stmt(s);
                break_stack_.pop_back();
                exit_scope();
                emit("b " + cond_l);
                label(exit_l);
                return;
            }
            case Stmt::Kind::Return: {
                if (stmt->expr) {
                    std::string t = infer_type(stmt->expr).value_or(T_INT);
                    gen_expr(stmt->expr);
                    pop_reg(is_float(t) ? "d0" : "x0");
                }
                emit("b L." + fn_ + ".ret");
                return;
            }
            case Stmt::Kind::Break: {
                if (break_stack_.empty()) throw TenetError("`break` 出现在循环之外");
                emit("b " + break_stack_.back());
                return;
            }
            case Stmt::Kind::FnDecl:
                return;
        }
    }

    int lookup_slot(const std::string& name) const {
        for (auto it = scope_stack_.rbegin(); it != scope_stack_.rend(); ++it) {
            auto f = flat_maps_[*it].find(name);
            if (f != flat_maps_[*it].end()) return f->second;
        }
        throw TenetError("未定义的变量 `" + name + "`");
    }

    /// 进入一个块作用域（消费预计算索引）。
    void enter_scope() {
        int idx = scope_queue_[scope_cursor_++];
        scope_stack_.push_back(idx);
    }

    void exit_scope() { scope_stack_.pop_back(); }

    std::string var_type(const std::string& name) const {
        auto it = types_.find(name);
        if (it != types_.end()) return it->second;
        throw TenetError("未定义的变量 `" + name + "`");
    }

    // ---- 表达式 ----

    /// 生成表达式：结果压入表达式栈；返回类型（Tenet 类型或 "void"）。
    std::string gen_expr(const ExprPtr& e) {
        switch (e->kind) {
            case Expr::Kind::Int: {
                emit_int_const(e->int_val);
                push_reg("x9");
                return T_INT;
            }
            case Expr::Kind::Float: {
                std::string name = "L.flt." + std::to_string(flt_c_++);
                data_ += ".section __TEXT,__const\n";
                data_ += ".align 3\n";
                data_ += name + ":\n";
                data_ += "\t.double " + std::to_string(e->float_val) + "\n";
                emit("adrp x9, " + name + "@PAGE");
                emit("add x9, x9, " + name + "@PAGEOFF");
                emit("ldr d9, [x9]");
                push_reg("d9");
                return T_FLOAT;
            }
            case Expr::Kind::Str: {
                load_string(e->str_val);
                push_reg("x9");
                return T_STR;
            }
            case Expr::Kind::Bool: {
                emit("mov x9, #" + std::string(e->bool_val ? "1" : "0"));
                push_reg("x9");
                return T_BOOL;
            }
            case Expr::Kind::Var: {
                std::string t = var_type(e->name);
                int off = lookup_slot(e->name);
                if (is_float(t)) {
                    emit("ldr d9, [x29, #" + std::to_string(off) + "]");
                    push_reg("d9");
                } else {
                    emit("ldr x9, [x29, #" + std::to_string(off) + "]");
                    push_reg("x9");
                }
                return t;
            }
            case Expr::Kind::Assign: {
                std::string t = var_type(e->name);
                gen_expr(e->value);
                int off = lookup_slot(e->name);
                pop_reg(is_float(t) ? "d9" : "x9");
                emit("str " + std::string(is_float(t) ? "d9" : "x9") + ", [x29, #" +
                     std::to_string(off) + "]");
                push_reg(is_float(t) ? "d9" : "x9");
                return t;
            }
            case Expr::Kind::Unary: {
                std::string t = gen_expr(e->value);
                if (e->op == OP_NEG) {
                    pop_reg(is_float(t) ? "d10" : "x10");
                    if (is_float(t)) {
                        emit("fneg d9, d10");
                        push_reg("d9");
                    } else {
                        emit("neg x9, x10");
                        push_reg("x9");
                    }
                    return t;
                }
                // !
                pop_reg("x10");
                emit("cmp x10, #0");
                emit("cset x9, eq");
                push_reg("x9");
                return T_BOOL;
            }
            case Expr::Kind::Binary:
                return gen_binary(e);
            case Expr::Kind::Call:
                return gen_call(e->name, e->args);
        }
        throw TenetError("未知的表达式类型");
    }

    void emit_int_const(int64_t v) {
        if (v >= -32768 && v <= 32767) {
            emit("mov x9, #" + std::to_string(v));
            return;
        }
        uint64_t u = static_cast<uint64_t>(v);
        emit("movz x9, #" + std::to_string(u & 0xFFFF));
        for (int shift = 16; shift < 64; shift += 16) {
            uint64_t part = (u >> shift) & 0xFFFF;
            if (part != 0) {
                emit("movk x9, #" + std::to_string(part) + ", lsl #" + std::to_string(shift));
            }
        }
    }

    std::string gen_binary(const ExprPtr& e) {
        const std::string& op = e->op;
        bool is_compare = op == OP_EQ || op == OP_NEQ || op == OP_LT || op == OP_LTE ||
                          op == OP_GT || op == OP_GTE;
        std::string lt = infer_type(e->lhs).value_or(T_INT);
        std::string rt = infer_type(e->rhs).value_or(T_INT);

        // 字符串拼接 / 比较：先都入栈，再弹（嵌套调用不破坏寄存器）
        if (lt == T_STR && rt == T_STR) {
            gen_expr(e->lhs);
            gen_expr(e->rhs);
            if (op == OP_ADD) {
                pop_reg("x1");
                pop_reg("x0");
                emit("bl _tenet_concat");
                push_reg("x0");
                return T_STR;
            }
            if (is_compare) {
                pop_reg("x1");
                pop_reg("x0");
                emit("bl _tenet_strcmp");
                emit("cmp x0, #0");
                emit("cset x9, " + cond_code(op));
                push_reg("x9");
                return T_BOOL;
            }
            throw TenetError("运算符 `" + op + "` 不能作用于 string 和 string");
        }

        if (op == OP_AND || op == OP_OR) return gen_logic(op, e);

        // 数值：先 lhs 后 rhs 入栈，再逆序弹出
        gen_expr(e->lhs);
        gen_expr(e->rhs);
        bool any_float = is_float(lt) || is_float(rt);
        if (any_float) {
            pop_reg(is_float(rt) ? "d10" : "x10");
            pop_reg(is_float(lt) ? "d9" : "x9");
            if (!is_float(lt)) emit("scvtf d9, x9");
            if (!is_float(rt)) emit("scvtf d10, x10");
            if (is_compare) {
                emit("fcmp d9, d10");
                emit("cset x9, " + cond_code(op));
                push_reg("x9");
                return T_BOOL;
            }
            std::string instr = op == OP_ADD ? "fadd" : op == OP_SUB ? "fsub"
                              : op == OP_MUL ? "fmul" : op == OP_DIV ? "fdiv" : "";
            if (instr.empty()) throw TenetError("运算符 `%` 只能作用于 int");
            emit(instr + " d9, d9, d10");
            push_reg("d9");
            return T_FLOAT;
        }
        // 整数
        pop_reg("x10");
        pop_reg("x9");
        if (is_compare) {
            emit("cmp x9, x10");
            emit("cset x9, " + cond_code(op));
            push_reg("x9");
            return T_BOOL;
        }
        if (op == OP_ADD) emit("add x9, x9, x10");
        else if (op == OP_SUB) emit("sub x9, x9, x10");
        else if (op == OP_MUL) emit("mul x9, x9, x10");
        else if (op == OP_DIV) emit("sdiv x9, x9, x10");
        else if (op == OP_MOD) {
            emit("sdiv x11, x9, x10");
            emit("msub x9, x11, x10, x9");
        } else throw TenetError("未知运算符 `" + op + "`");
        push_reg("x9");
        return T_INT;
    }

    std::string cond_code(const std::string& op) const {
        if (op == OP_EQ) return "eq";
        if (op == OP_NEQ) return "ne";
        if (op == OP_LT) return "lt";
        if (op == OP_LTE) return "le";
        if (op == OP_GT) return "gt";
        return "ge";
    }

    std::string gen_logic(const std::string& op, const ExprPtr& e) {
        gen_expr(e->lhs);
        pop_reg("x9");
        emit("cmp x9, #0");
        auto short_l = new_label("short");
        auto end_l = new_label("end");
        if (op == OP_AND) {
            emit("b.eq " + short_l);
            gen_expr(e->rhs);
            pop_reg("x10");
            emit("cmp x10, #0");
            emit("b.eq " + short_l);
            emit("mov x9, #1");
        } else {
            emit("b.ne " + short_l);
            gen_expr(e->rhs);
            pop_reg("x10");
            emit("cmp x10, #0");
            emit("b.ne " + short_l);
            emit("mov x9, #0");
        }
        emit("b " + end_l);
        label(short_l);
        emit("mov x9, #" + std::string(op == OP_AND ? "0" : "1"));
        label(end_l);
        push_reg("x9");
        return T_BOOL;
    }

    std::string gen_call(const std::string& callee, const std::vector<ExprPtr>& args) {
        if (callee == "print") return gen_print(args);
        auto it = functions_.find(callee);
        if (it == functions_.end()) throw TenetError("未定义的函数 `" + callee + "`");
        const FnSig& sig = it->second;
        if (sig.params.size() != args.size()) {
            throw TenetError("函数 `" + callee + "` 需要 " + std::to_string(sig.params.size()) +
                             " 个参数，实际传入 " + std::to_string(args.size()) + " 个");
        }
        if (args.size() > 8) throw TenetError("暂不支持超过 8 个参数");
        for (const auto& a : args) gen_expr(a);
        for (int i = (int)args.size() - 1; i >= 0; --i) {
            pop_reg(is_float(sig.params[i]) ? "d" + std::to_string(i) : "x" + std::to_string(i));
        }
        emit("bl _" + callee);
        if (!sig.ret.has_value()) return "void";
        if (is_float(*sig.ret)) {
            push_reg("d0");
        } else {
            push_reg("x0");
        }
        return *sig.ret;
    }

    /// print(a, b, ...)：Apple 变参约定——fmt 在 x0，变参全部压栈（实测与 clang 一致）。
    std::string gen_print(const std::vector<ExprPtr>& args) {
        std::string fmt;
        std::vector<std::string> types;
        for (size_t i = 0; i < args.size(); ++i) {
            if (i > 0) fmt += " ";
            std::string t = gen_expr(args[i]);
            types.push_back(t);
            if (t == T_INT) fmt += "%lld";
            else if (t == T_FLOAT) fmt += "%g";
            else if (t == T_STR) fmt += "%s";
            else if (t == T_BOOL) fmt += "%s";
            else throw TenetError("print 不支持该类型的值");
        }
        fmt += "\n";
        std::string fmt_name = "L.fmt." + std::to_string(str_c_++);
        data_string(fmt, fmt_name);

        int n = (int)args.size();
        if (n > 7) throw TenetError("print 暂不支持超过 7 个参数");
        // 逆序弹出到暂存寄存器 x9..x15（bool 转 true/false 串）
        for (int i = n - 1; i >= 0; --i) {
            std::string reg = "x" + std::to_string(9 + (n - 1 - i));
            if (types[i] == T_BOOL) {
                // 直接 pop 进目标寄存器；select 用 x16/x17（scratch，不占用结果寄存器）
                pop_reg(reg);
                emit("cmp " + reg + ", #0");
                std::string tn = "L.bool.true." + std::to_string(str_c_++);
                std::string fn = "L.bool.false." + std::to_string(str_c_++);
                data_string("true", tn);
                data_string("false", fn);
                emit("adrp x16, " + tn + "@PAGE");
                emit("add x16, x16, " + tn + "@PAGEOFF");
                emit("adrp x17, " + fn + "@PAGE");
                emit("add x17, x17, " + fn + "@PAGEOFF");
                emit("csel " + reg + ", x16, x17, ne");
            } else {
                pop_reg(reg);
            }
        }
        // 参数区压栈（16 对齐），变参从 [sp] 连续存放（Apple 约定，无保留槽）
        int area = ((8 * n) + 15) / 16 * 16;
        if (area > 0) emit("sub sp, sp, #" + std::to_string(area));
        for (int i = 0; i < n; ++i) {
            emit("str x" + std::to_string(9 + (n - 1 - i)) + ", [sp, #" +
                 std::to_string(8 * i) + "]");
        }
        emit("adrp x0, " + fmt_name + "@PAGE");
        emit("add x0, x0, " + fmt_name + "@PAGEOFF");
        emit("bl _printf");
        if (area > 0) emit("add sp, sp, #" + std::to_string(area));
        return "void";
    }

    // ---- 类型推断 ----

    std::optional<std::string> infer_type(const ExprPtr& e) {
        switch (e->kind) {
            case Expr::Kind::Int: return T_INT;
            case Expr::Kind::Float: return T_FLOAT;
            case Expr::Kind::Str: return T_STR;
            case Expr::Kind::Bool: return T_BOOL;
            case Expr::Kind::Var: return var_type(e->name);
            case Expr::Kind::Assign: return var_type(e->name);
            case Expr::Kind::Unary:
                if (e->op == OP_NOT) return T_BOOL;
                return infer_type(e->value);
            case Expr::Kind::Binary: {
                auto lt = infer_type(e->lhs);
                auto rt = infer_type(e->rhs);
                const std::string& op = e->op;
                if (op == OP_AND || op == OP_OR) return T_BOOL;
                if (op == OP_EQ || op == OP_NEQ || op == OP_LT || op == OP_LTE || op == OP_GT || op == OP_GTE) return T_BOOL;
                if (op == OP_MOD) {
                    return (lt == T_INT && rt == T_INT) ? std::optional<std::string>(T_INT) : std::nullopt;
                }
                if (op == OP_ADD) {
                    if (lt == T_STR && rt == T_STR) return T_STR;
                    if (lt == T_FLOAT || rt == T_FLOAT) return T_FLOAT;
                    if (lt == T_INT && rt == T_INT) return T_INT;
                    return std::nullopt;
                }
                if (lt == T_FLOAT || rt == T_FLOAT) return T_FLOAT;
                if (lt == T_INT && rt == T_INT) return T_INT;
                return std::nullopt;
            }
            case Expr::Kind::Call: {
                auto it = functions_.find(e->name);
                if (it == functions_.end() || !it->second.ret.has_value()) return std::nullopt;
                return it->second.ret;
            }
        }
        return std::nullopt;
    }
};

}  // namespace tenet
