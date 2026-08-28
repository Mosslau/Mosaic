// 环境（Environment）：变量作用域的链式结构。
// 与 tenet-rs/src/env.rs、tenet-py/tenet/env.py 语义一致。
//
// - 块（{}）与函数调用创建新的作用域，子作用域通过 parent 访问外层
// - 定义（define）只写当前层 → 允许遮蔽
// - 查找 / 赋值（get / assign）沿链向上
// - 顶层不建作用域：顶层 let 直接进全局环境（REPL 跨行记忆的关键）
#pragma once

#include <memory>
#include <string>
#include <unordered_map>

#include "error.hpp"
#include "value.hpp"

namespace tenet {

class Env;
using EnvPtr = std::shared_ptr<Env>;

class Env {
public:
    explicit Env(Env* parent = nullptr) : parent_(parent) {}

    static EnvPtr global() { return std::make_shared<Env>(nullptr); }

    static EnvPtr child(const EnvPtr& parent) { return std::make_shared<Env>(parent.get()); }

    void define(const std::string& name, Value value) { vars_[name] = std::move(value); }

    Value get(const std::string& name) const {
        const Env* env = this;
        while (env != nullptr) {
            auto it = env->vars_.find(name);
            if (it != env->vars_.end()) return it->second;
            env = env->parent_;
        }
        throw TenetError("未定义的变量 `" + name + "`");
    }

    void assign(const std::string& name, Value value) {
        Env* env = this;
        while (env != nullptr) {
            auto it = env->vars_.find(name);
            if (it != env->vars_.end()) {
                it->second = std::move(value);
                return;
            }
            env = env->parent_;
        }
        throw TenetError("未定义的变量 `" + name + "`");
    }

private:
    std::unordered_map<std::string, Value> vars_;
    Env* parent_;
};

}  // namespace tenet
