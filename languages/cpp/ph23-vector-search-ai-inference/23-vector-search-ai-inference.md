# C++ 向量检索与 AI 推理引擎方向阶段

> 面向向量数据库、RAG 检索、Faiss、CUDA/TensorRT 与推理服务方向：把 ph22 备好的「磁盘页与缓存、不可变文件、版本可见性」心智平移到「向量检索 + AI 推理引擎」——用 L2/Cosine/IP 距离、SIMD 内核、HNSW/IVF/PQ 图索引与量化、metadata filter、向量索引持久化、Faiss 阅读，以及 KV Cache/batching/serving runtime 概念，走完 C++ 学习路线的最后一个编号阶段。

## 1. 概述

本阶段是学习路线的第 23 步，也是 **C++ 路线（ph01~ph23）的收官阶段**（roadmap §23 即最后一节，其后再无编号阶段，只有「附录：阶段性项目验收标准」）。roadmap §23 的目标一句话：面向向量数据库、RAG 检索、Faiss、CUDA/TensorRT 和推理服务，掌握 C++ 在 AI Infra 底层的使用方式。ph22 结束时你手里是「一台会写 WAL、会 flush 不可变 SSTable、会拿 Buffer Pool 管页缓存、会用版本号判断可见性」的 mini LSM；本阶段问的是同一批心智的新战场：**如果"数据"不是 key-value 而是高维向量，"查询"不是按 key 点查而是"找最近邻"，ph22 的一切需要改什么、又能原样搬走什么**。搬走的是磁盘形态（不可变文件、快照 + 校验、缓存淘汰、增量日志），新学的是向量侧结构（距离内核、图索引、量化、SIMD）。这就是 ph22「下一阶段」预告兑现：**把磁盘页与缓存管理、不可变文件、版本可见性心智，平移到向量库与推理服务的存储/缓存问题上**。

| 核心维度 | 覆盖内容 |
|---------|---------|
| 距离度量 | L2 / Inner Product / Cosine 的定义、几何语义、换算恒等式、适用场景表（ex01） |
| 暴力 topK 检索 | flat 全扫 + 容量堆维护 top-k；与全排序 ground truth 逐位对照；QPS 实测（ex02） |
| SIMD 距离计算 | 标量串行链 / 手写 NEON / 编译器自动向量化三条路径；计算受限 vs 带宽受限（ex03） |
| HNSW | 分层图结构、随机层高插入、贪心下潜 + ef 搜索、参数 M/efConstruction/efSearch（ex04） |
| IVF 与 PQ | 聚类倒排缩小范围、乘积量化压缩内存；伪码 + 权衡表（本阶段概念为主） |
| metadata filter | 向量 + 标量联合过滤的两种工程形态与"复查铁律"（ex05） |
| 向量索引持久化 | 快照文件布局、temp+fsync+rename、整文件校验；复用 ph22 SSTable 磁盘形态（ex06） |
| Faiss 使用与源码阅读 | index_factory 三索引 API、recall-QPS 对照、核心模块解剖引导（ex07） |
| 推理服务基础 | KV Cache 字节账本、prefill/decode、batching 与 continuous batching、内存布局（ex08） |
| CUDA C++ / TensorRT | 线程块模型、显存拷贝、plugin 接口形态——概念 + 伪码（本机无 GPU，未在本环境验证） |

**边界声明（本阶段是路线终点的边界）**：这个阶段只涉及**单机、CPU 可验证的向量检索工程（距离/SIMD/HNSW/IVF-PQ 概念/metadata filter/索引持久化/Faiss 阅读）+ 推理引擎的运行时概念（KV Cache/batching/显存账本/CUDA 线程模型/TensorRT plugin 接口）**，**不涉及 GPU 内核级优化与 CUDA 工程化（本机无 GPU，只讲线程块模型与显存心智，内核调优属后续可深入方向而非编号阶段）、不涉及 TensorRT 生产化 plugin 开发与推理框架源码（属后续方向）、不涉及工业级向量库工程（Faiss/Milvus 的分布式、刷盘调度、复制迁移属后续方向）、不涉及 LLM 训练/微调（推理与训练分家）**。与 ph18 性能优化阶段的分工：ph18 讲的是通用方法论（profile、缓存局部性、拷贝消除），本阶段只把其中「SIMD、连续布局、带宽受限」这几条拿到向量场景讲透，不重复其通用框架；ph22 的「存储内核组件怎么写」不重复，只复用其结果（SSTable 布局、WAL 心智）——引用的代码形态均注明来源。关于推理引擎的定位再强调一次：**本阶段教的是"serving runtime 为什么关心 KV Cache、batch、显存布局"的概念与账本，不是教你写一个能上生产的推理框架**。

本阶段是 C++ 路线收官：ph01~ph22 教的每一层（语法/对象生命周期/STL/模板/并发/文件网络/构建调试/性能/ABI/互操作/数据结构/存储引擎）到这一步汇成「向量检索 + AI Infra」的落点。两个伏笔在此汇合：roadmap §21 把「HNSW toy implementation」列在数据结构阶段的推荐项目里（HNSW 是图结构 + 层高的组合，没有 STL 现成容器可用，必须自己构造），ph22 主文档第 7 章的「下一阶段」预告过「向量索引持久化直接复用 SSTable/Buffer Pool 的磁盘形态」——前者在本阶段 3.4/ex04 兑现，后者在 3.7/ex06/project 兑现。

C++ 路线 ph01~ph23 的完整形状（本阶段在链尾的落点）：

```text
语法/对象/STL/模板/现代C++        ph01~ph06  ← 会写、会用、会泛型
异常/工程规范/并发/网络/构建        ph07~ph10  ← 会工程化、会并发、会 IO
标准演进/ABI/生命周期/RAII/UB      ph11~ph15  ← 会读标准、会守内存纪律
测试质量/设计模式/性能/插件/互操作   ph16~ph20  ← 会验证、会架构、会跨界
数据结构与算法 ──▶ 存储引擎/AI 地基  ph21~ph22  ← 结构资产 + 磁盘页心智
                  │
                  ▼
向量检索 + AI 推理引擎（本阶段）   ph23 ← 距离/SIMD/图索引/量化/Faiss/KV Cache
                  │
                  ▼
后续可深入方向（不另设编号阶段）：CUDA 内核 → TensorRT 生产 plugin
                → 工业级向量库（Faiss/Milvus）→ 推理服务工程化 → Python 高性能扩展
```

这张图也是给分析/路线的定位图：C++ 路线的能力弧线是"从写得出程序 → 到让数据跨崩溃活下来（ph22）→ 到让数据被更快找到、并被 AI 服务消费（ph23）"，终点落在 AI Infra 底层而非应用层——这是与 Go/Python/Java 路线在能力形态上的关键差异（第 5 节展开）。

## 2. 来源与演变

向量检索的两条血脉——**「近似最近邻（ANN）算法」与「支撑它的工程库」**——分别来自 1990 年代的算法研究与 2010 年代起的工业需求，又在 2017~2023 年被深度学习与 RAG 点燃。**设计哲学一句话：高维空间里"最近邻"的精确答案几乎总是退化成全库扫描，所以一切 ANN 结构都是在做同一件事——用"只访问数据的一小部分"换"答案偶尔不是最精确"；召回率、延迟、内存是永远的三角，量化与图索引只是把三角形的两条边往下压的不同杠杆**。

算法线从「把空间切碎」开始：1970 年代的 metric space 索引（k-d tree、M-tree）是"树切空间"，但高维下树会退化（维度灾难：几乎所有点都离查询等距地远，剪枝失效）；1998 年 Indyk & Motwani 提出 **LSH（Locality-Sensitive Hashing）**，第一次给出 ANN 的随机化理论框架——按"相近的点大概率撞同一桶"来哈希，用桶过滤掉大多数点；2011 年 Jégou 等人的 **PQ（Product Quantization）** 把"压缩"引进 ANN——把向量切成子空间分别量化，用码本替换原始 float，把内存缩小一两个数量级；Malkov 等人在 2011~2016 年把方向从"切空间"换成"连图"——**NSW（Navigable Small World）** 用图上的贪心游走找近邻，2016 年 arXiv 的 **HNSW（Hierarchical NSW）** 在 NSW 上叠了"跳表式分层"：高层边稀疏、负责把游走"导航"到对的邻域，底层边密集、负责精确收尾——这正是 ph21 学的 SkipList 的图版（层高几何分布、从高层向下定位）。HNSW 今天仍是"召回/延迟/内存"综合最好的 CPU 图索引之一。工程线从「谁把这些结构做成可用的库」展开：Meta 的 FAIR 团队 2017 年开源 **Faiss**（论文 "Billion-scale similarity search with GPUs"），把精确扫描（IndexFlat）、倒排（IndexIVF）、量化（IndexPQ/ScalarQuantizer）、图（IndexHNSW）统一进 `index_factory` 的字符串 DSL——"IVF4096,PQ32" 一行创建出工业级索引，成为理解向量检索工程化的**第一 C++ 读本**；2019 年起 DiskANN（微软，SSD 友好的图索引）、ScaNN（谷歌）、Milvus（向量数据库）相继出现，把 ANN 从"库"推向"系统"；2020 年 Lewis 等人的 **RAG 论文** 让"检索增强生成"成为概念，2023 年 LLM 浪潮把 RAG 变成刚需，向量数据库/检索组件随之爆发——这条路线的每个 C++ 结构（SIMD 内核、倒排、图、量化）都在这波里重回聚光灯。

