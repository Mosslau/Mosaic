# Rust 模块化与 Cargo 阶段

> 从单文件脚本到多文件工程的分水岭：mod/pub/use 把代码组织成清晰的模块树，Cargo 把依赖、构建、测试、格式化与 lint 收敛成一条命令——面向数据基础设施与异步网络服务方向，这是每个真实项目的必修课。

## 1. 概述
模块化与 Cargo 阶段的定位：**能组织多文件 Rust 项目——用 mod/pub/use 构建清晰的模块树与可见性边界，用 lib.rs 与 main.rs 划分库 crate 与二进制 crate，用 Cargo.toml 管理依赖与语义化版本，用 features 与 workspace 组织多 crate 工程，并把 cargo build/test/fmt/clippy 变成日常肌肉记忆**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| mod 模块声明 | 内联模块与文件模块、模块树设计、文件组织约定 |
| pub 可见性 | pub / pub(crate) / pub(super) / 私有、公开 API 设计 |
| use 导入与路径 | 绝对路径 `crate::`、相对路径 `self::`/`super::`、重导出 |
| lib.rs 与 main.rs | 库 crate 与二进制 crate、双 crate 协作 |
| Cargo.toml 依赖管理 | 依赖声明、语义化版本、Cargo.lock 锁文件 |
| features 特性开关 | 特性声明、可选依赖、按需编译 |
| workspace 多 crate | 虚拟清单、成员 crate、path 依赖 |
| cargo 工作流 | build / test / fmt / clippy / doc / tree / update |

**本阶段边界**：承接 ph05 模式匹配（本阶段解析类代码大量使用 `Option`/`Result` 与 `match`）；不涉及 trait 与泛型抽象（ph07）、生命周期标注深入（ph08）、错误处理工程化（ph11）、异步运行时（ph12）。

## 2. 来源与演变
Cargo 与 rustc 于 2015 年随 Rust 1.0 一同稳定，此前依赖 `rustc` 直接编译、手工拼装依赖。Cargo 借鉴 Ruby Bundler 与 Node npm 的锁定思想，带来标准化构建、依赖解析与 crates.io 分发，强调"一次解析、确定性构建"——同一份 `Cargo.lock` 在任何机器上产出相同的依赖版本。

模块系统在 1.0 时已稳定（`mod`/`pub`/`use`），但路径规则在 2018 edition 经历重大变革：引入 `crate::` 绝对路径前缀，`use` 路径统一为 crate 内模块路径（消除与外部 crate 同名的二义性），并推荐 `foo.rs` 取代 `foo/mod.rs`。2021 edition 默认 `resolver = "2"`；workspace 则从简单成员列表演进到 `[workspace.package]` 共享元数据、`[workspace.dependencies]` 统一依赖版本。

| 时间 | 里程碑 | 影响 |
|------|--------|------|
| 2015 | Rust 1.0：rustc + Cargo 一同发布，crates.io 上线 | 模块系统与 Cargo 成为默认工程形态 |
| 2018 | Edition 2018：`crate::` 路径、use 语义统一 | 消除路径二义性，`foo.rs` 取代 `foo/mod.rs` |
| 2021 | Edition 2021：resolver = "2" 默认 | features 统一行为更可预期 |
| 2023+ | `workspace.package` / `workspace.dependencies` | 多 crate 工程共享元数据与依赖版本 |

## 3. 语法与参数

### 3.1 mod 模块声明与文件组织
`mod` 有两种写法：**内联模块**（花括号内直接写代码）和**文件模块**（`mod foo;` 让编译器读取 `src/foo.rs` 或 `src/foo/mod.rs`）——后者是拆分多文件工程的核心机制：

```rust
mod math {
    pub fn add(a: i32, b: i32) -> i32 { a + b }
}
mod greetings {
    pub fn hello() { println!("hello"); }
}
fn main() {
    greetings::hello();
    println!("1 + 2 = {}", math::add(1, 2));
}
```
要点与坑：
- **模块树由 mod 声明决定，不由文件位置决定**：`mod parser;` 声明后 `src/parser.rs` 才参与编译；嵌套 `mod a { mod b; }` 对应 `src/a/b.rs`。
- **坑：孤儿文件**——`src/` 下存在但没有任何 `mod` 声明的 `.rs` 文件**永远不会被编译**，被引用时报 unresolved import，不引用则静默忽略。
- **坑：模块树与文件路径不一致**——声明 `mod parser;` 但文件放错位置报 `error[E0583]: file not found for module`。
- 2018 edition 起优先用 `parser.rs`，旧式 `parser/mod.rs` 已不推荐。

