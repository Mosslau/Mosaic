# Rust 模式匹配与枚举阶段

> 从 match 穷尽匹配到 enum 状态建模：编译器强制你处理每一种情况，把"忘记处理"从运行时 bug 变成编译期错误——这是 Rust 类型系统最强大的安全特性之一。

## 1. 概述

模式匹配与枚举阶段的定位：**用 enum 替代魔法字符串表达状态和消息类型，用 match 穷尽性检查保证不遗漏分支，用 if let/while let 简洁处理单分支场景，用模式解构优雅提取嵌套数据**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| enum 携带数据 | 每个变体可携带不同类型和数量的数据（代数数据类型 ADT） |
| match 穷尽匹配 | 编译器检查所有变体是否被处理，遗漏即编译错误 |
| match 模式种类 | 字面值、变量绑定、通配符、解构、范围、守卫、或模式 |
| if let / while let | 单分支匹配语法糖；持续匹配直到失败 |
| ref / ref mut | 模式中借用而非移动所有权 |
| matches! 宏 | 返回 bool 的轻量匹配 |
| 状态建模 | 用 enum 表达设备状态、订单状态、连接状态——枚举最核心的实战用法 |

**本阶段边界**：不展开 trait 对象与 enum 的取舍（ph07 trait）、`#[non_exhaustive]` API 演进策略、宏中的模式匹配。ph03 讲过 enum 基础定义和简单 match，ph04 深入过 Option/Result（本身就是枚举）——本阶段在它们之上系统讲透模式匹配的全部能力。

## 2. 来源与演变

Rust 的 enum 是**代数数据类型**（Algebraic Data Type, ADT），源自 ML 语言家族（Standard ML、OCaml、Haskell）。ADT 由两部分组成：**和类型**（sum type，变体之间是"或"）和**积类型**（product type，变体内部是"与"的组合）。`Option<T>` 是最简 ADT：`None`（零数据）或 `Some(T)`（携带一个 T）。

模式匹配同样来自 ML/Haskell，但 Rust 加入了**穷尽性检查**——编译器静态验证 match 覆盖所有可能情况。这是 Rust 对 ADT 的最重要增强：C 的 `switch` 漏 `default` 合法，Java 的 `switch` 穷尽性仅警告，Python 3.10 的 `match` 不做检查。Rust 的 `match` 与所有权系统并列，是"编译即正确"承诺的核心支柱。

本文示例以 **Edition 2021** 为基线（`let-else` 可用），验证工具链 rustc 1.92.0。

## 3. 语法与参数

### 3.1 enum 携带数据：代数数据类型

ph03 学过不带数据的枚举，本阶段扩展到携带数据的完整 ADT：

```rust
#[derive(Debug)]
enum Message {
    Quit,                            // 无数据
    Move { x: i32, y: i32 },         // 命名字段（结构体风格）
    Write(String),                   // 单个未命名（元组风格）
    ChangeColor(u8, u8, u8),        // 多个未命名
}

fn main() {
    let msgs = vec![
        Message::Quit,
        Message::Move { x: 10, y: 20 },
        Message::Write(String::from("hello")),
        Message::ChangeColor(255, 128, 0),
    ];
    for msg in &msgs {
        match msg {
            Message::Quit => println!("quit"),
            Message::Move { x, y } => println!("move to ({}, {})", x, y),
            Message::Write(text) => println!("write: {}", text),
            Message::ChangeColor(r, g, b) => println!("color: #{:02X}{:02X}{:02X}", r, g, b),
        }
    }
}
```

每个变体是**构造器**——`Message::Write("hello".into())` 构造值，match **解构**回组成部分。

### 3.2 match 穷尽匹配：编译器强制不遗漏

Rust 的 `match` 是**穷尽的**——必须覆盖所有可能的情况，否则编译不通过：

```rust
#[allow(dead_code)]
enum Status { Active, Inactive, Suspended }

fn main() {
    let s = Status::Active;
    match s {
        Status::Active => println!("active"),
        Status::Inactive => println!("inactive"),
        // 注释掉 Suspended → error[E0004]: `Suspended` not covered
        Status::Suspended => println!("suspended"),
    }
}
```

