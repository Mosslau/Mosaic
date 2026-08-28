//! LLVM IR 代码生成器：AST → LLVM IR（.ll）。
//!
//! 与 rustc 相同的架构：前端生成 LLVM IR，后端（clang/llc）产出机器码。
//!
//! 设计要点：
//! - 类型映射：int → i64，float → double，bool → i1，string → i8*
//! - 变量：alloca + load/store（内存模型），避免 phi 节点
//! - 控制流：基本块 + br（if/while/break/短路都翻译成跳转）
//! - 基本块终止跟踪：ret/br 后不再追加指令（LLVM 要求终止指令在块尾）
//! - print：编译期按参数类型拼 printf 格式串
//! - 字符串拼接/比较：调用运行时库（链接时编入 compiler 内置 runtime.c）

use std::collections::HashMap;

use crate::ast::{Expr, Program, Stmt, T_BOOL, T_FLOAT, T_INT, T_STR};
use crate::error::{TenetError, TResult};

/// LLVM 类型映射。
fn llvm_type(ty: &str) -> &'static str {
    match ty {
        T_INT => "i64",
        T_FLOAT => "double",
        T_BOOL => "i1",
        T_STR => "ptr",
        other => panic!("未知类型 {other}"),
    }
}

const COMPARE_OPS_INT: [(&str, &str); 6] = [
    (crate::ast::OP_EQ, "eq"),
    (crate::ast::OP_NEQ, "ne"),
    (crate::ast::OP_LT, "slt"),
    (crate::ast::OP_LTE, "sle"),
    (crate::ast::OP_GT, "sgt"),
    (crate::ast::OP_GTE, "sge"),
];

const COMPARE_OPS_FLOAT: [(&str, &str); 6] = [
    (crate::ast::OP_EQ, "oeq"),
    (crate::ast::OP_NEQ, "one"),
    (crate::ast::OP_LT, "olt"),
    (crate::ast::OP_LTE, "ole"),
    (crate::ast::OP_GT, "ogt"),
    (crate::ast::OP_GTE, "oge"),
];

pub struct Codegen {
    out: String,
    /// 字符串字面量全局常量声明（文件头输出）。
    globals: Vec<String>,
    string_counter: usize,
    /// 变量作用域栈：name -> (LLVM 类型, alloca 名)。
    symbols: Vec<HashMap<String, (String, String)>>,
    /// 函数签名：name -> 返回类型（None = void）。
    functions: HashMap<String, Option<String>>,
    /// 指令临时名计数器。
    tmp: usize,
    /// 标签计数器。
    label: usize,
    /// break 目标的退出标签栈。
    break_stack: Vec<String>,
    /// 当前基本块是否已被终止指令（ret/br）结束。
    terminated: bool,
}

impl Codegen {
    pub fn new() -> Self {
        Self {
            out: String::new(),
            globals: Vec::new(),
            string_counter: 0,
            symbols: vec![HashMap::new()],
            functions: HashMap::new(),
            tmp: 0,
            label: 0,
            break_stack: Vec::new(),
            terminated: false,
        }
    }

    /// 完整编译：Program → LLVM IR 文本。
    pub fn generate(program: &Program) -> TResult<String> {
        let mut gen = Codegen::new();
        gen.collect_signatures(program)?;
        gen.emit_header();
        gen.emit_program(program)?;
        Ok(format!("{}\n{}", gen.globals.join("\n"), gen.out))
    }

    // ---- 辅助 ----

    fn tmp(&mut self) -> String {
        self.tmp += 1;
        format!("%v{}", self.tmp)
    }

    fn new_label(&mut self, name: &str) -> String {
        self.label += 1;
        format!("{name}.{}", self.label)
    }

    fn push(&mut self, line: &str) {
        self.out.push_str(line);
        self.out.push('\n');
    }

    /// 推送一条指令（使当前块未终止）。
    fn ins(&mut self, line: &str) {
        self.terminated = false;
        self.push(line);
    }

    /// 推送终止指令（ret/br），标记当前块已终止。
    fn term(&mut self, line: &str) {
        self.terminated = true;
        self.push(line);
    }

    /// 开始一个新标签（新基本块，未终止）。
    fn block(&mut self, name: &str) {
        self.terminated = false;
        self.push(&format!("{name}:"));
    }

