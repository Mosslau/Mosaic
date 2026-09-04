# Rust 性能优化与 Profiling 阶段

> 面向「让性能成为可测量、可解释、可回归的工程属性」的方向：本阶段把 ph19「先测量后优化」的承诺正式兑现——从 `[profile.release]` 的构建参数开始，用 criterion 建立可信的基准，用采样剖析找到热点，用分配计数把「少分配」从口号变成数字，最后落到缓存局部性、内联与单态化这些 CPU 结构性格局上——全程围绕同一句纪律：**没有测量就没有优化，没有回归就没有保持**。

## 1. 概述

本阶段对应 roadmap 第 22 节，目标是**能基于测量进行优化，而不是凭感觉修改代码**。它是学习路线里从「会写对」到「能写快」的转折点：前 20 个阶段教怎么写安全、正确、可测试的 Rust；ph21 刚把代码质量变成门禁；本阶段则回答「质量之上，性能如何证明与提升」。ph19 主文档两处预留了落点——「测量与调优属 ph22」（缓存行部分）与「别在没测量时按直觉改布局」；ph21 的 CI 模板把「性能回归 job」留成占位；ph18 的「分配次数是首要优化对象」、ph20 的「criterion 深水区交给 ph22」——本阶段逐条兑现。

| 核心维度 | 覆盖内容 |
|----------|---------|
| release/profile 配置 | `[profile.release]` 的 opt-level / lto / codegen-units / panic 各键的实际效果与代价；自定义 profile（3.1） |
| 优化方法论 | 「先测量 → 定位 → 优化 → 再测」闭环；何时值得优化；编译器消除陷阱与 black_box（3.2） |
| criterion 基准方法论 | benchmark_group / Throughput / 变化检测与回归阈值；把 ph20 的「会用 bench」升级为「系统化测量」（3.3） |
| flamegraph / perf 采样 | 采样剖析原理、读火焰图、热点定位；Linux perf + cargo flamegraph 命令与 macOS Instruments/sample 替代（3.4） |
| 内存分配剖析 | 全局计数分配器；分配次数/字节作为一等指标；避免分配：复用缓冲、String vs &str、小向量优化（3.5） |
| 算法与数据结构选择 | 复杂度 vs 常数；Vec / HashMap / BTreeMap 实测对比；先算法后微调（3.6） |
| 缓存局部性 | 缓存行、顺序 vs 随机访问、AoS vs SoA 布局（3.7） |
| 内联与单态化 | `#[inline]` 家族语义、泛型单态化 vs `dyn` 动态分发（3.8） |
| 底层原理 | 采样 vs 插桩、缓存行与伪共享、分配器行为、LTO 编译期权衡（4） |
| 场景与练习 | 何时优化/何时不优化 + C++/Go 跨语言对照；examples/exercises/project 四层配套（5~7） |

这个阶段只涉及 **Rust 进程内的通用代码路径性能**（CPU 时间、分配、缓存、分发），**不涉及 FFI 与跨语言边界的性能设计**（跨语言边界的优化——copy 策略、跨 ABI 调用开销、为 Python 暴露的加速函数该在哪一侧分配——属 ph23 Rust FFI 与跨语言接口设计阶段，roadmap 第 23 节，目录待建）、**依赖供应链与发布安全**（本阶段的基准 CI job 会用到 ph21 模板，但依赖漏洞、审计、许可证与制品安全属 ph24 安全、供应链与发布阶段，roadmap 第 24 节，目录待建）、**数据基础设施的专项调优**（本阶段的优化对象是**通用**代码路径——WAL/日志的解析与聚合只是载体；WAL append/replay、MemTable/SSTable、compaction 吞吐与写放大等引擎级专项优化属 ph25 Rust 数据基础设施专项阶段，roadmap 第 25 节，目录待建）。同时与两条相邻知识划清边界：**安全抽象的 unsafe 性能手段**（`get_unchecked`、`from_raw_parts` 这类「最后手段」属 ph14 Unsafe 与安全抽象阶段——本阶段先测出瓶颈再说，正文不鼓励为性能引入 unsafe）；**汇编/SIMD 级的指令优化**（本阶段只到「结构性格局」层——缓存、分配、分发；手写 SIMD/内联汇编的极致优化超出本阶段范围）。

## 2. 来源与演变

「Rust 性能」这个词组的来源可以拆成三股脉络，最后在本阶段汇合：**语言承诺**、**测量工具**与**剖析工具链**。

Rust 从 C++ 继承并强化了「零成本抽象」（zero-cost abstractions）哲学——C++ 之父 Bjarne Stroustrup 提出的口号在 Rust 里被所有权系统兑现得更彻底：你为不需要的抽象不付运行时成本，编译器在编译期（而非运行时）替你付掉抽象的成本。但这个承诺本身**不保证程序快**——它只保证「没有隐性运行时税」，至于你有没有选对算法、误伤了缓存、多做了分配，编译器一概不管。因此 Rust 社区很早就把「性能」理解为**一门测量科学**，而不是语言的自动属性。**设计哲学一句话加粗：Rust 认为性能不是优化出来的，而是测量出来、再按测量结果改出来的——语言消除「隐性成本」，测量工具消除「隐性假设」。**

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| C++「零成本抽象」口号 | 1994 前后 | Stroustrup 提出；成为 Rust 继承的设计价值观 |
| gprof / perf / VTune 生态 | 1980s~2000s | 采样剖析从 Unix 学术工具演进为工程标准；`perf` 成为 Linux 内核级剖析事实标准 |
| criterion 诞生 | ~2015 | japaric 发起 Rust 微基准框架，引入统计显著性、置信区间与回归检测——`cargo bench` 从「自己计时」变成「科学测量」 |
| cargo profile 正式化 | 2015~2016（Rust 1.0 起，`[profile]` 2016 前后扩展） | Cargo.toml 声明 opt-level/lto/codegen-units/panic 等，构建参数第一次可版本化、可复现 |
| flamegraph 工具化 | ~2016 | Brendan Gregg 的火焰图可视化被 `cargo flamegraph`（基于 perf/dtrace）带进 Rust 工作流——剖析输出从「函数占比表」变成可读的「火焰图」 |
| Criterion.rs 重写与流行 | 2017~2020 | 引入 `--save-baseline`/`--baseline` 基线对比与 HTML 报告，成为 Rust 基准事实标准（ph20 已实测使用） |
| profile-guided optimization 基建 | 2020~2022 | nightly 起 `-Cprofile-generate`/`-Cprofile-use` 让 PGO 进入 Rust 生态；stable 侧仍主要靠 rustc 自带启发式 + profile 调参 |
| `-Znext-lto` / 现代 LTO 演进 | 2022~ | fat/thin/off 三档 LTO 的权衡被文档化（本机 1.92 实测见 3.1），codegen-units 与增量编译的关系日趋清晰 |
| 本环境工具链 | 2025-12 | rustc/cargo 1.92.0（macOS arm64，Apple M4 Pro，缓存行 128B、L2 4MB 实测）；criterion 0.8.2 |

