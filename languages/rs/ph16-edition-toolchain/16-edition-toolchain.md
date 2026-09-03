# Rust Edition、工具链与版本管理阶段

> 面向工程可复现性方向：本阶段从 rustup 工具链管理起步，理解 Edition 如何让 Rust 「不换编译器就能换语言」，再到 rust-toolchain.toml、Cargo.lock 与 MSRV 的团队落地——最终能保证「我机器上能编」升级为「全队 + CI 任何一天都能编出同一个东西」。

## 1. 概述

Rust Edition、工具链与版本管理阶段对应 roadmap 第 16 节，目标是**能管理 Rust 版本、Edition 和项目工具链，保证团队环境一致**。具体定位分两层：**先建立工具链与通道认知——用 rustup 管理多条工具链（install/default/override），分清 stable/beta/nightly 三个发布通道，理解 Edition（2015/2018/2021/2024）是「crate 级的语法语义开关」而非编译器版本**。**再把版本治理落到工程——用 `cargo fix --edition` 实测一次 2015→2024 的迁移，用 rust-toolchain.toml 把工具链钉进仓库，用 Cargo.lock + `rust-version`（MSRV）+ resolver v3 把「依赖选谁」也变得可复现**。本阶段承接 ph06 模块化与 Cargo 阶段（Cargo.toml/cargo build 的基础用法，那里已预告「Cargo.lock 策略 ph16 展开」）、ph15 宏与元编程阶段（「宏展开由工具链驱动」——cargo-expand 的底层 `-Zunpretty=expanded` 是 nightly 特性，edition 决定宏/路径/借用规则按哪套规则编译）；并为 ph17 Crate 生态选择与常用库阶段（选 crate 要看它的 rust-version 与维护活跃度）、ph21 Clippy、rustfmt、CI 与代码质量阶段（CI 深度设计）、ph24 安全、供应链与发布阶段（cargo audit/deny）提供版本治理的地基。

| 核心维度 | 覆盖内容 |
|----------|---------|
| rustup 工具链管理 | toolchain install/list/default、`+toolchain` 临时指定、目录级 override、组件管理（3.1） |
| 发布通道 | stable/beta/nightly 语义、6 周火车模型、nightly 特性开关（3.2） |
| Edition 机制 | 2015/2018/2021/2024 差异表与实测矩阵、cargo fix --edition 迁移全流程实测（3.3） |
| rust-toolchain.toml | 字段语义、优先级顺序、团队落地（3.4） |
| Cargo.lock 策略 | 锁文件格式 v4、应用提交 vs 库不提交、升级/回退、`--locked`（3.5） |
| MSRV | rust-version 声明、resolver v3 的 MSRV 感知（实测）、依赖 MSRV 检查（3.6） |
| 底层原理 | 同一编译器按 edition 切换语义的实现、lint 迁移机制、resolver 版本选择（4） |

这个阶段只涉及 rustup 工具链管理、发布通道、Edition 机制与迁移、rust-toolchain.toml、Cargo.lock 与 MSRV 的版本治理，**不涉及 Cargo 的基础用法（cargo new/build/test、工作区组织——属于 ph06 模块化与 Cargo 阶段）、clippy/rustfmt 的规则细节与 CI 流水线设计本身（属于 ph21 Clippy、rustfmt、CI 与代码质量阶段，本阶段只把它们当「团队约定」配置进模板）、crate 选型与依赖审计（属于 [ph17 Crate 生态选择与常用库阶段](../ph17-crate-ecosystem/17-crate-ecosystem.md) 与 ph24 安全、供应链与发布阶段）**。承接 [ph06 模块化与 Cargo 阶段](../ph06-cargo-module/06-cargo-module.md)：那里承诺「Cargo.lock 策略 ph16 展开」，本阶段 3.5 兑现；承接 [ph15 宏与元编程阶段](../ph15-macros-metaprogramming/15-macros-metaprogramming.md)：宏展开产物按哪个 edition 的语义检查，正是本阶段的主题（3.3 末尾「宏与 edition」小节兑现）。

## 2. 来源与演变

Rust 自 1.0（2015-05-15）起就承诺**稳定版永不破坏兼容**——但语言要进化，有些改进天生是破坏性语法变化（比如把 `dyn`/`async` 变成关键字、改革模块路径）。两难在 2016~2017 年的「epoch」RFC（RFC 2052）中解决：**Edition 机制**——同一个编译器携带多套表层语义，每个 crate 在自己的 `Cargo.toml` 里声明用哪套；不同 edition 的 crate 可以在同一个依赖图里混编链接。设计哲学一句话加粗：**「语言可以大步进化，生态不许分裂——Edition 是给语法变化装上开关，让老代码永远能和新代码一起编译」**。2018-12-06 Rust 1.31 发布首个新 edition「Rust 2018」。版本管理侧，rustup 自 2016 年前后随 Rust 生态成熟（前身是社区脚本 multirust），随后成为官方安装与工具链管理器——rustup 侧的具体版本与年份为保守估计，以官方 CHANGELOG 为准。

**「Edition 是一组 RFC，不是版本号跳变」**——每次 edition 都由 rust-lang/rfcs 的提案定义，再由某个 stable 编译器「认领」落地（RFC 编号以 rust-lang/rfcs 仓库为准）：

| Edition | 落地编译器 | 主 RFC 与配套 |
|---------|-----------|--------------|
| Rust 2018 | 1.31（2018-12-06） | 主 RFC 2052「Rust 2018」（epoch 方案本身），配套路径改革等一批 |
| Rust 2021 | 1.56（2021-10-21） | 主 RFC 3085「Edition 2021」，闭包捕获等组件 RFC（如 RFC 2229） |
| Rust 2024 | 1.85（2025-02-20） | 无单一大 RFC，由一组独立 RFC 拼装：unsafe extern（RFC 3484）、RPIT 生命周期捕获（RFC 3498）、gen（RFC 3513）、resolver v3（RFC 3537，见 3.6）等 |

节奏约 **3 年一次**（2015 → 2018 → 2021 → 2024），且 edition 年份与 rustc 版本号无绑定关系——这正是「换 edition 不用换编译器」的另一面：edition 只跟语言语义走，编译器自己按 6 周节奏滚动。

**为什么不是「直接升 rustc 大版本 / 发 Rust 2.0」？** 对照两条已被走过并踩过坑的路：C++ 靠「各编译器各自实现同一标准档」对齐，老编译器编不了新标准代码，生态迁移取决于编译器供应商的节奏；Python 2→3 是「语言版本断裂」的教材级案例，多年双版本并行、生态长期分裂。Rust 选的是第三条路：**语言内部带多套语义，编译器永远向后兼容**——你想用新语法，给 crate 开新 edition；你不想动，老代码在新编译器上照常编译，还能和旁边新 edition 的 crate 链接。语言进化的成本从「全生态一次性断裂」摊薄成「每个 crate 自愿选择的一次性迁移」。这个对照在第 5 章跨语言小节还会从工程视角再收一次。

**edition 的生命周期三阶段**（机制预览，第 4 章细讲）：① **RFC 立项**——每个破坏性变化先设计迁移方案；② **提前 2~3 个 stable 以 lint 铺路**——变化先以 warning 形态出现在所有 edition（`bare_trait_objects`、`non_fmt_panics`、`unsafe_extern_blocks` 等都走过这条路），让生态在新 edition 落地前就有机会被工具提前改写；③ **新 edition 落地并永久冻结**——1.31/1.56/1.85 起分别可写 `edition = "2018"/"2021"/"2024"`，一经发布不再变动。「老代码永远编得了」靠的是这套 lint 铺路机制，不是口头承诺。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Rust 1.0 / Edition 2015 | 2015 | 创始 edition；`try!` 宏传播错误、裸 trait object、模块路径以 crate 根为锚 |
| rustup 1.0 | 约 2016 | 官方工具链管理器：多工具链并存、组件管理、目录 override |
| Rust 2018（1.31，2018-12-06） | 2018 | Edition 机制落地；模块系统改革（`crate::` 路径）、`dyn`/`async`/`try` 关键字化、NLL 借用检查器（NLL 对**所有 edition** 生效、随 1.31 发布——是编译器特性，不是 edition 门控的差异） |
| rustup 1.2x | 约 2020 | 新增 `rust-toolchain.toml`（TOML 格式；纯文本 rust-toolchain 文件是更早的形态，两者至今仍并存） |
| Rust 2021（1.56，2021-10-21） | 2021 | disjoint closure capture、数组 `into_iter` 按值、新 prelude（`TryInto`/`TryFrom`/`FromIterator`）、resolver v2 成默认；同版引入 `rust-version` 字段（MSRV 声明） |
| Cargo resolver v3 | 2025 | 随 2024 edition 默认启用：**MSRV 感知**的依赖解析（RFC 3537，本阶段 3.6 实测） |
| Rust 2024（1.85，2025-02-20） | 2025 | `gen` 保留关键字、`unsafe extern` 块强制、impl Trait 生命周期捕获规则收紧、尾表达式临时值作用域调整 |
| 本环境工具链 | 2025-12 | rustc/cargo 1.92.0 + rustup 1.28.2；cargo-msrv 0.19.3 经 rsproxy 安装实测 |

本文示例以 **Rust 2021 edition / rustc 1.92** 为基线（与 ph10~ph17 全仓库代码层一致：单文件示例统一 `rustc --edition 2021`；2021 是当前生态事实默认，2024 已稳定可演示差异），验证工具链 **rustc/cargo 1.92.0（stable-aarch64-apple-darwin，rustup 1.28.2 管理，2025-12-08 发布，已支持 2024 edition）**。这个阶段的机制（Edition 开关、rustup、锁文件）是 Rust 工程化里最稳定的部分——Edition 一旦发布就永久冻结，你学到的 2018/2021 语义永远不会再变。

## 3. 语法与参数

### 3.1 rustup 与工具链管理

**rustup 是「工具链管理器」而非编译器本身**：`~/.cargo/bin/rustc` 实际是一个 rustup 代理（proxy），每次调用时按「环境变量 → 目录 override → 默认工具链」的顺序决定转发给 `~/.rustup/toolchains/` 下的哪一份真实工具链。一个 rustup 可以并存任意多条工具链（stable/beta/nightly/精确版本），互不干扰。

