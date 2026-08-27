//! 语法分析器（Parser）：递归下降 + 优先级爬升，把 Token 流变成 AST。
//!
//! 优先级（低 → 高）：
//! ```text
//! ||  <  &&  <  == !=  <  < <= > >=  <  + -  <  * / %  <  一元 - !
//! ```

use crate::ast::{BinaryOp, Expr, Program, Stmt, Type, UnaryOp};
use crate::error::{TenetError, TResult};
use crate::token::{Token, TokenKind};

pub struct Parser {
    tokens: Vec<Token>,
    pos: usize,
}

impl Parser {
    pub fn new(tokens: Vec<Token>) -> Self {
        Self { tokens, pos: 0 }
    }

    /// 解析完整程序。
    pub fn parse(source: &str) -> TResult<Program> {
        let tokens = crate::lexer::Lexer::tokenize(source)?;
        let mut parser = Parser::new(tokens);
        let program = parser.parse_program()?;
        Ok(program)
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
        let pos = self.peek().pos.clone();
        TenetError::at_pos(message, pos)
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
        match &self.peek().kind {
            TokenKind::Let => self.parse_let(),
            TokenKind::Fn => self.parse_fn_decl(),
            TokenKind::If => self.parse_if(),
            TokenKind::While => self.parse_while(),
            TokenKind::Return => self.parse_return(),
            TokenKind::Break => {
                self.advance();
                self.expect(&TokenKind::Semi, "`;`")?;
                Ok(Stmt::Break)
            }
            TokenKind::LBrace => Ok(Stmt::Block(self.parse_block()?)),
            _ => {
                let expr = self.parse_expr()?;
                self.expect(&TokenKind::Semi, "`;`")?;
                Ok(Stmt::Expr(expr))
            }
        }
    }

    fn parse_let(&mut self) -> TResult<Stmt> {
        self.advance(); // let
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
        Ok(Stmt::Let { name, ty, value })
    }

    fn parse_fn_decl(&mut self) -> TResult<Stmt> {
        self.advance(); // fn
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
        Ok(Stmt::FnDecl {
            name,
            params,
            ret,
            body,
        })
    }

    fn parse_if(&mut self) -> TResult<Stmt> {
        self.advance(); // if
        self.expect(&TokenKind::LParen, "`(`")?;
        let cond = self.parse_expr()?;
        self.expect(&TokenKind::RParen, "`)`")?;
        let then_branch = self.parse_block()?;
        let else_branch = if self.check(&TokenKind::Else) {
            self.advance();
            if self.check(&TokenKind::If) {
                // else if 链：嵌套一个 if 语句
                let nested = self.parse_if()?;
                Some(vec![nested])
            } else {
                Some(self.parse_block()?)
            }
        } else {
            None
        };
        Ok(Stmt::If {
            cond,
            then_branch,
            else_branch,
        })
    }

    fn parse_while(&mut self) -> TResult<Stmt> {
        self.advance(); // while
        self.expect(&TokenKind::LParen, "`(`")?;
        let cond = self.parse_expr()?;
        self.expect(&TokenKind::RParen, "`)`")?;
        let body = self.parse_block()?;
        Ok(Stmt::While { cond, body })
    }

