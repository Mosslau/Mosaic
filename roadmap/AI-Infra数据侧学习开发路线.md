# AI Infra 数据侧学习开发路线

> 版本：v2 · 执行路线
> 定位：把 `engineering/` 两个平台、`languages/` 6 门语言 + Tenet、`algorithms/` 42 个算法编排成一条 60 个月、可验收的路线。
> 关系：本页是**编排层**，不替代各域文档；D 阶段、语言阶段、算法细节以各域 README / 路线文档为准。
> 纪律：每个路线阶段必须有「**命令 + 输入 + 观察结果**」；没有可重跑证据，不算完成。

## 0. 定位与边界

这条路线回答三个问题：

1. **先做什么、后做什么**：两个平台、三条数据侧线、6 门语言、42 个算法、Tenet 编译器如何排进同一张日历。
2. **每个阶段交付什么**：不是“看完”，而是可运行的系统、可复现的数据集、可重跑的证据。
3. **怎么算完成**：命令、输入、观察结果三要素齐全，第二个人能按命令重跑。

**不做什么**：

- 不替代 `engineering/` 的 D 阶段设计；本页只引用和排序。
- 不重写 `languages/studies/` 的 126 个阶段；本页按语言批次汇总，具体命令在各阶段 README。
- 不重写 `algorithms/` 的 42 个算法；本页按算法族批次跑现有测试。
- 不新增第三个平台；LLM 训练数据工程与训练数据通路归 **T2 AI 平台**。

**状态口径**：

- **仓库完成度**：数据平台 0/13、AI 平台 0/11、语言 126/126、算法 42/42。
- **个人路线进度**：从 0 开始，按本页阶段表逐项打勾；两者不是一回事。

**命令口径**：

- T1/T2（含 T2-B/T2-C）的工程尚未实现，表中的命令是**验收命令草案**，开工时固化到各阶段 README。
- 语言/算法命令是**现有可执行命令**，随各域 README 更新。

## 1. 四轨模型与总日历

### 1.1 四轨

| 轨道 | 内容 | 规模 | 真相源 |
|---|---|---|---|
| **T1 数据平台** | 集成、湖仓、计算、调度、语义、目录、治理、服务、控制面、生产化 | 13 个 D 阶段 + T1-S（共 14 个路线阶段） | [`engineering/data-platform/`](../engineering/data-platform/) |
| **T2 AI 平台** | T2-A 平台主链；T2-B LLM 训练数据工程；T2-C 训练数据通路 | 11 个 D 阶段 + 10 + 9 个专项模块 | [`engineering/ai-platform/`](../engineering/ai-platform/) |
| **T3 语言 + Tenet** | 6 门语言 126 阶段；Tenet 3 个编译器 + 三端一致性 | 6 批 + 4 项 | [`languages/`](../languages/) |
| **T4 算法** | 搜索、统计 ML、深度学习、Transformer、生成式 | 42 个，5 族 | [`algorithms/`](../algorithms/) |

T2 的三条子轨：

```text
T2-A 平台主链        D0–D10
T2-B LLM 训练数据工程  LD-1…LD-10  → 支撑 D2 的 A2-4…A2-8
T2-C 训练数据通路      TDP-1…TDP-9  → 支撑 D7 的 A7-4…A7-10
```

T2-B/T2-C 是 D2/D7 的扩展专项，**不新增 D 阶段**，也不改变 24 个 D 阶段的总数；后续若独立成阶段，再单独升版重编号。

### 1.2 60 个月总日历

| 年 | 主平台线 | 数据侧专项 | 语言 | 算法 / Tenet |
|---|---|---|---|---|
| 第 1 年 | T1 D0–D6；T2-D0/D1 | T2-B LD-1–LD-4；T1-S | Python、Go | 算法 p01/p02 |
| 第 2 年 | T1 D7–D12；T2-A D2–D5 | T2-B LD-5–LD-10 | Java、C | 算法 p03 |
| 第 3 年 | T2-A D6–D10 | T2-C TDP-1–TDP-9 | C++、Rust | 算法 p04/p05；Tenet 起步 |
| 第 4 年 | 生产化 + X1–X4 | T2-C 深化 | 语言收口 | Tenet 3 后端 |
| 第 5 年 | X5–X7 全栈集成 | 复盘/文档 | 复习 | 算法/Tenet 收口 |