目录布局（本机为单工具链 `stable-aarch64-apple-darwin`；`list/show/which` 读操作实测）：

```text
~/.cargo/bin/                        ~/.rustup/
  rustc / cargo / rustfmt / …          settings.toml        ← default、override set 的落点（机器级）
  （都是 rustup 的代理 shim）           toolchains/
  rustup（真实程序，仅此一个）            stable-aarch64-apple-darwin/
                                           └─ bin/rustc、bin/cargo、lib/rustlib/…
```

配套认知：

- **PATH 与代理**：安装脚本把 `~/.cargo/bin` 加进 PATH（`source ~/.cargo/env` 是常见收尾步骤）；`which rustc` 指到的就是代理，代理把调用转发给 `~/.rustup/toolchains/` 下按链选中的真实 rustc（选链规则见 3.4）。所以「换工具链」本质是换转发目标，不是重装编译器。
- **目录可重定向**：`RUSTUP_HOME` / `CARGO_HOME` 环境变量能把这两棵目录挪走——CI 缓存、隔离环境常用（examples 的 ex04/ex05 用临时 CARGO_HOME 放 rsproxy 镜像配置就是此手法）。
- **rustup 本体与工具链是两件事**：`rustup update` 更新的是**已装工具链**（表见下），`rustup self update` 更新的是 **rustup 自己**；rustup 的版本（本环境 1.28.2）与 rustc 的版本（1.92.0）彼此独立、各自演进——排查「为什么行为不对」时先分清是哪个在管。
- **两条进阶命令**：`rustup toolchain link <名字> <路径>` 把本地自编译的 rustc 注册成一条工具链；`rustup target add <target-triple>` 给当前工具链补交叉编译目标（与 `component add` 的分工：一个管平台标准库、一个管工具组件）。

| 命令 | 作用 | 验证状态 |
|------|------|---------|
| `rustup toolchain install stable` | 安装一条工具链（可加 `--profile minimal` 瘦身） | 未在本环境验证（沙箱禁写 `~/.rustup`，见下） |
| `rustup toolchain list` | 列出已装工具链 | 已验证：本机仅 `stable-aarch64-apple-darwin (active, default)` |
| `rustup default stable` | 设默认工具链 | 未在本环境验证（写 `~/.rustup/settings.toml`，同被沙箱拦截；语义以官方文档为准） |
| `rustup override set stable` | 给当前目录设 override（写入 rustup 全局设置） | 未在本环境验证（同上）；**团队场景更推荐 3.4 的 rust-toolchain.toml**（随仓库走） |
| `rustup show` | 显示当前生效的工具链及生效原因 | 已验证（3.4 实测输出 overridden by） |
| `rustup component add clippy rustfmt` | 给当前工具链补组件 | 未在本环境验证（写工具链目录）；本机 stable 已含 rustfmt/clippy（`rustup component list --installed` 实测） |
| `rustup which rustc` | 打印当前解析到的真实二进制路径 | 已验证：`~/.rustup/toolchains/stable-aarch64-apple-darwin/bin/rustc` |
| `rustup update` | 升级已装工具链 | 未在本环境验证（写工具链目录） |

**`+toolchain` 临时指定**（已验证）：任何 rustup 代理命令都能用 `+` 前缀临时换工具链——`rustc +stable --version`、`cargo +nightly build`。它只影响这一条命令，不改任何配置。

> ⚠️ 本机探测结论：rustup 1.28.2 已安装，但本环境沙箱禁止写 `~/.rustup`（实测报错 `error: could not create temp file /Users/ninebot/.rustup/tmp/...: Operation not permitted`），因此一切「安装/切换/升级工具链」的写操作（install/default/override/component add/update）都未实测，命令语义以 rustup 官方文档为准；读操作（list/show/which）与 `+toolchain` 语法、rust-toolchain.toml override 均已实测。

### 3.2 发布通道：stable / beta / nightly

Rust 用**火车模型（train model）**发版：每 6 周发一个 stable；新特性先进 nightly，到点「开车」进 beta，beta 稳 6 周后进 stable。所以版本号只随时间往前走，功能跟通道走：

| 通道 | 更新频率 | 特性门槛 | 典型用途 |
|------|---------|---------|---------|
| stable | 6 周 | 只有稳定特性 | 生产、CI、团队默认 |
| beta | 6 周滚动 | 下一版 stable 的候选 | 提前验证「我的项目在下一个 stable 上还能不能编」 |
| nightly | 每天 | 全部特性（含未稳定，需 `#![feature(...)]` 开关） | 试用新特性、跑 miri、`-Zunpretty=expanded` 之类的编译器内部工具 |

两个实战认知：

- **nightly 的「特性开关」是通道差异的实质**：同一份 nightly 编译器，稳定特性直接可用，未稳定特性必须在 crate 根写 `#![feature(...)]`；stable/beta 上写 feature 开关直接报错。ph15 用过的 `RUSTC_BOOTSTRAP=1 rustc -Zunpretty=expanded` 是「在 stable 上强开 nightly 通道行为」的逃生口——能用，但属于内部机制，别进生产 CI。
- **channel 字符串的三种形态**：`stable`/`beta`/`nightly`（跟随滚动）、`1.92.0`（精确版本）、`nightly-2025-12-08`（按日期快照）。团队和 CI 要复现历史构建时用后两种，日常开发用第一种。

**feature 从 nightly 到 stable 的稳定化流程**：新语法先在 nightly 以 `#![feature(...)]` 门控（feature gate）存在，供尝鲜与生态试水；rustc 团队评估成熟后走稳定性审查（语义冻结、与既有行为不冲突），随后写进该版 release notes 随 stable 发布——之后在 stable 上再写这个开关，会得到「feature has been stable since …」的报错。两个实例：`async/await` 2019-11（1.39）稳定、`let-else` 2022-11（1.65）稳定。想知道某功能何时稳定的最快途径是查 RELEASES.md 或对应 RFC 的 tracking issue。

**beta 通道的生态角色**：beta 是「下一版 stable 的预演」。对 Rust 团队，beta 期间跑 crater（把大量公开 GitHub crate 拉来试编译）做回归普查，抓「这个改动会不会弄坏别人的代码」；对普通项目，`cargo +beta test` 提前验证自己的工程在下一版 stable 上还能不能编——把「升级工具链弄坏构建」的发现时点，从被迫升级那天提前到 beta 期。

**RUSTC_BOOTSTRAP=1 的真实风险**：它只是绕过「stable 不认 feature 开关」的检查，并不改变「这些 feature 是 nightly-only、语义未冻结」的事实——今天能编的写法，下次 nightly 可能就改掉或删掉；拼错/不存在的 feature 名会直接报 unknown feature。所以它适合「本地看宏展开」这类一次性观察（ph15 用过），不适合写进任何长期重复执行的 CI 或脚本。

> ⚠️ 本阶段只需要「能说出三通道的分工」与「会装会用」；**beta/nightly 的安装在本环境未验证**（沙箱禁写 `~/.rustup`，`rustup toolchain install beta` 实测被拦截）。通道语义以官方文档为准。

### 3.3 Edition 机制：2015/2018/2021/2024 与迁移

**Edition 不是编译器版本**（roadmap 必会概念第一条）：rustc 1.92.0 一条编译器就能按 2015/2018/2021/2024 四种语义编译——`rustc --edition <年>` 直接切换。Edition 是 **crate 级**的语法/语义开关：每个 crate 在自己的 Cargo.toml 里声明（`edition = "2021"`），同一依赖图里 2015 的 crate 和 2024 的 crate 可以混编。

顺手澄清一个默认值落差：**rustc 单独编译不传 `--edition` 时，默认仍按 2015 语义处理**（历史默认，至今未变），而 **cargo 新建项目默认用最新 edition**（本环境实测：cargo 1.92 的 `cargo new` 生成 `edition = "2024"`）——所以单文件示例必须显式写 `rustc --edition 2021`（ex01/ex02 都这么写），cargo 工程则什么都不用配。实证：不传 `--edition` 编译 `let gen = 1` 照常通过（说明默认不是 2024），同一文件加 `--edition 2024` 立即报 `expected identifier, found reserved keyword gen`。

**Edition 差异实测矩阵**（examples/ex02，rustc 1.92.0，`-D warnings`，四个案例 × 四个 edition）：

| 案例 | 2015 | 2018 | 2021 | 2024 | 差异说明 |
|------|------|------|------|------|---------|
| move 闭包字段捕获 | ✗ | ✗ | ✓ | ✓ | 2021 起 disjoint capture：闭包只捕获真正用到的字段 |
| 数组 `into_iter()` 按值 | ✗ | ✗ | ✓ | ✓ | 2015/2018 因历史怪癖按引用迭代；2021 起按值 |
| `gen` 作变量名 | ✓ | ✓ | ✓ | ✗ | 2024 起 `gen` 是保留关键字（为生成器语法预留） |
| 裸 `extern "C"` 块 | ✓ | ✓ | ✓ | ✗ | 2024 起必须写 `unsafe extern` |

失败案例的错误原文（实测摘录）：`error[E0382]: borrow of moved value: cfg`（2018 闭包整体捕获）、`error[E0308]: mismatched types — expected i32, found &{integer}`（2018 数组按引用迭代）、`error: expected identifier, found reserved keyword gen`（2024）、`error: extern blocks must be unsafe`（2024）。**同一份代码、同一条 rustc，只因 `--edition` 不同就编译成败不同**——这就是「Edition 是语义开关」最直接的证据（完整矩阵脚本与输出解读见 §6 示例 2）。

**Edition 各年差异逐条清单**（§2 时间线表的展开版；矩阵 ✓/✗ 与错误原文为 rustc 1.92 实测，其余机制语义以官方 The Rust Edition Guide / 对应 RFC 为准）：

