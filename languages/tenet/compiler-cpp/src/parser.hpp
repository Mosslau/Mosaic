// 语法分析器：递归下降 + 优先级爬升（与 compiler-rs/src/parser.rs 对应）。
#pragma once

#include <string>
#include <vector>

#include "ast.hpp"
#include "error.hpp"
#include "lexer.hpp"
#include "token.hpp"

namespace tenet {

class Parser {
public:
    explicit Parser(std::vector<Token> tokens) : tokens_(std::move(tokens)), pos_(0) {}

    static Program parse(const std::string& source) {
        auto tokens = Lexer::tokenize(source);
        Parser parser(std::move(tokens));
        return parser.parse_program();
    }

private:
    std::vector<Token> tokens_;
    size_t pos_;

    const Token& peek() const { return tokens_[pos_]; }

    Token advance() {
        Token tok = tokens_[pos_];
        if (pos_ + 1 < tokens_.size()) ++pos_;
        return tok;
    }

    bool check(Kind kind) const { return peek().kind == kind; }

    Token expect(Kind kind, const std::string& what) {
        if (check(kind)) return advance();
        throw error("期望 " + what + "，但遇到 " + describe(peek().kind, peek()));
    }

    TenetError error(const std::string& msg) const {
        return TenetError::at_pos(msg, peek().pos);
    }

    Program parse_program() {
        Program prog;
        while (!check(Kind::Eof)) prog.stmts.push_back(parse_stmt());
        return prog;
    }

    StmtPtr parse_stmt() {
        Position p = peek().pos;
        switch (peek().kind) {
            case Kind::Let: return parse_let();
            case Kind::Fn: return parse_fn_decl();
            case Kind::Struct: return parse_struct_decl();
            case Kind::If: return parse_if();
            case Kind::While: return parse_while();
            case Kind::Return: return parse_return();
            case Kind::Break: {
                advance();
                expect(Kind::Semi, "`;`");
                auto s = std::make_shared<Stmt>();
                s->pos = p;
                s->kind = Stmt::Kind::Break;
                return s;
            }
            default: {
                auto s = std::make_shared<Stmt>();
                s->pos = p;
                s->kind = Stmt::Kind::Expr;
                s->expr = parse_expr();
                expect(Kind::Semi, "`;`");
                return s;
            }
        }
    }

    StmtPtr parse_let() {
        Position p = peek().pos;
        advance();
        auto s = std::make_shared<Stmt>();
        s->pos = p;
        s->kind = Stmt::Kind::Let;
        s->name = expect_ident("变量名");
        if (check(Kind::Colon)) {
            advance();
            s->ty = parse_type();
        }
        expect(Kind::Assign, "`=`");
        s->value = parse_expr();
        expect(Kind::Semi, "`;`");
        return s;
    }

    StmtPtr parse_fn_decl() {
        Position p = peek().pos;
        advance();
        auto s = std::make_shared<Stmt>();
        s->pos = p;
        s->kind = Stmt::Kind::FnDecl;
        s->name = expect_ident("函数名");
        expect(Kind::LParen, "`(`");
        if (!check(Kind::RParen)) {
            while (true) {
                std::string pname = expect_ident("参数名");
                expect(Kind::Colon, "`:`");
                std::string pty = parse_type();
                s->params.emplace_back(pname, pty);
                if (!check(Kind::Comma)) break;
                advance();
            }
        }
        expect(Kind::RParen, "`)`");
        if (check(Kind::Arrow)) {
            advance();
            s->ret = parse_type();
        }
        s->body = parse_block();
        return s;
    }

    StmtPtr parse_struct_decl() {
        Position p = peek().pos;
        advance();
        auto s = std::make_shared<Stmt>();
        s->pos = p;
        s->kind = Stmt::Kind::StructDecl;
        s->name = expect_ident("struct 名");
        expect(Kind::LBrace, "`{`");
        while (!check(Kind::RBrace) && !check(Kind::Eof)) {
            std::string fname = expect_ident("字段名");
            expect(Kind::Colon, "`:`");
            std::string fty = parse_type();
            expect(Kind::Semi, "`;`");
            s->fields.emplace_back(std::move(fname), std::move(fty));
        }
        expect(Kind::RBrace, "`}`");
        if (check(Kind::Semi)) advance();
        return s;
    }

    StmtPtr parse_if() {
        Position p = peek().pos;
        advance();
        auto s = std::make_shared<Stmt>();
        s->pos = p;
        s->kind = Stmt::Kind::If;
        expect(Kind::LParen, "`(`");
        s->cond = parse_expr();
        expect(Kind::RParen, "`)`");
        s->then_branch = parse_block();
        if (check(Kind::Else)) {
            advance();
            if (check(Kind::If)) {
                s->else_branch.push_back(parse_if());
            } else {
                s->else_branch = parse_block();
            }
        }
        return s;
    }

