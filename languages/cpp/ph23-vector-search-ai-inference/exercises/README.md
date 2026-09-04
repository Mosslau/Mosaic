# ph23 C++ 向量检索与 AI 推理引擎方向阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。题目与参考实现分离：本 README 只出题，答案在 `sol-*` 文件里，做完再看。

完成顺序建议：按 1~5 顺序完成，与 roadmap §23「练习」小节一一对应（brute-force vector search / L2·cosine·IP 三种距离计算 / 距离 benchmark + SIMD 优化 / HNSW 节点与邻接表基础搜索 / 用 Faiss 建 IVF/HNSW 索引测召回率）。卡住先看 examples/ 的手法：距离定义看 `ex01`、暴力 top-k 看 `ex02`、SIMD/自动向量化实测看 `ex03`、图索引搜索流程看 `ex04`、持久化看 `ex06`。**每题参考实现均已实测**（验证命令与状态见文末汇总；练习 5 依赖 faiss，本机走 /tmp 源码构建验证，命令见 sol-05 文件头）。

> ⚠️ 通用验收基线：`clang++ -std=c++20 -Wall -Wextra` 编译零警告、运行断言全绿、退出码 0；性能测量必须取多次中位数并消费结果（防编译器消除）；数据/文件一律 /tmp，仓库不落二进制。

## 练习 1：brute-force vector search（★★）

- **目标**：实现一个 flat 检索类：全库扫描 + 容量 k 的最大堆维护当前 top-k，返回 (id, 平方 L2)
- **要求**：
    - 类接口至少含 `add(id, vec)` 与 `search(query, k)`；内部向量按行主序连续存放
    - 距离计算循环手写（不准用 `std::inner_product` 等一步到位库函数——先体会循环形态）
    - 正确性：对若干 query 与"全排序 ground truth"逐位对照 top-k 的 id 与距离
    - 边界：k 大于库容量、库为空、向量维度不一致要可诊断报错
    - 数据规模与随机种子自定义（不要照抄 ex02 的规模/种子）
- **验收**：≥3 个 query 的 top-k 与全排序结果完全一致；k>N 时返回全部；空库查询不崩溃（参考实现 `sol-01-brute-force-search.cpp`）
- **提示**：用「距离更大的在堆顶」的最大堆淘汰最差候选；先写出朴素版再量距离调用次数

## 练习 2：L2 / cosine / inner product 三种距离（★）

- **目标**：手写三种距离并验证它们的数学性质（不许直接用 `std::inner_product`）
- **要求**：
    - 各自独立写循环实现；文档注释写清每个的几何含义与"何时用哪个"（一张小表）
    - 性质断言：L2 对称且 ≥0；cosine 值域 [-1,1]；对任意 a、b，`|a-b|² = |a|²+|b|²-2a·b`
    - 归一化后 `cos(a,b) == IP(a/|a|, b/|b|)`（容差 1e-4）
    - 造一组"长度悬殊但方向相同"的向量对，证明：不归一化时 IP 把长向量排在前面，cosine 不受长度影响
- **验收**：断言全绿；输出里能看到"方向相同但长度不同 → IP 排序 ≠ cosine 排序"的实例（参考实现 `sol-02-distance-triple.cpp`）
- **提示**：性质断言用相对误差（两浮点路径归约顺序不同）

## 练习 3：距离计算 benchmark + SIMD 优化（★★★）

- **目标**：先测量再优化——对距离函数写 benchmark，再用手写 NEON 与自动向量化验证加速
- **要求**：
    - 基准函数：L2（朴素串行累加版）+ SIMD 版；数据规模**压进 L2**（约 1~8MB），每轮预热、取 ≥5 轮中位数；结果必须被消费（volatile sink）
    - 故意用**非 4 的倍数维度**（如 150），验证你的 SIMD 版尾部标量收尾不越界、结果与标量一致
    - 三种编译形态各跑一遍并记录：`-O2` 标量基线 / 同代码 `-O2`（SIMD 版生效）/ `-O3 -ffast-math`（观察标量循环被自动向量化）
    - x86 说明：换 AVX2 的改法写在注释里（不必真编译）
