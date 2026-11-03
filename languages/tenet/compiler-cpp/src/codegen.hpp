// LLVM 代码生成器：AST → LLVM IR（进程内构建，调用 LLVM C++ API）。
//
// 与 compiler-rs（生成 .ll 文本 + clang 驱动）的关键差异：
// - 用 IRBuilder 在内存中构建 IR（不是写文本文件）
// - 变量用 alloca + load/store；控制流用基本块 + br
// - struct（S3a）：嵌套字段扁平化为标量槽位；参数传指针、返回值走隐藏 sret 指针，
//   被调函数入口/返回处逐字段拷贝（值语义）
// - array（S3b）：`array<T, N>` 是定长值数组类型，局部变量/参数/返回值都可用；
//   参数传指针、返回值走 sret，入口/返回逐元素拷贝
// - 动态数组（S3c-1）：局部 `array<T>` 用堆缓冲区 + data/len/cap 三个栈槽，
//   支持 push / 运行时 len / 下标 / 深拷贝 / 作用域 drop
// - 动态数组参数/返回值（S3c-2）：参数传 3 槽 descriptor 指针 + 入口深拷贝（值语义）；
//   返回值走隐藏 `ptr %sret` descriptor，`return 变量` 转移所有权并清空本地槽位
// - 动态数组表达式（S3c-3a）：字面量 / 函数调用结果可作动态实参（临时 descriptor
//   传给被调函数，调用返回后 free 临时缓冲区）与 `return` 值（所有权转移进 sret）
// - 固定 array<struct, N>（S3c-3b-1）：局部定长数组，元素按 struct 扁平字段
//   连续存放（元素 stride = 字段数 * 8 字节），支持 a[i].field / a[i].p.x 读写、
//   a[i] = struct 整体元素赋值、`let b = a` 深拷贝；单字段 struct 数组
//   （含 array<P, 1> / array<array<int, 1>, M>）同样走扁平槽布局
// - 固定 array<struct, N> 参数/返回值（S3c-3b-3）：参数传 ptr，被调函数入口按
//   总槽数 N*slots 拷贝到本地 `[N*slots x i64]` 扁平缓冲（值语义）；返回值走隐藏
//   `ptr %sret`，函数返回 void；`return 数组变量` 逐槽打包进 sret，调用方从返回
//   缓冲拷贝/接管本地数组
// - 固定数组整体赋值（S3c-3b-4）：`b = a` / `b = [..]` / `b = f()` 把右侧按总槽数
//   打包到临时 `[total x i64]` 缓冲，再逐槽覆盖 b（固定数组无堆，直接覆盖）
// - 动态 array<struct>（S3c-3b-2）：堆数组按元素 stride = slots*8 布局，支持字面量 /
//   变量深拷贝 / push struct / 元素字段与整体赋值；参数/返回值走 descriptor/sret ABI，
//   入口深拷贝、返回转移
// - 固定嵌套数组（S3c-3c v1/v2）：`array<array<T, N>, M>` 存储为 `[M*N x i64]`
//   扁平缓冲（内层 int/float，不支持 bool），支持字面量 / 同类型深拷贝、
//   a[i][j] 读写与内外层运行时边界检查；len(a) 仍是外层常量，暂不支持 len(a[i])
// - 固定嵌套数组参数/返回值（S3c-3c v2）：与 array<struct> 同构——参数传 ptr +
//   入口按总槽数 M*N 拷贝，返回值走隐藏 `ptr %sret`；调用方从返回缓冲拷贝/接管
// - 动态嵌套数组（S3c-3d v1）：`array<array<T>>`（外层与内层都动态，T 限
//   int/float/bool）。外层堆元素是内层 descriptor [data,len,cap]（3 个 i64 槽，
//   stride = 24 字节）；支持字面量 / 空字面量 / 同类型深拷贝 / 整体赋值、a[i][j]
//   读写（双层运行时边界检查）、len(a[i])、push（内层深拷贝 + 外层 cap*2）、
//   print `[[1, 2], [3]]`；参数/返回值走 descriptor/sret，入口逐内层深拷贝、
//   返回转移所有权；drop 先逐内层 free(data) 再 free 外层
// - print aggregate：struct / 定长与动态数组 / struct 数组 / 固定嵌套数组 /
//   动态嵌套数组可直接打印变量（`P { x: 1, y: 2 }` / `[1, 2, 3]` /
//   `[P { x: 1 }]` / `[[1, 2]]` / `[[1, 2], [3]]`）；纯标量 / 字符串 / 数组元素
//   仍走单次 printf，aggregate 表达式明确报错
// - struct 固定数组字段（S3d v1）：字段可为 array<int/float/bool,N> /
//   array<struct,N> / 固定嵌套 array<array<T,N>,M>，按 N*elem_slots 计入 struct
//   总槽数与后续字段偏移；支持字面量、s.a[i] 读写、s.a[i].field / s.a[i][j]、
//   整体深拷贝、struct 参数/返回值按总槽数 ABI、print 展开数组字段；
//   动态数组字段（array<T>）在声明处明确拒绝
// - 后端（IR → 机器码）由 LLVM 库进程内完成（rustc 方式），
//   不再调用 clang 解析文本
#pragma once

#include <algorithm>
#include <limits>
#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "llvm/IR/BasicBlock.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/DerivedTypes.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/LLVMContext.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Type.h"
#include "llvm/IR/Verifier.h"
#include "llvm/Support/raw_ostream.h"

#include "ast.hpp"
#include "error.hpp"

namespace tenet {

/// LLVM 类型映射：Tenet 类型 → LLVM 类型字符串（错误信息用）。
inline const char* llvm_type(const std::string& ty) {
    if (ty == T_INT) return "i64";
    if (ty == T_FLOAT) return "double";
    if (ty == T_BOOL) return "i1";
    if (ty == T_STR) return "ptr";
    throw TenetError("未知类型 `" + ty + "`");
}

/// LLVM 类型 → Tenet 类型名（错误信息用）。
inline const char* tenet_name(const std::string& ll) {
    if (ll == "i64") return T_INT;
    if (ll == "double") return T_FLOAT;
    if (ll == "i1") return T_BOOL;
    if (ll == "ptr") return T_STR;
    return "?";
}

/// 用户函数信息：LLVM Function + 参数/返回类型（参数核对用）。
struct FnInfo {
    llvm::Function* fn;
    std::optional<std::string> ret;
    std::vector<std::string> params;
};

/// S3c-1 动态数组（`array<T>`）的栈上 descriptor：三个槽位 data/len/cap。
/// 堆缓冲区由 malloc 分配，元素按 8 字节槽存放。
struct DynArrayInfo {
    llvm::AllocaInst* data = nullptr;  // ptr
    llvm::AllocaInst* len = nullptr;   // i64
    llvm::AllocaInst* cap = nullptr;   // i64
};

/// S3e：动态数组 descriptor 的通用三个槽地址。
/// 局部动态数组变量用 3 个独立 alloca；struct 动态字段在 ABI buffer / 数组元素里
/// 是连续 3 个 i64 槽，用 flat_slot 求出三个槽地址。load/store/drop/深拷贝只依赖
/// 这三个地址，因此局部 descriptor 与扁平槽 descriptor 共用一套实现。
struct DynSlots {
    llvm::Value* data = nullptr;  // ptr
    llvm::Value* len = nullptr;   // i64
    llvm::Value* cap = nullptr;   // i64
};

/// 变量信息。struct 变量不占一个聚合槽，而是按扁平布局拆字段槽位：
/// 标量叶子一个独立 alloca，固定数组字段一个 `[N*elem_slots x i64]` alloca，
/// 键是字段路径（如 `a.x` / `a`）；`addr == nullptr` 表示这是一个 struct 变量
/// （或动态数组变量）。
struct VarInfo {
    std::string ty;
    llvm::AllocaInst* addr = nullptr;
    std::unordered_map<std::string, std::pair<std::string, llvm::AllocaInst*>> fields;
    /// 固定数组的定长长度；非固定数组为 nullopt。
    /// 固定 array<struct, N> 的 addr 指向扁平 `[N*slots x i64]`（S3c-3b-1）。
    std::optional<size_t> array_len;
    /// 动态数组的 data/len/cap 槽位；非动态数组为 nullopt。
    std::optional<DynArrayInfo> dyn;
    /// S3e：struct 变量的动态数组字段（字段路径 → descriptor 三槽）。
    /// 局部 struct 变量每个动态字段分配 3 个独立 alloca；ABI buffer / 数组元素里的
    /// 字段是连续 3 槽，用 Place::Kind::DynArray 表示。
    std::unordered_map<std::string, DynArrayInfo> dyn_fields;
};

/// 左值解析结果：支持 `s.a[i]`、`s.a[i].f`、`s.a[i][j]` 这类
/// 「struct 变量 / 固定数组字段 / 数组元素」组合出的地址。
struct Place {
    enum class Kind { Scalar, Array, Struct, DynArray };
    Kind kind = Kind::Scalar;
    std::string ty;
    /// Scalar 的标量槽地址；Array 的数据首槽；Struct 的扁平槽块首槽。
    llvm::Value* addr = nullptr;
    /// Array：数据是否为扁平 i64 槽布局（struct 字段 / struct 元素 / 嵌套数组）。
    bool packed = false;
    /// Array 的定长长度。
    size_t len = 0;
    /// Struct：局部 struct 变量的字段表（可继续按点路径查字段）；
    /// 数组元素 / 字段块则为 nullptr，改用 addr + 槽偏移。
    const VarInfo* var = nullptr;
    /// Struct 变量当前字段前缀（`inner` 等）。
    std::string prefix;
    /// Scalar：地址是否指向扁平 i64 槽（struct 数组元素 / 固定数组字段）。
    /// 此时读写必须按 pack_scalar / unpack_scalar 走 i64，而不能直接 load/store
    /// double / i1（bool 槽宽 8 字节）。
    bool slot_storage = false;
    /// DynArray：descriptor 三槽地址（类型是 `array<T>` 动态数组）。
    DynSlots dyn;
};

/// struct 扁平槽位布局中的一项。
///
/// - `path`：字段点路径（嵌套 struct 递归展开成 `inner.x`）；
/// - `ty`：标量字段类型，或固定数组字段的完整数组类型；
/// - `offset`：相对 struct 起始的 8 字节槽偏移（不是字段序号）；
/// - `slots`：该字段占用的槽数（标量 1，固定数组 `N * elem_slots`）。
struct LayoutEntry {
    std::string path;
    std::string ty;
    size_t offset = 0;
    size_t slots = 1;
};

/// 编译产物：LLVMContext 与 Module 一起转移（Module 持有 Context 引用，
/// 二者生命周期必须一致——这是进程内 LLVM 后端的核心约束）。
struct CompiledModule {
    std::unique_ptr<llvm::LLVMContext> ctx;
    std::unique_ptr<llvm::Module> mod;
};

class Codegen {
public:
    Codegen(llvm::LLVMContext& ctx, llvm::Module& mod)
        : ctx_(ctx), mod_(mod), builder_(ctx), globals_str_(0) {}

    /// 完整编译：Program → (Context + Module)，二者一起返回保证存活。
    static CompiledModule compile(const Program& program) {
        auto ctx = std::make_unique<llvm::LLVMContext>();
        auto mod = std::make_unique<llvm::Module>("tenet", *ctx);
        Codegen gen(*ctx, *mod);
        gen.collect_structs(program);
        gen.emit_decls(program);
        gen.emit_program(program);
        return {std::move(ctx), std::move(mod)};
    }

    /// 进程内后端：Module → 对象文件（.o），由 LLVM 库完成 IR → 机器码。
    static void emit_object(llvm::Module& mod, const std::string& obj_path);

private:
    llvm::LLVMContext& ctx_;
    llvm::Module& mod_;
    llvm::IRBuilder<> builder_;
    unsigned globals_str_;

    // 变量作用域栈：name -> VarInfo（标量为 alloca，struct 为扁平字段槽位）
    std::vector<std::unordered_map<std::string, VarInfo>> symbols_;
    // 顶层 struct 名 → 字段 (名, 标量或 struct 类型)
    std::unordered_map<std::string, std::vector<std::pair<std::string, std::string>>> structs_;
    // struct 声明顺序（循环嵌套检查 / 错误定位用）
    std::vector<std::string> struct_order_;
    std::unordered_map<std::string, Position> struct_pos_;
    // 函数表：name -> FnInfo（Function + 参数/返回类型）
    std::unordered_map<std::string, FnInfo> functions_;
    // 当前函数上下文（返回类型核对用）
    std::string current_fn_;
    std::optional<std::string> current_ret_;
    // struct 返回值函数的隐藏 sret 指针（第一参数）
    llvm::Value* current_sret_ = nullptr;
    // break 目标栈：退出块 + 循环体作用域深度（break 前 drop 该层及内层动态数组）
    struct BreakTarget {
        llvm::BasicBlock* exit;
        size_t scope_depth;
    };
    std::vector<BreakTarget> break_stack_;

    llvm::Type* ty(const char* t) {
        if (std::string(t) == "i64") return llvm::Type::getInt64Ty(ctx_);
        if (std::string(t) == "double") return llvm::Type::getDoubleTy(ctx_);
        if (std::string(t) == "i1") return llvm::Type::getInt1Ty(ctx_);
        return llvm::PointerType::getUnqual(ctx_);
    }

    // ---- struct 预处理 ----

    /// 收集并校验顶层 struct 声明。字段可以是 int/float/bool 或另一个已声明 struct；
    /// 禁止 array 字段、未定义类型与循环嵌套（S3a）。
    void collect_structs(const Program& program) {
        // 第一阶段：登记所有声明（先登记完才能解析前向引用）。
        for (const auto& stmt : program.stmts) {
            if (stmt->kind != Stmt::Kind::StructDecl) continue;
            const std::string& name = stmt->name;
            if (name == T_INT || name == T_FLOAT || name == T_BOOL || name == T_STR) {
                throw TenetError::at_pos("struct 名 `" + name + "` 不能与标量类型重名", stmt->pos);
            }
            if (structs_.count(name)) {
                throw TenetError::at_pos("struct `" + name + "` 重复定义", stmt->pos);
            }
            if (stmt->fields.empty()) {
                throw TenetError::at_pos("struct `" + name + "` 至少需要一个字段", stmt->pos);
            }
            std::unordered_map<std::string, bool> seen;
            for (const auto& [fname, fty] : stmt->fields) {
                (void)fty;
                if (seen.count(fname)) {
                    throw TenetError::at_pos("struct `" + name + "` 的字段 `" + fname + "` 重复",
                                             stmt->pos);
                }
                seen[fname] = true;
            }
            structs_[name] = stmt->fields;
            struct_order_.push_back(name);
            struct_pos_[name] = stmt->pos;
        }

        // 第二阶段：字段类型校验（标量 int/float/bool、另一个 struct，或固定长度数组）。
        for (const auto& name : struct_order_) {
            const Position& pos = struct_pos_.at(name);
            for (const auto& [fname, fty] : structs_.at(name)) {
                if (fty == T_INT || fty == T_FLOAT || fty == T_BOOL) continue;
                if (fty == T_STR) {
                    throw TenetError::at_pos("struct `" + name + "` 的字段 `" + fname +
                                                 "` 只支持 int/float/bool 或另一个 struct",
                                             pos);
                }
                if (is_array(fty)) {
                    validate_struct_array_field(name, fname, fty, pos);
                    validate_struct_array_elem_defined(name, fname, fty, pos);
                    continue;
                }
                if (!is_struct(fty)) {
                    throw TenetError::at_pos("struct `" + name + "` 的字段 `" + fname +
                                                 "` 类型 `" + fty + "` 未定义",
                                             pos);
                }
            }
        }

        // 第三阶段：循环嵌套检测（DFS + 递归栈，沿声明顺序保证报错确定）。
        for (const auto& name : struct_order_) {
            std::vector<std::string> stack;
            check_struct_cycle(name, stack);
        }
    }

    /// struct 的数组字段校验。
    /// S3e：动态标量数组字段 `array<int/float/bool>` 允许，占 3 个 descriptor 槽；
    /// 动态 `array<struct>` 字段与动态嵌套字段（`array<array<T>>`）不在 v1 范围，
    /// 固定数组的每一层仍然必须写长度 `N`，叶子元素限标量或 struct。
    void validate_struct_array_field(const std::string& sname, const std::string& fname,
                                     const std::string& fty, const Position& pos) const {
        if (is_dynamic_array(fty)) {
            auto elem = array_elem(fty);
            if (!elem.has_value()) {
                throw TenetError::at_pos("struct `" + sname + "` 的字段 `" + fname +
                                             "` 的数组元素类型未知",
                                         pos);
            }
            if (*elem == T_INT || *elem == T_FLOAT || *elem == T_BOOL) return;
            if (is_struct(*elem)) {
                throw TenetError::at_pos(
                    "struct `" + sname + "` 的字段 `" + fname +
                        "` 不支持动态 array<struct> 字段；v1 动态字段只支持 "
                        "array<int/float/bool>",
                    pos);
            }
            if (is_array(*elem)) {
                throw TenetError::at_pos(
                    "struct `" + sname + "` 的字段 `" + fname +
                        "` 不支持动态嵌套数组字段；v1 动态字段只支持 "
                        "array<int/float/bool>",
                    pos);
            }
            if (*elem == T_STR) {
                throw TenetError::at_pos(
                    "struct `" + sname + "` 的字段 `" + fname +
                        "` 的数组元素不支持 string；只支持 int/float/bool 或 struct",
                    pos);
            }
            // 未定义的 struct 名交给 validate_struct_array_elem_defined 报错。
            return;
        }
        std::string cur = fty;
        while (is_array(cur)) {
            if (!array_decl_len(cur).has_value()) {
                throw TenetError::at_pos(
                    "struct `" + sname + "` 的字段 `" + fname +
                        "` 只支持 int/float/bool、struct 或固定长度 array<T, N>，"
                        "不支持动态数组 array<T>",
                    pos);
            }
            auto inner = array_elem(cur);
            if (!inner.has_value()) {
                throw TenetError::at_pos("struct `" + sname + "` 的字段 `" + fname +
                                             "` 的数组元素类型未知",
                                         pos);
            }
            if (is_array(*inner)) {
                cur = *inner;
                continue;
            }
            if (*inner == T_INT || *inner == T_FLOAT || *inner == T_BOOL) return;
            if (is_struct(*inner)) return;
            if (*inner == T_STR) {
                throw TenetError::at_pos(
                    "struct `" + sname + "` 的字段 `" + fname +
                        "` 的数组元素不支持 string；只支持 int/float/bool 或 struct",
                    pos);
            }
            // 未定义的 struct 名交给 validate_struct_array_elem_defined 报错。
            return;
        }
    }

    /// 数组字段（含嵌套数组）的叶子元素类型必须已定义。
    void validate_struct_array_elem_defined(const std::string& sname, const std::string& fname,
                                            const std::string& fty,
                                            const Position& pos) const {
        std::string cur = fty;
        while (is_array(cur)) {
            auto inner = array_elem(cur);
            if (!inner.has_value()) return;
            cur = *inner;
        }
        if (cur == T_INT || cur == T_FLOAT || cur == T_BOOL || is_struct(cur)) return;
        throw TenetError::at_pos("struct `" + sname + "` 的字段 `" + fname + "` 的数组元素类型 `" +
                                     cur + "` 未定义",
                                 pos);
    }

    /// 数组字段（可嵌套）的叶子 struct 名；叶子不是 struct 时返回 nullopt。
    std::optional<std::string> array_leaf_struct(const std::string& ty) const {
        std::string cur = ty;
        while (is_array(cur)) {
            auto inner = array_elem(cur);
            if (!inner.has_value()) return std::nullopt;
            cur = *inner;
        }
        if (is_struct(cur)) return cur;
        return std::nullopt;
    }

    void check_struct_cycle(const std::string& ty, std::vector<std::string>& stack) const {
        auto it = std::find(stack.begin(), stack.end(), ty);
        if (it != stack.end()) {
            std::vector<std::string> cycle(it, stack.end());
            cycle.push_back(ty);
            std::string path;
            for (size_t i = 0; i < cycle.size(); ++i) {
                if (i) path += " -> ";
                path += cycle[i];
            }
            throw TenetError::at_pos("struct 循环嵌套：" + path, struct_pos_.at(ty));
        }
        auto def = structs_.find(ty);
        if (def == structs_.end()) return;
        stack.push_back(ty);
        for (const auto& [fname, fty] : def->second) {
            (void)fname;
            if (is_struct(fty)) {
                check_struct_cycle(fty, stack);
            } else if (is_array(fty)) {
                auto leaf = array_leaf_struct(fty);
                if (leaf.has_value()) check_struct_cycle(*leaf, stack);
            }
        }
        stack.pop_back();
    }

    bool is_struct(const std::string& t) const { return structs_.count(t) != 0; }

    static bool is_scalar(const std::string& t) {
        return t == T_INT || t == T_FLOAT || t == T_BOOL || t == T_STR;
    }

    /// 解析 `array<...>` 的内部文本；不是数组类型返回 nullopt。
    static std::optional<std::string> array_inner(const std::string& t) {
        static const std::string prefix = "array<";
        if (t.size() <= prefix.size() + 1 || t.compare(0, prefix.size(), prefix) != 0 ||
            t.back() != '>') {
            return std::nullopt;
        }
        return t.substr(prefix.size(), t.size() - prefix.size() - 1);
    }

    /// 在 `array<...>` 内部找顶层逗号（忽略嵌套尖括号里的逗号）。
    static std::optional<size_t> top_level_comma(const std::string& inner) {
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
        return std::nullopt;
    }

    /// 数组元素类型：`array<int>` / `array<int,3>` → `int`；不是数组返回 nullopt。
    static std::optional<std::string> array_elem(const std::string& t) {
        auto inner = array_inner(t);
        if (!inner.has_value()) return std::nullopt;
        size_t comma = top_level_comma(*inner).value_or(inner->size());
        std::string elem = inner->substr(0, comma);
        if (elem.empty()) return std::nullopt;
        return elem;
    }

    /// S3b：`array<T, N>` 的定长 N；`array<T>`（S3c-1 动态数组）返回 nullopt。
    static std::optional<size_t> array_decl_len(const std::string& t) {
        auto inner = array_inner(t);
        if (!inner.has_value()) return std::nullopt;
        auto comma = top_level_comma(*inner);
        if (!comma.has_value()) return std::nullopt;
        std::string digits = inner->substr(*comma + 1);
        if (digits.empty()) return std::nullopt;
        size_t n = 0;
        for (char c : digits) {
            if (c < '0' || c > '9') return std::nullopt;
            size_t d = static_cast<size_t>(c - '0');
            if (n > (std::numeric_limits<size_t>::max() - d) / 10) return std::nullopt;
            n = n * 10 + d;
        }
        if (n == 0) return std::nullopt;
        return n;
    }

    static bool is_array(const std::string& t) { return array_elem(t).has_value(); }

    /// S3c-3b-1：数组元素是否为已声明的 struct（固定 / 动态数组都返回 true，
    /// 由调用方按 array_decl_len 区分动态与固定）。
    bool has_struct_elem(const std::string& t) const {
        auto elem = array_elem(t);
        return elem.has_value() && is_struct(*elem);
    }

    /// S3b：数组类型比较按“元素类型 + 长度”语义，不按原始字符串。
    static bool same_array_elem(const std::string& a, const std::string& b) {
        auto ea = array_elem(a);
        auto eb = array_elem(b);
        return ea.has_value() && eb.has_value() && *ea == *eb;
    }

    /// v1 数组元素只支持 int/float/bool。
    static std::string array_elem_scalar(const std::string& t, const Position& pos) {
        auto elem = array_elem(t);
        if (!elem.has_value()) {
            throw TenetError::at_pos("不是数组类型：" + t, pos);
        }
        if (*elem != T_INT && *elem != T_FLOAT && *elem != T_BOOL) {
            throw TenetError::at_pos(
                "v1 数组元素只支持 int/float/bool，实际 `" + *elem + "`", pos);
        }
        return *elem;
    }

    /// S3c-3c v2：固定嵌套数组 `array<array<T, N>, M>` 的内层必须是固定长度
    /// array<T, N>，且 T 只支持 int/float（参数/返回值 ABI 与局部变量共用校验）。
    void ensure_nested_scalar_array(const std::string& t, const Position& pos) const {
        auto outer_elem = array_elem(t);
        if (!outer_elem.has_value() || !is_array(*outer_elem)) {
            throw TenetError::at_pos("`" + t + "` 不是嵌套数组", pos);
        }
        if (!array_decl_len(*outer_elem).has_value()) {
            throw TenetError::at_pos("嵌套数组内层必须是固定长度 array<T, N>", pos);
        }
        auto inner_elem = array_elem(*outer_elem);
        if (!inner_elem.has_value()) {
            throw TenetError::at_pos("嵌套数组内层元素类型未知", pos);
        }
        if (*inner_elem == T_BOOL) {
            throw TenetError::at_pos("嵌套数组内层暂不支持 bool", pos);
        }
        if (*inner_elem != T_INT && *inner_elem != T_FLOAT) {
            throw TenetError::at_pos(
                "嵌套数组元素只支持标量 int/float，实际 `" + *inner_elem + "`", pos);
        }
    }

    /// v1 动态嵌套数组：`array<array<T>>`（外层动态、内层动态、T 为标量）。
    /// 只认这一种形状；固定内层 / array<struct> 内层 / 更深嵌套都返回 nullopt。
    /// 外层元素是内层 descriptor（data/len/cap 三个 i64 槽），堆 stride = 3*8 字节。
    static std::optional<std::string> dynamic_nested_scalar_elem(const std::string& t) {
        if (array_decl_len(t).has_value()) return std::nullopt;
        auto inner = array_elem(t);
        if (!inner.has_value() || array_decl_len(*inner).has_value()) return std::nullopt;
        auto scalar = array_elem(*inner);
        if (!scalar.has_value()) return std::nullopt;
        if (*scalar == T_INT || *scalar == T_FLOAT || *scalar == T_BOOL) return scalar;
        return std::nullopt;
    }

    /// v1 动态嵌套数组类型判断（外层与内层都是动态数组，内层元素是标量）。
    static bool is_dynamic_nested_array(const std::string& t) {
        return dynamic_nested_scalar_elem(t).has_value();
    }

    /// v1 动态嵌套数组形状校验：给出固定内层 / array<struct> 内层 / 更深嵌套的
    /// 明确拒绝错误（局部变量、参数、返回值共用）。
    void ensure_dynamic_nested_scalar_array(const std::string& t, const Position& pos) const {
        auto outer_elem = array_elem(t);
        if (!outer_elem.has_value() || !is_array(*outer_elem)) {
            throw TenetError::at_pos("`" + t + "` 不是嵌套数组", pos);
        }
        if (array_decl_len(t).has_value()) {
            throw TenetError::at_pos("`" + t + "` 不是动态嵌套数组", pos);
        }
        if (array_decl_len(*outer_elem).has_value()) {
            // 保留旧错误前缀，固定的内层仍不在 v1 范围内。
            throw TenetError::at_pos(
                "动态嵌套数组尚未支持固定长度内层；内层必须是动态数组 array<T>", pos);
        }
        auto scalar = array_elem(*outer_elem);
        if (!scalar.has_value()) {
            throw TenetError::at_pos("嵌套数组内层元素类型未知", pos);
        }
        if (*scalar == T_INT || *scalar == T_FLOAT || *scalar == T_BOOL) return;
        if (is_struct(*scalar)) {
            throw TenetError::at_pos(
                "嵌套数组内层元素只支持 int/float/bool，不支持 array<struct>", pos);
        }
        if (is_array(*scalar)) {
            throw TenetError::at_pos("只支持一层嵌套数组 array<array<T>>", pos);
        }
        throw TenetError::at_pos(
            "嵌套数组内层元素只支持标量 int/float/bool，实际 `" + *scalar + "`", pos);
    }

    std::vector<std::pair<std::string, std::string>> struct_fields(const std::string& t,
                                                                   const Position& pos) const {
        auto it = structs_.find(t);
        if (it == structs_.end()) {
            throw TenetError::at_pos("未定义的 struct `" + t + "`", pos);
        }
        return it->second;
    }

    /// 一个字段类型占用的 8 字节槽数：标量 1 槽；固定数组 `N * elem_slots`；
    /// 动态数组 descriptor 3 槽（S3e）；struct 递归求和。
    size_t field_slot_width(const std::string& ty) const {
        if (is_dynamic_array(ty)) return 3;
        auto len = array_decl_len(ty);
        if (len.has_value()) return *len * array_elem_slots(ty);
        if (is_struct(ty)) return struct_total_slots(ty);
        return 1;
    }

    /// struct 的总槽数（固定数组字段按 `N * elem_slots` 计入）。
    size_t struct_total_slots(const std::string& ty) const {
        auto it = structs_.find(ty);
        if (it == structs_.end()) return 0;
        size_t total = 0;
        for (const auto& [fname, fty] : it->second) {
            (void)fname;
            total += field_slot_width(fty);
        }
        return total;
    }

    /// struct 的扁平槽位布局（深度优先 + 声明顺序）：标量字段 1 槽，固定数组字段
    /// 占 `N * elem_slots` 槽，动态数组字段占 3 个 descriptor 槽（S3e），嵌套 struct
    /// 递归展开。返回顺序即 ABI 槽位顺序。
    std::vector<LayoutEntry> layout_of(const std::string& ty) const {
        std::vector<LayoutEntry> out;
        size_t offset = 0;
        layout_into(ty, "", offset, out);
        return out;
    }

    void layout_into(const std::string& ty, const std::string& prefix, size_t& offset,
                     std::vector<LayoutEntry>& out) const {
        auto it = structs_.find(ty);
        if (it == structs_.end()) return;
        for (const auto& [fname, fty] : it->second) {
            std::string path = prefix.empty() ? fname : prefix + "." + fname;
            if (is_struct(fty)) {
                layout_into(fty, path, offset, out);
            } else if (is_array(fty)) {
                const size_t slots = field_slot_width(fty);
                out.push_back({path, fty, offset, slots});
                offset += slots;
            } else {
                out.push_back({path, fty, offset, 1});
                ++offset;
            }
        }
    }

    /// 数组元素的 8 字节槽数（即元素 stride = slots * 8）。
    /// - 标量元素占 1 槽；
    /// - struct 元素占其扁平槽数（S3c-3b-1）；
    /// - 固定嵌套数组元素占 内层长度 × 内层元素槽数（S3c-3c v1）；
    /// - 动态嵌套数组元素是内层 descriptor，占 data/len/cap 三个槽（v1 动态嵌套）。
    size_t array_elem_slots(const std::string& t) const {
        auto elem = array_elem(t);
        if (!elem.has_value()) {
            throw TenetError("内部错误：`" + t + "` 不是数组类型");
        }
        if (is_struct(*elem)) return struct_total_slots(*elem);
        if (is_array(*elem)) {
            auto inner_len = array_decl_len(*elem);
            if (!inner_len.has_value()) {
                // v1 动态嵌套数组：外层堆元素是内层 descriptor（3 个 i64 槽）。
                return 3;
            }
            return *inner_len * array_elem_slots(*elem);
        }
        return 1;
    }

    /// S3e：该类型是否递归拥有需要释放的堆内存。
    /// 动态数组自身；固定数组看元素；struct 看直接字段（含嵌套 struct / 固定数组）。
    bool type_owns_heap(const std::string& ty) const {
        if (is_dynamic_array(ty)) return true;
        if (is_array(ty)) {
            auto elem = array_elem(ty);
            return elem.has_value() && type_owns_heap(*elem);
        }
        auto it = structs_.find(ty);
        if (it == structs_.end()) return false;
        for (const auto& [fname, fty] : it->second) {
            (void)fname;
            if (type_owns_heap(fty)) return true;
        }
        return false;
    }

    /// S3c-3c：`array<array<T, N>, M>` 的嵌套数组类型（内层必须是固定长度）。
    static bool is_nested_array(const std::string& t) {
        auto elem = array_elem(t);
        return elem.has_value() && is_array(*elem);
    }

    /// S3c-3b-3/S3c-3c v2：固定数组是否使用扁平 i64 槽布局。
    /// 按**元素种类**判断（struct 或 array），不看元素槽数——`array<P, 1>`
    /// （单字段 struct，1 槽）与 `array<array<int, 1>, M>`（内层 1 槽）同样走扁平
    /// 路径；标量数组仍是 `[N x T]`。
    bool is_flat_slot_array(const std::string& t) const {
        auto elem = array_elem(t);
        return array_decl_len(t).has_value() && elem.has_value() &&
               (is_struct(*elem) || is_array(*elem));
    }

    /// 固定数组的总 8 字节槽数：N*slots（struct 元素）或 M*N（嵌套数组）。
    size_t fixed_array_total_slots(const std::string& t) const {
        auto len = array_decl_len(t);
        if (!len.has_value()) {
            throw TenetError("内部错误：固定数组缺少定长长度 `" + t + "`");
        }
        return *len * array_elem_slots(t);
    }

    /// S3c-3b-1：struct 元素内字段路径的起始槽号（8 字节槽），不存在返回 nullopt。
    std::optional<size_t> field_offset(const std::string& ty, const std::string& path) const {
        for (const auto& entry : layout_of(ty)) {
            if (entry.path == path) return entry.offset;
        }
        return std::nullopt;
    }

