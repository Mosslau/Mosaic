# Rust Option 和 Result 阶段

> 从随意 unwrap 到类型安全的错误处理：Option 替代 null、Result 替代异常——编译器强制你在类型层面处理"没有值"和"出错了"两种情况，把运行时崩溃变成编译期错误。

## 1. 概述

Option 和 Result 阶段的定位是：**能判断何时用 Option 或 Result、用四种方式处理可能的失败（unwrap/expect/match/?）、用组合子链式转换值或错误类型，并在业务代码中避免无理由 panic**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| Option\<T\> | Some / None，空值显式化，编译器强制处理缺失情况 |
| Result\<T, E\> | Ok / Err，可恢复错误，错误变成返回值而非异常 |
| 四种处理方式 | unwrap（开发/原型）、expect（带错误消息）、match（完全控制）、?（传播给调用方） |
| ? 运算符 | 本质是 match + return Err，配合 From trait 自动转换错误类型 |
| Option 组合子 | map、and_then、unwrap_or、unwrap_or_else |
| Result 组合子 | map_err、and_then、ok() 转 Option |
| 类型转换 | copied()/cloned()、map_err 转换错误类型 |

**本阶段边界**：不展开自定义错误类型设计（ph07 trait）、thiserror/anyhow 库、panic/unwind 机制。枚举深度模式匹配在 **ph05 模式匹配与枚举阶段**。ph02 猜数字示例中用过的 `unwrap`/`expect`、ph03 `Vec::first()` 返回 `Option`——本阶段正式讲透。

## 2. 来源与演变

`Option<T>` 继承 ML/Haskell 的 `Maybe`/`Option` 类型——用一个带数据的枚举把"可能有值"编码进类型系统。`Result<T, E>` 来自函数式编程的 `Either` 和 Rust 自身对错误处理的设计选择：不用异常，而是让错误成为返回值，类型系统保证调用者必须处理。

核心哲学差异：C/Go 的错误码可以被调用方忽略；Java/C++ 异常是隐式控制流，调用方不知道函数可能抛什么；Rust 的 `Result<T, E>` 把错误可能性写进函数签名，编译器保证调用方必须处理。详细跨语言对照见第七节总结表。

本文示例以 **rustc 1.92.0**（edition 2021）为基线（本机验证工具链），`Option`/`Result`、`?` 运算符、组合子等语法在该版本长期稳定，示例全部零依赖，无需额外 crate。

## 3. 语法与参数

### 3.1 Option\<T\>：空值显式化

`Option<T>` 标准库定义只有两行，但它是 Rust 中最常用的枚举类型之一：

```rust
fn main() {
    let some_num: Option<i32> = Some(42);
    let _no_num: Option<i32> = None; // 演示 None 语法，未使用

    // 模式匹配解包
    match some_num {
        Some(v) => println!("value: {}", v),
        None => println!("no value"),
    }

    // Vec::first() 返回 Option——呼应 ph03
    let v = vec![10, 20, 30];
    let first = v.first(); // Option<&i32>
    println!("first: {:?}", first);
}
```

`Option<T>` 的核心价值：**类型签名本身告诉你"这里可能没有值"，编译器强制你处理两种情况**。不存在"忘记判空"——不处理 `None` 编译器就不通过。

### 3.2 Result\<T, E\>：错误变成返回值

`Result<T, E>` 把错误从隐式控制流（异常）变成显式返回值，函数签名直接声明"我可能失败"：

```rust
fn divide(a: i32, b: i32) -> Result<i32, String> {
    if b == 0 {
        Err(String::from("division by zero"))
    } else {
        Ok(a / b)
    }
}

fn main() {
    match divide(10, 2) {
        Ok(v) => println!("10 / 2 = {}", v),
        Err(e) => println!("error: {}", e),
    }

    match divide(10, 0) {
        Ok(v) => println!("result: {}", v),
        Err(e) => println!("error: {}", e),
    }
}
```

### 3.3 四种 unwrap 方式的选择矩阵

处理 `Option`/`Result` 有四种方式，选择取决于场景：

| 方式 | 行为 | 适用场景 | 失败后果 |
|------|------|---------|---------|
| `unwrap()` | 取出值，None/Err 时 panic | 原型、快速验证、测试 | 程序崩溃 |
| `expect(msg)` | 取出值，None/Err 时 panic + 自定义消息 | 开发期、"不可能失败"的断言 | 程序崩溃，带消息 |
| `match` | 分支处理 Some/None 或 Ok/Err | 需要分别处理两条路径 | 由你控制 |
| `?` | 取出值，Err 时提前 return Err | 错误传播给调用方 | 调用方获得 Err |