推理引擎是另一条相对年轻的线：Transformer 的自回归解码天然暴露了「算力密集的 prefill 与带宽密集的 decode」分裂。**服务端批处理（batching）** 在传统 DL 推理服务（NVIDIA TensorRT 2017、Triton）里已是常态——把多个请求拼成一个 batch 摊薄权重读取；但 LLM 的 decode 让"整批同步结束再收新请求"浪费严重，2022 年 **Orca** 提出 **continuous batching**（请求粒度调度，做完一个补一个）；**KV Cache** 是自回归的必然产物（每生成一步要把历史 K/V 投影缓存下来，否则每步都重算整个前缀），它的内存占用随模型结构确定增长，2023 年 **vLLM 的 PagedAttention** 把 KV Cache 管成"显存里的页表"解决碎片——ph22 的 Buffer Pool 心智在这里原样复活。CUDA（2007）提供了通用 GPU 编程模型，cuDNN（2014）与 TensorRT 先后把"算子库"与"推理编译引擎"产品化，C++ 始终是这条栈的底层语言。

**为什么这条史里的主角几乎都是 C++**：向量检索与推理引擎的工作负载（逐条算距离、批量矩阵乘、缓存逐字节管理、延迟敏感的服务路径）恰好落在 C++ 的舒适区——**没有 GC 停顿、内存布局完全可控、SIMD/内核级优化可达、又能暴露 C ABI 给 Python 生态当扩展层**。这不是语言偏好，是负载结构决定的：FAIR 开源 Faiss 用 C++、NVIDIA 的 TensorRT/plugin 接口是 C++、vLLM 用 C++ 写 PagedAttention 的底层、向量库 Milvus 的内核（基于 Knowhere，Faiss/HNSW 封装）是 C++。学完本阶段你应该能对这条链路的"每一层为什么是 C++"给出自己的解释。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| 度量空间索引（k-d tree / M-tree 等） | 1970s~1990s | 树切空间找近邻；高维退化 → 触发 ANN 研究 |
| LSH（Indyk & Motwani） | 1998 | ANN 随机化理论框架：相似点大概率同桶 |
| PQ（Jégou 等） | 2011 | 子空间量化压缩内存，量化时代的起点 |
| NSW / HNSW（Malkov 等） | 2014 / 2016 | 图上贪心游走 + 分层导航；召回/延迟/内存综合最优之一 |
| Faiss（Meta FAIR 开源） | 2017 | 工业级 ANN 库：index_factory DSL + 统一索引族，C++ 阅读范本 |
| TensorRT / Triton | 2017 前后 | GPU 推理编译 + 服务框架；batching/显存工程化 |
| DiskANN / Milvus / ScaNN | 2019 前后 | 图索引下 SSD；向量库产品化 |
| RAG（Lewis 等） | 2020 | 检索增强生成概念确立 |
| Orca（continuous batching） | 2022 | 请求粒度调度，decode 不再整批同步 |
| vLLM PagedAttention | 2023 | KV Cache 页表化管理（Buffer Pool 的显存版） |
| LLM × 向量库爆发 | 2023~ | RAG/记忆/Agent 检索成刚需，C++ 作高性能扩展层 |
| C++20 | 2020 | 本阶段基线：span/string_view/ranges/format 稳定可用 |

本文示例以 **C++20** 为基线（与 ph21/ph22 同口径——本阶段代码大量用 `std::vector` 连续布局、`string_view`、泛型与 `std::ranges`；C++20 在这些面上稳定且充分），验证工具链为 **Apple clang 21.0.0**（`/usr/bin/clang++`，默认 PATH）+ **Homebrew clang 21.1.8**（`/opt/homebrew/opt/llvm/bin/clang++`，交叉核对），macOS arm64 + libc++，实测环境。**验证状态总纲**：ex01~ex08 与 exercises/练习 1~5、project/ 均已在本机验证——ex01~ex06、ex08 与练习 1~4 在 Apple clang 21.0.0 下 `-std=c++20 -Wall -Wextra` 编译零警告、运行断言全绿（project 另过 ASan/UBSan 与 Homebrew clang 交叉编译），ex03 的 SIMD 数字另有 Homebrew clang 交叉核对（同量级）；**Faiss 相关（examples/ex07、exercises/练习 5）因本机 brew 写入受限，采用 faiss 1.9.0 /tmp 源码构建（摘除 OpenMP 强制依赖 + 自备 omp 桩满足编译链接，单线程 generic 构建）后实测**——绝对 QPS 与官方发行版不同，但 recall-延迟曲线形态完整可复现（细节见文件头与 examples/README）。**CUDA/TensorRT 部分只讲概念与伪码，本机无 NVIDIA GPU，一律标「未在本环境验证」并给出需 NVIDIA 环境的原因与验证路径**。SIMD 全部为本机 arm64 NEON 实测（Apple Silicon 上 `-O3` 自动向量化 + 手写 NEON 内建均可），x86 对应命令（`-mavx2 -mfma` 与 AVX2 内建）在注释中给出但未在本环境验证。

## 3. 语法与参数

> 本节代码块是**教学骨架**：聚焦单个概念裁剪。完整可运行文件见第 6 节与 [`examples/`](./examples/)（验证状态逐文件标注）；内嵌片段标注来源文件。本阶段的"语法与参数"不指向 C++ 语言特性，而指向**向量库/推理引擎组件的接口与调参语义**——这正是 roadmap §23 学习内容的形态：L2/IP/Cosine 是"度量参数"，M/efSearch/nprobe/nlist 是"索引参数"，batch/KV Cache 预算/plugin 描述符是"运行时参数"。

### 3.1 距离度量：L2 / Inner Product / Cosine 的定义、换算与选择

向量检索的全部工作就是把 query 与库内向量比"谁更近"，而"近"的定义——**度量**——是第一个必须显式选择的参数。三种最常见度量的数学定义与直觉（examples/ex01）：

| 度量 | 定义 | 语义 | 分数方向 | 用在哪 |
|------|------|------|---------|--------|
| 平方 L2 | ∑(a-b)² | 欧氏几何距离（编码**位置差**） | 越小越近 | 一般语义最近邻（图像/文档 embedding 默认） |
| Inner Product | ∑a·b | 方向相似 × 长度放大（编码**方向与幅值**） | 越大越相似 | 推荐/召回里"相关性打分"（偏好长向量） |
| Cosine | (a·b)/(\|a\|\|b\|) | 只比方向夹角（对长度不变） | 越大越相似（∈[-1,1]） | 文本/语义相似度（embedding 已归一化时退化为 IP） |

**为什么这么设计**：三个度量覆盖了工程对"近"的三种定义——L2 问"点靠得近不近"（位置），Cosine 问"方向像不像"（不管向量长短），IP 问"方向和强度都像不像"（长向量天然被偏好）。工程里最常用的是**「L2 归一化 + Inner Product = Cosine」**这条捷径：先把向量归一化到单位长度，再算 IP，就得到 cosine 且省去每次除范数——这也是 Faiss `IndexFlatIP` + 预归一化替代 cosine 的常规做法。

```cpp
// examples/ex01-distance-metrics.cpp —— 三种度量（节选，已验证）
float l2_sq(const vec& a, const vec& b) {          // 平方 L2：省一次 sqrt，排序等价
    float s = 0.0f;
    for (std::size_t i = 0; i < a.size(); ++i) {
        const float d = a[i] - b[i];
        s += d * d;
    }
    return s;
}
float inner_product(const vec& a, const vec& b) {  // IP
    return std::inner_product(a.begin(), a.end(), b.begin(), 0.0f);
}
float cosine(const vec& a, const vec& b) {         // 余弦 = 归一化后的 IP
    return inner_product(a, b) / (norm(a) * norm(b));
}
vec l2_normalize(const vec& v) { /* v/|v| */ }
```

**换算关系（ex01 [2][3] 实测断言）**：`|a-b|² = |a|² + |b|² - 2(a·b)`（本机实测 lhs==rhs）；归一化后 `cos(a,b) = IP(â,b̂)`。**长度敏感性是选择度量的关键**：ex01 [4] 在库里故意掺了"长度×3"的向量——未归一化时 IP 的 top-3 会被长向量主导（实测 ip 排序 top3=[92,116,28] 全是长向量），而 cosine 不受影响；归一化后 l2/ip/cos 三种排序**逐位一致**。给工程的三个判断：① 你的 embedding 训练时已归一化（很多模型输出单位向量）→ 直接用 IP 省事；② 未归一化且来源混杂（文档长短不一）→ cosine 或先归一化；③ 要表达"越相关越像还要考虑热度/幅值"→ IP。项目与练习均实测了这条铁律（project 的 metric 自测里 cosine 把长度 ×3 的同向向量与单位向量打成并列，而 IP 让长向量胜出）。

### 3.2 暴力 topK 检索：flat 全扫 + 容量堆，精确但 O(N·D)

一切 ANN 的起点是**暴力（flat）检索**：query 与全库逐条算距离，维护当前 top-k。它是精确检索（召回恒 = 1.0），也是所有 ANN 的 ground truth 与性能参照（本阶段 ex02、ex04、sol-04、project 全部拿它当对照）。实现只有三个要点，但每个都有工程讲究（examples/ex02）：

```cpp
// examples/ex02-brute-force-topk.cpp —— top-k 容量堆（节选，已验证）
std::priority_queue<pq_elt> pq;          // 默认大顶堆：距离最大的在堆顶 = "当前第 k 差"
for (std::uint32_t i = 0; i < n; ++i) {
    const float s = dist(row_i, q);      // 距离是唯一热点：整循环都是内存带宽/计算受限
    if (pq.size() < k) { pq.push({s, i}); }
    else if (s < pq.top().first) { pq.pop(); pq.push({s, i}); }  // 更好才替换最差
}
```