一个值得记住的历史结论：**criterion 与 flamegraph 都不是 Rust 官方发明的，而是社区工具先做出价值、再成为「半官方」事实标准**——这与 clippy/rustfmt 被官方收编的路径同构（ph21 已述），区别是性能工具停留在「生态标配」层级，因为性能测量与具体机器强绑定，不适合塞进语言规范。这也解释了本阶段的一个重要姿态：**工具只是放大器，测量口径与结论解释仍然是人（你）的活**——criterion 给你置信区间，但「这个区间说明什么」要你判断；flamegraph 给你热点，但「热点为什么存在」要你读代码。

另一个常被误认为「同族」的技术值得在这里划清：**profile-guided optimization（PGO）**——先用插桩版本跑真实负载收集「哪些分支/调用最热」，再用这份 profile 指导二次编译（`-Cprofile-generate` → 跑 → `-Cprofile-use`）。PGO 与本阶段的区别在两层：① PGO 优化的是**编译器看不到的运行时事实**（哪个 `if` 分支概率高、哪个虚调用真的只落到一个类型）；② PGO 需要**代表性负载**——profile 来自什么输入，优化就偏向什么输入。本阶段（稳定版 Rust 上）不直接用 PGO（nightly 能力 + 双轮构建复杂度），但 3.1 的 profile 调参与 3.4 的采样剖析正是 PGO 之前的两步：先用剖析找到该优化的函数，再用基准验证——**先让编译器在正确方向尽力，再考虑让编译器「看见」运行时事实**。

本文示例以 **rustc/cargo 1.92.0、criterion 0.8.2（edition 2021）** 为基线（与 ph20/ph21 的仓库代码层一致；所有 release/profile 行为、criterion 输出、缓存行/分配计数均在本机实测）。验证工具链 **rustc/cargo 1.92.0（macOS arm64，Apple M4 Pro，rustup 管理）**。**代码验证状态**：examples 的 ex01~ex06、exercises 的 sol-01~sol-03、project 的 log-aggregator 全部在本机实测（`cargo fmt --check` / `cargo clippy --all-targets -- -D warnings` / `cargo test` 全绿；`cargo bench` 与 release 二进制运行数字见各 README 与文件头注释），标注「已验证」；**flamegraph/perf 属于 Linux 工具、cargo-flamegraph 本机未安装、Instruments 为 GUI 采样器**，它们的输出**未在本环境验证**（3.4 给出 Linux 命令与 macOS 替代命令）。构建产物统一落 `/tmp`（`CARGO_TARGET_DIR`），仓库零二进制残留。这个阶段的语法是 Rust 里最**「与机器对话」**的部分：没有多少新关键字，核心是把配置文件、基准代码与系统工具用出方法论——学习重点是建立测量直觉，而不是背命令。

## 3. 语法与参数

本章按「构建参数 → 方法论 → 三类测量 → 三类结构性格局」推进，对应 roadmap 第 22 节学习内容的五块（release/profile 配置 / criterion / flamegraph-perf / 内存分配分析 / 算法与数据结构）并补齐方法论与缓存/内联两块。全部命令的完整工程形态见 [`examples/`](./examples/)，练习见 [`exercises/`](./exercises/)，综合项目见 [`project/`](./project/)。

### 3.1 release/profile 配置：opt-level / lto / codegen-units / panic

优化从**构建参数**开始：同样的源码，`cargo build`（dev）与 `cargo build --release` 的产物可能差一个数量级——dev 档为调试体验牺牲一切（opt-level=0、debug=true），release 档默认 opt-level=3。Cargo 用 `[profile.*]` 表把这些参数版本化在仓库里，让「怎么构建」与代码一起可复现（这正接上 ph21 的可复现构建纪律）。四个最常调的键及其代价：

| profile 键 | 默认值（release） | 调大/开启的收益 | 实际代价 | 建议 |
|------|------|------|------|------|
| `opt-level` | 3 | 运行时优化最强 | 编译变慢、二进制变大 | 保持 3；需要最小体积时降 2/s/z |
| `lto` | false | 跨 crate 链接期优化：跨 crate 内联、常量传播、去虚化 | 链接时间显著变长（fat 最慢） | 库/服务端常用 `thin`；追求极致再 `fat`（3.1.2） |
| `codegen-units` | 16 | 越小跨单元优化越充分 | 编译并行度下降，16→1 编译变慢 | 默认即可；配 LTO 时常一并设 1 |
| `panic` | unwind | ——（切换语义） | `abort` 删掉 unwinding 元数据，二进制变小；代价是 panic 不可捕获 | 追求最小二进制/明确「panic=进程死」语义时用 `abort` |

`opt-level` 是运行时优化的总开关，其余三键本质是「优化充分度 × 编译时间」的权衡。roadmap 第 22 节示例代码给的形态（lto = true + codegen-units = 1）是「把整个依赖图交给链接器做一次全程序优化」的经典组合。本阶段的实验对象（`examples/ex01-profile-config`，已验证）把同一份源码用三档 profile 各构建一次：

```toml
# examples/ex01-profile-config/Cargo.toml —— 三档 profile 的对照声明
[profile.release]              # 档 1：显式写出 Cargo 默认值
opt-level = 3
lto = false                    # 默认不做跨 crate 链接期优化
codegen-units = 16
panic = "unwind"

[profile.release-lto]          # 档 2：roadmap 示例形态
inherits = "release"
lto = "fat"                    # 全依赖图链接期优化
codegen-units = 1              # 单编译单元

[profile.release-thin-abort]   # 档 3：thin LTO + panic=abort
inherits = "release"
lto = "thin"
panic = "abort"
```

热点函数刻意放在 path 依赖 `hotcore` crate 里——默认 release 下 rustc 看不见别的 crate 内部，跨 crate 调用保持真实调用边界，LTO 才有「看穿边界」的对象。三档在本机（cargo 1.92.0，冷编译计时）的实测：

| 维度 | release（默认） | release-lto（fat+cgu1） | release-thin-abort |
|------|---------------|----------------------|-------------------|
| 冷编译时间 | 1.38 s | 2.69 s（≈1.9x） | 3.05 s（≈2.2x） |
| 二进制大小 | 445,392 B | 390,656 B（-12%） | 420,976 B（-5%） |
| 3×10⁸ 次调用（5 轮中位） | 201 ms | 219 ms | 201 ms |

实测的诚实结论比「LTO 一定更快」更有价值：**在这个微基准上，三档运行时间落在噪声内**（中位 201/219/201 ms，同档多次波动 ±15%），而 fat LTO 的编译时间代价（+1.9x）与体积收益（-12%）是明确可测的。为什么？因为热点循环每次调用已经足够简单，编译器默认（cgu16）下的单 crate 内优化已把热路径逼近极限，LTO 没有可再省的东西——**LTO 的收益场景是「跨 crate 边界真正挡住优化」的程序**：泛型实例化跨 crate、常量传播跨越模块边界、虚调用去虚化。所以实践法则是：先量出跨 crate 调用是不是热点，再决定开不开 fat；一般工程从 `thin` 起步。

