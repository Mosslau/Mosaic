# Rust 宏与元编程阶段

> 面向代码生成与编译期计算方向：本阶段从 `macro_rules!` 声明宏起步，理解宏如何在编译期把 token 变成代码，再到常用 derive 宏的使用（serde / thiserror，实测）与过程宏的概念——最终能判断「函数、泛型、宏」三层取舍，知道宏的维护成本。

## 1. 概述

Rust 宏与元编程阶段对应 roadmap 第 15 节，目标是**能使用声明宏和常见 derive 宏减少重复代码，并知道宏的维护成本**。具体定位是：**用 `macro_rules!` 写声明宏（匹配规则、片段分类符、repetition 重复展开、递归），用卫生性（hygiene）保证宏不污染调用方，把 `#[derive]` 从「会用」（ph07/ph13 只「用」不「写」）升级为「知道它在编译期做什么」，实测 serde/thiserror 两个 derive 宏的生成效果，再用 `cargo expand` 亲眼看到宏展开后的代码**。本阶段承接 ph07 trait 与泛型阶段（`#[derive(Debug, Clone, ...)]` 的 trait 语义基础）、ph11 错误处理与工程质量阶段（错误类型枚举 + thiserror 的生态讲解）、ph13 文件、网络与系统编程阶段（serde/clap derive 已「用」过，JSON 序列化/反序列化的用法基础）、ph14 Unsafe 与安全抽象阶段（「展开后的代码依然要过借用检查」——宏是编译期逃逸口，unsafe 是运行期逃逸口）；并为 [ph16 Rust Edition、工具链与版本管理阶段](../ph16-edition-toolchain/16-edition-toolchain.md)（工具链/edition 视角）、[ph17 Crate 生态选择与常用库阶段](../ph17-crate-ecosystem/17-crate-ecosystem.md)（生态视角）提供「宏与 derive 是怎么工作的」底层认知。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 声明宏 macro_rules! | 定义/调用、三种调用括号、多臂匹配、**声明宏 vs 函数差异**（3.1） |
| 匹配规则与片段分类符 | `expr`/`ident`/`ty`/`pat`/`literal`/`tt` 等元变量、先匹配先得、常见错误实测（3.2） |
| repetition 与递归 | `$(…)*`/`+`/`?` 重复展开、分隔符与尾逗号、编译期参数计数、递归收敛（3.3） |
| 卫生性 hygiene | 宏内变量不泄漏（实测）、宏参数 `ident` 指向调用方（实测）（3.4） |
| derive 宏使用 | derive 机制与宏展开顺序、serde derive 实测（3.5）、thiserror derive 实测（3.6） |
| 过程宏概念 | 三类过程宏、与声明宏的差异、最小标准代码结构（概念，不自写）（3.7） |
| 工具与维护 | cargo expand 观察宏展开（实测）、宏的维护成本与取舍（4、5） |

这个阶段只涉及 `macro_rules!` 声明宏（匹配规则、repetition、递归、卫生性）、常用 derive 宏的**使用**（serde/thiserror，含 `#[serde]`/`#[error]` 属性）与过程宏的**概念性理解**，**不涉及自写过程宏（用 syn/quote 开发自定义 derive/attribute 宏的完整工程，roadmap 无单列阶段，本阶段在 3.7 只给概念与最小标准代码骨架，完整开发作为第 5 章的进阶方向说明）、`macro 2.0`（声明宏的下一代语法，仍未稳定）、derive 的 trait 语义本身（trait 定义、derive 与手写 impl 的等价性，属 ph07 trait 与泛型阶段）、serde/crates 的生态用法（crate 选择、feature flags、其它数据格式，属 ph13 与 [ph17 Crate 生态选择与常用库阶段](../ph17-crate-ecosystem/17-crate-ecosystem.md)）**。承接 [ph07 trait 与泛型阶段](../ph07-trait-generics/07-trait-generics.md)：那里说「本阶段只『用』derive」，这里讲「derive 在编译期做了什么」；承接 [ph11 错误处理与工程质量阶段](../ph11-error-handling/11-error-handling.md)：thiserror 在 ph11 是「未在本环境验证」的生态讲解，本阶段补上实测（thiserror 2.0.20）；承接 [ph13 文件、网络与系统编程阶段](../ph13-file-network-sys/13-file-network-sys.md)：serde derive 的用法基础已在 ph13 示例 7/8 实测，本阶段把「derive 生成什么代码」用 cargo expand 摊开看；承接 [ph14 Unsafe Rust 与安全抽象阶段](../ph14-unsafe-safety-abstraction/14-unsafe-safety-abstraction.md)：unsafe 是运行时逃逸口，宏是编译期逃逸口——两个「高级逃逸口」的心智模型互补。

## 2. 来源与演变

宏来自 Lisp 的「代码即数据」传统，但 Rust 的宏观要克制得多：Rust 的目标是安全系统编程，**能通过函数/泛型/迭代器表达的抽象就绝不动宏**——宏是「编译器看不懂你的新语法时」的最后手段。设计哲学一句话加粗：**「宏 = 编译期的模式匹配代码生成：把一段 token 替换成另一段 token，替换完的代码继续走类型检查与借用检查」**。标准库里 `println!`/`format!`/`vec!`/`matches!`/`write!` 全是宏——它们需要「接受可变数量的参数 + 语法上像新关键字」，这是函数做不到的。

