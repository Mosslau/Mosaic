//! 代码生成器（Codegen）：把 Tenet AST 编译成 Go 源码。
//!
//! 这是「源码到源码」的编译器前端：Tenet 是静态类型语言，因此
//! 可以一一映射到 Go——类型、语句、表达式几乎逐行对应：
//!
//! | Tenet | Go |
//! |-------|----|
//! | `int` / `float` / `bool` / `string` | `int64` / `float64` / `bool` / `string` |
//! | `let x: T = v;` | `var x T = v;` |
//! | `while (c) { }` | `for c { }`（Go 没有 while） |
//! | `print(...)` | `fmt.Println(...)` |
//! | `fn f(a: int) -> int { }` | `func f(a int64) int64 { }` |
//!
//! `let` 省略类型标注时，由 `infer_type` 静态推断（字面量、变量、
//! 运算规则、函数返回类型），与解释器的动态语义保持一致。

use std::collections::HashMap;

use crate::ast::{BinaryOp, Expr, Program, Stmt, Type, UnaryOp};
use crate::error::{TenetError, TResult};

/// 函数签名（代码生成阶段只需要返回类型用于推断）。
struct FnSig {
    ret: Option<Type>,
}

pub struct GoCodegen {
    out: String,
    indent: usize,
    /// 当前作用域内可见的变量类型。
    symbols: HashMap<String, Type>,
    /// 全局函数签名表。
    functions: HashMap<String, FnSig>,
}

impl GoCodegen {
    pub fn new() -> Self {
        Self {
            out: String::new(),
            indent: 0,
            symbols: HashMap::new(),
            functions: HashMap::new(),
        }
    }

    /// 顶层入口：整个程序 → Go 源码字符串。
    pub fn generate(program: &Program) -> TResult<String> {
        let mut gen = GoCodegen::new();
        gen.collect_signatures(program)?;
        gen.emit_program(program)?;
        Ok(gen.out)
    }

    // ---- 预处理 ----

    /// 第一遍：收集所有函数签名（用于调用表达式推断返回类型）。
    fn collect_signatures(&mut self, program: &Program) -> TResult<()> {
        for stmt in &program.stmts {
            if let Stmt::FnDecl {
                name,
                ret,
                ..
            } = stmt
            {
                if self.functions.contains_key(name) {
                    return Err(TenetError::new(format!("函数 `{name}` 重复定义"), None));
                }
                self.functions.insert(
                    name.clone(),
                    FnSig {
                        ret: *ret,
                    },
                );
            }
        }
        Ok(())
    }

    // ---- 顶层 ----

    fn emit_program(&mut self, program: &Program) -> TResult<()> {
        self.push("package main");
        self.push("");

        // 是否用到 print（决定是否 import fmt）
        if program_uses_print(program) {
            self.push("import \"fmt\"");
            self.push("");
        }

        // 函数声明 → 包级 func
        for stmt in &program.stmts {
            if let Stmt::FnDecl { .. } = stmt {
                self.emit_stmt(stmt)?;
                self.push("");
            }
        }

        // 其余顶层语句 → main
        self.push("func main() {");
        self.indent += 1;
        for stmt in &program.stmts {
            if !matches!(stmt, Stmt::FnDecl { .. }) {
                self.emit_stmt(stmt)?;
            }
        }
        self.indent -= 1;
        self.push("}");
        Ok(())
    }

    // ---- 语句 ----

