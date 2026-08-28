//! 词法分析器（Lexer）：字符流 → Token 流。
//! 规则：最长匹配、i64 范围检查、转义序列、`[行:列]` 定位。

use crate::error::{TenetError, TResult};
use crate::error::Position;
use crate::token::{Token, TokenKind};

pub struct Lexer {
    src: Vec<char>,
    pos: usize,
    line: usize,
    col: usize,
}

impl Lexer {
    pub fn new(source: &str) -> Self {
        Self {
            src: source.chars().collect(),
            pos: 0,
            line: 1,
            col: 1,
        }
    }

    pub fn tokenize(source: &str) -> TResult<Vec<Token>> {
        let mut lexer = Lexer::new(source);
        let mut tokens = Vec::new();
        loop {
            let tok = lexer.next_token()?;
            let is_eof = tok.kind == TokenKind::Eof;
            tokens.push(tok);
            if is_eof {
                break;
            }
        }
        Ok(tokens)
    }

    fn peek(&self) -> Option<char> {
        self.src.get(self.pos).copied()
    }

    fn peek2(&self) -> Option<char> {
        self.src.get(self.pos + 1).copied()
    }

    fn advance(&mut self) -> Option<char> {
        let c = self.peek()?;
        self.pos += 1;
        if c == '\n' {
            self.line += 1;
            self.col = 1;
        } else {
            self.col += 1;
        }
        Some(c)
    }

    fn next_token(&mut self) -> TResult<Token> {
        self.skip_trivia();
        let (line, col) = (self.line, self.col);
        let make = |kind| Token {
            kind,
            pos: Position::new(line, col),
        };

        let Some(c) = self.peek() else {
            return Ok(make(TokenKind::Eof));
        };

        if c.is_ascii_digit() {
            return self.lex_number(line, col);
        }
        if c == '"' {
            return self.lex_string(line, col);
        }
        if c.is_alphabetic() || c == '_' {
            return self.lex_ident(line, col);
        }

        match (c, self.peek2()) {
            ('=', Some('=')) => {
                self.advance();
                self.advance();
                Ok(make(TokenKind::Eq))
            }
            ('!', Some('=')) => {
                self.advance();
                self.advance();
                Ok(make(TokenKind::NotEq))
            }
            ('<', Some('=')) => {
                self.advance();
                self.advance();
                Ok(make(TokenKind::LtEq))
            }
            ('>', Some('=')) => {
                self.advance();
                self.advance();
                Ok(make(TokenKind::GtEq))
            }
            ('&', Some('&')) => {
                self.advance();
                self.advance();
                Ok(make(TokenKind::And))
            }
            ('|', Some('|')) => {
                self.advance();
                self.advance();
                Ok(make(TokenKind::Or))
            }
            ('-', Some('>')) => {
                self.advance();
                self.advance();
                Ok(make(TokenKind::Arrow))
            }
            _ => self.lex_single(c, line, col),
        }
    }

    fn skip_trivia(&mut self) {
        loop {
            while matches!(self.peek(), Some(' ') | Some('\t') | Some('\r') | Some('\n')) {
                self.advance();
            }
            if self.peek() == Some('/') && self.peek2() == Some('/') {
                while let Some(c) = self.advance() {
                    if c == '\n' {
                        break;
                    }
                }
                continue;
            }
            if self.peek() == Some('/') && self.peek2() == Some('*') {
                self.advance();
                self.advance();
                loop {
                    match (self.peek(), self.peek2()) {
                        (Some('*'), Some('/')) => {
                            self.advance();
                            self.advance();
                            break;
                        }
                        (Some(_), _) => {
                            self.advance();
                        }
                        (None, _) => break,
                    }
                }
                continue;
            }
            break;
        }
    }

    fn lex_number(&mut self, line: usize, col: usize) -> TResult<Token> {
        let mut text = String::new();
        let mut is_float = false;
        while let Some(c) = self.peek() {
            if c.is_ascii_digit() {
                text.push(self.advance().unwrap());
            } else if c == '.' {
                is_float = true;
                text.push(self.advance().unwrap());
            } else {
                break;
            }
        }
        let kind = if is_float {
            TokenKind::Float(
                text.parse::<f64>()
                    .map_err(|_| TenetError::at("无效的浮点数", line, col))?,
            )
        } else {
            TokenKind::Int(
                text.parse::<i64>()
                    .map_err(|_| TenetError::at("整数超出 i64 范围", line, col))?,
            )
        };
        Ok(Token {
            kind,
            pos: Position::new(line, col),
        })
    }

