//! 树遍历解释器（Tree-walking Interpreter）。
//!
//! 直接对 AST 求值：表达式递归求值返回 `Value`，语句递归执行产生副作用。
//! 控制流（`return` / `break`）通过 `Flow` 枚举向上传播。
//!
//! 函数以名字存放在全局函数表中；调用时新建参数作用域，
//! 函数体结束后作用域即丢弃——因此不需要闭包捕获。

use std::collections::HashMap;
use std::rc::Rc;

use crate::ast::{BinaryOp, Expr, Program, Stmt, Type};
use crate::env::Env;
use crate::error::{TenetError, TResult};
use crate::value::Value;

/// 用户自定义函数。
pub struct Function {
    pub name: String,
    pub params: Vec<(String, Type)>,
    pub ret: Option<Type>,
    pub body: Vec<Stmt>,
}

/// 语句执行后的控制流信号。
enum Flow {
    /// 正常继续执行下一条语句。
    Normal,
    /// 跳出当前循环（`break;`）。
    Break,
    /// 从函数返回，携带返回值（可能为 Nil）。
    Return(Value),
}

pub struct Interpreter {
    functions: HashMap<String, Rc<Function>>,
    global: Rc<Env>,
}

impl Interpreter {
    pub fn new() -> Self {
        Self {
            functions: HashMap::new(),
            global: Env::global(),
        }
    }

    /// 顶层入口：执行整个程序。
    pub fn run(program: &Program) -> TResult<()> {
        let mut interp = Interpreter::new();
        interp.run_program(program)
    }

    /// 在当前解释器实例上执行程序（REPL 复用同一实例，保留函数表）。
    pub fn run_program(&mut self, program: &Program) -> TResult<()> {
        let global = Rc::clone(&self.global);
        self.exec_block(&program.stmts, &global)?;
        Ok(())
    }

    /// 在全局环境中求值单个表达式（REPL 回显表达式值用）。
    pub fn eval_expr(&mut self, expr: &Expr) -> TResult<Value> {
        let global = Rc::clone(&self.global);
        self.eval(expr, &global)
    }

    /// 执行语句序列：**不**新建作用域，直接在给定环境中执行。
    /// 作用域只在块语句（`Stmt::Block`）、if / while 分支和函数调用处创建。
    fn exec_block(&mut self, stmts: &[Stmt], env: &Rc<Env>) -> TResult<Flow> {
        for stmt in stmts {
            let flow = self.exec_stmt(stmt, env)?;
            if !matches!(flow, Flow::Normal) {
                return Ok(flow);
            }
        }
        Ok(Flow::Normal)
    }

    fn exec_stmt(&mut self, stmt: &Stmt, env: &Rc<Env>) -> TResult<Flow> {
        match stmt {
            Stmt::Let { name, value, .. } => {
                let v = self.eval(value, env)?;
                env.define(name, v);
                Ok(Flow::Normal)
            }
            Stmt::Expr(expr) => {
                self.eval(expr, env)?;
                Ok(Flow::Normal)
            }
            Stmt::If {
                cond,
                then_branch,
                else_branch,
            } => {
                let c = self.eval(cond, env)?;
                let truthy = expect_bool(&c)?;
                let branch = if truthy { then_branch } else { else_branch.as_deref().unwrap_or(&[]) };
                // if 分支自身就是一个块：新建作用域
                let branch_env = Env::child(env);
                self.exec_block(branch, &branch_env)
            }
            Stmt::While { cond, body } => {
                let mut flow = Flow::Normal;
                loop {
                    let c = self.eval(cond, env)?;
                    if !expect_bool(&c)? {
                        break;
                    }
                    let body_env = Env::child(env);
                    flow = self.exec_block(body, &body_env)?;
                    if matches!(flow, Flow::Break) {
                        flow = Flow::Normal;
                        break;
                    }
                    if matches!(flow, Flow::Return(_)) {
                        break;
                    }
                }
                Ok(flow)
            }
            Stmt::Return(expr) => {
                let v = match expr {
                    Some(e) => self.eval(e, env)?,
                    None => Value::Nil,
                };
                Ok(Flow::Return(v))
            }
            Stmt::Break => Ok(Flow::Break),
            Stmt::Block(stmts) => {
                let child = Env::child(env);
                self.exec_block(stmts, &child)
            }
            Stmt::FnDecl {
                name,
                params,
                ret,
                body,
            } => {
                let f = Rc::new(Function {
                    name: name.clone(),
                    params: params.clone(),
                    ret: *ret,
                    body: body.clone(),
                });
                self.functions.insert(name.clone(), f);
                Ok(Flow::Normal)
            }
        }
    }

