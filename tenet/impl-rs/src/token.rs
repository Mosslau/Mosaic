//! 词法单元（Token）定义。
//!
//! 词法分析器的输出：带位置的 `Token` 流。每个 `Token` 由
//! `TokenKind`（种类 + 字面量载荷）与 `Position`（行列）组成。

use crate::error::Position;
pub use crate::error::Position as TokenPosition;

/// 词法单元种类。字面量（整数 / 浮点 / 字符串 / 标识符）携带载荷。
#[derive(Debug, Clone, PartialEq)]
pub enum TokenKind {
    // ---- 字面量 ----
    Int(i64),
    Float(f64),
    Str(String),
    Ident(String),

    // ---- 关键字 ----
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

    // ---- 符号 ----
    LParen,   // (
    RParen,   // )
    LBrace,   // {
    RBrace,   // }
    Comma,    // ,
    Colon,    // :
    Semi,     // ;
    Arrow,    // ->
    Assign,   // =
    Plus,     // +
    Minus,    // -
    Star,     // *
    Slash,    // /
    Percent,  // %
    Eq,       // ==
    NotEq,    // !=
    Lt,       // <
    LtEq,     // <=
    Gt,       // >
    GtEq,     // >=
    And,      // &&
    Or,       // ||
    Not,      // !

    Eof,
}

/// 带位置的词法单元。
#[derive(Debug, Clone, PartialEq)]
pub struct Token {
    pub kind: TokenKind,
    pub pos: Position,
}

impl TokenKind {
    /// 人类可读的名字，用于错误信息（如 "expected `;`, found `}`"）。
    pub fn describe(&self) -> String {
        match self {
            TokenKind::Int(_) => "整数".into(),
            TokenKind::Float(_) => "浮点数".into(),
            TokenKind::Str(_) => "字符串".into(),
            TokenKind::Ident(s) => format!("标识符 `{s}`"),
            TokenKind::Let => "`let`".into(),
            TokenKind::Fn => "`fn`".into(),
            TokenKind::If => "`if`".into(),
            TokenKind::Else => "`else`".into(),
            TokenKind::While => "`while`".into(),
            TokenKind::Return => "`return`".into(),
            TokenKind::Break => "`break`".into(),
            TokenKind::True => "`true`".into(),
            TokenKind::False => "`false`".into(),
            TokenKind::IntType => "类型 `int`".into(),
            TokenKind::FloatType => "类型 `float`".into(),
            TokenKind::BoolType => "类型 `bool`".into(),
            TokenKind::StrType => "类型 `string`".into(),
            TokenKind::LParen => "`(`".into(),
            TokenKind::RParen => "`)`".into(),
            TokenKind::LBrace => "`{`".into(),
            TokenKind::RBrace => "`}`".into(),
            TokenKind::Comma => "`,`".into(),
            TokenKind::Colon => "`:`".into(),
            TokenKind::Semi => "`;`".into(),
            TokenKind::Arrow => "`->`".into(),
            TokenKind::Assign => "`=`".into(),
            TokenKind::Plus => "`+`".into(),
            TokenKind::Minus => "`-`".into(),
            TokenKind::Star => "`*`".into(),
            TokenKind::Slash => "`/`".into(),
            TokenKind::Percent => "`%`".into(),
            TokenKind::Eq => "`==`".into(),
            TokenKind::NotEq => "`!=`".into(),
            TokenKind::Lt => "`<`".into(),
            TokenKind::LtEq => "`<=`".into(),
            TokenKind::Gt => "`>`".into(),
            TokenKind::GtEq => "`>=`".into(),
            TokenKind::And => "`&&`".into(),
            TokenKind::Or => "`||`".into(),
            TokenKind::Not => "`!`".into(),
            TokenKind::Eof => "文件末尾".into(),
        }
    }
}
