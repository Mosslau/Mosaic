// 统一错误类型：词法 / 语法 / 类型 / 代码生成全链路共用，携带 `[行:列]`。
#pragma once

#include <optional>
#include <stdexcept>
#include <string>

namespace tenet {

struct Position {
    int line = 0;
    int col = 0;
    Position() = default;
    Position(int l, int c) : line(l), col(c) {}
    bool operator==(const Position& o) const {
        return line == o.line && col == o.col;
    }
};

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

    std::string str() const {
        if (pos.has_value()) {
            return "[" + std::to_string(pos->line) + ":" + std::to_string(pos->col) + "] "
                   + message;
        }
        return message;
    }
};

}  // namespace tenet
