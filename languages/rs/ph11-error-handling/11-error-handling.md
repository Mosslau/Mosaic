# Rust 错误处理与工程质量阶段

> 面向数据基础设施、异步网络服务方向：本阶段建立可维护的错误模型和基础工程质量习惯——让"哪里出错、为什么出错、怎么排查"从散落的 `unwrap` 和字符串拼接，变成带类型的错误枚举、可追溯的错误链和可观测的日志，并用测试守住核心路径。

## 1. 概述

Rust 错误处理与工程质量阶段的定位是：**能按"库 / 应用"分工设计错误类型（库偏向具体错误枚举、应用可用上下文错误），用 `?` 与 `From` 传播错误、用 `source()` 串联错误链，用 `tracing`/`log` 输出可观测日志，并用单元测试与集成测试覆盖正常路径和异常路径**。本阶段是 ph04 Option/Result 阶段的进阶：ph04 学会"错误是返回值、用 `?` 传播"，本阶段回答"传播到哪里、用什么类型承载、怎么给用户和运维讲清楚"；同时承接 ph10 智能指针——`Mutex` 中毒（poisoned）正是"共享状态下出错"的典型例子，`lock()` 返回 `Err` 的恢复策略就落在本阶段的错误模型里。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 自定义错误类型 | 实现 `Display` + `std::error::Error` + `From`，`source()` 提供底层原因 |
| 错误库与分工 | `thiserror`（库：具体枚举）、`anyhow`（应用：上下文错误）、`?` 自动转换 |
| 错误链与上下文 | `.context()`/`.with_context()` 逐层附加现场信息，`{:?}` 打印整条链 |
| 可观测性 | `tracing` 的 span/event 结构化字段、`log` 门面、敏感信息过滤 |
| 测试 | 单元测试（`#[cfg(test)]`）、集成测试（`tests/`）、`#[should_panic]`、测试金字塔 |

**本阶段边界**：承接 ph10 智能指针——`Mutex` 中毒的恢复策略与 `Result` 在共享状态上的工程化组合正是本阶段主题；不深入异步编程（ph12，跨 `.await` 的错误处理与任务取消）、文件网络与系统编程（ph13，`std::fs` 与网络 I/O 的系统化错误处理）、unsafe 与裸指针（ph14）；本阶段聚焦"错误类型设计 + 日志 + 测试"三位一体。

## 2. 来源与演变

Rust 的错误处理哲学从诞生起就与 C/Java 分道扬镳：**不用异常，错误是返回值**——`Result<T, E>` 把失败写进函数签名，编译器强制调用方处理。早期 `try!` 宏让传播少写样板，但嵌套难看；RFC 243（"First-class error handling with `?`"）推动 `?` 运算符在 Rust 1.13（2016）稳定，错误传播变成一行。2018 年前后 `Error::source()`（Rust 1.30 起可用）与 `Box<dyn Error>` 让"错误链（Error Chain）"成为标准概念；2019 年 10 月 dtolnay 的 `anyhow` 1.0（2019-10-07）与 `thiserror` 1.0（2019-10-09）在同周发布（crates.io 记录），把"应用用 anyhow、库用 thiserror"的分工固化成语生态惯例；同期 tokio 团队的 `tracing` 0.1（2019-06-28）把结构化日志与 span 引入主流，取代"字符串拼日志"。2024 年 `Error::provide` 稳定（Rust 1.81，RFC 2895），错误可以携带类型化上下文（backtrace、请求 id），不再依赖字段命名约定。

| 时间 | 里程碑 | 影响 |
|------|--------|------|
| 2011-2014 | `Option<T>`/`Result<T, E>` 与 `try!` 宏在 1.0 前定型 | "错误是返回值"成为语言哲学，编译器强制处理 |
| 2016-2017 | `?` 运算符稳定（RFC 243，Rust 1.13），随后扩展到 `Option`（Rust 1.22） | `try!` 的语法糖，错误传播一行完成 |
| 2018 | `Error::source()` 可用（Rust 1.30），`Box<dyn Error>` 成为常见签名 | 错误链成为标准概念，根因可追溯 |
| 2019 | `anyhow` 1.0（2019-10-07）与 `thiserror` 1.0（2019-10-09）发布 | "应用 anyhow、库 thiserror"的分工成为生态惯例 |
| 2019 | `tracing` 0.1 发布（tokio 团队，2019-06-28） | span + 结构化事件取代字符串拼日志 |
| 2024 | `Error::provide` 稳定（Rust 1.81，RFC 2895） | 类型化上下文（backtrace、请求 id）不再依赖字段命名 |

## 3. 语法与参数

### 3.1 std::error::Error trait（Display · source · provide）

