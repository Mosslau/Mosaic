// Tenet — C++17 实现（tenet-cpp）
//
// 与 tenet-rs/、tenet-py/ 三端对齐的移植版：
//   error/token/lexer → ast/parser → value/env/interpreter → codegen → repl
//
// 设计原则：
// - 纯标准库（C++17），零第三方依赖，仅需 clang++/g++ 编译
// - 语义与 Rust/Python 版完全一致（词法、语法、错误信息、运行时行为）
// - 代码生成输出与 Rust/Python 版逐字节一致
//
// 编译运行：
//   cd tenet-cpp
//   make            # 构建 tenet 与 test_tenet 并跑测试
//   ./tenet run examples/fib.tenet
//   ./tenet repl
//   ./tenet codegen examples/fib.tenet

// 统一错误类型：所有阶段（词法 / 语法 / 解释 / 代码生成）共用。
// 错误携带源码位置 `[行:列]`，与 tenet-rs/src/error.rs 一致。
#pragma once

#include <optional>
#include <stdexcept>
#include <string>

namespace tenet {

/// 源码位置：1 起始的行号与列号。
struct Position {
    int line = 0;
    int col = 0;

    Position() = default;
    Position(int l, int c) : line(l), col(c) {}

    bool operator==(const Position& o) const {
        return line == o.line && col == o.col;
    }
};

/// 带可选位置的错误。
class TenetError : public std::runtime_error {
public:
    std::string message;
    std::optional<Position> pos;

    explicit TenetError(std::string msg, std::optional<Position> p = std::nullopt)
        : std::runtime_error(msg), message(std::move(msg)), pos(std::move(p)) {}

    static TenetError at(std::string msg, int line, int col) {
        return TenetError(std::move(msg), Position(line, col));
    }

    static TenetError at_pos(std::string msg, Position p) {
        return TenetError(std::move(msg), p);
    }

    /// 完整错误信息：`[行:列] 消息` 或 `消息`。
    std::string str() const {
        if (pos.has_value()) {
            return "[" + std::to_string(pos->line) + ":" + std::to_string(pos->col) + "] "
                   + message;
        }
        return message;
    }
};

}  // namespace tenet