① **行主序连续布局**（Per.19 的向量版）：库存成 `std::vector<float>` 的 N×D 连续矩阵，逐行顺序读——缓存与 SIMD 都吃这一条（3.3 会量化）；数据结构用"vector of struct"存单条、用"struct of vector/矩阵"存全库，距离计算的唯一正确形态是后者。② **top-k 用容量 k 的堆而不是全排序**：全排序 O(N log N)，堆只要 O(N log k)，且每来一条只有一次堆顶比较——ex02 实测与全排序 ground truth 逐位一致。③ **距离计算是热点，别的都不是**：谓词检查、id 映射、结果拷贝都便宜，profile 时永远先看距离内核（ph18 的方法论在这里第一次显形）。

为什么在 ANN 时代还要学 flat：它是**正确性锚点**（ex04/exercises 的 recall 全靠它当 truth）、是**性能上限参照**（"你的 ANN 比 flat 快多少、用召回率换了什么"必须有基线）、也是**小库与高并发小 top-k 的真实选择**（几十万 × 几十维在 SIMD 下就是毫秒级，很多场景根本不需要 ANN——见 project 实测 QPS）。

> 召回率指标只对 ANN 有意义；flat 的 recall 恒 1.0，拿它当"AI 检索"上报是自欺。这是工程里常见的度量陷阱。

### 3.3 SIMD 距离计算：为什么快 / 手写 NEON / 自动向量化

距离函数是"逐元素独立运算 + 最后归约"，没有分支——这是 CPU 上最理想的 SIMD 形状。**SIMD 的原理一句话：普通指令一次算 1 个 float，SIMD（NEON/AVX）一条指令同时算 4/8 个**，把"每元素一条指令"的吞吐放大指令宽度倍。但有两个隐藏条件：数据要连续（正好是 3.2 的行主序布局）、浮点归约要允许重结合（编译器默认保守不重排浮点，`-ffast-math` 才放开）。examples/ex03 用同一份源码对比三条路径（本机 Apple clang 21.0.0 实测，dim=128、数据 4MB L2 内、7 轮取中位数）：

```text
-O2                : l2_scalar 49.4 ns/op  →  l2_neon 17.9 ns/op   （2.76x）
-O3 -ffast-math    : l2_scalar 14.6 ns/op  →  l2_neon 14.9 ns/op   （自动向量化 ≈ 手写 NEON）
Homebrew clang -O2 : l2 加速比 2.78x（交叉核对同量级）
```

**三条路径的取舍**（都该会写）：① **朴素标量**当正确性锚点与可移植基线；② **手写 NEON 内建**（`vld1q_f32` 载 4 个 float、`vfmaq_f32` 一条乘加、`vpadd` 收尾）——想精确控制向量宽度与指令数时用，代价是平台绑定（x86 要换 AVX2，本机未验证 x86 命令）；③ **靠编译器自动向量化**（`-O3 -ffast-math`）——**无内建代码也能吃到 SIMD**，实测把标量循环提到 ≈ 手写 NEON 的 90%+，这是最划算的默认路径。四个写码注意：NEON 的**尾部必须标量收尾**（维度不是 4 的倍数时，sol-03 用 dim=150 专门练了越界检测）；用**多个独立累加器**打散浮点依赖链（否则流水线空等）；计时必须有预热 + 多次取中位数 + 消费结果（`-O3 -ffast-math` 下不消费结果的整段循环会被编译器当死代码删掉，本示例开发时实测踩过）；**结论看加速比不看绝对 ns**（绝对数与机器频率有关）。

手写 NEON 的最小形态（examples/ex03，arm64 专属；x86 换 AVX2 内建，命令见文件头注释，未在本环境验证）：

```cpp
// examples/ex03-simd-distance.cpp —— NEON L2 内核（节选，已验证）
float l2_neon(const float* a, const float* b, std::size_t dim) {
    float32x4_t acc = vdupq_n_f32(0.0f);        // 4 个独立累加器：打散浮点依赖链
    std::size_t i = 0;
    for (; i + 4 <= dim; i += 4) {
        const float32x4_t va = vld1q_f32(a + i);  // 一条指令载 4 个 float（128-bit）
        const float32x4_t vb = vld1q_f32(b + i);
        const float32x4_t d = vsubq_f32(va, vb);
        acc = vfmaq_f32(acc, d, d);               // acc += d*d：一条乘加指令
    }
    const float32x2_t lo = vget_low_f32(acc);     // 水平归约只做一次
    const float32x2_t hi = vget_high_f32(acc);
    const float32x2_t s = vpadd_f32(lo, hi);
    float r = vget_lane_f32(vpadd_f32(s, s), 0);
    for (; i < dim; ++i) {                        // 尾部标量收尾：dim 非 4 倍数必写
        const float d = a[i] - b[i];
        r += d * d;
    }
    return r;
}
```

> SIMD 的收益上限由"计算受限还是带宽受限"决定——这是 4.3 的重点，先记住结论：数据放得进缓存（小库/热数据）→ 加速比接近指令宽度；数据远超缓存（海量库全扫）→ 内存带宽成瓶颈，加速比缩水。project 实测的就是后一种形态的真实数字（QPS 1.83x vs ex03 的 2.76x）。

### 3.4 HNSW：分层图索引的结构、插入、搜索与参数

HNSW 的思维模型是「**跳表的图版**」（ph21 的 SkipList 在此重逢）：SkipList 用"多层有序链表"让单链表上的 O(n) 查找变成 O(log n) 期望；HNSW 用"多层最近邻图"让全库逐点比较变成"沿图游走"。**为什么是图而不是树/哈希**：高维空间里树的分区剪枝在维度灾难下失效（几乎所有点都"等距地远"，剪哪边都白剪），而"每层只连离自己最近的 M 个邻居"的图天然只跟随局部密度走——导航只发生在有数据的地方。**为什么分层**：单层图上贪心游走容易停在局部最优（从入口到目标邻域的路可能绕远）；高层用**稀疏的长程边**把游走快速"导航"到正确邻域，低层用**密集的短程边**精确收尾——就像跳表先跳大步再走小步。

```text
HNSW 分层结构（每层是一张"局部最近邻"图；圆圈 = 节点，数字 = 数据点号）：
 层 2（最高）  (q)──(1)──(4)          ← 入口 q 在这一层与全库几个"地标"相连
                │                      （边稀疏、长程：一步跨过大片区域）
 层 1          (q)──(1)──(7)──(4)
                │     │     │          ← 中间层：边稍密，把游走导到目标邻域
 层 0          (q)─(1)─(3)─(7)─(9)─(4)
               (2)─(8)  (5)  (6)       ← 层 0 最密（出度可放宽 2M）：逐点收尾

搜索路径示例：q 要找回 9 的近邻 → 层 2 走 q→1→4 找不到 9 的邻域？
   不——层 2 是稀疏"导航图"，真实路径是：层 2 贪心从 q 走到离 9 最近的地标(4)
   → 层 1 从 4 走到 7 → 层 0 从 7 沿 (7)-(9) 找到 9，再在 9 邻域用 ef 搜索收 top-k。
```

**结构**：每个节点有随机层高 L（几何分布：P(层 ≥ i+1) = 0.5，与 SkipList 同款），每层一张邻接表（层 i 连不超过 M 个邻居，层 0 可放宽到 2M）。**插入**（examples/ex04 完整 toy 实现）：新节点从全局入口开始在"高于自己层高"的层做**贪心下潜**（每层只朝当前最近邻走一步），到层 0 前每层做一次 ef 搜索取候选、就近连边并回连——层越高连的边越少。**搜索**：同样从入口在上层贪心下潜到层 0，然后在层 0 做 ef 搜索（候选堆 + 结果堆双向收紧），取 top-k。

**结构**：每个节点有随机层高 L（几何分布：P(层 ≥ i+1) = 0.5，与 SkipList 同款），每层一张邻接表（层 i 连不超过 M 个邻居，层 0 可放宽到 2M）。**插入**（examples/ex04 完整 toy 实现）：新节点从全局入口开始在"高于自己层高"的层做**贪心下潜**（每层只朝当前最近邻走一步），到层 0 前每层做一次 ef 搜索取候选、就近连边并回连——层越高连的边越少。**搜索**：同样从入口在上层贪心下潜到层 0，然后在层 0 做 ef 搜索（候选堆 + 结果堆双向收紧），取 top-k。

```cpp
// examples/ex04-hnsw-toy.cpp —— ef 搜索核心（节选，已验证）
// 候选：最小堆（越近越先扩展）；结果：最大堆（堆顶 = 当前最差入选者，限 ef 个）
while (!candidates.empty()) {
    const hit cur = candidates.top();
    candidates.pop();
    if (cur.dist > results.top().dist) break;   // ★ 最近的未扩展点已比最差入选者还远 → 停
    for (const node_id n : layers_[cur.id][layer]) {
        if (visited[n]) continue;
        visited[n] = true;
        const float d = dist2(n, q);
        if (results.size() < ef || d < results.top().dist) {
            results.push({n, d});
            if (results.size() > ef) results.pop();
            candidates.push({n, d});
        }
    }
}
```

**为什么"贪心在图里走有效"**：HNSW 的边是"局部最近邻"边，从任何点出发，贪心选最近邻居前进，本质是在密度场上"下山"；高层边跳过无关区域。本机实测（ex04，n=2000、dim=16、M=8、efC=64、efS=48）**recall@10 = 98.55%，平均 36.4 µs/query，同机暴力检索 115.9 µs/query——用 1.45% 召回率换 3.2x 延迟**。参数是"召回-延迟-内存"三角的三个旋钮：

