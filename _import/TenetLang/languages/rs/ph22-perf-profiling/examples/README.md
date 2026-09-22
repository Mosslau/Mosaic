# examples —— 性能优化与 Profiling 阶段完整示例

对应主文档 `22-perf-profiling.md` 第 6 章。六个示例从「构建参数 → 基准方法论 → 分配剖析 → 缓存 → 分发 → 分配计数技巧」递进，全部围绕同一纪律：**先测量，后优化**。示例对象刻意选用 ph19/ph20 同款「WAL record / 日志行解析」域，示范的是「优化方法论」，不是新领域。

验证环境：rustc/cargo **1.92.0**（macOS arm64，rustup 管理），edition 2021。所有例子除注明外**零第三方依赖**；`ex02` 使用 criterion 0.8（dev-dependencies，本机缓存 0.8.2）。构建产物统一落 `/tmp`（`CARGO_TARGET_DIR`），仓库零二进制残留。全部示例均**已验证**（cargo fmt --check / clippy --all-targets -- -D warnings / cargo test 全绿；实测数字如下表与各文件头注释）。

> ⚠️ 微基准数字只在「本机 + 本工具链 + 本输入」下成立。复现时以你机器上跑出来的值为准——**这本身就是「先测量」的第一课**：任何写死的性能结论都值得被怀疑。

## 示例清单与实测数字

| 示例 | 对应主文档 | 一句话说明 | 实测数字（本机） | 验证状态 |
|------|-----------|-----------|-----------------|---------|
| `ex01-profile-config` | 3.1 | 同一 crate × 三档 `[profile]`：编译时间 / 体积 / 运行 | 冷编译 1.38 / 2.69 / 3.05 s；体积 445,392 / 390,656 / 420,976 B；3×10⁸ 次调用 5 轮中位 201 / 219 / 201 ms（噪声内持平） | 已验证 |
| `ex02-criterion-methodology` | 3.3 | criterion 系统方法论：group / throughput / 回归基线 | 借用 10k 行 465 µs（1.10 GiB/s）vs 复制 1.48 ms（353 MiB/s）≈ **3.2x** | 已验证 |
| `ex03-hotspot-alloc` | 3.5 | WAL 回放：零拷贝 vs 转 owned 的分配热点定位 | 200k 条：A 路径 **0 次分配 / 0.46 ms**；B 路径 400,017 次 / 28.6 MB / 8.58 ms | 已验证 |
| `ex04-cache-locality` | 3.7 | 访问模式（顺序 vs 随机）与布局（AoS vs SoA） | 随机 gather 单次读 ≈ 顺序的 **29x**；SoA 只求 x 比 AoS 快 **3.2x** | 已验证 |
| `ex05-monomorph-inline` | 3.8 | enum / 泛型单态化 / `Box<dyn>` 分发与 inline 注解 | dyn 比 enum 慢 ~1.5x、比泛型慢 ~2.7x；`#[inline(never)]` 比 `#[inline(always)]` 慢 ~1.8x | 已验证 |
| `ex06-alloc-count` | 3.6 | 分配计数四连：复用缓冲 / `&str` vs `String` / with_capacity / 小向量 | format! 300,000 次 vs 复用 1 次；`Vec<&str>` 收集 16 次 vs `Vec<String>` 100,016 次；with_capacity 19→1 次 | 已验证 |

## 运行命令

```bash
export PATH="$HOME/.cargo/bin:$PATH"

# ex01：三档 profile 对比（运行标签为命令行传入，见 src/main.rs 头注释）
cd examples/ex01-profile-config
CARGO_TARGET_DIR=/tmp/ph22-ex01-target cargo build --release        # 445 KB / ~1.4s
CARGO_TARGET_DIR=/tmp/ph22-ex01-target cargo build --profile release-lto        # 391 KB / ~2.7s
CARGO_TARGET_DIR=/tmp/ph22-ex01-target cargo build --profile release-thin-abort # 421 KB / ~3.1s
/tmp/ph22-ex01-target/release/ex01-profile-config 300000000 release
/tmp/ph22-ex01-target/release-lto/ex01-profile-config 300000000 release-lto
/tmp/ph22-ex01-target/release-thin-abort/ex01-profile-config 300000000 release-thin-abort

# ex02：criterion 方法论（group 报告 + save-baseline 回归检测）
cd ../ex02-criterion-methodology
CARGO_TARGET_DIR=/tmp/ph22-ex02-target cargo bench
CARGO_TARGET_DIR=/tmp/ph22-ex02-target cargo bench -- --save-baseline v1   # 存档基线
# 改实现后：cargo bench -- --baseline v1  对比（输出 change 估计与显著性）

# ex03：分配热点定位（可带记录数参数）
cd ../ex03-hotspot-alloc
CARGO_TARGET_DIR=/tmp/ph22-ex03-target cargo build --release
/tmp/ph22-ex03-target/release/ex03-hotspot-alloc 200000

# ex04：缓存局部性（先确认本机缓存行：sysctl hw.cachelinesize）
cd ../ex04-cache-locality
CARGO_TARGET_DIR=/tmp/ph22-ex04-target cargo build --release
/tmp/ph22-ex04-target/release/ex04-cache-locality

# ex05：静态 vs 动态分发与 inline（可选迭代次数参数，默认 4e8，建议 2e8）
cd ../ex05-monomorph-inline
CARGO_TARGET_DIR=/tmp/ph22-ex05-target cargo build --release
/tmp/ph22-ex05-target/release/ex05-monomorph-inline 200000000

# ex06：分配次数对照
cd ../ex06-alloc-count
CARGO_TARGET_DIR=/tmp/ph22-ex06-target cargo build --release
/tmp/ph22-ex06-target/release/ex06-alloc-count
```