    fn emit_stmt(&mut self, stmt: &Stmt) -> TResult<()> {
        match stmt {
            Stmt::Let { name, ty, value } => {
                let t = match ty {
                    Some(t) => *t,
                    None => self
                        .infer_type(value)?
                        .ok_or_else(|| {
                            TenetError::new(format!("无法推断 `{name}` 的类型，请显式标注"), None)
                        })?,
                };
                self.symbols.insert(name.clone(), t);
                let val = self.emit_expr(value)?;
                self.push(&format!("var {name} {} = {val};", go_type(t)));
            }
            Stmt::Expr(expr) => match expr {
                Expr::Call { callee, args } => {
                    let args = self.emit_args(args)?;
                    if callee == "print" {
                        self.push(&format!("fmt.Println({});", args.join(", ")));
                    } else {
                        self.push(&format!("{callee}({});", args.join(", ")));
                    }
                }
                Expr::Assign { name, value } => {
                    let val = self.emit_expr(value)?;
                    self.push(&format!("{name} = {val};"));
                }
                _ => return Err(TenetError::new("语句必须是函数调用或赋值", None)),
            },
            Stmt::If {
                cond,
                then_branch,
                else_branch,
            } => self.emit_if(cond, then_branch, else_branch, "")?,
            Stmt::While { cond, body } => {
                let c = self.emit_expr(cond)?;
                self.push(&format!("for {c} {{"));
                self.indent += 1;
                for s in body {
                    self.emit_stmt(s)?;
                }
                self.indent -= 1;
                self.push("}");
            }
            Stmt::Return(expr) => match expr {
                Some(e) => {
                    let val = self.emit_expr(e)?;
                    self.push(&format!("return {val};"));
                }
                None => self.push("return;"),
            },
            Stmt::Break => self.push("break;"),
            Stmt::Block(stmts) => {
                self.push("{");
                self.indent += 1;
                for s in stmts {
                    self.emit_stmt(s)?;
                }
                self.indent -= 1;
                self.push("}");
            }
            Stmt::FnDecl {
                name,
                params,
                ret,
                body,
            } => {
                let sig_params: Vec<String> =
                    params.iter().map(|(n, t)| format!("{n} {}", go_type(*t))).collect();
                let ret = ret.map(go_type).unwrap_or_default();
                let sig = if ret.is_empty() {
                    format!("{name}({})", sig_params.join(", "))
                } else {
                    format!("{name}({}) {ret}", sig_params.join(", "))
                };
                self.push(&format!("func {sig} {{"));
                self.indent += 1;
                // 参数进入符号表（函数体结束后恢复）
                let saved = self.symbols.clone();
                for (n, t) in params {
                    self.symbols.insert(n.clone(), *t);
                }
                for s in body {
                    self.emit_stmt(s)?;
                }
                self.indent -= 1;
                self.push("}");
                self.symbols = saved;
            }
        }
        Ok(())
    }

    /// 发射 if 语句；`prefix` 用于 `} else if` 的续行拼接。
    fn emit_if(
        &mut self,
        cond: &Expr,
        then_branch: &[Stmt],
        else_branch: &Option<Vec<Stmt>>,
        prefix: &str,
    ) -> TResult<()> {
        let c = self.emit_expr(cond)?;
        self.push(&format!("{prefix}if {c} {{"));
        self.indent += 1;
        for s in then_branch {
            self.emit_stmt(s)?;
        }
        self.indent -= 1;
        match else_branch {
            // else if 链：单条 if 语句的 else 分支 → Go 的 `} else if ...`
            Some(branch) if branch.len() == 1 && matches!(branch[0], Stmt::If { .. }) => {
                if let Stmt::If {
                    cond,
                    then_branch,
                    else_branch,
                } = &branch[0]
                {
                    self.emit_if(cond, then_branch, else_branch, "} else ")?;
                }
            }
            Some(branch) => {
                self.push("} else {");
                self.indent += 1;
                for s in branch {
                    self.emit_stmt(s)?;
                }
                self.indent -= 1;
                self.push("}");
            }
            None => self.push("}"),
        }
        Ok(())
    }

    // ---- 表达式 ----

    fn emit_expr(&mut self, expr: &Expr) -> TResult<String> {
        Ok(match expr {
            Expr::Int(v) => v.to_string(),
            Expr::Float(v) => {
                // Rust 的 f64 Display 会把 2.0 打印成 "2"，会丢失浮点语义，
                // 因此强制补上小数点：2.0 → "2.0"
                let s = v.to_string();
                if s.contains('.') {
                    s
                } else {
                    format!("{s}.0")
                }
            }
            Expr::Str(s) => go_string(s),
            Expr::Bool(b) => b.to_string(),
            Expr::Var(name) => name.clone(),
            Expr::Assign { name, value } => {
                let val = self.emit_expr(value)?;
                format!("{name} = {val}")
            }
            Expr::Unary { op, expr } => {
                let inner = self.emit_expr(expr)?;
                match op {
                    UnaryOp::Neg => format!("-{inner}"),
                    UnaryOp::Not => format!("!{inner}"),
                }
            }
            Expr::Binary { op, lhs, rhs } => {
                let l = self.emit_expr(lhs)?;
                let r = self.emit_expr(rhs)?;
                format!("({l} {} {r})", go_binop(*op))
            }
            Expr::Call { callee, args } => {
                let args = self.emit_args(args)?;
                if callee == "print" {
                    format!("fmt.Println({})", args.join(", "))
                } else {
                    format!("{callee}({})", args.join(", "))
                }
            }
        })
    }