给 enum 新增变体时，编译器立刻告诉你所有需要更新的 match 处——运行时漏掉 else 分支的 bug 从根源上被消除。

### 3.3 match 的多种模式

Rust 的 `match` 支持八种模式，远超枚举匹配本身：

```rust
fn main() {
    let x = 42;

    match x {
        1 => println!("exactly one"),                      // 字面值
        2 | 3 | 5 | 7 | 11 => println!("small prime"),    // 或模式
        10..=30 => println!("in range 10..=30"),           // 范围
        n @ 31..=40 => println!("early 30s: {}", n),      // 绑定 + 范围
        n if n % 2 == 0 => println!("even: {}", n),       // 模式守卫
        n => println!("odd: {}", n),                       // 变量绑定
    }

    // 通配符：匹配一切但不绑定值
    match 99 {
        1..=50 => println!("first half"),
        _ => println!("second half"),
    }
}
```

| 模式种类 | 写法 | 行为 |
|---------|------|------|
| 字面值 | `1 =>` | 精确匹配该值 |
| 变量绑定 | `n =>` | 匹配一切，绑定到变量 |
| 通配符 | `_ =>` | 匹配一切，不绑定值 |
| 或模式 | `A \| B =>` | 匹配任一 |
| 范围 | `1..=5 =>` | 匹配闭区间内的值 |
| 绑定 + 子模式 | `n @ 1..=5 =>` | 既匹配子模式又绑定值 |
| 模式守卫 | `x if x > 0 =>` | 模式匹配 + 额外布尔条件 |

关键规则：match 按分支**从上到下**依次检查，第一个匹配成功的即执行。更具体的模式必须放在更宽泛的模式之前——`n =>` 放最前面会导致后面分支不可达，编译器会警告。

### 3.4 结构体、元组和引用解构

模式匹配可以**深层嵌套解构**，一次性提取多层嵌套数据：

```rust
struct Point { x: i32, y: i32 }

fn main() {
    // 结构体解构：字段名即变量名（简写）
    let pts = vec![
        Point { x: 0, y: 0 },
        Point { x: 42, y: 0 },
        Point { x: 10, y: 20 },
    ];
    for p in &pts {
        match p {
            Point { x: 0, y: 0 } => println!("origin"),
            Point { x, y: 0 } => println!("x-axis at {}", x),
            Point { x, y } => println!("point: ({}, {})", x, y),
        }
    }
    // 元组解构 + 守卫
    let pair = (1, -2);
    match pair {
        (0, 0) => println!("origin"),
        (x, y) if x == y => println!("diagonal: ({}, {})", x, y),
        (x, y) => println!("point: ({}, {})", x, y),
    }
    // 引用解构：match 引用时自动解出内层引用
    let opt = Some(String::from("hello"));
    match &opt {
        Some(s) => println!("borrowed: {}", s), // s: &String
        None => println!("none"),
    }
    println!("still own: {:?}", opt);
}
```

解构的核心优势：**一次 match 同时完成"判断变体"和"提取数据"**，不用 C 的 switch(tag) + memcpy。

### 3.5 if let：单分支匹配语法糖

只关心一种模式时，`if let` 更简洁：

```rust
fn main() {
    let opt: Option<i32> = Some(3);

    // if let —— 等价于只有一个分支的 match
    if let Some(v) = opt {
        println!("value: {}", v);
    }
    // if let + 嵌套条件（等效于守卫）
    if let Some(v) = opt {
        if v > 0 { println!("positive: {}", v); }
    }
    // if let - else：两级分支的轻量写法
    let config: Option<&str> = None;
    if let Some(path) = config {
        println!("from: {}", path);
    } else {
        println!("using defaults");
    }
}
```

`if let` 的取舍：简洁但**丢失穷尽性检查**——新增变体编译器不提示。公开 API 的状态机匹配优先用 `match`。

### 3.6 while let：持续匹配直到失败

`while let` 持续匹配直到失败——消费栈或迭代器的标准写法：

