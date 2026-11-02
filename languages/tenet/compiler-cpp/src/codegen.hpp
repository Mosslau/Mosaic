// LLVM 代码生成器：AST → LLVM IR（进程内构建，调用 LLVM C++ API）。
//
// 与 compiler-rs（生成 .ll 文本 + clang 驱动）的关键差异：
// - 用 IRBuilder 在内存中构建 IR（不是写文本文件）
// - 变量用 alloca + load/store；控制流用基本块 + br
// - 后端（IR → 机器码）由 LLVM 库进程内完成（rustc 方式），
//   不再调用 clang 解析文本
#pragma once

#include <limits>
#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
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

/// 变量信息。struct 变量不占一个聚合槽，而是扁平化成字段槽位（v1 局部变量方案）：
/// 每个字段一个独立 alloca，`addr == nullptr` 表示这是一个 struct 变量。
struct VarInfo {
    std::string ty;
    llvm::AllocaInst* addr = nullptr;
    std::unordered_map<std::string, std::pair<std::string, llvm::AllocaInst*>> fields;
    /// 数组变量的定长长度；非数组为 nullopt。
    std::optional<size_t> array_len;
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
    // 顶层 struct 名 → 字段 (名, 标量类型)
    std::unordered_map<std::string, std::vector<std::pair<std::string, std::string>>> structs_;
    // 函数表：name -> FnInfo（Function + 参数/返回类型）
    std::unordered_map<std::string, FnInfo> functions_;
    // 当前函数上下文（返回类型核对用）
    std::string current_fn_;
    std::optional<std::string> current_ret_;
    // break 目标栈
    std::vector<llvm::BasicBlock*> break_stack_;

    llvm::Type* ty(const char* t) {
        if (std::string(t) == "i64") return llvm::Type::getInt64Ty(ctx_);
        if (std::string(t) == "double") return llvm::Type::getDoubleTy(ctx_);
        if (std::string(t) == "i1") return llvm::Type::getInt1Ty(ctx_);
        return llvm::PointerType::getUnqual(ctx_);
    }

    // ---- struct 预处理 ----

