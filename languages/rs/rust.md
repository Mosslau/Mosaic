# Rust 语言学习 Roadmap

> 面向安全高性能数据基础设施、KV / LSM 存储、向量数据库、异步网络服务、AI Agent 工具后端和跨语言加速模块，重点建立内存安全、并发安全和可交付工程能力。

## 1. Rust 基础语法阶段

> 📖 详细展开版见 [ph01-basic-syntax/01-basic-syntax.md](./ph01-basic-syntax/01-basic-syntax.md)

### 目标

能写简单 Rust 程序，理解 Rust 与 C/C++ 在类型、表达式和安全模型上的基础差异。

### 学习内容

- Rust 安装、rustup、cargo new/run/build、rustc
- fn main、变量绑定、mut、常量、shadowing
- 基本类型、元组、数组、字符串
- if、loop、while、for、match
- 函数、表达式、语句、println!

### 必会概念

- 默认不可变
- 静态类型
- 表达式有值
- 编译期检查

### 示例

```rust
fn main() {
    let name = "Rust";
    println!("Hello, {}", name);
}
```

### 练习

- 写 Hello Rust
- 猜数字游戏（基础版）
- 温度转换器
- 把 `if`/`else` 分支改写成 `match`
- 命令行计算器

### 阶段验收

- 能独立创建并运行 cargo 项目
- 能解释 mut、shadowing、表达式返回值
- 能根据编译错误定位基础语法问题

### 推荐项目

- 命令行计算器：支持加减乘除、错误输入提示和基础测试。

## 2. 所有权 Ownership 阶段

> 📖 详细展开版见 [ph02-ownership/02-ownership.md](./ph02-ownership/02-ownership.md)

### 目标

掌握 Rust 最核心的内存管理规则，能写出不依赖 GC 且不手动释放内存的安全代码。

### 学习内容

- 所有权移动 move
- Copy 与 Clone
- 不可变借用与可变借用
- 引用作用域
- String、&String、&str、slice

### 必会概念

- 一个值同一时刻只有一个 owner
- 可变引用与不可变引用不能同时活跃
- 借用不拥有资源
- 所有权规则用于避免悬垂引用和数据竞争

### 示例

```rust
fn print_len(s: &str) {
    println!("{}", s.len());
}

fn main() {
    let text = String::from("rust");
    print_len(&text);
    println!("{}", text);
}
```

### 练习

- 把会移动所有权的函数改成借用参数
- 练习 String、&str、slice 的转换
- 修复一组典型借用检查错误（E0382 / E0502）
- 用借用重写一个频繁 clone 的函数，对比改动前后的所有权流向

### 阶段验收

- 能解释 move 后变量为什么不可用
- 能选择传值、不可变借用或可变借用
- 能修复常见借用检查错误

### 推荐项目

- 文本统计器：统计行数、单词数、最长单词，并尽量减少 clone。

## 3. 基础数据结构阶段

> 📖 详细展开版见 [ph03-data-structure/03-data-structure.md](./ph03-data-structure/03-data-structure.md)

### 目标

能使用结构体、枚举和集合表达真实业务数据。

### 学习内容

- struct、tuple struct、unit struct
- impl 方法
- Vec、HashMap、HashSet
- 数组、元组、slice
- derive Debug、Clone、PartialEq

### 必会概念

- 结构体字段所有权
- self、&self、&mut self
- 集合扩容与元素所有权
- HashMap entry API

### 示例

```rust
use std::collections::HashMap;

fn main() {
    let mut scores = HashMap::new();
    scores.insert("alice", 90);
    scores.entry("bob").or_insert(80);
    println!("{:?}", scores);
}
```

### 练习

- 定义 User、Device、Order 等结构体
- 用 Vec 保存记录并排序过滤
- 用 HashMap 做分组统计

### 阶段验收

- 能用结构体和 impl 封装数据行为
- 能根据场景选择 Vec 或 HashMap
- 能避免集合遍历中的所有权问题

### 推荐项目

- 索引注册表：支持新增索引、按名称查询、按类型统计。
- 数据源注册表：支持新增数据源、按名称查询、按类型统计。

## 4. Option 和 Result 阶段

> 📖 详细展开版见 [ph04-option-result/04-option-result.md](./ph04-option-result/04-option-result.md)

### 目标

用类型系统表达缺失值和错误，让失败路径可见、可处理。