```rust
fn main() {
    let mut stack = vec![1, 2, 3];
    while let Some(top) = stack.pop() {
        println!("pop: {}", top);
    }
    println!("stack empty");
    // 等价于：loop { match stack.pop() { Some(top) => ..., None => break } }

    let mut iter = (0..5).into_iter();
    while let Some(n) = iter.next() {
        if n == 3 { break; }
        println!("iter: {}", n);
    }
}
```

### 3.7 ref / ref mut：模式中借用的关键字

默认 match 分支绑定变量会**移动**所有权。不想移动时用 `ref` 借用：

```rust
fn main() {
    let s = String::from("hello");
    // ref：借用而非移动（否则 match 会移走 s 的所有权）
    match s {
        ref r => println!("borrowed: {}", r),
    }
    println!("still own: {}", s); // s 仍可用

    // ref mut：可变借用
    let mut v = vec![1, 2, 3];
    match v {
        ref mut items => items.push(4),
    }
    println!("mutated: {:?}", v); // [1, 2, 3, 4]
}
```

`ref` 在旧代码中常见；现代 Rust（2018+）更倾向 `match &value` 然后在模式中自动解出引用（见 3.4 末尾）。

### 3.8 matches! 宏：返回 bool 的匹配

`matches!` 宏执行模式匹配并返回 `bool`——一行替代三行 match：

```rust
fn main() {
    let result: Result<i32, &str> = Ok(42);
    let is_ok = matches!(result, Ok(v) if v > 0);
    println!("is ok and positive: {}", is_ok); // true
    assert!(matches!(Some(10), Some(n) if n >= 5));
    // 等价于：match result { Ok(v) if v > 0 => true, _ => false }
}
```

## 4. 底层原理

### 4.1 match 的编译：跳转表 vs 决策树

Rust 编译器根据模式特征选择编译策略：

- **跳转表**（jump table）：枚举（编译后为整数 tag）且分支密集时，llvm 生成 O(1) 跳转表。
- **决策树**（decision tree）：模式包含范围、守卫、嵌套解构时，编译器生成优化后的 if-else 序列。

```rust
fn main() {
    #[derive(Debug)]
    #[allow(dead_code)]
    enum Op { Add, Sub, Mul, Div }

    fn apply(op: Op, a: i32, b: i32) -> i32 {
        match op {
            Op::Add => a + b,
            Op::Sub => a - b,
            Op::Mul => a * b,
            Op::Div => a / b,
        }
    }
    println!("12 + 8 = {}", apply(Op::Add, 12, 8));
}
```

穷尽性检查和代码生成是独立的——最复杂的模式也能高效编译。

### 4.2 穷尽性检查与不可达分支检测

编译器进行**覆盖性分析**：遍历每个变体检查是否有 match 覆盖；通配符和变量绑定覆盖未匹配项；守卫若 cond 为 false 则不匹配，编译器要求后续分支兜底。同时检测**不可达分支**：

```rust
fn main() {
    let x = 5;
    match x {
        n => println!("matched: {}", n),
        // _ => println!("never"), // warning: unreachable pattern
    }
}
```

## 5. 使用场景

### 5.1 enum 替代魔法字符串

| 反模式 | 改用 enum | 理由 |
|--------|----------|------|
| `"active"` / `"inactive"` 字符串 | `enum Status { Active, Inactive }` | 编译期拼写检查，类型安全 |
| `0` / `1` / `2` 数字状态码 | `enum State { ... }` | 自文档化，无需 enum-int 手工转换 |
| `"write"` / `"delete"` 操作指令 | `enum Event { Write, Delete, ... }` | 携带类型化数据而非散乱的 HashMap |

### 5.2 状态机建模

| 场景 | enum 设计示例 | 数据差异 |
|------|-------------|---------|
| 设备状态 | `Online{ip, uptime}` / `Offline` / `Fault(code)` | Online 有 IP，Fault 有错误码 |
| 订单状态 | `Pending` / `Confirmed{by}` / `Shipped(tracking)` | Confirmed 有确认人，Shipped 有单号 |
| 连接状态 | `Connected(stream)` / `Reconnecting{retry}` / `Closed` | Connected 持有连接，Reconnecting 记重试 |

