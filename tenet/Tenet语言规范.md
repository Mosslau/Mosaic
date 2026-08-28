# Tenet 语言规范（正式文法与语义）

> 本文档是 Tenet 设计的**唯一事实来源**：完整文法（EBNF）、类型系统、
> 求值语义与优先级规则。设计决策溯源见 [设计溯源](./Tenet设计溯源.md)，
> 编译器实现见 [`compiler/`](./compiler/)。
>
> Tenet 是一门吸收了 **C++（值语义/RAII 思想）、Rust（组合/Result/match/无继承）、
> Python（类型推断/REPL/可读性）** 设计的静态类型语言，编译器产出自包含的原生二进制。
>
> **实现状态**：`compiler/` 已实现核心子集（标量类型 + 函数递归 + 控制流 + print）；
> `struct`/`array<T>`/`Option`/`Result`/`match`/`?` 为已定设计，代码生成待扩展。

## 1. 设计定位

| 维度 | 定位 |
|------|------|
| 类型 | 静态类型 + 局部类型推断（let 可省标注） |
| 内存 | 自动管理：值语义 + 引用计数，作用域结束自动回收（无指针、无手动释放） |
| 抽象 | 组合优先：struct + 顶层函数（无继承、无类层次） |
| 错误 | 显式：`Result<T, E>` + `?` 传播（无异常） |
| 空值 | 显式：`Option<T>`（无 null） |
| 范式 | 一种惯用法：语句 + 表达式 + 函数（无多范式并存） |

## 2. 词法（Token）

### 2.1 字面量

```text
INT      := 十进制整数（i64 范围）
FLOAT    := 十进制浮点（`3.` 合法，Go 风格）
STRING   := '"' (字符 | 转义)* '"'    转义: \n \t \" \\
BOOL     := 'true' | 'false'
```

### 2.2 关键字

```text
let  fn  struct  if  else  while  match  break  continue  return
true  false  None  Some  Ok  Err
int  float  bool  string  array  Option  Result
```

> `len`、`print` 是**内建函数名**，不是关键字（保留字）。

### 2.3 符号

```text
( ) { } [ ] , : ; -> . = == != < <= > >=
+ - * / % && || ! ?
```

> `?` 是错误传播后缀运算符（吸收 Rust）；`.` 是成员访问（结构体字段）。

## 3. 完整文法（EBNF）

```text
program        := stmt*

stmt           := let_stmt ';'
                | fn_decl
                | struct_decl
                | if_stmt
                | while_stmt
                | match_stmt
                | return_stmt ';'
                | break_stmt ';'
                | continue_stmt ';'
                | expr_stmt ';'
                | block

let_stmt       := 'let' IDENT (':' type)? '=' expr
fn_decl        := 'fn' IDENT '(' param_list? ')' ('->' type)? block
struct_decl    := 'struct' IDENT '{' field* '}'
field          := IDENT ':' type ';'
param_list     := param (',' param)*
param          := IDENT ':' type

if_stmt        := 'if' '(' expr ')' block ('else' (if_stmt | block))?
while_stmt     := 'while' '(' expr ')' block
match_stmt     := 'match' expr '{' match_arm+ '}'
match_arm      := pattern '=>' (expr ';' | block)

return_stmt    := 'return' expr?
break_stmt     := 'break'
continue_stmt  := 'continue'
expr_stmt      := expr

block          := '{' stmt* '}'

type           := 'int' | 'float' | 'bool' | 'string'
                | 'array' '<' type '>'
                | 'Option' '<' type '>'
                | 'Result' '<' type ',' type '>'
                | IDENT                    (* struct 类型名 *)

expr           := assignment
assignment     := logic_or ('=' assignment)?
logic_or       := logic_and ('||' logic_and)*
logic_and      := equality ('&&' equality)*
equality       := comparison (('==' | '!=') comparison)*
comparison     := term (('<' | '<=' | '>' | '>=') term)*
term           := factor (('+' | '-') factor)*
factor         := unary (('*' | '/' | '%') unary)*
unary          := ('-' | '!') unary
                | postfix
postfix        := primary ('.' IDENT | '[' expr ']' | '?' | '(' arg_list? ')')*

primary        := INT | FLOAT | STRING | 'true' | 'false'
                | 'None' | 'Some' '(' expr ')'
                | 'Ok' '(' expr ')' | 'Err' '(' expr ')'
                | '[' arg_list? ']'            (* 数组字面量 *)
                | IDENT '{' field_init_list? '}'  (* 结构体构造 *)
                | IDENT
                | '(' expr ')'

arg_list       := expr (',' expr)*
field_init_list:= IDENT ':' expr (',' IDENT ':' expr)*

pattern        := INT | FLOAT | STRING | 'true' | 'false'
                | 'None' | 'Some' '(' pattern ')' | 'Ok' '(' pattern ')' | 'Err' '(' pattern ')'
                | IDENT                    (* 绑定变量 / 结构体模式 *)
                | '_'                      (* 通配 *)
```