**`std::error::Error` trait** 是生态里"可打印、可追溯的错误"的统一接口：实现它的前提是类型同时实现 **`Debug` 和 `Display`**（supertrait）。`Display` 写"给人看的消息"，`source()` 返回 `Option<&(dyn Error + 'static)>` 指回底层原因，`provide()`（Rust 1.81 起）挂载类型化上下文：

```rust
use std::fmt;

#[derive(Debug)]
struct MyError(String);

impl fmt::Display for MyError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "自定义错误: {}", self.0)
    }
}

impl std::error::Error for MyError {} // 默认 source() 返回 None
```

要点与坑：
- **`Error` 的实现通常是空 impl**：关键是 `Display` 写得好不好——错误消息是用户和运维唯一直接看到的东西；`source()` 返回类型擦除的 `&(dyn Error + 'static)`，调用方沿它一路走到根因（错误链的接口，见 4.2）。
- **坑：`Debug` 不能省**——`#[derive(Debug)]` 是惯例；`Error: Debug + Display` 是编译期强制。

### 3.2 ? 运算符与 From 自动转换

**`?` 运算符**是错误传播的语法糖：`x?` 在 `Result<T, E>` 上展开为 `match x { Ok(v) => v, Err(e) => return Err(From::from(e)) }`——函数返回类型必须是 `Result<T, E>`，且 `E: From<U>`（`U` 是 `x` 的错误类型）。标准库为 `io::Error`、`ParseIntError`、`FromUtf8Error` 等提供 `From` 转换，自定义错误实现 `From` 后 `?` 自动完成"包装"：

```rust
fn read_config(path: &str) -> Result<String, std::io::Error> {
    let text = std::fs::read_to_string(path)?; // 失败即 return Err(From::from(e))
    Ok(text)
}
```

要点与坑：
- `?` 是**编译期展开**：与手写 `match` 等价，零运行时开销（见 4.1）。
- `?` 也能用于 `Option`（Rust 1.22 起）：`None` 直接 `return None`。
- **坑：返回类型不匹配时编译报错**，提示"consider using `?`/`map_err`"——先想清楚"要转成哪个错误类型"，再用 `map_err` 或自定义 `From` 完成转换。

### 3.3 自定义错误枚举（Display + Error + From 三步）

自定义错误类型的标准形态是**枚举**：每个变体是一种失败模式。三步走：写 `Display`（人可读的消息）、实现 `Error`（进错误链）、实现 `From`（让 `?` 转换）：

```rust
use std::num::ParseIntError;

#[derive(Debug)]
enum PortError {
    MissingColon(String),   // 没有 ":" 分隔符
    BadPort(ParseIntError), // 端口不是数字（包装标准库错误）
    OutOfRange(u16),        // 端口超出 1-65535
}
// Display / Error / From 的完整实现见示例 1（同一类型，可运行）
```

要点与坑：
- **Display 面向人、Debug 面向开发者**：Display 写"哪个输入、哪个字段"，Debug 保留内部细节；`source()` 只对"包装了底层错误"的变体返回 `Some`。
- 手写样板较多——生产代码常用 `thiserror` 生成（3.4），但理解手写三步是看懂 derive 的基础。

### 3.4 thiserror derive 宏（库代码的错误类型）

**`thiserror`** 用 `#[derive(thiserror::Error)]` 自动生成 `Display`、`Error`、`source()`、`From` 的实现（编译期展开，零运行时开销）。roadmap 示例即最小形态：

```rust
#[derive(Debug, thiserror::Error)]
enum AppError {
    #[error("invalid input: {0}")]
    InvalidInput(String),
}
```

完整形态见示例 2 的可运行代码（`#[from]` 自动生成 `From`、`#[source]` 标注错误链、带字段变体）。

要点与坑：
- **格式串语法**：`{0}` 引用元组字段，`{name}` 引用具名字段；`#[source]` 字段自动实现 `source()`，`#[from]` 字段自动生成 `From<该类型>`。
- **库代码为什么用它**：枚举是"闭集"，调用方可以 `match` 穷尽失败模式做分支处理；`thiserror` 只省样板，不改变错误模型本质。

### 3.5 anyhow::Result 与 context（应用代码的错误类型）

**`anyhow`** 提供 `anyhow::Result<T>`（= `Result<T, anyhow::Error>`）与 **`Context` trait**：`anyhow::Error` 包装 `Box<dyn Error + Send + Sync + 'static>`，任何错误都能装进去；`.context(...)`/`.with_context(...)` 在 `Result`/`Option` 上附加"做什么时出错"的现场信息：

```rust
use anyhow::{Context, Result};

fn load(path: &str) -> Result<String> {
    let text = std::fs::read_to_string(path).with_context(|| format!("读取配置文件 {path}"))?;
    Ok(text)
}
```

