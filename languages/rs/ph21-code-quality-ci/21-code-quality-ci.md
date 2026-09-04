# Rust Clippy、rustfmt、CI 与代码质量阶段

> 面向「让代码风格与质量可自动化交付」的方向：本阶段把 ph06 起就挂在嘴边的质量门禁三连（fmt / clippy / test）从「我记起来了就敲一遍」升级为「不绿就进不了主干」——先吃透 `cargo fmt` 与 `cargo clippy` 的语法、参数和 lint 等级体系，再把它们编排进 GitHub Actions 的 workflow、矩阵与缓存，最后收敛成一份可复用的 Rust CI 模板，兑现 ph20 主文档「### 下一阶段」留给本阶段的预告：把 ph20 手敲的每条质量命令变成每次 PR 自动执行的关卡。

## 1. 概述

本阶段对应 roadmap 第 21 节，目标是**用工具链自动化保持代码风格、质量和可交付性**。它在学习路线里是一道「分水岭」：前 20 个阶段都在教「怎么写对」，从本阶段起把「怎么保证一直写对」变成可执行的门禁。ph06 已经把 `cargo build/test/fmt/clippy` 作为日常肌肉记忆带过，ph20 刚刚把「单元/集成/属性/基准」的测试体系搭完整——本阶段**不重复入门**，只做三件增量：**把 fmt/clippy 的命令讲透**（配置、参数、与 rustc lint 的关系）、**把 lint 的等级体系讲清**（哪些 lint 默认开、哪些要显式开、例外怎么管理才不失控）、**把质量门禁工程化**（CI workflow、toolchain×OS 矩阵、缓存命中、本地检查脚本与 PR 流程）。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 自动格式化 | `cargo fmt` 与 rustfmt 的关系、`--check` 的门禁语义、rustfmt.toml 配置（max_width/edition/tab_spaces，本机实测生效）、fmt 覆盖范围与边界（3.1） |
| 静态检查 | `cargo clippy` 是什么（rustc 之上加 lint passes）、与 rustc lint 的关系、`-A/-W/-D` 级别、`--all-targets`/`--no-deps`/`--fix`（3.2） |
| clippy lint 等级体系 | correctness/suspicious/style/complexity/perf/cargo 默认组 + pedantic/nursery/restriction 三档 opt-in 组；级别表与代表 lint 全列、何时开与何时不开（3.3） |
| lint 例外纪律 | `#[allow]`/`#[expect]` 带理由注释、作用域最小化、Cargo.toml `[lints]` 集中管理、clippy.toml 阈值（3.4） |
| GitHub Actions | workflow 心智模型（触发器→job→step→action）、质量门禁 job 骨架、失败定位（3.5） |
| 矩阵与缓存 | toolchain × OS 矩阵、`actions/cache` 与 Swatinem/rust-cache、缓存命中/失效原理、可复现构建（`Cargo.lock` 提交 + `--locked`）（3.6） |
| 本地脚本与流程 | `scripts/check.sh`、pre-commit/git hook、质量门禁与 PR 合并流程（3.7/3.8） |
| 底层原理 | clippy 在编译管线上的 lint pass（HIR/MIR 视角）、rustfmt 的解析-打印两段式、CI 缓存命中机制（4） |
| 场景与练习 | 何时开 pedantic/restriction + Go/Java/Python 跨语言对照；examples/exercises/project 四层配套（5~7） |

这个阶段只涉及 **fmt/clippy 工具链用法、lint 等级管理与 CI 编排本身**，**不涉及系统化性能剖析方法论**（clippy 的 `perf` 组本阶段只当「默认开的 lint 组」使用，讲到「热路径要不要按 perf 建议改」时点到为止——profiling/flamegraph、`[profile]` 调优、分配剖析与缓存局部性测量属 [ph22 性能优化与 Profiling 阶段](../ph22-perf-profiling/22-perf-profiling.md)）、**供应链安全与发布流水线**（依赖漏洞审计 `cargo audit`/`cargo deny`、许可证检查、secret 管理与制品签名——本阶段 CI 模板只留「预留注释位」，这些属 ph24 安全、供应链与发布阶段，roadmap 第 24 节，目录待建）、**FFI 与跨语言接口**（本阶段的可复现构建对 ph23 的 cdylib 同样适用，但 ABI/所有权跨边界不涉及，属 ph23 阶段，roadmap 第 23 节，目录待建）和 **Rust 数据基础设施组件本身**（本阶段 CI 模板会被 ph25 的 KV/LSM 项目直接拿去用，但 WAL/MemTable/SSTable 属 ph25 阶段，roadmap 第 25 节，目录待建）。同时与三条相邻知识划清边界：**工具链与版本管理**（rustup、rust-toolchain.toml、Cargo.lock 格式、MSRV 的字段语义属 ph16 阶段，本阶段直接「使用」它们——在 CI 里钉工具链、用 `--locked`——但不重讲字段含义）；**入门级 fmt/clippy 命令**（ph06 已带过，本阶段直接用、不重复）; **测试怎么写**（ph20 刚讲完，本阶段只把 `cargo test` 请进门禁，不动测试内容）。

## 2. 来源与演变

Rust 的质量工具链不是「官方先规划好再实现」的，而是**社区项目先做出价值、再被官方收编进发布列车**的典型路径。rustfmt 由 Nick Cameron（nrc，rust-analyzer 早期贡献者之一）约 2014 年发起，目标是终结 Rust 圈「格式化风格争吵」；clippy 由 Manish Goregaokar 等人约 2015 年发起，目标是把「常见 Rust 坏味道」从 review 意见变成自动报告。两者先后并入 rust-lang 官方组织，并借着 rustup 的 component 机制进入标准发布——从此 `clippy`/`rustfmt` 与 `rustc` **同版本号、同步发版**，这对本阶段的一切都至关重要：**CI 里 `rustc` 是什么版本，clippy 就是什么版本，不存在「工具链漂移」**。对比 Java 的 checkstyle 与编译器的完全独立版本，这是 Rust 独有的收编模式。**设计哲学一句话加粗：代码质量不靠「规范劝导」而靠「门禁自动化」——把「我记得要格式化/lint」改写成「提交过不了门禁就不存在」，质量就从个人习惯变成系统约束。**

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Rust 1.0 | 2015-06 | rustc 内置 lint 体系（allow/warn/deny/forbid 四级 + `#[allow]` 等属性）；测试/编译期检查成为语言一等公民 |
| rustfmt / clippy 项目启动 | 2014~2015 | rustfmt（nrc）、clippy（Manish Goregaokar 等）作为独立社区项目出现 |
| 官方收编与 rustup component | 2016~2017 前后 | 两者进入 rust-lang 组织并随 rustup 组件分发，`rustup component add clippy rustfmt` 即成日常；「官方组件 + 同版同步」模式确立 |
| 现代 CI 实践成形 | 2017~2020 | Travis/AppVeyor 时代「fmt + clippy + test」三连脚本是社区模板；GitHub Actions 2019-11 GA，`checkout`/`setup-toolchain` 等 action 生态把 CI 声明成仓库内 YAML |
| 矩阵与缓存行动化 | 2021~2022 前后 | `strategy.matrix` 普及；Swatinem/rust-cache 类 action 让「cargo registry + target 缓存」成为 Rust CI 标配（key 绑 rustc 版本与 Cargo.lock） |
| Cargo `[lints]` 表 | 2023-11（Rust 1.74） | 在 Cargo.toml 里集中声明 rustc/clippy lint 级别，`[workspace.lints]` 让 workspace 全成员共享一份策略 |
| `#[expect]` 稳定 | 2024-09（Rust 1.81） | 「预期该 lint 触发」的契约属性：触发则静默、未触发反而警告（本阶段 3.4 实测） |
| clippy lint 大规模重组 | 2025（1.8x 起） | 一批 lint 从 perf/complexity/nursery 归入 style 等组，默认开/关也随之变化——**分组以本机 clippy 0.1.92 实测为准**（3.3 表注） |
| 本环境工具链 | 2025-12 | rustc/cargo/clippy 1.92.0（clippy 0.1.92）、rustfmt 1.8.0（macOS arm64，rustup 管理，本机实测） |