> ⚠️ **panic=abort 不是性能键，是语义键**：它把 panic 从「可捕获的展开」改成「直接终止进程」。体积收益来自删掉的 unwind 表，但代价是 `catch_unwind` 失效、库跨 panic 边界的兼容性变化——**别为了几个 KB 二进制把语义改了**（改前先问：panic 在这条路径上是要被捕获的吗）。

> 自定义 profile 用 `[profile.<名字>]` + `inherits = "release"` 声明，构建用 `cargo build --profile <名字>`。这是 ph22 相对 ph06 增量：ph06 只教 `--release` 这个开关，本阶段讲清开关背后的参数与权衡。

`opt-level` 的档位值得单独看一眼，因为它是「运行时速度 vs 编译时间/体积」最直接的旋钮：

| opt-level | 语义 | 典型用途 |
|-----------|------|---------|
| 0 | 不做优化（dev 档默认） | 调试：编译最快、行为最直白 |
| 1 | 基础优化 | 快速验证 release 行为 |
| 2 | 较充分优化（不牺牲太多编译时间） | 部分项目的折中 |
| 3 | 最充分优化（release 默认） | 追求运行时速度的默认选择 |
| s / z | 优化目标改为体积 | 体积受限场景（嵌入式、wasm、下载体积敏感） |

把三档 profile 与 CI 结合起来就得到 ph21 预留的「性能回归 job」的完整形态：CI 里用 **release（接近用户实际跑的构建）** 建基准基线，用 `--save-baseline` 存档、`--baseline` 阈值判红；lto/codegen-units 的「实验性调参」则放在本地 profile 对照（ex01 的姿势）而不是直接改 CI——先量出收益，再决定把哪档配置固化进 Cargo.toml。

### 3.2 优化方法论：先测量 → 定位 → 优化 → 再测

ph19/ph20/ph21 反复预告的「先测量后优化」在本阶段落地为一套四步闭环，project 的 log-aggregator 是它的完整示范：

```text
① 先测量    —— 建基准：criterion 时间 + 分配计数（3.3/3.5）
                ↓  得到基线数字（优化前）
② 定位瓶颈  —— 采样/分配剖析：热点在哪、分配从哪来（3.4/3.5）
                ↓  假设清单：哪一行改动影响最大
③ 做优化    —— 最小的、不改变语义的改动（3.5~3.8）
                ↓
④ 再测      —— 同一基准复测 + 语义一致性断言
                ↓  没变好？回到 ②。变好了？固化成回归测试
```

每一步的纪律：

- **①必须先有「能复现的测量」**：两次 `cargo bench` 结果差在噪声内，才配叫基线。测量的可信度由三件事决定——**黑盒化**（`black_box` 夹住输入与输出，防编译器消除；见 3.3）、**环境控制**（关掉并行负载、固定机器）、**统计口径**（best-of-N / 中位 / 置信区间）。
- **②把「时间慢」翻译成「什么结构慢」**：时间只有一个数，剖析才能告诉你分配、缓存、调用这三层谁在拖。分配次数是比时间更早暴露问题的信号（3.5）。
- **③一次只改一件事**：把「减少分配」和「换容器」和「改布局」混在一次提交里，回归时就不知道是谁的功劳。
- **④优化必须以「语义不变」为验收**：project 用两版聚合器产出的 Report `assert_eq!` 相等来证明——**测量方法论不完整的标志，就是优化后「看起来快了」但没人证明结果还对**。

这个闭环还有一个反方向的应用——**什么时候不该优化**（5 节详述）：冷路径、一次性脚本、语义正在剧烈变化的地方。判断标准只有一个：**如果热路径上量不出它，它就还没资格被优化**。

### 3.3 criterion：把 ph20 的 bench 用法升级为系统方法论

ph20 已经示范了 criterion 的「会用」：写 `#[bench]` 风格的函数、跑 `cargo bench`、看 time/thrpt。本阶段把它升级为**方法论**，四个升级点对应 ex02（已验证）与 roadmap 练习 1：

**① 用 `benchmark_group` 组织对比实验**。一个 group 内展开「规模 × 实现」的多个测量点，criterion 报告给同一张两两对比表（含差异的显著性检验）——单点测时间的价值远低于「同一输入下 A/B」的对照：

```rust
// examples/ex02-criterion-methodology/benches/log_parse.rs —— 摘要
let mut group = c.benchmark_group("log_parse_borrow_vs_owned");
for &n in &[1_000usize, 10_000] {                    // 规模轴
    let lines = sample_lines(n);
    group.throughput(Throughput::Bytes(total_bytes as u64)); // 吞吐轴：声明每轮字节数
    group.bench_with_input(BenchmarkId::new("borrowed", n), &lines, |b, ls| {
        b.iter(|| black_box(run_borrowed(black_box(ls))))     // 输入黑盒
    });
    group.bench_with_input(BenchmarkId::new("owned", n), &lines, |b, ls| {
        b.iter(|| black_box(run_owned(black_box(ls))))
    });
}
group.finish();
```

**② 编译器消除陷阱与 black_box 是基准的第一课**。`b.iter(|| …)` 里的闭包若结果没被消费，LLVM 有权把整段循环优化成空。`std::hint::black_box` 是「告诉编译器：这个值我就是要，不许优化掉」的编译屏障，**必须夹在输入侧与输出侧**。示例中的 `run_borrowed`/`run_owned` 都把每行的解析结果 `black_box` 消费后才累计行数——去掉它会得到「快得不真实的假基准」。

**③ 统计口径**：criterion 默认输出 `time: [低值 中位 高值]` 的 95% 置信区间，再配 `thrpt`（每秒字节/元素）。教学采样配置（warm-up 300ms / measurement 2s / sample_size 20，见各 bench 文件头）是为了让 CI 与教学快速跑完；**正式回归请放宽到默认**（warm-up 3s / measurement 5s / sample_size 100），并连跑两次——第一次包含预热噪声。

**④ 回归检测 = 变化检测的自动化**。criterion 默认只报「相对上次的变化估计」；要它判红，用 `--save-baseline v1` 存档 → 改动代码 → `--baseline v1` 对比，输出 `change` 行的变化区间与显著性 p 值。CI 里把 change 超阈值当失败即可（ph21 模板的「性能回归 job 占位」就是为它留的；criterion 没有内置「超阈值退出非零」开关，判红通常由脚本解析输出完成）。

ex02 实测（本机，10,000 行日志解析）：

| 路径 | time（中位） | 吞吐 | 结论 |
|------|------------|------|------|
| borrowed（零拷贝借用） | 465 µs | 1.10 GiB/s | 借用路径稳定快 ~3.2x |
| owned（每字段 to_string） | 1.48 ms | 353 MiB/s | 复制代价是每行的常数项，随规模线性放大 |

**criterion 输出的标准读法**（ex02 真实输出的精简摘录）：每组给 `time: [下限 中位 上限]` 的 95% 置信区间——区间的宽窄告诉你这次测量的可信度；区间宽说明环境噪声大，先别下结论、先降噪。`thrpt` 与 time 是同一次测量的两种投影（每秒处理量），跨机器比较用 thrpt，同机对比用 time 中位即可：