```rust
fn try_parse(s: &str) -> Result<i32, String> {
    s.parse::<i32>().map_err(|e| format!("'{}': {}", s, e))
}

fn main() {
    // unwrap —— 开发/原型阶段，失败即崩
    let _n = try_parse("42").unwrap();

    // expect —— 带错误消息的 unwrap
    let _n = try_parse("42").expect("hardcoded value should parse");

    // match —— 完全控制两条路径
    match try_parse("42") {
        Ok(v) => println!("parsed: {}", v),
        Err(e) => eprintln!("error: {}", e),
    }

    // ? —— 传播给调用方（见下节）
    println!("all four approaches demonstrated");
}
```

### 3.4 ? 运算符：match + return Err 的语法糖

`?` 是 `match` + `return Err(...)` 的简写。放在返回 `Result` 的函数中，遇到 `Err` 时立即返回，遇到 `Ok` 时提取值继续执行：

```rust
fn parse_and_double(s: &str) -> Result<i32, String> {
    let n: i32 = s.parse().map_err(|e| format!("parse: {}", e))?;
    Ok(n * 2)
}

fn main() {
    match parse_and_double("21") {
        Ok(v) => println!("21 * 2 = {}", v),
        Err(e) => eprintln!("error: {}", e),
    }
}
```

`?` 的本质展开（编译器实际生成的等价代码）：

```rust
fn main() {
    // let n = "21".parse::<i32>()?;
    // 编译器展开为：
    // let n = match "21".parse::<i32>() {
    //     Ok(v) => v,
    //     Err(e) => return Err(e.into()), // From trait 自动转换类型
    // };
    println!("? 展开为 match + return Err(From::from(err))");
}
```

关键点：`?` 会调用 `.into()` 对错误做自动类型转换（`From` trait），所以当函数返回 `Box<dyn Error>` 或自定义错误类型时，不同来源的错误可以自动适配。

### 3.5 Option 组合子

组合子让链式处理"可能有值"的逻辑变得干净——每一步返回 `None` 时整条链短路：

```rust
fn main() {
    let nums = vec![2, 4, 6];

    // map: Option<T> -> Option<U>，转换内部值
    let first = nums.first().map(|&x| x * 10);
    println!("first * 10: {:?}", first); // Some(20)

    // and_then: 链式调用，任一步 None 整链短路
    let found = nums.first().and_then(|&x| {
        if x % 2 == 0 { Some(x * 100) } else { None }
    });
    println!("found: {:?}", found); // Some(200)

    // unwrap_or: 提供默认值（急求值）
    let empty: Vec<i32> = vec![];
    let val = empty.first().unwrap_or(&0);
    println!("unwrap_or: {}", val); // 0

    // unwrap_or_else: 惰性默认值（仅 None 时计算闭包）
    let val = empty.first().unwrap_or_else(|| {
        // 这里可以做复杂计算，仅 None 时执行
        &42
    });
    println!("unwrap_or_else: {}", val); // 42
}
```

| 组合子 | 签名字面 | 行为 |
|--------|---------|------|
| `map(f)` | `Option<T>` -> `Option<U>` | `Some` 时转换值，`None` 保持 |
| `and_then(f)` | `Option<T>` -> `Option<U>` | `Some` 时调用 f（返回 Option），`None` 保持 |
| `unwrap_or(v)` | `Option<T>` -> `T` | `Some` 取值，`None` 返回 v |
| `unwrap_or_else(f)` | `Option<T>` -> `T` | `Some` 取值，`None` 调用 f（惰性） |

### 3.6 Result 组合子

Result 的组合子侧重错误转换和链式操作：

```rust
fn parse_port(s: &str) -> Result<u16, String> {
    s.parse::<u16>().map_err(|e| format!("invalid port '{}': {}", s, e))
}

fn check_range(port: u16) -> Result<u16, String> {
    if (1..=65535).contains(&port) { Ok(port) }
    else { Err(format!("port {} out of range (1-65535)", port)) }
}

fn main() {
    // and_then: 链式 Result，Err 时短路
    let port = parse_port("8080").and_then(check_range);
    println!("8080: {:?}", port);       // Ok(8080)
    println!("99999: {:?}", parse_port("99999").and_then(check_range)); // Err

    // ok(): Result -> Option，丢弃错误
    println!("abc as option: {:?}", parse_port("abc").ok()); // None

    // map_err: 转换错误类型
    println!("80: {:?}", parse_port("80")); // Ok(80)
}
```