一个值得记住的历史结论：**Rust 把「格式化」和「lint」做成了官方组件，而不是留给第三方插件生态**。这直接造成两个结果：① 团队没有「选哪套规范」的自由，也就没有「规范之争」的成本——`rustfmt` 的输出就是唯一的默认答案；② 与编译器同版同步意味着**新 lint 会随工具链悄悄进来**，昨天绿的门禁今天可能红——这不是 bug，是门禁在提醒你「工具升级了，代码该跟上」。因此 ph16 教的 rust-toolchain.toml 钉版本、团队约定工具链升级节奏，在本阶段成为门禁稳定性的前置条件。

本文示例以 **rustc/cargo/clippy 1.92.0 与 rustfmt 1.8.0（edition 2021）** 为基线（仓库代码层全部用 edition 2021，与 ph20 一致；clippy 分组行为、默认开/关、`#[expect]` 语义全部在本机实测）。验证工具链 **rustc/cargo/clippy 1.92.0、rustfmt 1.8.0（macOS arm64，rustup 管理）**。**代码验证状态**：examples 的 ex01~ex03/ex06 与 exercises 的 sol-*、project 的 ci-template 均在 cargo 1.92.0 本机实测（`cargo fmt --check` / `cargo clippy --all-targets -- -D warnings` / `cargo test` 全绿或按示例设计红/绿两种状态均实测），标注「已验证」；ex04/ex05 及 project 的 `.github/workflows/*.yml` 属于 GitHub Actions 远端编排，**未在本环境实际运行验证**（本机无 runner），但 YAML 均用 Ruby psych 做过静态语法解析、并按官方 action 用法逐字段人工核对。构建产物统一落 `/tmp`（`CARGO_TARGET_DIR`），仓库零二进制残留。这个阶段的语法是 Rust 工具链里**最「机械」的部分**：没有运行时语义，全部是「规则 + 退出码」——也因此最适合自动化，学习重点是记规则、而不是理解内存模型。

## 3. 语法与参数

本章按「格式化 → 静态检查 → lint 等级 → 例外管理 → CI → 矩阵与缓存 → 本地脚本 → 门禁流程」推进，对应 roadmap 第 21 节学习内容的五块（cargo fmt / cargo clippy / clippy lint 等级 / GitHub Actions 或其他 CI / 缓存与矩阵构建）并补上 lint 例外纪律与门禁流程两块工程增量。全部命令的完整工程形态见 [`examples/`](./examples/)，练习见 [`exercises/`](./exercises/)，综合模板见 [`project/`](./project/)。

### 3.1 自动格式化：cargo fmt 与 rustfmt

**`cargo fmt` 是 rustfmt 的 cargo 前端**：rustfmt 是独立于 cargo 的格式化程序（也可 `rustfmt 文件.rs` 单文件跑），`cargo fmt` 负责「找出当前包该格式化的所有 .rs 文件并交给 rustfmt」。它处理当前 package 的 `src/`、`tests/`、`benches/`、`examples/` 目录下全部 Rust 源文件——**只处理这些标准源目录**。本机实测：在 crate 里另放一个 `before/` 目录，`cargo fmt` 完全不动它（`before/` 里的文件保持原样），这正是本阶段「治理前/后双版本并存于同一目录」教学手法的机制基础。

```bash
# 验证命令（cargo 1.92.0 / rustfmt 1.8.0 本机实测，退出码见行尾注释）
cargo fmt                     # 直接改写所有源文件为标准格式
cargo fmt --check             # 只检查不写回：有差异则打印 diff 并退出 1（实测 exit=1）
cargo fmt --check; echo $?    # 已格式化时干净退出（实测 exit=0）
cargo fmt -- --emit stdout    # 把格式化结果打到 stdout，不落盘（调试用）
```

`--check` 是门禁语义的关键：它把「这段代码需不需要格式化」变成一个**可判定的布尔断言**——CI 里 `cargo fmt --check` 红 = 「有文件没格式化」，与测试失败同样不可含糊。实测输出是标准 unified diff（节选自 ex01 治理前文件的真实 fmt 输出，本机验证）：

```text
Diff in src/main.rs:1:
 fn main() {
-let items = vec!["rustfmt", "clippy", "cargo"];
-println!("tools:");
-for item in items {
-println!("- {}", item);
+    let items = vec!["rustfmt", "clippy", "cargo"];
+    println!("tools:");
+    for item in items {
+        println!("- {}", item);
+    }
 }
```

**rustfmt 格式化的是「布局」，不是「内容」**：它重排空格、换行、缩进与可断行位置，但不改语义、不改字符串字面量内容、不删代码。两个教学上重要的边界：**① 格式化不了「没被解析为合法语法树的内容」**——`macro_rules!` 的匹配体、字符串内部等会按 token 级保守处理，别指望 rustfmt 替你整理宏内部排版；**② fmt 通过不代表代码对**——格式化后的代码依然可以充满逻辑 bug，它只保证「长成一个样子」，正确性由 clippy/test 负责（这解释了为什么门禁三连的顺序是 fmt → clippy → test：fmt 最便宜且先行消除「格式噪音」，让 clippy 与 test 的输出集中在真问题上）。

| rustfmt.toml 常用键 | 默认值 | 说明（本机实测） |
|------|------|------|
| `max_width` | 100 | 最大行宽，超出即尝试断行；`max_width = 48` 实测立即生效（见 ex01） |
| `edition` | 从 Cargo.toml 读 | 按 edition 决定个别排版规则；与 Cargo.toml 不一致时 rustfmt.toml 优先 |
| `tab_spaces` | 4 | 缩进宽度（空格数） |
| `use_small_heuristics` | Default | 控制 fn 调用/结构体等是否按小启发式紧凑换行 |
| `newline_style` | 随平台 | 团队跨平台建议显式设 `Unix`，否则 Windows 上会刷出整文件 diff |

配置文件叫 `rustfmt.toml`（或 `.rustfmt.toml`），放在 crate 目录或 workspace 根，rustfmt 从当前文件向上逐级查找。**工程纪律：能用默认就别配**——rustfmt 的价值一半在「零配置即统一」；配置越多，团队要记的例外越多。真正值得配的只有少数几项（行宽、缩进、edition），以及少量 **nightly-only 的不稳定选项**（需要 `-Z`，CI 里用 stable 就编不过，模板一律不碰）。

**多包与 workspace 的格式化**：`cargo fmt` 默认只格式化当前 package；在 workspace 根跑 `cargo fmt --all`（或用 `--package 名` 指定某个成员）才覆盖全部成员。`--all` 与 `--check` 都是 cargo-fmt 自带的参数（`cargo fmt --help` 实测列出），所以 workspace 门禁的命令形态是：

```bash
# workspace 根的格式化门禁（project/ci-template 的 workspace 即按此形态）
cargo fmt --all --check         # 全部成员 + 只检查不写回
```

`--` 之后的位置留给透传给 rustfmt 的参数（如 `cargo fmt -- --emit stdout` 把格式化结果打到 stdout）。rustfmt 也可以单文件检查：`rustfmt --check src/main.rs`（实测未格式化时退出 1），适合「只检查改动的文件」这类脚本场景，但门禁请一律用 `cargo fmt --check`/`--all --check`——它保证检查集合与 cargo 认识的目标一致。

### 3.2 静态检查：cargo clippy 与 lint 级别

`cargo clippy` 本质是**在 rustc 编译管线上多挂了一批 lint pass 的 clippy-driver 前端**：除了 rustc 自带 lint（`unused_variables`、`unused_must_use`、`nonstandard_style` 等），clippy 额外提供数百个以 `clippy::` 前缀命名的 lint，覆盖风格（style）、复杂度（complexity）、性能（perf）、可疑正确性（suspicious/correctness）等。命令行参数格式与 rustc lint 完全同构，因为底层就是同一套 lint 基础设施（4.1 展开）：