```text
log_parse_borrow_vs_owned/borrowed/10000lines
        time:   [444.47 µs 465.30 µs 483.79 µs]        ← 区间窄 → 测量可信
        thrpt:  [1.0566 GiB/s 1.0986 GiB/s 1.1501 GiB/s] ← 吞吐（跨机器可比）
log_parse_borrow_vs_owned/owned/10000lines
        time:   [1.4382 ms 1.4843 ms 1.5327 ms]        ← 组内同输入 → 直接对比
```

**回归检测的命令闭环**（CI 判红的落地形态，来自 project/README 的扩展方向）：

```bash
# 1. 优化前：存档当前实现为 v1
cargo bench -- --save-baseline v1
# 2. ……改实现……（一次只改一件事，3.2 纪律）
# 3. 优化后：与 v1 对比，criterion 输出 change 估计与显著性 p 值
cargo bench -- --baseline v1
# 4. CI：解析输出把「p < 0.05 且 change 超阈值」判为失败（ph21 预留 job）
```

### 3.4 采样剖析：flamegraph / perf 与 macOS 替代

基准回答「有多快」，剖析回答「时间去哪了」。Rust 生态的剖析主路径是 **perf（Linux 内核采样器）+ flamegraph（火焰图可视化）**：

```bash
# —— Linux 命令（本机 macOS 无 perf，未在本环境验证）——
cargo install flamegraph                     # 安装 cargo flamegraph（Linux 需 perf）
CARGO_PROFILE_RELEASE_DEBUG=true cargo flamegraph   # 生成 flamegraph.svg：含符号的火图
# 手动等效：
perf record --call-graph dwarf ./target/release/myapp   # 采样并记录调用栈
perf report --stdio                                    # 文本热点报告
perf script | inferno-collapse-perf > stacks.folded   # 折叠成 flamegraph 输入
# macOS 替代（Instruments 采样器 / 系统自带 sample）：
sample <pid> 3 -file profile.txt            # 对运行中的进程采样 3 秒，输出文本调用树
# Instruments.app：Time Profiler 模板 → 选进程 → 录制 → 得到与火焰图同源的调用树
```

**火焰图怎么读**（这是本阶段要建立的核心技能，图例基于 Brendan Gregg 的公开规范，本机未生成火焰图、仅作读图教学）：

```text
─────────────────────────────┬─────────────────────────────
         top frame（叶子，最宽=最热的被采样函数）
─────────────────────────────┘
   x 轴 = 采样占比（宽度=时间占比），y 轴 = 调用栈深度
   找「底部宽、顶部尖」的柱子 → 热调用路径；找「顶部宽平台」→ 单函数自身耗时
─────────────────────────────
```

- **采样原理见 4.1**：perf 按固定频率打断 CPU、记录当前调用栈，函数在采样中出现的次数占比 ≈ 它的 CPU 时间占比。它不改代码（不插桩），开销低，适合对 release 产物直接剖析。
- **三个读图要点**：① 先看**最宽的叶子**（实际干活的函数），不是栈底的 main；② 顺着宽叶子的调用链往上找「谁调了它」（`Self` 宽的顶层函数是内联后的真凶）；③ 火焰图回答「CPU 时间分布」，**回答不了分配次数和等待 I/O**——所以剖析之后通常还要分配剖析（3.5）补齐另一半。
- **没有剖析工具时的退路**（本机验证过、也是本仓库所有测量的兜底）：把可疑函数用计数分配器 + 分块计时夹住（3.5），先确认「这条路径到底花了多少时间/分配」，再决定要不要上采样器。

反复出现的四种火焰图形状对应四种结论（读图决策表）：

| 火焰图形状 | 含义 | 下一步动作 |
|-----------|------|-----------|
| 一根「底部宽、顶部尖」的柱子 | 一条清晰的深热路径 | 沿调用链读出热点函数，直接优化它 |
| 「顶部宽平台」（叶子宽而平） | 单函数自身耗时（可能已内联） | 展开函数看内联来源；考虑 `#[inline(never)]` 分开测 |
| 底部很宽、枝叶散乱 | 没有单一热点，时间摊在很多函数上 | 先看是不是分配/锁问题（配合 3.5/4.3），别急着逐函数优化 |
| 栈底以上大量同宽重复层 | 递归或循环内重复调用同一批函数 | 查外层循环能否整体跳过/缓存（算法层，3.6） |

> 本环境的诚实标注：**perf 是 Linux 工具，macOS 不可用；cargo-flamegraph 本机未安装**——故 flamegraph/perf 的输出**未在本环境验证**。macOS 的官方替代是 Instruments（GUI，Time Profiler 模板）与系统自带 `sample`（命令行，输出文本调用树），命令如上；本仓库代码层的剖析数字全部来自 criterion 基准 + 分配计数 + 分块计时（均可复现），不虚构任何 flamegraph 输出。

### 3.5 内存分配剖析：分配次数计数与「避免分配」三招

「程序慢」在 Rust 里最常见的结构原因是**堆分配比你以为的多**。单次分配 ~几十 ns 很难直接测出，但分配次数会在三处放大代价：**分配器锁**（多线程争用）、**内存碎片与缓存**（新分配的内存不热）、**page fault**（大分配触页）。所以 ph22 把「分配次数」列为与「时间」并列的一等指标——这也是 ph18 预告的「分配次数是首要优化对象」的兑现。

**分配计数的标准姿势**是实现一个包装 `GlobalAlloc` 的计数分配器，用 `#[global_allocator]` 装成进程唯一分配器（examples/ex03 的 counting.rs 与 ex06、project 均内置；40 行，零第三方）。测量段用 `reset() → 干活 → snapshot()` 夹住，得到净分配次数与字节——**计数发生在分配器层，业务代码零改动**：

```rust
// examples/ex03-hotspot-alloc/src/counting.rs —— 核心（摘要）
unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCS.fetch_add(1, Ordering::SeqCst);   // 每次分配 +1
        BYTES.fetch_add(layout.size(), Ordering::SeqCst);
        unsafe { System.alloc(layout) }
    }
    // dealloc 只转发；realloc 也按一次新分配计数
}
#[global_allocator]
static GLOBAL: CountingAllocator = CountingAllocator;
```

ex03 用 ph19/ph20 同款 WAL record 做了定位示范（200,000 条，已验证）：零拷贝回放路径 **0 次分配 / 0.46 ms**；「每条 to_vec 收集建索引」的路径 **400,017 次分配 / 28.6 MB / 8.58 ms**。时间差 18x 是本次的，分配差是结构性的——后者的消除需要改代码姿势而不是改编译器。

「借用还是拥有」的工程判断，project 的 `OptimizedAgg` 给出了一个可复用的生命周期模式：**让输入活过聚合全程，表 key 借用输入，收口时再统一转拥有**（以下为 `project/log-aggregator/src/agg.rs` 的真实代码摘录）：

