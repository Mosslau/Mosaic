// 词法单元（Token）定义。
// 与 tenet-rs/src/token.rs 对应：Token = (kind, 载荷, pos)。
// 载荷按 kind 存放在 Token 的不同字段里（int_val / float_val / str_val）。
#pragma once

#include <cstdint>
#include <string>

#include "error.hpp"

namespace tenet {

/// 词法单元种类（enum class，镜像 Rust 的 TokenKind）。
enum class Kind {
    // 字面量
    Int,
    Float,
    Str,
    Ident,
    // 关键字
    Let,
    Fn,
    If,
    Else,
    While,
    Return,
    Break,
    True,
    False,
    IntType,
    FloatType,
    BoolType,
    StrType,
    // 符号
    LParen,
    RParen,
    LBrace,
    RBrace,
    Comma,
    Colon,
    Semi,
    Arrow,
    Assign,
    Plus,
    Minus,
    Star,
    Slash,
    Percent,
    Eq,
    Neq,
    Lt,
    Lte,
    Gt,
    Gte,
    And,
    Or,
    Not,
    Eof,
};

/// 带位置的词法单元。
struct Token {
    Kind kind = Kind::Eof;
    int64_t int_val = 0;      // Int 的载荷
    double float_val = 0.0;   // Float 的载荷
    std::string str_val;      // Str 的内容 / Ident 的名字
    Position pos;
};

/// 人类可读的名字，用于错误信息（如 "期望 `;`，但遇到 `}`"）。
inline std::string describe(Kind kind, const Token& tok) {
    switch (kind) {
        case Kind::Int: return "整数";
        case Kind::Float: return "浮点数";
        case Kind::Str: return "字符串";
        case Kind::Ident: return "标识符 `" + tok.str_val + "`";
        case Kind::Let: return "`let`";
        case Kind::Fn: return "`fn`";
        case Kind::If: return "`if`";
        case Kind::Else: return "`else`";
        case Kind::While: return "`while`";
        case Kind::Return: return "`return`";
        case Kind::Break: return "`break`";
        case Kind::True: return "`true`";
        case Kind::False: return "`false`";
        case Kind::IntType: return "类型 `int`";
        case Kind::FloatType: return "类型 `float`";
        case Kind::BoolType: return "类型 `bool`";
        case Kind::StrType: return "类型 `string`";
        case Kind::LParen: return "`(`";
        case Kind::RParen: return "`)`";
        case Kind::LBrace: return "`{`";
        case Kind::RBrace: return "`}`";
        case Kind::Comma: return "`,`";
        case Kind::Colon: return "`:`";
        case Kind::Semi: return "`;`";
        case Kind::Arrow: return "`->`";
        case Kind::Assign: return "`=`";
        case Kind::Plus: return "`+`";
        case Kind::Minus: return "`-`";
        case Kind::Star: return "`*`";
        case Kind::Slash: return "`/`";
        case Kind::Percent: return "`%`";
        case Kind::Eq: return "`==`";
        case Kind::Neq: return "`!=`";
        case Kind::Lt: return "`<`";
        case Kind::Lte: return "`<=`";
        case Kind::Gt: return "`>`";
        case Kind::Gte: return "`>=`";
        case Kind::And: return "`&&`";
        case Kind::Or: return "`||`";
        case Kind::Not: return "`!`";
        case Kind::Eof: return "文件末尾";
    }
    return "未知记号";
}

}  // namespace tenet