| 参数 | 含义 | 本机实测行为 |
|------|------|-------------|
| `cargo clippy` | 跑默认开启的全部 clippy lint | 纯 warning 时编译成功、退出码 0 |
| `cargo clippy -- -D warnings` | 把所有 warning 升级为 error | 有任何 warning 即失败，退出码非零（实测 101） |
| `cargo clippy -- -W clippy::pedantic` | 显式把某组/某 lint 升为 warn | pedantic 组默认 allow，不加 `-W` 不报（实测） |
| `cargo clippy -- -A clippy::style` | 关闭整组 lint | 组内 lint 静默（实测，分组归属的验证手法） |
| `cargo clippy --all-targets` | 连 tests/benches/examples 一起查 | 否则测试代码里的坏味道能逃过门禁 |
| `cargo clippy --no-deps` | 只查本 crate，不查依赖 | 门禁标配：依赖质量问题留给 ph24，别让第三方 lint 挡你的门 |
| `cargo clippy --fix` | 自动应用机器可改的修复 | 实测把手写 `match { Some..None }` 改成 `o.map(...)`；在 git 仓库内直接跑，非 VCS 目录需加 `--allow-no-vcs` |
| `cargo clippy -- -A warnings` | 一次性静默（反模式，仅临时调试） | —— |

为什么 `-D warnings` 是门禁标配而 `cargo clippy` 裸跑不是：裸跑时 warning 只是「提示」，编译器照样成功退出——CI 里一个「有 warning 但绿」的 job 等于没设门禁。`-D warnings` 把「有 lint 就失败」变成硬约束。注意 **rustc 自带的 `warnings` lint 分组与 clippy lint 在 `-D warnings` 下都被覆盖**（本机实测：clippy warning 在 `-D warnings` 下同样让构建失败），所以这一条命令同时守住了 rustc 与 clippy 两拨 lint。

```bash
# 质量门禁三连的完整形态（ex02/ex06/project 均按此实测）
# 1. 格式化断言
cargo fmt --check
# 2. 静态检查：全目标 + 零告警
cargo clippy --all-targets -- -D warnings
# 3. 测试
cargo test
```

**`--all-targets` 为什么不能省**：ph20 的测试代码同样会被 clippy 检查，而测试里最常见的 `let _ =`、`.expect()` 模式在默认组下就有 lint。如果只跑 `cargo clippy`（默认只查 lib/bin target），tests/ 里的坏味道在本地全绿、在 CI 的 `cargo test` 编译时才暴露——门禁应该在最便宜的阶段抓问题，所以三连里 clippy 用 `--all-targets` 一次扫全。

退出码是本阶段要背的最小事实表（全部本机实测：cargo 约定编译失败返回 101，脚本只关心「是否非零」）：

| 命令 | 干净时 | 有 lint/差异时 | 说明 |
|------|--------|---------------|------|
| `cargo fmt --check` | 0 | 1 | diff 即差异；写回式 `cargo fmt` 不报错 |
| `cargo clippy`（仅 warning） | 0 | 0 | **裸跑不拦 warning，这正是要 `-D` 的原因** |
| `cargo clippy`（correctness deny / `-D warnings`） | 0 | 非零（实测 101） | deny 级即使没有 `-D` 也直接 error |
| `cargo test` | 0 | 非零 | 测试失败同样是非零退出 |
| `rustfmt --check 单文件` | 0 | 1 | 与 cargo-fmt 行为一致 |

排查复杂 lint 组合时，`--message-format=short` 能把输出压成 `文件:行:列: 级别: 消息` 一行一条，方便 grep/sort 对比（本阶段实验大量使用；JSON 格式 `--message-format=json` 则带结构化字段，含 lint 全名，供脚本消费）。

### 3.3 clippy lint 等级体系

「clippy lint 等级」在本阶段拆成两层理解：**级别（level）**——`allow/warn/deny/forbid` 四个处理档；**分组（group）**——lint 按主题聚成的集合，每组带一个默认级别。日常说的「clippy 太吵」「pedantic 要不要开」其实都在讨论分组与默认级别。分组分三类：

| 组 | 默认级别 | 定位 | 代表 lint（clippy 0.1.92 本机实测触发并核对组归属） |
|------|------|------|------|
| `correctness` | **deny** | 几乎肯定是 bug 的模式，裸跑就当 error 拦 | `eq_op`（`x == x` 自我比较）、越界/位运算类 |
| `suspicious` | warn | 值得怀疑、多半有问题的模式 | 可疑转换/重复分支类 |
| `style` | warn | 风格化写法（不优雅但能跑） | `collapsible_if`（可合并的嵌套 if）、`manual_map`、`needless_range_loop`、`ptr_arg`（`&Vec<T>` 参数） |
| `complexity` | warn | 写复杂了，通常有更简单等价写法 | `too_many_arguments`（实测 8 参触发，默认阈值 >7） |
| `perf` | warn | 写法低效，但语义不变 | `manual_memcpy`（手写循环拷切片）、`useless_vec` |
| `pedantic` | allow | 更严格、更「教条」的风格审查，噪声大 | `unnecessary_wraps`（无必要包一层 `Result`） |
| `nursery` | allow | 试验性新 lint，可能误报、可能变动 | `missing_const_for_fn`（本可 const 的纯函数） |
| `restriction` | allow | 反模式专用的「禁令」lint，**不适合整组开** | `unwrap_used`、`implicit_return`、`arithmetic_side_effects`、`indexing_slicing`、`print_stdout` |
| `cargo` | allow | 检查 Cargo.toml/manifest 本身 | 依赖项版本/命名/feature 类问题 |

三个默认 warn 组（style/complexity/perf）加上 suspicious，共同构成 `cargo clippy` 裸跑时会报的「默认噪音」；`correctness` 单独是 deny——这意味着**裸跑 `cargo clippy` 也可能直接编译失败**。本机实测（完整输出见 ex02 与 3.2 前的治理示例）：

```text
error: equal expressions as operands to `==`            ← correctness 组：直接 deny
  --> src/main.rs:17:28
   = note: `#[deny(clippy::eq_op)]` on by default
warning: this function has too many arguments (8/7)      ← complexity 组：warn
warning: the loop variable `i` is only used to index `v` ← style 组：warn
warning: it looks like you're manually copying between slices  ← perf 组：warn
```

三个 opt-in 组的定位差异是本阶段的重点教学增量：

- **pedantic**：适合「库作者想对 API 文档、错误处理吹毛求疵」的场景，开启方式是 `-W clippy::pedantic`。它的代价是大量「可以但不必要」的建议——全开会把 `-D warnings` 门禁变成「修不完的 TODO 清单」，所以实践中 pedantic 往往**开组 + 逐条 allow 你认为不合理的**（3.4），或干脆不开、只在单独 job 里出报告。
- **nursery**：新 lint 的试运行区，随时可能调整或移除（本机实测 `missing_const_for_fn` 就位于此组）。它**不应该进 `-D warnings` 门禁**——今天绿明天红的原因可能只是 lint 从 nursery 毕业/退回，噪音大于价值。
- **restriction**：与上面完全不同——它**明确禁止整组开启**。实测：`-W clippy::restriction` 一开，clippy 立刻报 `blanket_clippy_restriction_lints`：`clippy::restriction` 不是用来整组启用的。restriction 的正确用法是**按团队纪律逐条开**：例如「生产代码禁 `.unwrap()`」→ 只加 `-W clippy::unwrap_used`；「解析层禁裸下标」→ `-W clippy::indexing_slicing`。它把组织规范（而不是个人品味）编进门禁。

分组不是永久的：clippy 跨版本会重组 lint（见第 2 节演进表，本机 1.92 的 style 组就比旧版膨胀不少）。所以**团队要固定 rustc/clippy 版本再谈分组策略**——ph16 的 rust-toolchain.toml 在这里成为 lint 纪律的地基。想查某个 lint 的文档，官方入口是 `https://rust-lang.github.io/rust-clippy/`（按版本存档，clippy 报错里也附每个 lint 的说明链接）。

