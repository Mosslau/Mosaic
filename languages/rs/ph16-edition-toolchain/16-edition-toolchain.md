# Rust Edition、工具链与版本管理阶段

> 面向工程可复现性方向：本阶段从 rustup 工具链管理起步，理解 Edition 如何让 Rust 「不换编译器就能换语言」，再到 rust-toolchain.toml、Cargo.lock 与 MSRV 的团队落地——最终能保证「我机器上能编」升级为「全队 + CI 任何一天都能编出同一个东西」。

## 1. 概述

Rust Edition、工具链与版本管理阶段对应 roadmap 第 16 节，目标是**能管理 Rust 版本、Edition 和项目工具链，保证团队环境一致**。具体定位是：**用 rustup 管理多条工具链（install/default/override），分清 stable/beta/nightly 三个发布通道，理解 Edition（2015/2018/2021/2024）是「crate 级的语法语义开关」而非编译器版本，用 `cargo fix --edition` 实测一次 2015→2024 的迁移，用 rust-toolchain.toml 把工具链钉进仓库，用 Cargo.lock + `rust-version`（MSRV）+ resolver v3 把「依赖选谁」也变得可复现**。本阶段承接 ph06 模块化与 Cargo 阶段（Cargo.toml/cargo build 的基础用法，那里已预告「Cargo.lock 策略 ph16 展开」）、ph15 宏与元编程阶段（「宏展开由工具链驱动」——cargo-expand 的底层 `-Zunpretty=expanded` 是 nightly 特性，edition 决定宏/路径/借用规则按哪套规则编译）；并为 ph17 Crate 生态选择与常用库阶段（选 crate 要看它的 rust-version 与维护活跃度）、ph21 Clippy、rustfmt、CI 与代码质量阶段（CI 深度设计）、ph24 安全、供应链与发布阶段（cargo audit/deny）提供版本治理的地基。

| 核心维度 | 覆盖内容 |
|----------|---------|
| rustup 工具链管理 | toolchain install/list/default、`+toolchain` 临时指定、目录级 override、组件管理（3.1） |
| 发布通道 | stable/beta/nightly 语义、6 周火车模型、nightly 特性开关（3.2） |
| Edition 机制 | 2015/2018/2021/2024 差异表与实测矩阵、cargo fix --edition 迁移全流程实测（3.3） |
| rust-toolchain.toml | 字段语义、优先级顺序、团队落地（3.4） |
| Cargo.lock 策略 | 锁文件格式 v4、应用提交 vs 库不提交、升级/回退、`--locked`（3.5） |
| MSRV | rust-version 声明、resolver v3 的 MSRV 感知（实测）、依赖 MSRV 检查（3.6） |
| 底层原理 | 同一编译器按 edition 切换语义的实现、lint 迁移机制、resolver 版本选择（4） |

这个阶段只涉及 rustup 工具链管理、发布通道、Edition 机制与迁移、rust-toolchain.toml、Cargo.lock 与 MSRV 的版本治理，**不涉及 Cargo 的基础用法（cargo new/build/test、工作区组织——属于 ph06 模块化与 Cargo 阶段）、clippy/rustfmt 的规则细节与 CI 流水线设计本身（属于 ph21 Clippy、rustfmt、CI 与代码质量阶段，本阶段只把它们当「团队约定」配置进模板）、crate 选型与依赖审计（属于 ph17 Crate 生态选择与常用库阶段与 ph24 安全、供应链与发布阶段）**。承接 [ph06 模块化与 Cargo 阶段](../ph06-cargo-module/06-cargo-module.md)：那里承诺「Cargo.lock 策略 ph16 展开」，本阶段 3.5 兑现；承接 [ph15 宏与元编程阶段](../ph15-macros-metaprogramming/15-macros-metaprogramming.md)：宏展开产物按哪个 edition 的语义检查，正是本阶段的主题。

## 2. 来源与演变