要点与坑：
- **应用代码为什么用它**：应用关心"在哪一步失败"多于"失败的具体类型"；入口处 `{:?}` 打印整条错误链（"Caused by" 逐层一行）。`bail!`/`ensure!` 可在函数中间"提前失败"。
- **坑：不要在库的公开 API 返回 `anyhow::Error`**——调用方无法分支处理；原则是"库用具体枚举、应用入口用 anyhow"，错误类型在边界处转换（`map_err` 或 `?` + `From`）。

### 3.6 tracing 宏与 span（结构化日志）

**`tracing`** 提供五个级别宏（`trace!`/`debug!`/`info!`/`warn!`/`error!`）与 **span**（有开始有结束的作用域上下文）：`span!(Level::INFO, "process", id = 7)` 创建 span、`enter()` 返回 guard（离开作用域自动退出），`info!(step = "parse", "开始解析")` 记录事件并携带结构化字段（`%x` 用 Display 格式化）。完整可运行示例见示例 4。

要点与坑：
- **span vs event**：span 覆盖一段代码（进入/离开自动记录，可嵌套、子 span 继承父 span 字段）；event 是时间点上的单条记录，挂在当前 span 栈下。`#[instrument]` 属性可自动为函数包一个 span（ph12 中跨 `.await` 保持上下文的关键）。
- **结构化字段**：`key = value` 交给 subscriber 消费（可输出 JSON、可按字段检索），`%x` 用 Display、`?x` 用 Debug 格式化——不要把信息拼进消息字符串。
- **与 `log` 的关系**：`log`（2014 年以来的门面 crate）只有级别与文本；`tracing` 是它的替代（span + 结构化字段），二者可桥接（`tracing` 的 `log` feature 转发 `log` 记录）。
- **坑：忘记 `init()`**——没有 subscriber 时宏是空操作，日志静默丢失且不报错。

## 4. 底层原理

### 4.1 Result\<T, E\> 的表示与 ? 的展开

`Result<T, E>` 是一个枚举（`Ok(T)`/`Err(E)`），布局遵循"最大变体 + 判别位"规则；当某个变体的负载存在 **niche**（如 `&T` 不能为 null、`Box` 内部是指针）时，编译器把判别位塞进 niche——`Result<&T, E>` 在 `E` 不大于指针宽度时与 `&T` **等大**，错误处理不额外占内存。`x?` 编译期展开为 `match x { Ok(v) => v, Err(e) => return Err(From::from(e)) }`，与手写 `match` 的机器码一致、**零运行时开销**。`?` 的 `From` 转换让"每层函数返回自己的错误类型、底层错误自动包装"成为可能——这是分层错误模型的编译期基础：底层 `io::Error` 经 `From` 逐层变成中间层、入口层的具体错误，签名保持精确，传播保持简洁。

### 4.2 错误链：source() 如何串起底层原因

`Error::source()` 返回 `Option<&(dyn Error + 'static)>`，每一层形成单向链表：**Display 描述"这一层发生了什么"，source 指回"底层为什么失败"**。`thiserror` 的 `#[source]`/`#[from]`、`anyhow` 的 `context` 都在维护这条链：`anyhow::Error::chain()` 遍历打印；`{:?}`（普通 Debug）按"外层消息 + Caused by"输出，`{:#?}` 则打印内部结构，输出形如：

```text
解析 data.csv 第 2 行

Caused by:
    invalid digit found in string
```

设计准则：**Display 写"操作 + 输入"**（用户可读、可定位），**source 链写"原因链"**（开发者可追）；不要在某一层重复底层已说的信息（链式打印会冗余），也不要把根因藏进 Display 字符串而不走 `source()`（会丢失结构化追踪）。

### 4.3 Box\<dyn Error\>：动态分发与类型擦除

`dyn Error` 是 **trait 对象**：胖指针（数据指针 + vtable 指针），具体类型被擦除，`Box<dyn Error>` 固定为两个指针宽。它与具体枚举的分工是错误模型的核心：

| 维度 | 具体枚举（闭集） | `Box<dyn Error>`（开集） |
|------|----------------|-------------------------|
| 变体集合 | 编译期已知，`match` 可穷尽 | 任意实现 `Error` 的类型 |
| 调用方能做什么 | 按变体分支处理、提取字段 | 只能 `Display`/`source()`/`provide()` |
| 典型场景 | 库的公开 API | 应用入口、聚合层 |
| 转换成本 | 编译期静态分发 | 运行时 vtable 动态分发（极小） |

`anyhow::Error` 内部就是 `Box<dyn Error + Send + Sync + 'static>` + backtrace + chain 迭代器：`Send + Sync` 是为了错误能跨线程移动（ph12 中任务返回的错误要在任务间传递）——"任何错误都能装进去"与"调用方无法分支处理"是一体两面，这正是"库/应用分工"的底层原因。