**分组归属可以自己实测**（本阶段所有分组标注都来自这套方法，而非背诵文档）：对一段触发某 lint 的代码，逐个关闭候选组，看警告是否消失——警告消失的那一组就是它的归属组。这是「工具即文档」的验证姿势，也是 clippy 分组随版本漂移时团队自查的固定手法：

```bash
# 以 needless_range_loop 为例（触发代码见 ex02）：关掉 style 组警告消失 → 它属 style
cargo clippy --message-format short -- -A clippy::style   # 实测：警告消失
cargo clippy --message-format short -- -A clippy::perf    # 实测：警告还在 → 不是 perf
# 结论：needless_range_loop 在 clippy 0.1.92 属 style 组（默认 warn）
```

顺带记住一个反直觉事实：**clippy 里「默认 warn 三组」不等于「所有默认 warn 组都对应用户直觉」**——同一个 `needless_range_loop` 在旧版 clippy 属 perf、在本机 1.92 属 style（第 2 节重组），所以在文档/博客看到「某 lint 属某组」时，先确认对方用的 clippy 版本。

### 3.4 lint 例外纪律：#[allow] 的纪律与 #[expect] 契约

门禁一旦立起来，第一个反弹就是「这 lint 说的不对，我 allow 掉」。本阶段的立场不是「禁止 allow」而是：**每个 `#[allow]` 都是一条必须带理由的例外，allow 不是逃逸口，是审计日志**。rust-patterns 的反模式清单与本阶段正好互为镜像——ph11/ph20 教的「生产代码不裸 unwrap」「别为应付借用检查而 clone」「迭代器优于手写循环」等，在 clippy 里几乎都有对应 lint；**你治理完代码之后仍残留的 allow，就是「反模式例外」的登记处**。

```rust
// examples/ex03-lint-exception-discipline/src/main.rs（治理后版本，已验证：cargo 1.92.0）
// 例外纪律三步走：能修则修 → 修不了才 allow → allow 必须解释「为什么这次例外是值得的」

/// 解析 CSV 的字段长度表：一次性静态初值，逐字段传参比引入 builder 更直白。
/// #[allow(clippy::too_many_arguments)] —— 例外理由：这是固定列数的解码入口，
/// 拆结构体会让调用方多一次构造，8 个字段恰好一一对应文件列（8 列 / 8 参）。
#[allow(clippy::too_many_arguments)]
fn parse_row(
    id: u32,
    name: &str,
    city: &str,
    score: u32,
    active: bool,
    tags: &[&str],
    created: u64,
    note: &str,
) -> Row {
    Row { /* 与 8 个字段一一对应 */ }
}
```

`#[allow]` 的作用域纪律按从紧到松排列：**语句/函数级 > 模块级 > crate 级**。语句级 allow 只豁免眼前一处，是最小爆炸半径；`#![allow(clippy::xxx)]` 写在文件顶部就豁免整个文件，写着写着就没人知道还有没有 lint 在响；crate 级的 `#![allow(clippy::all)]` 则是把门禁直接拆了，属于反模式（rust-patterns 视角：等于宣布本 crate 不守质量契约）。**从 1.81 起有更好的工具**：`#[expect]` 表示「我预期这里的 lint 会触发，且我认可它」。实测行为（本机验证）：期望被满足则完全静默；**期望落空（代码改了、lint 不再触发）反而会报 `unfulfilled_lint_expectations` warning**——这正是它比 `#[allow]` 强的地方：`#[allow]` 在代码被修好后还赖着不动，`#[expect]` 会主动喊「这条例外已经不需要了，请删除」：

```rust
#[expect(clippy::manual_map)] // 故意手写 match 教学注释处；若未来改成 o.map(...) 会报期望落空
fn teaching_example(o: Option<u32>) -> Option<u32> {
    match o { Some(x) => Some(x + 1), None => None }
}
```

工程级 lint 策略集中在 Cargo.toml（Rust 1.74+），让「团队 lint 政策」进版本库而不是散落在每个文件头：`[lints.rust]` 管 rustc lint、`[lints.clippy]` 管 clippy、workspace 根用 `[workspace.lints]` 声明、成员 crate 用 `[lints] workspace = true` 继承。clippy 的**阈值类配置**（`too-many-arguments-threshold`、`type-complexity-threshold` 等）不在 Cargo.toml，而在 **clippy.toml**——放 crate/workspace 根，rustup 工具链会自动读取。两处配置的工程形态（ex03 有完整版）：

```toml
# workspace 根 Cargo.toml 片段（[workspace.lints] 是成员 lint 策略的单一事实来源）
[workspace.lints.rust]
unsafe_code = "deny"                        # rustc lint 也在这里统一声明

[workspace.lints.clippy]
all = "warn"                                # 三连门禁下 clippy 默认组保持 warn
pedantic = "allow"                          # pedantic 不整组开（3.3）
# 逐条例外：觉得某条 pedantic 值得遵守就单独开，allow/warn 都要能说出理由
unnecessary_wraps = "warn"                  # 库 API 不该无谓包 Result——全组成员共同决策
```

```toml
# 成员 crate 的 Cargo.toml：一行继承，策略不复制
[lints]
workspace = true
```

```toml
# clippy.toml（crate/workspace 根）——阈值类配置，工具链自动读取（实测：阈值=12 时 10 参函数不再报警）
too-many-arguments-threshold = 8            # 默认 7；团队放宽到 8 也应在 PR 里讨论过再改
# type-complexity-threshold = 250           # 默认 250：类型嵌套复杂度过高的阈值
```

注意 `[workspace.lints]` 声明的是**级别策略**（哪条 lint 什么级别），clippy.toml 管的是**工具的数值参数**（阈值是多少）——前者决定「查不查」，后者决定「查到多严」。lint 例外管理的最小纪律清单：

- **先修代码，再谈 allow**：lint 的建议通常等价且更优，直接改代码；allow 只留给「改代码反而更差」的场景
- **allow 必带理由注释**：写清「为什么这次例外是值得的」，理由类型只有三种站得住——故意教学/外部约束（代码生成、宏展开、必须匹配的外部格式）/已登记的技术债（带 TODO 或 issue 号）
- **作用域取最小**：语句/函数级优先；文件级要写段落理由；crate 级默认禁止
- **用 `#[expect]` 而不是 `#[allow]` 表达「预期触发」**：前者会自我清理，后者会永久残留
- **团队级策略进 `[workspace.lints]`，阈值进 clippy.toml**：个人喜好不进门禁，团队决策才进门禁

### 3.5 CI：GitHub Actions workflow 与质量门禁

本地跑门禁的问题是「只守护跑过的那一次」：别人提交不跑、换台机器不跑、忘了就不跑。**CI（持续集成）把它变成「每次 push / 每个 PR 自动在干净环境跑一遍」**。GitHub Actions 的四个层级心智模型（roadmap 第 21 节示例代码就是最小的 workflow，本阶段把它展开成完整形态）：

```text
workflow（.github/workflows/*.yml，声明式）
└── on（触发器：push / pull_request / workflow_dispatch / 定时）
    └── job（在独立 runner 上执行；同 workflow 内可并行多个 job）
        └── step（一条命令或一个 action；同 job 内顺序执行、共享文件系统）
            └── action（可复用单元，如 actions/checkout@v4 检代码）
```

Runner 是**每次全新**的：没有本地累积的依赖、缓存、target 目录。这既是 CI 可信的来源（「干净环境能过」= 不依赖我机器上的偶然状态），也是 CI 慢的来源（每次要重装工具链、重拉依赖、重编译）——后两个问题的解法正是 3.6 的缓存。质量门禁的最小 workflow（roadmap 示例的三步 + 检代码与装工具链两步，project 有完整带矩阵版本）：