| 参数 | 含义 | 调大效果 | 生产默认直觉 |
|------|------|---------|-------------|
| M | 每层最大出度 | 图更密：召回↑、建图/搜索都更慢、内存↑ | 16~64 |
| efConstruction | 建图时每层搜索宽度 | 建图质量↑（连边更准）：recall↑、建图慢 | 与 M 同量级到几倍 |
| efSearch | 查询时层 0 搜索宽度 | recall↑、延迟↑ | 查询侧按延迟预算调 |

**工程注意**：真实 HNSW（Faiss/HNSWlib）比 toy 多了"邻居选择启发式"（选邻居时不纯取最近——要保证多样性与可达性，防止入口附近节点边全指向同一方向）、层高截断、删除标记与并发插入；toy 的连边"超容换最远"不回传替换，recall 会随数据分布变差——这些是「工业级向量库工程」方向的内容，本阶段只到形态与趋势（exercises/练习 4 另用"给定图"练纯搜索机制与距离评估计量）。

### 3.5 IVF 与 PQ：聚类倒排缩小范围、乘积量化压缩内存

HNSW 走"连图"路线，IVF（Inverted File）+ PQ 走"**先聚类再只查最近的桶**"与"**把向量量化短**"的路线。两者常合体（Faiss 的 `IVF4096,PQ32`）但机制正交，分两半讲。

**IVF——用聚类缩小搜索范围**。建库时对全库跑 k-means（Faiss 里叫 train），得到 nlist 个聚类中心；每条向量归入最近的中心，中心下挂一个倒排桶（存该簇全部向量的原始值）。查询时先算 query 与 nlist 个中心的距离，挑最近的 nprobe 个桶，只在桶内做暴力 top-k。**为什么这样设计**：nlist=100 时桶平均只有全库 1% 的量，nprobe 从 1 到 100 是"精确度预算"的连续旋钮——nprobe 越大越接近全库暴力、召回越高越慢。**倒排（inverted list）这个结构与 ph22 的"稀疏索引"和 metadata filter（3.6）是同一个心智：先花 O(nlist) 定位"该去哪些桶"，再只在相关桶里付 O(桶内) 的昂贵代价**。

```text
IVF 查询路径：query ──▶ 与 nlist 个聚类中心算距离（O(nlist·D)，便宜）
              ──▶ 取最近 nprobe 个桶 ──▶ 桶内逐条算精确距离取 top-k
召回风险：真近邻的向量若被分到"没被 probe 的桶"→ 漏（聚类质量与 nprobe 决定召回）
```

**PQ——用量化压缩向量本身**。原始 float32 一条 d=128 的向量占 512B，百万条就是 512MB；PQ 把向量切成 m 段（每段 d/m 维），每段用 k-means 学出 k 个码字（一个子码本），向量每段只存"最近码字的编号"（log2(k) bit）——最终一条向量存成 m 个字节（k=256 → 每段 1B）。**为什么这样设计**：全空间量化（直接对整条向量 k-means）码字数量要爆炸才能跟得上维度（维度灾难又来了）；PQ 用**子空间乘积**——每段独立量化、距离用"查子码本表累加"近似——把码本数量从"指数于维度"降成"线性于段数"，这是"乘积"二字的由来（4.4 给量化误差直觉）。

```text
PQ 编码一条向量（d=128 → m=4 段，k=256 码字/段）：
 原始 float32 向量（512B）
 [ seg0:32维 │ seg1:32维 │ seg2:32维 │ seg3:32维 ]
      │           │           │           │
      ▼           ▼           ▼           ▼        每段独立 k-means → 子码本 0..3
  查最近码字    查最近码字    查最近码字    查最近码字  （每子码本 256 个 32 维码字）
      │           │           │           │
      ▼           ▼           ▼           ▼
  码号 [ 7 ]    码号 [203]    码号 [ 41]   码号 [188]  → 存成 4 字节（原 512B → 4B）
解码近似：query 与本向量距离 ≈ 逐段查"query段 ↔ 码字"的距离表累加（查表，不算真实距离）
```

| 维度 | HNSW | IVF | PQ（可叠加在任意检索结构上） |
|------|------|-----|------------------------------|
| 手段 | 图导航 | 聚类倒排 | 量化压缩 |
| 省什么 | 距离次数（延迟） | 距离次数（延迟） | 内存与带宽（容量/成本） |
| 召回损失来源 | 图路径没走到 | 真近邻在未 probe 桶 | 量化误差（码字是近似） |
| 调参旋钮 | M / efSearch | nlist / nprobe | m（段数）/ k（码字数） |
| 典型内存 | 原向量 + 邻接表 | 原向量 + 中心 | 压缩后 ~1B/维 |
| 何时首选 | 召回与延迟都要、内存够 | 海量 + 需要可控召回 | 内存是硬约束（亿级） |

**为什么三者常合体**：IVF 管"少算"，PQ 管"少存"，HNSW 管"更少算但建图贵"——Faiss 的工厂串 `IVF4096,PQ32` 就是"IVF 先挡到 1/4096，PQ 再把每条压缩到 32B"。本阶段对 IVF/PQ 的落地要求是**概念 + 伪码 + 权衡表**（roadmap 学习内容即此），Faiss 调用面在 3.8/ex07 实测；完整训练流程与超参调优属「工业级向量库工程」方向，边界声明已划。

### 3.6 metadata filter：向量 + 标量联合过滤的两种工程形态

生产的检索几乎从不"只看向量"：RAG 按文档来源/时间窗过滤、电商按类目与价格过滤、推荐按上架状态过滤——query 是 (向量, 谓词) 二元组。两种工程形态（examples/ex05）：

- **search-then-filter（先向量后过滤）**：全库算距离 → 逐条检查谓词 → 维护通过者的 top-k。正确性最简单，谓词怎么组合都成立；代价是谓词只命中 1% 时仍付 100% 的距离成本。
- **filter-then-search（先过滤后向量）**：给高频过滤键建倒排（tag → id 表），先拿谓词把候选缩小到 tag 桶，再只对候选算距离。ex05 实测（n=20000，高选择性谓词）：A=77µs（谓词检查 20000 次）vs B=24µs（5381 次）→ **3.2x**；低选择性谓词时差距消失（flat 场景距离次数相等，B 只省了谓词检查）。

**为什么通常选 filter-then-search**：在 flat 场景它的收益有限（如上），但**一旦检索结构换成 ANN（HNSW/IVF），metadata 前置的价值放大成数量级**——让昂贵的图/量化搜索只发生在小候选集里，而不是"先 ANN 出 top-k 再回头过滤"（后者会把"谓词不通过的真近邻"漏掉：ANN 本来就有召回损失，过滤再砍一刀，召回会双倍恶化）。**工程铁律（ex05 断言覆盖）**：倒排给的是"满足部分条件的候选"，**必须对候选逐条复查全部谓词**（价格、可见性等）——多键谓词的交集索引任何一步近似都可能放进不满足条件的点；校验不能省。数据形态上还有一个 ph22 的伏笔兑现：向量库的 upsert/删除让"这条向量现在算不算数"变成**版本可见性**问题（ph22 3.8 的 tombstone 心智）——Milvus 等生产库的 filter 通常绑定版本号做一致性读，本阶段点到为止。

### 3.7 向量索引持久化：把 ph22 的 SSTable/Buffer Pool 心智平移到向量库

ph22 的「下一阶段」预告兑现点。向量索引要跨进程/崩溃存活，落盘形态与 KV 引擎**几乎同构**：不可变快照文件 + 增量日志 + 定期合并。examples/ex06 把 ph22 project 的 SSTable 文件布局直接搬来当"向量快照"（源码注释注明出处）：

```text
向量快照文件（ex06 / project vsearch 同源布局，SSTable 心智）：
  [定长 header: magic|version|dim|metric|count]   ← 打开先读头，知道去哪找数据
  [id 表: 每向量一条业务 id]                       ← 行号 ↔ 业务 id 映射
  [float 行主序矩阵]                                ← 距离计算的缓存友好形态
  [整文件 FNV-1a 校验尾]                            ← 不可变文件"损坏即拒绝服务"，不修复
写盘纪律：temp 写完 → fsync → rename 原子替换      ← ph22 3.3"要么完整可见、要么不存在"
```

**为什么这些决策原样成立**：向量库与 KV 库共享同一批物理约束——不可变文件免锁读、崩溃安全（写不完整丢弃即可）、缓存放心做（只有干净页不用写回）；ex06 实测 8000×32 维快照 1,056,028 字节（≈1.03× 原始向量，id 表是唯一额外开销），篡改数据区一字节即被校验尾拦截。

```text
生产向量库的磁盘形态 = ph22 的 WAL + SSTable + Compaction（ex06/project 是单代快照的教学版）：
 写入        add 向量 ──▶ 增量日志（WAL：追加"id+向量"，崩了从日志重放）
 定期 flush ──▶ 新快照 Snapshot#3（不可变文件）──▶ 旧 WAL 作废
 后台合并     Snapshot#1 + #2 + #3 ──▶ 合并成 Snapshot#4（回收被删/被覆盖的向量）
 查询        读最新一代快照（跨代查询要"版本可见性"决定谁算数——ph22 3.8 的 MVCC 心智）
```

