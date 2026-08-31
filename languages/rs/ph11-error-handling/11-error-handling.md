# Rust 错误处理与工程质量阶段

> 面向数据基础设施、异步网络服务方向：本阶段建立可维护的错误模型和基础工程质量习惯——让「哪里出错、为什么出错、怎么排查」从散落的 `unwrap` 和字符串拼接，变成带类型的错误枚举、可追溯的错误链和清晰的恢复策略，并用测试守住核心路径。

## 1. 概述

Rust 错误处理与工程质量阶段对应 roadmap 第 11 节，目标是**建立可维护的错误模型和基础工程质量习惯**。具体定位是：**能按「库 / 应用」分工设计错误类型（库偏向具体错误枚举、应用可用上下文错误），用 `?` 与 `From` 传播错误、用 `source()` 串联错误链、用 `catch_unwind` 与 `PoisonError` 处理恢复边界，并用单元测试与集成测试覆盖正常路径和异常路径**。本阶段是 ph04 Option/Result 阶段的进阶：ph04 学会「错误是返回值、用 `?` 传播」，本阶段回答「传播到哪里、用什么类型承载、怎么给用户和运维讲清楚」；同时承接 ph10 智能指针——`Mutex` 中毒（poisoned）正是「共享状态下出错」的典型例子，`lock()` 返回 `Err` 的恢复策略就落在本阶段的错误模型里。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 组合子与传播 | Option/Result 组合子（map/and_then/or_else/ok_or_else/?），`?` 的 From 自动转换（3.1） |
| 自定义错误类型 | 手写三步走：Display + Error + From；错误枚举的闭集模型（3.2） |
| 错误链 | Error::source() 串联底层原因，错误上下文包装（Box\<dyn Error\>）逐层附加现场信息（3.3、3.4） |
| panic 与恢复边界 | catch_unwind、Mutex 中毒（poisoned）与 PoisonError 恢复、unwind/abort（3.6、4.4） |
| 生态讲解 | thiserror（库：具体枚举）、anyhow（应用：上下文错误）、tracing（结构化日志）——未在本环境验证（需第三方 crate）（3.5、3.7） |
| 测试 | 单元测试（#[cfg(test)]）、#[should_panic]、Result 返回测试、集成测试（3.8、练习 5、阶段项目） |

这个阶段只涉及错误处理工程化（组合子、自定义错误类型、错误链、上下文包装、panic 恢复边界）与基础测试，**不涉及并发与异步编程（`?` 跨 `.await`、任务取消与超时、`JoinError`）、文件/网络/系统编程的系统化错误处理（`std::fs` 全套、TCP/UDP 错误码与重试策略）和 unsafe 与裸指针** — 那些是 ph12 并发与异步阶段、ph13 文件网络与系统编程阶段、ph14 Unsafe Rust 与安全抽象阶段的内容（ph12~ph14 目录待建）。承接 [ph10 智能指针阶段](../ph10-smart-pointers/10-smart-pointers.md)：`Mutex` 中毒的恢复策略与 `Result` 在共享状态上的工程化组合正是本阶段主题；也承接 [ph04 Option/Result 阶段](../ph04-option-result/04-option-result.md)：组合子是 ph04 基础用法的系统化升级。

## 2. 来源与演变

Rust 的错误处理哲学从诞生起就与 C/Java 分道扬镳：**不用异常，错误是返回值**——`Result<T, E>` 把失败写进函数签名，编译器强制调用方处理。早期 `try!` 宏让传播少写样板，但嵌套难看；RFC 243（"First-class error handling with `?`"）推动 `?` 运算符在 Rust 1.13（2016）稳定，错误传播变成一行。2018 年前后 `Error::source()`（Rust 1.30 起可用）与 `Box<dyn Error>` 让「错误链（Error Chain）」成为标准概念；2019 年 dtolnay 的 `anyhow` 1.0（2019-10-07）与 `thiserror` 1.0（2019-10-09）同周发布，把「应用用 anyhow、库用 thiserror」的分工固化成语生态惯例；同期 tokio 团队的 `tracing` 0.1（2019-06-28）把结构化日志与 span 引入主流。2024 年 `Error::provide` 稳定（Rust 1.81，RFC 2895），错误可以携带类型化上下文（backtrace、请求 id），不再依赖字段命名约定。

| 时间 | 里程碑 | 影响 |
|------|--------|------|
| 2011-2014 | `Option<T>`/`Result<T, E>` 与 `try!` 宏在 1.0 前定型 | 「错误是返回值」成为语言哲学，编译器强制处理 |
| 2016-2017 | `?` 运算符稳定（RFC 243，Rust 1.13），随后扩展到 `Option`（Rust 1.22） | `try!` 的语法糖，错误传播一行完成 |
| 2018 | `Error::source()` 可用（Rust 1.30），`Box<dyn Error>` 成为常见签名 | 错误链成为标准概念，根因可追溯 |
| 2019 | `anyhow` 1.0（2019-10-07）与 `thiserror` 1.0（2019-10-09）发布 | 「应用 anyhow、库 thiserror」的分工成为生态惯例（发布记录来自 crates.io，本环境未安装验证） |
| 2019 | `tracing` 0.1 发布（tokio 团队，2019-06-28） | span + 结构化事件取代字符串拼日志（本环境未安装验证） |
| 2024 | `Error::provide` 稳定（Rust 1.81，RFC 2895） | 类型化上下文（backtrace、请求 id）不再依赖字段命名 |

本文示例以 **Rust 2021 edition（rustc 1.92.0）** 为基线（与 ph10 一致：全仓库代码层统一用 `rustc --edition 2021` 单文件编译——`rustc` 直接编译单文件默认仍是 edition 2015；错误处理核心 API（`Result`/`Option`/`?`/`From`/`Error`/`source`）自 Rust 1.0~1.30 全部稳定，是本阶段语法中最稳定的部分）。**依赖策略**：本阶段代码层（examples/exercises/project）只用标准库——错误处理全在 `std`，`rustc` 单文件编译、不依赖 cargo 联网；编译错误码与运行输出全部在本环境实测后写入。`thiserror`/`anyhow`/`tracing` 属于生态讲解内容（roadmap 学习内容），本环境未安装验证，涉及它们的示例一律标注「未在本环境验证（需第三方 crate）」——它们是「看懂本阶段纯 std 写法的进阶封装」，不是本阶段代码层的依赖。

## 3. 语法与参数

### 3.1 Option/Result 组合子（map / and_then / or_else / ok_or_else / ?）

ph04 已经学会用 `match` 与 `?` 处理 Option/Result，也见过 `map`/`and_then`；本阶段把组合子系统化——**组合子把「分支处理」压缩成链式调用，错误处理写进数据流**，重点补 `or_else`/`ok_or_else` 与 `?` 的组合：

```rust
// examples/ex01-option-result-combinators.rs —— Option/Result 组合子（完整可运行，主文档第 6 章示例 1）
// 验证环境：rustc 1.92.0，零第三方依赖；编译/运行：rustc --edition 2021 -D warnings ex01-option-result-combinators.rs -o /tmp/ex01 && /tmp/ex01（已验证）
let r: Result<u32, &str> = Ok(42);
println!("map Ok    = {:?}", r.map(|v| v * 2)); // Ok(84)：只改 Ok 里的值
let r2: Result<u32, &str> = Err("boom");
println!("map Err   = {:?}", r2.map(|v| v * 2)); // Err("boom")：错误原样穿过

// and_then：链式执行「可能失败」的下一步；or_else：失败时走替代路径
let s: Result<&str, &str> = Ok("42");
println!("and_then  = {:?}", s.and_then(|t| t.parse::<i32>().map_err(|_| "parse fail"))); // Ok(42)
let e: Result<u32, &str> = Err("not found");
println!("or_else   = {:?}", e.or_else(|_| Ok::<u32, &str>(7))); // Ok(7)

// ok_or_else + ?：Option 转 Result——「可能没有」升级为「可能出错」，附错误消息
let o: Option<u32> = None;
println!("ok_or_else = {:?}", o.ok_or_else(|| "missing value")); // Err("missing value")
```