    /// 若当前块未终止则跳转。
    fn br_if_open(&mut self, target: &str) {
        if !self.terminated {
            self.term(&format!("br label %{target}"));
        }
    }

    /// 注册/取回一个字符串字面量全局常量，返回 (全局名, 字节数)。
    fn intern_string(&mut self, s: &str) -> String {
        let name = format!(".str.{}", self.string_counter);
        self.string_counter += 1;
        let bytes: Vec<u8> = s.bytes().collect();
        let mut ll = String::from("c\"");
        for b in &bytes {
            match b {
                0x22 => ll.push_str("\\22"),
                0x5C => ll.push_str("\\5C"),
                0x0A => ll.push_str("\\0A"),
                0x09 => ll.push_str("\\09"),
                0x20..=0x7E => ll.push(*b as char),
                _ => ll.push_str(&format!("\\{:02X}", b)),
            }
        }
        ll.push_str("\\00\"");
        self.globals
            .push(format!("@{name} = private unnamed_addr constant [{} x i8] {ll}", bytes.len() + 1));
        name
    }

    /// 取字符串常量地址（i8*）。
    fn string_addr(&mut self, s: &str) -> String {
        let name = self.intern_string(s);
        let len = s.bytes().len() + 1;
        let t = self.tmp();
        self.ins(&format!(
            "{t} = getelementptr [{len} x i8], ptr @{name}, i64 0, i64 0"
        ));
        t
    }

    // ---- 预处理 ----

    fn collect_signatures(&mut self, program: &Program) -> TResult<()> {
        for stmt in &program.stmts {
            if let Stmt::FnDecl { name, ret, .. } = stmt {
                if matches!(name.as_str(), "main" | "printf" | "tenet_concat" | "tenet_strcmp") {
                    return Err(TenetError::new(format!("函数名 `{name}` 为编译器保留"), None));
                }
                if self.functions.contains_key(name) {
                    return Err(TenetError::new(format!("函数 `{name}` 重复定义"), None));
                }
                self.functions.insert(name.clone(), ret.clone());
            }
        }
        Ok(())
    }

    fn emit_header(&mut self) {
        self.push("; Tenet 编译器生成（前端自写 → LLVM IR → clang 链接）");
        self.push("declare i32 @printf(ptr, ...)");
        self.push("declare ptr @tenet_concat(ptr, ptr)");
        self.push("declare i32 @tenet_strcmp(ptr, ptr)");
        self.globals
            .push("@.str.true = private unnamed_addr constant [5 x i8] c\"true\\00\"".into());
        self.globals
            .push("@.str.false = private unnamed_addr constant [6 x i8] c\"false\\00\"".into());
    }

    // ---- 程序 ----

    fn emit_program(&mut self, program: &Program) -> TResult<()> {
        for stmt in &program.stmts {
            if let Stmt::FnDecl { .. } = stmt {
                self.emit_fn_decl(stmt)?;
            }
        }
        self.push("define i32 @main() {");
        self.block("entry");
        for stmt in &program.stmts {
            if let Stmt::FnDecl { .. } = stmt {
                continue;
            }
            if let Stmt::Return(_) = stmt {
                return Err(TenetError::new("顶层不能使用 `return`（main 自动返回 0）", None));
            }
            self.emit_stmt(stmt)?;
        }
        if !self.terminated {
            self.term("ret i32 0");
        }
        self.push("}");
        Ok(())
    }

    // ---- 语句 ----