| 档 | 变化 | 一句话影响 / 迁移线索 |
|----|------|----------------------|
| 2018 | 路径与模块系统改革 | `use` 与表达式路径语义统一，crate 根显式写 `crate::`；2015 的路径怪癖作废 |
| 2018 | 新保留字 `dyn`/`async`/`await`/`try` | 撞名标识符要 `r#` 转义（sol-03 的 `let async`→`r#async`、`try!`→`r#try!`） |
| 2018 | 裸 trait object 弃用（`dyn` 上位） | `Box<Fn>`/`&Fn` 等写法 2018 起警告、2021 起硬错误；cargo fix 自动补 `dyn` |
| 2018 | extern prelude | 依赖 crate 多数场景不再写 `extern crate`（2015 需要） |
| 2021 | 闭包 disjoint capture（RFC 2229） | 闭包只捕获实际用到的变量/字段（ex02 案例 A） |
| 2021 | 数组 `into_iter()` 按值 | 方法解析优先数组自身的 IntoIterator（ex02 案例 B） |
| 2021 | `panic!` 一致性 | `panic!(非字面量表达式)` 不再接受、首参一律按格式串处理；非串载荷用 `std::panic::panic_any`（lint `non_fmt_panics`，1.50 起全 edition 警告） |
| 2021 | prelude 扩充 | `TryInto`/`TryFrom`/`FromIterator` 进 prelude |
| 2021 | 默认 resolver v2 | cargo 对 2021 edition 默认 feature resolver v2（见 3.6 的表） |
| 2021 | 一批 warning 升 error | `bare_trait_objects`、`ellipsis_inclusive_range_patterns` 等（迁移时 cargo fix 自动处理） |
| 2024 | RPIT 生命周期全捕获（RFC 3498） | 返回位 `impl Trait` 默认捕获作用域内**全部**生命周期（2021 只捕获写在 bound 里的）；lint `impl_trait_overcaptures` 自动加 `use<..>` 保住旧语义（`use<..>` 语法自 1.82 起可用）。rustc 1.92 实测：同一函数在 2021 可满足调用方的 `+ 'static` 约束、2024 报 `lifetime may not live long enough` |
| 2024 | 尾表达式临时值析构提前（RFC 3606） | 尾表达式里的临时值在块结束前先析构（早于局部变量）——修掉一类借用错误（rustc 1.92 实测：`c.borrow().len()` 收尾 2021 报 E0597、2024 可编）；但也可能让 2021 能编的「借尾表达式临时值逃出块」写法在 2024 编不过（lint `tail_expr_drop_order` 只提示、无自动迁移） |
| 2024 | `unsafe extern` 强制（RFC 3484） | 裸 `extern "C" { … }` 必须写 `unsafe extern`（ex02 案例 D / sol-03 实测） |
| 2024 | `gen` 保留字（RFC 3513） | 为 gen block 生成器语法预留（ex02 案例 C） |
| 2024 | 其他一批 | if let 临时值作用域、禁引用 `static mut`、unsafe 属性等——本阶段不逐条展开，语义以 edition guide 为准 |

上面 2024 档里的 RPIT 与尾表达式两行，语义比「保留字/强制 unsafe」隐蔽得多，本阶段只给机制不给演示案例——想亲手验证可按表里的描述用 rustc 1.92 分别以 `--edition 2021/2024` 编译同一小文件对比。

**迁移演练：`cargo fix --edition`**（roadmap 学习内容「Edition 2018/2021/2024」的迁移命令；examples/ex03 全流程实测，cargo 1.92.0）。标准流程是「每升一档 edition：cargo fix → 手工 bump Cargo.toml → cargo fix --edition-idioms → 构建验证」：

```bash
# examples/ex03-cargo-fix-migration.sh 流程（每档 edition 重复一次此循环：fix → bump → idioms → 零警告终验）
# 1. 兼容修复：把「在旧 edition 合法、新 edition 非法」的代码改掉
cargo fix --edition              # git 仓库外演练加 --allow-no-vcs
# 2. 手工 bump Cargo.toml 的 edition 字段（实测：cargo fix 不改它！）
# 3. 习语现代化（可选）：新 edition 的惯用写法
cargo fix --edition-idioms
# 4. 零警告构建验证
RUSTFLAGS="-D warnings" cargo build
```

ex03 把一个 2015 crate（`try!` 宏、裸 trait object `Box<Fn>`、变量名 `gen`）迁到 2024 的实测记录：

| 步骤 | cargo fix 自动修了什么 | 手工做了什么 |
|------|----------------------|-------------|
| 2015→2018 | `try!` → `r#try!`（1 fix；2018 里 `try` 是保留关键字，先转义保编译） | bump `edition = "2018"` |
| 2018→2021 | `Box<Fn(&str)>` → `Box<dyn Fn(&str)>`（裸 trait object 在 2021 是硬错误） | bump `"2021"`；`r#try!` → `?`（只报 deprecated，cargo fix 不做语义现代化） |
| 2021→2024 | `let gen` → `let r#gen`（2 fixes；`gen` 成保留关键字） | bump `"2024"` |

**`(N fixes)` 的读法**：表里的数字是 cargo fix 报告的**修复应用数**，按源码里需要改写的标识符逐个计：ex03 的 2021→2024 一步里 `gen` 出现在 `let gen = 1;` 的绑定与 `println!("gen = {}", gen)` 的参数两处（格式串里的 `"gen"` 是字符串、不用改），所以是 2 fixes；sol-03 的 2015→2018 一步（`try!` 调用、`let async`、`async` 使用共 3 处标识符）报告 3 fixes——修复数 ≈ 受影响的标识符位置数，不是「代码块」数。

三个实测要点（教学增量，都是「文档没明说、实证才看清」的）：

1. **`cargo fix --edition` 打印 `Migrating Cargo.toml from 2015 edition to 2018` 但不改写 Cargo.toml**——edition 字段必须手工 bump（clean 复验：新建 2021 crate 跑 `cargo fix --edition` 后 `grep edition Cargo.toml` 仍是 `"2021"`）。
2. **cargo fix 的策略是「转义保编译」而非「语义现代化」**：`try!` 变 `r#try!`、`gen` 变 `r#gen`——先让你能编，现代化（`?`、改名）留给你。
3. **真实项目不需要 `--allow-no-vcs`**：cargo fix 默认要求 git 工作区干净，用版本控制当迁移前快照——这也是「迁移前先 commit」的强制纪律。

**cargo fix 的旗标家族**（一个子命令管住迁移的安全网）：`--allow-no-vcs`（演练目录不在 git 里时用——ex03/sol-03 都加了它）；`--allow-dirty` / `--allow-staged`（工作区有未提交改动但仍想修）；`--broken-code`（代码已有编译错误时也先把能修的修掉，剩下的留给你）；`--features <feat>` / `--target <triple>`（`cfg` 门控的代码只有开对应 feature/目标才会被编译到——cargo fix 修不到没被激活的代码，官方文档明示的边界）。

> ⚠️ 迁移的逆向问题（2024 代码在 2021 编译器上跑）无解——**Edition 只能升不能降**；团队要升 edition 前先在 CI 加新 edition 的构建矩阵验证。多 edition 混编的细节见第 4 章。

**为什么必须一档一档升、不能 2015 直接跳 2024？** 因为迁移 lint 是按「相邻 edition 对」设计的：`cargo fix --edition` 每次只把代码修到「能在**下一档**编译」，修复集合小到可以人工 review（机制见第 4 章）。直接跳档没有对应的修复集合可应用——ex03/sol-03 里 2015→2024 都要走 2018、2021 两趟中转，就是这个原因。

**宏与 edition：展开产物按谁的 edition 检查**（兑现 §1 承接句与 ph15「下一阶段」的预告：macro_rules! 的跨 edition 行为与 `#[macro_export]` 边界在这里收束）。宏**定义方**与**调用方** edition 不一致时，展开产物按哪边的 edition 做语法检查？答案不是一句话，rustc 1.92 的实测结论是**逐 token 按它来源文件的 edition 判定**（机制以 rustc 官方行为为准，以下为实测口径）。**一句话结论：macro_rules! 在调用处展开，但展开产物里每个 token 的语法判定跟着它的来源走——宏体自带 token 看定义方 edition，调用方写出的 token（实参）看调用方 edition。**

- **宏体里自带的 token**（宏作者写的代码）按**定义方** crate 的 edition 判。实测：一个 edition 2015 的库 `#[macro_export]` 一个宏、宏体写 `let gen = 42`（2015 里 `gen` 是普通标识符），2024 edition 的调用 crate 正常编译运行、输出 `gen = 42`；同样的宏体若定义在 2024 库里，连 2021 的调用方都会报 `error: expected identifier, found reserved keyword 'gen'`（报错定位在宏调用处）。
- **调用方传入的 token**（宏实参，尤其 `$x:ident` 这类会被展开进标识符位置的）按**调用方** crate 的 edition 判。实测：调用方在 2024 写 `let_var!(gen = 7)`（宏把实参绑成 `let $name = $v;`）报同样的保留字错误，改成 `r#gen` 即过；同样的调用在 2015/2021 调用方里照常编译。
- hygiene 只保证「同名标识符不互相污染」（ph15 已实测），**不管某个词在语法上是不是保留字**——保留字判定跟着 token 出处走，与 hygiene 是两套独立机制。

| token 来源 | 典型例子 | 保留字判定按谁 |
|-----------|---------|--------------|
| 宏体自带的代码 | 宏体里的 `let gen = 42` | 宏**定义方** crate 的 edition（实测：2015 定义→2024 调用照常编译；2024 定义→2021 调用报保留字） |
| 调用方写出的实参 | `let_var!(gen = 7)` 里的 `gen` | **调用方** crate 的 edition（实测：2024 调用方必须 `r#gen`，2015/2021 调用方裸写即可） |

这解释 ex03/sol-03 迁移里的 `r#try!`/`r#gen` 为什么是那个写法：2018 起 `try`、2024 起 `gen` 在**你自己 crate 的源码里**成为保留字，而宏调用名（`try!`）、变量绑定与传给宏的实参都是你写出的代码——按**调用方 edition**（正在迁移的 edition）判，必须转义（`r#try!`、`let r#gen`、以及会被宏展开到标识符位置的 `gen` 实参同理；ex03 的「2 fixes」= `let gen` 绑定与 `println!` 使用两处标识符，sol-03 的 `let async`→`r#async` 同源）。cargo fix「转义保编译」的本质正是：把**调用方**源码里的标识符改成按调用方 edition 合法的形态——它修的一直是「你正在迁移的 crate 的源码」，所以永远站在调用方视角。