Rust 自 1.0（2015-05-15）起就承诺**稳定版永不破坏兼容**——但语言要进化，有些改进天生是破坏性语法变化（比如把 `dyn`/`async` 变成关键字、改革模块路径）。两难在 2016~2017 年的「epoch」RFC（RFC 2052）中解决：**Edition 机制**——同一个编译器携带多套表层语义，每个 crate 在自己的 `Cargo.toml` 里声明用哪套；不同 edition 的 crate 可以在同一个依赖图里混编链接。设计哲学一句话加粗：**「语言可以大步进化，生态不许分裂——Edition 是给语法变化装上开关，让老代码永远能和新代码一起编译」**。2018-12-06 Rust 1.31 发布首个新 edition「Rust 2018」。版本管理侧，rustup 1.0 发布于 2016 年（前身是社区脚本 multirust），随后成为官方安装与工具链管理器。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Rust 1.0 / Edition 2015 | 2015 | 创始 edition；`try!` 宏传播错误、裸 trait object、模块路径以 crate 根为锚 |
| rustup 1.0 | 2016 | 官方工具链管理器：多工具链并存、组件管理、目录 override |
| Rust 2018（1.31，2018-12-06） | 2018 | Edition 机制落地；模块系统改革（`crate::` 路径）、`dyn`/`async`/`try` 关键字化、NLL 借用检查器 |
| rustup 1.23 | 2020 | 新增 `rust-toolchain.toml`（TOML 格式；纯文本 rust-toolchain 文件是更早的形态，两者至今仍并存） |
| Rust 2021（1.56，2021-10-21） | 2021 | disjoint closure capture、数组 `into_iter` 按值、新 prelude（`TryInto`/`TryFrom`/`FromIterator`）、resolver v2 成默认；同版引入 `rust-version` 字段（MSRV 声明） |
| Cargo resolver v3 | 2025 | 随 2024 edition 默认启用：**MSRV 感知**的依赖解析（RFC 3537，本阶段 3.6 实测） |
| Rust 2024（1.85，2025-02-20） | 2025 | `gen` 保留关键字、`unsafe extern` 块强制、impl Trait 生命周期捕获规则收紧、尾表达式临时值作用域调整 |
| 本环境工具链 | 2025-12 | rustc/cargo 1.92.0 + rustup 1.28.2；cargo-msrv 0.19.3 经 rsproxy 安装实测 |

本文示例以 **Rust 2021 edition / rustc 1.92** 为基线（与 ph10~ph15 全仓库代码层一致：单文件示例统一 `rustc --edition 2021`；2021 是当前生态事实默认，2024 已稳定可演示差异），验证工具链 **rustc/cargo 1.92.0（stable-aarch64-apple-darwin，rustup 1.28.2 管理，2025-12-08 发布，已支持 2024 edition）**。这个阶段的机制（Edition 开关、rustup、锁文件）是 Rust 工程化里最稳定的部分——Edition 一旦发布就永久冻结，你学到的 2018/2021 语义永远不会再变。

## 3. 语法与参数

### 3.1 rustup 与工具链管理

**rustup 是「工具链管理器」而非编译器本身**：`~/.cargo/bin/rustc` 实际是一个 rustup 代理（proxy），每次调用时按「环境变量 → 目录 override → 默认工具链」的顺序决定转发给 `~/.rustup/toolchains/` 下的哪一份真实工具链。一个 rustup 可以并存任意多条工具链（stable/beta/nightly/精确版本），互不干扰。

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

> 本阶段只需要「能说出三通道的分工」与「会装会用」；**beta/nightly 的安装在本环境未验证**（沙箱禁写 `~/.rustup`，`rustup toolchain install beta` 实测被拦截）。通道语义以官方文档为准。

### 3.3 Edition 机制：2015/2018/2021/2024 与迁移

**Edition 不是编译器版本**（roadmap 必会概念第一条）：rustc 1.92.0 一条编译器就能按 2015/2018/2021/2024 四种语义编译——`rustc --edition <年>` 直接切换。Edition 是 **crate 级**的语法/语义开关：每个 crate 在自己的 Cargo.toml 里声明（`edition = "2021"`），同一依赖图里 2015 的 crate 和 2024 的 crate 可以混编。