### 3.2 pub 可见性边界
Rust 可见性**默认私有**：item 默认只对定义它的模块及其子孙可见。可见性阶梯：

| 可见性 | 语义 |
|--------|------|
| 默认（无修饰符） | 仅当前模块及子模块可见 |
| `pub` | 对所有可见，包括外部 crate |
| `pub(crate)` | 仅本 crate 内所有模块可见 |
| `pub(super)` | 仅父模块内可见 |

```rust
mod outer {
    pub fn public_fn() { println!("public"); }
    #[allow(dead_code)]
    fn private_fn() { println!("private"); }
    pub(crate) fn crate_visible() { println!("crate"); }
}
fn main() {
    outer::public_fn();     // pub：模块外可见
    outer::crate_visible(); // pub(crate)：本 crate 内可见
    // outer::private_fn(); // error[E0603]: private
}
```
要点：
- **pub 不自动传播**：`pub struct` 的字段默认仍私有，嵌套路径上每一级都要显式 `pub`。
- **坑：pub 泄漏私有类型**——`pub fn` 返回私有类型报 `error[E0446]`；公开 API 只能涉及公开类型。
- 库 crate 内部共享优先用 `pub(crate)`；更细粒度还有 `pub(super)` 与 `pub(in path)`——公开面越小越容易演进。

### 3.3 use 导入与路径
路径分**绝对**（`crate::` 从 crate 根开始）与**相对**（`self::` 当前模块、`super::` 父模块）。2018 起 `use` 路径一律按 crate 内模块路径解析，无 2015 版的二义性：

```rust
mod kitchen {
    pub fn cook() { println!("cooking"); }
    pub mod pantry { pub fn stock() { println!("stocking"); } }
}
mod dining {
    pub fn serve() { super::kitchen::cook(); } // super:: 相对路径
}
use crate::kitchen::pantry::stock; // crate:: 绝对路径

fn main() {
    dining::serve();
    stock();
}
```
要点：
- `use` 只建立**本地绑定**，不改变可见性；要让外部使用，必须 `pub use` 重导出。
- **坑：同名冲突**——两个 `use` 引入同名 item 报 `error[E0252]`，用 `as` 起别名（如 `use std::collections::HashMap as Map;`）。
- `pub use` 是 API 设计利器：把 `crate::model::user::User` 重导出为 crate 根的 `User`，外部路径立刻变短。

### 3.4 lib.rs 与 main.rs：双 crate
一个 package 可同时含 `src/lib.rs`（库 crate）与 `src/main.rs`（二进制 crate）——它们是**两个独立编译单元**，二进制通过**包名**使用库。这正是 roadmap 的示例：

```rust
// src/lib.rs —— 库 crate：声明并公开模块
pub mod parser;

// src/parser.rs
pub fn parse(input: &str) -> Vec<&str> {
    input.lines().collect()
}

// src/main.rs —— 二进制 crate：通过包名使用库
use myproj::parser;
fn main() {
    println!("{:?}", parser::parse("a\nb\nc"));
}
```
要点：
- 包名 `my-proj` 在代码里写作 `my_proj`（连字符转下划线）。
- 二进制与库 crate 是不同编译单元，`pub(crate)` 跨不过它们（详见示例 2）。
- 多二进制：`src/bin/tool1.rs` 各自成 crate，用 `cargo run --bin tool1` 运行；集成测试放 `tests/`，只能用公开 API。

### 3.5 Cargo.toml 依赖管理与语义化版本
依赖声明在 `[dependencies]`，版本遵循**语义化版本**（Semantic Versioning）：`MAJOR.MINOR.PATCH`，`MAJOR` 变更即不兼容。

