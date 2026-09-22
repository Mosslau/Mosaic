# examples —— C++ 向量检索与 AI 推理引擎方向阶段完整示例

验证环境（实测）：macOS arm64，Apple clang 21.0.0（`/usr/bin/clang++`，默认 PATH）+ Homebrew clang 21.1.8（`/opt/homebrew/opt/llvm/bin/clang++`，交叉核对）、libc++。**ex01~ex06、ex08 均已在本环境 `clang++ -std=c++20 -Wall -Wextra` 编译零警告、运行断言全绿（退出码 0）**；ex03 另做 Homebrew clang 交叉编译核对（SIMD 数字双编译器同量级）。ex07 依赖 Faiss：本机 brew 写入受限，故 faiss 1.9.0 采用 **/tmp 源码构建**（摘除 OpenMP 强制依赖 + 自备 omp 桩头/桩库满足编译链接，单线程 generic 构建），ex07 已借此实测——编译零错误，唯一 warning 来自 faiss 第三方头文件内部（`unused parameter 'id'`，非本文件代码），绝对 QPS 与官方发行版不同，看曲线不看绝对值。以下命令在 examples/ 目录内执行；可执行文件一律输出到 /tmp，数据/快照文件一律写 /tmp 且退出自删，仓库不落二进制。

代码遵循 cpp-coding-standards：无裸 new/delete（R.11，容器与 unique_ptr 拥有资源）、`const`/`enum class` 默认、文件描述符 RAII 封装（ex06）、教学性简化以注释注明。

| 文件 | 对应主文档 | 一句话内容 | 验证状态 |
|------|-----------|-----------|----------|
| `ex01-distance-metrics.cpp` | 3.1 | L2 / Inner Product / Cosine 定义、恒等式、归一化后三排序同序实证 | 已验证（Apple clang 21.0.0） |
| `ex02-brute-force-topk.cpp` | 3.2 | flat top-k（容量堆维护）+ 与全排序 ground truth 对照 + QPS 实测 | 已验证（Apple clang 21.0.0） |
| `ex03-simd-distance.cpp` | 3.3 | 距离 SIMD：标量基线 / 手写 NEON / `-O3 -ffast-math` 自动向量化，三种构建同机实测 | 已验证（Apple clang 21.0.0 + Homebrew clang 21.1.8） |
| `ex04-hnsw-toy.cpp` | 3.4 | toy HNSW：随机层高插入 + 分层图 + ef 搜索，recall 与耗时对暴力检索实测 | 已验证（Apple clang 21.0.0） |
| `ex05-metadata-filter.cpp` | 3.6 | metadata filter：search-then-filter vs filter-then-search（倒排 tag），谓词检查次数断言 | 已验证（Apple clang 21.0.0） |
| `ex06-index-persistence.cpp` | 3.7 | 向量索引持久化：定长 header + id 表 + 行主序矩阵 + FNV 校验尾；temp+fsync+rename；篡改检测 | 已验证（Apple clang 21.0.0） |
| `ex07-faiss-bench.cpp` | 3.5/3.8 | Faiss：Flat / IVF(nprobe 扫描) / HNSW(efSearch 扫描) 的 recall-延迟曲线（聚类高斯数据） | 已验证（Apple clang 21.0.0 + faiss 1.9.0 /tmp 源码构建） |
| `ex08-inference-serving-concepts.cpp` | 3.9 | 推理服务概念（CPU 确定性账本模型）：KV Cache 字节公式、(batch,seq) 内存表、continuous batching 调度模拟 | 已验证（Apple clang 21.0.0，验证的是账本模型输出） |

## 统一编译运行命令

```bash
# 在 examples/ 目录内执行（产物一律输出到 /tmp）：
clang++ -std=c++20 -O2 -Wall -Wextra ex01-distance-metrics.cpp -o /tmp/ph23-ex01 && /tmp/ph23-ex01
# 其余示例把文件名与输出名替换即可；每个文件头注释自带编译/运行命令与验证状态。
# ex03 需按"三形态"分别编译（标量基线 / 手写 NEON / 自动向量化），命令见其文件头。
```

## 示例 1：三种距离度量（ex01-distance-metrics.cpp）