### 4.4 tracing 的 span/subscriber 机制

`tracing` 把日志拆成两层：**采集层**（宏生成 span/event 的"结构化事实"，不关心输出）与**输出层**（subscriber 决定消费方式：文本、JSON、按 span 栈组织）。span 是"有开始有结束"的上下文：`span!` 创建、`enter()` 返回 guard（离开作用域自动退出），subscriber 记录进入/退出及耗时；子 span 继承父 span 的字段，形成一棵 span 树——请求 id 挂在根 span 上，整条调用链的日志都带得上。**开销设计**：宏自带 `level_enabled` 短路——级别未启用时字段表达式不执行，格式化推迟到 subscriber 侧（`field::display` 包装不立即 `to_string`），这是它比"字符串拼接日志"高效的原因。**敏感信息防线**：字段是显式 key=value，审计"哪些字段进了日志"比审字符串拼接容易得多；配合 `Display` 实现里不打印密码/令牌，构成"日志不泄露敏感信息"的工程红线。

### 4.5 panic 与 unwind/abort（Mutex 中毒的底层机制）

panic 默认走 **unwind**：沿调用栈展开，逐层 drop 局部变量（运行析构、释放 `MutexGuard` 等 RAII 资源），触发 panic hook（默认打印到 stderr），`catch_unwind` 可截获（`UnwindSafe` 约束防止捕获已破坏不变量）。`panic = "abort"`（Cargo.toml `[profile.*]` 配置）直接中止进程：不运行析构、二进制更小、行为可预测，代价是无法捕获、资源不清理。**`Mutex` 中毒（poisoned）**正是 panic 与共享状态交汇的产物：持锁线程 panic 展开时，guard 的 `Drop` 把锁标记为中毒（内部 `poisoned: AtomicBool`），后续 `lock()` 返回 `PoisonError`——ph10 里 `lock().unwrap()` 会因此直接 panic，工程化做法是显式处理 `PoisonError`（`into_inner()` 取回数据，或记录后重建状态）。**panic 与 Result 的分工**：panic = 不可恢复的不变量破坏（程序员错误、契约违反，如 `expect("...")`）；Result = 可恢复的预期失败（用户输入、I/O）——错误"严重度分级"是错误模型设计的第一步。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 库的公开 API 返回精确错误（解析器、配置加载） | 自定义错误枚举 + `thiserror`（3.3、3.4） |
| CLI / 服务入口聚合错误，I/O 失败告诉用户"哪一步、哪个文件" | `anyhow::Result` + `.with_context()` 错误链（3.5） |
| 排查线上问题（请求级日志、耗时追踪） | `tracing` span（请求 id）+ 结构化字段（3.6） |
| 防止日志泄露密码/令牌/密钥 | 字段显式化、`Display` 不打印敏感内容（4.4） |
| 守护核心逻辑正确性 | 单元测试 + 集成测试，正常/异常路径（示例 5） |
| 共享状态被 panic 污染后的恢复 | `Mutex` 中毒检测 + `PoisonError` 处理（4.5） |

**不适合**此阶段的事项：
- 异步错误处理（ph12）：`?` 跨 `.await`、任务取消与超时、`JoinError`——本阶段只在线程边界（`thread::spawn` 的 `JoinHandle`）体会错误跨线程传递。
- 文件、网络与系统编程的系统化错误处理（ph13）：`std::fs`、TCP/UDP 错误码与重试策略——本阶段只用 `std::fs::read_to_string` 演示 I/O 错误的上下文化。

## 6. 代码示例

### 示例 1：手写自定义错误类型（纯 std，实现 Error + Display + From）

roadmap 练习"为解析模块定义错误枚举"的最小手写版：不依赖任何第三方 crate，验证"三步走"（Display + Error + From）与 `?` 的自动转换：