| 要求写法 | 含义 |
|---------|------|
| `"1.2.3"` | `^1.2.3`：`>=1.2.3, <2.0.0`，允许兼容升级 |
| `"0.8"` | `^0.8`：`>=0.8.0, <0.9.0`，0.x 次版本即破坏性 |
| `"=1.8.0"` | 精确锁定，任何升级都不允许 |
| `"1.2.*"` | 通配任意 patch |

```toml
[package]
name = "myapp"
version = "0.1.0"
edition = "2021"

[dependencies]
serde_json = "1.0.108"                            # 兼容 1.x
uuid = { version = "1.8", features = ["v4"] }     # 带 features 的依赖

[dev-dependencies]  # 仅测试/示例使用
pretty_assertions = "1.4"
```
要点：
- **真正的版本锁是 `Cargo.lock`**：语义化版本决定"允许哪些版本"，锁文件决定"实际用哪个版本"。`cargo add serde_json@1.0.108` 添加依赖，`cargo update -p serde_json --precise 1.0.108` 精确调整。
- **坑：依赖版本冲突**——依赖树中两个 crate 要求不兼容版本（如 `"=1.0.108"` 与 `"^2.0"`）时，Cargo 会同时引入两个版本，出现"两个版本的同名类型互不认"的编译错误；用 `cargo tree -d` 排查。
- 二进制项目务必提交 `Cargo.lock`；库项目视策略而定（ph16 展开）。

### 3.6 package、crate、module 三层概念
三者是不同层面的组织单元，必须区分清楚：

```
package（发布单元：一个 Cargo.toml 描述的项目）
 └── crate（编译单元：一次 rustc 调用）
      ├── 二进制 crate：src/main.rs → 可执行文件
      └── 库 crate：src/lib.rs → 可被复用的库
           └── module（命名空间：编译期解析名字）
                └── item（fn、struct、enum、impl…）
```
要点：
- **package 是发布与版本管理单元**（crates.io 上的一个包）；**crate 是编译单元**（借用检查、可见性、单态化的作用范围）；**module 是命名空间**（只影响名字查找，不影响编译产物）。
- 一个 package 最多一个库 crate、可含多个二进制 crate；工程决策顺序：先定 package 边界 → 再定 crate 划分 → 最后设计模块树。

### 3.7 features 特性开关入门
**features** 是 crate 级编译开关：启用某特性就多编译一部分代码（或引入一个可选依赖），默认行为由 `default` 特性决定：

```toml
[features]
default = ["json"]        # 默认开启 json
json = ["dep:serde_json"] # 可选依赖重命名为 json 特性
pretty = []               # 纯开关：不引入依赖
```

```rust
#[cfg(feature = "json")] // 只有启用 json 特性才编译本模块
pub mod json_util {
    pub fn pretty_print(json: &str) -> serde_json::Result<String> {
        let v: serde_json::Value = serde_json::from_str(json)?;
        serde_json::to_string_pretty(&v)
    }
}
```
要点：
- 命令对照：`cargo build`（默认特性）、`--no-default-features`（关默认）、`--features pretty`（叠加）、`--all-features`（全开）。
- `optional = true` 的依赖默认生成同名隐式特性；`dep:serde_json` 语法把它藏起来，改由 `json` 特性控制。
- **features 必须"加性"**（只增能力、不改变已有行为），否则在多依赖场景互相踩踏（详见 4.4）。

### 3.8 workspace 多 crate 组织
**workspace** 让多个 package（成员 crate）共享一个根清单、一份 `Cargo.lock`、一次统一构建。根清单只写 `[workspace]`（**虚拟清单**）：

```toml
# 根 Cargo.toml
[workspace]
resolver = "2"
members = ["crates/log-parser", "crates/log-aggregator", "crates/log-cli"]

[workspace.package]      # 共享元数据：成员用 version.workspace = true 继承
version = "0.1.0"
edition = "2021"
```
要点：
- 成员间用 **path 依赖**互引：`log-parser = { path = "../log-parser" }`。
- 常用命令：`cargo build --workspace`、`cargo test --workspace`、`cargo run -p log-cli`（`-p` 指定成员）。
- 完整可运行示例见示例 5。

### 3.9 cargo build、test、fmt、clippy 工作流
Cargo 是日常工程的唯一入口，命令要练成肌肉记忆：