### 学习内容

- Option<T>、Some、None
- Result<T, E>、Ok、Err
- unwrap、expect 的适用边界
- 问号运算符
- map、and_then、unwrap_or_else

### 必会概念

- 空值显式化
- 可恢复错误
- 错误传播
- 组合子链式处理

### 示例

```rust
fn parse_port(input: &str) -> Result<u16, std::num::ParseIntError> {
    let port = input.parse::<u16>()?;
    Ok(port)
}
```

### 练习

- 把随意 unwrap 改为 Result 返回
- 用 Option 处理可选配置项
- 写一组解析函数并串联问号运算符

### 阶段验收

- 能判断何时使用 Option 或 Result
- 能解释问号运算符如何传播错误
- 能在业务代码中避免无理由 panic

### 推荐项目

配置解析器：读取端口、超时、开关项，输出结构化配置或明确错误。

## 5. 模式匹配与枚举阶段

> 📖 详细展开版见 [ph05-pattern-match/05-pattern-match.md](./ph05-pattern-match/05-pattern-match.md)

### 目标

用 enum 和 match 表达状态、协议类型和业务分支。

### 学习内容

- enum 定义与携带数据
- match 穷尽匹配
- if let、while let
- 模式守卫
- 结构体、元组、引用解构

### 必会概念

- 代数数据类型
- 穷尽性检查
- 状态建模
- 不可达分支

### 示例

```rust
enum Event {
    Connected(String),
    Disconnected,
}

fn handle(event: Event) {
    match event {
        Event::Connected(id) => println!("{} connected", id),
        Event::Disconnected => println!("offline"),
    }
}
```

### 练习

- 用 enum 表达订单状态或设备状态
- 把字符串状态码改成 enum
- 用 match 处理不同消息类型

### 阶段验收

- 能用 enum 替代魔法字符串
- 能写出无遗漏 match
- 能读懂 Option/Result 的匹配写法

### 推荐项目

- 数据事件处理器：处理写入、删除、更新、过期和告警事件。

## 6. 模块化与 Cargo 阶段

> 📖 详细展开版见 [ph06-cargo-module/06-cargo-module.md](./ph06-cargo-module/06-cargo-module.md)

### 目标

能组织多文件 Rust 项目，掌握 Cargo 的日常工程工作流。

### 学习内容

- mod、pub、use
- lib.rs 与 main.rs
- crate、module、package
- Cargo.toml 依赖管理
- features 与 workspace 入门

### 必会概念

- 可见性边界
- 模块路径
- 二进制 crate 与库 crate
- 语义化版本

### 示例

```rust
// src/lib.rs
pub mod parser;

// src/parser.rs
pub fn parse(input: &str) -> Vec<&str> {
    input.lines().collect()
}
```

### 练习

- 把单文件项目拆成 model、parser、service
- 添加第三方 crate 并固定版本
- 创建一个 workspace 管理多个 crate

### 阶段验收

- 能解释 crate、package、module 的关系
- 能设计清晰 pub API
- 能熟练使用 cargo build/test/fmt/clippy

### 推荐项目

- 多模块日志分析工具：parser、aggregator、cli 分层清楚。

## 7. Trait 与泛型阶段

> 📖 详细展开版见 [ph07-trait-generics/07-trait-generics.md](./ph07-trait-generics/07-trait-generics.md)

### 目标

用 trait 和泛型抽象行为，同时保持类型安全和零成本抽象。

### 学习内容

- trait 定义与实现
- 泛型函数和结构体
- trait bound、where 子句
- impl Trait
- 常见 derive trait

### 必会概念

- 静态分发
- trait 约束
- 孤儿规则
- 对象安全初步

### 示例

```rust
trait Encode {
    fn encode(&self) -> String;
}

fn print_encoded<T: Encode>(value: &T) {
    println!("{}", value.encode());
}
```

### 练习

- 为多个结构体实现同一个 trait
- 把重复函数改造成泛型函数
- 练习 where 子句约束复杂泛型

### 阶段验收

- 能用 trait 表达能力而不是具体类型
- 能解释泛型单态化的基本影响
- 能处理常见 trait bound 编译错误

### 推荐项目

- 序列化接口：为日志记录、索引元数据、向量记录实现统一编码 trait。

## 8. 生命周期 Lifetime 阶段

