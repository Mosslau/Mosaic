//! # Tenet 编译器
//!
//! clang / rustc 式原生编译器：前端自写（词法 → 语法 → 类型 → LLVM IR），
//! 后端复用 LLVM/clang 产出可直接运行的二进制。

pub mod ast;
pub mod codegen;
pub mod error;
pub mod lexer;
pub mod parser;
pub mod token;

pub use error::{TenetError, TResult};

/// 把 Tenet 源码编译为 LLVM IR。
pub fn compile_to_ir(src: &str) -> TResult<String> {
    let program = parser::Parser::parse(src)?;
    codegen::Codegen::generate(&program)
}