    StmtPtr parse_while() {
        Position p = peek().pos;
        advance();
        auto s = std::make_shared<Stmt>();
        s->pos = p;
        s->kind = Stmt::Kind::While;
        expect(Kind::LParen, "`(`");
        s->cond = parse_expr();
        expect(Kind::RParen, "`)`");
        s->body = parse_block();
        return s;
    }

    StmtPtr parse_return() {
        Position p = peek().pos;
        advance();
        auto s = std::make_shared<Stmt>();
        s->pos = p;
        s->kind = Stmt::Kind::Return;
        if (check(Kind::Semi)) {
            advance();
        } else {
            s->expr = parse_expr();
            expect(Kind::Semi, "`;`");
        }
        return s;
    }

    std::vector<StmtPtr> parse_block() {
        expect(Kind::LBrace, "`{`");
        std::vector<StmtPtr> stmts;
        while (!check(Kind::RBrace) && !check(Kind::Eof)) stmts.push_back(parse_stmt());
        expect(Kind::RBrace, "`}`");
        return stmts;
    }

    std::string parse_type() {
        switch (peek().kind) {
            case Kind::IntType: advance(); return T_INT;
            case Kind::FloatType: advance(); return T_FLOAT;
            case Kind::BoolType: advance(); return T_BOOL;
            case Kind::StrType: advance(); return T_STR;
            case Kind::ArrayType: {
                advance();
                expect(Kind::Lt, "`<`");
                std::string inner = parse_type();
                expect(Kind::Gt, "`>`");
                return "array<" + inner + ">";
            }
            case Kind::Ident: {
                std::string name = peek().str_val;
                advance();
                return name;
            }
            default:
                throw error("期望类型 `int` / `float` / `bool` / `string` / `array<T>` 或 struct 名，但遇到 " +
                            describe(peek().kind, peek()));
        }
    }

    std::string expect_ident(const std::string& what) {
        if (check(Kind::Ident)) {
            std::string name = peek().str_val;
            advance();
            return name;
        }
        throw error("期望 " + what + "，但遇到 " + describe(peek().kind, peek()));
    }

    static int binary_prec(Kind kind) {
        switch (kind) {
            case Kind::Or: return 1;
            case Kind::And: return 2;
            case Kind::Eq:
            case Kind::Neq: return 3;
            case Kind::Lt:
            case Kind::Lte:
            case Kind::Gt:
            case Kind::Gte: return 4;
            case Kind::Plus:
            case Kind::Minus: return 5;
            case Kind::Star:
            case Kind::Slash:
            case Kind::Percent: return 6;
            default: return -1;
        }
    }

    static const char* binop_str(Kind kind) {
        switch (kind) {
            case Kind::Or: return OP_OR;
            case Kind::And: return OP_AND;
            case Kind::Eq: return OP_EQ;
            case Kind::Neq: return OP_NEQ;
            case Kind::Lt: return OP_LT;
            case Kind::Lte: return OP_LTE;
            case Kind::Gt: return OP_GT;
            case Kind::Gte: return OP_GTE;
            case Kind::Plus: return OP_ADD;
            case Kind::Minus: return OP_SUB;
            case Kind::Star: return OP_MUL;
            case Kind::Slash: return OP_DIV;
            case Kind::Percent: return OP_MOD;
            default: return "";
        }
    }

    /// 表达式：先解析二元表达式，再在最低优先级处理赋值（右结合）。
    /// 赋值左侧必须是变量、字段或数组下标（`x = ...` / `p.x = ...` / `a[i] = ...`）。
    ExprPtr parse_expr() {
        ExprPtr lhs = parse_binary(0);
        if (check(Kind::Assign)) {
            if (lhs->kind != Expr::Kind::Var && lhs->kind != Expr::Kind::Field &&
                lhs->kind != Expr::Kind::Index) {
                throw TenetError::at_pos("赋值左侧必须是变量或字段", lhs->pos);
            }
            Position p = lhs->pos;
            advance();
            ExprPtr value = parse_expr();
            auto e = std::make_shared<Expr>();
            e->pos = p;
            e->kind = Expr::Kind::Assign;
            e->lhs = std::move(lhs);
            e->value = std::move(value);
            return e;
        }
        return lhs;
    }

    ExprPtr parse_binary(int min_prec) {
        ExprPtr lhs = parse_unary();
        while (true) {
            int prec = binary_prec(peek().kind);
            if (prec < 0 || prec < min_prec) break;
            std::string op = binop_str(peek().kind);
            advance();
            ExprPtr rhs = parse_binary(prec + 1);
            auto e = std::make_shared<Expr>();
            e->pos = lhs->pos;
            e->kind = Expr::Kind::Binary;
            e->op = op;
            e->lhs = std::move(lhs);
            e->rhs = std::move(rhs);
            lhs = std::move(e);
        }
        return lhs;
    }