> 📖 详细展开版见 [ph08-lifetimes/08-lifetimes.md](./ph08-lifetimes/08-lifetimes.md)

### 目标

理解引用有效期，能处理函数、结构体和泛型中的生命周期约束。

### 学习内容

- 生命周期省略规则
- 显式生命周期参数
- 结构体持有引用
- static 生命周期
- 生命周期与泛型组合

### 必会概念

- 生命周期描述引用关系，不延长引用本身
- 输入引用与输出引用的约束
- 悬垂引用禁止
- 拥有数据可简化生命周期

### 示例

```rust
fn longest<'a>(a: &'a str, b: &'a str) -> &'a str {
    if a.len() >= b.len() { a } else { b }
}
```

### 练习

- 为返回引用的函数添加生命周期
- 把不必要的引用字段改成拥有字段
- 整理含泛型和生命周期的 where 子句

### 阶段验收

- 能说明生命周期参数表达的约束
- 能判断何时应返回拥有值
- 能修复 borrowed value does not live long enough

### 推荐项目

- 只读配置视图：从配置文本中借用字段并提供查询接口。

## 9. 集合、迭代器与函数式写法阶段

> 📖 详细展开版见 [ph09-collections-iterators/09-collections-iterators.md](./ph09-collections-iterators/09-collections-iterators.md)

### 目标

用迭代器写出简洁、可组合的数据处理代码。

### 学习内容

- Iterator trait
- iter、iter_mut、into_iter
- map、filter、fold、collect
- 闭包捕获
- 惰性求值

### 必会概念

- 迭代器适配器与消费器
- 所有权进入迭代器的方式
- 闭包 Fn/FnMut/FnOnce
- 零成本抽象

### 示例

```rust
let nums = vec![1, 2, 3, 4];
let sum: i32 = nums.iter().filter(|n| **n % 2 == 0).sum();
println!("{}", sum);
```

### 练习

- 用迭代器重写 for 循环统计
- 练习 collect 到 Vec 和 HashMap
- 用 fold 实现聚合
- 闭包捕获三种模式（Fn/FnMut/FnOnce 与意外移动）
- 迭代器与借用冲突（复现 E0502 并修复）

### 阶段验收

- 能选择 iter、iter_mut、into_iter
- 能读懂常见链式迭代器
- 能避免因闭包捕获造成意外移动

### 推荐项目

- 日志数据聚合器：过滤异常记录并计算错误分布、延迟分布和来源统计。

## 10. 智能指针阶段

> 📖 详细展开版见 [ph10-smart-pointers/10-smart-pointers.md](./ph10-smart-pointers/10-smart-pointers.md)

### 目标

掌握常见智能指针，能表达堆分配、共享所有权和内部可变性。

### 学习内容

- Box<T>
- Rc<T> 与 Arc<T>
- RefCell<T> 与 Mutex<T>
- Deref、Drop
- Weak<T> 避免循环引用

### 必会概念

- 堆分配
- 引用计数
- 内部可变性
- 运行时借用检查
- 线程安全共享

### 示例

```rust
use std::rc::Rc;

let shared = Rc::new(String::from("config"));
let another = Rc::clone(&shared);
println!("{} {}", shared, another);
```

### 练习

- 用 Box 构建递归链表
- 用 Rc 共享只读配置
- 用 RefCell 实现内部可变性并制造一次借用冲突（BorrowMutError）
- 用 Arc<Mutex<_>> 做线程间计数
- 用 Weak 打破循环引用

### 阶段验收

- 能区分 Box、Rc、Arc 的场景
- 能说明 RefCell 的风险
- 能避免循环引用泄漏

### 推荐项目

- 规则树执行器：用 Box 表达递归规则，用 Rc 共享规则元数据。

## 11. 错误处理与工程质量阶段

> 📖 详细展开版见 [ph11-error-handling/11-error-handling.md](./ph11-error-handling/11-error-handling.md)

### 目标

建立可维护的错误模型和基础工程质量习惯。

### 学习内容

- 自定义错误类型
- thiserror 与 anyhow
- 错误上下文
- tracing/log 日志
- 单元测试与集成测试

### 必会概念

- 库代码偏向具体错误
- 应用代码可使用上下文错误
- 错误链
- 可观测性
- 测试金字塔

### 示例

```rust
#[derive(Debug, thiserror::Error)]
enum AppError {
    #[error("invalid input: {0}")]
    InvalidInput(String),
}
```