核心优势：新增状态时编译器立刻报出所有待更新 match——**重构安全网**。

### 5.3 if let / while let / match 选择矩阵

| 场景 | 推荐方式 | 理由 |
|------|---------|------|
| 必须覆盖所有变体 | `match` | 穷尽检查，新增变体编译报错 |
| 只关心一种情况 | `if let` | 简洁，等价于单分支 match |
| 循环消费/弹出 | `while let` | 语义清晰，比 loop + match 紧凑 |
| 返回 bool 的判断 | `matches!` | 一行替代三行 match |

## 6. 代码示例

> 本节每个示例的完整可运行文件在 [`examples/`](./examples/) 目录，验证环境 rustc 1.92.0（零第三方依赖），编译命令统一 `rustc ex0X-*.rs -o /tmp/ex0X-*`，运行命令 `/tmp/ex0X-*`（命令见 examples/README.md）。

### 示例 1：设备状态建模

三种状态携带不同数据，match 一次性处理，matches! 判断可用性：

```rust
#[derive(Debug)]
enum DeviceState {
    Online { ip: String, uptime_secs: u64 },
    Offline,
    Fault(u32),
}

impl DeviceState {
    fn describe(&self) -> String {
        match self {
            DeviceState::Online { ip, uptime_secs } => {
                format!("在线 — IP: {}, 运行: {}s", ip, uptime_secs)
            }
            DeviceState::Offline => "离线".to_string(),
            DeviceState::Fault(code) => format!("故障 — 错误码: {}", code),
        }
    }

    fn is_available(&self) -> bool {
        matches!(self, DeviceState::Online { .. })
    }
}

fn main() {
    let devs = vec![
        DeviceState::Online { ip: "192.168.1.1".into(), uptime_secs: 3600 },
        DeviceState::Fault(500),
        DeviceState::Offline,
    ];
    for d in &devs {
        println!("[{}] {}", if d.is_available() { "可用" } else { "不可用" }, d.describe());
    }
}
```

完整文件：`examples/ex01-device-state.rs`

### 示例 2：字符串状态码改为 enum（消除魔法字符串）

```rust
#[derive(Debug, PartialEq)]
enum Status {
    Active,
    Inactive,
    Suspended,
}

impl Status {
    fn from_str(s: &str) -> Result<Status, String> {
        match s {
            "active" => Ok(Status::Active),
            "inactive" => Ok(Status::Inactive),
            "suspended" => Ok(Status::Suspended),
            other => Err(format!("unknown status: '{}'", other)),
        }
    }

    fn as_str(&self) -> &str {
        match self {
            Status::Active => "active",
            Status::Inactive => "inactive",
            Status::Suspended => "suspended",
        }
    }
}

fn main() {
    // 字符串安全转换
    assert_eq!(Status::from_str("active"), Ok(Status::Active));
    assert!(Status::from_str("deleted").is_err());

    // 枚举 -> 字符串
    println!("{}", Status::Suspended.as_str());

    // 不再能写错字符串 —— 类型系统保证
    let s = Status::Active;
    match s {
        Status::Active => println!("do activate"),
        Status::Inactive => println!("do deactivate"),
        Status::Suspended => println!("do suspend"),
    }
    // 如果未来加 Status::Deleted，编译器立刻报错——强制你更新所有 match
}
```

完整文件：`examples/ex02-status-from-str.rs`

### 示例 3：数据事件处理器（推荐项目）

五种事件类型分发——数据平台中枚举的典型用法：