```rust
// project/log-aggregator/src/agg.rs —— 优化版聚合器（借用的 arena 模式，已验证）
pub struct OptimizedAgg<'a> {
    map: BTreeMap<&'a str, Bucket>,   // key 借用输入行内的切片，全程零临时分配
    bad: u64,
}

impl<'a> OptimizedAgg<'a> {
    pub fn feed(&mut self, line: &'a str) {          // 借用限制：line 必须活到 finish
        let Ok(parsed) = parse_line(line) else {     // 解析零分配（见 src/line.rs）
            self.bad += 1;
            return;
        };
        // 无分配：key 借用 line 内的切片，只有首次出现才写入表
        let bucket = self.map.entry(parsed.service).or_default();
        feed_bucket(bucket, &parsed);
    }

    pub fn finish(self) -> Report {                  // 收口：借用 key 一次性转拥有
        Report {
            services: self.map.into_iter()
                .map(|(svc, b)| (svc.to_owned(), ServiceStat { /* … */ }))
                .collect(),
            bad_lines: self.bad,
        }
    }
}
```

这个模式依赖一个生命周期事实：**日志行集合（Vec\<String\>）在 measure 里活过整个聚合过程**（3.2 的 ①~④ 全程），所以借用安全由 borrow checker 保证，不需要 unsafe。基线与优化版产出的 Report 逐位一致（`assert_eq!` 验证）——**「借用 arena」不是减少语义，而是把「每行都拥有」改成「收口时每个唯一 key 拥有一次」**。

**避免分配的三招**（ex06 逐组实测）：

| 招数 | 写法 A（坏） | 写法 B（好） | 实测分配对比（本机） |
|------|------------|------------|-------------------|
| 复用缓冲 | 每轮 `format!("{k}={v}")` 新建 String | `clear()` + `write!` 复用容量 | 300,000 次 / 6.6 MB → **1 次 / 32 B** |
| `&str` 优先于 String | 收集 `Vec<String>`（每字段 to_string） | 源行存活时收集 `Vec<&str>` | 100,016 次 / 4.0 MB → **16 次**（仅 Vec 扩容） |
| 预留容量 | `Vec::new()` + push | `with_capacity(n)` | 19 次（1M 元素翻倍扩容）→ **1 次** |

第三招「小向量优化」的诚实边界（ex06 实测）：自写栈内嵌 `SmallVec`（≤4 元素在栈上），当集合几乎不溢出时效果惊人——50 万个 3 元素集合 0 分配 vs 普通 Vec 50 万次分配；但集合规模到 40 元素、每集合都溢出时，SmallVec 的堆增长与普通 Vec **完全持平**（各 100 万次）。**inline 缓冲的收益只在「几乎不溢出」时存在**——选它之前先量分布。

> **String vs &str 是 ph02/ph19 的旧知识在性能维度的回响**：`&str` 不是「更快的 String」，而是「不拥有数据的视图」。当数据（日志行、缓冲）能活得比使用点长，视图零分配；当数据必须独立存活（跨函数返回、进结构体），就注定要拥有——那时优化的是**分配次数**（一次 vs 每行一次），不是消灭拥有。

### 3.6 算法复杂度与数据结构选择：先算法，后微调

分配与缓存优化的是常数；**算法与数据结构决定数量级**。Rust 标准库三件套 `Vec` / `HashMap` / `BTreeMap` 的复杂度是 ph03 的知识，本阶段用实测把它变成选择直觉（exercises/sol-03，同一负载「批量插入 n 项 + 查找一半 key」，已验证）：

| 容器 | n=10,000 | n=100,000 | 复杂度特征 |
|------|---------|-----------|-----------|
| Vec + sort + binary_search | 847 µs | 9.88 ms | 插入后排序 O(n log n)、查找 O(log n)，无散列常数 |
| BTreeMap | 702 µs | 7.76 ms | 全操作 O(log n)，节点连续、缓存友好 |
| HashMap | 268 µs | 3.15 ms | 期望 O(1)，散列有常数开销 |

- **HashMap 快 BTreeMap ~2.5x、快 Vec+binary_search ~3x**，两个规模比例稳定——这正是「期望 O(1) vs O(log n)」的数量级差距（log 10⁵≈17 步 vs 1~2 次散列）。
- 但三个「别急着换容器」的提醒：① HashMap 的常数来自**散列成本**，key 越长越复杂（字符串、结构体）差距越小；② 需要**范围遍历/有序输出**时 BTreeMap 无替代品——性能不是唯一坐标；③ n 很小时 Vec 的线性 `find` 常常就够（缓存里 1 万次线性探测 < 散列的乘法开销），**小规模先量再换**。
- 复杂度判断还有一个 ph19 打过底的层面：**隐藏的 O(n)**。`Vec::remove(0)`、字符串 `+` 拼接、`split` 后逐段 `to_string`——这些 API 调用看起来是常数，实际每次 O(n)。分配剖析（3.5）常能暴露这类「隐藏线性」：分配次数突然随规模非线性增长，多半是循环里藏了复制。

**决策顺序**（本阶段立场）：先用复杂度把数量级选对（这是「算法」），再用分配/缓存/内联做常数优化（这是「微调」）——反过来做是本阶段明令禁止的坏习惯，因为常数优化救不了一个 O(n²) 的热循环。

### 3.7 缓存局部性：布局与访问模式

CPU 以**缓存行**为单位搬运内存（本机 Apple M4 Pro：`hw.cachelinesize` 实测 **128 B**，L2 4 MB）。一次「读一个 u64」实际把整条缓存行（16 个 u64）搬进缓存——顺序访问时这 16 个元素全用上（缓存行的胜利）；随机访问时每行只用 1 个、其余 120 B 全浪费。ex04 实测（已验证，1<<23 个 u64 的 gather vs 顺序求和）：

```text
[访问模式] 顺序遍历 8,388,608 元素: 0.79 ms (0.09 ns/元素)
[访问模式] 随机 gather 2,097,152 步: 5.78 ms (2.76 ns/步, 单次读 ≈ 29x 贵)
```

**随机访问比顺序贵 ~29x**——这不是算法问题而是物理：每次 gather 都大概率 miss L2（数据 64 MB ≫ 4 MB L2），代价是内存延迟而非计算。凡是「按索引乱序访问大数组」的代码（哈希表、指针追逐、稀疏索引），都在付这笔账——能改成顺序扫描就改，不能改就把数据集缩小到缓存内。

**数据布局的第二课：AoS vs SoA**。同一批「点」数据，`Vec<Point{x,y,z}>`（Array of Structs）与三条 `Vec<u64>` 列（Struct of Arrays）对「只求 x 的和」的遍历差异，ex04 实测：

| 布局 | 求 x+y+z | 只求 x |
|------|---------|--------|
| AoS（结构体数组） | 1.29 ms | 1.22 ms |
| SoA（列式数组） | 0.98 ms | **0.38 ms** |

SoA 只求 x 时快 **3.2x**——因为 `x` 列连续排布，一次取行全是有效载荷；AoS 里 `x` 每 24 B 才出现一次，取行时 2/3 是暂时用不到的 y/z。**读全字段时 SoA 优势消失**（0.98 vs 1.29 ms）——布局收益跟访问模式绑定。工程启示：数据库列存 vs 行存的争论在内存层同样成立；Rust 里把「热字段」拆列（SoA）、把「一起访问的字段」打包（AoS）是一个低成本高回报的重构，但**先量访问模式再动手**（ph19 的告诫在这里兑现）。

### 3.8 内联与单态化：分发方式与 #[inline]