**教学简化与生产形态的差距就是 ph22 那套**：ex06 的 reader"整文件读入内存"对应 ph22 ex02 的教学简化，换成页粒度 Buffer Pool + LRU/Clock 淘汰（ph22 3.7/ex04）即生产形态；快照 × N 代 + WAL 增量 + 后台合并 = ph22 的 WAL + Compaction 原样翻版（"新增向量写日志、定期 flush 成新快照、合并旧快照"）。**这一节想让你记住的只有一件事：ph22 学的存储心智 90% 可以整包搬进向量库，向量侧真正新增的知识是 3.1~3.6 的度量/结构/SIMD，不是磁盘管理。**

### 3.8 Faiss 使用与源码阅读引导：index_factory 三索引 API + 一个模块解剖

Faiss（Meta 2017 开源）是"向量检索的 LevelDB"：C++ 实现、单一索引族接口、工业验证。**先会用，再读源码**。使用面（examples/ex07 / exercises/练习 5）：

```cpp
// Faiss 最小使用（节选；依赖 faiss 库，编译命令见 ex07 文件头）
std::unique_ptr<faiss::Index> flat =                // 精确基线（也是 ground truth）
    faiss::index_factory(dim, "Flat", faiss::METRIC_L2);
std::unique_ptr<faiss::Index> ivf =                 // 倒排：字符串 DSL 一行建索引
    faiss::index_factory(dim, "IVF100,Flat", faiss::METRIC_L2);
ivf->train(n, xb.data());  ivf->add(n, xb.data());  // IVF 必须先 train（聚类中心）
dynamic_cast<faiss::IndexIVFFlat*>(ivf.get())->nprobe = 10;  // 召回旋钮
std::unique_ptr<faiss::Index> hnsw = faiss::index_factory(dim, "HNSW32,Flat", faiss::METRIC_L2);
hnsw->add(n, xb.data());
// 三种索引统一走 add/search 同一套 API：metric 与结构在工厂串里声明
```

**为什么这套 API 值得当 C++ 范本读**：`index_factory("结构,度量", metric)` 把"算法选择"从代码变成字符串参数；`train/add/search` 把"聚类训练、入库、查询"的生命周期显式分开（IVF 需要 train，HNSW 不需要——HNSW 的"训练"就是建图本身，这个差异就在讲算法结构）；所有索引继承同一抽象基类，上层（bench/服务）不感知具体算法——这是 ph17 策略模式的工业样本，也是 ph20 pybind11 能一行包一层的根基。实测口（ex07，faiss 1.9.0 /tmp 构建、聚类高斯数据 n=100k×64 维）：Flat recall 恒 1.0 当 ground truth（102 µs/query）；IVF200 扫 nprobe=1/10/100 得 recall 0.32→0.97→1.00（12→80→526 µs）；HNSW32 扫 efSearch=16/64/256 得 recall 0.28→0.34→0.41（12→42→243 µs）——nprobe/efSearch 越大召回与耗时同向的曲线被完整跑出。练习 5（均匀随机数据）同型扫描：HNSW efSearch 16/64/256 得 recall 0.36/0.71/0.95（39/144/723 µs）。注意：均匀随机数据是 ANN 的最坏情形、faiss 的 flat 走 BLAS 矩阵乘、本机 faiss 是无 OpenMP 单线程 generic 构建——所以"ANN 绝对比 flat 快"并不恒成立，读 benchmark 要看曲线形态而非单个数字。

**源码阅读引导（沿调用链走 + 解剖一个模块）**。最小阅读路径：`faiss/index_factory.cpp`（字符串怎么路由到具体类）→ `IndexFlat.cpp`（最简索引：add 存矩阵、search 全扫——你的 3.2 工程版）→ `IndexIVF.cpp`（train 跑聚类、search 先查中心再查桶——3.5 落地）→ `IndexHNSW.cpp` + `impl/HNSW.cpp`（3.4 落地）。**建议解剖的第一个核心模块：`IndexFlat`/`IndexFlatCodes` 的 search 与 `index_factory` 的字符串解析**——前者是本阶段距离内核在工业库里的样子（Faiss 的 flat 内核分 `fvec_L2sqr` 等一组带 SIMD 的 C 函数，配 `#ifdef __AVX2__` 等编译期分派——与 3.3 的三路径取舍直接对上），后者解释了"为什么所有索引长得一样"的架构选择。解剖时带三个问题：`为什么 search 的输入输出都是原始指针 + 显式维度`（C ABI 友好、pybind11/其他语言可包，呼应 ph19/ph20 的边界纪律）、`为什么 IVF 的 train 与 add 分离`（聚类中心是全局状态，必须先于任何向量确定）、`为什么 flat 内核用 C 风格 fvec_* 函数而不是模板`（SIMD 分派在 C 函数层做最干净，模板会让每个实例化都重复分派代码）。

### 3.9 推理服务基础：KV Cache / batching / 显存布局的账本

推理引擎（serving runtime）与向量库共享同一个主题叫"缓存和内存布局"，只是主角从"向量矩阵"换成"模型权重 + KV Cache"。用三件事讲清概念（examples/ex08 是 CPU 确定性账本模型，全部数字可由代码公式复核）：

**① KV Cache 的字节由模型结构唯一决定**：自回归生成第 t 个 token 时要对前 t 个 token 做注意力，为避免每步重算整个前缀的 K/V 投影，把每层每头的 K、V 缓存下来。公式：`bytes = 2(K与V) × 层数 × (kv头数 × 每头维度) × token数 × 每元素字节`。ex08 实测账本（示意 7B 量级）：MHA(32 kv 头) = **512 KiB/token**；GQA(8 kv 头) = **128 KiB/token**——一条 4096 token 的请求就是 2GiB/512MiB，GQA 把 KV 内存降到 1/4，这是它成为现代模型标配的原因。**这个账本决定 serving 的一切**：并发度 ≈ (显存 - 权重 - 激活) / (每请求 KV)，(batch, seq) 直接对到内存表（ex08 [2] 给出 40GiB 预算下各组合的占用，batch=64×seq=8192 即超预算）。

```text
KV Cache 在"请求 × 层 × 头"上的形状（每格 = 一块 K 或 V 缓存）：
 请求 r（已生成 s 个 token）                 batch 个请求同时驻留 = 显存账本主体
 ┌───────── 层 1 ─────────┐   ┌───────── 层 32 ────────┐
 │ 头1: [K][V][K][V]...s格 │ … │ 头1: [K][V]...[K][V]   │   ← 每格 = head_dim × 2B
 │ 头2: [K][V][K][V]...    │   │ 头2: ...               │      （K 和 V 各占一半）
 └────────────────────────┘   └────────────────────────┘
 decode 每步新 token 只"追加一格"到每层每头的尾部 → 但这格要拷进显存 = 写带宽
 prefill 阶段则是一次性把前缀 s 个 token 的 K/V 全算出来填满这些格（算力密集）
```

**② prefill 与 decode 是两种负载**：prefill（处理输入前缀）是"长序列并行算一次"，算力密集；decode（逐 token 生成）每步只算一个 token，但要顺序读全量 KV Cache + 权重，**带宽密集**。serving 的全部优化（batch 大小、量化、算子融合）都在为这两者的分裂找平衡。

**③ batching 与 continuous batching**：把多个请求的 decode 步拼成一批（矩阵里多一行 = 多一个请求），摊薄权重读取 → 吞吐↑；代价是延迟（要等批攒够）与显存（每请求的 KV 都要常驻）。continuous batching（Orca 2022）不等整批结束，**做完一个补一个新**，让槽位不空转——ex08 [3] 用 CPU 事件模拟演示槽位占用与完成延迟（教学标定的步进常数，非硬件数字）。**ph22 心智的第二次显形**：KV Cache 就是"显存里的 Buffer Pool"——vLLM 的 PagedAttention 用页表管理 KV 块，做的是 ph22 页帧缓存同一件事（帧 = KV 块、淘汰 = 块换出、pin = 生成中请求占用的块不能换）；而"批的槽位"像极了 ph22 的组提交——攒批摊薄固定开销。

> **边界声明**：KV Cache/batching 本阶段只到"概念 + 内存账本 + CPU 调度模拟"（ex08 确定性模型）；真实 GPU 的吞吐/延迟数字需要 NVIDIA 环境实测（本机无 GPU，未在本环境验证）。显存账本公式本身是确定性的——它不依赖硬件，只依赖模型结构与 dtype。

### 3.10 CUDA C++ 基础：线程块模型与显存心智（概念，无 GPU）

> 本机无 NVIDIA GPU：本节只讲**概念与心智**，不提供任何 CUDA 实测数字（未在本环境验证）。验证路径：NVIDIA 环境 `nvcc -arch=native xxx.cu`；或云 GPU 上跑 NVIDIA 官方 CUDA samples。

为什么向量检索与推理引擎要 GPU：SIMD（3.3）在 CPU 上一次指令并行 4~8 个 float；GPU 把同一件事放大到**数千线程同时执行**——距离函数（归约）、矩阵乘法（attention/MLP 的 GEMM）都是"海量独立运算"，正是 GPU 的形态。**C++ 视角下 CUDA 只有四个新概念**：

| 概念 | 是什么 | 与 CPU C++ 的对应 |
|------|--------|------------------|
| kernel（核函数） | `__global__` 函数，在 GPU 上被 N 个线程执行 | 普通函数，但"调用一次 = 起 N 个线程并行跑同一函数体" |
| thread / block / grid | 线程组织：grid(块) → block(线程块) → thread | 三维循环下标：`blockIdx/threadIdx` 算出"我负责哪份数据" |
| 显存（device memory） | GPU 自己的内存，`cudaMalloc/cudaMemcpy` 管理 | 另一块内存空间，CPU 不能直接解引用——要显式搬运 |
| warp 与 SIMT | GPU 以 32 线程为一组同步执行同一条指令 | SIMD 的"线程版" |