    fn emit_fn_decl(&mut self, stmt: &Stmt) -> TResult<()> {
        let Stmt::FnDecl {
            name,
            params,
            ret,
            body,
        } = stmt
        else {
            unreachable!()
        };

        // 轻量检查：声明了返回类型的函数，最后一条语句必须是 return
        if ret.is_some() && !matches!(body.last(), Some(Stmt::Return(_))) {
            return Err(TenetError::new(
                format!("函数 `{name}` 声明了返回类型，但函数末尾没有 return"),
                None,
            ));
        }

        let ret_ll = ret.as_deref().map(llvm_type).unwrap_or("void");
        let param_strs: Vec<String> = params
            .iter()
            .enumerate()
            .map(|(i, (_, t))| format!("{} %p{i}", llvm_type(t)))
            .collect();
        self.push(&format!("define {ret_ll} @{name}({}) {{", param_strs.join(", ")));
        self.block("entry");

        self.symbols.push(HashMap::new());
        for (i, (pname, pty)) in params.iter().enumerate() {
            let addr = format!("%p{i}.addr");
            self.ins(&format!("{addr} = alloca {}", llvm_type(pty)));
            self.ins(&format!("store {} %p{i}, ptr {addr}", llvm_type(pty)));
            self.symbols
                .last_mut()
                .unwrap()
                .insert(pname.clone(), (pty.clone(), addr));
        }
        for s in body {
            self.emit_stmt(s)?;
        }
        self.symbols.pop();

        // 末尾兜底：void 函数自然结束
        if ret.is_none() && !self.terminated {
            self.term("ret void");
        }
        self.push("}");
        Ok(())
    }

    fn emit_stmt(&mut self, stmt: &Stmt) -> TResult<()> {
        match stmt {
            Stmt::Let { name, ty, value } => {
                let t = match ty {
                    Some(t) => t.clone(),
                    None => self
                        .infer_type(value)?
                        .ok_or_else(|| {
                            TenetError::new(format!("无法推断 `{name}` 的类型，请显式标注"), None)
                        })?,
                };
                let (_, v) = self.gen_expr(value)?;
                let addr = self.tmp();
                self.ins(&format!("{addr} = alloca {}", llvm_type(&t)));
                self.ins(&format!("store {} {v}, ptr {addr}", llvm_type(&t)));
                self.symbols
                    .last_mut()
                    .unwrap()
                    .insert(name.clone(), (t, addr));
                Ok(())
            }
            Stmt::Expr(expr) => {
                self.gen_expr(expr)?;
                Ok(())
            }
            Stmt::If {
                cond,
                then_branch,
                else_branch,
            } => {
                let (_, c) = self.gen_expr(cond)?;
                let then_l = self.new_label("then");
                let else_l = self.new_label("else");
                let merge_l = self.new_label("merge");
                self.term(&format!("br i1 {c}, label %{then_l}, label %{else_l}"));
                self.block(&then_l);
                self.symbols.push(HashMap::new());
                for s in then_branch {
                    self.emit_stmt(s)?;
                }
                self.symbols.pop();
                self.br_if_open(&merge_l);
                self.block(&else_l);
                if let Some(branch) = else_branch {
                    self.symbols.push(HashMap::new());
                    for s in branch {
                        self.emit_stmt(s)?;
                    }
                    self.symbols.pop();
                }
                self.br_if_open(&merge_l);
                self.block(&merge_l);
                Ok(())
            }
            Stmt::While { cond, body } => {
                let cond_l = self.new_label("cond");
                let body_l = self.new_label("body");
                let exit_l = self.new_label("exit");
                self.term(&format!("br label %{cond_l}"));
                self.block(&cond_l);
                let (_, c) = self.gen_expr(cond)?;
                self.term(&format!("br i1 {c}, label %{body_l}, label %{exit_l}"));
                self.block(&body_l);
                self.symbols.push(HashMap::new());
                self.break_stack.push(exit_l.clone());
                for s in body {
                    self.emit_stmt(s)?;
                }
                self.break_stack.pop();
                self.symbols.pop();
                self.br_if_open(&cond_l);
                self.block(&exit_l);
                Ok(())
            }
            Stmt::Return(expr) => {
                if let Some(e) = expr {
                    let (t, v) = self.gen_expr(e)?;
                    self.term(&format!("ret {t} {v}"));
                } else {
                    self.term("ret void");
                }
                Ok(())
            }
            Stmt::Break => {
                let Some(exit) = self.break_stack.last() else {
                    return Err(TenetError::new("`break` 出现在循环之外", None));
                };
                self.term(&format!("br label %{exit}"));
                Ok(())
            }
            Stmt::FnDecl { .. } => Ok(()),
        }
    }

    // ---- 表达式 ----

