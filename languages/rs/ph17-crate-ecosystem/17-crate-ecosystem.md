# Rust Crate 生态选择与常用库阶段

> 面向生态工程化方向：本阶段从 crates.io 与 docs.rs 起步，学会像工程师一样评估「这个 crate 能不能引进来」，再把 serde / tokio / reqwest / clap / tracing 与三个 ORM 读透选对，最后用 semver、feature flags 与 cargo tree 系好依赖治理的缰绳——最终能把「加依赖」从一拍脑袋升级为一份可辩护的决策。

## 1. 概述

Rust Crate 生态选择与常用库阶段对应 roadmap 第 17 节，目标是**能评估并选择可靠 crate，避免盲目引入依赖**。具体定位是：**会用 crates.io 与 docs.rs 两个生态入口找 crate 并读 API 文档；掌握一套评估 crate 的六维清单（维护活跃度 / API 稳定性 / 依赖树膨胀 / 许可证兼容 / unsafe 面 / MSRV）；把 serde、tokio、reqwest、clap、tracing 五员大将的定位、选型边界与常见坑讲透；给 sqlx / diesel / sea-orm 三个 ORM 做一次有依据的三选一；把 semver 与 feature flags 当「依赖间的契约语言」理解；用 cargo tree / cargo audit / cargo deny / cargo diet 做依赖治理，为 ph24 的完整供应链安全打前置**。本阶段承接 ph06 模块化与 Cargo 阶段（Cargo.toml 的依赖写法与 `cargo build` 基础）、ph13 文件、网络与系统编程阶段（serde / clap 已被「用」过，阻塞式网络已见）、ph16 Rust Edition、工具链与版本管理阶段（那里预告：MSRV 检查、`cargo metadata`、锁文件与 resolver 语义正是「评估 crate 能不能引进来」的工具底座——本阶段 3.2 正式兑现，并把 ph16 project/ 的「依赖引入约定」登记表升级为完整评审清单）；并为 [ph18 Borrow Checker 调试专项阶段](../ph18-borrow-checker-debug/18-borrow-checker-debug.md)、ph21 Clippy、rustfmt、CI 与代码质量阶段（roadmap 第 21 节，目录待建；依赖治理进 CI 闸门）、ph24 安全、供应链与发布阶段（roadmap 第 24 节，目录待建；完整供应链安全）铺路。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 生态入口 | crates.io 注册表 / 索引语义、docs.rs 文档站点与阅读习惯（3.1） |
| crate 评估 | 六维评审清单：维护活跃度、API 稳定性、依赖树膨胀、许可证兼容、unsafe 面、MSRV（3.2） |
| 常用库 · 数据 | serde 序列化事实标准：derive 机制、性能、数据格式矩阵（3.3） |
| 常用库 · 异步 | tokio 生态全景：runtime / async I/O / select / 任务调度；何时不需要 tokio（3.4） |
| 常用库 · 网络 | reqwest 与 hyper 的关系与取舍（3.5） |
| 常用库 · CLI | clap 的 derive vs builder（3.6） |
| 常用库 · 日志 | tracing 与 log 的关系、tracing 的 span/event/结构化（3.7） |
| 常用库 · 数据库 | sqlx / diesel / sea-orm 简介与三选一对比表（3.8） |
| 契约语言 | semver 规则与 breaking change 判断、feature flags 语义（默认特性 / 特性统一 / 与 cfg 配合）（3.9） |
| 依赖治理 | cargo tree / audit / deny / diet、供应链安全前置（3.10） |
| 底层原理 | cargo 依赖解析：版本区间、resolver、feature 统一、Cargo.lock 与 metadata 的关系（4） |
| 场景与练习 | 何时引、何时不引、何时升级；examples/exercises/project 四层配套（5~7） |

这个阶段只涉及 crate 的**评估、选择与依赖治理**，以及 serde / tokio / reqwest / clap / tracing / 三 ORM 的**选型级认知与教学性使用**，**不涉及 tokio 内部机制与 async/await 语言层面的深入用法（runtime 工作原理、`select!` 宏细节、任务调度调优——属于 ph12 并发与异步阶段；阻塞式文件网络系统编程本身属于 ph13 文件、网络与系统编程阶段，tokio 版的网络用法已在 ph12/ph13 用过）、derive 宏的展开实现细节（属于 ph15 宏与元编程阶段，本阶段只讲「用 serde 的 derive 时要带哪些认知」）、完整供应链安全体系（SBOM、签名、发布完整性——属于 ph24 安全、供应链与发布阶段，roadmap 第 24 节，目录待建，本阶段只做「评审 + 审计命令」的前置）、借用错误的系统化调试（属于 [ph18 Borrow Checker 调试专项阶段](../ph18-borrow-checker-debug/18-borrow-checker-debug.md)）**。本阶段在 3.x 引用的 crate 版本区间、行为与维护状态以写作时 crates.io 为准；代码验证状态按文件头与 README 标注为准——ex02（serde）与 sol-04（feature 控制）已在 cargo 1.92.0 本机实测并标注「已验证」，其余依赖联网拉取 crate 的示例标注「未在本环境验证」，需要时按各文件头注释给出的命令在联网环境复跑。

## 2. 来源与演变

