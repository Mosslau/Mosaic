# 迁移项目：同源语料 RAG QA + 引用

## 需求

把 RAG 链路用到同源语料：

1. 建索引（切块 + TF-IDF 哈希 + 归一化）；
2. 对 12 个问题检索 top-3；
3. 返回抽取式答案 + citations；
4. 评估 Recall@3 与 citation。

## 功能清单

- [x] 索引/检索/生成/引用
- [x] 12 query 端到端
- [x] Recall/citation 指标
- [x] 验收断言

## 验收标准

1. Recall@3 **≥ 0.9**；
2. citation **≥ 0.9**。

## 运行方式

```bash
cd algorithms/p05-generative/mini-rag/project
uv run python qa.py
```

## 实测结果（已验证）

- Recall@3 **1.000**；
- citation **1.000**；
- 抽取式 answer match 0.917（来自 demo，不是 qa.py 的指标）。

## 结论

RAG 的检索/引用链路可跑通；但 12 个合成文档、TF-IDF 哈希、抽取式答案都不是生产级。