### 练习

- 为解析模块定义错误枚举
- 为 I/O 错误添加上下文
- 补充正常路径和异常路径测试

### 阶段验收

- 能让错误信息定位问题
- 能用测试覆盖核心分支
- 能让日志便于排查且不泄露敏感信息

### 推荐项目

- 可靠 CLI：读取文件、解析数据、输出报告，并提供清晰错误提示。

## 12. 并发与异步阶段

> 📖 详细展开版见 [ph12-concurrency-async/12-concurrency-async.md](./ph12-concurrency-async/12-concurrency-async.md)

### 目标

能编写线程安全和异步 I/O 程序，理解 Send/Sync 边界。

### 学习内容

- thread::spawn
- channel
- Arc、Mutex、RwLock
- async/await
- Tokio 任务、定时器、网络 I/O

### 必会概念

- 数据竞争在编译期受限
- Send 与 Sync
- 阻塞与非阻塞
- 任务调度
- 背压

### 示例

```rust
use tokio::time::{sleep, Duration};

#[tokio::main]
async fn main() {
    sleep(Duration::from_millis(100)).await;
    println!("done");
}
```

### 练习

- 用 channel 汇总多个线程结果
- 用 tokio 并发请求多个接口
- 为共享状态增加锁并评估粒度

### 阶段验收

- 能解释线程与 async task 的区别
- 能避免在 async 中长时间阻塞
- 能处理任务取消和超时

### 推荐项目

- 异步采集器：并发拉取多个数据源状态，超时重试并汇总结果。

## 13. 文件、网络与系统编程阶段

> 📖 详细展开版见 [ph13-file-network-sys/13-file-network-sys.md](./ph13-file-network-sys/13-file-network-sys.md)

### 目标

能使用 Rust 处理文件、路径、网络和常见系统资源。

### 学习内容

- std::fs 与 std::io
- Path 与 PathBuf
- TCP/UDP 基础
- serde JSON/TOML
- 命令行参数 clap

### 必会概念

- 缓冲 I/O
- 路径跨平台
- 序列化与反序列化
- 资源释放由 Drop 管理

### 示例

```rust
use std::fs;

fn main() -> std::io::Result<()> {
    let text = fs::read_to_string("config.toml")?;
    println!("{}", text.len());
    Ok(())
}
```

### 练习

- 读取大文件并逐行处理（迷你 wc）
- 递归统计目录大小
- 写一个 TCP 时间戳服务器（echo server 变体）
- 手写极简 JSON 解析器
- 手写子命令式 CLI 解析器

### 阶段验收

- 能写出清晰的 I/O 错误处理
- 能让路径处理不依赖硬编码分隔符
- 能让网络程序处理断连和超时

### 推荐项目

- 日志转发器：读取文件尾部变化并通过 TCP 发送到服务端。

## 14. Unsafe Rust 与安全抽象阶段

> 📖 详细展开版见 [ph14-unsafe-safety-abstraction/14-unsafe-safety-abstraction.md](./ph14-unsafe-safety-abstraction/14-unsafe-safety-abstraction.md)

### 目标

理解 unsafe 的能力边界，只在必要时封装最小不安全代码。

### 学习内容

- unsafe 关键字
- 裸指针
- unsafe fn
- FFI 调用基础
- 安全抽象封装

### 必会概念

- unsafe 不关闭借用检查
- 不变量由开发者维护
- 未定义行为
- 最小 unsafe 边界

### 示例

```rust
let mut value = 42;
let ptr = &mut value as *mut i32;

unsafe {
    *ptr += 1;
}
```

### 练习

- 阅读标准库中的 unsafe 封装示例
- 把 unsafe 块包在安全函数内
- 为 unsafe 抽象写边界测试

### 阶段验收

- 能说明每个 unsafe 块的必要性和不变量
- 能避免用 unsafe 绕过普通编译错误
- 能识别 UB 风险

### 推荐项目

- 受控缓冲区封装：提供安全 API，内部用少量 unsafe 操作切片。

## 15. 宏与元编程阶段

> 📖 详细展开版见 [ph15-macros-metaprogramming/15-macros-metaprogramming.md](./ph15-macros-metaprogramming/15-macros-metaprogramming.md)

### 目标

能使用声明宏和常见 derive 宏减少重复代码，并知道宏的维护成本。