    /// 生成表达式，返回 (LLVM 类型, 操作数)。
    fn gen_expr(&mut self, expr: &Expr) -> TResult<(String, String)> {
        match expr {
            Expr::Int(v) => Ok((llvm_type(T_INT).into(), v.to_string())),
            Expr::Float(v) => {
                let s = v.to_string();
                let s = if s.contains('.') { s } else { format!("{s}.0") };
                Ok((llvm_type(T_FLOAT).into(), s))
            }
            Expr::Str(s) => Ok((llvm_type(T_STR).into(), self.string_addr(s))),
            Expr::Bool(b) => Ok((
                llvm_type(T_BOOL).into(),
                if *b { "true".into() } else { "false".into() },
            )),
            Expr::Var(name) => {
                let (t, addr) = self.lookup_var(name)?;
                let r = self.tmp();
                self.ins(&format!("{r} = load {}, ptr {addr}", llvm_type(&t)));
                Ok((llvm_type(&t).into(), r))
            }
            Expr::Assign { name, value } => {
                let (t, addr) = self.lookup_var(name)?;
                let (vt, v) = self.gen_expr(value)?;
                if vt != llvm_type(&t) {
                    return Err(TenetError::new(
                        format!("赋值类型不匹配：`{name}` 是 {t}，右侧是 {vt}"),
                        None,
                    ));
                }
                self.ins(&format!("store {vt} {v}, ptr {addr}"));
                Ok((vt, v))
            }
            Expr::Unary { op, expr } => {
                let (t, v) = self.gen_expr(expr)?;
                match *op {
                    crate::ast::OP_NEG => {
                        if t == llvm_type(T_INT) {
                            let r = self.tmp();
                            self.ins(&format!("{r} = sub i64 0, {v}"));
                            Ok((t, r))
                        } else {
                            let r = self.tmp();
                            self.ins(&format!("{r} = fsub double 0.0, {v}"));
                            Ok((t, r))
                        }
                    }
                    crate::ast::OP_NOT => {
                        let r = self.tmp();
                        self.ins(&format!("{r} = xor i1 true, {v}"));
                        Ok((llvm_type(T_BOOL).into(), r))
                    }
                    _ => unreachable!(),
                }
            }
            Expr::Binary { op, lhs, rhs } => {
                if *op == crate::ast::OP_AND || *op == crate::ast::OP_OR {
                    return self.gen_logic(*op, lhs, rhs);
                }
                let (lt, lv) = self.gen_expr(lhs)?;
                let (rt, rv) = self.gen_expr(rhs)?;
                self.gen_arith(*op, lt, lv, rt, rv)
            }
            Expr::Call { callee, args } => self.gen_call(callee, args),
        }
    }

    fn lookup_var(&self, name: &str) -> TResult<(String, String)> {
        for scope in self.symbols.iter().rev() {
            if let Some((t, addr)) = scope.get(name) {
                return Ok((t.clone(), addr.clone()));
            }
        }
        Err(TenetError::new(format!("未定义的变量 `{name}`"), None))
    }

    /// 短路逻辑 && / ||：基本块跳转 + alloca 存结果（免 phi）。
    fn gen_logic(&mut self, op: &'static str, lhs: &Expr, rhs: &Expr) -> TResult<(String, String)> {
        let res = self.tmp();
        self.ins(&format!("{res} = alloca i1"));
        let (_, lv) = self.gen_expr(lhs)?;
        let rhs_l = self.new_label("l.rhs");
        let short_l = self.new_label("l.short");
        let end_l = self.new_label("l.end");
        // 短路判定：&& 时左侧为 false 短路；|| 时左侧为 true 短路
        if op == crate::ast::OP_AND {
            self.term(&format!("br i1 {lv}, label %{rhs_l}, label %{short_l}"));
        } else {
            self.term(&format!("br i1 {lv}, label %{short_l}, label %{rhs_l}"));
        }
        self.block(&short_l);
        let short_val = if op == crate::ast::OP_AND { "false" } else { "true" };
        self.ins(&format!("store i1 {short_val}, ptr {res}"));
        self.term(&format!("br label %{end_l}"));
        self.block(&rhs_l);
        let (_, rv) = self.gen_expr(rhs)?;
        self.ins(&format!("store i1 {rv}, ptr {res}"));
        self.term(&format!("br label %{end_l}"));
        self.block(&end_l);
        let r = self.tmp();
        self.ins(&format!("{r} = load i1, ptr {res}"));
        Ok((llvm_type(T_BOOL).into(), r))
    }