**Edition 差异实测矩阵**（examples/ex02，rustc 1.92.0，`-D warnings`，四个案例 × 四个 edition）：

| 案例 | 2015 | 2018 | 2021 | 2024 | 差异说明 |
|------|------|------|------|------|---------|
| move 闭包字段捕获 | ✗ | ✗ | ✓ | ✓ | 2021 起 disjoint capture：闭包只捕获真正用到的字段 |
| 数组 `into_iter()` 按值 | ✗ | ✗ | ✓ | ✓ | 2015/2018 因历史怪癖按引用迭代；2021 起按值 |
| `gen` 作变量名 | ✓ | ✓ | ✓ | ✗ | 2024 起 `gen` 是保留关键字（为生成器语法预留） |
| 裸 `extern "C"` 块 | ✓ | ✓ | ✓ | ✗ | 2024 起必须写 `unsafe extern` |

失败案例的错误原文（实测摘录）：`error[E0382]: borrow of moved value: cfg`（2018 闭包整体捕获）、`error[E0308]: mismatched types — expected i32, found &{integer}`（2018 数组按引用迭代）、`error: expected identifier, found reserved keyword gen`（2024）、`error: extern blocks must be unsafe`（2024）。**同一份代码、同一条 rustc，只因 `--edition` 不同就编译成败不同**——这就是「Edition 是语义开关」最直接的证据。

**迁移演练：`cargo fix --edition`**（roadmap 学习内容「Edition 2018/2021/2024」的迁移命令；examples/ex03 全流程实测，cargo 1.92.0）。标准流程是「每升一档 edition：cargo fix → 手工 bump Cargo.toml → cargo fix --edition-idioms → 构建验证」：

```bash
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

三个实测要点（教学增量，都是「文档没明说、实证才看清」的）：

1. **`cargo fix --edition` 打印 `Migrating Cargo.toml from 2015 edition to 2018` 但不改写 Cargo.toml**——edition 字段必须手工 bump（clean 复验：新建 2021 crate 跑 `cargo fix --edition` 后 `grep edition Cargo.toml` 仍是 `"2021"`）。
2. **cargo fix 的策略是「转义保编译」而非「语义现代化」**：`try!` 变 `r#try!`、`gen` 变 `r#gen`——先让你能编，现代化（`?`、改名）留给你。
3. **真实项目不需要 `--allow-no-vcs`**：cargo fix 默认要求 git 工作区干净，用版本控制当迁移前快照——这也是「迁移前先 commit」的强制纪律。

> 迁移的逆向问题（2024 代码在 2021 编译器上跑）无解——**Edition 只能升不能降**；团队要升 edition 前先在 CI 加新 edition 的构建矩阵验证。多 edition 混编的细节见第 4 章。

### 3.4 rust-toolchain.toml：把工具链钉进仓库

`rust-toolchain.toml` 是放在仓库根（或任意目录）的**工具链声明文件**：rustup 代理在任何 cargo/rustc 调用前，从当前目录向上查找该文件，找到就按它选择工具链——**clone 即生效，不用任何人肉配置**。

```toml
# examples/ex01-toolchain-file/rust-toolchain.toml —— 已验证的最小形态
[toolchain]
channel = "stable"                    # 发布通道 / "1.92.0" 精确版本 / "nightly-2025-12-08" 日期快照
components = ["rustfmt", "clippy"]    # 缺失时 rustup 自动补齐
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

工具链选择的**优先级**（从高到低）：`+toolchain` 命令行参数 → `RUSTUP_TOOLCHAIN` 环境变量 → 目录向上查 `rust-toolchain.toml` → `rustup override` 设置 → 默认工具链。前两条已实测（`RUSTUP_TOOLCHAIN=stable rustc --version`、`rustc +stable --version`）。

> ⚠️ 两个坑：① 文件对**进入该目录的所有人**生效——钉精确版本号会让没装该版本的成员触发联网下载（本环境实测：channel 写 `"1.92.0"`/`"1.999.0"` 时 rustup 立即尝试 `syncing channel updates`，沙箱拦截写 `~/.rustup` 而失败）；离线团队要么预装、要么钉已装版本。② 它是「目录级开关」，放进 examples/ 子目录会改变该子树里一切 cargo 调用的工具链——仓库里放几份要克制。

### 3.5 Cargo.lock 策略：应用 vs 库

`Cargo.lock` 记录**依赖树每个包的精确版本与 checksum**（实测格式：头部 `# This file is automatically @generated by Cargo. It is not intended for manual editing.` + `version = 4`，每个包 `name`/`version`/`source`/`checksum` 四要素）。它回答的问题是「这次构建用的到底是依赖的哪个具体版本」——**没有它，Cargo.toml 里的 `itoa = "1"` 今天解析成 1.0.14、下个月解析成 1.0.18**。