### 学习内容

- macro_rules!
- 声明宏匹配规则
- derive 宏使用
- 过程宏概念
- serde derive、thiserror derive

### 必会概念

- 编译期代码生成
- token tree
- 宏展开
- 卫生性 hygiene

### 示例

```rust
macro_rules! say {
    ($name:expr) => {
        println!("hello {}", $name);
    };
}

say!("rust");
```

### 练习

- 写一个生成日志字段的 macro_rules 宏
- 用 serde derive 生成序列化代码
- 用 cargo expand 观察宏展开

### 阶段验收

- 能判断函数、泛型和宏的取舍
- 能调试基本宏匹配错误
- 能让宏生成代码仍保持可读边界

### 推荐项目

- 事件结构体宏：为多类事件生成统一打印、校验或序列化辅助代码。

## 16. Rust Edition、工具链与版本管理阶段

> 📖 详细展开版见 [ph16-edition-toolchain/16-edition-toolchain.md](./ph16-edition-toolchain/16-edition-toolchain.md)

### 目标

能管理 Rust 版本、Edition 和项目工具链，保证团队环境一致。

### 学习内容

- rustup toolchain
- stable、beta、nightly
- Edition 2018/2021/2024
- rust-toolchain.toml
- Cargo.lock 策略

### 必会概念

- Edition 不是编译器版本
- MSRV
- 锁文件对应用和库的不同意义
- 工具链可复现

### 示例

```toml
# rust-toolchain.toml
[toolchain]
channel = "stable"
components = ["rustfmt", "clippy"]
```

### 练习

- 为项目固定 toolchain
- 检查依赖的 MSRV
- 执行一次 Edition 迁移演练

### 阶段验收

- 能说明 Edition 与 toolchain 的区别
- 能保持 CI 与本地工具链一致
- 能为依赖升级记录版本并提供回退方案

### 推荐项目

- 团队模板仓库：包含工具链文件、CI、格式化、lint 和 README 约定。

## 17. Crate 生态选择与常用库阶段

### 目标

能评估并选择可靠 crate，避免盲目引入依赖。

### 学习内容

- crates.io、docs.rs
- serde、tokio、reqwest、clap、tracing
- sqlx、diesel、sea-orm 简介
- semver 与 feature flags
- cargo tree 与依赖审计

### 必会概念

- 维护活跃度
- API 稳定性
- 依赖树膨胀
- 许可证兼容

### 示例

```toml
[dependencies]
serde = { version = "1", features = ["derive"] }
tracing = "0.1"
```

### 练习

- 为 HTTP 客户端比较 reqwest 与 hyper
- 检查 crate 最近发布和 issue 状态
- 用 cargo tree 观察依赖树

### 阶段验收

- 能在引入依赖前说明理由
- 能控制 feature 范围
- 能发现高风险或无人维护 crate

### 推荐项目

- 依赖评审报告：列出核心 crate、用途、风险和替代方案。

## 18. Borrow Checker 调试专项阶段

### 目标

系统掌握借用检查错误的定位与重构方法。

### 学习内容

- 常见错误 E0382、E0499、E0502、E0597
- 缩短借用作用域
- 拆分结构体字段借用
- 使用索引或临时变量
- 必要时引入拥有数据

### 必会概念

- 活跃借用范围
- 两阶段借用
- 字段级借用
- 重构优先于 clone

### 示例

```rust
let mut items = vec![1, 2, 3];
{
    let first = items[0];
    println!("{}", first);
}
items.push(4);
```

### 练习

- 收集 5 个借用错误并写修复说明
- 把长借用拆成短作用域
- 比较 clone、索引、拆结构体三种修复方式

### 阶段验收

- 能根据错误提示找到真实冲突
- 能在修复时避免过度 clone
- 能解释重构后的所有权流向

### 推荐项目

- 借用错误练习集：每个案例包含错误版、修复版和解释。

## 19. 内存布局、零拷贝与协议解析阶段

### 目标

理解数据布局和字节处理，能实现高效、安全的协议解析。

### 学习内容

- repr(C)、repr(packed) 风险
- 字节序
- slice 与 buffer
- bytes crate
- nom 或 winnow 解析器

### 必会概念

- 对齐 alignment
- padding
- 零拷贝借用
- 边界检查
- 网络序

### 示例