### 3.7 类型转换

常见转换场景：

```rust
fn main() {
    let v = vec![String::from("hello"), String::from("world")];

    // Option<&String> -> Option<String> (cloned)
    let first: Option<String> = v.first().cloned();
    println!("first: {:?}", first);

    // Option<&i32> -> Option<i32> (copied, 仅 Copy 类型可用)
    let nums = vec![1, 2, 3];
    let first_num: Option<i32> = nums.first().copied();
    println!("first_num: {:?}", first_num);

    // Result<T, E> -> Result<T, F> (map_err 转换错误类型)
    let r: Result<i32, &str> = Ok(42);
    let r2: Result<i32, String> = r.map_err(|e| e.to_string());
    println!("r2: {:?}", r2);

    // Option<T> -> Result<T, E> (给 None 配上错误)
    let opt: Option<i32> = None;
    let res: Result<i32, &str> = opt.ok_or("missing value");
    println!("res: {:?}", res); // Err("missing value")
}
```

| 转换 | 方法 | 适用条件 |
|------|------|---------|
| `Option<&T>` -> `Option<T>` | `.cloned()` | T: Clone |
| `Option<&T>` -> `Option<T>` | `.copied()` | T: Copy |
| `Result<T, E>` -> `Result<T, F>` | `.map_err(f)` | f: E -> F |
| `Result<T, E>` -> `Option<T>` | `.ok()` | 丢弃错误 |
| `Option<T>` -> `Result<T, E>` | `.ok_or(err)` | 给 None 配错误值 |

## 4. 底层原理

### 4.1 Option 和 Result 是泛型枚举

标准库源码级别的定义（简化）：

```rust
fn main() {
    // Option/Result 就是普通枚举定义：
    // pub enum Option<T> { None, Some(T) }
    // pub enum Result<T, E> { Ok(T), Err(E) }
    let opt: Option<i32> = Some(42);
    let res: Result<i32, &str> = Ok(42);
    println!("{:?} {:?}", opt, res);
}
```

这就是普通的枚举——`Option` 和 `Result` 没有"魔法"。编译器能强制穷尽匹配，是因为 Rust 的 `match` 要求覆盖所有变体。

### 4.2 ? 展开：match + return + From

编译器把 `expr?` 展开为 `match expr { Ok(v) => v, Err(e) => return Err(From::from(e)) }`。`From::from(e)` 是自动错误类型转换的关键——`io::Error` 可通过 `?` 自动转为自定义错误类型（只要实现了 `From<io::Error>`）。

### 4.3 Try trait（进阶）

`?` 在 `std::ops::Try` trait 上定义（目前不稳定，但 `Option`/`Result` 已实现等效行为）。现阶段知道 `?` 作用于 `Option` 和 `Result` 即可，它本质是 trait 多态。

## 5. 使用场景

### 5.1 Option vs Result 选择

| 场景 | 用 Option | 用 Result |
|------|----------|----------|
| 查找可能不存在 | `fn find(&self, key: &K) -> Option<&V>` | — |
| 解析可能失败 | — | `fn parse(s: &str) -> Result<T, E>` |
| 配置项可缺失 | `Option<String>` 字段 | — |
| IO / 网络操作 | — | `Result<T, io::Error>` |
| 数学可能无定义 | `Option<f64>`（如 sqrt(-1)） | `Result<f64, MathError>`（需要原因时） |

**简单规则**：没有值是可预期的正常状态用 `Option`（查找不到）；出了问题是异常状态用 `Result`（文件读不了、解析失败）——`Result` 带着错误原因。

### 5.2 四种处理方式的场景选择

| 场景 | 推荐方式 | 理由 |
|------|---------|------|
| 原型/学习期/测试 | `unwrap()` | 简单直接，失败即发现问题 |
| "不可能失败"的断言 | `expect("why")` | 万一崩了消息比 bare panic 有用 |
| 库/模块公开 API | `?` 传播 | 把处理权交给调用方 |
| 必须分支处理（重试/降级） | `match` | 完全控制两条路径 |
| 提供合理默认值 | `unwrap_or` / `unwrap_or_else` | 优雅降级，不 panic |

核心原则：返回 `Result` 的函数用 `?` 传播；仅在逻辑保证不可能失败（如刚 push 后 pop）和测试中使用 `unwrap`。

## 6. 代码示例

