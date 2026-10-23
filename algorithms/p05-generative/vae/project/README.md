# 迁移项目：VAE 采样 + latent 插值

## 需求

把 VAE 用到“生成 + 插值”：

1. 训练 2D latent VAE（beta=0.1）；
2. 从先验采样 8 张；
3. 取两张测试图的 μ，插值 8 帧；
4. 报告重构 MSE、采样范围、插值连续性。

## 功能清单

- [x] 2D VAE 训练
- [x] 先验采样
- [x] latent 线性插值
- [x] 验收断言

## 验收标准

1. test MSE **< 0.05**；
2. 采样有限且形状正确；
3. 插值帧数正确。

## 运行方式

```bash
cd algorithms/p05-generative/vae/project
uv run python generate.py
```

## 实测结果（已验证）

- test MSE **0.0424**；
- sample `(8,64)`，范围约 `[0.000, 0.972]`；
- interpolate `(8,64)`，相邻 L2 平均约 **0.091**。

## 结论

VAE 的 latent 是连续分布，插值能平滑过渡；但 2D latent 容量小，生成是模糊数字块。
