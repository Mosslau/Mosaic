# examples —— Rust 数据基础设施专项阶段完整示例

对应主文档 `25-data-infrastructure.md` 第 6 章。八个示例把 roadmap §25 的学习内容切成一条「存储 → 检索 → 服务 → Agent 工具」的组件链：**ex01 WAL（崩溃恢复）→ ex02 SSTable + Bloom（不可变有序文件/点查加速）→ ex03 Compaction（归并语义与放大）→ ex04 Mini Raft（单节点日志复制状态机）→ ex05 HNSW toy（图索引四件套指标）→ ex06 Axum（KV HTTP 服务）→ ex07 pyo3（Python 加速模块）→ ex08 Agent 工具后端（权限/超时/审计/可观测）**——ex06~ex08 需要网络拉取第三方依赖，ex01~ex05 纯 std 零依赖。

验证环境：rustc/cargo **1.92.0**（macOS arm64，stable-aarch64-apple-darwin）；Python **3.13.12**（`/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3`）。构建产物统一落 `/tmp`（每个示例一个 `CARGO_TARGET_DIR`），仓库零二进制残留。

## 示例清单与验证状态

| 示例 | 对应主文档 | 一句话说明 | 验证状态 |
|------|-----------|-----------|---------|
| `ex01-wal-replay` | 3.1 | WAL append/sync/replay + torn tail 截断修复 + 位翻转拦截（磁盘格式与 C/ph16、cpp/ph22 对齐） | **已验证**（8 测试全绿） |
| `ex02-sstable-bloom` | 3.2/3.3 | SSTable writer/reader（稀疏索引 + 块内升序）+ Bloom 假阳性实测 + range scan | **已验证**（6 测试全绿） |
| `ex03-compaction-sim` | 3.4/4.1 | 归并语义（覆盖丢弃/tombstone 到底才真删）+ 读写放大与归并节奏取舍实测（参照 cpp/ph22 ex06 模型） | **已验证**（6 测试全绿） |
| `ex04-mini-raft-state-machine` | 3.5 | 单节点 Raft：term/index 日志、commit→apply、崩溃恢复重放；选举概念退化形态 | **已验证**（5 测试全绿） |
| `ex05-hnsw-toy` | 3.6 | HNSW 多层图 toy：recall@10 / QPS / P95 / 内存四件套实测 + 暴力对照 | **已验证**（5 测试全绿） |
| `ex06-axum-kv-service` | 3.7 | Axum KV/range-scan HTTP 服务：State 共享、统一 JSON 错误、curl 冒烟 | **已验证**（3 测试 + HTTP 冒烟） |
| `ex07-pyo3-accelerate` | 3.8 | pyo3 0.23.5 Python 加速模块：帧解析 + L2/top-k（abi3 免链 libpython） | **已验证**（Python 3.13 import + verify.py 全过） |
| `ex08-agent-tool-backend` | 3.9 | Agent 工具后端：Tool trait / scope 权限 / 超时 / 审计日志 / 指标端点 | **已验证**（4 测试 + HTTP 冒烟） |

实测依赖版本（Cargo.lock）：axum **0.8.9**、tokio **1.53.1**、serde **1.0.229**、serde_json **1.0.151**、async-trait **0.1.92**、tower **0.5.3**（dev）、pyo3 **0.23.5**（abi3-py311）。全部命令输出为本机实跑；HNSW QPS/P95 与 verify.py 计时类数字会随机器负载浮动（README 记录的是某一次实测值）。

## 通用质量闸门（每个含 Cargo.toml 的目录内执行）

```bash
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/tmp/ph25-ex<NN>-target   # 仓库零二进制残留的关键
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test --release
```

## 运行命令与实测输出

### ex01：WAL append / replay / 崩溃恢复（纯 std）

```bash
cd examples/ex01-wal-replay
CARGO_TARGET_DIR=/tmp/ph25-ex01-target cargo run --release
# 实测输出（三场景摘要）：
#   [场景 1] 干净日志重放：Clean { applied: 3, last_seq: 3 }
#   [场景 2] 残尾日志重放：TornTail { applied: 2, last_seq: 2, offset: 39 }
#   [场景 2] 截断后重放：Clean { applied: 3, last_seq: 3 }
#   [场景 3] 位翻转重放：Corrupt { applied: 1, last_seq: 1, offset: 32, error: ChecksumMismatch { … } }
# 8 个单测（含 IEEE CRC 向量 crc32("123456789")==0xCBF43926、残尾/位翻转/越界长度）
```

### ex02：SSTable + Bloom（纯 std）

```bash
cd examples/ex02-sstable-bloom
CARGO_TARGET_DIR=/tmp/ph25-ex02-target cargo run --release
# 实测输出（2000 键、block 预算 128B）：
#   文件 88141 B | 667 块 | 2000 条 | Bloom m=32768 bits (16 bits/key), k=11
#   [点查] key1234 → value-of-key01234 （读块 1 次）
#   [Bloom] 2000 个不存在的 key 中 0 个被判 maybe（假阳性率 0.000%）
#   [Bloom] 2000 个已写 key 全过 Bloom：假阴性 = 0
#   [scan] key00100..=key00119 → 20 条（读块 8 次）
#   [tombstone] bravo 读出的是删除标记 / alpha 读出的是值 / 不存在 key → None
```