T2-B 的 LD-1–LD-4 可先用本地脚本做，不依赖 D2 平台；LD-5 起接入 D2/D4 的语料与快照。
T1-S 计入路线阶段，随第 1 年 T1 阶段并行。

### 1.3 周配额

| 强度 | 主平台 + 专项 | 语言 | 算法 | Tenet | 预计周期 |
|---|---:|---:|---:|---:|---:|
| 标准 | 12 h | 5 h | 2 h | 1 h | 60 个月 |
| 加速 | 18 h | 7 h | 3 h | 2 h | 48 个月 |
| 保守 | 6 h | 2.5 h | 1 h | 0.5 h | 90 个月 |

没有“删内容换短周期”这一档；只能延长周期或提高每周投入。

## 2. T1 数据平台（D0–D12）

> 详细架构、选型、契约、验收标准见 [`通用数据平台建设路线.md`](../engineering/data-platform/通用数据平台建设路线.md)。下表只加排序和证据。

| 阶段 | 建什么 | 命令（开工后固化） | 输入 | 观察 / 通过 |
|---|---|---|---|---|
| T1-D0 | 基础设施 | `make up && make health` | `deploy/compose.yaml` | Kafka/MinIO/PG/Redis 健康；Grafana 200 |
| T1-D1 | 契约与控制内核 | `make verify V1` | `contracts/envelope.json` | dummy 源注册；`trace_id` + 账本事件可查 |
| T1-D2 | 存储底座 | `make verify V2` | `datasets/orders_1g.parquet` | 建表/写入；`snapshot_id` 可查；count 对账 |
| T1-D3 | 数据集成 | `make verify V3` | `datasets/cdc_sample.jsonl` | 源→Kafka→Iceberg 可查；重放两次不变 |
| T1-D4 | 计算引擎 | `make verify V4` | `jobs/stream.sql` | 批/流任务完成；checkpoint 可查；重启续跑 |
| T1-D5 | 开发工作台与调度 | `make verify V5` | `portal/source_form.yaml` | 门户新增源；dev→prod 发布/回滚 |
| T1-D6 | 语义与特征 | `make verify V6` | `models/metrics.yaml`、`features/` | 指标复用；`V6-4` 最小 Feature Store 离线/在线一致 |
| T1-D7 | 统一目录 | `make verify V7` | `catalog/seed.json` | 指标→源表血缘；字段级 ≥90% |
| T1-D8 | 数据治理 | `make verify V8` | `quality/rules.yaml`、`pii_sample.csv` | 脏数据阻断；越权拒绝；PII 掩码；成本可分摊 |
| T1-D9 | 服务化 | `make verify V9` | `api/query.http` | API/BI 同口径；401/429/审计生效 |
| T1-D10 | AI 工程化 | `make verify V10` | `eval/questions_100.jsonl` | 问数 ≥80%；日志证明不直产 SQL |
| T1-D11 | 控制面与运营 | `make verify V11` | `stack.yaml` | 一条命令拉起；trace/成本/台账闭环 |
| T1-D12 | 生产化 | `make verify V12` | `chaos/kill_node.sh` | 节点故障自愈；备份恢复；压测/回滚达标 |

### 2.1 T1-S 分析 SQL / 数仓建模（学习子轨，计入 59 个路线阶段）

| 项 | 内容 | 命令 / 输入 / 观察 |
|---|---|---|
| 分析 SQL | 20 条：聚合、窗口、Join、去重、同比环比 | `psql -f sql/analysis_20.sql`；输入 `datasets/orders_events`；观察结果 + `EXPLAIN` |
| 维度建模 | 1 个星型模型：事实表 + 维表 + 指标口径 | DDL + `metric_def`；输入 ODS 样例；观察 ODS→DWD→DWS 口径说明 |

## 3. T2 AI 平台（D0–D10 + T2-B/T2-C）

### 3.1 T2-A 平台主链（D0–D10）

> 详细设计见 [`AI平台建设路线.md`](../engineering/ai-platform/AI平台建设路线.md)。D2/D3/D7/D9/D10 已扩验收，版本 v15。