    ExprPtr parse_unary() {
        if (check(Kind::Minus)) {
            Position p = peek().pos;
            advance();
            auto e = std::make_shared<Expr>();
            e->pos = p;
            e->kind = Expr::Kind::Unary;
            e->op = OP_NEG;
            e->value = parse_unary();
            return e;
        }
        if (check(Kind::Not)) {
            Position p = peek().pos;
            advance();
            auto e = std::make_shared<Expr>();
            e->pos = p;
            e->kind = Expr::Kind::Unary;
            e->op = OP_NOT;
            e->value = parse_unary();
            return e;
        }
        return parse_postfix();
    }

    /// 后缀 `.field` / `[index]`：v1 仅需一层字段/下标，但语法上允许链式（codegen 报错）。
    ExprPtr parse_postfix() {
        ExprPtr expr = parse_primary();
        while (true) {
            if (check(Kind::Dot)) {
                advance();
                std::string field = expect_ident("字段名");
                auto e = std::make_shared<Expr>();
                e->pos = expr->pos;
                e->kind = Expr::Kind::Field;
                e->base = std::move(expr);
                e->field = std::move(field);
                expr = std::move(e);
            } else if (check(Kind::LBracket)) {
                advance();
                ExprPtr index = parse_expr();
                expect(Kind::RBracket, "`]`");
                auto e = std::make_shared<Expr>();
                e->pos = expr->pos;
                e->kind = Expr::Kind::Index;
                e->base = std::move(expr);
                e->index = std::move(index);
                expr = std::move(e);
            } else {
                break;
            }
        }
        return expr;
    }

    ExprPtr parse_primary() {
        const Token tok = peek();
        auto e = std::make_shared<Expr>();
        e->pos = tok.pos;
        switch (tok.kind) {
            case Kind::Int: advance(); e->kind = Expr::Kind::Int; e->int_val = tok.int_val; return e;
            case Kind::Float: advance(); e->kind = Expr::Kind::Float; e->float_val = tok.float_val; return e;
            case Kind::Str: advance(); e->kind = Expr::Kind::Str; e->str_val = tok.str_val; return e;
            case Kind::True: advance(); e->kind = Expr::Kind::Bool; e->bool_val = true; return e;
            case Kind::False: advance(); e->kind = Expr::Kind::Bool; e->bool_val = false; return e;
            case Kind::Ident: {
                advance();
                if (check(Kind::LParen)) return parse_call_args(tok.str_val, tok.pos);
                if (check(Kind::LBrace)) return parse_struct_lit(tok.str_val, tok.pos);
                e->kind = Expr::Kind::Var;
                e->name = tok.str_val;
                return e;
            }
            case Kind::LParen: {
                advance();
                ExprPtr inner = parse_expr();
                expect(Kind::RParen, "`)`");
                return inner;
            }
            case Kind::LBracket: {
                advance();
                e->kind = Expr::Kind::Array;
                if (!check(Kind::RBracket)) {
                    while (true) {
                        e->args.push_back(parse_expr());
                        if (!check(Kind::Comma)) break;
                        advance();
                    }
                }
                expect(Kind::RBracket, "`]`");
                return e;
            }
            default:
                throw error("期望一个表达式，但遇到 " + describe(tok.kind, tok));
        }
    }

    ExprPtr parse_struct_lit(const std::string& name, Position pos) {
        expect(Kind::LBrace, "`{`");
        auto e = std::make_shared<Expr>();
        e->pos = pos;
        e->kind = Expr::Kind::StructLit;
        e->name = name;
        if (!check(Kind::RBrace)) {
            while (true) {
                std::string fname = expect_ident("字段名");
                expect(Kind::Colon, "`:`");
                ExprPtr value = parse_expr();
                e->init_fields.emplace_back(std::move(fname), std::move(value));
                if (!check(Kind::Comma)) break;
                advance();
            }
        }
        expect(Kind::RBrace, "`}`");
        return e;
    }

    ExprPtr parse_call_args(const std::string& callee, Position pos) {
        advance();
        auto e = std::make_shared<Expr>();
        e->pos = pos;
        e->kind = Expr::Kind::Call;
        e->name = callee;
        if (!check(Kind::RParen)) {
            while (true) {
                e->args.push_back(parse_expr());
                if (!check(Kind::Comma)) break;
                advance();
            }
        }
        expect(Kind::RParen, "`)`");
        return e;
    }
};

}  // namespace tenet