- **验收**：输出三行以上真实耗时/加速比；SIMD 版结果与标量一致（相对误差断言）；注释解释"为什么 -O3 -ffast-math 后标量与 SIMD 接近"（参考实现 `sol-03-distance-bench-simd.cpp`，文件头给出三种编译命令）
- **提示**：NEON 水平归约只在最后做一次；中途用 4 个独立累加器避免依赖链

## 练习 4：HNSW 节点与邻接表基础搜索（★★★）

- **目标**：给定一张"分层图"（节点 = 向量，层内邻接表 = 该节点在该层的邻居），实现 ef 搜索并量它的"距离评估次数"与召回
- **要求**：
    - 图从数据构造：对每个节点用精确 kNN 建"层 0"邻接（每节点 8 个最近邻）即可——本练习聚焦**搜索**，构造不做多层插入（与 ex04 的完整建图区分开）
    - 实现 `ef_search(entry, query, ef)`：候选集（最小堆扩展）+ 结果集（最大堆收窄），visit 去重；返回时能报"评估过的距离次数"
    - 跑 ef = 1 / 8 / 64 三档，输出每档的平均距离评估次数与 recall@10（对照精确 top-10）
    - 观察并解释：ef 越大距离评估越多、召回越高——把它与"暴力扫全库的距离次数"对比，量化图搜索省了多少距离
- **验收**：ef=1 时评估次数远小于 N（否则你的图搜索退化成了扫描）；recall 随 ef 单调不减（非严格）；能说出"候选从最近处扩展 + 结果集只留 ef 个"两堆各自的角色（参考实现 `sol-04-hnsw-basic-search.cpp`）
- **提示**：终止条件是"候选堆顶比结果堆顶（最差入选者）还远"——想清楚为什么此时可以停

## 练习 5：用 Faiss 建 IVF / HNSW 索引测召回率（★★★）

- **目标**：接上工业向量库——用 Faiss 的 `index_factory` 建 IVF 与 HNSW，输出 recall@10 与 QPS
- **要求**：
    - `IndexFlatL2` 建精确 ground truth；`"IVF100,Flat"` 与 `"HNSW32,Flat"` 各建一个；IVF 记得 `train`
    - 分别调 `nprobe`（如 1/10/100）与 `efSearch`（如 16/64/256）各跑一组，输出 (recall, QPS) 表
    - 回答（注释或输出）：为什么 nprobe/efSearch 调大召回与延迟同向变？Flat 那行 recall 为什么是 1.0？
- **验收**：能跑出三索引的 recall-QPS 对照表并解释每行；若本机装不了 faiss，则以"可运行代码 + 伪码注释 + 安装命令（brew install faiss；源码 cmake 见 ex07 文件头）"形式交付，并如实标注未在本环境验证（参考实现 `sol-05-faiss-recall.cpp`）
- **提示**：数据规模从 10 万 × 64 维起步；查询集与库集分开生成；IVF 的 `nlist` 不要超过库条数

## 验证状态汇总

| 练习 | 参考实现 | 工具链 | 状态 |
|------|---------|--------|------|
| 1 brute-force search | `sol-01-brute-force-search.cpp` | Apple clang 21.0.0 | 已验证（零警告、断言全绿） |
| 2 三种距离 | `sol-02-distance-triple.cpp` | Apple clang 21.0.0 | 已验证 |
| 3 距离 benchmark + SIMD | `sol-03-distance-bench-simd.cpp` | Apple clang 21.0.0（两种形态） | 已验证（含 Homebrew clang 交叉核对） |
| 4 HNSW 基础搜索 | `sol-04-hnsw-basic-search.cpp` | Apple clang 21.0.0 | 已验证 |
| 5 Faiss IVF/HNSW recall | `sol-05-faiss-recall.cpp` | Faiss 1.9.0（/tmp 源码构建）+ Apple clang 21.0.0 | 已验证（recall-耗时曲线表，见文件头输出节选） |

统一命令示例（每个 sol-* 文件头注释自带其命令；产物一律输出到 /tmp）：

```bash
clang++ -std=c++20 -O2 -Wall -Wextra sol-01-brute-force-search.cpp -o /tmp/ph23-sol01 && /tmp/ph23-sol01
```