**组合子速查表**

| 组合子 | 类型 | 语义 |
|--------|------|------|
| `map(f)` | `Option<T>` / `Result<T, E>` | 只改 `Some`/`Ok` 里的值，`None`/`Err` 原样穿过 |
| `and_then(f)` | 同上 | 链式执行「可能失败」的下一步（flatten 后 map），任一步失败整链短路 |
| `or_else(f)` | 同上 | 失败时走替代路径（闭包拿到错误值，可记录后再换路） |
| `ok_or_else(f)` | `Option<T>` → `Result<T, E>` | 「可能没有」升级为「可能出错」，错误消息惰性构造 |
| `unwrap_or(v)` / `unwrap_or_else(f)` | `Option<T>` → `T` | 安全取默认值，不 panic（ph04 已讲） |
| `?` | 解包或 return | 成功解包；`Result` 失败经 `From::from` 转换后 return，`Option` 失败直接 return `None` |

**坑（`?` 的四类编译错误，全部 rustc 1.92.0 实测，均为 E0277）**：

- `?` 用在返回 `()` 的函数里：报 `the `?` operator can only be used in a function that returns `Result` or `Option` (or another type that implements `FromResidual`)`，错误位置提示 `cannot use the `?` operator in a function that returns `()``
- `?` 在返回 `Result` 的函数里解 `Option`：报 `the `?` operator can only be used on `Result`s, not `Option`s, in a function that returns `Result``，编译器直接给解药：`use .ok_or(...)?` 提供与 `Result` 兼容的错误
- 反过来在返回 `Option` 的函数里解 `Result`：报 `the `?` operator can only be used on `Option`s, not `Result`s, in a function that returns `Option``，解药：`use .ok()?`
- `?` 的目标错误类型无法 `From` 转换：报 `?` couldn't convert the error to `MyErr`，说明 `the trait `From<std::io::Error>` is not implemented for `MyErr``，note 点破本质：`the question mark operation (`?`) implicitly performs a conversion on the error value using the `From` trait`——解法是给错误类型实现 `From`（3.2）或改用 `map_err` 手动转换

### 3.2 自定义错误类型：Display + Error + From 三步走

自定义错误类型的标准形态是**枚举**：每个变体是一种失败模式。手写三步走——**写 `Display`（人可读的消息）、实现 `Error`（进错误链）、实现 `From`（让 `?` 转换）**（roadmap 练习「为解析模块定义错误枚举」的最小形态）：

```rust
// examples/ex02-custom-error-from.rs —— 自定义错误类型 + From（完整可运行，主文档第 6 章示例 2）
// 验证环境：rustc 1.92.0，零第三方依赖；编译/运行：rustc --edition 2021 -D warnings ex02-custom-error-from.rs -o /tmp/ex02 && /tmp/ex02（已验证）
use std::error::Error;
use std::fmt;
use std::num::ParseIntError;

#[derive(Debug)]
enum PortError {
    MissingColon(String),   // 没有 ":" 分隔符（携带输入原文）
    BadPort(ParseIntError), // 端口不是数字（包装标准库错误，错误链的第一环）
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
        match self { PortError::BadPort(e) => Some(e), _ => None }
    }
}

impl From<ParseIntError> for PortError {
    fn from(e: ParseIntError) -> Self { PortError::BadPort(e) }
}

fn parse_addr(s: &str) -> Result<(String, u16), PortError> {
    let (host, port) = s.split_once(':')
        .ok_or_else(|| PortError::MissingColon(s.to_string()))?;
    let port: u16 = port.parse()?; // ParseIntError -> PortError：走 From 自动转换
    if port == 0 { return Err(PortError::OutOfRange(port)); }
    Ok((host.to_string(), port))
}
```

要点与坑：

- **Display 面向人、Debug 面向开发者**：Display 写「哪个输入、哪个字段」，Debug 保留内部细节（实测：`parse_addr("localhost:abc")` 的 Display 是 `端口号不是数字: invalid digit found in string`，Debug 是 `BadPort(ParseIntError { kind: InvalidDigit })`）。
- **`source()` 只对「包装了底层错误」的变体返回 `Some`**：`BadPort` 指回 `ParseIntError`，`MissingColon`/`OutOfRange` 返回 `None`——错误链的每一环都是「这一层发生了什么」+「底层为什么失败」。
- **`Error` 的实现通常是空 impl**：关键是 Display 写得好不好——错误消息是用户和运维唯一直接看到的东西；`Debug` 不能省（`Error: Debug + Display` 是编译期强制，`#[derive(Debug)]` 是惯例）。
- **`?` 的 From 转换已实测**：`port.parse()?` 处 `ParseIntError` 自动变成 `PortError::BadPort`，零运行时开销（见 4.1）；若目标错误没实现 `From`，编译器报 E0277（见 3.1 坑）。
- 手写样板较多——生产代码常用 `thiserror` 生成（3.5），但理解手写三步是看懂 derive 的基础。

### 3.3 Error trait 与 source()：错误链的接口

**`std::error::Error` trait** 是生态里「可打印、可追溯的错误」的统一接口：实现它的前提是类型同时实现 `Debug` 和 `Display`（supertrait）。`source()` 返回 `Option<&(dyn Error + 'static)>` 指回底层原因，`provide()`（Rust 1.81 起）可挂载类型化上下文。错误链的读法：**Display 描述「这一层发生了什么」，source 指回「底层为什么失败」**。纯 std 的链打印是沿 `source()` 逐层遍历（实测输出，见示例 3）：

```rust
// examples/ex03-error-trait-source.rs —— Error trait（Display + source）与错误链（完整可运行，主文档第 6 章示例 3）
// 验证环境：rustc 1.92.0，零第三方依赖；编译/运行：rustc --edition 2021 -D warnings ex03-error-trait-source.rs -o /tmp/ex03 && /tmp/ex03（已验证）
enum ScoreError {
    Io(std::io::Error),
    Parse { line: usize, source: ParseIntError },
}

impl Error for ScoreError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            ScoreError::Io(e) => Some(e),
            ScoreError::Parse { source, .. } => Some(source),
        }
    }
}

// 错误链打印：沿 source() 逐层走到根因（纯 std 做法）
fn print_chain(err: &(dyn Error + 'static)) {
    let mut cur = Some(err);
    while let Some(e) = cur {
        println!("  {e}");
        cur = e.source();
    }
}
```

实测输出（`load_scores` 解析坏文件 / 读不存在文件，两段链）：

```text
场景 A（解析失败）: 第 2 行不是合法数字: invalid digit found in string
错误链（source 逐层）:
  第 2 行不是合法数字: invalid digit found in string
  invalid digit found in string

场景 B（文件不存在）: 读取文件失败: No such file or directory (os error 2)
错误链（source 逐层）:
  读取文件失败: No such file or directory (os error 2)
  No such file or directory (os error 2)
```