    fn emit_args(&mut self, args: &[Expr]) -> TResult<Vec<String>> {
        args.iter().map(|a| self.emit_expr(a)).collect()
    }

    // ---- 类型推断（与解释器语义对齐）----

    fn infer_type(&self, expr: &Expr) -> TResult<Option<Type>> {
        Ok(match expr {
            Expr::Int(_) => Some(Type::Int),
            Expr::Float(_) => Some(Type::Float),
            Expr::Str(_) => Some(Type::Str),
            Expr::Bool(_) => Some(Type::Bool),
            Expr::Var(name) => self.symbols.get(name).copied(),
            Expr::Assign { name, .. } => self.symbols.get(name).copied(),
            Expr::Unary { op, expr } => match op {
                UnaryOp::Not => Some(Type::Bool),
                UnaryOp::Neg => match self.infer_type(expr)? {
                    Some(Type::Int) => Some(Type::Int),
                    Some(Type::Float) => Some(Type::Float),
                    _ => None,
                },
            },
            Expr::Binary { op, lhs, rhs } => {
                let lt = self.infer_type(lhs)?;
                let rt = self.infer_type(rhs)?;
                match op {
                    BinaryOp::And | BinaryOp::Or => Some(Type::Bool),
                    BinaryOp::Eq
                    | BinaryOp::NotEq
                    | BinaryOp::Lt
                    | BinaryOp::LtEq
                    | BinaryOp::Gt
                    | BinaryOp::GtEq => Some(Type::Bool),
                    BinaryOp::Mod => {
                        if lt == Some(Type::Int) && rt == Some(Type::Int) {
                            Some(Type::Int)
                        } else {
                            None
                        }
                    }
                    BinaryOp::Add => match (lt, rt) {
                        (Some(Type::Str), Some(Type::Str)) => Some(Type::Str),
                        (Some(Type::Float), _) | (_, Some(Type::Float)) => Some(Type::Float),
                        (Some(Type::Int), Some(Type::Int)) => Some(Type::Int),
                        _ => None,
                    },
                    BinaryOp::Sub | BinaryOp::Mul | BinaryOp::Div => match (lt, rt) {
                        (Some(Type::Float), _) | (_, Some(Type::Float)) => Some(Type::Float),
                        (Some(Type::Int), Some(Type::Int)) => Some(Type::Int),
                        _ => None,
                    },
                }
            }
            Expr::Call { callee, .. } => self.functions.get(callee).and_then(|s| s.ret),
        })
    }
}

// ---- 输出辅助 ----

impl GoCodegen {
    fn push(&mut self, line: &str) {
        if line.is_empty() {
            self.out.push('\n');
            return;
        }
        for _ in 0..self.indent {
            self.out.push('\t');
        }
        self.out.push_str(line);
        self.out.push('\n');
    }
}

// ---- 映射辅助 ----

fn go_type(t: Type) -> &'static str {
    match t {
        Type::Int => "int64",
        Type::Float => "float64",
        Type::Bool => "bool",
        Type::Str => "string",
    }
}

fn go_binop(op: BinaryOp) -> &'static str {
    match op {
        BinaryOp::Add => "+",
        BinaryOp::Sub => "-",
        BinaryOp::Mul => "*",
        BinaryOp::Div => "/",
        BinaryOp::Mod => "%",
        BinaryOp::Eq => "==",
        BinaryOp::NotEq => "!=",
        BinaryOp::Lt => "<",
        BinaryOp::LtEq => "<=",
        BinaryOp::Gt => ">",
        BinaryOp::GtEq => ">=",
        BinaryOp::And => "&&",
        BinaryOp::Or => "||",
    }
}

