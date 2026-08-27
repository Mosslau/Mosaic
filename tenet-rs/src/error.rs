//! Tenet 语言的统一错误类型：所有阶段（词法 / 语法 / 解释 / 代码生成）
//! 都通过 `TenetError` 上报，携带源码位置 `[行:列]`。

use std::fmt;

/// 源码位置：1 起始的行号与列号。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Position {
    pub line: usize,
    pub col: usize,
}

impl Position {
    pub fn new(line: usize, col: usize) -> Self {
        Self { line, col }
    }
}

/// 带可选位置的错误。
#[derive(Debug, Clone)]
pub struct TenetError {
    pub message: String,
    pub pos: Option<Position>,
}

impl TenetError {
    pub fn new(message: impl Into<String>, pos: Option<Position>) -> Self {
        Self {
            message: message.into(),
            pos,
        }
    }

    pub fn at(message: impl Into<String>, line: usize, col: usize) -> Self {
        Self::new(message, Some(Position::new(line, col)))
    }

    pub fn at_pos(message: impl Into<String>, pos: Position) -> Self {
        Self::new(message, Some(pos))
    }
}

impl fmt::Display for TenetError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match &self.pos {
            Some(p) => write!(f, "[{}:{}] {}", p.line, p.col, self.message),
            None => write!(f, "{}", self.message),
        }
    }
}

impl std::error::Error for TenetError {}

/// 统一的结果类型。
pub type TResult<T> = Result<T, TenetError>;