对应主文档 3.1 与 roadmap §23 练习「L2/cosine/IP 三种距离计算」。教学点：① L2 是几何距离（越小越近）、IP 同时编码方向与长度（越大越相似，**长向量作弊**）、cosine 只看方向；② 恒等式 `|a-b|²=|a|²+|b|²-2a·b` 实测成立；③ 归一化后 IP ≡ cosine；④ 同一库上对比排序：未归一化库中 IP 偏好长向量（实测 ip 的 top-3 与 cos 的 top-3 不同），L2 归一化后 l2/ip/cos 三种排序**逐位一致**——这就是 Faiss `IndexFlatIP + 归一化替代 cosine` 的依据。

## 示例 2：暴力 topK 检索（ex02-brute-force-topk.cpp）

对应主文档 3.2 与 roadmap §23 练习「brute-force vector search」。教学点：① 全库线性扫 + 「容量 k 的最大堆」维护 top-k，召回恒 1.0（与全排序 ground truth 逐位对照断言）；② 数据行主序连续存放（缓存友好）；③ 实测 QPS/平均 µs（本机：n=5000×64 维 ≈ 109 µs/query）；④ 距离计算是唯一热点 → ex03 接续 SIMD。

## 示例 3：SIMD 距离计算（ex03-simd-distance.cpp）

对应主文档 3.3 与 roadmap §23 练习「距离 benchmark + SIMD 优化」。教学点：三条实现路径（标量串行链 / 手写 NEON 4 宽累加 / 编译器自动向量化）+ 基准纪律（L2 内数据防带宽压扁、预热、7 轮取中位数、volatile sink 防死代码消除——开发时踩过 `-O3 -ffast-math` 下整段循环被删除的坑）。实测（Apple clang 21.0.0，dim=128、数据 4MB L2 内）：

```text
-O2:             l2_scalar  49.4 ns/op     l2_neon  17.9 ns/op   → 2.76x
-O3 -ffast-math: l2_scalar  14.6 ns/op     l2_neon  14.9 ns/op   → 标量被自动向量化 ≈ NEON
Homebrew clang -O2 交叉核对: l2 加速比 2.78x（同量级）
```

> ⚠️ 数字为单机参考，重跑会有 ±10% 波动；结论看加速比不看绝对 ns。

## 示例 4：toy HNSW（ex04-hnsw-toy.cpp）

对应主文档 3.4 与 roadmap §23 练习「HNSW 节点/邻接表/基础搜索」。教学点：① HNSW = "跳表的图版"（高层稀疏长程、层 0 密集收尾）；② 插入：随机几何分布层高 + 高层贪心下潜 + 各层 ef 搜索就近连边（双向 + 超容换最远，无启发式剪枝的教学简化）；③ 搜索：上层贪心到层 0 → ef 搜索；④ 参数 M/efConstruction/efSearch 决定"召回-内存-延迟"三角。实测（n=2000、dim=16、M=8、efC=64、efS=48）：

```text
recall@10 = 98.55%；同机同 query：HNSW 36.4 µs vs brute force 115.9 µs（≈3.2x，用 1.45% 召回率换）
```

## 示例 5：metadata filter（ex05-metadata-filter.cpp）

对应主文档 3.6 与 roadmap §23「metadata filter」。教学点：① 向量 + 标量联合过滤的生产形态；② 两种工程路线：search-then-filter（全扫 + 边扫边过滤）vs filter-then-search（tag 倒排缩小候选再复查）；③ 铁律：倒排候选集必须逐条复查全部谓词；④ 实测（n=20000、20% 命中率差场景）：

```text
高选择性谓词(t3 & price<8): A=77µs/20000次谓词检查 | B=24µs/5381次 → 3.2x
低选择性谓词(t5 & price<95): A=349µs | B=321µs → 差距消失（flat 场景距离次数相等，B 只省谓词检查）
```

结论与主文档 3.6 一致：flat 场景差距来自谓词检查次数与访存；上 ANN 索引后，metadata 先挡掉"不该碰的向量"，差距放大为"昂贵距离计算的次数差"。

## 示例 6：向量索引持久化（ex06-index-persistence.cpp）