| 时间 | 里程碑 | 影响 |
|------|--------|------|
| 2015 | Rust 1.0（2015-05-15） | `macro_rules!`（声明宏）随 1.0 稳定——标准库的 `println!`/`vec!` 即由其实现 |
| 2017 | 自定义 derive 能力公布（Rust 1.15，2017-02） | 第三方能写「给结构体/枚举加 impl」的宏（serde_derive 是第一批用户） |
| 2017 | serde 1.0 发布 | 「数据模型与格式解耦」的序列化事实标准成型；derive 是它的入口 |
| 2018 | Rust 1.30（2018-10-25） | attribute 宏与 function-like 过程宏稳定；`proc_macro` API 稳定；宏可用 `use` 导入（来源：[Announcing Rust 1.30](https://blog.rust-lang.org/2018/10/25/Rust-1.30.0/)） |
| 2019 | thiserror 1.0（2019-10-09）发布 | 「库用 thiserror 生成错误样板」成为生态惯例（ph11 已记录，当时未实测） |
| 2024 | thiserror 2.0 发布 | 消息模板 API 收紧（如移除 `{r#type}` 写法）、新增 `#[error(fmt = …)]` 等（本环境实测 2.0.20） |
| 2025 | 本环境工具链：rustc 1.92.0 + cargo-expand 1.0.126 | 本文全部错误码（E0425 与两处宏展开错误）与运行输出均在本环境实测；serde 1.0.229 / serde_json 1.0.151 / thiserror 2.0.20 经 rsproxy 拉取实测 |

本文示例以 **Rust 2021 edition（rustc 1.92.0）** 为基线（与 ph10~ph14 一致：全仓库代码层统一 `rustc --edition 2021` 单文件编译；`macro_rules!` 与 derive 是自 1.0/1.30 起稳定的语言特性，2021 edition 下语法无后续版本变数）。**依赖策略**：macro_rules! 部分（示例 1~5、练习 1~3）只用标准库，零依赖、不联网；serde/thiserror 部分（示例 6~7、练习 4、综合项目）为第三方 crate，本环境已通过 rsproxy 国内镜像成功拉取并完整编译运行——serde 1.0.229 / serde_json 1.0.151 / thiserror 2.0.20，全部标注「已验证」（拉取失败环境则按「未在本环境验证」处理，见 examples/README）；**cargo-expand 1.0.126 已安装并实测**（roadmap 练习「用 cargo expand 观察宏展开」，底层机制 `rustc -Zunpretty=expanded` 同样实测）。本阶段语法（宏匹配规则、derive 属性）是 Rust 元编程里最稳定的部分，写错的宏报错信息反而最不稳定（随编译器版本措辞变化），文档内错误文本均为 rustc 1.92.0 实测。

## 3. 语法与参数

### 3.1 macro_rules! 声明宏：定义、调用、与函数的差异

`macro_rules!` 是「按模式匹配 token 流、生成替换代码」的宏：定义形如 `macro_rules! 名字 { (模式) => { 展开体 }; … }`，每次调用把「模式里捕获的元变量」替换进展开体，替换结果继续参与编译。展开发生在**编译期**，运行期零调用开销；宏收到的是 **token**（代码本身），不是算好的值——`stringify!` 能证明这一点（示例 1 实测：`show: 10 + 11 = 21`，说明 `stringify!(10 + 11)` 拿到的是 `"10 + 11"` 这串代码而不是 21）。

```rust
// examples/ex01-macro-basics.rs —— 声明宏入门（片段）
macro_rules! say {
    ($name:expr) => {
        // 展开体里的 $name 会被调用处传入的 token 原样替换
        println!("hello, {}!", $name);
    };
}

// 多臂宏：第一臂匹配字面量 0，第二臂匹配任意表达式（臂之间用 ; 分隔，从上到下先匹配先得）
macro_rules! classify {
    (0) => {
        "zero"
    };
    ($n:expr) => {
        "nonzero"
    };
}

fn main() {
    // 1. 三种调用括号等价：() [] {}
    say!("rust");
    say!["rust"];
    say!{"rust"}
    // 2. 宏可以生成「语句」，也可以生成「表达式」
    let d = double!(10 + 11); // 展开为 (10 + 11) * 2，宏展开发生在编译期
    println!("double!(10 + 11) = {d}");
}
```

**声明宏 vs 函数**（必会概念，roadmap 阶段验收「能判断函数、泛型和宏的取舍」的第一步）：

| 维度 | 函数 `fn` | 声明宏 `macro_rules!` |
|------|----------|----------------------|
| 何时执行 | 运行期调用 | 编译期展开（token → token） |
| 参数个数 | 签名固定 | 模式匹配：0~N 个、可选、尾逗号随便写 |
| 参数类型 | 签名强制 | 片段分类符粗约束（`expr`/`ident`/…），展开后才类型检查 |
| 卫生性 | — | 宏体标识符有卫生性，不污染调用方（3.4） |
| 递归 | 支持（运行期） | 支持（编译期；深度上限默认 128，可 `#[recursion_limit]` 调高） |
| 出错位置 | 函数体内 | 常定位到宏调用处 + 「error originates in the macro」提示（4 章） |
| 适用场景 | 逻辑复用 | 新语法形态 / 样板代码批量生成 |

**片段分类符（fragment specifier）** 是模式里 `$名字:种类` 的「种类」：它声明这个元变量匹配哪一类 token。完整的常用清单见 3.2 表格。

### 3.2 匹配规则与片段分类符

宏的「匹配」在 **token 层**发生：调用处给的 token 串从左到右与模式比对，元变量按分类符捕获一段 token，随后原样代入展开体。臂之间从上到下匹配，**先匹配先得**（示例 2 实测：`is_zero!(0)` 命中字面量 `0` 臂，`is_zero!(7)` 落到通用 `expr` 臂）。

| 片段分类符 | 匹配内容 | 示例（实测见 ex02） |
|-----------|---------|--------------------|
| `:expr` | 一个表达式 | `show!(10 + 11)` |
| `:ident` | 一个标识符（变量/类型/字段名…） | `let_var!(counter = 41)` |
| `:ty` | 一个类型 | `typed_let!(bignum: u32 = 40 + 2)` |
| `:pat` | 一个模式 | `matches_some!(Some(7), Some(_))` |
| `:literal` | 一个字面量（数字/字符串/字符/布尔） | `assert_big!(8080)` |
| `:tt` | 单个 token tree（单 token 或一组括号） | 递归 muncher 的搬运单元（练习 3） |
| `:path` | 一个路径 | `use`/调用路径 |
| `:meta` | 属性内容 | `#[serde(…)]` 里的内容 |
| `:lifetime` / `:vis` | 生命周期 `'a` / 可见性 `pub` | 进阶使用 |

`expr`/`ident`/`ty`/`pat`/`literal` 都能展开进代码的不同位置（示例 2 把它们写进 `let`、类型标注、`matches!` 模式、`assert!` 条件里）。一个关键区别：**`ident` 在展开后指向「调用方」的标识符**（能造变量、能引用调用方变量，3.4 细讲），而 `expr` 就是一段值代码。

```rust
// examples/ex02-macro-metavariables.rs —— 多臂匹配（片段）
macro_rules! is_zero {
    (0) => {
        println!("is_zero!(0)      -> 命中第一臂（字面量 0）");
    };
    ($x:expr) => {
        println!(
            "is_zero!({}) -> 命中第二臂（通用 expr），值 = {}",
            stringify!($x),
            $x
        );
    };
}
// 实测输出：is_zero!(0) -> 命中第一臂；is_zero!(7) -> 命中第二臂，值 = 7
```

**常见匹配错误（全部实测，见示例 5）**：① 两个独立 repetition 在同一层混用 → `error: meta-variable \`a\` repeats 3 times, but \`b\` repeats 2 times`；② 展开体引用未声明的元变量 → `error: expected expression, found \`$\``；③ 卫生性边界（宏体直接写调用方局部变量名）→ `error[E0425]: cannot find value ... in this scope`，提示定位到宏调用处。

### 3.3 repetition（重复展开）与递归

宏要批量生成代码，靠 repetition：**调用处写几个元素，展开体里的 `$(…)*` 就展开几份**。三个重复运算符：

| 运算符 | 含义 | 例子 |
|--------|------|------|
| `$( … )*` | 0 次或多次 | `my_vec![1, 2]` 展开两句 push；`my_vec![]` 零句 |
| `$( … )+` | 1 次或多次 | `($first, $($rest),+)` 保证至少两个参数 |
| `$( … )?` | 0 次或 1 次 | `$(,)?` 吞可选尾逗号 |

```rust
// examples/ex03-macro-repetition.rs —— my_vec!：复刻标准库 vec! 的最小版（片段）
macro_rules! my_vec {
    () => {
        Vec::new() // 空调用单独一臂：省掉不必要的 mut
    };
    ($($x:expr),+ $(,)?) => {{
        let mut v = Vec::new();
        $( v.push($x); )+ // 至少 1 个元素，这里至少展开 1 句 push
        v
    }};
}
// 实测输出：my_vec![1, 2, 3, 4] = [1, 2, 3, 4], len = 4；my_vec![]（0 个元素）= []
```

repetition 的三个实战要点（ex03 全部实测）：

- **空调用单独一臂**：若空调用也走重复臂，`$(v.push($x);)*` 展开零句，`let mut v` 的 `mut` 变成 unused——`-D warnings` 会拒绝（本环境实测踩到 `variable does not need to be mutable`，教训写成代码注释）。
- **尾逗号用 `$(,)?` 吞掉**：`my_vec![1, 2, 3,]` 与 `my_vec![1, 2, 3]` 结果一致（断言通过）。
- **计数用「单位数组长度」技巧**：`<[()]>::len(&[$(count_args!(@unit $x)),*])`——给每个参数生成一个 `()`，数组长度即参数个数；`@unit` 是私有辅助臂（`@` 开头的臂不会被正常调用命中）。实测 `count_args!(a, b, c, d, e) = 5`（`a`/`b` 无需预定义——宏只数 token 不碰值）。

**递归**：`macro_rules!` 支持递归，但递归必须靠「结构变短」收敛——每层调用把参数列表剥掉一个，直到只剩一个命中终点臂（练习 3 的 `sum_args!`/`last_arg!`：实测 `sum_args!(1, 2, 3, 4, 5, 6, 7, 8, 9, 10) = 55`——求和必须把参数逐个枚举传入，写 `sum_args!(1..=10)` 会被单参终点臂原样返回整个 range，宏按 token 匹配、不会替你遍历 range）。**宏不做算术**：想用 `$n - 1` 把 3 减到 0 是经典陷阱——`$n - 1` 是一串 token，永远不等于字面量 `0`，递归到展开深度上限报 `error: recursion limit reached while expanding \`down_from!\``（练习 3 实测文本）。同一层混用两个独立 repetition（`zip_bad!(1,2,3; 10,20)`）则报次数不一致错误（示例 5 实测）。

### 3.4 卫生性（hygiene）

**卫生性 = 宏展开引入的标识符不会与调用方作用域冲突**。实现上，每个 token 携带一个「来源位置」标记（syntax context）：宏体里写出来的标识符标记为「宏定义处」，调用方代码里的同名标识符标记为「调用处」——两者是不同名字，编译器不会搞混。这就是为什么 `vec!` 内部怎么定义临时变量都不怕撞名。

```rust
// examples/ex04-macro-hygiene.rs —— 卫生性实测（片段）
macro_rules! inner_secret {
    () => {{
        let secret = 42; // 宏体内造的标识符：卫生的，不污染调用方作用域
        println!("  （宏内部）secret = {secret}");
        secret
    }};
}

macro_rules! bump {
    ($v:ident, $by:expr) => {
        $v += $by; // 这里的 $v 指向调用方作用域中的变量（参数由调用方提供）
    };
}
```

实测（ex04 输出）：调用方声明 `secret = 7`，宏内部也有 `secret = 42`，两个断言都通过——宏内变量未泄漏/未冲突；而 `bump!(counter, 5)` 通过**传入的 `ident`** 把调用方的 `counter` 改成 5。两条规则要分清：

- **宏体自造的标识符是卫生的**——不会污染调用方，也拿不到调用方的局部变量（想引用调用方的东西必须作为 `expr`/`ident` 传进来；宏体里直接写调用方局部变量名是编译错误 E0425，示例 5 实测）；
- **调用方传进来的 `ident` 不卫生（有意为之）**——它展开后就是调用方作用域里的那个名字，宏因此能「替调用方改局部变量」。标准库里 `thread_local!` 之类需要访问调用方名字的宏就依赖这一点。

> 本阶段只要求「会用宏时知道变量不泄漏」与「需要交换数据就传参」；**hygiene 的完整语法上下文模型（混合卫生性、`$crate` 路径卫生、闭包捕获边界）属于进阶**，跨 crate 使用时 `$crate` 的路径卫生在综合项目（project/ 的 `#[macro_export]` + `$crate::Event`）里已给出可用范本，原理不展开。

### 3.5 derive 宏使用：机制 + serde derive 实测

`#[derive(Trait)]` 是「让编译器调用一个宏，为这个类型生成 `impl Trait`」的语法糖：std 的 `Debug`/`Clone`/`PartialEq`/`Hash` 由编译器内置实现（ph07 已「用」），第三方 crate 提供的 trait（`serde::Serialize`/`Deserialize`、`thiserror::Error`）由**过程宏**实现（3.7 讲概念）。derive 的属性（`#[serde(...)]`）是喂给这个宏的输入——宏读结构体/枚举的字段信息，生成对应的 impl 代码。

**derive 与宏展开的先后**：`macro_rules!` 的展开发生在 derive 处理之前——所以宏的展开体里可以写 `#[derive(...)]`，编译器先展开宏、再对生成的结构体跑 derive（综合项目 `define_events!` 就是这么把 derive 属性写进宏体的，实测可用）。

serde derive 用 `#[derive(Serialize, Deserialize)]` 给结构体/枚举生成「数据模型 ↔ 序列化器」的桥接代码（`serde_json` 只是众多格式实现之一，ph13 示例 7/8 已用）。常用 `#[serde(...)]` 属性（实测点见示例 6 / 练习 4 / 综合项目）：

```rust
// examples/crates/src/bin/ex06-serde-derive.rs —— serde derive 结构体（片段）
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ServerConfig {
    host: String,
    port: u16,
    max_connections: u32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    tls_cert: Option<String>,
}
```

| 属性 | 作用 | 实测点 |
|------|------|--------|
| `#[serde(rename_all = "camelCase")]` | 结构体/枚举所有字段/变体名整体转换（另有 `snake_case`/`kebab-case`/`PascalCase`…） | ex06：JSON 键 `maxConnections`/`tlsCert`；练习 4：`page_view` |
| `#[serde(default)]` | 反序列化缺字段时用 `Default::default()`（结构体级 = 全部字段可缺） | ex06：缺 `tlsCert` 成功；练习 4：缺 `referrer` 得 `""` |
| `#[serde(skip_serializing_if = "Option::is_none")]` | 满足条件时序列化跳过该字段 | ex06：`tls_cert = None` 时 JSON 无 `tlsCert` 键 |
| 外标签（enum 默认） | variant 名做 JSON 外层键 | 练习 4：`{"page_view":{...}}` / `{"signup":{...}}` |
| `#[serde(tag = "kind")]` | enum 内部标签：JSON 自带判别字段 | 综合项目：`{"kind":"login","user":"ada",...}` |
| 类型错误 | derive 生成的解析代码报行列号 | ex06：`invalid type: string "oops", expected u16 at line 1 column 25` |

实测（ex06 输出）：`{"host":"127.0.0.1","port":8080,"maxConnections":512,"tlsCert":"cert-a"}`（字段顺序 = 结构体声明顺序，derive 生成的序列化代码确定性可断言）；`tls_cert = None` 时输出无 `tlsCert` 键；JSON → 结构体往返一致断言通过。**用 cargo expand 摊开看**：`#[serde]` 属性被翻译成真实的序列化代码——`rename_all` 的效果是字段名字符串直接变成 `"maxConnections"` 写死在生成的 `serialize_field` 调用里，`skip_serializing_if` 变成 `if !Option::is_none(&self.tls_cert) { … } else { skip_field }` 分支，且整个 impl 包在 `const _: () = { extern crate serde as _serde; … }` 里保证路径卫生（完整摘录见 examples/README 与第 4 章）。

### 3.6 thiserror derive：错误样板一键生成

手写一个 `std::error::Error` 类型要三步：实现 `Display`、实现 `Error`、维护 `source()` 链（ph11 3.2 已讲纯 std 写法）。**thiserror 用 `#[derive(Error)]` 把这三步变成模板声明**：`#[error("消息模板")]` 生成 `Display`，`#[from]` 自动生成 `From<原类型>` 与 `source()`——零运行时开销（展开成普通 impl）。

```rust
// examples/crates/src/bin/ex07-thiserror-derive.rs —— thiserror derive（片段）
// #[derive(Error)] 需要同时 derive Debug（std::error::Error: Debug + Display 是编译期强制）
#[derive(Debug, Error)]
pub enum AppError {
    // 具名字段用 {name} 引用；元组字段用 {0} 引用（模板写法见主文档 3.6）
    #[error("配置文件不存在: {path}")]
    ConfigNotFound { path: String },
    #[error("端口 {port} 越界（合法范围 1-65535）")]
    InvalidPort { port: u32 },
    #[error("网络错误: {0}")]
    Network(String),
    // #[from]：自动生成 From<io::Error>，`?` 遇到 io::Error 自动转成 AppError::Io；
    // 同时自动成为 source() 的错误链下一环（io::Error 实现了 std::error::Error）
    #[error("IO 错误: {0}")]
    Io(#[from] std::io::Error),
}
```

实测（ex07 输出，thiserror 2.0.20）：`Display` 消息 `端口 70000 越界（合法范围 1-65535）`；错误可装箱 `Box<dyn std::error::Error>`；`?` 遇到 `io::Error` 自动转 `AppError::Io`（`read_to_string` 读不存在的文件，实测 `io.kind() = NotFound`）；`source()` 链长度 2：`["IO 错误: No such file or directory (os error 2)", "No such file or directory (os error 2)"]`。与 ph11 的关系：ph11 当时未装第三方 crate，thiserror 以「生态讲解」标注「未在本环境验证」；本阶段 rsproxy 拉取成功，把它实测补齐——「手写三步」与「derive 一键」产出等价代码，错误模型不变（枚举闭集、`source` 链）。

> 本阶段讲 thiserror **derive 的机制**（模板/`#[from]` 生成什么）；**错误处理的设计取舍（Display 写什么、错误链怎么分层、anyhow vs thiserror 的场景分工）在 ph11 错误处理与工程质量阶段已系统讲过**，这里不重复。

### 3.7 过程宏概念（不要求自写）

过程宏（procedural macro）是**用真实 Rust 代码写的、在编译期执行的宏**：输入一个 `TokenStream`，输出一个 `TokenStream`（替换用的代码）。与声明宏最大的不同：声明宏只能做「模式匹配 → 替换」这种机械变换，过程宏可以做任意计算——解析输入的结构（`syn` 把 `TokenStream` 变成可遍历的 AST）、按字段逐个生成代码（`quote` 拼代码）、返回精确错误。**serde 的 derive、thiserror 的 derive、clap 的 derive（ph13 ex09 用过）、`async_trait` 都是过程宏**。

| 维度 | `macro_rules!` 声明宏 | 过程宏 |
|------|----------------------|--------|
| 实现语言 | 匹配语法（无逻辑） | 真实 Rust 代码（编译期运行） |
| 输入/输出 | 模式捕获 token → 展开 | `TokenStream` → `TokenStream` |
| 卫生性 | 默认有 | 无内置——生成代码的标识符要自己管理（serde 用 `_serde`/`__` 前缀 + `const _` 包装，见 4 章） |
| 错误报告 | 定位到宏调用处 | 可返回带 `span` 的精确错误 |
| 定义位置 | 普通模块里（先定义后使用 / `#[macro_export]`） | 必须在 `type = "proc-macro"` 的独立 crate，只能导出宏 |
| 复杂度 | 低（写不长逻辑） | 高（解析 + 生成，需 syn/quote） |
| 典型 | `println!`/`vec!`/`matches!` | serde derive、thiserror、clap derive |

三类过程宏（概念，最小标准代码结构如下——**roadmap 只要求「过程宏概念」，本阶段不自写、也不在本环境验证自写过程宏**）：

```rust
// 概念示意：proc-macro crate 里的最小骨架（lib.rs；完整开发是进阶方向，见第 5 章）
use proc_macro::TokenStream;

#[proc_macro_derive(MyTrait)] // derive 宏：加在类型上
pub fn my_trait_derive(input: TokenStream) -> TokenStream {
    // 输入 = 类型定义本身的 token；用 syn 解析、quote 生成 impl，返回替换代码
    TokenStream::new()
}

#[proc_macro_attribute] // attribute 宏：加在函数/结构体上，如 #[route(GET, "/")]
pub fn my_attr(_attr: TokenStream, item: TokenStream) -> TokenStream { item }

#[proc_macro] // function-like 宏：形如 my_macro!(...)
pub fn my_fn_like(input: TokenStream) -> TokenStream { input }
```

## 4. 底层原理

**宏在编译管线的哪个环节？** 编译器把源文件切成 token 流后，就进入宏展开：`macro_rules!` 在 token 树上做模式匹配替换，过程宏调用真正的 Rust 代码变换 token 流；**展开是递归的**（宏展开出宏、直到没有宏为止），全部展开完才做语法分析、类型检查与借用检查——所以「宏展开后代码依然要过借用检查」（承接 ph14 的心智：unsafe 是运行时逃逸，宏只是编译期提前生成代码，逃不出类型系统）：

```text
源文件 ──词法分析──▶ token 流 ──宏展开（macro_rules! 匹配替换 / 过程宏变换，递归到无宏）──▶ AST
        ──▶ 借用检查 / 类型检查（展开后的代码照常过）──▶ HIR/MIR ──▶ LLVM IR ──▶ 机器码
```

**token tree**：token 流里最小可嵌套的单位——单个 token（`ident`/`literal`/`;`…）或一组括号 `(...)`/`[...]`/`{...}`。宏匹配不关心 token 之间的空白与换行，只按 token tree 结构匹配（所以 `say! {"rust"}` 和 `say!("rust")` 等价）；`stringify!` 会把捕获的 token 原样还原成字符串。用 `rustc -Zunpretty=expanded`（cargo expand 的底层机制）看 ex01 的真实展开（本环境实测节选）：

```text
// RUSTC_BOOTSTRAP=1 rustc --edition 2021 -Zunpretty=expanded ex01-macro-basics.rs（节选）
let d = (10 + 11) * 2;      // double!(10 + 11) 展开成括号表达式
let tag = "zero";           // classify!(0) 第一臂展开成字符串字面量
{ ::std::io::_print(format_args!("show: {0} = {1}\n", "10 + 11", 10 + 11)); };
//                          ^ stringify!(10 + 11) 在展开期就变成了字符串 "10 + 11"
```

**卫生性怎么实现**：每个标识符 token 携带一个语法上下文（syntax context）标记「这段代码来自哪里」。宏体自造的标识符带「宏定义处」上下文，调用方代码的标识符带「调用处」上下文——两者同名也不同名。**传给宏的 token 保留调用方上下文**，所以 `ident` 参数能指向调用方变量；而宏体内直接写调用方局部变量名，解析发生在宏定义处作用域，找不到就是 E0425（示例 5 实测）。跨 crate 时还有一层路径卫生：`#[macro_export]` 的宏体里引用自己的 crate 必须写 `$crate::`，否则展开到别的 crate 时路径断掉（综合项目 lib.rs 的 `impl $crate::Event` 即范本）。

**derive（过程宏）展开长什么样**：用 cargo expand 看 ex06（cargo-expand 1.0.126 实测，完整摘录见 examples/README）：`#[serde]` 属性被翻译成真正的序列化代码——字段名 `"maxConnections"` 直接写死在生成的 `serialize_field` 调用里（rename_all 的产物）、`skip_serializing_if` 变成 `if !Option::is_none(&self.tls_cert) { serialize_field } else { skip_field }` 分支、序列化结构体字段个数按条件动态算（`false as usize + 1 + 1 + 1 + if ... {0} else {1}`）；反序列化侧生成一个内部 `__Field` 枚举 + `__FieldVisitor` 做字段派发；整个 impl 包在 `const _: () = { extern crate serde as _serde; … }` 里——过程宏没有内置卫生性，serde 用「匿名 const 包装 + 别名引入」自己保证不污染命名空间。

**为什么宏的错误难读（维护成本）**：展开发生在类型检查之前，编译错误定位到「宏调用处」而不是宏内部出错的那一行；rustc 会补一句 `= note: this error originates in the macro ...`（示例 5 / 练习文件实测输出里都可见），完整追溯要 nightly 的 `-Z macro-backtrace`。加上 rustfmt 对宏体内部格式化的支持有限、rust-analyzer 在宏展开边界的补全与跳转体验打折——**宏写起来省样板，读起来/查错起来贵**。

## 5. 使用场景

- **声明宏：制造「新语法」与批量样板**——标准库的 `println!`/`format!`/`vec!`/`matches!`/`write!` 全部是宏（可变参数 + 语法形态是函数给不了的）；工程里最实用的是「把重复的代码模式收成一句」（练习 1 的 `log_fields!`、综合项目的 `define_events!`）。**什么时候不用**：能写函数就用函数（类型检查、IDE、测试都好）；函数不够再用泛型/trait（ph07）；两者都表达不了「语法形态」才上宏——「宏是最后手段」是社区共识，roadmap 阶段验收「能判断函数、泛型和宏的取舍」即此意。
- **derive 宏：数据结构样板一键生成**——`Debug`/`Clone`/`PartialEq`（std，ph07 已用）、序列化（serde）、错误类型（thiserror）、CLI 定义（clap，ph13 ex09 已用）。**什么时候不用**：需要自定义语义（如 ph07 的「按部分字段比较的 Hash」）时手写 impl 而不是硬凑 derive。
- **过程宏：框架与自动化样板**——使用方视角：`#[derive(...)]` 和 `#[属性]` 只是注解，不需要懂内部；作者视角：当样板重复到「声明宏写不动 + 需要解析自定义语法」时（如 ORM 的 entity、Web 框架的路由注解），才值得自写过程宏（syn/quote）——代价是编译时间变长、proc-macro 必须独立成 crate、错误体验要自己打磨。这是本阶段之后的进阶方向（roadmap 未单列阶段，参考 The Rust Reference 与 The Little Book of Rust Macros）。
- **跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：C 宏是预处理期**文本替换**——无类型、无卫生性，参数副作用与命名冲突全靠纪律防；C++ 模板是类型级元编程——强大但错误信息爆炸、编译慢；Rust 宏是 **token 级展开 + 卫生性**，且分成「声明宏（简单机械）」与「过程宏（编译期程序）」两级，复杂度按需选择；Lisp 宏是「代码即数据」的同像性宏，自由度最高、约束最少。四种语言对「编译期生成代码」给出了四种「自由 vs 安全」配比。

## 6. 代码示例

本节展示完整可运行示例的关键片段，完整文件在 `examples/` 目录（示例 1~5 全部 `rustc --edition 2021 -D warnings` 单文件编译、产物输出 `/tmp/`；示例 6~7 是 cargo 工程 `examples/crates/`，验证环境 rustc 1.92.0 macOS arm64，serde 1.0.229 / serde_json 1.0.151 / thiserror 2.0.20）：

### 示例 1：声明宏入门（ex01-macro-basics.rs）

```rust
// examples/ex01-macro-basics.rs —— macro_rules! 声明宏入门：定义/调用/三种括号/多臂匹配/stringify! 观察「宏收到 token」
// 编译：rustc --edition 2021 -D warnings ex01-macro-basics.rs -o /tmp/ex01
macro_rules! say {
    ($name:expr) => {
        // 展开体里的 $name 会被调用处传入的 token 原样替换
        println!("hello, {}!", $name);
    };
}
fn main() {
    say!("rust");
    say!["rust"];
    say!{"rust"}
    let d = double!(10 + 11); // 展开为 (10 + 11) * 2
    println!("double!(10 + 11) = {d}");
    let tag = classify!(0); // 命中第一臂（字面量 0）
    let tag2 = classify!(42); // 命中第二臂（通用 expr）
    println!("classify!(0) = {tag}, classify!(42) = {tag2}");
    show!(10 + 11);
    show!(vec![1, 2, 3].len());
}
```

实测输出：`hello, rust!` ×3、`double!(10 + 11) = 42`、`classify!(0) = zero, classify!(42) = nonzero`、`show: 10 + 11 = 21`、`show: vec![1, 2, 3].len() = 3`。

### 示例 2：片段分类符与多臂匹配（ex02-macro-metavariables.rs）

```rust
// examples/ex02-macro-metavariables.rs —— 片段分类符实测：expr/ident/ty/pat/literal；多臂匹配「先匹配先得」
// 编译：rustc --edition 2021 -D warnings ex02-macro-metavariables.rs -o /tmp/ex02
macro_rules! let_var {
    ($name:ident = $init:expr) => {
        let $name = $init;
    };
}
macro_rules! typed_let {
    ($name:ident: $t:ty = $init:expr) => {
        let $name: $t = $init;
    };
}
macro_rules! matches_some {
    ($v:expr, $p:pat) => {
        matches!($v, $p)
    };
}
fn main() {
    let_var!(counter = 41);
    typed_let!(bignum: u32 = 40 + 2);
    println!(
        "matches_some!(Some(7), Some(_)) = {}",
        matches_some!(Some(7), Some(_))
    );
    is_zero!(0);
    is_zero!(7);
}
```

实测输出：`counter = 41`、`bignum = 42`、`matches_some!(Some(7), Some(_)) = true`、`is_zero!(0)` 命中第一臂 / `is_zero!(7)` 命中第二臂（详见文件内注释）。

### 示例 3：repetition 重复展开（ex03-macro-repetition.rs）

```rust
// examples/ex03-macro-repetition.rs —— repetition（重复展开）实测：$(…)* / + / ?、分隔符、尾逗号、参数计数
// 编译：rustc --edition 2021 -D warnings ex03-macro-repetition.rs -o /tmp/ex03
macro_rules! my_vec {
    () => {
        Vec::new() // 空调用单独一臂：省掉不必要的 mut
    };
    ($($x:expr),+ $(,)?) => {{
        let mut v = Vec::new();
        $( v.push($x); )+ // 至少 1 个元素，这里至少展开 1 句 push
        v
    }};
}
fn main() {
    let v = my_vec![1, 2, 3, 4];
    println!("1. my_vec![1, 2, 3, 4] = {:?}, len = {}", v, v.len());
    echo_args!(1, 2 + 3, 4 * 10);
    println!("5. count_args!(a, b, c, d, e) = {}", count_args!(a, b, c, d, e));
    println!(
        "6. min_len_2!(1, 2, 3) 参数个数 = {}（两个参数也接受: {}）",
        min_len_2!(1, 2, 3),
        min_len_2!(1, 2)
    );
}
```

实测输出：`my_vec![1, 2, 3, 4] = [1, 2, 3, 4], len = 4`、`echo_args!` 逐参数打印 `arg 1: 2 + 3 = 5`、`count_args!(a, b, c, d, e) = 5`、`min_len_2!(1, 2, 3) 参数个数 = 3`。

### 示例 4：卫生性实测（ex04-macro-hygiene.rs）

```rust
// examples/ex04-macro-hygiene.rs —— 卫生性实测：宏内变量不泄漏到调用方；传入 ident 指向调用方（参数不卫生是特性）
// 编译：rustc --edition 2021 -D warnings ex04-macro-hygiene.rs -o /tmp/ex04
macro_rules! inner_secret {
    () => {{
        let secret = 42; // 宏体内造的标识符：卫生的，不污染调用方作用域
        println!("  （宏内部）secret = {secret}");
        secret
    }};
}
macro_rules! bump {
    ($v:ident, $by:expr) => {
        $v += $by; // 这里的 $v 指向调用方作用域中的变量（参数由调用方提供）
    };
}
fn main() {
    let secret = 7;
    let got = inner_secret!();
    assert_eq!(secret, 7); // 宏没有改掉调用方的 secret
    assert_eq!(got, 42); // 宏内部 secret 是 42
    let mut counter = 0;
    bump!(counter, 5);
    println!("2. bump!(counter, 5) 后 counter = {counter}（宏通过参数修改调用方变量）");
}
```

实测输出：调用方 `secret = 7` 与宏内 `secret = 42` 互不干扰（断言通过：宏内变量未泄漏到调用方）；`bump!(counter, 5)` 后 `counter = 5`。

### 示例 5：声明宏典型编译错误（ex05-macro-errors.rs，故意编译失败）

> ⚠️ **运行前提**：本示例故意编译失败，用于实测三个宏错误，请勿期待编译成功。

```rust
// examples/ex05-macro-errors.rs —— 声明宏典型编译错误实测（故意编译失败，勿期待编译通过）
// 编译（预期失败）：rustc --edition 2021 -D warnings ex05-macro-errors.rs -o /tmp/ex05
macro_rules! zip_bad {
    ($($a:expr),*; $($b:expr),*) => {
        // 实测错误：error: meta-variable `a` repeats 3 times, but `b` repeats 2 times
        $( println!("a={} b={}", $a, $b); )*
    };
}
fn main() {
    demo_zip_bad();
    demo_undeclared();
    demo_hygiene();
}
```

实测错误（一次编译三个，rustc 1.92.0）：`error: meta-variable \`a\` repeats 3 times, but \`b\` repeats 2 times`、`error: expected expression, found \`$\``（引用未声明的元变量 `$undeclared`）、`error[E0425]: cannot find value \`total\` in this scope`（卫生性边界，提示定位到宏调用处）——完整错误文本见 examples/README。

### 示例 6~7：serde / thiserror derive（cargo 工程 crates/，已验证）

`examples/crates/` 是独立 cargo 工程（`Cargo.toml` 声明 serde/serde_json/thiserror，`Cargo.lock` 已提交锁定版本；rsproxy 拉取，`CARGO_TARGET_DIR` 指向 /tmp）。关键片段与实测输出（完整文件见 `examples/crates/src/bin/`）：

```rust
// examples/crates/src/bin/ex06-serde-derive.rs —— serde derive 实测：derive 生成序列化代码 + #[serde] 属性
// 构建：cd examples/crates && CARGO_TARGET_DIR=/tmp/ph15-examples-target cargo run --bin ex06-serde-derive
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ServerConfig {
    host: String,
    port: u16,
    max_connections: u32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    tls_cert: Option<String>,
}
```

实测输出：`1. 序列化（tls_cert = Some）: {"host":"127.0.0.1","port":8080,"maxConnections":512,"tlsCert":"cert-a"}`（`tls_cert = None` 时无 `tlsCert` 键）；`3. 反序列化往返一致 = true`；`4. 缺失 tlsCert 反序列化成功: tls_cert = None`；`5. 类型错误消息: invalid type: string "oops", expected u16 at line 1 column 25`。

```rust
// examples/crates/src/bin/ex07-thiserror-derive.rs —— thiserror derive 实测：#[derive(Error)] + #[error] 模板 + #[from]
// 构建：cd examples/crates && CARGO_TARGET_DIR=/tmp/ph15-examples-target cargo run --bin ex07-thiserror-derive
#[derive(Debug, Error)]
pub enum AppError {
    #[error("配置文件不存在: {path}")]
    ConfigNotFound { path: String },
    #[error("端口 {port} 越界（合法范围 1-65535）")]
    InvalidPort { port: u32 },
    #[error("网络错误: {0}")]
    Network(String),
    #[error("IO 错误: {0}")]
    Io(#[from] std::io::Error),
}
```

实测输出：`1. 配置文件不存在: /etc/app.toml`、`2. 端口 70000 越界（合法范围 1-65535）`、`5. \`?\` 自动转换: io.kind() = NotFound`、`6. source 错误链: ["IO 错误: No such file or directory (os error 2)", "No such file or directory (os error 2)"]`。

cargo expand 观察宏展开（roadmap 练习 3）在 `examples/crates` 下实测（cargo-expand 1.0.126）：`CARGO_TARGET_DIR=/tmp/ph15-examples-target cargo expand --bin ex06-serde-derive`，展开摘录与观察要点见 examples/README；单文件宏的展开用 `RUSTC_BOOTSTRAP=1 rustc --edition 2021 -Zunpretty=expanded ex01-macro-basics.rs`（第 4 章节选）。

## 7. 总结

### 关键要点

- **宏 = 编译期的模式匹配代码生成**：`macro_rules!` 收到 token、替换 token，展开产物照常过类型/借用检查（承接 ph14：「展开后代码依然要过借用检查」）；函数做不到「可变参数 + 新语法形态」，宏为此而生
- **取舍顺序**：函数 → 泛型/trait → 宏；能编译成普通代码就不用宏——宏的维护成本在「错误难读、格式化/IDE 支持有限」
- **匹配规则**：片段分类符（`expr`/`ident`/`ty`/`pat`/`literal`/`tt`…）声明「捕获哪类 token」；多臂从上到下先匹配先得；repetition 的 `*`/`+`/`?` 决定「展开几份」；递归靠结构变短收敛、宏不做算术（数值递归会 `recursion limit reached`，实测）
- **卫生性是实测可证的**：宏内变量不泄漏（ex04 断言通过）、传入的 `ident` 指向调用方（`bump!(counter, 5)` 实测）；宏体直接写调用方局部变量名 = E0425（ex05 实测）
- **derive = 编译器替类型调用宏生成 impl**：serde derive 生成序列化/反序列化代码（rename_all/default/skip/tag 属性实测），thiserror derive 生成 Display/Error/source/From（`#[error]` 模板 + `#[from]` 实测，thiserror 2.0.20）；cargo expand 亲眼可见这些代码
- **过程宏概念**：输入 TokenStream 输出 TokenStream 的编译期程序，三类（derive/attribute/function-like）；无内置卫生性（serde 用 `const _` + `_serde` 别名自管）；本阶段不自写
- **实测错误清单**：repetition 次数不一致 / 未声明元变量 `$` / E0425 卫生性边界 / `recursion limit reached`——全部 rustc 1.92.0 实测写入

### 阶段验收清单

- [ ] 能判断函数、泛型和宏的取舍（「先函数、再泛型、宏最后」），并说清各自的代价
- [ ] 能写基本 `macro_rules!`（多臂 + repetition），能调试基本宏匹配错误（对着实测错误文本定位：repetition 混用 / 未声明元变量 / 卫生性 E0425）
- [ ] 能让宏生成代码保持可读边界（展开体小而清晰、用 `{{ }}` 包块、可借助 cargo expand / `-Zunpretty=expanded` 检查展开结果——本阶段已实测）
- [ ] 能用 derive 宏生成样板代码：serde（序列化/反序列化 + `#[serde]` 属性）与 thiserror（错误模板 + `#[from]`）——两个都是本环境实测
- [ ] 能解释卫生性（宏内变量不泄漏、参数 ident 指向调用方），知道过程宏与声明宏的本质区别（TokenStream 程序 vs 模式匹配）

### 跨语言对比

- C 宏是预处理期文本替换（无类型、无卫生性）；C++ 模板是类型级元编程（错误爆炸）；Rust 是 token 级展开 + 卫生性 + 声明宏/过程宏两级；Lisp 是同像性宏（代码即数据）——四种「编译期生成代码」的自由度/安全配比是 analysis/ 的素材（详见第 5 章）。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题（log_fields! 日志宏 / swap_vars! 卫生性 / 递归声明宏 / serde derive 序列化）后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**事件结构体宏（event-hub）**——`define_events!` 声明宏批量生成事件结构体与统一打印（`render()`/`kind()`），配合 serde derive 内部标签统一序列化与 thiserror derive 错误建模（roadmap 推荐项目「为多类事件生成统一打印、校验或序列化辅助代码」落地；`demo` 5 段断言与实测输出见 project/README）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[Rust Edition、工具链与版本管理阶段](../ph16-edition-toolchain/16-edition-toolchain.md) — 宏与 derive 的展开结果由工具链驱动：cargo-expand（本阶段已实测的观察工具）与 `rustc -Zunpretty=expanded` 是 nightly 特性的稳定化封装，edition 选择决定宏/路径/借用规则按哪套规则编译；`macro_rules!` 与 2021/2024 edition 的兼容行为、`#[macro_export]` 跨 edition 语义也将在那里从「工具链管理」视角收束。