## 4. 运算符优先级（低 → 高）

```text
=                赋值（右结合）
||               逻辑或（短路）
&&               逻辑与（短路）
==  !=           相等
<  <=  >  >=     比较
+  -             加减
*  /  %          乘除模
-  !             一元
.  [ ]  ( )  ?   成员访问 / 索引 / 调用 / 错误传播（后缀，最紧）
```

## 5. 类型系统

### 5.1 类型构造

```text
标量    int | float | bool | string
复合    array<T>                   动态数组
        struct 名                   具名字段结构（用户定义）
可选    Option<T> = None | Some(T)   无 null，空值显式
错误    Result<T, E> = Ok(T) | Err(E)   E 默认 string
```

### 5.2 类型推断规则（`let x = expr` 省略标注时）

| 表达式 | 推断类型 |
|--------|---------|
| 整数字面量 | `int` |
| 浮点字面量 | `float` |
| 字符串 / bool 字面量 | `string` / `bool` |
| `None` | `Option<T>`（T 由上下文决定） |
| `Some(e)` / `Ok(e)` / `Err(e)` | `Option<T>` / `Result<T,E>`（由 e 及上下文决定） |
| 变量 / 字段访问 / 索引 | 符号表 / 结构体定义 / `array<T>` 的 T |
| `+` | 全 int → int；有 float → float；全 string → string |
| `- * / %` | 数值；有 float → float；`%` 仅 int |
| 比较 / `&&` / `\|\|` | `bool` |
| `match` | 所有分支一致的类型 |
| `expr?` | `Result<T,E>` 的 T（错误传播） |
| 函数调用 | 函数返回类型 |

> 推断失败必须显式标注——不允许"未定型"的值（对比 Python 的完全动态）。

### 5.3 静态检查（类型检查器阶段）

- 变量必须先声明后使用
- 运算数类型匹配（int/float 互通，其余严格）
- 条件表达式必须是 `bool`
- `match` 必须**穷尽**（覆盖全部模式；`Option` 必须含 `None` 分支，否则加 `_`）
- 函数参数 / 返回值类型核对
- 错误信息统一 `[行:列]` 定位

## 6. 求值语义要点

| 规则 | 语义 |
|------|------|
| 值语义 | struct/array 赋值与传参按值拷贝；无指针 → 无别名修改、无悬垂 |
| 整除 | int/int **向零截断**（`-7/2 == -3`，C/Rust/Go 语义） |
| 短路 | `&&`/`\|\|` 右侧只在需要时求值（`true \|\| (1/0==1)` 不报错） |
| 作用域 | 块 `{}` 新建作用域；内层 `let` 遮蔽外层；赋值沿链找外层变量 |
| 内存 | 引用计数自动回收（RAII 思想的运行时版），作用域结束即释放 |
| `?` | 在 `Result<T,E>` 上求值：`Ok(v)` → `v`；`Err(e)` → 当前函数立即返回 `Err(e)` |
| match | 自上而下匹配第一个命中的模式；穷尽性由类型检查器保证 |
| 错误报告 | 词法/语法/类型/求值错误统一带 `[行:列]`，错误即值（非异常） |

## 7. 内建函数

```text
print(x...)   打印任意数量、任意类型的值，空格分隔 + 换行（吸收 Python）
len(x)        返回 array 长度（或 string 字节数）
```

## 8. v1 → v2 变更记录

| 变更 | 说明 | 来源 |
|------|------|------|
| + `struct` | 具名字段组合，数据建模 | C / Rust（组合优先） |
| + `array<T>` + 索引 `[]` + `len` | 复合数据容器 | C / Go（slice 思想） |
| + `Option<T>` / `None` / `Some` | 显式空值，消灭 null | Rust |
| + `Result<T,E>` / `Ok` / `Err` / `?` | 显式错误处理，替代异常 | Rust |
| + `match` + 模式 + `_` | 穷尽性分支 | Rust |
| + `continue` | 循环控制补全 | C 家族 |
| 拒绝保持 | 无继承、无异常、无指针、无闭包、无运算符重载 | — |

## 9. 明确不在设计内（见设计溯源拒绝清单）

继承 / 类层次、异常、闭包与函数一等值、运算符重载、泛型（演进）、
移动语义、借用检查、完全动态类型、模板元编程、多范式并存。