对应主文档 3.7 与 roadmap §23「向量索引持久化」——**ph22 预告兑现**。教学点：文件布局借鉴 ph22 SSTable（定长 header + id 表 + 行主序矩阵 + 整文件校验尾），不可变文件三步写盘（temp + fsync + rename 原子替换），读盘先校验后暴露（损坏即拒绝服务）；实测 8000×32 维快照 1,056,028 字节（≈1.03× 原始向量），篡改数据区一字节即被校验拦截。与 ph22 的关系：本示例是"单代快照"，生产向量库 = 快照 × N 代 + WAL 增量（ph22 的 WAL/Compaction 心智直接平移）。

## 示例 7：Faiss 三索引 bench（ex07-faiss-bench.cpp）

对应主文档 3.5/3.8 与 roadmap §23「使用 Faiss 建索引测召回率」。教学点：① `index_factory("结构,度量")` 是理解 Faiss 工程结构的入口，train/add/search 生命周期显式；② Flat 恒 recall=1.0（精确基线）；③ 用**聚类高斯数据**（Faiss 官方 demo 同款形态）扫 nprobe / efSearch，观察 recall 与耗时同向。实测（Apple clang 21.0.0 + faiss 1.9.0 /tmp 构建，聚类高斯 n=100000×64 维）：

```text
Flat(L2)          recall=1.0000    102.0 µs/query
IVF200,nprobe=1   recall=0.3205     12.4 µs/query
IVF200,nprobe=10  recall=0.9660     79.5 µs/query
IVF200,nprobe=100 recall=1.0000    526.2 µs/query
HNSW32,efSearch=16   recall=0.2835   12.0 µs/query
HNSW32,efSearch=64   recall=0.3375   41.5 µs/query
HNSW32,efSearch=256  recall=0.4130  243.2 µs/query
```

> ⚠️ 均匀随机数据是 ANN 的最坏情形（无结构可挖），且 faiss flat 走 BLAS 矩阵乘——所以"ANN 必须快过 flat"不成立；本机 faiss 为无 OpenMP 单线程构建，绝对 QPS 仅供参考，请复跑核对。

安装/编译（依赖 faiss）：

```bash
# 方案 A（brew 可用机器）：brew install faiss
clang++ -std=c++17 -O2 -Wall -Wextra ex07-faiss-bench.cpp -o /tmp/ph23-ex07 -lfaiss && /tmp/ph23-ex07
# 方案 B（本机验证路径，/tmp 源码构建）：见 ex07 文件头注释（含 omp 桩的完整命令）
```

## 示例 8：推理服务概念 CPU 账本（ex08-inference-serving-concepts.cpp）

对应主文档 3.9 与 roadmap §23「KV Cache / batching / serving runtime 概念」。教学点：① KV Cache 字节公式（由模型结构唯一决定：2×层数×kv头×头维×token×字节）；② MHA vs GQA 的 KV 账本对比（同为 7B 量级：512 KiB/token vs 128 KiB/token）；③ (batch, seq) 在 40GiB KV 预算下的占用表；④ continuous batching 事件模拟（槽位补满即新请求）。**定位声明**：本示例是确定性账本 + 调度模型（所有数字可由代码公式复核），不是 GPU benchmark——真实吞吐/延迟需 NVIDIA 环境实测（本机无 GPU，未在本环境验证 GPU 数字）。

## 验证状态汇总

| 示例 | 工具链 | 状态 |
|------|--------|------|
| ex01-distance-metrics | Apple clang 21.0.0 | 已验证（零警告、断言全绿） |
| ex02-brute-force-topk | Apple clang 21.0.0 | 已验证 |
| ex03-simd-distance | Apple clang 21.0.0（-O2 与 -O3 -ffast-math）+ Homebrew clang 21.1.8 | 已验证（三形态、双编译器） |
| ex04-hnsw-toy | Apple clang 21.0.0 | 已验证 |
| ex05-metadata-filter | Apple clang 21.0.0 | 已验证 |
| ex06-index-persistence | Apple clang 21.0.0 | 已验证 |
| ex07-faiss-bench | Apple clang 21.0.0 + faiss 1.9.0（/tmp 源码构建） | 已验证（recall-延迟曲线；单线程 generic 构建） |
| ex08-inference-serving-concepts | Apple clang 21.0.0 | 已验证（账本模型输出；GPU 部分未在本环境验证） |
