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
        b.collect_structs(program);
        b.collect_signatures(program);
        b.emit_program(program);
        std::string out = b.text_;
        out += "\n";
        out += RUNTIME_ASM;
        return out;
    }

    /// 内嵌运行时（arm64 汇编）：字符串拼接/比较、数组越界报错，经 libc 实现。
    static constexpr const char* RUNTIME_ASM =
        "\t.text\n"
        "\t.p2align 2\n"
        "_tenet_strcmp:\n"
        "\tb _strcmp\n"
        "\t.p2align 2\n"
        "_tenet_bounds_fail:\n"
        "\tstp x29, x30, [sp, #-16]!\n"
        "\tmov x29, sp\n"
        "\tmov x11, x0\n"
        "\tmov x12, x1\n"
        "\tadrp x1, L.bounds.fmt@PAGE\n"
        "\tadd x1, x1, L.bounds.fmt@PAGEOFF\n"
        "\tmov x0, #2\n"
        "\tsub sp, sp, #16\n"
        "\tstr x11, [sp]\n"
        "\tstr x12, [sp, #8]\n"
        "\tbl _dprintf\n"
        "\tmov x0, #1\n"
        "\tbl _exit\n"
        "\t.section __TEXT,__cstring\n"
        "L.bounds.fmt:\n"
        "\t.asciz \"Tenet runtime error: array index %lld out of bounds for length %lld\\n\"\n"
        "\t.text\n"
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
    /// 顶层 struct 名 → 字段 (名, 标量类型)，字段顺序即槽位顺序。
    std::unordered_map<std::string, std::vector<std::pair<std::string, std::string>>> structs_;

    // 当前函数状态
    std::string fn_;
    std::optional<std::string> current_ret_;   // 当前函数声明返回类型（None = void）
    std::vector<std::unordered_map<std::string, int>> flat_maps_;  // 所有块作用域的槽位表
    std::vector<std::unordered_map<std::string, std::string>> type_maps_;  // 与 flat_maps_ 同索引
    std::vector<std::unordered_map<std::string, int>> array_len_maps_;  // 与 flat_maps_ 同索引：数组长度
    std::vector<int> scope_stack_;                                 // 当前作用域链（索引）
    std::vector<int> scope_queue_;                                 // 预计算的块索引（按遍历序）
    size_t scope_cursor_ = 0;                                      // 消费 scope_queue_
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

    bool is_scalar_type(const std::string& t) const {
        return t == T_INT || t == T_FLOAT || t == T_BOOL || t == T_STR;
    }

    /// `array<T>` → `T`；不是数组返回 nullopt。
    static std::optional<std::string> array_elem(const std::string& ty) {
        const std::string prefix = "array<";
        if (ty.size() <= prefix.size() + 1) return std::nullopt;
        if (ty.compare(0, prefix.size(), prefix) != 0) return std::nullopt;
        if (ty.back() != '>') return std::nullopt;
        return ty.substr(prefix.size(), ty.size() - prefix.size() - 1);
    }

    bool is_array(const std::string& t) const { return array_elem(t).has_value(); }

    /// 取数组元素类型并校验 v1 限制：元素只能是 int/float/bool。
    std::string array_elem_scalar(const std::string& ty, const Position& pos) const {
        auto elem = array_elem(ty);
        if (!elem.has_value()) {
            throw TenetError::at_pos("不是数组类型：" + ty, pos);
        }
        if (*elem != T_INT && *elem != T_FLOAT && *elem != T_BOOL) {
            throw TenetError::at_pos("v1 数组元素只支持 int/float/bool，实际 `" + *elem + "`",
                                     pos);
        }
        return *elem;
    }

    bool is_struct(const std::string& t) const { return structs_.count(t) != 0; }

    const std::vector<std::pair<std::string, std::string>>& struct_fields(
        const std::string& ty, const Position& pos) const {
        auto it = structs_.find(ty);
        if (it == structs_.end()) {
            throw TenetError::at_pos("未定义的 struct `" + ty + "`", pos);
        }
        return it->second;
    }

    std::optional<std::string> field_type(const std::string& ty, const std::string& field) const {
        auto it = structs_.find(ty);
        if (it == structs_.end()) return std::nullopt;
        for (const auto& [fname, fty] : it->second) {
            if (fname == field) return fty;
        }
        return std::nullopt;
    }

    /// 收集并校验顶层 struct 声明（字段只允许 int/float/bool、字段名唯一）。
    void collect_structs(const Program& program) {
        for (const auto& stmt : program.stmts) {
            if (stmt->kind != Stmt::Kind::StructDecl) continue;
            const std::string& name = stmt->name;
            if (is_scalar_type(name)) {
                throw TenetError::at_pos("struct 名 `" + name + "` 不能与标量类型重名", stmt->pos);
            }
            if (structs_.count(name)) {
                throw TenetError::at_pos("struct `" + name + "` 重复定义", stmt->pos);
            }
            if (stmt->fields.empty()) {
                throw TenetError::at_pos("struct `" + name + "` 至少需要一个字段", stmt->pos);
            }
            std::unordered_map<std::string, int> seen;
            for (const auto& [fname, fty] : stmt->fields) {
                if (fty != T_INT && fty != T_FLOAT && fty != T_BOOL) {
                    throw TenetError::at_pos(
                        "struct `" + name + "` 的字段 `" + fname + "` 只支持 int/float/bool",
                        stmt->pos);
                }
                if (seen.count(fname)) {
                    throw TenetError::at_pos("struct `" + name + "` 的字段 `" + fname + "` 重复",
                                             stmt->pos);
                }
                seen[fname] = 1;
            }
            structs_[name] = stmt->fields;
        }
    }

    void collect_signatures(const Program& program) {
        for (const auto& stmt : program.stmts) {
            if (stmt->kind != Stmt::Kind::FnDecl) continue;
            const auto& name = stmt->name;
            if (name == "main" || name == "printf" || name == "tenet_concat" || name == "tenet_strcmp") {
                throw TenetError::at_pos("函数名 `" + name + "` 为编译器保留", stmt->pos);
            }
            if (functions_.count(name)) {
                throw TenetError::at_pos("函数 `" + name + "` 重复定义", stmt->pos);
            }
            for (const auto& [pn, pt] : stmt->params) {
                if (is_struct(pt)) {
                    throw TenetError::at_pos(
                        "v1 不支持 struct 参数：`" + name + "` 的参数 `" + pn + "` 是 `" + pt + "`",
                        stmt->pos);
                }
                if (is_array(pt)) {
                    throw TenetError::at_pos(
                        "v1 不支持 array 参数：`" + name + "` 的参数 `" + pn + "` 是 `" + pt + "`",
                        stmt->pos);
                }
                if (!is_scalar_type(pt)) {
                    throw TenetError::at_pos("函数 `" + name + "` 的参数 `" + pn +
                                                 "` 类型未定义：`" + pt + "`",
                                             stmt->pos);
                }
            }
            if (stmt->ret.has_value()) {
                const std::string& rt = *stmt->ret;
                if (is_struct(rt)) {
                    throw TenetError::at_pos(
                        "v1 不支持 struct 返回值：`" + name + "` 返回 `" + rt + "`", stmt->pos);
                }
                if (is_array(rt)) {
                    throw TenetError::at_pos(
                        "v1 不支持 array 返回值：`" + name + "` 返回 `" + rt + "`", stmt->pos);
                }
                if (!is_scalar_type(rt)) {
                    throw TenetError::at_pos(
                        "函数 `" + name + "` 的返回类型未定义：`" + rt + "`", stmt->pos);
                }
            }
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

    /// let 的最终类型：显式标注优先，否则静态推断。显式标了未知类型直接报错。
    std::string resolve_let_type(const Stmt& stmt) {
        if (stmt.ty.has_value()) {
            const std::string& t = *stmt.ty;
            if (is_array(t)) {
                array_elem_scalar(t, stmt.pos);  // v1：元素仅 int/float/bool
                return t;
            }
            if (!is_scalar_type(t) && !is_struct(t)) {
                throw TenetError::at_pos("未定义的 struct `" + t + "`", stmt.pos);
            }
            return t;
        }
        auto inf = infer_type(stmt.value);
        if (!inf.has_value()) {
            throw TenetError::at_pos("无法推断 `" + stmt.name + "` 的类型，请显式标注",
                                     stmt.pos);
        }
        return *inf;
    }

    /// 数组 let 的定长长度：字面量取元素个数，变量取源数组长度。
    int plan_array_len(const Stmt& stmt, const std::string& ty) {
        const ExprPtr& v = stmt.value;
        if (!v) {
            throw TenetError::at_pos("`" + stmt.name + "` 的数组初始化缺失", stmt.pos);
        }
        if (v->kind == Expr::Kind::Array) {
            if (v->args.empty()) {
                throw TenetError::at_pos("v1 不支持空数组字面量", v->pos);
            }
            return (int)v->args.size();
        }
        if (v->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(v->name, v->pos);
            if (src_ty != ty) {
                throw TenetError::at_pos(
                    "`" + stmt.name + "` 需要 " + ty + "，但 `" + v->name + "` 是 " + src_ty,
                    v->pos);
            }
            return lookup_array_len(v->name, v->pos);
        }
        throw TenetError::at_pos(
            "`" + stmt.name + "` 的数组初始化必须是 `[...]` 或同类型数组变量", v->pos);
    }

    /// 遍历语句分配变量槽位（let 按出现顺序；遮蔽用不同槽）。
    /// 每个块（fn/if-then/if-else/while）在 flat_maps_ 里占一个表，
    /// 索引按遍历序压入 scope_queue_，发射时按同序消费——槽位不丢失。
    void plan_stmts(const std::vector<StmtPtr>& stmts, int& next_slot) {
        for (const auto& s : stmts) {
            switch (s->kind) {
                case Stmt::Kind::Let: {
                    std::string t = resolve_let_type(*s);
                    type_maps_[scope_stack_.back()][s->name] = t;
                    // struct 变量扁平化为字段槽位：name 指向首字段（禁止直接取值），
                    // 每个字段一个 8 字节槽；name.field 作为该字段的槽位键。
                    // 数组变量占用连续的 N 个槽：name 的槽位指向元素 0（最低地址），
                    // 元素 i 的槽位 = base + 8*i。
                    if (is_array(t)) {
                        int len = plan_array_len(*s, t);
                        int base_offset = -(8 * (next_slot + len));
                        flat_maps_[scope_stack_.back()][s->name] = base_offset;
                        array_len_maps_[scope_stack_.back()][s->name] = len;
                        next_slot += len;
                        break;
                    }
                    int first_offset = -(8 * (next_slot + 1));
                    flat_maps_[scope_stack_.back()][s->name] = first_offset;
                    if (is_struct(t)) {
                        const auto& defs = struct_fields(t, s->pos);
                        for (const auto& f : defs) {
                            flat_maps_[scope_stack_.back()][s->name + "." + f.first] =
                                -(8 * (next_slot + 1));
                            ++next_slot;
                        }
                    } else {
                        ++next_slot;
                    }
                    break;
                }
                case Stmt::Kind::If: {
                    flat_maps_.push_back({});
                    type_maps_.push_back({});
                    array_len_maps_.push_back({});
                    scope_queue_.push_back((int)flat_maps_.size() - 1);
                    scope_stack_.push_back((int)flat_maps_.size() - 1);
                    plan_stmts(s->then_branch, next_slot);
                    scope_stack_.pop_back();
                    if (!s->else_branch.empty()) {
                        flat_maps_.push_back({});
                        type_maps_.push_back({});
                        array_len_maps_.push_back({});
                        scope_queue_.push_back((int)flat_maps_.size() - 1);
                        scope_stack_.push_back((int)flat_maps_.size() - 1);
                        plan_stmts(s->else_branch, next_slot);
                        scope_stack_.pop_back();
                    }
                    break;
                }
                case Stmt::Kind::While: {
                    flat_maps_.push_back({});
                    type_maps_.push_back({});
                    array_len_maps_.push_back({});
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

    /// 大帧（数组可能占很多槽）超过 sub/add 的 12 位立即数范围时走寄存器。
    void emit_frame_adjust(int frame, bool allocate) {
        if (frame <= 0) return;
        if (frame <= 4095) {
            emit(std::string(allocate ? "sub" : "add") + " sp, sp, #" + std::to_string(frame));
            return;
        }
        emit_mov_const("x16", frame);
        emit(std::string(allocate ? "sub" : "add") + " sp, sp, x16");
    }

    void emit_fn(const StmtPtr& stmt) {
        const auto& name = stmt->name;
        if (stmt->ret.has_value() && !stmt->body.empty() &&
            stmt->body.back()->kind != Stmt::Kind::Return) {
            throw TenetError::at_pos("函数 `" + name + "` 声明了返回类型，但函数末尾没有 return",
                                     stmt->pos);
        }
        // 规划：参数槽 + 局部槽（作用域索引按遍历序进队列）
        flat_maps_.clear();
        type_maps_.clear();
        array_len_maps_.clear();
        scope_queue_.clear();
        scope_cursor_ = 0;
        scope_stack_.clear();
        flat_maps_.push_back({});
        type_maps_.push_back({});
        array_len_maps_.push_back({});
        scope_queue_.push_back(0);
        scope_stack_.push_back(0);
        int next_slot = (int)stmt->params.size();
        for (int i = 0; i < (int)stmt->params.size(); ++i) {
            flat_maps_[0][stmt->params[i].first] = -(8 * (i + 1));
            type_maps_[0][stmt->params[i].first] = stmt->params[i].second;
        }
        plan_stmts(stmt->body, next_slot);
        scope_stack_.pop_back();
        frame_ = ((next_slot * 8) + 15) / 16 * 16;

        fn_ = name;
        current_ret_ = stmt->ret;
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
        emit_frame_adjust(frame_, true);
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
        emit_frame_adjust(frame_, false);
        emit("ldp x29, x30, [sp], #16");
        emit("ret");
        fn_.clear();
        current_ret_ = std::nullopt;
    }

    void emit_main(const Program& program) {
        fn_ = "main";
        current_ret_ = std::nullopt;
        int next_slot = 0;
        std::vector<StmtPtr> body;
        for (const auto& s : program.stmts) {
            if (s->kind == Stmt::Kind::FnDecl) continue;
            if (s->kind == Stmt::Kind::Return) {
                throw TenetError::at_pos("顶层不能使用 `return`（main 自动返回 0）", s->pos);
            }
            body.push_back(s);
        }
        flat_maps_.clear();
        type_maps_.clear();
        array_len_maps_.clear();
        scope_queue_.clear();
        scope_cursor_ = 0;
        scope_stack_.clear();
        flat_maps_.push_back({});
        type_maps_.push_back({});
        array_len_maps_.push_back({});
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
        emit_frame_adjust(frame_, true);
        for (const auto& s : body) emit_stmt(s);
        label("L.main.ret");
        emit("mov x0, #0");
        emit_frame_adjust(frame_, false);
        emit("ldp x29, x30, [sp], #16");
        emit("ret");
        fn_.clear();
    }

    // ---- 语句 ----

    void emit_stmt(const StmtPtr& stmt) {
        switch (stmt->kind) {
            case Stmt::Kind::Let: {
                std::string t = resolve_let_type(*stmt);
                type_maps_[scope_stack_.back()][stmt->name] = t;
                if (is_struct(t)) {
                    emit_struct_init(*stmt, t);
                    return;
                }
                if (is_array(t)) {
                    emit_array_init(*stmt, t);
                    return;
                }
                std::string vt = gen_expr(stmt->value);
                if (vt != t) {
                    throw TenetError::at_pos("`" + stmt->name + "` 初始化类型不匹配：标注 " + t +
                                                 "，实际 " + vt,
                                             stmt->pos);
                }
                int off = lookup_slot(stmt->name, stmt->pos);
                pop_reg(is_float(t) ? "d9" : "x9");
                store_slot(is_float(t) ? "d9" : "x9", off);
                return;
            }
            case Stmt::Kind::Expr: {
                std::string t = gen_expr(stmt->expr);
                if (t != "void") pop_reg("x9");  // 丢弃结果
                return;
            }
            case Stmt::Kind::If: {
                std::string ct = gen_expr(stmt->cond);
                if (ct != T_BOOL) {
                    throw TenetError::at_pos("条件表达式需要 bool，实际为 " + ct, stmt->cond->pos);
                }
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
                std::string ct = gen_expr(stmt->cond);
                if (ct != T_BOOL) {
                    throw TenetError::at_pos("条件表达式需要 bool，实际为 " + ct, stmt->cond->pos);
                }
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
                    std::string vt = gen_expr(stmt->expr);
                    if (!current_ret_.has_value()) {
                        throw TenetError::at_pos("函数 `" + fn_ + "` 没有返回类型，不能 return 值",
                                                 stmt->expr->pos);
                    }
                    if (vt != *current_ret_) {
                        throw TenetError::at_pos("函数 `" + fn_ + "` 返回类型不匹配：声明 " +
                                                     *current_ret_ + "，实际 " + vt,
                                                 stmt->expr->pos);
                    }
                    pop_reg(is_float(vt) ? "d0" : "x0");
                }
                emit("b L." + fn_ + ".ret");
                return;
            }
            case Stmt::Kind::Break: {
                if (break_stack_.empty()) {
                    throw TenetError::at_pos("`break` 出现在循环之外", stmt->pos);
                }
                emit("b " + break_stack_.back());
                return;
            }
            case Stmt::Kind::FnDecl:
                return;
            case Stmt::Kind::StructDecl:
                return;
        }
    }

    int lookup_slot(const std::string& name, const Position& pos) const {
        for (auto it = scope_stack_.rbegin(); it != scope_stack_.rend(); ++it) {
            auto f = flat_maps_[*it].find(name);
            if (f != flat_maps_[*it].end()) return f->second;
        }
        throw TenetError::at_pos("未定义的变量 `" + name + "`", pos);
    }

    /// 进入一个块作用域（消费预计算索引）。
    void enter_scope() {
        int idx = scope_queue_[scope_cursor_++];
        scope_stack_.push_back(idx);
    }

    void exit_scope() { scope_stack_.pop_back(); }

    std::string var_type(const std::string& name, const Position& pos) const {
        for (auto it = scope_stack_.rbegin(); it != scope_stack_.rend(); ++it) {
            const auto& table = type_maps_[*it];
            auto f = table.find(name);
            if (f != table.end()) return f->second;
        }
        throw TenetError::at_pos("未定义的变量 `" + name + "`", pos);
    }

    // ---- struct v1：扁平化字段槽位 ----

    /// 取变量的 Tenet 类型，同时确认它在当前作用域可见。
    std::string scoped_var_type(const std::string& name, const Position& pos) const {
        (void)lookup_slot(name, pos);
        return var_type(name, pos);
    }

    /// 字段读写前的类型解析：base 必须是 struct 变量，字段必须存在。
    std::string field_access_type(const std::string& var, const std::string& field,
                                  const Position& pos, bool writing) const {
        std::string t = scoped_var_type(var, pos);
        if (!is_struct(t)) {
            throw TenetError::at_pos("`" + var + "` 不是 struct，不能" +
                                         (writing ? "写" : "取") + "字段 `" + field + "`",
                                     pos);
        }
        auto ft = field_type(t, field);
        if (!ft.has_value()) {
            throw TenetError::at_pos("struct `" + t + "` 没有字段 `" + field + "`", pos);
        }
        return *ft;
    }

    int field_slot(const std::string& var, const std::string& field,
                   const Position& pos) const {
        return lookup_slot(var + "." + field, pos);
    }

    /// 把 struct 字面量的字段逐个求值并存入 dst 的字段槽（不做聚合写入）。
    void store_struct_lit(const std::string& dst, const std::string& ty,
                          const ExprPtr& lit) {
        const auto& defs = struct_fields(ty, lit->pos);
        std::unordered_map<std::string, ExprPtr> inits;
        for (const auto& [fname, fexpr] : lit->fields) {
            if (inits.count(fname)) {
                throw TenetError::at_pos("struct `" + ty + "` 的字段 `" + fname + "` 重复初始化",
                                         fexpr->pos);
            }
            inits[fname] = fexpr;
        }
        for (const auto& [fname, fexpr] : lit->fields) {
            if (!field_type(ty, fname).has_value()) {
                throw TenetError::at_pos("struct `" + ty + "` 没有字段 `" + fname + "`",
                                         fexpr->pos);
            }
        }
        for (const auto& [fname, fty] : defs) {
            auto it = inits.find(fname);
            if (it == inits.end()) {
                throw TenetError::at_pos("struct `" + ty + "` 缺少字段 `" + fname + "`",
                                         lit->pos);
            }
            const ExprPtr& fexpr = it->second;
            std::string vt = gen_expr(fexpr);
            if (vt != fty) {
                throw TenetError::at_pos("struct `" + ty + "` 字段 `" + fname +
                                             "` 类型不匹配：需要 " + fty + "，实际 " + vt,
                                         fexpr->pos);
            }
            int off = field_slot(dst, fname, fexpr->pos);
            pop_reg(is_float(fty) ? "d9" : "x9");
            store_slot(is_float(fty) ? "d9" : "x9", off);
        }
    }

    /// 逐字段值拷贝：struct 变量之间不共享槽位。
    void copy_struct(const std::string& dst, const std::string& src, const std::string& ty,
                     const Position& pos) {
        for (const auto& [fname, fty] : struct_fields(ty, pos)) {
            int src_off = field_slot(src, fname, pos);
            int dst_off = field_slot(dst, fname, pos);
            std::string reg = is_float(fty) ? "d9" : "x9";
            load_slot(reg, src_off);
            store_slot(reg, dst_off);
        }
    }

    /// let p: Point = Point { ... }; 或 let q = p;
    void emit_struct_init(const Stmt& stmt, const std::string& ty) {
        const ExprPtr& v = stmt.value;
        if (v->kind == Expr::Kind::StructLit) {
            if (v->name != ty) {
                throw TenetError::at_pos(
                    "`" + stmt.name + "` 标注为 " + ty + "，但字面量是 " + v->name, v->pos);
            }
            store_struct_lit(stmt.name, ty, v);
            return;
        }
        if (v->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(v->name, v->pos);
            if (src_ty != ty) {
                throw TenetError::at_pos(
                    "`" + stmt.name + "` 需要 " + ty + "，但 `" + v->name + "` 是 " + src_ty,
                    v->pos);
            }
            copy_struct(stmt.name, v->name, ty, v->pos);
            return;
        }
        throw TenetError::at_pos("`" + stmt.name + "` 的 struct 初始化必须是 `" + ty +
                                     " { ... }` 或同类型 struct 变量",
                                 v->pos);
    }

    /// p = Point { ... }; 或 p = q;（逐字段覆盖）
    void assign_struct(const std::string& dst, const std::string& dst_ty, const ExprPtr& value,
                       const Position& pos) {
        if (value->kind == Expr::Kind::StructLit) {
            if (value->name != dst_ty) {
                throw TenetError::at_pos(
                    "赋值类型不匹配：需要 " + dst_ty + "，字面量是 " + value->name, pos);
            }
            store_struct_lit(dst, dst_ty, value);
            return;
        }
        if (value->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(value->name, value->pos);
            if (src_ty != dst_ty) {
                throw TenetError::at_pos(
                    "赋值类型不匹配：需要 " + dst_ty + "，右侧是 " + src_ty, pos);
            }
            copy_struct(dst, value->name, dst_ty, value->pos);
            return;
        }
        throw TenetError::at_pos("struct 整体赋值必须是同类型变量或字面量", value->pos);
    }

    // ---- array v1：定长栈数组（每元素 8 字节槽，bool 同样占 8 字节）----

    int lookup_array_len(const std::string& name, const Position& pos) const {
        for (auto it = scope_stack_.rbegin(); it != scope_stack_.rend(); ++it) {
            auto f = array_len_maps_[*it].find(name);
            if (f != array_len_maps_[*it].end()) return f->second;
        }
        throw TenetError::at_pos("`" + name + "` 不是数组", pos);
    }

    /// 编译期常量下标（字面量，含 `-1` 这种一元负号形式）。
    static std::optional<int64_t> const_index(const ExprPtr& e) {
        if (!e) return std::nullopt;
        if (e->kind == Expr::Kind::Int) return e->int_val;
        if (e->kind == Expr::Kind::Unary && e->op == OP_NEG && e->value &&
            e->value->kind == Expr::Kind::Int) {
            return -e->value->int_val;
        }
        return std::nullopt;
    }

    /// 把常量装入任意寄存器（大数组槽位地址用）。
    void emit_mov_const(const std::string& reg, int64_t v) {
        if (v >= -32768 && v <= 32767) {
            emit("mov " + reg + ", #" + std::to_string(v));
            return;
        }
        uint64_t u = static_cast<uint64_t>(v);
        emit("movz " + reg + ", #" + std::to_string(u & 0xFFFF));
        for (int shift = 16; shift < 64; shift += 16) {
            uint64_t part = (u >> shift) & 0xFFFF;
            if (part != 0) {
                emit("movk " + reg + ", #" + std::to_string(part) + ", lsl #" +
                         std::to_string(shift));
            }
        }
    }

    /// x29 相对槽位地址 → reg。ldr/str 的负立即数只有 9 位，大数组必须走寄存器寻址。
    void lea_slot(const std::string& reg, int off, const std::string& scratch = "x16") {
        if (off == 0) {
            emit("mov " + reg + ", x29");
            return;
        }
        int abs = off < 0 ? -off : off;
        if (abs <= 4095) {
            emit(std::string(off < 0 ? "sub " : "add ") + reg + ", x29, #" +
                 std::to_string(abs));
        } else {
            emit_mov_const(scratch, abs);
            emit(std::string(off < 0 ? "sub " : "add ") + reg + ", x29, " + scratch);
        }
    }

    void load_slot(const std::string& reg, int off) {
        if (off >= -256 && off <= 255) {
            emit("ldr " + reg + ", [x29, #" + std::to_string(off) + "]");
            return;
        }
        lea_slot("x16", off, "x17");
        emit("ldr " + reg + ", [x16]");
    }

    void store_slot(const std::string& reg, int off) {
        if (off >= -256 && off <= 255) {
            emit("str " + reg + ", [x29, #" + std::to_string(off) + "]");
            return;
        }
        lea_slot("x16", off, "x17");
        emit("str " + reg + ", [x16]");
    }

    /// 动态下标：地址 = 元素 0 槽位 + idx*8。
    void load_indexed(const std::string& reg, int base_off, const std::string& idx_reg) {
        lea_slot("x16", base_off, "x17");
        emit("ldr " + reg + ", [x16, " + idx_reg + ", lsl #3]");
    }

    void store_indexed(const std::string& reg, int base_off, const std::string& idx_reg) {
        lea_slot("x16", base_off, "x17");
        emit("str " + reg + ", [x16, " + idx_reg + ", lsl #3]");
    }

    /// 无符号比较同时挡住负数：idx >= len 时跳失败块，打印错误并 exit(1)。
    void emit_bounds_check(int len, const std::string& idx_reg) {
        if (len <= 4095) {
            emit("cmp " + idx_reg + ", #" + std::to_string(len));
        } else {
            emit_mov_const("x17", len);
            emit("cmp " + idx_reg + ", x17");
        }
        std::string fail = new_label("bounds.fail");
        std::string ok = new_label("bounds.ok");
        emit("b.hs " + fail);
        emit("b " + ok);
        label(fail);
        emit("mov x0, " + idx_reg);
        emit_mov_const("x1", len);
        emit("bl _tenet_bounds_fail");
        label(ok);
    }

    void copy_array_elems(int dst_off, int src_off, int len, const std::string& elem) {
        std::string reg = is_float(elem) ? "d9" : "x9";
        for (int i = 0; i < len; ++i) {
            load_slot(reg, src_off + 8 * i);
            store_slot(reg, dst_off + 8 * i);
        }
    }

    struct ArrayRef {
        std::string ty;
        std::string elem;
        int len = 0;
        int base_off = 0;
    };

    /// 下标读写共用的数组变量解析：必须是对局部数组变量取下标。
    ArrayRef array_ref(const ExprPtr& base, const Position& pos, bool writing) {
        if (!base || base->kind != Expr::Kind::Var) {
            throw TenetError::at_pos(
                std::string("v1 只支持对数组变量") + (writing ? "写下标" : "取下标"),
                base ? base->pos : pos);
        }
        ArrayRef ref;
        ref.ty = scoped_var_type(base->name, base->pos);
        if (!is_array(ref.ty)) {
            throw TenetError::at_pos(
                "`" + base->name + "` 不是数组，不能" + (writing ? "写下标" : "取下标"),
                base->pos);
        }
        ref.elem = array_elem_scalar(ref.ty, pos);
        ref.len = lookup_array_len(base->name, base->pos);
        ref.base_off = lookup_slot(base->name, base->pos);
        return ref;
    }

    std::string gen_index_read(const ExprPtr& e) {
        ArrayRef ref = array_ref(e->lhs, e->pos, false);
        if (auto ci = const_index(e->rhs)) {
            if (*ci < 0 || *ci >= ref.len) {
                throw TenetError::at_pos("数组下标 " + std::to_string(*ci) + " 越界（长度 " +
                                             std::to_string(ref.len) + "）",
                                         e->rhs->pos);
            }
            std::string reg = is_float(ref.elem) ? "d9" : "x9";
            load_slot(reg, ref.base_off + 8 * (int)*ci);
            push_reg(reg);
            return ref.elem;
        }
        std::string it = gen_expr(e->rhs);
        if (it != T_INT) {
            throw TenetError::at_pos("数组下标必须是 int，实际为 " + it, e->rhs->pos);
        }
        pop_reg("x10");
        emit_bounds_check(ref.len, "x10");
        std::string reg = is_float(ref.elem) ? "d9" : "x9";
        load_indexed(reg, ref.base_off, "x10");
        push_reg(reg);
        return ref.elem;
    }

    std::string gen_index_write(const ExprPtr& e, const ExprPtr& target) {
        ArrayRef ref = array_ref(target->lhs, target->pos, true);
        std::string reg = is_float(ref.elem) ? "d9" : "x9";
        if (auto ci = const_index(target->rhs)) {
            if (*ci < 0 || *ci >= ref.len) {
                throw TenetError::at_pos("数组下标 " + std::to_string(*ci) + " 越界（长度 " +
                                             std::to_string(ref.len) + "）",
                                         target->rhs->pos);
            }
            std::string vt = gen_expr(e->value);
            if (vt != ref.elem) {
                throw TenetError::at_pos("数组元素赋值类型不匹配：需要 " + ref.elem +
                                             "，实际 " + vt,
                                         e->value->pos);
            }
            pop_reg(reg);
            store_slot(reg, ref.base_off + 8 * (int)*ci);
            push_reg(reg);
            return ref.elem;
        }
        std::string it = gen_expr(target->rhs);
        if (it != T_INT) {
            throw TenetError::at_pos("数组下标必须是 int，实际为 " + it, target->rhs->pos);
        }
        pop_reg("x10");
        emit_bounds_check(ref.len, "x10");
        push_reg("x10");  // 保存下标，跨过右值求值
        std::string vt = gen_expr(e->value);
        if (vt != ref.elem) {
            throw TenetError::at_pos("数组元素赋值类型不匹配：需要 " + ref.elem + "，实际 " + vt,
                                     e->value->pos);
        }
        pop_reg(reg);
        pop_reg("x10");
        store_indexed(reg, ref.base_off, "x10");
        push_reg(reg);
        return ref.elem;
    }

    void emit_array_init(const Stmt& stmt, const std::string& ty) {
        std::string elem = array_elem_scalar(ty, stmt.pos);
        int base_off = lookup_slot(stmt.name, stmt.pos);
        int len = lookup_array_len(stmt.name, stmt.pos);
        const ExprPtr& v = stmt.value;
        if (v->kind == Expr::Kind::Array) {
            if ((int)v->args.size() != len) {
                throw TenetError::at_pos("数组初始化长度不匹配：需要 " + std::to_string(len) +
                                             "，实际 " + std::to_string(v->args.size()),
                                         v->pos);
            }
            for (size_t i = 0; i < v->args.size(); ++i) {
                std::string vt = gen_expr(v->args[i]);
                if (vt != elem) {
                    throw TenetError::at_pos("数组元素 " + std::to_string(i) +
                                                 " 类型不匹配：需要 " + elem + "，实际 " + vt,
                                             v->args[i]->pos);
                }
                std::string reg = is_float(elem) ? "d9" : "x9";
                pop_reg(reg);
                store_slot(reg, base_off + 8 * (int)i);
            }
            return;
        }
        if (v->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(v->name, v->pos);
            if (src_ty != ty) {
                throw TenetError::at_pos("`" + stmt.name + "` 需要 " + ty + "，但 `" +
                                             v->name + "` 是 " + src_ty,
                                         v->pos);
            }
            int src_off = lookup_slot(v->name, v->pos);
            copy_array_elems(base_off, src_off, len, elem);
            return;
        }
        throw TenetError::at_pos(
            "`" + stmt.name + "` 的数组初始化必须是 `[...]` 或同类型数组变量", v->pos);
    }

    /// a = [..]（同长度）或 a = b（逐元素值拷贝）。
    void assign_array(const std::string& dst, const std::string& dst_ty, const ExprPtr& value,
                      const Position& pos) {
        std::string elem = array_elem_scalar(dst_ty, pos);
        int len = lookup_array_len(dst, pos);
        int dst_off = lookup_slot(dst, pos);
        if (value->kind == Expr::Kind::Array) {
            if ((int)value->args.size() != len) {
                throw TenetError::at_pos("数组赋值长度不匹配：需要 " + std::to_string(len) +
                                             "，实际 " + std::to_string(value->args.size()),
                                         value->pos);
            }
            for (size_t i = 0; i < value->args.size(); ++i) {
                std::string vt = gen_expr(value->args[i]);
                if (vt != elem) {
                    throw TenetError::at_pos("数组元素 " + std::to_string(i) +
                                                 " 类型不匹配：需要 " + elem + "，实际 " + vt,
                                             value->args[i]->pos);
                }
                std::string reg = is_float(elem) ? "d9" : "x9";
                pop_reg(reg);
                store_slot(reg, dst_off + 8 * (int)i);
            }
            return;
        }
        if (value->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(value->name, value->pos);
            if (src_ty != dst_ty) {
                throw TenetError::at_pos(
                    "数组赋值类型不匹配：需要 " + dst_ty + "，右侧是 " + src_ty, value->pos);
            }
            int src_len = lookup_array_len(value->name, value->pos);
            if (src_len != len) {
                throw TenetError::at_pos("数组赋值长度不匹配：需要 " + std::to_string(len) +
                                             "，实际 " + std::to_string(src_len),
                                         value->pos);
            }
            int src_off = lookup_slot(value->name, value->pos);
            copy_array_elems(dst_off, src_off, len, elem);
            return;
        }
        throw TenetError::at_pos("数组赋值必须是同类型数组变量或同长度字面量", value->pos);
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
                int off = lookup_slot(e->name, e->pos);
                std::string t = var_type(e->name, e->pos);
                if (is_array(t)) {
                    throw TenetError::at_pos(
                        "数组变量 `" + e->name + "` 不能直接取值；请用下标或整体拷贝", e->pos);
                }
                if (is_struct(t)) {
                    throw TenetError::at_pos(
                        "struct 变量 `" + e->name + "` 不能直接取值；请用字段访问或整体拷贝",
                        e->pos);
                }
                if (is_float(t)) {
                    load_slot("d9", off);
                    push_reg("d9");
                } else {
                    load_slot("x9", off);
                    push_reg("x9");
                }
                return t;
            }
            case Expr::Kind::Index:
                return gen_index_read(e);
            case Expr::Kind::Array:
                throw TenetError::at_pos("数组字面量只能用于 let 初始化或整体赋值", e->pos);
            case Expr::Kind::Field: {
                const ExprPtr& base = e->lhs;
                if (!base || base->kind != Expr::Kind::Var) {
                    throw TenetError::at_pos(
                        "v1 只支持对 struct 变量取字段（不支持嵌套字段链）",
                        base ? base->pos : e->pos);
                }
                std::string ft = field_access_type(base->name, e->name, e->pos, false);
                int off = field_slot(base->name, e->name, e->pos);
                if (is_float(ft)) {
                    load_slot("d9", off);
                    push_reg("d9");
                } else {
                    load_slot("x9", off);
                    push_reg("x9");
                }
                return ft;
            }
            case Expr::Kind::StructLit:
                throw TenetError::at_pos("struct 字面量只能用于 let 初始化或整体赋值", e->pos);
            case Expr::Kind::Assign: {
                const ExprPtr& target = e->lhs;
                if (!target) {
                    throw TenetError::at_pos("赋值左侧必须是变量、字段或数组元素", e->pos);
                }
                if (target->kind == Expr::Kind::Var) {
                    int off = lookup_slot(target->name, target->pos);
                    std::string t = var_type(target->name, target->pos);
                    if (is_array(t)) {
                        assign_array(target->name, t, e->value, e->pos);
                        return "void";  // 数组赋值不产生可用的标量结果
                    }
                    if (is_struct(t)) {
                        assign_struct(target->name, t, e->value, e->pos);
                        return "void";  // struct 赋值不产生可用的标量结果
                    }
                    std::string vt = gen_expr(e->value);
                    if (vt != t) {
                        throw TenetError::at_pos("赋值类型不匹配：`" + target->name + "` 是 " + t +
                                                     "，右侧是 " + vt,
                                                 e->pos);
                    }
                    pop_reg(is_float(t) ? "d9" : "x9");
                    store_slot(is_float(t) ? "d9" : "x9", off);
                    push_reg(is_float(t) ? "d9" : "x9");
                    return t;
                }
                if (target->kind == Expr::Kind::Index) {
                    return gen_index_write(e, target);
                }
                if (target->kind == Expr::Kind::Field) {
                    const ExprPtr& base = target->lhs;
                    if (!base || base->kind != Expr::Kind::Var) {
                        throw TenetError::at_pos(
                            "v1 只支持对 struct 变量写字段",
                            base ? base->pos : target->pos);
                    }
                    std::string ft = field_access_type(base->name, target->name, target->pos, true);
                    std::string vt = gen_expr(e->value);
                    if (vt != ft) {
                        throw TenetError::at_pos("字段 `" + target->name + "` 类型不匹配：需要 " +
                                                     ft + "，实际 " + vt,
                                                 e->value->pos);
                    }
                    int off = field_slot(base->name, target->name, target->pos);
                    pop_reg(is_float(ft) ? "d9" : "x9");
                    store_slot(is_float(ft) ? "d9" : "x9", off);
                    push_reg(is_float(ft) ? "d9" : "x9");
                    return ft;
                }
                throw TenetError::at_pos("赋值左侧必须是变量、字段或数组元素", target->pos);
            }
            case Expr::Kind::Unary: {
                std::string t = gen_expr(e->value);
                if (e->op == OP_NEG) {
                    if (t == T_BOOL) {
                        throw TenetError::at_pos("运算符 `-` 不能作用于 bool", e->value->pos);
                    }
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
                if (t != T_BOOL) {
                    throw TenetError::at_pos("运算符 `!` 只能作用于 bool，实际为 " + t, e->value->pos);
                }
                pop_reg("x10");
                emit("cmp x10, #0");
                emit("cset x9, eq");
                push_reg("x9");
                return T_BOOL;
            }
            case Expr::Kind::Binary:
                return gen_binary(e);
            case Expr::Kind::Call:
                return gen_call(e->name, e->args, e->pos);
        }
        throw TenetError("未知的表达式类型");
    }

    void emit_int_const(int64_t v) { emit_mov_const("x9", v); }

    std::string gen_binary(const ExprPtr& e) {
        const std::string& op = e->op;
        // 逻辑运算先处理：操作数必须 bool
        if (op == OP_AND || op == OP_OR) return gen_logic(op, e);

        bool is_compare = op == OP_EQ || op == OP_NEQ || op == OP_LT || op == OP_LTE ||
                          op == OP_GT || op == OP_GTE;
        auto lt_opt = infer_type(e->lhs);
        auto rt_opt = infer_type(e->rhs);
        if (!lt_opt.has_value() || !rt_opt.has_value()) {
            throw TenetError::at_pos("无法推断操作数的类型（void 调用不能参与运算）", e->pos);
        }
        std::string lt = *lt_opt;
        std::string rt = *rt_opt;

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
            throw TenetError::at_pos("运算符 `" + op + "` 不能作用于 string 和 string", e->pos);
        }

        // 字符串与非字符串混合 → 类型错误（不得静默按数值处理）
        if ((lt == T_STR) != (rt == T_STR)) {
            throw TenetError::at_pos("运算符 `" + op + "` 不能作用于 " + lt + " 和 " + rt, e->pos);
        }
        // bool 不能参与数值与比较运算
        if (lt == T_BOOL || rt == T_BOOL) {
            throw TenetError::at_pos("运算符 `" + op + "` 不能作用于 " + lt + " 和 " + rt, e->pos);
        }

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
        auto lt = infer_type(e->lhs);
        auto rt = infer_type(e->rhs);
        if (lt.has_value() && *lt != T_BOOL) {
            throw TenetError::at_pos("运算符 `" + op + "` 只能作用于 bool，实际为 " + *lt, e->lhs->pos);
        }
        if (rt.has_value() && *rt != T_BOOL) {
            throw TenetError::at_pos("运算符 `" + op + "` 只能作用于 bool，实际为 " + *rt, e->rhs->pos);
        }
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

    /// len(a)：v1 的数组长度是编译期常量，直接压入 int 常量。
    std::string gen_len(const std::vector<ExprPtr>& args, const Position& pos) {
        if (args.size() != 1) {
            throw TenetError::at_pos("`len` 需要且只需要一个数组参数", pos);
        }
        const ExprPtr& a = args[0];
        if (!a || a->kind != Expr::Kind::Var) {
            throw TenetError::at_pos("`len` 参数必须是数组变量", a ? a->pos : pos);
        }
        std::string t = scoped_var_type(a->name, a->pos);
        if (!is_array(t)) {
            throw TenetError::at_pos("`" + a->name + "` 不是数组，不能取 len", a->pos);
        }
        int len = lookup_array_len(a->name, a->pos);
        emit_int_const(len);
        push_reg("x9");
        return T_INT;
    }

    std::string gen_call(const std::string& callee, const std::vector<ExprPtr>& args,
                         const Position& pos) {
        if (callee == "print") return gen_print(args, pos);
        if (callee == "len") return gen_len(args, pos);
        auto it = functions_.find(callee);
        if (it == functions_.end()) {
            throw TenetError::at_pos("未定义的函数 `" + callee + "`", pos);
        }
        const FnSig& sig = it->second;
        if (sig.params.size() != args.size()) {
            throw TenetError::at_pos("函数 `" + callee + "` 需要 " + std::to_string(sig.params.size()) +
                                         " 个参数，实际传入 " + std::to_string(args.size()) + " 个",
                                     pos);
        }
        if (args.size() > 8) throw TenetError::at_pos("暂不支持超过 8 个参数", pos);
        // 参数类型核对（print 除外）：期望类型 vs 实际类型
        for (size_t i = 0; i < args.size(); ++i) {
            std::string at = infer_type(args[i]).value_or("?");
            if (at != sig.params[i]) {
                throw TenetError::at_pos("函数 `" + callee + "` 参数 " + std::to_string(i) +
                                             " 类型不匹配：期望 " + sig.params[i] + "，实际 " + at,
                                         args[i]->pos);
            }
        }
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
    std::string gen_print(const std::vector<ExprPtr>& args, const Position& pos) {
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
            else throw TenetError::at_pos("print 不支持该类型的值", pos);
        }
        fmt += "\n";
        std::string fmt_name = "L.fmt." + std::to_string(str_c_++);
        data_string(fmt, fmt_name);

        int n = (int)args.size();
        if (n > 7) throw TenetError::at_pos("print 暂不支持超过 7 个参数", pos);
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
            case Expr::Kind::Var: return var_type(e->name, e->pos);
            case Expr::Kind::Index: {
                auto bt = infer_type(e->lhs);
                if (!bt.has_value()) {
                    throw TenetError::at_pos("无法推断数组类型", e->lhs->pos);
                }
                auto elem = array_elem(*bt);
                if (!elem.has_value()) {
                    throw TenetError::at_pos("`" + *bt + "` 不是数组", e->lhs->pos);
                }
                auto it = infer_type(e->rhs);
                if (it.has_value() && *it != T_INT) {
                    throw TenetError::at_pos("数组下标必须是 int，实际为 " + *it, e->rhs->pos);
                }
                return *elem;
            }
            case Expr::Kind::Array: {
                if (e->args.empty()) {
                    throw TenetError::at_pos("v1 不支持空数组字面量", e->pos);
                }
                auto first = infer_type(e->args[0]);
                if (!first.has_value()) {
                    throw TenetError::at_pos("无法推断数组元素类型", e->pos);
                }
                if (*first != T_INT && *first != T_FLOAT && *first != T_BOOL) {
                    throw TenetError::at_pos(
                        "v1 数组元素只支持 int/float/bool，实际 `" + *first + "`", e->pos);
                }
                for (size_t i = 1; i < e->args.size(); ++i) {
                    auto t = infer_type(e->args[i]);
                    if (!t.has_value() || *t != *first) {
                        throw TenetError::at_pos(
                            "数组元素类型不一致：第一个是 " + *first + "，后面是 " +
                                t.value_or("?"),
                            e->args[i]->pos);
                    }
                }
                return "array<" + *first + ">";
            }
            case Expr::Kind::Field: {
                const ExprPtr& base = e->lhs;
                if (!base || base->kind != Expr::Kind::Var) {
                    throw TenetError::at_pos(
                        "v1 只支持对 struct 变量取字段（不支持嵌套字段链）",
                        base ? base->pos : e->pos);
                }
                return field_access_type(base->name, e->name, e->pos, false);
            }
            case Expr::Kind::StructLit: {
                if (!is_struct(e->name)) {
                    throw TenetError::at_pos("未定义的 struct `" + e->name + "`", e->pos);
                }
                return e->name;
            }
            case Expr::Kind::Assign: {
                const ExprPtr& target = e->lhs;
                if (!target) {
                    throw TenetError::at_pos("赋值左侧必须是变量、字段或数组元素", e->pos);
                }
                if (target->kind == Expr::Kind::Var) {
                    return var_type(target->name, target->pos);
                }
                if (target->kind == Expr::Kind::Index) {
                    auto bt = infer_type(target->lhs);
                    if (!bt.has_value()) {
                        throw TenetError::at_pos("无法推断数组类型", target->lhs->pos);
                    }
                    auto elem = array_elem(*bt);
                    if (!elem.has_value()) {
                        throw TenetError::at_pos("`" + *bt + "` 不是数组", target->lhs->pos);
                    }
                    return *elem;
                }
                if (target->kind == Expr::Kind::Field) {
                    const ExprPtr& base = target->lhs;
                    if (!base || base->kind != Expr::Kind::Var) {
                        throw TenetError::at_pos(
                            "v1 只支持对 struct 变量写字段",
                            base ? base->pos : target->pos);
                    }
                    return field_access_type(base->name, target->name, target->pos, true);
                }
                throw TenetError::at_pos("赋值左侧必须是变量、字段或数组元素", target->pos);
            }
            case Expr::Kind::Unary:
                if (e->op == OP_NOT) {
                    auto t = infer_type(e->value);
                    if (t.has_value() && *t != T_BOOL) {
                        throw TenetError::at_pos("运算符 `!` 只能作用于 bool，实际为 " + *t, e->value->pos);
                    }
                    return T_BOOL;
                }
                {
                    auto t = infer_type(e->value);
                    if (t.has_value() && *t == T_BOOL) {
                        throw TenetError::at_pos("运算符 `-` 不能作用于 bool", e->value->pos);
                    }
                    return t;
                }
            case Expr::Kind::Binary: {
                auto lt = infer_type(e->lhs);
                auto rt = infer_type(e->rhs);
                const std::string& op = e->op;
                if (op == OP_AND || op == OP_OR) {
                    if (lt.has_value() && *lt != T_BOOL) {
                        throw TenetError::at_pos("运算符 `" + op + "` 只能作用于 bool，实际为 " + *lt,
                                                 e->lhs->pos);
                    }
                    if (rt.has_value() && *rt != T_BOOL) {
                        throw TenetError::at_pos("运算符 `" + op + "` 只能作用于 bool，实际为 " + *rt,
                                                 e->rhs->pos);
                    }
                    return T_BOOL;
                }
                // 字符串与任何非字符串混合 → 编译错误
                if ((lt == T_STR) != (rt == T_STR)) {
                    if (lt.has_value() && rt.has_value()) {
                        throw TenetError::at_pos("运算符 `" + op + "` 不能作用于 " + *lt + " 和 " + *rt,
                                                 e->pos);
                    }
                }
                // bool 不能参与数值与比较运算
                if ((lt.has_value() && *lt == T_BOOL) || (rt.has_value() && *rt == T_BOOL)) {
                    throw TenetError::at_pos(
                        "运算符 `" + op + "` 不能作用于 " + lt.value_or("?") + " 和 " + rt.value_or("?"),
                        e->pos);
                }
                if (op == OP_EQ || op == OP_NEQ || op == OP_LT || op == OP_LTE || op == OP_GT || op == OP_GTE) {
                    if (!lt.has_value() || !rt.has_value()) return std::nullopt;
                    return T_BOOL;
                }
                if (op == OP_MOD) {
                    if (lt == T_INT && rt == T_INT) return T_INT;
                    if (lt.has_value() && rt.has_value()) {
                        throw TenetError::at_pos("运算符 `%` 只能作用于 int", e->pos);
                    }
                    return std::nullopt;
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
                if (e->name == "print") return std::nullopt;
                if (e->name == "len") {
                    if (e->args.size() != 1) {
                        throw TenetError::at_pos("`len` 需要且只需要一个数组参数", e->pos);
                    }
                    auto t = infer_type(e->args[0]);
                    if (!t.has_value()) {
                        throw TenetError::at_pos("无法推断 `len` 参数类型", e->args[0]->pos);
                    }
                    if (!is_array(*t)) {
                        throw TenetError::at_pos("`len` 参数必须是数组，实际是 " + *t,
                                                 e->args[0]->pos);
                    }
                    return T_INT;
                }
                auto it = functions_.find(e->name);
                if (it == functions_.end()) {
                    throw TenetError::at_pos("未定义的函数 `" + e->name + "`", e->pos);
                }
                if (!it->second.ret.has_value()) return std::nullopt;
                return it->second.ret;
            }
        }
        return std::nullopt;
    }
};

}  // namespace tenet
