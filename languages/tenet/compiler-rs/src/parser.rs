//! 语法分析器（Parser）：递归下降 + 优先级爬升。
//!
//! 优先级（低 → 高）：
//!   ||  <  &&  <  == !=  <  < <= > >=  <  + -  <  * / %  <  一元 - !
//! 每个 AST 节点记录起始位置（表达式的第一个 token / 语句的关键字），
//! 供代码生成阶段全链路 `[行:列]` 报错。

use crate::ast::{
    Expr, ExprKind, Program, Stmt, StmtKind, T_BOOL, T_FLOAT, T_INT, T_STR, OP_ADD, OP_AND, OP_DIV,
    OP_EQ, OP_GTE, OP_GT, OP_LTE, OP_LT, OP_MOD, OP_MUL, OP_NEG, OP_NEQ, OP_NOT, OP_OR, OP_SUB,
};
use crate::error::{Position, TenetError, TResult};
use crate::token::{Token, TokenKind};

pub struct Parser {
    tokens: Vec<Token>,
    pos: usize,
}

impl Parser {
    pub fn new(tokens: Vec<Token>) -> Self {
        Self { tokens, pos: 0 }
    }

    pub fn parse(source: &str) -> TResult<Program> {
        let tokens = crate::lexer::Lexer::tokenize(source)?;
        let mut parser = Parser::new(tokens);
        parser.parse_program()
    }

    fn peek(&self) -> &Token {
        &self.tokens[self.pos]
    }

    fn advance(&mut self) -> Token {
        let tok = self.tokens[self.pos].clone();
        if self.pos + 1 < self.tokens.len() {
            self.pos += 1;
        }
        tok
    }

    fn check(&self, kind: &TokenKind) -> bool {
        std::mem::discriminant(&self.peek().kind) == std::mem::discriminant(kind)
    }

    fn expect(&mut self, kind: &TokenKind, what: &str) -> TResult<Token> {
        if self.check(kind) {
            Ok(self.advance())
        } else {
            Err(self.error(format!("期望 {what}，但遇到 {}", self.peek().kind.describe())))
        }
    }

    fn error(&self, message: impl Into<String>) -> TenetError {
        TenetError::at_pos(message, self.peek().pos.clone())
    }

    fn parse_program(&mut self) -> TResult<Program> {
        let mut stmts = Vec::new();
        while !self.check(&TokenKind::Eof) {
            stmts.push(self.parse_stmt()?);
        }
        Ok(Program { stmts })
    }

    // ---- 语句 ----

    fn parse_stmt(&mut self) -> TResult<Stmt> {
        let pos = self.peek().pos.clone();
        let kind = match &self.peek().kind {
            TokenKind::Let => self.parse_let()?,
            TokenKind::Fn => self.parse_fn_decl()?,
            TokenKind::If => self.parse_if()?,
            TokenKind::While => self.parse_while()?,
            TokenKind::Return => self.parse_return()?,
            TokenKind::Break => {
                self.advance();
                self.expect(&TokenKind::Semi, "`;`")?;
                StmtKind::Break
            }
            _ => {
                let expr = self.parse_expr()?;
                self.expect(&TokenKind::Semi, "`;`")?;
                StmtKind::Expr(expr)
            }
        };
        Ok(Stmt { pos, kind })
    }

    fn parse_let(&mut self) -> TResult<StmtKind> {
        self.advance();
        let name = self.expect_ident("变量名")?;
        let ty = if self.check(&TokenKind::Colon) {
            self.advance();
            Some(self.parse_type()?)
        } else {
            None
        };
        self.expect(&TokenKind::Assign, "`=`")?;
        let value = self.parse_expr()?;
        self.expect(&TokenKind::Semi, "`;`")?;
        Ok(StmtKind::Let { name, ty, value })
    }

    fn parse_fn_decl(&mut self) -> TResult<StmtKind> {
        self.advance();
        let name = self.expect_ident("函数名")?;
        self.expect(&TokenKind::LParen, "`(`")?;
        let mut params = Vec::new();
        if !self.check(&TokenKind::RParen) {
            loop {
                let pname = self.expect_ident("参数名")?;
                self.expect(&TokenKind::Colon, "`:`")?;
                let pty = self.parse_type()?;
                params.push((pname, pty));
                if !self.check(&TokenKind::Comma) {
                    break;
                }
                self.advance();
            }
        }
        self.expect(&TokenKind::RParen, "`)`")?;
        let ret = if self.check(&TokenKind::Arrow) {
            self.advance();
            Some(self.parse_type()?)
        } else {
            None
        };
        let body = self.parse_block()?;
        Ok(StmtKind::FnDecl {
            name,
            params,
            ret,
            body,
        })
    }

    fn parse_if(&mut self) -> TResult<StmtKind> {
        self.advance();
        self.expect(&TokenKind::LParen, "`(`")?;
        let cond = self.parse_expr()?;
        self.expect(&TokenKind::RParen, "`)`")?;
        let then_branch = self.parse_block()?;
        let else_branch = if self.check(&TokenKind::Else) {
            self.advance();
            if self.check(&TokenKind::If) {
                Some(vec![self.parse_stmt()?])
            } else {
                Some(self.parse_block()?)
            }
        } else {
            None
        };
        Ok(StmtKind::If {
            cond,
            then_branch,
            else_branch,
        })
    }

