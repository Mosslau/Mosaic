# exercises —— 性能优化与 Profiling 阶段练习

三题与 roadmap 第 22 节练习一一对应，每题一个参考实现目录 `sol-XX/`，**先自己做，做完再看**。每题标注难度（★~★★★）。练习对象可以取自己以前阶段的 crate，也可以直接复用本阶段的材料：`examples/ex02-criterion-methodology` 与被测对象 `project/log-aggregator` 的解析+聚合都是现成热点。

**实证纪律（本阶段所有练习的铁律）**：每道题的验收都要求「优化前后数据对比」——只有数字能证明优化有效，这正是 roadmap 验收「能在优化前后给出数据对比」的训练形态。

验证环境：rustc/cargo **1.92.0**（macOS arm64，rustup 管理），edition 2021，criterion 0.8（本机缓存 0.8.2）。构建产物统一落 `/tmp`，仓库零二进制残留。参考实现的通用质量闸门一致：

```bash
# 在任一 sol-XX 目录内执行
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/tmp/ph22-ex-solXX-target   # XX 换成题号
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

## 练习 1：为热点函数建立基准（★★）

**目标**：写一个规范的 criterion 基准来「先测量」，作为后续所有优化的出发线（roadmap 练习「为热点函数建立基准」）。

**要求**：取一个你怀疑「还能更快」的函数（可以是 `examples/ex02` 的日志行解析，或 `project/log-aggregator` 的 `OptimizedAgg::feed`，或自选）。为它建立基准：benchmark_group 组织、`Throughput` 声明工作量、`black_box` 夹住输入输出防编译器消除；给出两种数据规模。参考实现给的是「`key:value` 记录拆字段」的借用 vs 复制两个版本——你可以把它整体替换成自己的被测函数。

**提示**：基准首先要能**稳定复现**——两次 `cargo bench` 结果差在噪声内才能当基线；`sample_size`/`measurement_time` 太小会让数字抖动到不可信（主文档 3.3）。

**验收**：`cargo bench` 输出完整的 time 区间与吞吐（GiB/s 或 elements/s）；把被测函数改差一档（例如把借用改成每字段 `to_string`），`cargo bench` 应能测出差异——用数据说明你的基准「有分辨力」。
参考实现：`sol-01-hotspot-bench/`。

## 练习 2：减少临时 String 分配（★★★）

**目标**：给一个频繁产生临时 `String` 的处理函数做「减配优化」，量化分配次数与字节的下降（roadmap 练习「减少临时 String 分配」）。

**要求**：取一段每轮都做字符串拼接/收集的代码（自写或复用 `examples/ex06` 的 demo），用全局计数分配器测出**优化前**分配次数/字节；然后用「复用缓冲 + `write!`」或「改用 `&str` 借用」等方式改造，再测**优化后**；把两组数字摆出来（允许用 `examples/ex03-hotspot-alloc` 或 `examples/ex06-alloc-count` 里现成的计数分配器——注意 `#[global_allocator]` 每二进制只能装一个，自己 crate 里复制一份）。

**提示**：分配的代价不在单次 ~几十 ns，而在 allocator 锁与内存碎片随分配次数放大（主文档 3.5）；比较时**次数与字节要分开看**——`Vec::with_capacity` 次数少但预留给的字节可能更大。

**验收**：给出「优化前 vs 优化后」的分配次数与分配字节对比表，并解释：为什么有的场景分配次数降了几个数量级、耗时却变化不大（对照 `project` 的 measure 输出想这个问题）。
参考实现：`sol-02-temp-string-alloc/`。

## 练习 3：比较 Vec、HashMap、BTreeMap 的性能（★★）

**目标**：同一批「批量插入 + 按键查找」工作负载，用三种容器各实现一遍，用 criterion 给出对比数据（roadmap 练习「比较 Vec、HashMap、BTreeMap 的性能」）。

**要求**：生成 `n` 个不重复 key（如 `k000001`）和同量 value；对三种容器执行相同的操作序列：批量插入 `n` 项 → 再查找其中一半 key。Vec 用 `sort_unstable` + `binary_search`（线性 `find` 也可以做一个对照）。跑两个规模（如 1 万与 10 万）分别给数据。

**提示**：这是「算法与数据结构选择」的实测课——HashMap 均摊 O(1) 但哈希有常数开销、BTreeMap O(log n) 但缓存友好、Vec+binary_search 无散列开销但插入要排序；哪个赢取决于 n 与 workload（主文档 3.6）。先写基准再下结论，别凭印象。

**验收**：给出三容器在两个规模下的插入/查找耗时表；能解释「什么时候 BTreeMap 会反超 HashMap」「为什么小规模 Vec 常常够用」。
参考实现：`sol-03-collections-compare/`。

做完三题后，「先测量 → 定位 → 优化 → 再测」的闭环已经有手感了——去 `project/` 把它完整落到「日志聚合性能优化」上。
