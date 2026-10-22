# 迁移项目：内容检索 —— attention vs mean pooling

## 需求

把 attention 当成“内容寻址的软检索”：

1. 记忆库有 `T=64` 个 key/value；
2. query 等于其中一个 key；
3. attention 应返回对应 value；mean pooling 应失败。

## 功能清单

- [x] 随机 key/value 记忆库
- [x] 单个 query 的 attention 权重
- [x] attention vs mean pooling 的 top-1
- [x] 验收断言

## 验收标准

1. attention top-1 **> 0.95**；
2. mean pooling top-1 **< 0.1**。

## 运行方式

```bash
cd algorithms/p04-transformer/attention/project
uv run python retrieval.py
```

## 实测结果（已验证）

T=64、D=32、50 个 query：attention **1.000**；mean pooling **0.020**。

## 结论

attention 的权重是**按 query 内容现算**的；mean pooling 把 value 平均后，所有 query 得到同一个结果，
没有“选择”能力。这是 attention 与固定池化最本质的差别之一。