| 阶段 | 建什么 | 命令（开工后固化） | 输入 | 观察 / 通过 |
|---|---|---|---|---|
| T2-D0 | 基础设施 | `make up && make health` | `deploy/compose.yaml` | K8s/MinIO/PG/Vault/Prometheus/Grafana 健康 |
| T2-D1 | 契约与控制内核 | `make verify A1` | `contracts/asset_ref.json` | dummy 服务注册；trace + 账本可查 |
| T2-D2 | 数据与语料（含训练数据工程/多模态数据） | `make verify A2` | `corpus/10gb/`、`multimodal/` | 10GB 链；A2-4…A2-8（packing/数据卡/标注合成/多模态） |
| T2-D3 | 检索与知识（含持续评测） | `make verify A3` | `eval/qa_100.jsonl` | 答案+引用；100 题回归；A3-4 漂移基线 |
| T2-D4 | 存储与版本 | `make verify A4` | `iceberg/snapshot.json` | 同一 `snapshotId` 数据 + 索引复现 |
| T2-D5 | 推理与服务 | `make verify A5` | `models/qwen-small/` | OpenAI SDK 只改 `base_url`；TTFT/TPOT/P95 |
| T2-D6 | 算力与调度 | `make verify A6` | `gpu/queue.yaml` | 队列/配额；`已分配+空闲=总量`；GPU·秒可归集 |
| T2-D7 | 训练与微调（含预训练/对齐/多模态训练支持） | `make verify A7` | `train/lora.yaml`、`train/pretrain_smoke.yaml` | LoRA/MLflow；A7-4…A7-10 支持性 smoke |
| T2-D8 | Agent 与运行时 | `make verify A8` | `runtime/ports.yaml` | 两个运行时通过同一 `RuntimePort` |
| T2-D9 | 控制面与运营（含质量/反馈） | `make verify A9` | `stack.yaml`、`feedback/` | 一条命令拉起；A9-5/6 质量看板与反馈日志 |
| T2-D10 | 生产化（含护栏/数据飞轮） | `make verify A10` | `chaos/kill_node.sh`、`guardrails/` | 自愈/恢复/压测；A10-7/8 护栏与飞轮闭环 |

### 3.2 T2-B LLM 训练数据工程（LD-1…LD-10）

> 给 D2 补训练数据集构造/接入能力；对应验收 `A2-4`–`A2-8`。命令是待实现模块的验收草案。

| 编号 | 模块 | 命令 | 输入 | 观察 / 通过 |
|---|---|---|---|---|
| LD-1 | 来源与合规 | `python -m data.audit --manifest sources.yaml` | `sources.yaml` | 许可证/同意/保留字段齐全；高风险源被拒 |
| LD-2 | 解析与清洗 | `python -m data.clean --input raw/ --output clean/` | `raw/` 1GB 样本 | 解析率、语种分布、正文抽取可查 |
| LD-3 | 去重 | `python -m data.dedup --input clean/ --method minhash` | `clean/` | 重复率；误删抽样；MinHash 参数入档 |
| LD-4 | 质量与安全 | `python -m data.quality --input dedup/ --labels labels_200.jsonl` | `dedup/`、200 条标注 | PII/毒性 P/R；阈值与误杀率 |
| LD-5 | Tokenize 与 packing | `python -m data.pack --tokenizer tokenizer.json --seq-len 4096` | `dedup/` | tokens/doc；打包率；loss mask 测试 |
| LD-6 | 配比与课程 | `python -m data.mix --manifest mixture.yaml --ablation small` | `domains/` | 配比 manifest；小模型消融曲线 |
| LD-7 | 评测集与去污染 | `python -m data.contam --eval eval/golden.jsonl --corpus packed/` | `golden.jsonl`、`packed/` | n-gram/embedding 污染报告 |
| LD-8 | 数据集版本与数据卡 | `python -m data.card --snapshot <id>` | `packed/` | 数据卡；同快照重建同哈希 |
| LD-9 | 标注/合成数据接入 | `python -m data.augment --manifest annotate_synth.yaml` | 外部标注/合成 manifest | 质量抽检；许可/来源可追溯；不建 UI |
| LD-10 | 多模态数据接入 | `python -m data.multimodal --manifest mm.yaml` | 图文/音视频 manifest | 去重/质量/许可；小样本可训练 |

验收映射：

- `A2-1`–`A2-3` = LD-1–LD-3：10GB 全链、四类计数、去重/分片幂等。
- `A2-4` = LD-5 + LD-6：packing 与配比 manifest 可复现。
- `A2-5` = LD-4 + LD-7：质量/PII + 评测集/去污染报告。
- `A2-6` = LD-8：数据卡 + snapshot 哈希可重建。
- `A2-7` = LD-9：标注/合成数据接入可追溯。
- `A2-8` = LD-10：多模态数据 manifest/质量/许可。

