// LLVM 代码生成器：AST → LLVM IR（进程内构建，调用 LLVM C++ API）。
//
// 与 compiler-rs（生成 .ll 文本 + clang 驱动）的关键差异：
// - 用 IRBuilder 在内存中构建 IR（不是写文本文件）
// - 变量用 alloca + load/store；控制流用基本块 + br
// - 后端（IR → 机器码）由 LLVM 库进程内完成（rustc 方式），
//   不再调用 clang 解析文本
#pragma once

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

    // 变量作用域栈：name -> (Tenet 类型, alloca)
    std::vector<std::unordered_map<std::string, std::pair<std::string, llvm::AllocaInst*>>> symbols_;
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

        // 用户函数（先创建 Function 对象，供调用解析）
        for (const auto& stmt : program.stmts) {
            if (stmt->kind != Stmt::Kind::FnDecl) continue;
            const auto& name = stmt->name;
            if (name == "main" || name == "printf" || name == "tenet_concat" || name == "tenet_strcmp") {
                throw TenetError::at_pos("函数名 `" + name + "` 为编译器保留", stmt->pos);
            }
            if (functions_.count(name)) {
                throw TenetError::at_pos("函数 `" + name + "` 重复定义", stmt->pos);
            }
            std::vector<llvm::Type*> params;
            std::vector<std::string> param_tys;
            for (const auto& [_, pt] : stmt->params) {
                params.push_back(ty(llvm_type(pt)));
                param_tys.push_back(pt);
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
            if (stmt->kind == Stmt::Kind::FnDecl) continue;
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
            symbols_.back()[pname] = {pty, llvm::cast<llvm::AllocaInst>(addr)};
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
                auto [vt, v] = gen_expr(stmt->value);
                if (vt != llvm_type(t)) {
                    throw TenetError::at_pos(
                        "`" + stmt->name + "` 初始化类型不匹配：标注 " + t + "，实际 " + tenet_name(vt),
                        stmt->pos);
                }
                auto addr = builder_.CreateAlloca(ty(llvm_type(t)), nullptr, stmt->name);
                builder_.CreateStore(v, addr);
                symbols_.back()[stmt->name] = {t, llvm::cast<llvm::AllocaInst>(addr)};
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
                auto [t, addr] = lookup_var(e->name, e->pos);
                return {llvm_type(t), builder_.CreateLoad(ty(llvm_type(t)), addr, e->name)};
            }
            case Expr::Kind::Assign: {
                auto [t, addr] = lookup_var(e->name, e->pos);
                auto [vt, v] = gen_expr(e->value);
                if (vt != llvm_type(t)) {
                    throw TenetError::at_pos(
                        "赋值类型不匹配：`" + e->name + "` 是 " + t + "，右侧是 " + tenet_name(vt),
                        e->pos);
                }
                builder_.CreateStore(v, addr);
                return {vt, v};
            }
            case Expr::Kind::Unary: {
                auto [t, v] = gen_expr(e->value);
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
                return gen_arith(e->op, lt, lv, rt, rv, e->pos);
            }
            case Expr::Kind::Call:
                return gen_call(e->name, e->args, e->pos);
        }
        throw TenetError("未知的表达式类型");
    }

    std::pair<std::string, llvm::AllocaInst*> lookup_var(const std::string& name, const Position& pos) {
        for (auto it = symbols_.rbegin(); it != symbols_.rend(); ++it) {
            auto f = it->find(name);
            if (f != it->end()) return {f->second.first, f->second.second};
        }
        throw TenetError::at_pos("未定义的变量 `" + name + "`", pos);
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
                return lookup_var(e->name, e->pos).first;
            case Expr::Kind::Assign:
                return lookup_var(e->name, e->pos).first;
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