```yaml
# examples/ex04-ci-workflow/.github/workflows/ci.yml —— 最小质量门禁（未在本环境实际运行验证）
# 说明：GitHub Actions 需远端 runner 才能跑，本机无 runner；此文件经 Ruby psych 静态解析
#       + 按官方 action 用法人工核对。结构为业界通用形态（checkout → toolchain → 三连）。
name: ci

on:
  push:
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4          # 1. 把仓库代码检到 runner
      - uses: dtolnay/rust-toolchain@stable # 2. 装 stable 工具链（自动读 rust-toolchain.toml）
        with:
          components: rustfmt, clippy       #    rustfmt/clippy 是独立组件，显式声明
      - name: 质量门禁：格式化断言
        run: cargo fmt --check
      - name: 质量门禁：clippy 零告警
        run: cargo clippy --all-targets -- -D warnings
      - name: 质量门禁：测试
        run: cargo test
```

为什么三个门禁分成三个 step 而不是一条 `run`：**step 是 CI 日志的最小折叠单位**，失败时能立刻看出「是 fmt 红了还是 clippy 红了」；GitHub 会把每个 step 的 stdout 单独展示，定位失败从看红哪个 step 开始（roadmap 验收「CI 输出便于定位失败」的落地）。**顺序为什么 fmt 最前、test 最后**：fmt 毫秒级且失败最廉价，先红先省时间；test 最贵放最后——最便宜的检查永远最先执行（fail fast）。

其他 CI 与本阶段的关系一句话带过：GitLab CI（`.gitlab-ci.yml`）与自建 runner 是同一套「声明式 job + 干净环境」心智模型，把本节的 step 换成 GitLab 的 `script:` 块即可迁移；本阶段与 project 模板以 GitHub Actions 为准，因为它是 Rust 社区模板的事实标准、且「workflow 文件随仓库走」的形态最适合学习。

workflow 调试的三个实用补丁（project/ci.yml 均有，属模板标配而非教学重点）：**① `workflow_dispatch:`** 让 workflow 支持在 GitHub 页面手动触发（配 `inputs:` 还能手动选矩阵的 toolchain/OS），改 YAML 后不用反复 push 就能试跑；**② `concurrency:`** 给同分支的连续 push 设取消策略，避免「旧提交的 CI 还在跑、新提交排队等」浪费 runner；**③ act 之类本地 runner 模拟工具**可以把 workflow 拉到本机跑（无需远端），但 act 的 Docker 容器与真实 GitHub runner 存在差异、**未在本环境实测**，模板以远端跑为准、act 仅作调试辅助提及。

### 3.6 CI 矩阵、缓存与可复现构建

**矩阵（matrix）**回答「只在 Ubuntu 上绿算不算绿」：Rust 的产物要跨 OS（路径分隔符、信号、文件锁、`std::os` 差异在 ph13 见识过），本地开发是 macOS、CI 全绿跑 Ubuntu、用户可能跑 Windows——**矩阵让同一套门禁在多种「工具链版本 × OS」组合上各跑一遍**。最小可复现的版本是 toolchain × OS 双轴：

```yaml
# examples/ex05-matrix-cache/.github/workflows/matrix-cache.yml —— 矩阵 + 缓存（未在本环境实际运行验证）
name: ci-matrix
on:
  push:
  pull_request:

jobs:
  quality:
    strategy:
      fail-fast: false                 # 一个组合失败不取消其他组合：三平台全都要结果
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        rust: [stable, "1.85"]         # "1.85" 是最低支持版本（MSRV，ph16），引号防 YAML 当数字
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@master # @master 读取 rust-toolchain.toml 的精确 channel
        with:
          toolchain: ${{ matrix.rust }}
          components: rustfmt, clippy
      - uses: Swatinem/rust-cache@v2     # 按当前 matrix 单元自动生成缓存 key（见下）
      - run: cargo fmt --check
      - run: cargo clippy --all-targets -- -D warnings
      - run: cargo test
```

矩阵的成本控制是工程决策：toolchain × OS 是**乘法**——3 个 OS × 2 个工具链 = 6 个 runner，每个都要全量跑三连。实践中的两组常用矩阵是「**MSRV 矩阵**」（`stable` + 最低支持版本，验证库不悄悄用新语法，ph16 project 模板已示范）与「**平台矩阵**」（发布/需要原生能力时全 OS）。两者不必同时全开——本机开发 + CI 的常见折中是：全平台跑 stable，MSRV 只在 Linux 上跑。

**缓存**解决 runner 每次全新带来的重复劳动：真正贵的是「编译依赖 + 下载 registry」。GitHub Actions 的缓存原语是 `actions/cache`：给你一把 `key`，命中就把之前存的目录还原，否则跑完把目录 `upload`。手写 `actions/cache` 的问题是 key 设计难（Cargo.lock 变了、rustc 版本变了都要让 key 变，否则命中旧缓存反而出错），所以社区直接进化出 **Swatinem/rust-cache**：它自动把 **rustc 短版本号 + Cargo.lock 内容 hash + 目标三元组** 拼进 key，并拆成 `cargo registry` 缓存与 `target` 增量缓存两把——「工具链或依赖任一变化必然 miss，miss 只是慢、不会错」是它的设计底线（4.3 讲命中原理）。缓存的内存布局要点（ex05 有注释版）:

| 缓存什么 | 为什么值 | 失效条件 |
|------|------|------|
| `~/.cargo/registry`（下载的依赖源码） | 省网络下载，CI 上往往最慢的一环 | 依赖版本变化（Cargo.lock hash 变） |
| `target/`（编译产物） | 省重编译，cargo 靠 fingerprint 增量 | rustc 版本变 / 依赖变 / feature 变 |
| 测试产物、临时文件 | **不缓存**（ph20 4.4：stale 产物让基准与测试失真） | —— |

需要**手写缓存**时（比如不引第三方 action 的仓库），核心是把两个失效变量编进 key，并用 `restore-keys` 容忍近失配：

```yaml
# 手写 actions/cache 的最小形态（片段；完整注释版见 ex05，均未在本环境实际运行验证）
- uses: actions/cache@v4
  with:
    path: |
      ~/.cargo/registry
      target
    key: cargo-${{ runner.os }}-${{ steps.toolchain.outputs.rustc }}-${{ hashFiles('**/Cargo.lock') }}
    #       ↑ OS 变则失配        ↑ rustc 版本变则失配  ↑ 依赖变则失配
    restore-keys: |
      cargo-${{ runner.os }}-${{ steps.toolchain.outputs.rustc }}-
      cargo-${{ runner.os }}-
```

`key` 全等才精确命中；`restore-keys` 允许「key 不存在时退回最近的前缀缓存」——代价是可能命中内容过期的 target（rustc 或依赖已变），cargo 会靠 fingerprint 发现并重编，所以**近失配命中只是「多编译一点」，不会用错产物**。这正是 rust-cache 存在的理由：把上面这段「容易漏 rustc 版本、容易把路径写错」的样板封装成一个 action，团队就不用各自维护。矩阵里每个 cell（OS × toolchain）天然要一把独立缓存——若手写，key 里必须带上矩阵维度的值（`runner.os` 已在、toolchain 由 rustc 输出体现）；rust-cache 对此有内置处理。

**可复现构建**是矩阵与缓存的共同前提：如果每次 CI 拉的依赖版本都不同，绿的结果无法重放。ph16 讲过 Cargo.lock 的格式与提交策略，这里落到 CI 侧：应用（二进制）**必须提交 Cargo.lock**，CI 用 **`cargo test --locked`** 强制「lock 文件与仓库一致，任何依赖解析变化都报错」——杜绝「本地 Cargo.lock 已更新但忘了提交、CI 默默解析出新版本」的静默漂移；配合 rust-toolchain.toml 钉死工具链，「版本可复现」就齐了。`--locked` 的另一面是它要求仓库每次改依赖都**显式提交 lock 变更**——这正是可复现构建要的「变更可见」。依赖漏洞审计与 registry 镜像等供应链话题只在 CI 模板留占位注释，本体属 ph24。