```rust
// 示例 1：手写自定义错误类型（纯 std）：实现 Error + Display + From，让 `?` 自动转换
use std::error::Error;
use std::fmt;
use std::num::ParseIntError;

#[derive(Debug)]
pub enum PortError {
    MissingColon(String),   // 没有 ":" 分隔符
    BadPort(ParseIntError), // 端口不是数字（包装标准库错误）
    OutOfRange(u16),        // 端口超出 1-65535
}

impl fmt::Display for PortError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            PortError::MissingColon(s) => write!(f, "缺少冒号分隔符: {s:?}"),
            PortError::BadPort(e) => write!(f, "端口号不是数字: {e}"),
            PortError::OutOfRange(p) => write!(f, "端口号 {p} 超出 1-65535"),
        }
    }
}

impl Error for PortError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            PortError::BadPort(e) => Some(e), // 错误链：暴露底层原因
            _ => None,
        }
    }
}

// From：让 `?` 能把 ParseIntError 自动转成 PortError
impl From<ParseIntError> for PortError {
    fn from(e: ParseIntError) -> Self {
        PortError::BadPort(e)
    }
}

fn parse_addr(s: &str) -> Result<(String, u16), PortError> {
    let (host, port) = s
        .split_once(':')
        .ok_or_else(|| PortError::MissingColon(s.to_string()))?;
    let port: u16 = port.parse()?; // ParseIntError -> PortError（走 From）
    if port == 0 {
        return Err(PortError::OutOfRange(port));
    }
    Ok((host.to_string(), port))
}

fn main() {
    for input in ["127.0.0.1:8080", "localhost:abc", "no-colon-here", "127.0.0.1:0"] {
        match parse_addr(input) {
            Ok((h, p)) => println!("OK   {input:14} -> {h}:{p}"),
            Err(e) => println!("ERR  {input:14} -> {e}"),
        }
    }
}
```

输出：`OK 127.0.0.1:8080 -> 127.0.0.1:8080`；`ERR localhost:abc -> 端口号不是数字: invalid digit found in string`；`ERR no-colon-here -> 缺少冒号分隔符: "no-colon-here"`；`ERR 127.0.0.1:0 -> 端口号 0 超出 1-65535`。

要点与坑：
- **每条错误消息都定位到具体输入**（哪个地址、缺什么、哪个值越界）——对应阶段验收"错误信息能定位问题"；`?` 的两处使用分别演示 `ok_or_else` 与 `From` 自动转换。

### 示例 2：用 thiserror 定义错误枚举 + ? 自动转换

roadmap 示例（`#[derive(Debug, thiserror::Error)] enum AppError`）的完整版：`#[from]` 自动生成 `From`，`#[source]` 标注错误链，带行号的变体让错误"指到具体第几行"：

```rust
// 示例 2：thiserror 错误枚举 + `?` 自动转换（roadmap 示例的完整版）
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AppError {
    #[error("invalid input: {0}")]
    InvalidInput(String),

    #[error("I/O 错误: {0}")] // #[from]：io::Error 可经 `?` 自动转换
    Io(#[from] std::io::Error),

    #[error("第 {line} 行不是合法数字: {source}")] // {line} 定位行号，#[source] 标注底层原因
    ParseInt {
        line: usize,
        #[source]
        source: std::num::ParseIntError,
    },
}

// io::Error 走 #[from] 自动转换；解析错误手动包装成带行号的 ParseInt（方便定位）
fn load_scores(path: &str) -> Result<Vec<u32>, AppError> {
    let text = std::fs::read_to_string(path)?; // io::Error -> AppError::Io
    text.lines()
        .enumerate()
        .map(|(i, line)| {
            line.trim()
                .parse::<u32>()
                .map_err(|e| AppError::ParseInt { line: i + 1, source: e })
        })
        .collect()
}

fn main() {
    // 先造输入文件，保证示例可独立运行
    std::fs::write("scores.txt", "90\n85\nnot_a_number\n60\n").unwrap();

    match load_scores("scores.txt") {
        Ok(scores) => {
            println!("共 {} 个分数，总和 {}", scores.len(), scores.iter().sum::<u32>());
        }
        Err(e) => {
            eprintln!("加载失败: {e}"); // 第 3 行不是合法数字: invalid digit found in string
            std::process::exit(1);
        }
    }
}
```

运行输出（stderr）：`加载失败: 第 3 行不是合法数字: invalid digit found in string`，退出码 1。

要点与坑：
- **`#[from]` 与手动 `map_err` 并存**：`Io` 走自动转换，`ParseInt` 手动包装——因为要携带行号（`#[from]` 的自动 `From` 无法注入额外字段）；错误消息精确到行号，是"库代码偏向具体错误"的体现。

### 示例 3：anyhow + .context() 为 I/O 错误添加上下文

roadmap 练习"为 I/O 错误添加上下文"：`anyhow` 的 `Context` trait 在每层附加"做什么时出错"，`{:?}` 打印整条错误链：

```rust
// 示例 3：anyhow + .context() 为 I/O 错误添加上下文
use anyhow::{Context, Result};

// 应用代码：anyhow::Error 能装进任何错误；context 逐层附加"做什么时出错"的现场信息
fn load_report(path: &str) -> Result<String> {
    let text = std::fs::read_to_string(path)
        .with_context(|| format!("读取报告文件 {path}"))?;
    Ok(text)
}

fn parse_report(path: &str) -> Result<Vec<u32>> {
    let text = load_report(path)?;
    text.lines()
        .enumerate()
        .map(|(i, line)| {
            line.trim()
                .parse::<u32>()
                .with_context(|| format!("解析 {path} 第 {} 行", i + 1))
        })
        .collect()
}

fn main() {
    // 场景 A：内容不合法 -> 错误链带上"第几行"；场景 B：文件不存在 -> 带上"哪个文件"
    std::fs::write("data.csv", "10\nabc\n30\n").unwrap();
    if let Err(e) = parse_report("data.csv") {
        eprintln!("=== 场景 A：内容错误 ===");
        eprintln!("{e:?}");
    }
    if let Err(e) = parse_report("missing.csv") {
        eprintln!("=== 场景 B：文件不存在 ===");
        eprintln!("{e:?}");
    }
}
```