Rust 的分发方式（ph07 的知识）在性能维度有三档性格：**enum + match**（静态分支）、**泛型单态化**（编译期为每个具体类型生成一份代码，可完全内联）、**`Box<dyn Trait>` 动态分发**（每次调用走 vtable 间接跳转，编译器无法内联）。ex05 用语义等价的三种实现实测（已验证，2×10⁸ 次调用）：

| 分发方式 | time | 相对代价 |
|---------|------|---------|
| enum + match（静态） | 137–167 ms | 1.0x（基线） |
| 泛型单态化（单类型） | 77–107 ms | 最快（单类型全内联） |
| Box\<dyn\> 动态分发 | 228–246 ms | dyn/enum ≈ **1.5–1.7x**；dyn/泛型 ≈ **2.7–3.0x** |

数字读法：dyn 的代价是「间接调用 + 无法内联/常量传播」——语义灵活（异质集合、插件边界）换来的固定税。实践结论不是「永远别用 dyn」，而是**热循环里优先 enum/泛型；dyn 留给边界**（一次调用付出远小于进出边界的场景）。同一组实验还测了 `#[inline(always)]` vs `#[inline(never)]` 对**同一函数体**的差距：约 1.8x（25 vs 45 ms）——内联让调用点免去 call/ret 与参数搬运，但编译器通常自己判断得比人好：

| 注解 | 语义 | 使用纪律 |
|------|------|---------|
| 无注解 | 编译器按成本模型自决（跨 crate 默认不内联，除非 LTO） | 默认 |
| `#[inline]` | 提示：跨 crate 使用时也考虑内联 | 小函数、泛型方法（`#[inline]` 对泛型几乎总是值得） |
| `#[inline(always)]` | 强制内联 | 只在实测证明该调用点是热点时用；滥用会让二进制膨胀、icache 劣化 |
| `#[inline(never)]` | 禁止内联 | 保持调用边界（如避免把大函数复制进每个调用点、控制二进制大小） |

内联与单态化的关系：**单态化是编译期代码生成**（每个类型一份），**内联是把函数体嵌进调用点**——两者叠加就是 Rust「零成本抽象」的兑现路径：泛型方法在小类型上单态化后常被全内联，运行时与手写循环无异。代价在编译期（代码膨胀、编译时间），这正是 LTO/codegen-units 权衡（3.1）的微观基础。

## 4. 底层原理

### 4.1 采样剖析 vs 插桩剖析

perf/flamegraph 与「在函数进出埋计数器」是两类剖析哲学，选错工具会得出相反的结论：

| 维度 | 采样剖析（sampling） | 插桩剖析（instrumentation） |
|------|---------------------|---------------------------|
| 原理 | 定时打断 CPU，记录当时调用栈（如 99 Hz 或 1 kHz） | 编译/运行时在每个函数出入口插入计数器 |
| 开销 | 低（~1–5%），可对生产进程直接采样 | 高（函数调用越频繁开销越大），常改变被测行为 |
| 精度 | 统计性：函数占比 ≈ 时间占比，短函数/低频函数测不准 | 确定性：精确计数 |
| 代表 | Linux perf、macOS sample/Instruments Time Profiler | gprof 的插桩模式、编译期 `-finstrument-functions` |
| 输出 | 火焰图/调用树（占比） | 精确次数与时间表 |

火焰图是采样剖析的可视化：x 轴宽度 = 采样数占比（≈时间占比），y 轴 = 调用栈深度。读图找「宽叶子」（自身耗时最多的函数），再沿调用链向上确认「是谁的热路径」。采样剖析的盲区要记住：**它只见 CPU 不见墙钟**——等锁、等 I/O、被调度器让出 CPU 的时间采样不到；这正是 3.5 要补分配剖析、以及并发程序要配合锁分析的原因。

### 4.2 缓存行与伪共享

缓存行是 CPU 与内存之间的传输单元（本机 128 B）：一行要么在缓存（快，~ns）、要么不在（慢，~100ns 内存延迟）。两个推论是本阶段所有缓存优化的根：

1. **空间局部性决定有效带宽**：顺序遍历时一次取行服务多个元素，理论带宽上限 = 每周期一行 × 行利用率。SoA vs AoS（3.7）的本质就是行利用率：AoS 只读 x 时行利用率 8/24≈33%，SoA 是 100%——3.2x 实测差距正源于此。
2. **伪共享（false sharing）是并发陷阱**：两个线程各自改**不同的变量**，但它们落在同一条缓存行——缓存一致性协议把整行当共享状态来回失效，两个核互相拖慢，实际开销远超各自变量的操作。Rust 里 `Arc<Mutex<T>>` 相邻锁、并发计数器数组都是高危场景。解法是**行对齐隔离**：让被不同线程写的热变量各自占一条缓存行（ph19 提过的 `CachePadded` 惯用法在本阶段有了完整动机）——但要先量出争用再隔离，盲目 padding 浪费内存。

伪共享的几何示意（本机行宽 128 B，两个 8 B 计数器分居行首与行尾仍会被绑在一起失效）：

```text
缓存行（128 B）──────────────────────────────────────┐
  ├ 线程 A 写 counter_a（在行内）                     │
  ├ 线程 B 写 counter_b（也在行内！）                 │
  └ A 每次写 → 整行标记失效 → B 的缓存行同步作废 ◀── 真正被共享的是「行」，不是变量
隔离后：counter_a 独占一行、counter_b 独占另一行 → 各自失效互不牵连
```

值得强调的是一致性协议的粒度**永远是行而不是变量**——代码层「变量不共享」不代表缓存层「行不共享」。Rust 的类型系统能防数据竞争（ph12），但防不了伪共享：两个不相干的 `AtomicU64` 被放得足够近，性能上就等同于被共享。这是「安全的并发」与「快的并发」之间，编译器管不到、必须由布局意识补齐的一层。

### 4.3 分配器与 malloc 行为：为什么分配次数常被低估

Rust 默认 `#[global_allocator]` 是 **System = 平台 malloc**（macOS 上是 libmalloc）。malloc 家族为「快」做了大量工程：小对象走线程本地缓存（tcache）、空闲块复用、大对象走 mmap。后果是**单线程下小分配几乎免费**（ex06/project 实测：分配次数差 2400x、时间只差 1.4x），这让「分配很贵」的直觉在基准里失灵——但这正是把分配次数单独当指标的理由：

- 分配代价在**多线程**显形：tcache 命中率高时各线程互不干扰，一旦线程本地缓存耗尽或对象跨越阈值，就进入全局堆锁/arena 争用——分配次数直接放大为锁等待。
- 分配代价在**生命周期**显形：反复 alloc/free 造成堆碎片与缓存冷（刚 free 的块可能已被逐出缓存）；长跑服务的内存曲线常是「分配次数 × 滞留时间」的函数。
- 分配次数是**结构性可优化**的（改代码姿势即可，3.5），而单次分配成本是分配器的事——**优化者应把火力对准自己可控的次数**。

> 理解 malloc 还解释了为什么「用 jemalloc/mimalloc 换分配器」常被当万能药（project 扩展方向提到）：它优化的是**单次分配成本与并发策略**，不减少次数。次数归你管，单次成本归分配器管——两者都要量，别混为一谈。