```rust
#[derive(Debug)]
enum DataEvent {
    Write { key: String, value: Vec<u8> },
    Delete { key: String },
    Update { key: String, value: Vec<u8>, old_version: u64 },
    Expire { key: String, at: u64 },
    Alert { level: String, message: String },
}
fn process(event: &DataEvent) {
    match event {
        DataEvent::Write { key, value } =>
            println!("写入: key={}, 大小={}B", key, value.len()),
        DataEvent::Delete { key } =>
            println!("删除: key={}", key),
        DataEvent::Update { key, value, old_version } =>
            println!("更新: key={}, 大小={}B, 旧版本={}", key, value.len(), old_version),
        DataEvent::Expire { key, at } =>
            println!("过期: key={}, 过期时间={}", key, at),
        DataEvent::Alert { level, message } => {
            let prefix = if level == "critical" { "!! 严重" } else { "  提示" };
            println!("{} [{}]: {}", prefix, level, message);
        }
    }
}
fn main() {
    let events = vec![
        DataEvent::Write { key: "user:1".into(), value: vec![1, 2, 3] },
        DataEvent::Update { key: "user:1".into(), value: vec![4, 5, 6], old_version: 1 },
        DataEvent::Delete { key: "temp:99".into() },
        DataEvent::Expire { key: "session:42".into(), at: 1_723_159_200 },
        DataEvent::Alert { level: "critical".into(), message: "磁盘空间不足".into() },
    ];
    for event in &events {
        process(event);
    }
    let write_count = events.iter()
        .filter(|e| matches!(e, DataEvent::Write { .. }))
        .count();
    println!("Write 事件数: {}", write_count);
}
```

完整文件：`examples/ex03-data-event.rs`

如果新增 `DataEvent::Merge`，编译器标记所有 match 不穷尽——在几十个处理函数中精确标出待更新位置，if-else 或字符串分发做不到。

## 7. 总结

### 关键要点

1. **enum 携带数据 = ADT**：每个变体有独立数据结构——状态建模的基础。
2. **match 穷尽检查**：编译强制覆盖所有变体，新增变体时编译器指明所有需更新的位置。
3. **八种模式类型**：字面值、变量绑定、通配符、或模式、范围、绑定、守卫、解构——组合表达任意复杂匹配。
4. **深层解构**：一次 match 同时判断变体并提取嵌套数据。
5. **if let 是语法糖**：单分支 match。简洁但丢失穷尽检查，适合"只关心一种情况"。
6. **while let**：循环 + 单分支匹配，消费迭代器的标准写法。
7. **ref / ref mut**：模式中借用而非移动。现代 Rust 优先 `match &val`。
8. **matches! 宏**：一行 bool 替代三行 match。
9. **编译期安全无运行时开销**：穷尽检查是编译期分析，代码生成为跳转表或决策树。

### 跨语言对比：模式匹配

| 概念 | Rust | C | Java | Python 3.10+ |
|------|------|---|------|-------------|
| 带数据枚举 | `enum E { A(i32), B{x:f64} }` | `union` + tag（手工） | `sealed class` + record | — |
| 穷尽匹配 | `match`（编译错误） | `switch`（可漏 default） | `switch`（sealed: 警告） | `match`（不检查） |
| 模式解构 | `Point{x,y}` 嵌套解构 | 无 | 有限解构 | `case Point(x=x,y=y)` |
| 守卫 | `x if x > 0` | 无 | `when` | `if x > 0` |
| 单分支匹配 | `if let` | — | `if (x instanceof A a)` | — |
| 循环匹配 | `while let` | — | — | — |
| 编译期安全 | 穷尽 + 不可达检测 | 无 | sealed 部分 | 无 |

### 阶段验收清单

- [ ] 能用 enum 替代魔法字符串和数字状态码。
- [ ] 能写出无遗漏的 match，编译器不报 E0004。
- [ ] 能读懂 Option/Result 的 match 写法并自己实现类似匹配。
- [ ] 能解释 if let 和 match 的取舍（简洁 vs 穷尽检查）。
- [ ] 能用 enum 建模设备状态、订单状态或消息类型。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：enum 订单状态建模、字符串状态码改 enum、match 消息分发、if let/while let/matches! 精简、订单状态机共 5 题。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**数据事件处理器**（处理 Write、Delete、Update、Expire 和 Alert 事件，输出结构化处理日志，含单元测试）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[模块化与 Cargo 阶段](../ph06-cargo-module/06-cargo-module.md) —— mod/pub/use 可见性控制、lib.rs 与 main.rs、Cargo.toml 依赖管理、workspace 多 crate 组织。