    /// struct 的直接字段类型（不递归展开）。
    std::string direct_field_type(const std::string& ty, const std::string& field,
                                  const Position& pos) const {
        auto defs = struct_fields(ty, pos);
        for (const auto& [fname, fty] : defs) {
            if (fname == field) return fty;
        }
        throw TenetError::at_pos("struct `" + ty + "` 没有字段 `" + field + "`", pos);
    }

    /// struct 直接字段在扁平槽块中的起始槽偏移（前面的字段按各自槽数累加）。
    size_t direct_field_slot_offset(const std::string& ty, const std::string& field,
                                    const Position& pos) const {
        auto defs = struct_fields(ty, pos);
        size_t off = 0;
        for (const auto& [fname, fty] : defs) {
            if (fname == field) return off;
            off += field_slot_width(fty);
        }
        throw TenetError::at_pos("struct `" + ty + "` 没有字段 `" + field + "`", pos);
    }

    /// S3c-3b-1：把 `a[i].x.y` 拆成 (数组变量名, 下标表达式, 字段路径 x.y)。
    /// 只看 Field/Index 链；`s.x` 这种普通 struct 字段链返回 false（交给 expr_var_path）。
    static bool struct_index_fields(const ExprPtr& e, std::vector<std::string>& path,
                                    std::string& arr_name, ExprPtr& index) {
        if (!e) return false;
        if (e->kind == Expr::Kind::Field) {
            if (!struct_index_fields(e->base, path, arr_name, index)) return false;
            path.push_back(e->field);
            return true;
        }
        if (e->kind == Expr::Kind::Index) {
            if (!e->base || e->base->kind != Expr::Kind::Var) return false;
            arr_name = e->base->name;
            index = e->index;
            return true;
        }
        return false;
    }

    /// 从解析出的左值读取标量；数组 / struct 值整体读取给出明确错误。
    std::pair<std::string, llvm::Value*> read_place(const Place& place,
                                                    const Position& pos) {
        if (place.kind == Place::Kind::Scalar) {
            if (place.slot_storage) {
                auto* raw = builder_.CreateLoad(llvm::Type::getInt64Ty(ctx_), place.addr,
                                                place.ty);
                return {llvm_type(place.ty), unpack_scalar(place.ty, raw)};
            }
            return {llvm_type(place.ty),
                    builder_.CreateLoad(ty(llvm_type(place.ty)), place.addr, place.ty)};
        }
        if (place.kind == Place::Kind::Array) {
            throw TenetError::at_pos(
                "数组值不能直接取值；请使用下标或整体赋值", pos);
        }
        throw TenetError::at_pos(
            "struct 值不能直接取值；请继续访问到标量字段", pos);
    }

    /// 把固定数组表达式写入扁平槽区（`s.a = [..]` / `s.a[i] = [..]`）。
    void store_array_place(const std::string& arr_ty, llvm::Value* addr,
                           const ExprPtr& value, const Position& pos) {
        const size_t total = fixed_array_total_slots(arr_ty);
        auto* tmp = alloc_buffer(total, "__array_store");
        pack_array_field_expr(arr_ty, value, tmp, 0);
        (void)pos;
        copy_slots(addr, tmp, total);
    }

    /// 写入解析出的左值：标量直接 store，固定数组 / struct 值先打包再逐槽覆盖。
    void store_place(const Place& place, const ExprPtr& value, const Position& pos) {
        if (place.kind == Place::Kind::Scalar) {
            auto [vt, v] = gen_expr(value);
            if (vt != llvm_type(place.ty)) {
                throw TenetError::at_pos(
                    "赋值类型不匹配：需要 " + place.ty + "，实际 " + value_type_name(vt),
                    value->pos);
            }
            if (place.slot_storage) {
                builder_.CreateStore(pack_scalar(place.ty, v), place.addr);
            } else {
                builder_.CreateStore(v, place.addr);
            }
            return;
        }
        if (place.kind == Place::Kind::Array) {
            store_array_place(place.ty, place.addr, value, pos);
            return;
        }
        if (place.addr == nullptr) {
            throw TenetError::at_pos(
                "struct 整体赋值需要可寻址的 struct 槽位；请继续访问到标量字段", pos);
        }
        const size_t slots = struct_total_slots(place.ty);
        auto* tmp = alloc_buffer(slots, "__struct_store");
        pack_expr_to_buffer(place.ty, value, tmp);
        copy_slots(place.addr, tmp, slots);
    }

    /// 把字段路径拼成 `a.b.c`（struct_index_fields 的输出）。
    static std::string join_path(const std::vector<std::string>& path) {
        std::string out;
        for (size_t i = 0; i < path.size(); ++i) {
            if (i) out += ".";
            out += path[i];
        }
        return out;
    }

    /// S3c-3b-1：表达式是否为 `array<struct>` 元素整体读取（`a[i]`）。
    bool is_struct_array_index_read(const ExprPtr& e) const {
        if (!e || e->kind != Expr::Kind::Index || !e->base ||
            e->base->kind != Expr::Kind::Var) {
            return false;
        }
        const VarInfo& info = lookup_var(e->base->name, e->base->pos);
        auto elem = array_elem(info.ty);
        return elem.has_value() && is_struct(*elem);
    }

    /// 沿 `a.x` 路径求字段类型；中间的每一层都必须是 struct。
    std::string field_type_of(const std::string& ty, const std::string& path,
                              const Position& pos) const {
        std::string cur = ty;
        size_t start = 0;
        while (start <= path.size()) {
            size_t dot = path.find('.', start);
            std::string part = path.substr(start, dot == std::string::npos ? std::string::npos
                                                                          : dot - start);
            auto fields = struct_fields(cur, pos);
            std::string next;
            bool found = false;
            for (const auto& [fname, fty] : fields) {
                if (fname == part) {
                    next = fty;
                    found = true;
                    break;
                }
            }
            if (!found) {
                throw TenetError::at_pos("struct `" + cur + "` 没有字段 `" + part + "`", pos);
            }
            cur = next;
            if (dot == std::string::npos) break;
            start = dot + 1;
        }
        return cur;
    }

    /// 把 `base.field` 链解析成 (根变量名, 字段路径)。仅支持变量与字段链。
    static std::optional<std::pair<std::string, std::string>> expr_var_path(
        const ExprPtr& e) {
        if (!e) return std::nullopt;
        if (e->kind == Expr::Kind::Var) return std::make_pair(e->name, std::string());
        if (e->kind == Expr::Kind::Field) {
            auto base = expr_var_path(e->base);
            if (!base.has_value()) return std::nullopt;
            const std::string& path = base->second;
            return std::make_pair(base->first,
                                  path.empty() ? e->field : path + "." + e->field);
        }
        return std::nullopt;
    }

    /// 取 struct 变量的标量字段槽位；路径指向中间 struct 时给出“继续访问”提示。
    std::pair<std::string, llvm::AllocaInst*> scalar_field(const VarInfo& info,
                                                           const std::string& path,
                                                           const Position& pos) const {
        auto f = info.fields.find(path);
        if (f != info.fields.end()) return f->second;
        std::string fty = field_type_of(info.ty, path, pos);
        if (is_struct(fty)) {
            throw TenetError::at_pos(
                "字段 `" + path + "` 是 struct `" + fty + "`，请继续访问到标量字段", pos);
        }
        throw TenetError::at_pos("struct `" + info.ty + "` 没有标量字段 `" + path + "`", pos);
    }

    /// 解析左值风格的数组 / struct 访问（`s.a[i]`、`s.a[i].f`、`s.a[i][j]`、
    /// `a[i].f`、`arr[i].a[j]` 等）。动态数组变量本身交给既有 descriptor 路径，
    /// 返回 nullopt；struct 的动态数组字段返回 `Place::DynArray`（S3e）。
    std::optional<Place> resolve_place(const ExprPtr& e) {
        if (!e) return std::nullopt;
        if (e->kind == Expr::Kind::Var) {
            const VarInfo& info = lookup_var(e->name, e->pos);
            if (info.dyn.has_value()) return std::nullopt;
            if (is_array(info.ty)) {
                if (!info.array_len.has_value() || info.addr == nullptr) return std::nullopt;
                return Place{Place::Kind::Array, info.ty, info.addr,
                             is_flat_slot_array(info.ty), *info.array_len, nullptr, ""};
            }
            if (is_struct(info.ty)) {
                return Place{Place::Kind::Struct, info.ty, nullptr, false, 0, &info, ""};
            }
            if (info.addr == nullptr) return std::nullopt;
            return Place{Place::Kind::Scalar, info.ty, info.addr, false, 0, nullptr, ""};
        }
        if (e->kind == Expr::Kind::Field) {
            auto base = resolve_place(e->base);
            if (!base.has_value() || base->kind != Place::Kind::Struct) return std::nullopt;
            if (base->var != nullptr) {
                std::string path =
                    base->prefix.empty() ? e->field : base->prefix + "." + e->field;
                auto f = base->var->fields.find(path);
                if (f != base->var->fields.end()) {
                    const std::string& fty = f->second.first;
                    if (is_array(fty)) {
                        auto len = array_decl_len(fty);
                        return Place{Place::Kind::Array, fty, f->second.second, true,
                                     len.value_or(0), nullptr, ""};
                    }
                    return Place{Place::Kind::Scalar, fty, f->second.second, false, 0,
                                 nullptr, ""};
                }
                // S3e：动态数组字段在局部 struct 变量里是三个独立槽位。
                auto dynf = base->var->dyn_fields.find(path);
                if (dynf != base->var->dyn_fields.end()) {
                    auto dty = field_type_of(base->var->ty, path, e->pos);
                    return Place{Place::Kind::DynArray, dty, nullptr, false, 0, nullptr,
                                 "", false, dyn_slots_of(dynf->second)};
                }
                std::string fty = field_type_of(base->var->ty, path, e->pos);
                if (is_struct(fty)) {
                    return Place{Place::Kind::Struct, fty, nullptr, false, 0, base->var, path};
                }
                if (is_dynamic_array(fty)) {
                    throw TenetError("内部错误：动态字段 `" + path + "` 缺少 descriptor");
                }
                throw TenetError::at_pos(
                    "struct `" + base->var->ty + "` 没有字段 `" + path + "`", e->pos);
            }
            std::string fty = direct_field_type(base->ty, e->field, e->pos);
            size_t off = direct_field_slot_offset(base->ty, e->field, e->pos);
            auto* faddr = flat_slot(base->addr, off);
            if (is_struct(fty)) {
                return Place{Place::Kind::Struct, fty, faddr, false, 0, nullptr, ""};
            }
            if (is_dynamic_array(fty)) {
                // S3e：ABI buffer / 数组元素里的动态字段是连续 3 个 descriptor 槽。
                return Place{Place::Kind::DynArray, fty, nullptr, false, 0, nullptr, "",
                             false, dyn_slots_at(faddr)};
            }
            if (is_array(fty)) {
                auto len = array_decl_len(fty);
                return Place{Place::Kind::Array, fty, faddr, true, len.value_or(0), nullptr,
                             ""};
            }
            return Place{Place::Kind::Scalar, fty, faddr, false, 0, nullptr, "", true};
        }
        if (e->kind == Expr::Kind::Index) {
            // S3e：动态 array<struct> 的元素（`arr[i].a[j]` / `arr[i].a = ..`）。
            if (e->base && e->base->kind == Expr::Kind::Var) {
                const VarInfo& info = lookup_var(e->base->name, e->base->pos);
                if (info.dyn.has_value()) {
                    auto elem = array_elem(info.ty);
                    if (elem.has_value() && is_struct(*elem)) {
                        auto [elem_ty, elem_addr] =
                            struct_array_elem_addr(info, e->index, e->pos);
                        return Place{Place::Kind::Struct, elem_ty, elem_addr, false, 0,
                                     nullptr, ""};
                    }
                }
            }
            auto base = resolve_place(e->base);
            if (!base.has_value()) return std::nullopt;
            if (base->kind == Place::Kind::DynArray) {
                // S3e：`s.a[i]` / `arr[i].a[j]` —— 动态描述符下标（运行时界限检查）。
                auto elem = array_elem(base->ty);
                if (!elem.has_value() || is_struct(*elem) || is_array(*elem)) {
                    throw TenetError::at_pos(
                        "v1 动态数组字段只支持标量元素，不能对 `" + base->ty + "` 取下标",
                        e->pos);
                }
                auto* i64 = llvm::Type::getInt64Ty(ctx_);
                auto* data = builder_.CreateLoad(ptr_ty(ctx_), base->dyn.data, "dyn.field.data");
                auto* len = builder_.CreateLoad(i64, base->dyn.len, "dyn.field.len");
                auto [it, iv] = gen_expr(e->index);
                if (it != "i64") {
                    throw TenetError::at_pos(
                        "数组下标必须是 int，实际为 " + std::string(tenet_name(it)),
                        e->index->pos);
                }
                bounds_check_value(iv, len);
                return Place{Place::Kind::Scalar, *elem, dyn_slot(data, iv), false, 0,
                             nullptr, "", true};
            }
            if (base->kind != Place::Kind::Array) return std::nullopt;
            auto elem = array_elem(base->ty);
            if (!elem.has_value()) {
                throw TenetError::at_pos("`" + base->ty + "` 不是数组，不能取下标", e->pos);
            }
            const size_t slots = array_elem_slots(base->ty);
            auto* idx = gen_index(e->index, base->len);
            llvm::Value* addr = nullptr;
            if (base->packed) {
                auto* i64 = llvm::Type::getInt64Ty(ctx_);
                auto* row = builder_.CreateMul(
                    idx, llvm::ConstantInt::get(i64, static_cast<uint64_t>(slots)), "arr.row");
                addr = builder_.CreateGEP(i64, base->addr, {row}, "arr.elem");
            } else {
                if (is_struct(*elem) || is_array(*elem)) {
                    throw TenetError("内部错误：扁平数组元素缺少 packed 标记");
                }
                addr = array_addr(base->addr, base->len, idx, ty(llvm_type(*elem)));
            }
            if (is_struct(*elem)) {
                return Place{Place::Kind::Struct, *elem, addr, false, 0, nullptr, ""};
            }
            if (is_array(*elem)) {
                auto len = array_decl_len(*elem);
                return Place{Place::Kind::Array, *elem, addr, true, len.value_or(0), nullptr,
                             ""};
            }
            return Place{Place::Kind::Scalar, *elem, addr, false, 0, nullptr, "",
                         base->packed};
        }
        return std::nullopt;
    }

    /// S3e：解析动态数组左值（动态数组变量 / struct 动态字段 / 数组元素动态字段），
    /// 返回 (类型, descriptor 三槽)。不是动态数组左值时返回 nullopt。
    std::optional<std::pair<std::string, DynSlots>> resolve_dyn_target(const ExprPtr& e) {
        if (!e) return std::nullopt;
        if (e->kind == Expr::Kind::Var) {
            const VarInfo& info = lookup_var(e->name, e->pos);
            if (info.dyn.has_value()) {
                return std::make_pair(info.ty, dyn_slots_of(*info.dyn));
            }
            return std::nullopt;
        }
        if (e->kind != Expr::Kind::Field && e->kind != Expr::Kind::Index) {
            return std::nullopt;
        }
        auto place = resolve_place(e);
        if (place.has_value() && place->kind == Place::Kind::DynArray) {
            return std::make_pair(place->ty, place->dyn);
        }
        return std::nullopt;
    }

    /// S3e：动态数组左值整体赋值（`s.a = [..]` / `s.a = t.a` / `arr[i].a = ..`）。
    /// 先深拷贝右侧到临时 descriptor，再 drop 目标旧缓冲区，最后接管新缓冲区。
    /// 右侧先完整求值，因此 `s.a = s.a` / `arr[i].a = arr[i].a` 这类自赋值也安全。
    void assign_dyn_place(const std::string& ty, const DynSlots& target,
                          const ExprPtr& value, const Position& pos) {
        // `s.a = s.a`：目标与源是同一组 descriptor 槽 → 空操作。
        auto src = resolve_dyn_target(value);
        if (src.has_value() && src->first == ty && src->second.data == target.data &&
            src->second.len == target.len && src->second.cap == target.cap) {
            return;
        }
        VarInfo tmp = init_dynamic_array("__assign_tmp", ty, value, pos);
        DynSlots t = dyn_slots_of(*tmp.dyn);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        auto* nd = builder_.CreateLoad(pty, t.data, "dyn.assign.data");
        auto* nl = builder_.CreateLoad(i64, t.len, "dyn.assign.len");
        auto* nc = builder_.CreateLoad(i64, t.cap, "dyn.assign.cap");
        dyn_slots_clear(t);
        dyn_drop_slots(target.data, target.len, target.cap, ty);
        builder_.CreateStore(nd, target.data);
        builder_.CreateStore(nl, target.len);
        builder_.CreateStore(nc, target.cap);
    }

    /// 类型位置允许标量或已声明的 struct 名。
    void ensure_known_type(const std::string& t, const Position& pos) const {
        if (!is_scalar(t) && !is_struct(t) && !is_array(t)) {
            throw TenetError::at_pos("未定义的 struct 或类型 `" + t + "`", pos);
        }
    }

    // ---- 声明阶段 ----

    void emit_decls(const Program& program) {
        // 运行时与内建函数声明
        auto i32 = llvm::Type::getInt32Ty(ctx_);
        auto ptr = llvm::PointerType::getUnqual(ctx_);
        // printf：变参 (i32, ptr, ...)
        auto printf_fty = llvm::FunctionType::get(i32, {ptr}, true);
        llvm::Function::Create(printf_fty, llvm::Function::ExternalLinkage, "printf", &mod_);
        // tenet_concat / tenet_strcmp
        auto concat_fty = llvm::FunctionType::get(ptr, {ptr, ptr}, false);
        llvm::Function::Create(concat_fty, llvm::Function::ExternalLinkage, "tenet_concat", &mod_);
        auto strcmp_fty = llvm::FunctionType::get(i32, {ptr, ptr}, false);
        llvm::Function::Create(strcmp_fty, llvm::Function::ExternalLinkage, "tenet_strcmp", &mod_);
        // 数组动态下标越界运行时检查
        auto i64 = llvm::Type::getInt64Ty(ctx_);
        auto bounds_fty = llvm::FunctionType::get(llvm::Type::getVoidTy(ctx_), {i64, i64}, false);
        llvm::Function::Create(bounds_fty, llvm::Function::ExternalLinkage, "tenet_bounds_fail",
                               &mod_);
        // S3c-1：动态数组缓冲区直接调用 libc（内嵌 runtime.c 已包含 stdlib.h）
        auto malloc_fty = llvm::FunctionType::get(ptr, {i64}, false);
        llvm::Function::Create(malloc_fty, llvm::Function::ExternalLinkage, "malloc", &mod_);
        auto free_fty = llvm::FunctionType::get(llvm::Type::getVoidTy(ctx_), {ptr}, false);
        llvm::Function::Create(free_fty, llvm::Function::ExternalLinkage, "free", &mod_);

        // 用户函数（先创建 Function 对象，供调用解析）
        for (const auto& stmt : program.stmts) {
            if (stmt->kind != Stmt::Kind::FnDecl) continue;
            const auto& name = stmt->name;
            if (name == "main" || name == "printf" || name == "tenet_concat" ||
                name == "tenet_strcmp" || name == "tenet_bounds_fail" || name == "malloc" ||
                name == "free") {
                throw TenetError::at_pos("函数名 `" + name + "` 为编译器保留", stmt->pos);
            }
            if (functions_.count(name)) {
                throw TenetError::at_pos("函数 `" + name + "` 重复定义", stmt->pos);
            }
            std::vector<llvm::Type*> params;
            std::vector<std::string> param_tys;
            for (const auto& [pname, pt] : stmt->params) {
                if (is_array(pt)) {
                    // S3b 定长数组 / S3c-2 动态数组 / S3c-3b-3/S3c-3c v2 扁平固定数组：
                    // ABI 都传指针；动态数组指针指向调用方栈上的 3 槽 descriptor。
                    if (is_dynamic_array(pt)) {
                        if (is_nested_array(pt)) {
                            // v1 动态嵌套数组：array<array<int/float/bool>>（descriptor ABI）。
                            ensure_dynamic_nested_scalar_array(pt, stmt->pos);
                        } else if (!has_struct_elem(pt)) {
                            array_elem_scalar(pt, stmt->pos);
                        }
                    } else if (is_nested_array(pt)) {
                        // S3c-3c v2：固定嵌套数组参数，内层只支持 int/float。
                        ensure_nested_scalar_array(pt, stmt->pos);
                    } else if (has_struct_elem(pt)) {
                        // S3c-3b-3：固定 array<struct, N> 参数（入口按 N*slots 槽拷贝）。
                        if (!array_decl_len(pt).has_value()) {
                            throw TenetError::at_pos(
                                "array<struct> 参数必须写 array<P, N>", stmt->pos);
                        }
                    } else {
                        array_elem_scalar(pt, stmt->pos);
                    }
                    params.push_back(llvm::PointerType::getUnqual(ctx_));
                    param_tys.push_back(pt);
                    continue;
                }
                ensure_known_type(pt, stmt->pos);
                // S3a ABI：struct 参数传指针（被调函数入口逐字段拷贝到本地槽位）。
                params.push_back(is_struct(pt) ? llvm::PointerType::getUnqual(ctx_)
                                               : ty(llvm_type(pt)));
                param_tys.push_back(pt);
            }
            bool ret_struct = false;
            bool ret_array = false;
            if (stmt->ret.has_value()) {
                if (is_array(*stmt->ret)) {
                    // S3b 定长数组 / S3c-2 动态数组 / S3c-3b-3/S3c-3c v2 扁平固定数组
                    // 返回值都用隐藏 `ptr %sret`，函数返回 void：定长数组 sret 指向
                    // [N x T] 或 [total x i64]，动态数组指向 3 槽 descriptor。
                    if (is_dynamic_array(*stmt->ret)) {
                        if (is_nested_array(*stmt->ret)) {
                            // v1 动态嵌套数组返回值：隐藏 sret descriptor，转移所有权。
                            ensure_dynamic_nested_scalar_array(*stmt->ret, stmt->pos);
                        } else if (!has_struct_elem(*stmt->ret)) {
                            array_elem_scalar(*stmt->ret, stmt->pos);
                        }
                    } else if (is_nested_array(*stmt->ret)) {
                        // S3c-3c v2：固定嵌套数组返回值，内层只支持 int/float。
                        ensure_nested_scalar_array(*stmt->ret, stmt->pos);
                    } else if (has_struct_elem(*stmt->ret)) {
                        // S3c-3b-3：固定 array<struct, N> 返回值（sret 按 N*slots 槽打包）。
                        if (!array_decl_len(*stmt->ret).has_value()) {
                            throw TenetError::at_pos(
                                "array<struct> 返回值必须写 array<P, N>", stmt->pos);
                        }
                    } else {
                        array_elem_scalar(*stmt->ret, stmt->pos);
                    }
                    ret_array = true;
                } else {
                    ensure_known_type(*stmt->ret, stmt->pos);
                    // S3a ABI：struct 返回值用隐藏 `ptr %sret` 第一参数，函数返回 void。
                    ret_struct = is_struct(*stmt->ret);
                }
            }
            bool ret_composite = ret_struct || ret_array;
            auto ret_ll = ret_composite ? llvm::Type::getVoidTy(ctx_)
                                       : (stmt->ret.has_value() ? ty(llvm_type(*stmt->ret))
                                                                : llvm::Type::getVoidTy(ctx_));
            if (ret_composite) {
                params.insert(params.begin(), llvm::PointerType::getUnqual(ctx_));
            }
            auto fty = llvm::FunctionType::get(ret_ll, params, false);
            auto fn = llvm::Function::Create(fty, llvm::Function::ExternalLinkage, name, &mod_);
            functions_[name] = {fn, stmt->ret, param_tys};
        }
    }

    // ---- 程序 ----

    void emit_program(const Program& program) {
        // main：i32 ()，顶层语句
        auto main_fty = llvm::FunctionType::get(llvm::Type::getInt32Ty(ctx_), {}, false);
        auto main_fn = llvm::Function::Create(main_fty, llvm::Function::ExternalLinkage, "main", &mod_);
        auto entry = llvm::BasicBlock::Create(ctx_, "entry", main_fn);
        builder_.SetInsertPoint(entry);
        symbols_.emplace_back();
        current_fn_ = "main";
        current_ret_ = std::nullopt;
        for (const auto& stmt : program.stmts) {
            if (stmt->kind == Stmt::Kind::FnDecl || stmt->kind == Stmt::Kind::StructDecl) continue;
            if (stmt->kind == Stmt::Kind::Return) {
                throw TenetError::at_pos("顶层不能使用 `return`（main 自动返回 0）", stmt->pos);
            }
            emit_stmt(stmt);
            if (builder_.GetInsertBlock()->getTerminator()) break;
        }
        current_fn_.clear();
        current_ret_ = std::nullopt;
        if (!builder_.GetInsertBlock()->getTerminator()) {
            // S3c-1：main 结尾释放顶层作用域的动态数组（逆序 / 按名排序保证 IR 稳定）
            drop_all_scopes();
            builder_.CreateRet(llvm::ConstantInt::get(ctx_, llvm::APInt(32, 0)));
        }
        symbols_.pop_back();

        // 用户函数体
        for (const auto& stmt : program.stmts) {
            if (stmt->kind != Stmt::Kind::FnDecl) continue;
            emit_fn_body(stmt);
        }
    }