**显存心智的三句话**（VectorAdd 级别即可建立）：① **host/device 分离**——`cudaMemcpy` 是唯一桥梁，来回拷贝常吃掉性能，工程关注"数据一次性传上去、kernel 反复用"；② **kernel 的性能由"占用率 × 访存合并"决定**——线程太少藏不住访存延迟、访存不连续（非合并访问）让带宽浪费，与 4.3 的"带宽受限"一脉相承；③ **归约（reduction）是向量检索在 GPU 上的基本动作**——你的 `search` 里那个 top-k 距离循环，在 GPU 上就是"每线程负责若干行、块内树形归约局部 top-k、再跨块归并"，Faiss 的 GPU 版 IndexFlat 就是这么写的。给本机的学习路径建议：先在 CPU 把距离内核与 top-k 写对（本阶段全部例子都做了），CUDA 只是把这套循环"换执行模型"——概念通了再上真机，一天就能把 ex03/project 的内核移植成第一个 kernel。

### 3.11 TensorRT plugin 基础：接口形态（概念，无 GPU）

TensorRT 是 NVIDIA 的推理优化引擎：把训练好的模型**编译成针对具体 GPU 的优化执行计划（engine）**，内置算子融合与精度选择（FP16/INT8）。**Plugin 解决的问题**：TensorRT 不认识模型里的自定义算子（如某种注意力变体、非标准激活、自定义距离内核）时，用户写一个 plugin 把它"教"给引擎。plugin 的接口形态是纯 C++（正是 C++ 在 AI Infra 的典型位置），核心是**描述符类 + 两个工厂函数**：

```cpp
// TensorRT plugin 接口形态（概念示意，非完整 API；未在本环境验证）
class MyPlugin : public nvinfer1::IPluginV2DynamicExt {
    // getOutputDimensions / supportsFormatCombination / enqueue
    //   └ enqueue：实际执行——拿到输入输出 GPU 指针，在这里调你的 CUDA kernel
};
// 两个工厂：plugin 的"构造"必须能跨进程重建（engine 会序列化成文件分发部署）
extern "C" nvinfer1::IPluginV2* createMyPlugin(const void* data, size_t len);
extern "C" nvinfer1::IPluginV2* deserializeMyPlugin(const void* data, size_t len);
```

**为什么长这样**：plugin 要跨"建 engine 的进程"与"跑 engine 的进程"存活（engine 序列化成文件后分发部署到别的机器），所以每个 plugin 必须自带"序列化 / 反序列化自己"的工厂；`enqueue` 是唯一真正的计算入口，输入输出是裸 GPU 指针——**所有权与生命周期边界（谁分配谁释放）在这里是 ABI 级别的纪律**，正是 ph19（动态库/插件机制）+ ph20（跨语言边界）教的那套东西的 TensorRT 实例。本阶段对它的要求是"读得懂接口形态、知道它解决什么问题"；roadmap §23 把「TensorRT plugin demo」列为推荐项目——那属于**后续可深入方向**（需 NVIDIA 环境，未在本环境验证，不另设编号阶段），本阶段用概念 + 接口骨架收口。

## 4. 底层原理

### 4.1 召回率、延迟、内存的三角与 ANN 的误差来源

向量检索的全部指标可以收进一个三角：**召回率（recall@k）** 衡量"近似答案里有多少是真近邻"，**延迟/QPS** 衡量快不快，**内存** 衡量装不装得下。暴力检索站在三角的一个角上（召回恒 1.0、延迟 O(N·D)、内存 = 原向量）；**一切 ANN 结构都是在三角内选点**——把某条边压下去，必然把另外的边顶起来。误差（召回损失）只有三个来源，任何 ANN 的"近似"都来自其中一个或多个：

1. **访问遗漏**：根本没评估到真近邻——IVF 的真近邻在没 probe 的桶里、HNSW 的贪心路径没走到真近邻所在的图区域。这是**结构参数**（nprobe/efSearch/M）控制的误差。
2. **量化近似**：评估到的是"压缩后的代理"，与真实距离有偏差——PQ 的码字不是真向量。这是**压缩参数**（段数/码字数）控制的误差，见 4.4。
3. **排序抖动**：top-k 边界附近距离接近的向量谁先谁后无所谓，但精确率统计会把它算成"错"——数据分布本身带来的不可消除噪声。

**为什么"内存"也进三角**：把整库放内存 vs 放 SSD 是两个数量级的成本差；DiskANN 一类"图 + SSD"方案的思路就是把三角里的内存边换掉——牺牲一点延迟换容量。工程判断的落点永远是一句"我的约束是哪个"：内存够 → HNSW（4.1 实测 98.55% recall 换 3.2x）；内存紧 → PQ/标量量化；库太大装不进内存 → SSD 图索引（工业级方向）。project 的验收输出（recall/QPS/P95/内存）就是为让你养成"报检索性能必须四件套一起报"的习惯——只报 QPS 不报召回是 ANN 评测最常见的失真。

### 4.2 HNSW 的贪心为什么能"导航"：小世界性与连边启发式

HNSW 的搜索是贪心 + 局部扩展，却能达到近全局的召回，原理分两层。**第一层：图本身要有"导航性"（navigability）**。完全随机的图（每点随便连几个邻居）上贪心会困在局部；但"连局部最近邻"的图有**小世界性质**：真实数据（尤其嵌入）通常低维流形状，最近邻边跟着流形走，从任意点出发沿最近邻前进，像沿等高线下山，最终能到任意目标邻域——层数越多、每层边越稀疏，等效于"梯度下降 + 退火"：高层大步长（跳过无关区域）、低层小步长（精确定位）。**第二层：搜索本身是"在已见里取最近、从最近处扩展"**（ef 搜索的候选堆语义，见 3.4 代码）——它保证每步扩展的都是"当前信息下最可能有真近邻的方向"，访问量只与 ef 和图的平均出度有关，与全库 N 基本无关，这就是图搜索能把距离评估从 N 压到 O(ef·出度) 的原因（exercises/sol-04 实测：给定 8 度图上 ef=1/8/64 的平均评估次数 30/91/352 次 vs 全库 4000 次，recall 3.8%/45%/89.8%——评估次数与召回由 ef 直接对价）。

**工程 HNSW 比 toy 多的一步——连边启发式（neighbor selection heuristic）**，值得讲清它防的是什么：插入时若只连"最近的 M 个"，入口点附近的节点边会高度同质化（全指向同一小簇），远处节点反而可达性差；启发式做法是"先连最近的一个，再在"与已选邻居夹角够大"的候选里补"，用**多样性**保可达性——这是"为什么实际 HNSW 比 toy 召回稳"的核心差异，也是读 Faiss `HNSW.cpp` 时第一个值得盯的函数。理解了这两层，"HNSW 是黑魔法"就变成了"图导航性 + 分层 + 边多样性"三个可解释的设计。

### 4.3 SIMD 的缓存与带宽视角：计算受限 vs 带宽受限

ex03/sol-03 实测里出现过一个"反直觉"现象：同样的 NEON 代码，L2 内小数据时加速比 ~2.5~2.8x，project 全库 25MB 流式扫描时只有 ~1.8x。原因在内存层次。**当数据能驻留缓存时，CPU 的 ALU（算距离）比内存（喂数据）慢，加速比接近 SIMD 指令宽度**；**当数据远超缓存时，内存带宽成为瓶颈——标量和 SIMD 都受"每秒能从 DRAM 读多少字节"约束，加速比被压缩向 1**。判断方法只有一条（ph18 的铁律）：**测**——把数据规模从"L2 内"扫到"超缓存"看加速比曲线（sol-03 [2][3] 就是这条曲线的最小版）。这个认知直接决定工程选择：

- 单条 query 对海量库全扫（RAG 的 top-k over 百万级）→ **带宽受限**，优化手段是"减少每字节的浪费"（fp32→fp16/int8 量化，半条带宽双倍吞吐）或结构剪枝（IVF/HNSW 让数据根本不被扫到），而不是抠 SIMD 指令；
- 反复查询同一批热数据（缓存命中）→ **计算受限**，SIMD 与多累加器收益显著；
- ANN benchmark 的数字只有在"同一数据规模 + 同一机器 + 同一批次策略"下才可比较——这正是项目验收要求四件套的原因。

### 4.4 PQ 量化误差的直觉：质心分配误差 + 子空间独立假设

PQ 把 d 维向量切成 m 段、每段独立量化到 k 个码字。它的误差来自两层近似：**质心误差**——每段真实值被"最近的码字"代替，段内距离计算全用码字间的表查完成；**子空间独立假设**——把 d 维空间当成 m 个互不相关的 d/m 维子空间的笛卡尔积，实际数据各维相关时这个假设不成立，量化就浪费码字。直觉上两个推论：① **段数 m 越少、每段越长，量化越接近全空间聚类但码本需求指数涨**（m=1 退化成全空间 k-means）；② **码字数 k 越大每段表达越精细但码本与存储都涨**。工程经验是 k=256（每段 1B）配 m≈d/8~d/4 左右是常用带；d=128 的向量压缩到 32B（PQ32）是经典配置，内存降 16 倍、recall 损失可控——但**"可控"必须在你的数据上实测**（Faiss 建 `IndexPQ` 后同样跑 recall-QPS，别信默认值）。量化误差还与 4.1 的"量化近似"误差源直接对应：IVF 桶里放的是 PQ 压缩码，query 与码的距离是查表近似，top-k 用的是代理距离排序——代理排序抖动就是误差来源 2 在桶内的体现。