推论（对迁移的实用价值）：升 edition 时**不需要担心依赖宏的内部实现**——依赖仍按它自己声明的 edition 编译，其宏体 token 也按定义方判（上面 2015 老宏体里的 `gen` 在 2024 工程里照常展开即是例证）；真正要检查的是**你自己写出的宏调用与实参**。反过来，若依赖升了新 edition 而你没升，其宏体里用 `r#` 转义的写法（如 `r#gen`）也照常可用——`r#` 转义语法自 rustc 1.30 起在**所有 edition** 都可用，不随 edition 门控。

**`#[macro_export]` 与跨 crate 调用**：`#[macro_export]` 把声明宏导出到**定义 crate 的 crate 根**，其他 crate 才能 `use 定义crate::宏名;` 后按路径调用；不写它时 `macro_rules!` 只在定义处之后的文本作用域可见（跨模块/`#[macro_use]` 等可见性细节属 ph15，这里不展开）。跨 crate 调用的 edition 边界就是上面两条：实参按调用方、宏体按定义方。一个 2015 年代的连带差异：edition 2015 没有 extern prelude，调用方引用任何依赖都要先写 `extern crate 定义crate;`（与是不是宏无关，实测 2015 调用方直接 `use` 报 `error[E0432]: unresolved import`），2018+ 免掉这行。实际工程含义：你的 crate 升 2024 后，传给依赖宏的实参要过一遍新 edition 保留字检查；依赖宏内部只要依赖自己不升 edition，就不受你迁移影响（本段机制均为 rustc 1.92 实测，跨版本行为以 rustc 官方为准）。

想亲手复现上面最反直觉的一条（宏体里的保留字按**定义方** edition 判），零依赖、三条 rustc 命令即可（rustc 1.92 已验证）：

```bash
# 案例 1：宏体里写 let gen = 42，定义在 2015 crate，2024 调用方编译运行
cat > lib.rs <<'EOF'
#[macro_export]
macro_rules! make_gen {
    () => {{ let gen = 42; println!("gen = {}", gen); }};
}
EOF
rustc --edition 2015 --crate-type lib --crate-name def2015 lib.rs   # 定义方 2015
cat > app.rs <<'EOF'
use def2015::make_gen;
fn main() { make_gen!(); }
EOF
rustc --edition 2024 --extern def2015=./libdef2015.rlib app.rs -o app && ./app
# 输出 gen = 42 —— 2024 调用方编译 2015 宏体，gen 按定义方 2015 判（普通标识符），照常通过

# 案例 2：同样的宏体改定义在 2024 crate（rustc --edition 2024 重编 lib.rs 为 def2024），
#         2021 调用方编译即报 error: expected identifier, found reserved keyword 'gen'
```

两个案例只有「宏定义在哪个 edition 的 crate」不同，调用方行为就相反——这正是「展开产物按 token 来源文件判 edition」最直观的对照。

### 3.4 rust-toolchain.toml：把工具链钉进仓库

`rust-toolchain.toml` 是放在仓库根（或任意目录）的**工具链声明文件**：rustup 代理在任何 cargo/rustc 调用前，从当前目录向上查找该文件，找到就按它选择工具链——**clone 即生效，不用任何人肉配置**。

```toml
# examples/ex01-toolchain-file/rust-toolchain.toml —— 已验证的最小形态
[toolchain]
channel = "stable"                    # 发布通道 / "1.92.0" 精确版本 / "nightly-2025-12-08" 日期快照
components = ["rustfmt", "clippy"]    # 缺失时 rustup 自动补齐（未在本环境实测：本机 stable 已含这两组件）
# targets = ["x86_64-unknown-linux-gnu"]  # 交叉编译目标（本阶段用不到）
# profile = "minimal"                 # 安装粒度：minimal / default / complete
```

实测（examples/ex01，rustup 1.28.2）：文件放进目录后，`rustup show` 输出

```text
active toolchain
----------------
name: stable-aarch64-apple-darwin
active because: overridden by '<目录>/rust-toolchain.toml'
```

（完整文件布局、运行命令与输出解读见 §6 示例 1。）

工具链选择的**优先级**（从高到低，rustup 官方顺序）：`+toolchain` 命令行参数 → `RUSTUP_TOOLCHAIN` 环境变量 → **目录级覆盖**（`rustup override set` 与 `rust-toolchain.toml` 同属这一层：都从当前目录向上逐级查找，**以距当前目录最近者生效**）→ 默认工具链。注意官方把 override 与工具链文件并列、按就近竞争，不是文件永远压过 override——团队把工具链文件 commit 进仓库后，成员本机残留的 `rustup override` 只会作用于它被设置的那个目录及其子树，仓库内以文件为准。前三档均已实测（`RUSTUP_TOOLCHAIN=stable rustc --version`、`rustc +stable --version`、本小节的 `rustup show` overridden by）。

| 优先级 | 机制 | 例子 | 什么时候用 |
|--------|------|------|-----------|
| 1 | `+toolchain` 参数 | `cargo +nightly build` | 单条命令临时换工具链（不改任何配置） |
| 2 | `RUSTUP_TOOLCHAIN` 环境变量 | `RUSTUP_TOOLCHAIN=1.92.0 cargo build` | CI/脚本里让整次调用统一换工具链 |
| 3 | 目录级覆盖（就近生效） | `rust-toolchain.toml`（随仓库走）或 `rustup override set`（写 `~/.rustup/settings.toml`，机器级） | 团队/项目落地用**文件**；个人临时目录用 override |
| 4 | 默认工具链 | `rustup default stable` | 个人机器的兜底 |

另两个字段值得知道：`path = "..."`（直接指向一条本地自定义工具链，如自编译的 rustc；与 `channel` 互斥——rustup 官方文法里二者不可同写）与 `profile = "minimal"|"default"|"complete"`（安装粒度；文件里不写时按 `rustup set profile` 设定的当前默认；`components`/`targets` 与 profile 是**叠加**关系——profile 之外的额外组件按 components 列表补装，这就是「缺失时自动补齐」的来源，自动补齐路径在本环境未实测）。

一句话区分 3 档里的两个目录级手段：**`rustup override set` 把选择写进本机的 settings.toml（不进 git，别人 clone 不到），`rust-toolchain.toml` 把选择写进仓库（clone 即生效）**——团队环境一致只可能靠后者，这正是本阶段把它当「团队落地主力」的原因。历史沿革：rustup 约 2020 年（1.2x 时代，具体版本史以 rustup CHANGELOG 为准）引入 TOML 形态；更早的纯文本 `rust-toolchain`（文件里直接写 `stable`/`nightly-2025-12-08`）至今仍被支持（向后兼容），新项目直接写 `.toml` 形态即可。

> ⚠️ 两个坑：① 文件对**进入该目录的所有人**生效——钉精确版本号会让没装该版本的成员触发联网下载（本环境实测：channel 写 `"1.92.0"`/`"1.999.0"` 时 rustup 立即尝试 `syncing channel updates`，沙箱拦截写 `~/.rustup` 而失败）；离线团队要么预装、要么钉已装版本。② 它是「目录级开关」，放进 examples/ 子目录会改变该子树里一切 cargo 调用的工具链——仓库里放几份要克制。

### 3.5 Cargo.lock 策略：应用 vs 库

`Cargo.lock` 记录**依赖树每个包的精确版本与 checksum**（实测格式：头部 `# This file is automatically @generated by Cargo. It is not intended for manual editing.` + `version = 4`，每个包 `name`/`version`/`source`/`checksum` 四要素）。它回答的问题是「这次构建用的到底是依赖的哪个具体版本」——**没有它，Cargo.toml 里的 `itoa = "1"` 今天解析成 1.0.14、下个月解析成 1.0.18**。

**锁文件格式自身也有版本**（头部 `version = N`），且每次加版本都要求「够新的 cargo 才读得懂」：v2（cargo 1.38 起）压缩依赖数组、checksum 内联；v3（1.47 引入、1.53 起默认）文件头显式写 version、git 依赖编码方式改变；v4（1.78 起默认，本环境实测即 v4）修正含特殊字符源 URL 的编码规则（如 `?branch=foo bar` 编码为 `foo+bar`）。含义：**锁文件版本与 cargo 版本强绑定**——老 cargo 遇到新格式锁会拒绝工作（提示升级），所以「锁格式版本」本身也是工具链一致性的一部分（第 4 章再收束）。

| 维度 | 应用（bin/最终产物） | 库（lib/给别人依赖） |
|------|--------------------|---------------------|
| Cargo.lock 提交 git？ | **提交**（可复现构建的根基） | **不提交**（库的锁文件对下游无效——下游应用的锁才算数） |
| .gitignore | 只忽略 `/target` | `/target` + `Cargo.lock` |
| 依赖升级 | `cargo update` 后连锁文件一起 commit，可 review | `cargo test` 时自然解析到新版，CI 兼跑最低版本 |
| 回退手段 | `cargo update -p itoa --precise 1.0.14`（实测输出 `Downgrading itoa v1.0.18 -> v1.0.14`） | 同左，但影响仅限本地 |
| CI 守门 | `cargo build --locked`：锁文件与 Cargo.toml 失配即失败 | 一般不用 `--locked`（锁文件本就不进 git） |

实测（examples/ex05）：把 Cargo.toml 的 `itoa = "1"` 改成 `itoa = "=1.0.14"`（与锁里的 1.0.18 失配）后，`cargo build --locked` 报错 `error: the lock file ... needs to be updated but --locked was passed to prevent this`——这就是 CI 防「改了依赖忘了更锁文件」的机制。另一个反直觉点：版本要求失配才触发——改成 `itoa = "1.0.15"`（区间仍含 1.0.18）时 `--locked` 照常通过（实测）（完整脚本与逐条输出解读见 §6 示例 5）。

**锁文件对应用和库的不同意义**（roadmap 必会概念）一句话版：应用是「最终构建者」，锁文件是它的交付物；库是「被构建的零件」，它的锁文件连参考值都算不上——别让你的库把版本选择强加给下游。

**`--locked` / `--offline` / `--frozen` 三个旗标**（CI 相关配置里高频出现，一次分清）：