    fn gen_arith(
        &mut self,
        op: &'static str,
        lt: String,
        lv: String,
        rt: String,
        rv: String,
    ) -> TResult<(String, String)> {
        let is_compare = matches!(
            op,
            crate::ast::OP_EQ
                | crate::ast::OP_NEQ
                | crate::ast::OP_LT
                | crate::ast::OP_LTE
                | crate::ast::OP_GT
                | crate::ast::OP_GTE
        );
        let str_ll = llvm_type(T_STR);

        // 字符串拼接（+）
        if op == crate::ast::OP_ADD && lt == str_ll && rt == str_ll {
            let r = self.tmp();
            self.ins(&format!("{r} = call ptr @tenet_concat(ptr {lv}, ptr {rv})"));
            return Ok((llvm_type(T_STR).into(), r));
        }
        // 字符串比较
        if lt == str_ll && rt == str_ll {
            if is_compare {
                return self.gen_str_compare(op, lv, rv);
            }
            return Err(TenetError::new(
                format!("运算符 `{op}` 不能作用于 string 和 string"),
                None,
            ));
        }
        // 数值比较 → bool
        if is_compare {
            return self.gen_numeric_compare(op, lt, lv, rt, rv);
        }

        // 数值运算：混合 int/float 时提升 int → double
        let (is_float, fl, fr) = self.promote_numeric(lt, lv, rt, rv);
        if !is_float {
            if op == crate::ast::OP_MOD {
                let r = self.tmp();
                self.ins(&format!("{r} = srem i64 {fl}, {fr}"));
                return Ok((llvm_type(T_INT).into(), r));
            }
            let r = self.tmp();
            let instr = match op {
                crate::ast::OP_ADD => "add",
                crate::ast::OP_SUB => "sub",
                crate::ast::OP_MUL => "mul",
                crate::ast::OP_DIV => "sdiv",
                _ => unreachable!(),
            };
            self.ins(&format!("{r} = {instr} i64 {fl}, {fr}"));
            Ok((llvm_type(T_INT).into(), r))
        } else {
            if op == crate::ast::OP_MOD {
                return Err(TenetError::new("运算符 `%` 只能作用于 int", None));
            }
            let r = self.tmp();
            let instr = match op {
                crate::ast::OP_ADD => "fadd",
                crate::ast::OP_SUB => "fsub",
                crate::ast::OP_MUL => "fmul",
                crate::ast::OP_DIV => "fdiv",
                _ => unreachable!(),
            };
            self.ins(&format!("{r} = {instr} double {fl}, {fr}"));
            Ok((llvm_type(T_FLOAT).into(), r))
        }
    }

    /// int/float 混合时把 int 提升为 double；返回 (是否浮点, 左操作数, 右操作数)。
    fn promote_numeric(
        &mut self,
        lt: String,
        lv: String,
        rt: String,
        rv: String,
    ) -> (bool, String, String) {
        let int_ll = llvm_type(T_INT);
        let float_ll = llvm_type(T_FLOAT);
        let (is_float, fl, fr) = if lt == float_ll || rt == float_ll {
            let fl = if lt == float_ll {
                lv
            } else {
                let t = self.tmp();
                self.ins(&format!("{t} = sitofp i64 {lv} to double"));
                t
            };
            let fr = if rt == float_ll {
                rv
            } else {
                let t = self.tmp();
                self.ins(&format!("{t} = sitofp i64 {rv} to double"));
                t
            };
            (true, fl, fr)
        } else {
            let _ = int_ll;
            (false, lv, rv)
        };
        (is_float, fl, fr)
    }

    fn gen_numeric_compare(
        &mut self,
        op: &'static str,
        lt: String,
        lv: String,
        rt: String,
        rv: String,
    ) -> TResult<(String, String)> {
        let (is_float, fl, fr) = self.promote_numeric(lt, lv, rt, rv);
        let r = self.tmp();
        if is_float {
            let pred = COMPARE_OPS_FLOAT
                .iter()
                .find(|(o, _)| *o == op)
                .map(|(_, p)| *p)
                .unwrap();
            self.ins(&format!("{r} = fcmp {pred} double {fl}, {fr}"));
        } else {
            let pred = COMPARE_OPS_INT
                .iter()
                .find(|(o, _)| *o == op)
                .map(|(_, p)| *p)
                .unwrap();
            self.ins(&format!("{r} = icmp {pred} i64 {fl}, {fr}"));
        }
        Ok((llvm_type(T_BOOL).into(), r))
    }