```rust
fn read_u16_be(buf: &[u8]) -> Option<u16> {
    let bytes: [u8; 2] = buf.get(0..2)?.try_into().ok()?;
    Some(u16::from_be_bytes(bytes))
}
```

### 练习

- 解析固定头部二进制协议（含大端/小端字段）
- 用切片返回借用数据
- 解析 WAL record
- 解析 SSTable block header
- 实现 length-prefix frame parser

### 阶段验收

- 能避免直接把不可信字节转成结构体引用
- 能处理长度不足和非法字段
- 能让解析过程尽量少复制

### 推荐项目

- 二进制 record 解析器：解析消息头、时间戳、record ID 和 payload 字段。
- WAL record 解析器：解析 record header、sequence、key、value 和 checksum 字段。

## 20. 测试体系进阶阶段

### 目标

建立覆盖单元、集成、属性和基准的测试体系。

### 学习内容

- 单元测试与集成测试目录
- test fixtures
- mock 与 fake
- proptest
- criterion 基准测试

### 必会概念

- 可测试设计
- 属性测试
- 回归测试
- 基准噪声控制

### 示例

```rust
#[test]
fn parses_number() {
    assert_eq!("42".parse::<u32>().unwrap(), 42);
}
```

### 练习

- 为解析器加入异常样例测试
- 用 proptest 测边界输入
- 用 criterion 对比优化前后性能

### 阶段验收

- 能让核心逻辑有正反测试
- 能让 bug 修复伴随回归测试
- 能让性能结论有可重复基准

### 推荐项目

- record 解析测试套件：包含真实样例、错误样例、基准测试。

## 21. Clippy、rustfmt、CI 与代码质量阶段

### 目标

用工具链自动化保持代码风格、质量和可交付性。

### 学习内容

- cargo fmt
- cargo clippy
- clippy lint 等级
- GitHub Actions 或其他 CI
- 缓存与矩阵构建

### 必会概念

- 自动格式化
- 静态检查
- 质量门禁
- CI 可重复性

### 示例

```yaml
steps:
  - run: cargo fmt --check
  - run: cargo clippy -- -D warnings
  - run: cargo test
```

### 练习

- 给项目加 fmt/clippy/test CI
- 清理 clippy warnings
- 配置 pre-commit 或本地检查脚本

### 阶段验收

- 能让 PR 通过格式化、lint 和测试
- 能为 lint 例外给出明确理由
- 能让 CI 输出便于定位失败

### 推荐项目

- Rust CI 模板：可复用于 CLI、服务端和库项目。

## 22. 性能优化与 Profiling 阶段

### 目标

能基于测量进行优化，而不是凭感觉修改代码。

### 学习内容

- release/profile 配置
- criterion
- flamegraph/perf
- 内存分配分析
- 算法复杂度与数据结构选择

### 必会概念

- 先测量后优化
- 热路径
- 分配次数
- 缓存局部性
- 内联与单态化影响

### 示例

```toml
[profile.release]
lto = true
codegen-units = 1
```

### 练习

- 为热点函数建立基准
- 减少临时 String 分配
- 比较 Vec、HashMap、BTreeMap 的性能

### 阶段验收

- 能在优化前后给出数据对比
- 能在优化中不牺牲正确性和可维护性
- 能定位主要瓶颈而非微调冷路径

### 推荐项目

- 日志聚合性能优化：从基准出发降低处理延迟和内存占用。

## 23. Rust FFI 与跨语言接口设计阶段

### 目标

能安全地把 Rust 与 C、C++、Python 或其他语言集成。

### 学习内容

- extern "C"
- cdylib/staticlib
- CString/CStr
- bindgen/cbindgen
- pyo3 简介

### 必会概念

- ABI 稳定
- 所有权跨边界
- 错误码与结果转换
- 内存由谁分配谁释放

### 示例

```rust
#[no_mangle]
pub extern "C" fn add(a: i32, b: i32) -> i32 {
    a + b
}
```

### 练习

- 导出一个 C 可调用函数
- 用 cbindgen 生成头文件
- 把 Rust 函数包装成 Python 扩展

### 阶段验收

- 能让接口只暴露 ABI 稳定类型
- 能让跨语言内存释放规则明确
- 能让错误处理不跨 FFI 直接 panic

### 推荐项目