### 3.7 本地质量脚本与 pre-commit

CI 门禁管的是「合入前」，但开发者在提交前就该知道自己会不会红——**把三连包成一个本地脚本**，把「我记得要跑三连」变成「跑一个命令」：

```bash
#!/usr/bin/env bash
# examples/ex06-local-check-script/scripts/check.sh（与仓库文件一致；完整版已验证）
# 本地质量门禁：fmt → clippy -D warnings → test。用法：./scripts/check.sh（workspace 根执行）
set -euo pipefail
cd "$(dirname "$0")/.."                    # 切到 workspace 根，任何目录调用都有效
export PATH="$HOME/.cargo/bin:$PATH"

echo "── 1/3 cargo fmt --all --check"
cargo fmt --all --check
echo "── 2/3 cargo clippy --all-targets --workspace -- -D warnings"
cargo clippy --all-targets --workspace -- -D warnings
echo "── 3/3 cargo test --workspace"
cargo test --workspace
echo "✅ 质量门禁全绿"
```

`set -euo pipefail` 是脚本的三个保险丝：任何一步非零立即退出（`-e`）、未定义变量报错（`-u`）、管道中任一段失败都算失败（`-o pipefail`）——否则 `cargo fmt --check` 红了脚本还会继续往下跑，破坏「失败即停」的门禁语义。实测：脚本在干净 crate 上退出 0、在有 lint 的 crate 上于第 2 步以非零退出停下，输出能看到「卡在哪一步」。

再往前一步是**提交钩子**：把检查挂到 `git commit` 前自动跑。两种做法——**手写 `pre-commit` hook**（放 `.git/hooks/pre-commit`，但 hook 不进版本库，团队每人要各自装）与本阶段演示的 **pre-commit 框架**（`.pre-commit-config.yaml` 进版本库，`pre-commit install` 一次装好，成员共享同一份配置）。诚实的边界：pre-commit 框架**未在本机安装、未实际运行验证**（本环境无 `pre-commit` 命令），配置按社区通用形态给出并标注；手写 hook 与 `scripts/check.sh` 本身均已本机实测。**hook 的道德提醒**：`git commit --no-verify` 可以绕过一切本地钩子——所以本地钩子只是「省往返」的加速器，**最终裁判永远是 CI**（CI 不能 `--no-verify`，这就是 3.8 门禁流程的地基）。

### 3.8 质量门禁与 PR 流程

把前几节串成流程：开发者本地跑 `scripts/check.sh`（3.7）自查 → 推送分支 → GitHub Actions 的 workflow 自动跑（3.5）→ PR 页显示质量门禁 job 的红/绿 → 绿了才允许 review/merge（分支保护设 required check，把「门禁绿」变成合并的硬前提）。质量门禁在流程中的三个特性值得点破：

- **门禁不可跳过、不可 `--no-verify`**：CI 跑在仓库的声明（workflow YAML）上，不是跑在个人自觉上；这是它与本地 hook 的本质区别
- **例外必须过 PR 评审**：3.4 说「每个 `#[allow]` 是一条审计日志」，在 PR 流程里它同时是一条**评审意见**——reviewer 看到新增 allow 就问「理由是什么？有没有登记 TODO？」。lint 例外于是从「个人判断」升级为「团队决策」
- **门禁红要可定位**：step 拆分（fmt/clippy/test 各自独立）、失败即停、CI 输出直接指向具体 lint/文件/行——这些 3.5/3.7 的编排细节最终都服务于「PR 作者和 reviewer 都能在几秒内知道改什么」

roadmap 第 21 节给的最小 workflow（三步 run）就是本节门禁的骨架，3.5 补上了 checkout 与 toolchain，3.6 补上了矩阵与缓存——合成一份完整模板就是本阶段 project/ 的 ci-template。值得记的流程箴言：**质量门禁的目标不是「消灭所有 warning」而是「消灭『没被讨论过的 warning』」**——默认组全绿 + 例外走 PR，就是这套流程最朴素的形态。

## 4. 底层原理

### 4.1 clippy 如何做 lint：编译管线上的 lint passes

`cargo clippy` 换掉的不是 rustc 而是 rustc 的前端驱动——编译仍走完整管线，clippy 只是**往管线的特定阶段挂 lint pass**：

```text
源码 ──▶ AST ──▶ HIR ──▶（THIR）──▶ MIR ──▶ codegen
          │        │                      │
       语法错误   rustc lint 主战场    borrow-check /
       （不给 clippy 机会）          clippy 的 MIR pass 主战场
                      │
               clippy 绝大多数 lint 在这里：
               span 定位 + 建议修复（suggestion）
```

lint pass 与语法分析共享同一棵语法树，这就是为什么 clippy 能给出行级 `span` 与**可应用的修复建议**（3.2 的 `--fix`）：lint 在报告时附上 `MachineApplicable`（机器可直接改，如 manual_map）或 `MaybeIncorrect`/`HasPlaceholders`（只提示、不自动改）等适用性标记，`--fix` 只应用机器可改的那批。为什么多数 lint 挂在 HIR 而非 MIR：风格/复杂度类检查看的是「代码长什么样」（结构），不是「运行起来怎么样」——`needless_range_loop` 在 HIR 上看到 `for i in 0..v.len()` 的模式即可判定；少数需要数据流/控制流证据的 lint（如死代码、永不满足的分支、真正的复制语义）才下探 MIR。按「证据深度」给本阶段实测过的 lint 排个队（示意性分类，用于建立心智）：

| 证据深度 | 代表 lint | 判定依据 |
|------|------|------|
| 语法/AST 层 | `eq_op`（自我比较） | 两个操作数是否同一表达式/字面量，纯结构相等 |
| HIR 结构层 | `needless_range_loop`、`manual_map`、`collapsible_if`、`too_many_arguments` | 看 HIR 节点的形状（循环头/嵌套 if/match 模式），不看数据流 |
| MIR/语义层 | `manual_memcpy` 这类「读懂循环在做什么」的检查 | 需确认循环体只是复制、索引一一对应等语义性质 |
| 运行前静态判定 | `unwrap_used`、`indexing_slicing`（restriction） | 出现该 API/语法即报，不分析上下文——禁令类 lint 天然「看名字就报」 |

**关键认知：clippy 是「编译器视角」的静态检查，它不运行代码**——所以它既不会漏（只要 lint 规则覆盖，任何一次构建都必然报），也不可能全对（没有运行时证据，只能按模式匹配，这是误报的根源，也是 lint 例外的存在理由）。

### 4.2 rustfmt 的解析-打印两段式

rustfmt 复用 rustc 的**解析器**把源码读成语法树（能解析失败的文件就报语法错，不产生「半格式化」），然后交给自己的**打印端**按「配置 + 默认启发式」重新排版输出。注意它**不做语义分析**——不查类型、不查借用，只动布局。这套「解析 → 重排打印」的两段式决定了 rustfmt 的三个性质：① **安全**：不参与类型检查，就不存在「格式化把程序改坏」的路径，输出与输入语义必然一致；② **快**：省掉整个语义分析阶段，所以 `cargo fmt --check` 毫秒级、适合放门禁最前；③ **有盲区**：宏体、字符串这类不能/不该当作普通语法树重排的内容按 token 级保守保留——这就是 3.1 说的「别指望 rustfmt 整理宏内部」。`--check` 的实现也因此平凡而可靠：打印端产出的文本与原文件做 diff，非空即退出码 1（实测）——门禁断言的是「重排后没有变化」，而不是「代码好不好看」。

