# ph23 阶段项目：vsearch —— SIMD 加速的 brute-force 向量检索库 + 快照持久化

> 对应 roadmap §23「推荐项目」的**落地选择**：把「brute-force vector search（工程化）+ SIMD 距离计算 + 向量索引持久化 demo」合成一个可独立构建的检索库，并输出 roadmap 阶段验收要求的 **recall / QPS / P95 延迟 / 内存占用** 实测表。roadmap §23 其余推荐项目的去向：HNSW toy → examples/ex04（端到端建图+搜索）、Faiss benchmark → examples/ex07 + exercises/练习 5、TensorRT plugin demo → 主文档 3.11（无 GPU，概念+伪码，未在本环境验证）、推理服务 batching 原型 → examples/ex08（CPU 账本模型）、Python 调用 C++ 向量检索库 → ph20 已给 pybind11 路线（本 project 接口为纯 C++，pybind11 包装是 ph20 的既有练习）。

## 需求

做一个嵌入式 flat 检索库 `vsearch`：

- **建库**：`add(id, vec)` 任意条；行主序连续存储；三种度量 l2 / inner product / cosine（cosine 与 l2 预存 ||v||²，查询时用恒等式省一次向量扫描）
- **检索**：`search(query, k)` 单查询 O(N·D)；**SIMD 加速距离内核**（arm64 NEON，`make bench_scalar` 可产出同一源码的标量版对照）
- **持久化**：`save(path)` / `load(path)`——快照文件布局与 examples/ex06 同源（ph22 SSTable 心智平移：**定长 header + id 表 + 行主序矩阵 + 整文件 FNV-1a 校验尾**；写盘 = temp + fsync + rename 原子替换；读盘先校验后暴露，损坏即拒绝服务不修复），用源码注释注明该出处
- **测量**：bench 模式输出 recall（对照独立 double ground-truth）、QPS、P50/P95/P99 延迟、内存占用（索引账本 + 进程峰值 RSS）

## 功能清单

- [x] `vsearch.h` / `vsearch.cpp`：pimpl 接口（unique_ptr 持 impl，R.20）+ NEON/标量双后端（`VSEARCH_FORCE_SCALAR` 编译期开关，R.11 无裸 new/delete）
- [x] `main.cpp`：`selftest`（metric 正确性 / 检索对照 double ground truth / 持久化 round-trip + 篡改检测）+ `bench [N] [DIM] [NQ] [K] [metric]`
- [x] Makefile：`make` / `make test` / `make bench` / `make bench_scalar` / `make cross` / `make sanitize` / `make clean`

## 验收标准

- [ ] `make clean && make test` 退出码 0：selftest 5 项断言全绿（已验证）
- [ ] `make bench` 与 `make bench_scalar` 输出实测表（数字见下节；两版为同一源码不同后端）
- [ ] recall 行 = 1.0000（flat 精确检索，对照**独立** double 全排序，非自证）
- [ ] 能输出 QPS、P95（排序样本 95 分位）、内存（索引账本 MiB 与进程峰值 RSS MiB）
- [ ] 持久化：save→load 后检索结果逐位一致；篡改快照一字节 → `load` 抛错（已验证）
- [ ] `make cross`（Homebrew clang 21.1.8）零警告断言全绿；`make sanitize`（ASan/UBSan）零报告（已验证）
- [ ] `make clean` 零残留（产物与数据文件全在 /tmp）
- [ ] 能口头说清：为什么查询用恒等式 `d²=|a|²+|q|²-2a·q` 比逐元素差平方省一次访存；为什么快照能"损坏即拒绝服务"（不可变 + 校验尾）；NEON 版与标量版数字差距受什么限制（内存带宽 vs 计算）

## 实测（本机：macOS arm64，Apple clang 21.0.0，`make bench` / `make bench_scalar` 同参数 100000×64 维、300 查询、k=10）

```text
== vsearch bench: n=100000 dim=64 nq=300 k=10 metric=l2 backend=NEON  ==
build(仅 add):  12.6 ms | 索引内存账本 33.5 MiB | 进程峰值 RSS 87.3 MiB
recall@10   :  1.0000（精确检索，对照独立 double ground truth）
QPS         :  1102
latency     :  P50 654 µs | P95 1810 µs | P99 2356 µs

== vsearch bench: n=100000 dim=64 nq=300 k=10 metric=l2 backend=scalar ==
build(仅 add):  8.8 ms | 索引内存账本 33.5 MiB | 进程峰值 RSS 87.3 MiB
recall@10   :  1.0000
QPS         :  601
latency     :  P50 1170 µs | P95 3373 µs | P99 4237 µs
```

- **QPS 加速比 ≈ 1.83x**（1102 / 601），P50 延迟 ≈ 1.79x——真实数字随机器与频率波动，可重跑核对
- 说明：每查询要流式读全库 25.6MB（100000×64×4B），已部分受内存带宽影响；ex03 的 L2 内小数据形态加速比更高（≈2.5~2.8x）——SIMD 收益的上限由"计算受限还是带宽受限"决定
- recall = 1.0000 是 flat 检索的性质（非 ANN 近似），跑 `bench` 时对每个 query 对照 double 全排序 ground truth 复核

## 运行

```bash
make clean && make test         # 1. 自测（验收入口，退出码 0）
make bench                      # 2. SIMD 版实测表
make bench_scalar               # 3. 同一源码标量版实测表 → 与 2 对照
make cross                      # 4. Homebrew clang 21.1.8 交叉核对（可选）
make sanitize                   # 5. ASan/UBSan 复跑（先 make clean）
make clean                      # 6. 清理 /tmp 产物与数据
```

## 教学简化与取舍（源码注释已注明）

- 单线程、纯内存 flat 索引（无磁盘分页/Buffer Pool——需要时把 examples/ex04 帧缓存接上即生产形态）
- top-k 用"有序数组截断"（k 小、k 比较可忽略），换透明度；k 大时应换容量堆（见 examples/ex02）
- 快照是**整库一次性快照**（flush 语义）；增量写入要 WAL/段合并（ph22 的 WAL+Compaction 心智，见主文档 3.7）
- 校验用 FNV-1a（教学级，非 CRC32）；文件字节为宿主机小端（跨平台需显式字节序，ph22 大端纪律）

## 扩展方向（与路线的关系）

- **ANN 化**：把 `search` 内核换成 HNSW 图搜索（examples/ex04 已备好）或接 Faiss（examples/ex07/练习 5）——flat 精确检索的上限在 QPS，ANN 用召回率换 QPS
- **Buffer Pool + 页缓存**：快照文件按页读入、LRU/Clock 淘汰（examples/ex04），不整文件读内存
- **WAL 增量 + 后台合并**：add 先写日志、定时 flush 成新快照、合并旧快照——ph22 project Mini LSM KV 的"向量版"
- **pybind11 包装**：ph20 路线已铺（C++ 检索库给 Python AI 生态当高性能扩展层，呼应 roadmap §23 必会概念）
- **TensorRT/CUDA 后端**：本库的检索循环在 GPU 上即"一个归约 kernel"；CUDA 与 TensorRT 属主文档 3.10/3.11（无 GPU 环境，未在本环境验证）