| 维度 | 应用（bin/最终产物） | 库（lib/给别人依赖） |
|------|--------------------|---------------------|
| Cargo.lock 提交 git？ | **提交**（可复现构建的根基） | **不提交**（库的锁文件对下游无效——下游应用的锁才算数） |
| .gitignore | 只忽略 `/target` | `/target` + `Cargo.lock` |
| 依赖升级 | `cargo update` 后连锁文件一起 commit，可 review | `cargo test` 时自然解析到新版，CI 兼跑最低版本 |
| 回退手段 | `cargo update -p itoa --precise 1.0.14`（实测输出 `Downgrading itoa v1.0.18 -> v1.0.14`） | 同左，但影响仅限本地 |
| CI 守门 | `cargo build --locked`：锁文件与 Cargo.toml 失配即失败 | 一般不用 `--locked`（锁文件本就不进 git） |

实测（examples/ex05）：把 Cargo.toml 的 `itoa = "1"` 改成 `itoa = "=1.0.14"`（与锁里的 1.0.18 失配）后，`cargo build --locked` 报错 `error: the lock file ... needs to be updated but --locked was passed to prevent this`——这就是 CI 防「改了依赖忘了更锁文件」的机制。另一个反直觉点：版本要求失配才触发——改成 `itoa = "1.0.15"`（区间仍含 1.0.18）时 `--locked` 照常通过（实测）。

**锁文件对应用和库的不同意义**（roadmap 必会概念）一句话版：应用是「最终构建者」，锁文件是它的交付物；库是「被构建的零件」，它的锁文件连参考值都算不上——别让你的库把版本选择强加给下游。

### 3.6 MSRV：声明、解析与检查

**MSRV（Minimum Supported Rust Version，最低支持 Rust 版本）**是「这个 crate 至少要多新的 rustc 才能编」。声明方式：Cargo.toml 里 `rust-version = "1.85"`（cargo 1.56+ 支持）。它的两个作用：

1. **编译期护栏**：用比 rust-version 老的 rustc 编译直接报错（报错信息明确给出所需版本）；
2. **解析期参与选版本**（edition 2024 / resolver v3 起）：cargo 选依赖版本时优先选「其 rust-version 不超过你的 MSRV」的最新版。

**resolver v3 的 MSRV 感知实测**（examples/ex04，cargo 1.92.0，rsproxy）：项目 `edition = "2024"` + `rust-version = "1.85"`，依赖 `home = "0.5"`（最新版 0.5.12 要求 Rust 1.88）——

```text
# edition 2024（resolver v3）：自动选兼容版
Locking 11 packages to latest Rust 1.85 compatible versions
 Adding home v0.5.11 (available: v0.5.12, requires Rust 1.88)
# 对照组 edition 2021（resolver v2）：直接选最新，不管 MSRV
Locking 3 packages to latest compatible versions   → home 0.5.12
```