### 4.3 CI 缓存命中原理与可复现构建

缓存命中的本质是 **key → 内容的确定性映射**。GitHub Actions 的缓存层是键值存储：job 开始时用 `key` 精确匹配找缓存，找到就还原目录；跑完把目录连同 key 一起存回去。rust-cache 的关键设计是**把「会导致缓存内容失效的变量」全部编进 key**——rustc 版本号（换工具链则旧 target 全作废）、Cargo.lock 的 hash（依赖一变，registry 与重编译需求都变）、目标三元组（不同 OS/架构的产物不通用）。于是缓存正确性变成自动的：**key 变则必然 miss，miss 只是重下/重编、慢而不错；key 不变则稳定命中**。而 cargo 增量编译本身靠 fingerprint（源码与依赖的 hash/mtime）判断重编哪些单元，被还原的 target 目录让这份增量判断跨 runner 生效——这是「缓存 target」比「只缓存 registry」更省时间的原因。risk 也在这里：**不同 rustc 版本编出的 target 不兼容**，混用会触发大面积重编甚至疑难告警，所以 key 必须锁 rustc 版本（rust-cache 默认做了，手写 actions/cache 时最容易漏的就是这一点）。

可复现构建给缓存提供「确定性输入」：`Cargo.lock` 把每个依赖钉到「精确版本 + checksum」（ph16 已讲格式），CI 用 `--locked` 断言 lock 未被本地静默改动，rust-toolchain.toml 钉住编译器——三样合起来，CI 每次拉的依赖集合与工具链都相同，缓存 key 中的 lock hash 也就稳定。**换个说法：缓存与可复现是同一枚硬币**——没有 lock 的可复现，缓存 key 天天变，缓存天天 miss，CI 天天全量重编；有了它，缓存命中率高且可预期。

三个缓存实操认知，避免把缓存变成新的坑：**① 缓存是仓库作用域的近失配容忍**——不同分支 push 的 key 不同，用 `restore-keys` 退回共享前缀时，「别人分支的旧产物」会被还原，靠 cargo fingerprint 重编纠正，所以近失配缓存只影响时间、不影响正确性；**② 并发上传同 key 是「后写覆盖」**——矩阵里多个 job 若共享同一把 key，同一时刻只有一份能存成功，rust-cache 默认按 job 拆 key 就是为了避开这种覆盖竞争；**③ 缓存有保留期与容量上限**——GitHub 会按「最近未使用」淘汰条目并对单仓库缓存总量设限，超限时旧条目先被清，所以缓存是「命中率优化」不是「持久存储」，不要依赖缓存内容长期存在。

## 5. 使用场景

本阶段知识在真实工程里的落点，收敛成一张「什么时候开什么」的决策表：

| 场景 | 配置 | 理由 |
|------|------|------|
| CLI/服务端应用（默认推荐） | 默认组 + `-D warnings`，`--no-deps`，fmt 零配置 | 门禁便宜而有效；默认组外 lint 不进 `-D`，避免把门禁变成 TODO 清单 |
| 库 crate（追求 API 质量） | 默认组 `-D` + 单开 pedantic 的部分条目（逐条 allow 不合理的） | pedantic 的 `missing_docs`/`must_use_candidate` 类对库 API 有价值；但逐条评估，不整组 `-D` |
| 团队要禁某类反模式 | 按条开 restriction：如 `-W clippy::unwrap_used`、`-W clippy::panic` | restriction 整组开是反模式（3.3 实测），按条开 = 把组织规范编进门禁 |
| 探索性原型/一次性脚本 | 不设门禁，甚至跳过 fmt | 先直白后加固：原型期追求速度，稳定后接入（ph20 对测试的同一立场） |
| 什么时候不能只靠这些 | 架构评审、性能热路径、供应链审计 | fmt/clippy 不查的：性能要 ph22 的测量、依赖安全要 ph24 的 audit/deny |

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）。Rust 与主流语言的分水岭在「官方收编」：格式化与 lint 都跟编译器同版发布，而 Java/Python 的同类工具多半是独立版本、由插件生态撮合：

| 维度 | Rust | Go | Java | Python |
|------|------|-----|------|--------|
| 格式化器 | **官方组件 rustfmt**（随 rustc 同版，`cargo fmt`） | **官方 gofmt**（语言设计内置，`go fmt`） | 无官方；主流 google-java-format / spotless | 无官方；事实标准 black（ruff format 兼容） |
| 静态检查 | **官方 clippy**（rustc 管线加 lint，分组管理） | 官方 go vet（保守）+ golangci-lint（聚合社区 linter） | checkstyle（风格/规则 xml）+ SpotBugs/Error Prone（字节码/AST bug 模式） | ruff（聚合 flake8 + 插件生态，单二进制） |
| lint 分级/例外 | 分组默认级别 + `#[allow]`/`#[expect]` + `[lints]` 表，语法与 rustc lint 统一 | vet 少分级；golangci-lint 靠 enable/disable 列表 | checkstyle severity + suppression xml | ruff 按规则 select/ignore + `# noqa` 行内 |
| 门禁一键化 | `cargo clippy --all-targets -- -D warnings` 一条命令 | 无 `-D warnings` 同义物，靠工具自身 exit code | Maven/Gradle 插件 failOnViolation | ruff 非零退出 + CI step |
| 与编译器关系 | clippy/rustfmt 与 rustc **同版同步** | gofmt/vet 与 go 同版（官方） | 全第三方，版本独立于 javac | 全第三方，版本独立于 CPython |
| CI 实践 | matrix（toolchain×OS）+ rust-cache | matrix（go 版本×OS）生态成熟 | matrix + Maven 缓存 | matrix + pip/uv 缓存 |

跨语言读出的规律：**Rust 与 Go 都选择「官方格式化器」，但 lint 上分道**——Go 把 vet 做得极保守（官方几乎不报风格），把深度检查留给聚合器 golangci-lint；Rust 则让官方 clippy 承担深度检查并内置分组与例外语法。Java 是「编译器官方 lint 最弱、第三方生态最繁荣」的极端（checkstyle 管风格、SpotBugs 管 bug 模式、两者规则语言完全不同）；Python 的 ruff 是「后发聚合者」——把历史悠久的 flake8 插件生态压进一个快速 Rust 二进制。**对 Tenet 的启示候选：一门语言的质量基线 = 官方格式化器（零配置默认）+ 官方静态检查（内置分级与例外）+ CI 门禁模板随仓库走；「跟编译器同版」让 lint 升级像编译器升级一样可控，而第三方 lint 生态则需要独立的规则版本管理。** 这些观察在 analysis/ 设计解剖时再深化，本阶段只需收集素材。

## 6. 代码示例

本节展示示例的关键片段，完整工程在 [`examples/`](./examples/)。验证环境：rustc/cargo/clippy 1.92.0、rustfmt 1.8.0（macOS arm64）。**验证说明**：ex01~ex03/ex06 均已本机实测（按各示例设计的红/绿状态均验证其真实退出码与输出），标注「已验证」；ex04/ex05 是 GitHub Actions workflow，未在本环境实际运行验证（详见其文件头）。逐示例运行命令见 [`examples/README.md`](./examples/README.md)。

