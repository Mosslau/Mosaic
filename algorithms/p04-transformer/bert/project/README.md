# 迁移项目：MLM + [CLS] 情感分类

## 需求

把 BERT 的 `[CLS]` 表示用到下游分类：

1. 在 48 句合成情感句上做 MLM；
2. 取 `[CLS]` 向量；
3. 训练逻辑回归探针，区分正面/负面；
4. 报告 MLM 指标与探针 acc。

## 功能清单

- [x] 字符级 tokenizer + MLM
- [x] `[CLS]` 表示提取
- [x] 逻辑回归探针
- [x] 验收断言

## 验收标准

1. `[CLS]` 探针 acc **> 0.85**；
2. MLM masked acc > 0.8。

## 运行方式

```bash
cd algorithms/p04-transformer/bert/project
uv run python classify.py
```

## 实测结果（已验证）

- MLM loss **0.130**，masked acc **0.958**；
- `[CLS]` 探针 acc **0.933**。

## 结论

MLM 学到的 `[CLS]` 表示在这个小语料上能区分情感；但 **MLM loss 低 ≠ 表示一定好**，
换任务/换语料要重新做探针或微调。
