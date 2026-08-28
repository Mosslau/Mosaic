// 词法分析器（与 compiler-rs/src/lexer.rs 对应）。
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "error.hpp"
#include "token.hpp"

namespace tenet {

class Lexer {
public:
    explicit Lexer(const std::string& source) : src_(source), pos_(0), line_(1), col_(1) {}

    static std::vector<Token> tokenize(const std::string& source) {
        Lexer lexer(source);
        std::vector<Token> tokens;
        while (true) {
            Token tok = lexer.next_token();
            bool eof = tok.kind == Kind::Eof;
            tokens.push_back(std::move(tok));
            if (eof) break;
        }
        return tokens;
    }

private:
    std::string src_;
    size_t pos_;
    int line_;
    int col_;

    char peek() const { return pos_ < src_.size() ? src_[pos_] : '\0'; }
    char peek2() const { return pos_ + 1 < src_.size() ? src_[pos_ + 1] : '\0'; }

    char advance() {
        char c = peek();
        if (c == '\0') return c;
        ++pos_;
        if (c == '\n') { ++line_; col_ = 1; } else { ++col_; }
        return c;
    }

    Token next_token() {
        skip_trivia();
        int line = line_, col = col_;
        auto make = [&](Kind k) {
            Token t;
            t.kind = k;
            t.pos = Position(line, col);
            return t;
        };
        char c = peek();
        if (c == '\0') return make(Kind::Eof);
        if (c >= '0' && c <= '9') return lex_number(line, col);
        if (c == '"') return lex_string(line, col);
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_') return lex_ident(line, col);
        char n = peek2();
        switch (c) {
            case '=': if (n == '=') { advance(); advance(); return make(Kind::Eq); } break;
            case '!': if (n == '=') { advance(); advance(); return make(Kind::Neq); } break;
            case '<': if (n == '=') { advance(); advance(); return make(Kind::Lte); } break;
            case '>': if (n == '=') { advance(); advance(); return make(Kind::Gte); } break;
            case '&': if (n == '&') { advance(); advance(); return make(Kind::And); } break;
            case '|': if (n == '|') { advance(); advance(); return make(Kind::Or); } break;
            case '-': if (n == '>') { advance(); advance(); return make(Kind::Arrow); } break;
            default: break;
        }
        return lex_single(c, line, col);
    }

    void skip_trivia() {
        while (true) {
            while (peek() == ' ' || peek() == '\t' || peek() == '\r' || peek() == '\n') advance();
            if (peek() == '/' && peek2() == '/') {
                while (true) { char c = advance(); if (c == '\0' || c == '\n') break; }
                continue;
            }
            if (peek() == '/' && peek2() == '*') {
                advance(); advance();
                while (true) {
                    if (peek() == '*' && peek2() == '/') { advance(); advance(); break; }
                    if (peek() == '\0') break;
                    advance();
                }
                continue;
            }
            break;
        }
    }

    Token lex_number(int line, int col) {
        std::string text;
        bool is_float = false;
        while (true) {
            char c = peek();
            if (c >= '0' && c <= '9') {
                text.push_back(advance());
            } else if (c == '.') {
                is_float = true;
                text.push_back(advance());
            } else {
                break;
            }
        }
        Token t;
        t.pos = Position(line, col);
        if (is_float) {
            t.kind = Kind::Float;
            t.float_val = std::stod(text);
        } else {
            int64_t v = 0;
            try {
                v = std::stoll(text);
            } catch (...) {
                throw TenetError::at("整数超出 i64 范围", line, col);
            }
            t.kind = Kind::Int;
            t.int_val = v;
        }
        return t;
    }

    Token lex_string(int line, int col) {
        advance();
        std::string value;
        while (true) {
            char c = advance();
            if (c == '\0') throw TenetError::at("未闭合的字符串字面量", line, col);
            if (c == '"') break;
            if (c == '\\') {
                char esc = advance();
                if (esc == '\0') throw TenetError::at("字符串以反斜杠结尾", line, col);
                switch (esc) {
                    case 'n': value.push_back('\n'); break;
                    case 't': value.push_back('\t'); break;
                    case '"': value.push_back('"'); break;
                    case '\\': value.push_back('\\'); break;
                    default:
                        throw TenetError::at("未知的转义序列 `\\" + std::string(1, esc) + "`", line, col);
                }
            } else {
                value.push_back(c);
            }
        }
        Token t;
        t.kind = Kind::Str;
        t.str_val = std::move(value);
        t.pos = Position(line, col);
        return t;
    }

    Token lex_ident(int line, int col) {
        std::string text;
        while (true) {
            char c = peek();
            if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_') {
                text.push_back(advance());
            } else {
                break;
            }
        }
        Token t;
        t.pos = Position(line, col);
        t.str_val = text;
        if (text == "let") t.kind = Kind::Let;
        else if (text == "fn") t.kind = Kind::Fn;
        else if (text == "if") t.kind = Kind::If;
        else if (text == "else") t.kind = Kind::Else;
        else if (text == "while") t.kind = Kind::While;
        else if (text == "return") t.kind = Kind::Return;
        else if (text == "break") t.kind = Kind::Break;
        else if (text == "true") t.kind = Kind::True;
        else if (text == "false") t.kind = Kind::False;
        else if (text == "int") t.kind = Kind::IntType;
        else if (text == "float") t.kind = Kind::FloatType;
        else if (text == "bool") t.kind = Kind::BoolType;
        else if (text == "string") t.kind = Kind::StrType;
        else t.kind = Kind::Ident;
        return t;
    }

    Token lex_single(char c, int line, int col) {
        advance();
        Kind kind;
        switch (c) {
            case '(': kind = Kind::LParen; break;
            case ')': kind = Kind::RParen; break;
            case '{': kind = Kind::LBrace; break;
            case '}': kind = Kind::RBrace; break;
            case ',': kind = Kind::Comma; break;
            case ':': kind = Kind::Colon; break;
            case ';': kind = Kind::Semi; break;
            case '=': kind = Kind::Assign; break;
            case '+': kind = Kind::Plus; break;
            case '-': kind = Kind::Minus; break;
            case '*': kind = Kind::Star; break;
            case '/': kind = Kind::Slash; break;
            case '%': kind = Kind::Percent; break;
            case '<': kind = Kind::Lt; break;
            case '>': kind = Kind::Gt; break;
            case '!': kind = Kind::Not; break;
            default: throw TenetError::at("无法识别的字符 `" + std::string(1, c) + "`", line, col);
        }
        Token t;
        t.kind = kind;
        t.pos = Position(line, col);
        return t;
    }
};

}  // namespace tenet