### 3.3 T2-C 训练数据通路（TDP-1…TDP-9）

> 给 D7 补训练数据 IO/加载/恢复能力；TDP 对应 `A7-4`–`A7-6` / `A7-10`，`A7-7`–`A7-9` 见 D7 训练支持。

| 编号 | 模块 | 命令 | 输入 | 观察 / 通过 |
|---|---|---|---|---|
| TDP-1 | 格式与分片 | `python -m bench.format --input shards/ --format parquet,webdataset` | `shards/` | 顺序读吞吐；压缩比；shard 大小 |
| TDP-2 | 读取路径 | `python -m bench.read --source s3://bucket/corpus --cache nvme` | 对象存储 + NVMe | IO 利用率；缓存命中；首字节延迟 |
| TDP-3 | DataLoader | `python -m bench.loader --config loader.yaml` | `loader.yaml` | samples/s；GPU 利用率；worker 饱和度 |
| TDP-4 | 瓶颈定位 | `nsys profile python train.py --steps 100` | `train.py` | 瓶颈结论（IO/CPU/GPU）；优化前后加速比 |
| TDP-5 | Checkpoint | `python -m ckpt.save --sharded && kill -9 <pid>` | `ckpt/` | 恢复时间；无损坏；保存开销 |
| TDP-6 | 分布式与弹性 | `torchrun --nproc_per_node=8 train.py` | 2 节点 | 扩展效率；分片无重复/遗漏 |
| TDP-7 | 可复现 | `python train.py --seed 42` 两次 | 同一配置 | batch hash 一致；顺序可复现 |
| TDP-8 | 高级存储接口 | `python -m bench.remote --backend nfs,rdma` | 多机存储 | 吞吐/延迟 benchmark；接口可用，不承诺生产规模 |
| TDP-9 | 大规模 checkpoint | `python -m ckpt.bench --shards 64` | 分片 checkpoint | 保存/恢复时间；完整性校验 |

验收映射：

- `A7-1`–`A7-3` = LoRA 可复现、MLflow 登记、微调前后评测。
- `A7-4` = TDP-1–TDP-4：格式/读取/加载/瓶颈，吞吐达标。
- `A7-5` = TDP-5：checkpoint 原子写 + `kill -9` 恢复。
- `A7-6` = TDP-7：数据顺序/批次哈希可复现。TDP-6 是分布式扩展，不单独占验收项。
- `A7-10` = TDP-8 + TDP-9：高级存储接口与大规模 checkpoint 的 benchmark/完整性。
- `A7-7`/`A7-8`/`A7-9` = D7 训练支持：预训练/继续训练、RLHF/DPO、多模态训练（小样本 smoke，不占 TDP 模块）。

> TDP-8/9 是平台支持（接口 + benchmark），不承诺生产规模；生产触发条件：多机训练、IO 利用率 >80%、checkpoint >10min。

## 4. T3 语言 + Tenet

### 4.1 六门语言（126 阶段）

> 每个 `phNN` 的具体命令、输入、观察写在该阶段 README；本表只做批次汇总，不重写 126 个阶段。

| 语言 | 阶段数 | 批次命令 | 输入 | 观察 / 通过 |
|---|---:|---|---|---|
| C | 16 | `python3 .dsh/skills/tenetlang-notes/scripts/validate.py --links` + 各 phNN README 命令 | `languages/studies/c/ph*` | 16/16 交付物齐；examples/exercises/project 通过 |
| C++ | 23 | 同上 | `languages/studies/cpp/ph*` | 23/23 交付物齐 |
| Go | 21 | 同上 | `languages/studies/go/ph*` | 21/21 交付物齐 |
| Java | 23 | 同上 | `languages/studies/java/ph*` | 23/23 交付物齐 |
| Python | 18 | 同上 | `languages/studies/py/ph*` | 18/18 交付物齐 |
| Rust | 25 | 同上 | `languages/studies/rs/ph*` | 25/25 交付物齐 |

语言顺序：Python → Go → Java → C → C++ → Rust。Python/Go/Java 服务 T1/T2；C/C++/Rust 服务 T2-C 与 Tenet。

### 4.2 Tenet 与 3 个编译器