    fn gen_str_compare(&mut self, op: &'static str, lv: String, rv: String) -> TResult<(String, String)> {
        let c = self.tmp();
        self.ins(&format!("{c} = call i32 @tenet_strcmp(ptr {lv}, ptr {rv})"));
        let pred = COMPARE_OPS_INT
            .iter()
            .find(|(o, _)| *o == op)
            .map(|(_, p)| *p)
            .unwrap();
        let r = self.tmp();
        self.ins(&format!("{r} = icmp {pred} i32 {c}, 0"));
        Ok((llvm_type(T_BOOL).into(), r))
    }

    fn gen_call(&mut self, callee: &str, args: &[Expr]) -> TResult<(String, String)> {
        if callee == "print" {
            return self.gen_print(args);
        }
        let ret = self
            .functions
            .get(callee)
            .ok_or_else(|| TenetError::new(format!("未定义的函数 `{callee}`"), None))?
            .clone();
        let ret_ll = ret.as_deref().map(llvm_type).unwrap_or("void");
        let mut arg_ops = Vec::new();
        let mut arg_types = Vec::new();
        for a in args {
            let (t, v) = self.gen_expr(a)?;
            arg_ops.push(v);
            arg_types.push(t);
        }
        let joined = arg_types
            .iter()
            .zip(&arg_ops)
            .map(|(t, o)| format!("{t} {o}"))
            .collect::<Vec<_>>()
            .join(", ");
        if ret_ll == "void" {
            let r = self.tmp();
            self.ins(&format!("{r} = call void @{callee}({joined})"));
            Ok(("void".into(), r))
        } else {
            let r = self.tmp();
            self.ins(&format!("{r} = call {ret_ll} @{callee}({joined})"));
            Ok((ret_ll.into(), r))
        }
    }

    /// print(a, b, ...) → 编译期按参数类型拼 printf 格式串。
    fn gen_print(&mut self, args: &[Expr]) -> TResult<(String, String)> {
        let mut fmt = String::new();
        let mut arg_ops: Vec<String> = Vec::new();
        for (i, a) in args.iter().enumerate() {
            if i > 0 {
                fmt.push(' ');
            }
            let (t, v) = self.gen_expr(a)?;
            match t.as_str() {
                "i64" => {
                    fmt.push_str("%lld");
                    arg_ops.push(format!("i64 {v}"));
                }
                "double" => {
                    fmt.push_str("%g");
                    arg_ops.push(format!("double {v}"));
                }
                "ptr" => {
                    fmt.push_str("%s");
                    arg_ops.push(format!("ptr {v}"));
                }
                "i1" => {
                    fmt.push_str("%s");
                    let sel = self.tmp();
                    self.ins(&format!(
                        "{sel} = select i1 {v}, ptr @.str.true, ptr @.str.false"
                    ));
                    arg_ops.push(format!("ptr {sel}"));
                }
                _ => return Err(TenetError::new("print 不支持该类型的值", None)),
            }
        }
        fmt.push('\n');
        let fmt_addr = self.string_addr(&fmt);
        let r = self.tmp();
        let mut call = format!("call i32 (ptr, ...) @printf(ptr {fmt_addr}");
        for o in &arg_ops {
            call.push_str(", ");
            call.push_str(&o);
        }
        call.push(')');
        self.ins(&format!("{r} = {call}"));
        Ok(("void".into(), r))
    }

    // ---- 类型推断（与求值规则一致）----