| 命令 | 作用 |
|------|------|
| `cargo build` / `--release` | 调试 / 发布构建 |
| `cargo check` | 只做类型检查，最快的语法验证 |
| `cargo test` | 运行单元与集成测试 |
| `cargo fmt` / `--check` | 格式化 / 检查格式 |
| `cargo clippy` | 静态 lint 检查 |
| `cargo doc` / `tree` / `update` | 文档 / 依赖树 / 升级依赖 |

```rust
#[cfg(test)] // 单元测试只在测试构建中编译
mod tests {
    #[test]
    fn test_add() {
        assert_eq!(1 + 2, 3);
    }
}
fn main() {}
```
要点：
- 提交前质量门禁三连：`cargo fmt --check` → `cargo clippy -- -D warnings` → `cargo test`（ph21 深化）。
- 单元测试用 `#[cfg(test)] mod tests` 写在源码文件里，可直接访问私有函数；集成测试放 `tests/`，只能用公开 API。

## 4. 底层原理

### 4.1 模块树如何映射到编译单元
**crate 是编译单元**：`cargo build` 对每个 crate 单独调用一次 `rustc`，借用检查、可见性检查、单态化都以 crate 为边界。**module 只是命名空间**：模块树在编译期展平为 crate 内的一组 item，不产生额外编译产物、零运行时开销——这与 C++ 头文件展开（每个翻译单元重新解析、重复编译）形成根本区别。

模块树与文件系统的关系是"约定而非绑定"：`mod foo;` 让 rustc 按约定读 `src/foo.rs`，父子关系完全由 `mod` 声明决定——这也解释了"孤儿文件"为何不参与编译。增量编译缓存（target/debug 下的 `.fingerprint`）同样按 crate 粒度管理：只改一个模块，只有所属 crate 需要重新编译。

### 4.2 可见性在编译期的检查机制
可见性检查发生在**名称解析阶段**（resolution，早于代码生成）：编译器为每个 item 记录"最近可见性"（私有、`pub`、`pub(crate)`、`pub(super)`、`pub(in path)`），再按路径逐级验证。规则只有一条：**一个 item 从模块 M 可见，当且仅当路径上每一级模块都可见**——`pub struct` 放在私有模块里，外部依然不可见。

泄漏类错误全部是编译期错误：E0603（item 私有）、E0616（字段私有）、E0624（方法私有）、E0446（pub fn 返回私有类型）。可见性纯属编译期概念，对机器码零影响——`pub` 不改变数据布局或调用约定。

### 4.3 Cargo.lock 与依赖解析
依赖解析器读取所有 `Cargo.toml` 的版本要求，为每个依赖选出一个满足全部约束的版本，并把精确版本与源码校验和写入 **Cargo.lock**。语义化版本约束是"候选范围"，锁文件才是"最终答案"：只要 lock 存在，任何机器、任何时间都构建出相同依赖树（可复现构建）。

冲突分两种情况：要求兼容（如 `"1.2"` 与 `"1.5"`）时合并取最新；要求不兼容（如 `"=1.0.108"` 与 `"^2.0"`）时无法合并，Cargo 会**同时引入两个版本**，同名类型互不兼容，编译错误表现为"expected struct `X`, found struct `X`"——用 `cargo tree -d` 找出是谁拉了哪个版本。`cargo update` 把 lock 内版本升到兼容范围内最新，是升级依赖的标准入口。

### 4.4 features 的统一性（crate 级特性开关）
features 有一个关键性质：**统一（unification）**。依赖图中同一 crate 无论被多少处引用都只编译一次，编译时启用**所有被请求特性的并集**——某个深层依赖开启 `serde_json` 的 `preserve_order`，你的代码也一并生效。因此 features 是 crate 级开关：不是"某个用法局部开"，而是"整棵依赖树统一决定"。

正因如此，features 必须**加性**：新增特性只能增加能力，不能改变既有特性行为（否则开启顺序不同结果不同）。`dep:` 语法隐藏 optional 依赖的隐式特性，避免被外部依赖意外开启；`resolver = "2"`（2021 edition 默认）保证 build/dev-dependencies 的特性不泄漏进普通依赖。