要点与坑：

- **错误链的设计准则**：Display 写「操作 + 输入」（用户可读、可定位），source 链写「原因链」（开发者可追）；不要在某一层重复底层已说的信息（链式打印会冗余），也不要把根因藏进 Display 字符串而不走 `source()`（会丢失结构化追踪）。
- **`Caused by:` 是 anyhow 的打印格式**（3.5），纯 std 的等价物就是上面的 `source()` 遍历——本阶段练习 3 的思考题就在于此。
- **坑：`source()` 返回类型擦除的引用**——`&(dyn Error + 'static)`，调用方不能 `match` 具体类型，只能 Display/继续走链；要分支处理必须用错误枚举本身（3.2）。

### 3.4 Box\<dyn Error\>：错误上下文包装（开集错误）

**`Box<dyn Error>`** 是「开集」错误：任何实现 `Error` 的类型都能装进去（类型擦除），函数可以返回 `Result<T, Box<dyn Error>>` 而不暴露具体错误类型——配合 `map_err` 把「哪个文件、哪一行」逐层包进上下文，适合**应用/聚合层的错误处理**（roadmap 练习「为 I/O 错误添加上下文」）：

```rust
// examples/ex04-box-dyn-error-context.rs —— 错误上下文包装（完整可运行，主文档第 6 章示例 4）
// 验证环境：rustc 1.92.0，零第三方依赖；编译/运行：rustc --edition 2021 -D warnings ex04-box-dyn-error-context.rs -o /tmp/ex04 && /tmp/ex04（已验证）
use std::error::Error;

fn load(path: &str) -> Result<String, Box<dyn Error>> {
    std::fs::read_to_string(path).map_err(|e| format!("读取 {path} 失败: {e}").into())
}

fn parse_numbers(path: &str) -> Result<Vec<u32>, Box<dyn Error>> {
    let text = load(path)?; // Box<dyn Error> 之间 ? 直接传
    text.lines().enumerate().map(|(i, line)| {
        line.trim().parse::<u32>()
            .map_err(|e| format!("{path} 第 {} 行不是数字: {e}", i + 1).into())
    }).collect()
}
```

实测输出（三个文件：正常 / 坏行 / 不存在）：

```text
OK   /tmp/ph11-ex04-ok.txt -> [10, 20, 30]
ERR  /tmp/ph11-ex04-bad.txt -> "/tmp/ph11-ex04-bad.txt 第 2 行不是数字: invalid digit found in string"
ERR  /tmp/ph11-ex04-missing.txt -> "读取 /tmp/ph11-ex04-missing.txt 失败: No such file or directory (os error 2)"
```

要点与坑：

- **上下文是「消息文本」**：`format!(...).into()` 把 String 装箱成 `Box<dyn Error>`——注意 **String 装箱没有 `source()` 层**（String 实现 Error 但 source 为 None），错误链打印只有一层，上下文全在消息里。要多层结构化链，用自定义 Error 类型（3.3）或 anyhow（3.5）。
- **`main() -> Result<(), Box<dyn Error>>` 的退出行为（已实测）**：失败时运行时向 stderr 打印一行 `Error: "..."`（Debug 格式，String 带引号）并以退出码 1 结束；成功返回 `Ok(())` 退出码 0——`?` 一路传到 main 是最省事的「入口聚合」写法。
- **开集 vs 闭集**：`Box<dyn Error>` 调用方无法按类型分支处理（只能 Display/source），具体枚举可以 `match` 穷尽——「库用具体枚举、应用入口用 Box/anyhow」的分工见 4.3 的对比表。

### 3.5 thiserror 与 anyhow（生态讲解，未在本环境验证）

**`thiserror`** 用 `#[derive(thiserror::Error)]` 自动生成 `Display`、`Error`、`source()`、`From` 的实现（编译期展开，零运行时开销）——roadmap 示例即最小形态：

```rust
// roadmap 示例：thiserror 派生错误枚举（生态讲解，未在本环境验证（需第三方 crate：thiserror））
#[derive(Debug, thiserror::Error)]
enum AppError {
    #[error("invalid input: {0}")]
    InvalidInput(String),
}
```

- **格式串语法**：`{0}` 引用元组字段，`{name}` 引用具名字段；`#[source]` 字段自动实现 `source()`，`#[from]` 字段自动生成 `From<该类型>`——「三步走」的样板由 derive 代写，错误模型本质不变。
- **库代码为什么用它**：枚举是「闭集」，调用方可以 `match` 穷尽失败模式做分支处理；`thiserror` 只省样板，不改变错误模型。

**`anyhow`** 提供 `anyhow::Result<T>`（= `Result<T, anyhow::Error>`）与 `Context` trait：`anyhow::Error` 内部是 `Box<dyn Error + Send + Sync + 'static>` + backtrace + chain 迭代器，任何错误都能装进去；`.context(...)`/`.with_context(...)` 在 `Result`/`Option` 上附加「做什么时出错」的现场信息（`with_context` 接收闭包，只在出错时构造字符串）：

```rust
// 生态讲解，未在本环境验证（需第三方 crate：anyhow）
use anyhow::{Context, Result};

fn load(path: &str) -> Result<String> {
    let text = std::fs::read_to_string(path)
        .with_context(|| format!("读取配置文件 {path}"))?;
    Ok(text)
}
```

- **应用代码为什么用它**：应用关心「在哪一步失败」多于「失败的具体类型」；入口处 `{:?}` 打印整条错误链（外层消息 + `Caused by:` 逐层一行，这是 anyhow 的打印格式，等价于 3.3 的 `source()` 遍历）。`bail!`/`ensure!` 可在函数中间「提前失败」。
- **坑：不要在库的公开 API 返回 `anyhow::Error`**——调用方无法分支处理；原则是「库用具体枚举、应用入口用 anyhow」，错误类型在边界处转换（`map_err` 或 `?` + `From`）。

### 3.6 panic 与 recover 边界（catch_unwind / Mutex 中毒）

**panic 与 Result 的分工是错误模型设计的第一步**：panic = 不可恢复的不变量破坏（程序员错误、契约违反，如 `expect("...")`）；Result = 可恢复的预期失败（用户输入、I/O）。panic 默认走 **unwind**：沿调用栈展开，逐层 drop 局部变量（运行析构、释放 `MutexGuard` 等 RAII 资源），触发 panic hook（默认打印到 stderr），`catch_unwind` 可截获（`UnwindSafe` 约束防止捕获已破坏不变量）。panic 消息格式（已实测）：

```text
thread 'main' (PID) panicked at <文件>:<行>:<列>:
<消息>
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
```

`unwrap` 在 `Err` 上的 panic 消息（已实测）：`called `Result::unwrap()` on an `Err` value: "parse failed"`。

**`Mutex` 中毒（poisoned）** 是 panic 与共享状态交汇的产物（承接 ph10 伏笔）：持锁线程 panic 展开时，guard 的 `Drop` 把锁标记为中毒（内部 `poisoned: AtomicBool`），后续 `lock()` 返回 `Err`，消息实测为 `poisoned lock: another task failed inside`。工程化恢复：**日志记录后 `PoisonError::into_inner()` 取回 `MutexGuard` 读数据——数据本身未被破坏**（ph10 里 `lock().unwrap()` 会因此直接 panic，本阶段教显式处理）。`panic = "abort"`（Cargo.toml `[profile.*]` 配置）直接中止进程：不运行析构、二进制更小、行为可预测，代价是无法捕获、资源不清理。