    fn infer_type(&self, expr: &Expr) -> TResult<Option<String>> {
        Ok(match expr {
            Expr::Int(_) => Some(T_INT.to_string()),
            Expr::Float(_) => Some(T_FLOAT.to_string()),
            Expr::Str(_) => Some(T_STR.to_string()),
            Expr::Bool(_) => Some(T_BOOL.to_string()),
            Expr::Var(name) => self.lookup_var(name).ok().map(|(t, _)| t),
            Expr::Assign { name, .. } => self.lookup_var(name).ok().map(|(t, _)| t),
            Expr::Unary { op, expr } => match *op {
                crate::ast::OP_NOT => Some(T_BOOL.to_string()),
                _ => self.infer_type(expr)?,
            },
            Expr::Binary { op, lhs, rhs } => {
                let lt = self.infer_type(lhs)?;
                let rt = self.infer_type(rhs)?;
                match *op {
                    crate::ast::OP_AND | crate::ast::OP_OR => Some(T_BOOL.to_string()),
                    crate::ast::OP_EQ
                    | crate::ast::OP_NEQ
                    | crate::ast::OP_LT
                    | crate::ast::OP_LTE
                    | crate::ast::OP_GT
                    | crate::ast::OP_GTE => Some(T_BOOL.to_string()),
                    crate::ast::OP_MOD => {
                        if lt.as_deref() == Some(T_INT) && rt.as_deref() == Some(T_INT) {
                            Some(T_INT.to_string())
                        } else {
                            None
                        }
                    }
                    crate::ast::OP_ADD => match (lt.as_deref(), rt.as_deref()) {
                        (Some(T_STR), Some(T_STR)) => Some(T_STR.to_string()),
                        (Some(T_FLOAT), _) | (_, Some(T_FLOAT)) => Some(T_FLOAT.to_string()),
                        (Some(T_INT), Some(T_INT)) => Some(T_INT.to_string()),
                        _ => None,
                    },
                    _ => match (lt.as_deref(), rt.as_deref()) {
                        (Some(T_FLOAT), _) | (_, Some(T_FLOAT)) => Some(T_FLOAT.to_string()),
                        (Some(T_INT), Some(T_INT)) => Some(T_INT.to_string()),
                        _ => None,
                    },
                }
            }
            Expr::Call { callee, .. } => self.functions.get(callee).cloned().flatten(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser::Parser;

    fn gen(src: &str) -> TResult<String> {
        let prog = Parser::parse(src)?;
        Codegen::generate(&prog)
    }

    #[test]
    fn hello_ir() {
        let ir = gen("print(\"hello\");").unwrap();
        assert!(ir.contains("define i32 @main()"));
        assert!(ir.contains("call i32 (ptr, ...) @printf"));
        assert!(ir.contains("c\"hello\\00\""));
    }

    #[test]
    fn let_int_uses_alloca() {
        let ir = gen("let x: int = 42;").unwrap();
        assert!(ir.contains("alloca i64"));
        assert!(ir.contains("store i64 42"));
    }

    #[test]
    fn function_decl_ir() {
        let ir = gen("fn add(a: int, b: int) -> int { return a + b; }").unwrap();
        assert!(ir.contains("define i64 @add(i64 %p0, i64 %p1)"));
        assert!(ir.contains("add i64"));
    }

    #[test]
    fn while_becomes_basic_blocks() {
        let ir = gen("let x: int = 0; while (x < 10) { x = x + 1; }").unwrap();
        assert!(ir.contains("icmp slt"));
        assert!(ir.contains("br i1"));
    }

    #[test]
    fn recursion_call() {
        let ir = gen("fn fib(n: int) -> int { return fib(n - 1); }").unwrap();
        assert!(ir.contains("call i64 @fib"));
    }

    #[test]
    fn float_keeps_decimal_point() {
        let ir = gen("let x = 7 / 2.0;").unwrap();
        assert!(ir.contains("sitofp"));
        assert!(ir.contains("fdiv double"));
    }

    #[test]
    fn short_circuit_blocks() {
        let ir = gen("let x: bool = true || (1 / 0 == 1);").unwrap();
        assert!(ir.contains("br i1"));
    }

    #[test]
    fn missing_return_errors() {
        let err = gen("fn f() -> int { let x: int = 1; }").unwrap_err();
        assert!(err.message.contains("末尾没有 return"), "{}", err);
    }

    #[test]
    fn reserved_function_name_errors() {
        let err = gen("fn main() { }").unwrap_err();
        assert!(err.message.contains("保留"), "{}", err);
    }
}
