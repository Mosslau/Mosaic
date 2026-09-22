# exercises —— 测试体系进阶阶段练习

四题与 roadmap 第 20 节练习与学习内容对应，全部围绕**同一个被测对象**：共享迷你 record 解析器 crate `record-parser/`（结构复刻 ph19 阶段项目的 WAL record 解析器，格式见其主文档 3.8）。它自带 8 条单元测试与 1 条 doctest，你**不许改解析器，只许加测试**——这正是「回归测试守护成品」的姿态。

每题一个参考实现目录 `sol-XX/`，全部用 cargo crate 组织（需要 proptest/criterion 的题在 dev-dependencies 里声明）。**先自己做，做完再看**。每题标注难度（★~★★★）。

验证环境：rustc/cargo **1.92.0**（macOS arm64）；proptest **1.11.0**、criterion **0.8.2**。每个 sol 的通用质量闸门一致：

```bash
# 在任一 sol-XX 目录内执行（以 sol-01 为例）
export PATH="$HOME/.cargo/bin:$PATH"
cd exercises/sol-01-anomaly-matrix
CARGO_TARGET_DIR=/tmp/ph20-target cargo test
CARGO_TARGET_DIR=/tmp/ph20-target cargo fmt --check
CARGO_TARGET_DIR=/tmp/ph20-target cargo clippy --all-targets -- -D warnings
# 需要 proptest / criterion 的题
PROPTEST_CASES=2048 CARGO_TARGET_DIR=/tmp/ph20-target cargo test   # sol-03
CARGO_TARGET_DIR=/tmp/ph20-target cargo bench                       # sol-04
```

**验证说明**：`record-parser/` 与 sol-01~sol-04 均已在 cargo 1.92.0 本机实测——`cargo test` 全绿、sol-04 `cargo bench` 可跑通、fmt/clippy `-D warnings` 全绿，标注「已验证」。

## 练习 1：异常样例矩阵 + 数据夹具（★★）

**目标**：为解析器补上「每种坏输入至少一个固定样例」的异常矩阵（roadmap 练习「为解析器加入异常样例测试」）。
**要求**：在测试目录里建 `tests/fixtures/`，用 `.hex` 文本格式存样例（`#` 注释说明意图 + 十六进制字节，可参考 examples/ex02 的格式约定）；样例至少覆盖：合法 Put / 合法 Delete / 坏魔数 / 未知 op / CRC 失败（翻转一个字节）/ key 长度越上限 / 头部内截断 / key 内截断 / 空文件 / 恰好 25 字节边界；再写一个「case 表驱动」的矩阵测试逐个断言「该 Ok 的 Ok、该报哪类错就报哪类错」，外加一个**逐截断点全扫**测试（对一段合法双段日志的每个截断点，语义必须单调：只吐完整前缀、遇截断报 `Truncated` 并终止、绝不 panic）。
**提示**：用 `record-parser` 的 `WalWriter` 生成合法字节，再在脚本/小工具里改字节造坏样例（CRC 字段对不上没关系——你需要的就是「改了别处、CRC 没跟着改」的损坏输入）；夹具一旦落成文件就应保持不变。
**验收**：新增任意一个坏样例 = 加一个 `.hex` + 矩阵里加一行；全量扫描与字段级断言全过；`record-parser` 一行未改。
参考实现：`sol-01-anomaly-matrix/`。

## 练习 2：集成测试目录组织 + 共享模块 + 假引擎（★★）

**目标**：把「解析 → 落地成语义」的完整链路按集成测试目录组织起来（对应学习内容「单元测试与集成测试目录」「test fixtures」）。
**要求**：为 `record-parser` 的 `records` 迭代器写 3 个以上集成测试文件（`tests/` 下每个文件是独立 crate），共享构造辅助放 `tests/common/mod.rs`；在测试里实现一个**假引擎**（fake：Put 覆盖写、Delete 删除、记录操作日志），验证真实链路「文件 → 字节 → 解析 → 应用」；至少覆盖：Put 覆盖、Delete 删除、操作顺序、损坏点之后不再应用（引擎只拿到前缀）。
**提示**：先想清楚被测对象与测试替身的边界——解析器是纯函数，把它「应用」进一个实现 `apply(seq, op, key, value)` 语义的模型，就是 fake 的最小形态。
**验收**：`cargo test` 下能看到多个集成测试目标分别运行；共享模块不重复实现；引擎的最终态与操作日志都可断言。
参考实现：`sol-02-integration-tree/`。

## 练习 3：proptest 测边界输入（★★★）

**目标**：用 proptest 补手写样例覆盖不到的盲区（roadmap 练习「用 proptest 测边界输入」）。
**要求**：自定义策略——合法 record 的 key 长度 1..=64、value 长度**钉在 0/1/64/65 边界附近**（用权重混合的 `prop_oneof!` 或 `prop_flat_map` 组合），另有一个「任意字节」策略；性质至少三条：任意字节（0..=1023）解析永不 panic；`WalWriter` 编码 → 解析 roundtrip 逐字段相等；Delete 记录的 value 必为空。再补两个非性质断言：klen 声明为 `MAX_KEY + 1` 报 `TooLarge`、恰好等于 `MAX_KEY` 时不触发闸门但缺字节报 `Truncated`。
**提示**：编码必须走被测对象自己的 `WalWriter`，否则「编码 bug 互相抵消」；让 proptest 失败一次，观察它打印的 `minimal failing input`（那就是收缩）。
**验收**：加大 `PROPTEST_CASES` 后仍全绿；坏性质（如把 Delete 的 value 断言成非空）能被快速反例打脸。
参考实现：`sol-03-proptest-boundary/`。

## 练习 4：criterion 对比「优化前 vs 优化后」（★★★）

**目标**：用基准回答 ph19 留下的问题——零拷贝解析比「每条复制成拥有数据」快多少（roadmap 练习「用 criterion 对比优化前后性能」）。
**要求**：在 `benches/` 写 criterion 基准：v1「优化前」把整段日志解析成拥有数据的快照（key/value 各 `to_vec()` 一次）；v2「优化后」用 `records` 借用流式迭代零分配。用 `benchmark_group` + `BenchmarkId` 扫 2~3 个「record 数 × value 宽度」尺寸，`Throughput::Bytes` 报吞吐；显式配置 warm-up/measurement/sample_size 并注释说明「正式结论应放宽回默认」。
**提示**：防止编译器把空转优化掉——用 `std::hint::black_box`（criterion 0.8 已弃用 `criterion::black_box`）；先跑通再谈数字。
**验收**：能跑出每个尺寸两列 `time`/`thrpt`；用自己的话解释小 value 大条数时 v2 优势更明显的原因（分配次数 vs memcpy 带宽）；用 `--save-baseline v1` 与 `--baseline v1` 各跑一次，能读出 `change` 行的区间与 p 值。
参考实现：`sol-04-criterion-compare/`（跑法与主文档 3.6/ex05 一致）。

做完四题后，你对「异常样例、目录组织、属性轰炸、基准量化」四种测试姿势都有了肌肉记忆——去 `project/` 把它们合成一个完整测试套件。