## 5. 使用场景

**向量检索与 AI 推理引擎的 C++ 工程落点**——本阶段各组件各自回答一个真实问题：

| 场景 | 用什么 | 依据 |
|------|--------|------|
| RAG：文档/片段检索（语义召回 → 喂给 LLM） | embedding + HNSW/IVF（海量）或 flat（万级小库） | 召回-延迟-内存三角（4.1）；万级以下 flat SIMD 已够（project QPS 实测） |
| 推荐/相关性打分（召回候选后精排） | IP（要长度/热度信号）或归一化后 IP | 度量语义选择（3.1）；"召回粗排 + 精排"两段式架构与 flat/ANN 分层对应 |
| 去重/聚类/相似过滤（找"几乎一样"的） | 精确度要求高 → flat 或小 nprobe/大 efSearch | 误差来源与参数对价（4.1/3.4/3.5） |
| 亿级向量、内存是硬约束 | IVF + PQ（或标量量化） | 量化把内存降到 ~1B/维（3.5/4.4） |
| 检索必须带业务条件 | metadata filter：filter-then-search + 复查 | 倒排前置在 ANN 上放大收益；复查不可省（3.6/ex05） |
| 索引要跨重启存活 | 快照文件（temp+fsync+rename+校验尾）+ 增量 WAL | ph22 SSTable 心智整包平移（3.7/ex06/project） |
| 要给 Python AI 生态当高性能后端 | C++ 检索/推理扩展层（pybind11/C ABI） | ph20 已铺；roadmap §23 必会概念「C++ 常用于 Python AI 系统背后的高性能扩展层」 |
| LLM 服务的并发与吞吐 | batching / continuous batching / KV Cache 预算 | KV 账本决定并发上限（3.9/ex08）；显存是 serving 的第一约束 |
| 自定义算子进推理引擎 | TensorRT plugin | 序列化工厂 + enqueue 的 ABI 纪律（3.11，需 NVIDIA） |

**不适合**的场景：数据规模小到"SIMD flat 就够了"还要上 ANN（召回损失没有换回任何东西，4.1 的"报告四件套"会让你看到这点）；强一致分布式检索（多副本/事务属工业级向量库方向）；GPU 内核级调优与 TensorRT 生产 plugin（需 NVIDIA 环境，属后续方向）。

**与 Python AI 生态的分工**（roadmap §23 必会概念 8 的展开）：Python 生态负责**把语义变成向量**（LLM embedding 调用、数据处理、评估脚本、原型迭代），C++ 负责**把向量变成低延迟的检索/推理**。语言分界线在"一次写好、反复执行、延迟敏感"的内核（距离、top-k、attention、KV 管理）——这正是 pybind11/C ABI 包装层的形状（ph20 的 Python 调用 C++ 向量检索库项目即此）。给分析层的观察：**AI Infra 的分工不是"Python 写业务、C++ 写库"这么粗，而是"每次调用成本高且稀疏的（模型调用）留在 Python，每次执行成本低但高频的（距离/检索/批量算子）下沉 C++"**。

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：

| 维度 | C++（本阶段） | Rust | Go |
|------|--------------|------|-----|
| 代表实现 | Faiss / Milvus 内核 | 自研 HNSW/向量内核为主（生态无 Faiss 体量） | 少（生态偏服务层，检索内核多 cgo 调 C++） |
| 距离/SIMD 能力 | NEON/AVX 内建或自动向量化，零抽象税 | 同级别（`std::simd` 实验性；可手写内建，unsafe 收口） | 无内建 SIMD 惯用法；依赖汇编或 cgo 调 C |
| 内存布局直控 | 行主序矩阵 / 邻接表全手工（RAII） | 同级别（Vec + 借用检查保证邻接表无悬空） | 有 slice 但 GC 搬对象，紧布局要小心 |
| 抽象成本 | 索引族多态少量虚函数；热路径可绕开 | trait 泛型单态化近零成本 | interface 间接调用 + GC 停顿 |
| 生态位置 | 向量检索/AI Infra 的"库与内核"层 | 内存安全 + 性能都要时的重写候选 | 云原生编排与在线服务的胶水层 |
| 谁更适合 | 与 Python 深度互操作的高性能检索库（Faiss 路线） | 想要 C++ 性能又要内存安全的内核重写 | 服务组装、上线快、吞吐用并发撑 |

三条观察：① **SIMD 距离内核是 C++/Rust 的主场**——Go 在这里要么退化到标量要么 cgo 绕道，这是"语言能力决定能写在哪个层"的样本；② 向量检索结构（图/倒排/邻接表）比存储引擎更"引用密集"（节点互指、无 GC 更稳），Rust 的借用/所有权在这里比 C++ 的纪律更省心，而 C++ 用 RAII + 容器纪律达成同样的安全性（本阶段代码示范）；③ 给 Tenet 的启示：若 Tenet 要进 AI Infra，**"SIMD 内建 + 连续内存布局 + 无 GC 可选"是硬需求，Python/C++ 互操作边界（C ABI 或 pybind 等价物）是生态入场券**。

## 6. 代码示例

> 完整可运行文件在 [`examples/`](./examples/)，构建/运行命令与逐文件教学点见其 README。**ex01~ex06、ex08 在 Apple clang 21.0.0 下 `clang++ -std=c++20 -Wall -Wextra` 编译零警告、运行断言全绿**（ex03 另过 Homebrew clang 21.1.8）；**ex07（Faiss）经 faiss 1.9.0 /tmp 源码构建实测**（命令见其文件头与 examples/README）。通用命令：`clang++ -std=c++20 -O2 -Wall -Wextra exNN-<名>.cpp -o /tmp/ph23-exNN && /tmp/ph23-exNN`（产物一律在 /tmp）。以下给出示例与主文档小节的映射及关键实测输出。

| 示例文件 | 对应小节 | 实测输出关键行（本环境运行） |
|---------|---------|------------------------------|
| `ex01-distance-metrics.cpp` | 3.1 | 恒等式 lhs==rhs；归一化库 l2/ip/cos 三排序逐位一致 |
| `ex02-brute-force-topk.cpp` | 3.2 | top-k 与全排序一致；n=5000×64 维 ≈ 109 µs/query（~9.1k QPS） |
| `ex03-simd-distance.cpp` | 3.3 | -O2 标量 49.4 → NEON 17.9 ns/op（2.76x）；-O3 -ffast-math 自动向量化 ≈ NEON |
| `ex04-hnsw-toy.cpp` | 3.4 | recall@10=98.55%；HNSW 36.4 µs vs brute 115.9 µs（3.2x） |
| `ex05-metadata-filter.cpp` | 3.6 | 高选择性 A=77µs/2 万次检查 vs B=24µs/5381 次（3.2x）；低选择性差距消失 |
| `ex06-index-persistence.cpp` | 3.7 | 快照 1,056,028 字节（≈1.03× 原始向量）；篡改一字节即校验拦截 |
| `ex07-faiss-bench.cpp` | 3.5/3.8 | IVF/HNSW 的 nprobe/efSearch 扫描：recall 与耗时同向上移（聚类高斯数据，faiss 1.9.0 实测） |
| `ex08-inference-serving-concepts.cpp` | 3.9 | MHA 512 KiB/token vs GQA 128 KiB/token；40GiB 预算占用表；调度模拟吞吐/延迟 |

```cpp
// examples/ex04-hnsw-toy.cpp —— ef 搜索与 recall 计量（节选，已验证）
// 验证环境：Apple clang 21.0.0；命令见文件头
double recall_sum = 0.0;
for (const auto& q : qs) {
    const auto gt = brute(q);                 // 暴力 ground truth
    const auto hits = index.search(q, k);     // HNSW 近似搜索
    /* 统计 hits ∩ gt 的重叠数 → recall@10 */
}
std::printf("recall@10 = %.2f%%（M=8, efC=64, efS=48）\n", recall * 100.0);
```

exercises/ 的 5 题参考实现与 project/（vsearch：SIMD 加速 brute-force 检索库 + 快照持久化）的验证状态：练习 1~5 已实测——练习 1~4 在 Apple clang 21.0.0 下零警告断言全绿（sol-03 双编译器三形态），练习 5（Faiss，均匀随机数据扫 nprobe/efSearch）经 faiss 1.9.0 /tmp 源码构建实测（命令见其文件头，输出节选：HNSW efSearch 16/64/256 → recall 0.36/0.71/0.95 @ 39/144/723 µs）；project `make test` 自测全绿、`make cross`（Homebrew clang 21.1.8）与 `make sanitize`（ASan/UBSan）零报告，`make bench`/`make bench_scalar` 实测表见 project/README（SIMD 版 QPS 1102 vs 标量 601 ≈ 1.83x，P50 654 vs 1170 µs，P95 1810 vs 3373 µs）。全部代码遵循 cpp-coding-standards：无裸 new/delete（R.11）、`const`/`enum class`/RAII 默认、教学性简化以注释注明（如 ex06 用 FNV-1a 作教学校验、project 用"整文件快照"替代 WAL）。

## 7. 总结

### 关键要点