    /// 收集并校验顶层 struct 声明（字段仅 int/float/bool、字段名唯一、不与标量重名）。
    void collect_structs(const Program& program) {
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
                if (fty != T_INT && fty != T_FLOAT && fty != T_BOOL) {
                    throw TenetError::at_pos(
                        "struct `" + name + "` 的字段 `" + fname + "` 只支持 int/float/bool",
                        stmt->pos);
                }
                if (seen.count(fname)) {
                    throw TenetError::at_pos("struct `" + name + "` 的字段 `" + fname + "` 重复",
                                             stmt->pos);
                }
                seen[fname] = true;
            }
            structs_[name] = stmt->fields;
        }
    }

    bool is_struct(const std::string& t) const { return structs_.count(t) != 0; }

    static bool is_scalar(const std::string& t) {
        return t == T_INT || t == T_FLOAT || t == T_BOOL || t == T_STR;
    }

    /// 解析 `array<T>`，返回 T；不是数组类型返回 nullopt。
    static std::optional<std::string> array_elem(const std::string& t) {
        static const std::string prefix = "array<";
        if (t.size() <= prefix.size() + 1 || t.compare(0, prefix.size(), prefix) != 0 ||
            t.back() != '>') {
            return std::nullopt;
        }
        return t.substr(prefix.size(), t.size() - prefix.size() - 1);
    }

    static bool is_array(const std::string& t) { return array_elem(t).has_value(); }

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

    std::vector<std::pair<std::string, std::string>> struct_fields(const std::string& t,
                                                                   const Position& pos) const {
        auto it = structs_.find(t);
        if (it == structs_.end()) {
            throw TenetError::at_pos("未定义的 struct `" + t + "`", pos);
        }
        return it->second;
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

        // 用户函数（先创建 Function 对象，供调用解析）
        for (const auto& stmt : program.stmts) {
            if (stmt->kind != Stmt::Kind::FnDecl) continue;
            const auto& name = stmt->name;
            if (name == "main" || name == "printf" || name == "tenet_concat" ||
                name == "tenet_strcmp" || name == "tenet_bounds_fail") {
                throw TenetError::at_pos("函数名 `" + name + "` 为编译器保留", stmt->pos);
            }
            if (functions_.count(name)) {
                throw TenetError::at_pos("函数 `" + name + "` 重复定义", stmt->pos);
            }
            std::vector<llvm::Type*> params;
            std::vector<std::string> param_tys;
            for (const auto& [pname, pt] : stmt->params) {
                if (is_struct(pt)) {
                    throw TenetError::at_pos("v1 不支持 struct 参数：`" + name + "` 的参数 `" +
                                                 pname + "` 是 `" + pt + "`",
                                             stmt->pos);
                }
                if (is_array(pt)) {
                    throw TenetError::at_pos("v1 不支持 array 参数：`" + name + "` 的参数 `" +
                                                 pname + "` 是 `" + pt + "`",
                                             stmt->pos);
                }
                ensure_known_type(pt, stmt->pos);
                params.push_back(ty(llvm_type(pt)));
                param_tys.push_back(pt);
            }
            if (stmt->ret.has_value()) {
                if (is_struct(*stmt->ret)) {
                    throw TenetError::at_pos("v1 不支持 struct 返回值：`" + name + "` 返回 `" +
                                                 *stmt->ret + "`",
                                             stmt->pos);
                }
                if (is_array(*stmt->ret)) {
                    throw TenetError::at_pos("v1 不支持 array 返回值：`" + name + "` 返回 `" +
                                                 *stmt->ret + "`",
                                             stmt->pos);
                }
                ensure_known_type(*stmt->ret, stmt->pos);
            }
            auto ret_ll = stmt->ret.has_value() ? ty(llvm_type(*stmt->ret)) : llvm::Type::getVoidTy(ctx_);
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
        }
        current_fn_.clear();
        current_ret_ = std::nullopt;
        if (!builder_.GetInsertBlock()->getTerminator()) builder_.CreateRet(llvm::ConstantInt::get(ctx_, llvm::APInt(32, 0)));
        symbols_.pop_back();

        // 用户函数体
        for (const auto& stmt : program.stmts) {
            if (stmt->kind != Stmt::Kind::FnDecl) continue;
            emit_fn_body(stmt);
        }
    }

    void emit_fn_body(const StmtPtr& stmt) {
        const auto& name = stmt->name;
        if (stmt->ret.has_value() && !stmt->body.empty() &&
            stmt->body.back()->kind != Stmt::Kind::Return) {
            throw TenetError::at_pos("函数 `" + name + "` 声明了返回类型，但函数末尾没有 return",
                                     stmt->pos);
        }
        auto fn = functions_[name].fn;
        current_fn_ = name;
        current_ret_ = stmt->ret;
        auto entry = llvm::BasicBlock::Create(ctx_, "entry", fn);
        builder_.SetInsertPoint(entry);
        symbols_.emplace_back();
        unsigned i = 0;
        for (auto& arg : fn->args()) {
            const auto& [pname, pty] = stmt->params[i];
            auto addr = builder_.CreateAlloca(arg.getType(), nullptr, pname);
            builder_.CreateStore(&arg, addr);
            symbols_.back()[pname] = {pty, llvm::cast<llvm::AllocaInst>(addr), {}};
            ++i;
        }
        for (const auto& s : stmt->body) emit_stmt(s);
        symbols_.pop_back();
        current_fn_.clear();
        current_ret_ = std::nullopt;
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
                        "`" + stmt->name + "` 初始化类型不匹配：标注 " + t + "，实际 " + tenet_name(vt),
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
                    throw TenetError::at_pos("条件表达式需要 bool，实际为 " + std::string(tenet_name(ct)),
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
                for (const auto& s : stmt->then_branch) emit_stmt(s);
                symbols_.pop_back();
                if (!builder_.GetInsertBlock()->getTerminator()) builder_.CreateBr(merge_bb);

                else_bb->insertInto(fn);
                builder_.SetInsertPoint(else_bb);
                if (!stmt->else_branch.empty()) {
                    symbols_.emplace_back();
                    for (const auto& s : stmt->else_branch) emit_stmt(s);
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
                    throw TenetError::at_pos("条件表达式需要 bool，实际为 " + std::string(tenet_name(ct)),
                                             stmt->cond->pos);
                }
                builder_.CreateCondBr(c, body_bb, exit_bb);

                body_bb->insertInto(fn);
                builder_.SetInsertPoint(body_bb);
                symbols_.emplace_back();
                break_stack_.push_back(exit_bb);
                for (const auto& s : stmt->body) emit_stmt(s);
                break_stack_.pop_back();
                symbols_.pop_back();
                if (!builder_.GetInsertBlock()->getTerminator()) builder_.CreateBr(cond_bb);

                exit_bb->insertInto(fn);
                builder_.SetInsertPoint(exit_bb);
                return;
            }
            case Stmt::Kind::Return: {
                if (stmt->expr) {
                    auto [t, v] = gen_expr(stmt->expr);
                    if (!current_ret_.has_value()) {
                        throw TenetError::at_pos("函数 `" + current_fn_ + "` 没有返回类型，不能 return 值",
                                                 stmt->expr->pos);
                    }
                    if (is_struct(t)) {
                        throw TenetError::at_pos(
                            "v1 不支持 struct 返回值：`" + current_fn_ + "` 返回 `" + t + "`",
                            stmt->expr->pos);
                    }
                    if (std::string(tenet_name(t)) != *current_ret_) {
                        throw TenetError::at_pos(
                            "函数 `" + current_fn_ + "` 返回类型不匹配：声明 " + *current_ret_ +
                                "，实际 " + tenet_name(t),
                            stmt->expr->pos);
                    }
                    builder_.CreateRet(v);
                } else {
                    builder_.CreateRetVoid();
                }
                return;
            }
            case Stmt::Kind::Break: {
                if (break_stack_.empty()) {
                    throw TenetError::at_pos("`break` 出现在循环之外", stmt->pos);
                }
                builder_.CreateBr(break_stack_.back());
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
                if (base->kind != Expr::Kind::Var) {
                    throw TenetError::at_pos("v1 只支持对数组变量取下标", base->pos);
                }
                const VarInfo& info = lookup_var(base->name, base->pos);
                auto elem = array_elem(info.ty);
                if (!elem.has_value()) {
                    throw TenetError::at_pos("`" + base->name + "` 不是数组，不能取下标",
                                             base->pos);
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
                const ExprPtr& base = e->base;
                if (base->kind != Expr::Kind::Var) {
                    throw TenetError::at_pos("v1 只支持对 struct 变量取字段（不支持嵌套字段链）",
                                             base->pos);
                }
                const VarInfo& info = lookup_var(base->name, base->pos);
                if (!is_struct(info.ty)) {
                    throw TenetError::at_pos(
                        "`" + base->name + "` 不是 struct，不能取字段 `" + e->field + "`",
                        base->pos);
                }
                auto f = info.fields.find(e->field);
                if (f == info.fields.end()) {
                    throw TenetError::at_pos("struct `" + info.ty + "` 没有字段 `" + e->field + "`",
                                             e->pos);
                }
                const auto& [fty, addr] = f->second;
                return {llvm_type(fty), builder_.CreateLoad(ty(llvm_type(fty)), addr, e->field)};
            }
            case Expr::Kind::Array:
                throw TenetError::at_pos("数组字面量只能用于 let 初始化或整体赋值", e->pos);
            case Expr::Kind::StructLit:
                throw TenetError::at_pos("struct 字面量只能用于 let 初始化或整体赋值", e->pos);
            case Expr::Kind::Assign: {
                const ExprPtr& target = e->lhs;
                if (target->kind == Expr::Kind::Var) {
                    const VarInfo& info = lookup_var(target->name, target->pos);
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
                                tenet_name(vt),
                            e->pos);
                    }
                    builder_.CreateStore(v, info.addr);
                    return {vt, v};
                }
                if (target->kind == Expr::Kind::Field) {
                    const ExprPtr& base = target->base;
                    if (base->kind != Expr::Kind::Var) {
                        throw TenetError::at_pos("v1 只支持对 struct 变量写字段", base->pos);
                    }
                    const VarInfo& info = lookup_var(base->name, base->pos);
                    if (!is_struct(info.ty)) {
                        throw TenetError::at_pos(
                            "`" + base->name + "` 不是 struct，不能写字段 `" + target->field + "`",
                            base->pos);
                    }
                    auto f = info.fields.find(target->field);
                    if (f == info.fields.end()) {
                        throw TenetError::at_pos(
                            "struct `" + info.ty + "` 没有字段 `" + target->field + "`",
                            target->pos);
                    }
                    const auto& [fty, addr] = f->second;
                    auto [vt, v] = gen_expr(e->value);
                    if (vt != llvm_type(fty)) {
                        throw TenetError::at_pos(
                            "字段 `" + target->field + "` 类型不匹配：需要 " + fty + "，实际 " +
                                tenet_name(vt),
                            e->value->pos);
                    }
                    builder_.CreateStore(v, addr);
                    return {vt, v};
                }
                if (target->kind == Expr::Kind::Index) {
                    const ExprPtr& base = target->base;
                    if (base->kind != Expr::Kind::Var) {
                        throw TenetError::at_pos("v1 只支持对数组变量写下标", base->pos);
                    }
                    const VarInfo& info = lookup_var(base->name, base->pos);
                    auto elem = array_elem(info.ty);
                    if (!elem.has_value()) {
                        throw TenetError::at_pos("`" + base->name + "` 不是数组，不能写下标",
                                                 base->pos);
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

    /// 为 struct 局部变量分配扁平字段槽位（每个字段一个 alloca）。
    VarInfo alloc_struct(const std::string& ty_name, const Position& pos) {
        auto defs = struct_fields(ty_name, pos);
        VarInfo info;
        info.ty = ty_name;
        for (const auto& [fname, fty] : defs) {
            auto* addr = builder_.CreateAlloca(ty(llvm_type(fty)), nullptr, fname);
            info.fields[fname] = {fty, addr};
        }
        return info;
    }

    /// struct 初始化：从字面量或其他 struct 变量逐字段拷贝。
    VarInfo init_struct(const std::string& name, const std::string& ty_name, const ExprPtr& value,
                        const Position& pos) {
        auto defs = struct_fields(ty_name, pos);
        VarInfo dst = alloc_struct(ty_name, pos);
        if (value->kind == Expr::Kind::StructLit) {
            if (value->name != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 标注为 " + ty_name + "，但字面量是 " + value->name, value->pos);
            }
            std::unordered_map<std::string, ExprPtr> map;
            for (const auto& [fname, fexpr] : value->init_fields) {
                if (!map.emplace(fname, fexpr).second) {
                    throw TenetError::at_pos(
                        "struct `" + ty_name + "` 的字段 `" + fname + "` 重复初始化", fexpr->pos);
                }
            }
            for (const auto& [fname, fty] : defs) {
                auto it = map.find(fname);
                if (it == map.end()) {
                    throw TenetError::at_pos("struct `" + ty_name + "` 缺少字段 `" + fname + "`",
                                             value->pos);
                }
                auto [vt, v] = gen_expr(it->second);
                if (vt != llvm_type(fty)) {
                    throw TenetError::at_pos(
                        "struct `" + ty_name + "` 字段 `" + fname + "` 类型不匹配：需要 " + fty +
                            "，实际 " + tenet_name(vt),
                        it->second->pos);
                }
                builder_.CreateStore(v, dst.fields[fname].second);
                map.erase(it);
            }
            if (!map.empty()) {
                const auto& [extra, fexpr] = *map.begin();
                throw TenetError::at_pos(
                    "struct `" + ty_name + "` 没有字段 `" + extra + "`", fexpr->pos);
            }
            return dst;
        }
        if (value->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(value->name, value->pos);
            if (sinfo.ty != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但 `" + value->name + "` 是 " + sinfo.ty,
                    value->pos);
            }
            copy_struct(dst, sinfo);
            return dst;
        }
        throw TenetError::at_pos("`" + name + "` 的 struct 初始化必须是 `" + ty_name +
                                     " {{ ... }}` 或同类型 struct 变量",
                                 value->pos);
    }

    /// struct 整体赋值：字面量逐字段写入，或同类型变量逐字段拷贝。
    void assign_struct(const VarInfo& dst, const ExprPtr& value, const Position& pos) {
        if (value->kind == Expr::Kind::StructLit) {
            if (value->name != dst.ty) {
                throw TenetError::at_pos(
                    "赋值类型不匹配：需要 " + dst.ty + "，字面量是 " + value->name, pos);
            }
            auto defs = struct_fields(dst.ty, pos);
            std::unordered_map<std::string, ExprPtr> map;
            for (const auto& [fname, fexpr] : value->init_fields) {
                if (!map.emplace(fname, fexpr).second) {
                    throw TenetError::at_pos(
                        "struct `" + dst.ty + "` 的字段 `" + fname + "` 重复初始化", fexpr->pos);
                }
            }
            for (const auto& [fname, fty] : defs) {
                auto it = map.find(fname);
                if (it == map.end()) {
                    throw TenetError::at_pos("struct `" + dst.ty + "` 缺少字段 `" + fname + "`",
                                             value->pos);
                }
                auto [vt, v] = gen_expr(it->second);
                if (vt != llvm_type(fty)) {
                    throw TenetError::at_pos(
                        "struct `" + dst.ty + "` 字段 `" + fname + "` 类型不匹配：需要 " + fty +
                            "，实际 " + tenet_name(vt),
                        it->second->pos);
                }
                builder_.CreateStore(v, dst.fields.at(fname).second);
                map.erase(it);
            }
            if (!map.empty()) {
                const auto& [extra, fexpr] = *map.begin();
                throw TenetError::at_pos("struct `" + dst.ty + "` 没有字段 `" + extra + "`",
                                         fexpr->pos);
            }
            return;
        }
        if (value->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(value->name, value->pos);
            if (sinfo.ty != dst.ty) {
                throw TenetError::at_pos(
                    "赋值类型不匹配：需要 " + dst.ty + "，右侧是 " + sinfo.ty, pos);
            }
            copy_struct(dst, sinfo);
            return;
        }
        throw TenetError::at_pos("struct 整体赋值必须是同类型变量或字面量", value->pos);
    }

    /// 逐字段值拷贝（v1 的 struct 拷贝语义）。
    void copy_struct(const VarInfo& dst, const VarInfo& src) {
        for (const auto& [fname, dfield] : dst.fields) {
            auto it = src.fields.find(fname);
            if (it == src.fields.end()) {
                throw TenetError::at_pos("struct 字段 `" + fname + "` 不存在", Position(1, 1));
            }
            const auto& [fty, daddr] = dfield;
            auto* saddr = it->second.second;
            auto* v = builder_.CreateLoad(ty(llvm_type(fty)), saddr);
            builder_.CreateStore(v, daddr);
        }
    }

    // ---- array v1 ----

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
    llvm::Value* array_addr(llvm::AllocaInst* base, size_t len, llvm::Value* index,
                            llvm::Type* elem_ty) {
        auto* arr_ty = llvm::ArrayType::get(elem_ty, len);
        llvm::Value* idxs[] = {llvm::ConstantInt::get(llvm::Type::getInt64Ty(ctx_), 0), index};
        return builder_.CreateGEP(arr_ty, base, idxs, "a.slot");
    }

    /// 逐元素值拷贝（array 的赋值语义）。
    void copy_array(const VarInfo& dst, const VarInfo& src) {
        auto elem = array_elem(dst.ty);
        if (!elem.has_value() || !dst.array_len.has_value()) {
            throw TenetError("内部错误：数组拷贝目标不是数组");
        }
        size_t len = *dst.array_len;
        auto* elem_ty = ty(llvm_type(*elem));
        auto* i64 = llvm::Type::getInt64Ty(ctx_);
        for (size_t i = 0; i < len; ++i) {
            auto* idx = llvm::ConstantInt::get(i64, static_cast<uint64_t>(i));
            auto* saddr = array_addr(src.addr, len, idx, elem_ty);
            auto* daddr = array_addr(dst.addr, len, idx, elem_ty);
            auto* v = builder_.CreateLoad(elem_ty, saddr);
            builder_.CreateStore(v, daddr);
        }
    }

    /// 数组初始化：非空字面量（长度由此固定）或同类型数组变量（逐元素拷贝）。
    VarInfo init_array(const std::string& name, const std::string& ty_name, const ExprPtr& value,
                       const Position& pos) {
        std::string elem = array_elem_scalar(ty_name, pos);
        std::string elem_ll = llvm_type(elem);
        llvm::Type* elem_ty = ty(elem_ll.c_str());
        size_t len = 0;
        const std::vector<ExprPtr>* literal = nullptr;

        if (value->kind == Expr::Kind::Array) {
            if (value->args.empty()) {
                throw TenetError::at_pos("v1 不支持空数组字面量", value->pos);
            }
            len = value->args.size();
            literal = &value->args;
        } else if (value->kind == Expr::Kind::Var) {
            const VarInfo& sinfo = lookup_var(value->name, value->pos);
            if (!sinfo.array_len.has_value()) {
                throw TenetError::at_pos("`" + value->name + "` 不是数组", value->pos);
            }
            if (sinfo.ty != ty_name) {
                throw TenetError::at_pos(
                    "`" + name + "` 需要 " + ty_name + "，但 `" + value->name + "` 是 " + sinfo.ty,
                    value->pos);
            }
            len = *sinfo.array_len;
        } else {
            throw TenetError::at_pos(
                "`" + name + "` 的数组初始化必须是 `[...]` 或同类型数组变量", value->pos);
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
            copy_array(info, lookup_var(value->name, value->pos));
        }
        return info;
    }

    /// 数组整体赋值：同长度字面量逐元素写入，或同类型数组变量逐元素拷贝。
    void assign_array(const VarInfo& dst, const ExprPtr& value, const Position& pos) {
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
            if (!sinfo.array_len.has_value() || sinfo.ty != dst.ty) {
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
        throw TenetError::at_pos("数组赋值必须是同类型数组变量或同长度字面量", value->pos);
    }

    /// 短路 && / ||：基本块 + phi（IRBuilder 下 phi 最简洁）。
    std::pair<std::string, llvm::Value*> gen_logic(const std::string& op, const ExprPtr& lhs, const ExprPtr& rhs) {
        auto [lt, lv] = gen_expr(lhs);
        if (lt != "i1") {
            throw TenetError::at_pos("运算符 `" + op + "` 只能作用于 bool，实际为 " + std::string(tenet_name(lt)),
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
            throw TenetError::at_pos("运算符 `" + op + "` 只能作用于 bool，实际为 " + std::string(tenet_name(rt)),
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
        if (callee == "len") {
            if (args.size() != 1) {
                throw TenetError::at_pos("`len` 需要且只需要一个数组参数", pos);
            }
            if (args[0]->kind != Expr::Kind::Var) {
                throw TenetError::at_pos("`len` 参数必须是数组变量", args[0]->pos);
            }
            const VarInfo& info = lookup_var(args[0]->name, args[0]->pos);
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
        for (size_t i = 0; i < args.size(); ++i) {
            auto [t, v] = gen_expr(args[i]);
            if (std::string(tenet_name(t)) != info.params[i]) {
                throw TenetError::at_pos("函数 `" + callee + "` 参数 " + std::to_string(i) +
                                             " 类型不匹配：期望 " + info.params[i] + "，实际 " + tenet_name(t),
                                         args[i]->pos);
            }
            vals.push_back(v);
        }
        auto fn = info.fn;
        auto call = builder_.CreateCall(fn, vals);
        if (info.ret.has_value()) {
            return {llvm_type(*info.ret), call};
        }
        return {"void", call};
    }

    /// print(a, b, ...) → 编译期按类型拼 printf 格式串。
    std::pair<std::string, llvm::Value*> gen_print(const std::vector<ExprPtr>& args, const Position& pos) {
        std::string fmt;
        std::vector<llvm::Value*> vals;
        for (size_t i = 0; i < args.size(); ++i) {
            if (i > 0) fmt.push_back(' ');
            auto [t, v] = gen_expr(args[i]);
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
        auto fmt_addr = builder_.CreateGlobalStringPtr(fmt, ".str.fmt." + std::to_string(globals_str_++));
        std::vector<llvm::Value*> call_args;
        call_args.push_back(fmt_addr);
        call_args.insert(call_args.end(), vals.begin(), vals.end());
        auto printf_fn = mod_.getFunction("printf");
        auto call = builder_.CreateCall(printf_fn, call_args);
        return {"void", call};
    }

    // ---- 类型推断（与求值规则一致）----

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
                auto it = infer_type(e->index);
                if (it.has_value() && *it != T_INT) {
                    throw TenetError::at_pos("数组下标必须是 int，实际为 " + *it, e->index->pos);
                }
                return *elem;
            }
            case Expr::Kind::Field: {
                const ExprPtr& base = e->base;
                if (base->kind != Expr::Kind::Var) {
                    throw TenetError::at_pos("v1 只支持对 struct 变量取字段", base->pos);
                }
                const VarInfo& info = lookup_var(base->name, base->pos);
                if (!is_struct(info.ty)) {
                    throw TenetError::at_pos("`" + base->name + "` 不是 struct", base->pos);
                }
                auto f = info.fields.find(e->field);
                if (f == info.fields.end()) {
                    throw TenetError::at_pos("struct `" + info.ty + "` 没有字段 `" + e->field + "`",
                                             e->pos);
                }
                return f->second.first;
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
                    const ExprPtr& base = target->base;
                    if (base->kind != Expr::Kind::Var) {
                        throw TenetError::at_pos("v1 只支持对 struct 变量取字段", base->pos);
                    }
                    const VarInfo& info = lookup_var(base->name, base->pos);
                    auto f = info.fields.find(target->field);
                    if (f == info.fields.end()) {
                        throw TenetError::at_pos(
                            "struct `" + info.ty + "` 没有字段 `" + target->field + "`",
                            target->pos);
                    }
                    return f->second.first;
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