输出（stderr）：场景 A 打印 `解析 data.csv 第 2 行` + `Caused by: invalid digit found in string`；场景 B 打印 `读取报告文件 missing.csv` + `Caused by: No such file or directory (os error 2)`。

要点与坑：
- **上下文从外向里打印**：先是最外层操作（`读取报告文件`/`解析第 N 行`），`Caused by` 之后是底层根因——这就是错误链的可读形态。
- `with_context` 接收闭包：只在出错时才构造字符串（避免正常路径的格式化开销）；context 链逐层叠加，每层只写"自己这一步"（场景 A 里 `load_report` 成功、解析层失败）。

### 示例 4：tracing 日志（span 作用域 + 结构化字段）

roadmap 学习内容"tracing/log 日志"：span 覆盖批次处理（进入/离开自动记录），event 带结构化字段，`%` 表示用 Display 格式化：

```rust
// 示例 4：tracing 日志（span 作用域 + 结构化字段）
use tracing::{debug, error, info, span, warn, Level};

fn process_record(record: &str) -> Result<u32, String> {
    // 结构化字段：tracing 把 key=value 交给 subscriber，而不是拼进字符串
    record.trim().parse::<u32>().map_err(|_| format!("非法数字: {record:?}"))
}

fn process_batch(batch_id: u32, lines: &[&str]) {
    // span：作用域上下文，进入/离开由 subscriber 记录；guard 离开作用域即退出
    let span = span!(Level::INFO, "process_batch", batch_id, total = lines.len());
    let _guard = span.enter();

    for (i, line) in lines.iter().enumerate() {
        // 子 span 继承父 span 字段（batch_id、total 自动带上）
        let line_span = span!(Level::DEBUG, "line", line_no = i + 1);
        let _g = line_span.enter();
        match process_record(line) {
            Ok(v) => debug!(value = v, "解析成功"),
            Err(e) => warn!(error = %e, "跳过坏记录"), // %e：用 Display 格式化
        }
    }
    info!("批次处理完成");
}

fn main() {
    // fmt subscriber：渲染成带时间戳、级别、字段的文本
    tracing_subscriber::fmt()
        .with_max_level(Level::DEBUG)
        .with_target(false)
        .init();

    let batch = vec!["42", "7", "oops", "13"];
    process_batch(1, &batch);

    // 错误场景：error! 带结构化字段
    if let Err(e) = process_record("not-a-number") {
        error!(err = %e, "记录无法处理");
    }
}
```

输出（时间戳随运行时刻变化，级别、span 栈与字段固定）形如：`... DEBUG process_batch{batch_id=1 total=4}:line{line_no=1}: 解析成功 value=42`；坏记录为 `... WARN process_batch{...}:line{line_no=3}: 跳过坏记录 error=非法数字: "oops"`；最后的 `error!` 在 span 外，无 span 前缀。

要点与坑：
- **span 栈可见**：`process_batch{...}:line{...}` 说明事件挂在哪个 span 下——请求 id 类字段放根 span，整条链自动带上。
- **级别过滤**：`with_max_level(DEBUG)` 打开 `debug!`；不打开时 `debug!` 零开销（见 4.4）。生产化方向：`.json()` 输出结构化 JSON 供日志平台消费，`#[instrument]` 自动包 span。

### 示例 5：单元测试 + 集成测试（解析模块的正常/异常路径）

roadmap 练习"为解析模块定义错误枚举"+"补充正常路径和异常路径测试"的完整形态：库代码（手写错误枚举，不依赖 thiserror/anyhow）+ 同文件单元测试 + `tests/` 集成测试（含 `Result` 返回测试与 `#[should_panic]`）。

`src/lib.rs`：