### 3.7 tracing/log（生态讲解，未在本环境验证）

roadmap 学习内容「tracing/log 日志」。**`tracing`** 提供五个级别宏（`trace!`/`debug!`/`info!`/`warn!`/`error!`）与 **span**（有开始有结束的作用域上下文）：`span!(Level::INFO, "process", id = 7)` 创建 span、`enter()` 返回 guard（离开作用域自动退出），event 记录结构化字段（`%x` 用 Display、`?x` 用 Debug 格式化）。要点（未在本环境验证，需第三方 crate：tracing/tracing-subscriber）：

- **span vs event**：span 覆盖一段代码（可嵌套、子 span 继承父 span 字段）；event 是时间点上的单条记录，挂在当前 span 栈下。`#[instrument]` 属性可自动为函数包 span（ph12 中跨 `.await` 保持上下文的关键）。
- **与 `log` 的关系**：`log`（2014 年以来的门面 crate）只有级别与文本；`tracing` 是它的替代（span + 结构化字段），可桥接。
- **敏感信息防线**：字段是显式 key=value，审计「哪些字段进了日志」比审字符串拼接容易得多；配合 `Display` 实现里不打印密码/令牌，构成「日志不泄露敏感信息」的工程红线（对应 roadmap 阶段验收）。
- **坑：忘记 `init()`**——没有 subscriber 时宏是空操作，日志静默丢失且不报错。

### 3.8 单元测试与集成测试

roadmap 学习内容「单元测试与集成测试」。Rust 的测试是「代码内嵌」的：`#[cfg(test)] mod tests` 里的 `#[test]` 函数由测试 harness 执行，`#[should_panic(expected = "...")]` 验证契约性 panic，测试函数也可以返回 `Result<(), E>`（`Err` 时 `?` 传播、测试失败并打印错误）。跑法两种：cargo 项目用 `cargo test`（ph06 已讲），单文件用 `rustc --edition 2021 --test 文件.rs -o /tmp/t && /tmp/t`（本阶段练习 5 与阶段项目即用此法，已实测：练习 5 六个用例、项目八个用例全部通过，`test result: ok. N passed; 0 failed`）：

```rust
// 练习 5 的骨架：单元测试（正常路径 + 异常路径 + panic 契约），详见 exercises/sol-05-parser-tests.rs（已验证）
#[cfg(test)]
mod tests {
    #[test]
    fn parse_line_ok() { /* 正常路径：断言返回值 */ }

    #[test]
    fn parse_line_missing_equals() { /* 异常路径：断言错误枚举值 */ }

    #[test]
    fn parse_config_via_result() -> Result<(), ParseError> { /* Result 返回测试：? 传播 */ }

    #[test]
    #[should_panic(expected = "config text must be valid")]
    fn checked_panics_on_bad_input() { /* panic 契约 */ }
}
```

要点与坑：

- **测试金字塔**（roadmap 必会概念）：单元测试多而快（测内部逻辑与失败模式）、集成测试走公开 API（测契约，`tests/` 目录）、端到端测试少而慢；正常路径和异常路径都要覆盖。
- **错误枚举实现 `PartialEq, Eq`** 让 `assert_eq!(err, ParseError::MissingEquals(...))` 直接对比失败模式——测试断言的是「错误是什么」，不只是「是不是 Err」。

## 4. 底层原理

### 4.1 Result\<T, E\> 的表示与 ? 的展开

`Result<T, E>` 是一个枚举（`Ok(T)`/`Err(E)`），布局遵循「最大变体 + 判别位」规则；当某个变体的负载存在 **niche**（如 `&T` 不能为 null、`Box` 内部是指针）时，编译器把判别位塞进 niche——`Result<&T, E>` 在 `E` 不大于指针宽度时与 `&T` **等大**，错误处理不额外占内存。`x?` 编译期展开为 `match x { Ok(v) => v, Err(e) => return Err(From::from(e)) }`，与手写 `match` 的机器码一致、**零运行时开销**。`?` 的 `From` 转换让「每层函数返回自己的错误类型、底层错误自动包装」成为可能——这是分层错误模型的编译期基础：底层 `io::Error` 经 `From` 逐层变成中间层、入口层的具体错误（见 3.2 的 `PortError`），签名保持精确，传播保持简洁。

### 4.2 错误链：source() 如何串起底层原因

`Error::source()` 返回 `Option<&(dyn Error + 'static)>`，每一层形成单向链表：**Display 描述「这一层发生了什么」，source 指回「底层为什么失败」**。`thiserror` 的 `#[source]`/`#[from]`、`anyhow` 的 `context` 都在维护这条链：anyhow 的 `{:?}` 按「外层消息 + `Caused by:`」输出，纯 std 的等价打印是 `source()` 逐层遍历（3.3 已给实测输出——场景 A 两层：`第 2 行不是合法数字...` → `invalid digit found in string`）。设计准则：Display 写「操作 + 输入」（用户可读、可定位），source 链写「原因链」（开发者可追）；不要在某一层重复底层已说的信息，也不要把根因藏进 Display 字符串而不走 `source()`。

### 4.3 Box\<dyn Error\>：动态分发与类型擦除

`dyn Error` 是 **trait 对象**：胖指针（数据指针 + vtable 指针），具体类型被擦除，`Box<dyn Error>` 固定为两个指针宽。它与具体枚举的分工是错误模型的核心：

| 维度 | 具体枚举（闭集） | `Box<dyn Error>`（开集） |
|------|----------------|-------------------------|
| 变体集合 | 编译期已知，`match` 可穷尽 | 任意实现 `Error` 的类型 |
| 调用方能做什么 | 按变体分支处理、提取字段 | 只能 `Display`/`source()`/`provide()` |
| 典型场景 | 库的公开 API | 应用入口、聚合层 |
| 转换成本 | 编译期静态分发 | 运行时 vtable 动态分发（极小） |

`anyhow::Error` 内部就是 `Box<dyn Error + Send + Sync + 'static>` + backtrace + chain 迭代器：`Send + Sync` 是为了错误能跨线程移动（ph12 中任务返回的错误要在任务间传递）——「任何错误都能装进去」与「调用方无法分支处理」是一体两面，这正是「库/应用分工」的底层原因。

### 4.4 panic 与 unwind/abort（Mutex 中毒的底层机制）

panic 默认走 **unwind**：沿调用栈展开，逐层 drop 局部变量（运行析构、释放 `MutexGuard` 等 RAII 资源），触发 panic hook（默认打印到 stderr，消息格式见 3.6 实测），`catch_unwind` 可截获（`UnwindSafe` 约束防止捕获已破坏不变量）。`panic = "abort"` 直接中止进程：不运行析构、二进制更小、行为可预测，代价是无法捕获、资源不清理。**`Mutex` 中毒**正是 panic 与共享状态交汇的产物：持锁线程 panic 展开时，guard 的 `Drop` 把锁标记为中毒（内部 `poisoned: AtomicBool`），后续 `lock()` 返回 `PoisonError`——数据本身从未被破坏（锁保护的是访问，不是内容），所以 `into_inner()` 能安全取回。工程上「中毒即丢弃」还是「记录后取回」，取决于业务对数据一致性的容忍度：不可变缓存类数据（如示例 5 的 `42`）直接取回；聚合中的中间状态宁可重建。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 解析配置/输入，需要区分失败模式（缺字段/类型错/越界） | 自定义错误枚举 + `From`（3.2、示例 2、练习 2） |
| 库的公开 API 返回精确错误（解析器、配置加载） | 自定义错误枚举 + `thiserror`（3.2、3.5） |
| CLI / 服务入口聚合错误，告诉用户「哪一步、哪个文件、哪一行」 | `Box<dyn Error>` 上下文包装 + 错误链打印（3.4、示例 4、阶段项目） |
| 批量尝试 / 默认值 / 链式「可能失败」的步骤 | 组合子 map/and_then/or_else/ok_or_else/?（3.1、示例 1、练习 1） |
| 共享状态被 panic 污染后的恢复 | `Mutex` 中毒检测 + `PoisonError::into_inner()`（3.6、4.4、示例 5、练习 4） |
| 排查线上问题（请求级日志、耗时追踪） | `tracing` span + 结构化字段（3.7，未在本环境验证） |
| 守护核心逻辑正确性 | 单元测试 + 集成测试，正常/异常路径（3.8、练习 5、阶段项目） |