/// 把 Tenet 字符串转成 Go 字符串字面量。
fn go_string(s: &str) -> String {
    let mut out = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\t' => out.push_str("\\t"),
            '\r' => out.push_str("\\r"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\x{:02x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// 扫描整个程序是否调用 `print`（决定是否生成 `import "fmt"`）。
fn program_uses_print(program: &Program) -> bool {
    fn stmt_uses_print(stmts: &[Stmt]) -> bool {
        stmts.iter().any(stmt_uses_print_one)
    }
    fn stmt_uses_print_one(stmt: &Stmt) -> bool {
        match stmt {
            Stmt::Expr(expr) | Stmt::Let { value: expr, .. } | Stmt::Return(Some(expr)) => {
                expr_uses_print(expr)
            }
            Stmt::If {
                cond,
                then_branch,
                else_branch,
            } => {
                expr_uses_print(cond)
                    || stmt_uses_print(then_branch)
                    || else_branch.as_deref().map_or(false, stmt_uses_print)
            }
            Stmt::While { cond, body } => expr_uses_print(cond) || stmt_uses_print(body),
            Stmt::FnDecl { body, .. } => stmt_uses_print(body),
            Stmt::Block(stmts) => stmt_uses_print(stmts),
            Stmt::Return(None) | Stmt::Break => false,
        }
    }
    fn expr_uses_print(expr: &Expr) -> bool {
        match expr {
            Expr::Call { callee, args } => callee == "print" || args.iter().any(expr_uses_print),
            Expr::Assign { value, .. } => expr_uses_print(value),
            Expr::Unary { expr, .. } => expr_uses_print(expr),
            Expr::Binary { lhs, rhs, .. } => expr_uses_print(lhs) || expr_uses_print(rhs),
            _ => false,
        }
    }
    stmt_uses_print(&program.stmts)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser::Parser;

    fn gen(src: &str) -> TResult<String> {
        let prog = Parser::parse(src)?;
        GoCodegen::generate(&prog)
    }

    #[test]
    fn hello_world() {
        let out = gen("print(\"hello\");").unwrap();
        assert!(out.contains("package main"), "{out}");
        assert!(out.contains("import \"fmt\""), "{out}");
        assert!(out.contains("func main()"), "{out}");
        assert!(out.contains("fmt.Println(\"hello\")"), "{out}");
    }

    #[test]
    fn no_print_no_fmt_import() {
        let out = gen("let x: int = 1;").unwrap();
        assert!(!out.contains("import"), "{out}");
    }

    #[test]
    fn let_with_annotation() {
        let out = gen("let x: int = 42; let s: string = \"hi\";").unwrap();
        assert!(out.contains("var x int64 = 42;"), "{out}");
        assert!(out.contains("var s string = \"hi\";"), "{out}");
    }

    #[test]
    fn let_type_inference() {
        let out = gen("let x = 1 + 2.5;").unwrap();
        assert!(out.contains("var x float64 = (1 + 2.5);"), "{out}");
    }

    #[test]
    fn inference_from_function_return() {
        let out = gen("fn f() -> int { return 1; } let x = f();").unwrap();
        assert!(out.contains("var x int64 = f();"), "{out}");
    }

    #[test]
    fn while_becomes_for() {
        let out = gen("while (x < 10) { x = x + 1; }").unwrap();
        assert!(out.contains("for (x < 10) {"), "{out}");
    }

    #[test]
    fn function_decl() {
        let out = gen("fn add(a: int, b: int) -> int { return a + b; }").unwrap();
        assert!(out.contains("func add(a int64, b int64) int64 {"), "{out}");
        assert!(out.contains("return (a + b);"), "{out}");
    }

    #[test]
    fn void_function() {
        let out = gen("fn greet() { print(\"hi\"); }").unwrap();
        assert!(out.contains("func greet() {"), "{out}");
        assert!(!out.contains("func greet()  {"), "{out}");
    }

    #[test]
    fn else_if_chain() {
        let out = gen(
            "if (x > 0) { print(1); } else if (x < 0) { print(-1); } else { print(0); }",
        )
        .unwrap();
        assert!(out.contains("} else if (x < 0) {"), "{out}");
        assert!(out.contains("} else {"), "{out}");
    }

    #[test]
    fn string_escaping() {
        let out = gen("print(\"a\\n\\\"b\\\"\");").unwrap();
        assert!(out.contains("fmt.Println(\"a\\n\\\"b\\\"\")"), "{out}");
    }

    #[test]
    fn print_inside_function_triggers_import() {
        let out = gen("fn f() { print(1); }").unwrap();
        assert!(out.contains("import \"fmt\""), "{out}");
    }

    #[test]
    fn float_literal_keeps_decimal_point() {
        // Rust 的 f64 Display 会把 2.0 打印成 "2"，代码生成必须补回小数点，
        // 否则 Go 里 7 / 2.0 会变成整数除法 7 / 2
        let out = gen("print(7 / 2.0);").unwrap();
        assert!(out.contains("(7 / 2.0)"), "{out}");
    }

    #[test]
    fn cannot_infer_type_errors() {
        // 无返回类型的函数调用无法推断类型
        let err = gen("fn f() { } let x = f();").unwrap_err();
        assert!(err.message.contains("无法推断"), "{}", err);
    }
}