| 项 | 命令 | 输入 | 观察 / 通过 |
|---|---|---|---|
| compiler-rs | `cd languages/tenet/compiler-rs && cargo test` | `tests/`、`examples/*.tenet` | 当前 133 个测试通过（以 README 为准） |
| compiler-cpp | `cd languages/tenet/compiler-cpp && make test` | 同上 | 当前 993 个测试通过（以 README 为准） |
| compiler-arm64 | `cd languages/tenet/compiler-arm64 && make test` | 同上 | 当前 1279 个测试通过（以 README 为准） |
| 三后端一致性 | 三端分别编译并运行 `examples/*.tenet` | 同一组 `.tenet` | stdout/exit code 一致 |

## 5. T4 算法（42 个）

> 每个算法目录保留自己的 README / demo；本表按族跑现有 pytest，不重写 42 个算法。

| 族 | 算法数 | 命令 | 输入 | 观察 / 通过 |
|---|---:|---|---|---|
| p01 搜索 | 6 | `cd algorithms && uv run pytest p01-search -q` | `p01-search/` | 6/6 通过；demo 指标有数字 |
| p02 统计 ML | 14 | `cd algorithms && uv run pytest p02-statistical-ml -q` | `p02-statistical-ml/` | 14/14 通过；对照实验有结论 |
| p03 深度学习 | 11 | `cd algorithms && uv run pytest p03-deep-learning -q` | `p03-deep-learning/` | 11/11 通过；训练/评估可复现 |
| p04 Transformer | 8 | `cd algorithms && uv run pytest p04-transformer -q` | `p04-transformer/` | 8/8 通过；注意力/生成有对照 |
| p05 生成式 | 3 | `cd algorithms && uv run pytest p05-generative -q` | `p05-generative/` | 3/3 通过；VAE/DDPM/RAG 有指标 |

算法顺序：p01 → p02 → p03 → p04 → p05；与 T1/T2 的数据侧主线并行，不阻塞平台阶段。

## 6. 交叉项目（X1–X7）

| 项目 | 集成 | 验收 |
|---|---|---|
| X1 数据平台纵切 | T1-D0…D9 | 源→Kafka→Iceberg→Doris→API；一条链路可演示 |
| X2 10GB 语料→训练集 | T1-D2/D4 + T2-B | 清洗/去重/tokenize/pack/数据卡；同快照重建同哈希 |
| X3 训练数据通路 benchmark | T2-C + T2-D7 | samples/s、GPU 利用率、checkpoint 恢复、batch hash |
| X4 微调 + 推理 + 评测 | T2-D5/D7 + T2-B | LoRA 可复现；OpenAI 兼容；评测有数字 |
| X5 治理 / 血缘 / 成本 | T1-D7/D8 + T2-D9 | 指标→源表血缘；PII 掩码；成本可分摊 |
| X6 RAG + Agent | T2-D3/D8 | 引用可溯源；两个运行时通过 RuntimePort |
| X7 Tenet 三后端 + 语言收口 | T3 | 三端输出一致；126 阶段交付物齐 |

## 7. 证据契约

### 7.1 每个路线阶段的固定块

```markdown
#### <阶段编号> <阶段名>
- 命令：
- 输入：
- 观察：
- 通过：
- 产物：
```

示例：

```markdown
#### T1-D2 存储底座
- 命令：`make verify V2`
- 输入：`datasets/orders_1g.parquet`
- 观察：`snapshot_id=...`，`count=10,000,000`
- 通过：`V2-1`–`V2-3` 全绿
- 产物：`evidence/V2/`
```

### 7.2 两级证据

- **路线阶段（约 59 个）**：每个都要有完整四要素。
- **域内阶段（126 语言 + 42 算法）**：用批次命令 + 批次输入 + 通过数；具体阶段证据在各自 README，不重复造 168 个块。

### 7.3 门禁

上一阶段证据必须能被第二个人按命令重跑，才允许开下一阶段。以下不算证据：

- “看完了”“跑通了”但没有命令；
- 只有截图，没有输入；
- 只有最终数字，没有观察方式；
- 文档写完，代码没跑。

### 7.4 证据存放

- 工程阶段：`evidence/<stage-id>/README.md`，与代码同目录。
- 语言/算法：沿用各阶段 README 的输出；路线只放批次摘要。
- 路线总表：本页阶段表 + 交叉项目验收。