```rust
//! 解析模块：把 `key=value` 文本解析成配置表（库代码偏向"具体错误"，纯 std 手写）

use std::collections::HashMap;
use std::fmt;

#[derive(Debug, PartialEq, Eq)]
pub enum ParseError {
    MissingEquals(String), // 缺少 `=` 分隔符
    DuplicateKey(String),  // 重复的 key
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ParseError::MissingEquals(line) => write!(f, "缺少 `=` 分隔符: {line:?}"),
            ParseError::DuplicateKey(key) => write!(f, "重复的 key: {key:?}"),
        }
    }
}

impl std::error::Error for ParseError {}

pub fn parse_line(line: &str) -> Result<(String, String), ParseError> {
    line.split_once('=')
        .map(|(k, v)| (k.trim().to_string(), v.trim().to_string()))
        .ok_or_else(|| ParseError::MissingEquals(line.to_string()))
}

pub fn parse_config(text: &str) -> Result<HashMap<String, String>, ParseError> {
    let mut map = HashMap::new();
    for line in text.lines() {
        if line.trim().is_empty() {
            continue; // 空行在配置文件中合法，跳过
        }
        let (key, value) = parse_line(line)?;
        if map.insert(key.clone(), value).is_some() {
            return Err(ParseError::DuplicateKey(key));
        }
    }
    Ok(map)
}

pub fn parse_config_checked(text: &str) -> HashMap<String, String> {
    parse_config(text).expect("config text must be valid")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_line_ok() {
        // 正常路径：返回值正确
        assert_eq!(
            parse_line("host=127.0.0.1").unwrap(),
            ("host".to_string(), "127.0.0.1".to_string())
        );
    }

    #[test]
    fn parse_line_missing_equals() {
        // 异常路径：缺 `=` 报 MissingEquals
        let err = parse_line("no-equals").unwrap_err();
        assert_eq!(err, ParseError::MissingEquals("no-equals".to_string()));
    }

    #[test]
    fn parse_config_duplicate_key() {
        // 异常路径：重复 key 报 DuplicateKey
        let err = parse_config("a=1\nb=2\na=3").unwrap_err();
        assert_eq!(err, ParseError::DuplicateKey("a".to_string()));
    }

    #[test]
    #[should_panic(expected = "config text must be valid")]
    fn checked_panics_on_bad_input() {
        // panic 路径：便捷入口对非法输入 panic，验证调用契约
        let _ = parse_config_checked("bad line");
    }
}
```

`tests/parse_tests.rs`（集成测试，以"外部使用者"视角走公开 API）：

```rust
//! tests/parse_tests.rs —— 集成测试
//!
//! 以"外部使用者"的视角走 crate 的公开 API（只能访问 pub 项），
//! 覆盖正常路径与异常路径，含 Result 返回测试与 #[should_panic] 测试。

use ph11_verify::{parse_config, parse_config_checked, ParseError};

#[test]
fn integration_parse_config_ok() { // 正常路径：多行配置解析成表
    let cfg = parse_config("host=127.0.0.1\nport=8080").unwrap();
    assert_eq!(cfg.get("host").map(String::as_str), Some("127.0.0.1"));
    assert_eq!(cfg.get("port").map(String::as_str), Some("8080"));
}

#[test]
fn integration_parse_config_via_result() -> Result<(), ParseError> { // ? 传播，出错即测试失败
    let cfg = parse_config("host=127.0.0.1\nport=8080")?;
    assert_eq!(cfg.get("host").map(String::as_str), Some("127.0.0.1"));
    Ok(())
}

#[test]
fn integration_duplicate_key_rejected() { // 异常路径：返回 Err，不 panic
    assert!(parse_config("a=1\na=2").is_err());
}

#[test]
#[should_panic(expected = "config text must be valid")]
fn integration_checked_panics_on_bad_input() { // panic 契约
    let _ = parse_config_checked("bad line");
}
```

`cargo test` 运行结果：单元测试套件与集成测试套件各 4 个测试、全部通过（`test result: ok. 4 passed; 0 failed` × 2），含 `should panic` 与 `Result` 返回测试；四个 bin 目标无测试（`running 0 tests`，已省略）。

要点与坑：
- **单元测内部、集成测契约**：单元测试直接测 `parse_line` 的返回值（含 `PartialEq` 对比错误枚举），集成测试只走 `pub` API，覆盖"正常路径 + 异常路径 + panic 契约"三类。
- **`Result` 返回测试**：`Err` 时 `?` 传播、测试失败并打印错误——比 `unwrap()` 的 panic 信息更友好；`#[should_panic]` 用于验证"契约性 panic"；错误枚举实现 `PartialEq, Eq` 让 `assert_eq!(err, ...)` 直接对比失败模式。

## 7. 总结

### 关键要点