## 5. 使用场景
| 场景 | 涉及知识点 |
|------|-----------|
| 单文件程序拆分为多文件工程 | mod、文件组织、lib.rs/main.rs |
| 设计库 crate 的公开 API | pub、pub(crate)、私有字段、pub use 重导出 |
| 引入第三方库并锁定版本 | Cargo.toml、语义化版本、Cargo.lock |
| 分层架构（model / parser / service） | 模块树设计、模块间依赖方向 |
| 团队协作保持格式与质量一致 | cargo fmt、cargo clippy、质量门禁 |
| 一套代码库管理多个工具与库 | workspace、path 依赖、`-p` 指定成员 |
| 按需编译可选能力（如 json 支持） | features、optional 依赖、`cfg(feature)` |
| 依赖树排查与升级 | cargo tree、cargo update、cargo add |

**不适合**此阶段的事项：
- trait 对象与泛型抽象（ph07）：模块解决"组织"，不解决"行为抽象"，不要在本阶段强行引入泛型架构。
- 异步运行时与 Tokio（ph12）：网络与并发编程留到并发阶段。
- 自定义错误类型与 thiserror/anyhow（ph11）：本阶段用 `Result<T, E>` 与 `?` 即可。
- FFI 与跨语言接口（ph23）：`cdylib`、`extern "C"`、pyo3 属于 FFI 阶段。

## 6. 代码示例

### 示例 1：单文件拆分为 lib.rs + 多个 mod 文件（model/parser/service）
"把单文件项目拆成 model、parser、service"是 roadmap 的核心练习。文件树：

```
log-analyzer/
├── Cargo.toml
└── src/
    ├── lib.rs       # 模块树入口
    ├── main.rs      # 二进制 crate
    ├── model.rs     # 数据模型
    ├── parser.rs    # 解析
    └── service.rs   # 聚合服务
```

```toml
[package]
name = "log-analyzer"
version = "0.1.0"
edition = "2021"
```

```rust
// src/lib.rs —— 模块树唯一入口
pub mod model;
pub mod parser;
pub mod service;

// src/model.rs
#[derive(Debug, Clone, PartialEq)]
pub struct Record {
    pub ts: u64,        // 时间戳（Unix 秒）
    pub level: String,  // INFO / WARN / ERROR
    pub message: String,
}

// src/parser.rs —— 解析层
use crate::model::Record;

pub fn parse_line(line: &str) -> Option<Record> {
    let mut parts = line.splitn(3, ' ');
    let ts = parts.next()?.parse().ok()?;   // ? 传播 None（ph04/ph05）
    let level = parts.next()?.to_string();
    let message = parts.next()?.to_string();
    Some(Record { ts, level, message })
}

pub fn parse_all(input: &str) -> Vec<Record> {
    input.lines().filter_map(parse_line).collect()
}

// src/service.rs —— 聚合
use crate::model::Record;
use std::collections::HashMap;

pub fn aggregate(records: &[Record]) -> HashMap<String, usize> {
    let mut by_level = HashMap::new();
    for r in records {
        *by_level.entry(r.level.clone()).or_insert(0) += 1;
    }
    by_level
}

// src/main.rs —— main → service → parser → model 单向依赖
use log_analyzer::{parser, service};

fn main() {
    let records = parser::parse_all("1700000000 INFO boot ok\n1700000001 WARN slow query");
    println!("总记录数: {}", records.len());
    println!("按级别统计: {:?}", service::aggregate(&records));
}
```
依赖方向 `main → service → parser → model`：model 不依赖任何人，parser 只依赖 model，service 聚合 parser 的结果。重构时只需调整 `lib.rs` 的模块声明，调用方不变。

### 示例 2：pub API 设计与可见性控制（pub、pub(crate)、私有字段）
库 crate 的公开面应"小而稳定"。本示例展示每层可见性如何生效，以及**同 package 的 main.rs 与 lib.rs 是两个 crate**——`pub(crate)` 跨不过它们：

```
pub-api/
├── Cargo.toml
└── src/
    ├── lib.rs
    ├── main.rs
    ├── account.rs
    └── audit.rs
```

