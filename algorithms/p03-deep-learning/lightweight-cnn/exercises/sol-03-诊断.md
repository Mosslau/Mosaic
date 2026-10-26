# 参考解 3：三种实现的症状

**A：`groups=1` 但权重按 depthwise 用**

不报错。`Conv2D(4,4,3,groups=1)` 的输出把 4 个输入通道一起加权求和，形状仍是
`(N,4,H,W)`，训练照常，但**静默算错**——它已经是标准卷积，不是 depthwise。
用 `test_depthwise_equals_grouped_conv` 的逐通道参考实现对账即可发现；
`sol-03-诊断.py` 实测最大差 **5.15**。

**B：先 pointwise 再 depthwise**

不报错（形状兼容），但两个算子不可交换：1×1 先把通道混合，depthwise 再逐通道
卷积，与"先空间后通道"不等价。实测平均相对差 **1.13**（同量级于输出本身）。
诊断：用同一组权重按正确顺序跑参考，比较输出；或固定输入看是否有通道串扰。

**C：BN 推理仍用 `training=True`**

不报错，单张图也能出结果，但预测**依赖同批次的其它样本**（batch 统计随批次变）。
`sol-03-诊断.py` 实测：training 模式"单图 vs 批量"差 **0.92**；eval 模式差 **0.0**。
对应测试 `test_bn_eval_is_batch_independent`。修复：`predict` 一律 `training=False`。

**共同点**：三种错误都不会在形状/类型层报错，必须靠**数值对账**与**行为测试**
（分组等价、batch 无关性）才能发现——这正是 `test_impl.py` 存在的意义。
