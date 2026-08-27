//! # Tenet 语言
//!
//! 从零实现的小型语言，完整管线：
//!
//! ```text
//! Tenet 源码 → Lexer → Token 流 → Parser → AST → Interpreter（解释执行）
//!                                          └─→ Codegen → Go 源码
//! ```
//!
//! 纯标准库实现，无任何外部依赖。

pub mod ast;
pub mod codegen;
pub mod env;
pub mod error;
pub mod interpreter;
pub mod lexer;
pub mod parser;
pub mod repl;
pub mod token;
pub mod value;

pub use error::{TenetError, TResult};

/// 解释执行一段 Tenet 源码。
pub fn run_source(src: &str) -> TResult<()> {
    let program = parser::Parser::parse(src)?;
    interpreter::Interpreter::run(&program)
}

/// 把一段 Tenet 源码编译为 Go 源码。
pub fn codegen_source(src: &str) -> TResult<String> {
    let program = parser::Parser::parse(src)?;
    codegen::GoCodegen::generate(&program)
}