- Rust 加速库：为 Python 提供高性能解析、向量距离计算或 RAG chunk 处理函数，并附带测试。

## 24. 安全、供应链与发布阶段

### 目标

能发布可信 Rust 软件，并管理依赖、漏洞和制品。

### 学习内容

- cargo audit
- cargo deny
- 许可证检查
- secret 管理
- crates.io 发布流程

### 必会概念

- 供应链风险
- SBOM
- 最小权限
- 可复现构建
- 版本发布策略

### 示例

```toml
# deny.toml 片段
[licenses]
allow = ["MIT", "Apache-2.0"]
```

### 练习

- 对项目跑 cargo audit/deny
- 整理许可证清单
- 编写 CHANGELOG 和 release notes

### 阶段验收

- 能为依赖漏洞制定处理策略
- 能让发布包内容可审查
- 能让版本号和变更说明一致

### 推荐项目

- 安全发布流水线：自动测试、审计、构建、打包和生成发布说明。

## 25. Rust 数据基础设施专项阶段

### 目标

面向 KV 存储、LSM Tree、Raft KV、向量检索和 Agent 工具后端，构建安全、高性能、可测试的数据基础设施组件。

### 学习内容

- WAL append / replay、MemTable、SSTable
- Bloom Filter、Compaction、Snapshot
- MVCC 简化模型、Raft 日志复制基础
- HNSW 向量检索基础
- Axum / Tonic 数据服务、pyo3 Python 加速模块

### 必会概念

- WAL 用于崩溃恢复
- SSTable 是不可变有序文件
- LSM 通过顺序写提升写入吞吐，但会引入 compaction 成本
- Raft 通过日志复制保证多副本状态一致
- HNSW 用图结构提升近似最近邻搜索效率
- Rust 的所有权模型适合封装安全的存储和并发抽象
- Agent 工具后端要关注权限、超时、审计和可观测性

### 示例

为聚焦接口设计，示例省略了依赖声明；实际项目需在 Cargo.toml 中引入 `anyhow`、`serde_json`、`async-trait`。

```rust
#[derive(Debug, Clone)]
pub enum WalRecord {
    Put { key: Vec<u8>, value: Vec<u8> },
    Delete { key: Vec<u8> },
}

pub trait KvStore {
    fn put(&mut self, key: Vec<u8>, value: Vec<u8>) -> anyhow::Result<()>;
    fn get(&self, key: &[u8]) -> anyhow::Result<Option<Vec<u8>>>;
    fn delete(&mut self, key: &[u8]) -> anyhow::Result<()>;
}

#[async_trait::async_trait]
pub trait Tool {
    async fn call(&self, input: serde_json::Value) -> anyhow::Result<serde_json::Value>;
}
```

### 练习

- 实现 WAL append / replay 与 MemTable
- 实现 Mini SSTable writer / reader 并增加 Bloom Filter
- 实现基础 compaction 与 Mini Raft KV 的单节点状态机
- 实现 HNSW toy version 并输出 recall / QPS 指标
- 用 Axum 暴露 KV / 检索 API，并用 pyo3 暴露一个解析函数给 Python

### 阶段验收

- 能通过 WAL 恢复 put / delete 操作
- 能按 key 查询 SSTable
- 能完成基础 range scan
- 能解释 LSM 的读放大、写放大和空间放大
- 能解释 Raft 的 leader election 和 log replication
- 能输出向量检索 recall、QPS、P95 延迟和内存占用
- 能设计可被 Agent 调用的稳定工具 API
- 能构建 Python 调用 Rust 的加速模块

### 推荐项目

- Rust KV Store
- Mini LSM
- Mini Raft KV
- Time-series KV 原型
- HNSW toy implementation
- RAG vector index benchmark
- Agent 工具服务
- Python 调用 Rust 加速库

## 附录：阶段性项目验收标准

### 目标

用项目验收串联 Rust 能力，形成可展示作品集。

### 学习内容

- 需求拆解
- 模块边界
- 错误与日志规范
- 测试覆盖
- 性能与发布清单

### 必会概念

- 交付闭环
- 验收用例
- 可维护性
- 可观测性
- 文档化

### 示例

```text
验收清单：cargo fmt --check / cargo clippy / cargo test / README / release build
```

### 练习

- 为每个阶段项目写 README
- 补齐使用示例和失败示例
- 建立项目验收表

### 阶段验收