### ex03：Compaction 归并模拟（纯 std；模型参照 cpp/ph22 ex06）

```bash
cd examples/ex03-compaction-sim
CARGO_TARGET_DIR=/tmp/ph25-ex03-target cargo run --release
# 实测输出：
#   [1] full compaction: 6 条/92 B -> 2 条/31 B；覆盖丢弃 3，tombstone 真删 1
#       点查不存在 key：3 run 探测 3 次 → 合并后 1 次（读放大 3 → 1）
#       空间：物理 92 B / 有效 31 B（空间放大 2.97x）
#   [2] 非底层归并保留 tombstone（防旧值复活），到底层才真删
#   [3] 12 次 flush：每次全量归并写 13767 B，攒 4 次归并写 3809 B
#       平均读放大（12 次采样）：A=1.00（恒单 run）vs B=2.00（攒批期间累积）
#       命中一致性 A=24/B=24（攒批只影响性能指标，不影响正确性）
```

### ex04：Mini Raft 单节点状态机（纯 std）

```bash
cd examples/ex04-mini-raft-state-machine
CARGO_TARGET_DIR=/tmp/ph25-ex04-target cargo run --release
# 实测输出摘要：
#   [选举] term 0 → 1，投自己一票，单节点簇 majority=1/1 立即当选，append no-op 并提交
#   [写路径] put alpha=1 / put beta=2 / put alpha=10 / del beta，每条 append→commit→apply
#   [恢复] 丢弃内存状态机仅凭日志重放 5 条 → 状态机回到 {"alpha":"10"}（与崩溃前一致）
# 5 个单测：选举 term 递增/日志 index 连续/写路径有序应用/重复 apply 幂等/恢复重建
```

### ex05：HNSW toy 四件套（纯 std，确定性数据）

```bash
cd examples/ex05-hnsw-toy
CARGO_TARGET_DIR=/tmp/ph25-ex05-target cargo run --release
# 实测输出（N_build=2000 DIM=8 M=8 ef_c=64 ef_s=120 top_k=10，本机某次）：
#   构建：83.0 ms，图总边数 32832，层数 8，内存占用 ≈ 455.1 KiB（按结构成员计算估计）
#   查询：recall@10 = 0.831，QPS = 16166，P95 延迟 = 0.133 ms
#   暴力对照：QPS = 25163
#   结论打印在运行输出里：2k×8 维小尺度上图索引收益未显性——recall/QPS 是调参权衡
```

### ex06：Axum KV HTTP 服务（网络依赖）

```bash
cd examples/ex06-axum-kv-service
CARGO_TARGET_DIR=/tmp/ph25-ex06-target cargo run --release   # 默认 127.0.0.1:8090
# 另一个终端：
curl -s -X PUT http://127.0.0.1:8090/kv/temperature -H 'content-type: application/json' -d '{"value":"36.5"}'
curl -s http://127.0.0.1:8090/kv/temperature
curl -s -X PUT http://127.0.0.1:8090/kv/humidity -H 'content-type: application/json' -d '{"value":"68"}'
curl -s -X PUT http://127.0.0.1:8090/kv/pressure -H 'content-type: application/json' -d '{"value":"1013"}'
curl -s 'http://127.0.0.1:8090/kv?start=h&end=pressure'   # range scan（闭区间）
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE http://127.0.0.1:8090/kv/temperature  # 204
curl -s http://127.0.0.1:8090/kv/temperature               # {"error": …} [404]
# 本机实测输出见主文档 3.7 与 README 上表；3 个测试（含 HTTP 路由冒烟）
```

### ex07：pyo3 Python 加速模块（网络依赖 + Python 3.13）

```bash
cd examples/ex07-pyo3-accelerate
CARGO_TARGET_DIR=/tmp/ph25-ex07-target cargo build --release   # 产物 libph25_accel.dylib
mkdir -p /tmp/ph25-py
cp /tmp/ph25-ex07-target/release/libph25_accel.dylib \
   /tmp/ph25-py/ph25_accel.cpython-313-darwin.so
PYTHONPATH=/tmp/ph25-py /Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3 verify.py
# 实测输出：
#   [1] parse_frames 正常流 → [b'abc', b'de', b'']；坏流抛 ValueError（残尾/截断）
#   [2] l2_distance/bruteforce_topk 正确性通过
#   [3] 暴力 top-k（N=20000, dim=8）：Rust 2.9 ms vs 纯 Python 15.9 ms（本机一次实测）
#   verify.py 全部通过
```

注意：pyo3 extension-module crate 的 `cargo test` 需要把解释器符号链进测试二进制，本环境的可重定位 Python 不便嵌入——测试走 Python 侧 `verify.py`（已验证），这也是 pyo3 社区对 extension crate 的常规做法。macOS 下链接由 `.cargo/config.toml` 提供 `-undefined dynamic_lookup`。