> 本节每个示例的完整可运行文件在 [`examples/`](./examples/) 目录，验证环境 rustc 1.92.0，零第三方依赖，编译/运行命令见 examples/README.md。

### 示例 1：把随意 unwrap 改为 Result 返回

```rust
// examples/ex01-unwrap-to-result.rs —— 把随意 unwrap 改为 Result 返回
fn parse_and_validate(s: &str) -> Result<u16, String> {
    // 不良风格：s.parse::<u16>().unwrap() —— 解析失败直接 panic
    // 良好风格：用 ? 传播错误，交给调用方决定
    let port: u16 = s.parse().map_err(|e| format!("parse: {}", e))?;
    if port == 0 {
        return Err("port 0 is reserved".to_string());
    }
    Ok(port)
}

fn main() {
    match parse_and_validate("8080") {
        Ok(port) => println!("port: {}", port),
        Err(e) => eprintln!("error: {}", e),
    }
}
```

完整文件：`examples/ex01-unwrap-to-result.rs`

### 示例 2：用 Option 处理可选配置项

```rust
// examples/ex02-option-config.rs —— 用 Option 处理可选配置项
#[derive(Debug)]
#[allow(dead_code)]
struct AppConfig {
    host: String,
    port: u16,
    timeout_secs: Option<u32>,
    log_level: Option<String>,
}

impl AppConfig {
    fn new(host: &str, port: u16) -> Self {
        AppConfig { host: host.to_string(), port, timeout_secs: None, log_level: None }
    }

    fn effective_timeout(&self) -> u32 {
        self.timeout_secs.unwrap_or(30)
    }

    fn effective_log_level(&self) -> &str {
        self.log_level.as_deref().unwrap_or("info")
    }
}

fn main() {
    let mut cfg = AppConfig::new("localhost", 8080);
    println!("defaults: timeout={}s log={}", cfg.effective_timeout(), cfg.effective_log_level());

    cfg.timeout_secs = Some(10);
    cfg.log_level = Some(String::from("debug"));
    println!("updated: {:?}", cfg);
}
```

完整文件：`examples/ex02-option-config.rs`

### 示例 3：解析函数串联 ? 运算符

一组解析函数各自返回 `Result`，用 `?` 串联——Rust"管线式"数据处理的最常见模式：

```rust
// examples/ex03-parse-pipeline.rs —— 一组解析函数用 ? 串联
fn parse_port(s: &str) -> Result<u16, String> {
    s.parse::<u16>().map_err(|_| format!("'{}' is not a valid port number", s))
}

fn check_port_range(port: u16) -> Result<u16, String> {
    if port == 0 { Err("port 0 is reserved".to_string()) }
    else { Ok(port) }
}

fn resolve_service_port(service: &str) -> Result<u16, String> {
    match service {
        "http" => Ok(80), "https" => Ok(443), "ssh" => Ok(22),
        other => Err(format!("unknown service: {}", other)),
    }
}

fn get_port(input: &str) -> Result<u16, String> {
    if let Ok(num) = parse_port(input) { return check_port_range(num); }
    resolve_service_port(input) // 尝试解析为服务名
}

fn main() {
    for input in &["8080", "0", "https", "99999", "unknown"] {
        match get_port(input) {
            Ok(port) => println!("'{}' -> port {}", input, port),
            Err(e) => eprintln!("'{}' -> error: {}", input, e),
        }
    }
}
```

完整文件：`examples/ex03-parse-pipeline.rs`

### 示例 4：配置解析器——端口、超时、开关项

综合运用本阶段所有知识：Option 处理可选值、Result 处理可恢复错误、组合子链式转换、? 传播错误。