    fn parse_while(&mut self) -> TResult<StmtKind> {
        self.advance();
        self.expect(&TokenKind::LParen, "`(`")?;
        let cond = self.parse_expr()?;
        self.expect(&TokenKind::RParen, "`)`")?;
        let body = self.parse_block()?;
        Ok(StmtKind::While { cond, body })
    }

    fn parse_return(&mut self) -> TResult<StmtKind> {
        self.advance();
        if self.check(&TokenKind::Semi) {
            self.advance();
            Ok(StmtKind::Return(None))
        } else {
            let expr = self.parse_expr()?;
            self.expect(&TokenKind::Semi, "`;`")?;
            Ok(StmtKind::Return(Some(expr)))
        }
    }

    fn parse_block(&mut self) -> TResult<Vec<Stmt>> {
        self.expect(&TokenKind::LBrace, "`{`")?;
        let mut stmts = Vec::new();
        while !self.check(&TokenKind::RBrace) && !self.check(&TokenKind::Eof) {
            stmts.push(self.parse_stmt()?);
        }
        self.expect(&TokenKind::RBrace, "`}`")?;
        Ok(stmts)
    }

    fn parse_type(&mut self) -> TResult<String> {
        match &self.peek().kind {
            TokenKind::IntType => {
                self.advance();
                Ok(T_INT.to_string())
            }
            TokenKind::FloatType => {
                self.advance();
                Ok(T_FLOAT.to_string())
            }
            TokenKind::BoolType => {
                self.advance();
                Ok(T_BOOL.to_string())
            }
            TokenKind::StrType => {
                self.advance();
                Ok(T_STR.to_string())
            }
            _ => Err(self.error(format!(
                "期望类型 `int` / `float` / `bool` / `string`，但遇到 {}",
                self.peek().kind.describe()
            ))),
        }
    }

    fn expect_ident(&mut self, what: &str) -> TResult<String> {
        match self.peek().kind.clone() {
            TokenKind::Ident(name) => {
                self.advance();
                Ok(name)
            }
            _ => Err(self.error(format!("期望 {what}，但遇到 {}", self.peek().kind.describe()))),
        }
    }

    // ---- 表达式（优先级爬升）----

    fn binary_info(kind: &TokenKind) -> Option<(&'static str, u8)> {
        let info = match kind {
            TokenKind::Or => (OP_OR, 1),
            TokenKind::And => (OP_AND, 2),
            TokenKind::Eq => (OP_EQ, 3),
            TokenKind::NotEq => (OP_NEQ, 3),
            TokenKind::Lt => (OP_LT, 4),
            TokenKind::LtEq => (OP_LTE, 4),
            TokenKind::Gt => (OP_GT, 4),
            TokenKind::GtEq => (OP_GTE, 4),
            TokenKind::Plus => (OP_ADD, 5),
            TokenKind::Minus => (OP_SUB, 5),
            TokenKind::Star => (OP_MUL, 6),
            TokenKind::Slash => (OP_DIV, 6),
            TokenKind::Percent => (OP_MOD, 6),
            _ => return None,
        };
        Some(info)
    }

    fn parse_expr(&mut self) -> TResult<Expr> {
        self.parse_binary(0)
    }

    fn parse_binary(&mut self, min_prec: u8) -> TResult<Expr> {
        let mut lhs = self.parse_unary()?;
        loop {
            let Some((op, prec)) = Self::binary_info(&self.peek().kind) else {
                break;
            };
            if prec < min_prec {
                break;
            }
            self.advance();
            let rhs = self.parse_binary(prec + 1)?;
            let pos = lhs.pos.clone();
            lhs = Expr {
                pos,
                kind: ExprKind::Binary {
                    op,
                    lhs: Box::new(lhs),
                    rhs: Box::new(rhs),
                },
            };
        }
        Ok(lhs)
    }

    fn parse_unary(&mut self) -> TResult<Expr> {
        let op = match &self.peek().kind {
            TokenKind::Minus => Some(OP_NEG),
            TokenKind::Not => Some(OP_NOT),
            _ => None,
        };
        if let Some(op) = op {
            let pos = self.peek().pos.clone();
            self.advance();
            let expr = self.parse_unary()?;
            return Ok(Expr {
                pos,
                kind: ExprKind::Unary {
                    op,
                    expr: Box::new(expr),
                },
            });
        }
        self.parse_primary()
    }

