//! 抽象语法树（AST）：语法分析器的输出，代码生成器的输入。
//! 与十亿级编译器的 AST 设计一致：表达式/语句/程序。

use crate::error::Position;

// 类型常量
pub const T_INT: &str = "int";
pub const T_FLOAT: &str = "float";
pub const T_BOOL: &str = "bool";
pub const T_STR: &str = "string";

// 运算符常量
pub const OP_ADD: &str = "+";
pub const OP_SUB: &str = "-";
pub const OP_MUL: &str = "*";
pub const OP_DIV: &str = "/";
pub const OP_MOD: &str = "%";
pub const OP_EQ: &str = "==";
pub const OP_NEQ: &str = "!=";
pub const OP_LT: &str = "<";
pub const OP_LTE: &str = "<=";
pub const OP_GT: &str = ">";
pub const OP_GTE: &str = ">=";
pub const OP_AND: &str = "&&";
pub const OP_OR: &str = "||";
pub const OP_NEG: &str = "-";
pub const OP_NOT: &str = "!";

#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Int(i64),
    Float(f64),
    Str(String),
    Bool(bool),
    Var(String),
    Assign { name: String, value: Box<Expr> },
    Unary { op: &'static str, expr: Box<Expr> },
    Binary { op: &'static str, lhs: Box<Expr>, rhs: Box<Expr> },
    Call { callee: String, args: Vec<Expr> },
}

#[derive(Debug, Clone, PartialEq)]
pub enum Stmt {
    Let {
        name: String,
        ty: Option<String>,
        value: Expr,
    },
    Expr(Expr),
    If {
        cond: Expr,
        then_branch: Vec<Stmt>,
        else_branch: Option<Vec<Stmt>>,
    },
    While { cond: Expr, body: Vec<Stmt> },
    Return(Option<Expr>),
    Break,
    FnDecl {
        name: String,
        params: Vec<(String, String)>,
        ret: Option<String>,
        body: Vec<Stmt>,
    },
}

#[derive(Debug, Clone, PartialEq)]
pub struct Program {
    pub stmts: Vec<Stmt>,
}

/// 带位置的语句，供代码生成器定位报错。
#[derive(Debug, Clone)]
pub struct StmtNode {
    pub stmt: Stmt,
    pub pos: Position,
}