可选加 `roadmap/validate_evidence.py`：只校验阶段块四要素非空，不执行任意命令；后置，不阻塞路线。

## 8. 进度与维护

### 8.1 个人路线进度

| 轨道 | 阶段数 | 已完成 | 备注 |
|---|---:|---:|---|
| T1 数据平台 | 14 | 0 | 13 个 D 阶段 + T1-S |
| T2-A 平台主链 | 11 | 0 | 按 D0–D10 |
| T2-B 训练数据工程 | 10 | 0 | LD-1…LD-10 |
| T2-C 训练数据通路 | 9 | 0 | TDP-1…TDP-9 |
| T3 语言 + Tenet | 10 | 0 | 6 语言批 + 4 项 |
| T4 算法 | 5 | 0 | 5 族 |
| **合计** | **59** | **0** | 个人进度，不是仓库完成度 |

### 8.2 仓库资产状态

| 资产 | 状态 | 真相源 |
|---|---|---|
| 数据平台 | 0/13，设计阶段 | [`engineering/data-platform/README.md`](../engineering/data-platform/README.md) |
| AI 平台 | 0/11，D8 Part 1 资料完成 | [`engineering/ai-platform/README.md`](../engineering/ai-platform/README.md) |
| 语言 | 126/126 已建成 | [`languages/README.md`](../languages/README.md) |
| 算法 | 42/42 已完成 | [`algorithms/README.md`](../algorithms/README.md) |

### 8.3 维护规则

- D 阶段编号/验收变化时，先改 `engineering/` 真相源，再同步本页。
- 语言阶段增减时，只改 T3 批次行，不改本页结构。
- 算法增减时，只改 T4 族行。
- 每完成一个路线阶段，更新 8.1 的完成数，并在阶段块补证据链接。

## 9. 取舍与代价

### 9.1 不是“每门学一点”

原来的警告仍然成立：Java 学一点、Go 学一点、Python 学一点、Rust 学一点、Flink 学一点、大模型学一点，最后会很散。

“全都要”的正确姿势不是每门都浅，而是：

> **每门都要有交付物和证据，允许周期长，不允许停在“一点”。**

### 9.2 全都要的代价

| 内容 | 规模 |
|---|---|
| 两个平台 | 24 个 D 阶段 |
| 训练数据工程 + 通路 | 19 个专项模块 |
| 语言 | 6 门 × 126 阶段 |
| 算法 | 42 个 |
| Tenet | 3 个编译器 + 三端一致性 |

按 20 h/周：约 **60 个月**；30 h/周：约 **48 个月**；10 h/周：约 **90 个月**。

不删内容，只做三件事：**排顺序、定证据、设门禁**。

### 9.3 排序原则

1. 先共享底座：T1-D0/D2 + T2-D0/D1，避免两套重复。
2. 再做数据平台纵切：T1-D3…D9，先把湖仓/治理/服务跑通。
3. 再做 AI 平台：T2-A D2…D10，T2-B/T2-C 跟着 D2/D7 走。
4. 语言/算法/Tenet 全程并行，不占数据侧关键路径，但必须完成。
5. 最后做 X1–X7 交叉项目和生产化。

### 9.4 风险与对策

| 风险 | 对策 |
|---|---|
| 范围太大，每轨都浅 | 阶段证据门禁 + 交叉项目验收，不允许“看完就算” |
| 平台文档写了但没实现 | 以命令/输入/观察为准；文档不算完成 |
| 语言/算法轨被主线挤掉 | 固定周配额，按批次推进，不占主平台时间 |
| 训练数据工程做成“脚本堆” | LD/TDP 模块化 + 数据卡 + 可复现快照 |
| Tenet 变成无底洞 | 以三后端一致性 + 现有测试为边界，不无限加语言特性 |

## 10. 修订记录

| 版本 | 变更 |
|---|---|
| v2 | 按“平台支持”补：T2-B LD-9/10（标注/合成、多模态数据）、T2-C TDP-8/9（高级存储、大规模 checkpoint）、T1-S 计入路线；T2-A D2/D3/D7/D9/D10 扩验收；路线 54→59。 |
| v1 | 初版：四轨（T1 数据平台 / T2 AI 平台 / T3 语言+Tenet / T4 算法）；T2 含 T2-A 主链、T2-B 训练数据工程、T2-C 训练数据通路；全阶段证据契约；60 个月总日历。 |
