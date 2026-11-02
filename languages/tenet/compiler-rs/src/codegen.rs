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
//! - 类型检查（与三实现一致）：字符串×非字符串混合运算、bool 参与数值运算、
//!   `%` 非 int、逻辑/条件非 bool、声明/赋值/参数/返回类型不匹配，
//!   全部在前端报 `[行:列]` 错误，绝不让非法 IR 漏到 clang。

use std::collections::HashMap;

use crate::ast::{Expr, ExprKind, Program, Stmt, StmtKind, T_BOOL, T_FLOAT, T_INT, T_STR};
use crate::error::{Position, TenetError, TResult};

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

/// LLVM 类型 → Tenet 类型名（错误信息用）。
fn tenet_name(ll: &str) -> &'static str {
    match ll {
        "i64" => T_INT,
        "double" => T_FLOAT,
        "i1" => T_BOOL,
        "ptr" => T_STR,
        other => panic!("未知 LLVM 类型 {other}"),
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

/// 函数签名：参数类型 + 返回类型（None = void）。
#[derive(Clone)]
struct FnSig {
    params: Vec<String>,
    ret: Option<String>,
}

/// 变量信息。struct 变量不占一个聚合槽，而是扁平化成字段槽位（v1 局部变量方案）。
#[derive(Clone)]
struct VarInfo {
    ty: String,
    addr: Option<String>,
    fields: HashMap<String, VarInfo>,
    /// 数组变量的定长长度；非数组为 None。
    array: Option<usize>,
}

pub struct Codegen {
    out: String,
    /// 字符串字面量全局常量声明（文件头输出）。
    globals: Vec<String>,
    string_counter: usize,
    /// 变量作用域栈：name -> (LLVM 类型, alloca 名)。
    symbols: Vec<HashMap<String, VarInfo>>,
    /// 顶层 struct 名 → 字段 (名, 标量类型)。
    structs: HashMap<String, Vec<(String, String)>>,
    /// 函数签名表：name -> 签名。
    functions: HashMap<String, FnSig>,
    /// 当前函数上下文（错误信息用）。
    current_fn: String,
    current_ret: Option<String>,
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
            structs: HashMap::new(),
            functions: HashMap::new(),
            current_fn: String::new(),
            current_ret: None,
            tmp: 0,
            label: 0,
            break_stack: Vec::new(),
            terminated: false,
        }
    }

    /// 完整编译：Program → LLVM IR 文本。
    pub fn generate(program: &Program) -> TResult<String> {
        let mut gen = Codegen::new();
        gen.collect_structs(program)?;
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

    fn collect_structs(&mut self, program: &Program) -> TResult<()> {
        for stmt in &program.stmts {
            let StmtKind::StructDecl { name, fields } = &stmt.kind else {
                continue;
            };
            if matches!(name.as_str(), "int" | "float" | "bool" | "string") {
                return Err(TenetError::at_pos(
                    format!("struct 名 `{name}` 不能与标量类型重名"),
                    stmt.pos.clone(),
                ));
            }
            if self.structs.contains_key(name) {
                return Err(TenetError::at_pos(
                    format!("struct `{name}` 重复定义"),
                    stmt.pos.clone(),
                ));
            }
            if fields.is_empty() {
                return Err(TenetError::at_pos(
                    format!("struct `{name}` 至少需要一个字段"),
                    stmt.pos.clone(),
                ));
            }
            let mut seen = std::collections::HashSet::new();
            for (fname, fty) in fields {
                if !matches!(fty.as_str(), T_INT | T_FLOAT | T_BOOL) {
                    return Err(TenetError::at_pos(
                        format!("struct `{name}` 的字段 `{fname}` 只支持 int/float/bool"),
                        stmt.pos.clone(),
                    ));
                }
                if !seen.insert(fname.clone()) {
                    return Err(TenetError::at_pos(
                        format!("struct `{name}` 的字段 `{fname}` 重复"),
                        stmt.pos.clone(),
                    ));
                }
            }
            self.structs.insert(name.clone(), fields.clone());
        }
        Ok(())
    }

    fn is_struct(&self, ty: &str) -> bool {
        self.structs.contains_key(ty)
    }

    fn is_array(&self, ty: &str) -> bool {
        Self::array_elem(ty).is_some()
    }

    fn array_elem(ty: &str) -> Option<&str> {
        ty.strip_prefix("array<")?.strip_suffix('>')
    }

    fn struct_fields(&self, ty: &str, pos: Position) -> TResult<Vec<(String, String)>> {
        self.structs
            .get(ty)
            .cloned()
            .ok_or_else(|| TenetError::at_pos(format!("未定义的 struct `{ty}`"), pos))
    }

    fn collect_signatures(&mut self, program: &Program) -> TResult<()> {
        for stmt in &program.stmts {
            if let StmtKind::FnDecl { name, ret, params, .. } = &stmt.kind {
                if matches!(name.as_str(), "main" | "printf" | "tenet_concat" | "tenet_strcmp") {
                    return Err(TenetError::at_pos(
                        format!("函数名 `{name}` 为编译器保留"),
                        stmt.pos.clone(),
                    ));
                }
                if self.functions.contains_key(name) {
                    return Err(TenetError::at_pos(
                        format!("函数 `{name}` 重复定义"),
                        stmt.pos.clone(),
                    ));
                }
                for (pname, pty) in params {
                    if self.is_struct(pty) {
                        return Err(TenetError::at_pos(
                            format!("v1 不支持 struct 参数：`{name}` 的参数 `{pname}` 是 `{pty}`"),
                            stmt.pos.clone(),
                        ));
                    }
                    if self.is_array(pty) {
                        return Err(TenetError::at_pos(
                            format!("v1 不支持 array 参数：`{name}` 的参数 `{pname}` 是 `{pty}`"),
                            stmt.pos.clone(),
                        ));
                    }
                }
                if let Some(rt) = ret {
                    if self.is_struct(rt) {
                        return Err(TenetError::at_pos(
                            format!("v1 不支持 struct 返回值：`{name}` 返回 `{rt}`"),
                            stmt.pos.clone(),
                        ));
                    }
                    if self.is_array(rt) {
                        return Err(TenetError::at_pos(
                            format!("v1 不支持 array 返回值：`{name}` 返回 `{rt}`"),
                            stmt.pos.clone(),
                        ));
                    }
                }
                self.functions.insert(
                    name.clone(),
                    FnSig {
                        params: params.iter().map(|(_, t)| t.clone()).collect(),
                        ret: ret.clone(),
                    },
                );
            }
        }
        Ok(())
    }

    fn emit_header(&mut self) {
        self.push("; Tenet 编译器生成（前端自写 → LLVM IR → clang 链接）");
        self.push("declare i32 @printf(ptr, ...)");
        self.push("declare ptr @tenet_concat(ptr, ptr)");
        self.push("declare i32 @tenet_strcmp(ptr, ptr)");
        self.push("declare void @tenet_bounds_fail(i64, i64)");
        self.globals
            .push("@.str.true = private unnamed_addr constant [5 x i8] c\"true\\00\"".into());
        self.globals
            .push("@.str.false = private unnamed_addr constant [6 x i8] c\"false\\00\"".into());
    }

    // ---- 程序 ----

    fn emit_program(&mut self, program: &Program) -> TResult<()> {
        for stmt in &program.stmts {
            if let StmtKind::FnDecl { .. } = &stmt.kind {
                self.emit_fn_decl(stmt)?;
            }
        }
        self.current_fn = "main".into();
        self.current_ret = None;
        self.push("define i32 @main() {");
        self.block("entry");
        for stmt in &program.stmts {
            if matches!(&stmt.kind, StmtKind::FnDecl { .. } | StmtKind::StructDecl { .. }) {
                continue;
            }
            if let StmtKind::Return(_) = &stmt.kind {
                return Err(TenetError::at_pos(
                    "顶层不能使用 `return`（main 自动返回 0）",
                    stmt.pos.clone(),
                ));
            }
            self.emit_stmt(stmt)?;
        }
        self.current_fn.clear();
        if !self.terminated {
            self.term("ret i32 0");
        }
        self.push("}");
        Ok(())
    }

    // ---- 语句 ----

    fn emit_fn_decl(&mut self, stmt: &Stmt) -> TResult<()> {
        let StmtKind::FnDecl {
            name,
            params,
            ret,
            body,
        } = &stmt.kind
        else {
            unreachable!()
        };

        // 轻量检查：声明了返回类型的函数，最后一条语句必须是 return
        if ret.is_some() && !matches!(body.last().map(|s| &s.kind), Some(StmtKind::Return(_))) {
            return Err(TenetError::at_pos(
                format!("函数 `{name}` 声明了返回类型，但函数末尾没有 return"),
                stmt.pos.clone(),
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

        self.current_fn = name.clone();
        self.current_ret = ret.clone();
        self.symbols.push(HashMap::new());
        for (i, (pname, pty)) in params.iter().enumerate() {
            let addr = format!("%p{i}.addr");
            self.ins(&format!("{addr} = alloca {}", llvm_type(pty)));
            self.ins(&format!("store {} %p{i}, ptr {addr}", llvm_type(pty)));
            self.symbols.last_mut().unwrap().insert(
                pname.clone(),
                VarInfo {
                    ty: pty.clone(),
                    addr: Some(addr),
                    fields: HashMap::new(),
                    array: None,
                },
            );
        }
        for s in body {
            self.emit_stmt(s)?;
        }
        self.symbols.pop();
        self.current_fn.clear();
        self.current_ret = None;

        // 末尾兜底：void 函数自然结束
        if ret.is_none() && !self.terminated {
            self.term("ret void");
        }
        self.push("}");
        Ok(())
    }

    fn emit_stmt(&mut self, stmt: &Stmt) -> TResult<()> {
        match &stmt.kind {
            StmtKind::Let { name, ty, value } => {
                let t = match ty {
                    Some(t) => t.clone(),
                    None => self
                        .infer_type(value)?
                        .ok_or_else(|| {
                            TenetError::at_pos(
                                format!("无法推断 `{name}` 的类型，请显式标注"),
                                stmt.pos.clone(),
                            )
                        })?,
                };
                if self.is_array(&t) {
                    let info = self.init_array(name, &t, value, stmt.pos.clone())?;
                    self.symbols.last_mut().unwrap().insert(name.clone(), info);
                    return Ok(());
                }
                if self.is_struct(&t) {
                    let info = self.init_struct(name, &t, value, stmt.pos.clone())?;
                    self.symbols.last_mut().unwrap().insert(name.clone(), info);
                    return Ok(());
                }
                let (vt, v) = self.gen_expr(value)?;
                if vt != llvm_type(&t) {
                    return Err(TenetError::at_pos(
                        format!(
                            "`{name}` 初始化类型不匹配：标注 {t}，实际 {}",
                            tenet_name(&vt)
                        ),
                        stmt.pos.clone(),
                    ));
                }
                let addr = self.tmp();
                self.ins(&format!("{addr} = alloca {}", llvm_type(&t)));
                self.ins(&format!("store {} {v}, ptr {addr}", llvm_type(&t)));
                self.symbols.last_mut().unwrap().insert(
                    name.clone(),
                    VarInfo {
                        ty: t,
                        addr: Some(addr),
                        fields: HashMap::new(),
                        array: None,
                    },
                );
                Ok(())
            }
            StmtKind::Expr(expr) => {
                self.gen_expr(expr)?;
                Ok(())
            }
            StmtKind::If {
                cond,
                then_branch,
                else_branch,
            } => {
                let (ct, c) = self.gen_expr(cond)?;
                if ct != llvm_type(T_BOOL) {
                    return Err(TenetError::at_pos(
                        format!("条件表达式需要 bool，实际为 {}", tenet_name(&ct)),
                        cond.pos.clone(),
                    ));
                }
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
            StmtKind::While { cond, body } => {
                let cond_l = self.new_label("cond");
                let body_l = self.new_label("body");
                let exit_l = self.new_label("exit");
                self.term(&format!("br label %{cond_l}"));
                self.block(&cond_l);
                let (ct, c) = self.gen_expr(cond)?;
                if ct != llvm_type(T_BOOL) {
                    return Err(TenetError::at_pos(
                        format!("条件表达式需要 bool，实际为 {}", tenet_name(&ct)),
                        cond.pos.clone(),
                    ));
                }
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
            StmtKind::Return(expr) => {
                if let Some(e) = expr {
                    let (t, v) = self.gen_expr(e)?;
                    match &self.current_ret {
                        None => {
                            return Err(TenetError::at_pos(
                                format!("函数 `{}` 没有返回类型，不能 return 值", self.current_fn),
                                e.pos.clone(),
                            ));
                        }
                        Some(decl) if *decl != tenet_name(&t) => {
                            return Err(TenetError::at_pos(
                                format!(
                                    "函数 `{}` 返回类型不匹配：声明 {decl}，实际 {}",
                                    self.current_fn,
                                    tenet_name(&t)
                                ),
                                e.pos.clone(),
                            ));
                        }
                        Some(_) => {}
                    }
                    self.term(&format!("ret {t} {v}"));
                } else {
                    self.term("ret void");
                }
                Ok(())
            }
            StmtKind::Break => {
                if self.break_stack.is_empty() {
                    return Err(TenetError::at_pos(
                        "`break` 出现在循环之外",
                        stmt.pos.clone(),
                    ));
                }
                self.term(&format!("br label %{}", self.break_stack.last().unwrap()));
                Ok(())
            }
            StmtKind::StructDecl { .. } => Err(TenetError::at_pos(
                "struct 声明只能出现在顶层".to_string(),
                stmt.pos.clone(),
            )),
            StmtKind::FnDecl { .. } => Ok(()),
        }
    }

    // ---- 表达式 ----

    fn gen_expr(&mut self, expr: &Expr) -> TResult<(String, String)> {
        match &expr.kind {
            ExprKind::Int(v) => Ok((llvm_type(T_INT).into(), v.to_string())),
            ExprKind::Float(v) => {
                let s = v.to_string();
                let s = if s.contains('.') { s } else { format!("{s}.0") };
                Ok((llvm_type(T_FLOAT).into(), s))
            }
            ExprKind::Str(s) => Ok((llvm_type(T_STR).into(), self.string_addr(s))),
            ExprKind::Bool(b) => Ok((
                llvm_type(T_BOOL).into(),
                if *b { "true".into() } else { "false".into() },
            )),
            ExprKind::Var(name) => {
                let info = self.lookup_var(name, expr.pos.clone())?;
                if info.array.is_some() {
                    return Err(TenetError::at_pos(
                        format!("数组变量 `{name}` 不能直接取值；请用下标或整体拷贝"),
                        expr.pos.clone(),
                    ));
                }
                let Some(addr) = info.addr else {
                    return Err(TenetError::at_pos(
                        format!("struct 变量 `{name}` 不能直接取值；请用字段访问或整体拷贝"),
                        expr.pos.clone(),
                    ));
                };
                let r = self.tmp();
                self.ins(&format!("{r} = load {}, ptr {addr}", llvm_type(&info.ty)));
                Ok((llvm_type(&info.ty).into(), r))
            }
            ExprKind::Index { base, index } => {
                let ExprKind::Var(name) = &base.kind else {
                    return Err(TenetError::at_pos(
                        "v1 只支持对数组变量取下标",
                        base.pos.clone(),
                    ));
                };
                let info = self.lookup_var(name, base.pos.clone())?;
                let Some(len) = info.array else {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 不是数组，不能取下标"),
                        base.pos.clone(),
                    ));
                };
                let elem = Self::array_elem(&info.ty).unwrap();
                let elem_ll = llvm_type(elem);
                let base_addr = info.addr.clone().unwrap();
                let (it, iv) = self.gen_expr(index)?;
                if it != llvm_type(T_INT) {
                    return Err(TenetError::at_pos(
                        format!("数组下标必须是 int，实际为 {}", tenet_name(&it)),
                        index.pos.clone(),
                    ));
                }
                let idx = match &index.kind {
                    ExprKind::Int(v) => {
                        if *v < 0 || *v as usize >= len {
                            return Err(TenetError::at_pos(
                                format!("数组下标 {v} 越界（长度 {len}）"),
                                index.pos.clone(),
                            ));
                        }
                        v.to_string()
                    }
                    _ => {
                        self.bounds_check(&iv, len);
                        iv
                    }
                };
                let addr = self.array_addr(&base_addr, len, &idx, elem_ll);
                let r = self.tmp();
                self.ins(&format!("{r} = load {elem_ll}, ptr {addr}"));
                Ok((elem_ll.to_string(), r))
            }
            ExprKind::Array(_) => Err(TenetError::at_pos(
                "数组字面量只能用于 let 初始化或整体赋值",
                expr.pos.clone(),
            )),
            ExprKind::Field { base, field } => {
                let ExprKind::Var(name) = &base.kind else {
                    return Err(TenetError::at_pos(
                        "v1 只支持对 struct 变量取字段（不支持嵌套字段链）",
                        base.pos.clone(),
                    ));
                };
                let info = self.lookup_var(name, base.pos.clone())?;
                if !self.is_struct(&info.ty) {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 不是 struct，不能取字段 `{field}`"),
                        base.pos.clone(),
                    ));
                }
                let f = info.fields.get(field).ok_or_else(|| {
                    TenetError::at_pos(
                        format!("struct `{}` 没有字段 `{field}`", info.ty),
                        expr.pos.clone(),
                    )
                })?;
                let addr = f.addr.clone().unwrap();
                let r = self.tmp();
                self.ins(&format!("{r} = load {}, ptr {addr}", llvm_type(&f.ty)));
                Ok((llvm_type(&f.ty).into(), r))
            }
            ExprKind::StructLit { .. } => Err(TenetError::at_pos(
                "struct 字面量只能用于 let 初始化或整体赋值",
                expr.pos.clone(),
            )),
            ExprKind::Assign { target, value } => match &target.kind {
                ExprKind::Var(name) => {
                    let info = self.lookup_var(name, target.pos.clone())?;
                    if self.is_array(&info.ty) {
                        self.assign_array(&info, value, expr.pos.clone())?;
                        return Ok((info.ty.clone(), String::new()));
                    }
                    if self.is_struct(&info.ty) {
                        self.assign_struct(&info, value, expr.pos.clone())?;
                        return Ok((info.ty.clone(), String::new()));
                    }
                    let Some(addr) = info.addr.clone() else {
                        return Err(TenetError::at_pos(
                            format!("`{name}` 不是可赋值标量"),
                            target.pos.clone(),
                        ));
                    };
                    let (vt, v) = self.gen_expr(value)?;
                    if vt != llvm_type(&info.ty) {
                        return Err(TenetError::at_pos(
                            format!(
                                "赋值类型不匹配：`{name}` 是 {}，右侧是 {}",
                                info.ty,
                                tenet_name(&vt)
                            ),
                            expr.pos.clone(),
                        ));
                    }
                    self.ins(&format!("store {vt} {v}, ptr {addr}"));
                    Ok((vt, v))
                }
                ExprKind::Index { base, index } => {
                    let ExprKind::Var(name) = &base.kind else {
                        return Err(TenetError::at_pos(
                            "v1 只支持对数组变量写下标",
                            base.pos.clone(),
                        ));
                    };
                    let info = self.lookup_var(name, base.pos.clone())?;
                    let Some(len) = info.array else {
                        return Err(TenetError::at_pos(
                            format!("`{name}` 不是数组，不能写下标"),
                            base.pos.clone(),
                        ));
                    };
                    let elem = Self::array_elem(&info.ty).unwrap();
                    let elem_ll = llvm_type(elem);
                    let base_addr = info.addr.clone().unwrap();
                    let (it, iv) = self.gen_expr(index)?;
                    if it != llvm_type(T_INT) {
                        return Err(TenetError::at_pos(
                            format!("数组下标必须是 int，实际为 {}", tenet_name(&it)),
                            index.pos.clone(),
                        ));
                    }
                    let idx = match &index.kind {
                        ExprKind::Int(v) => {
                            if *v < 0 || *v as usize >= len {
                                return Err(TenetError::at_pos(
                                    format!("数组下标 {v} 越界（长度 {len}）"),
                                    index.pos.clone(),
                                ));
                            }
                            v.to_string()
                        }
                        _ => {
                            self.bounds_check(&iv, len);
                            iv
                        }
                    };
                    let (vt, v) = self.gen_expr(value)?;
                    if vt != elem_ll {
                        return Err(TenetError::at_pos(
                            format!(
                                "数组元素赋值类型不匹配：需要 {elem}，实际 {}",
                                tenet_name(&vt)
                            ),
                            value.pos.clone(),
                        ));
                    }
                    let addr = self.array_addr(&base_addr, len, &idx, elem_ll);
                    self.ins(&format!("store {vt} {v}, ptr {addr}"));
                    Ok((vt, v))
                }
            ExprKind::Field { base, field } => {
                    let ExprKind::Var(name) = &base.kind else {
                        return Err(TenetError::at_pos(
                            "v1 只支持对 struct 变量写字段",
                            base.pos.clone(),
                        ));
                    };
                    let info = self.lookup_var(name, base.pos.clone())?;
                    if !self.is_struct(&info.ty) {
                        return Err(TenetError::at_pos(
                            format!("`{name}` 不是 struct，不能写字段 `{field}`"),
                            base.pos.clone(),
                        ));
                    }
                    let f = info.fields.get(field).ok_or_else(|| {
                        TenetError::at_pos(
                            format!("struct `{}` 没有字段 `{field}`", info.ty),
                            target.pos.clone(),
                        )
                    })?;
                    let (vt, v) = self.gen_expr(value)?;
                    if vt != llvm_type(&f.ty) {
                        return Err(TenetError::at_pos(
                            format!(
                                "字段 `{field}` 类型不匹配：需要 {}，实际 {}",
                                f.ty,
                                tenet_name(&vt)
                            ),
                            value.pos.clone(),
                        ));
                    }
                    let addr = f.addr.clone().unwrap();
                    self.ins(&format!("store {vt} {v}, ptr {addr}"));
                    Ok((vt, v))
                }
                _ => Err(TenetError::at_pos(
                    "赋值左侧必须是变量或字段",
                    target.pos.clone(),
                )),
            },
            ExprKind::Unary { op, expr: inner } => {
                let (t, v) = self.gen_expr(inner)?;
                match *op {
                    crate::ast::OP_NEG => {
                        if t == llvm_type(T_BOOL) {
                            return Err(TenetError::at_pos(
                                "运算符 `-` 不能作用于 bool",
                                inner.pos.clone(),
                            ));
                        }
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
                        if t != llvm_type(T_BOOL) {
                            return Err(TenetError::at_pos(
                                format!("运算符 `!` 只能作用于 bool，实际为 {}", tenet_name(&t)),
                                inner.pos.clone(),
                            ));
                        }
                        let r = self.tmp();
                        self.ins(&format!("{r} = xor i1 true, {v}"));
                        Ok((llvm_type(T_BOOL).into(), r))
                    }
                    _ => unreachable!(),
                }
            }
            ExprKind::Binary { op, lhs, rhs } => {
                if *op == crate::ast::OP_AND || *op == crate::ast::OP_OR {
                    return self.gen_logic(*op, lhs, rhs);
                }
                let (lt, lv) = self.gen_expr(lhs)?;
                let (rt, rv) = self.gen_expr(rhs)?;
                self.gen_arith(*op, lt, lv, rt, rv, expr.pos.clone())
            }
            ExprKind::Call { callee, args } => self.gen_call(callee, args, expr.pos.clone()),
        }
    }

    fn array_elem_scalar(ty: &str, pos: Position) -> TResult<String> {
        let elem = Self::array_elem(ty)
            .ok_or_else(|| TenetError::at_pos(format!("不是数组类型：{ty}"), pos.clone()))?;
        if !matches!(elem, T_INT | T_FLOAT | T_BOOL) {
            return Err(TenetError::at_pos(
                format!("v1 数组元素只支持 int/float/bool，实际 `{elem}`"),
                pos,
            ));
        }
        Ok(elem.to_string())
    }

    fn array_addr(
        &mut self,
        base: &str,
        len: usize,
        index: &str,
        elem_ll: &str,
    ) -> String {
        let addr = self.tmp();
        self.ins(&format!(
            "{addr} = getelementptr [{len} x {elem_ll}], ptr {base}, i64 0, i64 {index}"
        ));
        addr
    }

    fn bounds_check(&mut self, index: &str, len: usize) {
        let ok = self.new_label("bounds.ok");
        let fail = self.new_label("bounds.fail");
        let cmp = self.tmp();
        self.ins(&format!("{cmp} = icmp uge i64 {index}, {len}"));
        self.term(&format!("br i1 {cmp}, label %{fail}, label %{ok}"));
        self.block(&fail);
        self.ins(&format!("call void @tenet_bounds_fail(i64 {index}, i64 {len})"));
        self.term("unreachable");
        self.block(&ok);
    }

    fn init_array(&mut self, name: &str, ty: &str, value: &Expr, pos: Position) -> TResult<VarInfo> {
        let elem = Self::array_elem_scalar(ty, pos.clone())?;
        let elem_ll = llvm_type(&elem);
        let (len, src_literal) = match &value.kind {
            ExprKind::Array(elems) => {
                if elems.is_empty() {
                    return Err(TenetError::at_pos(
                        "v1 不支持空数组字面量".to_string(),
                        value.pos.clone(),
                    ));
                }
                (elems.len(), Some(elems))
            }
            ExprKind::Var(src) => {
                let sinfo = self.lookup_var(src, value.pos.clone())?;
                let slen = sinfo.array.ok_or_else(|| {
                    TenetError::at_pos(format!("`{src}` 不是数组"), value.pos.clone())
                })?;
                if sinfo.ty != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，但 `{src}` 是 {}", sinfo.ty),
                        value.pos.clone(),
                    ));
                }
                (slen, None)
            }
            _ => {
                return Err(TenetError::at_pos(
                    format!("`{name}` 的数组初始化必须是 `[...]` 或同类型数组变量"),
                    value.pos.clone(),
                ))
            }
        };
        let addr = self.tmp();
        self.ins(&format!("{addr} = alloca [{len} x {elem_ll}]"));
        if let Some(elems) = src_literal {
            for (i, e) in elems.iter().enumerate() {
                let (vt, v) = self.gen_expr(e)?;
                if vt != elem_ll {
                    return Err(TenetError::at_pos(
                        format!(
                            "数组元素 {i} 类型不匹配：需要 {elem}，实际 {}",
                            tenet_name(&vt)
                        ),
                        e.pos.clone(),
                    ));
                }
                let slot = self.array_addr(&addr, len, &i.to_string(), elem_ll);
                self.ins(&format!("store {vt} {v}, ptr {slot}"));
            }
        } else if let ExprKind::Var(src) = &value.kind {
            let sinfo = self.lookup_var(src, value.pos.clone())?;
            let sbase = sinfo.addr.clone().unwrap();
            for i in 0..len {
                let sslot = self.array_addr(&sbase, len, &i.to_string(), elem_ll);
                let dslot = self.array_addr(&addr, len, &i.to_string(), elem_ll);
                let v = self.tmp();
                self.ins(&format!("{v} = load {elem_ll}, ptr {sslot}"));
                self.ins(&format!("store {elem_ll} {v}, ptr {dslot}"));
            }
        }
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: Some(addr),
            fields: HashMap::new(),
            array: Some(len),
        })
    }

    fn assign_array(&mut self, dst: &VarInfo, value: &Expr, pos: Position) -> TResult<()> {
        let elem = Self::array_elem_scalar(&dst.ty, pos.clone())?;
        let elem_ll = llvm_type(&elem);
        let len = dst.array.unwrap();
        let dbase = dst.addr.clone().unwrap();
        match &value.kind {
            ExprKind::Array(elems) => {
                if elems.len() != len {
                    return Err(TenetError::at_pos(
                        format!("数组赋值长度不匹配：需要 {len}，实际 {}", elems.len()),
                        value.pos.clone(),
                    ));
                }
                for (i, e) in elems.iter().enumerate() {
                    let (vt, v) = self.gen_expr(e)?;
                    if vt != elem_ll {
                        return Err(TenetError::at_pos(
                            format!(
                                "数组元素 {i} 类型不匹配：需要 {elem}，实际 {}",
                                tenet_name(&vt)
                            ),
                            e.pos.clone(),
                        ));
                    }
                    let slot = self.array_addr(&dbase, len, &i.to_string(), elem_ll);
                    self.ins(&format!("store {vt} {v}, ptr {slot}"));
                }
                Ok(())
            }
            ExprKind::Var(src) => {
                let sinfo = self.lookup_var(src, value.pos.clone())?;
                if sinfo.ty != dst.ty || sinfo.array != dst.array {
                    return Err(TenetError::at_pos(
                        format!("数组赋值类型不匹配：需要 {}，右侧是 {}", dst.ty, sinfo.ty),
                        value.pos.clone(),
                    ));
                }
                let sbase = sinfo.addr.clone().unwrap();
                for i in 0..len {
                    let sslot = self.array_addr(&sbase, len, &i.to_string(), elem_ll);
                    let dslot = self.array_addr(&dbase, len, &i.to_string(), elem_ll);
                    let v = self.tmp();
                    self.ins(&format!("{v} = load {elem_ll}, ptr {sslot}"));
                    self.ins(&format!("store {elem_ll} {v}, ptr {dslot}"));
                }
                Ok(())
            }
            _ => Err(TenetError::at_pos(
                "数组赋值必须是同类型数组变量或同长度字面量",
                value.pos.clone(),
            )),
        }
    }

    fn assign_struct(&mut self, dst: &VarInfo, value: &Expr, pos: Position) -> TResult<()> {
        match &value.kind {
            ExprKind::Var(src) => {
                let sinfo = self.lookup_var(src, value.pos.clone())?;
                if sinfo.ty != dst.ty {
                    return Err(TenetError::at_pos(
                        format!("赋值类型不匹配：需要 {}，右侧是 {}", dst.ty, sinfo.ty),
                        pos,
                    ));
                }
                self.copy_struct(dst, &sinfo)
            }
            ExprKind::StructLit { name: sname, fields: inits } => {
                if sname != &dst.ty {
                    return Err(TenetError::at_pos(
                        format!("赋值类型不匹配：需要 {}，字面量是 {sname}", dst.ty),
                        pos,
                    ));
                }
                let defs = self.struct_fields(&dst.ty, pos.clone())?;
                let mut map = HashMap::new();
                for (fname, fexpr) in inits {
                    if map.insert(fname.clone(), fexpr).is_some() {
                        return Err(TenetError::at_pos(
                            format!("struct `{}` 的字段 `{fname}` 重复初始化", dst.ty),
                            fexpr.pos.clone(),
                        ));
                    }
                }
                for (fname, fty) in &defs {
                    let Some(fexpr) = map.remove(fname) else {
                        return Err(TenetError::at_pos(
                            format!("struct `{}` 缺少字段 `{fname}`", dst.ty),
                            value.pos.clone(),
                        ));
                    };
                    let (vt, v) = self.gen_expr(fexpr)?;
                    if vt != llvm_type(fty) {
                        return Err(TenetError::at_pos(
                            format!(
                                "struct `{}` 字段 `{fname}` 类型不匹配：需要 {fty}，实际 {}",
                                dst.ty,
                                tenet_name(&vt)
                            ),
                            fexpr.pos.clone(),
                        ));
                    }
                    let addr = dst.fields[fname].addr.clone().unwrap();
                    self.ins(&format!("store {vt} {v}, ptr {addr}"));
                }
                if let Some((extra, e)) = map.into_iter().next() {
                    return Err(TenetError::at_pos(
                        format!("struct `{}` 没有字段 `{extra}`", dst.ty),
                        e.pos.clone(),
                    ));
                }
                Ok(())
            }
            _ => Err(TenetError::at_pos(
                "struct 整体赋值必须是同类型变量或字面量",
                value.pos.clone(),
            )),
        }
    }

    fn lookup_var(&self, name: &str, pos: Position) -> TResult<VarInfo> {
        for scope in self.symbols.iter().rev() {
            if let Some(info) = scope.get(name) {
                return Ok(info.clone());
            }
        }
        Err(TenetError::at_pos(format!("未定义的变量 `{name}`"), pos))
    }

    /// 为 struct 局部变量分配扁平字段槽位。
    fn alloc_struct(&mut self, ty: &str, pos: Position) -> TResult<VarInfo> {
        let defs = self.struct_fields(ty, pos)?;
        let mut fields = HashMap::new();
        for (fname, fty) in defs {
            let addr = self.tmp();
            self.ins(&format!("{addr} = alloca {}", llvm_type(&fty)));
            fields.insert(
                fname,
                VarInfo {
                    ty: fty,
                    addr: Some(addr),
                    fields: HashMap::new(),
                    array: None,
                },
            );
        }
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: None,
            fields,
            array: None,
        })
    }

    /// struct 初始化：从字面量或其他 struct 变量逐字段拷贝。
    fn init_struct(&mut self, name: &str, ty: &str, value: &Expr, pos: Position) -> TResult<VarInfo> {
        let defs = self.struct_fields(ty, pos.clone())?;
        let dst = self.alloc_struct(ty, pos.clone())?;
        match &value.kind {
            ExprKind::StructLit { name: sname, fields: inits } => {
                if sname != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 标注为 {ty}，但字面量是 {sname}"),
                        value.pos.clone(),
                    ));
                }
                let mut map = HashMap::new();
                for (fname, fexpr) in inits {
                    if map.insert(fname.clone(), fexpr).is_some() {
                        return Err(TenetError::at_pos(
                            format!("struct `{ty}` 的字段 `{fname}` 重复初始化"),
                            fexpr.pos.clone(),
                        ));
                    }
                }
                for (fname, fty) in &defs {
                    let Some(fexpr) = map.remove(fname) else {
                        return Err(TenetError::at_pos(
                            format!("struct `{ty}` 缺少字段 `{fname}`"),
                            value.pos.clone(),
                        ));
                    };
                    let (vt, v) = self.gen_expr(fexpr)?;
                    if vt != llvm_type(fty) {
                        return Err(TenetError::at_pos(
                            format!(
                                "struct `{ty}` 字段 `{fname}` 类型不匹配：需要 {fty}，实际 {}",
                                tenet_name(&vt)
                            ),
                            fexpr.pos.clone(),
                        ));
                    }
                    let addr = dst.fields[fname].addr.clone().unwrap();
                    self.ins(&format!("store {vt} {v}, ptr {addr}"));
                }
                if let Some((extra, e)) = map.into_iter().next() {
                    return Err(TenetError::at_pos(
                        format!("struct `{ty}` 没有字段 `{extra}`"),
                        e.pos.clone(),
                    ));
                }
                Ok(dst)
            }
            ExprKind::Var(src) => {
                let sinfo = self.lookup_var(src, value.pos.clone())?;
                if sinfo.ty != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，但 `{src}` 是 {}", sinfo.ty),
                        value.pos.clone(),
                    ));
                }
                self.copy_struct(&dst, &sinfo)?;
                Ok(dst)
            }
            _ => Err(TenetError::at_pos(
                format!("`{name}` 的 struct 初始化必须是 `{ty} {{ ... }}` 或同类型 struct 变量"),
                value.pos.clone(),
            )),
        }
    }

    fn copy_struct(&mut self, dst: &VarInfo, src: &VarInfo) -> TResult<()> {
        for (fname, dfield) in &dst.fields {
            let sfield = src.fields.get(fname).ok_or_else(|| {
                TenetError::at_pos(format!("struct 字段 `{fname}` 不存在"), Position::new(1, 1))
            })?;
            let (t, daddr) = (dfield.ty.clone(), dfield.addr.clone().unwrap());
            let saddr = sfield.addr.clone().unwrap();
            let v = self.tmp();
            self.ins(&format!("{v} = load {}, ptr {saddr}", llvm_type(&t)));
            self.ins(&format!("store {} {v}, ptr {daddr}", llvm_type(&t)));
        }
        Ok(())
    }

    /// 短路逻辑 && / ||：基本块跳转 + alloca 存结果（免 phi）。
    fn gen_logic(&mut self, op: &'static str, lhs: &Expr, rhs: &Expr) -> TResult<(String, String)> {
        let (lt, lv) = self.gen_expr(lhs)?;
        if lt != llvm_type(T_BOOL) {
            return Err(TenetError::at_pos(
                format!("运算符 `{op}` 只能作用于 bool，实际为 {}", tenet_name(&lt)),
                lhs.pos.clone(),
            ));
        }
        let res = self.tmp();
        self.ins(&format!("{res} = alloca i1"));
        let (rt, rv) = self.gen_expr(rhs)?;
        if rt != llvm_type(T_BOOL) {
            return Err(TenetError::at_pos(
                format!("运算符 `{op}` 只能作用于 bool，实际为 {}", tenet_name(&rt)),
                rhs.pos.clone(),
            ));
        }
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
        pos: Position,
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
            return Err(TenetError::at_pos(
                format!("运算符 `{op}` 不能作用于 string 和 string"),
                pos,
            ));
        }
        // 字符串与任何非字符串混合 → 编译错误（不得静默按数值处理）
        if (lt == str_ll) != (rt == str_ll) {
            let (s, o) = if lt == str_ll {
                (T_STR, tenet_name(&rt))
            } else {
                (tenet_name(&lt), T_STR)
            };
            return Err(TenetError::at_pos(
                format!("运算符 `{op}` 不能作用于 {s} 和 {o}"),
                pos,
            ));
        }
        // bool 不能参与数值与比较运算
        if lt == llvm_type(T_BOOL) || rt == llvm_type(T_BOOL) {
            return Err(TenetError::at_pos(
                format!(
                    "运算符 `{op}` 不能作用于 {} 和 {}",
                    tenet_name(&lt),
                    tenet_name(&rt)
                ),
                pos,
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
                return Err(TenetError::at_pos("运算符 `%` 只能作用于 int", pos));
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

    fn gen_call(&mut self, callee: &str, args: &[Expr], pos: Position) -> TResult<(String, String)> {
        if callee == "print" {
            return self.gen_print(args, pos);
        }
        if callee == "len" {
            if args.len() != 1 {
                return Err(TenetError::at_pos(
                    "`len` 需要且只需要一个数组参数".to_string(),
                    pos.clone(),
                ));
            }
            let ExprKind::Var(name) = &args[0].kind else {
                return Err(TenetError::at_pos(
                    "`len` 参数必须是数组变量",
                    args[0].pos.clone(),
                ));
            };
            let info = self.lookup_var(name, args[0].pos.clone())?;
            let Some(len) = info.array else {
                return Err(TenetError::at_pos(
                    format!("`{name}` 不是数组，不能取 len"),
                    args[0].pos.clone(),
                ));
            };
            return Ok((llvm_type(T_INT).into(), len.to_string()));
        }
        let sig = self
            .functions
            .get(callee)
            .ok_or_else(|| TenetError::at_pos(format!("未定义的函数 `{callee}`"), pos.clone()))?
            .clone();
        // 参数个数与类型核对（print 除外）
        if sig.params.len() != args.len() {
            return Err(TenetError::at_pos(
                format!(
                    "函数 `{callee}` 需要 {} 个参数，实际传入 {} 个",
                    sig.params.len(),
                    args.len()
                ),
                pos.clone(),
            ));
        }
        let ret_ll = sig.ret.as_deref().map(llvm_type).unwrap_or("void");
        let mut arg_ops = Vec::new();
        let mut arg_types = Vec::new();
        for (i, a) in args.iter().enumerate() {
            let (t, v) = self.gen_expr(a)?;
            let expect = llvm_type(&sig.params[i]);
            if t != expect {
                return Err(TenetError::at_pos(
                    format!(
                        "函数 `{callee}` 参数 {i} 类型不匹配：期望 {}，实际 {}",
                        sig.params[i],
                        tenet_name(&t)
                    ),
                    a.pos.clone(),
                ));
            }
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
    fn gen_print(&mut self, args: &[Expr], pos: Position) -> TResult<(String, String)> {
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
                _ => return Err(TenetError::at_pos("print 不支持该类型的值", pos)),
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
        Ok(match &expr.kind {
            ExprKind::Int(_) => Some(T_INT.to_string()),
            ExprKind::Float(_) => Some(T_FLOAT.to_string()),
            ExprKind::Str(_) => Some(T_STR.to_string()),
            ExprKind::Bool(_) => Some(T_BOOL.to_string()),
            ExprKind::Var(name) => Some(self.lookup_var(name, expr.pos.clone())?.ty),
            ExprKind::Index { base, index } => {
                let bt = self.infer_type(base)?;
                let Some(bt) = bt else {
                    return Err(TenetError::at_pos(
                        "无法推断数组类型".to_string(),
                        base.pos.clone(),
                    ));
                };
                let elem = Self::array_elem(&bt).ok_or_else(|| {
                    TenetError::at_pos(format!("`{bt}` 不是数组"), base.pos.clone())
                })?;
                let it = self.infer_type(index)?;
                if let Some(it) = it {
                    if it != T_INT {
                        return Err(TenetError::at_pos(
                            format!("数组下标必须是 int，实际为 {it}"),
                            index.pos.clone(),
                        ));
                    }
                }
                Some(elem.to_string())
            }
            ExprKind::Field { base, field } => {
                let ExprKind::Var(name) = &base.kind else {
                    return Err(TenetError::at_pos(
                        "v1 只支持对 struct 变量取字段",
                        base.pos.clone(),
                    ));
                };
                let info = self.lookup_var(name, base.pos.clone())?;
                if !self.is_struct(&info.ty) {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 不是 struct"),
                        base.pos.clone(),
                    ));
                }
                Some(
                    info.fields
                        .get(field)
                        .ok_or_else(|| {
                            TenetError::at_pos(
                                format!("struct `{}` 没有字段 `{field}`", info.ty),
                                expr.pos.clone(),
                            )
                        })?
                        .ty
                        .clone(),
                )
            }
            ExprKind::Array(elems) => {
                if elems.is_empty() {
                    return Err(TenetError::at_pos(
                        "v1 不支持空数组字面量".to_string(),
                        expr.pos.clone(),
                    ));
                }
                let first = self.infer_type(&elems[0])?;
                let Some(elem) = first else {
                    return Err(TenetError::at_pos(
                        "无法推断数组元素类型".to_string(),
                        expr.pos.clone(),
                    ));
                };
                if !matches!(elem.as_str(), T_INT | T_FLOAT | T_BOOL) {
                    return Err(TenetError::at_pos(
                        format!("v1 数组元素只支持 int/float/bool，实际 `{elem}`"),
                        expr.pos.clone(),
                    ));
                }
                for e in &elems[1..] {
                    let t = self.infer_type(e)?;
                    if t.as_deref() != Some(elem.as_str()) {
                        return Err(TenetError::at_pos(
                            format!(
                                "数组元素类型不一致：第一个是 {elem}，后面是 {}",
                                t.unwrap_or_else(|| "?".into())
                            ),
                            e.pos.clone(),
                        ));
                    }
                }
                Some(format!("array<{elem}>"))
            }
            ExprKind::StructLit { name, .. } => {
                self.struct_fields(name, expr.pos.clone())?;
                Some(name.clone())
            }
            ExprKind::Assign { target, .. } => Some(match &target.kind {
                ExprKind::Var(name) => self.lookup_var(name, target.pos.clone())?.ty,
                ExprKind::Index { base, .. } => {
                    let bt = self.infer_type(base)?;
                    let Some(bt) = bt else {
                        return Err(TenetError::at_pos(
                            "无法推断数组类型".to_string(),
                            base.pos.clone(),
                        ));
                    };
                    Self::array_elem(&bt)
                        .ok_or_else(|| {
                            TenetError::at_pos(format!("`{bt}` 不是数组"), base.pos.clone())
                        })?
                        .to_string()
                }
            ExprKind::Field { base, field } => {
                    let ExprKind::Var(name) = &base.kind else {
                        return Err(TenetError::at_pos(
                            "v1 只支持对 struct 变量取字段",
                            base.pos.clone(),
                        ));
                    };
                    let info = self.lookup_var(name, base.pos.clone())?;
                    info.fields
                        .get(field)
                        .ok_or_else(|| {
                            TenetError::at_pos(
                                format!("struct `{}` 没有字段 `{field}`", info.ty),
                                target.pos.clone(),
                            )
                        })?
                        .ty
                        .clone()
                }
                _ => {
                    return Err(TenetError::at_pos(
                        "赋值左侧必须是变量或字段",
                        target.pos.clone(),
                    ))
                }
            }),
            ExprKind::Unary { op, expr: inner } => match *op {
                crate::ast::OP_NOT => {
                    if let Some(t) = self.infer_type(inner)? {
                        if t != T_BOOL {
                            return Err(TenetError::at_pos(
                                format!("运算符 `!` 只能作用于 bool，实际为 {t}"),
                                inner.pos.clone(),
                            ));
                        }
                    }
                    Some(T_BOOL.to_string())
                }
                _ => {
                    let t = self.infer_type(inner)?;
                    if let Some(t) = &t {
                        if t == T_BOOL {
                            return Err(TenetError::at_pos(
                                "运算符 `-` 不能作用于 bool",
                                inner.pos.clone(),
                            ));
                        }
                    }
                    t
                }
            },
            ExprKind::Binary { op, lhs, rhs } => {
                let lt = self.infer_type(lhs)?;
                let rt = self.infer_type(rhs)?;
                match *op {
                    crate::ast::OP_AND | crate::ast::OP_OR => {
                        if let Some(t) = lt {
                            if t != T_BOOL {
                                return Err(TenetError::at_pos(
                                    format!("运算符 `{op}` 只能作用于 bool，实际为 {t}"),
                                    lhs.pos.clone(),
                                ));
                            }
                        }
                        if let Some(t) = rt {
                            if t != T_BOOL {
                                return Err(TenetError::at_pos(
                                    format!("运算符 `{op}` 只能作用于 bool，实际为 {t}"),
                                    rhs.pos.clone(),
                                ));
                            }
                        }
                        Some(T_BOOL.to_string())
                    }
                    crate::ast::OP_EQ
                    | crate::ast::OP_NEQ
                    | crate::ast::OP_LT
                    | crate::ast::OP_LTE
                    | crate::ast::OP_GT
                    | crate::ast::OP_GTE
                    | crate::ast::OP_ADD
                    | crate::ast::OP_SUB
                    | crate::ast::OP_MUL
                    | crate::ast::OP_DIV
                    | crate::ast::OP_MOD => {
                        // 字符串与任何非字符串混合 → 编译错误
                        if (lt.as_deref() == Some(T_STR)) != (rt.as_deref() == Some(T_STR)) {
                            if let (Some(l), Some(r)) = (lt.as_deref(), rt.as_deref()) {
                                return Err(TenetError::at_pos(
                                    format!("运算符 `{op}` 不能作用于 {l} 和 {r}"),
                                    expr.pos.clone(),
                                ));
                            }
                        }
                        // bool 不能参与数值与比较运算
                        if lt.as_deref() == Some(T_BOOL) || rt.as_deref() == Some(T_BOOL) {
                            let l = lt.as_deref().unwrap_or("?");
                            let r = rt.as_deref().unwrap_or("?");
                            return Err(TenetError::at_pos(
                                format!("运算符 `{op}` 不能作用于 {l} 和 {r}"),
                                expr.pos.clone(),
                            ));
                        }
                        match *op {
                            crate::ast::OP_EQ
                            | crate::ast::OP_NEQ
                            | crate::ast::OP_LT
                            | crate::ast::OP_LTE
                            | crate::ast::OP_GT
                            | crate::ast::OP_GTE => Some(T_BOOL.to_string()),
                            crate::ast::OP_MOD => {
                                if lt.as_deref() == Some(T_INT) && rt.as_deref() == Some(T_INT) {
                                    Some(T_INT.to_string())
                                } else if lt.is_some() && rt.is_some() {
                                    return Err(TenetError::at_pos(
                                        "运算符 `%` 只能作用于 int",
                                        expr.pos.clone(),
                                    ));
                                } else {
                                    None
                                }
                            }
                            crate::ast::OP_ADD => match (lt.as_deref(), rt.as_deref()) {
                                (Some(T_STR), Some(T_STR)) => Some(T_STR.to_string()),
                                (Some(T_FLOAT), _) | (_, Some(T_FLOAT)) => {
                                    Some(T_FLOAT.to_string())
                                }
                                (Some(T_INT), Some(T_INT)) => Some(T_INT.to_string()),
                                _ => None,
                            },
                            _ => match (lt.as_deref(), rt.as_deref()) {
                                (Some(T_FLOAT), _) | (_, Some(T_FLOAT)) => {
                                    Some(T_FLOAT.to_string())
                                }
                                (Some(T_INT), Some(T_INT)) => Some(T_INT.to_string()),
                                _ => None,
                            },
                        }
                    }
                    _ => unreachable!(),
                }
            }
            ExprKind::Call { callee, args } => {
                if callee == "print" {
                    None
                } else if callee == "len" {
                    if args.len() != 1 {
                        return Err(TenetError::at_pos(
                            "`len` 需要且只需要一个数组参数".to_string(),
                            expr.pos.clone(),
                        ));
                    }
                    let t = self.infer_type(&args[0])?;
                    let Some(t) = t else {
                        return Err(TenetError::at_pos(
                            "无法推断 `len` 参数类型".to_string(),
                            args[0].pos.clone(),
                        ));
                    };
                    if Self::array_elem(&t).is_none() {
                        return Err(TenetError::at_pos(
                            format!("`len` 参数必须是数组，实际是 {t}"),
                            args[0].pos.clone(),
                        ));
                    }
                    Some(T_INT.to_string())
                } else {
                    let sig = self.functions.get(callee).ok_or_else(|| {
                        TenetError::at_pos(format!("未定义的函数 `{callee}`"), expr.pos.clone())
                    })?;
                    sig.ret.clone()
                }
            }
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

    fn err_pos(src: &str) -> (String, Option<Position>) {
        match gen(src) {
            Ok(_) => panic!("期望编译错误: {src}"),
            Err(e) => (e.message.clone(), e.pos.clone()),
        }
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
        let (msg, pos) = err_pos("fn f() -> int { let x: int = 1; }");
        assert!(msg.contains("末尾没有 return"), "{msg}");
        assert_eq!(pos, Some(Position::new(1, 1)));
    }

    #[test]
    fn reserved_function_name_errors() {
        let err = gen("fn main() { }").unwrap_err();
        assert!(err.message.contains("保留"), "{}", err);
    }

    // ---- 混合类型（string × 非 string）----

    #[test]
    fn string_plus_int_implicit_errors() {
        let (msg, pos) = err_pos("let a: string = \"x\";\nlet b = a + 1;");
        assert_eq!(msg, "运算符 `+` 不能作用于 string 和 int", "{msg}");
        assert_eq!(pos, Some(Position::new(2, 9))); // `a` 的位置
    }

    #[test]
    fn string_plus_int_explicit_errors() {
        let (msg, pos) = err_pos("let a: string = \"x\";\nlet b: int = a + 1;");
        assert_eq!(msg, "运算符 `+` 不能作用于 string 和 int", "{msg}");
        assert_eq!(pos, Some(Position::new(2, 14))); // 二元表达式 `a` 的位置
    }

    #[test]
    fn string_compare_int_errors() {
        let (msg, _) = err_pos("let a: string = \"x\";\nlet b = a < 1;");
        assert_eq!(msg, "运算符 `<` 不能作用于 string 和 int", "{msg}");
    }

    #[test]
    fn int_plus_string_errors() {
        let (msg, _) = err_pos("let b = 1 + \"x\";");
        assert_eq!(msg, "运算符 `+` 不能作用于 int 和 string", "{msg}");
    }

    // ---- bool 不能参与数值/比较运算 ----

    #[test]
    fn bool_plus_int_errors() {
        let (msg, _) = err_pos("let b = true + 1;");
        assert_eq!(msg, "运算符 `+` 不能作用于 bool 和 int", "{msg}");
    }

    #[test]
    fn bool_compare_errors() {
        let (msg, _) = err_pos("let b = true == 1;");
        assert_eq!(msg, "运算符 `==` 不能作用于 bool 和 int", "{msg}");
    }

    #[test]
    fn logic_requires_bool() {
        let (msg, _) = err_pos("let b = 1 && true;");
        assert_eq!(msg, "运算符 `&&` 只能作用于 bool，实际为 int", "{msg}");
    }

    #[test]
    fn not_requires_bool() {
        let (msg, _) = err_pos("let b = !5;");
        assert_eq!(msg, "运算符 `!` 只能作用于 bool，实际为 int", "{msg}");
    }

    #[test]
    fn mod_requires_int() {
        let (msg, _) = err_pos("let b = 5.5 % 2;");
        assert_eq!(msg, "运算符 `%` 只能作用于 int", "{msg}");
    }

    #[test]
    fn condition_requires_bool() {
        let (msg, pos) = err_pos("if (1) { print(1); }");
        assert_eq!(msg, "条件表达式需要 bool，实际为 int", "{msg}");
        assert_eq!(pos, Some(Position::new(1, 5)));
    }

    // ---- 声明 / 赋值 / 调用 / 返回类型核对 ----

    #[test]
    fn declared_type_mismatch_errors() {
        let (msg, _) = err_pos("let b: int = \"x\";");
        assert_eq!(msg, "`b` 初始化类型不匹配：标注 int，实际 string", "{msg}");
    }

    #[test]
    fn assign_type_mismatch_errors() {
        let (msg, _) = err_pos("let b: int = 1;\nb = \"x\";");
        assert_eq!(msg, "赋值类型不匹配：`b` 是 int，右侧是 string", "{msg}");
    }

    #[test]
    fn call_arg_type_mismatch_errors() {
        let (msg, _) = err_pos("fn f(x: int) -> int { return x; }\nf(\"s\");");
        assert_eq!(msg, "函数 `f` 参数 0 类型不匹配：期望 int，实际 string", "{msg}");
    }

    #[test]
    fn call_arg_count_mismatch_errors() {
        let (msg, _) = err_pos("fn f(x: int) -> int { return x; }\nf(1, 2);");
        assert_eq!(msg, "函数 `f` 需要 1 个参数，实际传入 2 个", "{msg}");
    }

    #[test]
    fn return_type_mismatch_errors() {
        let (msg, _) = err_pos("fn f() -> int { return \"s\"; }");
        assert_eq!(msg, "函数 `f` 返回类型不匹配：声明 int，实际 string", "{msg}");
    }

    #[test]
    fn return_value_in_void_errors() {
        let (msg, _) = err_pos("fn f() { return 1; }");
        assert_eq!(msg, "函数 `f` 没有返回类型，不能 return 值", "{msg}");
    }

    // ---- 错误定位 ----

    #[test]
    fn undefined_var_has_position() {
        let (msg, pos) = err_pos("let x: int = 1;\nlet y = unknown + 1;");
        assert_eq!(msg, "未定义的变量 `unknown`", "{msg}");
        assert_eq!(pos, Some(Position::new(2, 9)));
    }

    #[test]
    fn undefined_fn_has_position() {
        let (msg, pos) = err_pos("let x = nope(1);");
        assert_eq!(msg, "未定义的函数 `nope`", "{msg}");
        assert_eq!(pos, Some(Position::new(1, 9)));
    }

    // ---- struct v1 ----

    #[test]
    fn struct_fields_are_flattened() {
        let ir = gen(
            "struct Point { x: int; y: int; }\n\
             let p: Point = Point { x: 1, y: 2 };\n\
             p.x = p.x + 1;\n\
             print(p.x, p.y);",
        )
        .unwrap();
        assert!(ir.contains("alloca i64"), "{ir}");
        assert!(ir.contains("store i64"), "{ir}");
        assert!(ir.contains("load i64"), "{ir}");
        assert!(!ir.contains("%Point"), "struct 不应生成聚合类型: {ir}");
    }

    #[test]
    fn struct_copy_is_fieldwise() {
        let ir = gen(
            "struct Point { x: int; y: float; }\n\
             let p: Point = Point { x: 1, y: 2.0 };\n\
             let q = p;\n\
             q.x = 9;\n\
             print(p.x, q.x);",
        )
        .unwrap();
        assert!(ir.contains("alloca double"), "{ir}");
        // p/q 各有 x/y 两个槽位，至少 4 个 alloca
        assert!(ir.matches("alloca i64").count() >= 2, "{ir}");
        assert!(ir.matches("alloca double").count() >= 2, "{ir}");
    }

    #[test]
    fn struct_missing_field_errors() {
        let (msg, _) = err_pos(
            "struct Point { x: int; y: int; }\nlet p: Point = Point { x: 1 };",
        );
        assert!(msg.contains("缺少字段 `y`"), "{msg}");
    }

    #[test]
    fn struct_unknown_field_errors() {
        let (msg, _) = err_pos(
            "struct Point { x: int; }\nlet p: Point = Point { x: 1, z: 2 };",
        );
        assert!(msg.contains("没有字段 `z`"), "{msg}");
    }

    #[test]
    fn struct_field_type_mismatch_errors() {
        let (msg, _) = err_pos(
            "struct Point { x: int; }\nlet p: Point = Point { x: \"s\" };",
        );
        assert!(msg.contains("字段 `x` 类型不匹配"), "{msg}");
    }

    #[test]
    fn struct_param_is_rejected() {
        let (msg, _) = err_pos(
            "struct Point { x: int; }\nfn f(p: Point) -> int { return p.x; }",
        );
        assert!(msg.contains("不支持 struct 参数"), "{msg}");
    }

    #[test]
    fn struct_ret_is_rejected() {
        let (msg, _) = err_pos(
            "struct Point { x: int; }\nfn f() -> Point { return Point { x: 1 }; }",
        );
        assert!(msg.contains("不支持 struct 返回值"), "{msg}");
    }


    #[test]
    fn struct_whole_assign_copies() {
        let ir = gen(
            "struct Point { x: int; y: int; }\n\
             let p: Point = Point { x: 1, y: 2 };\n\
             let q: Point = Point { x: 0, y: 0 };\n\
             q = p;\n\
             q.x = 9;\n\
             print(p.x, q.x);",
        )
        .unwrap();
        assert!(ir.contains("store i64"), "{ir}");
    }

    #[test]
    fn struct_print_errors() {
        let (msg, _) = err_pos(
            "struct Point { x: int; }\nlet p: Point = Point { x: 1 };\nprint(p);",
        );
        assert!(msg.contains("struct 变量"), "{msg}");
    }

    #[test]
    fn struct_duplicate_field_errors() {
        let (msg, _) = err_pos("struct Point { x: int; x: float; }");
        assert!(msg.contains("字段 `x` 重复"), "{msg}");
    }

    #[test]
    fn struct_field_string_is_rejected() {
        let (msg, _) = err_pos("struct Point { s: string; }");
        assert!(msg.contains("只支持 int/float/bool"), "{msg}");
    }

    #[test]
    fn nested_struct_decl_is_rejected() {
        let (msg, _) = err_pos("struct Point { x: int; }\nfn f() { struct Inner { y: int; } }");
        assert!(msg.contains("顶层"), "{msg}");
    }


    // ---- array v1 ----

    #[test]
    fn array_literal_alloca_and_index() {
        let ir = gen(
            "let a: array<int> = [1, 2, 3];\n\
             a[0] = a[1] + 1;\n\
             print(a[0], len(a));",
        )
        .unwrap();
        assert!(ir.contains("alloca [3 x i64]"), "{ir}");
        assert!(ir.contains("getelementptr [3 x i64]"), "{ir}");
        assert!(ir.contains("store i64"), "{ir}");
    }

    #[test]
    fn array_copy_is_elementwise() {
        let ir = gen(
            "let a = [1, 2];\nlet b = a;\na[0] = 9;\nprint(a[0], b[0]);",
        )
        .unwrap();
        assert!(ir.matches("alloca [2 x i64]").count() >= 2, "{ir}");
    }

    #[test]
    fn array_len_is_constant() {
        let ir = gen("let a = [1, 2, 3];\nprint(len(a));").unwrap();
        assert!(ir.contains("i64 3"), "{ir}");
    }

    #[test]
    fn array_float_and_bool_elements() {
        let ir = gen("let f: array<float> = [1.5, 2.5];\nprint(f[0], f[1]);").unwrap();
        assert!(ir.contains("alloca [2 x double]"), "{ir}");
        let ir = gen("let b: array<bool> = [true, false];\nprint(b[0], b[1]);").unwrap();
        assert!(ir.contains("alloca [2 x i1]"), "{ir}");
    }

    #[test]
    fn array_constant_index_out_of_bounds_errors() {
        let (msg, _) = err_pos("let a = [1, 2];\nprint(a[2]);");
        assert!(msg.contains("越界"), "{msg}");
    }

    #[test]
    fn array_element_type_mismatch_errors() {
        let (msg, _) = err_pos("let a: array<int> = [1, 2.0];");
        assert!(msg.contains("类型不匹配"), "{msg}");
    }

    #[test]
    fn array_param_is_rejected() {
        let (msg, _) = err_pos("fn f(a: array<int>) -> int { return 0; }");
        assert!(msg.contains("不支持 array 参数"), "{msg}");
    }

    #[test]
    fn array_ret_is_rejected() {
        let (msg, _) = err_pos("fn f() -> array<int> { return [1]; }");
        assert!(msg.contains("不支持 array 返回值"), "{msg}");
    }

    #[test]
    fn empty_array_is_rejected() {
        let (msg, _) = err_pos("let a: array<int> = [];");
        assert!(msg.contains("空数组"), "{msg}");
    }

    #[test]
    fn array_direct_print_is_rejected() {
        let (msg, _) = err_pos("let a = [1, 2];\nprint(a);");
        assert!(msg.contains("数组变量"), "{msg}");
    }

}