    fn lex_string(&mut self, line: usize, col: usize) -> TResult<Token> {
        self.advance();
        let mut value = String::new();
        loop {
            let Some(c) = self.advance() else {
                return Err(TenetError::at("未闭合的字符串字面量", line, col));
            };
            match c {
                '"' => break,
                '\\' => {
                    let Some(esc) = self.advance() else {
                        return Err(TenetError::at("字符串以反斜杠结尾", line, col));
                    };
                    match esc {
                        'n' => value.push('\n'),
                        't' => value.push('\t'),
                        '"' => value.push('"'),
                        '\\' => value.push('\\'),
                        other => {
                            return Err(TenetError::at(
                                format!("未知的转义序列 `\\{other}`"),
                                line,
                                col,
                            ))
                        }
                    }
                }
                other => value.push(other),
            }
        }
        Ok(Token {
            kind: TokenKind::Str(value),
            pos: Position::new(line, col),
        })
    }

    fn lex_ident(&mut self, line: usize, col: usize) -> TResult<Token> {
        let mut text = String::new();
        while let Some(c) = self.peek() {
            if c.is_alphanumeric() || c == '_' {
                text.push(self.advance().unwrap());
            } else {
                break;
            }
        }
        let kind = match text.as_str() {
            "let" => TokenKind::Let,
            "fn" => TokenKind::Fn,
            "if" => TokenKind::If,
            "else" => TokenKind::Else,
            "while" => TokenKind::While,
            "return" => TokenKind::Return,
            "break" => TokenKind::Break,
            "true" => TokenKind::True,
            "false" => TokenKind::False,
            "int" => TokenKind::IntType,
            "float" => TokenKind::FloatType,
            "bool" => TokenKind::BoolType,
            "string" => TokenKind::StrType,
            _ => TokenKind::Ident(text),
        };
        Ok(Token {
            kind,
            pos: Position::new(line, col),
        })
    }

    fn lex_single(&mut self, c: char, line: usize, col: usize) -> TResult<Token> {
        self.advance();
        let kind = match c {
            '(' => TokenKind::LParen,
            ')' => TokenKind::RParen,
            '{' => TokenKind::LBrace,
            '}' => TokenKind::RBrace,
            ',' => TokenKind::Comma,
            ':' => TokenKind::Colon,
            ';' => TokenKind::Semi,
            '=' => TokenKind::Assign,
            '+' => TokenKind::Plus,
            '-' => TokenKind::Minus,
            '*' => TokenKind::Star,
            '/' => TokenKind::Slash,
            '%' => TokenKind::Percent,
            '<' => TokenKind::Lt,
            '>' => TokenKind::Gt,
            '!' => TokenKind::Not,
            other => {
                return Err(TenetError::at(
                    format!("无法识别的字符 `{other}`"),
                    line,
                    col,
                ))
            }
        };
        Ok(Token {
            kind,
            pos: Position::new(line, col),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn kinds(src: &str) -> Vec<TokenKind> {
        Lexer::tokenize(src)
            .unwrap()
            .into_iter()
            .map(|t| t.kind)
            .collect()
    }

    #[test]
    fn literals() {
        assert_eq!(
            kinds("42 3.14 \"hi\" true false"),
            vec![
                TokenKind::Int(42),
                TokenKind::Float(3.14),
                TokenKind::Str("hi".into()),
                TokenKind::True,
                TokenKind::False,
                TokenKind::Eof
            ]
        );
    }

    #[test]
    fn operators_longest_match() {
        assert_eq!(
            kinds("== != <= >= && || -> = < > !"),
            vec![
                TokenKind::Eq,
                TokenKind::NotEq,
                TokenKind::LtEq,
                TokenKind::GtEq,
                TokenKind::And,
                TokenKind::Or,
                TokenKind::Arrow,
                TokenKind::Assign,
                TokenKind::Lt,
                TokenKind::Gt,
                TokenKind::Not,
                TokenKind::Eof
            ]
        );
    }

    #[test]
    fn keywords_and_identifiers() {
        assert_eq!(
            kinds("let x: int = 1;"),
            vec![
                TokenKind::Let,
                TokenKind::Ident("x".into()),
                TokenKind::Colon,
                TokenKind::IntType,
                TokenKind::Assign,
                TokenKind::Int(1),
                TokenKind::Semi,
                TokenKind::Eof
            ]
        );
    }

    #[test]
    fn comments_skipped() {
        assert_eq!(
            kinds("1 // line\n + /* block */ 2"),
            vec![TokenKind::Int(1), TokenKind::Plus, TokenKind::Int(2), TokenKind::Eof]
        );
    }

    #[test]
    fn string_escapes() {
        assert_eq!(
            kinds(r#""a\nb\t\"c\\""#),
            vec![TokenKind::Str("a\nb\t\"c\\".into()), TokenKind::Eof]
        );
    }

    #[test]
    fn positions_tracked() {
        let toks = Lexer::tokenize("1 +\n2").unwrap();
        assert_eq!(toks[0].pos, Position::new(1, 1));
        assert_eq!(toks[1].pos, Position::new(1, 3));
        assert_eq!(toks[2].pos, Position::new(2, 1));
    }

    #[test]
    fn errors() {
        assert!(Lexer::tokenize("\"abc").unwrap_err().message.contains("未闭合"));
        assert!(Lexer::tokenize("1 @ 2").unwrap_err().message.contains("无法识别"));
    }
}