| 旗标 | 语义 | 典型用法 |
|------|------|---------|
| `--locked` | 锁文件与 Cargo.toml 失配就失败，不许悄悄更新锁 | 应用/发布 CI 守门（ex05 实测） |
| `--offline` | 禁止一切网络访问，只用本地缓存 | 离线构建；缓存完备时避免网络抖动 |
| `--frozen` | = `--locked` + `--offline`（既不许改锁也不许联网） | 发布审计、完全确定性的构建 |

**依赖升级的决策序列**（「记录版本 + 可回退」的完整工作流）：① `cargo update --dry-run` 先看会动哪些包（不改锁）；② 定向升级 `cargo update -p <crate>`（或加 `--precise <版本>` 钉到具体版/回退）；③ 跑测试、review 锁文件 diff，升级与锁变更放进同一次 commit——ex05 的 `Downgrading itoa v1.0.18 -> v1.0.14` / `Updating itoa v1.0.14 -> v1.0.18` 就是 ②③ 步的日志；④ CI 用 `--locked` 防「有人改了依赖忘了更锁」。

**库的 CI 复现坑**：库不提交锁，但库自己的 CI 每次跑都在**重新解析**——昨天的测试和今天的测试可能悄悄用了不同版本的依赖。可选对策：CI 里先 `cargo generate-lockfile` 再 `cargo test`（保证单次 CI 内一致），或干脆把锁也提交进仓库（发布到 crates.io 后下游作为库依赖时以自己的锁为准，上游锁不影响下游解析，提交它只服务于仓库自身 CI 的可复现性）。

### 3.6 MSRV：声明、解析与检查

**MSRV（Minimum Supported Rust Version，最低支持 Rust 版本）**是「这个 crate 至少要多新的 rustc 才能编」。声明方式：Cargo.toml 里 `rust-version = "1.85"`（cargo 1.56+ 支持）。它的两个作用：

1. **编译期护栏**：用比 rust-version 老的 rustc 编译直接报错（报错信息明确给出所需版本）；
2. **解析期参与选版本**（edition 2024 / resolver v3 起）：cargo 选依赖版本时优先选「其 rust-version 不超过你的 MSRV」的最新版。

**resolver 版本速览**（别把 resolver 与 edition 混为一谈：resolver 管「feature 怎么合并 + 依赖版本怎么选」两件事）：

| resolver | 谁的默认 | 关键差异 |
|----------|---------|---------|
| `"1"` | 2021 edition 之前的 cargo 工程 | feature 在所有目标/依赖类型间统一合并（历史行为） |
| `"2"` | edition 2021 的 cargo 工程（1.56 起） | feature 解析精细化：构建脚本/开发依赖/按目标平台分离，避免 feature 串扰 |
| `"3"` | edition 2024 的 cargo 工程（1.85 起） | = v2 行为 + **MSRV 感知选版**（本阶段 3.6/4 章实测部分） |