**不适合**此阶段的事项（属于后续阶段，这里不展开）：

- 异步编程（ph12 并发与异步阶段，目录待建）：`?` 跨 `.await`、任务取消与超时、`JoinError`——本阶段只在线程边界（`thread::spawn` 的 `JoinHandle`）体会错误跨线程传递。
- 文件、网络与系统编程的系统化错误处理（ph13 文件网络与系统编程阶段，目录待建）：`std::fs` 全套、TCP/UDP 错误码与重试策略——本阶段只用 `std::fs::read_to_string` 演示 I/O 错误的上下文化。
- unsafe 与裸指针（ph14 Unsafe Rust 与安全抽象阶段，目录待建）：错误模型的安全边界不需要 `unsafe` 参与。

## 6. 代码示例

本节展示完整可运行示例，完整文件在 [`examples/`](./examples/) 目录，全部为零第三方依赖的单文件（错误处理全在 `std`），可用 `rustc --edition 2021 -D warnings` 直接编译运行（已验证：rustc 1.92.0，编译零警告；编译产物输出 /tmp，仓库无二进制残留）。

> 运行前提：示例 4 带 `--fail` 运行会故意让 main 返回错误、退出码 1；示例 5 的三处 panic 都被 `catch_unwind` 包住不会崩溃，但 stderr 会打印被捕获 panic 的钩子输出——详见各文件头部注释与 examples/README.md。

### 示例 1：Option/Result 组合子（map / and_then / or_else / ok_or_else / ?）

```rust
// examples/ex01-option-result-combinators.rs —— Option/Result 组合子（map/and_then/or_else/ok_or_else/?），主文档第 6 章示例 1
// 说明：Option/Result 组合子（map/and_then/or_else/ok_or_else/?）。
//       组合子把「分支处理」压缩成链式调用；? 则让错误传播一行完成。
//       本示例聚焦 ph04 Option/Result 基础之上的组合子用法（ph04 只用到 match 与 ?）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex01-option-result-combinators.rs -o /tmp/ex01
// 运行：/tmp/ex01
// 验证状态：已验证（编译零警告；以下输出为实测结果）

fn main() {
    // ===== Result 组合子 =====
    let r: Result<u32, &str> = Ok(42);
    println!("map Ok    = {:?}", r.map(|v| v * 2)); // Ok(84)：只改 Ok 里的值
    let r2: Result<u32, &str> = Err("boom");
    println!("map Err   = {:?}", r2.map(|v| v * 2)); // Err("boom")：错误原样穿过

    // and_then：链式执行「可能失败」的下一步（flatten 后 map）——两段都可能 Err
    let s: Result<&str, &str> = Ok("42");
    println!("and_then  = {:?}", s.and_then(|t| t.parse::<i32>().map_err(|_| "parse fail"))); // Ok(42)

    // or_else：失败时走替代路径（闭包拿到错误值，可记录后再换路）
    let e: Result<u32, &str> = Err("not found");
    println!("or_else   = {:?}", e.or_else(|msg| { println!("  (记录: {msg})"); Ok::<u32, &str>(7) })); // Ok(7)

    // ok_or_else + ?：Option 转 Result——「可能没有」升级为「可能出错」，附带错误消息
    let o: Option<u32> = None;
    println!("ok_or_else = {:?}", o.ok_or_else(|| "missing value")); // Err("missing value")

    // ===== Option 组合子 =====
    let some: Option<i32> = Some(5);
    let none: Option<i32> = None;
    println!("opt map     = {:?}", some.map(|v| v + 1));        // Some(6)
    println!("opt and_then= {:?}", some.and_then(|v| if v > 3 { Some(v * 2) } else { None })); // Some(10)
    println!("opt or_else = {:?}", none.or_else(|| Some(99)));  // Some(99)
    println!("opt unwrap_or = {}", none.unwrap_or(0));          // 0（安全取默认值，不 panic）

    // ===== 组合子 + ? 的真实组合：解析 "key=value" 配置行 =====
    // 返回 Result 而非 Option——失败原因（哪一行、缺什么）比「没有值」更有信息量。
    for line in ["host = 127.0.0.1", "no-equals-here", "debug = true"] {
        match parse_cfg_line(line) {
            Ok((k, v)) => println!("OK   {line:18} -> {k} = {v}"),
            Err(e) => println!("ERR  {line:18} -> {e}"),
        }
    }
}

fn parse_cfg_line(line: &str) -> Result<(String, String), String> {
    let (k, v) = line
        .split_once('=')
        .ok_or_else(|| format!("缺少 '=' 分隔符: {line:?}"))?; // Option -> Result（ok_or_else + ?）
    Ok((k.trim().to_string(), v.trim().to_string()))
}
```

实测输出：

```text
map Ok    = Ok(84)
map Err   = Err("boom")
and_then  = Ok(42)
  (记录: not found)
or_else   = Ok(7)
ok_or_else = Err("missing value")
opt map     = Some(6)
opt and_then= Some(10)
opt or_else = Some(99)
opt unwrap_or = 0
OK   host = 127.0.0.1   -> host = 127.0.0.1
ERR  no-equals-here     -> 缺少 '=' 分隔符: "no-equals-here"
OK   debug = true       -> debug = true
```

要点与坑：

- **组合子 vs 嵌套 match**：`lookup` 类「尝试多个输入、短路返回」的逻辑用 `find_map` + 组合子比嵌套 `match` 可读得多（练习 1 要求重构）；`or_else` 的闭包能拿到错误值——「记录一笔再换路」是它的典型用法。
- **`ok_or_else` 是惰性的**：只在 `None` 时构造错误消息；`ok_or`（非惰性）在 `Some` 路径也求值参数，能避免就不用。

### 示例 2：自定义错误类型 + From 转换（Display + Error + From 三步走）