1. **错误是值，不是异常**：`Result<T, E>` 把失败写进函数签名，编译器强制处理；`Option` 处理"可能没有"，`Result` 处理"可能出错"。
2. **自定义错误三步 + `?` 的本质**：`Display`（给人看）+ `Error`（进错误链）+ `From`（让 `?` 转换）；`?` 展开为 `match` + `From::from` + `return`，编译期展开、零运行时开销——`From` 是"分层错误模型"的编译期基础。
3. **库与应用分工**：库代码偏向具体错误（`thiserror` 枚举，调用方可 `match` 分支处理），应用代码可使用上下文错误（`anyhow`，关心"在哪一步失败"）；错误类型在边界转换。
4. **错误链**：`source()` 串起底层原因，`.context()` 附加现场信息，`{:?}` 打印整条链——"操作 + 输入"写给用户，"原因链"写给开发者。
5. **tracing 是下一代日志**：span 是作用域上下文（可嵌套、子继承父字段）、event 是时间点记录、字段是结构化 key=value；级别未启用时零开销。**日志红线**：字段显式化让"哪些信息进日志"可审计，`Display` 不打印密码/令牌，是"日志不泄露敏感信息"的工程底线。
6. **测试金字塔**：单元测试多而快（测内部逻辑与失败模式）、集成测试走公开 API（测契约）、端到端测试少而慢；正常路径和异常路径都要覆盖。
7. **panic 与 Result 分工**：panic 是"不可恢复的契约破坏"（`expect`、`#[should_panic]` 验证），Result 是"可恢复的预期失败"；`Mutex` 中毒的 `PoisonError` 显式处理承接 ph10 的伏笔。

### 跨语言对比：错误处理

| 维度 | Rust | Go | Java | Python | C++ |
|------|------|----|------|--------|-----|
| 错误表示 | `Result<T, E>` 返回值 | 多返回值 `(T, error)` | 异常（受检/非受检） | 异常（`raise`/`try-except`） | 异常 + 错误码并存 |
| 是否强制处理 | 编译器强制（`Result` 必须处理） | 靠自觉（`_` 可忽略） | 受检异常编译期强制 | 运行时才暴露 | 不强制 |
| 错误类型 | 具体枚举 / `Box<dyn Error>` | `error` 接口（值） | `Exception` 类层次 | `BaseException` 类层次 | 类层次 + `errno` |
| 错误上下文 | `?` + `context` 链式附加 | `fmt.Errorf("%w")` 包装 | 异常链 `initCause` | `raise ... from` | 无标准链（自造） |
| 清理保证 | RAII：unwind 逐层 drop（析构/解锁） | `defer` | `finally` | `finally` / `with` | RAII / `finally` |

### 阶段验收标准

- **错误信息能定位问题**：错误消息含"哪个操作、哪个输入/文件/行号"，`{:?}` 能打印完整错误链到根因；能区分"用户可读"（Display）与"开发者可追"（Debug/source）。
- **测试覆盖核心分支**：核心模块的正常路径与异常路径都有测试（单元 + 集成），`cargo test` 全绿。
- **日志便于排查且不泄露敏感信息**：日志按级别 + span + 结构化字段组织，能定位问题；密码、令牌等敏感字段不进日志（`Display` 不打印、字段不放行）。

### 进入下一阶段前

确保能完成以下练习：

- 为解析模块定义错误枚举（提示：先列失败模式清单，再写 `Display` + `Error` + `From`，或直接 `#[derive(thiserror::Error)]`；对照示例 1、2）。
- 为 I/O 错误添加上下文（提示：`anyhow` 的 `with_context` 带上"哪个文件、哪一步"，`{:?}` 看错误链；对照示例 3）。
- 补充正常路径和异常路径测试，并给程序加 `tracing` 日志验证 span 嵌套（提示：单元测内部、集成测契约；`with_max_level(DEBUG)` 观察子 span 字段继承；对照示例 4、5）。
- 口述库与应用错误处理的分工（提示：枚举是"闭集"可 `match` 穷尽，`Box<dyn Error>` 是"开集"只能 trait 方法——见 4.3；`Mutex` 中毒的 `PoisonError` 恢复属于哪一类？）。

### 推荐项目

- **可靠 CLI**（roadmap 推荐项目）：读取文件、解析数据、输出报告，并提供清晰错误提示。示例 3/5 已给出核心骨架（文件读取 + context、解析模块 + 测试）。扩展方向：错误输出用 `{:?}` 打印完整错误链；用 `tracing` 记录处理进度；把错误枚举接到 CLI 退出码（成功 0、解析失败非 0）。

### 下一阶段

**并发与异步阶段**（`ph12-concurrency-async`，文档规划中）—— 本阶段建立的错误模型将延伸到异步世界：`?` 跨 `.await` 传播（`Future` 的错误类型要求 `Send`）、任务失败用 `JoinError`/`tokio::spawn` 的错误类型表达、超时与取消成为新的错误来源（`tokio::time::error::Elapsed`）；`tracing` 的 span 则天然跨 `.await` 保持请求级上下文（`#[instrument]`），错误与日志在异步链路里汇合——ph11 打下的"错误类型设计 + 可观测性 + 测试"正是 ph12 并发正确性的地基。
