# 参考解：第 4 题（实现）——整网梯度检查

对每个参数做中心差分：

$$\frac{\partial L}{\partial \theta}\approx\frac{L(\theta+\epsilon)-L(\theta-\epsilon)}{2\epsilon}$$

与 `backward` 的解析梯度比较，取最大相对误差。
**预期**：误差 <1e-5（float64、无 dropout、无 weight decay）。