### 4.4 LTO 与 codegen-units 的编译期权衡

rustc 的优化分两阶段：**单 crate 内**（rustc 编译本 crate 时对已见代码做优化）与**链接期**（LTO 把所有 crate 的 LLVM IR 汇总后再优化一遍）。codegen-units 决定单 crate 内部分成几个并行编译单元——单元之间看不到对方，所以 cgu=16（默认）比 cgu=1 编译快，但牺牲单元间优化；LTO 则把「看不见」的边界整个打开：

```text
crate A ──▶ LLVM IR ──┐
crate B ──▶ LLVM IR ──┼── 无 LTO：A、B 各自优化后链接（跨边界黑盒）
hotcore ─▶ LLVM IR ──┘
                        └── LTO：全部 IR 合并 → 链接期统一优化（跨边界透明）
```

收益来自三件事：**跨 crate 内联**（小函数调用消失）、**常量传播跨边界**（`pub const` 与可推导值在另一 crate 里被折叠）、**去虚化**（dyn 调用若类型可确定则变直接调用）。代价是链接时间：fat LTO 是全量 IR 的全局优化（最慢），thin LTO 是带索引的增量跨模块优化（温和）。ex01 实测把权衡量化了：fat+cgu1 比默认慢 1.9x 编译、省 12% 体积，而运行持平——**LTO 的 ROI 取决于依赖图里有多少「值得看穿的跨 crate 热边界」**。独立进程或与二进制同构的 crate 值得，巨型依赖树里只有零星热点的值得三思。

## 5. 使用场景

本阶段知识在真实工程里的落点，收敛成一张「何时优化 / 何时不优化」的决策表：

| 场景 | 做什么 / 不做什么 | 理由 |
|------|-----------------|------|
| 有明确延迟 SLO 的服务（p99 超标） | 上采样剖析定位热点 → 分配计数 → 优化热路径 | 用户可感知的延迟是最正当的优化理由 |
| 吞吐型批处理（日志聚合、ETL、解析） | 先建 criterion 基准定基线 → 优化 → 回归 | 吞吐优化的每一步都要有「之前 vs 之后」数字 |
| 库 crate 的公开 API | 内部优化，但**别为基准改 API 形状** | API 稳定性（ph17 的语义化版本纪律）优先于常数优化 |
| 冷路径（初始化、错误处理、一次性 CLI） | **不优化** | 热路径量不出它之前，不值得（3.2 的「先测量」反用） |
| 语义还在变的功能 | 不优化，先直白 | 优化的前提是稳定语义——优化正在改的代码是双重浪费 |
| 已量出「单次分配 ~ns 级」的分配 | 停止逐行微调，改查分配次数与结构 | 别跟 allocator 较劲，跟自己代码里的分配次数较劲（4.3） |
| 怀疑是锁/等 I/O | 用锁分析/墙钟剖析，别用 CPU 火焰图 | 采样剖析不见墙钟（4.1 的盲区） |
| 多线程热数据互相踩 | 查伪共享，考虑行对齐隔离 | 先量争用再隔离（4.2） |

**优化预算**：性能工作是预算制，不是奖励制。一次「先测量 → 优化 → 再测」闭环的合理预算大约是一个下午到两天——超过还看不到数量级改善，大概率是优化对象选错了（该换算法/布局而不是继续微调当前路径）。把预算花在哪由测量指定，但**维护一份「基线库」是预算最好的花法**：project 的 log-aggregator 与 exercises 的 sol-01/sol-03 各留了一组可复现的 criterion 基线，下次改动代码先跑基线再动手——「现在比上周慢 5%」比「我觉得这里应该优化」贵一万倍。这正是 ph20 的回归测试思想从正确性延伸到性能：**性能也该有回归测试，只是断言的不是真值，而是基准差值**。

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）。Rust 与 C++/Go 的性能方法论同源但工具链性格不同：

| 维度 | Rust | C++ | Go |
|------|------|-----|-----|
| 构建期优化入口 | `[profile.*]`（版本化于 Cargo.toml） | `-O2/-O3/-flto` 等编译器 flag + CMake 配置 | `go build -ldflags`（编译器全程序优化内建，几乎无调参空间） |
| 基准事实标准 | criterion（统计显著性 + 回归基线） | Google Benchmark | `testing.B` + `benchstat`（统计对比） |
| 剖析工具链 | perf / cargo flamegraph / Instruments | perf / VTune / gprof | pprof（内置 `net/http/pprof`，含 CPU/堆/goroutine 剖析） |
| 分配剖析 | 计数分配器/`#[global_allocator]`/dhat | 无内建，Valgrind massif / heaptrack | pprof 堆剖析（采样）+ `runtime.MemStats` |
| 分配控制 | 所有权：`&str` vs String、arena、零拷贝是**编译期**可证的 | RAII + 智能指针，靠约定；引用易悬垂 | GC 托管：无法控制分配时机，只能减少压力 |
| 方法论共性 | 采样剖析 + 基准 + 统计对比，三者同源 | 同左 | 同左（pprof 把 CPU/堆合进一个工具） |
| 关键差异 | 分配是编译期可控的（本阶段主线） | 优化器成熟但分配/生命周期靠人守 | 自动 GC 换开发速度，热点分配只能「少产生」 |

跨语言读出的规律：**三家的测量方法论高度同构（采样 + 基准 + 统计），差异全在「分配可控性」**——Rust 的所有权把「减少分配」变成编译期约束（借用让你无法复制）、C++ 靠 RAII 约定与程序员自觉、Go 干脆交给 GC 只求少产生垃圾。**对 Tenet 的启示候选：一门高性能语言的性能底座 = 版本化的构建参数 + 统计性基准框架 + 系统级采样器，而「分配可证地少」是 Rust 独有的卖点——它让 ph22 的「先测量后优化」可以在编译器帮助下收敛到结构性最优，而不是靠人肉 review。** 这些观察在 analysis/ 设计解剖时再深化，本阶段只需收集素材。

## 6. 代码示例

本节展示示例的关键片段，完整工程在 [`examples/`](./examples/)。验证环境：rustc/cargo 1.92.0（macOS arm64）。全部示例均已本机实测，标注「已验证」；flamegraph/perf/Instruments 的系统工具输出未在本环境验证（见 3.4 命令）。逐示例运行命令与实测数字见 [`examples/README.md`](./examples/README.md)。

| 示例 | 对应主文档 | 一句话说明 | 验证状态 |
|------|-----------|-----------|---------|
| [`examples/ex01-profile-config/`](./examples/ex01-profile-config/) | 3.1 | 三档 `[profile]` 的编译/体积/运行对照（含 path 依赖 hotcore 作 LTO 对象） | 已验证 |
| [`examples/ex02-criterion-methodology/`](./examples/ex02-criterion-methodology/) | 3.3 | criterion 方法论：group / Throughput / 借用 vs 复制解析路径 | 已验证 |
| [`examples/ex03-hotspot-alloc/`](./examples/ex03-hotspot-alloc/) | 3.5 | WAL 回放分配热点：计数分配器 + 零拷贝 vs 转 owned | 已验证 |
| [`examples/ex04-cache-locality/`](./examples/ex04-cache-locality/) | 3.7 | 顺序 vs 随机访问 + AoS vs SoA 布局实测 | 已验证 |
| [`examples/ex05-monomorph-inline/`](./examples/ex05-monomorph-inline/) | 3.8 | enum / 泛型 / dyn 分发与 inline 注解对比 | 已验证 |
| [`examples/ex06-alloc-count/`](./examples/ex06-alloc-count/) | 3.5 | 分配次数四组对照：复用缓冲 / &str / with_capacity / 小向量 | 已验证 |