    void emit_fn_body(const StmtPtr& stmt) {
        const auto& name = stmt->name;
        if (stmt->ret.has_value() &&
            (stmt->body.empty() || stmt->body.back()->kind != Stmt::Kind::Return)) {
            throw TenetError::at_pos("函数 `" + name + "` 声明了返回类型，但函数末尾没有 return",
                                     stmt->pos);
        }
        auto fn = functions_[name].fn;
        current_fn_ = name;
        current_ret_ = stmt->ret;
        current_sret_ = nullptr;
        bool ret_struct = stmt->ret.has_value() && is_struct(*stmt->ret);
        bool ret_array = stmt->ret.has_value() && is_array(*stmt->ret);
        auto entry = llvm::BasicBlock::Create(ctx_, "entry", fn);
        builder_.SetInsertPoint(entry);
        symbols_.emplace_back();
        auto arg_it = fn->arg_begin();
        if (ret_struct || ret_array) {
            current_sret_ = &*arg_it;
            current_sret_->setName("sret");
            ++arg_it;
        }
        for (size_t i = 0; i < stmt->params.size(); ++i) {
            const auto& [pname, pty] = stmt->params[i];
            llvm::Argument* arg = &*arg_it;
            arg->setName("p" + std::to_string(i));
            if (is_dynamic_array(pty)) {
                // S3c-2 动态数组参数：参数是 3 槽 descriptor 指针；
                // 入口按 descriptor 的 data/len/cap 深拷贝到本地动态数组（值语义）。
                VarInfo info = dynamic_param_from_desc(pty, arg, pname, stmt->pos);
                symbols_.back()[pname] = std::move(info);
            } else if (is_array(pty)) {
                // S3b 定长数组参数：指针 ABI + 入口逐元素拷贝到本地（值语义）。
                auto len = array_decl_len(pty);
                if (!len.has_value()) {
                    throw TenetError("内部错误：非动态数组缺少定长长度");
                }
                if (is_flat_slot_array(pty)) {
                    // S3c-3b-3/S3c-3c v2：struct 元素 / 固定嵌套数组按总槽数
                    // （N*slots 或 M*N）拷贝到本地 `[total x i64]` 扁平缓冲。
                    // S3e：元素含动态字段时逐元素深拷贝（入口值语义）。
                    const size_t total = fixed_array_total_slots(pty);
                    auto* addr = alloc_buffer(total, pname);
                    if (type_owns_heap(pty)) {
                        deep_copy_value(pty, addr, arg);
                    } else {
                        copy_flat_i64(addr, arg, total);
                    }
                    symbols_.back()[pname] = VarInfo{pty, addr, {}, *len};
                } else {
                    std::string elem = array_elem_scalar(pty, stmt->pos);
                    llvm::Type* elem_ty = ty(llvm_type(elem));
                    auto* addr = builder_.CreateAlloca(
                        llvm::ArrayType::get(elem_ty, *len), nullptr, pname);
                    copy_array_ptr(addr, arg, *len, elem_ty);
                    symbols_.back()[pname] =
                        VarInfo{pty, llvm::cast<llvm::AllocaInst>(addr), {}, *len};
                }
            } else if (is_struct(pty)) {
                // struct 参数：入口按扁平布局把指针指向的字段值拷贝到本地槽位（值语义）。
                // S3e：动态数组字段重新 malloc 深拷贝，参数与调用方完全独立。
                VarInfo info = alloc_struct(pty, stmt->pos);
                unpack_buffer(info, pty, arg, /*deep=*/true);
                symbols_.back()[pname] = std::move(info);
            } else {
                auto addr = builder_.CreateAlloca(arg->getType(), nullptr, pname);
                builder_.CreateStore(arg, addr);
                symbols_.back()[pname] = {pty, llvm::cast<llvm::AllocaInst>(addr), {}};
            }
            ++arg_it;
        }
        for (const auto& s : stmt->body) { emit_stmt(s); if (builder_.GetInsertBlock()->getTerminator()) break; }
        if (!builder_.GetInsertBlock()->getTerminator()) {
            // S3c-1：函数正常落到底时释放所有作用域的动态数组
            drop_all_scopes();
        }
        symbols_.pop_back();
        current_fn_.clear();
        current_ret_ = std::nullopt;
        current_sret_ = nullptr;
        if (!builder_.GetInsertBlock()->getTerminator() && !stmt->ret.has_value()) {
            builder_.CreateRetVoid();
        }
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
                        throw TenetError::at_pos("无法推断 `" + stmt->name + "` 的类型，请显式标注",
                                                 stmt->pos);
                    }
                    t = *inf;
                }
                ensure_known_type(t, stmt->pos);
                if (is_array(t)) {
                    // S3c-1：显式标注 `array<T>`（无长度）是局部动态数组；`array<T, N>` 仍是定长值数组。
                    if (is_dynamic_array(t)) {
                        VarInfo info = init_dynamic_array(stmt->name, t, stmt->value, stmt->pos);
                        symbols_.back()[stmt->name] = std::move(info);
                        return;
                    }
                    VarInfo info = init_array(stmt->name, t, stmt->value, stmt->pos);
                    symbols_.back()[stmt->name] = std::move(info);
                    return;
                }
                if (is_struct(t)) {
                    VarInfo info = init_struct(stmt->name, t, stmt->value, stmt->pos);
                    symbols_.back()[stmt->name] = std::move(info);
                    return;
                }
                auto [vt, v] = gen_expr(stmt->value);
                if (vt != llvm_type(t)) {
                    throw TenetError::at_pos(
                        "`" + stmt->name + "` 初始化类型不匹配：标注 " + t + "，实际 " +
                            value_type_name(vt),
                        stmt->pos);
                }
                auto addr = builder_.CreateAlloca(ty(llvm_type(t)), nullptr, stmt->name);
                builder_.CreateStore(v, addr);
                symbols_.back()[stmt->name] = {t, llvm::cast<llvm::AllocaInst>(addr), {}};
                return;
            }
            case Stmt::Kind::Expr:
                gen_expr(stmt->expr);
                return;
            case Stmt::Kind::If: {
                auto [ct, c] = gen_expr(stmt->cond);
                if (ct != "i1") {
                    throw TenetError::at_pos("条件表达式需要 bool，实际为 " + value_type_name(ct),
                                             stmt->cond->pos);
                }
                auto then_bb = llvm::BasicBlock::Create(ctx_, "then");
                auto else_bb = llvm::BasicBlock::Create(ctx_, "else");
                auto merge_bb = llvm::BasicBlock::Create(ctx_, "merge");
                builder_.CreateCondBr(c, then_bb, else_bb);

                auto fn = builder_.GetInsertBlock()->getParent();
                then_bb->insertInto(fn);
                builder_.SetInsertPoint(then_bb);
                symbols_.emplace_back();
                for (const auto& s : stmt->then_branch) { emit_stmt(s); if (builder_.GetInsertBlock()->getTerminator()) break; }
                if (!builder_.GetInsertBlock()->getTerminator()) drop_scope();
                symbols_.pop_back();
                if (!builder_.GetInsertBlock()->getTerminator()) builder_.CreateBr(merge_bb);

                else_bb->insertInto(fn);
                builder_.SetInsertPoint(else_bb);
                if (!stmt->else_branch.empty()) {
                    symbols_.emplace_back();
                    for (const auto& s : stmt->else_branch) { emit_stmt(s); if (builder_.GetInsertBlock()->getTerminator()) break; }
                    if (!builder_.GetInsertBlock()->getTerminator()) drop_scope();
                    symbols_.pop_back();
                }
                if (!builder_.GetInsertBlock()->getTerminator()) builder_.CreateBr(merge_bb);

                merge_bb->insertInto(fn);
                builder_.SetInsertPoint(merge_bb);
                return;
            }
            case Stmt::Kind::While: {
                auto fn = builder_.GetInsertBlock()->getParent();
                auto cond_bb = llvm::BasicBlock::Create(ctx_, "cond");
                auto body_bb = llvm::BasicBlock::Create(ctx_, "body");
                auto exit_bb = llvm::BasicBlock::Create(ctx_, "exit");
                builder_.CreateBr(cond_bb);

                cond_bb->insertInto(fn);
                builder_.SetInsertPoint(cond_bb);
                auto [ct, c] = gen_expr(stmt->cond);
                if (ct != "i1") {
                    throw TenetError::at_pos("条件表达式需要 bool，实际为 " + value_type_name(ct),
                                             stmt->cond->pos);
                }
                builder_.CreateCondBr(c, body_bb, exit_bb);

                body_bb->insertInto(fn);
                builder_.SetInsertPoint(body_bb);
                symbols_.emplace_back();
                // S3c-1：记录循环体作用域深度，break 时 drop 该层及内层动态数组
                break_stack_.push_back({exit_bb, symbols_.size()});
                for (const auto& s : stmt->body) { emit_stmt(s); if (builder_.GetInsertBlock()->getTerminator()) break; }
                if (!builder_.GetInsertBlock()->getTerminator()) {
                    // 每轮循环结束（离开循环体作用域）drop 动态数组
                    drop_scope();
                }
                break_stack_.pop_back();
                symbols_.pop_back();
                if (!builder_.GetInsertBlock()->getTerminator()) builder_.CreateBr(cond_bb);

                exit_bb->insertInto(fn);
                builder_.SetInsertPoint(exit_bb);
                return;
            }
            case Stmt::Kind::Return: {
                if (stmt->expr) {
                    if (!current_ret_.has_value()) {
                        throw TenetError::at_pos("函数 `" + current_fn_ + "` 没有返回类型，不能 return 值",
                                                 stmt->expr->pos);
                    }
                    if (is_struct(*current_ret_)) {
                        // struct 返回值：写到隐藏 sret 指针，函数返回 void。
                        if (current_sret_ == nullptr) {
                            throw TenetError("内部错误：struct 返回函数缺少 sret 参数");
                        }
                        // S3e：变量返回转移动态 descriptor 并清空本地；字面量 / 调用
                        // 结果同样把所有权交给 sret。
                        transfer_struct_expr_to_sret(*current_ret_, stmt->expr, current_sret_);
                        drop_all_scopes();
                        builder_.CreateRetVoid();
                        return;
                    }
                    if (is_dynamic_array(*current_ret_)) {
                        // S3c-2/S3c-3a 动态数组返回值：变量 / 字面量 / 调用结果把
                        // data/len/cap 转移进隐藏 sret descriptor（不 free），随后 drop
                        // 其他局部。
                        if (current_sret_ == nullptr) {
                            throw TenetError("内部错误：动态数组返回函数缺少 sret 参数");
                        }
                        transfer_dynamic_expr_to_sret(*current_ret_, stmt->expr, current_sret_);
                        drop_all_scopes();
                        builder_.CreateRetVoid();
                        return;
                    }
                    if (is_array(*current_ret_)) {
                        // S3b 定长数组返回值：打包到隐藏 sret 缓冲区，函数返回 void。
                        if (current_sret_ == nullptr) {
                            throw TenetError("内部错误：数组返回函数缺少 sret 参数");
                        }
                        auto len = array_decl_len(*current_ret_);
                        if (!len.has_value()) {
                            throw TenetError("内部错误：固定数组缺少定长长度");
                        }
                        pack_array_expr_to_buffer(*current_ret_, *len, stmt->expr, current_sret_);
                        drop_all_scopes();
                        builder_.CreateRetVoid();
                        return;
                    }
                    auto [t, v] = gen_expr(stmt->expr);
                    if (is_struct(t) || std::string(tenet_name(t)) != *current_ret_) {
                        throw TenetError::at_pos(
                            "函数 `" + current_fn_ + "` 返回类型不匹配：声明 " + *current_ret_ +
                                "，实际 " + value_type_name(t),
                            stmt->expr->pos);
                    }
                    drop_all_scopes();
                    builder_.CreateRet(v);
                } else {
                    if (current_ret_.has_value()) {
                        throw TenetError::at_pos(
                            "函数 `" + current_fn_ + "` 声明了返回类型 " + *current_ret_ +
                                "，return 必须带值",
                            stmt->pos);
                    }
                    drop_all_scopes();
                    builder_.CreateRetVoid();
                }
                return;
            }
            case Stmt::Kind::Break: {
                if (break_stack_.empty()) {
                    throw TenetError::at_pos("`break` 出现在循环之外", stmt->pos);
                }
                // S3c-1：break 退出循环前 drop 循环体（含内层块）里的动态数组。
                const BreakTarget target = break_stack_.back();
                drop_scopes_from(target.scope_depth);
                builder_.CreateBr(target.exit);
                return;
            }
            case Stmt::Kind::FnDecl:
            case Stmt::Kind::StructDecl:
                return;
        }
    }

    // ---- 表达式 ----

    /// 生成表达式，返回 (LLVM 类型, 值)。
    std::pair<std::string, llvm::Value*> gen_expr(const ExprPtr& e) {
        switch (e->kind) {
            case Expr::Kind::Int:
                return {"i64", llvm::ConstantInt::get(ctx_, llvm::APInt(64, e->int_val))};
            case Expr::Kind::Float:
                return {"double", llvm::ConstantFP::get(ctx_, llvm::APFloat(e->float_val))};
            case Expr::Kind::Str: {
                auto g = builder_.CreateGlobalStringPtr(e->str_val, ".str." + std::to_string(globals_str_++));
                return {"ptr", g};
            }
            case Expr::Kind::Bool:
                return {"i1", llvm::ConstantInt::get(ctx_, llvm::APInt(1, e->bool_val ? 1 : 0))};
            case Expr::Kind::Var: {
                const VarInfo& info = lookup_var(e->name, e->pos);
                if (info.dyn.has_value()) {
                    throw TenetError::at_pos(
                        "动态数组变量 `" + e->name + "` 不能直接取值；请用下标或整体拷贝", e->pos);
                }
                if (info.array_len.has_value()) {
                    throw TenetError::at_pos(
                        "数组变量 `" + e->name + "` 不能直接取值；请用下标或整体拷贝", e->pos);
                }
                if (info.addr == nullptr) {
                    throw TenetError::at_pos(
                        "struct 变量 `" + e->name + "` 不能直接取值；请用字段访问或整体拷贝", e->pos);
                }
                return {llvm_type(info.ty),
                        builder_.CreateLoad(ty(llvm_type(info.ty)), info.addr, e->name)};
            }
            case Expr::Kind::Index: {
                const ExprPtr& base = e->base;
                // S3c-3c v1：嵌套数组 a[i][j] 读取（内层标量按扁平 8 字节槽存放）。
                // v1 动态嵌套数组：外层元素是内层 descriptor，二级下标各自做边界检查。
                if (base->kind == Expr::Kind::Index && base->base &&
                    base->base->kind == Expr::Kind::Var) {
                    const VarInfo& outer_info =
                        lookup_var(base->base->name, base->base->pos);
                    auto outer_elem = array_elem(outer_info.ty);
                    if (outer_elem.has_value() && is_array(*outer_elem)) {
                        std::string elem_name;
                        llvm::Value* addr = nullptr;
                        if (outer_info.dyn.has_value()) {
                            auto r = nested_dynamic_index_addr(
                                outer_info, base->index, e->index, e->pos);
                            elem_name = r.first;
                            addr = r.second;
                        } else {
                            auto r = nested_index_addr(outer_info, base->index, e->index,
                                                       e->pos);
                            elem_name = r.first;
                            addr = r.second;
                        }
                        auto* raw =
                            builder_.CreateLoad(llvm::Type::getInt64Ty(ctx_), addr, "nest.elem");
                        return {llvm_type(elem_name), unpack_scalar(elem_name, raw)};
                    }
                }
                if (base->kind != Expr::Kind::Var) {
                    // struct 数组字段 / 数组元素字段链：s.a[i]、s.a[i][j] 等。
                    auto place = resolve_place(e);
                    if (place.has_value()) {
                        if (place->kind == Place::Kind::Scalar) {
                            return read_place(*place, e->pos);
                        }
                        if (place->kind == Place::Kind::Struct) {
                            throw TenetError::at_pos(
                                "不支持整体读取 array<struct> 元素；请访问标量字段", e->pos);
                        }
                        throw TenetError::at_pos(
                            "不支持整体读取嵌套数组元素；请用 a[i][j]", e->pos);
                    }
                    throw TenetError::at_pos("v1 只支持对数组变量取下标", base->pos);
                }
                const VarInfo& info = lookup_var(base->name, base->pos);
                auto elem = array_elem(info.ty);
                if (!elem.has_value()) {
                    throw TenetError::at_pos("`" + base->name + "` 不是数组，不能取下标",
                                             base->pos);
                }
                if (is_struct(*elem)) {
                    // S3c-3b-1/S3c-3b-2：暂不支持把数组元素整体当成 struct 值读取。
                    throw TenetError::at_pos(
                        "不支持整体读取 array<struct> 元素；请访问标量字段", e->pos);
                }
                if (is_array(*elem)) {
                    // S3c-3c v1：嵌套数组只支持 a[i][j] 逐层下标，不整体读取内层数组。
                    throw TenetError::at_pos(
                        "不支持整体读取嵌套数组元素；请用 a[i][j]", e->pos);
                }
                if (info.dyn.has_value()) {
                    // S3c-1：动态数组下标 → 运行时 len 越界检查 + 8 字节槽解包
                    auto [elem_name, slot] = dynamic_index_addr(info, e->index);
                    auto* raw = builder_.CreateLoad(llvm::Type::getInt64Ty(ctx_), slot, "dyn.elem");
                    return {llvm_type(elem_name), unpack_scalar(elem_name, raw)};
                }
                if (!info.array_len.has_value() || info.addr == nullptr) {
                    throw TenetError::at_pos("`" + base->name + "` 不是数组，不能取下标",
                                             base->pos);
                }
                std::string elem_ll = llvm_type(*elem);
                llvm::Value* idx = gen_index(e->index, *info.array_len);
                auto* addr = array_addr(info.addr, *info.array_len, idx, ty(elem_ll.c_str()));
                return {elem_ll, builder_.CreateLoad(ty(elem_ll.c_str()), addr, "a.elem")};
            }
            case Expr::Kind::Field: {
                // S3c-3b-1：`a[i].field` / `a[i].p.x` —— array<struct, N> 元素字段读取。
                std::vector<std::string> ipath;
                std::string arr_name;
                ExprPtr arr_index;
                if (struct_index_fields(e, ipath, arr_name, arr_index)) {
                    const std::string path = join_path(ipath);
                    const VarInfo& info = lookup_var(arr_name, e->base->pos);
                    auto [elem_ty, elem_addr] =
                        struct_array_elem_addr(info, arr_index, e->pos);
                    std::string fty = field_type_of(elem_ty, path, e->pos);
                    if (is_struct(fty)) {
                        throw TenetError::at_pos(
                            "字段 `" + path + "` 是 struct `" + fty +
                                "`，请继续访问到标量字段",
                            e->pos);
                    }
                    if (is_array(fty)) {
                        throw TenetError::at_pos(
                            "数组字段 `" + path + "` 不能直接取值；请使用下标或整体赋值",
                            e->pos);
                    }
                    auto off = field_offset(elem_ty, path);
                    if (!off.has_value()) {
                        throw TenetError::at_pos(
                            "struct `" + elem_ty + "` 没有标量字段 `" + path + "`", e->pos);
                    }
                    auto* i64 = llvm::Type::getInt64Ty(ctx_);
                    auto* addr = builder_.CreateGEP(
                        i64, elem_addr,
                        {llvm::ConstantInt::get(i64, static_cast<uint64_t>(*off))}, "a.field");
                    // 字段槽统一按 i64 存取：float↔bitcast、bool↔zext/trunc，
                    // 保证元素整体/深拷贝时 8 字节槽完整。
                    auto* raw = builder_.CreateLoad(i64, addr, path);
                    return {llvm_type(fty), unpack_scalar(fty, raw)};
                }
                auto vp = expr_var_path(e->base);
                if (!vp.has_value()) {
                    // 扩展左值链：s.a[i].x / a[i].x / s.a[i][j].x 等。
                    auto place = resolve_place(e);
                    if (place.has_value()) {
                        if (place->kind == Place::Kind::Scalar) {
                            return read_place(*place, e->pos);
                        }
                        if (place->kind == Place::Kind::Array) {
                            throw TenetError::at_pos(
                                "数组值不能直接取值；请使用下标或整体赋值", e->pos);
                        }
                        throw TenetError::at_pos(
                            "struct 值不能直接取值；请继续访问到标量字段", e->pos);
                    }
                    throw TenetError::at_pos(
                        "v1 只支持对 struct 变量取字段（不支持任意表达式字段）", e->base->pos);
                }
                const std::string& name = vp->first;
                std::string path =
                    vp->second.empty() ? e->field : vp->second + "." + e->field;
                const VarInfo& info = lookup_var(name, e->base->pos);
                if (!is_struct(info.ty)) {
                    throw TenetError::at_pos(
                        "`" + name + "` 不是 struct，不能取字段 `" + e->field + "`",
                        e->base->pos);
                }
                std::string fty0 = field_type_of(info.ty, path, e->pos);
                if (is_array(fty0)) {
                    throw TenetError::at_pos(
                        "数组字段 `" + path + "` 不能直接取值；请使用下标或整体赋值",
                        e->pos);
                }
                auto [fty, addr] = scalar_field(info, path, e->pos);
                return {llvm_type(fty), builder_.CreateLoad(ty(llvm_type(fty)), addr, path)};
            }
            case Expr::Kind::Array:
                throw TenetError::at_pos("数组字面量只能用于 let 初始化或整体赋值", e->pos);
            case Expr::Kind::StructLit:
                throw TenetError::at_pos("struct 字面量只能用于 let 初始化或整体赋值", e->pos);
            case Expr::Kind::Assign: {
                const ExprPtr& target = e->lhs;
                if (target->kind == Expr::Kind::Var) {
                    const VarInfo& info = lookup_var(target->name, target->pos);
                    if (info.dyn.has_value()) {
                        // S3c-1：整体赋值 = 先深拷贝到临时 descriptor，drop 旧值后接管
                        assign_dynamic(target->name, info, e->value, e->pos);
                        return {info.ty, nullptr};
                    }
                    if (is_array(info.ty)) {
                        assign_array(info, e->value, e->pos);
                        return {info.ty, nullptr};
                    }
                    if (is_struct(info.ty)) {
                        assign_struct(info, e->value, e->pos);
                        return {info.ty, nullptr};
                    }
                    if (info.addr == nullptr) {
                        throw TenetError::at_pos("`" + target->name + "` 不是可赋值标量",
                                                 target->pos);
                    }
                    auto [vt, v] = gen_expr(e->value);
                    if (vt != llvm_type(info.ty)) {
                        throw TenetError::at_pos(
                            "赋值类型不匹配：`" + target->name + "` 是 " + info.ty + "，右侧是 " +
                                value_type_name(vt),
                            e->pos);
                    }
                    builder_.CreateStore(v, info.addr);
                    return {vt, v};
                }
                if (target->kind == Expr::Kind::Field) {
                    // S3c-3b-1：`a[i].field = v` / `a[i].p.x = v` —— array<struct> 元素字段写入。
                    std::vector<std::string> ipath;
                    std::string arr_name;
                    ExprPtr arr_index;
                    if (struct_index_fields(target, ipath, arr_name, arr_index)) {
                        const std::string path = join_path(ipath);
                        const VarInfo& info = lookup_var(arr_name, target->base->pos);
                        auto [elem_ty, elem_addr] =
                            struct_array_elem_addr(info, arr_index, target->pos);
                        std::string fty = field_type_of(elem_ty, path, target->pos);
                        if (is_struct(fty)) {
                            throw TenetError::at_pos(
                                "字段 `" + path + "` 是 struct `" + fty +
                                    "`，请继续访问到标量字段",
                                target->pos);
                        }
                        if (is_array(fty)) {
                            if (is_dynamic_array(fty)) {
                                // S3e：数组元素的动态字段整体赋值。
                                auto dt = resolve_dyn_target(target);
                                if (!dt.has_value()) {
                                    throw TenetError::at_pos(
                                        "动态数组字段 `" + path + "` 不能整体赋值",
                                        target->pos);
                                }
                                assign_dyn_place(fty, dt->second, e->value, e->pos);
                                return {fty, nullptr};
                            }
                            auto place = resolve_place(target);
                            if (!place.has_value()) {
                                throw TenetError::at_pos(
                                    "数组字段 `" + path + "` 不能整体赋值", target->pos);
                            }
                            store_place(*place, e->value, e->pos);
                            return {fty, nullptr};
                        }
                        auto off = field_offset(elem_ty, path);
                        if (!off.has_value()) {
                            throw TenetError::at_pos(
                                "struct `" + elem_ty + "` 没有标量字段 `" + path + "`",
                                target->pos);
                        }
                        auto [vt, v] = gen_expr(e->value);
                        if (vt != llvm_type(fty)) {
                            throw TenetError::at_pos(
                                "字段 `" + path + "` 类型不匹配：需要 " + fty + "，实际 " +
                                    value_type_name(vt),
                                e->value->pos);
                        }
                        auto* i64 = llvm::Type::getInt64Ty(ctx_);
                        auto* addr = builder_.CreateGEP(
                            i64, elem_addr,
                            {llvm::ConstantInt::get(i64,
                                                    static_cast<uint64_t>(*off))},
                            "a.field");
                        // 与字段读取对称：标量打包进 8 字节槽（float↔bitcast、bool↔zext）。
                        builder_.CreateStore(pack_scalar(fty, v), addr);
                        return {vt, v};
                    }
                    auto vp = expr_var_path(target->base);
                    if (!vp.has_value()) {
                        // 扩展左值链：s.a[i].x = v / a[i].x = v 等。
                        auto place = resolve_place(target);
                        if (place.has_value()) {
                            std::string pty = place->ty;
                            store_place(*place, e->value, e->pos);
                            return {pty, nullptr};
                        }
                        throw TenetError::at_pos("v1 只支持对 struct 变量写字段",
                                                 target->base->pos);
                    }
                    const std::string& name = vp->first;
                    std::string path = vp->second.empty()
                                           ? target->field
                                           : vp->second + "." + target->field;
                    const VarInfo& info = lookup_var(name, target->base->pos);
                    if (!is_struct(info.ty)) {
                        throw TenetError::at_pos(
                            "`" + name + "` 不是 struct，不能写字段 `" + target->field + "`",
                            target->base->pos);
                    }
                    std::string fty0 = field_type_of(info.ty, path, target->pos);
                    if (is_dynamic_array(fty0)) {
                        // S3e：动态数组字段整体赋值（s.a = [..] / s.a = t.a）。
                        auto dt = resolve_dyn_target(target);
                        if (!dt.has_value()) {
                            throw TenetError::at_pos(
                                "动态数组字段 `" + path + "` 不能整体赋值", target->pos);
                        }
                        if (dt->first != fty0) {
                            throw TenetError::at_pos(
                                "字段 `" + path + "` 类型不匹配：需要 " + fty0 + "，实际 " +
                                    value_type_name(dt->first),
                                target->pos);
                        }
                        assign_dyn_place(fty0, dt->second, e->value, e->pos);
                        return {fty0, nullptr};
                    }
                    if (is_array(fty0)) {
                        // struct 的固定数组字段整体赋值：s.a = [..] / s.a = t.a。
                        auto place = resolve_place(target);
                        if (!place.has_value()) {
                            throw TenetError::at_pos(
                                "数组字段 `" + path + "` 不能整体赋值", target->pos);
                        }
                        store_place(*place, e->value, e->pos);
                        return {fty0, nullptr};
                    }
                    auto [fty, addr] = scalar_field(info, path, target->pos);
                    auto [vt, v] = gen_expr(e->value);
                    if (vt != llvm_type(fty)) {
                        throw TenetError::at_pos(
                            "字段 `" + path + "` 类型不匹配：需要 " + fty + "，实际 " +
                                value_type_name(vt),
                            e->value->pos);
                    }
                    builder_.CreateStore(v, addr);
                    return {vt, v};
                }
                if (target->kind == Expr::Kind::Index) {
                    const ExprPtr& base = target->base;
                    // S3c-3c v1：嵌套数组 a[i][j] 写入（内层标量按 8 字节槽打包）。
                    // v1 动态嵌套数组：外层元素是内层 descriptor，二级下标各自做边界检查。
                    if (base->kind == Expr::Kind::Index && base->base &&
                        base->base->kind == Expr::Kind::Var) {
                        const VarInfo& outer_info =
                            lookup_var(base->base->name, base->base->pos);
                        auto outer_elem = array_elem(outer_info.ty);
                        if (outer_elem.has_value() && is_array(*outer_elem)) {
                            std::string elem_name;
                            llvm::Value* addr = nullptr;
                            if (outer_info.dyn.has_value()) {
                                auto r = nested_dynamic_index_addr(
                                    outer_info, base->index, target->index, target->pos);
                                elem_name = r.first;
                                addr = r.second;
                            } else {
                                auto r = nested_index_addr(outer_info, base->index,
                                                           target->index, target->pos);
                                elem_name = r.first;
                                addr = r.second;
                            }
                            auto [vt, v] = gen_expr(e->value);
                            if (vt != llvm_type(elem_name)) {
                                throw TenetError::at_pos(
                                    "数组元素赋值类型不匹配：需要 " + elem_name + "，实际 " +
                                        value_type_name(vt),
                                    e->value->pos);
                            }
                            builder_.CreateStore(pack_scalar(elem_name, v), addr);
                            return {vt, v};
                        }
                    }
                    if (base->kind != Expr::Kind::Var) {
                        // struct 数组字段 / 数组元素字段链写入：s.a[i] = v、s.a[i][j] = v。
                        auto place = resolve_place(target);
                        if (place.has_value()) {
                            std::string pty = place->ty;
                            store_place(*place, e->value, e->pos);
                            return {pty, nullptr};
                        }
                        throw TenetError::at_pos("v1 只支持对数组变量写下标", base->pos);
                    }
                    const VarInfo& info = lookup_var(base->name, base->pos);
                    auto elem = array_elem(info.ty);
                    if (!elem.has_value()) {
                        throw TenetError::at_pos("`" + base->name + "` 不是数组，不能写下标",
                                                 base->pos);
                    }
                    if (is_array(*elem)) {
                        // v1：内层数组只支持 a[i][j] 逐层下标，不能整体赋值 a[i] = [...]
                        throw TenetError::at_pos(
                            "暂不支持整体赋值 `" + base->name +
                                "[i] = ...`；请使用 `" + base->name + "[i][j] = ...`",
                            target->pos);
                    }
                    if (is_struct(*elem)) {
                        // S3c-3b-1/S3c-3b-2：`a[i] = struct` —— 先完整求值到临时
                        // [slots x i64] 缓冲，再逐槽写入元素（避免右侧引用同一元素时
                        // 边算边写导致读到被覆盖的字段）。
                        auto [elem_ty, elem_addr] =
                            struct_array_elem_addr(info, target->index, target->pos);
                        const size_t slots = array_elem_slots(info.ty);
                        auto* tmp = alloc_buffer(slots, "a.elem.tmp");
                        pack_expr_to_buffer(elem_ty, e->value, tmp);
                        auto* i64 = llvm::Type::getInt64Ty(ctx_);
                        for (size_t k = 0; k < slots; ++k) {
                            auto* v = builder_.CreateLoad(i64, buffer_slot(tmp, slots, k));
                            auto* dst = builder_.CreateGEP(
                                i64, elem_addr,
                                {llvm::ConstantInt::get(i64, static_cast<uint64_t>(k))});
                            builder_.CreateStore(v, dst);
                        }
                        return {elem_ty, nullptr};
                    }
                    if (info.dyn.has_value()) {
                        // S3c-1：动态数组元素写入（运行时越界检查 + 打包成 8 字节槽）
                        std::string elem_name = array_elem_scalar(info.ty, target->pos);
                        auto [delem, slot] = dynamic_index_addr(info, target->index);
                        (void)delem;
                        auto [vt, v] = gen_expr(e->value);
                        if (vt != llvm_type(elem_name)) {
                            throw TenetError::at_pos(
                                "数组元素赋值类型不匹配：需要 " + elem_name + "，实际 " +
                                    tenet_name(vt),
                                e->value->pos);
                        }
                        builder_.CreateStore(pack_scalar(elem_name, v), slot);
                        return {vt, v};
                    }
                    if (!info.array_len.has_value() || info.addr == nullptr) {
                        throw TenetError::at_pos("`" + base->name + "` 不是数组，不能写下标",
                                                 base->pos);
                    }
                    std::string elem_ll = llvm_type(*elem);
                    llvm::Value* idx = gen_index(target->index, *info.array_len);
                    auto [vt, v] = gen_expr(e->value);
                    if (vt != elem_ll) {
                        throw TenetError::at_pos(
                            "数组元素赋值类型不匹配：需要 " + *elem + "，实际 " + tenet_name(vt),
                            e->value->pos);
                    }
                    auto* addr = array_addr(info.addr, *info.array_len, idx, ty(elem_ll.c_str()));
                    builder_.CreateStore(v, addr);
                    return {vt, v};
                }
                throw TenetError::at_pos("赋值左侧必须是变量或字段", target->pos);
            }
            case Expr::Kind::Unary: {
                auto [t, v] = gen_expr(e->value);
                if (is_struct(t)) {
                    throw TenetError::at_pos(
                        "运算符 `" + e->op + "` 不能作用于 struct `" + t + "`", e->value->pos);
                }
                if (is_array(t)) {
                    throw TenetError::at_pos(
                        "运算符 `" + e->op + "` 不能作用于数组 `" + t + "`", e->value->pos);
                }
                if (e->op == OP_NEG) {
                    if (t == "i1") {
                        throw TenetError::at_pos("运算符 `-` 不能作用于 bool", e->value->pos);
                    }
                    if (t == "i64") return {t, builder_.CreateNeg(v)};
                    return {t, builder_.CreateFNeg(v)};
                }
                // !
                if (t != "i1") {
                    throw TenetError::at_pos("运算符 `!` 只能作用于 bool，实际为 " + std::string(tenet_name(t)),
                                             e->value->pos);
                }
                return {"i1", builder_.CreateXor(llvm::ConstantInt::getTrue(ctx_), v)};
            }
            case Expr::Kind::Binary: {
                if (e->op == OP_AND || e->op == OP_OR) return gen_logic(e->op, e->lhs, e->rhs);
                auto [lt, lv] = gen_expr(e->lhs);
                auto [rt, rv] = gen_expr(e->rhs);
                if (is_struct(lt) || is_struct(rt)) {
                    throw TenetError::at_pos("运算符 `" + e->op + "` 不能作用于 struct 值",
                                             e->pos);
                }
                if (is_array(lt) || is_array(rt)) {
                    throw TenetError::at_pos("运算符 `" + e->op + "` 不能作用于数组",
                                             e->pos);
                }
                return gen_arith(e->op, lt, lv, rt, rv, e->pos);
            }
            case Expr::Kind::Call:
                return gen_call(e->name, e->args, e->pos);
        }
        throw TenetError("未知的表达式类型");
    }

    const VarInfo& lookup_var(const std::string& name, const Position& pos) const {
        for (auto it = symbols_.rbegin(); it != symbols_.rend(); ++it) {
            auto f = it->find(name);
            if (f != it->end()) return f->second;
        }
        throw TenetError::at_pos("未定义的变量 `" + name + "`", pos);
    }

    /// 为 struct 局部变量分配扁平字段槽位（嵌套路径如 `a.x`，每个叶子一个 alloca）。
    /// S3e：动态数组字段分配 3 个 descriptor 槽（data/len/cap），单独记录在
    /// dyn_fields 里；固定数组字段仍是扁平 `[slots x i64]`。
    VarInfo alloc_struct(const std::string& ty_name, const Position& pos) {
        if (!is_struct(ty_name)) {
            throw TenetError::at_pos("未定义的 struct `" + ty_name + "`", pos);
        }
        VarInfo info;
        info.ty = ty_name;
        for (const auto& entry : layout_of(ty_name)) {
            if (is_dynamic_array(entry.ty)) {
                info.dyn_fields[entry.path] = dyn_new_slots(entry.path);
                continue;
            }
            if (is_array(entry.ty)) {
                // 固定数组字段统一用扁平 `[slots x i64]` 槽表示。
                info.fields[entry.path] = {entry.ty, alloc_buffer(entry.slots, entry.path)};
            } else {
                auto* addr =
                    builder_.CreateAlloca(ty(llvm_type(entry.ty)), nullptr, entry.path);
                info.fields[entry.path] = {entry.ty, addr};
            }
        }
        return info;
    }

    // ---- S3a struct ABI 缓冲区：统一用 [N x i64] 槽位 ----
    // 布局：所有标量字段 8 字节槽，深度优先按声明顺序。
    // int → i64；float → bitcast double↔i64；bool → zext/trunc i1↔i64。

    llvm::AllocaInst* alloc_buffer(size_t n, const std::string& name) {
        auto* arr = llvm::ArrayType::get(llvm::Type::getInt64Ty(ctx_), n);
        return builder_.CreateAlloca(arr, nullptr, name);
    }

    llvm::Value* buffer_slot(llvm::Value* buf, size_t n, size_t i) {
        auto* arr = llvm::ArrayType::get(llvm::Type::getInt64Ty(ctx_), n);
        llvm::Value* idxs[] = {
            llvm::ConstantInt::get(llvm::Type::getInt64Ty(ctx_), 0),
            llvm::ConstantInt::get(llvm::Type::getInt64Ty(ctx_), static_cast<uint64_t>(i))};
        return builder_.CreateGEP(arr, buf, idxs, "buf.slot");
    }

    /// S3c-3b-3/S3c-3c v2：在 `[total x i64]` 扁平缓冲之间逐槽值拷贝
    /// （参数入口、sret 打包、调用方接管共用；struct / 嵌套数组元素都是 8 字节槽）。
    void copy_flat_i64(llvm::Value* dst, llvm::Value* src, size_t total) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        for (size_t i = 0; i < total; ++i) {
            auto* v = builder_.CreateLoad(i64, buffer_slot(src, total, i));
            builder_.CreateStore(v, buffer_slot(dst, total, i));
        }
    }

    /// 扁平 i64 槽缓冲中的第 i 个槽地址（不做数组类型边界推导）。
    llvm::Value* flat_slot(llvm::Value* buf, size_t i) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        return builder_.CreateGEP(
            i64, buf, {llvm::ConstantInt::get(i64, static_cast<uint64_t>(i))}, "flat.slot");
    }

    /// S3e：局部动态数组变量 → 通用 descriptor 三槽。
    static DynSlots dyn_slots_of(const DynArrayInfo& d) {
        return DynSlots{d.data, d.len, d.cap};
    }

    /// S3e：扁平槽块里起始于 base 的连续 3 个 descriptor 槽（data/len/cap）。
    DynSlots dyn_slots_at(llvm::Value* base) {
        return DynSlots{flat_slot(base, 0), flat_slot(base, 1), flat_slot(base, 2)};
    }

    /// 在任意两个 8 字节槽区之间逐槽拷贝。
    void copy_slots(llvm::Value* dst, llvm::Value* src, size_t count) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        for (size_t i = 0; i < count; ++i) {
            auto* v = builder_.CreateLoad(i64, flat_slot(src, i));
            builder_.CreateStore(v, flat_slot(dst, i));
        }
    }

    /// 把标量元素的局部定长数组 `[N x T]` 逐元素打包进 `buf` 的 i64 槽区。
    void copy_scalar_array_to_slots(const std::string& arr_ty, llvm::Value* src,
                                    llvm::Value* buf, size_t off) {
        auto elem = array_elem(arr_ty);
        auto len = array_decl_len(arr_ty);
        if (!elem.has_value() || !len.has_value()) {
            throw TenetError("内部错误：`" + arr_ty + "` 不是固定数组");
        }
        const std::string elem_ll = llvm_type(*elem);
        llvm::Type* elem_ty = ty(elem_ll.c_str());
        for (size_t i = 0; i < *len; ++i) {
            auto* idx = llvm::ConstantInt::get(llvm::Type::getInt64Ty(ctx_),
                                               static_cast<uint64_t>(i));
            auto* addr = array_addr(src, *len, idx, elem_ty);
            auto* v = builder_.CreateLoad(elem_ty, addr, "arr.elem");
            builder_.CreateStore(pack_scalar(*elem, v), flat_slot(buf, off + i));
        }
    }

    llvm::Value* pack_scalar(const std::string& type, llvm::Value* v) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        if (type == T_INT) return v;
        if (type == T_FLOAT) return builder_.CreateBitCast(v, i64);
        if (type == T_BOOL) return builder_.CreateZExt(v, i64);
        throw TenetError("内部错误：struct 字段只允许 int/float/bool，实际 `" + type + "`");
    }

    llvm::Value* unpack_scalar(const std::string& type, llvm::Value* raw) {
        if (type == T_INT) return raw;
        if (type == T_FLOAT) return builder_.CreateBitCast(raw, llvm::Type::getDoubleTy(ctx_));
        if (type == T_BOOL) return builder_.CreateTrunc(raw, llvm::Type::getInt1Ty(ctx_));
        throw TenetError("内部错误：struct 字段只允许 int/float/bool，实际 `" + type + "`");
    }

    /// 把缓冲区 [total x i64] 逐槽解包到 struct 本地扁平字段槽位。
    /// 固定数组字段按 `N*elem_slots` 个连续槽处理。
    /// S3e：`deep == true` 用于函数入口参数——动态字段重新 malloc 深拷贝（值语义）；
    /// `deep == false` 用于字面量 / 调用结果——descriptor 直接接管并清空源槽位。
    void unpack_buffer(const VarInfo& dst, const std::string& ty_name, llvm::Value* buf,
                       bool deep = false) {
        const size_t total = struct_total_slots(ty_name);
        auto layout = layout_of(ty_name);
        for (const auto& entry : layout) {
            if (is_dynamic_array(entry.ty)) {
                auto d = dst.dyn_fields.find(entry.path);
                if (d == dst.dyn_fields.end()) {
                    throw TenetError("内部错误：缺少动态字段槽 `" + entry.path + "`");
                }
                DynSlots target = dyn_slots_of(d->second);
                DynSlots source = dyn_slots_at(flat_slot(buf, entry.offset));
                if (deep) {
                    dyn_slots_deep_copy(entry.ty, target, source);
                } else {
                    dyn_slots_transfer(target, source);
                }
                continue;
            }
            auto f = dst.fields.find(entry.path);
            if (f == dst.fields.end()) {
                throw TenetError("内部错误：缺少字段槽 `" + entry.path + "`");
            }
            if (is_array(entry.ty)) {
                auto* src = flat_slot(buf, entry.offset);
                if (type_owns_heap(entry.ty)) {
                    if (deep) {
                        deep_copy_value(entry.ty, f->second.second, src);
                    } else {
                        transfer_value_slots(entry.ty, f->second.second, src);
                    }
                } else {
                    copy_slots(f->second.second, src, entry.slots);
                }
                continue;
            }
            auto* slot = buffer_slot(buf, total, entry.offset);
            auto* raw = builder_.CreateLoad(llvm::Type::getInt64Ty(ctx_), slot);
            auto* v = unpack_scalar(entry.ty, raw);
            builder_.CreateStore(v, f->second.second);
        }
    }

    /// 递归展开 struct 字面量，返回 (扁平路径, 标量表达式) 列表。
    std::vector<std::pair<std::string, ExprPtr>> flatten_literal(
        const std::string& ty_name,
        const std::vector<std::pair<std::string, ExprPtr>>& fields,
        const std::string& prefix, const Position& lit_pos) {
        std::vector<std::pair<std::string, ExprPtr>> out;
        auto defs = struct_fields(ty_name, lit_pos);
        std::unordered_map<std::string, ExprPtr> map;
        for (const auto& [fname, fexpr] : fields) {
            if (!map.emplace(fname, fexpr).second) {
                throw TenetError::at_pos(
                    "struct `" + ty_name + "` 的字段 `" + fname + "` 重复初始化", fexpr->pos);
            }
        }
        for (const auto& [fname, fty] : defs) {
            auto it = map.find(fname);
            if (it == map.end()) {
                throw TenetError::at_pos("struct `" + ty_name + "` 缺少字段 `" + fname + "`",
                                         lit_pos);
            }
            std::string path = prefix.empty() ? fname : prefix + "." + fname;
            const ExprPtr& fexpr = it->second;
            if (is_struct(fty)) {
                if (fexpr->kind != Expr::Kind::StructLit) {
                    throw TenetError::at_pos("字段 `" + path + "` 需要 `" + fty + "` 字面量",
                                             fexpr->pos);
                }
                if (fexpr->name != fty) {
                    throw TenetError::at_pos("字段 `" + path + "` 需要 `" + fty +
                                                 "`，实际字面量是 `" + fexpr->name + "`",
                                             fexpr->pos);
                }
                auto nested = flatten_literal(fty, fexpr->init_fields, path, fexpr->pos);
                out.insert(out.end(), nested.begin(), nested.end());
            } else {
                out.emplace_back(path, fexpr);
            }
            map.erase(it);
        }
        if (!map.empty()) {
            for (const auto& [fname, fexpr] : fields) {
                if (map.count(fname)) {
                    throw TenetError::at_pos(
                        "struct `" + ty_name + "` 没有字段 `" + fname + "`", fexpr->pos);
                }
            }
        }
        return out;
    }

    /// 把固定数组表达式打包进 `buf` 的 i64 槽区（从 `off` 开始，共 total 槽）。
    ///
    /// struct 字段的数组统一用扁平 i64 槽表示：
    /// - 标量元素：每个元素 zext/bitcast 成一个 i64 槽；
    /// - `array<struct, N>` / 固定嵌套数组：元素本身就是若干连续 i64 槽；
    /// - 支持字面量、同类型数组变量、返回数组的调用，以及从另一个 struct
    ///   数组字段整块拷贝。
    void pack_array_field_expr(const std::string& ty, const ExprPtr& expr, llvm::Value* buf,
                               size_t off) {
        auto elem = array_elem(ty);
        auto len = array_decl_len(ty);
        if (!elem.has_value() || !len.has_value()) {
            throw TenetError("内部错误：`" + ty + "` 不是固定数组");
        }
        const size_t total = fixed_array_total_slots(ty);
        const size_t elem_slots = array_elem_slots(ty);
        if (expr->kind == Expr::Kind::Array) {
            if (expr->args.empty()) {
                throw TenetError::at_pos("固定数组不支持空字面量", expr->pos);
            }
            if (expr->args.size() != *len) {
                throw TenetError::at_pos(
                    "数组长度不匹配：需要 " + std::to_string(*len) + "，实际 " +
                        std::to_string(expr->args.size()),
                    expr->pos);
            }
            if (is_array(*elem)) {
                for (size_t i = 0; i < expr->args.size(); ++i) {
                    if (expr->args[i]->kind != Expr::Kind::Array) {
                        throw TenetError::at_pos("嵌套数组元素必须是 [ ... ] 字面量",
                                                 expr->args[i]->pos);
                    }
                    pack_array_field_expr(*elem, expr->args[i], buf, off + i * elem_slots);
                }
                return;
            }
            if (is_struct(*elem)) {
                for (size_t i = 0; i < expr->args.size(); ++i) {
                    pack_expr_to_buffer(*elem, expr->args[i], flat_slot(buf, off + i * elem_slots));
                }
                return;
            }
            const std::string elem_ll = llvm_type(*elem);
            for (size_t i = 0; i < expr->args.size(); ++i) {
                auto [vt, v] = gen_expr(expr->args[i]);
                if (vt != elem_ll) {
                    throw TenetError::at_pos(
                        "数组元素 " + std::to_string(i) + " 类型不匹配：需要 " + *elem +
                            "，实际 " + value_type_name(vt),
                        expr->args[i]->pos);
                }
                builder_.CreateStore(pack_scalar(*elem, v), flat_slot(buf, off + i));
            }
            return;
        }
        if (expr->kind == Expr::Kind::Var) {
            const VarInfo& src = lookup_var(expr->name, expr->pos);
            if (src.ty != ty || !src.array_len.has_value() || src.addr == nullptr) {
                throw TenetError::at_pos(
                    "数组类型不匹配：需要 " + ty + "，实际是 " + value_type_name(src.ty),
                    expr->pos);
            }
            if (is_flat_slot_array(ty)) {
                if (type_owns_heap(ty)) {
                    deep_copy_value(ty, flat_slot(buf, off), src.addr);
                } else {
                    copy_slots(flat_slot(buf, off), src.addr, total);
                }
            } else {
                copy_scalar_array_to_slots(ty, src.addr, buf, off);
            }
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            auto [rt, src] = gen_expr(expr);
            if (rt != ty) {
                throw TenetError::at_pos(
                    "数组类型不匹配：需要 " + ty + "，调用返回 " + value_type_name(rt),
                    expr->pos);
            }
            if (is_flat_slot_array(ty) && type_owns_heap(ty)) {
                transfer_value_slots(ty, flat_slot(buf, off), src);
            } else if (is_flat_slot_array(ty)) {
                copy_slots(flat_slot(buf, off), src, total);
            } else {
                copy_scalar_array_to_slots(ty, src, buf, off);
            }
            return;
        }
        if (expr->kind == Expr::Kind::Field || expr->kind == Expr::Kind::Index) {
            auto place = resolve_place(expr);
            if (place.has_value() && place->kind == Place::Kind::Array && place->ty == ty &&
                place->packed) {
                if (type_owns_heap(ty)) {
                    deep_copy_value(ty, flat_slot(buf, off), place->addr);
                } else {
                    copy_slots(flat_slot(buf, off), place->addr, total);
                }
                return;
            }
        }
        throw TenetError::at_pos(
            "字段 `" + ty + "` 的初始化必须是同类型数组字面量、变量或调用", expr->pos);
    }

    /// S3e：把动态数组表达式打包进扁平槽块的 descriptor 三槽（起始 off）。
    /// 先用动态数组初始化路径得到一个独立的临时动态数组（变量 / 字面量 / 调用都
    /// 会深拷贝），再把 data/len/cap 转移进目标槽位并清空临时槽位。
    void pack_dyn_field_expr(const std::string& ty, const ExprPtr& expr, llvm::Value* buf,
                             size_t off) {
        VarInfo tmp = init_dynamic_array("__field_tmp", ty, expr, expr->pos);
        DynSlots src = dyn_slots_of(*tmp.dyn);
        dyn_slots_copy(dyn_slots_at(flat_slot(buf, off)), src);
        dyn_slots_clear(src);
    }

    /// 把 struct 表达式（字面量 / 同类型变量 / 返回 struct 的调用）打包进 [total x i64]。
    /// S3e：动态数组字段重新 malloc 深拷贝（字面量字段也是新堆），保证打包结果
    /// 拥有独立的堆缓冲区；变量 / 调用结果的整体值语义与 Rust 实现一致。
    void pack_expr_to_buffer(const std::string& ty_name, const ExprPtr& expr,
                             llvm::Value* buf) {
        const size_t n = struct_total_slots(ty_name);
        auto layout = layout_of(ty_name);
        auto slot_index = [&](const std::string& path) -> std::optional<size_t> {
            for (size_t i = 0; i < layout.size(); ++i) {
                if (layout[i].path == path) return i;
            }
            return std::nullopt;
        };
        if (expr->kind == Expr::Kind::StructLit) {
            if (expr->name != ty_name) {
                throw TenetError::at_pos(
                    "需要 " + ty_name + "，字面量是 " + expr->name, expr->pos);
            }
            for (const auto& [path, fexpr] : flatten_literal(ty_name, expr->init_fields, "",
                                                              expr->pos)) {
                auto idx = slot_index(path);
                if (!idx.has_value()) {
                    throw TenetError::at_pos("未知字段 `" + path + "`", fexpr->pos);
                }
                const LayoutEntry& entry = layout[*idx];
                if (is_dynamic_array(entry.ty)) {
                    pack_dyn_field_expr(entry.ty, fexpr, buf, entry.offset);
                    continue;
                }
                if (is_array(entry.ty)) {
                    pack_array_field_expr(entry.ty, fexpr, buf, entry.offset);
                    continue;
                }
                auto [vt, v] = gen_expr(fexpr);
                if (vt != llvm_type(entry.ty)) {
                    throw TenetError::at_pos(
                        "struct `" + ty_name + "` 字段 `" + path + "` 类型不匹配：需要 " +
                            entry.ty + "，实际 " + value_type_name(vt),
                        fexpr->pos);
                }
                auto* raw = pack_scalar(entry.ty, v);
                builder_.CreateStore(raw, buffer_slot(buf, n, entry.offset));
            }
            return;
        }
        if (expr->kind == Expr::Kind::Var) {
            const VarInfo& src = lookup_var(expr->name, expr->pos);
            if (src.ty != ty_name || src.array_len.has_value()) {
                throw TenetError::at_pos(
                    "需要 " + ty_name + "，实际是 " + src.ty, expr->pos);
            }
            for (const auto& entry : layout) {
                if (is_dynamic_array(entry.ty)) {
                    auto d = src.dyn_fields.find(entry.path);
                    if (d == src.dyn_fields.end()) {
                        throw TenetError("内部错误：缺少动态字段槽 `" + entry.path + "`");
                    }
                    dyn_slots_deep_copy(entry.ty, dyn_slots_at(flat_slot(buf, entry.offset)),
                                        dyn_slots_of(d->second));
                    continue;
                }
                auto f = src.fields.find(entry.path);
                if (f == src.fields.end()) {
                    throw TenetError("内部错误：缺少字段槽 `" + entry.path + "`");
                }
                if (is_array(entry.ty)) {
                    if (type_owns_heap(entry.ty)) {
                        deep_copy_value(entry.ty, flat_slot(buf, entry.offset),
                                        f->second.second);
                    } else {
                        copy_slots(flat_slot(buf, entry.offset), f->second.second,
                                   entry.slots);
                    }
                    continue;
                }
                auto* v = builder_.CreateLoad(ty(llvm_type(entry.ty)), f->second.second);
                auto* raw = pack_scalar(entry.ty, v);
                builder_.CreateStore(raw, buffer_slot(buf, n, entry.offset));
            }
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            auto [rt, src_buf] = gen_expr(expr);
            if (rt != ty_name) {
                throw TenetError::at_pos("需要 " + ty_name + "，实际 " + rt, expr->pos);
            }
            // 调用结果的 sret 缓冲把所有权转移给目标槽块（动态字段清空源 descriptor）。
            transfer_value_slots(ty_name, buf, src_buf);
            return;
        }
        throw TenetError::at_pos(
            ty_name + " 值必须是字面量、同类型变量或返回 " + ty_name + " 的函数调用",
            expr->pos);
    }

    /// struct 初始化：字面量 / 同类型变量 / 返回 struct 的调用。
    /// S3e：动态字段在字面量 / 调用结果路径上直接从临时缓冲接管（transfer），
    /// 同类型变量路径做递归深拷贝。
    VarInfo init_struct(const std::string& name, const std::string& ty_name, const ExprPtr& value,
                        const Position& pos) {
        if (is_struct_array_index_read(value)) {
            throw TenetError::at_pos(
                "不支持整体读取 array<struct> 元素；请访问标量字段", value->pos);
        }
        VarInfo dst = alloc_struct(ty_name, pos);
        if (value->kind == Expr::Kind::StructLit) {
            if (value->name != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 标注为 " + ty_name + "，但字面量是 " + value->name,
                    value->pos);
            }
            auto* buf = alloc_buffer(struct_total_slots(ty_name), name + ".init");
            pack_expr_to_buffer(ty_name, value, buf);
            unpack_buffer(dst, ty_name, buf, false);
            return dst;
        }
        if (value->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(value->name, value->pos);
            if (sinfo.ty != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但 `" + value->name + "` 是 " +
                        sinfo.ty,
                    value->pos);
            }
            copy_struct(dst, sinfo);
            return dst;
        }
        if (value->kind == Expr::Kind::Call) {
            auto [rt, buf] = gen_expr(value);
            if (rt != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但调用返回 " + rt, value->pos);
            }
            unpack_buffer(dst, ty_name, buf, false);
            return dst;
        }
        throw TenetError::at_pos("`" + name + "` 的 struct 初始化必须是 `" + ty_name +
                                     " {{ ... }}`、同类型 struct 变量或返回 " + ty_name +
                                     " 的函数调用",
                                 value->pos);
    }

    /// struct 整体赋值：字面量 / 同类型变量 / 返回 struct 的调用，全部按值拷贝。
    /// S3e：右侧先完整求值（深拷贝 / 新堆 / sret 接管），再 drop 目标旧动态字段，
    /// 最后把新值写入目标；`t = t` 是空操作。
    void assign_struct(const VarInfo& dst, const ExprPtr& value, const Position& pos) {
        if (is_struct_array_index_read(value)) {
            throw TenetError::at_pos(
                "不支持整体读取 array<struct> 元素；请访问标量字段", value->pos);
        }
        if (value->kind == Expr::Kind::StructLit) {
            if (value->name != dst.ty) {
                throw TenetError::at_pos(
                    "赋值类型不匹配：需要 " + dst.ty + "，字面量是 " + value->name, pos);
            }
            auto* buf = alloc_buffer(struct_total_slots(dst.ty), dst.ty + ".assign");
            pack_expr_to_buffer(dst.ty, value, buf);
            drop_var(dst);
            unpack_buffer(dst, dst.ty, buf, false);
            return;
        }
        if (value->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(value->name, value->pos);
            if (sinfo.ty != dst.ty) {
                throw TenetError::at_pos(
                    "赋值类型不匹配：需要 " + dst.ty + "，右侧是 " + sinfo.ty, pos);
            }
            if (&sinfo == &dst) return;  // t = t
            // 先深拷贝到临时 struct，再释放旧值，最后转移，保证自赋值 / 别名安全。
            VarInfo tmp = alloc_struct(dst.ty, pos);
            copy_struct(tmp, sinfo);
            drop_var(dst);
            move_struct(dst, tmp);
            return;
        }
        if (value->kind == Expr::Kind::Call) {
            auto [rt, buf] = gen_expr(value);
            if (rt != dst.ty) {
                throw TenetError::at_pos(
                    "赋值类型不匹配：需要 " + dst.ty + "，右侧是 " + rt, pos);
            }
            drop_var(dst);
            unpack_buffer(dst, dst.ty, buf, false);
            return;
        }
        throw TenetError::at_pos(
            "struct 整体赋值必须是同类型变量、字面量或返回 struct 的函数调用", value->pos);
    }

    /// 逐字段深拷贝（struct 的值语义）：标量字段 load/store；固定数组字段在含堆
    /// 元素时递归深拷贝；动态数组字段 malloc 新缓冲区并复制元素。dst 是新分配的
    /// struct（无旧值需要释放）。
    void copy_struct(const VarInfo& dst, const VarInfo& src) {
        for (const auto& entry : layout_of(dst.ty)) {
            if (is_dynamic_array(entry.ty)) {
                auto d = dst.dyn_fields.find(entry.path);
                auto s = src.dyn_fields.find(entry.path);
                if (d == dst.dyn_fields.end() || s == src.dyn_fields.end()) {
                    throw TenetError::at_pos("struct 动态字段 `" + entry.path + "` 不存在",
                                             Position(1, 1));
                }
                dyn_slots_deep_copy(entry.ty, dyn_slots_of(d->second),
                                    dyn_slots_of(s->second));
                continue;
            }
            auto dfield = dst.fields.find(entry.path);
            auto sfield = src.fields.find(entry.path);
            if (dfield == dst.fields.end() || sfield == src.fields.end()) {
                throw TenetError::at_pos("struct 字段 `" + entry.path + "` 不存在",
                                         Position(1, 1));
            }
            const std::string& fty = dfield->second.first;
            auto* daddr = dfield->second.second;
            auto* saddr = sfield->second.second;
            if (is_array(fty)) {
                if (type_owns_heap(fty)) {
                    deep_copy_value(fty, daddr, saddr);
                } else {
                    copy_slots(daddr, saddr, entry.slots);
                }
                continue;
            }
            auto* v = builder_.CreateLoad(ty(llvm_type(fty)), saddr);
            builder_.CreateStore(v, daddr);
        }
    }

    /// 把 src 的字段转移到 dst（用于整体赋值的临时 struct）：动态 descriptor 复制后
    /// 清空 src，避免 src 之后再被 drop 造成 double free。src 是函数内临时变量，
    /// 不登记在作用域表里，因此实际只会转移一次。
    void move_struct(const VarInfo& dst, const VarInfo& src) {
        for (const auto& entry : layout_of(dst.ty)) {
            if (is_dynamic_array(entry.ty)) {
                auto d = dst.dyn_fields.find(entry.path);
                auto s = src.dyn_fields.find(entry.path);
                if (d == dst.dyn_fields.end() || s == src.dyn_fields.end()) {
                    throw TenetError::at_pos("struct 动态字段 `" + entry.path + "` 不存在",
                                             Position(1, 1));
                }
                dyn_slots_transfer(dyn_slots_of(d->second), dyn_slots_of(s->second));
                continue;
            }
            auto dfield = dst.fields.find(entry.path);
            auto sfield = src.fields.find(entry.path);
            if (dfield == dst.fields.end() || sfield == src.fields.end()) {
                throw TenetError::at_pos("struct 字段 `" + entry.path + "` 不存在",
                                         Position(1, 1));
            }
            const std::string& fty = dfield->second.first;
            auto* daddr = dfield->second.second;
            auto* saddr = sfield->second.second;
            if (is_array(fty) && type_owns_heap(fty)) {
                transfer_value_slots(fty, daddr, saddr);
                continue;
            }
            if (is_array(fty)) {
                copy_slots(daddr, saddr, entry.slots);
                continue;
            }
            auto* v = builder_.CreateLoad(ty(llvm_type(fty)), saddr);
            builder_.CreateStore(v, daddr);
        }
    }

    /// S3e：把局部 struct 字段转移到扁平槽块（return sret 用）。
    /// 动态字段 descriptor 复制后清空本地槽位（所有权交给调用方），随后函数收尾
    /// 的 drop_all_scopes 不会二次释放。
    void transfer_struct_local_to_slots(const std::string& struct_ty, const VarInfo& info,
                                        llvm::Value* dst) {
        const size_t n = struct_total_slots(struct_ty);
        for (const auto& entry : layout_of(struct_ty)) {
            if (is_dynamic_array(entry.ty)) {
                auto s = info.dyn_fields.find(entry.path);
                if (s == info.dyn_fields.end()) {
                    throw TenetError("内部错误：缺少动态字段槽 `" + entry.path + "`");
                }
                dyn_slots_transfer(dyn_slots_at(flat_slot(dst, entry.offset)),
                                   dyn_slots_of(s->second));
                continue;
            }
            auto f = info.fields.find(entry.path);
            if (f == info.fields.end()) {
                throw TenetError("内部错误：缺少字段槽 `" + entry.path + "`");
            }
            if (is_array(entry.ty)) {
                if (type_owns_heap(entry.ty)) {
                    transfer_value_slots(entry.ty, flat_slot(dst, entry.offset),
                                         f->second.second);
                } else {
                    copy_slots(flat_slot(dst, entry.offset), f->second.second,
                               entry.slots);
                }
                continue;
            }
            auto* v = builder_.CreateLoad(ty(llvm_type(entry.ty)), f->second.second);
            auto* raw = pack_scalar(entry.ty, v);
            builder_.CreateStore(raw, buffer_slot(dst, n, entry.offset));
        }
    }

    /// S3e：struct return 写 sret。
    /// - 变量：转移动态 descriptor 并清空本地；
    /// - 字面量：打包时构造新堆；
    /// - 调用：从被调函数的 sret 缓冲转移。
    void transfer_struct_expr_to_sret(const std::string& ty, const ExprPtr& expr,
                                      llvm::Value* sret) {
        if (!expr) {
            throw TenetError::at_pos("struct return 必须带值", Position(1, 1));
        }
        if (expr->kind == Expr::Kind::Var) {
            const VarInfo& info = lookup_var(expr->name, expr->pos);
            if (info.ty != ty) {
                throw TenetError::at_pos(
                    "返回类型不匹配：需要 " + ty + "，实际 " + info.ty, expr->pos);
            }
            transfer_struct_local_to_slots(ty, info, sret);
            return;
        }
        if (expr->kind == Expr::Kind::StructLit) {
            if (expr->name != ty) {
                throw TenetError::at_pos(
                    "返回类型不匹配：需要 " + ty + "，字面量是 " + expr->name, expr->pos);
            }
            pack_expr_to_buffer(ty, expr, sret);
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            auto [rt, src] = gen_expr(expr);
            if (rt != ty) {
                throw TenetError::at_pos(
                    "返回类型不匹配：需要 " + ty + "，调用返回 " + rt, expr->pos);
            }
            transfer_value_slots(ty, sret, src);
            return;
        }
        throw TenetError::at_pos(
            ty + " 返回只支持变量、字面量或返回 " + ty + " 的函数调用", expr->pos);
    }

    /// 错误信息里的实际类型名（struct / array 保留 Tenet 类型名，不走 tenet_name）。
    std::string value_type_name(const std::string& t) const {
        return (is_struct(t) || is_array(t)) ? t : std::string(tenet_name(t));
    }

    // ---- 定长数组 ----
    // `array<T, N>` 是定长值数组类型，局部变量/参数/返回值都可用；
    // 参数传 ptr，返回值走隐藏 ptr %sret。
    // `array<struct, N>`（S3c-3b-1）仅支持局部固定数组，元素按扁平 i64 槽布局，
    // 见下方 init_struct_array / struct_array_elem_addr。
    // `array<T>`（无长度）是动态数组：局部变量见 S3c-1，参数/返回值 ABI 见 S3c-2。

    /// 常量下标（含 `-N`）：编译期检查越界；动态下标生成运行时 bounds check。
    llvm::Value* gen_index(const ExprPtr& index, size_t len) {
        auto [it, iv] = gen_expr(index);
        if (it != "i64") {
            throw TenetError::at_pos(
                "数组下标必须是 int，实际为 " + std::string(tenet_name(it)), index->pos);
        }
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto c = const_int_value(index);
        if (c.has_value()) {
            if (*c < 0 || static_cast<uint64_t>(*c) >= len) {
                throw TenetError::at_pos(
                    "数组下标 " + std::to_string(*c) + " 越界（长度 " + std::to_string(len) + "）",
                    index->pos);
            }
            return llvm::ConstantInt::get(i64, static_cast<uint64_t>(*c));
        }
        bounds_check(iv, len);
        return iv;
    }

    /// 识别整型常量下标（字面量与一元负号），返回其编译期值。
    static std::optional<int64_t> const_int_value(const ExprPtr& e) {
        if (!e) return std::nullopt;
        if (e->kind == Expr::Kind::Int) return e->int_val;
        if (e->kind == Expr::Kind::Unary && e->op == OP_NEG) {
            auto v = const_int_value(e->value);
            if (v.has_value() && *v != std::numeric_limits<int64_t>::min()) return -*v;
        }
        return std::nullopt;
    }

    /// 动态下标运行时检查：idx >= len（无符号比较，负数同样命中）→ 调用 runtime 报错退出。
    void bounds_check(llvm::Value* index, size_t len) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* len_val = llvm::ConstantInt::get(i64, static_cast<uint64_t>(len));
        auto* cmp = builder_.CreateICmpUGE(index, len_val, "bounds.cmp");
        auto* fail_bb = llvm::BasicBlock::Create(ctx_, "bounds.fail");
        auto* ok_bb = llvm::BasicBlock::Create(ctx_, "bounds.ok");
        auto* fn = builder_.GetInsertBlock()->getParent();
        builder_.CreateCondBr(cmp, fail_bb, ok_bb);
        fail_bb->insertInto(fn);
        builder_.SetInsertPoint(fail_bb);
        auto* fail_fn = mod_.getFunction("tenet_bounds_fail");
        builder_.CreateCall(fail_fn, {index, len_val});
        builder_.CreateUnreachable();
        ok_bb->insertInto(fn);
        builder_.SetInsertPoint(ok_bb);
    }

    /// 数组元素地址：GEP [N x T], ptr base, i64 0, i64 index。
    /// base 可以是局部数组 alloca，也可以是 ABI 缓冲区（参数 / 返回 / 实参缓冲）。
    llvm::Value* array_addr(llvm::Value* base, size_t len, llvm::Value* index,
                            llvm::Type* elem_ty) {
        auto* arr_ty = llvm::ArrayType::get(elem_ty, len);
        llvm::Value* idxs[] = {llvm::ConstantInt::get(llvm::Type::getInt64Ty(ctx_), 0), index};
        return builder_.CreateGEP(arr_ty, base, idxs, "a.slot");
    }

    /// 逐元素值拷贝：src/dst 都是 `[len x elem]` 指针（局部数组或 ABI 缓冲）。
    void copy_array_ptr(llvm::Value* dst, llvm::Value* src, size_t len, llvm::Type* elem_ty) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        for (size_t i = 0; i < len; ++i) {
            auto* idx = llvm::ConstantInt::get(i64, static_cast<uint64_t>(i));
            auto* saddr = array_addr(src, len, idx, elem_ty);
            auto* daddr = array_addr(dst, len, idx, elem_ty);
            auto* v = builder_.CreateLoad(elem_ty, saddr);
            builder_.CreateStore(v, daddr);
        }
    }

    /// 逐元素值拷贝（array 变量之间的赋值语义）。
    void copy_array(const VarInfo& dst, const VarInfo& src) {
        auto elem = array_elem(dst.ty);
        if (!elem.has_value() || !dst.array_len.has_value() || dst.addr == nullptr ||
            src.addr == nullptr) {
            throw TenetError("内部错误：数组拷贝目标不是数组");
        }
        copy_array_ptr(dst.addr, src.addr, *dst.array_len, ty(llvm_type(*elem)));
    }

    /// array<struct> 元素地址。元素按 struct 扁平标量字段占连续 8 字节槽
    /// （元素 stride = slots*8），返回 (元素 struct 名, 元素首槽地址)。
    /// - S3c-3b-1：固定 array<struct, N> 基于 `[N*slots x i64]` 局部缓冲，
    ///   常量下标编译期越界、动态下标生成运行时 `tenet_bounds_fail` 检查；
    /// - S3c-3b-2：动态 array<struct> 基于堆缓冲区，运行时 len 检查后按 idx*slots 取槽。
    std::pair<std::string, llvm::Value*> struct_array_elem_addr(
        const VarInfo& info, const ExprPtr& index, const Position& pos) {
        auto elem = array_elem(info.ty);
        if (!elem.has_value() || !is_struct(*elem)) {
            throw TenetError::at_pos("`" + info.ty + "` 不是 array<struct>", pos);
        }
        const size_t slots = array_elem_slots(info.ty);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        if (info.dyn.has_value()) {
            // S3c-3b-2：动态 array<struct> 的堆缓冲区按 8 字节槽扁平存放元素。
            auto* data = builder_.CreateLoad(ptr_ty(ctx_), info.dyn->data, "dyn.data");
            auto* len = builder_.CreateLoad(i64, info.dyn->len, "dyn.len");
            auto [it, iv] = gen_expr(index);
            if (it != "i64") {
                throw TenetError::at_pos(
                    "数组下标必须是 int，实际为 " + std::string(tenet_name(it)),
                    index->pos);
            }
            bounds_check_value(iv, len);
            auto* row = builder_.CreateMul(
                iv, llvm::ConstantInt::get(i64, static_cast<uint64_t>(slots)), "arr.row");
            return {*elem, dyn_slot(data, row)};
        }
        if (!info.array_len.has_value() || info.addr == nullptr) {
            throw TenetError::at_pos("`" + info.ty + "` 不是 array<struct>", pos);
        }
        const size_t len = *info.array_len;
        llvm::Value* idx = gen_index(index, len);
        llvm::Value* row = builder_.CreateMul(
            idx, llvm::ConstantInt::get(i64, static_cast<uint64_t>(slots)), "arr.row");
        return {*elem, array_addr(info.addr, len * slots, row, i64)};
    }

    /// S3c-3b-1/S3c-3b-3：固定 array<struct, N> 初始化。
    /// 字面量 / 同类型数组变量深拷贝 / 返回同类型数组的调用（调用方接管 sret）。
    /// 存储为扁平 `[len*slots x i64]`：每个元素占用 slots 个连续 8 字节槽。
    VarInfo init_struct_array(const std::string& name, const std::string& ty_name,
                              const ExprPtr& value, const Position& pos) {
        auto elem = array_elem(ty_name);
        if (!elem.has_value() || !is_struct(*elem)) {
            throw TenetError::at_pos("`" + ty_name + "` 不是 array<struct>", pos);
        }
        const size_t slots = array_elem_slots(ty_name);
        auto decl_len = array_decl_len(ty_name);
        size_t len = 0;
        const std::vector<ExprPtr>* literal = nullptr;
        llvm::Value* src = nullptr;

        if (value->kind == Expr::Kind::Call) {
            // S3c-3b-3：调用返回同类型数组 → 从 sret 缓冲逐槽拷贝到本地扁平数组。
            auto [rt, sret] = gen_expr(value);
            if (rt != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，调用返回 " + rt, value->pos);
            }
            const size_t total = fixed_array_total_slots(ty_name);
            auto* addr = alloc_buffer(total, name);
            if (type_owns_heap(ty_name)) {
                transfer_value_slots(ty_name, addr, sret);
            } else {
                copy_flat_i64(addr, sret, total);
            }
            return VarInfo{ty_name, addr, {}, decl_len};
        }
        if (value->kind == Expr::Kind::Array) {
            if (value->args.empty()) {
                throw TenetError::at_pos("固定数组不支持空字面量", value->pos);
            }
            len = value->args.size();
            if (decl_len.has_value() && *decl_len != len) {
                throw TenetError::at_pos(
                    "数组长度不匹配：类型写 " + std::to_string(*decl_len) + "，字面量 " +
                        std::to_string(len),
                    value->pos);
            }
            literal = &value->args;
        } else if (value->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(value->name, value->pos);
            if (!sinfo.array_len.has_value()) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但 `" + value->name +
                        "` 不是固定数组",
                    value->pos);
            }
            if (sinfo.ty != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但 `" + value->name + "` 是 " +
                        sinfo.ty,
                    value->pos);
            }
            len = *sinfo.array_len;
            src = sinfo.addr;
        } else {
            throw TenetError::at_pos(
                "`" + name + "` 的 array<struct> 初始化必须是字面量、同类型数组变量或"
                "返回数组的调用",
                value->pos);
        }

        auto* addr = builder_.CreateAlloca(
            llvm::ArrayType::get(llvm::Type::getInt64Ty(ctx_), len * slots), nullptr, name);
        if (literal != nullptr) {
            auto* i64 = llvm::Type::getInt64Ty(ctx_);
            for (size_t i = 0; i < literal->size(); ++i) {
                // 把第 i 个元素直接打包到它在扁平数组里的首槽（buffer_slot 以
                // [slots x i64] 计算偏移，语义上就是该元素内部的字段槽）。
                auto* dst = array_addr(
                    addr, len * slots,
                    llvm::ConstantInt::get(i64, static_cast<uint64_t>(i * slots)), i64);
                pack_expr_to_buffer(*elem, (*literal)[i], dst);
            }
        } else if (type_owns_heap(ty_name)) {
            // S3e：固定 array<struct> 且元素含动态字段 → 逐元素深拷贝。
            deep_copy_value(ty_name, addr, src);
        } else {
            copy_array_ptr(addr, src, len * slots, llvm::Type::getInt64Ty(ctx_));
        }
        return VarInfo{ty_name, addr, {}, std::optional<size_t>(len)};
    }

    /// S3c-3c v1/v2：固定嵌套数组 `array<array<T, N>, M>` 初始化。
    /// 存储为扁平 `[M*N x i64]`：外层第 i 个元素占连续 N 个 8 字节槽。
    /// 支持字面量、同类型数组变量深拷贝与返回同类型数组的调用；内层仅 int/float。
    VarInfo init_nested_array(const std::string& name, const std::string& ty_name,
                              const ExprPtr& value, const Position& pos) {
        auto outer_elem = array_elem(ty_name);
        if (!outer_elem.has_value() || !is_array(*outer_elem)) {
            throw TenetError::at_pos("`" + ty_name + "` 不是嵌套数组", pos);
        }
        auto inner_len = array_decl_len(*outer_elem);
        if (!inner_len.has_value()) {
            throw TenetError::at_pos("嵌套数组内层必须是固定长度 array<T, N>", pos);
        }
        auto inner_elem = array_elem(*outer_elem);
        if (!inner_elem.has_value()) {
            throw TenetError::at_pos("嵌套数组内层元素类型未知", pos);
        }
        if (*inner_elem == T_BOOL) {
            throw TenetError::at_pos("嵌套数组内层暂不支持 bool", pos);
        }
        if (*inner_elem != T_INT && *inner_elem != T_FLOAT) {
            throw TenetError::at_pos(
                "嵌套数组元素只支持标量 int/float，实际 `" + *inner_elem + "`", pos);
        }
        const size_t inner_slots = *inner_len;  // 内层为标量元素，每元素 1 槽
        auto decl_len = array_decl_len(ty_name);
        size_t len = 0;
        const std::vector<ExprPtr>* literal = nullptr;
        llvm::Value* src = nullptr;

        if (value->kind == Expr::Kind::Call) {
            // S3c-3c v2：调用返回同类型嵌套数组 → 从 sret 缓冲逐槽拷贝到本地。
            auto [rt, sret] = gen_expr(value);
            if (rt != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，调用返回 " + rt, value->pos);
            }
            const size_t total = fixed_array_total_slots(ty_name);
            auto* addr = alloc_buffer(total, name);
            copy_flat_i64(addr, sret, total);
            return VarInfo{ty_name, addr, {}, decl_len};
        }
        if (value->kind == Expr::Kind::Array) {
            if (value->args.empty()) {
                throw TenetError::at_pos("固定数组不支持空字面量", value->pos);
            }
            len = value->args.size();
            if (decl_len.has_value() && *decl_len != len) {
                throw TenetError::at_pos(
                    "数组长度不匹配：类型写 " + std::to_string(*decl_len) + "，字面量 " +
                        std::to_string(len),
                    value->pos);
            }
            literal = &value->args;
        } else if (value->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(value->name, value->pos);
            if (!sinfo.array_len.has_value()) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但 `" + value->name +
                        "` 不是固定数组",
                    value->pos);
            }
            if (sinfo.ty != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但 `" + value->name + "` 是 " +
                        sinfo.ty,
                    value->pos);
            }
            len = *sinfo.array_len;
            src = sinfo.addr;
        } else if (value->kind == Expr::Kind::Index) {
            throw TenetError::at_pos(
                "不支持整体读取嵌套数组元素；请用 a[i][j]", value->pos);
        } else {
            throw TenetError::at_pos(
                "`" + name + "` 的嵌套数组初始化必须是字面量、同类型数组变量或"
                "返回数组的调用",
                value->pos);
        }

        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* addr = builder_.CreateAlloca(
            llvm::ArrayType::get(i64, len * inner_slots), nullptr, name);
        const size_t total_slots = len * inner_slots;
        if (literal != nullptr) {
            for (size_t i = 0; i < literal->size(); ++i) {
                const ExprPtr& row = (*literal)[i];
                if (row->kind != Expr::Kind::Array) {
                    throw TenetError::at_pos("嵌套数组元素必须是 [ ... ] 字面量", row->pos);
                }
                if (row->args.size() != inner_slots) {
                    throw TenetError::at_pos(
                        "内层数组长度不匹配：需要 " + std::to_string(inner_slots) +
                            "，实际 " + std::to_string(row->args.size()),
                        row->pos);
                }
                for (size_t k = 0; k < inner_slots; ++k) {
                    auto [vt, v] = gen_expr(row->args[k]);
                    if (vt != llvm_type(*inner_elem)) {
                        throw TenetError::at_pos(
                            "数组元素 [" + std::to_string(i) + "][" + std::to_string(k) +
                                "] 类型不匹配：需要 " + *inner_elem + "，实际 " +
                                value_type_name(vt),
                            row->args[k]->pos);
                    }
                    auto* slot = array_addr(
                        addr, total_slots,
                        llvm::ConstantInt::get(i64, static_cast<uint64_t>(i * inner_slots + k)),
                        i64);
                    builder_.CreateStore(pack_scalar(*inner_elem, v), slot);
                }
            }
        } else {
            copy_array_ptr(addr, src, total_slots, i64);
        }
        return VarInfo{ty_name, addr, {}, std::optional<size_t>(len)};
    }

    /// S3c-3c v1/v2：嵌套数组 `a[i][j]` 元素地址（内层标量，按扁平槽定位）。
    /// 外层与内层下标都生成运行时 `tenet_bounds_fail` 检查。
    std::pair<std::string, llvm::Value*> nested_index_addr(
        const VarInfo& info, const ExprPtr& outer_idx, const ExprPtr& inner_idx,
        const Position& pos) {
        auto inner_ty = array_elem(info.ty);
        if (!inner_ty.has_value() || !is_array(*inner_ty)) {
            throw TenetError::at_pos("`" + info.ty + "` 不是嵌套数组", pos);
        }
        if (!info.array_len.has_value() || info.addr == nullptr) {
            throw TenetError("内部错误：嵌套数组变量缺少扁平缓冲");
        }
        const size_t outer_len = *info.array_len;
        auto inner_len = array_decl_len(*inner_ty);
        if (!inner_len.has_value()) {
            throw TenetError::at_pos("嵌套数组内层必须是固定长度 array<T, N>", pos);
        }
        auto inner_elem = array_elem(*inner_ty);
        if (!inner_elem.has_value()) {
            throw TenetError::at_pos("嵌套数组内层元素类型未知", pos);
        }
        if (*inner_elem == T_BOOL) {
            throw TenetError::at_pos("嵌套数组内层暂不支持 bool", pos);
        }
        if (*inner_elem != T_INT && *inner_elem != T_FLOAT) {
            throw TenetError::at_pos(
                "嵌套数组元素只支持标量 int/float，实际 `" + *inner_elem + "`", pos);
        }
        const size_t outer_slots = array_elem_slots(info.ty);
        const size_t inner_slots = array_elem_slots(*inner_ty);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto [ot, ov] = gen_expr(outer_idx);
        if (ot != "i64") {
            throw TenetError::at_pos(
                "数组下标必须是 int，实际为 " + std::string(tenet_name(ot)), outer_idx->pos);
        }
        bounds_check_value(ov, llvm::ConstantInt::get(i64, static_cast<uint64_t>(outer_len)));
        auto [it, iv] = gen_expr(inner_idx);
        if (it != "i64") {
            throw TenetError::at_pos(
                "数组下标必须是 int，实际为 " + std::string(tenet_name(it)), inner_idx->pos);
        }
        bounds_check_value(iv, llvm::ConstantInt::get(i64, static_cast<uint64_t>(*inner_len)));
        auto* row =
            builder_.CreateMul(ov, llvm::ConstantInt::get(i64, static_cast<uint64_t>(outer_slots)),
                               "nest.row");
        auto* irow =
            builder_.CreateMul(iv, llvm::ConstantInt::get(i64, static_cast<uint64_t>(inner_slots)),
                               "nest.irow");
        auto* flat = builder_.CreateAdd(row, irow, "nest.flat");
        return {*inner_elem, array_addr(info.addr, outer_len * outer_slots, flat, i64)};
    }

    /// S3c-3b-3/S3c-3c v2：把扁平固定数组表达式（同类型变量 / `array<P,2>` 字面量 /
    /// 返回同类型数组的调用）逐槽打包进 `[total x i64]` 缓冲。
    /// sret 返回值与函数实参共用，保证值语义。
    void pack_fixed_array_expr(const std::string& ty_name, const ExprPtr& expr,
                               llvm::Value* buf) {
        const size_t total = fixed_array_total_slots(ty_name);
        if (expr->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(expr->name, expr->pos);
            if (sinfo.ty != ty_name || !sinfo.array_len.has_value() ||
                sinfo.addr == nullptr) {
                throw TenetError::at_pos(
                    "数组参数类型不匹配：需要 " + ty_name + "，实际是 " +
                        value_type_name(sinfo.ty),
                    expr->pos);
            }
            if (type_owns_heap(ty_name)) {
                deep_copy_value(ty_name, buf, sinfo.addr);
            } else {
                copy_flat_i64(buf, sinfo.addr, total);
            }
            return;
        }
        if (expr->kind == Expr::Kind::Array) {
            VarInfo tmp = init_array("__arr_tmp", ty_name, expr, expr->pos);
            if (type_owns_heap(ty_name)) {
                transfer_value_slots(ty_name, buf, tmp.addr);
            } else {
                copy_flat_i64(buf, tmp.addr, total);
            }
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            auto [rt, src] = gen_expr(expr);
            if (rt != ty_name) {
                throw TenetError::at_pos(
                    "数组参数类型不匹配：需要 " + ty_name + "，调用返回 " +
                        value_type_name(rt),
                    expr->pos);
            }
            if (type_owns_heap(ty_name)) {
                transfer_value_slots(ty_name, buf, src);
            } else {
                copy_flat_i64(buf, src, total);
            }
            return;
        }
        throw TenetError::at_pos(
            "固定数组实参必须是同类型数组变量、字面量或返回数组的调用", expr->pos);
    }

    /// 把数组表达式（字面量 / 同类型同长变量 / 返回数组的调用）打包进 `[len x T]` 缓冲。
    /// struct 元素 / 嵌套数组元素走扁平 `[total x i64]` 槽布局（S3c-3b-3/S3c-3c v2）。
    /// sret 返回值、函数实参都走这里，保证值语义。
    void pack_array_expr_to_buffer(const std::string& ty_name, size_t len, const ExprPtr& expr,
                                   llvm::Value* buf) {
        if (is_flat_slot_array(ty_name)) {
            pack_fixed_array_expr(ty_name, expr, buf);
            return;
        }
        std::string elem = array_elem_scalar(ty_name, expr->pos);
        std::string elem_ll = llvm_type(elem);
        llvm::Type* elem_ty = ty(elem_ll.c_str());
        if (expr->kind == Expr::Kind::Array) {
            if (expr->args.size() != len) {
                throw TenetError::at_pos(
                    "数组长度不匹配：需要 " + std::to_string(len) + "，实际 " +
                        std::to_string(expr->args.size()),
                    expr->pos);
            }
            auto* i64 = llvm::Type::getInt64Ty(ctx_);
            for (size_t i = 0; i < expr->args.size(); ++i) {
                auto [vt, v] = gen_expr(expr->args[i]);
                if (vt != elem_ll) {
                    throw TenetError::at_pos(
                        "数组元素 " + std::to_string(i) + " 类型不匹配：需要 " + elem + "，实际 " +
                            tenet_name(vt),
                        expr->args[i]->pos);
                }
                auto* idx = llvm::ConstantInt::get(i64, static_cast<uint64_t>(i));
                builder_.CreateStore(v, array_addr(buf, len, idx, elem_ty));
            }
            return;
        }
        if (expr->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(expr->name, expr->pos);
            if (!sinfo.array_len.has_value() || !same_array_elem(sinfo.ty, ty_name)) {
                throw TenetError::at_pos(
                    "数组类型不匹配：需要 " + ty_name + "，实际是 " + value_type_name(sinfo.ty),
                    expr->pos);
            }
            if (*sinfo.array_len != len) {
                throw TenetError::at_pos(
                    "数组长度不匹配：需要 " + std::to_string(len) + "，实际 " +
                        std::to_string(*sinfo.array_len),
                    expr->pos);
            }
            copy_array_ptr(buf, sinfo.addr, len, elem_ty);
            return;
        }
        if (expr->kind == Expr::Kind::Call) {
            auto [rt, src_buf] = gen_expr(expr);
            if (!is_array(rt) || !same_array_elem(rt, ty_name)) {
                throw TenetError::at_pos(
                    "数组类型不匹配：需要 " + ty_name + "，调用返回 " + value_type_name(rt),
                    expr->pos);
            }
            auto rlen = array_decl_len(rt);
            if (!rlen.has_value()) {
                throw TenetError::at_pos(
                    "数组类型不匹配：需要 " + ty_name + "，调用返回 " + rt, expr->pos);
            }
            if (*rlen != len) {
                throw TenetError::at_pos(
                    "数组长度不匹配：需要 " + std::to_string(len) + "，调用返回 " +
                        std::to_string(*rlen),
                    expr->pos);
            }
            copy_array_ptr(buf, src_buf, len, elem_ty);
            return;
        }
        throw TenetError::at_pos(
            "数组实参必须是同类型数组变量、同长度字面量或返回数组的调用", expr->pos);
    }

    /// 数组初始化：字面量 / 同类型数组变量 / 返回数组的调用；`array<T,N>` 长度必须匹配。
    VarInfo init_array(const std::string& name, const std::string& ty_name, const ExprPtr& value,
                       const Position& pos) {
        auto elem0 = array_elem(ty_name);
        if (!elem0.has_value()) {
            throw TenetError::at_pos("不是数组类型：" + ty_name, pos);
        }
        if (is_struct(*elem0)) {
            // S3c-3b-1：固定 array<struct, N> 走扁平槽布局。
            return init_struct_array(name, ty_name, value, pos);
        }
        if (is_array(*elem0)) {
            // S3c-3c v1：固定嵌套数组 array<array<T, N>, M> 走扁平标量槽布局。
            return init_nested_array(name, ty_name, value, pos);
        }
        std::string elem = array_elem_scalar(ty_name, pos);
        std::string elem_ll = llvm_type(elem);
        llvm::Type* elem_ty = ty(elem_ll.c_str());
        auto decl_len = array_decl_len(ty_name);
        size_t len = 0;
        const std::vector<ExprPtr>* literal = nullptr;
        llvm::Value* src_buf = nullptr;

        if (value->kind == Expr::Kind::Array) {
            if (value->args.empty()) {
                throw TenetError::at_pos("v1 不支持空数组字面量", value->pos);
            }
            len = value->args.size();
            if (decl_len.has_value() && *decl_len != len) {
                throw TenetError::at_pos(
                    "数组长度不匹配：类型写 " + std::to_string(*decl_len) + "，字面量 " +
                        std::to_string(len),
                    value->pos);
            }
            literal = &value->args;
        } else if (value->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(value->name, value->pos);
            if (!sinfo.array_len.has_value()) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但 `" + value->name + "` 是 " +
                        sinfo.ty,
                    value->pos);
            }
            if (!same_array_elem(sinfo.ty, ty_name)) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但 `" + value->name + "` 是 " + sinfo.ty,
                    value->pos);
            }
            if (decl_len.has_value() && *decl_len != *sinfo.array_len) {
                throw TenetError::at_pos(
                    "数组长度不匹配：需要 " + std::to_string(*decl_len) + "，实际是 " +
                        std::to_string(*sinfo.array_len),
                    value->pos);
            }
            len = *sinfo.array_len;
            src_buf = sinfo.addr;
        } else if (value->kind == Expr::Kind::Call) {
            auto [rt, buf] = gen_expr(value);
            if (!is_array(rt) || !same_array_elem(rt, ty_name)) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，调用返回 " + value_type_name(rt),
                    value->pos);
            }
            auto rlen = array_decl_len(rt);
            if (!rlen.has_value()) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，调用返回 " + rt, value->pos);
            }
            if (decl_len.has_value() && *decl_len != *rlen) {
                throw TenetError::at_pos(
                    "数组长度不匹配：需要 " + std::to_string(*decl_len) + "，调用返回 " +
                        std::to_string(*rlen),
                    value->pos);
            }
            len = *rlen;
            src_buf = buf;
        } else {
            throw TenetError::at_pos(
                "`" + name + "` 的数组初始化必须是字面量、同类型数组变量或返回数组的调用",
                value->pos);
        }

        auto* addr = builder_.CreateAlloca(llvm::ArrayType::get(elem_ty, len), nullptr, name);
        VarInfo info{ty_name, addr, {}, std::optional<size_t>(len)};
        if (literal != nullptr) {
            auto* i64 = llvm::Type::getInt64Ty(ctx_);
            for (size_t i = 0; i < literal->size(); ++i) {
                auto [vt, v] = gen_expr((*literal)[i]);
                if (vt != elem_ll) {
                    throw TenetError::at_pos(
                        "数组元素 " + std::to_string(i) + " 类型不匹配：需要 " + elem + "，实际 " +
                            tenet_name(vt),
                        (*literal)[i]->pos);
                }
                auto* idx = llvm::ConstantInt::get(i64, static_cast<uint64_t>(i));
                builder_.CreateStore(v, array_addr(addr, len, idx, elem_ty));
            }
        } else {
            copy_array_ptr(addr, src_buf, len, elem_ty);
        }
        return info;
    }

    /// 数组整体赋值：同长度字面量 / 同类型同长变量 / 返回数组的调用，逐元素值拷贝。
    void assign_array(const VarInfo& dst, const ExprPtr& value, const Position& pos) {
        if (is_flat_slot_array(dst.ty)) {
            // S3c-3b-4：固定 array<struct, N> / 固定嵌套数组整体赋值。右侧变量 /
            // 字面量 / 返回数组的调用先按总槽数打包到临时 `[total x i64]` 缓冲，
            // 再逐槽覆盖目标；固定数组无堆，直接覆盖即可（值语义）。
            // S3e：元素含动态字段时先释放目标旧缓冲区，再转移新值；`b = b` 空操作。
            if (dst.addr == nullptr) {
                throw TenetError::at_pos("固定数组整体赋值目标无效", pos);
            }
            if (value->kind == Expr::Kind::Var) {
                const VarInfo& sinfo = lookup_var(value->name, value->pos);
                if (&sinfo == &dst) return;
            }
            const size_t total = fixed_array_total_slots(dst.ty);
            auto* tmp = alloc_buffer(total, "__array_assign");
            pack_fixed_array_expr(dst.ty, value, tmp);
            if (type_owns_heap(dst.ty)) {
                drop_var(dst);
                transfer_value_slots(dst.ty, dst.addr, tmp);
            } else {
                copy_flat_i64(dst.addr, tmp, total);
            }
            return;
        }
        std::string elem = array_elem_scalar(dst.ty, pos);
        std::string elem_ll = llvm_type(elem);
        llvm::Type* elem_ty = ty(elem_ll.c_str());
        size_t len = *dst.array_len;
        if (value->kind == Expr::Kind::Array) {
            if (value->args.size() != len) {
                throw TenetError::at_pos(
                    "数组赋值长度不匹配：需要 " + std::to_string(len) + "，实际 " +
                        std::to_string(value->args.size()),
                    value->pos);
            }
            auto* i64 = llvm::Type::getInt64Ty(ctx_);
            for (size_t i = 0; i < value->args.size(); ++i) {
                auto [vt, v] = gen_expr(value->args[i]);
                if (vt != elem_ll) {
                    throw TenetError::at_pos(
                        "数组元素 " + std::to_string(i) + " 类型不匹配：需要 " + elem + "，实际 " +
                            tenet_name(vt),
                        value->args[i]->pos);
                }
                auto* idx = llvm::ConstantInt::get(i64, static_cast<uint64_t>(i));
                builder_.CreateStore(v, array_addr(dst.addr, len, idx, elem_ty));
            }
            return;
        }
        if (value->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(value->name, value->pos);
            if (!sinfo.array_len.has_value() || !same_array_elem(sinfo.ty, dst.ty)) {
                throw TenetError::at_pos(
                    "数组赋值类型不匹配：需要 " + dst.ty + "，右侧是 " + sinfo.ty, value->pos);
            }
            if (*sinfo.array_len != len) {
                throw TenetError::at_pos(
                    "数组赋值长度不匹配：需要 " + std::to_string(len) + "，实际 " +
                        std::to_string(*sinfo.array_len),
                    value->pos);
            }
            copy_array(dst, sinfo);
            return;
        }
        if (value->kind == Expr::Kind::Call) {
            auto [rt, buf] = gen_expr(value);
            if (!is_array(rt) || !same_array_elem(rt, dst.ty)) {
                throw TenetError::at_pos(
                    "数组赋值类型不匹配：需要 " + dst.ty + "，调用返回 " + value_type_name(rt),
                    value->pos);
            }
            auto rlen = array_decl_len(rt);
            if (!rlen.has_value()) {
                throw TenetError::at_pos(
                    "数组赋值类型不匹配：需要 " + dst.ty + "，调用返回 " + rt, value->pos);
            }
            if (*rlen != len) {
                throw TenetError::at_pos(
                    "数组赋值长度不匹配：需要 " + std::to_string(len) + "，调用返回 " +
                        std::to_string(*rlen),
                    value->pos);
            }
            copy_array_ptr(dst.addr, buf, len, elem_ty);
            return;
        }
        throw TenetError::at_pos(
            "数组赋值必须是同类型数组变量、同长度字面量或返回数组的调用", value->pos);
    }

    // ---- S3c-1/S3c-2：动态数组 `array<T>` ----
    // 变量由三个栈槽组成：data(ptr)/len(i64)/cap(i64)；堆缓冲区用 malloc/free。
    // 元素按 8 字节槽存放（int → i64，float ↔ bitcast，bool ↔ zext/trunc）。
    // 局部变量在作用域退出 / return / break 前 drop；参数/返回值走 3 槽 descriptor ABI。

    /// 动态数组类型：`array<T>`（没有逗号 + 长度）。
    static bool is_dynamic_array(const std::string& t) {
        return is_array(t) && !array_decl_len(t).has_value();
    }

    static llvm::PointerType* ptr_ty(llvm::LLVMContext& ctx) {
        return llvm::PointerType::getUnqual(ctx);
    }

    llvm::Function* runtime_fn(const char* name) {
        auto* fn = mod_.getFunction(name);
        if (fn == nullptr) throw TenetError(std::string("内部错误：缺少运行时声明 ") + name);
        return fn;
    }

    /// 分配 descriptor 的三个栈槽，并初始化为 null / 0 / 0。
    DynArrayInfo dyn_new_slots(const std::string& name) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        auto* data = builder_.CreateAlloca(pty, nullptr, name + ".data");
        auto* len = builder_.CreateAlloca(i64, nullptr, name + ".len");
        auto* cap = builder_.CreateAlloca(i64, nullptr, name + ".cap");
        builder_.CreateStore(llvm::ConstantPointerNull::get(pty), data);
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), len);
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), cap);
        return DynArrayInfo{data, len, cap};
    }

    /// 堆缓冲区第 index 个 8 字节槽地址：GEP i64, ptr data, i64 index。
    llvm::Value* dyn_slot(llvm::Value* data, llvm::Value* index) {
        return builder_.CreateGEP(llvm::Type::getInt64Ty(ctx_), data, {index}, "dyn.slot");
    }

    /// 分配堆缓冲区并写入 descriptor（cap 至少 1 个槽，空数组默认 cap=4）。
    void dyn_alloc(const DynArrayInfo& dyn, size_t len, size_t cap) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        uint64_t bytes = static_cast<uint64_t>(std::max<size_t>(cap, 1) * 8);
        auto* p = builder_.CreateCall(runtime_fn("malloc"),
                                      {llvm::ConstantInt::get(i64, bytes)}, "dyn.data");
        builder_.CreateStore(p, dyn.data);
        builder_.CreateStore(llvm::ConstantInt::get(i64, static_cast<uint64_t>(len)), dyn.len);
        builder_.CreateStore(llvm::ConstantInt::get(i64, static_cast<uint64_t>(cap)), dyn.cap);
    }

    /// 逐元素拷贝 len 个 8 字节槽（堆缓冲区之间）。
    void dyn_copy_elems(llvm::Value* dst_data, llvm::Value* src_data, llvm::Value* len) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* fn = builder_.GetInsertBlock()->getParent();
        auto* cond_bb = llvm::BasicBlock::Create(ctx_, "dyn.copy.cond");
        auto* body_bb = llvm::BasicBlock::Create(ctx_, "dyn.copy.body");
        auto* end_bb = llvm::BasicBlock::Create(ctx_, "dyn.copy.end");
        auto* i_slot = builder_.CreateAlloca(i64, nullptr, "dyn.copy.i");
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), i_slot);
        builder_.CreateBr(cond_bb);
        cond_bb->insertInto(fn);
        builder_.SetInsertPoint(cond_bb);
        auto* i = builder_.CreateLoad(i64, i_slot, "dyn.copy.idx");
        auto* cmp = builder_.CreateICmpSLT(i, len, "dyn.copy.cmp");
        builder_.CreateCondBr(cmp, body_bb, end_bb);
        body_bb->insertInto(fn);
        builder_.SetInsertPoint(body_bb);
        auto* s = dyn_slot(src_data, i);
        auto* d = dyn_slot(dst_data, i);
        builder_.CreateStore(builder_.CreateLoad(i64, s), d);
        auto* next = builder_.CreateAdd(i, llvm::ConstantInt::get(i64, 1), "dyn.copy.next");
        builder_.CreateStore(next, i_slot);
        builder_.CreateBr(cond_bb);
        end_bb->insertInto(fn);
        builder_.SetInsertPoint(end_bb);
    }

    /// 释放动态数组堆缓冲区并把 descriptor 重置为 null / 0 / 0（空指针安全）。
    /// v1 动态嵌套数组先逐内层 `free(data)`，再 `free` 外层。
    void dyn_drop(const DynArrayInfo& dyn, const std::string& ty) {
        dyn_drop_slots(dyn.data, dyn.len, dyn.cap, ty);
    }

    /// 按 descriptor 槽位释放动态数组（局部 descriptor 与栈上临时 descriptor 共用）。
    /// 动态嵌套数组逐内层释放 `data`，再释放外层缓冲区；空指针安全。
    void dyn_drop_slots(llvm::Value* data_slot, llvm::Value* len_slot,
                        llvm::Value* cap_slot, const std::string& ty) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        auto* p = builder_.CreateLoad(pty, data_slot, "dyn.drop.data");
        auto* is_null =
            builder_.CreateICmpEQ(p, llvm::ConstantPointerNull::get(pty), "dyn.drop.isnull");
        auto* fn = builder_.GetInsertBlock()->getParent();
        auto* free_bb = llvm::BasicBlock::Create(ctx_, "dyn.free");
        auto* end_bb = llvm::BasicBlock::Create(ctx_, "dyn.drop.end");
        builder_.CreateCondBr(is_null, end_bb, free_bb);
        free_bb->insertInto(fn);
        builder_.SetInsertPoint(free_bb);
        if (is_dynamic_nested_array(ty)) {
            // 外层每个元素是内层 descriptor [data,len,cap]：逐行 free(data)。
            auto* len = builder_.CreateLoad(i64, len_slot, "dyn.drop.len");
            auto* i_slot = builder_.CreateAlloca(i64, nullptr, "dyn.drop.i");
            builder_.CreateStore(llvm::ConstantInt::get(i64, 0), i_slot);
            auto* cond_bb = llvm::BasicBlock::Create(ctx_, "dyn.drop.cond");
            auto* body_bb = llvm::BasicBlock::Create(ctx_, "dyn.drop.inner");
            auto* next_bb = llvm::BasicBlock::Create(ctx_, "dyn.drop.next");
            auto* after_bb = llvm::BasicBlock::Create(ctx_, "dyn.drop.rows");
            builder_.CreateBr(cond_bb);
            cond_bb->insertInto(fn);
            builder_.SetInsertPoint(cond_bb);
            auto* iv = builder_.CreateLoad(i64, i_slot, "dyn.drop.idx");
            auto* cmp = builder_.CreateICmpSLT(iv, len, "dyn.drop.cmp");
            builder_.CreateCondBr(cmp, body_bb, after_bb);
            body_bb->insertInto(fn);
            builder_.SetInsertPoint(body_bb);
            auto* row_off =
                builder_.CreateMul(iv, llvm::ConstantInt::get(i64, 3), "dyn.drop.row");
            auto* row = dyn_slot(p, row_off);
            auto* dp = desc_slot(row, 0);
            auto* ip = builder_.CreateLoad(pty, dp, "dyn.drop.inner.data");
            auto* inner_null = builder_.CreateICmpEQ(
                ip, llvm::ConstantPointerNull::get(pty), "dyn.drop.inner.isnull");
            auto* inner_free_bb = llvm::BasicBlock::Create(ctx_, "dyn.drop.inner.free");
            builder_.CreateCondBr(inner_null, next_bb, inner_free_bb);
            inner_free_bb->insertInto(fn);
            builder_.SetInsertPoint(inner_free_bb);
            builder_.CreateCall(runtime_fn("free"), {ip});
            builder_.CreateStore(llvm::ConstantPointerNull::get(pty), dp);
            builder_.CreateBr(next_bb);
            next_bb->insertInto(fn);
            builder_.SetInsertPoint(next_bb);
            auto* ni =
                builder_.CreateAdd(iv, llvm::ConstantInt::get(i64, 1), "dyn.drop.nexti");
            builder_.CreateStore(ni, i_slot);
            builder_.CreateBr(cond_bb);
            after_bb->insertInto(fn);
            builder_.SetInsertPoint(after_bb);
        } else if (is_dynamic_array(ty)) {
            // S3e：动态 array<struct> 且元素含动态字段时递归 drop 每个元素。
            auto elem = array_elem(ty);
            if (elem.has_value() && is_struct(*elem) && type_owns_heap(*elem)) {
                const size_t eslots = array_elem_slots(ty);
                auto* len = builder_.CreateLoad(i64, len_slot, "dyn.drop.len");
                auto* i_slot = builder_.CreateAlloca(i64, nullptr, "dyn.elem.drop.i");
                builder_.CreateStore(llvm::ConstantInt::get(i64, 0), i_slot);
                auto* cond_bb = llvm::BasicBlock::Create(ctx_, "dyn.elem.drop.cond");
                auto* body_bb = llvm::BasicBlock::Create(ctx_, "dyn.elem.drop.body");
                auto* end_elem_bb = llvm::BasicBlock::Create(ctx_, "dyn.elem.drop.end");
                builder_.CreateBr(cond_bb);
                cond_bb->insertInto(fn);
                builder_.SetInsertPoint(cond_bb);
                auto* iv = builder_.CreateLoad(i64, i_slot, "dyn.elem.drop.idx");
                auto* cmp = builder_.CreateICmpSLT(iv, len, "dyn.elem.drop.cmp");
                builder_.CreateCondBr(cmp, body_bb, end_elem_bb);
                body_bb->insertInto(fn);
                builder_.SetInsertPoint(body_bb);
                auto* row = builder_.CreateMul(
                    iv, llvm::ConstantInt::get(i64, static_cast<uint64_t>(eslots)),
                    "dyn.elem.drop.row");
                drop_value_slots(*elem, dyn_slot(p, row));
                auto* ni = builder_.CreateAdd(iv, llvm::ConstantInt::get(i64, 1),
                                              "dyn.elem.drop.next");
                builder_.CreateStore(ni, i_slot);
                builder_.CreateBr(cond_bb);
                end_elem_bb->insertInto(fn);
                builder_.SetInsertPoint(end_elem_bb);
            }
        }
        builder_.CreateCall(runtime_fn("free"), {p});
        builder_.CreateStore(llvm::ConstantPointerNull::get(pty), data_slot);
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), len_slot);
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), cap_slot);
        builder_.CreateBr(end_bb);
        end_bb->insertInto(fn);
        builder_.SetInsertPoint(end_bb);
    }

    // ---- S3e：descriptor 通用三槽 + 扁平槽块的递归深拷贝 / 转移 / drop ----
    // struct 的动态数组字段在局部变量里是三槽；在 ABI buffer / 数组元素里是连续
    // 3 个 i64 槽。二者统一用 DynSlots（三个槽地址）表示。扁平槽块里的 struct /
    // 固定数组 / 动态 descriptor 通过布局递归处理。

    /// 三个 descriptor 槽逐槽值拷贝（目标/源都可以是任意槽地址）。
    void dyn_slots_copy(const DynSlots& dst, const DynSlots& src) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        builder_.CreateStore(builder_.CreateLoad(pty, src.data, "desc.copy.data"), dst.data);
        builder_.CreateStore(builder_.CreateLoad(i64, src.len, "desc.copy.len"), dst.len);
        builder_.CreateStore(builder_.CreateLoad(i64, src.cap, "desc.copy.cap"), dst.cap);
    }

    /// 把 descriptor 重置为 null / 0 / 0（所有权转移后避免 double free）。
    void dyn_slots_clear(const DynSlots& s) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        builder_.CreateStore(llvm::ConstantPointerNull::get(pty), s.data);
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), s.len);
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), s.cap);
    }

    /// descriptor 复制 + 清空源（return 所有权转移）。
    void dyn_slots_transfer(const DynSlots& dst, const DynSlots& src) {
        dyn_slots_copy(dst, src);
        dyn_slots_clear(src);
    }

    /// 把 descriptor 三槽写进 `[3 x i64]` 栈上 descriptor（函数实参）。
    void desc_store_slots(llvm::Value* desc, const DynSlots& s) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        builder_.CreateStore(builder_.CreateLoad(pty, s.data, "desc.store.data"),
                             desc_slot(desc, 0));
        builder_.CreateStore(builder_.CreateLoad(i64, s.len, "desc.store.len"),
                             desc_slot(desc, 1));
        builder_.CreateStore(builder_.CreateLoad(i64, s.cap, "desc.store.cap"),
                             desc_slot(desc, 2));
    }

    /// 堆缓冲区之间逐元素拷贝：元素含堆时递归深拷贝，否则按 8 字节槽拷贝。
    /// `count` 是元素个数（不是槽数）。
    void dyn_elems_copy(const std::string& elem, size_t eslots, llvm::Value* dst_data,
                        llvm::Value* src_data, llvm::Value* count) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        if (!type_owns_heap(elem)) {
            auto* total = builder_.CreateMul(
                count, llvm::ConstantInt::get(i64, static_cast<uint64_t>(eslots)),
                "dyn.copy.total");
            dyn_copy_elems(dst_data, src_data, total);
            return;
        }
        auto* fn = builder_.GetInsertBlock()->getParent();
        auto* i_slot = builder_.CreateAlloca(i64, nullptr, "dyn.deep.i");
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), i_slot);
        auto* cond_bb = llvm::BasicBlock::Create(ctx_, "dyn.deep.cond");
        auto* body_bb = llvm::BasicBlock::Create(ctx_, "dyn.deep.body");
        auto* end_bb = llvm::BasicBlock::Create(ctx_, "dyn.deep.end");
        builder_.CreateBr(cond_bb);
        cond_bb->insertInto(fn);
        builder_.SetInsertPoint(cond_bb);
        auto* iv = builder_.CreateLoad(i64, i_slot, "dyn.deep.idx");
        auto* cmp = builder_.CreateICmpSLT(iv, count, "dyn.deep.cmp");
        builder_.CreateCondBr(cmp, body_bb, end_bb);
        body_bb->insertInto(fn);
        builder_.SetInsertPoint(body_bb);
        auto* row = builder_.CreateMul(
            iv, llvm::ConstantInt::get(i64, static_cast<uint64_t>(eslots)), "dyn.deep.row");
        auto* d = dyn_slot(dst_data, row);
        auto* s = dyn_slot(src_data, row);
        deep_copy_value(elem, d, s);
        auto* next = builder_.CreateAdd(iv, llvm::ConstantInt::get(i64, 1), "dyn.deep.next");
        builder_.CreateStore(next, i_slot);
        builder_.CreateBr(cond_bb);
        end_bb->insertInto(fn);
        builder_.SetInsertPoint(end_bb);
    }

    /// 深拷贝 descriptor 三槽：重新 malloc 堆缓冲区并递归复制元素。
    void dyn_slots_deep_copy(const std::string& ty, const DynSlots& dst,
                             const DynSlots& src) {
        if (is_dynamic_nested_array(ty)) {
            // 动态嵌套数组：逐内层 descriptor 深拷贝（struct 字段不在 v1 范围，
            // 但通用路径仍保持正确）。
            VarInfo tmp = nested_copy_from_slots(ty, src.data, src.len, src.cap,
                                                 Position(1, 1));
            DynSlots ts = dyn_slots_of(*tmp.dyn);
            dyn_slots_copy(dst, ts);
            dyn_slots_clear(ts);
            return;
        }
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        auto* sp = builder_.CreateLoad(pty, src.data, "deep.src.data");
        auto* sl = builder_.CreateLoad(i64, src.len, "deep.src.len");
        auto* sc = builder_.CreateLoad(i64, src.cap, "deep.src.cap");
        const size_t eslots = array_elem_slots(ty);
        auto* bytes = builder_.CreateMul(
            sc, llvm::ConstantInt::get(i64, static_cast<uint64_t>(eslots * 8)),
            "deep.bytes");
        auto* np = builder_.CreateCall(runtime_fn("malloc"), {bytes}, "deep.data");
        auto elem = array_elem(ty);
        if (!elem.has_value()) {
            throw TenetError("内部错误：`" + ty + "` 不是数组");
        }
        dyn_elems_copy(*elem, eslots, np, sp, sl);
        builder_.CreateStore(np, dst.data);
        builder_.CreateStore(sl, dst.len);
        builder_.CreateStore(sc, dst.cap);
    }

    /// 从任意 descriptor 三槽深拷贝出一个新的局部动态数组变量。
    VarInfo dyn_deep_copy_from(const std::string& name, const std::string& ty,
                               const DynSlots& src) {
        if (!is_dynamic_array(ty)) {
            throw TenetError::at_pos("`" + ty + "` 不是动态数组", Position(1, 1));
        }
        DynArrayInfo dyn = dyn_new_slots(name);
        dyn_slots_deep_copy(ty, dyn_slots_of(dyn), src);
        return VarInfo{ty, nullptr, {}, std::nullopt, dyn};
    }

    /// 深拷贝扁平槽块中的一个值：dst / src 是起始槽地址（源保持有效）。
    /// 标量 / 无堆固定数组逐槽复制；动态 descriptor 重新 malloc；struct 递归字段。
    void deep_copy_value(const std::string& ty, llvm::Value* dst, llvm::Value* src) {
        if (!type_owns_heap(ty)) {
            copy_slots(dst, src, field_slot_width(ty));
            return;
        }
        if (is_dynamic_array(ty)) {
            dyn_slots_deep_copy(ty, dyn_slots_at(dst), dyn_slots_at(src));
            return;
        }
        auto elem = array_elem(ty);
        if (elem.has_value()) {
            const size_t len = array_decl_len(ty).value_or(0);
            const size_t eslots = array_elem_slots(ty);
            for (size_t i = 0; i < len; ++i) {
                deep_copy_value(*elem, flat_slot(dst, i * eslots),
                                flat_slot(src, i * eslots));
            }
            return;
        }
        auto it = structs_.find(ty);
        if (it == structs_.end()) return;
        for (const auto& [fname, fty] : it->second) {
            const size_t off = direct_field_slot_offset(ty, fname, Position(1, 1));
            if (is_dynamic_array(fty)) {
                dyn_slots_deep_copy(fty, dyn_slots_at(flat_slot(dst, off)),
                                    dyn_slots_at(flat_slot(src, off)));
            } else if (type_owns_heap(fty)) {
                deep_copy_value(fty, flat_slot(dst, off), flat_slot(src, off));
            } else {
                copy_slots(flat_slot(dst, off), flat_slot(src, off),
                           field_slot_width(fty));
            }
        }
    }

    /// 扁平槽块中的值转移（return / 整体赋值）：descriptor 复制后清空源；
    /// 无堆字段逐槽复制。源块之后不应再被 drop。
    void transfer_value_slots(const std::string& ty, llvm::Value* dst, llvm::Value* src) {
        if (!type_owns_heap(ty)) {
            copy_slots(dst, src, field_slot_width(ty));
            return;
        }
        if (is_dynamic_array(ty)) {
            dyn_slots_transfer(dyn_slots_at(dst), dyn_slots_at(src));
            return;
        }
        auto elem = array_elem(ty);
        if (elem.has_value()) {
            const size_t len = array_decl_len(ty).value_or(0);
            const size_t eslots = array_elem_slots(ty);
            for (size_t i = 0; i < len; ++i) {
                transfer_value_slots(*elem, flat_slot(dst, i * eslots),
                                     flat_slot(src, i * eslots));
            }
            return;
        }
        auto it = structs_.find(ty);
        if (it == structs_.end()) return;
        for (const auto& [fname, fty] : it->second) {
            const size_t off = direct_field_slot_offset(ty, fname, Position(1, 1));
            if (is_dynamic_array(fty)) {
                dyn_slots_transfer(dyn_slots_at(flat_slot(dst, off)),
                                   dyn_slots_at(flat_slot(src, off)));
            } else if (type_owns_heap(fty)) {
                transfer_value_slots(fty, flat_slot(dst, off), flat_slot(src, off));
            } else {
                copy_slots(flat_slot(dst, off), flat_slot(src, off),
                           field_slot_width(fty));
            }
        }
    }

    /// 递归 drop 扁平槽块中的一个值（标量 / 无堆字段不处理）。
    void drop_value_slots(const std::string& ty, llvm::Value* base) {
        if (!type_owns_heap(ty)) return;
        if (is_dynamic_array(ty)) {
            dyn_drop_slots(flat_slot(base, 0), flat_slot(base, 1), flat_slot(base, 2), ty);
            return;
        }
        auto elem = array_elem(ty);
        if (elem.has_value()) {
            const size_t len = array_decl_len(ty).value_or(0);
            const size_t eslots = array_elem_slots(ty);
            for (size_t i = 0; i < len; ++i) {
                drop_value_slots(*elem, flat_slot(base, i * eslots));
            }
            return;
        }
        auto it = structs_.find(ty);
        if (it == structs_.end()) return;
        for (const auto& [fname, fty] : it->second) {
            if (!type_owns_heap(fty)) continue;
            const size_t off = direct_field_slot_offset(ty, fname, Position(1, 1));
            if (is_dynamic_array(fty)) {
                dyn_drop_slots(flat_slot(base, off), flat_slot(base, off + 1),
                               flat_slot(base, off + 2), fty);
            } else {
                drop_value_slots(fty, flat_slot(base, off));
            }
        }
    }

    /// S3e：递归 drop 一个局部变量（动态数组 / struct 动态字段 / 固定数组元素）。
    void drop_var(const VarInfo& info) {
        if (info.dyn.has_value()) {
            dyn_drop(*info.dyn, info.ty);
            return;
        }
        if (is_array(info.ty)) {
            // 固定 array<struct> / 嵌套数组：只处理元素含堆的类型。
            if (!info.array_len.has_value() || info.addr == nullptr) return;
            auto elem = array_elem(info.ty);
            if (!elem.has_value() || !type_owns_heap(*elem)) return;
            const size_t eslots = array_elem_slots(info.ty);
            for (size_t i = 0; i < *info.array_len; ++i) {
                drop_value_slots(*elem, flat_slot(info.addr, i * eslots));
            }
            return;
        }
        if (!is_struct(info.ty)) return;
        for (const auto& entry : layout_of(info.ty)) {
            if (is_dynamic_array(entry.ty)) {
                auto f = info.dyn_fields.find(entry.path);
                if (f == info.dyn_fields.end()) {
                    throw TenetError("内部错误：struct 字段 `" + entry.path +
                                     "` 缺少 descriptor");
                }
                dyn_drop(f->second, entry.ty);
                continue;
            }
            if (!type_owns_heap(entry.ty)) continue;
            auto f = info.fields.find(entry.path);
            if (f == info.fields.end()) {
                throw TenetError("内部错误：struct 字段 `" + entry.path + "` 缺少槽位");
            }
            drop_value_slots(entry.ty, f->second.second);
        }
    }

    // ---- S3c-2：动态数组参数 / 返回值的 3 槽 descriptor ----
    // descriptor 布局：slot0 = data(ptr)，slot1 = len(i64)，slot2 = cap(i64)。
    // 调用方为动态实参分配 descriptor；被调函数入口按 descriptor 深拷贝（值语义）。
    // 动态返回值走隐藏 `ptr %sret` descriptor；`return 变量` 转移所有权并清空本地槽位。
    // S3c-3a：字面量/调用结果作实参时构造临时 descriptor，调用返回后只 free 堆缓冲区；
    // 作 return 值时把 data/len/cap 转移进 sret，不 free。

    /// S3c-3a 动态实参的临时所有权：
    /// - `var`：字面量构造的临时动态数组，调用返回后按 descriptor drop；
    /// - `desc`：调用结果 descriptor，调用返回后只 free 其 data（不 free 栈上 descriptor）。
    /// `ty` 记录实参类型：动态嵌套数组 drop 时要先逐内层 free，再 free 外层。
    struct TempDyn {
        std::optional<DynArrayInfo> var;
        llvm::Value* desc = nullptr;
        std::string ty;
    };

    /// 分配一个 3 槽 descriptor 栈空间（[3 x i64]）。
    llvm::Value* desc_alloc(const std::string& name) {
        auto* arr = llvm::ArrayType::get(llvm::Type::getInt64Ty(ctx_), 3);
        return builder_.CreateAlloca(arr, nullptr, name);
    }

    /// descriptor 第 i 槽地址：GEP [3 x i64], ptr desc, i64 0, i64 i。
    llvm::Value* desc_slot(llvm::Value* desc, size_t i) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* arr = llvm::ArrayType::get(i64, 3);
        llvm::Value* idxs[] = {llvm::ConstantInt::get(i64, 0),
                               llvm::ConstantInt::get(i64, static_cast<uint64_t>(i))};
        return builder_.CreateGEP(arr, desc, idxs, "desc.slot");
    }

    /// 把动态数组的 data/len/cap 写进 descriptor。
    void desc_store_info(llvm::Value* desc, const VarInfo& info) {
        if (!info.dyn.has_value()) {
            throw TenetError("内部错误：不是动态数组，无法写入 descriptor");
        }
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        auto* d = builder_.CreateLoad(pty, info.dyn->data, "desc.data");
        auto* l = builder_.CreateLoad(i64, info.dyn->len, "desc.len");
        auto* c = builder_.CreateLoad(i64, info.dyn->cap, "desc.cap");
        builder_.CreateStore(d, desc_slot(desc, 0));
        builder_.CreateStore(l, desc_slot(desc, 1));
        builder_.CreateStore(c, desc_slot(desc, 2));
    }

    /// 清空动态数组变量的 data/len/cap 槽位（所有权转移后避免 double free）。
    void desc_clear_info(const VarInfo& info) {
        if (!info.dyn.has_value()) {
            throw TenetError("内部错误：不是动态数组，无法清空 descriptor");
        }
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        builder_.CreateStore(llvm::ConstantPointerNull::get(pty), info.dyn->data);
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), info.dyn->len);
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), info.dyn->cap);
    }

    /// 清空任意 descriptor 的 data/len/cap（S3c-3a：所有权转移后避免 double free）。
    void desc_clear(llvm::Value* desc) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        builder_.CreateStore(llvm::ConstantPointerNull::get(pty), desc_slot(desc, 0));
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), desc_slot(desc, 1));
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), desc_slot(desc, 2));
    }

    /// 逐槽复制 descriptor（S3c-3a：调用结果作实参 / return 调用结果）。
    void desc_copy(llvm::Value* dst, llvm::Value* src) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        for (size_t i = 0; i < 3; ++i) {
            auto* v = builder_.CreateLoad(i64, desc_slot(src, i), "desc.copy");
            builder_.CreateStore(v, desc_slot(dst, i));
        }
    }

    /// 释放 descriptor 拥有的堆缓冲区（只 free data，不 free 栈上 descriptor），
    /// 随后清空槽位；空指针安全。S3c-3a 由调用方清理临时实参 descriptor。
    /// 动态嵌套数组按 ty 先逐内层 free(data)，再 free 外层。
    void drop_desc_owned(llvm::Value* desc, const std::string& ty) {
        dyn_drop_slots(desc_slot(desc, 0), desc_slot(desc, 1), desc_slot(desc, 2), ty);
    }

    /// 从返回值的 sret descriptor 接管堆缓冲区到新的本地动态数组。
    /// 接管后清空 descriptor，调用方不再拥有缓冲区（后续由本地变量的 drop 释放）。
    VarInfo dynamic_from_desc(const std::string& ty_name, llvm::Value* desc,
                              const std::string& name, const Position& pos) {
        if (!array_elem(ty_name).has_value()) {
            throw TenetError::at_pos("`" + ty_name + "` 不是数组类型", pos);
        }
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        auto* d = builder_.CreateLoad(pty, desc_slot(desc, 0), "desc.data");
        auto* l = builder_.CreateLoad(i64, desc_slot(desc, 1), "desc.len");
        auto* c = builder_.CreateLoad(i64, desc_slot(desc, 2), "desc.cap");
        DynArrayInfo dyn = dyn_new_slots(name);
        builder_.CreateStore(d, dyn.data);
        builder_.CreateStore(l, dyn.len);
        builder_.CreateStore(c, dyn.cap);
        // 临时 descriptor 的缓冲区已被接管，清空避免再次 free。
        builder_.CreateStore(llvm::ConstantPointerNull::get(pty), desc_slot(desc, 0));
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), desc_slot(desc, 1));
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), desc_slot(desc, 2));
        return VarInfo{ty_name, nullptr, {}, std::nullopt, dyn};
    }

    /// 动态数组参数入口：按调用方 descriptor 的 data/len/cap 深拷贝到本地（值语义）。
    /// 动态嵌套数组逐内层 realloc + 拷贝，参数与调用方完全独立。
    VarInfo dynamic_param_from_desc(const std::string& ty_name, llvm::Value* desc,
                                    const std::string& name, const Position& pos) {
        auto elem = array_elem(ty_name);
        if (!elem.has_value()) {
            throw TenetError::at_pos("`" + ty_name + "` 不是数组类型", pos);
        }
        if (is_array(*elem)) {
            ensure_dynamic_nested_scalar_array(ty_name, pos);
            return nested_copy_from_slots(ty_name, desc_slot(desc, 0), desc_slot(desc, 1),
                                          desc_slot(desc, 2), pos);
        }
        // S3c-3b-2：struct 元素按 slots 个 8 字节槽存放，入口深拷贝按槽计数。
        const size_t slots = array_elem_slots(ty_name);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        auto* sp = builder_.CreateLoad(pty, desc_slot(desc, 0), "desc.src.data");
        auto* sl = builder_.CreateLoad(i64, desc_slot(desc, 1), "desc.src.len");
        auto* sc = builder_.CreateLoad(i64, desc_slot(desc, 2), "desc.src.cap");
        auto* bytes = builder_.CreateMul(
            sc, llvm::ConstantInt::get(i64, static_cast<uint64_t>(slots * 8)), "desc.bytes");
        auto* np = builder_.CreateCall(runtime_fn("malloc"), {bytes}, "dyn.param.data");
        if (type_owns_heap(*elem)) {
            // S3e：array<struct> 元素含动态字段 → 逐元素深拷贝。
            dyn_elems_copy(*elem, slots, np, sp, sl);
        } else {
            auto* total = builder_.CreateMul(
                sl, llvm::ConstantInt::get(i64, static_cast<uint64_t>(slots)), "desc.total");
            dyn_copy_elems(np, sp, total);
        }
        DynArrayInfo dyn = dyn_new_slots(name);
        builder_.CreateStore(np, dyn.data);
        builder_.CreateStore(sl, dyn.len);
        builder_.CreateStore(sc, dyn.cap);
        return VarInfo{ty_name, nullptr, {}, std::nullopt, dyn};
    }

    /// 动态数组 return（S3c-3a）：支持变量 / 字面量 / 返回动态数组的调用。
    /// - 变量：把 data/len/cap 写进 sret 并清空本地槽位（不 free）。
    /// - 字面量：构造临时动态数组，把 data/len/cap 转移进 sret（不 free，所有权给调用方）。
    /// - 调用：把内层调用返回的 descriptor 复制进 sret，清空临时 descriptor（不 free）。
    void transfer_dynamic_expr_to_sret(const std::string& ty_name, const ExprPtr& expr,
                                       llvm::Value* sret) {
        if (!expr) {
            throw TenetError::at_pos("动态数组 return 必须带值", Position(1, 1));
        }
        switch (expr->kind) {
            case Expr::Kind::Var: {
                const VarInfo& info = lookup_var(expr->name, expr->pos);
                if (info.ty != ty_name || !info.dyn.has_value()) {
                    throw TenetError::at_pos(
                        "返回类型不匹配：需要 " + ty_name + "，实际 " +
                            value_type_name(info.ty),
                        expr->pos);
                }
                desc_store_info(sret, info);
                desc_clear_info(info);
                return;
            }
            case Expr::Kind::Array: {
                VarInfo tmp = init_dynamic_array("__ret_tmp", ty_name, expr, expr->pos);
                desc_store_info(sret, tmp);
                // 所有权已交给调用方：清空临时槽位，避免后续 drop 误 free。
                desc_clear_info(tmp);
                return;
            }
            case Expr::Kind::Call: {
                auto [rt, desc] = gen_expr(expr);
                if (rt != ty_name) {
                    throw TenetError::at_pos(
                        "返回类型不匹配：需要 " + ty_name + "，调用返回 " +
                            value_type_name(rt),
                        expr->pos);
                }
                desc_copy(sret, desc);
                // 内层调用的缓冲区已转移给 sret；只清空临时 descriptor，栈槽本身不 free。
                desc_clear(desc);
                return;
            }
            default:
                throw TenetError::at_pos(
                    "动态数组 return 只支持变量、字面量或返回动态数组的调用", expr->pos);
        }
    }

    /// 运行时 len 越界检查：idx >= len（无符号比较，负数同样命中）→ tenet_bounds_fail。
    void bounds_check_value(llvm::Value* index, llvm::Value* len) {
        auto* cmp = builder_.CreateICmpUGE(index, len, "dbounds.cmp");
        auto* fail_bb = llvm::BasicBlock::Create(ctx_, "dbounds.fail");
        auto* ok_bb = llvm::BasicBlock::Create(ctx_, "dbounds.ok");
        auto* fn = builder_.GetInsertBlock()->getParent();
        builder_.CreateCondBr(cmp, fail_bb, ok_bb);
        fail_bb->insertInto(fn);
        builder_.SetInsertPoint(fail_bb);
        builder_.CreateCall(runtime_fn("tenet_bounds_fail"), {index, len});
        builder_.CreateUnreachable();
        ok_bb->insertInto(fn);
        builder_.SetInsertPoint(ok_bb);
    }

    /// 动态数组下标：加载 data/len，下标运行时边界检查，返回 (元素类型, 槽地址)。
    std::pair<std::string, llvm::Value*> dynamic_index_addr(const VarInfo& info,
                                                            const ExprPtr& index) {
        if (!info.dyn.has_value()) {
            throw TenetError("内部错误：变量不是动态数组");
        }
        std::string elem = array_elem_scalar(info.ty, index->pos);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* data = builder_.CreateLoad(ptr_ty(ctx_), info.dyn->data, "dyn.data");
        auto* len = builder_.CreateLoad(i64, info.dyn->len, "dyn.len");
        auto [it, iv] = gen_expr(index);
        if (it != "i64") {
            throw TenetError::at_pos(
                "数组下标必须是 int，实际为 " + std::string(tenet_name(it)), index->pos);
        }
        bounds_check_value(iv, len);
        return {elem, dyn_slot(data, iv)};
    }

    /// S3c-3b-2：动态 `array<struct>` 初始化。
    /// 堆缓冲区按 元素 stride = slots*8 布局，支持字面量 / 同类型动态数组变量深拷贝 /
    /// 返回动态数组的调用（接管 sret descriptor）。drop 只 free 堆缓冲（struct 不含 array）。
    VarInfo init_dynamic_struct_array(const std::string& name, const std::string& ty_name,
                                      const ExprPtr& value, const Position& pos) {
        auto elem = array_elem(ty_name);
        if (!elem.has_value() || !is_struct(*elem)) {
            throw TenetError::at_pos("`" + ty_name + "` 不是 array<struct>", pos);
        }
        const size_t slots = array_elem_slots(ty_name);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        if (value->kind == Expr::Kind::Call) {
            // S3c-2 ABI：函数调用返回动态 array<struct> → 接管 sret descriptor。
            auto [rt, desc] = gen_expr(value);
            if (rt != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，调用返回 " + value_type_name(rt),
                    value->pos);
            }
            return dynamic_from_desc(ty_name, desc, name, value->pos);
        }
        DynArrayInfo dyn = dyn_new_slots(name);
        if (value->kind == Expr::Kind::Array) {
            size_t len = value->args.size();
            size_t cap = std::max<size_t>(len, 4);
            auto* bytes = llvm::ConstantInt::get(
                i64, static_cast<uint64_t>(cap * slots * 8));
            auto* p = builder_.CreateCall(runtime_fn("malloc"), {bytes}, "dyn.data");
            builder_.CreateStore(p, dyn.data);
            builder_.CreateStore(llvm::ConstantInt::get(i64, static_cast<uint64_t>(len)),
                                 dyn.len);
            builder_.CreateStore(llvm::ConstantInt::get(i64, static_cast<uint64_t>(cap)),
                                 dyn.cap);
            for (size_t i = 0; i < value->args.size(); ++i) {
                auto* dst = dyn_slot(
                    p, llvm::ConstantInt::get(i64, static_cast<uint64_t>(i * slots)));
                pack_expr_to_buffer(*elem, value->args[i], dst);
            }
            return VarInfo{ty_name, nullptr, {}, std::nullopt, dyn};
        }
        if (value->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(value->name, value->pos);
            if (!sinfo.dyn.has_value()) {
                throw TenetError::at_pos("`" + value->name + "` 不是动态数组", value->pos);
            }
            if (sinfo.ty != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但 `" + value->name + "` 是 " +
                        sinfo.ty,
                    value->pos);
            }
            // 深拷贝：按源 cap * slots 重新 malloc，逐槽复制，源数组不受影响。
            // S3e：struct 元素含动态字段时逐元素递归深拷贝。
            if (type_owns_heap(*elem)) {
                dyn_slots_deep_copy(ty_name, dyn_slots_of(dyn),
                                    dyn_slots_of(*sinfo.dyn));
                return VarInfo{ty_name, nullptr, {}, std::nullopt, dyn};
            }
            auto* slen = builder_.CreateLoad(i64, sinfo.dyn->len, "dyn.src.len");
            auto* scap = builder_.CreateLoad(i64, sinfo.dyn->cap, "dyn.src.cap");
            auto* sp = builder_.CreateLoad(pty, sinfo.dyn->data, "dyn.src.data");
            auto* bytes = builder_.CreateMul(
                scap, llvm::ConstantInt::get(i64, static_cast<uint64_t>(slots * 8)),
                "dyn.bytes");
            auto* p = builder_.CreateCall(runtime_fn("malloc"), {bytes}, "dyn.copy.data");
            builder_.CreateStore(p, dyn.data);
            builder_.CreateStore(slen, dyn.len);
            builder_.CreateStore(scap, dyn.cap);
            auto* total = builder_.CreateMul(
                slen, llvm::ConstantInt::get(i64, static_cast<uint64_t>(slots)),
                "dyn.total");
            dyn_copy_elems(p, sp, total);
            return VarInfo{ty_name, nullptr, {}, std::nullopt, dyn};
        }
        throw TenetError::at_pos(
            "`" + name + "` 的 array<struct> 初始化必须是字面量、同类型动态数组或返回数组的调用",
            value->pos);
    }

    /// S3c-3b-2 / S3e：`push(a, struct)` —— 元素按 slots 个 8 字节槽追加。
    /// 目标可以是动态数组变量，也可以是 struct 的动态数组字段（Descriptor 三槽）。
    /// 容量不足时 cap*2，按 slots 计算新缓冲区字节数并逐槽拷贝，free 旧缓冲区。
    void push_struct_dynamic(const std::string& ty, const DynSlots& dslots,
                             const ExprPtr& value) {
        auto elem = array_elem(ty);
        if (!elem.has_value() || !is_struct(*elem)) {
            throw TenetError("内部错误：push 目标不是 array<struct>");
        }
        const size_t eslots = array_elem_slots(ty);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        auto* tmp = alloc_buffer(eslots, "push.tmp");
        pack_expr_to_buffer(*elem, value, tmp);
        auto* len = builder_.CreateLoad(i64, dslots.len, "dyn.len");
        auto* cap = builder_.CreateLoad(i64, dslots.cap, "dyn.cap");
        auto* full = builder_.CreateICmpEQ(len, cap, "dyn.full");
        auto* fn = builder_.GetInsertBlock()->getParent();
        auto* grow_bb = llvm::BasicBlock::Create(ctx_, "dyn.grow");
        auto* after_bb = llvm::BasicBlock::Create(ctx_, "dyn.grow.after");
        builder_.CreateCondBr(full, grow_bb, after_bb);
        grow_bb->insertInto(fn);
        builder_.SetInsertPoint(grow_bb);
        auto* newcap = builder_.CreateMul(cap, llvm::ConstantInt::get(i64, 2), "dyn.newcap");
        auto* bytes = builder_.CreateMul(
            newcap, llvm::ConstantInt::get(i64, static_cast<uint64_t>(eslots * 8)),
            "dyn.bytes");
        auto* np = builder_.CreateCall(runtime_fn("malloc"), {bytes}, "dyn.newdata");
        auto* op = builder_.CreateLoad(pty, dslots.data, "dyn.olddata");
        auto* total =
            builder_.CreateMul(len, llvm::ConstantInt::get(i64, static_cast<uint64_t>(eslots)),
                               "dyn.grow.total");
        dyn_copy_elems(np, op, total);
        builder_.CreateCall(runtime_fn("free"), {op});
        builder_.CreateStore(np, dslots.data);
        builder_.CreateStore(newcap, dslots.cap);
        builder_.CreateBr(after_bb);
        after_bb->insertInto(fn);
        builder_.SetInsertPoint(after_bb);
        auto* data = builder_.CreateLoad(pty, dslots.data, "dyn.data");
        auto* row = builder_.CreateMul(
            len, llvm::ConstantInt::get(i64, static_cast<uint64_t>(eslots)), "dyn.row");
        auto* dst = dyn_slot(data, row);
        for (size_t k = 0; k < eslots; ++k) {
            auto* src_slot = buffer_slot(tmp, eslots, k);
            auto* v = builder_.CreateLoad(i64, src_slot, "push.slot");
            auto* dst_slot = dyn_slot(
                dst, llvm::ConstantInt::get(i64, static_cast<uint64_t>(k)));
            builder_.CreateStore(v, dst_slot);
        }
        auto* newlen = builder_.CreateAdd(len, llvm::ConstantInt::get(i64, 1), "dyn.newlen");
        builder_.CreateStore(newlen, dslots.len);
    }

    /// S3e：`push(a, scalar)` —— 目标可以是动态数组变量或 struct 的动态数组字段。
    /// 容量不足时 cap*2，malloc 新缓冲区 + 逐槽拷贝 + free 旧缓冲区。
    void push_scalar_dynamic(const std::string& ty, const DynSlots& dslots,
                             const ExprPtr& value) {
        std::string elem = array_elem_scalar(ty, value->pos);
        std::string elem_ll = llvm_type(elem);
        auto [vt, v] = gen_expr(value);
        if (vt != elem_ll) {
            throw TenetError::at_pos(
                "push 值类型不匹配：需要 " + elem + "，实际 " + tenet_name(vt),
                value->pos);
        }
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        auto* len = builder_.CreateLoad(i64, dslots.len, "dyn.len");
        auto* cap = builder_.CreateLoad(i64, dslots.cap, "dyn.cap");
        auto* full = builder_.CreateICmpEQ(len, cap, "dyn.full");
        auto* fn = builder_.GetInsertBlock()->getParent();
        auto* grow_bb = llvm::BasicBlock::Create(ctx_, "dyn.grow");
        auto* after_bb = llvm::BasicBlock::Create(ctx_, "dyn.grow.after");
        builder_.CreateCondBr(full, grow_bb, after_bb);
        grow_bb->insertInto(fn);
        builder_.SetInsertPoint(grow_bb);
        auto* newcap = builder_.CreateMul(cap, llvm::ConstantInt::get(i64, 2), "dyn.newcap");
        auto* bytes = builder_.CreateMul(newcap, llvm::ConstantInt::get(i64, 8), "dyn.bytes");
        auto* np = builder_.CreateCall(runtime_fn("malloc"), {bytes}, "dyn.newdata");
        auto* op = builder_.CreateLoad(pty, dslots.data, "dyn.olddata");
        dyn_copy_elems(np, op, len);
        builder_.CreateCall(runtime_fn("free"), {op});
        builder_.CreateStore(np, dslots.data);
        builder_.CreateStore(newcap, dslots.cap);
        builder_.CreateBr(after_bb);
        after_bb->insertInto(fn);
        builder_.SetInsertPoint(after_bb);
        auto* data = builder_.CreateLoad(pty, dslots.data, "dyn.data");
        builder_.CreateStore(pack_scalar(elem, v), dyn_slot(data, len));
        auto* newlen = builder_.CreateAdd(len, llvm::ConstantInt::get(i64, 1), "dyn.newlen");
        builder_.CreateStore(newlen, dslots.len);
    }

    // ---- v1 动态嵌套数组：array<array<T>>（外层动态、内层动态标量）----
    // 外层堆元素是内层 descriptor 的 3 个 i64 槽 `[data, len, cap]`，
    // 外层 stride = 3 * 8 = 24 字节；内层堆仍是普通标量 8 字节槽。
    // 深拷贝 / push / 参数入口 / drop 都必须逐内层处理，不能只 memcpy 外层描述符。

    /// 深拷贝一个动态嵌套数组：源为 [data,len,cap] 的三个槽位，
    /// 每个外层元素（内层 descriptor）都重新 malloc + 拷贝内层元素。
    VarInfo nested_copy_from_slots(const std::string& ty_name, llvm::Value* src_data,
                                   llvm::Value* src_len, llvm::Value* src_cap,
                                   const Position& pos) {
        ensure_dynamic_nested_scalar_array(ty_name, pos);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        auto* sp = builder_.CreateLoad(pty, src_data, "nested.src.data");
        auto* sl = builder_.CreateLoad(i64, src_len, "nested.src.len");
        auto* sc = builder_.CreateLoad(i64, src_cap, "nested.src.cap");
        DynArrayInfo dyn = dyn_new_slots("nested.copy");
        auto* obytes = builder_.CreateMul(sc, llvm::ConstantInt::get(i64, 24),
                                          "nested.copy.bytes");
        auto* np = builder_.CreateCall(runtime_fn("malloc"), {obytes}, "nested.copy.data");
        builder_.CreateStore(np, dyn.data);
        builder_.CreateStore(sl, dyn.len);
        builder_.CreateStore(sc, dyn.cap);

        auto* fn = builder_.GetInsertBlock()->getParent();
        auto* i_slot = builder_.CreateAlloca(i64, nullptr, "nested.copy.i");
        auto* j_slot = builder_.CreateAlloca(i64, nullptr, "nested.copy.j");
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), i_slot);
        auto* cond_bb = llvm::BasicBlock::Create(ctx_, "nested.copy.cond");
        auto* body_bb = llvm::BasicBlock::Create(ctx_, "nested.copy.body");
        auto* jcond_bb = llvm::BasicBlock::Create(ctx_, "nested.copy.jcond");
        auto* jbody_bb = llvm::BasicBlock::Create(ctx_, "nested.copy.jbody");
        auto* jend_bb = llvm::BasicBlock::Create(ctx_, "nested.copy.jend");
        auto* end_bb = llvm::BasicBlock::Create(ctx_, "nested.copy.end");
        builder_.CreateBr(cond_bb);
        cond_bb->insertInto(fn);
        builder_.SetInsertPoint(cond_bb);
        auto* i = builder_.CreateLoad(i64, i_slot, "nested.copy.idx");
        auto* cmp = builder_.CreateICmpSLT(i, sl, "nested.copy.cmp");
        builder_.CreateCondBr(cmp, body_bb, end_bb);
        body_bb->insertInto(fn);
        builder_.SetInsertPoint(body_bb);
        auto* row_off = builder_.CreateMul(i, llvm::ConstantInt::get(i64, 3), "nested.copy.row");
        auto* row = dyn_slot(sp, row_off);
        auto* ip = builder_.CreateLoad(pty, desc_slot(row, 0), "nested.copy.inner.data");
        auto* il = builder_.CreateLoad(i64, desc_slot(row, 1), "nested.copy.inner.len");
        auto* ic = builder_.CreateLoad(i64, desc_slot(row, 2), "nested.copy.inner.cap");
        auto* ibytes = builder_.CreateMul(ic, llvm::ConstantInt::get(i64, 8),
                                          "nested.copy.inner.bytes");
        auto* nip = builder_.CreateCall(runtime_fn("malloc"), {ibytes}, "nested.copy.inner");
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), j_slot);
        builder_.CreateBr(jcond_bb);
        jcond_bb->insertInto(fn);
        builder_.SetInsertPoint(jcond_bb);
        auto* j = builder_.CreateLoad(i64, j_slot, "nested.copy.jidx");
        auto* jc = builder_.CreateICmpSLT(j, il, "nested.copy.jcmp");
        builder_.CreateCondBr(jc, jbody_bb, jend_bb);
        jbody_bb->insertInto(fn);
        builder_.SetInsertPoint(jbody_bb);
        auto* ss = dyn_slot(ip, j);
        auto* dd = dyn_slot(nip, j);
        builder_.CreateStore(builder_.CreateLoad(i64, ss, "nested.copy.elem"), dd);
        auto* nj = builder_.CreateAdd(j, llvm::ConstantInt::get(i64, 1), "nested.copy.jnext");
        builder_.CreateStore(nj, j_slot);
        builder_.CreateBr(jcond_bb);
        jend_bb->insertInto(fn);
        builder_.SetInsertPoint(jend_bb);
        auto* drow_off =
            builder_.CreateMul(i, llvm::ConstantInt::get(i64, 3), "nested.copy.drow");
        auto* drow = dyn_slot(np, drow_off);
        builder_.CreateStore(nip, desc_slot(drow, 0));
        builder_.CreateStore(il, desc_slot(drow, 1));
        builder_.CreateStore(ic, desc_slot(drow, 2));
        auto* ni = builder_.CreateAdd(i, llvm::ConstantInt::get(i64, 1), "nested.copy.next");
        builder_.CreateStore(ni, i_slot);
        builder_.CreateBr(cond_bb);
        end_bb->insertInto(fn);
        builder_.SetInsertPoint(end_bb);
        return VarInfo{ty_name, nullptr, {}, std::nullopt, dyn};
    }

    /// v1 动态嵌套数组初始化：字面量（可空）/ 同类型变量深拷贝 /
    /// 返回动态嵌套数组的调用（接管 sret descriptor）。
    VarInfo init_dynamic_nested_array(const std::string& name, const std::string& ty_name,
                                      const ExprPtr& value, const Position& pos) {
        ensure_dynamic_nested_scalar_array(ty_name, pos);
        auto inner_ty = array_elem(ty_name).value();
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        if (value->kind == Expr::Kind::Call) {
            auto [rt, desc] = gen_expr(value);
            if (rt != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，调用返回 " + value_type_name(rt),
                    value->pos);
            }
            return dynamic_from_desc(ty_name, desc, name, value->pos);
        }
        DynArrayInfo dyn = dyn_new_slots(name);
        if (value->kind == Expr::Kind::Array) {
            size_t len = value->args.size();
            size_t cap = std::max<size_t>(len, 4);
            auto* bytes =
                llvm::ConstantInt::get(i64, static_cast<uint64_t>(cap * 3 * 8));
            auto* p = builder_.CreateCall(runtime_fn("malloc"), {bytes}, "dyn.data");
            builder_.CreateStore(p, dyn.data);
            builder_.CreateStore(llvm::ConstantInt::get(i64, static_cast<uint64_t>(len)),
                                 dyn.len);
            builder_.CreateStore(llvm::ConstantInt::get(i64, static_cast<uint64_t>(cap)),
                                 dyn.cap);
            for (size_t i = 0; i < value->args.size(); ++i) {
                const ExprPtr& row_expr = value->args[i];
                if (row_expr->kind != Expr::Kind::Array &&
                    row_expr->kind != Expr::Kind::Var &&
                    row_expr->kind != Expr::Kind::Call) {
                    throw TenetError::at_pos(
                        "嵌套数组第 " + std::to_string(i) +
                            " 个元素必须是内层数组字面量、同类型变量或返回数组的调用",
                        row_expr->pos);
                }
                // 内层先构造成独立的动态数组，再把 descriptor 三个槽写进外层元素。
                VarInfo row =
                    init_dynamic_array("__nested_row", inner_ty, row_expr, row_expr->pos);
                auto* rd = builder_.CreateLoad(pty, row.dyn->data, "nested.row.data");
                auto* rl = builder_.CreateLoad(i64, row.dyn->len, "nested.row.len");
                auto* rc = builder_.CreateLoad(i64, row.dyn->cap, "nested.row.cap");
                auto* dst = dyn_slot(
                    p, llvm::ConstantInt::get(i64, static_cast<uint64_t>(i * 3)));
                builder_.CreateStore(rd, desc_slot(dst, 0));
                builder_.CreateStore(rl, desc_slot(dst, 1));
                builder_.CreateStore(rc, desc_slot(dst, 2));
            }
            return VarInfo{ty_name, nullptr, {}, std::nullopt, dyn};
        }
        if (value->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(value->name, value->pos);
            if (!sinfo.dyn.has_value()) {
                throw TenetError::at_pos("`" + value->name + "` 不是动态数组", value->pos);
            }
            if (sinfo.ty != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但 `" + value->name + "` 是 " +
                        sinfo.ty,
                    value->pos);
            }
            return nested_copy_from_slots(ty_name, sinfo.dyn->data, sinfo.dyn->len,
                                          sinfo.dyn->cap, value->pos);
        }
        throw TenetError::at_pos(
            "`" + name + "` 的动态嵌套数组初始化必须是字面量、同类型动态数组或"
            "返回动态数组的调用",
            value->pos);
    }

    /// `push(a, inner)`：内层数组先深拷贝到临时动态数组，再把 descriptor
    /// 三个槽追加到外层元素（stride=3）；外层容量不足时 cap*2。
    void push_nested_dynamic(const std::string& ty, const DynSlots& dslots,
                             const ExprPtr& value) {
        ensure_dynamic_nested_scalar_array(ty, value->pos);
        auto inner_ty = array_elem(ty).value();
        if (value->kind != Expr::Kind::Array && value->kind != Expr::Kind::Var &&
            value->kind != Expr::Kind::Call) {
            throw TenetError::at_pos(
                "push 的嵌套数组值必须是内层数组字面量、同类型变量或返回数组的调用",
                value->pos);
        }
        // 内层深拷贝：变量 / 字面量 / 调用结果都得到独立缓冲区，随后转移给外层。
        VarInfo tmp = init_dynamic_array("__push_tmp", inner_ty, value, value->pos);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        auto* td = builder_.CreateLoad(pty, tmp.dyn->data, "push.inner.data");
        auto* tl = builder_.CreateLoad(i64, tmp.dyn->len, "push.inner.len");
        auto* tc = builder_.CreateLoad(i64, tmp.dyn->cap, "push.inner.cap");
        auto* len = builder_.CreateLoad(i64, dslots.len, "dyn.len");
        auto* cap = builder_.CreateLoad(i64, dslots.cap, "dyn.cap");
        auto* full = builder_.CreateICmpEQ(len, cap, "dyn.full");
        auto* fn = builder_.GetInsertBlock()->getParent();
        auto* grow_bb = llvm::BasicBlock::Create(ctx_, "dyn.grow");
        auto* after_bb = llvm::BasicBlock::Create(ctx_, "dyn.grow.after");
        builder_.CreateCondBr(full, grow_bb, after_bb);
        grow_bb->insertInto(fn);
        builder_.SetInsertPoint(grow_bb);
        auto* newcap = builder_.CreateMul(cap, llvm::ConstantInt::get(i64, 2), "dyn.newcap");
        auto* bytes = builder_.CreateMul(newcap, llvm::ConstantInt::get(i64, 24),
                                         "dyn.bytes");
        auto* np = builder_.CreateCall(runtime_fn("malloc"), {bytes}, "dyn.newdata");
        auto* op = builder_.CreateLoad(pty, dslots.data, "dyn.olddata");
        auto* total = builder_.CreateMul(len, llvm::ConstantInt::get(i64, 3),
                                         "dyn.grow.total");
        dyn_copy_elems(np, op, total);
        builder_.CreateCall(runtime_fn("free"), {op});
        builder_.CreateStore(np, dslots.data);
        builder_.CreateStore(newcap, dslots.cap);
        builder_.CreateBr(after_bb);
        after_bb->insertInto(fn);
        builder_.SetInsertPoint(after_bb);
        auto* data = builder_.CreateLoad(pty, dslots.data, "dyn.data");
        auto* row = builder_.CreateMul(len, llvm::ConstantInt::get(i64, 3), "dyn.row");
        auto* dst = dyn_slot(data, row);
        builder_.CreateStore(td, desc_slot(dst, 0));
        builder_.CreateStore(tl, desc_slot(dst, 1));
        builder_.CreateStore(tc, desc_slot(dst, 2));
        builder_.CreateStore(llvm::ConstantPointerNull::get(pty), tmp.dyn->data);
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), tmp.dyn->len);
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), tmp.dyn->cap);
        auto* newlen = builder_.CreateAdd(len, llvm::ConstantInt::get(i64, 1), "dyn.newlen");
        builder_.CreateStore(newlen, dslots.len);
    }

    /// 计算 `a[i]` 的内层 descriptor 地址（外层下标越界检查）。
    llvm::Value* dynamic_nested_row_desc(const VarInfo& info, const ExprPtr& outer_idx) {
        ensure_dynamic_nested_scalar_array(info.ty, outer_idx->pos);
        if (!info.dyn.has_value()) {
            throw TenetError::at_pos("`" + info.ty + "` 不是动态数组", outer_idx->pos);
        }
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* data = builder_.CreateLoad(ptr_ty(ctx_), info.dyn->data, "dyn.data");
        auto* len = builder_.CreateLoad(i64, info.dyn->len, "dyn.len");
        auto [ot, ov] = gen_expr(outer_idx);
        if (ot != "i64") {
            throw TenetError::at_pos(
                "数组下标必须是 int，实际为 " + std::string(tenet_name(ot)),
                outer_idx->pos);
        }
        bounds_check_value(ov, len);
        auto* row = builder_.CreateMul(ov, llvm::ConstantInt::get(i64, 3), "nested.row");
        return dyn_slot(data, row);
    }

    /// `a[i][j]` 的标量地址：内外两层各自做边界检查（内层 len 从 descriptor 读）。
    std::pair<std::string, llvm::Value*> nested_dynamic_index_addr(
        const VarInfo& info, const ExprPtr& outer_idx, const ExprPtr& inner_idx,
        const Position& pos) {
        auto scalar = dynamic_nested_scalar_elem(info.ty);
        if (!scalar.has_value()) {
            throw TenetError::at_pos(
                "只支持 array<array<int/float/bool>> 的二级下标", pos);
        }
        auto* row = dynamic_nested_row_desc(info, outer_idx);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* ip = builder_.CreateLoad(ptr_ty(ctx_), desc_slot(row, 0), "nested.inner.data");
        auto* il = builder_.CreateLoad(i64, desc_slot(row, 1), "nested.inner.len");
        auto [it, iv] = gen_expr(inner_idx);
        if (it != "i64") {
            throw TenetError::at_pos(
                "数组下标必须是 int，实际为 " + std::string(tenet_name(it)),
                inner_idx->pos);
        }
        bounds_check_value(iv, il);
        return {*scalar, dyn_slot(ip, iv)};
    }

    /// 构造动态数组值：数组字面量（可空，新建堆缓冲）/ 同类型动态数组变量（深拷贝）
    /// / 返回动态数组的调用（接管 sret descriptor）。S3c-3a 的字面量实参与
    /// `return 字面量` 也复用它构造临时动态数组，再转移/清理 descriptor。
    VarInfo init_dynamic_array(const std::string& name, const std::string& ty_name,
                               const ExprPtr& value, const Position& pos) {
        // S3e：`s.a` / `t.a` / `arr[i].a` 这类动态数组字段左值 → 深拷贝一份新数组。
        if (value && (value->kind == Expr::Kind::Field || value->kind == Expr::Kind::Index)) {
            auto dt = resolve_dyn_target(value);
            if (dt.has_value()) {
                if (dt->first != ty_name) {
                    throw TenetError::at_pos(
                        "`" + name + "` 需要 " + ty_name + "，实际是 " + dt->first,
                        value->pos);
                }
                return dyn_deep_copy_from(name, ty_name, dt->second);
            }
        }
        if (is_nested_array(ty_name)) {
            // v1 动态嵌套数组：外层与内层都必须动态，内层元素限标量。
            ensure_dynamic_nested_scalar_array(ty_name, pos);
            return init_dynamic_nested_array(name, ty_name, value, pos);
        }
        if (has_struct_elem(ty_name)) {
            // S3c-3b-2：动态 array<struct> 的元素按 struct 扁平槽存放。
            return init_dynamic_struct_array(name, ty_name, value, pos);
        }
        std::string elem = array_elem_scalar(ty_name, pos);
        std::string elem_ll = llvm_type(elem);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* pty = ptr_ty(ctx_);
        if (value->kind == Expr::Kind::Call) {
            // S3c-2：函数调用返回动态数组 → 接管 sret descriptor 的堆缓冲区；
            // 临时 descriptor 本身在调用方栈上，不需要也不允许 free。
            auto [rt, desc] = gen_expr(value);
            if (rt != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，调用返回 " + value_type_name(rt),
                    value->pos);
            }
            return dynamic_from_desc(ty_name, desc, name, value->pos);
        }
        DynArrayInfo dyn = dyn_new_slots(name);
        if (value->kind == Expr::Kind::Array) {
            size_t len = value->args.size();
            size_t cap = std::max<size_t>(len, 4);  // 空数组 / 小数组默认 4 个槽
            dyn_alloc(dyn, len, cap);
            auto* data = builder_.CreateLoad(pty, dyn.data, name + ".data.0");
            for (size_t i = 0; i < value->args.size(); ++i) {
                auto [vt, v] = gen_expr(value->args[i]);
                if (vt != elem_ll) {
                    throw TenetError::at_pos(
                        "数组元素 " + std::to_string(i) + " 类型不匹配：需要 " + elem + "，实际 " +
                            tenet_name(vt),
                        value->args[i]->pos);
                }
                auto* idx = llvm::ConstantInt::get(i64, static_cast<uint64_t>(i));
                builder_.CreateStore(pack_scalar(elem, v), dyn_slot(data, idx));
            }
            return VarInfo{ty_name, nullptr, {}, std::nullopt, dyn};
        }
        if (value->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(value->name, value->pos);
            if (!sinfo.dyn.has_value()) {
                throw TenetError::at_pos("`" + value->name + "` 不是动态数组", value->pos);
            }
            if (!same_array_elem(sinfo.ty, ty_name)) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但 `" + value->name + "` 是 " +
                        sinfo.ty,
                    value->pos);
            }
            // 深拷贝：按源 cap 重新 malloc，逐元素复制，源数组不受影响。
            auto* slen = builder_.CreateLoad(i64, sinfo.dyn->len, "dyn.src.len");
            auto* scap = builder_.CreateLoad(i64, sinfo.dyn->cap, "dyn.src.cap");
            auto* sp = builder_.CreateLoad(pty, sinfo.dyn->data, "dyn.src.data");
            auto* bytes = builder_.CreateMul(scap, llvm::ConstantInt::get(i64, 8), "dyn.bytes");
            auto* p = builder_.CreateCall(runtime_fn("malloc"), {bytes}, "dyn.copy.data");
            builder_.CreateStore(p, dyn.data);
            builder_.CreateStore(slen, dyn.len);
            builder_.CreateStore(scap, dyn.cap);
            dyn_copy_elems(p, sp, slen);
            return VarInfo{ty_name, nullptr, {}, std::nullopt, dyn};
        }
        throw TenetError::at_pos(
            "`" + name + "` 的动态数组初始化必须是数组字面量、同类型动态数组或返回动态数组的调用",
            value->pos);
    }

    /// 动态数组整体赋值：先深拷贝到临时 descriptor，drop 旧值后接管（自赋值直接忽略）。
    void assign_dynamic(const std::string& name, const VarInfo& dst, const ExprPtr& value,
                        const Position& pos) {
        if (value->kind == Expr::Kind::Var && value->name == name) return;
        if (value->kind == Expr::Kind::Var) {
            const VarInfo& src = lookup_var(value->name, value->pos);
            if (!src.dyn.has_value() || !same_array_elem(src.ty, dst.ty)) {
                throw TenetError::at_pos(
                    "数组赋值类型不匹配：需要 " + dst.ty + "，右侧是 " +
                        value_type_name(src.ty),
                    value->pos);
            }
        }
        VarInfo tmp = init_dynamic_array("__assign_tmp", dst.ty, value, pos);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* td = builder_.CreateLoad(ptr_ty(ctx_), tmp.dyn->data, "dyn.assign.data");
        auto* tl = builder_.CreateLoad(i64, tmp.dyn->len, "dyn.assign.len");
        auto* tc = builder_.CreateLoad(i64, tmp.dyn->cap, "dyn.assign.cap");
        dyn_drop(*dst.dyn, dst.ty);
        builder_.CreateStore(td, dst.dyn->data);
        builder_.CreateStore(tl, dst.dyn->len);
        builder_.CreateStore(tc, dst.dyn->cap);
    }

    /// drop 指定作用域里拥有堆内存的变量（动态数组 / 含动态字段的 struct /
    /// 元素含堆的固定数组）。按变量名排序，保证 IR 稳定。
    void drop_scope_at(size_t idx) {
        std::vector<std::string> names;
        for (const auto& [name, info] : symbols_[idx]) {
            if (type_owns_heap(info.ty)) names.push_back(name);
        }
        std::sort(names.begin(), names.end());
        for (const auto& name : names) {
            drop_var(symbols_[idx].at(name));
        }
    }

    /// 离开当前（最内层）作用域：drop 其中的动态数组。
    void drop_scope() {
        if (!symbols_.empty()) drop_scope_at(symbols_.size() - 1);
    }

    /// drop 索引 >= depth 的所有作用域（break 退出循环体用）。
    void drop_scopes_from(size_t depth) {
        for (size_t i = symbols_.size(); i-- > depth;) drop_scope_at(i);
    }

    /// drop 所有作用域里的动态数组（return / 函数结束用）。
    void drop_all_scopes() {
        for (size_t i = symbols_.size(); i-- > 0;) drop_scope_at(i);
    }

    /// 短路 && / ||：基本块 + phi（IRBuilder 下 phi 最简洁）。
    std::pair<std::string, llvm::Value*> gen_logic(const std::string& op, const ExprPtr& lhs, const ExprPtr& rhs) {
        auto [lt, lv] = gen_expr(lhs);
        if (lt != "i1") {
            throw TenetError::at_pos("运算符 `" + op + "` 只能作用于 bool，实际为 " + value_type_name(lt),
                                     lhs->pos);
        }
        auto fn = builder_.GetInsertBlock()->getParent();
        auto rhs_bb = llvm::BasicBlock::Create(ctx_, "l.rhs");
        auto short_bb = llvm::BasicBlock::Create(ctx_, "l.short");
        auto end_bb = llvm::BasicBlock::Create(ctx_, "l.end");
        if (op == OP_AND) {
            builder_.CreateCondBr(lv, rhs_bb, short_bb);
        } else {
            builder_.CreateCondBr(lv, short_bb, rhs_bb);
        }
        short_bb->insertInto(fn);
        builder_.SetInsertPoint(short_bb);
        builder_.CreateBr(end_bb);
        rhs_bb->insertInto(fn);
        builder_.SetInsertPoint(rhs_bb);
        auto [rt, rv] = gen_expr(rhs);
        if (rt != "i1") {
            throw TenetError::at_pos("运算符 `" + op + "` 只能作用于 bool，实际为 " + value_type_name(rt),
                                     rhs->pos);
        }
        builder_.CreateBr(end_bb);
        end_bb->insertInto(fn);
        builder_.SetInsertPoint(end_bb);
        auto phi = builder_.CreatePHI(llvm::Type::getInt1Ty(ctx_), 2);
        auto short_val = (op == OP_AND) ? llvm::ConstantInt::getFalse(ctx_) : llvm::ConstantInt::getTrue(ctx_);
        phi->addIncoming(short_val, short_bb);
        phi->addIncoming(rv, rhs_bb);
        return {"i1", phi};
    }

    std::pair<std::string, llvm::Value*> gen_arith(const std::string& op, const std::string& lt,
                                                   llvm::Value* lv, const std::string& rt, llvm::Value* rv,
                                                   const Position& pos) {
        auto is_compare = op == OP_EQ || op == OP_NEQ || op == OP_LT || op == OP_LTE || op == OP_GT || op == OP_GTE;

        // 字符串拼接 / 比较
        if (lt == "ptr" && rt == "ptr") {
            if (op == OP_ADD) {
                auto fn = mod_.getFunction("tenet_concat");
                return {"ptr", builder_.CreateCall(fn, {lv, rv})};
            }
            if (is_compare) {
                auto fn = mod_.getFunction("tenet_strcmp");
                auto c = builder_.CreateCall(fn, {lv, rv});
                auto i32 = llvm::Type::getInt32Ty(ctx_);
                auto pred = op == OP_EQ ? llvm::CmpInst::ICMP_EQ
                          : op == OP_NEQ ? llvm::CmpInst::ICMP_NE
                          : op == OP_LT  ? llvm::CmpInst::ICMP_SLT
                          : op == OP_LTE ? llvm::CmpInst::ICMP_SLE
                          : op == OP_GT  ? llvm::CmpInst::ICMP_SGT
                          :               llvm::CmpInst::ICMP_SGE;
                return {"i1", builder_.CreateICmp(pred, c, llvm::ConstantInt::get(i32, 0))};
            }
            throw TenetError::at_pos("运算符 `" + op + "` 不能作用于 string 和 string", pos);
        }

        // 字符串与任何非字符串混合 → 编译错误（不得静默按数值处理）
        if ((lt == "ptr") != (rt == "ptr")) {
            std::string s = (lt == "ptr") ? std::string(T_STR) : tenet_name(lt);
            std::string o = (lt == "ptr") ? tenet_name(rt) : std::string(T_STR);
            throw TenetError::at_pos("运算符 `" + op + "` 不能作用于 " + s + " 和 " + o, pos);
        }
        // bool 不能参与数值与比较运算
        if (lt == "i1" || rt == "i1") {
            throw TenetError::at_pos("运算符 `" + op + "` 不能作用于 " + tenet_name(lt) + " 和 " +
                                         tenet_name(rt),
                                     pos);
        }

        // 混合数值提升
        std::string lt2 = lt, rt2 = rt;
        if ((lt == "double" || rt == "double") && !(lt == "ptr" || rt == "ptr")) {
            auto dbl = llvm::Type::getDoubleTy(ctx_);
            if (lt != "double") lv = builder_.CreateSIToFP(lv, dbl);
            if (rt != "double") rv = builder_.CreateSIToFP(rv, dbl);
            lt2 = rt2 = "double";
        }

        if (is_compare) {
            llvm::CmpInst::Predicate pred;
            if (lt2 == "double") {
                pred = op == OP_EQ ? llvm::CmpInst::FCMP_OEQ
                     : op == OP_NEQ ? llvm::CmpInst::FCMP_ONE
                     : op == OP_LT  ? llvm::CmpInst::FCMP_OLT
                     : op == OP_LTE ? llvm::CmpInst::FCMP_OLE
                     : op == OP_GT  ? llvm::CmpInst::FCMP_OGT
                     :               llvm::CmpInst::FCMP_OGE;
                return {"i1", builder_.CreateFCmp(pred, lv, rv)};
            }
            pred = op == OP_EQ ? llvm::CmpInst::ICMP_EQ
                 : op == OP_NEQ ? llvm::CmpInst::ICMP_NE
                 : op == OP_LT  ? llvm::CmpInst::ICMP_SLT
                 : op == OP_LTE ? llvm::CmpInst::ICMP_SLE
                 : op == OP_GT  ? llvm::CmpInst::ICMP_SGT
                 :               llvm::CmpInst::ICMP_SGE;
            return {"i1", builder_.CreateICmp(pred, lv, rv)};
        }

        // 算术
        if (lt2 == "double") {
            if (op == OP_MOD) throw TenetError::at_pos("运算符 `%` 只能作用于 int", pos);
            auto instr = op == OP_ADD ? llvm::Instruction::FAdd
                       : op == OP_SUB ? llvm::Instruction::FSub
                       : op == OP_MUL ? llvm::Instruction::FMul
                       :               llvm::Instruction::FDiv;
            return {"double", builder_.CreateBinOp(instr, lv, rv)};
        }
        if (op == OP_MOD) return {"i64", builder_.CreateSRem(lv, rv)};
        auto instr = op == OP_ADD ? llvm::Instruction::Add
                   : op == OP_SUB ? llvm::Instruction::Sub
                   : op == OP_MUL ? llvm::Instruction::Mul
                   :               llvm::Instruction::SDiv;
        return {"i64", builder_.CreateBinOp(instr, lv, rv)};
    }

    std::pair<std::string, llvm::Value*> gen_call(const std::string& callee, const std::vector<ExprPtr>& args,
                                                  const Position& pos) {
        if (callee == "print") return gen_print(args, pos);
        if (callee == "push") {
            // S3c-1 / S3e：push(a, x) —— 目标可以是动态数组变量，也可以是 struct 的
            // 动态数组字段（`push(s.a, x)` / `push(arr[i].a, x)`）。
            if (args.size() != 2) {
                throw TenetError::at_pos("`push` 需要两个参数：数组变量和值", pos);
            }
            bool is_var = args[0]->kind == Expr::Kind::Var;
            if (is_var) {
                const VarInfo& info = lookup_var(args[0]->name, args[0]->pos);
                if (!info.dyn.has_value()) {
                    throw TenetError::at_pos(
                        "`" + args[0]->name + "` 不是动态数组，不能 push", args[0]->pos);
                }
            }
            auto dt = resolve_dyn_target(args[0]);
            if (!dt.has_value()) {
                if (is_var) throw TenetError("内部错误：动态数组变量缺少 descriptor");
                throw TenetError::at_pos("`push` 第一个参数必须是动态数组变量", args[0]->pos);
            }
            const std::string& ty = dt->first;
            const DynSlots& dslots = dt->second;
            auto elem0 = array_elem(ty);
            if (elem0.has_value() && is_array(*elem0)) {
                // v1 动态嵌套数组：push 内层变量 / 字面量 / 返回内层数组的调用；
                // 先深拷贝内层，再把 descriptor 追加到外层（stride=3，cap*2）。
                ensure_dynamic_nested_scalar_array(ty, args[0]->pos);
                push_nested_dynamic(ty, dslots, args[1]);
                return {"void", nullptr};
            }
            if (elem0.has_value() && is_struct(*elem0)) {
                // S3c-3b-2：push struct 字面量 / 同类型 struct 变量 / 返回 struct 的调用。
                push_struct_dynamic(ty, dslots, args[1]);
                return {"void", nullptr};
            }
            push_scalar_dynamic(ty, dslots, args[1]);
            return {"void", nullptr};
        }
        if (callee == "len") {
            if (args.size() != 1) {
                throw TenetError::at_pos("`len` 需要且只需要一个数组参数", pos);
            }
            if (args[0]->kind == Expr::Kind::Index && args[0]->base &&
                args[0]->base->kind == Expr::Kind::Var) {
                const VarInfo& ninfo =
                    lookup_var(args[0]->base->name, args[0]->base->pos);
                if (is_dynamic_nested_array(ninfo.ty)) {
                    // len(a[i])：先做外层越界检查，再读内层 descriptor 的 len 槽。
                    auto* row = dynamic_nested_row_desc(ninfo, args[0]->index);
                    return {"i64", builder_.CreateLoad(llvm::Type::getInt64Ty(ctx_),
                                                        desc_slot(row, 1), "nested.len")};
                }
            }
            // S3e：len(s.a) / len(arr[i].a)；len(a) 动态数组变量 / 固定数组仍走下面。
            if (args[0]->kind != Expr::Kind::Var) {
                auto dt = resolve_dyn_target(args[0]);
                if (dt.has_value()) {
                    return {"i64", builder_.CreateLoad(llvm::Type::getInt64Ty(ctx_),
                                                        dt->second.len, "dyn.len")};
                }
                throw TenetError::at_pos("`len` 参数必须是数组变量", args[0]->pos);
            }
            const VarInfo& info = lookup_var(args[0]->name, args[0]->pos);
            if (info.dyn.has_value()) {
                // S3c-1：动态数组 len 是运行时读取
                return {"i64", builder_.CreateLoad(llvm::Type::getInt64Ty(ctx_), info.dyn->len,
                                                   "dyn.len")};
            }
            if (!info.array_len.has_value()) {
                throw TenetError::at_pos("`" + args[0]->name + "` 不是数组，不能取 len",
                                         args[0]->pos);
            }
            return {"i64", llvm::ConstantInt::get(llvm::Type::getInt64Ty(ctx_),
                                                  static_cast<uint64_t>(*info.array_len))};
        }
        auto it = functions_.find(callee);
        if (it == functions_.end()) {
            throw TenetError::at_pos("未定义的函数 `" + callee + "`", pos);
        }
        const FnInfo& info = it->second;
        if (info.params.size() != args.size()) {
            throw TenetError::at_pos("函数 `" + callee + "` 需要 " + std::to_string(info.params.size()) +
                                         " 个参数，实际传入 " + std::to_string(args.size()) + " 个",
                                     pos);
        }
        std::vector<llvm::Value*> vals;
        // S3a/S3b/S3c-2 ABI：struct / 定长数组 / 动态数组返回值 → 先分配结果缓冲
        // （动态数组是 3 槽 descriptor），作为隐藏第一参数传入。
        bool ret_struct = info.ret.has_value() && is_struct(*info.ret);
        bool ret_dynamic = info.ret.has_value() && is_dynamic_array(*info.ret);
        bool ret_array = info.ret.has_value() && is_array(*info.ret) && !ret_dynamic;
        llvm::Value* sret_buf = nullptr;
        if (ret_struct) {
            sret_buf = alloc_buffer(struct_total_slots(*info.ret), callee + ".sret");
            vals.push_back(sret_buf);
        } else if (ret_dynamic) {
            sret_buf = desc_alloc(callee + ".sret");
            vals.push_back(sret_buf);
        } else if (ret_array) {
            if (is_flat_slot_array(*info.ret)) {
                // S3c-3b-3/S3c-3c v2：struct 元素 / 固定嵌套数组 → `[total x i64]` sret。
                const size_t total = fixed_array_total_slots(*info.ret);
                sret_buf = alloc_buffer(total, callee + ".sret");
                vals.push_back(sret_buf);
            } else {
                auto len = array_decl_len(*info.ret);
                if (!len.has_value()) {
                    throw TenetError("内部错误：非动态数组缺少定长长度");
                }
                std::string elem = array_elem_scalar(*info.ret, pos);
                llvm::Type* elem_ty = ty(llvm_type(elem));
                sret_buf = builder_.CreateAlloca(llvm::ArrayType::get(elem_ty, *len), nullptr,
                                                 callee + ".sret");
                vals.push_back(sret_buf);
            }
        }
        // S3c-3a / S3e：实参里的字面量 / 调用结果 / 深拷贝产生的临时缓冲区，
        // 调用返回后由调用方释放。
        std::vector<TempDyn> temp_dyn;
        std::vector<std::pair<std::string, llvm::Value*>> temp_struct;
        std::vector<std::pair<std::string, llvm::Value*>> temp_fixed;
        for (size_t i = 0; i < args.size(); ++i) {
            const std::string& pty = info.params[i];
            if (is_struct(pty)) {
                // struct 实参：字面量 / 同类型变量 / 返回 struct 的调用，打包后传指针。
                // S3e：打包时动态字段深拷贝得到独立缓冲区，调用返回后释放实参缓冲。
                auto* buf = alloc_buffer(struct_total_slots(pty),
                                         callee + ".arg" + std::to_string(i));
                pack_expr_to_buffer(pty, args[i], buf);
                if (type_owns_heap(pty)) temp_struct.emplace_back(pty, buf);
                vals.push_back(buf);
                continue;
            }
            if (is_dynamic_array(pty)) {
                // S3c-2/S3c-3a 动态数组实参：变量 / 字面量 / 返回动态数组的调用。
                // 统一传调用方栈上 3 槽 descriptor 指针；被调函数入口深拷贝（值语义）。
                // 变量保持原语义（不复制、不 drop 调用方变量）；字面量与调用结果的
                // 临时缓冲区在调用返回后由调用方 free。
                auto* desc = desc_alloc(callee + ".arg" + std::to_string(i));
                if (args[i]->kind == Expr::Kind::Var) {
                    const VarInfo& src = lookup_var(args[i]->name, args[i]->pos);
                    if (!src.dyn.has_value() || src.ty != pty) {
                        throw TenetError::at_pos(
                            "函数 `" + callee + "` 参数 " + std::to_string(i) +
                                " 类型不匹配：期望 " + pty + "，实际 " +
                                value_type_name(src.ty),
                            args[i]->pos);
                    }
                    desc_store_info(desc, src);
                } else if (args[i]->kind == Expr::Kind::Array) {
                    // 字面量：先构造临时动态数组，再写进实参 descriptor。
                    VarInfo tmp =
                        init_dynamic_array("__arg_tmp", pty, args[i], args[i]->pos);
                    desc_store_info(desc, tmp);
                    temp_dyn.push_back(TempDyn{tmp.dyn, nullptr, pty});
                } else if (args[i]->kind == Expr::Kind::Call) {
                    // 调用结果：复制其 sret descriptor，调用返回后只 free 数据。
                    auto [rt, rdesc] = gen_expr(args[i]);
                    if (rt != pty) {
                        throw TenetError::at_pos(
                            "参数类型不匹配：需要 " + pty + "，调用返回 " +
                                value_type_name(rt),
                            args[i]->pos);
                    }
                    desc_copy(desc, rdesc);
                    temp_dyn.push_back(TempDyn{std::nullopt, rdesc, pty});
                } else if (args[i]->kind == Expr::Kind::Field ||
                           args[i]->kind == Expr::Kind::Index) {
                    // S3e：struct 动态字段实参（s.a / arr[i].a）——被调函数入口深拷贝，
                    // 调用方不拥有该缓冲区，因此不登记临时释放。
                    auto dt = resolve_dyn_target(args[i]);
                    if (!dt.has_value() || dt->first != pty) {
                        throw TenetError::at_pos(
                            "动态数组实参只支持变量、字段、字面量或返回动态数组的调用",
                            args[i]->pos);
                    }
                    desc_store_slots(desc, dt->second);
                } else {
                    throw TenetError::at_pos(
                        "动态数组实参只支持变量、字面量或返回动态数组的调用",
                        args[i]->pos);
                }
                vals.push_back(desc);
                continue;
            }
            if (is_array(pty)) {
                // S3b/S3c-3b-3/S3c-3c v2 定长数组实参：按值打包成缓冲后传指针
                // （被调函数入口再逐元素 / 逐槽拷贝）。
                auto len = array_decl_len(pty);
                if (!len.has_value()) {
                    throw TenetError("内部错误：非动态数组缺少定长长度");
                }
                if (is_flat_slot_array(pty)) {
                    const size_t total = fixed_array_total_slots(pty);
                    auto* buf = alloc_buffer(total, callee + ".arg" + std::to_string(i));
                    pack_fixed_array_expr(pty, args[i], buf);
                    if (type_owns_heap(pty)) temp_fixed.emplace_back(pty, buf);
                    vals.push_back(buf);
                } else {
                    std::string elem = array_elem_scalar(pty, args[i]->pos);
                    llvm::Type* elem_ty = ty(llvm_type(elem));
                    auto* buf = builder_.CreateAlloca(
                        llvm::ArrayType::get(elem_ty, *len), nullptr,
                        callee + ".arg" + std::to_string(i));
                    pack_array_expr_to_buffer(pty, *len, args[i], buf);
                    vals.push_back(buf);
                }
                continue;
            }
            auto [t, v] = gen_expr(args[i]);
            if (t != llvm_type(pty)) {
                throw TenetError::at_pos("函数 `" + callee + "` 参数 " + std::to_string(i) +
                                             " 类型不匹配：期望 " + pty + "，实际 " +
                                             value_type_name(t),
                                         args[i]->pos);
            }
            vals.push_back(v);
        }
        auto fn = info.fn;
        auto call = builder_.CreateCall(fn, vals);
        // S3c-3a / S3e：被调函数入口已深拷贝，调用返回后释放临时实参缓冲区。
        for (auto& t : temp_dyn) {
            if (t.desc != nullptr) {
                drop_desc_owned(t.desc, t.ty);
            } else if (t.var.has_value()) {
                dyn_drop(*t.var, t.ty);
            }
        }
        for (const auto& [ty, buf] : temp_struct) {
            drop_value_slots(ty, buf);
        }
        for (const auto& [ty, buf] : temp_fixed) {
            drop_value_slots(ty, buf);
        }
        if (ret_struct || ret_array || ret_dynamic) {
            return {*info.ret, sret_buf};
        }
        if (info.ret.has_value()) {
            return {llvm_type(*info.ret), call};
        }
        return {"void", call};
    }

    // ---- print：标量 / struct / 定长与动态数组 ----
    //
    // 纯标量 print 仍用单个 printf 拼格式串（保持既有行为）；参数里出现 struct /
    // 数组变量时改为逐片段多次 printf：struct 字段、数组元素、分隔符和括号各自
    // 一个片段，避免 aggregate 展开与变参列表互相干扰。
    // aggregate 只支持直接打印变量：print(f()) / print([1, 2]) / print(a[i]) 这类
    // 表达式仍由原有表达式路径明确报错。

    /// 一次 printf 片段：fmt 是编译期字符串，args 是已经算好的变参值。
    void printf_raw(const std::string& fmt,
                    const std::vector<llvm::Value*>& args = {}) {
        auto* fmt_addr = builder_.CreateGlobalStringPtr(
            fmt, ".str.pfmt." + std::to_string(globals_str_++));
        std::vector<llvm::Value*> call_args;
        call_args.reserve(args.size() + 1);
        call_args.push_back(fmt_addr);
        call_args.insert(call_args.end(), args.begin(), args.end());
        builder_.CreateCall(mod_.getFunction("printf"), call_args);
    }

    /// 打印一个已求值的标量（LLVM 类型 i64 / double / ptr / i1）。
    void print_scalar_op(const std::string& llty, llvm::Value* v, const Position& pos) {
        if (llty == "i64") {
            printf_raw("%lld", {v});
            return;
        }
        if (llty == "double") {
            printf_raw("%g", {v});
            return;
        }
        if (llty == "ptr") {
            printf_raw("%s", {v});
            return;
        }
        if (llty == "i1") {
            auto* gtrue = builder_.CreateGlobalStringPtr(
                "true", ".str.true." + std::to_string(globals_str_++));
            auto* gfalse = builder_.CreateGlobalStringPtr(
                "false", ".str.false." + std::to_string(globals_str_++));
            printf_raw("%s", {builder_.CreateSelect(v, gtrue, gfalse)});
            return;
        }
        throw TenetError::at_pos("print 不支持该类型的值", pos);
    }

    /// 打印地址指向的标量（struct 字段 / 数组元素）。
    void print_scalar_at(const std::string& llty, llvm::Value* addr, const Position& pos) {
        auto* v = builder_.CreateLoad(ty(llty.c_str()), addr, "print.scalar");
        print_scalar_op(llty, v, pos);
    }

    /// 打印扁平 i64 槽块里的固定数组（struct 字段 / struct 元素字段）：
    /// 输出 `[1, 2, 3]` / `[P { x: 1 }]` / `[[1, 2], [3, 4]]`。
    void print_array_slots_at(const std::string& ty, llvm::Value* base,
                              const Position& pos) {
        auto elem = array_elem(ty);
        auto len = array_decl_len(ty);
        if (!elem.has_value() || !len.has_value()) {
            throw TenetError::at_pos("`" + ty + "` 不是固定数组", pos);
        }
        const size_t slots = array_elem_slots(ty);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        printf_raw("[");
        for (size_t i = 0; i < *len; ++i) {
            if (i > 0) printf_raw(", ");
            auto* item = builder_.CreateGEP(
                i64, base,
                {llvm::ConstantInt::get(i64, static_cast<uint64_t>(i * slots))},
                "print.arr");
            if (is_struct(*elem)) {
                print_struct_at(*elem, item, pos);
            } else if (is_array(*elem)) {
                print_array_slots_at(*elem, item, pos);
            } else {
                auto* raw = builder_.CreateLoad(i64, item, "print.raw");
                print_scalar_op(llvm_type(*elem), unpack_scalar(*elem, raw), pos);
            }
        }
        printf_raw("]");
    }

    /// struct 变量：按扁平字段顺序打印 `P { x: 1, y: 2 }`；嵌套字段用点分路径
    /// （`Q { p.x: 1, p.y: 2, z: 3 }`）；固定数组字段展开成 `a: [..]`。
    void print_struct_var(const VarInfo& info, const Position& pos) {
        auto flat = layout_of(info.ty);
        printf_raw(info.ty + " { ");
        for (size_t i = 0; i < flat.size(); ++i) {
            if (i > 0) printf_raw(", ");
            printf_raw(flat[i].path + ": ");
            if (is_dynamic_array(flat[i].ty)) {
                auto d = info.dyn_fields.find(flat[i].path);
                if (d == info.dyn_fields.end()) {
                    throw TenetError("内部错误：struct `" + info.ty +
                                     "` 缺少动态字段槽 `" + flat[i].path + "`");
                }
                print_dyn_slots(flat[i].ty, dyn_slots_of(d->second), pos);
                continue;
            }
            auto f = info.fields.find(flat[i].path);
            if (f == info.fields.end()) {
                throw TenetError("内部错误：struct `" + info.ty + "` 缺少字段槽 `" +
                                 flat[i].path + "`");
            }
            if (is_array(flat[i].ty)) {
                print_array_slots_at(flat[i].ty, f->second.second, pos);
            } else {
                print_scalar_at(llvm_type(flat[i].ty), f->second.second, pos);
            }
        }
        printf_raw(" }");
    }

    /// struct 元素（数组里按 8 字节槽扁平存放）：字段位于 base + 8*offset，
    /// 标量读出 i64 后按字段类型 unpack，固定数组字段整块展开。
    void print_struct_at(const std::string& struct_ty, llvm::Value* base,
                         const Position& pos) {
        auto flat = layout_of(struct_ty);
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        printf_raw(struct_ty + " { ");
        for (size_t i = 0; i < flat.size(); ++i) {
            if (i > 0) printf_raw(", ");
            printf_raw(flat[i].path + ": ");
            auto* addr = builder_.CreateGEP(
                i64, base,
                {llvm::ConstantInt::get(i64, static_cast<uint64_t>(flat[i].offset))},
                "print.field");
            if (is_dynamic_array(flat[i].ty)) {
                // S3e：ABI buffer / 数组元素里的动态字段是连续 3 个 descriptor 槽。
                print_dyn_slots(flat[i].ty, dyn_slots_at(addr), pos);
                continue;
            }
            if (is_array(flat[i].ty)) {
                print_array_slots_at(flat[i].ty, addr, pos);
                continue;
            }
            auto* raw = builder_.CreateLoad(i64, addr, "print.raw");
            print_scalar_op(llvm_type(flat[i].ty), unpack_scalar(flat[i].ty, raw), pos);
        }
        printf_raw(" }");
    }

    /// v1 动态嵌套数组的一行：内层 descriptor 已定位到槽位，输出 `[1, 2]`。
    void print_dynamic_nested_row(const std::string& inner_ty, llvm::Value* row,
                                  const Position& pos) {
        auto scalar = array_elem(inner_ty);
        if (!scalar.has_value()) {
            throw TenetError::at_pos("内层不是数组", pos);
        }
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        auto* data = builder_.CreateLoad(ptr_ty(ctx_), desc_slot(row, 0), "pnr.data");
        auto* len = builder_.CreateLoad(i64, desc_slot(row, 1), "pnr.len");
        printf_raw("[");
        auto* idx_slot = builder_.CreateAlloca(i64, nullptr, "pnr.i");
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), idx_slot);
        auto* cond_bb = llvm::BasicBlock::Create(ctx_, "pnr.cond");
        auto* body_bb = llvm::BasicBlock::Create(ctx_, "pnr.body");
        auto* sep_bb = llvm::BasicBlock::Create(ctx_, "pnr.sep");
        auto* after_bb = llvm::BasicBlock::Create(ctx_, "pnr.after");
        auto* end_bb = llvm::BasicBlock::Create(ctx_, "pnr.end");
        auto* fn = builder_.GetInsertBlock()->getParent();
        builder_.CreateBr(cond_bb);
        cond_bb->insertInto(fn);
        builder_.SetInsertPoint(cond_bb);
        auto* iv = builder_.CreateLoad(i64, idx_slot, "pnr.idx");
        auto* cmp = builder_.CreateICmpSLT(iv, len, "pnr.cmp");
        builder_.CreateCondBr(cmp, body_bb, end_bb);
        body_bb->insertInto(fn);
        builder_.SetInsertPoint(body_bb);
        auto* iv_body = builder_.CreateLoad(i64, idx_slot, "pnr.idx");
        auto* nz =
            builder_.CreateICmpSGT(iv_body, llvm::ConstantInt::get(i64, 0), "pnr.nz");
        builder_.CreateCondBr(nz, sep_bb, after_bb);
        sep_bb->insertInto(fn);
        builder_.SetInsertPoint(sep_bb);
        printf_raw(", ");
        builder_.CreateBr(after_bb);
        after_bb->insertInto(fn);
        builder_.SetInsertPoint(after_bb);
        auto* iv_elem = builder_.CreateLoad(i64, idx_slot, "pnr.idx");
        auto* slot = dyn_slot(data, iv_elem);
        auto* raw = builder_.CreateLoad(i64, slot, "pnr.raw");
        print_scalar_op(llvm_type(*scalar), unpack_scalar(*scalar, raw), pos);
        auto* next = builder_.CreateAdd(iv_elem, llvm::ConstantInt::get(i64, 1), "pnr.next");
        builder_.CreateStore(next, idx_slot);
        builder_.CreateBr(cond_bb);
        end_bb->insertInto(fn);
        builder_.SetInsertPoint(end_bb);
        printf_raw("]");
    }

    /// 动态数组：运行时循环，索引存栈槽；标量元素按 1 槽、struct 元素按 slots 槽
    /// 从堆缓冲区定位。v1 动态嵌套数组的外层元素是内层 descriptor（3 槽），
    /// 逐行打印成 `[[1, 2], [3]]`。空数组输出 `[]`。
    /// S3e：descriptor 用 DynSlots，局部数组与 struct 动态字段共用。
    void print_dynamic_array(const std::string& arr_ty, const DynSlots& dslots,
                             const std::string& elem, const Position& pos) {
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        printf_raw("[");
        auto* idx_slot = builder_.CreateAlloca(i64, nullptr, "print.i");
        builder_.CreateStore(llvm::ConstantInt::get(i64, 0), idx_slot);
        auto* cond_bb = llvm::BasicBlock::Create(ctx_, "pr.cond");
        auto* body_bb = llvm::BasicBlock::Create(ctx_, "pr.body");
        auto* sep_bb = llvm::BasicBlock::Create(ctx_, "pr.sep");
        auto* after_bb = llvm::BasicBlock::Create(ctx_, "pr.after");
        auto* end_bb = llvm::BasicBlock::Create(ctx_, "pr.end");
        auto* fn = builder_.GetInsertBlock()->getParent();
        builder_.CreateBr(cond_bb);
        cond_bb->insertInto(fn);
        builder_.SetInsertPoint(cond_bb);
        auto* iv = builder_.CreateLoad(i64, idx_slot, "print.idx");
        auto* len = builder_.CreateLoad(i64, dslots.len, "print.len");
        auto* cmp = builder_.CreateICmpSLT(iv, len, "print.cmp");
        builder_.CreateCondBr(cmp, body_bb, end_bb);
        body_bb->insertInto(fn);
        builder_.SetInsertPoint(body_bb);
        auto* iv_body = builder_.CreateLoad(i64, idx_slot, "print.idx");
        auto* nz = builder_.CreateICmpSGT(iv_body, llvm::ConstantInt::get(i64, 0),
                                          "print.nz");
        builder_.CreateCondBr(nz, sep_bb, after_bb);
        sep_bb->insertInto(fn);
        builder_.SetInsertPoint(sep_bb);
        printf_raw(", ");
        builder_.CreateBr(after_bb);
        after_bb->insertInto(fn);
        builder_.SetInsertPoint(after_bb);
        auto* iv_elem = builder_.CreateLoad(i64, idx_slot, "print.idx");
        auto* data = builder_.CreateLoad(ptr_ty(ctx_), dslots.data, "print.data");
        if (is_array(elem)) {
            // v1 动态嵌套数组：外层元素是内层 descriptor，stride = 3 槽。
            auto* row = builder_.CreateMul(iv_elem, llvm::ConstantInt::get(i64, 3),
                                           "print.row");
            print_dynamic_nested_row(elem, dyn_slot(data, row), pos);
        } else if (is_struct(elem)) {
            const size_t slots = array_elem_slots(arr_ty);
            auto* row = builder_.CreateMul(
                iv_elem, llvm::ConstantInt::get(i64, static_cast<uint64_t>(slots)),
                "print.row");
            print_struct_at(elem, dyn_slot(data, row), pos);
        } else {
            auto* slot = dyn_slot(data, iv_elem);
            auto* raw = builder_.CreateLoad(i64, slot, "print.raw");
            print_scalar_op(llvm_type(elem), unpack_scalar(elem, raw), pos);
        }
        auto* next =
            builder_.CreateAdd(iv_elem, llvm::ConstantInt::get(i64, 1), "print.next");
        builder_.CreateStore(next, idx_slot);
        builder_.CreateBr(cond_bb);
        end_bb->insertInto(fn);
        builder_.SetInsertPoint(end_bb);
        printf_raw("]");
    }

    /// S3e：打印一个动态数组 descriptor（struct 字段 / `print(s.a)` 用）。
    void print_dyn_slots(const std::string& ty, const DynSlots& dslots,
                         const Position& pos) {
        auto elem = array_elem(ty);
        if (!elem.has_value()) {
            throw TenetError::at_pos("`" + ty + "` 不是数组", pos);
        }
        print_dynamic_array(ty, dslots, *elem, pos);
    }

    /// 数组变量：定长标量 / 定长 struct / 定长嵌套 / 动态数组。
    void print_array_info(const VarInfo& info, const Position& pos) {
        auto elem = array_elem(info.ty);
        if (!elem.has_value()) {
            throw TenetError("内部错误：`" + info.ty + "` 不是数组");
        }
        if (info.dyn.has_value()) {
            print_dynamic_array(info.ty, dyn_slots_of(*info.dyn), *elem, pos);
            return;
        }
        if (!info.array_len.has_value() || info.addr == nullptr) {
            throw TenetError("内部错误：固定数组变量缺少扁平缓冲");
        }
        const size_t len = *info.array_len;
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        if (is_struct(*elem)) {
            const size_t slots = array_elem_slots(info.ty);
            printf_raw("[");
            for (size_t k = 0; k < len; ++k) {
                if (k > 0) printf_raw(", ");
                auto* base = array_addr(
                    info.addr, len * slots,
                    llvm::ConstantInt::get(i64, static_cast<uint64_t>(k * slots)), i64);
                print_struct_at(*elem, base, pos);
            }
            printf_raw("]");
            return;
        }
        if (is_array(*elem)) {
            auto inner_len = array_decl_len(*elem);
            auto inner_elem = array_elem(*elem);
            if (!inner_len.has_value() || !inner_elem.has_value()) {
                throw TenetError::at_pos("嵌套数组内层必须是固定长度 array<T, N>", pos);
            }
            const size_t slots = array_elem_slots(info.ty);
            printf_raw("[");
            for (size_t k = 0; k < len; ++k) {
                if (k > 0) printf_raw(", ");
                printf_raw("[");
                for (size_t j = 0; j < *inner_len; ++j) {
                    if (j > 0) printf_raw(", ");
                    auto* addr = array_addr(
                        info.addr, len * slots,
                        llvm::ConstantInt::get(i64, static_cast<uint64_t>(k * slots + j)),
                        i64);
                    auto* raw = builder_.CreateLoad(i64, addr, "print.raw");
                    print_scalar_op(llvm_type(*inner_elem),
                                    unpack_scalar(*inner_elem, raw), pos);
                }
                printf_raw("]");
            }
            printf_raw("]");
            return;
        }
        const std::string elem_ll = llvm_type(*elem);
        llvm::Type* elem_ty = ty(elem_ll.c_str());
        printf_raw("[");
        for (size_t k = 0; k < len; ++k) {
            if (k > 0) printf_raw(", ");
            auto* addr = array_addr(
                info.addr, len,
                llvm::ConstantInt::get(i64, static_cast<uint64_t>(k)), elem_ty);
            print_scalar_at(elem_ll, addr, pos);
        }
        printf_raw("]");
    }

    /// aggregate 变量分派：struct / 数组（含动态、struct 元素、嵌套定长）。
    void print_aggregate_var(const VarInfo& info, const Position& pos) {
        if (is_struct(info.ty)) {
            print_struct_var(info, pos);
            return;
        }
        if (is_array(info.ty)) {
            print_array_info(info, pos);
            return;
        }
        throw TenetError::at_pos("print 不支持该类型的值", pos);
    }

    /// print(a, b, ...) → 纯标量沿用单次 printf；出现 aggregate 变量 / 数组字段时
    /// 逐片段打印。
    std::pair<std::string, llvm::Value*> gen_print(const std::vector<ExprPtr>& args,
                                                   const Position& pos) {
        bool has_aggregate = false;
        for (const auto& a : args) {
            if (a->kind == Expr::Kind::Var) {
                const VarInfo& info = lookup_var(a->name, a->pos);
                if (is_struct(info.ty) || is_array(info.ty)) {
                    has_aggregate = true;
                    break;
                }
                continue;
            }
            // S3e：print(s.a) / print(arr[i].a) / print(s.arr) 这类数组字段链。
            // 只处理顶层是字段访问的形式：print(a[0]) 之类仍走既有表达式错误路径。
            if (a->kind == Expr::Kind::Field) {
                auto chain = infer_chain_type(a);
                if (chain.has_value() && is_dynamic_array(*chain)) {
                    has_aggregate = true;
                    break;
                }
            }
        }
        if (!has_aggregate) return gen_print_scalars(args, pos);
        return gen_print_multi(args, pos);
    }

    /// 纯标量 print：编译期拼一个格式串，只调用一次 printf（既有行为）。
    std::pair<std::string, llvm::Value*> gen_print_scalars(
        const std::vector<ExprPtr>& args, const Position& pos) {
        std::string fmt;
        std::vector<llvm::Value*> vals;
        for (size_t i = 0; i < args.size(); ++i) {
            if (i > 0) fmt.push_back(' ');
            auto [t, v] = gen_expr(args[i]);
            if (is_struct(t)) {
                throw TenetError::at_pos(
                    "print 不支持 struct `" + t + "`，请打印标量字段", args[i]->pos);
            }
            if (t == "i64") {
                fmt += "%lld";
                vals.push_back(v);
            } else if (t == "double") {
                fmt += "%g";
                vals.push_back(v);
            } else if (t == "ptr") {
                fmt += "%s";
                vals.push_back(v);
            } else if (t == "i1") {
                fmt += "%s";
                auto gtrue = builder_.CreateGlobalStringPtr("true", ".str.true");
                auto gfalse = builder_.CreateGlobalStringPtr("false", ".str.false");
                vals.push_back(builder_.CreateSelect(v, gtrue, gfalse));
            } else {
                throw TenetError::at_pos("print 不支持该类型的值", pos);
            }
        }
        fmt.push_back('\n');
        auto fmt_addr = builder_.CreateGlobalStringPtr(
            fmt, ".str.fmt." + std::to_string(globals_str_++));
        std::vector<llvm::Value*> call_args;
        call_args.push_back(fmt_addr);
        call_args.insert(call_args.end(), vals.begin(), vals.end());
        auto printf_fn = mod_.getFunction("printf");
        auto call = builder_.CreateCall(printf_fn, call_args);
        return {"void", call};
    }

    /// aggregate print：每个片段一次 printf；参数之间一个空格、结尾换行。
    std::pair<std::string, llvm::Value*> gen_print_multi(
        const std::vector<ExprPtr>& args, const Position& pos) {
        (void)pos;
        for (size_t i = 0; i < args.size(); ++i) {
            if (i > 0) printf_raw(" ");
            if (args[i]->kind == Expr::Kind::Var) {
                const VarInfo& info = lookup_var(args[i]->name, args[i]->pos);
                if (is_struct(info.ty) || is_array(info.ty)) {
                    print_aggregate_var(info, args[i]->pos);
                    continue;
                }
            } else if (args[i]->kind == Expr::Kind::Field) {
                // S3e：动态数组字段（`print(s.a)` / `print(arr[i].a)`）按 descriptor 打印。
                auto chain = infer_chain_type(args[i]);
                if (chain.has_value() && is_dynamic_array(*chain)) {
                    auto dt = resolve_dyn_target(args[i]);
                    if (dt.has_value()) {
                        print_dyn_slots(dt->first, dt->second, args[i]->pos);
                        continue;
                    }
                    auto place = resolve_place(args[i]);
                    if (place.has_value() && place->kind == Place::Kind::Array) {
                        print_array_slots_at(place->ty, place->addr, args[i]->pos);
                        continue;
                    }
                    throw TenetError::at_pos(
                        "print 不支持该数组字段表达式；请打印数组变量", args[i]->pos);
                }
            }
            auto [t, v] = gen_expr(args[i]);
            if (is_struct(t)) {
                throw TenetError::at_pos(
                    "print 不支持 struct `" + t + "`，请打印标量字段", args[i]->pos);
            }
            print_scalar_op(t, v, args[i]->pos);
        }
        printf_raw("\n");
        return {"void", nullptr};
    }

    // ---- 类型推断（与求值规则一致）----

    /// 仅按语法链推断类型（Var / Field / Index），用于 `s.a[i].x` 这类
    /// 数组字段左值链；不生成 IR，也不要求中间值可取。
    std::optional<std::string> infer_chain_type(const ExprPtr& e) {
        if (!e) return std::nullopt;
        if (e->kind == Expr::Kind::Var) return lookup_var(e->name, e->pos).ty;
        if (e->kind == Expr::Kind::Field) {
            auto base = infer_chain_type(e->base);
            if (!base.has_value() || !is_struct(*base)) return std::nullopt;
            return direct_field_type(*base, e->field, e->pos);
        }
        if (e->kind == Expr::Kind::Index) {
            auto base = infer_chain_type(e->base);
            if (!base.has_value()) return std::nullopt;
            auto elem = array_elem(*base);
            if (!elem.has_value()) return std::nullopt;
            return *elem;
        }
        return std::nullopt;
    }

    std::optional<std::string> infer_type(const ExprPtr& e) {
        switch (e->kind) {
            case Expr::Kind::Int: return T_INT;
            case Expr::Kind::Float: return T_FLOAT;
            case Expr::Kind::Str: return T_STR;
            case Expr::Kind::Bool: return T_BOOL;
            case Expr::Kind::Var:
                return lookup_var(e->name, e->pos).ty;
            case Expr::Kind::Index: {
                auto bt = infer_type(e->base);
                if (!bt.has_value()) {
                    throw TenetError::at_pos("无法推断数组类型", e->base->pos);
                }
                auto elem = array_elem(*bt);
                if (!elem.has_value()) {
                    throw TenetError::at_pos("`" + *bt + "` 不是数组", e->base->pos);
                }
                if (is_struct(*elem)) {
                    // S3c-3b-1/S3c-3b-2：数组元素整体读取为 struct 值仍未开放。
                    throw TenetError::at_pos(
                        "不支持整体读取 array<struct> 元素；请访问标量字段", e->pos);
                }
                auto it = infer_type(e->index);
                if (it.has_value() && *it != T_INT) {
                    throw TenetError::at_pos("数组下标必须是 int，实际为 " + *it, e->index->pos);
                }
                return *elem;
            }
            case Expr::Kind::Field: {
                std::vector<std::string> ipath;
                std::string arr_name;
                ExprPtr arr_index;
                if (struct_index_fields(e, ipath, arr_name, arr_index)) {
                    const std::string path = join_path(ipath);
                    const VarInfo& info = lookup_var(arr_name, e->base->pos);
                    auto elem = array_elem(info.ty);
                    if (!elem.has_value() || !is_struct(*elem)) {
                        throw TenetError::at_pos("`" + arr_name + "` 不是 struct 数组",
                                                 e->base->pos);
                    }
                    std::string fty = field_type_of(*elem, path, e->pos);
                    if (is_struct(fty)) {
                        throw TenetError::at_pos(
                            "字段 `" + path + "` 是 struct `" + fty +
                                "`，请继续访问到标量字段",
                            e->pos);
                    }
                    return fty;
                }
                auto vp = expr_var_path(e->base);
                if (!vp.has_value()) {
                    auto chain = infer_chain_type(e);
                    if (chain.has_value()) {
                        if (is_struct(*chain)) {
                            throw TenetError::at_pos(
                                "struct 值不能直接取值；请继续访问到标量字段", e->pos);
                        }
                        return *chain;
                    }
                    throw TenetError::at_pos("v1 只支持对 struct 变量取字段", e->base->pos);
                }
                const std::string& name = vp->first;
                std::string path =
                    vp->second.empty() ? e->field : vp->second + "." + e->field;
                const VarInfo& info = lookup_var(name, e->base->pos);
                if (!is_struct(info.ty)) {
                    throw TenetError::at_pos("`" + name + "` 不是 struct", e->base->pos);
                }
                std::string fty = field_type_of(info.ty, path, e->pos);
                if (is_struct(fty)) {
                    throw TenetError::at_pos(
                        "字段 `" + path + "` 是 struct `" + fty + "`，请继续访问到标量字段",
                        e->pos);
                }
                return fty;
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
                        "数组元素只支持 int/float/bool、struct 或固定 array<T, N>，实际 `" +
                            *first + "`",
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
                // S3b：字面量推断为定长 `array<T, N>`，长度是类型的一部分。
                return "array<" + *first + "," + std::to_string(e->args.size()) + ">";
            }
            case Expr::Kind::StructLit:
                struct_fields(e->name, e->pos);
                return e->name;
            case Expr::Kind::Assign: {
                const ExprPtr& target = e->lhs;
                if (target->kind == Expr::Kind::Var) {
                    return lookup_var(target->name, target->pos).ty;
                }
                if (target->kind == Expr::Kind::Index) {
                    auto bt = infer_type(target->base);
                    if (!bt.has_value()) {
                        throw TenetError::at_pos("无法推断数组类型", target->base->pos);
                    }
                    auto elem = array_elem(*bt);
                    if (!elem.has_value()) {
                        throw TenetError::at_pos("`" + *bt + "` 不是数组", target->base->pos);
                    }
                    return *elem;
                }
                if (target->kind == Expr::Kind::Field) {
                    auto vp = expr_var_path(target->base);
                    if (!vp.has_value()) {
                        throw TenetError::at_pos("v1 只支持对 struct 变量取字段",
                                                 target->base->pos);
                    }
                    std::string path = vp->second.empty()
                                           ? target->field
                                           : vp->second + "." + target->field;
                    const VarInfo& info = lookup_var(vp->first, target->base->pos);
                    std::string fty = field_type_of(info.ty, path, target->pos);
                    if (is_struct(fty)) {
                        throw TenetError::at_pos(
                            "字段 `" + path + "` 是 struct `" + fty +
                                "`，请继续访问到标量字段",
                            target->pos);
                    }
                    return fty;
                }
                throw TenetError::at_pos("赋值左侧必须是变量或字段", target->pos);
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
                    if (!array_elem(*t).has_value()) {
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