```rust
// examples/ex02-custom-error-from.rs —— 自定义错误类型 + From 转换（Display + Error + From 三步走），主文档第 6 章示例 2
// 说明：自定义错误类型 + From 转换（纯 std 手写「三步走」：Display + Error + From）。
//       ? 运算符的 From 自动转换让 ParseIntError 无缝变成 PortError；
//       source() 暴露底层原因（错误链的第一环）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex02-custom-error-from.rs -o /tmp/ex02
// 运行：/tmp/ex02
// 验证状态：已验证（编译零警告；输出、Debug 与错误链遍历均为实测结果）

use std::error::Error;
use std::fmt;
use std::num::ParseIntError;

// 自定义错误枚举：每个变体是一种失败模式，闭集——调用方可以 match 穷尽
#[derive(Debug)]
enum PortError {
    MissingColon(String),   // 没有 ":" 分隔符（携带输入原文）
    BadPort(ParseIntError), // 端口不是数字（包装标准库错误，错误链的第一环）
    OutOfRange(u16),        // 端口超出 1-65535
}

// 第一步：Display——写「给人看的消息」，每条都定位到具体输入
impl fmt::Display for PortError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            PortError::MissingColon(s) => write!(f, "缺少冒号分隔符: {s:?}"),
            PortError::BadPort(e) => write!(f, "端口号不是数字: {e}"),
            PortError::OutOfRange(p) => write!(f, "端口号 {p} 超出 1-65535"),
        }
    }
}

// 第二步：Error——进错误链；source() 只对「包装了底层错误」的变体返回 Some
impl Error for PortError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            PortError::BadPort(e) => Some(e), // 暴露底层 ParseIntError
            _ => None,
        }
    }
}

// 第三步：From——让 `?` 能把 ParseIntError 自动转成 PortError（编译期零开销）
impl From<ParseIntError> for PortError {
    fn from(e: ParseIntError) -> Self {
        PortError::BadPort(e)
    }
}

fn parse_addr(s: &str) -> Result<(String, u16), PortError> {
    let (host, port) = s
        .split_once(':')
        .ok_or_else(|| PortError::MissingColon(s.to_string()))?; // ok_or_else 手动构造错误
    let port: u16 = port.parse()?; // ParseIntError -> PortError：走 From 自动转换
    if port == 0 {
        return Err(PortError::OutOfRange(port)); // 语义校验失败：直接返回
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

    // Debug 输出（开发者视角，含内部结构）
    let err = parse_addr("localhost:abc").unwrap_err();
    println!("Debug = {err:?}");

    // 错误链遍历：source() 逐层走到根因（Display 写「这一层」，source 指「底层」）
    let mut cur: Option<&(dyn Error + 'static)> = Some(&err);
    while let Some(e) = cur {
        println!("链层: {e}");
        cur = e.source();
    }
}
```

实测输出：

```text
OK   127.0.0.1:8080 -> 127.0.0.1:8080
ERR  localhost:abc  -> 端口号不是数字: invalid digit found in string
ERR  no-colon-here  -> 缺少冒号分隔符: "no-colon-here"
ERR  127.0.0.1:0    -> 端口号 0 超出 1-65535
Debug = BadPort(ParseIntError { kind: InvalidDigit })
链层: 端口号不是数字: invalid digit found in string
链层: invalid digit found in string
```

要点与坑：

- **每条错误消息都定位到具体输入**（哪个地址、缺什么、哪个值越界）——对应阶段验收「错误信息能定位问题」；`?` 的两处使用分别演示 `ok_or_else` 与 `From` 自动转换。
- **Debug 与 Display 的分工在这里最直观**：Display 是用户看到的一行，Debug 是开发者看到的结构（`ParseIntError { kind: InvalidDigit }`）；链遍历从 Display 消息逐层走到根因。

### 示例 3：Error trait 实现（Display + source）与错误链打印

```rust
// examples/ex03-error-trait-source.rs —— Error trait 实现（Display + source）与错误链打印，主文档第 6 章示例 3
// 说明：Error trait 实现（Display + source）与错误链。
//       两个变体都实现 source()：Io 指回 io::Error、Parse 指回 ParseIntError；
//       错误链打印用「source() 逐层遍历」（纯 std 的标准做法，输出已实测）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex03-error-trait-source.rs -o /tmp/ex03
// 运行：/tmp/ex03
// 验证状态：已验证（编译零警告；错误链输出为实测结果）

use std::error::Error;
use std::fmt;
use std::num::ParseIntError;

// 错误枚举：Io（I/O 失败，包装 io::Error）+ Parse（解析失败，带行号定位）
#[derive(Debug)]
enum ScoreError {
    Io(std::io::Error),
    Parse { line: usize, source: ParseIntError },
}

// Display：每条消息都定位到「哪个操作 + 哪个输入/行号」
impl fmt::Display for ScoreError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ScoreError::Io(e) => write!(f, "读取文件失败: {e}"),
            ScoreError::Parse { line, source } => write!(f, "第 {line} 行不是合法数字: {source}"),
        }
    }
}

// Error：两个变体都暴露底层原因——错误链的每一环都有来源
impl Error for ScoreError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            ScoreError::Io(e) => Some(e),
            ScoreError::Parse { source, .. } => Some(source),
        }
    }
}

// From：io::Error 可经 `?` 自动转成 ScoreError::Io
impl From<std::io::Error> for ScoreError {
    fn from(e: std::io::Error) -> Self {
        ScoreError::Io(e)
    }
}

// 逐行解析：行号错误手动 map_err 包装（要携带行号，From 的自动转换注入不了额外字段）
fn load_scores(path: &str) -> Result<Vec<u32>, ScoreError> {
    let text = std::fs::read_to_string(path)?; // io::Error -> ScoreError::Io（走 From）
    text.lines()
        .enumerate()
        .map(|(i, l)| {
            l.trim()
                .parse::<u32>()
                .map_err(|e| ScoreError::Parse { line: i + 1, source: e })
        })
        .collect() // Result<Vec<_>, ScoreError>：遇错短路
}

// 错误链打印：沿 source() 逐层走到根因（纯 std 做法；anyhow 的 {:?} 是生态封装，见主文档 3.5）
fn print_chain(err: &(dyn Error + 'static)) {
    let mut cur = Some(err);
    while let Some(e) = cur {
        println!("  {e}");
        cur = e.source();
    }
}

fn main() {
    // 场景 A：内容不合法 -> 错误链带上「第几行」
    std::fs::write("/tmp/ph11-ex03-scores.txt", "90\nabc\n60\n").unwrap();
    let err = load_scores("/tmp/ph11-ex03-scores.txt").unwrap_err();
    println!("场景 A（解析失败）: {err}");
    println!("错误链（source 逐层）:");
    print_chain(&err);

    // 场景 B：文件不存在 -> 错误链带上「哪个文件」
    let err2 = load_scores("/tmp/ph11-ex03-missing.txt").unwrap_err();
    println!("\n场景 B（文件不存在）: {err2}");
    println!("错误链（source 逐层）:");
    print_chain(&err2);
}
```

实测输出（同 3.3 的链打印）：

```text
场景 A（解析失败）: 第 2 行不是合法数字: invalid digit found in string
错误链（source 逐层）:
  第 2 行不是合法数字: invalid digit found in string
  invalid digit found in string

场景 B（文件不存在）: 读取文件失败: No such file or directory (os error 2)
错误链（source 逐层）:
  读取文件失败: No such file or directory (os error 2)
  No such file or directory (os error 2)
```

要点与坑：

- **`#[from]` 与手动 `map_err` 并存**（对比 thiserror 版本 3.5）：`Io` 走自动转换，`Parse` 手动包装——因为要携带行号（`From` 的自动转换注入不了额外字段）；错误消息精确到行号，是「库代码偏向具体错误」的体现。
- **错误链只在「包装了底层错误」的变体上有第二层**：场景 A 链 2 层（Parse → ParseIntError），场景 B 链 2 层（Io → io::Error）；没有底层原因的变体（如 3.2 的 `MissingColon`）链只有 1 层。

### 示例 4：错误上下文包装（Box\<dyn Error\>）与 main 退出行为

