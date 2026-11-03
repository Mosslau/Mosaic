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
// - struct ABI（S3a）：struct 参数传扁平槽首地址（x 寄存器），被调函数入口逐字段拷贝；
//   struct 返回值用隐藏 sret 指针（x0），函数返回 void，字段写回调用方缓冲区
// - array ABI（S3b）：array<T, N> 参数同样传元素 0 地址（入口逐元素拷贝到本地 [N x T] 槽）；
//   返回值复用隐藏 sret 指针，按 8 字节槽由调用方缓冲区打包/解包
// - 动态数组（S3c）：array<T> 是堆缓冲 + data/len/cap 三个栈槽，
//   push 扩容、len 运行时读取、下标运行时越界检查、赋值/初始化深拷贝、作用域/return drop
// - 动态数组 ABI（S3c-2/S3c-3a）：参数传 3 槽描述符指针，被调函数入口深拷贝（参数值语义）；
//   返回值走隐藏 sret 指针（x0）指向的 3 槽描述符，return 时转移所有权（变量/字面量/调用）；
//   调用方 let/赋值从调用结果接管堆缓冲。动态实参支持变量、字面量、返回动态数组的调用：
//   字面量/调用结果先构造临时描述符，调用返回后只 free 临时堆缓冲（不 free 栈描述符）
// - 动态 struct 数组（S3c-3b-2）：array<S> 的堆元素按扁平字段槽存放，stride = slots*8；
//   push/字段读写/整体元素赋值/深拷贝与参数、返回值 ABI 同动态数组（drop 只 free 堆缓冲）
// - 嵌套固定数组（S3c-3c）：array<array<T,N>,M> 扁平 [M*N x i64]，
//   a[i][j] 做外层/内层边界检查，不支持 len(a[i])
// - 固定数组 ABI（S3c-3d）：多槽固定数组（array<S,N> / array<array<T,N>,M>）参数传
//   元素 0 地址，被调函数入口按总槽数（N*slots / M*N）拷贝到本地扁平槽；
//   返回值复用隐藏 sret 指针（函数返回 void），return 打包到 sret，调用方逐槽接管
// - 动态嵌套数组（S3c-3e）：array<array<T>>（外层/内层均动态、内层标量）；外层堆元素
//   是内层 descriptor（stride=24），a[i][j] 双边界检查、push 深拷贝、参数入口逐内层
//   深拷贝、sret 转移、先内层后外层 drop、print 输出 [[1, 2], [3]]
// - struct 布局：深度优先按声明顺序展开为 8 字节槽；标量 1 槽，固定数组字段占
//   N*elem_slots 槽（S3d），struct 总槽数递归求和（float 位模式 / bool 0-1）
// - 字符串：.data 常量 + adrp/add 取址；拼接/比较调用 libc（strlen/malloc/memcpy/strcmp）
// - 控制流：if/while/break/短路全部翻译为标签 + 条件分支
#pragma once