    fn parse_primary(&mut self) -> TResult<Expr> {
        let tok = self.peek().clone();
        let pos = tok.pos.clone();
        match &tok.kind {
            TokenKind::Int(v) => {
                self.advance();
                Ok(Expr {
                    pos,
                    kind: ExprKind::Int(*v),
                })
            }
            TokenKind::Float(v) => {
                self.advance();
                Ok(Expr {
                    pos,
                    kind: ExprKind::Float(*v),
                })
            }
            TokenKind::Str(s) => {
                self.advance();
                Ok(Expr {
                    pos,
                    kind: ExprKind::Str(s.clone()),
                })
            }
            TokenKind::True => {
                self.advance();
                Ok(Expr {
                    pos,
                    kind: ExprKind::Bool(true),
                })
            }
            TokenKind::False => {
                self.advance();
                Ok(Expr {
                    pos,
                    kind: ExprKind::Bool(false),
                })
            }
            TokenKind::Ident(name) => {
                self.advance();
                if self.check(&TokenKind::LParen) {
                    self.parse_call_args(name.clone(), pos)
                } else if self.check(&TokenKind::Assign) {
                    self.advance();
                    let value = self.parse_expr()?;
                    Ok(Expr {
                        pos,
                        kind: ExprKind::Assign {
                            name: name.clone(),
                            value: Box::new(value),
                        },
                    })
                } else {
                    Ok(Expr {
                        pos,
                        kind: ExprKind::Var(name.clone()),
                    })
                }
            }
            TokenKind::LParen => {
                self.advance();
                let expr = self.parse_expr()?;
                self.expect(&TokenKind::RParen, "`)`")?;
                Ok(expr)
            }
            _ => Err(self.error(format!(
                "期望一个表达式，但遇到 {}",
                tok.kind.describe()
            ))),
        }
    }

    fn parse_call_args(&mut self, callee: String, pos: Position) -> TResult<Expr> {
        self.advance();
        let mut args = Vec::new();
        if !self.check(&TokenKind::RParen) {
            loop {
                args.push(self.parse_expr()?);
                if !self.check(&TokenKind::Comma) {
                    break;
                }
                self.advance();
            }
        }
        self.expect(&TokenKind::RParen, "`)`")?;
        Ok(Expr {
            pos,
            kind: ExprKind::Call { callee, args },
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_ok(src: &str) -> Program {
        Parser::parse(src).unwrap()
    }

    #[test]
    fn let_declaration() {
        let prog = parse_ok("let x: int = 42;");
        match &prog.stmts[0].kind {
            StmtKind::Let { name, ty, value } => {
                assert_eq!(name, "x");
                assert_eq!(ty.as_deref(), Some(T_INT));
                assert_eq!(value.kind, ExprKind::Int(42));
            }
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn positions_recorded() {
        let prog = parse_ok("let x: int = 42;\nlet y = x + 1;");
        assert_eq!(prog.stmts[0].pos, Position::new(1, 1));
        let StmtKind::Let { value, .. } = &prog.stmts[1].kind else {
            panic!()
        };
        assert_eq!(value.pos, Position::new(2, 9)); // `x` 的起始列
        let ExprKind::Binary { lhs, .. } = &value.kind else {
            panic!()
        };
        assert_eq!(lhs.pos, Position::new(2, 9));
    }

    #[test]
    fn precedence() {
        let prog = parse_ok("let x: int = 1 + 2 * 3;");
        let StmtKind::Let { value, .. } = &prog.stmts[0].kind else {
            panic!()
        };
        let ExprKind::Binary { op: add, lhs, rhs } = &value.kind else {
            panic!()
        };
        assert_eq!(*add, OP_ADD);
        assert_eq!(lhs.kind, ExprKind::Int(1));
        let ExprKind::Binary { op: mul, .. } = &rhs.kind else {
            panic!()
        };
        assert_eq!(*mul, OP_MUL);
    }

    #[test]
    fn function_declaration() {
        let prog = parse_ok("fn add(a: int, b: int) -> int { return a + b; }");
        match &prog.stmts[0].kind {
            StmtKind::FnDecl {
                name,
                params,
                ret,
                body,
            } => {
                assert_eq!(name, "add");
                assert_eq!(
                    params,
                    &vec![("a".to_string(), T_INT.to_string()), ("b".to_string(), T_INT.to_string())]
                );
                assert_eq!(ret.as_deref(), Some(T_INT));
                assert_eq!(body.len(), 1);
            }
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn if_else_chain() {
        let prog = parse_ok(
            "if (x > 0) { print(1); } else if (x < 0) { print(-1); } else { print(0); }",
        );
        match &prog.stmts[0].kind {
            StmtKind::If {
                else_branch: Some(branch),
                ..
            } => match &branch[0].kind {
                StmtKind::If { .. } => {}
                other => panic!("unexpected {other:?}"),
            },
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn call_and_assignment() {
        let prog = parse_ok("x = f(1, 2);");
        match &prog.stmts[0].kind {
            StmtKind::Expr(Expr {
                kind: ExprKind::Assign { name, value },
                ..
            }) => {
                assert_eq!(name, "x");
                let ExprKind::Call { callee, args } = &value.kind else {
                    panic!()
                };
                assert_eq!(callee, "f");
                assert_eq!(args.len(), 2);
            }
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn syntax_errors() {
        assert!(Parser::parse("let x: int = 1").unwrap_err().message.contains("`;`"));
        assert!(Parser::parse("if x > 0 { }").unwrap_err().message.contains("`(`"));
    }
}