1. **度量是第一参数**：L2 问位置、IP 问"方向 × 长度"、cosine 只看方向；归一化后 l2/ip/cos 排序同序，"归一化 + IP"是工程捷径（3.1/ex01/project 自测）
2. **flat 检索是锚点不是古董**：召回恒 1.0、O(N·D) 但 SIMD 后小库毫秒级；它是 ground truth、性能基线，也是"该不该上 ANN"的裁判（3.2/ex02/project）
3. **SIMD 的本质是"一条指令算多个 float"**：NEON 手写 / `-O3 -ffast-math` 自动向量化两条路都要会；收益上限由"计算受限 vs 带宽受限"决定（3.3/ex03/sol-03/4.3）
4. **HNSW = 跳表的图版**：高层稀疏导航、层 0 密集收尾；贪心下潜 + ef 搜索把评估次数从 N 压到 O(ef·出度)；M/efC/efS 是三角旋钮（3.4/ex04/sol-04）
5. **IVF 管"少算"、PQ 管"少存"**：nlist/nprobe 对价召回，m/k 对价内存；`IVF4096,PQ32` 就是两个杠杆串起来（3.5/4.4）
6. **metadata filter 必须"候选复查"**：倒排前置在 ANN 上收益放大，但复查谓词不可省；向量库的删除/更新是 ph22 版本可见性心智的翻版（3.6/ex05）
7. **向量索引持久化 = ph22 整包平移**：不可变快照 + temp/fsync/rename + 校验尾；WAL 增量与合并是 ph22 的 WAL/Compaction（3.7/ex06/project）
8. **Faiss 是向量检索的 LevelDB**：index_factory 字符串选算法、train/add/search 生命周期显式、统一抽象基类；读它从 IndexFlat + 字符串解析开始（3.8/ex07）
9. **KV Cache 的字节由模型结构唯一决定**：MHA 512 KiB/token vs GQA 128 KiB/token；KV 账本决定并发上限；PagedAttention 是显存里的 Buffer Pool（3.9/ex08）
10. **CUDA/TensorRT 对 CPU 版 C++ 是"换执行模型"不是"换语言"**：距离内核的归约在 GPU 上是树形归约、plugin 的 enqueue 是裸指针边界——概念与 ABI 纪律先于硬件（3.10/3.11，未在本环境验证）

### ph22 → ph23 心智平移核对表（收官复盘）

本阶段是 ph22「下一阶段」预告的兑现，逐条核对"ph22 的心智搬到向量库/推理服务后长什么样"：

| ph22 的心智（来源） | ph23 里平移成 | 兑现位置 |
|--------------------|--------------|---------|
| SSTable 不可变有序文件 + 稀疏索引（3.3） | 向量快照文件：定长 header + id 表 + 行主序矩阵 + 校验尾 | 3.7/ex06/project `vsearch` save/load |
| 整文件读入内存是教学简化 → 页缓存（3.3/3.7） | 向量库同样先"整读"再上 Buffer Pool；缓存里只有干净页 | 3.7（ex06 注释）、3.9 KV Cache 对照 |
| WAL 先写意图再改状态 + 作废重建（3.1/3.2） | 向量增量写日志 + 定期 flush 新快照 | 3.7 ASCII 多代图 |
| Compaction 收空间/真删 tombstone（3.5） | 旧代快照合并，回收被覆盖/删除向量 | 3.7 |
| Bloom Filter 挡"肯定不在"（3.4） | 同类"预过滤"思想出现在 metadata filter 倒排前置 | 3.6/ex05 |
| Buffer Pool 的"帧 = 缓存块 + pin"（3.7） | KV Cache 的"页表 = KV 块 + 生成中请求 pin"（PagedAttention） | 3.9 |
| 组提交：攒批摊薄 fsync 固定成本（4.3） | batching：攒请求摊薄 decode 的权重读取固定成本 | 3.9/ex08 |
| tombstone = "删除 = 写新版本"（3.2/3.8） | 向量删除/upsert 的版本可见性（filter 一致性） | 3.6 末尾点到 |
| Iterator/统一读面（3.9） | Faiss 的统一 Index 基类 + index_factory 字符串选算法 | 3.8 |

对照完这张表，"向量库是存储引擎 + 一套新结构"这句话就有了具体证据：**磁盘/缓存/日志层几乎原样搬，新增的是度量（3.1）、SIMD（3.3）、图/量化（3.4/3.5）与 serving 的 KV 账本（3.9）**。

### 阶段验收清单

- [ ] 能解释 L2/Cosine/Inner Product 的适用场景，并说明"归一化 + IP = cosine"（3.1/练习 2）
- [ ] 能完成 brute-force topK 并说出它为什么是 ANN 的 ground truth（3.2/练习 1/project）
- [ ] 能输出 recall、QPS、P95 延迟和内存占用四件套（project/ 的验收输出表）
- [ ] 能解释 SIMD 为什么加速距离计算：一条指令多个 float、依赖链打散、带宽受限的边界（3.3/ex03/4.3）
- [ ] 能画/讲清 HNSW 的分层图、插入（贪心下潜 + 逐层连边）与搜索（ef）流程，说出 M/efConstruction/efSearch 的语义（3.4/ex04）
- [ ] 能说明 IVF/PQ 的基本取舍：倒排省距离次数、量化省内存，召回损失各从哪来（3.5/4.4）
- [ ] 能解释 metadata filter 的两种形态与"复查铁律"（3.6/ex05）
- [ ] 能用 ph22 的 SSTable/Buffer Pool 心智解释向量索引持久化与 KV Cache 管理（3.7/3.9）
- [ ] 能用 Faiss 跑通一个向量检索 benchmark，并解释 nprobe/efSearch 增大时 recall 与耗时为何同向（ex07/练习 5，本机已实测）
- [ ] 能说明推理服务中 batching、KV Cache 和显存占用的关系（3.9/ex08）

### 跨语言对比

见第 5 节末对照表。给 analysis/ 与 Tenet 合成的三条启示：① **"能不能写距离内核"是区分系统语言与胶水语言的试金石**——C++/Rust 手写 SIMD、Go 靠并发与 cgo、Python 只当调度层；② **向量结构的"引用密集 + 无 GC 偏好"让 Rust 的所有权比 C++ 的纪律更省心、C++ 用 RAII 追平**——两者共享"连续布局 + 直控内存"的硬需求；③ 若 Tenet 想进 AI Infra，**C ABI 互操作边界 + SIMD 内建 + 可选无 GC 是入场券**（ph19/ph20/本阶段三处交叉印证）。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 5 题，与 roadmap §23「练习」小节一一对应：brute-force vector search（练习 1）/ L2·cosine·IP 三种距离（练习 2）/ 距离 benchmark + SIMD 优化（练习 3）/ HNSW 节点与邻接表基础搜索（练习 4）/ Faiss IVF·HNSW 召回率（练习 5）。卡住时回看 examples/ 对应文件的手法。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**vsearch —— SIMD 加速的 brute-force 检索库 + 快照持久化**（roadmap §23 推荐项目取其一落地；其余推荐项目去向见 project/README：HNSW toy 在 examples/ex04、Faiss benchmark 在 ex07/练习 5、TensorRT plugin demo 属后续方向、batching 原型在 ex08、Python 调用见 ph20）。`make test` 自测 5 项断言、`make bench`/`make bench_scalar` 输出四件套实测表（SIMD 版 QPS 1102 vs 标量 601，P50 654 vs 1170 µs，索引 33.5 MiB/进程 RSS 87.3 MiB）、`make cross`/`make sanitize` 全绿。建议完成练习后再动手——它是 ph01~ph23 全部技能的收官考场。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make clean && make test` 退出码 0、ASan/UBSan 零报告、能复现实测表、`make clean` 零残留）

### 下一阶段

**本阶段是 C++ 学习路线的终点（roadmap 第 23 节即最后一节，其后只有「附录：阶段性项目验收标准」这一非编号章节，不存在 ph24）**——ph01~ph23 走完「语法 → 现代 C++ → 并发网络 → 存储/AI 地基 → 向量检索与 AI 推理引擎」的完整闭环，落点是"用 C++ 写 AI Infra 底层"的能力。终点之后不再另设编号阶段，但有几个可继续深入的**方向**（各自通向别的工程纵深，而非 C++ 路线的新阶段）：

- **GPU 内核级优化（CUDA）**：把本阶段的距离/top-k/归约内核移植成 CUDA kernel，学线程块组织、共享内存归约、访存合并——本机无 GPU，需 NVIDIA 环境，方向入口见 3.10；
- **TensorRT 生产化 plugin**：把自定义算子写成可序列化、可部署的 plugin 并过性能验收——需 NVIDIA 环境，接口形态见 3.11；
- **工业级向量库工程（Faiss/Milvus）**：在 Faiss 源码里补"邻接启发式、量化训练、并发写入"这些 toy 之外的部分，或参与开源——本阶段 3.8 已给阅读引导，roadmap §21 就埋伏的「HNSW toy 从数据结构习题长成工业索引」在这里得到完整答案；
- **推理服务工程化**：KV Cache 页表化（vLLM PagedAttention 是 ph22 Buffer Pool 的显存版）、continuous batching 调度器、量化推理——从 ex08 的 CPU 账本模型走向真实 serving；
- **Python AI 生态的高性能扩展**：ph20 的 pybind11/C ABI 路线 + 本阶段的检索/推理内核，合成"Python 调 C++ 的 RAG 检索服务"——roadmap §23 必会概念 8 的工程兑现。

把最后一句话带出 C++ 路线：**ph22 教你让数据"跨崩溃活下来"，ph23 教你让数据"被更快地找到"——两者共用同一套存储与缓存心智，这正是 C++ 站在 AI Infra 底层的原因**。23 个阶段全部完成：恭喜，去写下一个真实系统的高性能内核吧。




