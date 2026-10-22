# 迁移项目：手写数字 10 分类 —— MLP vs torch vs 逻辑回归

## 需求

把 MLP 用到真实图像数据上。与教学示例（合成二维）的差别是三个**新约束**：

1. **真实 8×8 像素**：sklearn `digits` 1797 张、10 类；
2. **多分类**：softmax + 交叉熵，不是二分类；
3. **三路对照**：手写 numpy、PyTorch、线性逻辑回归基线。

## 功能清单

- [x] 手写 MLP（64→32→10，Adam，40 轮）
- [x] PyTorch 同结构对照
- [x] 逻辑回归线性基线
- [x] 测试 acc / macro F1 / 耗时
- [x] 5 条验收断言

## 验收标准

1. 手写 MLP 测试 acc **≥ 0.95**；
2. torch MLP 测试 acc **≥ 0.95**；
3. 手写 vs torch 差 **≤ 0.03**；
4. 手写 macro F1 **≥ 0.95**；
5. MLP 比逻辑回归高 **≥ 0.005**。

脚本 `digits.py` 内逐条断言。

## 运行方式

```bash
cd algorithms/p03-deep-learning/mlp-backprop/project
uv run python digits.py
```

依赖：numpy + scikit-learn + torch；运行约 2 秒（CPU）。

## 实测结果（已验证）

环境：uv（Python 3.13.15 / numpy 2.5.4 / scikit-learn 1.9.1 / torch 2.14.1），`seed = 0`。
样本 1797（训练 1200 / 测试 597），特征 64 维，10 类。

| 方法 | 测试 acc | macro F1 | 耗时（s） |
|---|---|---|---|
| 手写 MLP | 0.9765 | 0.9766 | ≈0.15 |
| torch MLP | **0.9849** | **0.9849** | ≈1.6 |
| 逻辑回归 | 0.9698 | 0.9700 | 0.00 |

手写 MLP 40 轮，末轮 loss 0.0002。

**四条结论**：

1. **非线性 MLP 略强于线性基线**：0.9765 vs 0.9698（+0.0067），不是碾压。
2. **手写与 torch 同量级**：差 0.0084；torch 的初始化/算子顺序/float32 不同。
3. **torch 更慢**：逐 batch 框架调用，1.56s vs 手写 0.14s；不是算法更复杂。
4. **digits 太“干净”**：线性基线已 0.97，MLP 的优势要在更难的数据/任务上才明显。

## 扩展方向

- 换 **Fashion-MNIST/CIFAR-10**，看 MLP 与 CNN 的差距；
- 加 **数据增强 / dropout / 早停**，观察泛化；
- 做 **混淆矩阵/每类 F1**，找最容易混的数字对；
- 用 **温度缩放** 校准 softmax 概率。