    fn parse_return(&mut self) -> TResult<Stmt> {
        self.advance(); // return
        if self.check(&TokenKind::Semi) {
            self.advance();
            Ok(Stmt::Return(None))
        } else {
            let expr = self.parse_expr()?;
            self.expect(&TokenKind::Semi, "`;`")?;
            Ok(Stmt::Return(Some(expr)))
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

    fn parse_type(&mut self) -> TResult<Type> {
        match &self.peek().kind {
            TokenKind::IntType => {
                self.advance();
                Ok(Type::Int)
            }
            TokenKind::FloatType => {
                self.advance();
                Ok(Type::Float)
            }
            TokenKind::BoolType => {
                self.advance();
                Ok(Type::Bool)
            }
            TokenKind::StrType => {
                self.advance();
                Ok(Type::Str)
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

    fn parse_expr(&mut self) -> TResult<Expr> {
        self.parse_binary(0)
    }

    /// 二元运算优先级表：返回 `(操作符, 优先级)`，优先级数字越大越紧。
    fn binary_info(kind: &TokenKind) -> Option<(BinaryOp, u8)> {
        let info = match kind {
            TokenKind::Or => (BinaryOp::Or, 1),
            TokenKind::And => (BinaryOp::And, 2),
            TokenKind::Eq => (BinaryOp::Eq, 3),
            TokenKind::NotEq => (BinaryOp::NotEq, 3),
            TokenKind::Lt => (BinaryOp::Lt, 4),
            TokenKind::LtEq => (BinaryOp::LtEq, 4),
            TokenKind::Gt => (BinaryOp::Gt, 4),
            TokenKind::GtEq => (BinaryOp::GtEq, 4),
            TokenKind::Plus => (BinaryOp::Add, 5),
            TokenKind::Minus => (BinaryOp::Sub, 5),
            TokenKind::Star => (BinaryOp::Mul, 6),
            TokenKind::Slash => (BinaryOp::Div, 6),
            TokenKind::Percent => (BinaryOp::Mod, 6),
            _ => return None,
        };
        Some(info)
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
            lhs = Expr::Binary {
                op,
                lhs: Box::new(lhs),
                rhs: Box::new(rhs),
            };
        }
        Ok(lhs)
    }

    fn parse_unary(&mut self) -> TResult<Expr> {
        let op = match &self.peek().kind {
            TokenKind::Minus => Some(UnaryOp::Neg),
            TokenKind::Not => Some(UnaryOp::Not),
            _ => None,
        };
        if let Some(op) = op {
            self.advance();
            let expr = self.parse_unary()?;
            return Ok(Expr::Unary {
                op,
                expr: Box::new(expr),
            });
        }
        self.parse_primary()
    }

    fn parse_primary(&mut self) -> TResult<Expr> {
        let tok = self.peek().clone();
        match &tok.kind {
            TokenKind::Int(v) => {
                self.advance();
                Ok(Expr::Int(*v))
            }
            TokenKind::Float(v) => {
                self.advance();
                Ok(Expr::Float(*v))
            }
            TokenKind::Str(s) => {
                self.advance();
                Ok(Expr::Str(s.clone()))
            }
            TokenKind::True => {
                self.advance();
                Ok(Expr::Bool(true))
            }
            TokenKind::False => {
                self.advance();
                Ok(Expr::Bool(false))
            }
            TokenKind::Ident(name) => {
                self.advance();
                if self.check(&TokenKind::LParen) {
                    self.parse_call_args(name.clone())
                } else if self.check(&TokenKind::Assign) {
                    self.advance();
                    let value = self.parse_expr()?;
                    Ok(Expr::Assign {
                        name: name.clone(),
                        value: Box::new(value),
                    })
                } else {
                    Ok(Expr::Var(name.clone()))
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

    fn parse_call_args(&mut self, callee: String) -> TResult<Expr> {
        self.advance(); // (
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
        Ok(Expr::Call { callee, args })
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
        match &prog.stmts[0] {
            Stmt::Let { name, ty, value } => {
                assert_eq!(name, "x");
                assert_eq!(*ty, Some(Type::Int));
                assert_eq!(*value, Expr::Int(42));
            }
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn let_without_type() {
        let prog = parse_ok("let x = 3.14;");
        match &prog.stmts[0] {
            Stmt::Let { ty, .. } => assert_eq!(*ty, None),
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn precedence() {
        // 1 + 2 * 3 == 7 → 乘法先结合
        let prog = parse_ok("let x: int = 1 + 2 * 3;");
        let Stmt::Let { value, .. } = &prog.stmts[0] else {
            panic!()
        };
        let Expr::Binary { op: add, lhs, rhs } = value else {
            panic!("{value:?}")
        };
        assert_eq!(*add, BinaryOp::Add);
        assert_eq!(**lhs, Expr::Int(1));
        let Expr::Binary { op: mul, .. } = **rhs else {
            panic!()
        };
        assert_eq!(mul, BinaryOp::Mul);
    }

    #[test]
    fn comparison_chain_not_allowed() {
        // 2 < 3 < 4 按左结合解析为 (2 < 3) < 4，语义上运行时才会报错
        let prog = parse_ok("let x: bool = 2 < 3 < 4;");
        let Stmt::Let { value, .. } = &prog.stmts[0] else {
            panic!()
        };
        let Expr::Binary { op, .. } = value else {
            panic!()
        };
        assert_eq!(*op, BinaryOp::Lt);
    }

    #[test]
    fn unary_minus() {
        let prog = parse_ok("let x: int = -5;");
        let Stmt::Let { value, .. } = &prog.stmts[0] else {
            panic!()
        };
        assert_eq!(
            *value,
            Expr::Unary {
                op: UnaryOp::Neg,
                expr: Box::new(Expr::Int(5))
            }
        );
    }

    #[test]
    fn function_declaration() {
        let prog = parse_ok("fn add(a: int, b: int) -> int { return a + b; }");
        match &prog.stmts[0] {
            Stmt::FnDecl {
                name,
                params,
                ret,
                body,
            } => {
                assert_eq!(name, "add");
                assert_eq!(
                    params,
                    &vec![("a".to_string(), Type::Int), ("b".to_string(), Type::Int)]
                );
                assert_eq!(*ret, Some(Type::Int));
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
        match &prog.stmts[0] {
            Stmt::If {
                else_branch: Some(branch),
                ..
            } => match &branch[0] {
                Stmt::If { .. } => {}
                other => panic!("unexpected {other:?}"),
            },
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn call_and_assignment() {
        let prog = parse_ok("x = f(1, 2);");
        match &prog.stmts[0] {
            Stmt::Expr(Expr::Assign { name, value }) => {
                assert_eq!(name, "x");
                let Expr::Call { callee, args } = &**value else {
                    panic!()
                };
                assert_eq!(callee, "f");
                assert_eq!(args.len(), 2);
            }
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn missing_semicolon_errors() {
        let err = Parser::parse("let x: int = 1").unwrap_err();
        assert!(err.message.contains("`;`"), "{}", err);
    }

    #[test]
    fn missing_paren_errors() {
        let err = Parser::parse("if x > 0 { }").unwrap_err();
        assert!(err.message.contains("`(`"), "{}", err);
    }

    #[test]
    fn unexpected_token_errors() {
        let err = Parser::parse("let 1: int = 2;").unwrap_err();
        assert!(err.message.contains("变量名"), "{}", err);
    }
}