## 每个示例的看点

- **ex01**：同一个程序用三种 `[profile]` 构建——Cargo 默认 release、`lto="fat"+codegen-units=1`（roadmap 示例形态）、`lto="thin"+panic="abort"`。实测教学点比「LTO 更快」更有价值：**默认 release 与 fat LTO 的运行差异落在噪声内**（本机 3×10⁸ 次跨 crate 调用 5 轮中位 201 vs 219 ms），而 fat LTO 的编译时间代价明确（2.7s vs 1.4s）、体积收益明确（-12%）。结论不是「别开 LTO」，而是「LTO 的收益要在跨 crate 边界真正挡住优化的场景才显性，先量再开」——`acc` 校验和两档一致证明三档跑的是同一份语义。
- **ex02**：把 ph20 的 criterion 用法升级成方法论。`benchmark_group` 内 2 规模 × 2 路径共 4 个测量点共享同一份显著性比较报告；`Throughput::Bytes` 让结果能跨机器比（GiB/s）。数字给了一个干净结论：**复制路径稳定慢 ~3.2x、吞吐 ~1/3**，且不随行数放大比例变化（10k 行 465 µs vs 1.48 ms）——分配次数把「每次 to_string」摊在每行的常数成本上。
- **ex03**：WAL 回放的两条路径在**分配维度**差异比时间维度大得多：200k 条 record 时 A（零拷贝借用）0 次分配，B（每条 to_vec 收集建索引）400,017 次 / 28.6 MB。时间的 18x 差距是**本次**的、分配差距是**结构性**的——这解释了为什么 ph22 把「分配次数」与「时间」并列为第一等测量。
- **ex04**：两个经典效应在 M4 Pro（L2 4MB、缓存行 128B）上实测。随机 gather 单次读 ~2.8 ns vs 顺序 ~0.09 ns（**~29x**）；AoS 与 SoA 求同一列 x：SoA 0.38 ms vs AoS 1.22 ms（**快 3.2x**）。注意 SoA 的优势在「只读部分字段/可向量化」时放大；读全字段时差距消失（0.98 vs 1.29 ms）——**布局优化的收益跟访问模式绑定，别盲目 SoA**。
- **ex05**：语义等价的分发，三种写法性能分层稳定：`enum+match`（静态）≈ 最快、泛型单态化紧随、`Box<dyn>` 动态分发慢 ~1.5x（相对 enum）/~2.7x（相对泛型单类型）。`#[inline(always)]` 与 `#[inline(never)]` 对同一函数体的差距 ~1.8x。教学点：dyn 的代价是「间接调用 + 无法内联/常量传播」——它在**异质集合/插件边界**才值得，热循环里优先 enum/泛型。
- **ex06**：四组「写代码就少分配」的对照，全用同一个 40 行的计数分配器测出（分配发生在 GlobalAlloc 层，业务代码零改动）。其中「小向量」一组的诚实结论值得记：集合恒 ≤4 元素时栈内嵌确实 0 分配（50 万集合 0 vs 50 万次）；一旦集合大到 40 元素，SmallVec 溢出后的扩容分配与普通 Vec 完全持平——**inline 缓冲的收益只在「几乎不溢出」时存在**。

## 阅读顺序建议

按主文档 3.1→3.8 推进：先看 ex01 理解「优化前提是选对构建参数」，再 ex02 建立「怎么测才可信」，接着 ex03/ex06 认识「分配是第一测量对象」，ex04/ex05 理解「缓存与分发的结构性格局」。每看完一组就去 `exercises/` 做对应一题，最后到 `project/` 合成完整闭环。

## 验证状态汇总

- 全部六个示例：**已验证**（cargo 1.92.0 本机实测；数字见上表，均取本机串行运行，best-of-N/中位等口径见各程序头注释）
- flamegraph / perf / Instruments 采样命令不在 examples 内运行（见主文档 3.4 与文件头），**未在本环境验证**——它们的系统命令以主文档与 project/README 为准。