注：v1→v2 改的是 feature 合并语义（机制细节属 ph06/ph17 工程范畴，本阶段只展开它与 edition 迁移的联动，见下）；**v3 相对 v2 才引入 MSRV 感知**——所以 ex04 对照组（edition 2021 = resolver v2）看不到任何 MSRV 行为，只有 2024 那组看得到。这套感知不止作用于锁文件解析：cargo 1.84+ 的 `cargo add` 也会按声明的 MSRV 挑兼容版本（[Rust 1.84 release notes](https://blog.rust-lang.org/2025/01/09/Rust-1.84.0/) 的 `cargo add clap` 示例即此行为），`cargo metadata`/`cargo tree` 等命令同样基于同一套解析结果。另注意：在 Cargo.toml 显式写 `resolver = "3"` 需要 rust-version ≥ 1.84（老 cargo 不认这个值），edition 2024 则自带默认（1.85+ 起），不用你写。

**迁移 2018→2021 的 resolver 联动：默认会静默从 v1 翻到 v2**。上面表里的「谁的默认」是 cargo 按 edition 自动取的：2015/2018 工程（Cargo.toml 不写 resolver 键）实际跑 v1；**edition 字段一 bump 到 2021（仍不写 resolver 键），默认就翻到 v2**——这是 edition 迁移里唯一不要求手工改、却会改变构建行为的联动。对照 3.3 的 ex03/sol-03：两个演练 crate 零依赖、无 feature，翻不翻完全无感；真项目要把这当一件事验收。

v1→v2 改的是 **feature 统一的边界**：v1 把 dev/build/target-specific 依赖的 feature 跟正常依赖「一锅烩」；v2 把它们隔开——**dev-dependency 与 build-dependency 的 feature 不再参与正常构建的统一，按平台门控（`cfg(target_os = ...)` 之类）的依赖其 feature 也各自解析**。cargo 1.92 实测一个可复现的泄漏现场：应用依赖 `base`（不开 feature），dev-dependency `louder` 依赖 `base` 并开 `features = ["loud"]`——edition 2018（v1）下 `cargo build -vv` 里 `base` 带 `feature="loud"` 编译（dev 依赖的 feature 悄悄漏进正常构建），同样工程 edition 2021（v2）下不再带。**结果：迁移后同样的 `cargo build`，实际启用的 feature 集合可能变了**——不是编译报错，而是「悄悄变」（代码路径、优化、乃至二进制都不同）。

迁移期建议三步走：① `cargo tree -e features` 对比迁移前后实际启用的 feature（注意 `cargo tree` 画的是依赖图上的 feature **边**，编译时真正传给 rustc 的 cfg 才反映统一结果——以 `cargo build -vv` 或构建日志为准）；② 全量 CI（build/test/clippy 各 target）过一遍，别只看「能编译」；③ 想「一次只动一个变量」，可以在**不升 edition 的 2018 工程里先显式写 `resolver = "2"`**——resolver 键与 edition 解耦，2015/2018 也能开 v2（本环境 cargo 1.92 实测行为与 2021 默认一致），先单独消化 feature 隔离的影响，再单独升 edition。类似联动 2021→2024 还会再来一次：默认 resolver 翻到 v3（v2 的隔离语义全保留 + MSRV 感知选版，见上文 ex04）——2024 迁移同时改变语言语义与依赖选择，两件事都要验收。

另外注意 `rust-version` 字段本身的写法细节：cargo 1.56 起支持该字段，值为两位或三位版本号（如 `"1.85"` / `"1.85.0"`）；声明后 cargo 在**编译期**（rustc 老于声明即报错并给出所需版本）与**解析期**（见上）双重把关；crate 发布后该字段也会展示在 crates.io 页面上，作为下游选版的依据。

**resolver v3 的 MSRV 感知实测**（examples/ex04，cargo 1.92.0，rsproxy）：项目 `edition = "2024"` + `rust-version = "1.85"`，依赖 `home = "0.5"`（最新版 0.5.12 要求 Rust 1.88）——

```text
# edition 2024（resolver v3）：自动选兼容版
Locking 11 packages to latest Rust 1.85 compatible versions
 Adding home v0.5.11 (available: v0.5.12, requires Rust 1.88)
# 对照组 edition 2021（resolver v2）：直接选最新，不管 MSRV
Locking 3 packages to latest compatible versions   → home 0.5.12
```

（完整对照实验与逐幕输出解读见 §6 示例 4。）

**检查依赖的 MSRV**（roadmap 练习）：依赖的 rust-version 在 `cargo metadata` 的 JSON 里（exercises/sol-02 脚本实测输出，2026-09-02 复测确认：`home 0.5.11: rust-version = 1.81`、`windows-sys 0.59.0: rust-version = 1.60`、`windows-targets 0.52.6: rust-version = 1.56`——这些是传递依赖，版本随 crates.io 索引日期漂移，复测时以本机 lock 实况为准）。专用工具 **cargo-msrv**（0.19.3，本环境经 rsproxy `cargo install cargo-msrv --locked` 实测安装）的子命令分工：`cargo msrv show` 读本 crate 的 MSRV（实测 `MSRV is Rust 1.85.0`）、`cargo msrv list` 列全部依赖的 MSRV 表格（均已实测）；而 `cargo msrv find`（求真实下限：用二分/线性试探各历史工具链找首个可编译版本）与 `cargo msrv verify`（验证声明的 rust-version 真的能编，可自定义 check 命令）都需要 rustup 联网安装历史工具链——**未在本环境验证**（沙箱禁写 `~/.rustup`），语义以 cargo-msrv 官方文档为准。

> 本阶段只讲「声明 + 解析 + 检查」；**库的 MSRV 测试策略（CI 跑最低版本矩阵）在 project/ 模板里有可抄的最小形态**（`.github/workflows/ci.yml` 的 test 矩阵 `stable + 1.85.0`）。

## 4. 底层原理

**同一编译器怎么按 edition 切换语义**：rustc 内部没有「四个编译器」，而是一份代码 + 一组按 edition 门控的行为开关。Cargo 编译每个 crate 时把它的 edition 传给 rustc（`rustc --edition 2021 ...`——这就是 ex02 能直接用一条 rustc 演示四 edition 矩阵的原因）；解析器、名称解析、借用检查里按 `span.edition()` 分流：比如 `gen` 在 2024 的语法上下文里被词法成保留关键字、在 2021 里仍是普通标识符；闭包捕获分析在 2021+ 走 disjoint capture 路径。ABI 与 crate 间接口与 edition 无关——所以混编安全：**edition 只改「源码怎么被理解」，不改「产物怎么被链接」**。

```text
crate A (edition 2015) ──┐
crate B (edition 2021) ──┼── cargo 逐个传 --edition ──▶ 同一条 rustc ──▶ 各自语义开关 ──▶ 统一链接
crate C (edition 2024) ──┘
```

**混编安全，但边界上有裂缝：哪些场景会出问题**。上面「混编安全」的根子是 ABI/类型布局与 edition 无关：对外函数签名、结构体布局、类型身份都不带 edition 标签——`Box<Fn(...)>` 与 `Box<dyn Fn(...)>` 是**同一个类型**，区别只在写法带不带 `dyn`。所以 2015 老库被 2024 新工程依赖，链接运行照常；裂缝不在产物，在**消费方自己源码里写出的语法**：

- **写类型名的语法**：2015 库的公开 API 若带裸 trait object（2015 里 `pub fn log(&self, f: &Fn(&str))` 合法），2021+ 消费方在**自己代码里**写 `&Fn(&str)` 是硬错误（`bare_trait_objects`），必须写 `&dyn Fn(&str)` 才能引用同一 API——**类型没变，写法按消费方 edition**（ex03 的 `Box<Fn>`→`Box<dyn Fn>` 就是消费方视角的修正；库作者一行不用改）。
- **`r#` 命名冲突**：2015 库可以合法导出后来成了保留字的名字（如 2015 里写 `pub fn gen()`——`gen` 在 2015 不是关键字，现代 rustc 照常编译）；2024 消费方引用它必须写 `r#gen`，且**导入与调用两处都要转义**（实测：`use oldlib::r#gen;` 后写裸 `gen()` 仍报 `expected expression, found reserved keyword 'gen'`，必须写 `r#gen()`；`r#` 语法自 rustc 1.30 起全 edition 可用，2015 文件里也能写）——**名字没变，引用语法按消费方 edition**。
- **宏的跨 edition 调用**：传给依赖宏的实参按调用方 edition 检查（3.3 末尾「宏与 edition」小节实测）——同一个依赖宏，在不同 edition 的调用方手里可编译性可能不同。

一句收束：混编的「安全」是 ABI/布局层面的事实，**语义差异藏在被调方内部**——2015 库内部的 edition 语义（闭包整体捕获、数组 `into_iter` 按引用迭代）在它自己内部自洽、不泄漏到接口；真正会在边界上咬人的，永远是「消费方自己写出的语法」。这也是「迁移是每个 crate 自己的责任」的另一面：混编允许整个依赖图**慢慢升**，但**升完的 crate 要用自己 edition 的语法去引用全图**——老库不用动，新消费方按自己的 edition 写引用即可。

一个更本质的模型：**把 edition 看作 rustc 内部「一组已开启的语义开关（feature gate）的预设集合」**——2024 edition 的 crate 等价于默认打开一组针对 2024 的 gate（gen 保留字、unsafe extern 强制、RPIT 全捕获……），2015 edition 一个都不开。这些 gate 的检查点散布在编译管线各阶段，且都按「正在编译的代码属于哪个 edition」取值——ex02 的四个案例其实是四个不同的分流点：`gen` 走词法层（保留字表按 edition 切换）、闭包捕获走借用检查层、数组 `into_iter` 走方法解析层、unsafe extern 走 AST 校验层。这解释了为什么 edition 的差异永远「局部而精确」：不是换了套编译器，而是同一编译器的几个检查点在读 edition 字段。（一个易被忽略的例外：宏展开产物里的 token 不是按「正在编译的 crate」统一取值，而是**逐 token 按来源文件**的 edition 判保留字——宏体自带 token 按定义方、调用方实参按调用方，见 3.3 末尾「宏与 edition」小节。）

**迁移为什么不破坏生态（lint 迁移机制）**：每个「新 edition 非法」的旧写法，先在所有 edition 上变成带 machine-applicable suggestion 的 warning（如 `bare_trait_objects`），只有在新 edition 的语法上下文里才升级为硬错误。`cargo fix --edition` 做的事就是：**用当前 edition 编译，收集这些「在新 edition 会变成错误」的 warning，批量应用编译器给出的机械修复**——所以它能修的都是编译器知道怎么修的（转义关键字、加 `dyn`），修不了语义层（`r#try!` → `?` 是「用现代写法重写」，不是「保编译」）。这也解释了 ex03 的实测：cargo fix 的修复清单永远「保守但安全」。

**迁移 lint 的组织**：每个 edition 的破坏性变化会先落成「兼容性 lint 组」（rustc 的 `rust-2021-compatibility` / `rust-2024-compatibility` 两组），`cargo fix --edition` 实际就是「针对这些 lint 组批量应用 machine-applicable 修复」。修复能力分三档：① **机械可修**——转义保留字、补 `dyn`/`unsafe`、自动加 `use<..>` bound 等（绝大多数，自动完成）；② **只报不修**——如尾表达式析构顺序没有保语义的改写（lint `tail_expr_drop_order` 只提示你人工检查）；③ **语义现代化**——`cargo fix --edition-idioms` 单独做（`r#try!` → `?` 这类「用现代写法重写」，不是保编译）。这就是 ex03/sol-03 实测里「该自动修的自动修、该手工的永远留给你」的原因。

**MSRV 与 resolver**：resolver（依赖解析器）输入是版本要求（`itoa = "1"` → 区间 `[1.0.0, 2.0.0)`），输出是锁文件里的精确版本。v1/v2 只看 semver 区间取最新；**v3（edition 2024 默认，`resolver = "3"`）额外看每个候选版本的 `rust-version` 元数据，过滤掉「需要比你声明的 MSRV 更新的 rustc」的版本**——ex04 里 `Adding home v0.5.11 (available: v0.5.12, requires Rust 1.88)` 那行日志就是过滤动作的现场。索引侧的支撑：sparse 索引（`sparse+https://...`）里每个版本带 `rust_version` 字段，rsproxy 镜像原样转发，`cargo metadata` 再把它暴露给检查工具（sol-02 的提取路径）。

MSRV 感知选版还有一个**可配置的回退旋钮**：cargo 1.84 稳定这项能力时（[Rust 1.84 release notes](https://blog.rust-lang.org/2025/01/09/Rust-1.84.0/)）提供了 `.cargo/config.toml` 里的 `resolver.incompatible-rust-versions`（三档：`allow`=完全无视 MSRV 选最新 / `fallback`=优先兼容版、找不到兼容版时退回不兼容并提示 / `deny`=找不到兼容版直接报错），也可在 Cargo.toml 显式写 `resolver = "3"`；2024 edition 自 1.85 起默认启用（默认即 ex04 看到的 fallback 行为）。CI 里想验证「项目在新依赖下还能不能编」时，可以用 `CARGO_RESOLVER_INCOMPATIBLE_RUST_VERSIONS=allow cargo update` 临时关掉过滤再构建。

**Cargo.lock 与确定性构建**：锁文件是「解析结果的序列化」——cargo 先查锁，锁里的版本仍满足 Cargo.toml 区间就直接用（不再问索引），所以全队 + CI 解析结果逐位一致；`--locked` 把「锁可能过期」从静默修复变成硬错误。锁格式本身也版本化（`version = 4`，v4 自 2024 年随新 cargo 默认生成），老 cargo 读新锁可能拒绝——**锁格式版本也是工具链一致性的一部分**。另两个相关事实：每个 registry 包在锁里带 `checksum`，cargo 下载后先验哈希再解压（防索引/镜像被篡改后给错代码）；`cargo update -p x --precise 1.0.14` 能回退的前提是该版本仍可从索引解析——被 yank 的版本不能再被选为**新**解析结果（--precise 到 yanked 版本会失败），但已锁定在锁文件里的旧版本仍可继续构建。

## 5. 使用场景

- **团队/开源项目统一环境**：rust-toolchain.toml + Cargo.lock + CI `--locked` 三件套（project/ 模板即落地形态）。什么时候**不**用 rust-toolchain.toml：一次性脚本、给别人的教学片段（读者工具链各异，钉死反而添堵）。
- **升 edition 的时机**：项目惰性/新特性驱动均可，但要走完整迁移流程（fix → bump → idioms → 零警告构建 → CI 矩阵）；升之前确认全部依赖与 MSRV 承诺兼容。**库 crate 升 edition 是 breaking change 级决策**（下游老 rustc 用户编不了），慎升。
- **MSRV 承诺**：库作者声明 `rust-version` 并在 CI 跑最低版本矩阵（project/ 模板的 `stable + 1.85.0`）；应用开发者对 MSRV 无承诺义务，但声明它能让 resolver v3 帮你挡掉「装了编不了的依赖」。
- **nightly 的正当用途**：试用未稳定特性、跑 miri/cargo-expand 类工具链内部工具；生产代码钉 stable。ph15 的 cargo expand 观察宏展开就是「借 nightly 机制做学习观察」的典型。

**决策速查**（把上面的场景压成一张表）：

| 你的处境 | 推荐做法 | 落点 |
|----------|---------|------|
| 新项目（bin） | `cargo new` 默认 edition（1.85+ 即 2024）+ 提交锁文件 | `Cargo.toml` edition / `Cargo.lock` |
| 新项目（lib） | 第一天就声明 `rust-version`；锁文件不提交 | `Cargo.toml` rust-version / `.gitignore` |
| 存量项目升 edition | 逐档 `cargo fix --edition` + CI 矩阵加新 edition | 见 3.3 / ex03 |
| 团队/发布项目 | `rust-toolchain.toml` 钉工具链 + CI 用 `--locked`/`--frozen` | 见 3.4 / project 模板 |

一句话：真正什么都不用配的只有「纯个人一次性脚本」——其余形态都能从本阶段的某件套里直接受益。

**真实工程叙事 1：升 2021 那周，构建「悄悄」变了**。某团队在一个 2018 edition 的长期服务上升级 2021：`cargo fix --edition` 逐档跑完、`-D warnings` 零警告、CI 全绿——看似一帆风顺。上线后接到反馈：某个老功能行为不对。查因发现：测试工具（dev-dependency）很久以前给共享依赖 `base` 顺手开了个 `legacy-mode` feature，2018 edition 下 resolver v1 把 dev 依赖的 feature 一锅烩进正常构建——`base` 一直带着 `legacy-mode` 编译，那段 `cfg` 门控的旧代码路径在生产二进制里是活的；bump 到 2021 后默认 resolver 静默翻到 v2，feature 隔离，`legacy-mode` 不再进正常构建，旧路径随之消失。**代码一行没改、CI 全绿，行为却变了**——这是 3.6 联动块（resolver v1→v2）的现实版。教训：升 edition 的验收清单必须包含「resolver 行为对照」（`cargo tree -e features` 前后 diff、`cargo build -vv` 日志抽查），不能只看「能不能编」；更稳的做法是先在 2018 上显式 `resolver = "2"` 单独验证 feature 差异，再升 edition——一次只动一个变量。

**真实工程叙事 2：核心库留在 2015，新服务直接 2024**。团队的核心数值库是十年前写的 2015 edition（内部还挂着 `try!` 类迁移债务），评估后决定它不升——混编允许，老库照常被 2024 的新服务依赖，链接运行全正常，这是「ABI 与 edition 无关」的日常证明。摩擦出现在代码审查：新同学写 `core_lib::gen`（该库 2015 里合法导出过 `pub fn gen()`）编译不过，报 `expected identifier, found reserved keyword 'gen'`——不是库坏了，是**引用语法按消费方 edition**：2024 代码里得写 `core_lib::r#gen`（导入与调用两处都要转义，第 4 章混编块有详解）。这类问题编译期就暴露、改一行就好，但会反复出现——团队共识是把「老库有没有导出后来成了保留字的名字」列进引入前的检查项（ph17 评审清单的落点之一）。另一面：老库没声明 `rust-version`，resolver v3 选它的版本时无从按 MSRV 过滤（cargo 对未声明 rust-version 的候选不拦）——库不声明 MSRV 的隐性代价，最终由依赖它的人来付（ph17 的 MSRV 评审维度会正式处理）。

- **跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：C/C++ 没有「语言版本开关」概念，`-std=c++17` 只选标准档、老编译器不能编新代码，生态靠「各家编译器实现同一标准」对齐；Go 用「go.mod 的 go 指令 +  toolchain 指令」做类似的事（Go 1.21+ 工具链自动下载管理，与 rustup 思路趋同）；Java 的 `--release` 是单编译器多目标的语言层开关，但没有 crate 级混编。Rust 的 Edition 是「同一工具链、多套语义、包级粒度、永久冻结」四要素的独特组合——语言进化的兼容性难题，Rust 的解法是把变化做成显式开关而不是版本分裂。

## 6. 代码示例

本节展示完整示例的关键片段，完整文件在 `examples/` 目录（验证环境 rustc/cargo 1.92.0 macOS arm64 + rustup 1.28.2；ex04/ex05 依赖经 rsproxy 镜像；全部产物落 /tmp）；每个示例末尾给出**预期输出怎么读 / 常见坑 / 与主文档 3.x 小节的锚点**，主文档各小节已按示例编号反向引用 examples/ex0N 的实测：

| 示例 | 文件 | 主文档锚点 | 一句话 |
|------|------|-----------|--------|
| 示例 1 | `examples/ex01-toolchain-file/` | 3.4 / 3.1 | rust-toolchain.toml 目录级钉死（rustup show 观察） |
| 示例 2 | `examples/ex02-edition-diff.sh` | 3.3 / 第 4 章 | 同一代码 × 四 edition 的编译矩阵 |
| 示例 3 | `examples/ex03-cargo-fix-migration.sh` | 3.3 | 2015→2024 逐档迁移与人机分工 |
| 示例 4 | `examples/ex04-msrv-check.sh` | 3.6 / 第 4 章 | resolver v3 的 MSRV 过滤 + 依赖 MSRV 提取 |
| 示例 5 | `examples/ex05-cargo-lock.sh` | 3.5 / 第 4 章 | 锁文件全生命周期（提交/升级/回退/守门） |

### 示例 1：rust-toolchain.toml 实战（ex01-toolchain-file/）

```toml
# examples/ex01-toolchain-file/rust-toolchain.toml —— 目录级工具链钉死
# 验证：cd examples/ex01-toolchain-file && rustup show
[toolchain]
channel = "stable"
components = ["rustfmt", "clippy"]
```

实测：`rustup show` 显示 `active because: overridden by '<...>/rust-toolchain.toml'`；`rustc --edition 2021 -D warnings hello.rs -o /tmp/ph16-ex01-hello && /tmp/ph16-ex01-hello` 输出 `hello from the toolchain pinned by rust-toolchain.toml` / `1 + 1 = 2`。

**预期输出怎么读**：`rustup show` 的 active toolchain 一节是三行结构——`name:` 行给出最终选中的工具链（`stable-aarch64-apple-darwin`），`active because:` 行给出**为什么选中它**；看到 `overridden by '<...>/rust-toolchain.toml'` 就说明文件已生效，这正是 3.4 优先级表里「目录级覆盖」档的现场证据。hello 的两行输出本身不是重点，重点在**这次编译走的是文件钉住的工具链**——想交叉验证就 `rustup which rustc`，看它解析到的真实二进制路径（3.1 的读操作）。
**常见坑**：
- ① 文件对**进入该目录的所有人**生效，放 examples/ 子目录会改变该子树里一切 cargo 调用的工具链（本仓库只在示例里放一份，3.4 末尾的 ⚠️ 有详解）
- ② `channel` 写精确版本号（如 `"1.92.0"`）时，没有该工具链的机器会触发 rustup 联网下载——离线团队要么预装、要么钉已装版本
- ③ `components` 里的组件缺失时 rustup 会自动补齐（本机 stable 已含 rustfmt/clippy，自动补齐路径未实测）
**与主文档的锚点**：↔ 3.4（工具链文件字段与优先级链）、3.1（`rustup which/show` 读操作）。

### 示例 2：Edition 差异实测矩阵（ex02-edition-diff.sh）

```rust
// ex02 内嵌案例 A：a_closure_capture.rs —— disjoint closure capture（2018 → 2021 变化）
let show_host = move || println!("host = {}", cfg.host);
show_host();
println!("port = {}", cfg.port); // 2015/2018：error[E0382]；2021+：正常（只捕获 cfg.host）
```

实测矩阵（同一条 rustc 1.92.0）：闭包捕获与数组 `into_iter` 在 2015/2018 失败、2021/2024 通过；`gen` 变量名与裸 extern 块在 2015~2021 通过、2024 失败。完整错误原文与运行输出见 examples/README。

**预期输出怎么读**（按脚本输出顺序）：
- **读矩阵**：4 案例 × 4 edition 的「通过/失败」表——关键是**看失败落在哪一侧**：前两行（闭包捕获、数组 `into_iter`）在 2015/2018 失败 → 是 2021 修正的行为；后两行（`gen`、裸 extern）在 2024 失败 → 是 2024 收紧的语法
- **读错误原文**：每行失败案例打印首条错误——`E0382`/`E0308`、词法层保留字报错、`extern blocks must be unsafe` 各代表一个编译阶段的分流点（第 4 章）
- **读运行输出**：2021 edition 编译通过版运行打印 `host = localhost`、`port = 8080`、`10 20 30`、`42`、`3`——`port = 8080` 证明 2021 下 `move` 闭包没有整体吞掉 `cfg`（案例 A）
**常见坑**：
- ① 四类失败不在同一「位面」——`E0382`/`E0308` 是借用检查/类型错误，`expected identifier, found reserved keyword gen` 是词法层错误，`extern blocks must be unsafe` 是 AST 校验——正是第 4 章「不同检查点按 edition 分流」的活样本
- ② `rustc` 单文件编译**不传 `--edition` 默认按 2015**，少写参数会得到看似「版本不对」的结果（3.3 开头的默认值落差）
- ③ 2024 的「隐蔽差异」（RPIT 捕获、尾表达式析构）不在本示例覆盖内，想亲手验证按 3.3 差异清单表里的描述自建小文件、分别用 `--edition 2021/2024` 编译对比
**与主文档的锚点**：↔ 3.3（差异实测矩阵同源）、第 4 章（四个案例 = 四个编译阶段检查点）。

### 示例 3：cargo fix --edition 迁移演练（ex03-cargo-fix-migration.sh）

```bash
# examples/ex03-cargo-fix-migration.sh 的核心循环（2015 → 2024 逐档）
cargo fix --edition --allow-no-vcs   # 1. 自动修「新 edition 非法」的写法
sed -i '' 's/edition = "2015"/edition = "2018"/' Cargo.toml  # 2. 手工 bump（cargo fix 不改它，实测）
cargo fix --edition-idioms --allow-no-vcs                    # 3. 习语现代化
RUSTFLAGS="-D warnings" cargo build                          # 4. 零警告终验
```

实测修复清单：`try!` → `r#try!`（2015→2018）、`Box<Fn>` → `Box<dyn Fn>`（2018→2021）、`let gen` → `let r#gen`（2021→2024）；`r#try!` → `?` 手工完成。终验输出 `[log] port = 8080` / `gen = 1`。

**预期输出怎么读**：脚本每档先打 `Migrating Cargo.toml from X edition to Y` 与 `Fixed src/main.rs (N fix(es))`，随后 grep 展示改后的关键行——读点是**每档改了什么、几处**：2015→2018 是 `r#try!`（ex03 报 1 fix）、2018→2021 是补 `dyn`（裸 trait object 在 2021 是硬错误）、2021→2024 是 `r#gen`（2 fixes：绑定与使用两处标识符，`"gen"` 字符串不改——`(N fixes)` 的读法见 3.3 的实测表后说明）。每档中间的「手工步骤」= sed bump edition + 手工把 `r#try!` 换成 `?`，对应 3.3 的实测要点 1/2。终验 `RUSTFLAGS="-D warnings" cargo build` 零警告后运行输出 `[log] port = 8080` / `gen = 1`（sol-03 是另一组起点代码，终验输出 `pending 7 abs(-3) = 3`）。
**常见坑**：
- ① 演练目录不在 git 里必须加 `--allow-no-vcs`；真项目在 git 中**不要加**——cargo fix 反而要求工作区干净，用 git 状态当迁移前快照（实测要点 3）
- ② 版本号必须手工 bump，漏了就是「代码已修、edition 还是旧的」的半迁移状态（cargo fix 打印 `Migrating Cargo.toml` 但**不改写它**，实证）
- ③ 修不到没被激活的代码——`cfg` 门控或未开 feature 的代码 cargo fix 看不到（旗标家族，见 3.3）
**与主文档的锚点**：↔ 3.3（迁移实测表、`(N fixes)` 读法、为什么必须一档一档升）、3.3 末尾「宏与 edition」小节（`r#try!`/`r#gen` 的转义本质：保留字按调用方 edition 判）。

### 示例 4：MSRV 检查（ex04-msrv-check.sh）

```bash
# resolver v3 MSRV 感知对照实验（实测）
# a：edition 2024 + rust-version = "1.85" → Adding home v0.5.11 (available: v0.5.12, requires Rust 1.88)
# b：edition 2021（resolver v2）           → 直接锁 home 0.5.12
cargo metadata --format-version 1 | python3 -c '...提取每个包的 rust_version...'
# cargo-msrv 0.19.3（已装）：cargo msrv show → MSRV is Rust 1.85.0；cargo msrv list → 依赖 MSRV 表格
```

完整的依赖 MSRV 提取脚本见 [`exercises/sol-02-check-msrv.sh`](./exercises/sol-02-check-msrv.sh)（`cargo metadata` + python3 解析，并汇总「依赖要求的最高 MSRV」）。

**预期输出怎么读**：实验分三幕，一幕一个知识点——
- 第一幕（resolver 对照，最关键）：`msrv-aware`（edition 2024 + `rust-version = "1.85"`）的 `cargo generate-lockfile` 打两行：`Locking 11 packages to latest Rust 1.85 compatible versions`（解析器声明按 MSRV 过滤）+ `Adding home v0.5.11 (available: v0.5.12, requires Rust 1.88)`（**`available:` 括号是过滤动作的现场**：候选 0.5.12 被 rust-version 挡掉）；对照组 `semver-only`（edition 2021）直接 `Locking 3 packages ...`、锁到 0.5.12——读法是看「同一句 `home = "0.5"`，两种结局」
- 第二幕（依赖 MSRV 提取）：`cargo metadata` + python3 逐包打印 `rust_version`（实测 `home 0.5.11 → 1.81`、`windows-sys 0.59.0 → 1.60`、`windows-targets 0.52.6 → 1.56`；传递依赖版本随 crates.io 索引日期漂移，复测以 lock 实况为准）
- 第三幕（cargo-msrv）：`cargo msrv show` → `MSRV is Rust 1.85.0`；`cargo msrv list` → 依赖 MSRV 表格
**常见坑**：
- ① ex04 有第三方依赖，需要网络（脚本内置 rsproxy 镜像配置；海外网络删 `/tmp/ph16-cargo-home/config.toml` 即用默认 crates.io）
- ② **只声明 rust-version 不升 edition 2024，resolver 仍是 v2，看不到任何 MSRV 过滤**（3.6 对照表注）——想单测 v3 行为要么 edition 2024、要么显式 `resolver = "3"`
- ③ `cargo msrv find/verify` 需要 rustup 联网装历史工具链，本环境未验证，真实环境直接跑（README 有命令）
**与主文档的锚点**：↔ 3.6（resolver 对照表、依赖 MSRV 检查、cargo-msrv 子命令分工）、第 4 章「MSRV 与 resolver」段（过滤动作的机制）。

### 示例 5：Cargo.lock 策略演示（ex05-cargo-lock.sh）

```bash
# 应用提交锁文件、库不提交（.gitignore 差一行 Cargo.lock）；升级/回退：
cargo update -p itoa --precise 1.0.14   # 实测：Downgrading itoa v1.0.18 -> v1.0.14
cargo update -p itoa                     # 实测：Updating itoa v1.0.14 -> v1.0.18
cargo build --locked                     # 锁与清单失配时：error: the lock file ... needs to be updated
```

**预期输出怎么读**（脚本四步 = 锁文件全生命周期）：
- **第 1 步（格式）**：`cat Cargo.lock` 看两件事——头部 `# This file is automatically @generated by Cargo...` + `version = 4`（v4 锁格式，3.5 有格式版本演进表），与每个包的 name/version/source/checksum 四要素
- **第 2 步（应用 vs 库）**：对比 app 与 mylib 的 `.gitignore`——差一行 `Cargo.lock`，即「应用提交、库不提交」的落点（3.5 的策略表）
- **第 3 步（升级/回退）**：两条 update 是现场——`Downgrading itoa v1.0.18 -> v1.0.14`（`--precise` 回退）与 `Updating itoa v1.0.14 -> v1.0.18`（无参升回最新兼容版）
- **第 4 步（CI 守门）**：Cargo.toml 改成 `itoa = "=1.0.14"`（与锁里 1.0.18 失配）后 `cargo build --locked` 报 `the lock file ... needs to be updated but --locked was passed to prevent this`——守门员报错原文（3.5 的 `--locked` 行）
**常见坑**：
- ① `--locked` 只守「失配」不守「不是最新」——版本要求区间仍含锁内版本时不报错（实测 `"1.0.15"` 含 1.0.18 照常通过）
- ② 库的锁文件本地构建也会生成，别误提交——`.gitignore` 多写一行即可
- ③ `--precise` 回退到被 yank 的版本会失败（第 4 章 lock 段），但已锁定在锁文件里的旧版本仍能继续构建
**与主文档的锚点**：↔ 3.5（应用/库策略表、`--locked`/`--offline`/`--frozen`、依赖升级决策序列）、第 4 章「Cargo.lock 与确定性构建」。

## 7. 总结

### 关键要点

- **Edition 不是编译器版本**：一条 rustc 1.92 按 `--edition` 在 2015/2018/2021/2024 四套语义间切换（ex02 四案例矩阵实测）；edition 是 crate 级开关，混编安全，只升不降（复现：`bash examples/ex02-edition-diff.sh`）
- **2024 的隐蔽差异**：RPIT 生命周期全捕获与尾表达式析构顺序是 2024 里最容易被升版本打到的两项（rustc 1.92 实测对照见 3.3 差异清单表）——升 2024 前先跑 `cargo fix --edition`，留意 `impl_trait_overcaptures`/`tail_expr_drop_order` 的提示（复现：按 3.3 清单表的描述，同一小文件分别 `--edition 2021/2024` 编译对比）
- **rustup 管工具链，rust-toolchain.toml 管团队**：代理转发 + 优先级链（`+toolchain` > 环境变量 > 目录级覆盖（文件/override 就近竞争）> 默认）；目录文件 clone 即生效（`rustup show` 的 overridden by 实测）（复现：`cd examples/ex01-toolchain-file && rustup show`）
- **通道分工**：stable 生产 / beta 预验 / nightly 试新特性（feature 开关是通道差异的实质）；6 周火车模型（复现：`rustup toolchain list` + `rustup show` 看生效原因）
- **cargo fix --edition 的实证三件事**：修代码不修 Cargo.toml（版号手工 bump）、策略是转义保编译（`r#try!`/`r#gen`）而非现代化、git 干净工作区是默认前提（复现：`bash examples/ex03-cargo-fix-migration.sh`；练习版 `bash exercises/sol-03-edition-migration.sh`）
- **Cargo.lock**：应用提交、库不提交；`--locked` 守 CI；`cargo update -p <pkg> --precise <ver>` 是回退手段（均实测）（复现：`bash examples/ex05-cargo-lock.sh`）
- **MSRV**：`rust-version` 声明；resolver v3（edition 2024 默认）按 MSRV 过滤依赖版本（home 0.5.11 vs 0.5.12 实测）；检查靠 `cargo metadata` / cargo-msrv（复现：`bash examples/ex04-msrv-check.sh`）
- **宏与 edition**：展开产物逐 token 按其来源文件的 edition 判保留字——宏体按定义方、实参按调用方（rustc 1.92 实测）；`r#try!`/`r#gen` 转义是「调用方代码按调用方 edition 改写」（复现：3.3 末尾「宏与 edition」小节的两 crate 复现命令）
- **resolver 联动**：2018→2021 迁移会把默认 resolver 静默从 v1 翻到 v2（dev/build/target 依赖的 feature 隔离），构建结果可能悄悄变（复现：`cargo tree -e features` 迁移前后对照，泄漏现场见 3.6）

**关键命令速查**（每条对应当前小节，均本环境实测过；标注「需联网」的除外）：

```bash
rustup toolchain list && rustup show      # 3.1/3.4 已装链 + 当前生效原因（读操作）
rustc --edition 2021 -D warnings a.rs -o /tmp/a && /tmp/a    # 3.3 单文件按 edition 编译（不传默认 2015！）
cargo fix --edition                        # 3.3 修「新 edition 非法」代码；edition 字段仍要手工 bump
cargo update -p <pkg> --precise <ver>      # 3.5 回退到指定版本（实测 Downgrading ...）
cargo build --locked                       # 3.5 CI 守门：锁与清单失配即失败
cargo tree -e features                     # 3.6 看实际启用的 feature（迁移前后对照）
cargo metadata --format-version 1          # 3.6 依赖 rust-version 的机器可读出口（sol-02 脚本解析它）
cargo msrv show && cargo msrv list         # 3.6 本 crate 与依赖的 MSRV（cargo-msrv 0.19.3 已装实测）
bash examples/ex0{2,3,4,5}-*.sh            # §6 四个演练脚本，产物全落 /tmp、可重复跑（ex04/ex05 需联网）
```

### 阶段验收清单

- [ ] 能说明 Edition 与 toolchain 的区别（crate 级语义开关 vs 编译器二进制；ex02 矩阵能亲手复现）
- [ ] 能保持 CI 与本地工具链一致（rust-toolchain.toml + CI 矩阵引用同一 MSRV；project/ 模板可抄）
- [ ] 能为依赖升级记录版本并提供回退方案（提交锁文件 + `cargo update -p --precise` 回退实测）
- [ ] 能用 `cargo fix --edition` 完成一次 2015→2024 迁移并说清人机分工（ex03/sol-03 实测流程）
- [ ] 能检查依赖的 MSRV（cargo metadata / cargo msrv list）并解释 resolver v3 的过滤行为
- [ ] 能说清宏展开产物按哪个 edition 检查（宏体 token 按定义方、调用方实参按调用方），并能跑 3.3 末尾的两 crate 复现
- [ ] 知道 2018→2021 迁移会把默认 resolver 从 v1 翻到 v2，会用 `cargo tree -e features` 对照迁移前后 feature 激活差异

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 3 题（固定 toolchain / 检查依赖 MSRV / Edition 迁移演练）后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**团队模板仓库（team-template）**——工具链文件 + CI 四道闸 + rustfmt/clippy 约定 + MSRV 声明 + 锁文件策略 + README 依赖引入约定（roadmap 推荐项目落地；build/test/clippy/fmt/`--locked` 全部本环境实测）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[Crate 生态选择与常用库阶段](../ph17-crate-ecosystem/17-crate-ecosystem.md) — 把本阶段的 MSRV 检查（sol-02 脚本）、`cargo metadata` 元数据与锁文件 / resolver 语义正式用起来，评估「这个 crate 能不能引进来」；project/ 模板里的「依赖引入约定」登记表将在那里升级为完整的依赖评审清单。