```rust
// src/lib.rs
pub mod account;          // 公开模块：外部可见
mod audit;                // 私有模块：外部不可见，即使其中函数是 pub
pub use account::Account; // 重导出：外部直接用 pub_api::Account

// src/audit.rs —— 私有模块：对 account 可见，对外部 crate 不可见
pub fn log(msg: String) {
    println!("[audit] {}", msg);
}

// src/account.rs
use crate::audit;

#[allow(dead_code)] // 演示用：secret/set_secret 仅供 crate 内部
pub struct Account {
    pub id: u32,               // 完全公开
    pub(crate) secret: String, // 仅本 crate 可见
    balance: i64,              // 私有：仅本模块可见
}

impl Account {
    pub fn open(id: u32) -> Account {
        Account { id, secret: String::new(), balance: 0 }
    }
    pub fn deposit(&mut self, amount: i64) -> Result<(), String> {
        if amount <= 0 { return Err(String::from("金额必须为正")); }
        self.balance += amount;
        audit::log(format!("deposit {} -> {}", self.id, amount));
        Ok(())
    }
    pub fn balance(&self) -> i64 { self.balance }
    #[allow(dead_code)] // pub(crate) 方法：仅供 crate 内部（见 lib.rs 注释说明）
    pub(crate) fn set_secret(&mut self, secret: String) { self.secret = secret; }
}

// src/main.rs —— 与 lib.rs 是不同 crate：只能用公开 API
use pub_api::Account;

fn main() {
    let mut acc = Account::open(42);
    acc.deposit(100).unwrap();
    println!("id={}, balance={}", acc.id, acc.balance());
    // 以下都无法编译：acc.secret / acc.set_secret(...) 是 pub(crate)，对另一个
    // crate 不可见（E0616/E0624）；acc.balance 是私有字段（E0616）。
}
```
设计原则：只暴露 `open`/`deposit`/`balance` 这类稳定操作，`balance` 无 setter，内部状态用 `pub(crate)` 共享——公开面越小，未来演进越自由。

### 示例 3：添加第三方 crate 并固定版本（serde_json）
`cargo new json-cfg` 后执行 `cargo add serde_json@1.0.108` 与 `cargo add serde@1 --features derive`：

```toml
[package]
name = "json-cfg"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1.0.197", features = ["derive"] }
serde_json = "=1.0.108"  # "=" 精确锁定：manifest 层面也不允许升级
```

```rust
// src/main.rs
use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Deserialize)]
struct Config {
    name: String,
    port: u16,
    tags: Vec<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let json = r#"{"name":"svc-a","port":8080,"tags":["rust","storage"]}"#;
    let v: Value = serde_json::from_str(json)?;    // 动态 Value
    println!("name = {}, port = {}", v["name"], v["port"]);
    let cfg: Config = serde_json::from_str(json)?; // 类型化反序列化
    println!("name={} port={} tags={:?}", cfg.name, cfg.port, cfg.tags);
    Ok(())
}
```
要点：`Cargo.lock` 记录解析出的精确版本与校验和，`cargo build` 永远按它构建——这才是"固定版本"的落点；手工调整用 `cargo update -p serde_json --precise 1.0.108`，查看依赖树用 `cargo tree`。

### 示例 4：features 特性开关（可选依赖）
```
feat-demo/
├── Cargo.toml
└── src/
    ├── lib.rs
    └── main.rs
```

```toml
[package]
name = "feat-demo"
version = "0.1.0"
edition = "2021"

[features]
default = ["json"]
json = ["dep:serde_json"]  # 可选依赖重命名为 json 特性
pretty = []                # 纯开关

[dependencies]
serde_json = { version = "1.0.108", optional = true }
```

```rust
// src/lib.rs
pub fn describe() -> &'static str {
    if cfg!(feature = "pretty") { "feat-demo (pretty)" } else { "feat-demo" }
}

#[cfg(feature = "json")]
pub mod json_util {
    pub fn pretty_print(json: &str) -> serde_json::Result<String> {
        let v: serde_json::Value = serde_json::from_str(json)?;
        serde_json::to_string_pretty(&v)
    }
}

// src/main.rs —— 同一 package 的二进制同样受 features 控制
use feat_demo::describe;

fn main() {
    println!("{}", describe());
    #[cfg(feature = "json")] // 关掉 json 后本块不编译，也不引用 serde_json
    {
        let pretty = feat_demo::json_util::pretty_print(r#"{"a":1}"#).unwrap();
        println!("{}", pretty);
    }
}
```
命令对照：`cargo build`（默认含 json）→ `--no-default-features`（零依赖）→ `--features pretty` → `--all-features`；用 `cargo tree -e features` 查看特性开启来源。可选依赖让"轻量模式"成为可能——用户不需要 JSON 时就不拉 `serde_json`。

