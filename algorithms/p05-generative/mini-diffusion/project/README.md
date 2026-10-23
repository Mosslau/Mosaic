# 迁移项目：class-conditional DDPM + CFG

## 需求

把 DDPM 从无条件推进到条件生成：

1. 训练 100 步条件 DDPM；
2. 每类采 20 个样本；
3. 用真实数据训练的分类器评估类别一致性；
4. 报告 CFG w=3 的 acc。

## 功能清单

- [x] 条件 DDPM（类别嵌入 + 条件 dropout）
- [x] CFG 采样
- [x] 分类器代理评估
- [x] 验收断言

## 验收标准

1. CFG w=3 的 class acc **> 0.9**；
2. 样本在 `[0,1]` 且形状正确。

## 运行方式

```bash
cd algorithms/p05-generative/mini-diffusion/project
uv run python conditional.py
```

## 实测结果（已验证）

- train loss **0.295**；
- CFG w=3 class acc **0.995**（200 个样本）。

## 结论

类别条件 + CFG 能显著提高类别一致性；但 `acc` 只是代理，视觉质量仍受 MLP/8×8/100 步限制。