### ex08：Agent 工具后端（网络依赖）

```bash
cd examples/ex08-agent-tool-backend
CARGO_TARGET_DIR=/tmp/ph25-ex08-target cargo run --release   # 默认 127.0.0.1:8091
# 另一个终端：
curl -s -X POST http://127.0.0.1:8091/tools/call -H 'content-type: application/json' \
     -H 'x-client-id: writer' -d '{"tool":"kv.put","input":{"key":"voltage","value":"12.8"}}'
curl -s -X POST http://127.0.0.1:8091/tools/call -H 'content-type: application/json' \
     -H 'x-client-id: reader' -d '{"tool":"kv.get","input":{"key":"voltage"}}'
curl -s -w ' [%{http_code}]\n' -X POST http://127.0.0.1:8091/tools/call -H 'content-type: application/json' \
     -H 'x-client-id: reader' -d '{"tool":"kv.put","input":{"key":"x","value":"1"}}'   # 403
curl -s -w ' [%{http_code}]\n' -X POST http://127.0.0.1:8091/tools/call -H 'content-type: application/json' \
     -H 'x-client-id: admin' -d '{"tool":"debug.sleep","input":{}}'                    # 504 超时
curl -s http://127.0.0.1:8091/metrics     # {"by_decision":{"allowed":2,"denied":1,"timeout":1}, …}
curl -s http://127.0.0.1:8091/audit       # 审计 JSON 行（只记 key 不记 value）
```

## 每个示例的看点

- **ex01**：append 返回 ≠ 持久化（fsync 才可承诺）；魔数先行 → 长度上限 → CRC 的四道校验顺序；残尾用「文件尾 > 已解析位置」判定并 `ftruncate` 修复——engine 层 WAL 与 ph19 解析器的关系是「字段同源、校验范围升级」（本格式 CRC 覆盖整段，连 op/长度字段一起验，这是与 C/ph16、cpp/ph22 对齐的取舍）。
- **ex02**：SSTable 不可变有序文件 + 稀疏索引二分定位块 + Bloom 无假阴性拦截；`get` 只读 1 块而 `scan` 读全区间块——读盘面的差异在这里是可见的结构属性，不是猜的。
- **ex03**：归并是「用 seq 保序去重 + tombstone 到底才真删」；非底层归并丢 tombstone 会让旧值复活；攒批降写放大但推迟读放大——「何时 compaction」是 LSM 的运维杠杆。
- **ex04**：Raft 在单节点也成立的部分 = 先日志后状态机 + commit→apply 顺序 + 崩溃重放幂等；多节点部分（quorum/RPC/心跳）只做概念说明。
- **ex05**：四件套指标必须来自真实测量——recall 需要暴力真值、QPS/P95 来自 `Instant` 计时、内存按结构成员计算并标注口径；toy 尺度下诚实承认图索引尚未跑赢暴力。
- **ex06**：Axum 的 `State` 共享 + `Arc<Mutex>` 并发面；统一 JSON 错误用 `IntoResponse`；range scan 变成 URL 查询参数——服务面把 ex02 的语义原样暴露。
- **ex07**：ph23 pyo3 技能的复用落点：abi3 免链 libpython、`#[pyfunction]`/`#[pymodule]`、错误用 `PyErr` 类型而不是 panic 越界；正确性测试在 Python 侧（`verify.py`）。
- **ex08**：工具边界 = 权限（scope 集合 × required_scope）+ 超时（每工具预算 + `tokio::time::timeout`）+ 审计（JSON 行，记 key 不记 value）+ 指标（按工具/决策计数）——`Box<dyn Tool>` 注册表让 Agent 框架层能枚举与调用，而框架层本身不属本阶段。

## 阅读顺序建议

按主文档 3.1→3.9 推进：先 ex01~ex03 把存储三层（WAL→SSTable→Compaction）跑通，ex04 看单机版的一致性状态机，ex05 切到向量检索，再 ex06/ex08 把它们接到 HTTP 与工具调用面，ex07 说明「Python 要快就调 Rust」的出口——project/ 把 ex01~ex06/ex08 的形态合体成「Mini LSM KV + Axum HTTP + Agent 工具 API」的三合一收官工程。

## 验证状态汇总

- ex01~ex05（纯 std）：**已验证**，测试数 8/6/6/5/5 全绿，`clippy -D warnings` 与 `fmt --check` 通过
- ex06/ex08（axum）：**已验证**，测试 3/4 全绿 + HTTP 冒烟实测；依赖版本 axum 0.8.9 / tokio 1.53.1
- ex07（pyo3）：**已验证**（构建 + Python 3.13 import + verify.py）；`cargo test` 因 extension-module 需嵌入解释器而未在本环境跑通，测试形态为 Python 侧（如实标注）
- 无任何命令输出为虚构；计时/内存类数字以你本机复现为准