    fn eval(&mut self, expr: &Expr, env: &Rc<Env>) -> TResult<Value> {
        match expr {
            Expr::Int(v) => Ok(Value::Int(*v)),
            Expr::Float(v) => Ok(Value::Float(*v)),
            Expr::Str(s) => Ok(Value::Str(s.clone())),
            Expr::Bool(b) => Ok(Value::Bool(*b)),
            Expr::Var(name) => env.get(name),
            Expr::Assign { name, value } => {
                let v = self.eval(value, env)?;
                env.assign(name, v.clone())?;
                Ok(v)
            }
            Expr::Unary { op, expr } => {
                let v = self.eval(expr, env)?;
                v.apply_unary(*op)
            }
            Expr::Binary { op, lhs, rhs } => {
                // `&&` / `||` 短路求值：右侧只在需要时求值
                if *op == BinaryOp::And || *op == BinaryOp::Or {
                    let l = self.eval(lhs, env)?;
                    let lb = expect_bool(&l)?;
                    if *op == BinaryOp::And && !lb {
                        return Ok(Value::Bool(false));
                    }
                    if *op == BinaryOp::Or && lb {
                        return Ok(Value::Bool(true));
                    }
                    let r = self.eval(rhs, env)?;
                    let rb = expect_bool(&r)?;
                    return Ok(Value::Bool(rb));
                }
                let l = self.eval(lhs, env)?;
                let r = self.eval(rhs, env)?;
                l.apply_binary(*op, &r)
            }
            Expr::Call { callee, args } => self.call(callee, args, env),
        }
    }

    fn call(&mut self, callee: &str, args: &[Expr], env: &Rc<Env>) -> TResult<Value> {
        // 内建函数
        if let Some(builtin) = builtin(callee) {
            let mut values = Vec::with_capacity(args.len());
            for a in args {
                values.push(self.eval(a, env)?);
            }
            return (builtin)(&values);
        }

        // 用户函数
        let Some(f) = self.functions.get(callee).cloned() else {
            return Err(TenetError::new(format!("未定义的函数 `{callee}`"), None));
        };
        if f.params.len() != args.len() {
            return Err(TenetError::new(
                format!(
                    "函数 `{callee}` 需要 {} 个参数，实际传入 {} 个",
                    f.params.len(),
                    args.len()
                ),
                None,
            ));
        }

        // 参数作用域：父为全局环境（函数之间共享全局变量，但不捕获调用方局部变量）
        let call_env = Env::child(&self.global);
        for ((pname, pty), arg) in f.params.iter().zip(args) {
            let v = self.eval(arg, env)?;
            if !v.matches(*pty) {
                return Err(TenetError::new(
                    format!(
                        "参数 `{pname}` 期望类型 {}，实际传入 {}",
                        pty.name(),
                        v.type_name()
                    ),
                    None,
                ));
            }
            call_env.define(pname, v);
        }

        let flow = self.exec_block(&f.body, &call_env)?;
        match flow {
            Flow::Return(v) => {
                if let Some(ret) = f.ret {
                    if !v.matches(ret) && !matches!(v, Value::Nil) {
                        return Err(TenetError::new(
                            format!(
                                "函数 `{callee}` 返回类型期望 {}，实际返回 {}",
                                ret.name(),
                                v.type_name()
                            ),
                            None,
                        ));
                    }
                }
                Ok(v)
            }
            Flow::Break => Err(TenetError::new(
                format!("`break` 出现在函数 `{callee}` 的循环之外"),
                None,
            )),
            Flow::Normal => {
                if f.ret.is_some() {
                    Err(TenetError::new(
                        format!("函数 `{callee}` 声明了返回类型，但没有返回值"),
                        None,
                    ))
                } else {
                    Ok(Value::Nil)
                }
            }
        }
    }
}