- 能让项目从零构建运行
- 能让核心路径有测试
- 能让错误处理清楚
- 能记录性能和安全风险

### 推荐项目

- 异步数据基础设施网关，包含二进制解析、缓存、HTTP API、日志、测试和 CI。
- Agent 工具网关，包含工具注册、权限校验、HTTP API、日志、测试和 CI。

## 推荐学习顺序

```text
→ Rust 基础语法
→ 所有权 / 借用
→ String / Vec / struct / enum
→ Option / Result
→ match 模式匹配
→ Cargo / module
→ trait / 泛型
→ 生命周期
→ 迭代器 / 闭包
→ 智能指针
→ 错误处理 / 测试
→ 并发 / async
→ 系统编程 / 网络编程
→ unsafe / FFI
→ 内存布局 / 零拷贝 / 二进制格式
→ WAL / SSTable / LSM / KV
→ Raft / 分布式状态机
→ 向量检索 / HNSW
→ Agent 工具后端
→ pyo3 / Python 加速模块
```

---

## Rust 和 C / C++ 的核心区别

| 方向   | C                | C++         | Rust           |
| ---- | ---------------- | ----------- | -------------- |
| 内存管理 | 手动 `malloc/free` | RAII + 智能指针 | 所有权 + 借用检查     |
| 空值   | `NULL`           | `nullptr`   | `Option<T>`    |
| 错误处理 | 错误码              | 异常 / 错误码    | `Result<T, E>` |
| 泛型   | 宏 / void 指针      | 模板          | 泛型 + trait     |
| 并发安全 | 程序员保证            | 程序员保证       | 编译期限制数据竞争      |
| 面向对象 | 无                | class / 继承  | struct + trait |
| 运行时  | 很小               | 取决于用法       | 无 GC，运行时很小     |
| 数据基础设施 | 常用于底层库 | 常用于数据库内核 | 适合安全高性能组件 |
| 跨语言扩展 | C ABI 常用 | pybind11 常用 | pyo3 / FFI 常用 |

---

## 项目路线

### 初级项目

- 猜数字游戏
- 计算器
- 通讯录
- 文件统计工具
- 简单日志工具
- Todo CLI

### 中级项目

- CSV 解析器
- JSON 配置读取器
- 命令行工具
- 词频统计器
- TCP echo server
- 简单 HTTP server
- Ring Buffer
- 线程安全队列

### 高级项目

- 多线程任务队列
- 异步 HTTP 服务
- 日志采集系统
- KV 存储引擎
- WebSocket 服务
- 内存池
- Mini LSM
- Mini Raft KV
- HNSW toy implementation
- RAG vector index benchmark
- Agent 工具服务
- FFI / pyo3 加速库

### 数据基础设施 / AI Infra 项目

- Rust KV Store
- Mini LSM
- Time-series KV 原型
- Mini Raft KV
- WAL / SSTable 文件库
- 向量检索库
- Agent 工具网关
- Python 调用 Rust 加速模块

---

## 对你最推荐的 Rust 路线

如果你的目标是 **KV 库、数据库内核、向量库、AI Agent 工具后端和 Python/RAG 加速模块**，建议走这条线：

```text
Rust 基础
→ 所有权 / 借用
→ struct / enum / match
→ Option / Result
→ trait / 泛型
→ Cargo / workspace
→ 错误处理 / tracing / 测试
→ Tokio / async
→ Axum / Tonic
→ 文件 IO / mmap / bytes
→ unsafe 安全边界
→ WAL / SSTable / LSM
→ Raft KV
→ HNSW / 向量检索
→ Agent 工具服务
→ pyo3 / Python 加速模块
```

重点掌握：所有权、借用检查、Option、Result、match、struct、enum、trait、lifetime、Vec、HashMap、Arc、Mutex、Tokio、Axum、Tonic、bytes、mmap、unsafe、WAL、SSTable、LSM、Raft、HNSW、criterion、tracing、pyo3、maturin。

## 从 C/C++ 转 Rust 的学习建议

- 不要用 unsafe 模拟 C 指针写法，先用所有权、借用和类型系统解决问题。
- 少用全局可变状态，多用结构体、trait 和明确的数据流。
- 遇到 borrow checker 错误时优先缩短借用作用域，而不是立刻 clone。
- 把 Result 当成默认错误通道，把 panic 留给不可恢复错误或测试。