### 示例 5：workspace 管理多 crate（成员 crate 互相依赖）
多模块日志分析工具的 workspace 形态：三个 crate 分层，`log-cli` 依赖另外两个：

```
log-workspace/
├── Cargo.toml                    # 虚拟清单
└── crates/
    ├── log-parser/       # 库：解析日志行
    ├── log-aggregator/   # 库：依赖 log-parser
    └── log-cli/          # 二进制：依赖前两者
```
每个成员 crate 都有自己的 `Cargo.toml`，通过 `version.workspace = true` 继承根清单元数据；`log-cli` 的 `[dependencies]` 同时写 `log-parser` 与 `log-aggregator` 两个 path 依赖：

```toml
# 根 Cargo.toml
[workspace]
resolver = "2"
members = ["crates/log-parser", "crates/log-aggregator", "crates/log-cli"]

[workspace.package]
version = "0.1.0"
edition = "2021"
```

```rust
// crates/log-parser/src/lib.rs
#[derive(Debug, Clone, PartialEq)]
pub struct LogLine {
    pub ts: u64,
    pub level: String,
    pub message: String,
}

pub fn parse(line: &str) -> Option<LogLine> {
    let mut parts = line.splitn(3, ' ');
    let ts = parts.next()?.parse().ok()?;
    let level = parts.next()?.to_string();
    let message = parts.next()?.to_string();
    Some(LogLine { ts, level, message })
}

pub fn parse_all(input: &str) -> Vec<LogLine> {
    input.lines().filter_map(parse).collect()
}
```

```toml
# crates/log-aggregator/Cargo.toml —— 成员间 path 依赖
[package]
name = "log-aggregator"
version.workspace = true
edition.workspace = true

[dependencies]
log-parser = { path = "../log-parser" }
```

```rust
// crates/log-aggregator/src/lib.rs
use log_parser::LogLine;
use std::collections::BTreeMap;

pub fn count_by_level(lines: &[LogLine]) -> BTreeMap<String, usize> {
    let mut counts = BTreeMap::new();
    for line in lines {
        *counts.entry(line.level.clone()).or_insert(0) += 1;
    }
    counts
}
```

```toml
# crates/log-parser/Cargo.toml
[package]
name = "log-parser"
version.workspace = true
edition.workspace = true

# crates/log-cli/Cargo.toml
[package]
name = "log-cli"
version.workspace = true
edition.workspace = true

[dependencies]
log-parser = { path = "../log-parser" }
log-aggregator = { path = "../log-aggregator" }
```

```rust
// crates/log-cli/src/main.rs —— 包名连字符在代码中写为下划线
use log_aggregator::count_by_level;
use log_parser::parse_all;

fn main() {
    let lines = parse_all("1700000000 INFO boot ok\n1700000002 ERROR disk full");
    println!("总行数: {}", lines.len());
    println!("按级别统计: {:?}", count_by_level(&lines));
}
```
构建与运行：`cargo build --workspace`（一次构建全部成员）、`cargo run -p log-cli`（运行指定成员）、`cargo test --workspace`（测试全部成员）。

workspace 的价值：三个 crate 共享一份 `Cargo.lock` 与编译缓存；`log-parser` 可被其他项目单独复用（发到 crates.io 或作为 git 依赖），`log-cli` 只是薄薄一层入口——这正是 roadmap 推荐项目"多模块日志分析工具（parser、aggregator、cli 分层清楚）"的落地形态。

## 7. 总结