/// 内建函数表：`print` 打印任意数量的值，以空格分隔并换行。
type Builtin = fn(&[Value]) -> TResult<Value>;

fn builtin(name: &str) -> Option<Builtin> {
    match name {
        "print" => Some(|args| {
            let parts: Vec<String> = args.iter().map(|v| v.to_string()).collect();
            println!("{}", parts.join(" "));
            Ok(Value::Nil)
        }),
        _ => None,
    }
}

fn expect_bool(v: &Value) -> TResult<bool> {
    match v {
        Value::Bool(b) => Ok(*b),
        other => Err(TenetError::new(
            format!("条件表达式需要 bool，实际为 {}", other.type_name()),
            None,
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser::Parser;

    fn run_src(src: &str) -> TResult<()> {
        let prog = Parser::parse(src)?;
        Interpreter::run(&prog)
    }

    #[test]
    fn arithmetic_and_precedence() {
        run_src("let x: int = 1 + 2 * 3; print(x);").unwrap();
        run_src("let x: float = 1 + 2.5; print(x);").unwrap();
        run_src("let x: int = 10 / 3; print(x);").unwrap();
        run_src("let x: float = 10 / 3.0; print(x);").unwrap();
    }

    #[test]
    fn integer_division_and_mod() {
        // 通过 print 输出验证（手工核对）
        run_src("print(7 / 2); print(7 % 2);").unwrap();
    }

    #[test]
    fn string_concat() {
        run_src("let s: string = \"a\" + \"b\" + \"c\"; print(s);").unwrap();
    }

    #[test]
    fn comparison_and_logic() {
        run_src("print(1 < 2); print(1 == 1.0); print(true && !false);").unwrap();
    }

    #[test]
    fn short_circuit_or() {
        // || 短路：右侧 1/0 不会求值，因此不报除零错
        run_src("let x: bool = true || (1 / 0 == 1); print(x);").unwrap();
    }

    #[test]
    fn assignment_updates_outer_scope() {
        run_src("let x: int = 1; { x = 2; } print(x);").unwrap();
    }

    #[test]
    fn block_scoping_shadows() {
        run_src("let x: int = 1; { let x: int = 2; print(x); } print(x);").unwrap();
    }

    #[test]
    fn if_else_and_while() {
        run_src(
            r#"
            let n: int = 10;
            let acc: int = 0;
            while (n > 0) {
                if (n % 2 == 0) { acc = acc + n; }
                n = n - 1;
            }
            print(acc);
            "#,
        )
        .unwrap();
    }

    #[test]
    fn break_exits_loop() {
        run_src(
            r#"
            let i: int = 0;
            while (true) {
                i = i + 1;
                if (i >= 5) { break; }
            }
            print(i);
            "#,
        )
        .unwrap();
    }

    #[test]
    fn recursion_fib() {
        run_src(
            r#"
            fn fib(n: int) -> int {
                if (n < 2) { return n; }
                return fib(n - 1) + fib(n - 2);
            }
            print(fib(10));
            "#,
        )
        .unwrap();
    }

    #[test]
    fn function_type_mismatch_errors() {
        let err = run_src("fn f(a: int) -> int { return a; } f(true);").unwrap_err();
        assert!(err.message.contains("参数"), "{}", err);
    }

    #[test]
    fn undefined_variable_errors() {
        let err = run_src("print(unknown_var);").unwrap_err();
        assert!(err.message.contains("未定义的变量"), "{}", err);
    }

    #[test]
    fn undefined_function_errors() {
        let err = run_src("no_such_fn(1);").unwrap_err();
        assert!(err.message.contains("未定义的函数"), "{}", err);
    }

    #[test]
    fn divide_by_zero_errors() {
        let err = run_src("let x: int = 1 / 0;").unwrap_err();
        assert!(err.message.contains("除以零"), "{}", err);
    }
}