#include <algorithm>
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

    /// S3c 动态数组描述符：三个 8 字节栈槽（data 指针 / len / cap）。
    struct DynArrayInfo {
        int data = 0;
        int len = 0;
        int cap = 0;
        /// S3c-3e：array<array<T>> 的外层描述符。堆上每个元素是内层 descriptor
        /// （data/len/cap 三个 i64），drop 时必须先逐内层 free(data) 再 free 外层。
        bool nested = false;
    };

    std::string text_;
    std::string data_;
    int str_c_ = 0, flt_c_ = 0, label_c_ = 0;
    std::unordered_map<std::string, FnSig> functions_;
    /// 顶层 struct 名 → 字段 (名, 类型)；字段类型可为标量或另一个 struct。
    std::unordered_map<std::string, std::vector<std::pair<std::string, std::string>>> structs_;

    // 当前函数状态
    std::string fn_;
    std::optional<std::string> current_ret_;   // 当前函数声明返回类型（None = void）
    std::vector<std::unordered_map<std::string, int>> flat_maps_;  // 所有块作用域的槽位表
    std::vector<std::unordered_map<std::string, std::string>> type_maps_;  // 与 flat_maps_ 同索引
    std::vector<std::unordered_map<std::string, int>> array_len_maps_;  // 与 flat_maps_ 同索引：数组长度
    /// 与 flat_maps_ 同索引：动态数组 array<T> 的 data/len/cap 槽位。
    std::vector<std::unordered_map<std::string, DynArrayInfo>> dyn_maps_;
    std::vector<int> scope_stack_;                                 // 当前作用域链（索引）
    std::vector<int> scope_queue_;                                 // 预计算的块索引（按遍历序）
    size_t scope_cursor_ = 0;                                      // 消费 scope_queue_
    int frame_ = 0;
    /// 当前函数里由调用点按需分配的临时缓冲槽（struct/array 实参与字面量、sret）。
    /// 槽位接在普通局部槽之后，函数体发射完才知道帧大小，故 prologue 帧调整用占位符回填。
    int scratch_slots_ = 0;
    int sret_slot_ = 0;              // struct/array 返回值的隐藏 sret 指针槽（无则不用）
    bool current_ret_struct_ = false;
    int pushes_ = 0;
    bool terminated_ = false;
    std::vector<std::string> break_stack_;
    /// 与 break_stack_ 并行：进入循环体时的作用域深度（break 时 drop 到该深度）。
    std::vector<size_t> break_depth_stack_;

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

    /// `array<...>` 尖括号内的原文（`array<int>` / `array<int,3>` → `int` / `int,3`）。
    static std::optional<std::string> array_inner(const std::string& ty) {
        const std::string prefix = "array<";
        if (ty.size() <= prefix.size() + 1) return std::nullopt;
        if (ty.compare(0, prefix.size(), prefix) != 0) return std::nullopt;
        if (ty.back() != '>') return std::nullopt;
        return ty.substr(prefix.size(), ty.size() - prefix.size() - 1);
    }

    /// 在 array 内层找顶层逗号（跳过嵌套 `<...>`，如 `array<array<int,3>,2>`）。
    static size_t array_top_comma(const std::string& inner) {
        int depth = 0;
        for (size_t i = 0; i < inner.size(); ++i) {
            char c = inner[i];
            if (c == '<') {
                ++depth;
            } else if (c == '>') {
                if (depth > 0) --depth;
            } else if (c == ',' && depth == 0) {
                return i;
            }
        }
        return std::string::npos;
    }

    /// `array<T>` / `array<T, N>` → 元素类型 `T`；不是数组返回 nullopt。
    static std::optional<std::string> array_elem(const std::string& ty) {
        auto inner = array_inner(ty);
        if (!inner.has_value()) return std::nullopt;
        size_t comma = array_top_comma(*inner);
        std::string elem =
            comma == std::string::npos ? *inner : inner->substr(0, comma);
        if (elem.empty()) return std::nullopt;
        return elem;
    }

    /// `array<T, N>` → N；`array<T>`（S3c 动态数组）或非数组返回 nullopt。
    static std::optional<int> array_decl_len(const std::string& ty) {
        auto inner = array_inner(ty);
        if (!inner.has_value()) return std::nullopt;
        size_t comma = array_top_comma(*inner);
        if (comma == std::string::npos || comma + 1 >= inner->size()) return std::nullopt;
        std::string digits = inner->substr(comma + 1);
        if (digits.empty() ||
            digits.find_first_not_of("0123456789") != std::string::npos) {
            return std::nullopt;
        }
        int n = std::stoi(digits);
        return n > 0 ? std::optional<int>(n) : std::nullopt;
    }

    bool is_array(const std::string& t) const { return array_elem(t).has_value(); }

    /// S3c：`array<T>`（不带长度）是局部动态数组；`array<T, N>` 是定长栈数组。
    bool is_dynamic_array(const std::string& t) const {
        return is_array(t) && !array_decl_len(t).has_value();
    }

    /// S3c-3e v1 动态嵌套数组：`array<array<T>>`——外层、内层都是动态数组，
    /// 内层元素限 int/float/bool。固定内层、struct 内层与更深嵌套都不算。
    bool is_dynamic_nested_array(const std::string& t) const {
        if (!is_dynamic_array(t)) return false;
        auto elem = array_elem(t);
        if (!elem.has_value() || array_decl_len(*elem).has_value()) return false;
        auto scalar = array_elem(*elem);
        return scalar.has_value() &&
               (*scalar == T_INT || *scalar == T_FLOAT || *scalar == T_BOOL);
    }

    /// 校验动态嵌套数组形状并返回内层标量类型。只接受 `array<array<T>>`
    /// （T = int/float/bool）；其他嵌套形状给出明确的不支持错误。
    std::string dynamic_nested_scalar_elem(const std::string& ty,
                                           const Position& pos) const {
        if (!is_array(ty)) {
            throw TenetError::at_pos("`" + ty + "` 不是数组", pos);
        }
        if (!is_dynamic_array(ty)) {
            throw TenetError::at_pos(
                "动态嵌套数组外层必须是动态数组 `array<array<T>>`，实际 `" + ty + "`", pos);
        }
        auto elem = array_elem(ty);
        if (!elem.has_value() || !is_array(*elem)) {
            throw TenetError::at_pos(
                "`" + ty + "` 不是嵌套数组（需要 `array<array<T>>`）", pos);
        }
        if (array_decl_len(*elem).has_value()) {
            throw TenetError::at_pos(
                "动态嵌套数组的内层必须是动态数组 `array<T>`，实际 `" + *elem +
                    "`（不支持固定长度内层）",
                pos);
        }
        auto scalar = array_elem(*elem);
        if (!scalar.has_value()) {
            throw TenetError::at_pos("嵌套数组内层不是数组：`" + *elem + "`", pos);
        }
        if (is_struct(*scalar)) {
            throw TenetError::at_pos(
                "嵌套数组内层元素只支持 int/float/bool，不支持 array<struct>", pos);
        }
        if (is_array(*scalar)) {
            throw TenetError::at_pos("只支持一层嵌套数组 array<array<T>>，不支持更深嵌套",
                                     pos);
        }
        if (*scalar != T_INT && *scalar != T_FLOAT && *scalar != T_BOOL) {
            throw TenetError::at_pos(
                "嵌套数组内层元素只支持 int/float/bool，实际 `" + *scalar + "`", pos);
        }
        return *scalar;
    }

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

    /// struct 的扁平槽位布局条目（S3d：固定数组字段 v1）。
    ///
    /// - `path`：字段点路径（嵌套 struct 递归展开成 `inner.x`）。
    /// - `ty`：标量字段类型，或固定数组字段的完整数组类型。
    /// - `offset`：相对 struct 起始的 8 字节槽偏移（不是字段序号）。
    /// - `slots`：该字段占用的槽数；标量 1，固定数组 `N * elem_slots`。
    ///
    /// 布局始终按声明顺序深度优先递增 offset；局部 struct 变量的字段槽从
    /// base 向低地址排列（slot j 在 base - 8*j），数组元素/packed 缓冲则从
    /// base 向高地址排列（slot j 在 base + 8*j），由各使用点决定方向。
    struct LayoutEntry {
        std::string path;
        std::string ty;
        int offset = 0;
        int slots = 1;
    };

    /// 一个字段类型占用的 8 字节槽数：标量 1；固定数组 N * elem_slots；
    /// struct 递归求和。动态数组字段在 collect_structs 阶段已被拒绝。
    int field_slot_width(const std::string& fty) const {
        if (auto n = array_decl_len(fty); n.has_value()) {
            return *n * array_elem_slots(fty, Position());
        }
        if (is_struct(fty)) return struct_total_slots(fty);
        return 1;
    }

    /// struct 的总槽数（固定数组字段按 N * elem_slots 计入）。
    int struct_total_slots(const std::string& ty) const {
        auto it = structs_.find(ty);
        if (it == structs_.end()) return 0;
        int total = 0;
        for (const auto& [fname, fty] : it->second) {
            (void)fname;
            total += field_slot_width(fty);
        }
        return total;
    }

    /// 把 struct 递归展开为扁平布局：标量一个 entry，固定数组字段一个 entry
    /// （占 slots 槽），嵌套 struct 递归。返回顺序即 ABI 槽位顺序。
    std::vector<LayoutEntry> layout_of(const std::string& ty) const {
        std::vector<LayoutEntry> out;
        int offset = 0;
        layout_into(ty, "", offset, out);
        return out;
    }

    void layout_into(const std::string& ty, const std::string& prefix, int& offset,
                     std::vector<LayoutEntry>& out) const {
        auto it = structs_.find(ty);
        if (it == structs_.end()) return;
        for (const auto& [fname, fty] : it->second) {
            std::string path = prefix.empty() ? fname : prefix + "." + fname;
            if (is_struct(fty)) {
                layout_into(fty, path, offset, out);
                continue;
            }
            int slots = field_slot_width(fty);
            out.push_back({path, fty, offset, slots});
            offset += slots;
        }
    }

    /// 在 struct 布局里按点分路径查条目（嵌套 struct 已递归展开）。
    std::optional<LayoutEntry> layout_entry(const std::string& ty,
                                            const std::string& path) const {
        for (const auto& entry : layout_of(ty)) {
            if (entry.path == path) return entry;
        }
        return std::nullopt;
    }

    /// 固定数组最内层元素若是 struct，返回该 struct 名（用于循环检测）。
    std::optional<std::string> array_inner_struct(const std::string& ty) const {
        std::string cur = ty;
        while (auto elem = array_elem(cur)) {
            cur = *elem;
        }
        if (is_struct(cur)) return cur;
        return std::nullopt;
    }

    /// S3c-3b-1：数组元素类型允许标量或 struct（struct 只用于固定长度数组）。
    /// S3c-3b-2：动态 `array<S>` 同样允许 struct 元素。
    /// S3c-3c：固定外层数组允许内层固定数组（嵌套数组，仅局部、内层 int/float）。
    /// S3c-3e：动态外层数组允许内层动态标量数组（`array<array<T>>`）。
    /// 标量路径仍由 array_elem_scalar 负责（保持既有错误文案）。
    std::string array_elem_checked(const std::string& ty, const Position& pos) const {
        auto elem = array_elem(ty);
        if (!elem.has_value()) {
            throw TenetError::at_pos("不是数组类型：" + ty, pos);
        }
        if (*elem == T_INT || *elem == T_FLOAT || *elem == T_BOOL) return *elem;
        if (is_struct(*elem)) return *elem;
        if (is_array(*elem)) {
            if (is_dynamic_array(ty)) {
                // S3c-3e：array<array<T>>。内层必须也是动态数组，元素限 int/float/bool；
                // 固定内层、struct 内层、更深嵌套与固定/动态混用都不支持。
                dynamic_nested_scalar_elem(ty, pos);
                return *elem;
            }
            // S3c-3c：array<array<T, N>, M>。外层必须是固定长度；内层必须是固定长度，
            // 且内层元素只支持 int/float（bool 明确拒绝，struct/更深嵌套也不支持）。
            auto inner_len = array_decl_len(*elem);
            if (!inner_len.has_value()) {
                throw TenetError::at_pos(
                    "嵌套数组内层必须是固定长度 `array<T, N>`，实际 `" + *elem + "`", pos);
            }
            auto inner_elem = array_elem(*elem);
            if (!inner_elem.has_value()) {
                throw TenetError::at_pos("嵌套数组内层不是数组：`" + *elem + "`", pos);
            }
            if (*inner_elem == T_BOOL) {
                throw TenetError::at_pos("嵌套数组内层暂不支持 bool（只支持 int/float）", pos);
            }
            if (*inner_elem != T_INT && *inner_elem != T_FLOAT) {
                throw TenetError::at_pos(
                    "嵌套数组内层只支持 int/float，实际 `" + *inner_elem + "`", pos);
            }
            return *elem;
        }
        throw TenetError::at_pos(
            "v1 数组元素只支持 int/float/bool 或 struct，实际 `" + *elem + "`", pos);
    }

    /// 数组一个元素占多少个 8 字节扁平槽：
    /// struct 为总槽数（含固定数组字段）；固定嵌套数组为内层长度 × 内层元素槽数；
    /// S3c-3e 动态嵌套数组的外层元素是内层 descriptor（3 个 i64 槽）；标量为 1。
    ///
    /// 这里按「槽位」直接递归，不重复套用局部数组的元素限制（struct 字段的固定
    /// 数组允许 bool/struct 叶子）；非法元素类型仍由 array_elem_checked 报错。
    int array_elem_slots(const std::string& ty, const Position& pos) const {
        auto elem = array_elem(ty);
        if (!elem.has_value()) {
            throw TenetError::at_pos("不是数组类型：" + ty, pos);
        }
        if (is_struct(*elem)) return struct_total_slots(*elem);
        if (is_array(*elem)) {
            if (is_dynamic_nested_array(ty)) return 3;
            auto inner_len = array_decl_len(*elem);
            if (!inner_len.has_value()) {
                // 非法嵌套形状：沿用既有校验文案（动态内层 / 固定/动态混用）。
                array_elem_checked(ty, pos);
                return 3;
            }
            return *inner_len * array_elem_slots(*elem, pos);
        }
        if (*elem != T_INT && *elem != T_FLOAT && *elem != T_BOOL) {
            // 保留 "v1 数组元素只支持 …" 等既有错误文案。
            array_elem_checked(ty, pos);
        }
        return 1;
    }

    /// S3c-3c 嵌套数组的布局信息：外层 M 个元素、每个内层 N 个标量，扁平 [M*N x i64]。
    struct NestedArrayInfo {
        std::string ty;         // 外层数组类型 array<array<T,N>,M>
        std::string inner_ty;   // 内层数组类型 array<T,N>
        std::string elem;       // 内层标量元素类型 int/float
        int outer_len = 0;      // M
        int inner_len = 0;      // N
        int slots = 0;          // 每个外层元素的槽数（= N）
    };

    /// 校验并拆解嵌套数组类型（仅局部）：外层/内层都必须固定长度，内层元素 int/float。
    NestedArrayInfo nested_array_info(const std::string& ty, const Position& pos) const {
        if (!is_array(ty)) {
            throw TenetError::at_pos("`" + ty + "` 不是数组", pos);
        }
        std::string elem = array_elem_checked(ty, pos);
        if (!is_array(elem)) {
            throw TenetError::at_pos(
                "`" + ty + "` 不是嵌套数组（需要 `array<array<T, N>, M>`）", pos);
        }
        NestedArrayInfo info;
        info.ty = ty;
        info.inner_ty = elem;
        info.outer_len = *array_decl_len(ty);
        info.inner_len = *array_decl_len(elem);
        info.elem = *array_elem(elem);
        info.slots = info.inner_len;
        return info;
    }

    /// 检测循环嵌套（A 含 B、B 含 A，或自引用）。
    void check_struct_cycle(const std::string& ty, std::vector<std::string>& stack,
                            const Position& pos) const {
        if (std::find(stack.begin(), stack.end(), ty) != stack.end()) {
            std::vector<std::string> cycle = stack;
            cycle.push_back(ty);
            std::string chain;
            for (size_t i = 0; i < cycle.size(); ++i) {
                if (i) chain += " -> ";
                chain += cycle[i];
            }
            // 旧 v1 测试对自引用断言过「只支持 int/float/bool」，这里在循环错误里保留该表述。
            throw TenetError::at_pos("struct 循环嵌套：" + chain +
                                         "（struct 字段只支持 int/float/bool 或其他非循环 struct）",
                                     pos);
        }
        if (!is_struct(ty)) return;
        stack.push_back(ty);
        for (const auto& [fname, fty] : structs_.at(ty)) {
            (void)fname;
            if (is_struct(fty)) {
                check_struct_cycle(fty, stack, pos);
            } else if (is_array(fty)) {
                // S3d：固定数组字段也要沿最内层 struct 元素检测循环。
                if (auto inner = array_inner_struct(fty)) {
                    check_struct_cycle(*inner, stack, pos);
                }
            }
        }
        stack.pop_back();
    }

    /// S3d：struct 字段的固定数组校验——每一层都必须是固定长度，最内层限标量
    /// 或 struct；动态 `array<T>` 字段明确拒绝。
    void validate_struct_array_field(const std::string& sname, const std::string& fname,
                                     const std::string& fty, const Position& pos) const {
        std::string cur = fty;
        while (is_array(cur)) {
            if (!array_decl_len(cur).has_value()) {
                // 旧测试同时断言「不支持 array」与「只支持 int/float/bool」，保留两者。
                throw TenetError::at_pos(
                    "struct 字段不支持 array 动态数组字段（`" + sname + "." + fname +
                        "`）；字段只支持 int/float/bool、其他 struct 或固定 array<T, N>"
                        "（不允许动态 array<T>）",
                    pos);
            }
            auto inner = array_elem(cur);
            if (!inner.has_value()) {
                throw TenetError::at_pos("struct `" + sname + "` 的字段 `" + fname +
                                             "` 数组元素缺失",
                                         pos);
            }
            cur = *inner;
        }
        if (cur == T_STR) {
            throw TenetError::at_pos("struct `" + sname + "` 的字段 `" + fname +
                                         "` 的数组元素不支持 string（只支持 int/float/bool/struct）",
                                     pos);
        }
        // 未定义的 struct 名交给第二遍类型检查报错。
    }

    /// 收集并校验顶层 struct 声明：字段可为标量、其他 struct 或固定数组
    /// （array<T,N> / array<struct,N> / 固定嵌套 array<array<T,N>,M>）；
    /// 禁止循环、string 与动态 array<T> 字段。
    void collect_structs(const Program& program) {
        // 第一遍：登记所有 struct 名与原始字段（允许前向引用）。
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
                if (seen.count(fname)) {
                    throw TenetError::at_pos("struct `" + name + "` 的字段 `" + fname + "` 重复",
                                             stmt->pos);
                }
                seen[fname] = 1;
                if (fty == T_STR) {
                    throw TenetError::at_pos(
                        "struct `" + name + "` 的字段 `" + fname +
                            "` 只支持 int/float/bool、其他 struct 或固定数组",
                        stmt->pos);
                }
                if (is_array(fty)) {
                    validate_struct_array_field(name, fname, fty, stmt->pos);
                }
            }
            structs_[name] = stmt->fields;
        }
        // 第二遍：字段类型必须已定义（标量或已声明的 struct），并检测循环嵌套。
        for (const auto& stmt : program.stmts) {
            if (stmt->kind != Stmt::Kind::StructDecl) continue;
            for (const auto& [fname, fty] : stmt->fields) {
                // 固定数组字段要走到最内层元素判断类型是否已定义。
                std::string leaf = fty;
                while (is_array(leaf)) {
                    auto inner = array_elem(leaf);
                    if (!inner.has_value()) break;
                    leaf = *inner;
                }
                if (leaf != T_INT && leaf != T_FLOAT && leaf != T_BOOL && !is_struct(leaf)) {
                    throw TenetError::at_pos("struct `" + stmt->name + "` 的字段 `" + fname +
                                                 "` 类型 `" + leaf + "` 未定义",
                                             stmt->pos);
                }
            }
            std::vector<std::string> stack;
            check_struct_cycle(stmt->name, stack, stmt->pos);
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
                if (is_array(pt)) {
                    // S3b：array<T, N> 参数走定长数组指针 ABI；
                    // S3c-2：array<T> 参数走 3 槽描述符指针 ABI；
                    // S3c-3b-2：动态 array<S> 参数同样走描述符指针（入口深拷贝）；
                    // S3c-3d：固定 array<S, N> 与固定嵌套数组参数也走指针 ABI
                    // （被调函数入口按总槽数拷贝，参数值语义）。
                    std::string elem = array_elem_checked(pt, stmt->pos);
                    if (is_array(elem) && !is_dynamic_nested_array(pt)) {
                        nested_array_info(pt, stmt->pos);
                    }
                    (void)pn;
                    continue;
                }
                if (!is_scalar_type(pt) && !is_struct(pt)) {
                    throw TenetError::at_pos("函数 `" + name + "` 的参数 `" + pn +
                                                 "` 类型未定义：`" + pt + "`",
                                             stmt->pos);
                }
            }
            bool ret_struct = stmt->ret.has_value() && is_struct(*stmt->ret);
            bool ret_array = stmt->ret.has_value() && is_array(*stmt->ret);
            if (stmt->ret.has_value()) {
                const std::string& rt = *stmt->ret;
                if (is_array(rt)) {
                    // S3b 定长数组 / S3c-2、S3c-3b-2 动态数组都允许作返回值。
                    // S3c-3d：固定 array<S, N> 与固定嵌套数组返回值也允许（走 sret）。
                    std::string elem = array_elem_checked(rt, stmt->pos);
                    if (is_array(elem) && !is_dynamic_nested_array(rt)) {
                        nested_array_info(rt, stmt->pos);
                    }
                    (void)elem;
                } else if (!is_scalar_type(rt) && !is_struct(rt)) {
                    throw TenetError::at_pos(
                        "函数 `" + name + "` 的返回类型未定义：`" + rt + "`", stmt->pos);
                }
            }
            // 自定义 Tenet ABI：struct/array 指针与隐藏 sret 指针都占一个参数位（x0-x7）。
            size_t arg_positions = stmt->params.size() + (ret_struct || ret_array ? 1 : 0);
            if (arg_positions > 8) {
                throw TenetError::at_pos(
                    "函数 `" + name +
                        "` 的参数位超过 8 个（sret 与 struct/array 指针也占参数位，x0-x7）",
                    stmt->pos);
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
                // S3c：`array<T>` 是局部动态数组；`array<T, N>` 是定长栈数组。
                // S3c-3b-1/2：元素可为标量或 struct（动态/固定都支持）。
                // S3c-3c：`array<array<T, N>, M>` 仅局部，内层固定且元素 int/float。
                std::string elem = array_elem_checked(t, stmt.pos);
                if (is_array(elem) && !is_dynamic_nested_array(t)) {
                    nested_array_info(t, stmt.pos);
                }
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

    /// 数组 let 的定长长度：字面量取元素个数，变量/调用取源数组长度。
    /// 显式写了 `array<T, N>` 时长度必须与来源一致。
    int plan_array_len(const Stmt& stmt, const std::string& ty) {
        const ExprPtr& v = stmt.value;
        if (!v) {
            throw TenetError::at_pos("`" + stmt.name + "` 的数组初始化缺失", stmt.pos);
        }
        auto decl_len = array_decl_len(ty);
        std::string elem = array_elem_checked(ty, stmt.pos);
        if (is_array(elem) && !is_dynamic_nested_array(ty)) {
            nested_array_info(ty, stmt.pos);
        }
        if (v->kind == Expr::Kind::Array) {
            if (v->args.empty()) {
                throw TenetError::at_pos("v1 不支持空数组字面量", v->pos);
            }
            int n = (int)v->args.size();
            if (decl_len.has_value() && *decl_len != n) {
                throw TenetError::at_pos("数组初始化长度不匹配：需要 " +
                                             std::to_string(*decl_len) + "，实际 " +
                                             std::to_string(n),
                                         v->pos);
            }
            return n;
        }
        if (v->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(v->name, v->pos);
            if (is_dynamic_array(src_ty)) {
                throw TenetError::at_pos(
                    "`" + stmt.name + "` 是定长数组 " + ty + "，不能用动态数组 `" + v->name +
                        "`（" + src_ty + "）初始化",
                    v->pos);
            }
            if (!is_array(src_ty) || array_elem(src_ty) != elem) {
                throw TenetError::at_pos(
                    "`" + stmt.name + "` 需要 " + ty + "，但 `" + v->name + "` 是 " + src_ty,
                    v->pos);
            }
            int src_len = lookup_array_len(v->name, v->pos);
            if (decl_len.has_value() && *decl_len != src_len) {
                throw TenetError::at_pos("数组初始化长度不匹配：需要 " +
                                             std::to_string(*decl_len) + "，实际 " +
                                             std::to_string(src_len),
                                         v->pos);
            }
            return src_len;
        }
        if (v->kind == Expr::Kind::Call) {
            auto rt = infer_type(v);
            if (!rt.has_value() || !is_array(*rt)) {
                throw TenetError::at_pos(
                    "`" + stmt.name + "` 需要 " + ty + "，但调用返回 " +
                        rt.value_or("void"),
                    v->pos);
            }
            if (array_elem(*rt) != elem) {
                throw TenetError::at_pos(
                    "`" + stmt.name + "` 需要 " + ty + "，调用返回 " + *rt, v->pos);
            }
            auto ret_len = array_decl_len(*rt);
            if (!ret_len.has_value()) {
                throw TenetError::at_pos("返回数组必须带长度 array<T, N>", v->pos);
            }
            if (decl_len.has_value() && *decl_len != *ret_len) {
                throw TenetError::at_pos("数组初始化长度不匹配：需要 " +
                                             std::to_string(*decl_len) + "，调用返回 " +
                                             std::to_string(*ret_len),
                                         v->pos);
            }
            return *ret_len;
        }
        throw TenetError::at_pos(
            "`" + stmt.name + "` 的数组初始化必须是字面量、同类型数组变量或返回数组的调用",
            v->pos);
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
                        if (is_dynamic_array(t)) {
                            // S3c：动态数组占 3 个连续槽（data/len/cap），运行时 malloc。
                            // S3c-3b-2：元素可为 struct（stride = 扁平字段数*8）。
                            // S3c-3e：array<array<T>> 的堆元素是内层 descriptor。
                            array_elem_checked(t, s->pos);
                            int data = -(8 * (next_slot + 1));
                            flat_maps_[scope_stack_.back()][s->name] = data;
                            DynArrayInfo di{data, data - 8, data - 16};
                            di.nested = is_dynamic_nested_array(t);
                            dyn_maps_[scope_stack_.back()][s->name] = di;
                            next_slot += 3;
                            break;
                        }
                        int len = plan_array_len(*s, t);
                        // S3c-3b-1：每个 struct 元素按扁平字段占 slots 个连续槽，
                        // 元素 0 在最低地址；元素 stride = slots*8。
                        // S3c-3c：嵌套数组每个外层元素占 N 个标量槽，扁平 [M*N x i64]。
                        int slots = array_elem_slots(t, s->pos);
                        int total = len * slots;
                        int base_offset = -(8 * (next_slot + total));
                        flat_maps_[scope_stack_.back()][s->name] = base_offset;
                        array_len_maps_[scope_stack_.back()][s->name] = len;
                        next_slot += total;
                        break;
                    }
                    int first_offset = -(8 * (next_slot + 1));
                    flat_maps_[scope_stack_.back()][s->name] = first_offset;
                    if (is_struct(t)) {
                        // S3d：字段槽按 layout_of 的槽偏移分配，固定数组字段占
                        // N*elem_slots 个连续槽（局部布局向低地址展开）。
                        for (const auto& entry : layout_of(t)) {
                            flat_maps_[scope_stack_.back()][s->name + "." + entry.path] =
                                first_offset - 8 * entry.offset;
                        }
                        next_slot += struct_total_slots(t);
                    } else {
                        ++next_slot;
                    }
                    break;
                }
                case Stmt::Kind::If: {
                    flat_maps_.push_back({});
                    type_maps_.push_back({});
                    array_len_maps_.push_back({});
                    dyn_maps_.push_back({});
                    scope_queue_.push_back((int)flat_maps_.size() - 1);
                    scope_stack_.push_back((int)flat_maps_.size() - 1);
                    plan_stmts(s->then_branch, next_slot);
                    scope_stack_.pop_back();
                    if (!s->else_branch.empty()) {
                        flat_maps_.push_back({});
                        type_maps_.push_back({});
                        array_len_maps_.push_back({});
                        dyn_maps_.push_back({});
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
                    dyn_maps_.push_back({});
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
    static std::string frame_adjust_asm(int frame, bool allocate) {
        if (frame <= 0) return "";
        std::string op = allocate ? "sub" : "add";
        if (frame <= 4095) {
            return "\t" + op + " sp, sp, #" + std::to_string(frame) + "\n";
        }
        return mov_const_asm("x16", frame) + "\t" + op + " sp, sp, x16\n";
    }

    void emit_frame_adjust(int frame, bool allocate) {
        text_ += frame_adjust_asm(frame, allocate);
    }

    /// 函数体发射时才能确定帧大小（scratch 槽按调用点增长），prologue 先用占位符。
    void patch_frame_alloc(const std::string& marker, int frame) {
        size_t pos = text_.rfind(marker);
        if (pos == std::string::npos) return;
        text_.replace(pos, marker.size(), frame_adjust_asm(frame, true));
    }

    void zero_dynamic_slots() {
        for (const auto& m : dyn_maps_) {
            for (const auto& [name, di] : m) {
                (void)name;
                emit("str xzr, [x29, #" + std::to_string(di.data) + "]");
                emit("str xzr, [x29, #" + std::to_string(di.len) + "]");
                emit("str xzr, [x29, #" + std::to_string(di.cap) + "]");
            }
        }
    }

    void emit_fn(const StmtPtr& stmt) {
        const auto& name = stmt->name;
        if (stmt->ret.has_value() && !stmt->body.empty() &&
            stmt->body.back()->kind != Stmt::Kind::Return) {
            throw TenetError::at_pos("函数 `" + name + "` 声明了返回类型，但函数末尾没有 return",
                                     stmt->pos);
        }
        // 规划：sret 隐藏槽 + 参数槽 + 局部槽（作用域索引按遍历序进队列）
        flat_maps_.clear();
        type_maps_.clear();
        array_len_maps_.clear();
        dyn_maps_.clear();
        scope_queue_.clear();
        scope_cursor_ = 0;
        scope_stack_.clear();
        flat_maps_.push_back({});
        type_maps_.push_back({});
        array_len_maps_.push_back({});
        dyn_maps_.push_back({});
        scope_queue_.push_back(0);
        scope_stack_.push_back(0);
        bool ret_struct = stmt->ret.has_value() && is_struct(*stmt->ret);
        bool ret_array = stmt->ret.has_value() && is_array(*stmt->ret);
        bool ret_composite = ret_struct || ret_array;
        int next_slot = 0;
        sret_slot_ = 0;
        if (ret_composite) {
            sret_slot_ = -(8 * (next_slot + 1));
            ++next_slot;
        }
        for (const auto& [pn, pt] : stmt->params) {
            type_maps_[0][pn] = pt;
            if (is_struct(pt)) {
                // struct 参数在入口从指针逐字段拷贝到本地扁平槽，函数内修改不影响调用方。
                // S3d：固定数组字段占 N*elem_slots 个槽，按布局偏移分配。
                int first_offset = -(8 * (next_slot + 1));
                flat_maps_[0][pn] = first_offset;
                for (const auto& entry : layout_of(pt)) {
                    flat_maps_[0][pn + "." + entry.path] = first_offset - 8 * entry.offset;
                }
                next_slot += struct_total_slots(pt);
            } else if (is_array(pt)) {
                if (is_dynamic_array(pt)) {
                    // S3c-2：动态数组参数占 3 个连续槽（data/len/cap）。
                    // 入口先保存调用方描述符指针，再把堆缓冲深拷贝到本地（参数值语义）。
                    // S3c-3e：array<array<T>> 入口逐内层深拷贝。
                    int data = -(8 * (next_slot + 1));
                    flat_maps_[0][pn] = data;
                    DynArrayInfo di{data, data - 8, data - 16};
                    di.nested = is_dynamic_nested_array(pt);
                    dyn_maps_[0][pn] = di;
                    next_slot += 3;
                } else {
                    // S3b：数组参数在入口从指针逐元素拷贝到本地 [N x T] 栈数组。
                    // S3c-3d：固定 array<S, N> / 嵌套数组占 N*slots（M*N）个连续槽，
                    // 入口按总槽数拷贝，函数内就是普通扁平数组局部变量。
                    int len = *array_decl_len(pt);
                    int total = len * array_elem_slots(pt, stmt->pos);
                    flat_maps_[0][pn] = -(8 * (next_slot + total));
                    array_len_maps_[0][pn] = len;
                    next_slot += total;
                }
            } else {
                flat_maps_[0][pn] = -(8 * (next_slot + 1));
                ++next_slot;
            }
        }
        plan_stmts(stmt->body, next_slot);
        scope_stack_.pop_back();
        scratch_slots_ = next_slot;  // 调用点临时缓冲从普通槽之后分配

        fn_ = name;
        current_ret_ = stmt->ret;
        current_ret_struct_ = ret_struct;
        scope_stack_.clear();
        scope_stack_.push_back(0);
        scope_cursor_ = 1;  // 0 号块（fn body）已进入
        pushes_ = 0;
        // 上一函数可能以 return 结束（terminated_ 为 true），必须按函数重置，
        // 否则本函数的 if/while 体在发出第一条语句后会被误判为已终止。
        terminated_ = false;
        break_stack_.clear();
        break_depth_stack_.clear();

        text_ += "\n.p2align 2\n";
        text_ += "\t.globl _" + name + "\n";
        label("_" + name);
        emit("stp x29, x30, [sp, #-16]!");
        emit("mov x29, sp");
        const std::string frame_marker = "\t@FRAME_ALLOC@\n";
        text_ += frame_marker;
        zero_dynamic_slots();
        size_t param_pos = 0;
        if (ret_composite) {
            // 隐藏 sret 指针在 x0，函数返回 void（自定义 Tenet ABI，struct/array 共用）。
            emit("str x0, [x29, #" + std::to_string(sret_slot_) + "]");
            param_pos = 1;
        }
        // 参数入槽：先全部落槽，再对动态数组参数深拷贝。
        // （malloc 会破坏尚未落槽的参数寄存器，所以不能边落槽边深拷贝。）
        for (size_t i = 0; i < stmt->params.size(); ++i, ++param_pos) {
            const auto& [pn, pt] = stmt->params[i];
            std::string arg_reg = std::string(is_float(pt) ? "d" : "x") +
                                  std::to_string(param_pos);
            if (is_struct(pt)) {
                unpack_buffer_from_reg(pn, pt, arg_reg, stmt->pos);
            } else if (is_dynamic_array(pt)) {
                // S3c-2：xN 是调用方描述符指针，先暂存在 data 槽，第二阶段再深拷贝覆盖。
                store_slot(arg_reg, dyn_maps_[0][pn].data);
            } else if (is_array(pt)) {
                // S3b/S3c-3d：xN 是调用方数组元素 0 的地址，按总槽数逐槽拷贝到本地
                // （struct 元素按扁平字段槽、嵌套数组按 M*N 扁平槽，均按 8 字节值拷贝）。
                copy_array_from_reg(flat_maps_[0][pn], arg_reg,
                                    *array_decl_len(pt) * array_elem_slots(pt, stmt->pos));
            } else {
                int off = flat_maps_[0][pn];
                store_slot(arg_reg, off);
            }
        }
        for (const auto& [pn, pt] : stmt->params) {
            if (is_dynamic_array(pt)) deep_copy_dynamic_param(dyn_maps_[0][pn], pt, stmt->pos);
        }
        for (const auto& s : stmt->body) emit_stmt(s);
        // void 函数自然落回：离开函数作用域前 drop 局部动态数组（return 路径已各自 drop）。
        if (!terminated_) drop_all_scopes();
        // 函数 epilogue（return 跳转到此；void 函数自然落回）
        label("L." + name + ".ret");
        frame_ = ((scratch_slots_ * 8) + 15) / 16 * 16;
        emit_frame_adjust(frame_, false);
        emit("ldp x29, x30, [sp], #16");
        emit("ret");
        patch_frame_alloc(frame_marker, frame_);
        fn_.clear();
        current_ret_ = std::nullopt;
        current_ret_struct_ = false;
        sret_slot_ = 0;
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
        dyn_maps_.clear();
        scope_queue_.clear();
        scope_cursor_ = 0;
        scope_stack_.clear();
        flat_maps_.push_back({});
        type_maps_.push_back({});
        array_len_maps_.push_back({});
        dyn_maps_.push_back({});
        scope_queue_.push_back(0);
        scope_stack_.push_back(0);
        plan_stmts(body, next_slot);
        scope_stack_.pop_back();
        scratch_slots_ = next_slot;
        scope_stack_.clear();
        scope_stack_.push_back(0);
        scope_cursor_ = 1;
        pushes_ = 0;
        terminated_ = false;  // 与 emit_fn 同理：main 前一个函数可能以 return 结束
        break_stack_.clear();
        break_depth_stack_.clear();

        text_ += "\n.p2align 2\n";
        text_ += "\t.globl _main\n";
        label("_main");
        emit("stp x29, x30, [sp, #-16]!");
        emit("mov x29, sp");
        const std::string frame_marker = "\t@FRAME_ALLOC@\n";
        text_ += frame_marker;
        zero_dynamic_slots();
        for (const auto& s : body) emit_stmt(s);
        drop_all_scopes();  // main 结束前释放顶层动态数组
        label("L.main.ret");
        emit("mov x0, #0");
        frame_ = ((scratch_slots_ * 8) + 15) / 16 * 16;
        emit_frame_adjust(frame_, false);
        emit("ldp x29, x30, [sp], #16");
        emit("ret");
        patch_frame_alloc(frame_marker, frame_);
        fn_.clear();
        current_ret_struct_ = false;
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
                    if (is_dynamic_array(t)) {
                        emit_dynamic_init(*stmt, t);
                    } else {
                        emit_array_init(*stmt, t);
                    }
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
                for (const auto& s : stmt->then_branch) {
                    emit_stmt(s);
                    if (terminated_) break;
                }
                exit_scope();
                if (!terminated_) emit("b " + merge_l);
                terminated_ = false;
                label(else_l);
                if (!stmt->else_branch.empty()) {
                    enter_scope();
                    for (const auto& s : stmt->else_branch) {
                        emit_stmt(s);
                        if (terminated_) break;
                    }
                    exit_scope();
                }
                terminated_ = false;
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
                break_depth_stack_.push_back(scope_stack_.size());
                for (const auto& s : stmt->body) {
                    emit_stmt(s);
                    if (terminated_) break;
                }
                break_depth_stack_.pop_back();
                break_stack_.pop_back();
                exit_scope();
                if (!terminated_) emit("b " + cond_l);
                terminated_ = false;
                label(exit_l);
                return;
            }
            case Stmt::Kind::Return: {
                if (current_ret_.has_value() && is_dynamic_array(*current_ret_)) {
                    // S3c-2：动态数组返回值把 data/len/cap 写进调用方描述符（隐藏 sret 第一参数）。
                    transfer_dynamic_return(*stmt);
                    return;
                }
                if (current_ret_.has_value() && is_array(*current_ret_)) {
                    // S3b：定长数组返回值打包到隐藏 sret 指针指向的调用方缓冲区。
                    // S3c-3d：多槽固定数组（array<S, N> / 嵌套数组）按 N*slots（M*N）
                    // 总槽数打包/写出，元素仍是扁平 8 字节槽。
                    if (!stmt->expr) {
                        throw TenetError::at_pos("函数 `" + fn_ + "` 返回 " + *current_ret_ +
                                                     "，return 必须带值",
                                                 stmt->pos);
                    }
                    auto len = array_decl_len(*current_ret_);
                    if (!len.has_value()) {
                        throw TenetError::at_pos("array 返回值必须写 array<T, N>", stmt->pos);
                    }
                    int slots = array_elem_slots(*current_ret_, stmt->pos);
                    int total = *len * slots;
                    int buf_off = alloc_array_scratch(total);
                    if (fixed_array_flat_slots(*current_ret_, stmt->pos)) {
                        pack_fixed_array_expr(*current_ret_, stmt->expr, buf_off);
                    } else {
                        pack_array_expr_to_buffer(*current_ret_, *len, stmt->expr, buf_off);
                    }
                    load_slot("x15", sret_slot_);
                    copy_array_to_ptr("x15", buf_off, total);
                    // return 前 drop 当前所有作用域里的局部动态数组。
                    drop_all_scopes();
                    emit("b L." + fn_ + ".ret");
                    terminated_ = true;
                    return;
                }
                if (current_ret_struct_) {
                    if (!stmt->expr) {
                        throw TenetError::at_pos("函数 `" + fn_ + "` 返回 " + *current_ret_ +
                                                     "，return 必须带值",
                                                 stmt->pos);
                    }
                    // 先把返回值打包到临时缓冲，再整块写到隐藏 sret 指针指向的缓冲区。
                    int n = struct_total_slots(*current_ret_);
                    int buf_off = alloc_scratch(n);
                    pack_expr_to_buffer(buf_off, *current_ret_, stmt->expr);
                    load_slot("x15", sret_slot_);
                    for (int j = 0; j < n; ++j) {
                        load_slot("x9", buf_off - 8 * j);
                        store_reg_offset("x9", "x15", -8 * j);
                    }
                    drop_all_scopes();
                    emit("b L." + fn_ + ".ret");
                    terminated_ = true;
                    return;
                }
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
                    // 返回值已在表达式栈上；先 drop（调用会破坏寄存器），再弹进返回寄存器。
                    drop_all_scopes();
                    pop_reg(is_float(vt) ? "d0" : "x0");
                } else {
                    drop_all_scopes();
                }
                emit("b L." + fn_ + ".ret");
                terminated_ = true;
                return;
            }
            case Stmt::Kind::Break: {
                if (break_stack_.empty()) {
                    throw TenetError::at_pos("`break` 出现在循环之外", stmt->pos);
                }
                // break 跳出循环：先 drop 循环体作用域（含其内嵌套块）再跳。
                if (!break_depth_stack_.empty()) {
                    emit_drop_scopes_from(break_depth_stack_.back());
                }
                emit("b " + break_stack_.back());
                terminated_ = true;
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

    /// 退出块作用域：先 drop 该作用域内的动态数组，再弹出作用域。
    void exit_scope() {
        emit_drop_scope(scope_stack_.back());
        scope_stack_.pop_back();
    }

    std::string var_type(const std::string& name, const Position& pos) const {
        for (auto it = scope_stack_.rbegin(); it != scope_stack_.rend(); ++it) {
            const auto& table = type_maps_[*it];
            auto f = table.find(name);
            if (f != table.end()) return f->second;
        }
        throw TenetError::at_pos("未定义的变量 `" + name + "`", pos);
    }

    // ---- struct：嵌套扁平化字段槽位 + 指针 ABI ----

    /// 取变量的 Tenet 类型，同时确认它在当前作用域可见。
    std::string scoped_var_type(const std::string& name, const Position& pos) const {
        (void)lookup_slot(name, pos);
        return var_type(name, pos);
    }

    /// `l.a.x` → (var="l", path="a.x")；base 不是变量字段链时返回 false。
    static bool expr_var_path(const ExprPtr& e, std::string& var, std::string& path) {
        if (!e) return false;
        if (e->kind == Expr::Kind::Var) {
            var = e->name;
            path.clear();
            return true;
        }
        if (e->kind == Expr::Kind::Field) {
            std::string base_path;
            if (!expr_var_path(e->lhs, var, base_path)) return false;
            path = base_path.empty() ? e->name : base_path + "." + e->name;
            return true;
        }
        return false;
    }

    struct FieldRef {
        std::string var;
        std::string path;
        std::string ty;
    };

    /// 解析字段链（支持 l.a.x）：根必须是 struct 变量，中间路径必须都是 struct，
    /// 最终字段必须是标量（struct 字段需继续访问到标量）。
    FieldRef resolve_field(const ExprPtr& field, bool writing) const {
        std::string var, path;
        if (!expr_var_path(field, var, path) || path.empty()) {
            throw TenetError::at_pos("v1 只支持对 struct 变量" +
                                         std::string(writing ? "写" : "取") + "字段",
                                     field->lhs ? field->lhs->pos : field->pos);
        }
        Position pos = field->lhs ? field->lhs->pos : field->pos;
        std::string root = scoped_var_type(var, pos);
        std::string verb = writing ? "写" : "取";
        size_t first_dot = path.find('.');
        std::string first = path.substr(0, first_dot);
        if (!is_struct(root)) {
            throw TenetError::at_pos("`" + var + "` 不是 struct，不能" + verb + "字段 `" +
                                         first + "`",
                                     pos);
        }
        std::string cur = root;
        std::string prefix;
        size_t start = 0;
        while (true) {
            size_t dot = path.find('.', start);
            std::string part =
                path.substr(start, dot == std::string::npos ? std::string::npos : dot - start);
            if (!is_struct(cur)) {
                throw TenetError::at_pos("v1 只支持对 struct 变量" + verb + "字段（`" + var +
                                             (prefix.empty() ? "" : "." + prefix) +
                                             "` 不是 struct）",
                                         pos);
            }
            auto ft = field_type(cur, part);
            if (!ft.has_value()) {
                throw TenetError::at_pos("struct `" + cur + "` 没有字段 `" + part + "`",
                                         field->pos);
            }
            cur = *ft;
            prefix = prefix.empty() ? part : prefix + "." + part;
            if (dot == std::string::npos) break;
            start = dot + 1;
        }
        if (is_struct(cur)) {
            throw TenetError::at_pos("字段 `" + var + "." + path +
                                         "` 是 struct，请继续访问到标量字段",
                                     field->pos);
        }
        return {var, path, cur};
    }

    struct FieldPathInfo {
        std::string ty;
        int offset = 0;  // 相对 struct 起始的槽偏移
    };

    /// 解析 struct 根类型下的点分字段路径，返回最终字段类型与布局槽偏移。
    /// 用于 `s.a[i]` / `s.p.a[i]` 这类「struct 的固定数组字段」寻址。
    FieldPathInfo field_path_info(const std::string& root_ty, const std::string& path,
                                  const Position& pos) const {
        std::string cur = root_ty;
        int offset = 0;
        size_t start = 0;
        while (true) {
            size_t dot = path.find('.', start);
            std::string part = path.substr(
                start, dot == std::string::npos ? std::string::npos : dot - start);
            if (!is_struct(cur)) {
                throw TenetError::at_pos("`" + cur + "` 不是 struct，不能取字段 `" + part + "`",
                                         pos);
            }
            const auto& defs = struct_fields(cur, pos);
            bool found = false;
            for (const auto& [fname, fty] : defs) {
                if (fname != part) {
                    offset += field_slot_width(fty);
                    continue;
                }
                found = true;
                if (dot == std::string::npos) return {fty, offset};
                if (!is_struct(fty)) {
                    throw TenetError::at_pos("`" + cur + "." + part + "` 不是 struct，不能再取字段",
                                             pos);
                }
                // offset 保持为该嵌套 struct 的起始槽；其内部字段偏移在下一轮累加。
                cur = fty;
                break;
            }
            if (!found) {
                throw TenetError::at_pos("struct `" + cur + "` 没有字段 `" + part + "`", pos);
            }
            start = dot + 1;
        }
    }

    int field_slot(const std::string& var, const std::string& path,
                   const Position& pos) const {
        return lookup_slot(var + "." + path, pos);
    }

    // ---- S3c-3b-1：array<struct, N> 元素字段 ----

    /// `a[i].p.x` → 根数组变量 `a`、下标表达式 `i`、字段路径 `p.x`。
    struct StructElemRef {
        ExprPtr base;   // 数组变量节点（用于作用域查找与错误定位）
        ExprPtr index;
        std::string path;
    };

    /// 递归拆解 `a[i].p.x` / `s.a[i].p.x`：最内层必须是「数组变量[下标]」或
    /// 「struct 变量.固定数组字段[下标]」。
    static bool struct_elem_path(const ExprPtr& e, StructElemRef& ref) {
        if (!e) return false;
        if (e->kind == Expr::Kind::Field) {
            if (!struct_elem_path(e->lhs, ref)) return false;
            ref.path = ref.path.empty() ? e->name : ref.path + "." + e->name;
            return true;
        }
        if (e->kind == Expr::Kind::Index) {
            if (!e->lhs ||
                (e->lhs->kind != Expr::Kind::Var && e->lhs->kind != Expr::Kind::Field)) {
                return false;
            }
            ref.base = e->lhs;
            ref.index = e->rhs;
            ref.path.clear();
            return true;
        }
        return false;
    }

    /// S3d 深路径：`arr[i].f[j]` / `s.ps[i].q.f[j]`——先取 struct 数组元素，
    /// 再访问元素内固定数组字段的某个元素。
    struct DeepArrayFieldRef {
        ExprPtr base;          // 数组变量 / struct 固定数组字段
        ExprPtr elem_index;    // 数组元素下标
        std::string field_path;  // 元素 struct 内的字段点路径
        ExprPtr field_index;   // 字段数组下标
    };

    /// 拆分 `arr[i].f[j]`（f 可嵌套为 q.f）；结构不符返回 false。
    static bool deep_array_field_parts(const ExprPtr& e, DeepArrayFieldRef& out) {
        if (!e || e->kind != Expr::Kind::Index || !e->lhs ||
            e->lhs->kind != Expr::Kind::Field) {
            return false;
        }
        std::vector<std::string> names;
        ExprPtr cur = e->lhs;
        while (cur && cur->kind == Expr::Kind::Field) {
            names.push_back(cur->name);
            cur = cur->lhs;
        }
        if (!cur || cur->kind != Expr::Kind::Index) return false;
        if (!cur->lhs ||
            (cur->lhs->kind != Expr::Kind::Var && cur->lhs->kind != Expr::Kind::Field)) {
            return false;
        }
        std::string path;
        for (auto it = names.rbegin(); it != names.rend(); ++it) {
            path += (path.empty() ? "" : ".") + *it;
        }
        out.base = cur->lhs;
        out.elem_index = cur->rhs;
        out.field_path = path;
        out.field_index = e->rhs;
        return true;
    }

    struct FlatFieldRef {
        std::string ty;   // 标量类型
        int offset = 0;   // 在 struct 布局里的槽位偏移
    };

    /// 暂不支持把 `a[i]` 整体读成 struct 值（S3c-3b-1 只支持标量字段路径）。
    [[noreturn]] static void reject_struct_elem_read(const ExprPtr& e) {
        throw TenetError::at_pos(
            "array<struct> 元素不能整体读取为 struct 值；请访问标量字段（如 a[i].x）",
            e->pos);
    }

    /// 校验点分字段路径并返回标量类型与布局槽偏移。
    FlatFieldRef struct_flat_field(const std::string& ty, const std::string& path,
                                   const Position& pos) const {
        std::string cur = ty;
        size_t start = 0;
        while (true) {
            size_t dot = path.find('.', start);
            std::string part = path.substr(
                start, dot == std::string::npos ? std::string::npos : dot - start);
            if (!is_struct(cur)) {
                throw TenetError::at_pos(
                    "v1 只支持对 struct 路径取字段（`" + cur + "` 不是 struct）", pos);
            }
            auto ft = field_type(cur, part);
            if (!ft.has_value()) {
                throw TenetError::at_pos("struct `" + cur + "` 没有字段 `" + part + "`", pos);
            }
            cur = *ft;
            if (dot == std::string::npos) break;
            start = dot + 1;
        }
        if (is_struct(cur)) {
            throw TenetError::at_pos(
                "字段 `" + path + "` 是 struct，请继续访问到标量字段", pos);
        }
        if (is_array(cur)) {
            throw TenetError::at_pos(
                "字段 `" + path + "` 是固定数组，请用下标访问（如 `" + path + "[0]`）", pos);
        }
        auto entry = layout_entry(ty, path);
        if (!entry.has_value()) {
            throw TenetError::at_pos("struct `" + ty + "` 没有标量字段 `" + path + "`", pos);
        }
        return {entry->ty, entry->offset};
    }

    /// 把 struct 字面量递归展开为标量字段初始化：路径 → 表达式（按声明顺序）。
    void flatten_literal(const std::string& ty,
                         const std::vector<std::pair<std::string, ExprPtr>>& fields,
                         const std::string& prefix, const Position& lit_pos,
                         std::vector<std::pair<std::string, ExprPtr>>& out) const {
        const auto& defs = struct_fields(ty, lit_pos);
        std::unordered_map<std::string, ExprPtr> inits;
        for (const auto& [fname, fexpr] : fields) {
            if (inits.count(fname)) {
                throw TenetError::at_pos("struct `" + ty + "` 的字段 `" + fname + "` 重复初始化",
                                         fexpr->pos);
            }
            if (!field_type(ty, fname).has_value()) {
                throw TenetError::at_pos("struct `" + ty + "` 没有字段 `" + fname + "`",
                                         fexpr->pos);
            }
            inits[fname] = fexpr;
        }
        for (const auto& [fname, fty] : defs) {
            auto it = inits.find(fname);
            if (it == inits.end()) {
                throw TenetError::at_pos("struct `" + ty + "` 缺少字段 `" + fname + "`", lit_pos);
            }
            const ExprPtr& fexpr = it->second;
            std::string path = prefix.empty() ? fname : prefix + "." + fname;
            if (is_struct(fty)) {
                if (fexpr->kind != Expr::Kind::StructLit) {
                    throw TenetError::at_pos("字段 `" + path + "` 需要 " + fty + " 字面量",
                                             fexpr->pos);
                }
                if (fexpr->name != fty) {
                    throw TenetError::at_pos("字段 `" + path + "` 需要 " + fty +
                                                 "，实际字面量是 " + fexpr->name,
                                             fexpr->pos);
                }
                flatten_literal(fty, fexpr->fields, path, fexpr->pos, out);
            } else {
                out.push_back({path, fexpr});
            }
        }
    }

    /// S3d：把固定数组值写入扁平槽。
    /// `elem0_off` 是元素 0 的槽位，`stride` 为元素间槽位方向：
    /// - 局部数组 / packed 缓冲 / struct 数组元素：+8（元素 i 在 elem0 + 8*i）；
    /// - 局部 struct 变量的字段：-8（元素 i 在 elem0 - 8*i，字段向低地址展开）。
    /// 支持数组字面量、同类型局部数组变量、返回同类型数组的调用；字面量可递归。
    void store_fixed_array_value(int elem0_off, int stride, const std::string& ty,
                                 const ExprPtr& expr, const std::string& what) {
        auto len = array_decl_len(ty);
        if (!len.has_value()) {
            throw TenetError::at_pos(what + " 需要固定长度数组 " + ty, expr->pos);
        }
        auto elem = array_elem(ty);
        if (!elem.has_value()) {
            throw TenetError::at_pos(what + " 不是数组类型 " + ty, expr->pos);
        }
        int slots = array_elem_slots(ty, expr->pos);
        int total = *len * slots;
        if (expr->kind == Expr::Kind::Array) {
            if ((int)expr->args.size() != *len) {
                throw TenetError::at_pos(what + " 数组长度不匹配：需要 " +
                                             std::to_string(*len) + "，实际 " +
                                             std::to_string(expr->args.size()),
                                         expr->pos);
            }
            if (is_struct(*elem)) {
                int tmp = alloc_scratch(slots);
                for (int i = 0; i < *len; ++i) {
                    const ExprPtr& arg = expr->args[i];
                    std::string item = what + "[" + std::to_string(i) + "]";
                    if (arg->kind == Expr::Kind::StructLit && arg->name != *elem) {
                        throw TenetError::at_pos(item + " 类型不匹配：需要 " + *elem +
                                                     "，字面量是 " + arg->name,
                                                 arg->pos);
                    }
                    if (arg->kind == Expr::Kind::Var) {
                        std::string vt = scoped_var_type(arg->name, arg->pos);
                        if (vt != *elem) {
                            throw TenetError::at_pos(item + " 类型不匹配：需要 " + *elem +
                                                         "，实际 " + vt,
                                                     arg->pos);
                        }
                    }
                    pack_expr_to_buffer(tmp, *elem, arg);
                    for (int k = 0; k < slots; ++k) {
                        load_slot("x9", tmp - 8 * k);
                        store_slot("x9", elem0_off + stride * (i * slots + k));
                    }
                }
                return;
            }
            if (is_array(*elem)) {
                for (int i = 0; i < *len; ++i) {
                    store_fixed_array_value(elem0_off + stride * (i * slots), stride, *elem,
                                            expr->args[i],
                                            what + "[" + std::to_string(i) + "]");
                }
                return;
            }
            for (int i = 0; i < *len; ++i) {
                std::string vt = gen_expr(expr->args[i]);
                if (vt != *elem) {
                    throw TenetError::at_pos(what + "[" + std::to_string(i) +
                                                 "] 类型不匹配：需要 " + *elem + "，实际 " + vt,
                                             expr->args[i]->pos);
                }
                std::string reg = is_float(*elem) ? "d9" : "x9";
                pop_reg(reg);
                store_slot(reg, elem0_off + stride * i);
            }
            return;
        }
        if (expr->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(expr->name, expr->pos);
            if (src_ty != ty) {
                throw TenetError::at_pos(what + " 类型不匹配：需要 " + ty + "，实际 " + src_ty,
                                         expr->pos);
            }
            int src_off = lookup_slot(expr->name, expr->pos);
            for (int k = 0; k < total; ++k) {
                load_slot("x9", src_off + 8 * k);
                store_slot("x9", elem0_off + stride * k);
            }
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(expr);
            if (rt != ty) {
                throw TenetError::at_pos(what + " 类型不匹配：需要 " + ty + "，调用返回 " + rt,
                                         expr->pos);
            }
            pop_reg("x10");
            // 数组返回值/sret 缓冲按元素 0 最低地址、向高地址排列。
            for (int k = 0; k < total; ++k) {
                load_reg_offset("x9", "x10", 8 * k);
                store_slot("x9", elem0_off + stride * k);
            }
            return;
        }
        throw TenetError::at_pos(what +
                                     " 的初始化必须是数组字面量、同类型数组变量或返回数组的调用",
                                 expr->pos);
    }

    /// 把 struct 字面量的字段逐个求值并写入 dst 的扁平字段槽。
    void store_struct_lit(const std::string& dst, const std::string& ty,
                          const ExprPtr& lit) {
        std::vector<std::pair<std::string, ExprPtr>> flat;
        flatten_literal(ty, lit->fields, "", lit->pos, flat);
        std::unordered_map<std::string, LayoutEntry> layout;
        for (const auto& entry : layout_of(ty)) layout[entry.path] = entry;
        for (const auto& [path, fexpr] : flat) {
            auto it = layout.find(path);
            if (it == layout.end()) {
                throw TenetError::at_pos("struct `" + ty + "` 没有标量字段 `" + path + "`",
                                         fexpr->pos);
            }
            const LayoutEntry& entry = it->second;
            int off = field_slot(dst, path, fexpr->pos);
            if (is_array(entry.ty)) {
                store_fixed_array_value(off, -8, entry.ty, fexpr,
                                        "struct `" + ty + "` 字段 `" + path + "`");
                continue;
            }
            std::string vt = gen_expr(fexpr);
            if (vt != entry.ty) {
                throw TenetError::at_pos("struct `" + ty + "` 字段 `" + path +
                                             "` 类型不匹配：需要 " + entry.ty + "，实际 " + vt,
                                         fexpr->pos);
            }
            pop_reg(is_float(entry.ty) ? "d9" : "x9");
            store_slot(is_float(entry.ty) ? "d9" : "x9", off);
        }
    }

    /// 逐字段值拷贝：struct 变量之间不共享槽位（固定数组字段逐槽拷贝）。
    void copy_struct(const std::string& dst, const std::string& src, const std::string& ty,
                     const Position& pos) {
        for (const auto& entry : layout_of(ty)) {
            int src_off = field_slot(src, entry.path, pos);
            int dst_off = field_slot(dst, entry.path, pos);
            for (int k = 0; k < entry.slots; ++k) {
                load_slot("x9", src_off - 8 * k);
                store_slot("x9", dst_off - 8 * k);
            }
        }
    }

    /// 把 struct 值（字面量 / 同类型变量 / 返回 struct 的调用）打包到临时缓冲。
    /// 缓冲 slot j 在 buf_off - 8*j（布局偏移，固定数组字段连续占 slots 槽）。
    void pack_expr_to_buffer(int buf_off, const std::string& ty, const ExprPtr& expr) {
        const auto layout = layout_of(ty);
        std::unordered_map<std::string, LayoutEntry> by_path;
        for (const auto& entry : layout) by_path[entry.path] = entry;

        if (expr->kind == Expr::Kind::StructLit) {
            if (expr->name != ty) {
                throw TenetError::at_pos("需要 " + ty + "，字面量是 " + expr->name, expr->pos);
            }
            std::vector<std::pair<std::string, ExprPtr>> init;
            flatten_literal(ty, expr->fields, "", expr->pos, init);
            for (const auto& [path, fexpr] : init) {
                auto it = by_path.find(path);
                if (it == by_path.end()) {
                    throw TenetError::at_pos("struct `" + ty + "` 没有标量字段 `" + path + "`",
                                             fexpr->pos);
                }
                const LayoutEntry& entry = it->second;
                if (is_array(entry.ty)) {
                    // 先按升序打包到临时缓冲，再按 packed 布局（向低地址）拷贝。
                    int tmp = alloc_scratch(entry.slots);
                    store_fixed_array_value(tmp, +8, entry.ty, fexpr,
                                            "字段 `" + path + "`");
                    for (int k = 0; k < entry.slots; ++k) {
                        load_slot("x9", tmp + 8 * k);
                        store_slot("x9", buf_off - 8 * (entry.offset + k));
                    }
                    continue;
                }
                std::string vt = gen_expr(fexpr);
                if (vt != entry.ty) {
                    throw TenetError::at_pos("字段 `" + path + "` 类型不匹配：需要 " +
                                                 entry.ty + "，实际 " + vt,
                                             fexpr->pos);
                }
                if (is_float(entry.ty)) {
                    pop_reg("d9");
                    emit("fmov x9, d9");  // 统一按 8 字节位模式存储
                } else {
                    pop_reg("x9");
                }
                store_slot("x9", buf_off - 8 * entry.offset);
            }
            return;
        }
        if (expr->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(expr->name, expr->pos);
            if (src_ty != ty) {
                throw TenetError::at_pos("需要 " + ty + "，实际是 " + src_ty, expr->pos);
            }
            int src_off = lookup_slot(expr->name, expr->pos);
            for (const auto& entry : layout) {
                for (int k = 0; k < entry.slots; ++k) {
                    load_slot("x9", src_off - 8 * (entry.offset + k));
                    store_slot("x9", buf_off - 8 * (entry.offset + k));
                }
            }
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(expr);
            if (rt != ty) {
                throw TenetError::at_pos("需要 " + ty + "，实际是 " + rt, expr->pos);
            }
            pop_reg("x10");  // 调用返回的 struct 缓冲区指针
            for (const auto& entry : layout) {
                for (int k = 0; k < entry.slots; ++k) {
                    load_reg_offset("x9", "x10", -8 * (entry.offset + k));
                    store_slot("x9", buf_off - 8 * (entry.offset + k));
                }
            }
            return;
        }
        if (expr->kind == Expr::Kind::Index) reject_struct_elem_read(expr);
        throw TenetError::at_pos(
            "`" + ty + "` 值必须是字面量、同类型变量或返回 `" + ty + "` 的函数调用",
            expr->pos);
    }

    /// 从寄存器指向的缓冲区逐字段拷到本地扁平槽（struct 参数入口 / 调用返回值）。
    void unpack_buffer_from_reg(const std::string& dst, const std::string& ty,
                                const std::string& reg, const Position& pos) {
        for (const auto& entry : layout_of(ty)) {
            int dst_off = field_slot(dst, entry.path, pos);
            for (int k = 0; k < entry.slots; ++k) {
                load_reg_offset("x9", reg, -8 * (entry.offset + k));
                store_slot("x9", dst_off - 8 * k);
            }
        }
    }

    /// struct 类型的实参：同类型变量传其扁平槽首地址（被调方入口拷贝），
    /// 字面量打包到临时缓冲，调用返回则直接传返回缓冲区指针。结果压栈。
    void push_struct_value(const std::string& ty, const ExprPtr& expr) {
        if (expr->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(expr->name, expr->pos);
            if (src_ty != ty) {
                throw TenetError::at_pos("需要 " + ty + "，实际是 " + src_ty, expr->pos);
            }
            int off = lookup_slot(expr->name, expr->pos);
            lea_slot("x9", off);
            push_reg("x9");
            return;
        }
        if (expr->kind == Expr::Kind::StructLit) {
            if (expr->name != ty) {
                throw TenetError::at_pos("需要 " + ty + "，字面量是 " + expr->name, expr->pos);
            }
            int n = struct_total_slots(ty);
            int buf_off = alloc_scratch(n);
            pack_expr_to_buffer(buf_off, ty, expr);
            lea_slot("x9", buf_off);
            push_reg("x9");
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(expr);
            if (rt != ty) {
                throw TenetError::at_pos("需要 " + ty + "，实际 " + rt, expr->pos);
            }
            return;  // gen_expr 已压入返回缓冲区指针
        }
        if (expr->kind == Expr::Kind::Index) reject_struct_elem_read(expr);
        throw TenetError::at_pos(
            "`" + ty + "` 类型的实参必须是同类型变量、字面量或返回 `" + ty + "` 的函数调用",
            expr->pos);
    }

    /// let p: Point = Point { ... }; / let q = p; / let m = make();
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
        if (v->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(v);
            if (rt != ty) {
                throw TenetError::at_pos(
                    "`" + stmt.name + "` 需要 " + ty + "，但调用返回 " + rt, v->pos);
            }
            pop_reg("x10");
            unpack_buffer_from_reg(stmt.name, ty, "x10", v->pos);
            return;
        }
        if (v->kind == Expr::Kind::Index) reject_struct_elem_read(v);
        throw TenetError::at_pos("`" + stmt.name + "` 的 struct 初始化必须是 `" + ty +
                                     " { ... }`、同类型变量或返回 " + ty + " 的调用",
                                 v->pos);
    }

    /// p = Point { ... }; / p = q; / p = make();
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
        if (value->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(value);
            if (rt != dst_ty) {
                throw TenetError::at_pos(
                    "赋值类型不匹配：需要 " + dst_ty + "，右侧调用返回 " + rt, pos);
            }
            pop_reg("x10");
            unpack_buffer_from_reg(dst, dst_ty, "x10", value->pos);
            return;
        }
        if (value->kind == Expr::Kind::Index) reject_struct_elem_read(value);
        throw TenetError::at_pos(
            "struct 整体赋值必须是同类型变量、字面量或返回 struct 的调用", value->pos);
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

    /// 把常量装入任意寄存器（大数组槽位地址 / 大栈帧用）。返回带制表符的完整行。
    static std::string mov_const_asm(const std::string& reg, int64_t v) {
        std::string out;
        if (v >= -32768 && v <= 32767) {
            return "\tmov " + reg + ", #" + std::to_string(v) + "\n";
        }
        uint64_t u = static_cast<uint64_t>(v);
        out += "\tmovz " + reg + ", #" + std::to_string(u & 0xFFFF) + "\n";
        for (int shift = 16; shift < 64; shift += 16) {
            uint64_t part = (u >> shift) & 0xFFFF;
            if (part != 0) {
                out += "\tmovk " + reg + ", #" + std::to_string(part) + ", lsl #" +
                       std::to_string(shift) + "\n";
            }
        }
        return out;
    }

    void emit_mov_const(const std::string& reg, int64_t v) { text_ += mov_const_asm(reg, v); }

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

    /// 寄存器基址 + 有符号偏移的 8 字节读写（struct 缓冲槽用；槽位向低地址增长）。
    void load_reg_offset(const std::string& reg, const std::string& base, int off) {
        if (off >= -256 && off <= 255) {
            emit("ldr " + reg + ", [" + base + ", #" + std::to_string(off) + "]");
            return;
        }
        int abs = off < 0 ? -off : off;
        if (abs <= 4095) {
            emit(std::string(off < 0 ? "sub " : "add ") + "x17, " + base + ", #" +
                 std::to_string(abs));
        } else {
            emit_mov_const("x17", abs);
            emit(std::string(off < 0 ? "sub " : "add ") + "x17, " + base + ", x17");
        }
        emit("ldr " + reg + ", [x17]");
    }

    void store_reg_offset(const std::string& reg, const std::string& base, int off) {
        if (off >= -256 && off <= 255) {
            emit("str " + reg + ", [" + base + ", #" + std::to_string(off) + "]");
            return;
        }
        int abs = off < 0 ? -off : off;
        if (abs <= 4095) {
            emit(std::string(off < 0 ? "sub " : "add ") + "x17, " + base + ", #" +
                 std::to_string(abs));
        } else {
            emit_mov_const("x17", abs);
            emit(std::string(off < 0 ? "sub " : "add ") + "x17, " + base + ", x17");
        }
        emit("str " + reg + ", [x17]");
    }

    /// 在帧尾按需分配 n 个连续 8 字节临时槽，返回 slot 0（最高地址）的 x29 偏移。
    /// 槽 j 位于 base - 8*j，与 struct 局部字段的扁平槽布局一致。
    int alloc_scratch(int n) {
        int base_slot = scratch_slots_;
        scratch_slots_ += n;
        return -(8 * (base_slot + 1));
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

    /// S3b：数组缓冲布局与局部数组槽一致——元素 i 在 base + 8*i（元素 0 最低地址）。
    /// 从寄存器指向的缓冲区逐元素拷到本地数组槽（参数入口 / 调用返回值）。
    void copy_array_from_reg(int dst_off, const std::string& reg, int len) {
        for (int i = 0; i < len; ++i) {
            load_reg_offset("x9", reg, 8 * i);
            store_slot("x9", dst_off + 8 * i);
        }
    }

    /// 本地数组槽逐元素写到寄存器指向的缓冲区（数组返回值写入隐藏 sret）。
    void copy_array_to_ptr(const std::string& reg, int src_off, int len) {
        for (int i = 0; i < len; ++i) {
            load_slot("x9", src_off + 8 * i);
            store_reg_offset("x9", reg, 8 * i);
        }
    }

    /// 数组临时缓冲：返回元素 0（最低地址）的槽位偏移；元素 i 在 base + 8*i。
    int alloc_array_scratch(int n) {
        int base_slot = scratch_slots_;
        scratch_slots_ += n;
        return -(8 * (base_slot + n));
    }

    /// 把数组值（字面量 / 同类型同长度变量 / 返回数组的调用）打包到临时缓冲。
    void pack_array_expr_to_buffer(const std::string& ty, int len, const ExprPtr& expr,
                                   int buf_off) {
        std::string elem = array_elem_scalar(ty, expr->pos);
        if (expr->kind == Expr::Kind::Array) {
            if ((int)expr->args.size() != len) {
                throw TenetError::at_pos("数组长度不匹配：需要 " + std::to_string(len) +
                                             "，实际 " +
                                             std::to_string(expr->args.size()),
                                         expr->pos);
            }
            for (size_t i = 0; i < expr->args.size(); ++i) {
                std::string vt = gen_expr(expr->args[i]);
                if (vt != elem) {
                    throw TenetError::at_pos("数组元素 " + std::to_string(i) +
                                                 " 类型不匹配：需要 " + elem + "，实际 " + vt,
                                             expr->args[i]->pos);
                }
                if (is_float(elem)) {
                    pop_reg("d9");
                    emit("fmov x9, d9");  // 统一按 8 字节位模式打包
                } else {
                    pop_reg("x9");
                }
                store_slot("x9", buf_off + 8 * (int)i);
            }
            return;
        }
        if (expr->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(expr->name, expr->pos);
            if (!is_array(src_ty) || array_elem(src_ty) != elem) {
                throw TenetError::at_pos("数组类型不匹配：需要 " + ty + "，实际 " + src_ty,
                                         expr->pos);
            }
            int src_len = lookup_array_len(expr->name, expr->pos);
            if (src_len != len) {
                throw TenetError::at_pos("数组长度不匹配：需要 " + std::to_string(len) +
                                             "，实际 " + std::to_string(src_len),
                                         expr->pos);
            }
            int src_off = lookup_slot(expr->name, expr->pos);
            copy_array_elems(buf_off, src_off, len, elem);
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(expr);
            if (!is_array(rt) || array_elem(rt) != elem) {
                throw TenetError::at_pos("数组调用返回类型不匹配：需要 " + ty + "，实际 " + rt,
                                         expr->pos);
            }
            auto rlen = array_decl_len(rt);
            if (!rlen.has_value() || *rlen != len) {
                throw TenetError::at_pos(
                    "数组调用返回长度不匹配：需要 " + std::to_string(len) + "，实际 " +
                        (rlen.has_value() ? std::to_string(*rlen) : std::string("?")),
                    expr->pos);
            }
            pop_reg("x10");
            copy_array_from_reg(buf_off, "x10", len);
            return;
        }
        throw TenetError::at_pos(
            "数组实参必须是同类型同长度数组变量、同长度字面量或返回数组的调用",
            expr->pos);
    }

    /// 数组实参：变量传其元素 0 的地址（被调方入口逐元素拷贝）；
    /// 字面量打包到临时缓冲；返回数组的调用直接传返回缓冲区指针。结果压栈。
    void push_array_value(const std::string& ty, const ExprPtr& expr) {
        auto len = array_decl_len(ty);
        if (!len.has_value()) {
            // 动态数组参数在 gen_call 里已分流到 push_dynamic_arg。
            throw TenetError::at_pos("内部错误：动态数组实参应走 push_dynamic_arg",
                                     expr->pos);
        }
        std::string elem = array_elem_scalar(ty, expr->pos);
        if (expr->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(expr->name, expr->pos);
            if (!is_array(src_ty) || array_elem(src_ty) != elem) {
                throw TenetError::at_pos("数组实参类型不匹配：需要 " + ty + "，实际 " + src_ty,
                                         expr->pos);
            }
            int src_len = lookup_array_len(expr->name, expr->pos);
            if (src_len != *len) {
                throw TenetError::at_pos("数组实参长度不匹配：需要 " + std::to_string(*len) +
                                             "，实际 " + std::to_string(src_len),
                                         expr->pos);
            }
            int off = lookup_slot(expr->name, expr->pos);
            lea_slot("x9", off);
            push_reg("x9");
            return;
        }
        if (expr->kind == Expr::Kind::Array) {
            int buf_off = alloc_array_scratch(*len);
            pack_array_expr_to_buffer(ty, *len, expr, buf_off);
            lea_slot("x9", buf_off);
            push_reg("x9");
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(expr);
            if (!is_array(rt) || array_elem(rt) != elem || array_decl_len(rt) != len) {
                throw TenetError::at_pos(
                    "数组实参类型不匹配：需要 " + ty + "，调用返回 " + rt, expr->pos);
            }
            return;  // gen_expr 已压入返回缓冲区指针
        }
        throw TenetError::at_pos(
            "数组实参必须是同类型同长度数组变量、同长度字面量或返回数组的调用",
            expr->pos);
    }

    /// S3c-3d：多槽固定数组（array<S, N> / array<array<T, N>, M>）的总槽数。
    /// 标量数组为 N（slots=1），struct 数组为 N*slots，嵌套数组为 M*N。
    int fixed_array_total_slots(const std::string& ty, const Position& pos) const {
        auto len = array_decl_len(ty);
        if (!len.has_value()) {
            throw TenetError::at_pos("需要固定长度数组", pos);
        }
        return *len * array_elem_slots(ty, pos);
    }

    /// 固定数组是否按"元素整体平铺槽"处理（struct 元素 / 嵌套数组）。
    /// 与每个元素占几个槽无关（单字段 struct 也是 1 槽），这类数组的参数、返回值
    /// 与实参打包都走扁平槽路径，而不是标量数组的逐元素路径。
    bool fixed_array_flat_slots(const std::string& ty, const Position& pos) const {
        std::string elem = array_elem_checked(ty, pos);
        return is_struct(elem) || is_array(elem);
    }

    /// 把多槽固定数组值（字面量 / 同类型变量 / 返回数组的调用）打包到扁平槽缓冲。
    /// 缓冲布局与局部数组一致：元素 0 字段 0 在 buf_off（最低地址），槽 k 在 buf_off + 8*k；
    /// 因此参数入口与 sret 打包都只需按总槽数逐槽拷贝。
    void pack_fixed_array_expr(const std::string& ty, const ExprPtr& expr, int buf_off) {
        int total = fixed_array_total_slots(ty, expr->pos);
        auto len = array_decl_len(ty);
        std::string elem = array_elem_checked(ty, expr->pos);
        int slots = array_elem_slots(ty, expr->pos);
        if (expr->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(expr->name, expr->pos);
            if (src_ty != ty) {
                throw TenetError::at_pos("数组类型不匹配：需要 " + ty + "，实际 " + src_ty,
                                         expr->pos);
            }
            int src_off = lookup_slot(expr->name, expr->pos);
            copy_struct_array_slots(buf_off, src_off, total);
            return;
        }
        if (expr->kind == Expr::Kind::Array) {
            if ((int)expr->args.size() != *len) {
                throw TenetError::at_pos("数组长度不匹配：需要 " + std::to_string(*len) +
                                             "，实际 " +
                                             std::to_string(expr->args.size()),
                                         expr->pos);
            }
            if (is_struct(elem)) {
                // struct 元素：先把元素打包到 slots 槽临时缓冲，再逐槽平铺到数组槽。
                int tmp = alloc_scratch(slots);
                for (size_t i = 0; i < expr->args.size(); ++i) {
                    const ExprPtr& arg = expr->args[i];
                    if (arg->kind == Expr::Kind::StructLit && arg->name != elem) {
                        throw TenetError::at_pos("数组元素 " + std::to_string(i) +
                                                     " 类型不匹配：需要 " + elem +
                                                     "，字面量是 " + arg->name,
                                                 arg->pos);
                    }
                    if (arg->kind == Expr::Kind::Var) {
                        std::string vt = scoped_var_type(arg->name, arg->pos);
                        if (vt != elem) {
                            throw TenetError::at_pos("数组元素 " + std::to_string(i) +
                                                         " 类型不匹配：需要 " + elem +
                                                         "，实际 " + vt,
                                                     arg->pos);
                        }
                    }
                    pack_expr_to_buffer(tmp, elem, arg);
                    for (int k = 0; k < slots; ++k) {
                        load_slot("x9", tmp - 8 * k);
                        store_slot("x9", buf_off + 8 * ((int)i * slots + k));
                    }
                }
                return;
            }
            // 嵌套数组：每个内层 `[...]` / 内层数组变量平铺到 N 个槽。
            NestedArrayInfo info = nested_array_info(ty, expr->pos);
            for (size_t i = 0; i < expr->args.size(); ++i) {
                store_nested_inner(info, buf_off + 8 * (int)i * info.inner_len, expr->args[i],
                                   (int)i);
            }
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(expr);
            if (rt != ty) {
                throw TenetError::at_pos("数组类型不匹配：需要 " + ty + "，调用返回 " + rt,
                                         expr->pos);
            }
            pop_reg("x10");  // 调用返回的 sret 缓冲区（元素 0 地址）
            copy_array_from_reg(buf_off, "x10", total);
            return;
        }
        throw TenetError::at_pos(
            "固定数组值必须是同类型数组变量、字面量或返回数组的调用", expr->pos);
    }

    /// S3c-3d：多槽固定数组实参——变量传元素 0 地址（被调方入口按总槽数拷贝）；
    /// 字面量打包到临时缓冲；返回数组的调用直接传 sret 返回缓冲区指针。结果压栈。
    void push_fixed_array_value(const std::string& ty, const ExprPtr& expr) {
        int total = fixed_array_total_slots(ty, expr->pos);
        if (expr->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(expr->name, expr->pos);
            if (src_ty != ty) {
                throw TenetError::at_pos("数组实参类型不匹配：需要 " + ty + "，实际 " + src_ty,
                                         expr->pos);
            }
            int off = lookup_slot(expr->name, expr->pos);
            lea_slot("x9", off);
            push_reg("x9");
            return;
        }
        if (expr->kind == Expr::Kind::Array) {
            int buf_off = alloc_array_scratch(total);
            pack_fixed_array_expr(ty, expr, buf_off);
            lea_slot("x9", buf_off);
            push_reg("x9");
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(expr);
            if (rt != ty) {
                throw TenetError::at_pos("数组实参类型不匹配：需要 " + ty + "，调用返回 " + rt,
                                         expr->pos);
            }
            return;  // gen_expr 已压入返回缓冲区指针
        }
        throw TenetError::at_pos(
            "数组实参必须是同类型数组变量、字面量或返回数组的调用", expr->pos);
    }

    /// S3c-2/S3c-3a 动态数组实参：在调用方帧尾构造 3 槽描述符
    /// （data/len/cap 从低地址到高地址），把描述符地址作为指针实参压栈；
    /// 被调函数入口再深拷贝，调用方数组仍保留所有权。结果压栈。
    /// - 变量：只把源槽复制进临时描述符，不复制、不 drop 调用方变量
    /// - 字面量：构造临时动态数组（malloc + 填元素），登记到 temp_dyn，
    ///   调用返回后由 gen_call 只 free 堆缓冲（描述符本身是栈槽，不 free）
    /// - 调用：内层调用已在 sret 描述符里返回堆缓冲；复制进临时描述符并清空内层描述符，
    ///   同样登记到 temp_dyn，外层调用返回后 free（被调函数入口已深拷贝，安全）
    void push_dynamic_arg(const std::string& ty, const ExprPtr& expr,
                          std::vector<DynArrayInfo>& temp_dyn) {
        if (!expr) {
            throw TenetError::at_pos("动态数组实参只支持变量、字面量或返回动态数组的调用",
                                     Position());
        }
        array_elem_checked(ty, expr->pos);
        if (expr->kind == Expr::Kind::Var) {
            std::string at = scoped_var_type(expr->name, expr->pos);
            if (at != ty) {
                throw TenetError::at_pos("参数类型不匹配：需要 " + ty + "，实际 " + at,
                                         expr->pos);
            }
            const DynArrayInfo src = lookup_dyn(expr->name, expr->pos);
            DynArrayInfo desc = alloc_dyn_desc();
            load_slot("x9", src.data);
            store_slot("x9", desc.data);
            load_slot("x9", src.len);
            store_slot("x9", desc.len);
            load_slot("x9", src.cap);
            store_slot("x9", desc.cap);
            lea_slot("x9", desc.data);
            push_reg("x9");
            return;
        }
        if (expr->kind == Expr::Kind::Array) {
            DynArrayInfo desc = alloc_dyn_desc();
            init_dynamic_into(desc, ty, expr);
            desc.nested = is_dynamic_nested_array(ty);
            temp_dyn.push_back(desc);
            lea_slot("x9", desc.data);
            push_reg("x9");
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(expr);
            if (!is_dynamic_array(rt) || rt != ty) {
                throw TenetError::at_pos(
                    "参数类型不匹配：需要 " + ty + "，调用返回 " + rt, expr->pos);
            }
            // gen_expr 已压入内层调用的 sret 描述符指针：复制到本实参的临时描述符，
            // 并清空内层描述符（堆缓冲所有权改由 temp_dyn 负责，避免重复 free）。
            pop_reg("x10");
            DynArrayInfo desc = alloc_dyn_desc();
            load_reg_offset("x9", "x10", 0);
            store_slot("x9", desc.data);
            load_reg_offset("x9", "x10", 8);
            store_slot("x9", desc.len);
            load_reg_offset("x9", "x10", 16);
            store_slot("x9", desc.cap);
            desc.nested = is_dynamic_nested_array(ty);
            store_reg_offset("xzr", "x10", 0);
            store_reg_offset("xzr", "x10", 8);
            store_reg_offset("xzr", "x10", 16);
            temp_dyn.push_back(desc);
            lea_slot("x9", desc.data);
            push_reg("x9");
            return;
        }
        throw TenetError::at_pos("动态数组实参只支持变量、字面量或返回动态数组的调用",
                                 expr->pos);
    }

    struct ArrayRef {
        std::string ty;
        std::string elem;
        int len = 0;        // 定长数组长度（动态数组为 0）
        int base_off = 0;   // 定长数组元素 0 槽位 / 动态数组 data 槽位
        bool dynamic = false;
        int dyn_len_off = 0;
        int dyn_cap_off = 0;
        /// S3d：局部 struct 变量的固定数组字段按低地址展开，元素 stride = -8；
        /// 数组变量 / packed 缓冲 / struct 数组元素为 +8。
        int stride = 8;
    };

    /// 校验数组字段的元素类型（struct 字段可含固定嵌套 bool/struct，不套局部限制）。
    void check_field_elem_kind(const std::string& elem, const Position& pos) const {
        if (elem == T_INT || elem == T_FLOAT || elem == T_BOOL || is_struct(elem) ||
            is_array(elem)) {
            return;
        }
        throw TenetError::at_pos("数组元素只支持 int/float/bool、struct 或固定数组，实际 `" +
                                     elem + "`",
                                 pos);
    }

    /// 下标读写共用的数组基址解析：局部数组变量，或 struct 变量的固定数组字段。
    ArrayRef array_ref(const ExprPtr& base, const Position& pos, bool writing) {
        ArrayRef ref;
        if (base && base->kind == Expr::Kind::Field) {
            // S3d：`s.a[i]` / `s.p.a[i]`——struct 的固定数组字段。
            std::string var, path;
            if (!expr_var_path(base, var, path) || path.empty()) {
                throw TenetError::at_pos(
                    std::string("v1 只支持对数组变量") + (writing ? "写下标" : "取下标"),
                    base->pos);
            }
            std::string root = scoped_var_type(var, base->pos);
            if (!is_struct(root)) {
                throw TenetError::at_pos("`" + var + "` 不是 struct，不能" +
                                             (writing ? "写下标" : "取下标"),
                                         base->pos);
            }
            FieldPathInfo info = field_path_info(root, path, base->pos);
            if (!is_array(info.ty)) {
                throw TenetError::at_pos("`" + var + "." + path + "` 不是数组，不能" +
                                             (writing ? "写下标" : "取下标"),
                                         base->pos);
            }
            if (is_dynamic_array(info.ty)) {
                throw TenetError::at_pos("struct 字段 `" + var + "." + path +
                                             "` 是动态数组，不支持下标访问",
                                         base->pos);
            }
            auto elem = array_elem(info.ty);
            if (!elem.has_value()) {
                throw TenetError::at_pos("不是数组类型：" + info.ty, base->pos);
            }
            check_field_elem_kind(*elem, base->pos);
            ref.ty = info.ty;
            ref.elem = *elem;
            ref.len = *array_decl_len(info.ty);
            ref.base_off = lookup_slot(var, base->pos) - 8 * info.offset;
            ref.stride = -8;
            return ref;
        }
        if (!base || base->kind != Expr::Kind::Var) {
            throw TenetError::at_pos(
                std::string("v1 只支持对数组变量") + (writing ? "写下标" : "取下标"),
                base ? base->pos : pos);
        }
        ref.ty = scoped_var_type(base->name, base->pos);
        if (!is_array(ref.ty)) {
            throw TenetError::at_pos(
                "`" + base->name + "` 不是数组，不能" + (writing ? "写下标" : "取下标"),
                base->pos);
        }
        ref.elem = array_elem_checked(ref.ty, pos);
        if (is_dynamic_array(ref.ty)) {
            // S3c：动态数组元素在堆上，data 指针与 len 都在运行时读取。
            // S3c-3b-2：struct 元素同样走 data/len/cap 描述符 + slots 步长。
            const DynArrayInfo di = lookup_dyn(base->name, base->pos);
            ref.dynamic = true;
            ref.base_off = di.data;
            ref.dyn_len_off = di.len;
            ref.dyn_cap_off = di.cap;
            return ref;
        }
        ref.len = lookup_array_len(base->name, base->pos);
        ref.base_off = lookup_slot(base->name, base->pos);
        ref.stride = 8;
        return ref;
    }

    // ---- S3c-3b-1：固定长度 array<struct, N> ----
    //
    // 元素 i 的扁平字段 j 位于 base + 8*(i*slots + j)（元素 0 在最低地址），
    // slots = struct 总槽数（含固定数组字段），因此元素 stride = slots*8。

    /// 把 idx*slots + field_idx 算进 dst（AArch64 寄存器）。slots 为 2 的幂时用 lsl。
    void emit_flat_slot_index(const std::string& dst, const std::string& idx_reg, int slots,
                              int field_idx) {
        int shift = 0;
        while ((1 << shift) < slots) ++shift;
        if (slots == 1) {
            emit("mov " + dst + ", " + idx_reg);
        } else if ((1 << shift) == slots) {
            emit("lsl " + dst + ", " + idx_reg + ", #" + std::to_string(shift));
        } else {
            emit_mov_const("x15", slots);
            emit("mul " + dst + ", " + idx_reg + ", x15");
        }
        if (field_idx != 0) {
            if (field_idx <= 4095) {
                emit("add " + dst + ", " + dst + ", #" + std::to_string(field_idx));
            } else {
                emit_mov_const("x15", field_idx);
                emit("add " + dst + ", " + dst + ", x15");
            }
        }
    }

    /// x14 = &a[idx].field0（元素基址）：base_off + stride*(idx*slots)。
    void emit_struct_elem_base(int base_off, int slots, const std::string& idx_reg,
                               int stride = 8) {
        lea_slot("x14", base_off);
        emit_flat_slot_index("x17", idx_reg, slots, 0);
        emit(std::string(stride < 0 ? "sub " : "add ") + "x14, x14, x17, lsl #3");
    }

    /// x14 = &a[idx].field0（S3c-3b-2 动态 array<struct> 元素基址）：
    /// data 指针 + idx*slots*8（idx 已通过运行时边界检查）。
    void emit_dyn_struct_elem_base(int data_off, int slots, const std::string& idx_reg) {
        load_slot("x14", data_off);
        emit_flat_slot_index("x17", idx_reg, slots, 0);
        emit("add x14, x14, x17, lsl #3");
    }

    /// infer_type 用：`a[i].p.x` 的标量字段类型。
    std::string struct_array_field_type(const ExprPtr& e, bool writing) {
        StructElemRef er;
        if (!struct_elem_path(e, er)) {
            throw TenetError::at_pos("内部错误：不是 array<struct> 元素字段访问", e->pos);
        }
        ArrayRef ref = array_ref(er.base, e->pos, writing);
        if (!is_struct(ref.elem)) {
            throw TenetError::at_pos(
                "`" + er.base->name + "` 不是 array<struct>，不能对元素" +
                    std::string(writing ? "写" : "取") + "字段 `" + er.path + "`",
                e->pos);
        }
        return struct_flat_field(ref.elem, er.path, e->pos).ty;
    }

    std::string gen_struct_array_field_read(const ExprPtr& e) {
        StructElemRef er;
        if (!struct_elem_path(e, er)) {
            throw TenetError::at_pos("内部错误：不是 array<struct> 元素字段访问", e->pos);
        }
        ArrayRef ref = array_ref(er.base, e->pos, false);
        if (!is_struct(ref.elem)) {
            throw TenetError::at_pos(
                "`" + er.base->name + "` 不是 array<struct>，不能对元素取字段 `" + er.path +
                    "`",
                e->pos);
        }
        FlatFieldRef f = struct_flat_field(ref.elem, er.path, e->pos);
        int slots = array_elem_slots(ref.ty, e->pos);
        std::string reg = is_float(f.ty) ? "d9" : "x9";
        if (ref.dynamic) {
            // S3c-3b-2：动态 array<struct> 元素字段读：运行时下标 + data 指针寻址。
            std::string it = gen_expr(er.index);
            if (it != T_INT) {
                throw TenetError::at_pos("数组下标必须是 int，实际为 " + it, er.index->pos);
            }
            pop_reg("x10");
            load_slot("x11", ref.dyn_len_off);
            emit_bounds_check_dyn("x10", "x11");
            load_slot("x14", ref.base_off);
            emit_flat_slot_index("x17", "x10", slots, f.offset);
            emit(std::string(is_float(f.ty) ? "ldr d9, " : "ldr x9, ") +
                 "[x14, x17, lsl #3]");
            push_reg(reg);
            return f.ty;
        }
        if (auto ci = const_index(er.index)) {
            if (*ci < 0 || *ci >= ref.len) {
                throw TenetError::at_pos("数组下标 " + std::to_string(*ci) + " 越界（长度 " +
                                             std::to_string(ref.len) + "）",
                                         er.index->pos);
            }
            load_slot(reg, ref.base_off +
                              ref.stride * ((int)*ci * slots + f.offset));
            push_reg(reg);
            return f.ty;
        }
        std::string it = gen_expr(er.index);
        if (it != T_INT) {
            throw TenetError::at_pos("数组下标必须是 int，实际为 " + it, er.index->pos);
        }
        pop_reg("x10");
        emit_bounds_check(ref.len, "x10");
        lea_slot("x14", ref.base_off);
        emit_flat_slot_index("x17", "x10", slots, f.offset);
        if (ref.stride < 0) emit("sub x14, x14, x17, lsl #3");
        emit(std::string(is_float(f.ty) ? "ldr d9, " : "ldr x9, ") +
             (ref.stride < 0 ? "[x14]" : "[x14, x17, lsl #3]"));
        push_reg(reg);
        return f.ty;
    }

    std::string gen_struct_array_field_write(const ExprPtr& target, const ExprPtr& value) {
        StructElemRef er;
        if (!struct_elem_path(target, er)) {
            throw TenetError::at_pos("内部错误：不是 array<struct> 元素字段写", target->pos);
        }
        ArrayRef ref = array_ref(er.base, target->pos, true);
        if (!is_struct(ref.elem)) {
            throw TenetError::at_pos(
                "`" + er.base->name + "` 不是 array<struct>，不能对元素写字段 `" + er.path +
                    "`",
                target->pos);
        }
        FlatFieldRef f = struct_flat_field(ref.elem, er.path, target->pos);
        int slots = array_elem_slots(ref.ty, target->pos);
        std::string reg = is_float(f.ty) ? "d9" : "x9";
        if (ref.dynamic) {
            // S3c-3b-2：动态 array<struct> 元素字段写：运行时下标 + data 指针寻址。
            std::string it = gen_expr(er.index);
            if (it != T_INT) {
                throw TenetError::at_pos("数组下标必须是 int，实际为 " + it, er.index->pos);
            }
            pop_reg("x10");
            load_slot("x11", ref.dyn_len_off);
            emit_bounds_check_dyn("x10", "x11");
            push_reg("x10");  // 保存下标，跨过右值求值
            std::string vt = gen_expr(value);
            if (vt != f.ty) {
                throw TenetError::at_pos("字段 `" + er.path + "` 类型不匹配：需要 " + f.ty +
                                             "，实际 " + vt,
                                         value->pos);
            }
            pop_reg(reg);
            pop_reg("x10");
            load_slot("x14", ref.base_off);
            emit_flat_slot_index("x17", "x10", slots, f.offset);
            emit(std::string(is_float(f.ty) ? "str d9, " : "str x9, ") +
                 "[x14, x17, lsl #3]");
            push_reg(reg);
            return f.ty;
        }
        if (auto ci = const_index(er.index)) {
            if (*ci < 0 || *ci >= ref.len) {
                throw TenetError::at_pos("数组下标 " + std::to_string(*ci) + " 越界（长度 " +
                                             std::to_string(ref.len) + "）",
                                         er.index->pos);
            }
            std::string vt = gen_expr(value);
            if (vt != f.ty) {
                throw TenetError::at_pos("字段 `" + er.path + "` 类型不匹配：需要 " + f.ty +
                                             "，实际 " + vt,
                                         value->pos);
            }
            pop_reg(reg);
            store_slot(reg, ref.base_off +
                              ref.stride * ((int)*ci * slots + f.offset));
            push_reg(reg);
            return f.ty;
        }
        std::string it = gen_expr(er.index);
        if (it != T_INT) {
            throw TenetError::at_pos("数组下标必须是 int，实际为 " + it, er.index->pos);
        }
        pop_reg("x10");
        emit_bounds_check(ref.len, "x10");
        push_reg("x10");  // 保存下标，跨过右值求值
        std::string vt = gen_expr(value);
        if (vt != f.ty) {
            throw TenetError::at_pos("字段 `" + er.path + "` 类型不匹配：需要 " + f.ty +
                                         "，实际 " + vt,
                                     value->pos);
        }
        pop_reg(reg);
        pop_reg("x10");
        lea_slot("x14", ref.base_off);
        emit_flat_slot_index("x17", "x10", slots, f.offset);
        if (ref.stride < 0) emit("sub x14, x14, x17, lsl #3");
        emit(std::string(is_float(f.ty) ? "str d9, " : "str x9, ") +
             (ref.stride < 0 ? "[x14]" : "[x14, x17, lsl #3]"));
        push_reg(reg);
        return f.ty;
    }

    /// `a[i] = P { ... }` / `a[i] = p`：整体元素赋值（逐槽复制）。
    std::string gen_struct_array_elem_write(const ExprPtr& target_index, ArrayRef& ref,
                                            const ExprPtr& value, const Position& pos) {
        int slots = array_elem_slots(ref.ty, pos);
        if (value->kind == Expr::Kind::StructLit && value->name != ref.elem) {
            throw TenetError::at_pos("数组元素赋值类型不匹配：需要 " + ref.elem +
                                         "，字面量是 " + value->name,
                                     value->pos);
        }
        if (value->kind == Expr::Kind::Var) {
            std::string vt = scoped_var_type(value->name, value->pos);
            if (vt != ref.elem) {
                throw TenetError::at_pos("数组元素赋值类型不匹配：需要 " + ref.elem +
                                             "，实际 " + vt,
                                         value->pos);
            }
        }
        if (ref.dynamic) {
            // S3c-3b-2：动态 array<struct> 整体元素赋值：运行时下标 + 逐槽复制。
            std::string it = gen_expr(target_index);
            if (it != T_INT) {
                throw TenetError::at_pos("数组下标必须是 int，实际为 " + it,
                                         target_index->pos);
            }
            pop_reg("x10");
            load_slot("x11", ref.dyn_len_off);
            emit_bounds_check_dyn("x10", "x11");
            push_reg("x10");  // 保存下标，跨过右值求值
            int buf = alloc_scratch(slots);
            pack_expr_to_buffer(buf, ref.elem, value);
            pop_reg("x10");
            emit_dyn_struct_elem_base(ref.base_off, slots, "x10");
            for (int k = 0; k < slots; ++k) {
                load_slot("x9", buf - 8 * k);
                store_reg_offset("x9", "x14", 8 * k);
            }
            return "void";
        }
        if (auto ci = const_index(target_index)) {
            if (*ci < 0 || *ci >= ref.len) {
                throw TenetError::at_pos("数组下标 " + std::to_string(*ci) + " 越界（长度 " +
                                             std::to_string(ref.len) + "）",
                                         target_index->pos);
            }
            int buf = alloc_scratch(slots);
            pack_expr_to_buffer(buf, ref.elem, value);
            for (int k = 0; k < slots; ++k) {
                load_slot("x9", buf - 8 * k);
                store_slot("x9", ref.base_off + ref.stride * ((int)*ci * slots + k));
            }
            return "void";
        }
        std::string it = gen_expr(target_index);
        if (it != T_INT) {
            throw TenetError::at_pos("数组下标必须是 int，实际为 " + it, target_index->pos);
        }
        pop_reg("x10");
        emit_bounds_check(ref.len, "x10");
        push_reg("x10");  // 保存下标，跨过右值求值
        int buf = alloc_scratch(slots);
        pack_expr_to_buffer(buf, ref.elem, value);
        pop_reg("x10");
        emit_struct_elem_base(ref.base_off, slots, "x10", ref.stride);
        for (int k = 0; k < slots; ++k) {
            load_slot("x9", buf - 8 * k);
            store_reg_offset("x9", "x14", ref.stride * k);
        }
        return "void";
    }

    // ---- S3c-3c：固定嵌套数组 array<array<T, N>, M>（仅局部变量）----
    //
    // 扁平布局 [M*N x i64]：外层元素 i 的内层元素 j 位于 base + 8*(i*N + j)。
    // 下标读写都做编译期（常量下标）或运行时（动态下标）边界检查：
    // 先检查外层 M，再检查内层 N。

    struct NestedIndexParts {
        ExprPtr base;   // 数组变量节点 / struct 固定数组字段
        ExprPtr outer;  // 外层下标表达式
        ExprPtr inner;  // 内层下标表达式
    };

    /// `a[i][j]` / `s.m[i][j]` → (base, outer=i, inner=j)；结构不符返回 false。
    static bool nested_index_parts(const ExprPtr& e, NestedIndexParts& out) {
        if (!e || e->kind != Expr::Kind::Index) return false;
        if (!e->lhs || e->lhs->kind != Expr::Kind::Index) return false;
        if (!e->lhs->lhs ||
            (e->lhs->lhs->kind != Expr::Kind::Var &&
             e->lhs->lhs->kind != Expr::Kind::Field)) {
            return false;
        }
        out.base = e->lhs->lhs;
        out.outer = e->lhs->rhs;
        out.inner = e->rhs;
        return true;
    }

    struct NestedRef {
        NestedArrayInfo info;
        int base_off = 0;  // 外层元素 0 的槽位
        int stride = 8;    // struct 固定数组字段为 -8
    };

    /// S3d：解析 struct 固定数组字段的嵌套数组信息（允许 bool 叶子）。
    NestedArrayInfo nested_array_info_field(const std::string& ty,
                                            const Position& pos) const {
        if (!is_array(ty)) {
            throw TenetError::at_pos("`" + ty + "` 不是数组", pos);
        }
        auto inner = array_elem(ty);
        if (!inner.has_value() || !is_array(*inner)) {
            throw TenetError::at_pos(
                "`" + ty + "` 不是嵌套数组（需要 `array<array<T, N>, M>`）", pos);
        }
        auto inner_len = array_decl_len(*inner);
        if (!inner_len.has_value()) {
            throw TenetError::at_pos(
                "嵌套数组内层必须是固定长度 `array<T, N>`，实际 `" + *inner + "`", pos);
        }
        auto elem = array_elem(*inner);
        if (!elem.has_value()) {
            throw TenetError::at_pos("嵌套数组内层不是数组：`" + *inner + "`", pos);
        }
        if (*elem != T_INT && *elem != T_FLOAT && *elem != T_BOOL) {
            throw TenetError::at_pos(
                "固定嵌套数组字段的元素只支持 int/float/bool，实际 `" + *elem + "`", pos);
        }
        NestedArrayInfo info;
        info.ty = ty;
        info.inner_ty = *inner;
        info.outer_len = *array_decl_len(ty);
        info.inner_len = *inner_len;
        info.elem = *elem;
        info.slots = info.inner_len;
        return info;
    }

    /// 解析嵌套数组：局部数组变量，或 struct 变量的固定嵌套数组字段
    /// （`s.m[i][j]`，字段按低地址展开，stride = -8）。
    NestedRef nested_ref(const ExprPtr& base, const Position& pos, bool writing) {
        NestedRef ref;
        if (base && base->kind == Expr::Kind::Field) {
            ArrayRef ar = array_ref(base, pos, writing);
            if (!is_array(ar.elem)) {
                throw TenetError::at_pos(
                    "`" + base->name + "` 不是嵌套数组（需要 `array<array<T, N>, M>`），"
                    "不能取两层下标",
                    base->pos);
            }
            ref.info = nested_array_info_field(ar.ty, pos);
            ref.base_off = ar.base_off;
            ref.stride = ar.stride;
            return ref;
        }
        if (!base || base->kind != Expr::Kind::Var) {
            throw TenetError::at_pos(
                std::string("v1 只支持对数组变量") + (writing ? "写" : "取") + "两层下标",
                base ? base->pos : pos);
        }
        std::string ty = scoped_var_type(base->name, base->pos);
        if (!is_array(ty)) {
            throw TenetError::at_pos(
                "`" + base->name + "` 不是数组，不能" + (writing ? "写" : "取") + "下标",
                base->pos);
        }
        std::string elem = array_elem_checked(ty, pos);
        if (!is_array(elem)) {
            throw TenetError::at_pos(
                "`" + base->name + "` 不是嵌套数组（需要 `array<array<T, N>, M>`），不能取两层下标",
                base->pos);
        }
        ref.info = nested_array_info(ty, pos);
        ref.base_off = lookup_slot(base->name, base->pos);
        ref.stride = 8;
        return ref;
    }

    /// 常量下标越界错误（编译期）。
    [[noreturn]] static void throw_nested_oob(bool outer, int64_t idx, int len,
                                              const Position& pos) {
        throw TenetError::at_pos(
            std::string(outer ? "外层" : "内层") + "数组下标 " + std::to_string(idx) +
                " 越界（长度 " + std::to_string(len) + "）",
            pos);
    }

    /// 求一个下标：常量则做编译期越界检查（返回 false，不生成代码）；
    /// 动态则求值、运行时边界检查并压栈（返回 true）。
    bool eval_nested_index(const ExprPtr& idx, bool outer, int len) {
        if (auto ci = const_index(idx)) {
            if (*ci < 0 || *ci >= len) throw_nested_oob(outer, *ci, len, idx->pos);
            return false;
        }
        std::string t = gen_expr(idx);
        if (t != T_INT) {
            throw TenetError::at_pos("数组下标必须是 int，实际为 " + t, idx->pos);
        }
        pop_reg("x10");
        emit_bounds_check(len, "x10");
        push_reg("x10");
        return true;
    }

    /// 计算 a[outer][inner] 的槽地址到 x14；动态下标已按 outer、inner 顺序压栈。
    void emit_nested_addr(const NestedRef& ref, bool outer_dyn, bool inner_dyn,
                          int flat_const) {
        lea_slot("x14", ref.base_off);
        if (!outer_dyn && !inner_dyn) {
            if (flat_const != 0) {
                if (flat_const <= 4095) {
                    emit(std::string(ref.stride < 0 ? "sub " : "add ") +
                         "x14, x14, #" + std::to_string(flat_const * 8));
                } else {
                    emit_mov_const("x17", (int64_t)flat_const * 8);
                    emit(std::string(ref.stride < 0 ? "sub " : "add ") +
                         "x14, x14, x17");
                }
            }
            return;
        }
        // 弹出动态下标（压栈顺序 outer → inner，故逆序弹出）。
        std::string oreg, ireg;
        if (inner_dyn) {
            pop_reg("x10");
            ireg = "x10";
        }
        if (outer_dyn) {
            if (inner_dyn) {
                pop_reg("x11");
                oreg = "x11";
            } else {
                pop_reg("x10");
                oreg = "x10";
            }
        }
        if (outer_dyn) {
            emit_flat_slot_index("x17", oreg, ref.info.inner_len, flat_const);
            if (inner_dyn) emit("add x17, x17, " + ireg);
        } else {
            emit("mov x17, " + ireg);
            if (flat_const != 0) {
                if (flat_const <= 4095) {
                    emit("add x17, x17, #" + std::to_string(flat_const));
                } else {
                    emit_mov_const("x15", flat_const);
                    emit("add x17, x17, x15");
                }
            }
        }
        emit(std::string(ref.stride < 0 ? "sub " : "add ") +
             "x14, x14, x17, lsl #3");
    }

    std::string gen_nested_index_read(const ExprPtr& e) {
        NestedIndexParts p;
        if (!nested_index_parts(e, p)) {
            throw TenetError::at_pos("内部错误：不是嵌套数组下标读", e->pos);
        }
        NestedRef ref = nested_ref(p.base, e->pos, false);
        const NestedArrayInfo& info = ref.info;
        int flat = 0;
        bool outer_dyn = eval_nested_index(p.outer, true, info.outer_len);
        if (!outer_dyn) flat += (int)*const_index(p.outer) * info.inner_len;
        bool inner_dyn = eval_nested_index(p.inner, false, info.inner_len);
        if (!inner_dyn) flat += (int)*const_index(p.inner);
        std::string reg = is_float(info.elem) ? "d9" : "x9";
        if (!outer_dyn && !inner_dyn) {
            load_slot(reg, ref.base_off + ref.stride * flat);
        } else {
            emit_nested_addr(ref, outer_dyn, inner_dyn, flat);
            emit(std::string(is_float(info.elem) ? "ldr d9, " : "ldr x9, ") +
                 "[x14, #0]");
        }
        push_reg(reg);
        return info.elem;
    }

    std::string gen_nested_index_write(const ExprPtr& target, const ExprPtr& value) {
        NestedIndexParts p;
        if (!nested_index_parts(target, p)) {
            throw TenetError::at_pos("内部错误：不是嵌套数组下标写", target->pos);
        }
        NestedRef ref = nested_ref(p.base, target->pos, true);
        const NestedArrayInfo& info = ref.info;
        int flat = 0;
        bool outer_dyn = eval_nested_index(p.outer, true, info.outer_len);
        if (!outer_dyn) flat += (int)*const_index(p.outer) * info.inner_len;
        bool inner_dyn = eval_nested_index(p.inner, false, info.inner_len);
        if (!inner_dyn) flat += (int)*const_index(p.inner);
        std::string vt = gen_expr(value);
        if (vt != info.elem) {
            throw TenetError::at_pos(
                "嵌套数组元素赋值类型不匹配：需要 " + info.elem + "，实际 " + vt, value->pos);
        }
        std::string reg = is_float(info.elem) ? "d9" : "x9";
        pop_reg(reg);
        if (!outer_dyn && !inner_dyn) {
            store_slot(reg, ref.base_off + ref.stride * flat);
        } else {
            emit_nested_addr(ref, outer_dyn, inner_dyn, flat);
            emit(std::string(is_float(info.elem) ? "str d9, " : "str x9, ") +
                 "[x14, #0]");
        }
        push_reg(reg);
        return info.elem;
    }

    /// 把一个内层数组值（`[..]` 字面量或同类型内层数组变量）写进扁平槽 dst_off。
    void store_nested_inner(const NestedArrayInfo& info, int dst_off,
                            const ExprPtr& expr, int outer_i) {
        if (expr->kind == Expr::Kind::Array) {
            if ((int)expr->args.size() != info.inner_len) {
                throw TenetError::at_pos(
                    "内层数组长度不匹配：需要 " + std::to_string(info.inner_len) + "，实际 " +
                        std::to_string(expr->args.size()),
                    expr->pos);
            }
            for (int k = 0; k < info.inner_len; ++k) {
                std::string vt = gen_expr(expr->args[k]);
                if (vt != info.elem) {
                    throw TenetError::at_pos(
                        "嵌套数组元素 " + std::to_string(outer_i) + "[" + std::to_string(k) +
                            "] 类型不匹配：需要 " + info.elem + "，实际 " + vt,
                        expr->args[k]->pos);
                }
                std::string reg = is_float(info.elem) ? "d9" : "x9";
                pop_reg(reg);
                store_slot(reg, dst_off + 8 * k);
            }
            return;
        }
        if (expr->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(expr->name, expr->pos);
            if (src_ty != info.inner_ty) {
                throw TenetError::at_pos(
                    "嵌套数组元素 " + std::to_string(outer_i) + " 类型不匹配：需要 " +
                        info.inner_ty + "，实际 " + src_ty,
                    expr->pos);
            }
            int src_off = lookup_slot(expr->name, expr->pos);
            for (int k = 0; k < info.inner_len; ++k) {
                load_slot("x9", src_off + 8 * k);
                store_slot("x9", dst_off + 8 * k);
            }
            return;
        }
        throw TenetError::at_pos(
            "嵌套数组元素必须是内层数组字面量 `[...]` 或同类型内层数组变量", expr->pos);
    }

    /// let a: array<array<T,N>,M> = [[...], ...]; / let b = a;（深拷贝）
    void emit_nested_array_init(const Stmt& stmt, const std::string& ty) {
        NestedArrayInfo info = nested_array_info(ty, stmt.pos);
        int base_off = lookup_slot(stmt.name, stmt.pos);
        int len = lookup_array_len(stmt.name, stmt.pos);
        const ExprPtr& v = stmt.value;
        if (v->kind == Expr::Kind::Array) {
            if ((int)v->args.size() != len) {
                throw TenetError::at_pos("数组初始化长度不匹配：需要 " + std::to_string(len) +
                                             "，实际 " + std::to_string(v->args.size()),
                                         v->pos);
            }
            for (int i = 0; i < len; ++i) {
                store_nested_inner(info, base_off + 8 * i * info.inner_len, v->args[i], i);
            }
            return;
        }
        if (v->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(v->name, v->pos);
            if (src_ty != ty) {
                throw TenetError::at_pos(
                    "`" + stmt.name + "` 需要 " + ty + "，但 `" + v->name + "` 是 " + src_ty,
                    v->pos);
            }
            int src_off = lookup_slot(v->name, v->pos);
            copy_struct_array_slots(base_off, src_off, len * info.inner_len);
            return;
        }
        if (v->kind == Expr::Kind::Call) {
            // S3c-3d：返回固定嵌套数组的调用：把 sret 缓冲按 M*N 总槽数拷进本地数组。
            std::string rt = gen_expr(v);
            if (rt != ty) {
                throw TenetError::at_pos(
                    "`" + stmt.name + "` 需要 " + ty + "，但调用返回 " + rt, v->pos);
            }
            pop_reg("x10");
            copy_array_from_reg(base_off, "x10", len * info.inner_len);
            return;
        }
        throw TenetError::at_pos(
            "`" + stmt.name +
                "` 的嵌套数组初始化必须是 `[[...], ...]` 字面量、同类型数组变量或返回数组的调用",
            v->pos);
    }

    /// a = [[...], ...] / a = b（同类型深拷贝）
    void assign_nested_array(const std::string& dst, const std::string& dst_ty,
                             const ExprPtr& value, const Position& pos) {
        NestedArrayInfo info = nested_array_info(dst_ty, pos);
        int dst_off = lookup_slot(dst, pos);
        int len = lookup_array_len(dst, pos);
        if (value->kind == Expr::Kind::Array) {
            if ((int)value->args.size() != len) {
                throw TenetError::at_pos("数组赋值长度不匹配：需要 " + std::to_string(len) +
                                             "，实际 " + std::to_string(value->args.size()),
                                         value->pos);
            }
            for (int i = 0; i < len; ++i) {
                store_nested_inner(info, dst_off + 8 * i * info.inner_len, value->args[i], i);
            }
            return;
        }
        if (value->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(value->name, value->pos);
            if (src_ty != dst_ty) {
                throw TenetError::at_pos(
                    "数组赋值类型不匹配：需要 " + dst_ty + "，右侧是 " + src_ty, value->pos);
            }
            int src_off = lookup_slot(value->name, value->pos);
            copy_struct_array_slots(dst_off, src_off, len * info.inner_len);
            return;
        }
        if (value->kind == Expr::Kind::Call) {
            // S3c-3d：a = make()：把 sret 返回缓冲按 M*N 总槽数逐槽拷进本地数组。
            std::string rt = gen_expr(value);
            if (rt != dst_ty) {
                throw TenetError::at_pos(
                    "数组赋值类型不匹配：需要 " + dst_ty + "，右侧调用返回 " + rt, value->pos);
            }
            pop_reg("x10");
            copy_array_from_reg(dst_off, "x10", len * info.inner_len);
            return;
        }
        throw TenetError::at_pos(
            "数组赋值必须是同类型嵌套数组变量、同长度 `[[...], ...]` 字面量或返回数组的调用",
            value->pos);
    }

    // ---- S3c-3e：动态嵌套数组 array<array<T>>（外层/内层均动态，内层标量）----
    //
    // 外层堆元素是内层 descriptor 的三个 i64 槽 [data, len, cap]，外层 stride = 24。
    // a[i][j] 读写：外层按 len 运行时检查，内层按内层 descriptor 的 len 运行时检查；
    // a[i] 整体取值/赋值暂不支持。

    struct DynamicNestedRef {
        std::string ty;        // array<array<T>>
        std::string inner_ty;  // array<T>
        std::string elem;      // T
        DynArrayInfo di;       // 外层描述符槽位
    };

    /// 解析动态嵌套数组变量（仅当类型确为 array<array<T>> 时）。
    DynamicNestedRef dynamic_nested_ref(const ExprPtr& base, const Position& pos) {
        if (!base || base->kind != Expr::Kind::Var) {
            throw TenetError::at_pos("v1 只支持对数组变量取两层下标", pos);
        }
        std::string ty = scoped_var_type(base->name, base->pos);
        if (!is_dynamic_nested_array(ty)) {
            throw TenetError::at_pos(
                "`" + base->name + "` 不是动态嵌套数组（需要 `array<array<T>>`）", base->pos);
        }
        DynamicNestedRef ref;
        ref.ty = ty;
        ref.inner_ty = *array_elem(ty);
        ref.elem = dynamic_nested_scalar_elem(ty, pos);
        ref.di = lookup_dyn(base->name, base->pos);
        return ref;
    }

    /// 若 base 是动态嵌套数组变量，返回其类型；否则 nullopt（交给固定嵌套路径）。
    std::optional<std::string> dynamic_nested_base_type(const ExprPtr& base,
                                                        const Position& pos) {
        if (!base || base->kind != Expr::Kind::Var) return std::nullopt;
        std::string ty = var_type(base->name, base->pos);
        if (!is_dynamic_nested_array(ty)) return std::nullopt;
        dynamic_nested_scalar_elem(ty, pos);
        return ty;
    }

    /// 外层下标求值 + 运行时边界检查 + 行 descriptor 地址压栈。
    void emit_dynamic_nested_row(const DynamicNestedRef& ref, const ExprPtr& outer) {
        std::string ot = gen_expr(outer);
        if (ot != T_INT) {
            throw TenetError::at_pos("数组下标必须是 int，实际为 " + ot, outer->pos);
        }
        pop_reg("x10");
        load_slot("x11", ref.di.len);
        emit_bounds_check_dyn("x10", "x11");
        load_slot("x12", ref.di.data);
        emit_mov_const("x13", 24);
        emit("mul x10, x10, x13");
        emit("add x10, x12, x10");
        push_reg("x10");  // 行 descriptor 指针，跨内层下标求值保存
    }

    /// 弹出内层下标（x11）与行 descriptor 指针（x10），检查内层 len 后
    /// 把内层 data 指针放 x14。返回内层标量类型。
    std::string emit_dynamic_nested_inner_addr(const DynamicNestedRef& ref,
                                               const ExprPtr& inner) {
        std::string it = gen_expr(inner);
        if (it != T_INT) {
            throw TenetError::at_pos("数组下标必须是 int，实际为 " + it, inner->pos);
        }
        pop_reg("x11");
        pop_reg("x10");
        emit("ldr x15, [x10, #8]");   // 内层 len
        emit_bounds_check_dyn("x11", "x15");
        emit("ldr x14, [x10, #0]");   // 内层 data
        return ref.elem;
    }

    std::string gen_dynamic_nested_index_read(const ExprPtr& e) {
        NestedIndexParts p;
        if (!nested_index_parts(e, p)) {
            throw TenetError::at_pos("内部错误：不是动态嵌套数组下标读", e->pos);
        }
        DynamicNestedRef ref = dynamic_nested_ref(p.base, e->pos);
        emit_dynamic_nested_row(ref, p.outer);
        std::string elem = emit_dynamic_nested_inner_addr(ref, p.inner);
        std::string reg = is_float(elem) ? "d9" : "x9";
        emit(std::string(is_float(elem) ? "ldr d9, " : "ldr x9, ") +
             "[x14, x11, lsl #3]");
        push_reg(reg);
        return elem;
    }

    std::string gen_dynamic_nested_index_write(const ExprPtr& target, const ExprPtr& value) {
        NestedIndexParts p;
        if (!nested_index_parts(target, p)) {
            throw TenetError::at_pos("内部错误：不是动态嵌套数组下标写", target->pos);
        }
        DynamicNestedRef ref = dynamic_nested_ref(p.base, target->pos);
        emit_dynamic_nested_row(ref, p.outer);
        std::string elem = emit_dynamic_nested_inner_addr(ref, p.inner);
        // 内层 data 指针与下标跨右值求值保存；右值不能破坏它们。
        push_reg("x14");
        push_reg("x11");
        std::string vt = gen_expr(value);
        if (vt != elem) {
            throw TenetError::at_pos(
                "动态嵌套数组元素赋值类型不匹配：需要 " + elem + "，实际 " + vt, value->pos);
        }
        if (is_float(elem)) {
            pop_reg("d9");
            emit("fmov x9, d9");
        } else {
            pop_reg("x9");
        }
        // 先恢复内层 data 指针与下标，再写值（值求值期间寄存器可能被破坏）。
        pop_reg("x11");
        pop_reg("x14");
        emit("str x9, [x14, x11, lsl #3]");
        push_reg(is_float(elem) ? "d9" : "x9");
        return elem;
    }

    /// S3d 深路径：把任意数组的第 idx 个元素基址算进 reg（默认 x14）。
    /// 固定数组支持编译期常量下标；动态数组常量下标也做运行时 len 检查。
    void emit_any_array_elem_base(const ArrayRef& ref, const ExprPtr& idx,
                                  const Position& pos, const std::string& reg = "x14") {
        int slots = array_elem_slots(ref.ty, pos);
        if (ref.dynamic) {
            std::string it = gen_expr(idx);
            if (it != T_INT) {
                throw TenetError::at_pos("数组下标必须是 int，实际为 " + it, idx->pos);
            }
            pop_reg("x10");
            load_slot("x11", ref.dyn_len_off);
            emit_bounds_check_dyn("x10", "x11");
            load_slot(reg, ref.base_off);
            emit_flat_slot_index("x17", "x10", slots, 0);
            emit("add " + reg + ", " + reg + ", x17, lsl #3");
            return;
        }
        if (auto ci = const_index(idx)) {
            if (*ci < 0 || *ci >= ref.len) {
                throw TenetError::at_pos("数组下标 " + std::to_string(*ci) + " 越界（长度 " +
                                             std::to_string(ref.len) + "）",
                                         idx->pos);
            }
            lea_slot(reg, ref.base_off + ref.stride * ((int)*ci * slots));
            return;
        }
        std::string it = gen_expr(idx);
        if (it != T_INT) {
            throw TenetError::at_pos("数组下标必须是 int，实际为 " + it, idx->pos);
        }
        pop_reg("x10");
        emit_bounds_check(ref.len, "x10");
        lea_slot(reg, ref.base_off);
        emit_flat_slot_index("x17", "x10", slots, 0);
        emit(std::string(ref.stride < 0 ? "sub " : "add ") + reg + ", " + reg +
             ", x17, lsl #3");
    }

    /// 解析 `arr[i].f[j]` 的字段数组信息；返回 false 表示不是该形状。
    bool deep_array_field_info(const DeepArrayFieldRef& d, const Position& pos,
                               ArrayRef& ar, LayoutEntry& entry, int& field_len,
                               std::string& felem) {
        ar = array_ref(d.base, pos, false);
        if (!is_struct(ar.elem)) {
            throw TenetError::at_pos(
                "`" + d.base->name + "` 不是 array<struct>，不能对元素取字段 `" +
                    d.field_path + "`",
                pos);
        }
        auto it = layout_entry(ar.elem, d.field_path);
        if (!it.has_value()) {
            throw TenetError::at_pos(
                "struct `" + ar.elem + "` 没有字段 `" + d.field_path + "`", pos);
        }
        entry = *it;
        if (!is_array(entry.ty)) {
            throw TenetError::at_pos(
                "字段 `" + d.field_path + "` 不是数组，不能取下标", pos);
        }
        auto len = array_decl_len(entry.ty);
        if (!len.has_value()) {
            throw TenetError::at_pos(
                "字段 `" + d.field_path + "` 是动态数组，不能取下标", pos);
        }
        field_len = *len;
        auto elem = array_elem(entry.ty);
        if (!elem.has_value()) {
            throw TenetError::at_pos("字段 `" + d.field_path + "` 不是数组", pos);
        }
        if (is_struct(*elem) || is_array(*elem)) {
            throw TenetError::at_pos(
                "字段数组 `" + d.field_path + "` 的元素不能整体读取；请继续访问到标量",
                pos);
        }
        felem = *elem;
        return true;
    }

    /// 把 `arr[i].f[j]` 的槽地址算进 x14（i/j 均支持常量或运行时下标）。
    void emit_deep_array_field_addr(const DeepArrayFieldRef& d, const ArrayRef& ar,
                                    const LayoutEntry& entry, int field_len,
                                    const Position& pos) {
        emit_any_array_elem_base(ar, d.elem_index, pos);
        if (auto ci = const_index(d.field_index)) {
            if (*ci < 0 || *ci >= field_len) {
                throw TenetError::at_pos("数组下标 " + std::to_string(*ci) + " 越界（长度 " +
                                             std::to_string(field_len) + "）",
                                         d.field_index->pos);
            }
            int flat = entry.offset + (int)*ci;
            if (flat != 0) {
                if (flat <= 4095) {
                    emit(std::string(ar.stride < 0 ? "sub " : "add ") +
                         "x14, x14, #" + std::to_string(flat * 8));
                } else {
                    emit_mov_const("x17", (int64_t)flat * 8);
                    emit(std::string(ar.stride < 0 ? "sub " : "add ") +
                         "x14, x14, x17");
                }
            }
            return;
        }
        push_reg("x14");  // 元素基址跨字段下标求值保存
        std::string it = gen_expr(d.field_index);
        if (it != T_INT) {
            throw TenetError::at_pos("数组下标必须是 int，实际为 " + it,
                                     d.field_index->pos);
        }
        pop_reg("x11");
        pop_reg("x14");
        emit_bounds_check(field_len, "x11");
        if (entry.offset != 0) {
            if (entry.offset <= 4095) {
                emit(std::string(ar.stride < 0 ? "sub " : "add ") +
                     "x14, x14, #" + std::to_string(entry.offset * 8));
            } else {
                emit_mov_const("x17", (int64_t)entry.offset * 8);
                emit(std::string(ar.stride < 0 ? "sub " : "add ") +
                     "x14, x14, x17");
            }
        }
        emit(std::string(ar.stride < 0 ? "sub " : "add ") +
             "x14, x14, x11, lsl #3");
    }

    std::string gen_deep_array_field_read(const DeepArrayFieldRef& d, const Position& pos) {
        ArrayRef ar;
        LayoutEntry entry;
        int field_len = 0;
        std::string felem;
        deep_array_field_info(d, pos, ar, entry, field_len, felem);
        emit_deep_array_field_addr(d, ar, entry, field_len, pos);
        std::string reg = is_float(felem) ? "d9" : "x9";
        emit("ldr " + reg + ", [x14, #0]");
        push_reg(reg);
        return felem;
    }

    std::string gen_deep_array_field_write(const DeepArrayFieldRef& d, const ExprPtr& value,
                                           const Position& pos) {
        ArrayRef ar;
        LayoutEntry entry;
        int field_len = 0;
        std::string felem;
        deep_array_field_info(d, pos, ar, entry, field_len, felem);
        emit_deep_array_field_addr(d, ar, entry, field_len, pos);
        push_reg("x14");  // 目标地址跨右值求值保存
        std::string vt = gen_expr(value);
        if (vt != felem) {
            throw TenetError::at_pos("字段数组元素赋值类型不匹配：需要 " + felem +
                                         "，实际 " + vt,
                                     value->pos);
        }
        std::string reg = is_float(felem) ? "d9" : "x9";
        pop_reg(reg);
        pop_reg("x14");
        emit("str " + reg + ", [x14, #0]");
        push_reg(reg);
        return felem;
    }

    std::string gen_index_read(const ExprPtr& e) {
        DeepArrayFieldRef deep;
        if (deep_array_field_parts(e, deep)) {
            return gen_deep_array_field_read(deep, e->pos);
        }
        ArrayRef ref = array_ref(e->lhs, e->pos, false);
        if (is_struct(ref.elem)) {
            throw TenetError::at_pos(
                "array<struct> 元素不能整体读取为 struct 值；请访问标量字段（如 a[i].x）",
                e->pos);
        }
        if (is_array(ref.elem)) {
            throw TenetError::at_pos(
                "嵌套数组元素不能整体取值；请用 a[i][j] 访问内层元素", e->pos);
        }
        if (ref.dynamic) {
            std::string it = gen_expr(e->rhs);
            if (it != T_INT) {
                throw TenetError::at_pos("数组下标必须是 int，实际为 " + it, e->rhs->pos);
            }
            pop_reg("x10");
            load_slot("x11", ref.dyn_len_off);
            emit_bounds_check_dyn("x10", "x11");
            load_slot("x14", ref.base_off);
            std::string reg = is_float(ref.elem) ? "d9" : "x9";
            emit((is_float(ref.elem) ? "ldr d9, [x14, x10, lsl #3]"
                                     : "ldr x9, [x14, x10, lsl #3]"));
            push_reg(reg);
            return ref.elem;
        }
        if (auto ci = const_index(e->rhs)) {
            if (*ci < 0 || *ci >= ref.len) {
                throw TenetError::at_pos("数组下标 " + std::to_string(*ci) + " 越界（长度 " +
                                             std::to_string(ref.len) + "）",
                                         e->rhs->pos);
            }
            std::string reg = is_float(ref.elem) ? "d9" : "x9";
            load_slot(reg, ref.base_off + ref.stride * (int)*ci);
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
        if (ref.stride > 0) {
            load_indexed(reg, ref.base_off, "x10");
        } else {
            lea_slot("x16", ref.base_off, "x17");
            emit("sub x16, x16, x10, lsl #3");
            emit("ldr " + reg + ", [x16]");
        }
        push_reg(reg);
        return ref.elem;
    }

    std::string gen_index_write(const ExprPtr& e, const ExprPtr& target) {
        DeepArrayFieldRef deep;
        if (deep_array_field_parts(target, deep)) {
            return gen_deep_array_field_write(deep, e->value, target->pos);
        }
        ArrayRef ref = array_ref(target->lhs, target->pos, true);
        if (is_struct(ref.elem)) {
            return gen_struct_array_elem_write(target->rhs, ref, e->value, target->pos);
        }
        if (is_array(ref.elem)) {
            throw TenetError::at_pos(
                "嵌套数组元素不能整体赋值；请用 a[i][j] 写内层元素", target->pos);
        }
        std::string reg = is_float(ref.elem) ? "d9" : "x9";
        if (ref.dynamic) {
            std::string it = gen_expr(target->rhs);
            if (it != T_INT) {
                throw TenetError::at_pos("数组下标必须是 int，实际为 " + it, target->rhs->pos);
            }
            pop_reg("x10");
            load_slot("x11", ref.dyn_len_off);
            emit_bounds_check_dyn("x10", "x11");
            push_reg("x10");  // 保存下标，跨过右值求值
            std::string vt = gen_expr(e->value);
            if (vt != ref.elem) {
                throw TenetError::at_pos("数组元素赋值类型不匹配：需要 " + ref.elem +
                                             "，实际 " + vt,
                                         e->value->pos);
            }
            pop_reg(reg);
            pop_reg("x10");
            load_slot("x14", ref.base_off);
            emit(std::string("str ") + (is_float(ref.elem) ? "d9" : "x9") +
                 ", [x14, x10, lsl #3]");
            push_reg(reg);
            return ref.elem;
        }
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
            store_slot(reg, ref.base_off + ref.stride * (int)*ci);
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
        if (ref.stride > 0) {
            store_indexed(reg, ref.base_off, "x10");
        } else {
            lea_slot("x16", ref.base_off, "x17");
            emit("sub x16, x16, x10, lsl #3");
            emit("str " + reg + ", [x16]");
        }
        push_reg(reg);
        return ref.elem;
    }

    /// struct 数组的逐槽值拷贝：total = len*slots，元素 0 字段 0 在最低地址。
    void copy_struct_array_slots(int dst_off, int src_off, int total) {
        for (int k = 0; k < total; ++k) {
            load_slot("x9", src_off + 8 * k);
            store_slot("x9", dst_off + 8 * k);
        }
    }

    /// let a: array<P, 2> = [P { ... }, ...]; / let b = a;（深拷贝）
    void emit_struct_array_init(const Stmt& stmt, const std::string& ty) {
        std::string elem = array_elem_checked(ty, stmt.pos);
        int base_off = lookup_slot(stmt.name, stmt.pos);
        int len = lookup_array_len(stmt.name, stmt.pos);
        int slots = array_elem_slots(ty, stmt.pos);
        const ExprPtr& v = stmt.value;
        if (v->kind == Expr::Kind::Array) {
            if ((int)v->args.size() != len) {
                throw TenetError::at_pos("数组初始化长度不匹配：需要 " + std::to_string(len) +
                                             "，实际 " + std::to_string(v->args.size()),
                                         v->pos);
            }
            int buf = alloc_scratch(slots);
            for (size_t i = 0; i < v->args.size(); ++i) {
                const ExprPtr& arg = v->args[i];
                if (arg->kind == Expr::Kind::StructLit && arg->name != elem) {
                    throw TenetError::at_pos("数组元素 " + std::to_string(i) +
                                                 " 类型不匹配：需要 " + elem + "，字面量是 " +
                                                 arg->name,
                                             arg->pos);
                }
                if (arg->kind == Expr::Kind::Var) {
                    std::string vt = scoped_var_type(arg->name, arg->pos);
                    if (vt != elem) {
                        throw TenetError::at_pos("数组元素 " + std::to_string(i) +
                                                     " 类型不匹配：需要 " + elem + "，实际 " +
                                                     vt,
                                                 arg->pos);
                    }
                }
                pack_expr_to_buffer(buf, elem, arg);
                for (int k = 0; k < slots; ++k) {
                    load_slot("x9", buf - 8 * k);
                    store_slot("x9", base_off + 8 * ((int)i * slots + k));
                }
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
            copy_struct_array_slots(base_off, src_off, len * slots);
            return;
        }
        if (v->kind == Expr::Kind::Call) {
            // S3c-3d：返回固定 array<S, N> 的调用：把 sret 缓冲按总槽数拷进本地数组。
            std::string rt = gen_expr(v);
            if (rt != ty) {
                throw TenetError::at_pos(
                    "`" + stmt.name + "` 需要 " + ty + "，但调用返回 " + rt, v->pos);
            }
            pop_reg("x10");
            copy_array_from_reg(base_off, "x10", len * slots);
            return;
        }
        throw TenetError::at_pos(
            "`" + stmt.name +
                "` 的 array<struct> 初始化必须是字面量、同类型数组变量或返回数组的调用",
            v->pos);
    }

    /// b = [P { ... }, ...] / b = a（深拷贝）
    void assign_struct_array(const std::string& dst, const std::string& dst_ty,
                             const ExprPtr& value, const Position& pos) {
        std::string elem = array_elem_checked(dst_ty, pos);
        int len = lookup_array_len(dst, pos);
        int dst_off = lookup_slot(dst, pos);
        int slots = array_elem_slots(dst_ty, pos);
        if (value->kind == Expr::Kind::Array) {
            if ((int)value->args.size() != len) {
                throw TenetError::at_pos("数组赋值长度不匹配：需要 " + std::to_string(len) +
                                             "，实际 " + std::to_string(value->args.size()),
                                         value->pos);
            }
            int buf = alloc_scratch(slots);
            for (size_t i = 0; i < value->args.size(); ++i) {
                const ExprPtr& arg = value->args[i];
                if (arg->kind == Expr::Kind::StructLit && arg->name != elem) {
                    throw TenetError::at_pos("数组元素 " + std::to_string(i) +
                                                 " 类型不匹配：需要 " + elem + "，字面量是 " +
                                                 arg->name,
                                             arg->pos);
                }
                if (arg->kind == Expr::Kind::Var) {
                    std::string vt = scoped_var_type(arg->name, arg->pos);
                    if (vt != elem) {
                        throw TenetError::at_pos("数组元素 " + std::to_string(i) +
                                                     " 类型不匹配：需要 " + elem + "，实际 " +
                                                     vt,
                                                 arg->pos);
                    }
                }
                pack_expr_to_buffer(buf, elem, arg);
                for (int k = 0; k < slots; ++k) {
                    load_slot("x9", buf - 8 * k);
                    store_slot("x9", dst_off + 8 * ((int)i * slots + k));
                }
            }
            return;
        }
        if (value->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(value->name, value->pos);
            if (src_ty != dst_ty) {
                throw TenetError::at_pos(
                    "数组赋值类型不匹配：需要 " + dst_ty + "，右侧是 " + src_ty, value->pos);
            }
            int src_off = lookup_slot(value->name, value->pos);
            copy_struct_array_slots(dst_off, src_off, len * slots);
            return;
        }
        if (value->kind == Expr::Kind::Call) {
            // S3c-3d：b = make()：把 sret 返回缓冲按总槽数逐槽拷进本地数组。
            std::string rt = gen_expr(value);
            if (rt != dst_ty) {
                throw TenetError::at_pos(
                    "数组赋值类型不匹配：需要 " + dst_ty + "，右侧调用返回 " + rt, value->pos);
            }
            pop_reg("x10");
            copy_array_from_reg(dst_off, "x10", len * slots);
            return;
        }
        throw TenetError::at_pos(
            "数组赋值必须是同类型数组变量、同长度字面量或返回数组的调用", value->pos);
    }

    void emit_array_init(const Stmt& stmt, const std::string& ty) {
        std::string elem0 = array_elem_checked(ty, stmt.pos);
        if (is_struct(elem0)) {
            emit_struct_array_init(stmt, ty);
            return;
        }
        if (is_array(elem0)) {
            emit_nested_array_init(stmt, ty);
            return;
        }
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
            if (!is_array(src_ty) || array_elem(src_ty) != elem) {
                throw TenetError::at_pos("`" + stmt.name + "` 需要 " + ty + "，但 `" +
                                             v->name + "` 是 " + src_ty,
                                         v->pos);
            }
            int src_len = lookup_array_len(v->name, v->pos);
            if (src_len != len) {
                throw TenetError::at_pos("数组初始化长度不匹配：需要 " + std::to_string(len) +
                                             "，实际 " + std::to_string(src_len),
                                         v->pos);
            }
            int src_off = lookup_slot(v->name, v->pos);
            copy_array_elems(base_off, src_off, len, elem);
            return;
        }
        if (v->kind == Expr::Kind::Call) {
            // S3b：返回数组的调用：先把 sret 缓冲指针解包到本地数组槽。
            std::string rt = gen_expr(v);
            if (!is_array(rt) || array_elem(rt) != elem ||
                array_decl_len(rt) != std::optional<int>(len)) {
                throw TenetError::at_pos(
                    "`" + stmt.name + "` 需要 " + ty + "，但调用返回 " + rt, v->pos);
            }
            pop_reg("x10");
            copy_array_from_reg(base_off, "x10", len);
            return;
        }
        throw TenetError::at_pos(
            "`" + stmt.name + "` 的数组初始化必须是 `[...]` 或同类型数组变量"
            "（或返回数组的调用）",
            v->pos);
    }

    /// a = [..]（同长度）或 a = b（逐元素值拷贝）。
    void assign_array(const std::string& dst, const std::string& dst_ty, const ExprPtr& value,
                      const Position& pos) {
        std::string elem0 = array_elem_checked(dst_ty, pos);
        if (is_struct(elem0)) {
            assign_struct_array(dst, dst_ty, value, pos);
            return;
        }
        if (is_array(elem0)) {
            assign_nested_array(dst, dst_ty, value, pos);
            return;
        }
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
            if (is_dynamic_array(src_ty)) {
                throw TenetError::at_pos(
                    "定长数组 `" + dst + "`（" + dst_ty + "）不能整体赋值为动态数组 `" +
                        value->name + "`（" + src_ty + "）",
                    value->pos);
            }
            if (!is_array(src_ty) || array_elem(src_ty) != elem) {
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
        if (value->kind == Expr::Kind::Call) {
            // S3b：a = make()：把返回数组从 sret 缓冲逐元素值拷贝到本地数组。
            std::string rt = gen_expr(value);
            if (!is_array(rt) || array_elem(rt) != elem ||
                array_decl_len(rt) != std::optional<int>(len)) {
                throw TenetError::at_pos(
                    "数组赋值类型不匹配：需要 " + dst_ty + "，右侧调用返回 " + rt, value->pos);
            }
            pop_reg("x10");
            copy_array_from_reg(dst_off, "x10", len);
            return;
        }
        throw TenetError::at_pos(
            "数组赋值必须是同类型数组变量或同长度字面量（或返回数组的调用）", value->pos);
    }

    // ---- array S3c：动态数组 array<T>（堆缓冲 {data,len,cap}）----
    //
    // 局部变量 + 函数参数/返回值（S3c-2/S3c-3a）。元素按 8 字节槽存堆上（int/float/bool，
    // float 用位模式），只 malloc/free，无 RC/GC。
    // ABI：参数传 3 槽描述符指针（被调函数入口深拷贝）；返回值走隐藏 sret 指针（x0）。
    // 实参/return 支持变量、字面量、返回动态数组的调用：字面量/调用结果先构造临时
    // 描述符，return 时把 data/len/cap 转移给 sret（不 free），实参在调用返回后只 free
    // 临时堆缓冲；调用方 let/赋值从调用结果接管。

    const DynArrayInfo& lookup_dyn(const std::string& name, const Position& pos) const {
        for (auto it = scope_stack_.rbegin(); it != scope_stack_.rend(); ++it) {
            auto f = dyn_maps_[*it].find(name);
            if (f != dyn_maps_[*it].end()) return f->second;
        }
        throw TenetError::at_pos("`" + name + "` 不是动态数组（array<T> 变量或参数）", pos);
    }

    /// 在帧尾分配 3 个临时描述符槽（整体赋值时先构造新值再用）。
    DynArrayInfo alloc_dyn_scratch() {
        int base = alloc_scratch(3);
        return DynArrayInfo{base, base - 8, base - 16};
    }

    /// 调用点/实参描述符：3 个临时槽按 data/len/cap 从低地址到高地址排列，
    /// 与 callee 的 `[desc]` / `[desc, #8]` / `[desc, #16]` 访问顺序一致。
    DynArrayInfo alloc_dyn_desc() {
        int base = alloc_array_scratch(3);
        return DynArrayInfo{base, base + 8, base + 16};
    }

    /// S3c-2 动态数组参数入口深拷贝：调用方只传描述符指针，本地按 cap 重新 malloc
    /// 并拷贝 len 个元素；此后函数内 push/改元素都不影响调用方（参数值语义）。
    /// S3c-3b-2：元素为 struct 时按 stride=slots*8 拷贝 len*slots 个 8 字节槽。
    /// 入口第一阶段已把描述符指针暂存到 di.data。
    void deep_copy_dynamic_param(const DynArrayInfo& di, const std::string& ty,
                                 const Position& pos) {
        array_elem_checked(ty, pos);
        if (is_dynamic_nested_array(ty)) {
            // S3c-3e：参数入口逐内层深拷贝。先把调用方描述符复制到 3 个临时槽，
            // 再走与 let 变量初始化相同的嵌套深拷贝（本地数组与调用方完全独立）。
            DynArrayInfo src = alloc_dyn_scratch();
            load_slot("x10", di.data);  // 调用方描述符指针
            load_reg_offset("x9", "x10", 0);
            store_slot("x9", src.data);
            load_reg_offset("x9", "x10", 8);
            store_slot("x9", src.len);
            load_reg_offset("x9", "x10", 16);
            store_slot("x9", src.cap);
            nested_deep_copy_from_slots(di, ty, src.data, src.len, src.cap);
            return;
        }
        int slots = array_elem_slots(ty, pos);
        load_slot("x10", di.data);  // 调用方描述符指针
        load_reg_offset("x11", "x10", 0);   // data
        load_reg_offset("x12", "x10", 8);   // len
        load_reg_offset("x13", "x10", 16);  // cap
        push_reg("x11");
        push_reg("x12");
        push_reg("x13");
        if (slots == 1) {
            emit("lsl x0, x13, #3");
        } else {
            emit_mov_const("x0", slots);
            emit("mul x0, x13, x0");
            emit("lsl x0, x0, #3");
        }
        emit("bl _malloc");
        pop_reg("x13");
        pop_reg("x12");
        pop_reg("x11");
        store_slot("x0", di.data);
        store_slot("x12", di.len);
        store_slot("x13", di.cap);
        // 深拷贝 len*slots 个 8 字节槽：新缓冲与调用方完全独立。
        emit("mov x14, x0");
        emit("mov x15, x11");
        if (slots == 1) {
            emit("mov x17, x12");
        } else {
            emit_mov_const("x16", slots);
            emit("mul x17, x12, x16");
        }
        emit("mov x16, #0");
        std::string loop = new_label("dyn.param.copy");
        std::string end = new_label("dyn.param.copy.end");
        label(loop);
        emit("cmp x16, x17");
        emit("b.hs " + end);
        emit("ldr x9, [x15, x16, lsl #3]");
        emit("str x9, [x14, x16, lsl #3]");
        emit("add x16, x16, #1");
        emit("b " + loop);
        label(end);
    }

    /// 把临时动态数组的 data/len/cap 写入调用方 sret 描述符，并清空临时槽
    /// （所有权转移：不 free 堆缓冲，之后 drop 只会 free(NULL)）。
    void transfer_dyn_slots_to_sret(const DynArrayInfo& di) {
        load_slot("x15", sret_slot_);
        load_slot("x9", di.data);
        store_reg_offset("x9", "x15", 0);
        load_slot("x9", di.len);
        store_reg_offset("x9", "x15", 8);
        load_slot("x9", di.cap);
        store_reg_offset("x9", "x15", 16);
        store_slot("xzr", di.data);
        store_slot("xzr", di.len);
        store_slot("xzr", di.cap);
    }

    /// S3c-2/S3c-3a 动态数组返回值：把 data/len/cap 写入调用方 sret 描述符，
    /// 并清空临时描述符（所有权转移，不 free）。
    /// - 变量：转移本地描述符并清空，函数退出时 drop 只会 free(NULL)
    /// - 字面量：先构造临时动态数组（malloc + 填元素），再把描述符转移给 sret
    /// - 调用：把内层调用返回的 sret 描述符复制给 sret，并清空内层临时描述符
    void transfer_dynamic_return(const Stmt& stmt) {
        if (!stmt.expr) {
            throw TenetError::at_pos("函数 `" + fn_ + "` 返回 " + *current_ret_ +
                                         "，return 必须带值",
                                     stmt.pos);
        }
        const Position& pos = stmt.expr->pos;
        if (stmt.expr->kind == Expr::Kind::Var) {
            const std::string& name = stmt.expr->name;
            std::string vt = scoped_var_type(name, pos);
            if (vt != *current_ret_) {
                throw TenetError::at_pos(
                    "返回类型不匹配：需要 " + *current_ret_ + "，实际 " + vt, pos);
            }
            transfer_dyn_slots_to_sret(lookup_dyn(name, pos));
        } else if (stmt.expr->kind == Expr::Kind::Array) {
            DynArrayInfo tmp = alloc_dyn_desc();
            init_dynamic_into(tmp, *current_ret_, stmt.expr);
            transfer_dyn_slots_to_sret(tmp);
        } else if (stmt.expr->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(stmt.expr);
            if (!is_dynamic_array(rt) || rt != *current_ret_) {
                throw TenetError::at_pos(
                    "返回类型不匹配：需要 " + *current_ret_ + "，调用返回 " + rt, pos);
            }
            // gen_expr 已压入内层调用的 sret 描述符指针：复制进本函数的 sret，
            // 再清空内层描述符（所有权已转移，避免重复 free）。
            pop_reg("x10");
            load_slot("x15", sret_slot_);
            load_reg_offset("x9", "x10", 0);
            store_reg_offset("x9", "x15", 0);
            load_reg_offset("x9", "x10", 8);
            store_reg_offset("x9", "x15", 8);
            load_reg_offset("x9", "x10", 16);
            store_reg_offset("x9", "x15", 16);
            store_reg_offset("xzr", "x10", 0);
            store_reg_offset("xzr", "x10", 8);
            store_reg_offset("xzr", "x10", 16);
        } else {
            throw TenetError::at_pos(
                "动态数组 return 只支持变量、字面量或返回动态数组的调用", pos);
        }
        drop_all_scopes();
        emit("b L." + fn_ + ".ret");
        terminated_ = true;
    }

    /// 从调用返回的 sret 描述符接管堆缓冲（临时描述符随即清零，之后不再 free 它）。
    void take_dynamic_from_desc(const DynArrayInfo& di, const std::string& desc_reg) {
        load_reg_offset("x14", desc_reg, 0);
        store_slot("x14", di.data);
        load_reg_offset("x14", desc_reg, 8);
        store_slot("x14", di.len);
        load_reg_offset("x14", desc_reg, 16);
        store_slot("x14", di.cap);
        store_reg_offset("xzr", desc_reg, 0);
        store_reg_offset("xzr", desc_reg, 8);
        store_reg_offset("xzr", desc_reg, 16);
    }

    /// free 堆缓冲并把描述符清零。free(NULL) 合法，因此重复 drop / 已清零的槽位都安全。
    /// S3c-3e：动态嵌套数组先逐内层 free(data)，再 free 外层。
    void drop_dyn(const DynArrayInfo& di) {
        if (di.nested) {
            std::string clear = new_label("dnest.drop.clear");
            load_slot("x9", di.data);
            emit("cmp x9, #0");
            emit("b.eq " + clear);
            int s_data = alloc_scratch(1);
            int s_len = alloc_scratch(1);
            int s_idx = alloc_scratch(1);
            store_slot("x9", s_data);
            load_slot("x9", di.len);
            store_slot("x9", s_len);
            store_slot("xzr", s_idx);
            std::string loop = new_label("dnest.drop.loop");
            std::string after = new_label("dnest.drop.after");
            label(loop);
            load_slot("x9", s_idx);
            load_slot("x10", s_len);
            emit("cmp x9, x10");
            emit("b.hs " + after);
            // 外层行地址 = data + idx*24；free 内层 data 指针。
            emit_mov_const("x11", 24);
            emit("mul x10, x9, x11");
            load_slot("x11", s_data);
            emit("add x11, x11, x10");
            emit("ldr x0, [x11, #0]");
            push_reg("x11");  // 行指针跨 _free 保存（外层缓冲不会被内层 free 破坏）
            emit("bl _free");
            pop_reg("x11");
            emit("str xzr, [x11, #0]");
            load_slot("x9", s_idx);
            emit("add x9, x9, #1");
            store_slot("x9", s_idx);
            emit("b " + loop);
            label(after);
            load_slot("x0", s_data);
            emit("bl _free");
            label(clear);
            emit("mov x9, #0");
            store_slot("x9", di.data);
            store_slot("x9", di.len);
            store_slot("x9", di.cap);
            return;
        }
        load_slot("x0", di.data);
        emit("bl _free");
        emit("mov x9, #0");
        store_slot("x9", di.data);
        store_slot("x9", di.len);
        store_slot("x9", di.cap);
    }

    /// drop 单个块作用域里的所有动态数组（按声明逆序，确定性输出）。
    void emit_drop_scope(int scope_idx) {
        std::vector<const DynArrayInfo*> vars;
        vars.reserve(dyn_maps_[scope_idx].size());
        for (const auto& [name, di] : dyn_maps_[scope_idx]) {
            (void)name;
            vars.push_back(&di);
        }
        // 槽位越靠低地址声明越晚：按 data 升序 = 声明逆序。
        std::sort(vars.begin(), vars.end(), [](const DynArrayInfo* a, const DynArrayInfo* b) {
            return a->data < b->data;
        });
        for (const DynArrayInfo* di : vars) drop_dyn(*di);
    }

    /// 离开函数：drop 当前作用域栈上的全部动态数组（由内向外）。
    void drop_all_scopes() {
        for (size_t i = scope_stack_.size(); i-- > 0;) emit_drop_scope(scope_stack_[i]);
    }

    /// break 用：从栈顶向下 drop 到（含）第 depth-1 层作用域。
    void emit_drop_scopes_from(size_t depth) {
        if (depth == 0) return;
        for (size_t i = scope_stack_.size(); i-- > depth - 1;) {
            emit_drop_scope(scope_stack_[i]);
        }
    }

    /// 运行时边界检查：idx >= len（无符号，顺带挡住负数）时打印错误并 exit(1)。
    void emit_bounds_check_dyn(const std::string& idx_reg, const std::string& len_reg) {
        emit("cmp " + idx_reg + ", " + len_reg);
        std::string fail = new_label("dbounds.fail");
        std::string ok = new_label("dbounds.ok");
        emit("b.hs " + fail);
        emit("b " + ok);
        label(fail);
        emit("mov x0, " + idx_reg);
        emit("mov x1, " + len_reg);
        emit("bl _tenet_bounds_fail");
        label(ok);
    }

    /// 运行时按 8 字节槽拷贝 count 个槽（dst/src/count 为寄存器）。
    /// 使用 x13 作计数器、x11 作数据暂存；dst/src/count 不得是 x11/x13。
    void emit_copy_words_runtime(const std::string& dst, const std::string& src,
                                 const std::string& count) {
        std::string loop = new_label("copy.words");
        std::string end = new_label("copy.words.end");
        emit("mov x13, #0");
        label(loop);
        emit("cmp x13, " + count);
        emit("b.hs " + end);
        emit("ldr x11, [" + src + ", x13, lsl #3]");
        emit("str x11, [" + dst + ", x13, lsl #3]");
        emit("add x13, x13, #1");
        emit("b " + loop);
        label(end);
    }

    /// S3c-3b-2：动态 array<struct> 初始化。堆缓冲按 stride=slots*8 存放扁平字段槽。
    /// 字面量：cap = max(n, 4)；变量：按源 cap 深拷贝 len*slots 个槽；调用：接管 sret。
    void init_dynamic_struct_into(const DynArrayInfo& di, const std::string& ty,
                                  const ExprPtr& value) {
        std::string elem = array_elem_checked(ty, value->pos);
        int slots = array_elem_slots(ty, value->pos);
        if (value->kind == Expr::Kind::Array) {
            int n = (int)value->args.size();
            int cap = std::max(n, 4);  // 空数组也分配 cap=4
            emit_mov_const("x0", (int64_t)cap * slots * 8);
            emit("bl _malloc");
            store_slot("x0", di.data);
            emit_mov_const("x9", n);
            store_slot("x9", di.len);
            emit_mov_const("x9", cap);
            store_slot("x9", di.cap);
            int buf = alloc_scratch(slots);
            for (int i = 0; i < n; ++i) {
                const ExprPtr& e = value->args[i];
                if (e->kind == Expr::Kind::StructLit && e->name != elem) {
                    throw TenetError::at_pos("数组元素 " + std::to_string(i) +
                                                 " 类型不匹配：需要 " + elem + "，字面量是 " +
                                                 e->name,
                                             e->pos);
                }
                if (e->kind == Expr::Kind::Var) {
                    std::string vt = scoped_var_type(e->name, e->pos);
                    if (vt != elem) {
                        throw TenetError::at_pos("数组元素 " + std::to_string(i) +
                                                     " 类型不匹配：需要 " + elem + "，实际 " + vt,
                                                 e->pos);
                    }
                }
                pack_expr_to_buffer(buf, elem, e);
                load_slot("x14", di.data);
                for (int k = 0; k < slots; ++k) {
                    load_slot("x9", buf - 8 * k);
                    store_reg_offset("x9", "x14", 8 * (i * slots + k));
                }
            }
            return;
        }
        if (value->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(value->name, value->pos);
            if (!is_dynamic_array(src_ty)) {
                throw TenetError::at_pos(
                    "动态数组初始化需要同类型 `array<T>` 变量，`" + value->name + "` 是 " +
                        src_ty,
                    value->pos);
            }
            if (src_ty != ty) {
                throw TenetError::at_pos(
                    "动态数组类型不匹配：需要 " + ty + "，`" + value->name + "` 是 " + src_ty,
                    value->pos);
            }
            const DynArrayInfo src = lookup_dyn(value->name, value->pos);
            // cap / len 跨 malloc 保存（调用会破坏 x0-x18）。
            load_slot("x9", src.cap);
            push_reg("x9");
            load_slot("x9", src.len);
            push_reg("x9");
            load_slot("x10", src.cap);
            if (slots == 1) {
                emit("lsl x0, x10, #3");
            } else {
                emit_mov_const("x0", slots);
                emit("mul x0, x10, x0");
                emit("lsl x0, x0, #3");
            }
            emit("bl _malloc");
            store_slot("x0", di.data);
            pop_reg("x9");
            store_slot("x9", di.len);
            pop_reg("x9");
            store_slot("x9", di.cap);
            // 深拷贝 len*slots 个槽：新缓冲与源完全独立。
            load_slot("x14", src.data);
            load_slot("x9", di.len);
            load_slot("x15", di.data);
            if (slots == 1) {
                emit("mov x10, x9");
            } else {
                emit_mov_const("x10", slots);
                emit("mul x10, x9, x10");
            }
            emit_copy_words_runtime("x15", "x14", "x10");
            return;
        }
        if (value->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(value);
            if (!is_dynamic_array(rt)) {
                throw TenetError::at_pos(
                    "动态数组 `" + ty + "` 不能用返回 " + rt + " 的调用初始化", value->pos);
            }
            if (rt != ty) {
                throw TenetError::at_pos(
                    "动态数组类型不匹配：需要 " + ty + "，调用返回 " + rt, value->pos);
            }
            pop_reg("x10");
            take_dynamic_from_desc(di, "x10");
            return;
        }
        throw TenetError::at_pos(
            "`" + ty + "` 初始化必须是 `[...]` 字面量、同类型动态数组变量或返回数组的调用",
            value->pos);
    }

    /// S3c-3e：动态嵌套数组深拷贝。src_* 是源描述符的三个栈槽偏移：
    /// 外层按源 cap malloc（cap*24 字节），逐内层 malloc(cap*8) 并拷贝 len 个标量槽。
    /// 新数组与源完全独立；外层元素是内层 descriptor [data, len, cap]。
    void nested_deep_copy_from_slots(const DynArrayInfo& di, const std::string& ty,
                                     int src_data, int src_len, int src_cap) {
        dynamic_nested_scalar_elem(ty, Position());
        // 源 cap/len 跨 _malloc 保存（调用会破坏 x0-x18）。
        load_slot("x9", src_cap);
        push_reg("x9");
        load_slot("x9", src_len);
        push_reg("x9");
        load_slot("x10", src_cap);
        emit_mov_const("x11", 24);
        emit("mul x0, x10, x11");
        emit("bl _malloc");
        pop_reg("x9");
        store_slot("x9", di.len);
        pop_reg("x9");
        store_slot("x9", di.cap);
        store_slot("x0", di.data);

        // 循环状态全部放帧尾 scratch：_malloc/_free 会破坏 caller-saved 寄存器。
        int s_idx = alloc_scratch(1);
        int s_len = alloc_scratch(1);
        int s_src = alloc_scratch(1);
        int s_dst = alloc_scratch(1);
        int s_isrc = alloc_scratch(1);
        int s_ilen = alloc_scratch(1);
        int s_icap = alloc_scratch(1);
        int s_idst = alloc_scratch(1);
        load_slot("x9", src_data);
        store_slot("x9", s_src);
        load_slot("x9", di.len);
        store_slot("x9", s_len);
        load_slot("x9", di.data);
        store_slot("x9", s_dst);
        store_slot("xzr", s_idx);
        std::string loop = new_label("dnest.copy");
        std::string end = new_label("dnest.copy.end");
        label(loop);
        load_slot("x9", s_idx);
        load_slot("x10", s_len);
        emit("cmp x9, x10");
        emit("b.hs " + end);
        // 源行 / 目标行地址 = base + idx*24。
        emit_mov_const("x12", 24);
        emit("mul x10, x9, x12");
        load_slot("x11", s_src);
        emit("add x11, x11, x10");
        load_slot("x12", s_dst);
        emit("add x12, x12, x10");
        // 读内层 descriptor [data, len, cap]。
        emit("ldr x13, [x11, #0]");
        store_slot("x13", s_isrc);
        emit("ldr x13, [x11, #8]");
        store_slot("x13", s_ilen);
        emit("ldr x13, [x11, #16]");
        store_slot("x13", s_icap);
        // malloc(icap*8) + 拷贝 ilen 个标量槽。
        emit("lsl x0, x13, #3");
        emit("bl _malloc");
        store_slot("x0", s_idst);
        load_slot("x12", s_idst);
        load_slot("x10", s_isrc);
        load_slot("x9", s_ilen);
        emit_copy_words_runtime("x12", "x10", "x9");
        // 写回目标行 descriptor。
        load_slot("x9", s_idx);
        emit_mov_const("x10", 24);
        emit("mul x10, x9, x10");
        load_slot("x11", s_dst);
        emit("add x11, x11, x10");
        load_slot("x9", s_idst);
        emit("str x9, [x11, #0]");
        load_slot("x9", s_ilen);
        emit("str x9, [x11, #8]");
        load_slot("x9", s_icap);
        emit("str x9, [x11, #16]");
        load_slot("x9", s_idx);
        emit("add x9, x9, #1");
        store_slot("x9", s_idx);
        emit("b " + loop);
        label(end);
    }

    /// S3c-3e：`array<array<T>>` 初始化。外层堆元素是内层 descriptor（stride=24）。
    /// 字面量：cap = max(n, 4)，逐行构造内层动态数组后把 descriptor 搬进外层；
    /// 变量：逐内层深拷贝；调用：接管返回的 sret 描述符。
    void init_dynamic_nested_into(const DynArrayInfo& di, const std::string& ty,
                                  const ExprPtr& value) {
        std::string inner_ty = array_elem_checked(ty, value->pos);
        dynamic_nested_scalar_elem(ty, value->pos);
        if (value->kind == Expr::Kind::Array) {
            int n = (int)value->args.size();
            int cap = std::max(n, 4);
            emit_mov_const("x0", (int64_t)cap * 24);
            emit("bl _malloc");
            store_slot("x0", di.data);
            emit_mov_const("x9", n);
            store_slot("x9", di.len);
            emit_mov_const("x9", cap);
            store_slot("x9", di.cap);
            DynArrayInfo tmp = alloc_dyn_scratch();
            for (int i = 0; i < n; ++i) {
                const ExprPtr& row = value->args[i];
                if (row->kind != Expr::Kind::Array && row->kind != Expr::Kind::Var &&
                    row->kind != Expr::Kind::Call) {
                    throw TenetError::at_pos(
                        "嵌套数组第 " + std::to_string(i) +
                            " 个元素必须是内层数组字面量、同类型内层数组变量或返回数组的调用",
                        row->pos);
                }
                init_dynamic_into(tmp, inner_ty, row);
                load_slot("x14", di.data);
                int64_t off = (int64_t)i * 24;
                if (off != 0) {
                    if (off <= 4095) {
                        emit("add x14, x14, #" + std::to_string(off));
                    } else {
                        emit_mov_const("x15", off);
                        emit("add x14, x14, x15");
                    }
                }
                load_slot("x9", tmp.data);
                store_reg_offset("x9", "x14", 0);
                load_slot("x9", tmp.len);
                store_reg_offset("x9", "x14", 8);
                load_slot("x9", tmp.cap);
                store_reg_offset("x9", "x14", 16);
                // 内层堆所有权已转移给外层元素；清空临时描述符避免误用。
                store_slot("xzr", tmp.data);
                store_slot("xzr", tmp.len);
                store_slot("xzr", tmp.cap);
            }
            return;
        }
        if (value->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(value->name, value->pos);
            if (src_ty != ty) {
                throw TenetError::at_pos(
                    "动态嵌套数组类型不匹配：需要 " + ty + "，`" + value->name + "` 是 " +
                        src_ty,
                    value->pos);
            }
            const DynArrayInfo src = lookup_dyn(value->name, value->pos);
            nested_deep_copy_from_slots(di, ty, src.data, src.len, src.cap);
            return;
        }
        if (value->kind == Expr::Kind::Call) {
            std::string rt = gen_expr(value);
            if (rt != ty) {
                throw TenetError::at_pos(
                    "动态嵌套数组类型不匹配：需要 " + ty + "，调用返回 " + rt, value->pos);
            }
            pop_reg("x10");
            take_dynamic_from_desc(di, "x10");
            return;
        }
        throw TenetError::at_pos(
            "`" + ty +
                "` 初始化必须是 `[[...], ...]` 字面量、同类型动态嵌套数组变量或返回数组的调用",
            value->pos);
    }

    /// 把动态数组值（`[...]` 字面量 / 同类型动态数组变量）写入描述符槽。
    /// 字面量：cap = max(n, 4)；变量：按源 cap 分配新堆缓冲并深拷贝 len 个元素。
    /// S3c-3b-2：元素为 struct 时转 init_dynamic_struct_into（stride=slots*8）。
    /// S3c-3e：元素为动态数组时转 init_dynamic_nested_into（外层 stride=24）。
    void init_dynamic_into(const DynArrayInfo& di, const std::string& ty,
                           const ExprPtr& value) {
        if (!value) {
            throw TenetError::at_pos("`" + ty + "` 初始化缺失", Position());
        }
        std::string elem = array_elem_checked(ty, value->pos);
        if (is_struct(elem)) {
            init_dynamic_struct_into(di, ty, value);
            return;
        }
        if (is_array(elem)) {
            init_dynamic_nested_into(di, ty, value);
            return;
        }
        if (value->kind == Expr::Kind::Array) {
            int n = (int)value->args.size();
            int cap = std::max(n, 4);  // 空数组也分配 cap=4
            int64_t bytes = (int64_t)cap * 8;
            emit_mov_const("x0", bytes);
            emit("bl _malloc");
            store_slot("x0", di.data);
            emit_mov_const("x9", n);
            store_slot("x9", di.len);
            emit_mov_const("x9", cap);
            store_slot("x9", di.cap);
            for (int i = 0; i < n; ++i) {
                std::string vt = gen_expr(value->args[i]);
                if (vt != elem) {
                    throw TenetError::at_pos("数组元素 " + std::to_string(i) +
                                                 " 类型不匹配：需要 " + elem + "，实际 " + vt,
                                             value->args[i]->pos);
                }
                if (is_float(elem)) {
                    pop_reg("d9");
                    emit("fmov x9, d9");  // 8 字节位模式
                } else {
                    pop_reg("x9");
                }
                load_slot("x14", di.data);
                store_reg_offset("x9", "x14", 8 * i);
            }
            return;
        }
        if (value->kind == Expr::Kind::Var) {
            std::string src_ty = scoped_var_type(value->name, value->pos);
            if (!is_dynamic_array(src_ty)) {
                throw TenetError::at_pos(
                    "动态数组初始化需要同类型 `array<T>` 变量，`" + value->name + "` 是 " +
                        src_ty,
                    value->pos);
            }
            if (array_elem(src_ty) != elem) {
                throw TenetError::at_pos(
                    "动态数组类型不匹配：需要 " + ty + "，`" + value->name + "` 是 " + src_ty,
                    value->pos);
            }
            const DynArrayInfo src = lookup_dyn(value->name, value->pos);
            // cap / len 跨 malloc 保存（调用会破坏 x0-x18）。
            load_slot("x9", src.cap);
            push_reg("x9");
            load_slot("x9", src.len);
            push_reg("x9");
            load_slot("x10", src.cap);
            emit("lsl x0, x10, #3");
            emit("bl _malloc");
            store_slot("x0", di.data);
            pop_reg("x9");
            store_slot("x9", di.len);
            pop_reg("x9");
            store_slot("x9", di.cap);
            // 深拷贝：新缓冲与源完全独立。
            load_slot("x14", src.data);
            load_slot("x9", di.len);
            load_slot("x15", di.data);
            emit("mov x13, #0");
            std::string loop = new_label("dyn.copy");
            std::string end = new_label("dyn.copy.end");
            label(loop);
            emit("cmp x13, x9");
            emit("b.hs " + end);
            emit("ldr x11, [x14, x13, lsl #3]");
            emit("str x11, [x15, x13, lsl #3]");
            emit("add x13, x13, #1");
            emit("b " + loop);
            label(end);
            return;
        }
        if (value->kind == Expr::Kind::Call) {
            // S3c-2：返回动态数组的调用——接管 sret 描述符里的堆缓冲，
            // 临时描述符只是调用方栈槽，不 free；之后由本变量的 drop 释放堆缓冲。
            std::string rt = gen_expr(value);
            if (!is_dynamic_array(rt)) {
                throw TenetError::at_pos(
                    "动态数组 `" + ty + "` 不能用返回 " + rt + " 的调用初始化", value->pos);
            }
            if (rt != ty) {
                throw TenetError::at_pos(
                    "动态数组类型不匹配：需要 " + ty + "，调用返回 " + rt, value->pos);
            }
            pop_reg("x10");
            take_dynamic_from_desc(di, "x10");
            return;
        }
        throw TenetError::at_pos(
            "`array<T>` 初始化必须是 `[...]` 字面量或同类型动态数组变量", value->pos);
    }

    /// let a: array<T> = [...]; / let b = a;（深拷贝）
    void emit_dynamic_init(const Stmt& stmt, const std::string& ty) {
        const DynArrayInfo di = lookup_dyn(stmt.name, stmt.pos);
        init_dynamic_into(di, ty, stmt.value);
    }

    /// b = a / b = [...];：先构造新值（临时描述符），再 drop 旧 b，最后搬描述符。
    void assign_dynamic(const std::string& dst, const std::string& dst_ty,
                        const ExprPtr& value, const Position& pos) {
        if (value && value->kind == Expr::Kind::Var && value->name == dst) {
            return;  // b = b; 无操作（也不能先 drop 再拷自己）
        }
        const DynArrayInfo ddi = lookup_dyn(dst, pos);
        DynArrayInfo tmp = alloc_dyn_scratch();
        init_dynamic_into(tmp, dst_ty, value);
        drop_dyn(ddi);
        load_slot("x9", tmp.data);
        store_slot("x9", ddi.data);
        load_slot("x9", tmp.len);
        store_slot("x9", ddi.len);
        load_slot("x9", tmp.cap);
        store_slot("x9", ddi.cap);
    }

    /// push(a, x)：容量不足时 cap*2（空数组 cap=4），malloc 新缓冲、拷贝、free 旧缓冲。
    std::string gen_push(const std::vector<ExprPtr>& args, const Position& pos) {
        if (args.size() != 2) {
            throw TenetError::at_pos("`push` 需要两个参数：动态数组变量和值", pos);
        }
        if (!args[0] || args[0]->kind != Expr::Kind::Var) {
            throw TenetError::at_pos("`push` 第一个参数必须是动态数组变量",
                                     args[0] ? args[0]->pos : pos);
        }
        std::string ty = scoped_var_type(args[0]->name, args[0]->pos);
        if (!is_array(ty)) {
            throw TenetError::at_pos("`" + args[0]->name + "` 不是数组，不能 push",
                                     args[0]->pos);
        }
        if (!is_dynamic_array(ty)) {
            throw TenetError::at_pos("`" + args[0]->name + "` 是定长数组 " + ty +
                                         "，不能 push（push 只支持 array<T> 动态数组）",
                                     args[0]->pos);
        }
        std::string elem = array_elem_checked(ty, args[0]->pos);
        const DynArrayInfo di = lookup_dyn(args[0]->name, args[0]->pos);
        if (is_struct(elem)) {
            // S3c-3b-2：push(a, S { ... }) / push(a, s)：按 slots 个扁平槽追加。
            return gen_push_struct(di, ty, elem, args[1]);
        }
        if (is_array(elem)) {
            // S3c-3e：push(a, inner)：深拷贝内层数组后把 descriptor 追加到外层。
            return gen_push_nested(di, ty, elem, args[1]);
        }
        std::string vt = gen_expr(args[1]);
        if (vt != elem) {
            throw TenetError::at_pos("push 值类型不匹配：需要 " + elem + "，实际 " + vt,
                                     args[1]->pos);
        }
        if (is_float(elem)) {
            pop_reg("d9");
            emit("fmov x11, d9");
        } else {
            pop_reg("x11");
        }
        load_slot("x9", di.len);
        load_slot("x10", di.cap);
        emit("cmp x9, x10");
        std::string grow = new_label("dyn.grow");
        std::string after = new_label("dyn.grow.after");
        emit("b.eq " + grow);
        // 容量足够：data[len] = value; len += 1
        load_slot("x14", di.data);
        emit("str x11, [x14, x9, lsl #3]");
        emit("add x9, x9, #1");
        store_slot("x9", di.len);
        emit("b " + after);
        label(grow);
        // 扩容：newcap = cap*2（cap==0 时保底 4），malloc → 拷 len 个 → 写新元素 → free 旧。
        emit("add x12, x10, x10");
        emit("cmp x10, #0");
        emit("mov x13, #4");
        emit("csel x12, x13, x12, eq");
        push_reg("x9");   // len
        push_reg("x12");  // newcap
        push_reg("x11");  // value
        emit("lsl x0, x12, #3");
        emit("bl _malloc");
        pop_reg("x11");
        pop_reg("x12");
        pop_reg("x9");
        emit("mov x14, x0");        // 新缓冲
        load_slot("x15", di.data);  // 旧缓冲
        emit("mov x13, #0");
        std::string copy = new_label("dyn.grow.copy");
        std::string copy_end = new_label("dyn.grow.copy.end");
        label(copy);
        emit("cmp x13, x9");
        emit("b.hs " + copy_end);
        emit("ldr x10, [x15, x13, lsl #3]");
        emit("str x10, [x14, x13, lsl #3]");
        emit("add x13, x13, #1");
        emit("b " + copy);
        label(copy_end);
        emit("str x11, [x14, x9, lsl #3]");
        store_slot("x14", di.data);
        store_slot("x12", di.cap);
        emit("add x9, x9, #1");
        store_slot("x9", di.len);
        emit("mov x0, x15");
        emit("bl _free");
        label(after);
        return "void";
    }

    /// S3c-3b-2：push 一个 struct 元素。值先打包到栈上临时缓冲（slots 个槽），
    /// 容量不足时按 slots*8 字节扩容并搬运 len*slots 个槽，再追加新元素。
    std::string gen_push_struct(const DynArrayInfo& di, const std::string& ty,
                                const std::string& elem, const ExprPtr& value) {
        int slots = array_elem_slots(ty, value->pos);
        if (value->kind == Expr::Kind::StructLit && value->name != elem) {
            throw TenetError::at_pos(
                "push 值类型不匹配：需要 " + elem + "，字面量是 " + value->name, value->pos);
        }
        if (value->kind == Expr::Kind::Var) {
            std::string vt = scoped_var_type(value->name, value->pos);
            if (vt != elem) {
                throw TenetError::at_pos(
                    "push 值类型不匹配：需要 " + elem + "，实际 " + vt, value->pos);
            }
        }
        int buf = alloc_scratch(slots);
        pack_expr_to_buffer(buf, elem, value);
        load_slot("x9", di.len);
        load_slot("x10", di.cap);
        emit("cmp x9, x10");
        std::string grow = new_label("dyn.grow");
        std::string after = new_label("dyn.grow.after");
        emit("b.eq " + grow);
        // 容量足够：把临时缓冲的 slots 个槽写到 data[len*slots]。
        load_slot("x14", di.data);
        emit_flat_slot_index("x15", "x9", slots, 0);
        emit("add x14, x14, x15, lsl #3");
        for (int k = 0; k < slots; ++k) {
            load_slot("x12", buf - 8 * k);
            store_reg_offset("x12", "x14", 8 * k);
        }
        emit("add x9, x9, #1");
        store_slot("x9", di.len);
        emit("b " + after);
        label(grow);
        // 扩容：newcap = cap*2（cap==0 时保底 4），malloc → 拷 len*slots 槽 → free 旧缓冲。
        emit("add x12, x10, x10");
        emit("cmp x10, #0");
        emit("mov x13, #4");
        emit("csel x12, x13, x12, eq");
        push_reg("x9");   // len
        push_reg("x12");  // newcap
        if (slots == 1) {
            emit("lsl x0, x12, #3");
        } else {
            emit_mov_const("x0", slots);
            emit("mul x0, x12, x0");
            emit("lsl x0, x0, #3");
        }
        emit("bl _malloc");
        pop_reg("x12");
        pop_reg("x9");
        emit("mov x14, x0");        // 新缓冲
        load_slot("x15", di.data);  // 旧缓冲
        if (slots == 1) {
            emit("mov x10, x9");
        } else {
            emit_mov_const("x10", slots);
            emit("mul x10, x9, x10");
        }
        emit_copy_words_runtime("x14", "x15", "x10");
        store_slot("x14", di.data);
        store_slot("x12", di.cap);
        // free 旧缓冲会破坏调用者寄存器：先保存新 data 与旧 len。
        push_reg("x14");
        push_reg("x9");
        emit("mov x0, x15");
        emit("bl _free");
        pop_reg("x9");
        pop_reg("x14");
        // 新元素写到新缓冲末尾（旧 len*slots 处）。
        emit_flat_slot_index("x12", "x9", slots, 0);
        emit("add x12, x14, x12, lsl #3");
        for (int k = 0; k < slots; ++k) {
            load_slot("x11", buf - 8 * k);
            store_reg_offset("x11", "x12", 8 * k);
        }
        emit("add x9, x9, #1");
        store_slot("x9", di.len);
        label(after);
        return "void";
    }

    /// S3c-3e：push 一个内层动态数组。先把内层值构造到 3 槽临时描述符
    /// （变量深拷贝、字面量新建、调用结果接管），外层扩容后把 descriptor
    /// 追加到末尾；外层元素 stride = 3*8 = 24 字节，扩容 newcap = cap*2。
    std::string gen_push_nested(const DynArrayInfo& di, const std::string& ty,
                                const std::string& inner_ty, const ExprPtr& value) {
        dynamic_nested_scalar_elem(ty, value->pos);
        if (value->kind != Expr::Kind::Array && value->kind != Expr::Kind::Var &&
            value->kind != Expr::Kind::Call) {
            throw TenetError::at_pos(
                "push 的内层值必须是内层数组字面量、同类型内层数组变量或返回数组的调用",
                value->pos);
        }
        DynArrayInfo tmp = alloc_dyn_scratch();
        init_dynamic_into(tmp, inner_ty, value);
        load_slot("x9", di.len);
        load_slot("x10", di.cap);
        emit("cmp x9, x10");
        std::string grow = new_label("dyn.nested.grow");
        std::string after = new_label("dyn.nested.grow.after");
        emit("b.eq " + grow);
        emit("b " + after);
        label(grow);
        // 扩容：newcap = cap*2（cap==0 时保底 4），malloc newcap*24 → 拷 len*3 槽 → free 旧。
        emit("add x12, x10, x10");
        emit("cmp x10, #0");
        emit("mov x13, #4");
        emit("csel x12, x13, x12, eq");
        push_reg("x9");   // len
        push_reg("x12");  // newcap
        emit_mov_const("x11", 24);
        emit("mul x0, x12, x11");
        emit("bl _malloc");
        pop_reg("x12");
        pop_reg("x9");
        emit("mov x14, x0");        // 新缓冲
        load_slot("x15", di.data);  // 旧缓冲
        emit("mov x10, x9");
        emit_mov_const("x11", 3);
        emit("mul x10, x10, x11");
        emit_copy_words_runtime("x14", "x15", "x10");
        // free 旧缓冲会破坏 caller-saved 寄存器：先保存新 data / cap / len。
        push_reg("x14");
        push_reg("x12");
        push_reg("x9");
        emit("mov x0, x15");
        emit("bl _free");
        pop_reg("x9");
        pop_reg("x12");
        pop_reg("x14");
        store_slot("x14", di.data);
        store_slot("x12", di.cap);
        label(after);
        // 追加：data[len*3] = tmp descriptor。
        load_slot("x14", di.data);
        emit_mov_const("x12", 24);
        emit("mul x12, x9, x12");
        emit("add x14, x14, x12");
        load_slot("x9", tmp.data);
        emit("str x9, [x14, #0]");
        load_slot("x9", tmp.len);
        emit("str x9, [x14, #8]");
        load_slot("x9", tmp.cap);
        emit("str x9, [x14, #16]");
        // 内层堆所有权已转移给外层元素；清空临时描述符避免误用。
        store_slot("xzr", tmp.data);
        store_slot("xzr", tmp.len);
        store_slot("xzr", tmp.cap);
        load_slot("x9", di.len);
        emit("add x9, x9, #1");
        store_slot("x9", di.len);
        return "void";
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
            case Expr::Kind::Index: {
                NestedIndexParts np;
                if (nested_index_parts(e, np)) {
                    if (dynamic_nested_base_type(np.base, e->pos).has_value()) {
                        return gen_dynamic_nested_index_read(e);
                    }
                    return gen_nested_index_read(e);
                }
                return gen_index_read(e);
            }
            case Expr::Kind::Array:
                throw TenetError::at_pos(
                    "数组字面量只能用于 let 初始化或整体赋值、函数实参或返回值", e->pos);
            case Expr::Kind::Field: {
                StructElemRef er;
                if (struct_elem_path(e, er)) return gen_struct_array_field_read(e);
                FieldRef ref = resolve_field(e, false);
                if (is_array(ref.ty)) {
                    throw TenetError::at_pos(
                        "struct 的固定数组字段 `" + ref.var + "." + ref.path +
                            "` 不能整体取值；请用下标（如 `" + ref.var + "." + ref.path +
                            "[0]`）",
                        e->pos);
                }
                int off = field_slot(ref.var, ref.path, e->pos);
                if (is_float(ref.ty)) {
                    load_slot("d9", off);
                    push_reg("d9");
                } else {
                    load_slot("x9", off);
                    push_reg("x9");
                }
                return ref.ty;
            }
            case Expr::Kind::StructLit:
                throw TenetError::at_pos(
                    "struct 字面量只能用于 let 初始化、函数参数/返回值或整体赋值", e->pos);
            case Expr::Kind::Assign: {
                const ExprPtr& target = e->lhs;
                if (!target) {
                    throw TenetError::at_pos("赋值左侧必须是变量、字段或数组元素", e->pos);
                }
                if (target->kind == Expr::Kind::Var) {
                    int off = lookup_slot(target->name, target->pos);
                    std::string t = var_type(target->name, target->pos);
                    if (is_array(t)) {
                        if (is_dynamic_array(t)) {
                            assign_dynamic(target->name, t, e->value, e->pos);
                        } else {
                            assign_array(target->name, t, e->value, e->pos);
                        }
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
                    NestedIndexParts np;
                    if (nested_index_parts(target, np)) {
                        if (dynamic_nested_base_type(np.base, target->pos).has_value()) {
                            return gen_dynamic_nested_index_write(target, e->value);
                        }
                        return gen_nested_index_write(target, e->value);
                    }
                    return gen_index_write(e, target);
                }
                if (target->kind == Expr::Kind::Field) {
                    StructElemRef er;
                    if (struct_elem_path(target, er)) {
                        return gen_struct_array_field_write(target, e->value);
                    }
                    FieldRef ref = resolve_field(target, true);
                    if (is_array(ref.ty)) {
                        // S3d：`s.a = [...]` / `s.a = 同类型数组变量` / `s.a = 返回数组的调用`
                        // 整体写入固定数组字段；下标写仍走 Index 路径。
                        int off = field_slot(ref.var, ref.path, target->pos);
                        store_fixed_array_value(off, -8, ref.ty, e->value,
                                                "struct `" + ref.var + "." + ref.path + "`");
                        return "void";
                    }
                    std::string vt = gen_expr(e->value);
                    if (vt != ref.ty) {
                        throw TenetError::at_pos("字段 `" + ref.path + "` 类型不匹配：需要 " +
                                                     ref.ty + "，实际 " + vt,
                                                 e->value->pos);
                    }
                    int off = field_slot(ref.var, ref.path, target->pos);
                    pop_reg(is_float(ref.ty) ? "d9" : "x9");
                    store_slot(is_float(ref.ty) ? "d9" : "x9", off);
                    push_reg(is_float(ref.ty) ? "d9" : "x9");
                    return ref.ty;
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
        if (a && a->kind == Expr::Kind::Index && a->lhs && a->lhs->kind == Expr::Kind::Var) {
            std::string base_ty = scoped_var_type(a->lhs->name, a->lhs->pos);
            if (is_dynamic_nested_array(base_ty)) {
                // S3c-3e：len(a[i]) 读内层 descriptor 的 len 槽（外层先做运行时检查）。
                DynamicNestedRef ref = dynamic_nested_ref(a->lhs, a->pos);
                emit_dynamic_nested_row(ref, a->rhs);
                pop_reg("x10");
                emit("ldr x9, [x10, #8]");
                push_reg("x9");
                return T_INT;
            }
        }
        if (!a || a->kind != Expr::Kind::Var) {
            throw TenetError::at_pos("`len` 参数必须是数组变量", a ? a->pos : pos);
        }
        std::string t = scoped_var_type(a->name, a->pos);
        if (!is_array(t)) {
            throw TenetError::at_pos("`" + a->name + "` 不是数组，不能取 len", a->pos);
        }
        if (is_dynamic_array(t)) {
            // S3c：动态数组长度运行时读取 len 槽。
            load_slot("x9", lookup_dyn(a->name, a->pos).len);
            push_reg("x9");
            return T_INT;
        }
        int len = lookup_array_len(a->name, a->pos);
        emit_int_const(len);
        push_reg("x9");
        return T_INT;
    }

    std::string gen_call(const std::string& callee, const std::vector<ExprPtr>& args,
                         const Position& pos) {
        if (callee == "print") return gen_print(args, pos);
        if (callee == "push") return gen_push(args, pos);
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
        bool ret_struct = sig.ret.has_value() && is_struct(*sig.ret);
        auto ret_len = sig.ret.has_value() ? array_decl_len(*sig.ret) : std::nullopt;
        bool ret_dynamic = sig.ret.has_value() && is_dynamic_array(*sig.ret);
        bool ret_composite = ret_struct || ret_len.has_value() || ret_dynamic;
        size_t base_pos = ret_composite ? 1 : 0;  // struct/array 返回值占隐藏第一参数 x0
        if (args.size() + base_pos > 8) {
            throw TenetError::at_pos(
                "函数 `" + callee +
                    "` 的参数位超过 8 个（sret 与 struct/array 指针也占参数位，x0-x7）",
                pos);
        }
        // 参数类型核对（print 除外）：期望类型 vs 实际类型。
        // 定长数组参数由 push_array_value / push_fixed_array_value 按元素类型 + 长度校验
        // （多槽固定数组：array<S, N> 与嵌套数组，元素按扁平槽）。
        // 动态数组参数由 push_dynamic_arg 校验（变量/字面量/返回动态数组的调用）。
        for (size_t i = 0; i < args.size(); ++i) {
            if (is_array(sig.params[i])) continue;
            std::string at = infer_type(args[i]).value_or("?");
            if (at != sig.params[i]) {
                throw TenetError::at_pos("函数 `" + callee + "` 参数 " + std::to_string(i) +
                                             " 类型不匹配：期望 " + sig.params[i] + "，实际 " + at,
                                         args[i]->pos);
            }
        }
        // struct/array 返回值：调用方先分配临时缓冲，地址作为隐藏第一参数传入。
        // S3c-2 动态数组返回值用 3 槽描述符（data/len/cap 递增）；先清零，
        // 被调函数异常落空时调用方接管的也是空描述符（free(NULL) 安全）。
        int sret_off = 0;
        if (ret_struct) {
            int n = struct_total_slots(*sig.ret);
            sret_off = alloc_scratch(n);
        } else if (ret_dynamic) {
            DynArrayInfo desc = alloc_dyn_desc();
            sret_off = desc.data;
            store_slot("xzr", desc.data);
            store_slot("xzr", desc.len);
            store_slot("xzr", desc.cap);
        } else if (ret_len.has_value()) {
            // S3b/S3c-3d：定长数组返回值在 sret 缓冲区里按总槽数存放
            // （array<S, N> 为 N*slots，嵌套数组为 M*N；标量数组即 N）。
            sret_off = alloc_array_scratch(*ret_len * array_elem_slots(*sig.ret, pos));
        }
        // 动态数组实参的临时堆缓冲（字面量/调用结果）：被调函数入口已深拷贝，
        // 调用返回后统一 free；描述符本身是栈槽，不 free。
        std::vector<DynArrayInfo> temp_dyn;
        for (size_t i = 0; i < args.size(); ++i) {
            if (is_struct(sig.params[i])) {
                push_struct_value(sig.params[i], args[i]);
            } else if (is_dynamic_array(sig.params[i])) {
                push_dynamic_arg(sig.params[i], args[i], temp_dyn);
            } else if (is_array(sig.params[i])) {
                // S3c-3d：struct 元素 / 嵌套数组实参走扁平槽缓冲；
                // 标量定长数组沿用 S3b 的逐元素路径。
                if (fixed_array_flat_slots(sig.params[i], args[i]->pos)) {
                    push_fixed_array_value(sig.params[i], args[i]);
                } else {
                    push_array_value(sig.params[i], args[i]);
                }
            } else {
                gen_expr(args[i]);
            }
        }
        for (int i = (int)args.size() - 1; i >= 0; --i) {
            size_t reg_pos = (size_t)i + base_pos;
            if (is_struct(sig.params[i]) || is_array(sig.params[i])) {
                pop_reg("x" + std::to_string(reg_pos));
            } else {
                pop_reg(is_float(sig.params[i]) ? "d" + std::to_string(reg_pos)
                                                : "x" + std::to_string(reg_pos));
            }
        }
        if (ret_composite) {
            lea_slot("x0", sret_off);
        }
        emit("bl _" + callee);
        // S3c-3a：被调函数入口已深拷贝，调用返回后只 free 字面量/调用结果实参的
        // 临时堆缓冲（描述符是栈槽，不 free）。标量返回值在 x0/d0，跨 _free
        // 调用先压栈保存；struct/array 返回值走 sret 缓冲，不占返回寄存器。
        if (!temp_dyn.empty()) {
            bool ret_scalar = sig.ret.has_value() && !ret_composite;
            bool ret_x = ret_scalar && !is_float(*sig.ret);
            bool ret_d = ret_scalar && is_float(*sig.ret);
            if (ret_x) push_reg("x0");
            if (ret_d) push_reg("d0");
            for (auto it = temp_dyn.rbegin(); it != temp_dyn.rend(); ++it) drop_dyn(*it);
            if (ret_x) pop_reg("x0");
            if (ret_d) pop_reg("d0");
        }
        if (!sig.ret.has_value()) return "void";
        if (ret_composite) {
            lea_slot("x9", sret_off);
            push_reg("x9");
            return *sig.ret;
        }
        if (is_float(*sig.ret)) {
            push_reg("d0");
        } else {
            push_reg("x0");
        }
        return *sig.ret;
    }

    // ---- print：标量 / struct / 定长与动态数组 ----
    //
    // 标量 print 仍沿用一个 printf 拼格式串（保持既有行为与 9 变参上限）；
    // 只要参数里出现 struct / 数组变量，就改用"多次 _printf"：每个片段一次调用，
    // 避免变参寄存器/栈槽与 aggregate 展开互相干扰。printf 仍是 Apple 变参约定：
    // 固定参数 fmt 在 x0，唯一的 8 字节变参放在 [sp]。
    //
    // aggregate 只支持直接打印变量：print(f()) / print([1,2]) / print(a[i]) 这类
    // 表达式明确报错。动态数组在运行时循环（下标存帧尾 scratch 槽，跨 printf 调用
    // 仍然有效）；定长数组/嵌套定长数组在编译期展开。

    /// 无变参 printf：fmt 地址放 x0。
    void printf_piece(const std::string& fmt) {
        std::string name = "L.pfmt." + std::to_string(str_c_++);
        data_string(fmt, name);
        emit("adrp x0, " + name + "@PAGE");
        emit("add x0, x0, " + name + "@PAGEOFF");
        emit("bl _printf");
    }

    /// 一个 64 位变参 printf：值先落 [sp]，再取 fmt 地址（Apple 变参约定）。
    /// float 也按 8 字节位模式放在同一个栈槽（与既有标量 print 一致）。
    void printf_piece1(const std::string& fmt, const std::string& reg) {
        std::string name = "L.pfmt." + std::to_string(str_c_++);
        data_string(fmt, name);
        emit("sub sp, sp, #16");
        emit("str " + reg + ", [sp]");
        emit("adrp x0, " + name + "@PAGE");
        emit("add x0, x0, " + name + "@PAGEOFF");
        emit("bl _printf");
        emit("add sp, sp, #16");
    }

    /// 打印寄存器里的标量（已按 64 位位模式载入的 int/float/bool/string）。
    /// bool 先 csel 成 "true"/"false" 指针，再按 %s 打印。
    void print_scalar_reg(const std::string& ty, const std::string& reg,
                          const Position& pos) {
        if (ty == T_INT) {
            printf_piece1("%lld", reg);
            return;
        }
        if (ty == T_FLOAT) {
            printf_piece1("%g", reg);
            return;
        }
        if (ty == T_STR) {
            printf_piece1("%s", reg);
            return;
        }
        if (ty == T_BOOL) {
            emit("cmp " + reg + ", #0");
            std::string tname = "L.bool.true." + std::to_string(str_c_++);
            std::string fname = "L.bool.false." + std::to_string(str_c_++);
            data_string("true", tname);
            data_string("false", fname);
            emit("adrp x16, " + tname + "@PAGE");
            emit("add x16, x16, " + tname + "@PAGEOFF");
            emit("adrp x17, " + fname + "@PAGE");
            emit("add x17, x17, " + fname + "@PAGEOFF");
            emit("csel x9, x16, x17, ne");
            printf_piece1("%s", "x9");
            return;
        }
        throw TenetError::at_pos("print 不支持该类型的值", pos);
    }

    /// 从 x29 相对槽位读一个标量并打印。
    void print_scalar_slot(const std::string& ty, int off, const Position& pos) {
        load_slot("x9", off);
        print_scalar_reg(ty, "x9", pos);
    }

    /// 打印寄存器基址 x10 指向的标量（struct 数组元素字段用）。
    void print_scalar_ptr(const std::string& ty, const std::string& base, int off,
                          const Position& pos) {
        load_reg_offset("x9", base, off);
        print_scalar_reg(ty, "x9", pos);
    }

    /// S3d：按扁平槽打印任意方向的固定数组（struct 字段/嵌套字段用）。
    /// `elem0_off` 为元素 0 槽位；`stride` 为元素间方向（局部 struct 字段 -8，
    /// packed 缓冲 +8）。
    void print_fixed_array_slots(const std::string& ty, int elem0_off, int stride,
                                 int len, const Position& pos) {
        auto elem = array_elem(ty);
        if (!elem.has_value()) {
            throw TenetError::at_pos("不是数组类型：" + ty, pos);
        }
        int slots = array_elem_slots(ty, pos);
        printf_piece("[");
        for (int k = 0; k < len; ++k) {
            if (k > 0) printf_piece(", ");
            int off = elem0_off + stride * (k * slots);
            if (is_struct(*elem)) {
                print_struct_fields(*elem, off, stride, pos);
            } else if (is_array(*elem)) {
                print_fixed_array_slots(*elem, off, stride, *array_decl_len(*elem), pos);
            } else {
                print_scalar_slot(*elem, off, pos);
            }
        }
        printf_piece("]");
    }

    /// struct 的字段逐个打印：`P { x: 1, y: 2 }`，嵌套字段用点分路径
    /// （`Q { p.x: 1, p.y: 2, z: 3 }`）。field_stride：
    /// - 局部 struct 变量字段向低地址排列，传 -8；
    /// - 数组元素 / 指针缓冲字段向高地址排列，传 +8。
    /// S3d：固定数组字段按 `[..]` 展开（元素方向与字段一致）。
    void print_struct_fields(const std::string& ty, int base_off, int field_stride,
                             const Position& pos) {
        const auto layout = layout_of(ty);
        printf_piece(ty + " { ");
        for (int i = 0; i < (int)layout.size(); ++i) {
            if (i > 0) printf_piece(", ");
            const LayoutEntry& entry = layout[i];
            printf_piece(entry.path + ": ");
            int off = base_off + field_stride * entry.offset;
            if (is_array(entry.ty)) {
                print_fixed_array_slots(entry.ty, off, field_stride,
                                        *array_decl_len(entry.ty), pos);
            } else {
                print_scalar_slot(entry.ty, off, pos);
            }
        }
        printf_piece(" }");
    }

    /// 动态 struct 数组元素：x10 = data + idx*slots*8，字段 j 在 x10 + 8*j
    /// （packed 布局）。每个字段重新算基址，因为 printf 会破坏 x10。
    /// S3d：含固定数组字段的 struct 先拷进临时缓冲再按局部布局整体展开。
    void print_struct_dyn_elem(const std::string& ty, const DynArrayInfo& di,
                               int idx_off, int slots, const Position& pos) {
        const auto layout = layout_of(ty);
        bool has_array = false;
        for (const auto& entry : layout) {
            if (is_array(entry.ty)) has_array = true;
        }
        if (has_array) {
            int buf = alloc_scratch(slots);
            load_slot("x14", di.data);
            load_slot("x9", idx_off);
            if (slots != 1) {
                emit_mov_const("x11", slots);
                emit("mul x9, x9, x11");
            }
            emit("add x14, x14, x9, lsl #3");
            for (int k = 0; k < slots; ++k) {
                load_reg_offset("x9", "x14", 8 * k);
                store_slot("x9", buf - 8 * k);
            }
            print_struct_fields(ty, buf, -8, pos);
            return;
        }
        printf_piece(ty + " { ");
        for (int i = 0; i < (int)layout.size(); ++i) {
            if (i > 0) printf_piece(", ");
            printf_piece(layout[i].path + ": ");
            load_slot("x10", di.data);
            load_slot("x9", idx_off);
            if (slots != 1) {
                emit_mov_const("x11", slots);
                emit("mul x9, x9, x11");
            }
            emit("add x10, x10, x9, lsl #3");
            print_scalar_ptr(layout[i].ty, "x10", 8 * layout[i].offset, pos);
        }
        printf_piece(" }");
    }

    /// 定长标量数组：编译期展开 `[1, 2, 3]`。
    void print_fixed_scalar_array(const std::string& elem, int base_off, int len,
                                  const Position& pos) {
        printf_piece("[");
        for (int k = 0; k < len; ++k) {
            if (k > 0) printf_piece(", ");
            print_scalar_slot(elem, base_off + 8 * k, pos);
        }
        printf_piece("]");
    }

    /// 定长 nested 数组：外层/内层都编译期展开，`[[1, 2], [3, 4]]`。
    void print_fixed_nested_array(const std::string& ty, int base_off, int len,
                                  const Position& pos) {
        std::string inner = array_elem_checked(ty, pos);
        std::string inner_elem = array_elem_checked(inner, pos);
        int inner_len = *array_decl_len(inner);
        int slots = array_elem_slots(ty, pos);  // 每个外层元素的标量槽数 = inner_len
        printf_piece("[");
        for (int k = 0; k < len; ++k) {
            if (k > 0) printf_piece(", ");
            printf_piece("[");
            for (int j = 0; j < inner_len; ++j) {
                if (j > 0) printf_piece(", ");
                print_scalar_slot(inner_elem, base_off + 8 * (k * slots + j), pos);
            }
            printf_piece("]");
        }
        printf_piece("]");
    }

    /// 定长 struct 数组：每个元素按 slots 槽步长展开，`[P { x: 1 }, P { x: 2 }]`。
    void print_fixed_struct_array(const std::string& ty, const std::string& elem,
                                  int base_off, int len, const Position& pos) {
        int slots = array_elem_slots(ty, pos);
        printf_piece("[");
        for (int k = 0; k < len; ++k) {
            if (k > 0) printf_piece(", ");
            print_struct_fields(elem, base_off + 8 * k * slots, +8, pos);
        }
        printf_piece("]");
    }

    /// 动态数组：运行时循环，下标存 scratch 槽（printf 调用会破坏 caller-saved 寄存器）。
    /// S3c-3e：动态嵌套数组 print：外层运行时循环，每个外层元素再循环打印内层，
    /// 输出 `[[1, 2], [3]]`（空内层 `[]`，空外层 `[]`）。所有循环状态存 scratch 槽，
    /// 因为 printf 会破坏 caller-saved 寄存器。
    void print_dynamic_nested_array(const std::string& ty, const DynArrayInfo& di,
                                    const Position& pos) {
        std::string elem = dynamic_nested_scalar_elem(ty, pos);
        int oi = alloc_scratch(1);
        int idata = alloc_scratch(1);
        int ilen = alloc_scratch(1);
        int ii = alloc_scratch(1);
        printf_piece("[");
        store_slot("xzr", oi);
        std::string ocond = new_label("print.nested.cond");
        std::string osep = new_label("print.nested.sep");
        std::string oend = new_label("print.nested.end");
        std::string icond = new_label("print.inner.cond");
        std::string isep = new_label("print.inner.sep");
        std::string iend = new_label("print.inner.end");
        emit("b " + ocond);
        label(ocond);
        load_slot("x9", oi);
        load_slot("x10", di.len);
        emit("cmp x9, x10");
        emit("b.hs " + oend);
        load_slot("x9", oi);
        emit("cmp x9, #0");
        emit("b.eq " + osep);
        printf_piece(", ");
        label(osep);
        // 定位外层元素（内层 descriptor）：data + oi*24。
        load_slot("x10", di.data);
        load_slot("x9", oi);
        emit_mov_const("x11", 24);
        emit("mul x9, x9, x11");
        emit("add x10, x10, x9");
        emit("ldr x9, [x10, #0]");
        store_slot("x9", idata);
        emit("ldr x9, [x10, #8]");
        store_slot("x9", ilen);
        printf_piece("[");
        store_slot("xzr", ii);
        emit("b " + icond);
        label(icond);
        load_slot("x9", ii);
        load_slot("x10", ilen);
        emit("cmp x9, x10");
        emit("b.hs " + iend);
        load_slot("x9", ii);
        emit("cmp x9, #0");
        emit("b.eq " + isep);
        printf_piece(", ");
        label(isep);
        load_slot("x10", idata);
        load_slot("x9", ii);
        emit("ldr x9, [x10, x9, lsl #3]");
        print_scalar_reg(elem, "x9", pos);
        load_slot("x9", ii);
        emit("add x9, x9, #1");
        store_slot("x9", ii);
        emit("b " + icond);
        label(iend);
        printf_piece("]");
        load_slot("x9", oi);
        emit("add x9, x9, #1");
        store_slot("x9", oi);
        emit("b " + ocond);
        label(oend);
        printf_piece("]");
    }

    void print_dynamic_array(const std::string& ty, const DynArrayInfo& di,
                             const Position& pos) {
        std::string elem = array_elem_checked(ty, pos);
        int slots = array_elem_slots(ty, pos);
        if (is_array(elem)) {
            print_dynamic_nested_array(ty, di, pos);
            return;
        }
        printf_piece("[");
        int idx_off = alloc_scratch(1);
        store_slot("xzr", idx_off);
        std::string cond = new_label("print.cond");
        std::string after_sep = new_label("print.sep");
        std::string end = new_label("print.end");
        emit("b " + cond);
        label(cond);
        load_slot("x9", idx_off);
        load_slot("x10", di.len);
        emit("cmp x9, x10");
        emit("b.hs " + end);
        load_slot("x9", idx_off);
        emit("cmp x9, #0");
        emit("b.eq " + after_sep);
        printf_piece(", ");
        label(after_sep);
        if (is_struct(elem)) {
            print_struct_dyn_elem(elem, di, idx_off, slots, pos);
        } else {
            load_slot("x10", di.data);
            load_slot("x9", idx_off);
            emit("ldr x9, [x10, x9, lsl #3]");
            print_scalar_reg(elem, "x9", pos);
        }
        load_slot("x9", idx_off);
        emit("add x9, x9, #1");
        store_slot("x9", idx_off);
        emit("b " + cond);
        label(end);
        printf_piece("]");
    }

    /// 打印 aggregate 变量：struct / 定长数组（含 struct 元素、嵌套定长） / 动态数组。
    void print_aggregate_var(const std::string& name, const Position& pos) {
        std::string ty = scoped_var_type(name, pos);
        if (is_struct(ty)) {
            print_struct_fields(ty, lookup_slot(name, pos), -8, pos);
            return;
        }
        if (is_dynamic_array(ty)) {
            print_dynamic_array(ty, lookup_dyn(name, pos), pos);
            return;
        }
        if (is_array(ty)) {
            std::string elem = array_elem_checked(ty, pos);
            int len = lookup_array_len(name, pos);
            int base_off = lookup_slot(name, pos);
            if (is_struct(elem)) {
                print_fixed_struct_array(ty, elem, base_off, len, pos);
            } else if (is_array(elem)) {
                print_fixed_nested_array(ty, base_off, len, pos);
            } else {
                print_fixed_scalar_array(elem, base_off, len, pos);
            }
            return;
        }
        throw TenetError::at_pos("print 不支持该类型的值", pos);
    }

    /// aggregate 表达式（不是变量）明确拒绝：字面量/调用/元素整体读取都不支持。
    [[noreturn]] void reject_aggregate_print_expr(const ExprPtr& e) const {
        if (e->kind == Expr::Kind::StructLit) {
            throw TenetError::at_pos(
                "struct 字面量只能用于 let 初始化、函数参数/返回值或整体赋值；"
                "print 只能直接打印 struct 变量",
                e->pos);
        }
        if (e->kind == Expr::Kind::Array) {
            throw TenetError::at_pos(
                "数组字面量只能用于 let 初始化或整体赋值、函数实参或返回值；"
                "print 只能直接打印数组变量",
                e->pos);
        }
        throw TenetError::at_pos(
            "print 不支持该类型的值：aggregate 表达式（调用/下标/字段）不能直接打印，"
            "请先赋值给变量",
            e->pos);
    }

    /// print 分派：纯标量沿用单次 printf；出现 aggregate 变量时逐片段多次 printf。
    /// 预扫只对"可能是 aggregate"的表达式做类型推断，避免改变纯标量路径既有的
    /// 报错顺序/文案（例如 x[0]、len(a[0]) 仍由 gen_expr/gen_len 报告原错误）。
    std::string gen_print(const std::vector<ExprPtr>& args, const Position& pos) {
        bool has_aggregate = false;
        for (const auto& a : args) {
            if (a->kind == Expr::Kind::Var) {
                std::string t = var_type(a->name, a->pos);
                if (is_struct(t) || is_array(t)) has_aggregate = true;
                continue;
            }
            if (a->kind == Expr::Kind::StructLit || a->kind == Expr::Kind::Array) {
                reject_aggregate_print_expr(a);
            }
            if (a->kind == Expr::Kind::Index) {
                try {
                    auto t = infer_type(a);
                    if (t.has_value() && (is_struct(*t) || is_array(*t))) {
                        reject_aggregate_print_expr(a);
                    }
                } catch (const TenetError&) {
                    // 标量下标错误交给下面原有求值路径报告，保持既有文案。
                }
                continue;
            }
            if (a->kind == Expr::Kind::Call && a->name != "print" && a->name != "push" &&
                a->name != "len") {
                auto t = infer_type(a);
                if (t.has_value() && (is_struct(*t) || is_array(*t))) {
                    reject_aggregate_print_expr(a);
                }
            }
        }
        if (!has_aggregate) return gen_print_scalar_only(args, pos);
        return gen_print_multi(args, pos);
    }

    std::string gen_print_multi(const std::vector<ExprPtr>& args, const Position& pos) {
        (void)pos;
        for (size_t i = 0; i < args.size(); ++i) {
            if (i > 0) printf_piece(" ");
            if (args[i]->kind == Expr::Kind::Var) {
                std::string vt = var_type(args[i]->name, args[i]->pos);
                if (is_struct(vt) || is_array(vt)) {
                    print_aggregate_var(args[i]->name, args[i]->pos);
                    continue;
                }
            }
            std::string t = gen_expr(args[i]);
            if (t != T_INT && t != T_FLOAT && t != T_STR && t != T_BOOL) {
                throw TenetError::at_pos("print 不支持该类型的值", args[i]->pos);
            }
            pop_reg("x9");
            print_scalar_reg(t, "x9", args[i]->pos);
        }
        printf_piece("\n");
        return "void";
    }

    /// 纯标量 print：Apple 变参约定——fmt 在 x0，变参全部压栈（实测与 clang 一致）。
    /// 暂存寄存器 x9-x15 只够 7 个变参；更多时额外借用 callee-saved x19/x20
    /// （只在需要时成对保存/恢复，不影响常规 print 的栈帧）。
    std::string gen_print_scalar_only(const std::vector<ExprPtr>& args, const Position& pos) {
        static const char* kTmpRegs[] = {"x9",  "x10", "x11", "x12", "x13",
                                         "x14", "x15", "x19", "x20"};
        int n = (int)args.size();
        if (n > 9) throw TenetError::at_pos("print 暂不支持超过 9 个参数", pos);
        bool need_callee_saved = n > 7;
        if (need_callee_saved) emit("stp x19, x20, [sp, #-16]!");

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

        // 逆序弹出到暂存寄存器（bool 转 true/false 串）
        for (int i = n - 1; i >= 0; --i) {
            std::string reg = kTmpRegs[n - 1 - i];
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
            emit(std::string("str ") + kTmpRegs[n - 1 - i] + ", [sp, #" +
                 std::to_string(8 * i) + "]");
        }
        emit("adrp x0, " + fmt_name + "@PAGE");
        emit("add x0, x0, " + fmt_name + "@PAGEOFF");
        emit("bl _printf");
        if (area > 0) emit("add sp, sp, #" + std::to_string(area));
        if (need_callee_saved) emit("ldp x19, x20, [sp], #16");
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
                NestedIndexParts np;
                if (nested_index_parts(e, np)) {
                    if (auto dty = dynamic_nested_base_type(np.base, e->pos)) {
                        // S3c-3e：动态嵌套数组 a[i][j] 的标量元素类型。
                        auto ot = infer_type(np.outer);
                        if (ot.has_value() && *ot != T_INT) {
                            throw TenetError::at_pos("数组下标必须是 int，实际为 " + *ot,
                                                     np.outer->pos);
                        }
                        auto it = infer_type(np.inner);
                        if (it.has_value() && *it != T_INT) {
                            throw TenetError::at_pos("数组下标必须是 int，实际为 " + *it,
                                                     np.inner->pos);
                        }
                        return dynamic_nested_scalar_elem(*dty, e->pos);
                    }
                    // S3c-3c：a[i][j] 的标量元素类型。
                    NestedRef ref = nested_ref(np.base, e->pos, false);
                    auto ot = infer_type(np.outer);
                    if (ot.has_value() && *ot != T_INT) {
                        throw TenetError::at_pos("数组下标必须是 int，实际为 " + *ot,
                                                 np.outer->pos);
                    }
                    auto it = infer_type(np.inner);
                    if (it.has_value() && *it != T_INT) {
                        throw TenetError::at_pos("数组下标必须是 int，实际为 " + *it,
                                                 np.inner->pos);
                    }
                    return ref.info.elem;
                }
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
                if (is_struct(*elem)) {
                    throw TenetError::at_pos(
                        "array<struct> 元素不能整体读取为 struct 值；请访问标量字段（如 a[i].x）",
                        e->pos);
                }
                if (is_array(*elem)) {
                    throw TenetError::at_pos(
                        "嵌套数组元素不能整体取值；请用 a[i][j] 访问内层元素", e->pos);
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
                if (*first != T_INT && *first != T_FLOAT && *first != T_BOOL &&
                    !is_struct(*first) && !is_array(*first)) {
                    throw TenetError::at_pos(
                        "v1 数组元素只支持 int/float/bool 或 struct，实际 `" + *first + "`",
                        e->pos);
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
                // S3b：字面量推断为定长 array<T, N>，长度是类型的一部分。
                // S3c-3c：内层字面量推断为 array<array<T, N>, M>（仅局部变量）。
                std::string result =
                    "array<" + *first + "," + std::to_string(e->args.size()) + ">";
                if (is_array(*first)) {
                    array_elem_checked(result, e->pos);
                    nested_array_info(result, e->pos);
                }
                return result;
            }
            case Expr::Kind::Field: {
                StructElemRef er;
                if (struct_elem_path(e, er)) return struct_array_field_type(e, false);
                return resolve_field(e, false).ty;
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
                    NestedIndexParts np;
                    if (nested_index_parts(target, np)) {
                        if (auto dty = dynamic_nested_base_type(np.base, target->pos)) {
                            // S3c-3e：a[i][j] = ... 返回内层标量元素类型。
                            auto ot = infer_type(np.outer);
                            if (ot.has_value() && *ot != T_INT) {
                                throw TenetError::at_pos("数组下标必须是 int，实际为 " + *ot,
                                                         np.outer->pos);
                            }
                            auto it = infer_type(np.inner);
                            if (it.has_value() && *it != T_INT) {
                                throw TenetError::at_pos("数组下标必须是 int，实际为 " + *it,
                                                         np.inner->pos);
                            }
                            return dynamic_nested_scalar_elem(*dty, target->pos);
                        }
                        // S3c-3c：a[i][j] = ... 返回内层标量元素类型。
                        NestedRef ref = nested_ref(np.base, target->pos, true);
                        auto ot = infer_type(np.outer);
                        if (ot.has_value() && *ot != T_INT) {
                            throw TenetError::at_pos("数组下标必须是 int，实际为 " + *ot,
                                                     np.outer->pos);
                        }
                        auto it = infer_type(np.inner);
                        if (it.has_value() && *it != T_INT) {
                            throw TenetError::at_pos("数组下标必须是 int，实际为 " + *it,
                                                     np.inner->pos);
                        }
                        return ref.info.elem;
                    }
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
                    StructElemRef er;
                    if (struct_elem_path(target, er)) return struct_array_field_type(target, true);
                    return resolve_field(target, true).ty;
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
                if (e->name == "push") return std::nullopt;  // push 返回 void
                if (e->name == "len") {
                    if (e->args.size() != 1) {
                        throw TenetError::at_pos("`len` 需要且只需要一个数组参数", e->pos);
                    }
                    const ExprPtr& la = e->args[0];
                    if (la && la->kind == Expr::Kind::Index && la->lhs &&
                        la->lhs->kind == Expr::Kind::Var) {
                        std::string bt = var_type(la->lhs->name, la->lhs->pos);
                        if (is_dynamic_nested_array(bt)) {
                            // S3c-3e：len(a[i]) 的结果是 int，a[i] 本身不整体取值。
                            auto it = infer_type(la->rhs);
                            if (it.has_value() && *it != T_INT) {
                                throw TenetError::at_pos("数组下标必须是 int，实际为 " + *it,
                                                         la->rhs->pos);
                            }
                            return T_INT;
                        }
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