**检查依赖的 MSRV**（roadmap 练习）：依赖的 rust-version 在 `cargo metadata` 的 JSON 里（exercises/sol-02 脚本实测输出：`home 0.5.11: rust-version = 1.81`、`windows-sys 0.59.0: rust-version = 1.60`、`windows-targets 0.52.6: rust-version = 1.56`）。专用工具 **cargo-msrv**（0.19.3，本环境经 rsproxy `cargo install cargo-msrv --locked` 实测安装）：`cargo msrv show` 读本 crate 的 MSRV（实测 `MSRV is Rust 1.85.0`），`cargo msrv list` 列出全部依赖的 MSRV 表格，`cargo msrv verify` 逐版本装旧工具链实测真正的最低可编译版本（**未在本环境验证**：需 rustup 安装旧工具链，沙箱禁写 `~/.rustup`）。

> 本阶段只讲「声明 + 解析 + 检查」；**库的 MSRV 测试策略（CI 跑最低版本矩阵）在 project/ 模板里有可抄的最小形态**（`.github/workflows/ci.yml` 的 test 矩阵 `stable + 1.85.0`）。

## 4. 底层原理

**同一编译器怎么按 edition 切换语义**：rustc 内部没有「四个编译器」，而是一份代码 + 一组按 edition 门控的行为开关。Cargo 编译每个 crate 时把它的 edition 传给 rustc（`rustc --edition 2021 ...`——这就是 ex02 能直接用一条 rustc 演示四 edition 矩阵的原因）；解析器、名称解析、借用检查里按 `span.edition()` 分流：比如 `gen` 在 2024 的语法上下文里被词法成保留关键字、在 2021 里仍是普通标识符；闭包捕获分析在 2021+ 走 disjoint capture 路径。ABI 与 crate 间接口与 edition 无关——所以混编安全：**edition 只改「源码怎么被理解」，不改「产物怎么被链接」**。

```text
crate A (edition 2015) ──┐
crate B (edition 2021) ──┼── cargo 逐个传 --edition ──▶ 同一条 rustc ──▶ 各自语义开关 ──▶ 统一链接
crate C (edition 2024) ──┘
```

**迁移为什么不破坏生态（lint 迁移机制）**：每个「新 edition 非法」的旧写法，先在所有 edition 上变成带 machine-applicable suggestion 的 warning（如 `bare_trait_objects`），只有在新 edition 的语法上下文里才升级为硬错误。`cargo fix --edition` 做的事就是：**用当前 edition 编译，收集这些「在新 edition 会变成错误」的 warning，批量应用编译器给出的机械修复**——所以它能修的都是编译器知道怎么修的（转义关键字、加 `dyn`），修不了语义层（`r#try!` → `?` 是「用现代写法重写」，不是「保编译」）。这也解释了 ex03 的实测：cargo fix 的修复清单永远「保守但安全」。

**MSRV 与 resolver**：resolver（依赖解析器）输入是版本要求（`itoa = "1"` → 区间 `[1.0.0, 2.0.0)`），输出是锁文件里的精确版本。v1/v2 只看 semver 区间取最新；**v3（edition 2024 默认，`resolver = "3"`）额外看每个候选版本的 `rust-version` 元数据，过滤掉「需要比你声明的 MSRV 更新的 rustc」的版本**——ex04 里 `Adding home v0.5.11 (available: v0.5.12, requires Rust 1.88)` 那行日志就是过滤动作的现场。索引侧的支撑：sparse 索引（`sparse+https://...`）里每个版本带 `rust_version` 字段，rsproxy 镜像原样转发，`cargo metadata` 再把它暴露给检查工具（sol-02 的提取路径）。

**Cargo.lock 与确定性构建**：锁文件是「解析结果的序列化」——cargo 先查锁，锁里的版本仍满足 Cargo.toml 区间就直接用（不再问索引），所以全队 + CI 解析结果逐位一致；`--locked` 把「锁可能过期」从静默修复变成硬错误。锁格式本身也版本化（`version = 4`，v4 自 2024 年随新 cargo 默认生成），老 cargo 读新锁可能拒绝——**锁格式版本也是工具链一致性的一部分**。

## 5. 使用场景

