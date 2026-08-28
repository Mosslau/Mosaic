// 运行时值系统。
// 与 tenet-rs/src/value.rs、tenet-py/tenet/value.py 语义一致。
//
// 用 std::variant 表达 Tenet 的值：int64 / double / bool / string / nil。
//
// 关键对齐点：
// - int/int 除法是**向零截断**（C++ 原生语义，与 Rust 一致）
// - 负数取模同理（-7 % 2 == -1）
// - int 与 float 比较互通（1 == 1.0 → true）
// - 浮点打印对齐 Rust f64 Display（3.0 显示为 "3"，不用科学计数法）
#pragma once

#include <charconv>
#include <cstdint>
#include <string>
#include <variant>

#include "ast.hpp"
#include "error.hpp"

namespace tenet {

/// nil 哨兵：无返回值函数调用的结果。
struct Nil {};

/// Tenet 的运行时值。
using Value = std::variant<int64_t, double, bool, std::string, Nil>;

// 显式构造工厂（避免 int → int64_t / bool 的重载歧义）
inline Value v_int(int64_t x) { return Value(std::in_place_type<int64_t>, x); }
inline Value v_float(double x) { return Value(std::in_place_type<double>, x); }
inline Value v_bool(bool b) { return Value(std::in_place_type<bool>, b); }
inline Value v_str(std::string s) { return Value(std::in_place_type<std::string>, std::move(s)); }
inline Value v_nil() { return Value(std::in_place_type<Nil>, Nil{}); }

inline bool is_int(const Value& v) { return std::holds_alternative<int64_t>(v); }
inline bool is_float(const Value& v) { return std::holds_alternative<double>(v); }
inline bool is_bool(const Value& v) { return std::holds_alternative<bool>(v); }
inline bool is_str(const Value& v) { return std::holds_alternative<std::string>(v); }
inline bool is_nil(const Value& v) { return std::holds_alternative<Nil>(v); }
inline bool is_number(const Value& v) { return is_int(v) || is_float(v); }

/// 值的类型名（用于错误信息）。
inline std::string type_name(const Value& v) {
    if (is_nil(v)) return "nil";
    if (is_bool(v)) return "bool";
    if (is_int(v)) return "int";
    if (is_float(v)) return "float";
    if (is_str(v)) return "string";
    return "unknown";
}

/// 值在类型系统中的类别（nil 没有标注类型）。
inline std::optional<std::string> as_type(const Value& v) {
    if (is_int(v)) return std::string(T_INT);
    if (is_float(v)) return std::string(T_FLOAT);
    if (is_bool(v)) return std::string(T_BOOL);
    if (is_str(v)) return std::string(T_STR);
    return std::nullopt;
}

/// 值与给定标注类型是否匹配。
inline bool matches(const Value& v, const std::string& ty) {
    return as_type(v) == ty;
}

/// 浮点 → 字符串：最短往返表示 + 十进制展开（对齐 Rust f64 Display）。
inline std::string fmt_float(double v) {
    char buf[64];
    // chars_format::fixed 给出十进制展开的最短往返表示：
    // 3.14 → "3.14"，3.0 → "3"，1e21 → "1000000000000000000000"
    auto res = std::to_chars(buf, buf + sizeof(buf), v, std::chars_format::fixed);
    return std::string(buf, res.ptr);
}

/// 值的人类可读输出（print / REPL 用）。
inline std::string display(const Value& v) {
    if (is_nil(v)) return "nil";
    if (is_bool(v)) return std::get<bool>(v) ? "true" : "false";
    if (is_int(v)) return std::to_string(std::get<int64_t>(v));
    if (is_float(v)) return fmt_float(std::get<double>(v));
    return std::get<std::string>(v);
}

/// 二元运算。规则与 Rust/Python 版完全一致。
inline Value apply_binary(const Value& a, const std::string& op, const Value& b) {
    // ---- 整数 × 整数 ----
    if (is_int(a) && is_int(b)) {
        int64_t x = std::get<int64_t>(a), y = std::get<int64_t>(b);
        if (op == OP_ADD) return v_int(x + y);
        if (op == OP_SUB) return v_int(x - y);
        if (op == OP_MUL) return v_int(x * y);
        if (op == OP_DIV) {
            if (y == 0) throw TenetError("整数除以零");
            return v_int(x / y);  // C++ 原生向零截断
        }
        if (op == OP_MOD) {
            if (y == 0) throw TenetError("整数取模零");
            return v_int(x % y);
        }
        if (op == OP_EQ) return v_bool(x == y);
        if (op == OP_NEQ) return v_bool(x != y);
        if (op == OP_LT) return v_bool(x < y);
        if (op == OP_LTE) return v_bool(x <= y);
        if (op == OP_GT) return v_bool(x > y);
        if (op == OP_GTE) return v_bool(x >= y);
        throw TenetError("运算符 `" + op + "` 不能作用于 " + type_name(a) + " 和 " + type_name(b));
    }

    // ---- 数值混合（int × float / float × float）----
    if (is_number(a) && is_number(b)) {
        double x = is_int(a) ? static_cast<double>(std::get<int64_t>(a)) : std::get<double>(a);
        double y = is_int(b) ? static_cast<double>(std::get<int64_t>(b)) : std::get<double>(b);
        if (op == OP_ADD) return v_float(x + y);
        if (op == OP_SUB) return v_float(x - y);
        if (op == OP_MUL) return v_float(x * y);
        if (op == OP_DIV) {
            if (y == 0.0) throw TenetError("浮点除以零");
            return v_float(x / y);
        }
        if (op == OP_EQ) return v_bool(x == y);
        if (op == OP_NEQ) return v_bool(x != y);
        if (op == OP_LT) return v_bool(x < y);
        if (op == OP_LTE) return v_bool(x <= y);
        if (op == OP_GT) return v_bool(x > y);
        if (op == OP_GTE) return v_bool(x >= y);
        // `%` 只支持 int：镜像 Rust 的 numeric_float
        throw TenetError("运算符 `" + op + "` 不能作用于 float");
    }

    // ---- 字符串 × 字符串 ----
    if (is_str(a) && is_str(b)) {
        const std::string& x = std::get<std::string>(a);
        const std::string& y = std::get<std::string>(b);
        if (op == OP_ADD) return v_str(x + y);
        if (op == OP_EQ) return v_bool(x == y);
        if (op == OP_NEQ) return v_bool(x != y);
        if (op == OP_LT) return v_bool(x < y);
        if (op == OP_LTE) return v_bool(x <= y);
        if (op == OP_GT) return v_bool(x > y);
        if (op == OP_GTE) return v_bool(x >= y);
        throw TenetError("运算符 `" + op + "` 不能作用于 " + type_name(a) + " 和 " + type_name(b));
    }

    // ---- 布尔 × 布尔（仅 == / !=）----
    if (is_bool(a) && is_bool(b)) {
        if (op == OP_EQ) return v_bool(std::get<bool>(a) == std::get<bool>(b));
        if (op == OP_NEQ) return v_bool(std::get<bool>(a) != std::get<bool>(b));
        throw TenetError("运算符 `" + op + "` 不能作用于 " + type_name(a) + " 和 " + type_name(b));
    }

    throw TenetError("运算符 `" + op + "` 不能作用于 " + type_name(a) + " 和 " + type_name(b));
}

/// 一元运算：`-` 数值取负，`!` 布尔取反。
inline Value apply_unary(const Value& v, const std::string& op) {
    if (op == OP_NEG) {
        if (is_int(v)) return v_int(-std::get<int64_t>(v));
        if (is_float(v)) return v_float(-std::get<double>(v));
        throw TenetError("一元运算符 `-` 不能作用于 " + type_name(v));
    }
    if (op == OP_NOT) {
        if (is_bool(v)) return v_bool(!std::get<bool>(v));
        throw TenetError("一元运算符 `!` 不能作用于 " + type_name(v));
    }
    throw TenetError("未知的一元运算符 `" + op + "`");
}

/// 把值解释为条件（必须是真的 bool）。
inline bool expect_bool(const Value& v) {
    if (is_bool(v)) return std::get<bool>(v);
    throw TenetError("条件表达式需要 bool，实际为 " + type_name(v));
}

}  // namespace tenet