```rust
// examples/ex04-config-parser.rs —— 配置解析器：Option/Result 贯穿 + ? 传播
use std::collections::HashMap;

#[derive(Debug)]
#[allow(dead_code)]
struct Config {
    port: u16,
    timeout_secs: u32,
    debug_mode: bool,
    log_level: String,
}

fn parse_u16(raw: Option<&String>) -> Result<u16, String> {
    raw.ok_or_else(|| "missing value".to_string())
        .and_then(|s| s.parse::<u16>().map_err(|e| format!("invalid number: {}", e)))
}

fn parse_bool(raw: Option<&String>) -> Result<bool, String> {
    match raw.map(|s| s.as_str()) {
        Some("true") | Some("1") | Some("yes") => Ok(true),
        Some("false") | Some("0") | Some("no") => Ok(false),
        Some(other) => Err(format!("invalid bool: '{}'", other)),
        None => Ok(false),
    }
}

fn parse_config(raw: &HashMap<String, String>) -> Result<Config, String> {
    let port = parse_u16(raw.get("port"))?;
    let timeout_secs = parse_u16(raw.get("timeout")).map(|v| v as u32)?;
    let debug_mode = parse_bool(raw.get("debug"))?;
    let log_level = raw.get("log_level").cloned().unwrap_or_else(|| "info".to_string());
    if port == 0 {
        return Err("port cannot be 0".to_string());
    }
    Ok(Config { port, timeout_secs, debug_mode, log_level })
}

fn main() {
    let mut raw = HashMap::new();
    raw.insert("port".to_string(), "8080".to_string());
    raw.insert("timeout".to_string(), "30".to_string());
    raw.insert("debug".to_string(), "true".to_string());
    raw.insert("log_level".to_string(), "debug".to_string());
    println!("valid: {:?}", parse_config(&raw));

    // 缺失必需字段 port
    let mut incomplete = HashMap::new();
    incomplete.insert("timeout".to_string(), "10".to_string());
    println!("missing: {:?}", parse_config(&incomplete));
}
```

完整文件：`examples/ex04-config-parser.rs`

## 7. 总结

### 关键要点

1. **空值显式化**：`Option<T>` 把"可能有值"编码进类型，编译期强制处理缺失——不存在忘记判空。
2. **错误成返回值**：`Result<T, E>` 把错误变显式返回值，函数签名声明失败可能，编译期强制处理。
3. **四种处理方式**：`unwrap`（原型）| `expect`（带消息）| `match`（完全控制）| `?`（传播给调用方）。
4. **? = match + return Err(From::from(err))**：单字符替代 Go 的 `if err != nil`，利用 `From` trait 自动转换错误类型。
5. **组合子链式处理**：`map`/`and_then` 转换值、`map_err` 转换错误、`unwrap_or_else` 惰性默认值。
6. **本质是泛型枚举**：标准库两行 `enum` 定义，编译器靠穷尽匹配保证安全，没有魔法。
7. **避免无理由 panic**：返回 `Result` 的函数用 `?` 传播；仅逻辑保证不可能失败时用 `unwrap`。

### 跨语言对比：Option/Result

| 概念 | Rust | C | C++ | Go | Java |
|------|------|---|-----|----|------|
| 空值 | `Option<T>`（编译期强制） | `NULL`（运行时崩溃） | `std::optional` / `nullptr` | `nil`（零值可用） | `Optional<T>` / `null` |
| 可恢复错误 | `Result<T, E>`（签名声明） | 错误码 + errno | 异常 / `std::expected` | `error` 返回值 | 受检/非受检异常 |
| 错误传播 | `?` 单字符 | `if (ret < 0) return -1;` | 自动冒泡 / `.value()` | `if err != nil { return ... }` | `throws` / `throw` |
| 编译期强制 | 是（两种） | 否 | 异常不强制 | 否（可忽略 error） | 受检异常部分强制 |
| panic 语义 | `unwrap` 会 panic | `assert` / segfault | 未捕获异常 terminate | `panic` | 未捕获异常传播 |

### 阶段验收清单

- [ ] 能判断何时用 `Option<T>`（缺失正常）还是 `Result<T, E>`（带错误原因）
- [ ] 能解释 `?` 运算符如何传播错误（展开为 match + return Err）
- [ ] 能用 `map` / `and_then` / `unwrap_or_else` 链式处理 `Option`
- [ ] 能用 `map_err` 转换错误类型、`.ok()` 把 `Result` 转 `Option`
- [ ] 能把一组解析函数用 `?` 串联成完整管线
- [ ] 业务代码中避免无理由 `unwrap()`，用 `Result` 返回 + `?` 传播

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：猜数字输入改造、AppConfig 可选配置项、parse_endpoint 解析管线、unwrap 灾难现场、扩展配置解析器共 5 题，难度 ★~★★★。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**配置解析器**（读取端口、超时、开关项，输出结构化 `Config` 或带字段名的明确错误；示例 4 给出核心实现，项目扩展为带自定义错误类型与单元测试的完整 Cargo 工程）。建议完成练习后再动手。

- [ ] 完成 exercises 全部练习并对照参考实现复盘
- [ ] 独立完成 project 并通过其验收标准

### 下一阶段

[模式匹配与枚举阶段](../ph05-pattern-match/05-pattern-match.md)—— enum 携带数据、match 穷尽匹配、if let/while let、matches! 宏、切片和范围模式。