- **团队/开源项目统一环境**：rust-toolchain.toml + Cargo.lock + CI `--locked` 三件套（project/ 模板即落地形态）。什么时候**不**用 rust-toolchain.toml：一次性脚本、给别人的教学片段（读者工具链各异，钉死反而添堵）。
- **升 edition 的时机**：项目惰性/新特性驱动均可，但要走完整迁移流程（fix → bump → idioms → 零警告构建 → CI 矩阵）；升之前确认全部依赖与 MSRV 承诺兼容。**库crate 升 edition 是 breaking change 级决策**（下游老 rustc 用户编不了），慎升。
- **MSRV 承诺**：库作者声明 `rust-version` 并在 CI 跑最低版本矩阵（project/ 模板的 `stable + 1.85.0`）；应用开发者对 MSRV 无承诺义务，但声明它能让 resolver v3 帮你挡掉「装了编不了的依赖」。
- **nightly 的正当用途**：试用未稳定特性、跑 miri/cargo-expand 类工具链内部工具；生产代码钉 stable。ph15 的 cargo expand 观察宏展开就是「借 nightly 机制做学习观察」的典型。
- **跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：C/C++ 没有「语言版本开关」概念，`-std=c++17` 只选标准档、老编译器不能编新代码，生态靠「各家编译器实现同一标准」对齐；Go 用「go.mod 的 go 指令 +  toolchain 指令」做类似的事（Go 1.21+ 工具链自动下载管理，与 rustup 思路趋同）；Java 的 `--release` 是单编译器多目标的语言层开关，但没有 crate 级混编。Rust 的 Edition 是「同一工具链、多套语义、包级粒度、永久冻结」四要素的独特组合——语言进化的兼容性难题，Rust 的解法是把变化做成显式开关而不是版本分裂。

## 6. 代码示例

本节展示完整示例的关键片段，完整文件在 `examples/` 目录（验证环境 rustc/cargo 1.92.0 macOS arm64 + rustup 1.28.2；ex04/ex05 依赖经 rsproxy 镜像；全部产物落 /tmp）：

### 示例 1：rust-toolchain.toml 实战（ex01-toolchain-file/）

```toml
# examples/ex01-toolchain-file/rust-toolchain.toml —— 目录级工具链钉死
# 验证：cd examples/ex01-toolchain-file && rustup show
[toolchain]
channel = "stable"
components = ["rustfmt", "clippy"]
```

实测：`rustup show` 显示 `active because: overridden by '<...>/rust-toolchain.toml'`；`rustc --edition 2021 -D warnings hello.rs -o /tmp/ph16-ex01-hello && /tmp/ph16-ex01-hello` 输出 `hello from the toolchain pinned by rust-toolchain.toml` / `1 + 1 = 2`。

### 示例 2：Edition 差异实测矩阵（ex02-edition-diff.sh）

```rust
// ex02 内嵌案例 A：a_closure_capture.rs —— disjoint closure capture（2018 → 2021 变化）
let show_host = move || println!("host = {}", cfg.host);
show_host();
println!("port = {}", cfg.port); // 2015/2018：error[E0382]；2021+：正常（只捕获 cfg.host）
```

实测矩阵（同一条 rustc 1.92.0）：闭包捕获与数组 `into_iter` 在 2015/2018 失败、2021/2024 通过；`gen` 变量名与裸 extern 块在 2015~2021 通过、2024 失败。完整错误原文与运行输出见 examples/README。

### 示例 3：cargo fix --edition 迁移演练（ex03-cargo-fix-migration.sh）

```bash
# examples/ex03-cargo-fix-migration.sh 的核心循环（2015 → 2024 逐档）
cargo fix --edition --allow-no-vcs   # 1. 自动修「新 edition 非法」的写法
sed -i '' 's/edition = "2015"/edition = "2018"/' Cargo.toml  # 2. 手工 bump（cargo fix 不改它，实测）
cargo fix --edition-idioms --allow-no-vcs                    # 3. 习语现代化
RUSTFLAGS="-D warnings" cargo build                          # 4. 零警告终验
```

实测修复清单：`try!` → `r#try!`（2015→2018）、`Box<Fn>` → `Box<dyn Fn>`（2018→2021）、`let gen` → `let r#gen`（2021→2024）；`r#try!` → `?` 手工完成。终验输出 `[log] port = 8080` / `gen = 1`。