Rust 的依赖生态不是「后来才有的」，它与语言本身同年诞生。2014 年 11 月，Rust 团队在 [Cargo: Rust's community crate host](https://blog.rust-lang.org/2014/11/20/Cargo/) 宣布了 crate 分发方案：**cargo 负责解析与构建，crates.io 负责托管与索引**，二者在 2015 年随 Rust 1.0 一同成为默认工程形态。设计哲学一句话加粗：**「依赖管理是编译系统的原生职责，不是事后补的工具」**——这一决策让 Rust 从一开始就没有 C/C++ 那种「手动下源码、手工管版本」的割裂期，也让「依赖图」成为每个 Rust 工程随时可见、可查、可审的一等公民。

生态的第二次分水岭是 **docs.rs**：每个 crate 的每个版本都自动构建并发布 API 文档，文档与源码版本一一对应。docs.rs 最初是社区服务，如今运行于 Rust 官方基础设施之下（[Rust Forge 的 docs-rs 页面](https://forge.rust-lang.org/docs-rs/index.html) 记录其构建规则与运营状态）。它和 crates.io 一起回答了选型的第一个问题：「这个 crate 有没有人维护、文档写得怎么样、API 长什么样」。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| cargo 与 crates.io 上线 | 2014 | cargo 成为默认构建工具，crates.io 作为社区 crate 托管站开张（官方博客 2014-11-20 宣布）；2015 随 Rust 1.0 成为默认形态 |
| docs.rs | 约 2016 | 每版本自动构建 API 文档；后并入 Rust 官方基础设施；支持 feature 组合文档化 |
| log / env_logger 时代 | 2014~2019 | `log` 作为日志门面（facade）成为事实标准：库只发日志记录、应用选实现器 |
| serde 1.0 | 2017 | David Tolnay 主导的序列化框架稳定（承 rust-serialize 时代衣钵），derive + 零拷贝反序列化路线定形 |
| tokio 立项与 1.0 | 2016 立项 / 2020-12 发布 1.0 | async/await 落地的运行时事实标准；生态整合（mio → tokio）、1.0 兼容承诺 |
| RustSec / cargo-audit | 2018 | RustSec advisory-db 与 `cargo audit` 出现，漏洞公告与依赖审计进入日常工作流 |
| tracing 0.1 | 2019 | tokio 团队推出的结构化诊断框架：span/event + 结构化字段，面向 async 程序 |
| clap 4 | 2022 | derive 路径成为主流写法；错误提示、帮助排版大幅进化 |
| cargo-deny / cargo-diet | 约 2020 | Embark 系治理工具：deny 做许可/漏洞/重复依赖门禁，diet 做「打包最小文件集」审查 |
| sqlx / diesel / sea-orm | 2016~2023 | 三个数据库访问层各自定型：diesel 1.0（2017）/ 2.0（2022）、sqlx 0.x（2019 起）、sea-orm 1.0（2023） |
| cargo 依赖治理深化 | 2020~2025 | feature 语义收紧（v1→v2→v3 resolver）、`cargo tree`/`cargo metadata` 常态化、MSRV 感知解析（RFC 3537，见 ph16） |
| 本环境工具链 | 2025-12 | rustc/cargo 1.92.0 + rustup 1.28.2（macOS arm64）；本阶段为纯写作沙箱，代码全部标注「未在本环境验证」 |

**为什么「会选 crate」是一门值得单开阶段的学问？** 对照历史：C/C++ 生态把「引第三方库」的成本外推给了每个构建系统（autotools / cmake / vcpkg / conan 各自为政），Python 把「依赖解析」推迟到 pip 时代才系统化（早期 setup.py + 全局 site-packages 的依赖地狱是教材级案例）。Rust 选了另一条路：**cargo 从一开始就做「可复现 + 可观测」的依赖图**——锁文件让选定的版本可复现（ph16 已讲），`cargo tree` 让依赖图随时可见，crates.io 的下载量 / 最近更新 / 许可证元数据让选型有据可查。代价是：**选择权被下放给了开发者**——编译器不拦你引入一个无人维护的 crate，正确性靠你的评审能力。这正是本阶段存在的理由。

本文示例以 **rustc 1.8x+ / edition 2021** 为基线（edition 2021 自 Rust 1.56 起就是生态事实默认，与 ph10~ph16 全仓库代码层一致——单文件示例统一 `--edition 2021`；rustc 1.8x+ 覆盖 2021 edition 时代的活跃支持区间，本阶段讨论的 semver 解析、feature 合并、`cargo tree`/`cargo metadata` 行为在该区间与更新版本间一致），**crate 版本以 crates.io 当前稳定为参照**（写作时：serde 1.x、tokio 1.x、reqwest 0.12、clap 4.x、tracing 0.1.x、sqlx 0.8、diesel 2.x、sea-orm 1.x——示例一律写主版本区间不钉小版本，小版本随 crates.io 日期漂移，锁定行为以 ph16 的锁文件策略为准），验证工具链 **rustc/cargo 1.92.0（macOS arm64，rustup 1.28.2 管理）**。这个阶段的主题——crate 评审维度、semver 契约、feature 语义、依赖图治理——是 Rust 生态里最稳定的部分：serde/tokio 的 1.x 兼容承诺与 semver 规则自发布起不变，你今天学的评审方法五年后依然适用；会漂的只有具体版本号与个别 API 细节，以 docs.rs 当前版本为准即可。

## 3. 语法与参数

本章按「入口 → 评审方法 → 六大常用库逐个读透 → 契约语言（semver/features）→ 治理工具」的顺序推进。前两节（3.1/3.2）是**元能力**——不绑定具体库，教你怎么看、怎么评；3.3~3.8 是**具体库**的选型级认知；3.9/3.10 回到**工程机制**。章节代码与命令的可运行完整版见 `examples/`，练习见 `exercises/`。

### 3.1 crates.io 与 docs.rs：生态入口怎么读

**crates.io 是「找得到 + 有元数据」的注册表**。每个 crate 页面给出五类信息，恰好构成评审的第一手材料：

| crates.io 页面信息 | 含义 | 对应评审维度 |
|------|------|---------|
| 版本列表与发布时间 | 最近一次 publish 距今多久 | 维护活跃度 |
| Downloads / Recent Downloads | 全时段与近 90 天下载量 | 采用面（警惕：下载量可被旧版本长期累积，近 90 天更敏感） |
| Dependencies 表 | 该版本直接依赖了哪些 crate | 依赖树膨胀（点进每个依赖看它又依赖什么） |
| Categories / Keywords | crate 的定位标签 | 快速判断是不是同类问题里的主流解 |
| Owners / 仓库链接 / 许可证 | 维护者组织、源码位置、license 字段 | 维护活跃度 / 许可证兼容 |
| Docs.rs badge（`docs.rs` 链接） | 每版本 API 文档 | API 稳定性与文档质量 |

配套心智：**crates.io 的版本列表附带每个版本的 rust-version（MSRV）与 edition**——ph16 预告的「选 crate 要看它的 rust-version」在这里就能先扫一眼，再进 `cargo metadata` 核实。crates.io 页面底部还列出**依赖反向图**（谁依赖了这个 crate），评估「上游挂了影响面多大」很有用。

**docs.rs 是「读 API」的地方**。三个使用习惯值得养成：

```text
docs.rs/<crate>/<版本>/<crate>/            ← 按版本读，别读 latest 忘了版本漂移
右上角 Feature flags 面板                   ← 看默认开了哪些 feature、可选哪些
src 链接（每页顶部）                        ← 从签名跳实现，看 unsafe 面与内部行为
```

- 文档顶部按 feature 分栏列出「开启哪些 feature 后哪些 API 可用」——这是 docs.rs 独有的价值：**同一份源码按不同 feature 组合构建出不同文档**，等于把 3.9 的 feature 语义可视化
- 读库型 crate 先找 `lib.rs` 的模块地图（`crate::` 一级导出），再看 Examples 章节——官方示例是「最小可用姿势」的最快路径
- **版本漂移警惕**：docs.rs 默认展示的版本与 crates.io 的 yanked（撤回）状态同步；`#[deprecated]` 标注在文档里带删除线，升级前扫一遍目标版本的变化日志（CHANGELOG / Releases 标签）比读源码快得多

> ⚠️ crates.io 与 docs.rs 的具体 UI 随年份改版，本节描述的是 2025 年的版式；**判据（版本时间、下载量、依赖表、许可证、MSRV）不变**，版式变化不影响评审流程。

### 3.2 评估一个 crate：六维评审清单

**评估的本质是回答三个问题：它能干我要的活吗？它还能活多久？它出事了我兜得住吗？** 三个问题展开成六个维度。六维清单承接 ph16 的工具底座——**MSRV 检查（`cargo metadata` + resolver v3）、`rust-version` 字段、锁文件**都是第 6 维的直接工具；ph16 project/ 的「依赖引入约定」登记表（用途/维护活跃度/替代品/MSRV 影响）是下面这张清单的最简原型，本阶段把它补成完整的六维。

| 维度 | 看什么 | 判据（哪个信号危险） | 工具/入口 |
|------|--------|---------------------|---------|
| ① 维护活跃度 | 最近 publish 时间、issue/PR 响应、commit 频率、维护者数量 | 一年以上没发版 + issue 无人应答；单点维护者且长期失联；依赖它的知名项目开始 fork | crates.io 版本列表、GitHub 仓库、[crates.io 反向依赖](https://crates.io) |
| ② API 稳定性 | 主版本号是否 ≥1、semver 遵守记录、CHANGELOG、`#[deprecated]` 清理节奏 | 0.x 常驻 + 破坏性小版本升级（0.x 的 minor 可破坏）；从不写 CHANGELOG；API 与文档对不上 | docs.rs 版本 diff、CHANGELOG、Release notes |
| ③ 依赖树膨胀 | 直接依赖数量、每个依赖又拖了多少传递依赖、是否有多个大件（tokio/openssl）重复出现 | 一个「干小事」的 crate 拖进 50+ 传递依赖；为一个小功能引入带 openssl 的依赖；`cargo tree` 里同一 crate 多版本并存 | `cargo tree`、crates.io Dependencies 表 |
| ④ 许可证兼容 | license 字段、SPDX 表达式、商用条款 | 无 license 字段或非标准标识；Copyleft（GPL/AGPL）与你产品的分发模式冲突；依赖树里混进不兼容许可 | crates.io license 字段、`cargo deny check licenses`（3.10） |
| ⑤ unsafe 面 | 源码里 `unsafe` 出现位置与密度、是否集中封装、有没有 `#![forbid(unsafe_code)]` 的上层约束 | unsafe 散布全库无封装注释；unsafe 做「绕过借用检查的便利」而非「FFI/性能边界的必要」；历史 CVE 记录 | docs.rs 源码阅读、`cargo geiger`（统计 unsafe）、RustSec 公告 |
| ⑥ MSRV 与版本兼容 | `rust-version` 是否高于你的 MSRV、resolver v3 是否已帮你过滤、edition 新旧 | rust-version 高于团队 MSRV 且不可降级；只支持最新 edition 的老 API；和你已引 crate 的版本区间冲突 | `cargo metadata`（ph16 sol-02）、`cargo msrv list`、crates.io 版本页 |

**评审流程（最小可执行版）**：新建 crate 并声明目标 MSRV → 逐候选执行 ① 扫 crates.io 版本时间线与 issues → ② 记下主版本与 CHANGELOG 节奏 → ③ `cargo add` 后立即 `cargo tree` 看膨胀（不满意就回退）→ ④ `cargo deny check licenses` 跑兼容 → ⑤ 对「高危位置」crate（unsafe 密集 / 处理不可信输入）读源码确认 unsafe 封装 → ⑥ `cargo metadata` 核对 rust-version。全流程的脚本化骨架见 [`examples/ex01-crate-review.sh`](./examples/ex01-crate-review.sh)（未在本环境验证）。

**两个反模式**：

- **「最新即最好」**：追着刚发布的 0.x / 大版本第一天就升——大版本 0 天升仓是踩 breaking change 的高发姿势；生产依赖至少等一个 patch 周期
- **「别人都在用就不用评」**：下载量高只说明历史采用面大，不说明「现在还在维护」——近 90 天下载量与最近 publish 日期才是活跃度信号，star 数可以长期不动

> 本阶段把评审做成「清单 + 命令」的可执行流程；**把评审沉淀成 CI 门禁、SBOM、发布签名等完整供应链体系属于 ph24 安全、供应链与发布阶段（roadmap 第 24 节，目录待建）**，这里只需理解「引入前评审」是那道防线的第一环。

### 3.3 serde：序列化的事实标准

**serde 定位**：Rust 生态里「结构化数据 ↔ 字节」双向转换的事实标准框架。它分两层——**框架层**（`serde` 本体：`Serialize` / `Deserialize` 两个 trait 与数据模型）与**格式层**（json / yaml / toml / bincode / msgpack / csv …各自实现 `Serializer` / `Deserializer`）。框架层不知道任何格式，格式层不关心你的结构体，你的类型只要 `#[derive(Serialize, Deserialize)]` 就能被任意格式序列化。这个「类型 + 框架 + 格式」三角解耦是 serde 设计最值得学的一笔。

```rust
// examples/ex02-serde-basics/src/main.rs —— 教学片段（完整可运行版见 examples/ex02-serde-basics/）
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, PartialEq)]
struct Repo {
    name: String,
    stars: u32,
    // #[serde(default)]          // 反序列化时缺字段用默认值兜底
    // #[serde(rename = "openIssues")]  // 字段名映射（对接 snake_case 外的命名）
    archived: bool,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let repo = Repo { name: "serde".into(), stars: 10_000, archived: false };
    let json = serde_json::to_string_pretty(&repo)?;   // 序列化：结构体 → JSON
    println!("{json}");
    let back: Repo = serde_json::from_str(&json)?;     // 反序列化：JSON → 结构体
    assert_eq!(repo, back);
    println!("round-trip ok, len = {}", json.len());
    Ok(())
}
```

**derive 机制（承接 ph15 的认知，这里讲使用侧影响）**：`#[derive(Serialize)]` 展开成 `impl Serialize for Repo`，逐个字段调用格式层的 `serialize_*` 方法；反序列化同理。ph15 讲过「derive 在编译期生成代码」——这带来三个使用侧推论：**① 编译期生成 = 零运行时反射开销**（对比 Java Jackson / Python pickle 的运行时反射，这是 serde 高性能的根源之一）；**② 字段级属性（`#[serde(...)]`）是给展开代码的指令**，写错属性名在编译期报错而非运行期；**③ 展开代码照常过借用检查**——`#[serde(borrow)]` / `Deserialize<'de>` 涉及的生命周期标注要自己写对，这是新手第一个报错高发点。

**性能心智**：serde 的常见性能分化点在「要不要借用」与「要不要零拷贝」——`&str` 反序列化可以借用输入缓冲区（`Deserialize<'de>`），`String` 则必然分配；`serde_json` 的 `from_str` 返回的借用切片比 `to_owned` 快一个分配。追求极限时用 `serde_json` 的 `Value` 直接操作、或用 bincode/msgpack 这类紧凑二进制格式——但它们各有取舍（见下表）。

| 格式 | 框架 crate | 特点 | 典型场景 |
|------|-----------|------|---------|
| JSON | serde_json | 人类可读、生态最大、`Value` 动态解析方便 | 配置文件、REST API、日志 |
| TOML | toml | 配置格式事实标准（Cargo.toml 同款） | 应用配置 |
| YAML | serde_yaml（维护状态需确认） | 人类可读但语法复杂 | 已被 TOML 挤压 |
| bincode | bincode | 紧凑二进制、快 | 进程内缓存、网络协议 |
| msgpack | rmp-serde | 二进制 + 部分自描述 | RPC、消息队列 |
| CSV | csv | 表格行式 | 数据处理 |

**选格式的三个问题**：数据要给人类看吗（要 → JSON/TOML）？数据要跨语言互通吗（要 → 用该语言生态的通用格式，别用 bincode）？性能是瓶颈吗（是 → 先 profile 再上二进制格式，别预优化）。

> serde 的宏展开实现（过程宏如何生成 `impl`）属于 ph15 宏与元编程阶段；本阶段只把 derive 当「编译期生成、使用侧要懂字段属性与生命周期」的既有工具用。**手写 `Serialize`/`Deserialize` 的 trait 语义本身属 ph07 trait 与泛型阶段**。

### 3.4 tokio：异步生态全景与选型边界

**tokio 定位**：Rust async 生态的事实标准运行时——它提供事件循环（reactor）、线程池（worker）、定时器、async I/O 原语与任务调度。本阶段不重复 ph12/ph13 的用法教学，只补三块：**全景图（一揽子包含什么）、两个选型问题（要不要它、要哪部分）、以及「何时不需要 tokio」**。

**tokio 一揽子包含**（按依赖 features 分组，`tokio = { version = "1", features = [...] }` 逐个开）：

| 组 | 内容 | 何时开 |
|----|------|--------|
| rt / rt-multi-thread | runtime（单线程 / 多线程 worker） | 几乎总要（除非只用 `current_thread` 场景） |
| macros | `#[tokio::main]` / `#[tokio::test]` / `select!` | CLI / 应用入口 |
| net | `TcpListener` / `TcpStream` / `UdpSocket` | 网络服务 |
| time | `sleep` / `timeout` / `interval` | 定时、超时、心跳 |
| io-util | `AsyncReadExt` / `AsyncWriteExt` | 字节流处理 |
| sync | `Mutex` / `mpsc` / `watch` / `Notify`（async 版） | 任务间同步 |
| signal | Ctrl-C 等信号处理 | 服务优雅退出 |
| process | `Command` 的 async 版 | 调外部进程 |

**配套生态（tokio 全家桶）**：`tokio-util`（`CancellationToken`、`TaskTracker` 等组合件）、`tokio-stream`（`Stream` 适配）、`tracing`（诊断，见 3.7）、`hyper`（HTTP 底层，见 3.5）、`axum`（Web 框架，基于 hyper/tower）、`tonic`（gRPC）。选型时注意：**axum/tonic 都只是 tokio 生态的应用层，它们的底座是 hyper + tokio**——所以「要不要 tokio」往往先于「要不要 axum」被决定。

**运行时选择的两个问题**：

1. **要不要 async 运行时**——判断标准是 I/O 密集且并发规模大（大量连接/请求、每个任务大部分时间在等 I/O）。反例（**不需要 tokio**）：CPU 密集计算用多线程 + 数据并行更简单；一次性的脚本/CLI（读文件、算一下、退出）用同步 std 更直白；需要调外部进程但交互简单时 `std::process` 够用。**别为「赶时髦」引 tokio**——它带来 `Send` 约束、`!Send` 类型处理、调试复杂度，同步能解决的问题同步解决。
2. **要哪个 runtime**——`current_thread`（省线程、适合少量任务）vs `multi_thread`（默认，worker 线程池）；选型后整个依赖树里的 async 代码都要跑在同一个运行时上（见 3.9 特性统一：`rt` 与 `rt-multi-thread` 是互斥 feature）。

**select 与任务调度的工程直觉**：`tokio::select!` 同时等待多个 future、先到先执行并取消其余分支——是「超时 + 主逻辑」「多路信号」的惯用组合；ph12 已给过用法，这里补一条选型认知：**select 的取消是协作式的**，被取消分支的 future 在 `.await` 点被 drop，若它持有锁/缓冲要确保 drop 安全——这是 async 代码「谁负责清理」的常见坑。任务调度侧，`tokio::spawn` 把任务丢给 worker 池，`JoinHandle` 等待结果；密集任务要显式让出（`yield_now`）或换 `spawn_blocking`（把阻塞操作挪出 worker 线程）——**`spawn_blocking` 是 async 世界里调用同步阻塞库的官方出口**（数据库驱动、加密等）。

```rust
// examples/ex04-tracing-log 同款工程的 Cargo.toml 依赖（教学片段）
// [dependencies]
// tokio = { version = "1", features = ["rt-multi-thread", "macros", "time", "net"] }
```

> 本阶段只给 tokio 的**全景与选型**；runtime 内部机制（reactor 如何驱动 I/O、任务如何被调度、`select!` 宏展开）属于 ph12 并发与异步阶段与 ph15 宏与元编程阶段，这里只需建立「要异步先想清楚要不要 tokio、要哪一组 feature」的决策框架。

### 3.5 reqwest 与 hyper：HTTP 客户端怎么选

**关系一句话**：reqwest 是**面向普通开发者的高层 HTTP 客户端**，hyper 是**面向库作者/服务端的 HTTP 协议引擎**——reqwest 0.12 内部就是基于 hyper 1.x 实现的，你写业务代码用 reqwest，几乎永远不该直接碰 hyper。

| 维度 | reqwest | hyper |
|------|---------|-------|
| 定位 | 开箱即用的 HTTP 客户端：`reqwest::get(url).await?.text().await?` | HTTP/1.1 + HTTP/2 协议层引擎（client + server 两侧） |
| API 风格 | 高层：builder 配置、自动重定向、cookie、JSON 编解码 | 底层：手动拼 `Request`/`Response`、管理连接、写协议逻辑 |
| 异步 | 基于 tokio + hyper | 也是 tokio 生态 |
| 何时用 | 业务里「发个请求拿响应」 | 你**在写** HTTP 库 / 框架（如给 axum 做中间件层）、或要极致控制连接池 |
| 心智负担 | 低（教程/示例遍地） | 高（要懂连接、版本协商、body 流式处理） |
| 典型依赖写法 | `reqwest = { version = "0.12", default-features = false, features = ["json", "rustls-tls"] }` | `hyper = { version = "1", features = ["client", "http1"] }` |

**两个常见的选型坑**：

1. **TLS 后端之争**：reqwest 默认走 `native-tls`（OpenSSL 系）还是 `rustls`（纯 Rust）由 feature 决定。`rustls-tls` 省去系统 OpenSSL 依赖、编译更可复现、无系统库版本地狱——**新工程优先 `rustls-tls`**；`native-tls` 适合必须对接系统证书存储的企业环境。两者的选择同时影响你的部署镜像与依赖树（见 3.2 维度③：openssl-sys 会拖进一堆系统依赖）。
2. **把 hyper 当客户端用**：教程里偶尔出现「直接 hyper 发请求」的写法——除非你在做库，否则是在为「少一个依赖」付「多十倍代码」的税。判据：**你的代码是想表达「发个请求」，还是想表达「管理 HTTP 连接」？前者 reqwest，后者才考虑 hyper**。

> roadmap 练习「为 HTTP 客户端比较 reqwest 与 hyper」就是 3.5 的练习化——分析模板见 [`exercises/README.md`](./exercises/README.md) 练习 1。异步 HTTP 的网络用法本身在 ph12/ph13 已演示；reqwest 的阻塞模式（`blocking` feature）适合脚本场景，但库型代码应避免阻塞模式混入异步程序。

### 3.6 clap：命令行参数解析

**clap 定位**：Rust CLI 参数解析的事实标准。两条写法路线——**derive（声明式，推荐默认）** 与 **builder（命令式，需要动态/程序化构建时）**。ph13 已用过 derive 基础，这里讲清两路线的取舍与「把 struct 变 CLI」的机制。

```rust
// examples/ex03-clap-cli/src/main.rs —— derive 路线教学片段（完整版见 examples/ex03-clap-cli/）
use clap::{Args, Parser, Subcommand};

/// 一个演示 CLI：参数解析三件套（flag / 选项 / 子命令）齐活
#[derive(Parser)]
#[command(name = "ph17-demo", version, about)]
struct Cli {
    /// 详细输出开关（flag）
    #[arg(short, long)]
    verbose: bool,

    /// 输出次数（选项，带默认值）
    #[arg(short, long, default_value_t = 1)]
    count: u32,

    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// 问候某人
    Greet { name: String },
    /// 打印配置，--json 用 JSON 输出
    Show(ShowArgs),
}

#[derive(Args)]
struct ShowArgs {
    /// 以 JSON 格式输出
    #[arg(long)]
    json: bool,
}
```

**derive vs builder 的取舍**：

| 维度 | derive（声明式） | builder（命令式） |
|------|-----------------|-------------------|
| 写法 | 结构体 + 字段属性描述 CLI | 链式调用 `Command::new().arg(Arg::new(...))` |
| 心智 | 「CLI 的形状 = 结构体的形状」 | 「CLI 的形状 = 你逐步搭出来的形状」 |
| 优点 | 类型安全（解析结果直接是 typed struct）、代码少、帮助文本自动生成 | 动态能力：参数集合运行时才知道（插件式）、条件加参数 |
| 缺点 | 动态场景别扭（同一参数组出现与否取决于其他输入） | 代码长、易漏帮助/校验 |
| 适用 | **默认选择**——绝大多数静态 CLI | 交互式补全、参数来自配置/插件的场景 |

**机制认知**：`#[derive(Parser)]` 展开后（承接 ph15 的「derive 是编译期代码生成」），clap 从**结构体字段的类型与 doc 注释**反推每个参数——`String`/`u32`/`bool` 决定取值方式，`#[arg(short, long)]` 决定绑定形式，`/// 注释` 变成 `--help` 里的说明。所以**写 clap derive 时 doc 注释就是文档**，别写空注释。字段类型用 `Option<T>` 表示「可不传」，`Vec<T>` 表示「可多次出现」，`default_value_t` 给默认值——类型系统替你定义了「CLI 的合法输入空间」，非法输入在解析阶段就报错退出（`clap::Error`），业务代码拿到的永远是合法值。这就是 rust-patterns 里「Parse, don't validate」在 CLI 边界的落地。

**进阶认知**：`#[command(flatten)]` 把一组参数抽成公共结构体复用（如全局 `--verbose`/`--config`）；`value_parser` 可以挂自定义校验（如枚举值）；`clap_complete` 生成 bash/zsh/fish 补全脚本。**与 ph11 错误处理衔接**：clap 的解析错误默认带 usage 提示与退出码，`try_parse` 可以把错误并进你自己的错误枚举——CLI 应用常用 `anyhow::Result` + `Cli::parse()` 的薄组合。

> 本阶段只讲 clap 的**选型与 derive 机制**；过程宏展开细节（clap_derive 生成了什么）属 ph15 宏与元编程阶段；CLI 工程化（补全脚本、CI 里测 help 输出）属 ph21 Clippy、rustfmt、CI 与代码质量阶段（roadmap 第 21 节，目录待建）。

### 3.7 tracing 与 log：日志生态的现在与过去

**关系一句话**：`log` 是「库发日志」的老门面，`tracing` 是「带结构化与执行轨迹的下一代门面」——`tracing` 通过 `tracing-log` 桥接层兼容 `log`，所以**老库的 `log::info!` 也能汇入 tracing 管道**，两者不是二选一的敌人，是迁移期的兼容设计。

**两者本质差异**：

| 维度 | log（门面时代） | tracing（结构化时代） |
|------|----------------|---------------------|
| 最小单位 | `log::info!("msg {}", x)` 一条扁平记录 | `event!` 记录 + `span!` 跨 async/线程的执行轨迹 |
| 附加数据 | 只有格式化文本 | **结构化字段**：`info!(user_id, latency_ms, "processed")` |
| 上下文 | 无隐式上下文（要手动塞进每个消息） | span 自动携带上下文，span 内所有 event 共享 |
| async 友好 | 差（async 任务交错时日志互相穿插、无归属） | 好（span 随任务走，`tracing-futures`/`Instrument` 把 span 绑到 future 上） |
| 输出端 | `env_logger` / `fern` / `log4rs` 等 | `tracing-subscriber`（fmt + json 两种主要格式） |
| 生态现状 | 仍在被大量老库使用 | 新项目事实标准（tokio/axum 全家桶默认） |

**核心心智：span 是「一段带名字的执行区间」，event 是「区间里的单点记录」**。一个请求进来开一个 `info_span!("handle_request", method, path)`，span 内的每个 `event!`（数据库查询、HTTP 调用、错误分支）自动带上 method/path 上下文；请求结束 span 关闭。异步场景下把 span 用 `.instrument(span)` 绑到 future 上，任务在哪个 worker 线程执行、嵌套了哪些子 span，全部可追溯——这是 log 的扁平消息给不了的，也是「async 程序为什么需要 tracing」的根本答案。

```rust
// examples/ex04-tracing-log/src/main.rs —— 教学片段（完整版见 examples/ex04-tracing-log/）
use tracing::{debug, error, info, info_span, instrument};
use tracing_subscriber::EnvFilter;

#[instrument]  // 自动以函数名开 span，参数进字段
async fn fetch(url: &str) -> Result<String, reqwest::Error> {
    info!(url, "sending request");           // 结构化字段：url 不是拼进文本
    let body = reqwest::get(url).await?.text().await?;
    debug!(bytes = body.len(), "response ok");
    Ok(body)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 订阅者：日志级别 + 目标过滤（env_logger 式） + fmt 输出
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env()
            .unwrap_or_else(|_| EnvFilter::new("info,ph17_demo=debug")))
        .init();
    let span = info_span!("job", job_id = 42);
    let body = fetch("https://example.com").instrument(span).await?;
    error!(len = body.len(), "demo done (error level 只是演示)");
    Ok(())
}
```

**选择建议**：**库型 crate 依赖 `tracing`（或为兼容只发 `log`），应用型项目直接上 `tracing` + `tracing-subscriber`**；老代码库可以先用 `tracing-log` 桥接过渡。`EnvFilter` 的「目标（target）+ 级别」过滤与 `env_logger` 的 `RUST_LOG` 语义一致，迁移平滑。JSON 输出（`tracing_subscriber::fmt().json()`）在采集进日志系统（ELK/Loki）时几乎是标配。

> ⚠️ 结构化字段的值要求实现 `tracing::Value`——`&str`/数值/`bool` 原生支持；自定义类型要么实现 `Value`，要么用 `?` 占位符（`error!(err = ?e)`，`Debug` 输出）。**把「字段」错写成「格式化文本」是新手最常见的不变量破坏**：`info!("url={url}")` 不是结构化，`info!(url, ...)` 才是。

### 3.8 数据库访问三选：sqlx / diesel / sea-orm

三个 crate 都解决「Rust ↔ 关系数据库」，哲学与取舍完全不同。**选型先问三个问题：要编译期 SQL 检查吗？要 ORM 的对象模型吗？要 async 原生吗？** 答案组合指向下表：

| 维度 | sqlx | diesel | sea-orm |
|------|------|--------|---------|
| 本质 | **异步 SQL 工具包**：手写 SQL + 编译期检查 + 行映射 | **同步 ORM**：类型安全 query builder + 迁移 + 编译期检查（diesel 2 起可选 async） | **异步 ORM**：entity/relation 对象模型，Active Record 风格 |
| SQL 形态 | 手写 SQL（`query!` 宏对数据库做编译期校验） | Query DSL（Rust 表达 SQL）+ 可选 raw SQL | Query DSL（近似 diesel）+ raw SQL |
| 编译期检查 | `query!`/`query_as!` 宏**连库校验 SQL 与类型**（需要 DATABASE_URL 或离线缓存） | 类型系统检查查询构造（不连库） | 同 diesel：DSL 类型检查（不连库） |
| async | 原生 async（无 runtime 绑定，但用 async 就需运行时） | 同步为主；diesel-async 为桥接 | 原生 async（tokio） |
| 运行时依赖 | 无 ORM 魔法；驱动层（sqlx 自带） | 自带连接管理 | 底层可用 sqlx 驱动 |
| 学习曲线 | 中（SQL 熟练者最顺） | 高（schema/DSL/迁移体系完整但概念多） | 中高（ORM 对象模型要学） |
| 适用 | 团队写 SQL、要 async、要编译期 SQL 正确性 | 大型同步 CRUD 应用、要成熟迁移工具、非 async 栈 | 异步栈 + 想要对象模型（领域层友好） |
| 版本 | 0.8（0.x 时代，API 偶有破坏） | 2.x | 1.x |

**三者心法**：

- **sqlx 的编译期检查是它的招牌**：`sqlx::query!("SELECT id, name FROM repo WHERE id = ?", id)` 在**编译时**连数据库校验列名与类型（`DATABASE_URL` 环境变量或 `.sqlx` 离线缓存）；代价是 CI/构建需要数据库可达或缓存——这是它与其他两家的本质差异（把「SQL 写错」从运行期提前到编译期，但把「数据库可达」变成构建依赖）
- **diesel 是最「工程化完整」的同步 ORM**：schema 从数据库自动生成（`diesel migration` + `diesel print-schema`）、迁移体系成熟、类型安全贯穿；代价是学习曲线与「非 async 优先」——选它通常意味着整个服务栈决定走同步线程模型
- **sea-orm 是「异步栈里要 ORM 对象模型」的答案**：entity/relation 让你以对象思维操作行（`Repo::find_by_id(id).one(db).await`），底层可用 sqlx；适合领域模型复杂、不想写 SQL 的 async 服务——但对象模型的灵活性代价是复杂查询要回落 raw SQL

**判据收口**：写 SQL 且要 async → sqlx；大型同步 CRUD + 成熟迁移 → diesel；async + 领域对象模型 → sea-orm。**「全都要」的代价**：对象模型（sea-orm）会限制你对 SQL 的完全控制，编译期连库检查（sqlx `query!`）会把构建与数据库耦合——选型本质是选「把哪个复杂度放在哪一层」。

> ⚠️ 三个 crate 都要求你**先懂 SQL**：ORM/DSL 是「省写 SQL 样板」不是「免学 SQL」。另外三者的连接池/事务/迁移 API 各不相同，本阶段只到选型与 hello-world 级使用（见 examples 与 exercises），**数据基础设施的深入（分库分表、连接池调优、审计表设计）属 ph25 Rust 数据基础设施专项阶段（roadmap 第 25 节，目录待建）**。

### 3.9 semver 与 feature flags：依赖间的契约语言

**semver（语义化版本，Semantic Versioning）** 是 crate 之间唯一通用的兼容契约：`MAJOR.MINOR.PATCH`。Rust 生态把 semver 当**硬承诺**执行——cargo 的版本解析（`^` 区间：`"1.5"` 允许 ≥1.5 且 <2.0）完全建立在该承诺上；**破坏性变更只允许出现在 MAJOR 递增时**，这使 `cargo update` 在 1.x 内可以放心升。反例对照：0.x 版本没有兼容承诺（0.y 的 y 递增可以破坏），所以依赖写 `"0.8"` 不代表 0.8.0→0.8.1 一定兼容——**0.x 依赖要主动盯 changelog**。

| semver 动作 | 例子 | 是否破坏 |
|------------|------|---------|
| PATCH 递增（修 bug，不改 API 语义） | 1.2.3 → 1.2.4 | 否 |
| MINOR 递增（加 API，向后兼容） | 1.2.3 → 1.3.0 | 否 |
| MAJOR 递增（任何不兼容变更） | 1.2.3 → 2.0.0 | 是 |
| 加 feature / 默认关新 behavior | — | 否（但见下「行为兼容」） |
| yank 某个版本 | crates.io 撤回 | 警告性操作：已锁定的构建不受影响，新解析避开它 |
| 0.x 的 MINOR/PATCH | 0.8.1 → 0.9.0 | **可以破坏**（0.x 契约豁免） |

**breaking change 判断口诀**：改了公开 API 的**签名/语义/移除**就是破坏——「只加不改不删」才是 MINOR。三处隐蔽破坏要特别当心：**① 行为兼容**（同签名但语义变了，如错误时机、默认值、panic 条件——semver 管不到，靠 changelog）；**② 类型推断面**（新 trait impl 可能改变 `?` 或泛型推断结果）；**③ 传递依赖升级**（A 升级依赖 B 的 MAJOR，你的代码里直接 `use` 的 B 类型可能因版本重复而错配——`cargo tree -d` 能看见多版本并存，见 3.10）。Rust 生态为此有 **semver 检查工具**（`cargo semver-checks`）：对比两个版本的公开 API 面，自动报告哪些变更违反 semver——发布前跑一遍是成熟团队的标配。

**feature flags 语义**：feature 是 Cargo.toml 里声明的**编译期开关**，每个 feature 是一组附加依赖或附加代码路径，由 `cfg(feature = "...")` 在源码里启用。四个必须内化的语义点：

1. **默认特性（default features）**：`[features] default = ["std", "derive"]` 是隐式默认开的集合；依赖方用 `default-features = false` 关掉再显式开自己需要的——**「关默认 + 只开所需」是控制依赖树膨胀与 unsafe 面的第一杠杆**（reqwest 关掉默认的 native-tls 换 rustls-tls 就是 3.5 的例子）
2. **特性统一（feature unification）**：**同一个 crate 在依赖图里出现多次时，它的 feature 取并集**——只要有一个依赖方开了某 feature，全图共享。推论：A 依赖 `tokio/rt-multi-thread`、B 依赖 `tokio/rt`，合并后 tokio 同时有两者——**你的 feature 不只由你决定，还由整棵依赖树决定**（这就是为什么互斥 feature 要用 `dep:` 语法做独占，也解释了 3.4 的「runtime 选择是整棵树的事」）
3. **可选依赖即 feature**：`[dependencies] serde = { version = "1", optional = true }` 隐式生成 `features = ["serde"]`；`dep:serde` 语法把它变成「纯内部依赖开关，不暴露成 feature 名」——库作者用它避免「下游无意中开了你的内部依赖」的 feature 名冲突（ph16 的 3.5/v1→v2→v3 讲解可回看）
4. **与 cfg 的配合**：`#[cfg(feature = "json")]` 控制代码编译；cfg 是编译期常量判断，feature 是它的一个输入源——**feature 决定「编译进哪些代码」，cfg 决定「哪些代码参与编译」**，两者同一个开关的正面反面。调试 feature 组合最常用的命令是 `cargo tree -e features`（看每个 crate 实际开了哪些 feature，见 3.10）

**写 feature 的工程惯例**：feature 名用 kebab-case；**「每个 feature 只加不减」**是库作者对下游的兼容承诺（下游可能依赖你的旧 feature 名）；语义互斥的配置（如 TLS 后端二选一）用 `dep:` 独占，避免 feature 统一把两个都打开。

```toml
# Cargo.toml 片段：关默认 + 精选 feature（教学）
[dependencies]
reqwest = { version = "0.12", default-features = false, features = ["json", "rustls-tls"] }
tokio = { version = "1", default-features = false, features = ["rt-multi-thread", "macros"] }
serde = { version = "1", features = ["derive"] }
```

### 3.10 依赖治理：cargo tree / audit / deny / diet 与供应链安全前置

**cargo tree 是依赖图的「CT 扫描」**——四个高频用法：

```text
cargo tree                     # 全量依赖树（缩进即层级）
cargo tree -i <crate>          # 反向：谁依赖了它（impact）
cargo tree -d                  # duplicates：同一 crate 的多版本并存
cargo tree -e features         # 每个 crate 实际开的 feature（对照 3.9 特性统一）
cargo tree --depth 2           # 只看两层（依赖树膨胀的第一道体检）
```

读法：**看深度**（`--depth 2` 内就该出现的业务依赖拖到第 5 层说明引错了层）、**看重复**（`-d` 出现同 crate 多版本 = 传递依赖没对齐，常因某库锁老版本）、**看 surprise**（`cargo tree -i openssl-sys` 问「谁把系统 OpenSSL 拖进来了」——多半是某个库默认 feature 开了 native-tls）。

**三个审计工具的分工**：

| 工具 | 装法 | 查什么 | 高频命令 | 在流程里的位置 |
|------|------|--------|---------|--------------|
| cargo-audit（RustSec） | `cargo install cargo-audit` | **已知漏洞**：对照 RustSec advisory-db 公告库查 CVE 级漏洞 | `cargo audit`（全量）/ `cargo audit --fix` | 依赖树「有没有已知雷」的第一道闸 |
| cargo-deny | `cargo install cargo-deny --locked` | **许可证 + 漏洞 + 重复依赖 + 源码许可**四合一门禁，deny.toml 配策略 | `cargo deny check licenses` / `cargo deny check bans` / `cargo deny check advisories` | 引入前评审 + CI 门禁（ph24 完整化） |
| cargo-diet | `cargo install cargo-diet` | **打包体检**：`cargo package` 会带上哪些文件、缺不缺 license/README | `cargo diet -n`（列将打包文件）/ `cargo package --list` 对照 | 库发布前（衔接 ph24 发布） |

**供应链安全前置（本阶段做到哪一层）**：本阶段把供应链安全落成三个「评审习惯」——**① 引入前六维评审**（3.2，含 unsafe 面与维护活跃度）；**② 引入后立即 `cargo audit` 与 `cargo deny check advisories` 扫雷**；**③ 升级时看 changelog + `cargo semver-checks` 防隐蔽破坏**。更完整的体系——SBOM 生成、依赖签名验证（cargo 的 spdx/SBOM 支持）、发布完整性、私仓镜像、`cargo vendor` 离线供应链——**属于 ph24 安全、供应链与发布阶段（roadmap 第 24 节，目录待建）**，本阶段不展开，但 3.2 的评审清单与本节命令就是 ph24 的第一层地基。

**治理流程收口（结合 ph16 的锁文件策略）**：应用型工程 = 提交 Cargo.lock + `cargo build --locked` 守 CI（ph16）+ 每次 `cargo update` 后跑 `cargo audit` + `cargo test` + 抽查 `cargo tree -d`；库型工程 = 依赖面控制（`default-features = false` 文化）+ 发布前 `cargo diet -n` + `cargo semver-checks`。两型工程共同的底线：**CI 里至少一道 `cargo audit`（或 cargo-deny advisories）**——它不贵、不慢，是「已知漏洞」的唯一自动防线。

> ⚠️ cargo-audit / cargo-deny / cargo-diet / cargo-semver-checks 均为 `cargo install` 的独立子命令（非 rustup 组件），版本与行为以各自仓库 README 为准；RustSec advisory-db 的维护组织与数据库地址随年份变动，`cargo audit` 首次运行会拉库——**联网行为在本写作沙箱未验证，命令语义以官方文档为准**。

## 4. 底层原理

### 4.1 cargo 如何选版本：从「写 `"1.5"`」到「锁文件里的一行」

cargo 的依赖解析不是「取最新」而是**在 semver 契约内求一个满足全图的解**：

```text
Cargo.toml 需求                 crates.io 索引                 解析结果
"reqwest = 0.12"  ──▶  候选：0.12.0 … 0.12.x（≥0.12 <0.13）  ──▶  0.12.latest
"serde = 1"       ──▶  候选：1.0.0 … 1.x（≥1 <2）            ──▶  1.latest
版本区间 = semver 契约的投影        全部候选来自稀疏/完整索引          锁进 Cargo.lock（ph16）
```

- 候选区间来自**主版本边界**：`"1.5"` 的兼容集是 `[1.5, 2.0)`——cargo 信任「1.x 内不破坏」，这就是 3.9 的 semver 契约如何变成解析器的执行规则
- 多 crate 的区间求**交集**：A 要 `tokio ^1.20`、B 要 `tokio ^1.30`，交集是 `[1.30, 2.0)`；无交集时要么报错，要么**同一 crate 两版本并存**（见 4.2）
- 解析结果写进 Cargo.lock（应用提交），`cargo update` 在区间内前进、`--precise` 回退——ph16 已实测这套行为，这里补的是「区间为什么长这样」的底层

### 4.2 feature 统一与「两版本并存」：依赖图的拓扑现实

```text
你的应用
 ├── A ── tokio 1（features: rt-multi-thread）     ← 开了 rt-multi-thread
 └── B ── tokio 1（features: rt）                  ← 只要 rt
合并：tokio 1 的 features = rt ∪ rt-multi-thread（取并集）
```

**feature 统一（unification）是 cargo 的默认行为**：同一版本号的 crate 在图中只构建一份，feature 取所有依赖方的并集。它省内存省编译，代价是 **「你的 feature 选择被全图共享」**——所以互斥选项（TLS 后端、runtime 形态）要设计成独占（`dep:` + `cfg` 判互斥），否则并集可能把两个互斥后端都编进来。历史上 resolver v1 到 v2 改的正是「feature 要不要跨依赖方合并」的边界（features 只对「直接或间接依赖的相同版本」统一），v3 再加 MSRV 感知——ph16 的 3.5/3.6 讲版本治理侧，本节从「为什么会有这套规则」讲。

**当两个依赖方对同一 crate 要求不兼容的版本区间时**（A 锁 `tokio 1.20` 的某个 API 被 B 的 `tokio ^1.40` 语义覆盖不了，或区间无交集），cargo 允许**同 crate 多版本并存**（如 `rand 0.8` 与 `rand 0.9` 同图）。这不是 bug，是「不破坏任何一方的 semver 契约」的务实解——代价是体积、以及**类型不通**（A 给你的 `rand 0.8` 类型传不进要求 `rand 0.9` 的 B 的 API）。`cargo tree -d` 看见重复版本时：先查是不是某库锁了老主版本，能对齐就对齐，不能就接受并记录。

### 4.3 unsafe 面与「安全依赖」的静态观察

`cargo geiger` 类工具按 crate 统计 unsafe 块数量与涉及函数，把 3.2 的维度⑤变成可扫的数字；但要警惕**数字的欺骗性**——`unsafe` 集中在 FFI 封装层的 crate（如 `libc`）反而是「封装良好」的信号，散布全库且无 `// SAFETY` 注释才是危险信号。判据不是「有没有 unsafe」而是「**unsafe 是否被约束在最小、可审计、有注释的边界内**」。RustSec 公告库给出「unsafe 实现细节被利用」的真实案例模式——本阶段只需建立观察习惯，系统性的安全审查方法属 ph14 Unsafe 与安全抽象阶段与 ph24 安全、供应链与发布阶段（roadmap 第 24 节，目录待建）。

## 5. 使用场景

**什么时候该为功能引 crate，什么时候忍住**：

- **引**：问题在生态有事实标准解，且你的用法在标准解的安全区内（序列化 → serde；CLI → clap；async I/O → tokio；HTTP 客户端 → reqwest）——引标准解的成本是「学习曲线 + 升级跟随」，收益是「不重复造轮子 + 安全补丁自动跟进」
- **忍住（用 std）**：单次脚本、纯 CPU 计算、简单文件处理——`std::fs`/`std::thread` 够用；**为「少写 10 行」引入带 40 传递依赖的 crate 是负资产**（3.2 维度③）
- **忍住（自己做薄封装）**：需求只有某个大 crate 的 5% 能力——一个 30 行的函数比一个依赖更可维护；但「自己做」前先确认未来需求不会膨胀到 50%（膨胀了就引）
- **升级决策**：patch 级随 `cargo update` 跟进（安全修复几乎都在 patch）；minor 级看 changelog 再升（可能带行为兼容问题）；major 级当新选型做一次（跑 3.2 评审 + `cargo semver-checks` + 全文搜索旧 API 用法）——**升级不是「点一下」，是一次小评审**

**分场景的依赖组合速查**（写作时 crates.io 稳定版为参照，具体以 docs.rs 为准）：

| 场景 | 推荐组合（默认关、精选开） | 不推荐 |
|------|--------------------------|--------|
| CLI 工具 | clap(derive) + anyhow + tracing(+subscriber) | 手写参数解析；unwrap 满屏 |
| Web API 服务 | tokio + axum（hyper/tower 底座）+ serde_json + sqlx/sea-orm | 自己拼 hyper 当框架 |
| HTTP 客户端 | reqwest(rustls-tls, json) | 直接 hyper；默认 native-tls 无脑开 |
| 批量数据处理 | serde + csv/serde_json + rayon（ph22 性能优化与 Profiling 阶段再深入，roadmap 第 22 节，目录待建） | 为 1 万行引分布式框架 |
| 配置管理 | serde + toml；复杂配置加 figment/config crate | 手写解析器 |
| 日志 | tracing + tracing-subscriber（EnvFilter） | log + env_logger 新项目（除非兼容老库） |
| 错误处理 | 库用 thiserror、应用用 anyhow（ph11 已讲） | Box<dyn Error> 裸奔（rust-patterns 反模式） |

**跨语言对比（为 analysis/ 积累素材）**：crates.io 的「锁文件 + 六维评审文化」对标 Python PyPI（无锁文件传统、依赖解析晚到）+ npm（锁文件有但 semver 执行松弛、左倾依赖文化）、Go modules（无中央评审文化但内置最小版本选择）。Rust 的独特点是 **semver 被当硬契约执行 + 依赖树透明可审**——这使「评估 crate」成为一门可教学的工程手艺，而非经验玄学。

## 6. 代码示例

本节展示示例的关键片段，完整可运行文件在 [`examples/`](./examples/) 目录（验证环境 rustc/cargo 1.92.0 macOS arm64 + rustup 1.28.2；依赖 crates.io 的示例经 rsproxy 镜像拉取；**验证说明**：ex02（serde）与 sol-04（feature+reqwest）已在 cargo 1.92.0 本机实测构建（ex02 运行亦通过）并标注「已验证」；ex03（clap）、ex04（tracing）、lib-skeleton 依赖未入本机缓存、需联网拉取，标注「未在本环境验证」（命令在联网环境可复现，国内可用 rsproxy 镜像）：

### 示例 1：crate 六维评审脚本（ex01-crate-review.sh）

```bash
# examples/ex01-crate-review.sh —— 评审一个 crate 的命令流水线骨架
# 验证环境：bash + rustc/cargo 1.92.0 + cargo-audit/cargo-deny/cargo-semver-checks（如未装则跳过对应步骤）
# 运行：bash examples/ex01-crate-review.sh <crate名>（未在本环境验证）
cargo search <crate>                    # 1. 看简介/最新版本/近 90 天下载
cargo add <crate>                       # 2. 引入（先关默认再精开，见 3.9）
cargo tree --depth 2                    # 3. 两层内看膨胀
cargo tree -d                           # 4. 重复版本体检
cargo audit                             # 5. 已知漏洞扫描（需网络拉 RustSec 库）
cargo deny check licenses               # 6. 许可证门禁（可选）
```

### 示例 2：serde 序列化教学（ex02-serde-basics/）

```rust
// examples/ex02-serde-basics/src/main.rs —— serde derive + 属性教学（片段见 3.3）
// 验证环境：rustc/cargo 1.92.0；依赖 serde 1 + serde_json 1（crates.io 拉取，rsproxy）
// 运行：cargo run / cargo test（已验证：cargo 1.92.0 本机实测构建+运行通过）
#[derive(Debug, Serialize, Deserialize, PartialEq)]
struct Repo {
    name: String,
    stars: u32,
    #[serde(default)]            // 缺字段用 Default 兜底
    archived: bool,
    #[serde(rename = "openIssues")] // JSON 键名映射
    open_issues: u32,
}
let back: Repo = serde_json::from_str(&json)?;   // 反序列化：JSON → 结构体
```

### 示例 3：clap CLI 教学（ex03-clap-cli/）

```rust
// examples/ex03-clap-cli/src/main.rs —— clap 4 derive：flag/选项/子命令（片段见 3.6）
// 验证环境：rustc/cargo 1.92.0；依赖 clap 4（features derive）
// 运行：cargo run -- --help / cargo run -- greet world / cargo run -- show --json（未在本环境验证）
#[derive(Parser)]
#[command(name = "ph17-demo", version, about)]
struct Cli {
    #[arg(short, long)]               // flag：出现即 true
    verbose: bool,
    #[arg(short, long, default_value_t = 1)] // 选项，带默认值
    count: u32,
    #[command(subcommand)]            // 子命令
    cmd: Cmd,
}
```

### 示例 4：tracing 日志教学（ex04-tracing-log/）

```rust
// examples/ex04-tracing-log/src/main.rs —— tracing + tracing-subscriber：span/event/字段/instrument（片段见 3.7）
// 验证环境：rustc/cargo 1.92.0；依赖 tracing 0.1 + tracing-subscriber 0.3 + tokio 1 + reqwest 0.12
// 运行：RUST_LOG=ph17_demo=debug cargo run（未在本环境验证；需网络访问 example.com）
#[instrument]                        // 自动以函数名开 span，参数进字段
async fn fetch(url: &str) -> Result<String, reqwest::Error> {
    info!(url, "sending request");   // 结构化字段：url 作为字段而非拼进文本
    let body = reqwest::get(url).await?.text().await?;
    debug!(bytes = body.len(), "response ok");
    Ok(body)
}
```

### 示例 5：feature flags 与依赖治理命令演示（ex05-cargo-tree-features.sh）

```bash
# examples/ex05-cargo-tree-features.sh —— cargo tree 四用法 + feature 并集对照实验
# 验证环境：bash + cargo 1.92.0；需网络拉取演示用 crate（rsproxy）
# 运行：bash examples/ex05-cargo-tree-features.sh（未在本环境验证）
cargo tree -d -e features   # 重复版本 + 每个 crate 实际开的 feature（特性统一可视化）
cargo tree -i reqwest       # 反向影响面
```

## 7. 总结

### 关键要点

- **评估先于引入**：六维清单（维护活跃度 / API 稳定性 / 依赖树膨胀 / 许可证兼容 / unsafe 面 / MSRV）是「加依赖」前的默认动作；crates.io 版本时间线 + docs.rs 文档 + `cargo tree` + `cargo audit` 是执行工具（3.1/3.2/3.10）
- **五员大将各安其位**：serde（序列化事实标准：框架/格式解耦 + derive 编译期生成）、tokio（async 事实标准：先问「要不要」再问「要哪组 feature」，`spawn_blocking` 是 async 世界调同步库的出口）、reqwest（面向业务的高层客户端，基于 hyper 引擎，TLS 后端优先 rustls）、clap（CLI 事实标准：derive 默认、类型即输入空间）、tracing（结构化诊断：span 跨 async 携带上下文，兼容 log 老库）
- **ORM 三选一是哲学题**：sqlx = SQL 熟练 + 编译期连库检查 + async；diesel = 同步大 CRUD + 成熟迁移；sea-orm = async + 对象模型——先懂 SQL 再选框架
- **semver 是硬契约、feature 是编译期开关**：破坏只进 MAJOR、0.x 无承诺、行为兼容要盯 changelog；默认特性要关、特性取并集（全图共享）、`dep:` 做互斥、`cfg(feature)` 决定代码进不进编译
- **依赖治理有命令可依**：`cargo tree`（膨胀/重复/feature）/ `cargo audit`（已知漏洞）/ `cargo deny`（许可+漏洞+重复门禁）/ `cargo diet`（打包体检）——至少 CI 里有一道 audit；完整供应链体系属 ph24

### 阶段验收清单

- [ ] 能在引入依赖前按六维说明理由（对照 ph16 project/ 的「依赖引入约定」登记表扩展版）
- [ ] 能控制 feature 范围（`default-features = false` + 精选 feature；能解释 feature 统一对依赖树的影响）
- [ ] 能发现高风险或无人维护 crate（版本时间线 >1 年 + issue 无响应 + 依赖树异常膨胀 → 红灯）
- [ ] 能用 `cargo tree` / `cargo audit`（/ cargo-deny）跑一轮依赖体检并解释输出
- [ ] 能说明 serde / tokio / reqwest / clap / tracing 各自的定位与「何时不需要它」
- [ ] 能为一个具体数据库访问场景在 sqlx / diesel / sea-orm 间做有依据的三选一

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。四题对应 roadmap 练习：比较 reqwest 与 hyper、检查 crate 活跃度、用 cargo tree 观察依赖树、选型与 feature 控制。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**依赖评审报告**——为一个真实场景（命令行下载工具）列出核心 crate、用途、风险与替代方案，附检查脚本与选型备忘（roadmap 推荐项目落地）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 跨语言对比

- Rust 把「依赖管理」做进了编译系统（cargo 原生、锁文件可复现、依赖图可审），C/C++ 把成本外推给构建系统各自为政、Python 到 pip 时代才系统化、npm 有锁文件但 semver 执行宽松——**「semver 硬契约 + 依赖透明」是 Rust 生态评审文化的制度根基**（为 analysis/ 与 Tenet 合成积累素材）

### 下一阶段

[**ph18 Borrow Checker 调试专项阶段**](../ph18-borrow-checker-debug/18-borrow-checker-debug.md)——引入 crate 只是工程的一半，另一半是读懂编译器：当新依赖的类型设计与借用规则冲突、或你在评审中读到老 crate 的 `unsafe` 封装时，系统化定位 E0382/E0499/E0502/E0597 并重构出干净所有权流的能力，正是下一步要练的手艺。