```rust
// examples/ex04-box-dyn-error-context.rs —— 错误上下文包装（Box<dyn Error>），主文档第 6 章示例 4
// 说明：错误上下文包装（Box<dyn Error>）。
//       Box<dyn Error> 是「开集」：任何实现 Error 的错误都能装进去（类型擦除），
//       map_err 把上下文信息包进 String 再 .into() 装箱；层与层之间用 ? 直接传播。
//       运行前提：普通运行（/tmp/ex04）打印三组场景、退出码 0；
//       带 --fail 运行（/tmp/ex04 --fail）故意让 main 返回 Err——运行时打印
//       `Error: "..."` 到 stderr 并以退出码 1 结束（演示 main -> Result 的退出行为）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex04-box-dyn-error-context.rs -o /tmp/ex04
// 运行：/tmp/ex04  或  /tmp/ex04 --fail
// 验证状态：已验证（编译零警告；两种运行模式的输出均为实测结果）

use std::error::Error;

// 第一层：读文件，失败时把「哪个文件」包进错误上下文
fn load(path: &str) -> Result<String, Box<dyn Error>> {
    std::fs::read_to_string(path).map_err(|e| format!("读取 {path} 失败: {e}").into())
}

// 第二层：逐行解析，失败时把「哪一行」包进上下文；load 的错误经 ? 直接向上传播
fn parse_numbers(path: &str) -> Result<Vec<u32>, Box<dyn Error>> {
    let text = load(path)?; // Box<dyn Error> 与 Box<dyn Error> 之间 ? 直接传
    text.lines()
        .enumerate()
        .map(|(i, line)| {
            line.trim()
                .parse::<u32>()
                .map_err(|e| format!("{path} 第 {} 行不是数字: {e}", i + 1).into())
        })
        .collect()
}

fn main() -> Result<(), Box<dyn Error>> {
    std::fs::write("/tmp/ph11-ex04-ok.txt", "10\n20\n30\n").unwrap();
    std::fs::write("/tmp/ph11-ex04-bad.txt", "10\nabc\n30\n").unwrap();

    for p in ["/tmp/ph11-ex04-ok.txt", "/tmp/ph11-ex04-bad.txt", "/tmp/ph11-ex04-missing.txt"] {
        match parse_numbers(p) {
            Ok(v) => println!("OK   {p} -> {v:?}"),
            Err(e) => println!("ERR  {p} -> {e:?}"),
        }
    }

    // --fail 模式：故意让 ? 在 main 里失败——运行时打印 Error: "..." 并以退出码 1 结束
    if std::env::args().any(|a| a == "--fail") {
        let _text = load("/tmp/ph11-ex04-missing.txt")?;
    }
    Ok(())
}
```

实测输出（普通运行）：

```text
OK   /tmp/ph11-ex04-ok.txt -> [10, 20, 30]
ERR  /tmp/ph11-ex04-bad.txt -> "/tmp/ph11-ex04-bad.txt 第 2 行不是数字: invalid digit found in string"
ERR  /tmp/ph11-ex04-missing.txt -> "读取 /tmp/ph11-ex04-missing.txt 失败: No such file or directory (os error 2)"
```

`/tmp/ex04 --fail` 运行：同样先打印上面三行，然后 stderr 打印一行 `Error: "读取 /tmp/ph11-ex04-missing.txt 失败: No such file or directory (os error 2)"`，退出码 1（`main -> Result` 失败时的运行时行为，已实测）。

要点与坑：

- **上下文从外到内读**：最外层是入口操作（`读取 ... 失败`），`?` 把内层错误原样带出；`map_err` 只给「自己这一步」加信息，不吞掉底层消息。
- **`Box<dyn Error>` 的 `{:?}` 只显示顶层消息**（String 带引号）——没有 anyhow 的 `Caused by:` 链式打印；纯 std 要多层结构化链，用自定义 Error 类型（示例 3）。

### 示例 5：panic 与 recover 边界（catch_unwind / Mutex 中毒恢复）

```rust
// examples/ex05-panic-recover-boundary.rs —— panic 与 recover 边界（catch_unwind / Mutex 中毒恢复），主文档第 6 章示例 5
// 说明：panic 与 recover 边界。
//       panic = 不可恢复的不变量破坏（unwind 逐层 drop 局部变量）；recover 手段：
//       catch_unwind（截获 panic，UnwindSafe 约束）、Mutex 中毒恢复（PoisonError +
//       into_inner 取回数据）。运行本文件时 stderr 会打印 3 行 panic 消息——
//       这是被 catch_unwind 捕获的 panic 的钩子输出（panic hook 仍会打印），
//       程序本身退出码 0，正常继续。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex05-panic-recover-boundary.rs -o /tmp/ex05
// 运行：/tmp/ex05
// 验证状态：已验证（编译零警告；panic 消息、中毒消息均为实测文本）

use std::panic;

fn main() {
    // ===== recover 1：catch_unwind 截获 panic，拿回 payload =====
    let result = panic::catch_unwind(|| {
        panic!("配置缺失: app.toml"); // 故意 panic（已用 catch_unwind 包住，不会崩）
    });
    match result {
        Ok(_) => println!("未 panic"),
        Err(payload) => {
            let msg = payload
                .downcast_ref::<&str>()
                .copied()
                .unwrap_or("<非字符串 payload>");
            println!("catch 到 panic，消息 = {msg:?}"); // "配置缺失: app.toml"
        }
    }

    // ===== recover 2：unwrap 在 Err 上 panic，消息含错误值 =====
    let r2 = panic::catch_unwind(|| {
        let x: Result<u32, &str> = Err("parse failed");
        let _ = x.unwrap(); // 故意 unwrap（已用 catch_unwind 包住）
    });
    println!("unwrap Err 是否 panic: {}", r2.is_err()); // true

    // ===== recover 3：Mutex 中毒（poisoned）的恢复 =====
    // 持锁线程 panic -> guard 的 Drop 把锁标记为中毒 -> 后续 lock() 返回 Err。
    // 工程化处理：PoisonError::into_inner() 取回 MutexGuard 读数据（数据本身完好）。
    use std::sync::{Arc, Mutex};
    let m = Arc::new(Mutex::new(42u32));
    let m2 = Arc::clone(&m);
    let handle = std::thread::spawn(move || {
        let _guard = m2.lock().unwrap(); // guard 保持存活到 panic，Drop 时标记中毒
        panic!("持锁线程 panic");
    });
    let _ = handle.join();

    let lock_result = m.lock(); // 先绑定，避免 match 临时值生命周期问题（E0597 的坑）
    match lock_result {
        Ok(g) => println!("锁正常: {}", *g),
        Err(poisoned) => {
            println!("锁中毒: {}", poisoned); // poisoned lock: another task failed inside
            let inner = poisoned.into_inner(); // 取回 MutexGuard（数据未被破坏）
            println!("into_inner 取回数据: {}", *inner); // 42
        }
    }
}
```

实测输出（stdout）：

```text
catch 到 panic，消息 = "配置缺失: app.toml"
unwrap Err 是否 panic: true
锁中毒: poisoned lock: another task failed inside
into_inner 取回数据: 42
```

stderr 还会打印 3 行 panic 钩子输出（被捕获的 panic 仍会触发 panic hook，已实测）：

```text
thread 'main' (PID) panicked at ex05-panic-recover-boundary.rs:<行>:<列>:
配置缺失: app.toml
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace

thread 'main' (PID) panicked at ex05-panic-recover-boundary.rs:<行>:<列>:
called `Result::unwrap()` on an `Err` value: "parse failed"

thread '<unnamed>' (PID) panicked at ex05-panic-recover-boundary.rs:<行>:<列>:
持锁线程 panic
```

