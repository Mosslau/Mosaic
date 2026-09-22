# ph22 阶段项目：日志聚合性能优化（log-aggregator）

对应 roadmap 第 22 节推荐项目「日志聚合性能优化：从基准出发降低处理延迟和内存占用」。落地为完整 cargo 工程 `log-aggregator/`：**基线版 + 优化版两种聚合器 + criterion 基准对比 + 内存分配计数 + 双版本语义一致性校验**，验收产出「优化前后 p50/p95 与分配次数对比」。

## 需求

一个把海量文本日志行解析并聚合的处理器：每行 `2026-09-04T10:00:00.123Z INFO svc=auth op=login latency_ms=42`，按 `svc` 分组统计行数与延迟分布（p50/p95）。两种实现语义完全一致：

- **基线版 `BaselineAgg`**：每行把 service 复制成 `String` 再入表（无论是否已存在都付一次堆分配），典型的「能跑但从不考虑分配」；
- **优化版 `OptimizedAgg`**：输入行在整个聚合期存活，聚合表的 key **借用**行内切片，只有新 service 首次出现才写一次 key；临时 `String` 全部消失。

优化手段刻意选「语言级」（借用/生命周期），而不是换算法——目的不是赢在哈希还是 B 树，而是示范 **Rust 所有权模型把「减少分配」从代码规范变成编译期可证明的约束**：优化版不通过 unsafe、不改输入格式，只是让 borrow checker 保证每行零拷贝进出。

## 目录与功能清单

```text
log-aggregator/
├── Cargo.toml            # 无运行时第三方依赖；criterion 0.8 仅 dev
├── src/
│   ├── lib.rs            # 公开 API
│   ├── line.rs           # 日志行解析（借用实现，返回 &str 字段）
│   ├── agg.rs            # BaselineAgg（基线）/ OptimizedAgg（优化）
│   ├── report.rs         # 聚合报告 + p50/p95 百分位
│   ├── counting.rs       # 全局计数分配器（仅 bin 需要）
│   └── bin/measure.rs    # 测量入口：时间 + 批延迟 p50/p95 + 分配次数
├── benches/
│   └── agg_compare.rs    # criterion：两版时间与吞吐对比
└── tests（内嵌 #[cfg(test)]）  # 语义一致性 / 脏行 / 百分位
```

- [x] 两种聚合器 `feed → finish` 同一 `Report`（数据语义可断言相等）
- [x] `measure` 命令行输出双版本 p50/p95（每批 2000 行处理延迟的分布）与分配计数
- [x] criterion bench 报告时间区间与行/秒吞吐
- [x] 质量闸门：fmt / clippy `-D warnings` / test 全绿

## 验收标准

在 `project/log-aggregator/` 目录内执行：

```bash
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/tmp/ph22-proj-target
cargo test          # ① 9 个测试全绿：含「两版报告必须一致」
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo build --release
./target/release/measure 200000      # ② 输出对比表（见下）
cargo bench                          # ③ criterion：两版时间/吞吐
```

**② 实测对比表（本机 macOS arm64 / cargo 1.92.0，200,000 行 = 100 批）：**

| 版本 | 分配次数 | 分配字节 | p50（批 ms） | p95（批 ms） |
|------|---------|---------|-------------|-------------|
| 基线版 | 200,077 | 3,262,438 | 0.204 | 0.545 |
| 优化版 | 82 | 2,362,394 | 0.146 | 0.219 |

- 分配次数下降 **≈2440x**（每行 1 次 → 每行 0 次，剩余 82 次是表节点与延迟 Vec 增长）
- 单批 p50 延迟下降 **≈1.4x**、p95 下降 **≈2.5x**（单线程小分配在时间上不贵——分配的真实代价在多线程 allocator 争用与内存带宽上放大）
- 语义校验：两版报告完全一致（5 服务 / 200,000 行 / 0 脏行）——**优化没有改变正确性**

**③ criterion 实测（教学采样配置）：**

```text
aggregate/baseline_5000lines     time: 606 µs   thrpt: 8.25 Melem/s
aggregate/optimized_5000lines    time: 437 µs   thrpt: 11.44 Melem/s   (≈1.39x)
aggregate/baseline_50000lines    time: 5.69 ms  thrpt: 8.79 Melem/s
aggregate/optimized_50000lines   time: 4.65 ms  thrpt: 10.74 Melem/s   (≈1.22x)
```

**验收口径（对应 roadmap「能定位主要瓶颈而非微调冷路径」）**：交付物必须同时给出 **时间（p50/p95、吞吐）** 与 **内存（分配次数/字节）** 两组对比，并能解释「为什么分配次数差了 2400 倍而时间只差 1.3 倍」——本机的答案是单线程小分配近乎免费；把这个工程扔进多线程、或用真实 allocator 压力场景，分配次数的代价才会在时间上显形。这正是 ph22「分配次数是一等测量指标」的论据。

> **验证说明**：上述全部数字均为本机实测（cargo 1.92.0，macOS arm64，Apple M4 Pro），标注「已验证」。`flamegraph`/`perf`/Instruments 采样**未在本环境验证**，替代命令见主文档 3.4。

## 优化闭环对照（与主文档 3.2 的「先测量→定位→优化→再测」对应）

```text
先测量  criterion/counting 建基线        → 分配 200,077 / p50 0.204 ms
定位    分配计数显示热点=每行的临时 String  → 82 次里 200,000 次来自 BaselineAgg::feed
优化    借用 arena：key=&str 借用行内切片   → 每行零分配
再测    measure + bench 复测              → 分配 82 / p50 0.146 ms，报告逐位一致
```

## 扩展方向

- **接 ph25 数据基础设施**：把 `line.rs` 的文本解析换成 WAL/SSTable 二进制 record（ph19/ph20 的格式），聚合器与优化闭环原样复用——本工程就是「数据基础设施的通用解析+聚合路径」的优化样板（roadmap 第 25 节）。
- **多线程压力**：用 `std::thread` 多线程灌日志，观察分配器争用让分配次数的代价在 p50/p95 上显形（ph12 的并发知识 + 本阶段的测量方法）。
- **接入 CI 性能回归**：用 `cargo bench -- --save-baseline` + 阈值判红，把本工程挂进 ph21 模板预留的性能 job（ph21 project 扩展方向已留位）。
- **换 jemalloc/mimalloc**：本机 system allocator 下分配免费，换 tcmalloc 系 allocator 重测，理解 allocator 行为对测量的影响（对应主文档 4.3）。
