//! 抽象语法树（AST）：语法分析器的输出，也是解释器与代码生成器的共同输入。

use crate::error::Position;

/// Tenet 的类型系统：只有 4 种标量类型。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Type {
    Int,
    Float,
    Bool,
    Str,
}

impl Type {
    pub fn name(&self) -> &'static str {
        match self {
            Type::Int => "int",
            Type::Float => "float",
            Type::Bool => "bool",
            Type::Str => "string",
        }
    }
}

/// 一元运算符。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UnaryOp {
    Neg, // -
    Not, // !
}

/// 二元运算符。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BinaryOp {
    Add,      // +
    Sub,      // -
    Mul,      // *
    Div,      // /
    Mod,      // %
    Eq,       // ==
    NotEq,    // !=
    Lt,       // <
    LtEq,     // <=
    Gt,       // >
    GtEq,     // >=
    And,      // &&
    Or,       // ||
}

/// 表达式。
#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Int(i64),
    Float(f64),
    Str(String),
    Bool(bool),
    Var(String),
    Assign { name: String, value: Box<Expr> },
    Unary { op: UnaryOp, expr: Box<Expr> },
    Binary { op: BinaryOp, lhs: Box<Expr>, rhs: Box<Expr> },
    Call { callee: String, args: Vec<Expr> },
}

/// 语句。
#[derive(Debug, Clone, PartialEq)]
pub enum Stmt {
    /// `let x: int = 42;`（类型标注可省略，由代码生成阶段推断）
    Let {
        name: String,
        ty: Option<Type>,
        value: Expr,
    },
    /// 表达式语句，如 `x = x + 1;` 或 `print("hi");`
    Expr(Expr),
    /// `if cond { ... } else { ... }`
    If {
        cond: Expr,
        then_branch: Vec<Stmt>,
        else_branch: Option<Vec<Stmt>>,
    },
    /// `while cond { ... }`
    While { cond: Expr, body: Vec<Stmt> },
    /// `return expr;` 或 `return;`
    Return(Option<Expr>),
    /// `break;` —— 只能出现在循环体内
    Break,
    /// 裸块语句 `{ ... }`：新建一个词法作用域
    Block(Vec<Stmt>),
    /// `fn name(a: int, b: float) -> int { ... }`
    FnDecl {
        name: String,
        params: Vec<(String, Type)>,
        ret: Option<Type>,
        body: Vec<Stmt>,
    },
}

/// 完整程序：顶层语句序列。
#[derive(Debug, Clone, PartialEq)]
pub struct Program {
    pub stmts: Vec<Stmt>,
}

/// 带位置的语句，供解释器 / 代码生成器定位报错。
#[derive(Debug, Clone)]
pub struct StmtNode {
    pub stmt: Stmt,
    pub pos: Position,
}
