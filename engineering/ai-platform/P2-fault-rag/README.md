# P2 故障诊断纵切（AI 平台 · 对应 D3/D9 的一部分）

> 状态：🚧 进行中
> 所属平台与单元：ai-platform · P2 故障诊断纵切（类别：期，对应 D3 检索与 D9 反馈的一部分）
> 对应文档：[AI 平台建设路线](../../ai-platform/AI平台建设路线.md)（D3/D9）· [数据侧纵切 P2](../../data-platform/P2-device-slice/README.md)（故障来源）

## 1. 目标

把数据平台产出的故障事件，走完 AI 侧的「检索 → 带引用答案 → 动作 → 反馈」：

1. 从 `fault_events` 读故障（`P0A1` / `P0A2`）；
2. 检索手册语料，产出 **带引用的 `Answer`**（用 AI P1 的契约校验）；
3. 有依据 → 建工单（`suggested`）；无依据 → 转人工（`manual_review`）；
4. 写入反馈事件（`verdict` + `reason_code`），形成可归因的闭环。

**一句话验收**：`./rag.sh` 输出 `answers=8 workorders=8 feedback=8 new_answers=2 no_evidence=0`，且 `./query.sh` 能查到引用、工单状态与反馈分布。

## 2. 范围与不做

**做**：

- 字符 bigram + TF-IDF 余弦检索（零依赖，可替换为 Milvus/faiss）；
- `Answer` 契约的生产与校验（`text` / `citations[]` / `confidence` / `no_evidence`）；
- 无依据判定与转人工动作；
- 工单表与反馈表；`prediction_id` 确定性生成，支持按预测归因；
- 结果写 PG，`ai_pipeline_ledger` 记录每段。

**不做**：

- 真实模型调用 / embedding（D5/D2 的正式能力）；
- 100 题评测集与门禁（D3 的 `A3-2`/`A3-4`）；
- 工单系统对接（业务系统在平台外，本单元只写 `suggested` 状态）；
- 自动训练 / 飞轮（D10 的 `A10-8`）；
- 鉴权、租户、审批流（D8/D10）。

## 3. 技术栈

| 层 | 选择 | 说明 |
|---|---|---|
| 检索 | Python 3.9 标准库（TF-IDF + bigram） | 不引向量库，先证明链路 |
| 契约 | `mosaic_ai_contracts`（AI P1） | `Answer` 直接复用，跨单元契约测试 |
| 存储 | PostgreSQL 16（共享底座） | 答案/工单/反馈/账本 |
| 访问 | `mosaic_kernel.docker_cli` | 与数据侧纵切共用 PG 访问，不重复拼 docker 命令 |
| 测试 | `unittest` | 9 项，不依赖 Docker |

## 4. 系统架构

```text
fault_events（PG，数据侧写入）
        │  limit N
        ▼
Retriever（手册语料 6 篇，TF-IDF）
        │  top-2 + score
        ▼
build_answer() ──► Answer 契约校验（AI P1）
        │
        ├── 有依据 → workorder:suggested
        └── 无依据 → manual_review
        │
        ▼
feedback_events（verdict / reason_code / prediction_id）
        │
        └──► ai_pipeline_ledger（trace_id 可查）
```

表结构：

| 表 | 主键 | 说明 |
|---|---|---|
| `diagnosis_answers` | `event_id` | 每个故障一条答案；`prediction_id` 供归因 |
| `workorders` | `workorder_id` | `WO-<prediction_id>`，状态 `suggested` / `manual_review` |
| `feedback_events` | `feedback_id` | `verdict` + `reason_code`（数据错/检索错/推理错/动作错/业务变更） |
| `ai_pipeline_ledger` | 自增 | 每次纵切的 read/answer/feedback 三段 |

## 5. 复用的算法实验

- 最小 RAG 闭环：[`algorithms/p05-generative/mini-rag/`](../../../algorithms/p05-generative/mini-rag/)——本纵切的检索 + 引用结构直接对齐它的闭环；
- 注意力机制：[`algorithms/p04-transformer/attention/`](../../../algorithms/p04-transformer/attention/)——D5 接真实模型时的原理参照；
- MCTS 与规划：[`algorithms/p01-search/mcts/`](../../../algorithms/p01-search/mcts/)——后续 Agent 任务分解的参照。

## 6. 验收标准

| 编号 | 通过标准 | 当前状态 | 证据 |
|---|---|---|---|
| `A3-1` | `/ask` 返回答案 + 引用 | ✅（纵切级） | 4 条答案均带 `manual://...` 引用与 `sha256:` 前缀哈希 |
| `A3-3` | 负例不编造 | ✅（纵切级） | 未知故障码 → `no_evidence=true`、`citations=[]`、转人工 |
| `A9-6` | 反馈日志可查 | ✅（纵切级） | `feedback_events` 4/8 条，含 `verdict` 与 `reason_code` |
| `A3-2` | 100 题评测有数字 | ⬜ | 评测集未建 |
| `A10-10` | 一条完整飞轮 | 🟡 | 反馈已写回，但训练/评测回灌未做 |

**复现命令**：

```bash
cd engineering/ai-platform/P2-fault-rag
./test.sh     # 9 项单元测试

# 先跑数据侧纵切，产生 fault_events
cd ../../data-platform/P2-device-slice && ./slice.sh
cd ../../ai-platform/P2-fault-rag && ./rag.sh --limit 20
./query.sh
```

实测输出（2026-11-11，跨平台一条命令 `engineering/vertical-slice.sh`）：

```text
[summary] {"faults": 8, "answers": 8, "workorders": 8, "feedback": 8,
           "new_answers": 2, "no_evidence": 0, "avg_confidence": 0.2368,
           "model": "local-tfidf-rag/v0", "verdict": "correct"}
[sample] veh-0001-...-P0A1 conf=0.225 no_evidence=False citation=manual://battery/p0a1 status=suggested
```

## 7. 实施笔记

- **2026-11-11 新建**：语料 6 篇、检索器、Answer 生产者、动作与反馈、9 项测试；首次跑通「故障 → 诊断 → 工单 → 反馈」。
- **契约复用**：`Answer` 直接调用 AI P1 的 `CONTRACTS.validate`，不复制字段定义；这就是 D1 契约内核的第一个真实消费者。
- **幂等与计数**：答案/工单/反馈都按确定性主键 `on conflict do nothing`；重复处理旧故障时 `new_*` 为 0，只有新故障才增长。为此给工单/反馈补了 `trace_id` 列，按 run 可查。
- **取舍**：TF-IDF 分数不是校准概率（0.22 不代表 22% 正确率），只用于排序与「有无依据」阈值；接真实 embedding 后再谈校准。
- **待办**：
  1. 检索换 Milvus/faiss + 真实文档加工（D2/D3）；
  2. 建 100 题评测集与回归门禁（`A3-2`/`A3-4`）；
  3. 接 `agent-service` 作为运行时，把「答案 → 工具调用 → 工单」交给 RuntimePort（D8）；
  4. 反馈驱动评测集/训练集回流（`A10-10`）。