| 示例 | 对应主文档 | 一句话说明 | 验证状态 |
|------|-----------|-----------|---------|
| [`examples/ex01-fmt-diff/`](./examples/ex01-fmt-diff/) | 3.1 | rustfmt 门禁演示：治理前/后双版本 + `cargo fmt --check` 的 diff 与退出码、rustfmt.toml 配置生效 | 已验证 |
| [`examples/ex02-clippy-lint-levels/`](./examples/ex02-clippy-lint-levels/) | 3.2/3.3 | clippy lint 动物园：correctness/style/complexity/perf 实测触发 + pedantic/nursery/restriction 开启方式 + `-D warnings` | 已验证 |
| [`examples/ex03-lint-exception-discipline/`](./examples/ex03-lint-exception-discipline/) | 3.4 | lint 例外纪律：带理由的 `#[allow]`、`#[expect]` 契约、Cargo.toml `[lints]` 与 clippy.toml 配置 | 已验证 |
| [`examples/ex04-ci-workflow/`](./examples/ex04-ci-workflow/) | 3.5 | 最小质量门禁 workflow（checkout → toolchain → fmt/clippy/test 三连 step） | 未在本环境实际运行验证（无 runner） |
| [`examples/ex05-matrix-cache/`](./examples/ex05-matrix-cache/) | 3.6 | 矩阵（OS × 工具链）与缓存（rust-cache）workflow + 缓存失效对照表 | 未在本环境实际运行验证（无 runner） |
| [`examples/ex06-local-check-script/`](./examples/ex06-local-check-script/) | 3.7 | `scripts/check.sh` 本地门禁（真 crate 实测红/绿） + pre-commit 配置示例 | 脚本已验证；pre-commit 框架未安装未验证 |

```rust
// examples/ex01-fmt-diff/src/main.rs —— 治理后的参考实现（已验证：rustfmt 1.8.0）
// 治理前版本在 before/main.rs（故意未格式化，供复制回 src/ 复现 fmt --check 失败）。
// 复现步骤：cp before/main.rs src/main.rs → cargo fmt --check（exit=1）→ cargo fmt（自动治理）
fn main() {
    let items = vec!["rustfmt", "clippy", "cargo"];
    println!("tools:");
    for item in items {
        println!("- {}", item);
    }
}

fn add(a: i32, b: i32) -> i32 {
    a + b
}
```

```rust
// examples/ex02-clippy-lint-levels/ex02a-default-warn-zoo/src/main.rs（治理前，故意携带 lint；已验证）
// 直接跑 cargo clippy 可见：needless_range_loop / manual_map（实测均属 style 组，默认 warn）
// 与 too_many_arguments（complexity 组）一起作为 warning；裸跑退出 0，加 -D warnings 才失败。
fn bump(opt: Option<u32>) -> Option<u32> {
    match opt {
        Some(v) => Some(v + 1), // style：manual_map —— 治理成 opt.map(|v| v + 1)
        None => None,
    }
}
```

```rust
// examples/ex02-clippy-lint-levels/ex02b-correctness-deny/src/main.rs（治理前；已验证）
// correctness 组默认 deny：裸跑 cargo clippy 即 error，不需要 -D warnings。
fn crc_matches(expected: u32, _actual: u32) -> bool {
    expected == expected // 与自身比较 = eq_op；粘贴变量名时把 actual 也写成 expected 的 typo
}
```

## 7. 总结

### 关键要点

- **门禁三连是顺序工程**：`cargo fmt --check`（毫秒级、断言布局）→ `cargo clippy --all-targets -- -D warnings`（零告警硬约束）→ `cargo test`（最贵最后）；fmt 先行消除格式噪音，最便宜的先红先省时间（3.1/3.2）
- **`cargo clippy` 裸跑不是门禁，`-D warnings` 才是**：裸跑 warning 也退出 0；`--all-targets` 堵住 tests/benches 逃逸口；`--no-deps` 让第三方 lint 不挡自己的门；`--fix` 自动应用机器可改建议（3.2）
- **lint 分两组心智**：默认组（correctness deny，suspicious/style/complexity/perf warn）+ 三档 opt-in（pedantic 严格审查、nursery 试验田、restriction 禁令组）——restriction **禁止整组开**，按团队纪律逐条 `-W`（3.3）
- **例外纪律 = 带理由的 allow**：能修先修；allow 必写理由（教学/外部约束/登记技术债三类）；作用域取最小；`#[expect]` 优于 `#[allow]`——期望落空会自动报错提醒清理；团队策略进 `[workspace.lints]`、阈值进 clippy.toml（3.4）
- **CI 把门禁变成不可跳过**：runner 每次全新是可信来源也是慢的来源；workflow 用 step 拆分保证失败可定位；矩阵解决「只在 Ubuntu 绿不算绿」，缓存（rust-cache，key 绑 rustc 版本 + Cargo.lock hash）让全量重编只在依赖/工具链变化时发生（3.5/3.6）
- **可复现构建三件套**：提交 Cargo.lock + CI 用 `--locked` + rust-toolchain.toml 钉工具链——同时是缓存高命中率的前提（3.6/4.3）
- **本地脚本 + 远端 CI 双层设防**：`scripts/check.sh` 省提交往返，pre-commit hook 进一步前置；但 hook 可 `--no-verify` 绕过，最终裁判永远是 CI，例外必须走 PR 评审（3.7/3.8）

### 阶段验收清单

- [ ] 能说清 `cargo fmt` 与 rustfmt 的关系、`--check` 为什么是门禁语义；能配 rustfmt.toml 的行宽并解释其生效范围（3.1）
- [ ] 能解释 `-A/-W/-D` 与 rustc lint 的关系；知道为什么门禁必须 `cargo clippy --all-targets -- -D warnings` 而不是裸跑 clippy（3.2）
- [ ] 能列出 clippy 全部 lint 组的默认级别，说清 pedantic/nursery/restriction 各自的定位与「何时开、何时不开」，并解释 restriction 为何禁止整组开（3.3）
- [ ] 能为一个现有 crate 治理 clippy warnings 到零告警，并为残留例外写出带理由的 `#[allow]` 或 `#[expect]`（roadmap 验收「能为 lint 例外给出明确理由」）（3.4）
- [ ] 能写出最小质量门禁 workflow（checkout → toolchain → 三连），并为它加 toolchain×OS 矩阵与 rust-cache 缓存（3.5/3.6）
- [ ] 能配置本地检查脚本并在 PR 流程里让 CI 输出定位到具体失败 step（roadmap 验收「能让 PR 通过格式化、lint 和测试」「能让 CI 输出便于定位失败」）（3.7/3.8）
- [ ] 能解释缓存 key 为什么会失效、`--locked` 为什么是 CI 标配（4.3）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。三题与 roadmap 第 21 节练习一一对应：练习 1 =「给项目加 fmt/clippy/test CI」（本地模拟 CI 门禁 + workflow 文件），练习 2 =「清理 clippy warnings」（治理前/治理后双版本），练习 3 =「配置本地检查脚本 + pre-commit」。完成 3 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**Rust CI 模板工程（ci-template）**——可复用于 CLI/服务端/库项目的完整模板（roadmap 第 21 节推荐项目落地）：`.github/workflows/ci.yml`（矩阵 + 缓存 + 三连门禁）、`scripts/check.sh`、`[workspace.lints]` 与 clippy.toml 配置、rust-toolchain.toml、一个「故意带 lint 问题 → 治理后全绿」的演示 crate，验收标准见 project/README.md。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（本机 `scripts/check.sh` 全绿；workflow 按验收清单人工核对）

### 跨语言对比

- Rust 与 Go 都选「官方格式化器」（rustfmt/gofmt），但 lint 分道：Go 官方 vet 保守、深度检查交给 golangci-lint 聚合器；Rust 让官方 clippy 承担深度检查并内置分组 + 例外语法。Java 是编译器 lint 最弱、第三方最繁荣的极端；Python 的 ruff 是后发聚合者（为 analysis/ 与 Tenet 合成积累素材，详见 5 节对比表）

### 下一阶段

[**ph22 性能优化与 Profiling 阶段**](../ph22-perf-profiling/22-perf-profiling.md)——本阶段把代码质量的门禁立起来了，下一阶段回答「质量之上，性能怎么证明与提升」：release/profile 配置（`[profile.release]` 的 lto/codegen-units）、criterion 基准、flamegraph/perf 采样、内存分配剖析——届时本阶段 CI 模板中「只留占位」的性能回归 job 将成为落地对象；clippy `perf` 组在本阶段只是默认开的一组 lint，到 ph22 你会明白它的每条建议背后都有一台测量仪器。
