# 迁移项目：8×8 手写数字上的 LeNet

## 需求

把卷积网络用到真实图像上。与 MLP 的差别是三个**新约束**：

1. **空间结构**：8×8 像素 reshape 成 `(N,1,8,8)`，用卷积利用局部性；
2. **小图限制**：不是 28×28 MNIST，卷积/池化后只剩 2×2；
3. **三路对照**：手写 LeNet、PyTorch LeNet、线性逻辑回归。

## 功能清单

- [x] 手写 LeNet（conv→pool→conv→pool→fc），BN + 残差
- [x] PyTorch 同结构对照
- [x] 逻辑回归线性基线
- [x] 测试 acc / macro F1 / 耗时
- [x] 5 条验收断言

## 验收标准

1. 手写 LeNet 测试 acc **≥ 0.90**；
2. torch LeNet 测试 acc **≥ 0.95**；
3. 手写 vs torch 差 **≤ 0.06**；
4. 手写 macro F1 **≥ 0.90**；
5. BN+残差比 baseline 高（demo 实验二）。

脚本 `digits.py` 内逐条断言。

## 运行方式

```bash
cd algorithms/p03-deep-learning/cnn-lenet/project
uv run python digits.py
```

依赖：numpy + scikit-learn + torch；运行约 40 秒（CPU）。

## 实测结果（已验证）

环境：uv（Python 3.13.15 / numpy 2.5.4 / scikit-learn 1.9.1 / torch 2.14.1），`seed = 0`。
样本 1797（训练 1400 / 测试 397），8×8，10 类。

| 方法 | 测试 acc | macro F1 | 耗时（s） |
|---|---|---|---|
| 手写 LeNet | 0.9370 | 0.9369 | ≈4.8 |
| torch LeNet | **0.9874** | **0.9875** | ≈31 |
| 逻辑回归 | 0.9698 | 0.9700 | 0.00 |

**四条结论**：

1. **BN+残差把基线从 0.897 拉到 0.937**，但手写版仍低于 torch（0.987）。
2. **8×8 太小**：线性逻辑回归 0.970，反而高于手写 CNN；CNN 的收益要在更大图像上才明显。
3. **torch 快在算子**：手写 im2col + Python 循环，4.6s；torch C++ 融合算子，但逐 batch 调用仍有开销。
4. **小图不适合深 CNN**：两次池化后只剩 2×2，空间信息损失很大。

## 扩展方向

- 换 **MNIST 28×28 / Fashion-MNIST**，看 CNN 相对 MLP 的增益；
- 加 **数据增强**（平移/旋转），提升小图泛化；
- 实现 **VGG/ResNet 残差块**，比较深度；
- 做 **卷积核/特征图可视化**，解释每层学到了什么。