### 关键要点
1. **crate 是编译单元，module 是命名空间**：cargo 按 crate 编译，module 零运行时开销。
2. **Rust 默认私有**：每一级都要显式 `pub`——与多数语言相反，却最利于 API 演进。
3. **可见性五档**：私有、`pub`、`pub(crate)`、`pub(super)`、`pub(in path)`；库内部共享用 `pub(crate)`。
4. **路径两套**：绝对 `crate::` 与相对 `self::`/`super::`；2018 起 `use` 路径无二义性；`pub use` 重导出缩短外部路径。
5. **lib.rs + main.rs 是两个 crate**：main 通过包名使用 lib，`pub(crate)` 跨不过这个边界。
6. **Cargo.lock 才是真正的版本锁**：语义化版本定"允许哪些版本"，锁文件定"实际用哪个版本"。
7. **features 必须加性**：同一 crate 只编译一次，特性取所有请求的并集——统一性的代价与约束。
8. **workspace 是工程层组织**：共享 lock 与构建，成员间 path 依赖互引。
9. **质量门禁三连**：`cargo fmt --check` → `cargo clippy -- -D warnings` → `cargo test`，提交前跑通。

### 跨语言对比：模块系统
| 维度 | Rust mod/crate | Go package | Java package | Python module | C++ namespace |
|------|---------------|------------|--------------|---------------|---------------|
| 组织单元 | crate（编译单元）内嵌 module 树 | package（目录内文件同包） | package 下的 class 文件 | module = 一个 .py 文件 | namespace 块 |
| 文件约定 | `mod foo;` → foo.rs / foo/mod.rs | 目录内所有 .go 同属一个包 | 目录 + package 声明 | 目录 + `__init__.py` 成包 | 无（靠头文件 include） |
| 导入语法 | `use crate::a::b` | `import "pkg"`，包名.标识符 | `import a.b.C` | `import a.b` | `using namespace` / 限定名 |
| 可见性与公开 API | 默认私有，`pub` + `pub use` 重导出 | 首字母大小写决定导出 | public / private 修饰符 | 下划线 `_x` + `__all__` | public / private 段 + 头文件 |
| 编译单元 | 每个 crate 单独编译，module 零开销 | 每个 package 编译 | 每个 .java → .class | 运行期 import，无编译期检查 | 每个 .cpp 翻译单元 |

### 阶段验收标准
- 能解释 crate、package、module 三者的关系：编译单元 / 发布单元 / 命名空间。
- 能设计清晰的 pub API：知道什么该 `pub`、什么该 `pub(crate)`、什么该私有，会用 `pub use` 重导出。
- 能熟练使用 cargo build / test / fmt / clippy，会用 cargo tree / update 排查依赖问题。
- 能读懂 Cargo.toml 的依赖声明与语义化版本约束，理解 Cargo.lock 的作用与提交策略。
- 能组织一个包含多个 crate 的 workspace，并让成员通过 path 依赖协作。

### 进入下一阶段前
确保能完成以下练习：
- 把单文件项目拆成 model、parser、service 三个模块（提示：先画模块树再按文件落地；对照示例 1）。
- 添加一个第三方 crate 并固定版本（提示：`cargo add serde_json@1.0.108`，观察 Cargo.lock 变化；对照示例 3）。
- 创建一个 workspace 管理多个 crate（提示：虚拟清单 + crates/ 目录 + path 依赖；对照示例 5）。
- 为库 crate 编写单元测试并跑通 cargo test（提示：`#[cfg(test)] mod tests` + `#[test]`）。
- 跑通 `cargo fmt --check` 与 `cargo clippy -- -D warnings`，把警告清零。
- 用 features 给项目加一个可选能力（提示：optional 依赖 + `dep:` 语法；对照示例 4）。

### 推荐项目
- **多模块日志分析工具**：parser（解析日志行为结构化记录）、aggregator（按级别/来源聚合统计）、cli（命令行入口与输出）三层分层清楚。示例 1 是单包三层结构，示例 5 是 workspace 多 crate 版本——建议先按示例 1 落地，再迁移到示例 5，体会两种组织方式的取舍。

### 下一阶段
**Trait 与泛型阶段**（`ph07-trait-generics`，文档规划中）—— trait 定义与实现、泛型、trait 对象、关联类型。模块化解决"代码怎么组织"，trait 与泛型解决"行为怎么抽象"，两者结合才构成真实库工程的骨架。