要点与坑：

- **catch_unwind 是「最后防线」**：生产代码应该优先让错误走 `Result`，`catch_unwind` 只用于「第三方代码可能 panic、不能让它带崩整个进程」的边界（如插件、任务池）。
- **panic hook 无法关闭式忽略**：被 `catch_unwind` 捕获的 panic 仍会打印钩子输出——这是正常行为，不是泄漏；真正要吞掉输出需自定义 `panic::set_hook`。
- **坑：`match m.lock() {...}` 直接写会撞 E0597**（临时值 `PoisonError` 持有 borrow 活到 match 结束）——先绑定 `let lock_result = m.lock();` 再 match（示例 5 与练习 4 都演示了这个写法）。

## 7. 总结

### 关键要点

1. **错误是值，不是异常**：`Result<T, E>` 把失败写进函数签名，编译器强制处理；`Option` 处理「可能没有」，`Result` 处理「可能出错」——组合子（`map`/`and_then`/`or_else`/`ok_or_else`/`?`）把分支处理压缩成链式调用。
2. **自定义错误三步 + `?` 的本质**：`Display`（给人看）+ `Error`（进错误链）+ `From`（让 `?` 转换）；`?` 展开为 `match` + `From::from` + `return`，编译期展开、零运行时开销——`From` 是「分层错误模型」的编译期基础。`?` 的返回类型约束错（非 Result/Option 函数、From 未实现、Option/Result 混用）全部报 E0277（已实测）。
3. **错误链**：`source()` 串起底层原因（Display 描述「这一层」，source 指回「底层」），纯 std 用 `source()` 逐层遍历打印，anyhow 的 `{:?}`/`Caused by:` 是生态封装；上下文包装（`Box<dyn Error>` + `map_err`）把「哪个文件、哪一行」逐层附加。
4. **库与应用分工**：库代码偏向具体错误（枚举，调用方可 `match` 分支处理），应用代码可使用上下文错误（`Box<dyn Error>`/`anyhow`，关心「在哪一步失败」）；错误类型在边界转换。
5. **panic 与 Result 分工**：panic = 不可恢复的契约破坏（消息格式与 `unwrap` panic 消息已实测），Result = 可恢复的预期失败；`catch_unwind` 是最后防线；`Mutex` 中毒的 `PoisonError` 显式处理（`into_inner()` 取回数据）承接 ph10 的伏笔——中毒消息实测为 `poisoned lock: another task failed inside`。
6. **测试守核心路径**：单元测试多而快（测内部逻辑与失败模式）、集成测试走公开 API（测契约）、端到端测试少而慢；正常路径和异常路径都要覆盖，`#[should_panic]` 验证契约性 panic，`Result` 返回测试让错误信息可读。
7. **生态讲解**：`thiserror`（派生错误枚举）、`anyhow`（上下文错误）、`tracing`（结构化日志）是纯 std 写法的进阶封装——本环境未安装验证，标注「未在本环境验证（需第三方 crate）」。

### 跨语言对比：错误处理

| 维度 | Rust | Go | Java | Python | C++ |
|------|------|----|------|--------|-----|
| 错误表示 | `Result<T, E>` 返回值 | 多返回值 `(T, error)` | 异常（受检/非受检） | 异常（`raise`/`try-except`） | 异常 + 错误码并存 |
| 是否强制处理 | 编译器强制（`Result` 必须处理） | 靠自觉（`_` 可忽略） | 受检异常编译期强制 | 运行时才暴露 | 不强制 |
| 错误类型 | 具体枚举 / `Box<dyn Error>` | `error` 接口（值） | `Exception` 类层次 | `BaseException` 类层次 | 类层次 + `errno` |
| 错误上下文 | `?` + `map_err`/`context` 链式附加 | `fmt.Errorf("%w")` 包装 | 异常链 `initCause` | `raise ... from` | 无标准链（自造） |
| 清理保证 | RAII：unwind 逐层 drop（析构/解锁） | `defer` | `finally` | `finally` / `with` | RAII / `finally` |

### 阶段验收清单

- [ ] 能说清 `panic` 与 `Result` 的分工，并能用 `catch_unwind` 与 `PoisonError::into_inner()` 处理恢复边界（含 Mutex 中毒消息文本）
- [ ] 能按「三步走」手写自定义错误枚举（`Display` + `Error` + `From`），让 `?` 自动转换标准库错误；错误消息定位到「哪个操作、哪个输入/文件/行号」
- [ ] 能用 `source()` 逐层打印错误链到根因，能区分「用户可读」（Display）与「开发者可追」（Debug/source）
- [ ] 能说出「库用具体枚举、应用用上下文错误（`Box<dyn Error>`/anyhow）」的分工及其底层原因（开集 vs 闭集）
- [ ] 能用组合子（`map`/`and_then`/`or_else`/`ok_or_else`/`?`）重构嵌套 `match`，并知道 `?` 的四类 E0277 编译错误与解法
- [ ] 能说明 `tracing` 的 span/event 与结构化字段如何支撑可观测性，理解「字段显式化 + `Display` 不打印敏感信息」是日志不泄露敏感信息的工程红线（3.7，未在本环境验证）
- [ ] 能用测试覆盖核心模块的正常路径与异常路径（`rustc --test` 单文件跑通，含 `#[should_panic]` 与 `Result` 返回测试）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 5 题，覆盖本章示例 1~5 的主题：

- 练习 1（★）：Option/Result 组合子重构——嵌套 match 改写成组合子链（对照示例 1）
- 练习 2（★★）：为解析模块定义错误枚举——`ConfigError` 三步走 + `?` 自动转换（roadmap 练习，对照示例 2）
- 练习 3（★★）：为 I/O 错误添加上下文——`Box<dyn Error>` 上下文包装 + 错误链打印（roadmap 练习，对照示例 4）
- 练习 4（★★★）：panic 与 recover 边界——`catch_unwind` + Mutex 中毒恢复（对照示例 5）
- 练习 5（★★★）：补充正常路径和异常路径测试——`rustc --test` 单文件跑 6 个用例（roadmap 练习，对照 3.8）

完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**可靠 CLI（成绩报告生成器）**——读取 `姓名,分数` 文本文件、解析校验、聚合输出报告，任何一步出错都给出「哪个文件、哪一行、什么值、底层原因」的可定位错误并退出码非 0（roadmap 推荐项目；零第三方依赖，单文件，含 8 个单元测试）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（编译零警告、8 个测试通过、三种退出码场景实测）

### 下一阶段

**ph12+（roadmap 第 12 节，目录待建）**：后续可深入「并发与异步」方向——本阶段是当前最后一个有目录的阶段，ph12~ph25 的阶段目录尚未建立（roadmap 见 `languages/rs/rust.md`）。本阶段建立的错误模型将延伸到异步世界：`?` 跨 `.await` 传播（`Future` 的错误类型要求 `Send`）、任务失败用 `JoinError`/`tokio::spawn` 的错误类型表达、超时与取消成为新的错误来源（`tokio::time::error::Elapsed`）；`tracing` 的 span 则天然跨 `.await` 保持请求级上下文（`#[instrument]`），错误与日志在异步链路里汇合——ph11 打下的「错误类型设计 + 恢复边界 + 测试」正是 ph12 并发正确性的地基。