```rust
// examples/ex03-hotspot-alloc/src/main.rs —— 分配热点定位的骨架（已验证）
// 验证环境：cargo 1.92.0；运行：cargo build --release && ./target/release/ex03-hotspot-alloc 200000
// 输出节选（200k 条 WAL record）：
//   Path A 零拷贝回放  : 分配 0 次 / 0 B        耗时 0.46 ms
//   Path B 转 owned 收集: 分配 400017 次 / 28.6 MB 耗时 8.58 ms
counting::reset();                       // 测量窗口开
let t0 = Instant::now();
let sum = replay_owned(black_box(&log)); // 被测路径（这里故意用转 owned 版）
let dt = t0.elapsed();
let (n_alloc, n_bytes) = counting::snapshot(); // 测量窗口关：净分配
```

```rust
// examples/ex05-monomorph-inline/src/main.rs —— 分发方式对比的核心（已验证）
// dyn 路径：每次调用走 vtable，编译器无法内联（实测比 enum 慢 ~1.5x）
fn dyn_dispatch(ops: &[Box<dyn CalcTrait>], n: u64) -> u64 {
    for i in 0..n {
        let op: &dyn CalcTrait = &*ops[(i % ops.len()) as usize];
        acc ^= black_box(op.calc(black_box(seq))); // 间接调用
    }
}
```

## 7. 总结

### 关键要点

- **先测量后优化是本阶段唯一宪法**：没有「能复现的基准」（两次结果在噪声内）就没有优化资格；一次只改一件事；优化必须附「语义不变」的验证（project 用 `Report` 相等断言）——3.2 的四步闭环把 ph19~ph21 的预告兑现成可执行流程
- **`[profile.release]` 是优化的起点不是终点**：opt-level/lto/codegen-units/panic 四键的实际效果与代价，ex01 实测 fat LTO「编译 +1.9x、体积 -12%、运行持平」——LTO 收益只在跨 crate 边界真挡住优化时显性，默认从 thin 起步（3.1）
- **criterion 的价值是统计对比不是单点计时**：group 组织 A/B 实验、`Throughput` 让结果跨机器、`black_box` 双端防编译器消除、`--save-baseline`/`--baseline` 做回归检测——ph20 的「会用」在 ph22 升级为「方法论」（3.3）
- **分配次数是与时间并列的一等指标**：计数分配器让「每行少一次 to_string」变成可量化数字；实测分配次数差 2400x 时时间只差 1.4x——分配的真实代价在锁、碎片与缓存上，单线程微基准测不出（3.5/4.3）
- **结构性格局按序排查**：算法复杂度（数量级）→ 分配次数（结构性）→ 缓存局部性（行利用率）→ 分发方式（dyn/单态化/内联）——sol-03/ex04/ex05 的实测把每层都变成了「可复现的数字」而不是直觉（3.6~3.8）
- **剖析工具要知道盲区**：perf/flamegraph 采样只见 CPU 不见墙钟；macOS 用 Instruments/sample 替代；本机未验证的命令按 3.4 标注（4.1）
- **不优化的勇气**：冷路径、未稳定语义、量不出的「优化」都不该做——优化的正确对象永远由测量指定（5 节决策表）

### 阶段验收清单

- [ ] 能说清 `[profile.release]` 四个键各改什么、各付什么代价；能在本机跑三档 profile 对照并解释「为什么这次 LTO 没带来运行时收益」（roadmap 验收「能定位主要瓶颈而非微调冷路径」的起点）（3.1）
- [ ] 能写出带 `benchmark_group` + `Throughput` + `black_box` 的 criterion 基准，并解释「编译器消除陷阱」为什么会让基准假快（3.3）
- [ ] 能用计数分配器量出某段代码的分配次数/字节，并指出「分配次数高而时间不高」该如何解释（3.5/4.3）
- [ ] 能说出采样剖析与插桩剖析的区别、火焰图怎么读、perf/flamegraph 在 macOS 上的替代命令；能如实区分本机已验证与未验证的工具（3.4/4.1）
- [ ] 能对同一负载给出 Vec/HashMap/BTreeMap 的实测对比，并解释为什么 HashMap 的常数会随 key 复杂度变化（3.6）
- [ ] 能设计并解释一个缓存局部性或分发方式实验（AoS/SoA、顺序 vs 随机、enum vs dyn），给出本机数字（3.7/3.8）
- [ ] 能对一段可优化代码执行完整「先测量→定位→优化→再测」闭环，并以**优化前后数据对比**（含语义一致性断言）收尾——roadmap 验收「能在优化前后给出数据对比」「能在优化中不牺牲正确性和可维护性」（3.2/project）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。三题与 roadmap 第 22 节练习一一对应：练习 1 =「为热点函数建立基准」（sol-01：借用 vs 复制解析，实测 ~9x 差距），练习 2 =「减少临时 String 分配」（sol-02：500k 行 format! 990,000 次分配 vs 复用缓冲 1 次，时间 4.2x），练习 3 =「比较 Vec、HashMap、BTreeMap 的性能」（sol-03：HashMap 快 ~3x）。三题都要求以**优化前后数据对比**为验收形态。完成 3 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**日志聚合性能优化（log-aggregator）**——roadmap 第 22 节推荐项目落地：基线版 + 优化版两种聚合器、criterion 基准、分配计数、p50/p95 输出与语义一致性校验，验收标准为「给出优化前后 p50/p95 与分配次数对比」（本机实测：分配 200,077 → 82 次，p50 0.204 → 0.146 ms，两版报告逐位一致）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（本机跑出 `measure` 对比表 + criterion bench + 语义一致断言）

### 跨语言对比

- Rust/C++/Go 的性能方法论同源（采样 + 基准 + 统计），差异全在「分配可控性」：Rust 所有权把减少分配变成编译期约束、C++ 靠 RAII 约定、Go 靠 GC + 少产生垃圾——这是 Rust 在数据基础设施场景的差异化卖点（为 analysis/ 与 Tenet 合成积累素材，详见 5 节对比表）

### 下一阶段

**ph23 Rust FFI 与跨语言接口设计阶段**（roadmap 第 23 节，目录待建）——本阶段优化的都是 Rust 进程内路径；下一阶段回答「当热点必须跨语言协作时怎么设计边界」：extern "C" ABI、cdylib、所有权与内存释放规则跨边界、pyo3 加速模块——届时本阶段的「分配在哪一侧」思考会换成「分配由谁负责」，把 ph22 的性能纪律带过 FFI 边界。