### 示例 4：MSRV 检查（ex04-msrv-check.sh）

```bash
# resolver v3 MSRV 感知对照实验（实测）
# a：edition 2024 + rust-version = "1.85" → Adding home v0.5.11 (available: v0.5.12, requires Rust 1.88)
# b：edition 2021（resolver v2）           → 直接锁 home 0.5.12
cargo metadata --format-version 1 | python3 -c '...提取每个包的 rust_version...'
# cargo-msrv 0.19.3（已装）：cargo msrv show → MSRV is Rust 1.85.0；cargo msrv list → 依赖 MSRV 表格
```

### 示例 5：Cargo.lock 策略演示（ex05-cargo-lock.sh）

```bash
# 应用提交锁文件、库不提交（.gitignore 差一行 Cargo.lock）；升级/回退：
cargo update -p itoa --precise 1.0.14   # 实测：Downgrading itoa v1.0.18 -> v1.0.14
cargo update -p itoa                     # 实测：Updating itoa v1.0.14 -> v1.0.18
cargo build --locked                     # 锁与清单失配时：error: the lock file ... needs to be updated
```

## 7. 总结

### 关键要点

- **Edition 不是编译器版本**：一条 rustc 1.92 按 `--edition` 在 2015/2018/2021/2024 四套语义间切换（ex02 四案例矩阵实测）；edition 是 crate 级开关，混编安全，只升不降
- **rustup 管工具链，rust-toolchain.toml 管团队**：代理转发 + 优先级链（`+toolchain` > 环境变量 > 目录文件 > override > 默认）；目录文件 clone 即生效（`rustup show` 的 overridden by 实测）
- **通道分工**：stable 生产 / beta 预验 / nightly 试新特性（feature 开关是通道差异的实质）；6 周火车模型
- **cargo fix --edition 的实证三件事**：修代码不修 Cargo.toml（版号手工 bump）、策略是转义保编译（`r#try!`/`r#gen`）而非现代化、git 干净工作区是默认前提
- **Cargo.lock**：应用提交、库不提交；`--locked` 守 CI；`cargo update -p <pkg> --precise <ver>` 是回退手段（均实测）
- **MSRV**：`rust-version` 声明；resolver v3（edition 2024 默认）按 MSRV 过滤依赖版本（home 0.5.11 vs 0.5.12 实测）；检查靠 `cargo metadata` / cargo-msrv

### 阶段验收清单

- [ ] 能说明 Edition 与 toolchain 的区别（crate 级语义开关 vs 编译器二进制；ex02 矩阵能亲手复现）
- [ ] 能保持 CI 与本地工具链一致（rust-toolchain.toml + CI 矩阵引用同一 MSRV；project/ 模板可抄）
- [ ] 能为依赖升级记录版本并提供回退方案（提交锁文件 + `cargo update -p --precise` 回退实测）
- [ ] 能用 `cargo fix --edition` 完成一次 2015→2024 迁移并说清人机分工（ex03/sol-03 实测流程）
- [ ] 能检查依赖的 MSRV（cargo metadata / cargo msrv list）并解释 resolver v3 的过滤行为

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 3 题（固定 toolchain / 检查依赖 MSRV / Edition 迁移演练）后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**团队模板仓库（team-template）**——工具链文件 + CI 四道闸 + rustfmt/clippy 约定 + MSRV 声明 + 锁文件策略 + README 依赖引入约定（roadmap 推荐项目落地；build/test/clippy/fmt/`--locked` 全部本环境实测）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

**ph17+（roadmap 第 17 节，目录待建）**：Crate 生态选择与常用库阶段——本阶段的 MSRV 检查（sol-02 脚本）、`cargo metadata` 元数据、锁文件与 resolver 语义，正是评估「这个 crate 能不能引进来」的工具底座；project/ 模板里的「依赖引入约定」登记表（用途/维护活跃度/MSRV 影响）就是下一阶段评审清单的最小原型。在此之前可先按推荐学习顺序巩固本阶段的迁移演练与模板项目。
