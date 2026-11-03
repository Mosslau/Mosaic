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
enum TempDyn {
    Var(VarInfo),
    Desc { desc: String, ty: String },
}

#[derive(Clone)]
struct DynArrayInfo {
    data: String,
    len: String,
    cap: String,
}

#[derive(Clone)]
struct VarInfo {
    ty: String,
    addr: Option<String>,
    fields: HashMap<String, VarInfo>,
    /// 固定数组的定长长度；非固定数组为 None。
    array: Option<usize>,
    /// 动态数组的 data/len/cap 槽位；非动态数组为 None。
    dyn_array: Option<DynArrayInfo>,
}

/// struct 的扁平槽位布局条目。
///
/// - `path`：字段点路径（嵌套 struct 会递归展开成 `inner.x` 这种形式）。
/// - `ty`：标量字段类型，或数组字段的完整数组类型。
/// - `offset`：相对 struct 起始的 8 字节槽偏移（不是字段序号）。
/// - `slots`：该字段占用的槽数；标量为 1，固定数组为 `N * elem_slots`，
///   动态数组为 3（data/len/cap descriptor）。
#[derive(Clone)]
struct LayoutEntry {
    path: String,
    ty: String,
    offset: usize,
    slots: usize,
}

/// 左值解析结果：支持 `s.a[i]`、`s.a[i].f`、`s.a[i][j]` 这类
/// 「struct 变量 / 固定数组字段 / 数组元素」组合出的地址。
#[derive(Clone)]
enum Place {
    Scalar {
        ty: String,
        addr: String,
    },
    /// 固定数组；`packed=true` 表示数据是扁平 i64 槽（struct 字段），
    /// false 表示普通局部数组的 `[N x T]` 表示。
    Array {
        ty: String,
        addr: String,
        len: usize,
        packed: bool,
    },
    /// 动态数组 descriptor：三个槽的地址（data ptr / len i64 / cap i64）。
    /// 可以来自局部动态数组、struct 的局部字段，也可以来自扁平槽块中的字段。
    DynArray {
        ty: String,
        info: DynArrayInfo,
    },
    /// struct 值：局部变量用 `fields` 字段表；数组元素/字段块用 `addr`。
    Struct {
        ty: String,
        addr: Option<String>,
        fields: Option<HashMap<String, VarInfo>>,
        prefix: String,
    },
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
    loop_depths: Vec<usize>,
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
            loop_depths: Vec::new(),
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
        // 先收集所有名字与字段，允许前向引用。
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
                if !seen.insert(fname.clone()) {
                    return Err(TenetError::at_pos(
                        format!("struct `{name}` 的字段 `{fname}` 重复"),
                        stmt.pos.clone(),
                    ));
                }
                if fty == "string" {
                    return Err(TenetError::at_pos(
                        format!(
                            "struct `{name}` 的字段 `{fname}` 只支持 int/float/bool、\
                             其他 struct、固定数组或标量动态数组"
                        ),
                        stmt.pos.clone(),
                    ));
                }
                if self.is_array(fty) {
                    self.validate_struct_array_field(name, fname, fty, stmt.pos.clone())?;
                }
            }
            self.structs.insert(name.clone(), fields.clone());
        }
        // 再校验字段类型与循环嵌套。
        let names: Vec<String> = self.structs.keys().cloned().collect();
        for name in names {
            let fields = self.structs.get(&name).unwrap().clone();
            for (fname, fty) in &fields {
                self.check_field_type_defined(&name, fname, fty)?;
            }
            let mut stack = Vec::new();
            self.check_struct_cycle(&name, &mut stack)?;
        }
        Ok(())
    }

    /// struct 字段的数组校验：
    /// - 固定数组：每一层都必须是固定长度，元素限标量或 struct；
    /// - 动态数组（v1）：只允许标量元素 `array<int/float/bool>`，占 3 个
    ///   descriptor 槽；不支持动态 `array<struct>` 与动态嵌套字段。
    fn validate_struct_array_field(
        &self,
        sname: &str,
        fname: &str,
        fty: &str,
        pos: Position,
    ) -> TResult<()> {
        let elem = Self::array_elem(fty).unwrap();
        if Self::array_decl_len(fty).is_none() {
            if self.is_array(elem) {
                return Err(TenetError::at_pos(
                    format!(
                        "struct `{sname}` 的字段 `{fname}` 不支持动态嵌套数组字段；\
                         v1 只支持一层动态数组 `array<int/float/bool>`"
                    ),
                    pos,
                ));
            }
            if self.is_struct(elem) {
                return Err(TenetError::at_pos(
                    format!(
                        "struct `{sname}` 的字段 `{fname}` 不支持动态 array<struct> 字段；\
                         v1 的动态数组字段元素只支持 int/float/bool"
                    ),
                    pos,
                ));
            }
            if elem == T_STR {
                return Err(TenetError::at_pos(
                    format!("struct `{sname}` 的字段 `{fname}` 的数组元素不支持 string"),
                    pos,
                ));
            }
            // 标量元素（或未定义的 struct 名，交给第二阶段检查）。
            return Ok(());
        }
        let mut cur = fty.to_string();
        loop {
            if Self::array_decl_len(&cur).is_none() {
                return Err(TenetError::at_pos(
                    format!(
                        "struct `{sname}` 的字段 `{fname}` 的固定数组内层不支持动态数组；\
                         v1 固定数组的每一层都必须是固定长度"
                    ),
                    pos,
                ));
            }
            let inner = Self::array_elem(&cur).unwrap();
            if self.is_array(inner) {
                cur = inner.to_string();
                continue;
            }
            if self.is_struct(inner) || matches!(inner, T_INT | T_FLOAT | T_BOOL) {
                return Ok(());
            }
            if inner == T_STR {
                return Err(TenetError::at_pos(
                    format!("struct `{sname}` 的字段 `{fname}` 的数组元素不支持 string"),
                    pos,
                ));
            }
            // 未定义的 struct 名交给第二阶段的类型检查报错。
            return Ok(());
        }
    }

    /// 字段类型（含固定数组元素）必须已定义。
    fn check_field_type_defined(&self, sname: &str, fname: &str, fty: &str) -> TResult<()> {
        let mut cur = fty.to_string();
        loop {
            if let Some(inner) = Self::array_elem(&cur) {
                cur = inner.to_string();
                continue;
            }
            if matches!(cur.as_str(), T_INT | T_FLOAT | T_BOOL) || self.structs.contains_key(&cur) {
                return Ok(());
            }
            return Err(TenetError::at_pos(
                format!("struct `{sname}` 的字段 `{fname}` 类型 `{cur}` 未定义"),
                Position::new(1, 1),
            ));
        }
    }

    /// 若 `ty` 是固定数组且最内层元素是 struct 名，返回该 struct 名。
    fn array_elem_struct(ty: &str) -> Option<String> {
        if Self::array_elem(ty).is_none() {
            return None;
        }
        let mut cur = ty;
        while let Some(inner) = Self::array_elem(cur) {
            cur = inner;
        }
        if matches!(cur, T_INT | T_FLOAT | T_BOOL) {
            None
        } else {
            Some(cur.to_string())
        }
    }

    fn check_struct_cycle(&self, ty: &str, stack: &mut Vec<String>) -> TResult<()> {
        if stack.iter().any(|t| t == ty) {
            let mut cycle = stack.clone();
            cycle.push(ty.to_string());
            return Err(TenetError::at_pos(
                format!("struct 循环嵌套：{}", cycle.join(" -> ")),
                Position::new(1, 1),
            ));
        }
        if !self.is_struct(ty) {
            return Ok(());
        }
        stack.push(ty.to_string());
        for (_, fty) in self.structs.get(ty).unwrap() {
            if let Some(inner) = Self::array_elem_struct(fty) {
                self.check_struct_cycle(&inner, stack)?;
            } else if self.is_struct(fty) {
                self.check_struct_cycle(fty, stack)?;
            }
        }
        stack.pop();
        Ok(())
    }

    /// 一个字段类型占用的 8 字节槽数：
    /// 标量 1 槽；固定数组 `N * elem_slots`；动态数组 3 槽（data/len/cap）；
    /// struct 递归求和。
    fn field_slot_width(&self, ty: &str) -> usize {
        if Self::is_dynamic_array(ty) {
            3
        } else if let Some(n) = Self::array_decl_len(ty) {
            n * self.array_elem_slots(ty).unwrap_or(1)
        } else if self.is_struct(ty) {
            self.struct_total_slots(ty)
        } else {
            1
        }
    }

    /// 一个值在扁平 i64 槽块中占用的槽数（标量 / struct / 固定数组 / 动态 descriptor）。
    fn value_slots(&self, ty: &str) -> usize {
        self.field_slot_width(ty)
    }

    /// 该类型是否（递归地）拥有需要释放的堆内存：
    /// 动态数组自身；固定数组看元素；struct 看字段。
    fn type_owns_heap(&self, ty: &str) -> bool {
        if Self::is_dynamic_array(ty) {
            return true;
        }
        if let Some(elem) = Self::array_elem(ty) {
            return self.type_owns_heap(elem);
        }
        if let Some(fields) = self.structs.get(ty) {
            return fields.iter().any(|(_, fty)| self.type_owns_heap(fty));
        }
        false
    }

    /// struct 的总槽数（固定数组字段按 `N * elem_slots` 计入）。
    fn struct_total_slots(&self, ty: &str) -> usize {
        let Some(fields) = self.structs.get(ty) else {
            return 0;
        };
        fields
            .iter()
            .map(|(_, fty)| self.field_slot_width(fty))
            .sum()
    }

    /// struct 的扁平槽位布局：标量字段 1 槽，固定数组字段占 `N * elem_slots` 槽，
    /// 嵌套 struct 递归展开。返回顺序即 ABI 槽位顺序。
    fn layout_of(&self, ty: &str) -> Vec<LayoutEntry> {
        let mut out = Vec::new();
        let mut offset = 0;
        self.layout_into(ty, "", &mut offset, &mut out);
        out
    }

    fn layout_into(
        &self,
        ty: &str,
        prefix: &str,
        offset: &mut usize,
        out: &mut Vec<LayoutEntry>,
    ) {
        let Some(fields) = self.structs.get(ty) else {
            return;
        };
        for (fname, fty) in fields {
            let path = if prefix.is_empty() {
                fname.clone()
            } else {
                format!("{prefix}.{fname}")
            };
            if self.is_struct(fty) {
                self.layout_into(fty, &path, offset, out);
            } else if self.is_array(fty) {
                let slots = self.field_slot_width(fty);
                out.push(LayoutEntry {
                    path,
                    ty: fty.clone(),
                    offset: *offset,
                    slots,
                });
                *offset += slots;
            } else {
                out.push(LayoutEntry {
                    path,
                    ty: fty.clone(),
                    offset: *offset,
                    slots: 1,
                });
                *offset += 1;
            }
        }
    }

    /// 字段在所属 struct 中的起始槽偏移。
    fn field_slot_offset(&self, ty: &str, path: &str) -> Option<usize> {
        self.layout_of(ty)
            .iter()
            .find(|e| e.path == path)
            .map(|e| e.offset)
    }

    fn field_type_of(&self, ty: &str, path: &str) -> TResult<String> {
        let mut cur = ty.to_string();
        for part in path.split('.') {
            let fields = self.structs.get(&cur).ok_or_else(|| {
                TenetError::at_pos(format!("`{cur}` 不是 struct"), Position::new(1, 1))
            })?;
            let fty = fields
                .iter()
                .find(|(n, _)| n == part)
                .map(|(_, t)| t.clone())
                .ok_or_else(|| {
                    TenetError::at_pos(
                        format!("struct `{cur}` 没有字段 `{part}`"),
                        Position::new(1, 1),
                    )
                })?;
            cur = fty;
        }
        Ok(cur)
    }

    fn is_struct(&self, ty: &str) -> bool {
        self.structs.contains_key(ty)
    }

    fn is_array(&self, ty: &str) -> bool {
        Self::array_elem(ty).is_some()
    }

    fn array_inner(ty: &str) -> Option<(&str, Option<usize>)> {
        let inner = ty.strip_prefix("array<")?.strip_suffix('>')?;
        let mut depth = 0i32;
        let mut split = None;
        for (i, ch) in inner.char_indices() {
            match ch {
                '<' => depth += 1,
                '>' => depth -= 1,
                ',' if depth == 0 => split = Some(i),
                _ => {}
            }
        }
        match split {
            Some(i) => {
                let elem = &inner[..i];
                let n = inner[i + 1..].parse().ok()?;
                Some((elem, Some(n)))
            }
            None => Some((inner, None)),
        }
    }

    fn array_elem(ty: &str) -> Option<&str> {
        Self::array_inner(ty).map(|(e, _)| e)
    }

    fn array_decl_len(ty: &str) -> Option<usize> {
        Self::array_inner(ty).and_then(|(_, n)| n)
    }

    fn struct_fields(&self, ty: &str, pos: Position) -> TResult<Vec<(String, String)>> {
        self.structs
            .get(ty)
            .cloned()
            .ok_or_else(|| TenetError::at_pos(format!("未定义的 struct `{ty}`"), pos))
    }

    fn buffer_slot(&mut self, buf: &str, n: usize, i: usize) -> String {
        let addr = self.tmp();
        self.ins(&format!(
            "{addr} = getelementptr [{n} x i64], ptr {buf}, i64 0, i64 {i}"
        ));
        addr
    }

    fn alloc_buffer(&mut self, n: usize) -> String {
        let buf = self.tmp();
        self.ins(&format!("{buf} = alloca [{n} x i64]"));
        buf
    }

    fn pack_scalar(&mut self, ty: &str, v: &str) -> String {
        match ty {
            T_INT => v.to_string(),
            T_BOOL => {
                let r = self.tmp();
                self.ins(&format!("{r} = zext i1 {v} to i64"));
                r
            }
            T_FLOAT => {
                let r = self.tmp();
                self.ins(&format!("{r} = bitcast double {v} to i64"));
                r
            }
            _ => unreachable!("struct 字段只允许 int/float/bool"),
        }
    }

    fn unpack_scalar(&mut self, ty: &str, raw: &str) -> String {
        match ty {
            T_INT => raw.to_string(),
            T_BOOL => {
                let r = self.tmp();
                self.ins(&format!("{r} = trunc i64 {raw} to i1"));
                r
            }
            T_FLOAT => {
                let r = self.tmp();
                self.ins(&format!("{r} = bitcast i64 {raw} to double"));
                r
            }
            _ => unreachable!("struct 字段只允许 int/float/bool"),
        }
    }

    fn flatten_literal(
        &self,
        ty: &str,
        fields: &[(String, Expr)],
        prefix: &str,
    ) -> TResult<Vec<(String, Expr)>> {
        let defs = self.struct_fields(ty, Position::new(1, 1))?;
        let mut map = HashMap::new();
        for (fname, fexpr) in fields {
            if map.insert(fname.clone(), fexpr.clone()).is_some() {
                return Err(TenetError::at_pos(
                    format!("struct `{ty}` 的字段 `{fname}` 重复初始化"),
                    fexpr.pos.clone(),
                ));
            }
        }
        let mut out = Vec::new();
        for (fname, fty) in defs {
            let Some(fexpr) = map.remove(&fname) else {
                return Err(TenetError::at_pos(
                    format!("struct `{ty}` 缺少字段 `{fname}`"),
                    Position::new(1, 1),
                ));
            };
            let path = if prefix.is_empty() {
                fname.clone()
            } else {
                format!("{prefix}.{fname}")
            };
            if self.is_struct(&fty) {
                let ExprKind::StructLit { name, fields } = &fexpr.kind else {
                    return Err(TenetError::at_pos(
                        format!("字段 `{path}` 需要 {fty} 字面量"),
                        fexpr.pos.clone(),
                    ));
                };
                if name != &fty {
                    return Err(TenetError::at_pos(
                        format!("字段 `{path}` 需要 {fty}，实际字面量是 {name}"),
                        fexpr.pos.clone(),
                    ));
                }
                out.extend(self.flatten_literal(&fty, fields, &path)?);
            } else {
                out.push((path, fexpr));
            }
        }
        if let Some((extra, e)) = map.into_iter().next() {
            return Err(TenetError::at_pos(
                format!("struct `{ty}` 没有字段 `{extra}`"),
                e.pos.clone(),
            ));
        }
        Ok(out)
    }

    /// 扁平 i64 槽缓冲中的第 i 个槽地址。
    fn flat_slot(&mut self, buf: &str, i: usize) -> String {
        let addr = self.tmp();
        self.ins(&format!("{addr} = getelementptr i64, ptr {buf}, i64 {i}"));
        addr
    }

    /// 把「标量元素固定数组」的局部表示 `[N x elem]` 逐元素打包进 i64 槽缓冲。
    fn copy_scalar_array_to_packed_slots(
        &mut self,
        ty: &str,
        src: &str,
        buf: &str,
        off: usize,
    ) {
        let elem = Self::array_elem(ty).unwrap();
        let len = Self::array_decl_len(ty).unwrap();
        let elem_ll = llvm_type(elem);
        for i in 0..len {
            let s = self.array_slot(src, len, elem_ll, i);
            let v = self.tmp();
            self.ins(&format!("{v} = load {elem_ll}, ptr {s}"));
            let raw = self.pack_scalar(elem, &v);
            let d = self.flat_slot(buf, off + i);
            self.ins(&format!("store i64 {raw}, ptr {d}"));
        }
    }

    /// 把固定数组表达式打包进 `buf` 的 i64 槽区（从 `off` 开始，共 total 槽）。
    ///
    /// struct 字段的数组统一用扁平 i64 槽表示：
    /// - 标量元素：每个元素 zext/bitcast 成一个 i64 槽；
    /// - `array<struct, N>` / 固定嵌套数组：元素本身就是若干 i64 槽。
    fn pack_array_field_expr(
        &mut self,
        ty: &str,
        expr: &Expr,
        buf: &str,
        off: usize,
    ) -> TResult<()> {
        let total = self.fixed_array_total_slots(ty)?;
        let elem = self.array_elem_or_err(ty, expr.pos.clone())?;
        if self.is_struct(&elem) || self.is_array(&elem) {
            let tmp = self.alloc_buffer(total);
            self.pack_fixed_array_expr(ty, expr, &tmp)?;
            let dst = self.flat_slot(buf, off);
            self.copy_flat_i64(&dst, &tmp, total);
            return Ok(());
        }
        let len = Self::array_decl_len(ty).unwrap();
        let elem_ll = llvm_type(&elem);
        match &expr.kind {
            ExprKind::Array(elems) => {
                if elems.len() != len {
                    return Err(TenetError::at_pos(
                        format!("数组长度不匹配：类型写 {len}，字面量 {}", elems.len()),
                        expr.pos.clone(),
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
                    let raw = self.pack_scalar(&elem, &v);
                    let d = self.flat_slot(buf, off + i);
                    self.ins(&format!("store i64 {raw}, ptr {d}"));
                }
                Ok(())
            }
            ExprKind::Var(name) => {
                let info = self.lookup_var(name, expr.pos.clone())?;
                if info.ty != ty || info.array != Some(len) || info.dyn_array.is_some() {
                    return Err(TenetError::at_pos(
                        format!("数组类型不匹配：需要 {ty}，实际是 {}", info.ty),
                        expr.pos.clone(),
                    ));
                }
                let src = info.addr.clone().unwrap();
                self.copy_scalar_array_to_packed_slots(ty, &src, buf, off);
                Ok(())
            }
            ExprKind::Call { .. } => {
                let (rt, src) = self.gen_expr(expr)?;
                if rt != ty {
                    return Err(TenetError::at_pos(
                        format!("数组类型不匹配：需要 {ty}，调用返回 {rt}"),
                        expr.pos.clone(),
                    ));
                }
                self.copy_scalar_array_to_packed_slots(ty, &src, buf, off);
                Ok(())
            }
            ExprKind::Field { .. } => {
                // 另一个 struct 的数组字段（已是扁平 i64 槽表示）。
                match self.resolve_place(expr)? {
                    Some(Place::Array {
                        ty: sty,
                        addr,
                        len: slen,
                        packed: true,
                    }) if sty == ty && slen == len => {
                        let dst = self.flat_slot(buf, off);
                        self.copy_flat_i64(&dst, &addr, total);
                        Ok(())
                    }
                    _ => Err(TenetError::at_pos(
                        format!("字段 `{ty}` 的初始化必须是同类型数组字面量、变量或调用"),
                        expr.pos.clone(),
                    )),
                }
            }
            _ => Err(TenetError::at_pos(
                format!("字段 `{ty}` 的初始化必须是同类型数组字面量、变量或调用"),
                expr.pos.clone(),
            )),
        }
    }

    /// 把一个动态数组表达式初始化后写入扁平 struct buffer 的 descriptor 三槽。
    /// 新数组的所有权随槽位转移给 buffer / 调用方。
    fn pack_dyn_field_expr(
        &mut self,
        ty: &str,
        expr: &Expr,
        buf: &str,
        off: usize,
    ) -> TResult<()> {
        let tmp = self.init_dynamic_array("__field_tmp", ty, expr, expr.pos.clone())?;
        let di = tmp.dyn_array.as_ref().unwrap();
        let p = self.dyn_load(&di.data, "ptr");
        let l = self.dyn_load(&di.len, "i64");
        let c = self.dyn_load(&di.cap, "i64");
        let s0 = self.flat_slot(buf, off);
        let s1 = self.flat_slot(buf, off + 1);
        let s2 = self.flat_slot(buf, off + 2);
        self.ins(&format!("store ptr {p}, ptr {s0}"));
        self.ins(&format!("store i64 {l}, ptr {s1}"));
        self.ins(&format!("store i64 {c}, ptr {s2}"));
        Ok(())
    }

    fn unpack_buffer(&mut self, dst: &VarInfo, ty: &str, buf: &str) -> TResult<()> {
        let n = self.struct_total_slots(ty);
        for entry in self.layout_of(ty) {
            if Self::is_dynamic_array(&entry.ty) {
                let f = dst.fields.get(&entry.path).ok_or_else(|| {
                    TenetError::at_pos(
                        format!("缺少字段槽 `{}`", entry.path),
                        Position::new(1, 1),
                    )
                })?;
                let di = f.dyn_array.as_ref().ok_or_else(|| {
                    TenetError::at_pos(
                        format!("字段 `{}` 不是动态数组", entry.path),
                        Position::new(1, 1),
                    )
                })?;
                let s0 = self.flat_slot(buf, entry.offset);
                let s1 = self.flat_slot(buf, entry.offset + 1);
                let s2 = self.flat_slot(buf, entry.offset + 2);
                let p = self.load_slot_ptr(&s0);
                let l = self.load_slot_i64(&s1);
                let c = self.load_slot_i64(&s2);
                self.ins(&format!("store ptr {p}, ptr {}", di.data));
                self.store_slot_i64(&di.len, &l);
                self.store_slot_i64(&di.cap, &c);
                continue;
            }
            let addr = dst
                .fields
                .get(&entry.path)
                .and_then(|f| f.addr.clone())
                .ok_or_else(|| {
                    TenetError::at_pos(
                        format!("缺少字段槽 `{}`", entry.path),
                        Position::new(1, 1),
                    )
                })?;
            if entry.slots > 1 {
                let src = self.flat_slot(buf, entry.offset);
                self.copy_flat_i64(&addr, &src, entry.slots);
                continue;
            }
            let slot = self.buffer_slot(buf, n, entry.offset);
            let raw = self.tmp();
            self.ins(&format!("{raw} = load i64, ptr {slot}"));
            let v = self.unpack_scalar(&entry.ty, &raw);
            self.ins(&format!(
                "store {} {v}, ptr {addr}",
                llvm_type(&entry.ty)
            ));
        }
        Ok(())
    }

    /// 函数入口的 struct 参数：从 ABI buffer 深拷贝到本地字段（动态字段重新 malloc）。
    fn unpack_buffer_deep(&mut self, dst: &VarInfo, ty: &str, buf: &str) -> TResult<()> {
        let n = self.struct_total_slots(ty);
        for entry in self.layout_of(ty) {
            let f = dst.fields.get(&entry.path).ok_or_else(|| {
                TenetError::at_pos(
                    format!("缺少字段槽 `{}`", entry.path),
                    Position::new(1, 1),
                )
            })?;
            if Self::is_dynamic_array(&entry.ty) {
                let di = f.dyn_array.as_ref().ok_or_else(|| {
                    TenetError::at_pos(
                        format!("字段 `{}` 不是动态数组", entry.path),
                        Position::new(1, 1),
                    )
                })?;
                let s0 = self.flat_slot(buf, entry.offset);
                let src_di = self.dyn_info_in_block(&s0, 0);
                self.deep_copy_dyn_to_local(&entry.ty, di, &src_di)?;
                continue;
            }
            let addr = f.addr.clone().ok_or_else(|| {
                TenetError::at_pos(
                    format!("缺少字段槽 `{}`", entry.path),
                    Position::new(1, 1),
                )
            })?;
            if entry.slots > 1 {
                let src = self.flat_slot(buf, entry.offset);
                if self.type_owns_heap(&entry.ty) {
                    self.deep_copy_value(&entry.ty, &addr, &src);
                } else {
                    self.copy_flat_i64(&addr, &src, entry.slots);
                }
                continue;
            }
            let slot = self.buffer_slot(buf, n, entry.offset);
            let raw = self.tmp();
            self.ins(&format!("{raw} = load i64, ptr {slot}"));
            let v = self.unpack_scalar(&entry.ty, &raw);
            self.ins(&format!(
                "store {} {v}, ptr {addr}",
                llvm_type(&entry.ty)
            ));
        }
        Ok(())
    }

    fn pack_expr_to_buffer(&mut self, ty: &str, expr: &Expr, buf: &str) -> TResult<()> {
        let layout = self.layout_of(ty);
        let n = self.struct_total_slots(ty);
        match &expr.kind {
            ExprKind::StructLit { name, fields } => {
                if name != ty {
                    return Err(TenetError::at_pos(
                        format!("需要 {ty}，字面量是 {name}"),
                        expr.pos.clone(),
                    ));
                }
                let flat = self.flatten_literal(ty, fields, "")?;
                for (path, e) in flat {
                    let entry = layout
                        .iter()
                        .find(|en| en.path == path)
                        .cloned()
                        .ok_or_else(|| {
                            TenetError::at_pos(format!("未知字段 `{path}`"), e.pos.clone())
                        })?;
                    if Self::is_dynamic_array(&entry.ty) {
                        self.pack_dyn_field_expr(&entry.ty, &e, buf, entry.offset)?;
                        continue;
                    }
                    if entry.slots > 1 {
                        self.pack_array_field_expr(&entry.ty, &e, buf, entry.offset)?;
                        continue;
                    }
                    let (vt, v) = self.gen_expr(&e)?;
                    if vt != llvm_type(&entry.ty) {
                        return Err(TenetError::at_pos(
                            format!(
                                "字段 `{path}` 类型不匹配：需要 {}，实际 {}",
                                entry.ty,
                                tenet_name(&vt)
                            ),
                            e.pos.clone(),
                        ));
                    }
                    let raw = self.pack_scalar(&entry.ty, &v);
                    let slot = self.buffer_slot(buf, n, entry.offset);
                    self.ins(&format!("store i64 {raw}, ptr {slot}"));
                }
            }
            ExprKind::Var(src) => {
                let info = self.lookup_var(src, expr.pos.clone())?;
                if info.ty != ty || info.array.is_some() || !self.is_struct(&info.ty) {
                    return Err(TenetError::at_pos(
                        format!("需要 {ty}，实际是 {}", info.ty),
                        expr.pos.clone(),
                    ));
                }
                for entry in layout {
                    let f = info.fields.get(&entry.path).ok_or_else(|| {
                        TenetError::at_pos(
                            format!("缺少字段槽 `{}`", entry.path),
                            expr.pos.clone(),
                        )
                    })?;
                    if Self::is_dynamic_array(&entry.ty) {
                        let di = f.dyn_array.as_ref().ok_or_else(|| {
                            TenetError::at_pos(
                                format!("字段 `{}` 不是动态数组", entry.path),
                                expr.pos.clone(),
                            )
                        })?;
                        let p = self.dyn_load(&di.data, "ptr");
                        let l = self.dyn_load(&di.len, "i64");
                        let c = self.dyn_load(&di.cap, "i64");
                        let s0 = self.flat_slot(buf, entry.offset);
                        let s1 = self.flat_slot(buf, entry.offset + 1);
                        let s2 = self.flat_slot(buf, entry.offset + 2);
                        self.ins(&format!("store ptr {p}, ptr {s0}"));
                        self.ins(&format!("store i64 {l}, ptr {s1}"));
                        self.ins(&format!("store i64 {c}, ptr {s2}"));
                        continue;
                    }
                    let addr = f.addr.clone().unwrap();
                    if entry.slots > 1 {
                        let dst = self.flat_slot(buf, entry.offset);
                        self.copy_flat_i64(&dst, &addr, entry.slots);
                        continue;
                    }
                    let v = self.tmp();
                    self.ins(&format!(
                        "{v} = load {}, ptr {addr}",
                        llvm_type(&entry.ty)
                    ));
                    let raw = self.pack_scalar(&entry.ty, &v);
                    let slot = self.buffer_slot(buf, n, entry.offset);
                    self.ins(&format!("store i64 {raw}, ptr {slot}"));
                }
            }
            ExprKind::Call { .. } => {
                let (rt, ptr) = self.gen_expr(expr)?;
                if rt != ty {
                    return Err(TenetError::at_pos(
                        format!("需要 {ty}，实际 {rt}"),
                        expr.pos.clone(),
                    ));
                }
                self.copy_flat_i64(buf, &ptr, n);
            }
            _ => {
                return Err(TenetError::at_pos(
                    format!("{ty} 值必须是字面量、同类型变量或返回 {ty} 的函数调用"),
                    expr.pos.clone(),
                ))
            }
        }
        Ok(())
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
                for (_pname, pty) in params {
                    if self.is_array(pty) {
                        let _elem = self.array_elem_or_err(pty, stmt.pos.clone())?;
                        self.validate_array_type(pty, stmt.pos.clone())?;
                    }
                }
                if let Some(rt) = ret {
                    if self.is_array(rt) {
                        let _elem = self.array_elem_or_err(rt, stmt.pos.clone())?;
                        self.validate_array_type(rt, stmt.pos.clone())?;
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
        self.push("declare ptr @malloc(i64)");
        self.push("declare void @free(ptr)");
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
            if self.terminated {
                break;
            }
        }
        self.current_fn.clear();
        if !self.terminated {
            // 顶层作用域收尾：释放局部动态数组 / struct 动态字段。
            self.drop_all_scopes();
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

        if ret.is_some() && !matches!(body.last().map(|s| &s.kind), Some(StmtKind::Return(_))) {
            return Err(TenetError::at_pos(
                format!("函数 `{name}` 声明了返回类型，但函数末尾没有 return"),
                stmt.pos.clone(),
            ));
        }

        let ret_struct = ret.as_deref().map(|t| self.is_struct(t)).unwrap_or(false);
        let ret_array_len = ret.as_deref().and_then(Self::array_decl_len);
        let ret_dynamic = ret.as_deref().map(Self::is_dynamic_array).unwrap_or(false);
        let ret_composite = ret_struct || ret_array_len.is_some() || ret_dynamic;
        let ret_ll = if ret_composite {
            "void"
        } else {
            ret.as_deref().map(llvm_type).unwrap_or("void")
        };
        let mut param_strs = Vec::new();
        if ret_composite {
            param_strs.push("ptr %sret".to_string());
        }
        for (i, (_, pty)) in params.iter().enumerate() {
            if self.is_struct(pty) || self.is_array(pty) {
                param_strs.push(format!("ptr %p{i}"));
            } else {
                param_strs.push(format!("{} %p{i}", llvm_type(pty)));
            }
        }
        self.push(&format!("define {ret_ll} @{name}({}) {{", param_strs.join(", ")));
        self.block("entry");

        self.current_fn = name.clone();
        self.current_ret = ret.clone();
        self.symbols.push(HashMap::new());
        for (i, (pname, pty)) in params.iter().enumerate() {
            if self.is_struct(pty) {
                let info = self.alloc_struct(pty, stmt.pos.clone())?;
                let arg = format!("%p{i}");
                self.unpack_buffer_deep(&info, pty, &arg)?;
                self.symbols.last_mut().unwrap().insert(pname.clone(), info);
            } else if Self::is_dynamic_array(pty) {
                let arg = format!("%p{i}");
                let info = self.dynamic_param_from_desc(pty, &arg, stmt.pos.clone())?;
                self.symbols.last_mut().unwrap().insert(pname.clone(), info);
            } else if self.is_array(pty) {
                let slots = self.array_elem_slots(pty)?;
                let len = Self::array_decl_len(pty).ok_or_else(|| {
                    TenetError::at_pos("array 参数必须写 array<T, N>".to_string(), stmt.pos.clone())
                })?;
                if self.is_flat_slot_array(pty) {
                    let total = len * slots;
                    let addr = self.tmp();
                    self.ins(&format!("{addr} = alloca [{total} x i64]"));
                    if self.type_owns_heap(pty) {
                        self.deep_copy_value(pty, &addr, &format!("%p{i}"));
                    } else {
                        self.copy_flat_i64(&addr, &format!("%p{i}"), total);
                    }
                    self.symbols.last_mut().unwrap().insert(
                        pname.clone(),
                        VarInfo {
                            ty: pty.clone(),
                            addr: Some(addr),
                            fields: HashMap::new(),
                            array: Some(len),
                            dyn_array: None,
                        },
                    );
                    continue;
                }
                let elem = Self::array_elem_scalar(pty, stmt.pos.clone())?;
                let elem_ll = llvm_type(&elem);
                let addr = self.tmp();
                self.ins(&format!("{addr} = alloca [{len} x {elem_ll}]"));
                let arg = format!("%p{i}");
                for k in 0..len {
                    let src = self.array_slot(&arg, len, elem_ll, k);
                    let dst = self.array_slot(&addr, len, elem_ll, k);
                    let v = self.tmp();
                    self.ins(&format!("{v} = load {elem_ll}, ptr {src}"));
                    self.ins(&format!("store {elem_ll} {v}, ptr {dst}"));
                }
                self.symbols.last_mut().unwrap().insert(
                    pname.clone(),
                    VarInfo {
                        ty: pty.clone(),
                        addr: Some(addr),
                        fields: HashMap::new(),
                        array: Some(len),
                        dyn_array: None,
                    },
                );
            } else {
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
                        dyn_array: None,
                    },
                );
            }
        }
        for s in body {
            self.emit_stmt(s)?;
        }
        if ret.is_none() && !self.terminated {
            // 函数体正常落空：先递归 drop 函数作用域（含 struct 参数），再返回。
            self.drop_all_scopes();
            self.term("ret void");
        }
        self.symbols.pop();
        self.current_fn.clear();
        self.current_ret = None;

        if ret_composite && !self.terminated {
            return Err(TenetError::at_pos(
                format!("函数 `{name}` 的复合类型返回路径没有 return"),
                stmt.pos.clone(),
            ));
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
                    self.validate_array_type(&t, stmt.pos.clone())?;
                    let info = if Self::array_decl_len(&t).is_none() {
                        self.init_dynamic_array(name, &t, value, stmt.pos.clone())?
                    } else {
                        self.init_array(name, &t, value, stmt.pos.clone())?
                    };
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
                        dyn_array: None,
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
                    if self.terminated {
                        break;
                    }
                }
                if !self.terminated {
                    self.drop_scope();
                }
                self.symbols.pop();
                self.br_if_open(&merge_l);
                self.block(&else_l);
                if let Some(branch) = else_branch {
                    self.symbols.push(HashMap::new());
                    for s in branch {
                        self.emit_stmt(s)?;
                        if self.terminated {
                            break;
                        }
                    }
                    if !self.terminated {
                        self.drop_scope();
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
                self.loop_depths.push(self.symbols.len());
                for s in body {
                    self.emit_stmt(s)?;
                    if self.terminated {
                        break;
                    }
                }
                if !self.terminated {
                    self.drop_scope();
                }
                self.break_stack.pop();
                self.loop_depths.pop();
                self.symbols.pop();
                self.br_if_open(&cond_l);
                self.block(&exit_l);
                Ok(())
            }
            StmtKind::Return(expr) => {
                if let Some(decl) = self.current_ret.clone() {
                    if self.is_struct(&decl) {
                        let Some(e) = expr else {
                            return Err(TenetError::at_pos(
                                format!("函数 `{}` 返回 {decl}，return 必须带值", self.current_fn),
                                stmt.pos.clone(),
                            ));
                        };
                        self.return_struct_to_sret(&decl, e)?;
                        self.drop_all_scopes();
                        self.term("ret void");
                        return Ok(());
                    }
                    if Self::is_dynamic_array(&decl) {
                        let Some(e) = expr else {
                            return Err(TenetError::at_pos(
                                format!("函数 `{}` 返回 {decl}，return 必须带值", self.current_fn),
                                stmt.pos.clone(),
                            ));
                        };
                        self.transfer_dynamic_expr_to_sret(&decl, e, "%sret")?;
                        self.drop_all_scopes();
                        self.term("ret void");
                        return Ok(());
                    }
                    if self.is_array(&decl) {
                        let Some(e) = expr else {
                            return Err(TenetError::at_pos(
                                format!("函数 `{}` 返回 {decl}，return 必须带值", self.current_fn),
                                stmt.pos.clone(),
                            ));
                        };
                        let len = Self::array_decl_len(&decl).ok_or_else(|| {
                            TenetError::at_pos("array 返回值必须写 array<T, N>".to_string(), stmt.pos.clone())
                        })?;
                        if self.is_flat_slot_array(&decl) {
                            if let ExprKind::Var(src) = &e.kind {
                                let info = self.lookup_var(src, e.pos.clone())?;
                                if info.ty != decl {
                                    return Err(TenetError::at_pos(
                                        format!(
                                            "返回类型不匹配：需要 {decl}，实际 {}",
                                            info.ty
                                        ),
                                        e.pos.clone(),
                                    ));
                                }
                                let addr = info.addr.clone().unwrap();
                                self.transfer_value_slots(&decl, "%sret", &addr);
                            } else {
                                self.pack_array_expr_to_buffer(&decl, len, e, "%sret")?;
                            }
                        } else {
                            self.pack_array_expr_to_buffer(&decl, len, e, "%sret")?;
                        }
                        self.drop_all_scopes();
                        self.term("ret void");
                        return Ok(());
                    }
                }
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
                    self.drop_all_scopes();
                    self.term(&format!("ret {t} {v}"));
                } else {
                    self.drop_all_scopes();
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
                if let Some(&depth) = self.loop_depths.last() {
                    while self.symbols.len() > depth {
                        self.drop_scope();
                        self.symbols.pop();
                    }
                    if self.symbols.len() == depth {
                        self.drop_scope();
                    }
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
                if let ExprKind::Index { base: outer, index: oi } = &base.kind {
                    if let ExprKind::Var(name) = &outer.kind {
                        let info = self.lookup_var(name, outer.pos.clone())?;
                        if info.dyn_array.is_some() {
                            let inner =
                                self.array_elem_or_err(&info.ty, expr.pos.clone())?;
                            if !self.is_array(&inner) {
                                return Err(TenetError::at_pos(
                                    format!("`{name}` 的元素不是数组，不能连续下标"),
                                    expr.pos.clone(),
                                ));
                            }
                            self.validate_array_type(&info.ty, expr.pos.clone())?;
                            let (elem, addr) = self.nested_dynamic_index_addr(
                                &info,
                                oi,
                                index,
                                expr.pos.clone(),
                            )?;
                            let r = self.tmp();
                            self.ins(&format!("{r} = load {}, ptr {addr}", llvm_type(&elem)));
                            return Ok((llvm_type(&elem).into(), r));
                        }
                        let (elem, addr) =
                            self.nested_index_addr(&info, oi, index, expr.pos.clone())?;
                        let r = self.tmp();
                        self.ins(&format!("{r} = load {}, ptr {addr}", llvm_type(&elem)));
                        return Ok((llvm_type(&elem).into(), r));
                    }
                }
                let ExprKind::Var(name) = &base.kind else {
                    // `s.a[i]` / `s.a[i][j]` 等：由左值解析器处理。
                    if let Some(place) = self.resolve_place(expr)? {
                        return self.load_place(&place, expr.pos.clone());
                    }
                    return Err(TenetError::at_pos(
                        "只支持对数组变量、struct 数组字段或嵌套数组元素取下标",
                        base.pos.clone(),
                    ));
                };
                let info = self.lookup_var(name, base.pos.clone())?;
                if info.dyn_array.is_some() {
                    let inner = self.array_elem_or_err(&info.ty, base.pos.clone())?;
                    if self.is_array(&inner) {
                        self.validate_array_type(&info.ty, expr.pos.clone())?;
                        return Err(TenetError::at_pos(
                            format!(
                                "暂不支持整体读取 `{name}[i]`；请使用 `{name}[i][j]` 读取标量"
                            ),
                            expr.pos.clone(),
                        ));
                    }
                    let (elem, slot, _) = self.dynamic_index_addr(&info, index)?;
                    let raw = self.tmp();
                    self.ins(&format!("{raw} = load i64, ptr {slot}"));
                    let v = self.dyn_unpack(&elem, &raw);
                    return Ok((llvm_type(&elem).into(), v));
                }
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
                let mut ipath: Vec<&str> = Vec::new();
                if let Some((arr_name, index)) = self.struct_index_fields(expr, &mut ipath) {
                    let fpath = ipath.join(".");
                    let info = self.lookup_var(arr_name, base.pos.clone())?;
                    let (elem, elem_addr) =
                        self.struct_array_elem_addr(&info, index, expr.pos.clone())?;
                    let off = self.field_offset(&elem, &fpath).ok_or_else(|| {
                        TenetError::at_pos(
                            format!("struct `{elem}` 没有字段 `{fpath}`"),
                            expr.pos.clone(),
                        )
                    })?;
                    let fty = self.field_type_of(&elem, &fpath)?;
                    if self.is_array(&fty) {
                        return Err(TenetError::at_pos(
                            format!("数组字段 `{fpath}` 不能直接取值；请继续下标"),
                            expr.pos.clone(),
                        ));
                    }
                    let addr = self.tmp();
                    self.ins(&format!(
                        "{addr} = getelementptr i8, ptr {elem_addr}, i64 {}",
                        off * 8
                    ));
                    let r = self.tmp();
                    self.ins(&format!("{r} = load {}, ptr {addr}", llvm_type(&fty)));
                    return Ok((llvm_type(&fty).into(), r));
                }
                let Some((name, mut path)) = Self::expr_var_path(base) else {
                    // `s.a[i].f` / `arr[i].f` 等：由左值解析器处理。
                    if let Some(place) = self.resolve_place(expr)? {
                        return self.load_place(&place, expr.pos.clone());
                    }
                    return Err(TenetError::at_pos(
                        "只支持 struct 变量、array<struct> 元素或 struct 数组字段元素取字段",
                        base.pos.clone(),
                    ));
                };
                if path.is_empty() {
                    path = field.clone();
                } else {
                    path = format!("{path}.{field}");
                }
                let info = self.lookup_var(&name, base.pos.clone())?;
                if !self.is_struct(&info.ty) {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 不是 struct，不能取字段 `{field}`"),
                        base.pos.clone(),
                    ));
                }
                let f = info.fields.get(&path).ok_or_else(|| {
                    TenetError::at_pos(
                        format!("struct `{}` 没有字段 `{path}`", info.ty),
                        expr.pos.clone(),
                    )
                })?;
                if self.is_array(&f.ty) {
                    return Err(TenetError::at_pos(
                        format!(
                            "数组字段 `{path}` 不能直接取值；请用下标 `{path}[i]` 或 print(struct)"
                        ),
                        expr.pos.clone(),
                    ));
                }
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
                    // 自赋值是 no-op（尤其 struct 深拷贝 / 整体赋值时避免先 drop 自己）。
                    if matches!(&value.kind, ExprKind::Var(src) if src == name) {
                        return Ok((info.ty.clone(), String::new()));
                    }
                    if info.dyn_array.is_some() {
                        self.assign_dynamic(name, &info, value, expr.pos.clone())?;
                        return Ok((info.ty.clone(), String::new()));
                    }
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
                    if let ExprKind::Index { base: outer, index: oi } = &base.kind {
                        if let ExprKind::Var(name) = &outer.kind {
                            let info = self.lookup_var(name, outer.pos.clone())?;
                            if info.dyn_array.is_some() {
                                let inner =
                                    self.array_elem_or_err(&info.ty, target.pos.clone())?;
                                if !self.is_array(&inner) {
                                    return Err(TenetError::at_pos(
                                        format!("`{name}` 的元素不是数组，不能连续下标"),
                                        target.pos.clone(),
                                    ));
                                }
                                self.validate_array_type(&info.ty, target.pos.clone())?;
                                let (elem, addr) = self.nested_dynamic_index_addr(
                                    &info,
                                    oi,
                                    index,
                                    target.pos.clone(),
                                )?;
                                let (vt, v) = self.gen_expr(value)?;
                                if vt != llvm_type(&elem) {
                                    return Err(TenetError::at_pos(
                                        format!(
                                            "数组元素赋值类型不匹配：需要 {elem}，实际 {}",
                                            tenet_name(&vt)
                                        ),
                                        value.pos.clone(),
                                    ));
                                }
                                self.ins(&format!("store {vt} {v}, ptr {addr}"));
                                return Ok((vt, v));
                            }
                            let (elem, addr) =
                                self.nested_index_addr(&info, oi, index, target.pos.clone())?;
                            let (vt, v) = self.gen_expr(value)?;
                            if vt != llvm_type(&elem) {
                                return Err(TenetError::at_pos(
                                    format!(
                                        "数组元素赋值类型不匹配：需要 {elem}，实际 {}",
                                        tenet_name(&vt)
                                    ),
                                    value.pos.clone(),
                                ));
                            }
                            self.ins(&format!("store {vt} {v}, ptr {addr}"));
                            return Ok((vt, v));
                        }
                    }
                    let ExprKind::Var(name) = &base.kind else {
                        // `s.a[i] = ...` / `s.a[i][j] = ...` 等。
                        if let Some(place) = self.resolve_place(target)? {
                            return self.store_place(&place, value, expr.pos.clone());
                        }
                        return Err(TenetError::at_pos(
                            "只支持对数组变量、struct 数组字段或嵌套数组元素写下标",
                            base.pos.clone(),
                        ));
                    };
                    let info = self.lookup_var(name, base.pos.clone())?;
                    let elem_ty = self.array_elem_or_err(&info.ty, base.pos.clone())?;
                    if self.is_struct(&elem_ty) {
                        let (_, elem_addr) =
                            self.struct_array_elem_addr(&info, index, target.pos.clone())?;
                        self.write_struct_expr_to_slots(&elem_ty, value, &elem_addr, true)?;
                        return Ok((elem_ty, String::new()));
                    }
                    if info.dyn_array.is_some() {
                        if self.is_array(&elem_ty) {
                            self.validate_array_type(&info.ty, target.pos.clone())?;
                            return Err(TenetError::at_pos(
                                format!(
                                    "暂不支持整体赋值 `{name}[i] = ...`；请使用 `{name}[i][j] = ...`"
                                ),
                                target.pos.clone(),
                            ));
                        }
                        let (elem, slot, _) = self.dynamic_index_addr(&info, index)?;
                        let (vt, v) = self.gen_expr(value)?;
                        if vt != llvm_type(&elem) {
                            return Err(TenetError::at_pos(
                                format!(
                                    "数组元素赋值类型不匹配：需要 {elem}，实际 {}",
                                    tenet_name(&vt)
                                ),
                                value.pos.clone(),
                            ));
                        }
                        let raw = self.dyn_pack(&elem, &v);
                        self.ins(&format!("store i64 {raw}, ptr {slot}"));
                        return Ok((vt, v));
                    }
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
                // `s.a = s.a` / `arr[0].x = arr[0].x` 是 no-op，避免先 drop 再拷贝自己。
                if Self::place_path(target).is_some()
                    && Self::place_path(target) == Self::place_path(value)
                {
                    if let Ok(Some(t)) = self.infer_type(target) {
                        return Ok((t, String::new()));
                    }
                }
                let mut ipath: Vec<&str> = Vec::new();
                if let Some((arr_name, index)) = self.struct_index_fields(target, &mut ipath) {
                    let fpath = ipath.join(".");
                    let info = self.lookup_var(arr_name, base.pos.clone())?;
                    let (elem, elem_addr) =
                        self.struct_array_elem_addr(&info, index, target.pos.clone())?;
                    let off = self.field_offset(&elem, &fpath).ok_or_else(|| {
                        TenetError::at_pos(
                            format!("struct `{elem}` 没有字段 `{fpath}`"),
                            target.pos.clone(),
                        )
                    })?;
                    let fty = self.field_type_of(&elem, &fpath)?;
                    if self.is_array(&fty) {
                        let faddr = self.gep_i8(&elem_addr, off * 8);
                        if Self::is_dynamic_array(&fty) {
                            let di = self.dyn_info_in_block(&faddr, 0);
                            self.assign_dyn_place(&fty, &di, value, target.pos.clone())?;
                        } else {
                            self.store_array_place(&fty, &faddr, value, target.pos.clone())?;
                        }
                        return Ok((fty, String::new()));
                    }
                    let (vt, v) = self.gen_expr(value)?;
                    if vt != llvm_type(&fty) {
                        return Err(TenetError::at_pos(
                            format!(
                                "字段 `{fpath}` 类型不匹配：需要 {fty}，实际 {}",
                                tenet_name(&vt)
                            ),
                            value.pos.clone(),
                        ));
                    }
                    let addr = self.tmp();
                    self.ins(&format!(
                        "{addr} = getelementptr i8, ptr {elem_addr}, i64 {}",
                        off * 8
                    ));
                    self.ins(&format!("store {vt} {v}, ptr {addr}"));
                    return Ok((vt, v));
                }
                let Some((name, mut path)) = Self::expr_var_path(base) else {
                    // `s.a[i].f = ...` 等。
                    if let Some(place) = self.resolve_place(target)? {
                        return self.store_place(&place, value, expr.pos.clone());
                    }
                    return Err(TenetError::at_pos(
                        "只支持 struct 变量、array<struct> 元素或 struct 数组字段元素写字段",
                        base.pos.clone(),
                    ));
                };
                if path.is_empty() {
                    path = field.clone();
                } else {
                    path = format!("{path}.{field}");
                }
                let info = self.lookup_var(&name, base.pos.clone())?;
                if !self.is_struct(&info.ty) {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 不是 struct，不能写字段 `{field}`"),
                        base.pos.clone(),
                    ));
                }
                let f = info.fields.get(&path).ok_or_else(|| {
                    TenetError::at_pos(
                        format!("struct `{}` 没有字段 `{path}`", info.ty),
                        target.pos.clone(),
                    )
                })?;
                if self.is_array(&f.ty) {
                    let fty = f.ty.clone();
                    if let Some(di) = &f.dyn_array {
                        let di = di.clone();
                        self.assign_dyn_place(&fty, &di, value, target.pos.clone())?;
                    } else {
                        let faddr = f.addr.clone().unwrap();
                        self.store_array_place(&fty, &faddr, value, target.pos.clone())?;
                    }
                    return Ok((fty, String::new()));
                }
                let (vt, v) = self.gen_expr(value)?;
                if vt != llvm_type(&f.ty) {
                    return Err(TenetError::at_pos(
                        format!(
                            "字段 `{path}` 类型不匹配：需要 {}，实际 {}",
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

    fn array_slot(&mut self, buf: &str, len: usize, elem_ll: &str, i: usize) -> String {
        let addr = self.tmp();
        self.ins(&format!(
            "{addr} = getelementptr [{len} x {elem_ll}], ptr {buf}, i64 0, i64 {i}"
        ));
        addr
    }

    fn copy_array_ptr(
        &mut self,
        dst: &str,
        src: &str,
        len: usize,
        elem_ll: &str,
    ) {
        for i in 0..len {
            let s = self.array_slot(src, len, elem_ll, i);
            let d = self.array_slot(dst, len, elem_ll, i);
            let v = self.tmp();
            self.ins(&format!("{v} = load {elem_ll}, ptr {s}"));
            self.ins(&format!("store {elem_ll} {v}, ptr {d}"));
        }
    }

    fn pack_array_expr_to_buffer(
        &mut self,
        ty: &str,
        len: usize,
        expr: &Expr,
        buf: &str,
    ) -> TResult<()> {
        if self.is_flat_slot_array(ty) {
            return self.pack_fixed_array_expr(ty, expr, buf);
        }
        let elem = Self::array_elem_scalar(ty, expr.pos.clone())?;
        let elem_ll = llvm_type(&elem);
        match &expr.kind {
            ExprKind::Array(elems) => {
                if elems.len() != len {
                    return Err(TenetError::at_pos(
                        format!("数组长度不匹配：需要 {len}，实际 {}", elems.len()),
                        expr.pos.clone(),
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
                    let slot = self.array_slot(buf, len, elem_ll, i);
                    self.ins(&format!("store {vt} {v}, ptr {slot}"));
                }
            }
            ExprKind::Var(name) => {
                let info = self.lookup_var(name, expr.pos.clone())?;
                if info.array != Some(len) || Self::array_elem(&info.ty) != Some(elem.as_str()) {
                    return Err(TenetError::at_pos(
                        format!("数组参数类型不匹配：需要 {ty}，实际是 {}", info.ty),
                        expr.pos.clone(),
                    ));
                }
                let src = info.addr.clone().unwrap();
                self.copy_array_ptr(buf, &src, len, &elem_ll);
            }
            ExprKind::Call { .. } => {
                let (rt, src) = self.gen_expr(expr)?;
                if Self::array_elem(&rt) != Some(elem.as_str())
                    || Self::array_decl_len(&rt) != Some(len)
                {
                    return Err(TenetError::at_pos(
                        format!("数组调用返回类型不匹配：需要 {ty}，实际 {rt}"),
                        expr.pos.clone(),
                    ));
                }
                self.copy_array_ptr(buf, &src, len, &elem_ll);
            }
            _ => {
                return Err(TenetError::at_pos(
                    "数组实参必须是同类型数组变量、字面量或返回数组的调用",
                    expr.pos.clone(),
                ))
            }
        }
        Ok(())
    }

    fn is_dynamic_array(ty: &str) -> bool {
        Self::array_elem(ty).is_some() && Self::array_decl_len(ty).is_none()
    }

    /// v1 动态嵌套数组：`array<array<T>>`（外层动态、内层动态、T 为标量）。
    ///
    /// 只认这一种形状：内层必须是动态标量数组；不支持固定内层、
    /// `array<struct>` 内层或更深嵌套。
    fn is_dynamic_nested_array(ty: &str) -> bool {
        Self::nested_scalar_elem(ty).is_some()
    }

    fn nested_scalar_elem(ty: &str) -> Option<&str> {
        if Self::array_decl_len(ty).is_some() {
            return None;
        }
        let inner = Self::array_elem(ty)?;
        if Self::array_decl_len(inner).is_some() {
            return None;
        }
        let scalar = Self::array_elem(inner)?;
        matches!(scalar, T_INT | T_FLOAT | T_BOOL).then_some(scalar)
    }

    /// 校验数组类型形状（只在需要时调用；未支持的嵌套会给出明确错误）。
    fn validate_array_type(&self, ty: &str, pos: Position) -> TResult<()> {
        let Some(elem) = Self::array_elem(ty) else {
            return Ok(());
        };
        if !self.is_array(elem) {
            return Ok(());
        }
        if Self::array_decl_len(ty).is_some() {
            // 固定外层：内层也必须是固定长度（沿用既有 v1 规则）。
            if Self::array_decl_len(elem).is_none() {
                return Err(TenetError::at_pos(
                    "固定嵌套数组的内层必须是固定长度 array<T, N>".to_string(),
                    pos,
                ));
            }
            return Ok(());
        }
        // 动态外层：v1 只支持内层同样是动态标量数组。
        if Self::array_decl_len(elem).is_some() {
            return Err(TenetError::at_pos(
                "动态嵌套数组的内层必须是动态数组 array<T>，不支持固定长度内层".to_string(),
                pos,
            ));
        }
        let scalar = Self::array_elem(elem).unwrap();
        if matches!(scalar, T_INT | T_FLOAT | T_BOOL) {
            return Ok(());
        }
        if self.is_struct(scalar) {
            return Err(TenetError::at_pos(
                "嵌套数组内层元素只支持 int/float/bool，不支持 array<struct>".to_string(),
                pos,
            ));
        }
        if Self::array_elem(scalar).is_some() {
            return Err(TenetError::at_pos(
                "只支持一层嵌套数组 array<array<T>>".to_string(),
                pos,
            ));
        }
        Err(TenetError::at_pos(
            format!("嵌套数组内层元素只支持 int/float/bool，实际 `{scalar}`"),
            pos,
        ))
    }

    fn dyn_new_slots(&mut self) -> (String, String, String) {
        let data = self.tmp();
        let len = self.tmp();
        let cap = self.tmp();
        self.ins(&format!("{data} = alloca ptr"));
        self.ins(&format!("{len} = alloca i64"));
        self.ins(&format!("{cap} = alloca i64"));
        self.ins(&format!("store ptr null, ptr {data}"));
        self.ins(&format!("store i64 0, ptr {len}"));
        self.ins(&format!("store i64 0, ptr {cap}"));
        (data, len, cap)
    }

    fn dyn_load(&mut self, slot: &str, ty: &str) -> String {
        let r = self.tmp();
        self.ins(&format!("{r} = load {ty}, ptr {slot}"));
        r
    }

    fn dyn_pack(&mut self, ty: &str, v: &str) -> String {
        self.pack_scalar(ty, v)
    }

    fn dyn_unpack(&mut self, ty: &str, raw: &str) -> String {
        self.unpack_scalar(ty, raw)
    }

    fn dyn_slot(&mut self, data: &str, i: &str) -> String {
        let r = self.tmp();
        self.ins(&format!("{r} = getelementptr i64, ptr {data}, i64 {i}"));
        r
    }

    /// 扩容后的容量：至少 4（空数组 push 时 cap=0，不能继续乘 2 得 0）。
    fn grow_cap(&mut self, cap: &str) -> String {
        let doubled = self.tmp();
        self.ins(&format!("{doubled} = mul i64 {cap}, 2"));
        let small = self.tmp();
        self.ins(&format!("{small} = icmp ult i64 {doubled}, 4"));
        let nc = self.tmp();
        self.ins(&format!(
            "{nc} = select i1 {small}, i64 4, i64 {doubled}"
        ));
        nc
    }

    fn dyn_alloc(
        &mut self,
        data_slot: &str,
        len_slot: &str,
        cap_slot: &str,
        len: usize,
        cap: usize,
    ) {
        let bytes = (cap.max(1) * 8) as i64;
        let p = self.tmp();
        self.ins(&format!("{p} = call ptr @malloc(i64 {bytes})"));
        self.ins(&format!("store ptr {p}, ptr {data_slot}"));
        self.ins(&format!("store i64 {len}, ptr {len_slot}"));
        self.ins(&format!("store i64 {cap}, ptr {cap_slot}"));
    }

    fn dyn_copy_elems(
        &mut self,
        dst_data: &str,
        src_data: &str,
        len_op: &str,
        elem: &str,
    ) {
        let _ = elem;
        let label = self.new_label("dyn.copy");
        let body = self.new_label("dyn.copy.body");
        let end = self.new_label("dyn.copy.end");
        let i_slot = self.tmp();
        self.ins(&format!("{i_slot} = alloca i64"));
        self.ins(&format!("store i64 0, ptr {i_slot}"));
        self.term(&format!("br label %{label}"));
        self.block(&label);
        let i = self.dyn_load(&i_slot, "i64");
        let cond = self.tmp();
        self.ins(&format!("{cond} = icmp slt i64 {i}, {len_op}"));
        self.term(&format!("br i1 {cond}, label %{body}, label %{end}"));
        self.block(&body);
        let s = self.dyn_slot(src_data, &i);
        let d = self.dyn_slot(dst_data, &i);
        let v = self.tmp();
        self.ins(&format!("{v} = load i64, ptr {s}"));
        self.ins(&format!("store i64 {v}, ptr {d}"));
        let ni = self.tmp();
        self.ins(&format!("{ni} = add i64 {i}, 1"));
        self.ins(&format!("store i64 {ni}, ptr {i_slot}"));
        self.term(&format!("br label %{label}"));
        self.block(&end);
    }

    fn dyn_drop(&mut self, info: &DynArrayInfo, ty: &str) {
        self.dyn_drop_slots(&info.data, &info.len, &info.cap, ty);
    }

    /// 释放动态数组：嵌套数组先逐内层 free(data)，struct 元素先递归 drop 其动态字段，
    /// 再 free 外层，最后清空槽位。
    fn dyn_drop_slots(&mut self, data_slot: &str, len_slot: &str, cap_slot: &str, ty: &str) {
        let p = self.dyn_load(data_slot, "ptr");
        let is_null = self.tmp();
        self.ins(&format!("{is_null} = icmp eq ptr {p}, null"));
        let do_free = self.new_label("dyn.free");
        let end = self.new_label("dyn.drop.end");
        self.term(&format!("br i1 {is_null}, label %{end}, label %{do_free}"));
        self.block(&do_free);
        if Self::is_dynamic_nested_array(ty) {
            let len = self.dyn_load(len_slot, "i64");
            let i_slot = self.tmp();
            self.ins(&format!("{i_slot} = alloca i64"));
            self.ins(&format!("store i64 0, ptr {i_slot}"));
            let cond = self.new_label("dyn.drop.cond");
            let body = self.new_label("dyn.drop.inner");
            let next = self.new_label("dyn.drop.next");
            let after = self.new_label("dyn.drop.rows");
            self.term(&format!("br label %{cond}"));
            self.block(&cond);
            let i = self.dyn_load(&i_slot, "i64");
            let c = self.tmp();
            self.ins(&format!("{c} = icmp slt i64 {i}, {len}"));
            self.term(&format!("br i1 {c}, label %{body}, label %{after}"));
            self.block(&body);
            let row_off = self.tmp();
            self.ins(&format!("{row_off} = mul i64 {i}, 3"));
            let row = self.dyn_slot(&p, &row_off);
            let ds = self.desc_slot(&row, 0);
            let ip = self.tmp();
            self.ins(&format!("{ip} = load ptr, ptr {ds}"));
            let inner_null = self.tmp();
            self.ins(&format!("{inner_null} = icmp eq ptr {ip}, null"));
            let do_inner_free = self.new_label("dyn.drop.inner.free");
            self.term(&format!(
                "br i1 {inner_null}, label %{next}, label %{do_inner_free}"
            ));
            self.block(&do_inner_free);
            self.ins(&format!("call void @free(ptr {ip})"));
            self.ins(&format!("store ptr null, ptr {ds}"));
            self.term(&format!("br label %{next}"));
            self.block(&next);
            let ni = self.tmp();
            self.ins(&format!("{ni} = add i64 {i}, 1"));
            self.ins(&format!("store i64 {ni}, ptr {i_slot}"));
            self.term(&format!("br label %{cond}"));
            self.block(&after);
        } else if let Some(elem) = Self::array_elem(ty).map(|s| s.to_string()) {
            // 动态 array<struct>：元素里的动态字段需要先递归 drop。
            if self.is_struct(&elem) && self.type_owns_heap(&elem) {
                let len = self.dyn_load(len_slot, "i64");
                let eslots = self.array_elem_slots(ty).unwrap_or(1);
                let i_slot = self.tmp();
                self.ins(&format!("{i_slot} = alloca i64"));
                self.ins(&format!("store i64 0, ptr {i_slot}"));
                let cond = self.new_label("dyn.drop.elem.cond");
                let body = self.new_label("dyn.drop.elem");
                let after = self.new_label("dyn.drop.elems");
                self.term(&format!("br label %{cond}"));
                self.block(&cond);
                let i = self.dyn_load(&i_slot, "i64");
                let c = self.tmp();
                self.ins(&format!("{c} = icmp slt i64 {i}, {len}"));
                self.term(&format!("br i1 {c}, label %{body}, label %{after}"));
                self.block(&body);
                let row = self.tmp();
                self.ins(&format!("{row} = mul i64 {i}, {eslots}"));
                let base = self.slot_addr_dyn(&p, &row);
                self.drop_value_slots(&elem, &base);
                let ni = self.tmp();
                self.ins(&format!("{ni} = add i64 {i}, 1"));
                self.ins(&format!("store i64 {ni}, ptr {i_slot}"));
                self.term(&format!("br label %{cond}"));
                self.block(&after);
            }
        }
        self.ins(&format!("call void @free(ptr {p})"));
        self.ins(&format!("store ptr null, ptr {data_slot}"));
        self.ins(&format!("store i64 0, ptr {len_slot}"));
        self.ins(&format!("store i64 0, ptr {cap_slot}"));
        self.term(&format!("br label %{end}"));
        self.block(&end);
    }

    fn bounds_check_op(&mut self, index: &str, len: &str) {
        let ok = self.new_label("dbounds.ok");
        let fail = self.new_label("dbounds.fail");
        let cmp = self.tmp();
        self.ins(&format!("{cmp} = icmp uge i64 {index}, {len}"));
        self.term(&format!("br i1 {cmp}, label %{fail}, label %{ok}"));
        self.block(&fail);
        self.ins(&format!("call void @tenet_bounds_fail(i64 {index}, i64 {len})"));
        self.term("unreachable");
        self.block(&ok);
    }

    fn dynamic_index_addr(
        &mut self,
        info: &VarInfo,
        index: &Expr,
    ) -> TResult<(String, String, String)> {
        let di = info.dyn_array.as_ref().unwrap();
        let elem = self.array_elem_or_err(&info.ty, index.pos.clone())?;
        let data = self.dyn_load(&di.data, "ptr");
        let len = self.dyn_load(&di.len, "i64");
        let (it, iv) = self.gen_expr(index)?;
        if it != llvm_type(T_INT) {
            return Err(TenetError::at_pos(
                format!("数组下标必须是 int，实际为 {}", tenet_name(&it)),
                index.pos.clone(),
            ));
        }
        self.bounds_check_op(&iv, &len);
        let slots = self.dyn_stride(&info.ty)?;
        let row = self.tmp();
        self.ins(&format!("{row} = mul i64 {iv}, {slots}"));
        let slot = self.dyn_slot(&data, &row);
        Ok((elem, slot, len))
    }

    /// 计算 `a[i]` 的内层 descriptor 地址（外层下标越界检查）。
    fn dynamic_nested_row_desc(&mut self, info: &VarInfo, outer_idx: &Expr) -> TResult<String> {
        self.validate_array_type(&info.ty, outer_idx.pos.clone())?;
        let Some(di) = info.dyn_array.as_ref() else {
            return Err(TenetError::at_pos(
                "不是动态数组".to_string(),
                outer_idx.pos.clone(),
            ));
        };
        let data = self.dyn_load(&di.data, "ptr");
        let len = self.dyn_load(&di.len, "i64");
        let (ot, ov) = self.gen_expr(outer_idx)?;
        if ot != llvm_type(T_INT) {
            return Err(TenetError::at_pos(
                format!("数组下标必须是 int，实际为 {}", tenet_name(&ot)),
                outer_idx.pos.clone(),
            ));
        }
        self.bounds_check_op(&ov, &len);
        let row = self.tmp();
        self.ins(&format!("{row} = mul i64 {ov}, 3"));
        Ok(self.dyn_slot(&data, &row))
    }

    /// `a[i][j]` 的标量地址：内外两层各自做边界检查。
    fn nested_dynamic_index_addr(
        &mut self,
        info: &VarInfo,
        outer_idx: &Expr,
        inner_idx: &Expr,
        pos: Position,
    ) -> TResult<(String, String)> {
        let scalar = Self::nested_scalar_elem(&info.ty)
            .ok_or_else(|| {
                TenetError::at_pos(
                    "只支持 array<array<int/float/bool>> 的二级下标".to_string(),
                    pos.clone(),
                )
            })?
            .to_string();
        let row = self.dynamic_nested_row_desc(info, outer_idx)?;
        let s0 = self.desc_slot(&row, 0);
        let s1 = self.desc_slot(&row, 1);
        let ip = self.dyn_load(&s0, "ptr");
        let il = self.dyn_load(&s1, "i64");
        let (it, iv) = self.gen_expr(inner_idx)?;
        if it != llvm_type(T_INT) {
            return Err(TenetError::at_pos(
                format!("数组下标必须是 int，实际为 {}", tenet_name(&it)),
                inner_idx.pos.clone(),
            ));
        }
        self.bounds_check_op(&iv, &il);
        let slot = self.dyn_slot(&ip, &iv);
        Ok((scalar, slot))
    }

    fn desc_alloc(&mut self) -> String {
        let d = self.tmp();
        self.ins(&format!("{d} = alloca [3 x i64]"));
        d
    }

    fn desc_slot(&mut self, desc: &str, i: usize) -> String {
        let a = self.tmp();
        self.ins(&format!(
            "{a} = getelementptr [3 x i64], ptr {desc}, i64 0, i64 {i}"
        ));
        a
    }

    fn desc_store_info(&mut self, desc: &str, info: &VarInfo) {
        let di = info.dyn_array.as_ref().unwrap();
        let d = self.dyn_load(&di.data, "ptr");
        let l = self.dyn_load(&di.len, "i64");
        let c = self.dyn_load(&di.cap, "i64");
        let s0 = self.desc_slot(desc, 0);
        let s1 = self.desc_slot(desc, 1);
        let s2 = self.desc_slot(desc, 2);
        self.ins(&format!("store ptr {d}, ptr {s0}"));
        self.ins(&format!("store i64 {l}, ptr {s1}"));
        self.ins(&format!("store i64 {c}, ptr {s2}"));
    }

    fn desc_clear_info(&mut self, info: &VarInfo) {
        let di = info.dyn_array.as_ref().unwrap();
        self.ins(&format!("store ptr null, ptr {}", di.data));
        self.ins(&format!("store i64 0, ptr {}", di.len));
        self.ins(&format!("store i64 0, ptr {}", di.cap));
    }

    fn dynamic_from_desc(&mut self, ty: &str, desc: &str, pos: Position) -> TResult<VarInfo> {
        let elem = self.array_elem_or_err(ty, pos.clone())?;
        let d = self.tmp();
        let l = self.tmp();
        let c = self.tmp();
        let s0 = self.desc_slot(desc, 0);
        let s1 = self.desc_slot(desc, 1);
        let s2 = self.desc_slot(desc, 2);
        self.ins(&format!("{d} = load ptr, ptr {s0}"));
        self.ins(&format!("{l} = load i64, ptr {s1}"));
        self.ins(&format!("{c} = load i64, ptr {s2}"));
        let (data, len_s, cap_s) = self.dyn_new_slots();
        self.ins(&format!("store ptr {d}, ptr {data}"));
        self.ins(&format!("store i64 {l}, ptr {len_s}"));
        self.ins(&format!("store i64 {c}, ptr {cap_s}"));
        // 调用结果描述符被接管，清空避免后续误用；调用方栈槽本身不需要 drop。
        self.ins(&format!("store ptr null, ptr {s0}"));
        self.ins(&format!("store i64 0, ptr {s1}"));
        self.ins(&format!("store i64 0, ptr {s2}"));
        let _ = elem;
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: None,
            fields: HashMap::new(),
            array: None,
            dyn_array: Some(DynArrayInfo { data, len: len_s, cap: cap_s }),
        })
    }

    fn dynamic_param_from_desc(&mut self, ty: &str, desc: &str, pos: Position) -> TResult<VarInfo> {
        let elem = self.array_elem_or_err(ty, pos.clone())?;
        if self.is_array(&elem) {
            // 动态嵌套数组：入口逐内层深拷贝，参数与调用方完全独立。
            self.validate_array_type(ty, pos.clone())?;
            let s0 = self.desc_slot(desc, 0);
            let s1 = self.desc_slot(desc, 1);
            let s2 = self.desc_slot(desc, 2);
            return self.nested_copy_from_slots(ty, &s0, &s1, &s2, pos);
        }
        let s0 = self.desc_slot(desc, 0);
        let s1 = self.desc_slot(desc, 1);
        let s2 = self.desc_slot(desc, 2);
        let sp = self.tmp();
        let sl = self.tmp();
        let sc = self.tmp();
        self.ins(&format!("{sp} = load ptr, ptr {s0}"));
        self.ins(&format!("{sl} = load i64, ptr {s1}"));
        self.ins(&format!("{sc} = load i64, ptr {s2}"));
        let slots = self.array_elem_slots(ty)?;
        let bytes = self.tmp();
        self.ins(&format!("{bytes} = mul i64 {sc}, {}", slots * 8));
        let np = self.tmp();
        self.ins(&format!("{np} = call ptr @malloc(i64 {bytes})"));
        let (data, len_s, cap_s) = self.dyn_new_slots();
        self.ins(&format!("store ptr {np}, ptr {data}"));
        self.ins(&format!("store i64 {sl}, ptr {len_s}"));
        self.ins(&format!("store i64 {sc}, ptr {cap_s}"));
        if self.is_struct(&elem) && self.type_owns_heap(&elem) {
            // array<struct> 且 struct 含动态字段：逐元素深拷贝。
            let i_slot = self.tmp();
            self.ins(&format!("{i_slot} = alloca i64"));
            self.ins(&format!("store i64 0, ptr {i_slot}"));
            let cond = self.new_label("arr.param.copy.cond");
            let body = self.new_label("arr.param.copy.body");
            let end = self.new_label("arr.param.copy.end");
            self.term(&format!("br label %{cond}"));
            self.block(&cond);
            let i = self.dyn_load(&i_slot, "i64");
            let c = self.tmp();
            self.ins(&format!("{c} = icmp slt i64 {i}, {sl}"));
            self.term(&format!("br i1 {c}, label %{body}, label %{end}"));
            self.block(&body);
            let row = self.tmp();
            self.ins(&format!("{row} = mul i64 {i}, {slots}"));
            let d = self.slot_addr_dyn(&np, &row);
            let s = self.slot_addr_dyn(&sp, &row);
            self.deep_copy_value(&elem, &d, &s);
            let ni = self.tmp();
            self.ins(&format!("{ni} = add i64 {i}, 1"));
            self.ins(&format!("store i64 {ni}, ptr {i_slot}"));
            self.term(&format!("br label %{cond}"));
            self.block(&end);
        } else {
            let total = self.tmp();
            self.ins(&format!("{total} = mul i64 {sl}, {slots}"));
            self.dyn_copy_elems(&np, &sp, &total, &elem);
        }
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: None,
            fields: HashMap::new(),
            array: None,
            dyn_array: Some(DynArrayInfo { data, len: len_s, cap: cap_s }),
        })
    }

    /// 深拷贝一个动态嵌套数组：源为 [data,len,cap] 的三个槽位，
    /// 每个外层元素（内层 descriptor）都重新 malloc + 拷贝元素。
    fn nested_copy_from_slots(
        &mut self,
        ty: &str,
        src_data: &str,
        src_len: &str,
        src_cap: &str,
        pos: Position,
    ) -> TResult<VarInfo> {
        self.validate_array_type(ty, pos.clone())?;
        let sp = self.dyn_load(src_data, "ptr");
        let sl = self.dyn_load(src_len, "i64");
        let sc = self.dyn_load(src_cap, "i64");
        let (data, len_s, cap_s) = self.dyn_new_slots();
        let obytes = self.tmp();
        self.ins(&format!("{obytes} = mul i64 {sc}, 24"));
        let np = self.tmp();
        self.ins(&format!("{np} = call ptr @malloc(i64 {obytes})"));
        self.ins(&format!("store ptr {np}, ptr {data}"));
        self.ins(&format!("store i64 {sl}, ptr {len_s}"));
        self.ins(&format!("store i64 {sc}, ptr {cap_s}"));

        let i_slot = self.tmp();
        let j_slot = self.tmp();
        self.ins(&format!("{i_slot} = alloca i64"));
        self.ins(&format!("{j_slot} = alloca i64"));
        self.ins(&format!("store i64 0, ptr {i_slot}"));
        let cond = self.new_label("nested.copy.cond");
        let body = self.new_label("nested.copy.body");
        let jcond = self.new_label("nested.copy.jcond");
        let jbody = self.new_label("nested.copy.jbody");
        let jend = self.new_label("nested.copy.jend");
        let end = self.new_label("nested.copy.end");
        self.term(&format!("br label %{cond}"));
        self.block(&cond);
        let i = self.dyn_load(&i_slot, "i64");
        let c = self.tmp();
        self.ins(&format!("{c} = icmp slt i64 {i}, {sl}"));
        self.term(&format!("br i1 {c}, label %{body}, label %{end}"));
        self.block(&body);
        let row_off = self.tmp();
        self.ins(&format!("{row_off} = mul i64 {i}, 3"));
        let row = self.dyn_slot(&sp, &row_off);
        let is0 = self.desc_slot(&row, 0);
        let is1 = self.desc_slot(&row, 1);
        let is2 = self.desc_slot(&row, 2);
        let ip = self.tmp();
        let il = self.tmp();
        let ic = self.tmp();
        self.ins(&format!("{ip} = load ptr, ptr {is0}"));
        self.ins(&format!("{il} = load i64, ptr {is1}"));
        self.ins(&format!("{ic} = load i64, ptr {is2}"));
        let ibytes = self.tmp();
        self.ins(&format!("{ibytes} = mul i64 {ic}, 8"));
        let nip = self.tmp();
        self.ins(&format!("{nip} = call ptr @malloc(i64 {ibytes})"));
        self.ins(&format!("store i64 0, ptr {j_slot}"));
        self.term(&format!("br label %{jcond}"));
        self.block(&jcond);
        let j = self.dyn_load(&j_slot, "i64");
        let jc = self.tmp();
        self.ins(&format!("{jc} = icmp slt i64 {j}, {il}"));
        self.term(&format!("br i1 {jc}, label %{jbody}, label %{jend}"));
        self.block(&jbody);
        let ss = self.dyn_slot(&ip, &j);
        let dd = self.dyn_slot(&nip, &j);
        let v = self.tmp();
        self.ins(&format!("{v} = load i64, ptr {ss}"));
        self.ins(&format!("store i64 {v}, ptr {dd}"));
        let nj = self.tmp();
        self.ins(&format!("{nj} = add i64 {j}, 1"));
        self.ins(&format!("store i64 {nj}, ptr {j_slot}"));
        self.term(&format!("br label %{jcond}"));
        self.block(&jend);
        let drow_off = self.tmp();
        self.ins(&format!("{drow_off} = mul i64 {i}, 3"));
        let drow = self.dyn_slot(&np, &drow_off);
        let ds0 = self.desc_slot(&drow, 0);
        let ds1 = self.desc_slot(&drow, 1);
        let ds2 = self.desc_slot(&drow, 2);
        self.ins(&format!("store ptr {nip}, ptr {ds0}"));
        self.ins(&format!("store i64 {il}, ptr {ds1}"));
        self.ins(&format!("store i64 {ic}, ptr {ds2}"));
        let ni = self.tmp();
        self.ins(&format!("{ni} = add i64 {i}, 1"));
        self.ins(&format!("store i64 {ni}, ptr {i_slot}"));
        self.term(&format!("br label %{cond}"));
        self.block(&end);
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: None,
            fields: HashMap::new(),
            array: None,
            dyn_array: Some(DynArrayInfo { data, len: len_s, cap: cap_s }),
        })
    }

    fn transfer_dynamic_to_sret(&mut self, ty: &str, expr: &Expr, sret: &str) -> TResult<()> {
        let ExprKind::Var(name) = &expr.kind else {
            return Err(TenetError::at_pos(
                "S3c-2 v1 的 return 只支持返回动态数组变量".to_string(),
                expr.pos.clone(),
            ));
        };
        let info = self.lookup_var(name, expr.pos.clone())?;
        if info.ty != ty {
            return Err(TenetError::at_pos(
                format!("返回类型不匹配：需要 {ty}，实际 {}", info.ty),
                expr.pos.clone(),
            ));
        }
        self.desc_store_info(sret, &info);
        self.desc_clear_info(&info);
        Ok(())
    }

    fn desc_clear(&mut self, desc: &str) {
        for i in 0..3 {
            let a = self.desc_slot(desc, i);
            if i == 0 {
                self.ins(&format!("store ptr null, ptr {a}"));
            } else {
                self.ins(&format!("store i64 0, ptr {a}"));
            }
        }
    }

    fn desc_copy(&mut self, dst: &str, src: &str) {
        for i in 0..3 {
            let s = self.desc_slot(src, i);
            let d = self.desc_slot(dst, i);
            let v = self.tmp();
            self.ins(&format!("{v} = load i64, ptr {s}"));
            self.ins(&format!("store i64 {v}, ptr {d}"));
        }
    }

    fn drop_desc_owned(&mut self, desc: &str, ty: &str) {
        let s0 = self.desc_slot(desc, 0);
        let s1 = self.desc_slot(desc, 1);
        let s2 = self.desc_slot(desc, 2);
        self.dyn_drop_slots(&s0, &s1, &s2, ty);
    }

    fn transfer_dynamic_expr_to_sret(&mut self, ty: &str, expr: &Expr, sret: &str) -> TResult<()> {
        match &expr.kind {
            ExprKind::Var(_) => {
                let info = match &expr.kind {
                    ExprKind::Var(n) => self.lookup_var(n, expr.pos.clone())?,
                    _ => unreachable!(),
                };
                if info.ty != ty {
                    return Err(TenetError::at_pos(
                        format!("返回类型不匹配：需要 {ty}，实际 {}", info.ty),
                        expr.pos.clone(),
                    ));
                }
                self.desc_store_info(sret, &info);
                self.desc_clear_info(&info);
                Ok(())
            }
            ExprKind::Array(_) => {
                let tmp = self.init_dynamic_array("__ret_tmp", ty, expr, expr.pos.clone())?;
                self.desc_store_info(sret, &tmp);
                self.desc_clear_info(&tmp);
                Ok(())
            }
            ExprKind::Call { .. } => {
                let (rt, desc) = self.gen_expr(expr)?;
                if rt != ty {
                    return Err(TenetError::at_pos(
                        format!("返回类型不匹配：需要 {ty}，调用返回 {rt}"),
                        expr.pos.clone(),
                    ));
                }
                self.desc_copy(sret, &desc);
                self.desc_clear(&desc);
                Ok(())
            }
            _ => Err(TenetError::at_pos(
                "动态数组 return 只支持变量、字面量或返回动态数组的调用".to_string(),
                expr.pos.clone(),
            )),
        }
    }

    fn push_struct_dynamic(&mut self, info: &VarInfo, value: &Expr, pos: Position) -> TResult<()> {
        let di = info.dyn_array.as_ref().unwrap();
        let elem = self.array_elem_or_err(&info.ty, pos.clone())?;
        let slots = self.array_elem_slots(&info.ty)?;
        let len = self.dyn_load(&di.len, "i64");
        let cap = self.dyn_load(&di.cap, "i64");
        let need = self.tmp();
        self.ins(&format!("{need} = icmp eq i64 {len}, {cap}"));
        let grow = self.new_label("dyn.grow");
        let after = self.new_label("dyn.grow.after");
        self.term(&format!("br i1 {need}, label %{grow}, label %{after}"));
        self.block(&grow);
        let newcap = self.grow_cap(&cap);
        let bytes = self.tmp();
        self.ins(&format!("{bytes} = mul i64 {newcap}, {}", slots * 8));
        let np = self.tmp();
        self.ins(&format!("{np} = call ptr @malloc(i64 {bytes})"));
        let op = self.dyn_load(&di.data, "ptr");
        let total = self.tmp();
        self.ins(&format!("{total} = mul i64 {len}, {slots}"));
        self.dyn_copy_elems(&np, &op, &total, &elem);
        self.ins(&format!("call void @free(ptr {op})"));
        self.ins(&format!("store ptr {np}, ptr {}", di.data));
        self.ins(&format!("store i64 {newcap}, ptr {}", di.cap));
        self.term(&format!("br label %{after}"));
        self.block(&after);
        let data = self.dyn_load(&di.data, "ptr");
        let row = self.tmp();
        self.ins(&format!("{row} = mul i64 {len}, {slots}"));
        let dst = self.dyn_slot(&data, &row);
        self.write_struct_expr_to_slots(&elem, value, &dst, false)?;
        let nl = self.tmp();
        self.ins(&format!("{nl} = add i64 {len}, 1"));
        self.ins(&format!("store i64 {nl}, ptr {}", di.len));
        Ok(())
    }

    /// push(a, inner)：深拷贝内层 descriptor 后追加到外层；外层 cap*2。
    fn push_nested_dynamic(&mut self, info: &VarInfo, value: &Expr, pos: Position) -> TResult<()> {
        self.validate_array_type(&info.ty, pos.clone())?;
        let inner_ty = self.array_elem_or_err(&info.ty, pos.clone())?;
        if !matches!(
            value.kind,
            ExprKind::Array(_) | ExprKind::Var(_) | ExprKind::Call { .. }
        ) {
            return Err(TenetError::at_pos(
                "push 的嵌套数组值必须是内层数组字面量、同类型变量或返回数组的调用".to_string(),
                value.pos.clone(),
            ));
        }
        let tmp = self.init_dynamic_array("__push_tmp", &inner_ty, value, value.pos.clone())?;
        let tdi = tmp.dyn_array.as_ref().unwrap();
        let td = self.dyn_load(&tdi.data, "ptr");
        let tl = self.dyn_load(&tdi.len, "i64");
        let tc = self.dyn_load(&tdi.cap, "i64");
        let di = info.dyn_array.as_ref().unwrap();
        let len = self.dyn_load(&di.len, "i64");
        let cap = self.dyn_load(&di.cap, "i64");
        let need = self.tmp();
        self.ins(&format!("{need} = icmp eq i64 {len}, {cap}"));
        let grow = self.new_label("dyn.grow");
        let after = self.new_label("dyn.grow.after");
        self.term(&format!("br i1 {need}, label %{grow}, label %{after}"));
        self.block(&grow);
        let newcap = self.grow_cap(&cap);
        let bytes = self.tmp();
        self.ins(&format!("{bytes} = mul i64 {newcap}, 24"));
        let np = self.tmp();
        self.ins(&format!("{np} = call ptr @malloc(i64 {bytes})"));
        let op = self.dyn_load(&di.data, "ptr");
        let total = self.tmp();
        self.ins(&format!("{total} = mul i64 {len}, 3"));
        self.dyn_copy_elems(&np, &op, &total, "i64");
        self.ins(&format!("call void @free(ptr {op})"));
        self.ins(&format!("store ptr {np}, ptr {}", di.data));
        self.ins(&format!("store i64 {newcap}, ptr {}", di.cap));
        self.term(&format!("br label %{after}"));
        self.block(&after);
        let data = self.dyn_load(&di.data, "ptr");
        let row_off = self.tmp();
        self.ins(&format!("{row_off} = mul i64 {len}, 3"));
        let dst = self.dyn_slot(&data, &row_off);
        let d0 = self.desc_slot(&dst, 0);
        let d1 = self.desc_slot(&dst, 1);
        let d2 = self.desc_slot(&dst, 2);
        self.ins(&format!("store ptr {td}, ptr {d0}"));
        self.ins(&format!("store i64 {tl}, ptr {d1}"));
        self.ins(&format!("store i64 {tc}, ptr {d2}"));
        let nl = self.tmp();
        self.ins(&format!("{nl} = add i64 {len}, 1"));
        self.ins(&format!("store i64 {nl}, ptr {}", di.len));
        Ok(())
    }

    fn assign_dynamic(&mut self, name: &str, dst: &VarInfo, value: &Expr, pos: Position) -> TResult<()> {
        if let ExprKind::Var(src) = &value.kind {
            if src == name {
                return Ok(());
            }
        }
        let tmp = self.init_dynamic_array("__assign_tmp", &dst.ty, value, pos)?;
        let tdi = tmp.dyn_array.as_ref().unwrap();
        let ddi = dst.dyn_array.as_ref().unwrap();
        let td = self.dyn_load(&tdi.data, "ptr");
        let tl = self.dyn_load(&tdi.len, "i64");
        let tc = self.dyn_load(&tdi.cap, "i64");
        self.dyn_drop(ddi, &dst.ty);
        self.ins(&format!("store ptr {td}, ptr {}", ddi.data));
        self.ins(&format!("store i64 {tl}, ptr {}", ddi.len));
        self.ins(&format!("store i64 {tc}, ptr {}", ddi.cap));
        Ok(())
    }

    fn drop_scope(&mut self) {
        let vars: Vec<VarInfo> = self
            .symbols
            .last()
            .map(|m| m.values().cloned().collect())
            .unwrap_or_default();
        for v in vars {
            self.drop_var(&v);
        }
    }

    fn drop_all_scopes(&mut self) {
        for i in (0..self.symbols.len()).rev() {
            let vars: Vec<VarInfo> = self.symbols[i].values().cloned().collect();
            for v in vars {
                self.drop_var(&v);
            }
        }
    }

    fn init_dynamic_struct_array(
        &mut self,
        name: &str,
        ty: &str,
        value: &Expr,
        pos: Position,
    ) -> TResult<VarInfo> {
        let elem = self.array_elem_or_err(ty, pos.clone())?;
        let slots = self.array_elem_slots(ty)?;
        let (data, len_s, cap_s) = self.dyn_new_slots();
        match &value.kind {
            ExprKind::Array(elems) => {
                let len = elems.len();
                let cap = len.max(4);
                let bytes = (cap * slots * 8) as i64;
                let p = self.tmp();
                self.ins(&format!("{p} = call ptr @malloc(i64 {bytes})"));
                self.ins(&format!("store ptr {p}, ptr {data}"));
                self.ins(&format!("store i64 {len}, ptr {len_s}"));
                self.ins(&format!("store i64 {cap}, ptr {cap_s}"));
                for (i, e) in elems.iter().enumerate() {
                    let dst = self.tmp();
                    self.ins(&format!(
                        "{dst} = getelementptr i64, ptr {p}, i64 {}",
                        i * slots
                    ));
                    self.write_struct_expr_to_slots(&elem, e, &dst, false)?;
                }
            }
            ExprKind::Var(src) => {
                let sinfo = self.lookup_var(src, value.pos.clone())?;
                let Some(di) = &sinfo.dyn_array else {
                    return Err(TenetError::at_pos(
                        format!("`{src}` 不是动态数组"),
                        value.pos.clone(),
                    ));
                };
                if sinfo.ty != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，但 `{src}` 是 {}", sinfo.ty),
                        value.pos.clone(),
                    ));
                }
                if self.type_owns_heap(&elem) {
                    return self.dyn_deep_copy_from(ty, di);
                }
                let slen = self.dyn_load(&di.len, "i64");
                let scap = self.dyn_load(&di.cap, "i64");
                let sp = self.dyn_load(&di.data, "ptr");
                let bytes = self.tmp();
                self.ins(&format!("{bytes} = mul i64 {scap}, {}", slots * 8));
                let p = self.tmp();
                self.ins(&format!("{p} = call ptr @malloc(i64 {bytes})"));
                self.ins(&format!("store ptr {p}, ptr {data}"));
                self.ins(&format!("store i64 {slen}, ptr {len_s}"));
                self.ins(&format!("store i64 {scap}, ptr {cap_s}"));
                let total = self.tmp();
                self.ins(&format!("{total} = mul i64 {slen}, {slots}"));
                self.dyn_copy_elems(&p, &sp, &total, &elem);
            }
            ExprKind::Call { .. } => {
                let (rt, desc) = self.gen_expr(value)?;
                if rt != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，调用返回 {rt}"),
                        value.pos.clone(),
                    ));
                }
                return self.dynamic_from_desc(ty, &desc, value.pos.clone());
            }
            _ => {
                return Err(TenetError::at_pos(
                    format!("`{name}` 的 array<struct> 初始化必须是字面量、同类型变量或返回数组的调用"),
                    value.pos.clone(),
                ))
            }
        }
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: None,
            fields: HashMap::new(),
            array: None,
            dyn_array: Some(DynArrayInfo { data, len: len_s, cap: cap_s }),
        })
    }

    /// 初始化 `array<array<T>>`（外层动态、内层动态）。
    ///
    /// 外层堆布局 = `cap * 3` 个 i64，每个元素是内层 descriptor `[data,len,cap]`。
    fn init_dynamic_nested_array(
        &mut self,
        name: &str,
        ty: &str,
        value: &Expr,
        pos: Position,
    ) -> TResult<VarInfo> {
        self.validate_array_type(ty, pos.clone())?;
        let inner_ty = self.array_elem_or_err(ty, pos.clone())?;
        let (data, len_s, cap_s) = self.dyn_new_slots();
        match &value.kind {
            ExprKind::Array(rows) => {
                let len = rows.len();
                let cap = len.max(4);
                let bytes = (cap * 3 * 8) as i64;
                let p = self.tmp();
                self.ins(&format!("{p} = call ptr @malloc(i64 {bytes})"));
                self.ins(&format!("store ptr {p}, ptr {data}"));
                self.ins(&format!("store i64 {len}, ptr {len_s}"));
                self.ins(&format!("store i64 {cap}, ptr {cap_s}"));
                for (i, row_expr) in rows.iter().enumerate() {
                    if !matches!(
                        row_expr.kind,
                        ExprKind::Array(_) | ExprKind::Var(_) | ExprKind::Call { .. }
                    ) {
                        return Err(TenetError::at_pos(
                            format!(
                                "嵌套数组第 {i} 个元素必须是内层数组字面量、同类型变量或返回数组的调用"
                            ),
                            row_expr.pos.clone(),
                        ));
                    }
                    let row = self.init_dynamic_array(
                        "__nested_row",
                        &inner_ty,
                        row_expr,
                        row_expr.pos.clone(),
                    )?;
                    let rdi = row.dyn_array.as_ref().unwrap();
                    let rd = self.dyn_load(&rdi.data, "ptr");
                    let rl = self.dyn_load(&rdi.len, "i64");
                    let rc = self.dyn_load(&rdi.cap, "i64");
                    let dst = self.dyn_slot(&p, &(i * 3).to_string());
                    let d0 = self.desc_slot(&dst, 0);
                    let d1 = self.desc_slot(&dst, 1);
                    let d2 = self.desc_slot(&dst, 2);
                    self.ins(&format!("store ptr {rd}, ptr {d0}"));
                    self.ins(&format!("store i64 {rl}, ptr {d1}"));
                    self.ins(&format!("store i64 {rc}, ptr {d2}"));
                }
            }
            ExprKind::Var(src) => {
                let sinfo = self.lookup_var(src, value.pos.clone())?;
                if sinfo.ty != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，但 `{src}` 是 {}", sinfo.ty),
                        value.pos.clone(),
                    ));
                }
                let Some(di) = &sinfo.dyn_array else {
                    return Err(TenetError::at_pos(
                        format!("`{src}` 不是动态数组"),
                        value.pos.clone(),
                    ));
                };
                return self.nested_copy_from_slots(
                    ty,
                    &di.data,
                    &di.len,
                    &di.cap,
                    value.pos.clone(),
                );
            }
            ExprKind::Call { .. } => {
                let (rt, desc) = self.gen_expr(value)?;
                if rt != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，调用返回 {rt}"),
                        value.pos.clone(),
                    ));
                }
                return self.dynamic_from_desc(ty, &desc, value.pos.clone());
            }
            _ => {
                return Err(TenetError::at_pos(
                    format!(
                        "`{name}` 的动态嵌套数组初始化必须是字面量、同类型动态数组或返回动态数组的调用"
                    ),
                    value.pos.clone(),
                ))
            }
        }
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: None,
            fields: HashMap::new(),
            array: None,
            dyn_array: Some(DynArrayInfo { data, len: len_s, cap: cap_s }),
        })
    }

    fn init_dynamic_array(
        &mut self,
        name: &str,
        ty: &str,
        value: &Expr,
        pos: Position,
    ) -> TResult<VarInfo> {
        if matches!(value.kind, ExprKind::Field { .. }) {
            // `s.a = t.a` / 字段整体初始化：从另一个动态数组字段深拷贝。
            let Some((sty, di)) = self.resolve_dyn_target(value)? else {
                return Err(TenetError::at_pos(
                    format!("`{name}` 的初始化需要动态数组表达式"),
                    value.pos.clone(),
                ));
            };
            if sty != ty {
                return Err(TenetError::at_pos(
                    format!("`{name}` 需要 {ty}，实际是 {sty}"),
                    value.pos.clone(),
                ));
            }
            return self.dyn_deep_copy_from(ty, &di);
        }
        let elem0 = self.array_elem_or_err(ty, pos.clone())?;
        if self.is_struct(&elem0) {
            return self.init_dynamic_struct_array(name, ty, value, pos);
        }
        if self.is_array(&elem0) {
            return self.init_dynamic_nested_array(name, ty, value, pos);
        }
        let elem = Self::array_elem_scalar(ty, pos.clone())?;
        let elem_ll = llvm_type(&elem);
        let (data, len_s, cap_s) = self.dyn_new_slots();
        match &value.kind {
            ExprKind::Array(elems) => {
                let len = elems.len();
                let cap = len.max(4);
                self.dyn_alloc(&data, &len_s, &cap_s, len, cap);
                let p = self.dyn_load(&data, "ptr");
                for (i, e) in elems.iter().enumerate() {
                    let (vt, v) = self.gen_expr(e)?;
                    if vt != elem_ll {
                        return Err(TenetError::at_pos(
                            format!("数组元素 {i} 类型不匹配：需要 {elem}，实际 {}", tenet_name(&vt)),
                            e.pos.clone(),
                        ));
                    }
                    let raw = self.dyn_pack(&elem, &v);
                    let slot = self.dyn_slot(&p, &i.to_string());
                    self.ins(&format!("store i64 {raw}, ptr {slot}"));
                }
            }
            ExprKind::Var(src) => {
                let sinfo = self.lookup_var(src, value.pos.clone())?;
                let Some(di) = &sinfo.dyn_array else {
                    return Err(TenetError::at_pos(
                        format!("`{src}` 不是动态数组"),
                        value.pos.clone(),
                    ));
                };
                if Self::array_elem(&sinfo.ty) != Some(elem.as_str()) {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，但 `{src}` 是 {}", sinfo.ty),
                        value.pos.clone(),
                    ));
                }
                let slen = self.dyn_load(&di.len, "i64");
                let scap = self.dyn_load(&di.cap, "i64");
                let sp = self.dyn_load(&di.data, "ptr");
                let bytes = self.tmp();
                self.ins(&format!("{bytes} = mul i64 {scap}, 8"));
                let p = self.tmp();
                self.ins(&format!("{p} = call ptr @malloc(i64 {bytes})"));
                self.ins(&format!("store ptr {p}, ptr {data}"));
                self.ins(&format!("store i64 {slen}, ptr {len_s}"));
                self.ins(&format!("store i64 {scap}, ptr {cap_s}"));
                self.dyn_copy_elems(&p, &sp, &slen, &elem);
            }
            ExprKind::Call { .. } => {
                let (rt, desc) = self.gen_expr(value)?;
                if rt != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，调用返回 {rt}"),
                        value.pos.clone(),
                    ));
                }
                return self.dynamic_from_desc(ty, &desc, value.pos.clone());
            }
            _ => {
                return Err(TenetError::at_pos(
                    format!("`{name}` 的动态数组初始化必须是字面量、同类型动态数组或返回动态数组的调用"),
                    value.pos.clone(),
                ))
            }
        }
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: None,
            fields: HashMap::new(),
            array: None,
            dyn_array: Some(DynArrayInfo { data, len: len_s, cap: cap_s }),
        })
    }

    fn array_elem_or_err(&self, ty: &str, pos: Position) -> TResult<String> {
        Self::array_elem(ty)
            .map(|s| s.to_string())
            .ok_or_else(|| TenetError::at_pos(format!("`{ty}` 不是数组类型"), pos))
    }

    fn dyn_stride(&self, ty: &str) -> TResult<usize> {
        self.array_elem_slots(ty)
    }

    fn array_elem_slots(&self, ty: &str) -> TResult<usize> {
        let elem = self.array_elem_or_err(ty, Position::new(1, 1))?;
        if self.is_struct(&elem) {
            Ok(self.struct_total_slots(&elem))
        } else if self.is_array(&elem) {
            match Self::array_decl_len(&elem) {
                // 固定内层：整块扁平槽位。
                Some(n) => Ok(n * self.array_elem_slots(&elem)?),
                // 动态内层：外层元素是内层 descriptor（data/len/cap 三个 i64 槽）。
                None => Ok(3),
            }
        } else {
            Ok(1)
        }
    }

    /// 字段在所属 struct 中的起始槽偏移（返回槽数，不是字节）。
    fn field_offset(&self, ty: &str, path: &str) -> Option<usize> {
        self.field_slot_offset(ty, path)
    }

    fn struct_index_fields<'a>(
        &self,
        expr: &'a Expr,
        path: &mut Vec<&'a str>,
    ) -> Option<(&'a str, &'a Expr)> {
        match &expr.kind {
            ExprKind::Field { base, field } => {
                let r = self.struct_index_fields(base, path)?;
                path.push(field);
                Some(r)
            }
            ExprKind::Index { base, index } => match &base.kind {
                ExprKind::Var(name) => Some((name, index)),
                _ => None,
            },
            _ => None,
        }
    }

    fn struct_array_elem_addr(
        &mut self,
        info: &VarInfo,
        index: &Expr,
        pos: Position,
    ) -> TResult<(String, String)> {
        let elem = self.array_elem_or_err(&info.ty, pos.clone())?;
        let slots = self.array_elem_slots(&info.ty)?;
        let (it, iv) = self.gen_expr(index)?;
        if it != llvm_type(T_INT) {
            return Err(TenetError::at_pos("数组下标必须是 int".to_string(), index.pos.clone()));
        }
        if let Some(di) = &info.dyn_array {
            let data = self.dyn_load(&di.data, "ptr");
            let len = self.dyn_load(&di.len, "i64");
            self.bounds_check_op(&iv, &len);
            let row = self.tmp();
            self.ins(&format!("{row} = mul i64 {iv}, {slots}"));
            let addr = self.tmp();
            self.ins(&format!("{addr} = getelementptr i64, ptr {data}, i64 {row}"));
            return Ok((elem, addr));
        }
        let len = info.array.ok_or_else(|| {
            TenetError::at_pos("array<struct> 参数/返回值尚未支持".to_string(), pos.clone())
        })?;
        let base = info.addr.clone().unwrap();
        self.bounds_check(&iv, len);
        let row = self.tmp();
        self.ins(&format!("{row} = mul i64 {iv}, {slots}"));
        let addr = self.tmp();
        self.ins(&format!(
            "{addr} = getelementptr [{} x i64], ptr {base}, i64 0, i64 {row}",
            len * slots
        ));
        Ok((elem, addr))
    }

    fn init_struct_array(
        &mut self,
        name: &str,
        ty: &str,
        value: &Expr,
        pos: Position,
    ) -> TResult<VarInfo> {
        let elem = self.array_elem_or_err(ty, pos.clone())?;
        let slots = self.array_elem_slots(ty)?;
        let decl_len = Self::array_decl_len(ty);
        let (len, src_literal, src_addr) = match &value.kind {
            ExprKind::Array(elems) => {
                if elems.is_empty() {
                    return Err(TenetError::at_pos("固定数组不支持空字面量", value.pos.clone()));
                }
                if let Some(n) = decl_len {
                    if n != elems.len() {
                        return Err(TenetError::at_pos(
                            format!("数组长度不匹配：类型写 {n}，字面量 {}", elems.len()),
                            value.pos.clone(),
                        ));
                    }
                }
                (elems.len(), Some(elems), None)
            }
            ExprKind::Var(src) => {
                let sinfo = self.lookup_var(src, value.pos.clone())?;
                let slen = sinfo.array.ok_or_else(|| {
                    TenetError::at_pos(format!("`{src}` 不是固定数组"), value.pos.clone())
                })?;
                if sinfo.ty != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，但 `{src}` 是 {}", sinfo.ty),
                        value.pos.clone(),
                    ));
                }
                (slen, None, Some(sinfo.addr.clone().unwrap()))
            }
            ExprKind::Call { .. } => {
                let (rt, src) = self.gen_expr(value)?;
                if rt != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，调用返回 {rt}"),
                        value.pos.clone(),
                    ));
                }
                let total = decl_len.unwrap_or(0) * slots;
                let addr = self.tmp();
                self.ins(&format!("{addr} = alloca [{total} x i64]"));
                self.copy_flat_i64(&addr, &src, total);
                return Ok(VarInfo {
                    ty: ty.to_string(),
                    addr: Some(addr),
                    fields: HashMap::new(),
                    array: Some(decl_len.unwrap_or(0)),
                    dyn_array: None,
                });
            }
            _ => {
                return Err(TenetError::at_pos(
                    format!("`{name}` 的 array<struct> 初始化必须是字面量、同类型变量或返回数组的调用"),
                    value.pos.clone(),
                ))
            }
        };
        let addr = self.tmp();
        self.ins(&format!(
            "{addr} = alloca [{} x i64]",
            len * slots
        ));
        if let Some(elems) = src_literal {
            for (i, e) in elems.iter().enumerate() {
                let dst = self.tmp();
                self.ins(&format!(
                    "{dst} = getelementptr [{} x i64], ptr {addr}, i64 0, i64 {}",
                    len * slots,
                    i * slots
                ));
                self.write_struct_expr_to_slots(&elem, e, &dst, false)?;
            }
        } else if let Some(src) = src_addr {
            if self.type_owns_heap(ty) {
                self.deep_copy_value(ty, &addr, &src);
            } else {
                for k in 0..(len * slots) {
                    let saddr = self.tmp();
                    self.ins(&format!(
                        "{saddr} = getelementptr [{} x i64], ptr {src}, i64 0, i64 {k}",
                        len * slots
                    ));
                    let daddr = self.tmp();
                    self.ins(&format!(
                        "{daddr} = getelementptr [{} x i64], ptr {addr}, i64 0, i64 {k}",
                        len * slots
                    ));
                    let v = self.tmp();
                    self.ins(&format!("{v} = load i64, ptr {saddr}"));
                    self.ins(&format!("store i64 {v}, ptr {daddr}"));
                }
            }
        }
        let _ = slots;
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: Some(addr),
            fields: HashMap::new(),
            array: Some(len),
            dyn_array: None,
        })
    }

    fn nested_index_addr(
        &mut self,
        info: &VarInfo,
        outer_idx: &Expr,
        inner_idx: &Expr,
        pos: Position,
    ) -> TResult<(String, String)> {
        let outer_len = info.array.ok_or_else(|| {
            TenetError::at_pos("嵌套数组参数/返回值尚未支持".to_string(), pos.clone())
        })?;
        let inner_ty = self.array_elem_or_err(&info.ty, pos.clone())?;
        let inner_len = Self::array_decl_len(&inner_ty).ok_or_else(|| {
            TenetError::at_pos("嵌套数组内层必须是固定长度".to_string(), pos.clone())
        })?;
        let inner_elem = Self::array_elem(&inner_ty).unwrap().to_string();
        if inner_elem == T_BOOL {
            return Err(TenetError::at_pos("嵌套数组内层暂不支持 bool".to_string(), pos.clone()));
        }
        let outer_slots = self.array_elem_slots(&info.ty)?;
        let inner_slots = self.array_elem_slots(&inner_ty)?;
        let base = info.addr.clone().unwrap();
        let (ot, ov) = self.gen_expr(outer_idx)?;
        if ot != llvm_type(T_INT) {
            return Err(TenetError::at_pos("数组下标必须是 int".to_string(), outer_idx.pos.clone()));
        }
        self.bounds_check(&ov, outer_len);
        let (it, iv) = self.gen_expr(inner_idx)?;
        if it != llvm_type(T_INT) {
            return Err(TenetError::at_pos("数组下标必须是 int".to_string(), inner_idx.pos.clone()));
        }
        self.bounds_check(&iv, inner_len);
        let row = self.tmp();
        self.ins(&format!("{row} = mul i64 {ov}, {outer_slots}"));
        let irow = self.tmp();
        self.ins(&format!("{irow} = mul i64 {iv}, {inner_slots}"));
        let flat = self.tmp();
        self.ins(&format!("{flat} = add i64 {row}, {irow}"));
        let addr = self.tmp();
        self.ins(&format!(
            "{addr} = getelementptr [{} x i64], ptr {base}, i64 0, i64 {flat}",
            outer_len * outer_slots
        ));
        Ok((inner_elem, addr))
    }

    fn is_flat_slot_array(&self, ty: &str) -> bool {
        if let Some(elem) = Self::array_elem(ty) {
            self.is_struct(elem)
                || (self.is_array(elem) && Self::array_decl_len(elem).is_some())
        } else {
            false
        }
    }

    fn fixed_array_total_slots(&self, ty: &str) -> TResult<usize> {
        let len = Self::array_decl_len(ty).ok_or_else(|| {
            TenetError::at_pos("需要固定长度数组".to_string(), Position::new(1, 1))
        })?;
        Ok(len * self.array_elem_slots(ty)?)
    }

    fn copy_flat_i64(&mut self, dst: &str, src: &str, total: usize) {
        for i in 0..total {
            let sa = self.tmp();
            self.ins(&format!("{sa} = getelementptr i64, ptr {src}, i64 {i}"));
            let da = self.tmp();
            self.ins(&format!("{da} = getelementptr i64, ptr {dst}, i64 {i}"));
            let v = self.tmp();
            self.ins(&format!("{v} = load i64, ptr {sa}"));
            self.ins(&format!("store i64 {v}, ptr {da}"));
        }
    }

    // ---- 动态字段的通用深拷贝 / 转移 / 递归 drop ----

    /// 扁平槽块中第 `slot` 个 i64 槽的地址（基址按字节寻址）。
    fn slot_addr(&mut self, base: &str, slot: usize) -> String {
        let a = self.tmp();
        self.ins(&format!(
            "{a} = getelementptr i8, ptr {base}, i64 {}",
            slot * 8
        ));
        a
    }

    /// 运行时下标：扁平槽块中第 `slot_var` 个槽的地址。
    fn slot_addr_dyn(&mut self, base: &str, slot_var: &str) -> String {
        let byte = self.tmp();
        self.ins(&format!("{byte} = mul i64 {slot_var}, 8"));
        let a = self.tmp();
        self.ins(&format!("{a} = getelementptr i8, ptr {base}, i64 {byte}"));
        a
    }

    fn load_slot_ptr(&mut self, addr: &str) -> String {
        let v = self.tmp();
        self.ins(&format!("{v} = load ptr, ptr {addr}"));
        v
    }

    fn load_slot_i64(&mut self, addr: &str) -> String {
        let v = self.tmp();
        self.ins(&format!("{v} = load i64, ptr {addr}"));
        v
    }

    fn store_slot_i64(&mut self, addr: &str, v: &str) {
        self.ins(&format!("store i64 {v}, ptr {addr}"));
    }

    fn copy_slot_i64(&mut self, dst: &str, src: &str) {
        let v = self.load_slot_i64(src);
        self.store_slot_i64(dst, &v);
    }

    /// 清空一个动态数组 descriptor 槽（所有权转移后避免二次释放）。
    fn clear_desc_addr(&mut self, data: &str, len: &str, cap: &str) {
        self.ins(&format!("store ptr null, ptr {data}"));
        self.store_slot_i64(len, "0");
        self.store_slot_i64(cap, "0");
    }

    /// 构造扁平槽块中某个字段位置上的 descriptor 三元组地址。
    fn dyn_info_in_block(&mut self, base: &str, slot_off: usize) -> DynArrayInfo {
        DynArrayInfo {
            data: self.slot_addr(base, slot_off),
            len: self.slot_addr(base, slot_off + 1),
            cap: self.slot_addr(base, slot_off + 2),
        }
    }

    /// 深拷贝一个值（struct / 固定数组 / 动态数组 / 标量）：
    /// `dst` 与 `src` 都是扁平 i64 槽块中的起始地址。源保持有效。
    fn deep_copy_value(&mut self, ty: &str, dst: &str, src: &str) {
        if !self.type_owns_heap(ty) {
            let n = self.value_slots(ty);
            self.copy_flat_i64(dst, src, n);
            return;
        }
        if Self::is_dynamic_array(ty) {
            self.deep_copy_dyn_slots(ty, dst, src)
                .expect("动态数组类型已经校验");
            return;
        }
        if let Some(elem) = Self::array_elem(ty) {
            let elem = elem.to_string();
            let len = Self::array_decl_len(ty).expect("固定数组");
            let eslots = self.array_elem_slots(ty).expect("数组元素槽数");
            for i in 0..len {
                let d = self.slot_addr(dst, i * eslots);
                let s = self.slot_addr(src, i * eslots);
                self.deep_copy_value(&elem, &d, &s);
            }
            return;
        }
        // struct：逐直接字段递归。
        let defs = self.structs.get(ty).cloned().unwrap_or_default();
        for (fname, fty) in defs {
            let off = self
                .direct_field_slot_offset(ty, &fname)
                .expect("字段布局");
            let d = self.slot_addr(dst, off);
            let s = self.slot_addr(src, off);
            if Self::is_dynamic_array(&fty) {
                self.deep_copy_dyn_slots(&fty, &d, &s)
                    .expect("动态数组字段类型已经校验");
            } else if self.type_owns_heap(&fty) {
                self.deep_copy_value(&fty, &d, &s);
            } else {
                let n = self.value_slots(&fty);
                self.copy_flat_i64(&d, &s, n);
            }
        }
    }

    /// 深拷贝动态数组负载：给定源 data/len/cap 值，返回新 data 指针。
    /// 元素为 struct 或嵌套动态数组时递归深拷贝；标量元素按打包槽复制。
    fn dyn_copy_payload(
        &mut self,
        ty: &str,
        sp: &str,
        len: &str,
        cap: &str,
    ) -> TResult<String> {
        let elem = self.array_elem_or_err(ty, Position::new(1, 1))?;
        let eslots = self.array_elem_slots(ty)?;
        let bytes = self.tmp();
        self.ins(&format!("{bytes} = mul i64 {cap}, {}", eslots * 8));
        let np = self.tmp();
        self.ins(&format!("{np} = call ptr @malloc(i64 {bytes})"));

        let i_slot = self.tmp();
        self.ins(&format!("{i_slot} = alloca i64"));
        self.store_slot_i64(&i_slot, "0");
        let cond = self.new_label("deep.copy.cond");
        let body = self.new_label("deep.copy.body");
        let end = self.new_label("deep.copy.end");
        self.term(&format!("br label %{cond}"));
        self.block(&cond);
        let i = self.dyn_load(&i_slot, "i64");
        let c = self.tmp();
        self.ins(&format!("{c} = icmp slt i64 {i}, {len}"));
        self.term(&format!("br i1 {c}, label %{body}, label %{end}"));
        self.block(&body);
        let row = self.tmp();
        self.ins(&format!("{row} = mul i64 {i}, {eslots}"));
        let d = self.slot_addr_dyn(&np, &row);
        let s = self.slot_addr_dyn(sp, &row);
        if self.type_owns_heap(&elem) {
            self.deep_copy_value(&elem, &d, &s);
        } else {
            self.copy_slot_i64(&d, &s);
        }
        let ni = self.tmp();
        self.ins(&format!("{ni} = add i64 {i}, 1"));
        self.store_slot_i64(&i_slot, &ni);
        self.term(&format!("br label %{cond}"));
        self.block(&end);
        Ok(np)
    }

    /// 深拷贝 descriptor 三元组（源、目标都可能是互不相邻的槽位地址）。
    fn deep_copy_dyn_to_local(
        &mut self,
        ty: &str,
        dst: &DynArrayInfo,
        src: &DynArrayInfo,
    ) -> TResult<()> {
        let sp = self.load_slot_ptr(&src.data);
        let len = self.load_slot_i64(&src.len);
        let cap = self.load_slot_i64(&src.cap);
        let np = self.dyn_copy_payload(ty, &sp, &len, &cap)?;
        self.ins(&format!("store ptr {np}, ptr {}", dst.data));
        self.store_slot_i64(&dst.len, &len);
        self.store_slot_i64(&dst.cap, &cap);
        Ok(())
    }

    /// 深拷贝扁平块中的 descriptor 三元组（目标/源按连续 3 槽解释）。
    fn deep_copy_dyn_slots(&mut self, ty: &str, dst: &str, src: &str) -> TResult<()> {
        let ddi = self.dyn_info_in_block(dst, 0);
        let sdi = self.dyn_info_in_block(src, 0);
        self.deep_copy_dyn_to_local(ty, &ddi, &sdi)
    }

    /// 从已有 descriptor 深拷贝出一个新的局部动态数组。
    fn dyn_deep_copy_from(&mut self, ty: &str, src: &DynArrayInfo) -> TResult<VarInfo> {
        let (data, len_s, cap_s) = self.dyn_new_slots();
        let dst = DynArrayInfo {
            data: data.clone(),
            len: len_s.clone(),
            cap: cap_s.clone(),
        };
        self.deep_copy_dyn_to_local(ty, &dst, src)?;
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: None,
            fields: HashMap::new(),
            array: None,
            dyn_array: Some(DynArrayInfo { data, len: len_s, cap: cap_s }),
        })
    }

    /// 把扁平槽块中的值转移给另一块（用于 return）：动态 descriptor 复制后清空源，
    /// 避免调用方接管后本地又 drop 一次。
    fn transfer_value_slots(&mut self, ty: &str, dst: &str, src: &str) {
        if !self.type_owns_heap(ty) {
            let n = self.value_slots(ty);
            self.copy_flat_i64(dst, src, n);
            return;
        }
        if Self::is_dynamic_array(ty) {
            let d0 = self.slot_addr(dst, 0);
            let d1 = self.slot_addr(dst, 1);
            let d2 = self.slot_addr(dst, 2);
            let s0 = self.slot_addr(src, 0);
            let s1 = self.slot_addr(src, 1);
            let s2 = self.slot_addr(src, 2);
            self.copy_slot_i64(&d0, &s0);
            self.copy_slot_i64(&d1, &s1);
            self.copy_slot_i64(&d2, &s2);
            self.clear_desc_addr(&s0, &s1, &s2);
            return;
        }
        if let Some(elem) = Self::array_elem(ty) {
            let elem = elem.to_string();
            let len = Self::array_decl_len(ty).expect("固定数组");
            let eslots = self.array_elem_slots(ty).expect("数组元素槽数");
            for i in 0..len {
                let d = self.slot_addr(dst, i * eslots);
                let s = self.slot_addr(src, i * eslots);
                self.transfer_value_slots(&elem, &d, &s);
            }
            return;
        }
        let defs = self.structs.get(ty).cloned().unwrap_or_default();
        for (fname, fty) in defs {
            let off = self
                .direct_field_slot_offset(ty, &fname)
                .expect("字段布局");
            let d = self.slot_addr(dst, off);
            let s = self.slot_addr(src, off);
            if Self::is_dynamic_array(&fty) {
                self.desc_transfer(&d, &s);
            } else if self.type_owns_heap(&fty) {
                self.transfer_value_slots(&fty, &d, &s);
            } else {
                let n = self.value_slots(&fty);
                self.copy_flat_i64(&d, &s, n);
            }
        }
    }

    /// descriptor 三元组复制 + 清空源（两者均为块中起始槽地址）。
    fn desc_transfer(&mut self, dst: &str, src: &str) {
        let d0 = self.slot_addr(dst, 0);
        let d1 = self.slot_addr(dst, 1);
        let d2 = self.slot_addr(dst, 2);
        let s0 = self.slot_addr(src, 0);
        let s1 = self.slot_addr(src, 1);
        let s2 = self.slot_addr(src, 2);
        self.copy_slot_i64(&d0, &s0);
        self.copy_slot_i64(&d1, &s1);
        self.copy_slot_i64(&d2, &s2);
        self.clear_desc_addr(&s0, &s1, &s2);
    }

    /// 递归 drop 扁平槽块中的值（不触碰标量）。
    fn drop_value_slots(&mut self, ty: &str, base: &str) {
        if !self.type_owns_heap(ty) {
            return;
        }
        if Self::is_dynamic_array(ty) {
            let d = self.slot_addr(base, 0);
            let l = self.slot_addr(base, 1);
            let c = self.slot_addr(base, 2);
            self.dyn_drop_slots(&d, &l, &c, ty);
            return;
        }
        if let Some(elem) = Self::array_elem(ty) {
            let elem = elem.to_string();
            let len = Self::array_decl_len(ty).expect("固定数组");
            let eslots = self.array_elem_slots(ty).expect("数组元素槽数");
            for i in 0..len {
                let a = self.slot_addr(base, i * eslots);
                self.drop_value_slots(&elem, &a);
            }
            return;
        }
        let defs = self.structs.get(ty).cloned().unwrap_or_default();
        for (fname, fty) in defs {
            let off = self
                .direct_field_slot_offset(ty, &fname)
                .expect("字段布局");
            if !self.type_owns_heap(&fty) {
                continue;
            }
            let a = self.slot_addr(base, off);
            if Self::is_dynamic_array(&fty) {
                let d = self.slot_addr(&a, 0);
                let l = self.slot_addr(&a, 1);
                let c = self.slot_addr(&a, 2);
                self.dyn_drop_slots(&d, &l, &c, &fty);
            } else {
                self.drop_value_slots(&fty, &a);
            }
        }
    }

    /// 递归 drop 一个局部变量（动态数组 / struct 字段 / 固定数组元素）。
    fn drop_var(&mut self, v: &VarInfo) {
        if let Some(di) = &v.dyn_array {
            let di = di.clone();
            self.dyn_drop(&di, &v.ty);
            return;
        }
        if let Some(len) = v.array {
            let Some(elem) = Self::array_elem(&v.ty).map(|s| s.to_string()) else {
                return;
            };
            if self.type_owns_heap(&elem) {
                let base = v.addr.clone().unwrap_or_default();
                let eslots = self.array_elem_slots(&v.ty).unwrap_or(1);
                for i in 0..len {
                    let a = self.slot_addr(&base, i * eslots);
                    self.drop_value_slots(&elem, &a);
                }
            }
            return;
        }
        if self.is_struct(&v.ty) {
            let fields: Vec<VarInfo> = v.fields.values().cloned().collect();
            for f in fields {
                self.drop_var(&f);
            }
        }
    }

    /// 把局部 struct 字段深拷贝到扁平槽块（目标可以是数组元素 / ABI buffer）。
    fn store_struct_local_to_slots(
        &mut self,
        ty: &str,
        fields: &HashMap<String, VarInfo>,
        dst: &str,
    ) -> TResult<()> {
        for entry in self.layout_of(ty) {
            let f = fields.get(&entry.path).ok_or_else(|| {
                TenetError::at_pos(
                    format!("缺少字段槽 `{}`", entry.path),
                    Position::new(1, 1),
                )
            })?;
            let target = self.slot_addr(dst, entry.offset);
            if Self::is_dynamic_array(&entry.ty) {
                let di = f.dyn_array.as_ref().ok_or_else(|| {
                    TenetError::at_pos(
                        format!("字段 `{}` 缺少动态数组 descriptor", entry.path),
                        Position::new(1, 1),
                    )
                })?;
                let dst_di = self.dyn_info_in_block(&target, 0);
                self.deep_copy_dyn_to_local(&entry.ty, &dst_di, di)?;
            } else if self.type_owns_heap(&entry.ty) {
                let src = f.addr.clone().unwrap();
                self.deep_copy_value(&entry.ty, &target, &src);
            } else if entry.slots > 1 {
                let src = f.addr.clone().unwrap();
                self.copy_flat_i64(&target, &src, entry.slots);
            } else {
                let src = f.addr.clone().unwrap();
                let v = self.tmp();
                self.ins(&format!(
                    "{v} = load {}, ptr {src}",
                    llvm_type(&entry.ty)
                ));
                let raw = self.pack_scalar(&entry.ty, &v);
                self.store_slot_i64(&target, &raw);
            }
        }
        Ok(())
    }

    /// 把局部 struct 字段转移到扁平槽块（return 用）：动态 descriptor 复制后清空源。
    fn transfer_struct_local_to_slots(
        &mut self,
        ty: &str,
        fields: &HashMap<String, VarInfo>,
        dst: &str,
    ) -> TResult<()> {
        for entry in self.layout_of(ty) {
            let f = fields.get(&entry.path).ok_or_else(|| {
                TenetError::at_pos(
                    format!("缺少字段槽 `{}`", entry.path),
                    Position::new(1, 1),
                )
            })?;
            let target = self.slot_addr(dst, entry.offset);
            if Self::is_dynamic_array(&entry.ty) {
                let di = f.dyn_array.as_ref().ok_or_else(|| {
                    TenetError::at_pos(
                        format!("字段 `{}` 缺少动态数组 descriptor", entry.path),
                        Position::new(1, 1),
                    )
                })?;
                let s0 = di.data.clone();
                let s1 = di.len.clone();
                let s2 = di.cap.clone();
                let d0 = self.slot_addr(&target, 0);
                let d1 = self.slot_addr(&target, 1);
                let d2 = self.slot_addr(&target, 2);
                self.copy_slot_i64(&d0, &s0);
                self.copy_slot_i64(&d1, &s1);
                self.copy_slot_i64(&d2, &s2);
                self.clear_desc_addr(&s0, &s1, &s2);
            } else if self.type_owns_heap(&entry.ty) {
                let src = f.addr.clone().unwrap();
                self.transfer_value_slots(&entry.ty, &target, &src);
            } else if entry.slots > 1 {
                let src = f.addr.clone().unwrap();
                self.copy_flat_i64(&target, &src, entry.slots);
            } else {
                let src = f.addr.clone().unwrap();
                let v = self.tmp();
                self.ins(&format!(
                    "{v} = load {}, ptr {src}",
                    llvm_type(&entry.ty)
                ));
                let raw = self.pack_scalar(&entry.ty, &v);
                self.store_slot_i64(&target, &raw);
            }
        }
        Ok(())
    }

    /// struct return 写入 %sret：
    /// - 变量：转移动态 descriptor 并清空本地（避免函数收尾时二次释放）；
    /// - 字面量：直接构造到 sret；
    /// - 调用：从被调函数的 sret buffer 转移。
    fn return_struct_to_sret(&mut self, ty: &str, expr: &Expr) -> TResult<()> {
        match &expr.kind {
            ExprKind::Var(src) => {
                let info = self.lookup_var(src, expr.pos.clone())?;
                if info.ty != ty {
                    return Err(TenetError::at_pos(
                        format!("返回类型不匹配：需要 {ty}，实际 {}", info.ty),
                        expr.pos.clone(),
                    ));
                }
                self.transfer_struct_local_to_slots(ty, &info.fields, "%sret")
            }
            ExprKind::StructLit { .. } => {
                self.pack_expr_to_buffer(ty, expr, "%sret")?;
                Ok(())
            }
            ExprKind::Call { .. } => {
                let (rt, buf) = self.gen_expr(expr)?;
                if rt != ty {
                    return Err(TenetError::at_pos(
                        format!("返回类型不匹配：需要 {ty}，调用返回 {rt}"),
                        expr.pos.clone(),
                    ));
                }
                self.transfer_value_slots(ty, "%sret", &buf);
                Ok(())
            }
            _ => Err(TenetError::at_pos(
                format!("{ty} 返回只支持变量、字面量或返回 {ty} 的调用"),
                expr.pos.clone(),
            )),
        }
    }

    /// 用字面量/变量/调用结果写入扁平槽块中的一个 struct 值。
    /// `drop_old=true` 时先递归 drop 目标位置的旧动态字段。
    fn write_struct_expr_to_slots(
        &mut self,
        ty: &str,
        expr: &Expr,
        dst: &str,
        drop_old: bool,
    ) -> TResult<()> {
        match &expr.kind {
            ExprKind::Var(src) => {
                let info = self.lookup_var(src, expr.pos.clone())?;
                if info.ty != ty {
                    return Err(TenetError::at_pos(
                        format!("需要 {ty}，实际是 {}", info.ty),
                        expr.pos.clone(),
                    ));
                }
                if drop_old {
                    self.drop_value_slots(ty, dst);
                }
                self.store_struct_local_to_slots(ty, &info.fields, dst)
            }
            ExprKind::StructLit { name, .. } => {
                if name != ty {
                    return Err(TenetError::at_pos(
                        format!("需要 {ty}，字面量是 {name}"),
                        expr.pos.clone(),
                    ));
                }
                let n = self.value_slots(ty);
                let buf = self.alloc_buffer(n);
                self.pack_expr_to_buffer(ty, expr, &buf)?;
                if drop_old {
                    self.drop_value_slots(ty, dst);
                }
                self.copy_flat_i64(dst, &buf, n);
                Ok(())
            }
            ExprKind::Call { .. } => {
                let (rt, buf) = self.gen_expr(expr)?;
                if rt != ty {
                    return Err(TenetError::at_pos(
                        format!("需要 {ty}，调用返回 {rt}"),
                        expr.pos.clone(),
                    ));
                }
                if drop_old {
                    self.drop_value_slots(ty, dst);
                }
                let n = self.value_slots(ty);
                self.copy_flat_i64(dst, &buf, n);
                Ok(())
            }
            _ => Err(TenetError::at_pos(
                format!("{ty} 值必须是字面量、同类型变量或返回 {ty} 的函数调用"),
                expr.pos.clone(),
            )),
        }
    }

    /// 整体赋值动态数组字段 `s.a = [..]` / `s.a = t.a`：先深拷贝右侧，再 drop 旧值。
    fn assign_dyn_place(
        &mut self,
        ty: &str,
        target: &DynArrayInfo,
        value: &Expr,
        pos: Position,
    ) -> TResult<()> {
        let tmp = self.init_dynamic_array("__assign_tmp", ty, value, pos)?;
        let tdi = tmp.dyn_array.as_ref().unwrap();
        let nd = self.dyn_load(&tdi.data, "ptr");
        let nl = self.dyn_load(&tdi.len, "i64");
        let nc = self.dyn_load(&tdi.cap, "i64");
        self.dyn_drop_slots(&target.data, &target.len, &target.cap, ty);
        self.ins(&format!("store ptr {nd}, ptr {}", target.data));
        self.store_slot_i64(&target.len, &nl);
        self.store_slot_i64(&target.cap, &nc);
        Ok(())
    }

    /// 解析一个动态数组左值（变量或 struct 字段 / 数组元素的动态字段）。
    fn resolve_dyn_target(&mut self, expr: &Expr) -> TResult<Option<(String, DynArrayInfo)>> {
        if let ExprKind::Var(name) = &expr.kind {
            let info = self.lookup_var(name, expr.pos.clone())?;
            if let Some(di) = info.dyn_array {
                return Ok(Some((info.ty, di)));
            }
        }
        if let Some(Place::DynArray { ty, info }) = self.resolve_place(expr)? {
            return Ok(Some((ty, info)));
        }
        Ok(None)
    }

    fn pack_fixed_array_expr(&mut self, ty: &str, expr: &Expr, buf: &str) -> TResult<()> {
        let total = self.fixed_array_total_slots(ty)?;
        match &expr.kind {
            ExprKind::Var(src) => {
                let info = self.lookup_var(src, expr.pos.clone())?;
                if info.ty != ty {
                    return Err(TenetError::at_pos(
                        format!("数组参数类型不匹配：需要 {ty}，实际 {}", info.ty),
                        expr.pos.clone(),
                    ));
                }
                let src_addr = info.addr.clone().unwrap();
                self.copy_flat_i64(buf, &src_addr, total);
                Ok(())
            }
            ExprKind::Array(_) => {
                let tmp = self.init_array("__arr_tmp", ty, expr, expr.pos.clone())?;
                let src = tmp.addr.clone().unwrap();
                self.copy_flat_i64(buf, &src, total);
                Ok(())
            }
            ExprKind::Call { .. } => {
                let (rt, src) = self.gen_expr(expr)?;
                if rt != ty {
                    return Err(TenetError::at_pos(
                        format!("数组参数类型不匹配：需要 {ty}，调用返回 {rt}"),
                        expr.pos.clone(),
                    ));
                }
                self.copy_flat_i64(buf, &src, total);
                Ok(())
            }
            _ => Err(TenetError::at_pos(
                "嵌套数组实参必须是变量、字面量或返回数组的调用".to_string(),
                expr.pos.clone(),
            )),
        }
    }

    fn init_nested_array(
        &mut self,
        name: &str,
        ty: &str,
        value: &Expr,
        pos: Position,
    ) -> TResult<VarInfo> {
        let elem = self.array_elem_or_err(ty, pos.clone())?;
        let inner_len = Self::array_decl_len(&elem).ok_or_else(|| {
            TenetError::at_pos("嵌套数组内层必须是固定长度 array<T, N>".to_string(), pos.clone())
        })?;
        let inner_elem = Self::array_elem(&elem).unwrap();
        if inner_elem == T_BOOL {
            return Err(TenetError::at_pos(
                "嵌套数组内层暂不支持 bool".to_string(),
                pos.clone(),
            ));
        }
        let inner_slots = self.array_elem_slots(ty)?;
        if let ExprKind::Call { .. } = &value.kind {
            let (rt, src) = self.gen_expr(value)?;
            if rt != ty {
                return Err(TenetError::at_pos(
                    format!("`{name}` 需要 {ty}，调用返回 {rt}"),
                    value.pos.clone(),
                ));
            }
            let total = self.fixed_array_total_slots(ty)?;
            let addr = self.tmp();
            self.ins(&format!("{addr} = alloca [{total} x i64]"));
            self.copy_flat_i64(&addr, &src, total);
            return Ok(VarInfo {
                ty: ty.to_string(),
                addr: Some(addr),
                fields: HashMap::new(),
                array: Some(Self::array_decl_len(ty).unwrap()),
                dyn_array: None,
            });
        }
        let decl_len = Self::array_decl_len(ty);
        let (len, src_literal, src_addr) = match &value.kind {
            ExprKind::Array(elems) => {
                if elems.is_empty() {
                    return Err(TenetError::at_pos("固定数组不支持空字面量", value.pos.clone()));
                }
                if let Some(n) = decl_len {
                    if n != elems.len() {
                        return Err(TenetError::at_pos(
                            format!("数组长度不匹配：类型写 {n}，字面量 {}", elems.len()),
                            value.pos.clone(),
                        ));
                    }
                }
                (elems.len(), Some(elems), None)
            }
            ExprKind::Var(src) => {
                let sinfo = self.lookup_var(src, value.pos.clone())?;
                let slen = sinfo.array.ok_or_else(|| {
                    TenetError::at_pos(format!("`{src}` 不是固定数组"), value.pos.clone())
                })?;
                if sinfo.ty != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，但 `{src}` 是 {}", sinfo.ty),
                        value.pos.clone(),
                    ));
                }
                (slen, None, Some(sinfo.addr.clone().unwrap()))
            }
            _ => {
                return Err(TenetError::at_pos(
                    format!("`{name}` 的嵌套数组初始化必须是字面量或同类型数组变量"),
                    value.pos.clone(),
                ))
            }
        };
        let addr = self.tmp();
        self.ins(&format!("{addr} = alloca [{} x i64]", len * inner_slots));
        if let Some(elems) = src_literal {
            for (i, e) in elems.iter().enumerate() {
                let tmp = self.init_array("__nested_tmp", &elem, e, e.pos.clone())?;
                let taddr = tmp.addr.clone().unwrap();
                for k in 0..inner_slots {
                    let sa = self.tmp();
                    self.ins(&format!("{sa} = getelementptr i64, ptr {taddr}, i64 {k}"));
                    let da = self.tmp();
                    self.ins(&format!(
                        "{da} = getelementptr i64, ptr {addr}, i64 {}",
                        i * inner_slots + k
                    ));
                    let v = self.tmp();
                    self.ins(&format!("{v} = load i64, ptr {sa}"));
                    self.ins(&format!("store i64 {v}, ptr {da}"));
                }
                let _ = inner_len;
            }
        } else if let Some(src) = src_addr {
            for k in 0..(len * inner_slots) {
                let sa = self.tmp();
                self.ins(&format!("{sa} = getelementptr i64, ptr {src}, i64 {k}"));
                let da = self.tmp();
                self.ins(&format!("{da} = getelementptr i64, ptr {addr}, i64 {k}"));
                let v = self.tmp();
                self.ins(&format!("{v} = load i64, ptr {sa}"));
                self.ins(&format!("store i64 {v}, ptr {da}"));
            }
        }
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: Some(addr),
            fields: HashMap::new(),
            array: Some(len),
            dyn_array: None,
        })
    }

    fn init_array(&mut self, name: &str, ty: &str, value: &Expr, pos: Position) -> TResult<VarInfo> {
        let elem0 = self.array_elem_or_err(ty, pos.clone())?;
        if self.is_struct(&elem0) {
            return self.init_struct_array(name, ty, value, pos);
        }
        if self.is_array(&elem0) {
            return self.init_nested_array(name, ty, value, pos);
        }
        let elem = Self::array_elem_scalar(ty, pos.clone())?;
        let elem_ll = llvm_type(&elem);
        let decl_len = Self::array_decl_len(ty);
        let (len, src_literal, src_ptr) = match &value.kind {
            ExprKind::Array(elems) => {
                if elems.is_empty() {
                    return Err(TenetError::at_pos(
                        "v1 不支持空数组字面量".to_string(),
                        value.pos.clone(),
                    ));
                }
                if let Some(n) = decl_len {
                    if n != elems.len() {
                        return Err(TenetError::at_pos(
                            format!("数组长度不匹配：类型写 {n}，字面量 {}", elems.len()),
                            value.pos.clone(),
                        ));
                    }
                }
                (elems.len(), Some(elems), None)
            }
            ExprKind::Var(src) => {
                let sinfo = self.lookup_var(src, value.pos.clone())?;
                let slen = sinfo.array.ok_or_else(|| {
                    TenetError::at_pos(format!("`{src}` 不是数组"), value.pos.clone())
                })?;
                if Self::array_elem(&sinfo.ty) != Some(elem.as_str()) {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，但 `{src}` 是 {}", sinfo.ty),
                        value.pos.clone(),
                    ));
                }
                if let Some(n) = decl_len {
                    if n != slen {
                        return Err(TenetError::at_pos(
                            format!("数组长度不匹配：需要 {n}，实际是 {slen}"),
                            value.pos.clone(),
                        ));
                    }
                }
                (slen, None, Some(sinfo.addr.clone().unwrap()))
            }
            ExprKind::Call { .. } => {
                let (rt, buf) = self.gen_expr(value)?;
                let relem = Self::array_elem(&rt).ok_or_else(|| {
                    TenetError::at_pos(format!("调用没有返回数组：{rt}"), value.pos.clone())
                })?;
                if relem != elem {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，调用返回 {rt}"),
                        value.pos.clone(),
                    ));
                }
                let rlen = Self::array_decl_len(&rt).ok_or_else(|| {
                    TenetError::at_pos("返回数组必须带长度 array<T, N>".to_string(), value.pos.clone())
                })?;
                if let Some(n) = decl_len {
                    if n != rlen {
                        return Err(TenetError::at_pos(
                            format!("数组长度不匹配：需要 {n}，调用返回 {rlen}"),
                            value.pos.clone(),
                        ));
                    }
                }
                (rlen, None, Some(buf))
            }
            _ => {
                return Err(TenetError::at_pos(
                    format!("`{name}` 的数组初始化必须是字面量、同类型数组变量或返回数组的调用"),
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
        } else if let Some(src) = src_ptr {
            self.copy_array_ptr(&addr, &src, len, elem_ll);
        }
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: Some(addr),
            fields: HashMap::new(),
            array: Some(len),
            dyn_array: None,
        })
    }

    fn assign_array(&mut self, dst: &VarInfo, value: &Expr, pos: Position) -> TResult<()> {
        if self.is_flat_slot_array(&dst.ty) {
            let total = self.fixed_array_total_slots(&dst.ty)?;
            let dbase = dst.addr.clone().unwrap();
            if let ExprKind::Var(src) = &value.kind {
                let sinfo = self.lookup_var(src, value.pos.clone())?;
                if sinfo.ty != dst.ty {
                    return Err(TenetError::at_pos(
                        format!("数组赋值类型不匹配：需要 {}，右侧是 {}", dst.ty, sinfo.ty),
                        value.pos.clone(),
                    ));
                }
                self.drop_var(dst);
                if self.type_owns_heap(&dst.ty) {
                    let sbase = sinfo.addr.clone().unwrap();
                    self.deep_copy_value(&dst.ty, &dbase, &sbase);
                } else {
                    let sbase = sinfo.addr.clone().unwrap();
                    self.copy_flat_i64(&dbase, &sbase, total);
                }
                return Ok(());
            }
            let tmp = self.alloc_buffer(total);
            self.pack_fixed_array_expr(&dst.ty, value, &tmp)?;
            self.drop_var(dst);
            self.copy_flat_i64(&dbase, &tmp, total);
            return Ok(());
        }
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
                if Self::array_elem(&sinfo.ty) != Some(elem.as_str()) || sinfo.array != Some(len) {
                    return Err(TenetError::at_pos(
                        format!("数组赋值类型不匹配：需要 {}，右侧是 {}", dst.ty, sinfo.ty),
                        value.pos.clone(),
                    ));
                }
                let sbase = sinfo.addr.clone().unwrap();
                self.copy_array_ptr(&dbase, &sbase, len, &elem_ll);
                Ok(())
            }
            ExprKind::Call { .. } => {
                let (rt, buf) = self.gen_expr(value)?;
                if Self::array_elem(&rt) != Some(elem.as_str())
                    || Self::array_decl_len(&rt) != Some(len)
                {
                    return Err(TenetError::at_pos(
                        format!("数组赋值类型不匹配：需要 {}，调用返回 {rt}", dst.ty),
                        value.pos.clone(),
                    ));
                }
                self.copy_array_ptr(&dbase, &buf, len, &elem_ll);
                Ok(())
            }
            _ => Err(TenetError::at_pos(
                "数组赋值必须是同类型数组变量、同长度字面量或返回数组的调用",
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
                // 先释放旧值，再深拷贝右侧（右侧来自另一个局部变量）。
                self.drop_var(dst);
                self.copy_struct(dst, &sinfo)
            }
            ExprKind::StructLit { name: sname, .. } => {
                if sname != &dst.ty {
                    return Err(TenetError::at_pos(
                        format!("赋值类型不匹配：需要 {}，字面量是 {sname}", dst.ty),
                        pos,
                    ));
                }
                let n = self.struct_total_slots(&dst.ty);
                let buf = self.alloc_buffer(n);
                self.pack_expr_to_buffer(&dst.ty, value, &buf)?;
                self.drop_var(dst);
                self.unpack_buffer(dst, &dst.ty, &buf)
            }
            ExprKind::Call { .. } => {
                let (rt, buf) = self.gen_expr(value)?;
                if rt != dst.ty {
                    return Err(TenetError::at_pos(
                        format!("赋值类型不匹配：需要 {}，右侧是 {rt}", dst.ty),
                        pos,
                    ));
                }
                self.drop_var(dst);
                self.unpack_buffer(dst, &dst.ty, &buf)
            }
            _ => Err(TenetError::at_pos(
                "struct 整体赋值必须是同类型变量、字面量或返回 struct 的调用",
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

    fn expr_var_path(expr: &Expr) -> Option<(String, String)> {
        match &expr.kind {
            ExprKind::Var(name) => Some((name.clone(), String::new())),
            ExprKind::Field { base, field } => {
                let (name, path) = Self::expr_var_path(base)?;
                Some((
                    name,
                    if path.is_empty() { field.clone() } else { format!("{path}.{field}") },
                ))
            }
            _ => None,
        }
    }

    /// 纯字段/常量下标路径（用于识别 `s.a = s.a` 这类自赋值）。
    fn place_path(expr: &Expr) -> Option<String> {
        match &expr.kind {
            ExprKind::Var(name) => Some(name.clone()),
            ExprKind::Field { base, field } => {
                Some(format!("{}.{}", Self::place_path(base)?, field))
            }
            ExprKind::Index { base, index } => match &index.kind {
                ExprKind::Int(i) => Some(format!("{}[{}]", Self::place_path(base)?, i)),
                _ => None,
            },
            _ => None,
        }
    }

    /// 为 struct 局部变量分配扁平字段槽位（嵌套路径如 a.x）。
    ///
    /// - 标量字段：`alloca <标量类型>`；
    /// - 固定数组字段：`alloca [N * elem_slots x i64]`，统一用扁平 i64 槽表示；
    /// - 动态数组字段：data/len/cap 三个独立槽位（局部表示）；
    /// - 嵌套 struct：递归展开成点路径。
    fn alloc_struct(&mut self, ty: &str, pos: Position) -> TResult<VarInfo> {
        if !self.structs.contains_key(ty) {
            return Err(TenetError::at_pos(format!("未定义的 struct `{ty}`"), pos));
        }
        let mut fields = HashMap::new();
        self.alloc_struct_fields(ty, "", &mut fields)?;
        Ok(VarInfo {
            ty: ty.to_string(),
            addr: None,
            fields,
            array: None,
            dyn_array: None,
        })
    }

    fn alloc_struct_fields(
        &mut self,
        ty: &str,
        prefix: &str,
        fields: &mut HashMap<String, VarInfo>,
    ) -> TResult<()> {
        let defs = self.struct_fields(ty, Position::new(1, 1))?;
        for (fname, fty) in defs {
            let path = if prefix.is_empty() {
                fname.clone()
            } else {
                format!("{prefix}.{fname}")
            };
            if self.is_struct(&fty) {
                self.alloc_struct_fields(&fty, &path, fields)?;
            } else if Self::is_dynamic_array(&fty) {
                // 动态数组字段：data/len/cap 三个独立槽位（局部表示）。
                let (data, len, cap) = self.dyn_new_slots();
                fields.insert(
                    path,
                    VarInfo {
                        ty: fty.clone(),
                        addr: None,
                        fields: HashMap::new(),
                        array: None,
                        dyn_array: Some(DynArrayInfo { data, len, cap }),
                    },
                );
            } else if self.is_array(&fty) {
                let slots = self.field_slot_width(&fty);
                let addr = self.tmp();
                self.ins(&format!("{addr} = alloca [{slots} x i64]"));
                fields.insert(
                    path,
                    VarInfo {
                        ty: fty.clone(),
                        addr: Some(addr),
                        fields: HashMap::new(),
                        array: Some(Self::array_decl_len(&fty).unwrap()),
                        dyn_array: None,
                    },
                );
            } else {
                let addr = self.tmp();
                self.ins(&format!("{addr} = alloca {}", llvm_type(&fty)));
                fields.insert(
                    path,
                    VarInfo {
                        ty: fty,
                        addr: Some(addr),
                        fields: HashMap::new(),
                        array: None,
                        dyn_array: None,
                    },
                );
            }
        }
        Ok(())
    }

    /// struct 初始化：字面量/同类型变量/返回 struct 的调用。
    fn init_struct(&mut self, name: &str, ty: &str, value: &Expr, pos: Position) -> TResult<VarInfo> {
        let dst = self.alloc_struct(ty, pos.clone())?;
        match &value.kind {
            ExprKind::StructLit { name: sname, .. } => {
                if sname != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 标注为 {ty}，但字面量是 {sname}"),
                        value.pos.clone(),
                    ));
                }
                let n = self.struct_total_slots(ty);
                let buf = self.alloc_buffer(n);
                self.pack_expr_to_buffer(ty, value, &buf)?;
                self.unpack_buffer(&dst, ty, &buf)?;
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
            ExprKind::Call { .. } => {
                let (rt, buf) = self.gen_expr(value)?;
                if rt != ty {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 需要 {ty}，但调用返回 {rt}"),
                        value.pos.clone(),
                    ));
                }
                self.unpack_buffer(&dst, ty, &buf)?;
                Ok(dst)
            }
            _ => Err(TenetError::at_pos(
                format!("`{name}` 的 struct 初始化必须是 `{ty} {{ ... }}`、同类型变量或返回 {ty} 的调用"),
                value.pos.clone(),
            )),
        }
    }

    /// struct 整体拷贝（深拷贝）：
    /// 标量字段逐槽复制；固定数组字段在含堆元素时递归深拷贝；
    /// 动态数组字段 malloc 新块并复制元素。
    fn copy_struct(&mut self, dst: &VarInfo, src: &VarInfo) -> TResult<()> {
        for (path, dfield) in &dst.fields {
            let sfield = src.fields.get(path).ok_or_else(|| {
                TenetError::at_pos(format!("struct 字段 `{path}` 不存在"), Position::new(1, 1))
            })?;
            if let Some(ddi) = &dfield.dyn_array {
                let sdi = sfield.dyn_array.as_ref().ok_or_else(|| {
                    TenetError::at_pos(
                        format!("结构字段 `{path}` 的动态数组状态不一致"),
                        Position::new(1, 1),
                    )
                })?;
                self.deep_copy_dyn_to_local(&dfield.ty, ddi, sdi)?;
                continue;
            }
            let daddr = dfield.addr.clone().unwrap();
            let saddr = sfield.addr.clone().unwrap();
            if self.is_array(&dfield.ty) {
                if self.type_owns_heap(&dfield.ty) {
                    self.deep_copy_value(&dfield.ty, &daddr, &saddr);
                } else {
                    let slots = self.field_slot_width(&dfield.ty);
                    self.copy_flat_i64(&daddr, &saddr, slots);
                }
                continue;
            }
            let t = dfield.ty.clone();
            let v = self.tmp();
            self.ins(&format!("{v} = load {}, ptr {saddr}", llvm_type(&t)));
            self.ins(&format!("store {} {v}, ptr {daddr}", llvm_type(&t)));
        }
        Ok(())
    }

    /// struct 直接字段（不递归展开）在 struct 块中的起始槽偏移。
    fn direct_field_slot_offset(&self, ty: &str, field: &str) -> TResult<usize> {
        let defs = self.struct_fields(ty, Position::new(1, 1))?;
        let mut off = 0;
        for (fname, fty) in defs {
            if fname == field {
                return Ok(off);
            }
            off += self.field_slot_width(&fty);
        }
        Err(TenetError::at_pos(
            format!("struct `{ty}` 没有字段 `{field}`"),
            Position::new(1, 1),
        ))
    }

    fn gep_i8(&mut self, base: &str, byte_off: usize) -> String {
        let addr = self.tmp();
        self.ins(&format!(
            "{addr} = getelementptr i8, ptr {base}, i64 {byte_off}"
        ));
        addr
    }

    /// 解析左值风格的固定数组/struct 访问（含字段、下标、数组元素字段）。
    fn resolve_place(&mut self, expr: &Expr) -> TResult<Option<Place>> {
        match &expr.kind {
            ExprKind::Var(name) => {
                let info = self.lookup_var(name, expr.pos.clone())?;
                if info.dyn_array.is_some() {
                    return Ok(None);
                }
                if let Some(len) = info.array {
                    return Ok(Some(Place::Array {
                        ty: info.ty,
                        addr: info.addr.unwrap(),
                        len,
                        packed: false,
                    }));
                }
                if self.is_struct(&info.ty) {
                    return Ok(Some(Place::Struct {
                        ty: info.ty,
                        addr: None,
                        fields: Some(info.fields),
                        prefix: String::new(),
                    }));
                }
                Ok(info.addr.map(|addr| Place::Scalar {
                    ty: info.ty,
                    addr,
                }))
            }
            ExprKind::Field { base, field } => {
                let Some(bp) = self.resolve_place(base)? else {
                    return Ok(None);
                };
                let Place::Struct {
                    ty,
                    addr,
                    fields,
                    prefix,
                } = bp
                else {
                    return Ok(None);
                };
                let defs = self.struct_fields(&ty, expr.pos.clone())?;
                let fty = defs
                    .iter()
                    .find(|(n, _)| n == field)
                    .map(|(_, t)| t.clone())
                    .ok_or_else(|| {
                        TenetError::at_pos(
                            format!("struct `{ty}` 没有字段 `{field}`"),
                            expr.pos.clone(),
                        )
                    })?;
                if let Some(fs) = &fields {
                    let path = if prefix.is_empty() {
                        field.clone()
                    } else {
                        format!("{prefix}.{field}")
                    };
                    if let Some(f) = fs.get(&path) {
                        if self.is_array(&f.ty) {
                            if let Some(di) = &f.dyn_array {
                                return Ok(Some(Place::DynArray {
                                    ty: f.ty.clone(),
                                    info: di.clone(),
                                }));
                            }
                            return Ok(Some(Place::Array {
                                ty: f.ty.clone(),
                                addr: f.addr.clone().unwrap(),
                                len: f.array.unwrap(),
                                packed: true,
                            }));
                        }
                        return Ok(Some(Place::Scalar {
                            ty: f.ty.clone(),
                            addr: f.addr.clone().unwrap(),
                        }));
                    }
                    if self.is_struct(&fty) {
                        return Ok(Some(Place::Struct {
                            ty: fty,
                            addr: None,
                            fields: Some(fs.clone()),
                            prefix: path,
                        }));
                    }
                    return Err(TenetError::at_pos(
                        format!("struct `{ty}` 没有字段 `{path}`"),
                        expr.pos.clone(),
                    ));
                }
                let base_addr = addr.ok_or_else(|| {
                    TenetError::at_pos(
                        format!("struct `{ty}` 没有可寻址的内存块"),
                        expr.pos.clone(),
                    )
                })?;
                let off = self.direct_field_slot_offset(&ty, field)?;
                let faddr = self.gep_i8(&base_addr, off * 8);
                if self.is_struct(&fty) {
                    Ok(Some(Place::Struct {
                        ty: fty,
                        addr: Some(faddr),
                        fields: None,
                        prefix: String::new(),
                    }))
                } else if self.is_array(&fty) {
                    if Self::is_dynamic_array(&fty) {
                        Ok(Some(Place::DynArray {
                            ty: fty.clone(),
                            info: self.dyn_info_in_block(&faddr, 0),
                        }))
                    } else {
                        Ok(Some(Place::Array {
                            ty: fty.clone(),
                            addr: faddr,
                            len: Self::array_decl_len(&fty).unwrap(),
                            packed: true,
                        }))
                    }
                } else {
                    Ok(Some(Place::Scalar {
                        ty: fty,
                        addr: faddr,
                    }))
                }
            }
            ExprKind::Index { base, index } => {
                // `dynamic_arr[i]` 的 struct 元素：供 `arr[i].field` / `arr[i].a[j]` 链式访问。
                if let ExprKind::Var(name) = &base.kind {
                    let info = self.lookup_var(name, base.pos.clone())?;
                    if info.dyn_array.is_some() {
                        let elem =
                            self.array_elem_or_err(&info.ty, expr.pos.clone())?;
                        if self.is_struct(&elem) {
                            let (elem, elem_addr) = self.struct_array_elem_addr(
                                &info,
                                index,
                                expr.pos.clone(),
                            )?;
                            return Ok(Some(Place::Struct {
                                ty: elem,
                                addr: Some(elem_addr),
                                fields: None,
                                prefix: String::new(),
                            }));
                        }
                    }
                }
                let Some(bp) = self.resolve_place(base)? else {
                    return Ok(None);
                };
                let (ty, addr, len, packed) = match bp {
                    Place::DynArray { ty, info } => {
                        let elem = self.array_elem_or_err(&ty, expr.pos.clone())?;
                        if self.is_array(&elem) || self.is_struct(&elem) {
                            return Err(TenetError::at_pos(
                                format!(
                                    "v1 动态数组字段只支持标量元素，不支持对 `{elem}` 元素取下标"
                                ),
                                expr.pos.clone(),
                            ));
                        }
                        let data = self.dyn_load(&info.data, "ptr");
                        let dlen = self.dyn_load(&info.len, "i64");
                        let (it, iv) = self.gen_expr(index)?;
                        if it != llvm_type(T_INT) {
                            return Err(TenetError::at_pos(
                                format!(
                                    "数组下标必须是 int，实际为 {}",
                                    tenet_name(&it)
                                ),
                                index.pos.clone(),
                            ));
                        }
                        self.bounds_check_op(&iv, &dlen);
                        let slots = self.array_elem_slots(&ty)?;
                        let row = self.tmp();
                        self.ins(&format!("{row} = mul i64 {iv}, {slots}"));
                        let slot = self.dyn_slot(&data, &row);
                        return Ok(Some(Place::Scalar {
                            ty: elem,
                            addr: slot,
                        }));
                    }
                    Place::Array {
                        ty,
                        addr,
                        len,
                        packed,
                    } => (ty, addr, len, packed),
                    _ => return Ok(None),
                };
                let elem = self.array_elem_or_err(&ty, expr.pos.clone())?;
                let slots = self.array_elem_slots(&ty)?;
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
                let flat_elem = slots > 1 || packed || self.is_array(&elem);
                let elem_addr = if flat_elem {
                    let row = self.tmp();
                    self.ins(&format!("{row} = mul i64 {idx}, {slots}"));
                    let a = self.tmp();
                    self.ins(&format!("{a} = getelementptr i64, ptr {addr}, i64 {row}"));
                    a
                } else {
                    let elem_ll = llvm_type(&elem);
                    self.array_addr(&addr, len, &idx, elem_ll)
                };
                if self.is_struct(&elem) {
                    Ok(Some(Place::Struct {
                        ty: elem,
                        addr: Some(elem_addr),
                        fields: None,
                        prefix: String::new(),
                    }))
                } else if self.is_array(&elem) {
                    Ok(Some(Place::Array {
                        ty: elem.clone(),
                        addr: elem_addr,
                        len: Self::array_decl_len(&elem).unwrap_or(0),
                        packed: true,
                    }))
                } else {
                    Ok(Some(Place::Scalar {
                        ty: elem,
                        addr: elem_addr,
                    }))
                }
            }
            _ => Ok(None),
        }
    }

    /// 从解析出的左值读取值。
    fn load_place(&mut self, place: &Place, pos: Position) -> TResult<(String, String)> {
        match place {
            Place::Scalar { ty, addr } => {
                let r = self.tmp();
                self.ins(&format!("{r} = load {}, ptr {addr}", llvm_type(ty)));
                Ok((llvm_type(ty).into(), r))
            }
            Place::Array { .. } => Err(TenetError::at_pos(
                "数组值不能直接取值；请使用下标或整体赋值".to_string(),
                pos,
            )),
            Place::DynArray { .. } => Err(TenetError::at_pos(
                "动态数组字段不能直接取值；请使用下标、len()、print() 或整体字段赋值"
                    .to_string(),
                pos,
            )),
            Place::Struct { .. } => Err(TenetError::at_pos(
                "struct 值不能直接取值；请继续访问字段".to_string(),
                pos,
            )),
        }
    }

    /// 把固定数组表达式写入已解析的数组槽区（`addr` 为扁平 i64 槽）。
    /// 变量来源会深拷贝；字面量/调用结果先构造再接管，覆盖前先 drop 旧值。
    fn store_array_place(
        &mut self,
        ty: &str,
        addr: &str,
        value: &Expr,
        pos: Position,
    ) -> TResult<()> {
        let total = self.fixed_array_total_slots(ty)?;
        if let ExprKind::Var(src) = &value.kind {
            let info = self.lookup_var(src, value.pos.clone())?;
            if info.ty != ty {
                return Err(TenetError::at_pos(
                    format!("数组赋值类型不匹配：需要 {ty}，右侧是 {}", info.ty),
                    value.pos.clone(),
                ));
            }
            self.drop_value_slots(ty, addr);
            let saddr = info.addr.clone().unwrap();
            self.deep_copy_value(ty, addr, &saddr);
            return Ok(());
        }
        let buf = self.alloc_buffer(total);
        self.pack_array_field_expr(ty, value, &buf, 0).map_err(|mut e| {
            if e.pos.is_none() {
                e.pos = Some(pos);
            }
            e
        })?;
        self.drop_value_slots(ty, addr);
        self.copy_flat_i64(addr, &buf, total);
        Ok(())
    }

    /// 写入解析出的左值。
    fn store_place(
        &mut self,
        place: &Place,
        value: &Expr,
        pos: Position,
    ) -> TResult<(String, String)> {
        match place {
            Place::Scalar { ty, addr } => {
                let (vt, v) = self.gen_expr(value)?;
                if vt != llvm_type(ty) {
                    return Err(TenetError::at_pos(
                        format!(
                            "赋值类型不匹配：需要 {ty}，实际 {}",
                            tenet_name(&vt)
                        ),
                        value.pos.clone(),
                    ));
                }
                self.ins(&format!("store {vt} {v}, ptr {addr}"));
                Ok((vt, v))
            }
            Place::Array { ty, addr, .. } => {
                self.store_array_place(ty, addr, value, pos)?;
                Ok((ty.clone(), String::new()))
            }
            Place::DynArray { ty, info } => {
                self.assign_dyn_place(ty, info, value, pos)?;
                Ok((ty.clone(), String::new()))
            }
            Place::Struct {
                ty,
                addr: Some(addr),
                ..
            } => {
                self.write_struct_expr_to_slots(ty, value, addr, true)?;
                Ok((ty.clone(), String::new()))
            }
            Place::Struct { addr: None, .. } => Err(TenetError::at_pos(
                "struct 整体赋值需要可寻址的 struct 变量".to_string(),
                pos,
            )),
        }
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
        if callee == "push" {
            if args.len() != 2 {
                return Err(TenetError::at_pos(
                    "`push` 需要两个参数：数组变量和值".to_string(),
                    pos.clone(),
                ));
            }
            let Some((ty, di)) = self.resolve_dyn_target(&args[0])? else {
                return Err(TenetError::at_pos(
                    "`push` 第一个参数必须是动态数组变量或 struct 的动态数组字段"
                        .to_string(),
                    args[0].pos.clone(),
                ));
            };
            let info = VarInfo {
                ty: ty.clone(),
                addr: None,
                fields: HashMap::new(),
                array: None,
                dyn_array: Some(di),
            };
            let elem0 = self.array_elem_or_err(&info.ty, args[0].pos.clone())?;
            if self.is_struct(&elem0) {
                self.push_struct_dynamic(&info, &args[1], pos)?;
                return Ok(("void".into(), String::new()));
            }
            if self.is_array(&elem0) {
                self.push_nested_dynamic(&info, &args[1], pos)?;
                return Ok(("void".into(), String::new()));
            }
            let di = info.dyn_array.as_ref().unwrap();
            let elem = Self::array_elem_scalar(&info.ty, args[0].pos.clone())?;
            let elem_ll = llvm_type(&elem);
            let (vt, v) = self.gen_expr(&args[1])?;
            if vt != elem_ll {
                return Err(TenetError::at_pos(
                    format!("push 值类型不匹配：需要 {elem}，实际 {}", tenet_name(&vt)),
                    args[1].pos.clone(),
                ));
            }
            let len = self.dyn_load(&di.len, "i64");
            let cap = self.dyn_load(&di.cap, "i64");
            let need = self.tmp();
            self.ins(&format!("{need} = icmp eq i64 {len}, {cap}"));
            let grow = self.new_label("dyn.grow");
            let after = self.new_label("dyn.grow.after");
            self.term(&format!("br i1 {need}, label %{grow}, label %{after}"));
            self.block(&grow);
            let newcap = self.grow_cap(&cap);
            let bytes = self.tmp();
            self.ins(&format!("{bytes} = mul i64 {newcap}, 8"));
            let np = self.tmp();
            self.ins(&format!("{np} = call ptr @malloc(i64 {bytes})"));
            let op = self.dyn_load(&di.data, "ptr");
            self.dyn_copy_elems(&np, &op, &len, &elem);
            self.ins(&format!("call void @free(ptr {op})"));
            self.ins(&format!("store ptr {np}, ptr {}", di.data));
            self.ins(&format!("store i64 {newcap}, ptr {}", di.cap));
            self.term(&format!("br label %{after}"));
            self.block(&after);
            let data = self.dyn_load(&di.data, "ptr");
            let slot = self.dyn_slot(&data, &len);
            let raw = self.dyn_pack(&elem, &v);
            self.ins(&format!("store i64 {raw}, ptr {slot}"));
            let nl = self.tmp();
            self.ins(&format!("{nl} = add i64 {len}, 1"));
            self.ins(&format!("store i64 {nl}, ptr {}", di.len));
            return Ok(("void".into(), String::new()));
        }
        if callee == "len" {
            if args.len() != 1 {
                return Err(TenetError::at_pos(
                    "`len` 需要且只需要一个数组参数".to_string(),
                    pos.clone(),
                ));
            }
            if let ExprKind::Index { base, index } = &args[0].kind {
                if let ExprKind::Var(name) = &base.kind {
                    let info = self.lookup_var(name, base.pos.clone())?;
                    if Self::is_dynamic_nested_array(&info.ty) {
                        // len(a[i])：先做外层越界检查，再读内层 descriptor 的 len 槽。
                        let row = self.dynamic_nested_row_desc(&info, index)?;
                        let s1 = self.desc_slot(&row, 1);
                        let len = self.dyn_load(&s1, "i64");
                        return Ok((llvm_type(T_INT).into(), len));
                    }
                }
            }
            if let Some((_ty, di)) = self.resolve_dyn_target(&args[0])? {
                let len = self.dyn_load(&di.len, "i64");
                return Ok((llvm_type(T_INT).into(), len));
            }
            let ExprKind::Var(name) = &args[0].kind else {
                return Err(TenetError::at_pos(
                    "`len` 参数必须是数组变量",
                    args[0].pos.clone(),
                ));
            };
            let info = self.lookup_var(name, args[0].pos.clone())?;
            if let Some(di) = &info.dyn_array {
                let len = self.dyn_load(&di.len, "i64");
                return Ok((llvm_type(T_INT).into(), len));
            }
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

        let ret_struct = sig.ret.as_deref().map(|t| self.is_struct(t)).unwrap_or(false);
        let ret_array_len = sig.ret.as_deref().and_then(Self::array_decl_len);
        let ret_dynamic = sig.ret.as_deref().map(Self::is_dynamic_array).unwrap_or(false);
        let mut arg_ops = Vec::new();
        let sret_buf = if ret_struct {
            let rt = sig.ret.as_deref().unwrap();
            let n = self.struct_total_slots(rt);
            let buf = self.alloc_buffer(n);
            arg_ops.push(format!("ptr {buf}"));
            Some((rt.to_string(), buf))
        } else if ret_dynamic {
            let rt = sig.ret.as_deref().unwrap();
            let desc = self.desc_alloc();
            arg_ops.push(format!("ptr {desc}"));
            Some((rt.to_string(), desc))
        } else if let Some(len) = ret_array_len {
            let rt = sig.ret.as_deref().unwrap();
            let slots = self.array_elem_slots(rt)?;
            if self.is_flat_slot_array(rt) {
                let total = len * slots;
                let buf = self.tmp();
                self.ins(&format!("{buf} = alloca [{total} x i64]"));
                arg_ops.push(format!("ptr {buf}"));
                Some((rt.to_string(), buf))
            } else {
                let elem = Self::array_elem_scalar(rt, pos.clone())?;
                let elem_ll = llvm_type(&elem);
                let buf = self.tmp();
                self.ins(&format!("{buf} = alloca [{len} x {elem_ll}]"));
                arg_ops.push(format!("ptr {buf}"));
                Some((rt.to_string(), buf))
            }
        } else {
            None
        };

        let mut temp_dyn: Vec<TempDyn> = Vec::new();
        // 非变量实参（字面量/调用结果）构造出的临时槽块由调用方拥有：
        // 被调函数入口会深拷贝，调用返回后必须释放，避免泄漏。
        let mut temp_owned: Vec<(String, String)> = Vec::new();
        for (i, a) in args.iter().enumerate() {
            let pty = &sig.params[i];
            if self.is_struct(pty) {
                let n = self.struct_total_slots(pty);
                let buf = self.alloc_buffer(n);
                self.pack_expr_to_buffer(pty, a, &buf)?;
                if !matches!(a.kind, ExprKind::Var(_)) && self.type_owns_heap(pty) {
                    temp_owned.push((pty.clone(), buf.clone()));
                }
                arg_ops.push(format!("ptr {buf}"));
            } else if Self::is_dynamic_array(pty) {
                let desc = self.desc_alloc();
                match &a.kind {
                    ExprKind::Var(vname) => {
                        let info = self.lookup_var(vname, a.pos.clone())?;
                        if info.ty != *pty {
                            return Err(TenetError::at_pos(
                                format!("参数类型不匹配：需要 {pty}，实际 {}", info.ty),
                                a.pos.clone(),
                            ));
                        }
                        self.desc_store_info(&desc, &info);
                    }
                    ExprKind::Array(_) => {
                        let tmp = self.init_dynamic_array("__arg_tmp", pty, a, a.pos.clone())?;
                        self.desc_store_info(&desc, &tmp);
                        temp_dyn.push(TempDyn::Var(tmp));
                    }
                    ExprKind::Call { .. } => {
                        let (rt, rdesc) = self.gen_expr(a)?;
                        if rt != *pty {
                            return Err(TenetError::at_pos(
                                format!("参数类型不匹配：需要 {pty}，调用返回 {rt}"),
                                a.pos.clone(),
                            ));
                        }
                        self.desc_copy(&desc, &rdesc);
                        temp_dyn.push(TempDyn::Desc { desc: rdesc, ty: pty.clone() });
                    }
                    _ => {
                        return Err(TenetError::at_pos(
                            "动态数组实参只支持变量、字面量或返回动态数组的调用".to_string(),
                            a.pos.clone(),
                        ))
                    }
                }
                arg_ops.push(format!("ptr {desc}"));
            } else if self.is_array(pty) {
                let len = Self::array_decl_len(pty).ok_or_else(|| {
                    TenetError::at_pos("array 参数必须写 array<T, N>".to_string(), a.pos.clone())
                })?;
                let slots = self.array_elem_slots(pty)?;
                if self.is_flat_slot_array(pty) {
                    let total = len * slots;
                    let buf = self.tmp();
                    self.ins(&format!("{buf} = alloca [{total} x i64]"));
                    self.pack_fixed_array_expr(pty, a, &buf)?;
                    if !matches!(a.kind, ExprKind::Var(_)) && self.type_owns_heap(pty) {
                        temp_owned.push((pty.clone(), buf.clone()));
                    }
                    arg_ops.push(format!("ptr {buf}"));
                } else {
                    let elem = Self::array_elem_scalar(pty, a.pos.clone())?;
                    let elem_ll = llvm_type(&elem);
                    let buf = self.tmp();
                    self.ins(&format!("{buf} = alloca [{len} x {elem_ll}]"));
                    self.pack_array_expr_to_buffer(pty, len, a, &buf)?;
                    arg_ops.push(format!("ptr {buf}"));
                }
            } else {
                let (t, v) = self.gen_expr(a)?;
                let expect = llvm_type(pty);
                if t != expect {
                    return Err(TenetError::at_pos(
                        format!(
                            "函数 `{callee}` 参数 {i} 类型不匹配：期望 {pty}，实际 {}",
                            tenet_name(&t)
                        ),
                        a.pos.clone(),
                    ));
                }
                arg_ops.push(format!("{t} {v}"));
            }
        }

        let joined = arg_ops.join(", ");
        let result = if let Some((rt, buf)) = sret_buf {
            self.ins(&format!("call void @{callee}({joined})"));
            (rt, buf)
        } else {
            let ret_ll = sig.ret.as_deref().map(llvm_type).unwrap_or("void");
            if ret_ll == "void" {
                self.ins(&format!("call void @{callee}({joined})"));
                ("void".into(), String::new())
            } else {
                let r = self.tmp();
                self.ins(&format!("{r} = call {ret_ll} @{callee}({joined})"));
                (ret_ll.into(), r)
            }
        };
        for (ty, buf) in temp_owned {
            self.drop_value_slots(&ty, &buf);
        }
        for t in temp_dyn {
            match t {
                TempDyn::Var(v) => {
                    if let Some(di) = v.dyn_array {
                        self.dyn_drop(&di, &v.ty);
                    }
                }
                TempDyn::Desc { desc, ty } => self.drop_desc_owned(&desc, &ty),
            }
        }
        Ok(result)
    }

    /// print(a, b, ...) → 编译期按参数类型拼 printf 格式串。
    fn printf_raw(&mut self, fmt: &str, args: &[String]) {
        let addr = self.string_addr(fmt);
        let r = self.tmp();
        let mut call = format!("{r} = call i32 (ptr, ...) @printf(ptr {addr}");
        for o in args {
            call.push_str(", ");
            call.push_str(o);
        }
        call.push(')');
        self.ins(&call);
    }

    fn print_scalar_op(&mut self, ty: &str, op: &str) {
        match ty {
            "i64" => self.printf_raw("%lld", &[format!("i64 {op}")]),
            "double" => self.printf_raw("%g", &[format!("double {op}")]),
            "ptr" => self.printf_raw("%s", &[format!("ptr {op}")]),
            "i1" => {
                let sel = self.tmp();
                self.ins(&format!(
                    "{sel} = select i1 {op}, ptr @.str.true, ptr @.str.false"
                ));
                self.printf_raw("%s", &[format!("ptr {sel}")]);
            }
            _ => {}
        }
    }

    fn print_scalar_at(&mut self, ty: &str, addr: &str) {
        let ll = llvm_type(ty);
        let v = self.tmp();
        self.ins(&format!("{v} = load {ll}, ptr {addr}"));
        self.print_scalar_op(&ll, &v);
    }

    /// 打印扁平 i64 槽里的标量（bool/float 先按打包规则还原）。
    fn print_packed_scalar_at(&mut self, ty: &str, addr: &str) {
        let raw = self.tmp();
        self.ins(&format!("{raw} = load i64, ptr {addr}"));
        match ty {
            T_INT => self.print_scalar_op("i64", &raw),
            T_BOOL => {
                let v = self.tmp();
                self.ins(&format!("{v} = trunc i64 {raw} to i1"));
                self.print_scalar_op("i1", &v);
            }
            T_FLOAT => {
                let v = self.tmp();
                self.ins(&format!("{v} = bitcast i64 {raw} to double"));
                self.print_scalar_op("double", &v);
            }
            _ => {}
        }
    }

    /// 打印固定数组字段（数据是扁平 i64 槽）：`[1, 2, 3]`。
    fn print_packed_array_at(&mut self, ty: &str, base: &str) -> TResult<()> {
        let elem = self.array_elem_or_err(ty, Position::new(1, 1))?;
        let len = Self::array_decl_len(ty).ok_or_else(|| {
            TenetError::at_pos(
                "数组字段必须是固定长度 array<T, N>".to_string(),
                Position::new(1, 1),
            )
        })?;
        let slots = self.array_elem_slots(ty)?;
        self.printf_raw("[", &[]);
        for k in 0..len {
            if k > 0 {
                self.printf_raw(", ", &[]);
            }
            let a = self.flat_slot(base, k * slots);
            if self.is_struct(&elem) {
                self.print_struct_at(&elem, Some(&a), None)?;
            } else if self.is_array(&elem) {
                self.print_packed_array_at(&elem, &a)?;
            } else {
                self.print_packed_scalar_at(&elem, &a);
            }
        }
        self.printf_raw("]", &[]);
        Ok(())
    }

    /// 打印扁平槽块中某个动态数组字段（descriptor 三元组）。
    fn print_dyn_info(&mut self, ty: &str, di: &DynArrayInfo) -> TResult<()> {
        let fake = VarInfo {
            ty: ty.to_string(),
            addr: None,
            fields: HashMap::new(),
            array: None,
            dyn_array: Some(di.clone()),
        };
        self.print_array_info(&fake)
    }

    fn print_struct_at(
        &mut self,
        ty: &str,
        base: Option<&str>,
        fields: Option<&HashMap<String, VarInfo>>,
    ) -> TResult<()> {
        self.printf_raw(&format!("{ty} {{ "), &[]);
        let entries = self.layout_of(ty);
        for (i, entry) in entries.iter().enumerate() {
            if i > 0 {
                self.printf_raw(", ", &[]);
            }
            self.printf_raw(&format!("{}: ", entry.path), &[]);
            if let Some(fs) = fields {
                if let Some(f) = fs.get(&entry.path) {
                    if Self::is_dynamic_array(&entry.ty) {
                        let di = f.dyn_array.as_ref().ok_or_else(|| {
                            TenetError::at_pos(
                                format!("字段 `{}` 不是动态数组", entry.path),
                                Position::new(1, 1),
                            )
                        })?;
                        let di = di.clone();
                        self.print_dyn_info(&entry.ty, &di)?;
                        continue;
                    }
                    let a = f.addr.clone().unwrap();
                    if entry.slots > 1 {
                        self.print_packed_array_at(&entry.ty, &a)?;
                    } else {
                        self.print_scalar_at(&entry.ty, &a);
                    }
                    continue;
                }
            }
            if let Some(b) = base {
                let a = self.gep_i8(b, entry.offset * 8);
                if Self::is_dynamic_array(&entry.ty) {
                    let di = self.dyn_info_in_block(&a, 0);
                    self.print_dyn_info(&entry.ty, &di)?;
                } else if entry.slots > 1 {
                    self.print_packed_array_at(&entry.ty, &a)?;
                } else {
                    self.print_packed_scalar_at(&entry.ty, &a);
                }
            }
        }
        self.printf_raw(" }", &[]);
        Ok(())
    }

    /// 打印动态嵌套数组的一行：`[1, 2]`（内层 descriptor 已定位到槽位）。
    fn print_dynamic_nested_row(&mut self, inner_ty: &str, row: &str) -> TResult<()> {
        let elem = Self::array_elem(inner_ty).ok_or_else(|| {
            TenetError::at_pos("内层不是数组".to_string(), Position::new(1, 1))
        })?;
        let s0 = self.desc_slot(row, 0);
        let s1 = self.desc_slot(row, 1);
        let data = self.dyn_load(&s0, "ptr");
        let len = self.dyn_load(&s1, "i64");
        self.printf_raw("[", &[]);
        let i = self.tmp();
        self.ins(&format!("{i} = alloca i64"));
        self.ins(&format!("store i64 0, ptr {i}"));
        let cond = self.new_label("pnr.cond");
        let body = self.new_label("pnr.body");
        let sep = self.new_label("pnr.sep");
        let after = self.new_label("pnr.after");
        let end = self.new_label("pnr.end");
        self.term(&format!("br label %{cond}"));
        self.block(&cond);
        let iv = self.dyn_load(&i, "i64");
        let c = self.tmp();
        self.ins(&format!("{c} = icmp slt i64 {iv}, {len}"));
        self.term(&format!("br i1 {c}, label %{body}, label %{end}"));
        self.block(&body);
        let nz = self.tmp();
        self.ins(&format!("{nz} = icmp sgt i64 {iv}, 0"));
        self.term(&format!("br i1 {nz}, label %{sep}, label %{after}"));
        self.block(&sep);
        self.printf_raw(", ", &[]);
        self.term(&format!("br label %{after}"));
        self.block(&after);
        let ll = llvm_type(elem);
        let slot = self.dyn_slot(&data, &iv);
        let raw = self.tmp();
        self.ins(&format!("{raw} = load {ll}, ptr {slot}"));
        self.print_scalar_op(ll, &raw);
        let ni = self.tmp();
        self.ins(&format!("{ni} = add i64 {iv}, 1"));
        self.ins(&format!("store i64 {ni}, ptr {i}"));
        self.term(&format!("br label %{cond}"));
        self.block(&end);
        self.printf_raw("]", &[]);
        Ok(())
    }

    fn print_array_info(&mut self, info: &VarInfo) -> TResult<()> {
        let elem = self.array_elem_or_err(&info.ty, Position::new(1, 1))?;
        self.printf_raw("[", &[]);
        if let Some(di) = &info.dyn_array {
            let data = self.dyn_load(&di.data, "ptr");
            let len = self.dyn_load(&di.len, "i64");
            let i = self.tmp();
            self.ins(&format!("{i} = alloca i64"));
            self.ins(&format!("store i64 0, ptr {i}"));
            let cond = self.new_label("pr.cond");
            let body = self.new_label("pr.body");
            let sep = self.new_label("pr.sep");
            let after = self.new_label("pr.after");
            let end = self.new_label("pr.end");
            self.term(&format!("br label %{cond}"));
            self.block(&cond);
            let iv = self.dyn_load(&i, "i64");
            let c = self.tmp();
            self.ins(&format!("{c} = icmp slt i64 {iv}, {len}"));
            self.term(&format!("br i1 {c}, label %{body}, label %{end}"));
            self.block(&body);
            let nz = self.tmp();
            self.ins(&format!("{nz} = icmp sgt i64 {iv}, 0"));
            self.term(&format!("br i1 {nz}, label %{sep}, label %{after}"));
            self.block(&sep);
            self.printf_raw(", ", &[]);
            self.term(&format!("br label %{after}"));
            self.block(&after);
            let slots = self.array_elem_slots(&info.ty)?;
            let row = self.tmp();
            self.ins(&format!("{row} = mul i64 {iv}, {slots}"));
            let slot = self.dyn_slot(&data, &row);
            if self.is_struct(&elem) {
                self.print_struct_at(&elem, Some(&slot), None)?;
            } else if self.is_array(&elem) {
                if Self::is_dynamic_nested_array(&info.ty) {
                    self.print_dynamic_nested_row(&elem, &slot)?;
                } else {
                    self.printf_raw("[]", &[]);
                }
            } else {
                let ll = llvm_type(&elem);
                let raw = self.tmp();
                self.ins(&format!("{raw} = load {ll}, ptr {slot}"));
                self.print_scalar_op(&ll, &raw);
            }
            let ni = self.tmp();
            self.ins(&format!("{ni} = add i64 {iv}, 1"));
            self.ins(&format!("store i64 {ni}, ptr {i}"));
            self.term(&format!("br label %{cond}"));
            self.block(&end);
        } else {
            let len = info.array.unwrap();
            let base = info.addr.clone().unwrap();
            let slots = self.array_elem_slots(&info.ty)?;
            for k in 0..len {
                if k > 0 {
                    self.printf_raw(", ", &[]);
                }
                if self.is_struct(&elem) {
                    let a = self.tmp();
                    self.ins(&format!(
                        "{a} = getelementptr [{} x i64], ptr {base}, i64 0, i64 {}",
                        len * slots,
                        k * slots
                    ));
                    self.print_struct_at(&elem, Some(&a), None)?;
                } else if self.is_array(&elem) {
                    // 固定嵌套数组：逐元素打印
                    let inner = elem.clone();
                    let n = Self::array_decl_len(&inner).unwrap();
                    let inner_elem = Self::array_elem(&inner).unwrap();
                    self.printf_raw("[", &[]);
                    for j in 0..n {
                        if j > 0 {
                            self.printf_raw(", ", &[]);
                        }
                        let a = self.tmp();
                        self.ins(&format!(
                            "{a} = getelementptr [{} x i64], ptr {base}, i64 0, i64 {}",
                            len * slots,
                            k * slots + j
                        ));
                        self.print_scalar_at(inner_elem, &a);
                    }
                    self.printf_raw("]", &[]);
                } else {
                    let a = self.tmp();
                    self.ins(&format!(
                        "{a} = getelementptr [{} x i64], ptr {base}, i64 0, i64 {k}",
                        len
                    ));
                    self.print_scalar_at(&elem, &a);
                }
            }
        }
        self.printf_raw("]", &[]);
        Ok(())
    }

    fn gen_print(&mut self, args: &[Expr], _pos: Position) -> TResult<(String, String)> {
        for (i, a) in args.iter().enumerate() {
            if i > 0 {
                self.printf_raw(" ", &[]);
            }
            if let Some((name, path)) = Self::expr_var_path(a) {
                if !path.is_empty() {
                    let info = self.lookup_var(&name, a.pos.clone())?;
                    if let Some(f) = info.fields.get(&path) {
                        if let Some(di) = &f.dyn_array {
                            let ty = f.ty.clone();
                            let di = di.clone();
                            self.print_dyn_info(&ty, &di)?;
                            continue;
                        }
                    }
                }
            }
            if let ExprKind::Var(name) = &a.kind {
                let info = self.lookup_var(name, a.pos.clone())?;
                if self.is_struct(&info.ty) {
                    self.print_struct_at(&info.ty, None, Some(&info.fields))?;
                    continue;
                }
                if self.is_array(&info.ty) {
                    self.print_array_info(&info)?;
                    continue;
                }
            }
            let (t, v) = self.gen_expr(a)?;
            self.print_scalar_op(&t, &v);
        }
        self.printf_raw("\n", &[]);
        Ok(("void".into(), String::new()))
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
                let Some((name, mut path)) = Self::expr_var_path(base) else {
                    return Err(TenetError::at_pos(
                        "v1 只支持对 struct 变量取字段",
                        base.pos.clone(),
                    ));
                };
                if path.is_empty() {
                    path = field.clone();
                } else {
                    path = format!("{path}.{field}");
                }
                let info = self.lookup_var(&name, base.pos.clone())?;
                if !self.is_struct(&info.ty) {
                    return Err(TenetError::at_pos(
                        format!("`{name}` 不是 struct"),
                        base.pos.clone(),
                    ));
                }
                let fty = self.field_type_of(&info.ty, &path)?;
                if self.is_struct(&fty) {
                    return Err(TenetError::at_pos(
                        format!("字段 `{path}` 是 struct，请继续访问到标量字段"),
                        expr.pos.clone(),
                    ));
                }
                Some(fty)
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
                if !matches!(elem.as_str(), T_INT | T_FLOAT | T_BOOL)
                    && !self.is_struct(&elem)
                    && !self.is_array(&elem)
                {
                    return Err(TenetError::at_pos(
                        format!("数组元素只支持 int/float/bool 或 struct，实际 `{elem}`"),
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
                Some(format!("array<{elem},{}>", elems.len()))
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
                    let Some((name, mut path)) = Self::expr_var_path(base) else {
                        return Err(TenetError::at_pos(
                            "v1 只支持对 struct 变量取字段",
                            base.pos.clone(),
                        ));
                    };
                    if path.is_empty() {
                        path = field.clone();
                    } else {
                        path = format!("{path}.{field}");
                    }
                    let info = self.lookup_var(&name, base.pos.clone())?;
                    let fty = self.field_type_of(&info.ty, &path)?;
                    if self.is_struct(&fty) {
                        return Err(TenetError::at_pos(
                            format!("字段 `{path}` 是 struct，请继续访问到标量字段"),
                            target.pos.clone(),
                        ));
                    }
                    fty
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
    fn struct_param_uses_pointer_abi() {
        let ir = gen(
            "struct Point { x: int; }\nfn f(p: Point) -> int { return p.x; }",
        )
        .unwrap();
        assert!(ir.contains("define i64 @f(ptr %p0)"), "{ir}");
    }

    #[test]
    fn struct_ret_uses_sret_pointer() {
        let ir = gen(
            "struct Point { x: int; }\nfn f() -> Point { return Point { x: 1 }; }",
        )
        .unwrap();
        assert!(ir.contains("define void @f(ptr %sret)"), "{ir}");
    }

    #[test]
    fn nested_struct_literal_and_field_path() {
        let ir = gen(
            "struct Point { x: int; y: int; }\n\
             struct Line { a: Point; b: Point; }\n\
             let l: Line = Line { a: Point { x: 1, y: 2 }, b: Point { x: 3, y: 4 } };\n\
             print(l.a.x, l.b.y);",
        )
        .unwrap();
        assert!(ir.contains("alloca i64"), "{ir}");
    }

    #[test]
    fn nested_struct_param_return() {
        let ir = gen(
            "struct Point { x: int; }\n\
             struct Line { a: Point; b: Point; }\n\
             fn mid(l: Line) -> Point { return Point { x: l.a.x }; }\n\
             let l: Line = Line { a: Point { x: 1 }, b: Point { x: 2 } };\n\
             let m: Point = mid(l);\n\
             print(m.x);",
        )
        .unwrap();
        assert!(ir.contains("define void @mid(ptr %sret, ptr %p0)"), "{ir}");
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
    fn struct_print_supported() {
        let ir = gen(
            "struct Point { x: int; }\nlet p: Point = Point { x: 1 };\nprint(p);",
        )
        .unwrap();
        assert!(ir.contains("Point { "), "{ir}");
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
            "let a: array<int, 3> = [1, 2, 3];\n\
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
        let ir = gen("let f: array<float, 2> = [1.5, 2.5];\nprint(f[0], f[1]);").unwrap();
        assert!(ir.contains("alloca [2 x double]"), "{ir}");
        let ir = gen("let b: array<bool, 2> = [true, false];\nprint(b[0], b[1]);").unwrap();
        assert!(ir.contains("alloca [2 x i1]"), "{ir}");
    }

    #[test]
    fn array_constant_index_out_of_bounds_errors() {
        let (msg, _) = err_pos("let a = [1, 2];\nprint(a[2]);");
        assert!(msg.contains("越界"), "{msg}");
    }

    #[test]
    fn array_element_type_mismatch_errors() {
        let (msg, _) = err_pos("let a: array<int, 2> = [1, 2.0];");
        assert!(msg.contains("类型不匹配"), "{msg}");
    }

    #[test]
    fn dynamic_array_param_uses_descriptor() {
        let ir = gen("fn f(a: array<int>) -> int { return len(a); }").unwrap();
        assert!(ir.contains("define i64 @f(ptr %p0)"), "{ir}");
    }

    #[test]
    fn dynamic_array_ret_uses_sret() {
        let ir = gen("fn f(a: array<int>) -> array<int> { return a; }").unwrap();
        assert!(ir.contains("define void @f(ptr %sret, ptr %p0)"), "{ir}");
    }

    #[test]
    fn dynamic_array_return_literal() {
        let ir = gen("fn f() -> array<int> { return [1]; }").unwrap();
        assert!(ir.contains("define void @f(ptr %sret)"), "{ir}");
    }

    #[test]
    fn dynamic_array_param_literal_and_call() {
        let ir = gen(
            "fn id(a: array<int>) -> array<int> { return a; }\nfn m() -> array<int> { return [1]; }\nlet a: array<int> = id([1, 2]);\nlet b: array<int> = id(m());",
        )
        .unwrap();
        assert!(ir.matches("call void @id").count() >= 2, "{ir}");
        assert!(ir.contains("call void @free"), "{ir}");
    }

    #[test]
    fn dynamic_array_return_call() {
        let ir = gen(
            "fn m() -> array<int> { return [1]; }\nfn c() -> array<int> { return m(); }\nlet a: array<int> = c();",
        )
        .unwrap();
        assert!(ir.contains("call void @c"), "{ir}");
    }

    #[test]
    fn dynamic_array_param_and_return_ir() {
        let ir = gen(
            "fn clone(a: array<int>) -> array<int> { return a; }\nlet a: array<int> = [1];\nlet b: array<int> = clone(a);\nprint(len(b));",
        )
        .unwrap();
        assert!(ir.contains("call void @clone"), "{ir}");
        assert!(ir.contains("call ptr @malloc"), "{ir}");
        assert!(ir.contains("call void @free"), "{ir}");
    }

    #[test]
    fn array_param_uses_pointer_abi() {
        let ir = gen("fn sum(a: array<int, 3>) -> int { return a[0]; }").unwrap();
        assert!(ir.contains("define i64 @sum(ptr %p0)"), "{ir}");
    }

    #[test]
    fn array_ret_uses_sret_pointer() {
        let ir = gen("fn make() -> array<int, 3> { return [1, 2, 3]; }").unwrap();
        assert!(ir.contains("define void @make(ptr %sret)"), "{ir}");
    }

    #[test]
    fn array_param_length_mismatch_errors() {
        let (msg, _) = err_pos(
            "fn sum(a: array<int, 3>) -> int { return a[0]; }\nlet b: array<int, 2> = [1, 2];\nprint(sum(b));",
        );
        assert!(msg.contains("长度不匹配") || msg.contains("类型不匹配"), "{msg}");
    }

    #[test]
    fn empty_array_is_rejected() {
        let (msg, _) = err_pos("let a: array<int, 1> = [];");
        assert!(msg.contains("空数组"), "{msg}");
    }

    #[test]
    fn array_direct_print_supported() {
        let ir = gen("let a = [1, 2];\nprint(a);").unwrap();
        assert!(ir.contains("@printf"), "{ir}");
    }


    #[test]
    fn nested_struct_field_write() {
        let ir = gen(
            "struct Point { x: int; }\n\
             struct Line { a: Point; b: Point; }\n\
             let l: Line = Line { a: Point { x: 1 }, b: Point { x: 2 } };\n\
             l.a.x = 9;\n\
             print(l.a.x);",
        )
        .unwrap();
        assert!(ir.contains("store i64"), "{ir}");
    }

    #[test]
    fn nested_struct_return() {
        let ir = gen(
            "struct Point { x: int; }\n\
             struct Line { a: Point; b: Point; }\n\
             fn make() -> Line { return Line { a: Point { x: 1 }, b: Point { x: 2 } }; }\n\
             let l = make();\n\
             print(l.b.x);",
        )
        .unwrap();
        assert!(ir.contains("define void @make(ptr %sret)"), "{ir}");
    }

    #[test]
    fn struct_cycle_is_rejected() {
        let (msg, _) = err_pos("struct A { b: B; }\nstruct B { a: A; }");
        assert!(msg.contains("循环嵌套"), "{msg}");
    }

    #[test]
    fn struct_dynamic_array_field_layout() {
        // S 的布局：a 占 3 个 descriptor 槽 + x 1 槽 = 4 槽。
        let ir = gen(
            "struct S { a: array<int>; x: int; }\n\
             let s: S = S { a: [1, 2], x: 9 };\n\
             print(len(s.a), s.a[0], s.x);\n\
             print(s);",
        )
        .unwrap();
        assert!(ir.contains("alloca [4 x i64]"), "{ir}");
        assert!(ir.contains("call ptr @malloc"), "{ir}");
        assert!(ir.contains("S { "), "{ir}");
        assert!(ir.contains("pr.cond"), "print(struct) 应展开动态字段: {ir}");
    }


    #[test]
    fn dynamic_array_literal_and_push() {
        let ir = gen(
            "let a: array<int> = [1, 2];\npush(a, 3);\nprint(len(a), a[2]);",
        )
        .unwrap();
        assert!(ir.contains("call ptr @malloc"), "{ir}");
        assert!(ir.contains("call void @free"), "{ir}");
    }

    #[test]
    fn dynamic_array_empty_and_push() {
        let ir = gen("let a: array<int> = [];\npush(a, 7);\nprint(len(a), a[0]);").unwrap();
        assert!(ir.contains("call ptr @malloc"), "{ir}");
    }

    #[test]
    fn dynamic_array_deep_copy() {
        let ir = gen(
            "let a: array<int> = [1, 2];\nlet b = a;\npush(b, 3);\na[0] = 9;\nprint(b[0]);",
        )
        .unwrap();
        assert!(ir.matches("call ptr @malloc").count() >= 2, "{ir}");
    }

    #[test]
    fn dynamic_array_assignment_drops_old() {
        let ir = gen(
            "let a: array<int> = [1, 2];\nlet b: array<int> = [3];\nb = a;\nprint(b[0]);",
        )
        .unwrap();
        assert!(ir.contains("call void @free"), "{ir}");
    }

    #[test]
    fn dynamic_array_scope_drop() {
        let ir = gen(
            "let i: int = 0;\nwhile (i < 2) { let a: array<int> = [1]; push(a, 2); i = i + 1; }",
        )
        .unwrap();
        assert!(ir.contains("call void @free"), "{ir}");
    }


    #[test]
    fn dynamic_array_break_drops_body() {
        let ir = gen(
            "let i: int = 0;\nwhile (i < 1) { let a: array<int> = [1]; push(a, 2); break; }\nprint(1);",
        )
        .unwrap();
        assert!(ir.contains("call void @free"), "{ir}");
    }


    #[test]
    fn fixed_struct_array_literal_field_assign() {
        let ir = gen(
            "struct P { x: int; y: int; }\nlet a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\na[0].x = 9;\na[1] = P { x: 7, y: 8 };\nprint(a[0].x);",
        )
        .unwrap();
        assert!(ir.contains("alloca [4 x i64]"), "{ir}");
    }

    #[test]
    fn nested_struct_array_field_path() {
        let ir = gen(
            "struct P { x: int; y: int; }\nstruct Q { p: P; z: int; }\nlet q: array<Q, 2> = [Q { p: P { x: 1, y: 2 }, z: 3 }, Q { p: P { x: 4, y: 5 }, z: 6 }];\nq[0].p.x = 9;\nprint(q[0].p.x);",
        )
        .unwrap();
        assert!(ir.contains("alloca [6 x i64]"), "{ir}");
    }

    #[test]
    fn dynamic_struct_array_literal_push_field() {
        let ir = gen(
            "struct P { x: int; y: int; }\nlet a: array<P> = [P { x: 1, y: 2 }];\npush(a, P { x: 3, y: 4 });\na[0].x = 9;\nprint(a[1].y);",
        )
        .unwrap();
        assert!(ir.contains("call ptr @malloc"), "{ir}");
    }

    #[test]
    fn dynamic_struct_array_param_ret() {
        let ir = gen(
            "struct P { x: int; }\nfn clone(a: array<P>) -> array<P> { return a; }\nlet a: array<P> = [P { x: 1 }];\nlet b: array<P> = clone(a);",
        )
        .unwrap();
        assert!(ir.contains("define void @clone(ptr %sret, ptr %p0)"), "{ir}");
    }

    #[test]
    fn dynamic_struct_array_return_literal() {
        let ir = gen(
            "struct P { x: int; }\nfn m() -> array<P> { return [P { x: 1 }]; }",
        )
        .unwrap();
        assert!(ir.contains("define void @m(ptr %sret)"), "{ir}");
    }


    #[test]
    fn fixed_nested_array_read_write() {
        let ir = gen(
            "let a: array<array<int, 2>, 3> = [[1, 2], [3, 4], [5, 6]];\na[0][1] = 9;\na[2][0] = 7;\nprint(a[0][1], a[2][0]);",
        )
        .unwrap();
        assert!(ir.contains("alloca [6 x i64]"), "{ir}");
    }

    #[test]
    fn nested_array_bool_inner_is_rejected() {
        let (msg, _) = err_pos("let a: array<array<bool, 2>, 2> = [[true, false], [false, true]];");
        assert!(msg.contains("bool"), "{msg}");
    }


    #[test]
    fn fixed_struct_array_param_ret() {
        let ir = gen(
            "struct P { x: int; y: int; }\nfn id(a: array<P, 2>) -> array<P, 2> { return a; }\nlet a: array<P, 2> = [P { x: 1, y: 2 }, P { x: 3, y: 4 }];\nlet b: array<P, 2> = id(a);",
        )
        .unwrap();
        assert!(ir.contains("define void @id(ptr %sret, ptr %p0)"), "{ir}");
    }

    #[test]
    fn fixed_nested_array_param_ret() {
        let ir = gen(
            "fn id(a: array<array<int, 2>, 2>) -> array<array<int, 2>, 2> { return a; }\nlet n: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\nlet m: array<array<int, 2>, 2> = id(n);",
        )
        .unwrap();
        assert!(ir.contains("define void @id(ptr %sret, ptr %p0)"), "{ir}");
    }


    #[test]
    fn fixed_array_whole_assignment_call() {
        let ir = gen(
            "struct P { x: int; }\nfn f() -> array<P, 1> { return [P { x: 7 }]; }\nlet b: array<P, 1> = [P { x: 0 }];\nb = f();\nprint(b[0].x);",
        )
        .unwrap();
        assert!(ir.contains("call void @f"), "{ir}");
    }

    #[test]
    fn single_field_struct_array_param_ret() {
        let ir = gen(
            "struct P { x: int; }\nfn id(a: array<P, 1>) -> array<P, 1> { return a; }\nlet a: array<P, 1> = [P { x: 1 }];\nlet b: array<P, 1> = id(a);",
        )
        .unwrap();
        assert!(ir.contains("define void @id(ptr %sret, ptr %p0)"), "{ir}");
    }


    #[test]
    fn print_struct_and_fixed_array() {
        let ir = gen(
            "struct P { x: int; y: int; }\nlet p: P = P { x: 1, y: 2 };\nlet a: array<P, 2> = [P { x: 3, y: 4 }, P { x: 5, y: 6 }];\nprint(p);\nprint(a);",
        )
        .unwrap();
        assert!(ir.contains("P { "), "{ir}");
        assert!(ir.contains("%lld"), "{ir}");
    }

    #[test]
    fn print_dynamic_array_and_nested() {
        let ir = gen(
            "let d: array<int> = [7, 8];\nprint(d);\nlet n: array<array<int, 2>, 2> = [[1, 2], [3, 4]];\nprint(n);",
        )
        .unwrap();
        assert!(ir.contains("pr.cond"), "{ir}");
    }

    // ---- 动态嵌套数组 array<array<T>> v1 ----

    #[test]
    fn dynamic_nested_array_literal_layout() {
        let ir = gen("let a: array<array<int>> = [[1, 2], [3]];").unwrap();
        // 外层 cap = max(2, 4) = 4 → 4 * 3 * 8 = 96 字节；两行内层各 malloc 32 字节。
        assert!(ir.contains("call ptr @malloc(i64 96)"), "{ir}");
        assert_eq!(ir.matches("call ptr @malloc").count(), 3, "{ir}");
        // 外层元素按 [data,len,cap] 三个 i64 槽访问。
        assert!(ir.contains("getelementptr [3 x i64]"), "{ir}");
    }

    #[test]
    fn dynamic_nested_array_user_program_compiles() {
        let ir = gen(
            "let a: array<array<int>> = [[1, 2], [3]];\n\
             push(a, [4, 5]);\n\
             let b: array<array<int>> = a;\n\
             a[0][0] = 9;\n\
             print(len(a), a[0][0], a[1][0], b[0][0]);\n\
             fn clone(x: array<array<int>>) -> array<array<int>> { return x; }\n\
             let c: array<array<int>> = clone(b);\n\
             print(len(c), c[0][1]);",
        )
        .unwrap();
        assert!(ir.contains("define void @clone(ptr %sret, ptr %p0)"), "{ir}");
        assert!(ir.contains("call void @clone"), "{ir}");
        assert!(ir.contains("nested.copy.cond"), "{ir}");
        assert!(ir.contains("dyn.grow"), "{ir}");
        assert!(ir.contains("dyn.drop.cond"), "{ir}");
        assert!(
            ir.matches("call void @tenet_bounds_fail").count() >= 2,
            "{ir}"
        );
    }

    #[test]
    fn dynamic_nested_array_deep_copy_let_and_assign() {
        let ir = gen(
            "let a: array<array<int>> = [[1], [2]];\n\
             let b: array<array<int>> = a;\n\
             b = a;\n\
             a[0][0] = 9;\n\
             print(b[0][0]);",
        )
        .unwrap();
        // let 深拷贝 + 赋值右侧深拷贝。
        assert!(ir.matches("nested.copy.cond").count() >= 2, "{ir}");
        // 赋值前先 drop 旧 b（逐内层 free）。
        assert!(ir.contains("dyn.drop.cond"), "{ir}");
        assert!(ir.contains("dyn.drop.inner.free"), "{ir}");
    }

    #[test]
    fn dynamic_nested_array_push_literal_and_var() {
        let ir = gen(
            "let a: array<array<int>> = [];\n\
             let r: array<int> = [7];\n\
             push(a, [1, 2]);\n\
             push(a, r);\n\
             r[0] = 9;\n\
             print(a[1][0]);",
        )
        .unwrap();
        assert!(ir.contains("dyn.grow"), "{ir}");
        assert!(ir.contains("dyn.copy"), "{ir}");
        assert!(ir.matches("call ptr @malloc").count() >= 3, "{ir}");
    }

    #[test]
    fn dynamic_nested_array_float_bool_and_print() {
        let ir = gen(
            "let f: array<array<float>> = [[1.5], [2.5]];\n\
             print(f);\n\
             let b: array<array<bool>> = [[true], [false]];\n\
             print(b);",
        )
        .unwrap();
        assert!(ir.contains("%g"), "{ir}");
        assert!(ir.contains("select i1"), "{ir}");
        // 嵌套 print 的内层循环标签。
        assert!(ir.contains("pnr.cond"), "{ir}");
    }

    #[test]
    fn dynamic_nested_array_param_ret_entry_copy() {
        let ir = gen(
            "fn clone(x: array<array<int>>) -> array<array<int>> { return x; }\n\
             let a: array<array<int>> = [[1]];\n\
             let b: array<array<int>> = clone(a);\n\
             let c: array<array<int>> = clone([[2]]);\n\
             print(len(b), len(c));",
        )
        .unwrap();
        assert!(ir.contains("define void @clone(ptr %sret, ptr %p0)"), "{ir}");
        assert_eq!(ir.matches("call void @clone").count(), 2, "{ir}");
        // 参数入口逐内层深拷贝。
        assert!(ir.contains("nested.copy.cond"), "{ir}");
    }

    #[test]
    fn dynamic_nested_array_len_inner() {
        let ir = gen("let a: array<array<int>> = [[1]];\nprint(len(a[0]));").unwrap();
        // len(a[i]) 只做外层一次边界检查，然后读内层 descriptor 的 len 槽。
        assert_eq!(
            ir.matches("call void @tenet_bounds_fail").count(),
            1,
            "{ir}"
        );
        assert!(ir.contains("getelementptr [3 x i64]"), "{ir}");
    }

    #[test]
    fn dynamic_nested_array_double_bounds_check() {
        let ir = gen("let a: array<array<int>> = [[1]];\nprint(a[0][0]);").unwrap();
        assert_eq!(
            ir.matches("call void @tenet_bounds_fail").count(),
            2,
            "{ir}"
        );
    }

    #[test]
    fn dynamic_nested_array_empty_literal_and_push() {
        let ir = gen(
            "let a: array<array<int>> = [];\npush(a, []);\nprint(len(a), len(a[0]));",
        )
        .unwrap();
        assert!(ir.contains("call ptr @malloc(i64 96)"), "{ir}");
        assert!(ir.contains("call ptr @malloc(i64 32)"), "{ir}");
    }

    #[test]
    fn dynamic_nested_array_scope_drop_frees_inner_then_outer() {
        let ir = gen(
            "let i: int = 0;\n\
             while (i < 1) {\n\
               let a: array<array<int>> = [[1], [2]];\n\
               i = i + 1;\n\
             }",
        )
        .unwrap();
        // 内层循环里 free(data)，循环结束后 free 外层；共两条 free 指令。
        assert!(ir.contains("dyn.drop.inner.free"), "{ir}");
        assert!(ir.contains("dyn.drop.rows"), "{ir}");
        assert!(ir.matches("call void @free").count() >= 2, "{ir}");
    }

    #[test]
    fn dynamic_nested_array_struct_inner_is_rejected() {
        let (msg, _) = err_pos(
            "struct P { x: int; }\nlet a: array<array<P>> = [[P { x: 1 }]];",
        );
        assert!(msg.contains("array<struct>"), "{msg}");
    }

    #[test]
    fn dynamic_nested_array_deeper_is_rejected() {
        let (msg, _) = err_pos("let a: array<array<array<int>>> = [[[1]]];");
        assert!(msg.contains("只支持一层"), "{msg}");
    }

    #[test]
    fn dynamic_nested_array_fixed_inner_is_rejected() {
        let (msg, _) = err_pos("let a: array<array<int, 2>> = [[1, 2]];");
        assert!(msg.contains("内层必须是动态数组"), "{msg}");
    }

    #[test]
    fn dynamic_nested_array_whole_row_is_rejected() {
        let (msg, _) = err_pos("let a: array<array<int>> = [[1]];\nprint(a[0]);");
        assert!(msg.contains("整体读取"), "{msg}");
        let (msg, _) = err_pos("let a: array<array<int>> = [[1]];\na[0] = [2];");
        assert!(msg.contains("整体赋值"), "{msg}");
    }

    #[test]
    fn dynamic_nested_array_type_mismatch_errors() {
        let (msg, _) = err_pos("let a: array<array<int>> = [[1], 2];");
        assert!(msg.contains("嵌套数组第"), "{msg}");
        let (msg, _) = err_pos("let a: array<array<int>> = [[1], [2.5]];");
        assert!(msg.contains("类型不匹配"), "{msg}");
        let (msg, _) = err_pos("let a: array<array<int>> = [[1]];\npush(a, [1.5]);");
        assert!(msg.contains("类型不匹配"), "{msg}");
        let (msg, _) = err_pos(
            "fn f(x: array<array<int>>) -> int { return len(x); }\nlet a: array<array<float>> = [[1.0]];\nprint(f(a));",
        );
        assert!(msg.contains("参数类型不匹配"), "{msg}");
    }


    #[test]
    fn struct_fixed_array_field_literal_copy_param() {
        let ir = gen(
            "struct S { a: array<int, 3>; x: int; }\nlet s: S = S { a: [1, 2, 3], x: 9 };\ns.a[1] = 7;\nlet t: S = s;\nt.a[0] = 5;\nfn f(v: S) -> S { v.a[2] = 8; return v; }\nlet u: S = f(s);\nprint(s.a[1], t.a[0], u.a[2]);",
        )
        .unwrap();
        assert!(ir.contains("define void @f(ptr %sret, ptr %p0)"), "{ir}");
    }

    #[test]
    fn struct_array_field_of_struct() {
        let ir = gen(
            "struct P { x: int; }\nstruct S { a: array<P, 2>; }\nlet s: S = S { a: [P { x: 1 }, P { x: 2 }] };\ns.a[0].x = 9;\nprint(s.a[0].x, s.a[1].x);\nprint(s);",
        )
        .unwrap();
        assert!(ir.contains("P { "), "{ir}");
    }

    #[test]
    fn struct_dynamic_array_field_unsupported_shapes_rejected() {
        let (msg, _) = err_pos("struct P { x: int; }\nstruct S { a: array<P>; }");
        assert!(msg.contains("array<struct>"), "{msg}");
        let (msg, _) = err_pos("struct S { a: array<array<int>>; }");
        assert!(msg.contains("嵌套"), "{msg}");
        let (msg, _) = err_pos("struct S { a: array<string>; }");
        assert!(msg.contains("string"), "{msg}");
    }

    // ---- struct 的动态数组字段 v1 ----

    #[test]
    fn struct_dynamic_field_index_push_len() {
        let ir = gen(
            "struct S { a: array<int>; x: int; }\n\
             let s: S = S { a: [1, 2], x: 9 };\n\
             s.a[0] = 7;\n\
             push(s.a, 3);\n\
             let t: S = s;\n\
             t.a[0] = 5;\n\
             print(len(s.a), s.a[0], t.a[0], s.x);",
        )
        .unwrap();
        // 动态下标有边界检查；push 有容量判断；深拷贝有独立 malloc。
        assert!(ir.contains("dbounds.fail"), "{ir}");
        assert!(ir.contains("icmp eq i64"), "{ir}");
        assert!(ir.contains("deep.copy.cond"), "{ir}");
        assert!(ir.matches("call ptr @malloc").count() >= 2, "{ir}");
    }

    #[test]
    fn struct_dynamic_field_whole_field_assign() {
        let ir = gen(
            "struct S { a: array<int>; x: int; }\n\
             let s: S = S { a: [1, 2], x: 9 };\n\
             let t: S = S { a: [3], x: 4 };\n\
             s.a = [5, 6];\n\
             t.a = s.a;\n\
             print(s.a[1], t.a[0], len(t.a));",
        )
        .unwrap();
        // 整体字段赋值：右侧深拷贝 + 先 drop 旧 descriptor。
        assert!(ir.contains("deep.copy.cond"), "{ir}");
        assert!(ir.contains("call void @free"), "{ir}");
        assert!(ir.matches("call ptr @malloc").count() >= 4, "{ir}");
    }

    #[test]
    fn struct_dynamic_field_param_ret_entry_copy_and_transfer() {
        let ir = gen(
            "struct S { a: array<int>; x: int; }\n\
             fn f(v: S) -> S { v.a[0] = 8; return v; }\n\
             let s: S = S { a: [1, 2], x: 9 };\n\
             let u: S = f(s);\n\
             print(u.a[0], s.a[0]);",
        )
        .unwrap();
        assert!(ir.contains("define void @f(ptr %sret, ptr %p0)"), "{ir}");
        assert!(ir.contains("call void @f"), "{ir}");
        // 参数入口深拷贝 + 返回前转移后清空本地 descriptor。
        assert!(ir.contains("deep.copy.cond"), "{ir}");
        assert!(ir.contains("store ptr null"), "{ir}");
    }

    #[test]
    fn struct_dynamic_field_scope_and_break_drop() {
        let ir = gen(
            "struct S { a: array<int>; x: int; }\n\
             let i: int = 0;\n\
             while (i < 1) {\n\
               let w: S = S { a: [1, 2], x: 1 };\n\
               push(w.a, 3);\n\
               print(w.a[0]);\n\
               break;\n\
             }\n\
             print(0);",
        )
        .unwrap();
        // break 前递归 drop 函数作用域里的 struct 动态字段。
        assert!(ir.contains("dyn.free"), "{ir}");
        assert!(ir.contains("call void @free"), "{ir}");
    }

    #[test]
    fn fixed_array_and_struct_field_with_dynamic_leaf() {
        let ir = gen(
            "struct P { a: array<int>; }\n\
             struct Q { ps: array<P, 2>; z: int; }\n\
             let q: Q = Q { ps: [P { a: [1] }, P { a: [2] }], z: 5 };\n\
             let q2: Q = q;\n\
             q2.ps[0].a[0] = 9;\n\
             print(q.ps[0].a[0], q2.ps[0].a[0], q.z);\n\
             q.ps = [P { a: [7] }, P { a: [8] }];\n\
             print(q.ps[0].a[0], q.ps[1].a[0]);",
        )
        .unwrap();
        // Q 的总槽数 = 2 * 3 + 1 = 7；固定数组字段本身占 6 个扁平槽。
        assert!(ir.contains("alloca [7 x i64]"), "{ir}");
        assert!(ir.contains("alloca [6 x i64]"), "{ir}");
        assert!(ir.contains("deep.copy.cond"), "{ir}");
    }

    #[test]
    fn dynamic_array_of_struct_with_dynamic_field() {
        let ir = gen(
            "struct P { a: array<int>; }\n\
             fn clone(x: array<P>) -> array<P> { return x; }\n\
             let d: array<P> = [P { a: [1] }, P { a: [2] }];\n\
             let d2: array<P> = d;\n\
             push(d, P { a: [3] });\n\
             d[0].a = [4, 5];\n\
             print(len(d), d[0].a[0], d2[0].a[0], d2[1].a[0]);\n\
             let d3: array<P> = clone(d);\n\
             print(d3[2].a[0]);",
        )
        .unwrap();
        assert!(ir.contains("define void @clone(ptr %sret, ptr %p0)"), "{ir}");
        // array<struct> 元素里的动态字段：拷贝、参数入口、drop 都递归。
        assert!(ir.contains("deep.copy.cond"), "{ir}");
        assert!(ir.contains("arr.param.copy.cond"), "{ir}");
        assert!(ir.contains("dyn.drop.elem"), "{ir}");
    }

    #[test]
    fn fixed_array_of_struct_dynamic_field_param_ret() {
        let ir = gen(
            "struct S { a: array<int>; x: int; }\n\
             fn id(a: array<S, 1>) -> array<S, 1> { return a; }\n\
             let a: array<S, 1> = [S { a: [1, 2], x: 3 }];\n\
             let b: array<S, 1> = id(a);\n\
             print(b[0].a[0], b[0].x);",
        )
        .unwrap();
        assert!(ir.contains("define void @id(ptr %sret, ptr %p0)"), "{ir}");
        assert!(ir.contains("deep.copy.cond"), "{ir}");
    }

    #[test]
    fn struct_dynamic_field_return_literal_and_call() {
        let ir = gen(
            "struct S { a: array<int>; x: int; }\n\
             fn make() -> S { return S { a: [1, 2], x: 3 }; }\n\
             fn chain() -> S { return make(); }\n\
             let m: S = chain();\n\
             print(m.a[0], m.a[1], m.x);",
        )
        .unwrap();
        assert!(ir.contains("define void @make(ptr %sret)"), "{ir}");
        assert!(ir.contains("define void @chain(ptr %sret)"), "{ir}");
        assert!(ir.contains("call void @make"), "{ir}");
    }

    #[test]
    fn struct_dynamic_float_bool_print() {
        let ir = gen(
            "struct F { a: array<float>; }\n\
             struct B { a: array<bool>; }\n\
             let f: F = F { a: [1.5, 2.5] };\n\
             let b: B = B { a: [true, false] };\n\
             print(f);\n\
             print(b);\n\
             print(f.a[0], b.a[1]);",
        )
        .unwrap();
        assert!(ir.contains("%g"), "{ir}");
        assert!(ir.contains("select i1"), "{ir}");
        assert!(ir.contains("F { "), "{ir}");
        assert!(ir.contains("B { "), "{ir}");
    }

    #[test]
    fn struct_dynamic_field_array_element_chains() {
        let ir = gen(
            "struct S { a: array<int>; x: int; }\n\
             let arr: array<S, 2> = [S { a: [1], x: 1 }, S { a: [2], x: 2 }];\n\
             arr[0].a[0] = 7;\n\
             arr[1].a = [8, 9];\n\
             print(arr[0].a[0], arr[1].a[1], len(arr[1].a));\n\
             let d: array<S> = [S { a: [3], x: 3 }];\n\
             d[0].a[0] = 4;\n\
             print(d[0].a[0], len(d[0].a));",
        )
        .unwrap();
        assert!(ir.contains("dbounds.fail"), "{ir}");
        // 数组元素的动态字段整体赋值：构造新数组后 drop 旧值。
        assert!(ir.contains("call void @free"), "{ir}");
        assert!(ir.contains("dyn.free"), "{ir}");
    }

    #[test]
    fn struct_dynamic_field_type_errors() {
        let (msg, _) = err_pos(
            "struct S { a: array<int>; }\nlet s: S = S { a: [1] };\ns.a = [1.5];",
        );
        assert!(msg.contains("类型不匹配"), "{msg}");
        let (msg, _) = err_pos(
            "struct S { a: array<int>; }\nstruct T { a: array<float>; }\n\
             let s: S = S { a: [1] };\nlet t: T = T { a: [1.5] };\ns.a = t.a;",
        );
        assert!(msg.contains("需要 array<int>") || msg.contains("类型不匹配"), "{msg}");
    }

    #[test]
    fn struct_dynamic_field_self_assign_is_noop() {
        let ir = gen(
            "struct S { a: array<int>; }\n\
             let s: S = S { a: [1, 2] };\n\
             s = s;\n\
             s.a = s.a;\n\
             print(len(s.a), s.a[0]);",
        )
        .unwrap();
        // 自赋值不应生成复制/释放路径；仅字面量初始化的一次 malloc。
        assert_eq!(ir.matches("call ptr @malloc").count(), 1, "{ir}");
        assert!(!ir.contains("__assign_tmp"), "{ir}");
    }

    // ---- 运行期语义测试（clang 可用时执行；带 malloc/free 追踪器检查泄漏/双重释放）----

    /// 带 malloc/free 追踪的运行时：程序正常退出时若仍有未释放块则退出码 3，
    /// 重复 free 则退出码 2。用于替代 ASan（Apple clang 的 ASan 在本机沙箱中不可用）。
    const TRACK_RUNTIME_C: &str = r#"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>

#define ARENA_SIZE (128UL * 1024 * 1024)
static unsigned char arena[ARENA_SIZE];
static size_t arena_off = 0;
static long long live_blocks = 0, live_bytes = 0;
typedef struct { size_t size; int freed; } Hdr;

static void report(void) {
    if (live_blocks != 0) {
        fprintf(stderr, "[tracker] LEAK: %lld blocks, %lld bytes\n", live_blocks, live_bytes);
        _exit(3);
    }
}

void* malloc(size_t n) {
    if (n == 0) n = 1;
    n = (n + 15) & ~((size_t)15);
    if (arena_off + sizeof(Hdr) + n > ARENA_SIZE) { fprintf(stderr, "[tracker] OOM\n"); _exit(4); }
    Hdr* h = (Hdr*)(arena + arena_off);
    arena_off += sizeof(Hdr) + n;
    h->size = n;
    h->freed = 0;
    live_blocks++; live_bytes += (long long)n;
    return (void*)(h + 1);
}

void free(void* p) {
    if (!p) return;
    Hdr* h = ((Hdr*)p) - 1;
    if (h->freed) { fprintf(stderr, "[tracker] DOUBLE FREE\n"); fflush(stderr); _exit(2); }
    h->freed = 1;
    live_blocks--; live_bytes -= (long long)h->size;
}

char* tenet_concat(const char* a, const char* b) {
    size_t la = strlen(a), lb = strlen(b);
    char* r = malloc(la + lb + 1);
    memcpy(r, a, la);
    memcpy(r + la, b, lb + 1);
    return r;
}

int tenet_strcmp(const char* a, const char* b) { return strcmp(a, b); }

void tenet_bounds_fail(long long idx, long long len) {
    fprintf(stderr, "Tenet runtime error: array index %lld out of bounds for length %lld\n", idx, len);
    exit(1);
}

__attribute__((constructor)) static void init_tracker(void) { atexit(report); }
"#;

    /// 编译并运行 Tenet 程序；clang 不可用时返回 None（跳过运行期测试）。
    fn run_program(src: &str) -> Option<String> {
        use std::process::Command;
        use std::sync::atomic::{AtomicUsize, Ordering};
        static SEQ: AtomicUsize = AtomicUsize::new(0);
        let clang = std::env::var("TENET_CLANG").unwrap_or_else(|_| "clang".to_string());
        if Command::new(&clang).arg("--version").output().is_err() {
            return None;
        }
        let ir = gen(src).expect("编译失败");
        let dir = std::env::temp_dir();
        let tag = format!(
            "tenet-sem-{}-{}",
            std::process::id(),
            SEQ.fetch_add(1, Ordering::SeqCst)
        );
        let ir_path = dir.join(format!("{tag}.ll"));
        let rt_path = dir.join(format!("{tag}-runtime.c"));
        let bin_path = dir.join(format!("{tag}.bin"));
        std::fs::write(&ir_path, ir).unwrap();
        std::fs::write(&rt_path, TRACK_RUNTIME_C).unwrap();
        let out = Command::new(&clang)
            .arg(&ir_path)
            .arg(&rt_path)
            .arg("-o")
            .arg(&bin_path)
            .output()
            .expect("无法执行 clang");
        if !out.status.success() {
            panic!(
                "clang 链接失败:\n{}",
                String::from_utf8_lossy(&out.stderr)
            );
        }
        let run = Command::new(&bin_path).output().expect("运行失败");
        let _ = std::fs::remove_file(&ir_path);
        let _ = std::fs::remove_file(&rt_path);
        let _ = std::fs::remove_file(&bin_path);
        let stderr = String::from_utf8_lossy(&run.stderr).to_string();
        assert!(
            run.status.success(),
            "程序退出失败: {:?}\nstdout:\n{}\nstderr:\n{}",
            run.status,
            String::from_utf8_lossy(&run.stdout),
            stderr
        );
        assert!(
            !stderr.contains("DOUBLE FREE") && !stderr.contains("LEAK"),
            "内存错误: {stderr}"
        );
        assert!(
            stderr.contains("[tracker]") || stderr.is_empty(),
            "追踪器未生效: {stderr}"
        );
        Some(String::from_utf8_lossy(&run.stdout).to_string())
    }

    fn assert_runtime(src: &str, expected: &str) {
        if let Some(out) = run_program(src) {
            assert_eq!(out, expected);
        }
    }

    #[test]
    fn struct_dynamic_field_runtime_deep_copy_and_push() {
        assert_runtime(
            "struct S { a: array<int>; x: int; }\n\
             let s: S = S { a: [1, 2], x: 9 };\n\
             s.a[0] = 7;\n\
             push(s.a, 3);\n\
             let t: S = s;\n\
             t.a[0] = 5;\n\
             print(len(s.a), s.a[0], t.a[0], s.x);\n\
             print(s);\n\
             print(s.a);\n\
             print(len(t.a), t.a[0]);",
            "3 7 5 9\nS { a: [7, 2, 3], x: 9 }\n[7, 2, 3]\n3 5\n",
        );
    }

    #[test]
    fn struct_dynamic_field_runtime_whole_field_assign() {
        assert_runtime(
            "struct S { a: array<int>; x: int; }\n\
             let s: S = S { a: [1, 2], x: 9 };\n\
             let t: S = S { a: [3], x: 4 };\n\
             s.a = [5, 6];\n\
             t.a = s.a;\n\
             print(len(s.a), s.a[0], s.a[1], len(t.a), t.a[0], t.a[1]);\n\
             t.a = [];\n\
             push(t.a, 8);\n\
             print(len(t.a), t.a[0]);",
            "2 5 6 2 5 6\n1 8\n",
        );
    }

    #[test]
    fn struct_dynamic_field_runtime_param_ret() {
        assert_runtime(
            "struct S { a: array<int>; x: int; }\n\
             fn f(v: S) -> S { v.a[0] = 8; return v; }\n\
             let s: S = S { a: [1, 2], x: 9 };\n\
             s.a[0] = 7;\n\
             push(s.a, 3);\n\
             let u: S = f(s);\n\
             print(u.a[0], s.a[0]);\n\
             let v: S = f(s);\n\
             print(v);",
            "8 7\nS { a: [8, 2, 3], x: 9 }\n",
        );
    }

    #[test]
    fn struct_dynamic_field_runtime_arrays_and_scope_drop() {
        assert_runtime(
            "struct P { a: array<int>; }\n\
             let arr: array<P, 2> = [P { a: [1] }, P { a: [2] }];\n\
             let cp: array<P, 2> = arr;\n\
             cp[0].a[0] = 9;\n\
             print(arr[0].a[0], cp[0].a[0]);\n\
             let d: array<P> = [P { a: [3] }, P { a: [4] }];\n\
             let d2: array<P> = d;\n\
             d2[1].a[0] = 8;\n\
             push(d, P { a: [5] });\n\
             print(len(d), d[1].a[0], d[2].a[0], d2[1].a[0]);\n\
             let i: int = 0;\n\
             while (i < 1) {\n\
               let w: P = P { a: [6, 7] };\n\
               print(len(w.a), w.a[1]);\n\
               break;\n\
             }\n\
             print(0);",
            "1 9\n3 4 5 8\n2 7\n0\n",
        );
    }

    #[test]
    fn struct_dynamic_field_runtime_return_transfer_and_drop() {
        assert_runtime(
            "struct S { a: array<int>; x: int; }\n\
             fn early() -> S {\n\
               let w: S = S { a: [1, 2], x: 1 };\n\
               let z: S = S { a: [3], x: 2 };\n\
               return w;\n\
             }\n\
             let e: S = early();\n\
             print(e.a[0], e.a[1], e.x);\n\
             fn lit() -> S { return S { a: [4, 5], x: 6 }; }\n\
             let l: S = lit();\n\
             print(l);\n\
             fn chain() -> S { return lit(); }\n\
             let c: S = chain();\n\
             print(len(c.a), c.a[1], c.x);",
            "1 2 1\nS { a: [4, 5], x: 6 }\n2 5 6\n",
        );
    }

}
