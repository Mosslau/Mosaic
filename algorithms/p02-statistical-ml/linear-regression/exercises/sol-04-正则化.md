# 参考解：第 4 题（实现）——给梯度下降加 L2

目标函数（**只惩罚 w，不惩罚 b**）：

$$J(w,b) = \frac{1}{n}\lVert Xw + b - y\rVert^2 + \lambda\lVert w\rVert^2$$

梯度多一项 `2λw`：

$$\nabla_w J = \frac{2}{n}X^\top(\hat y - y) + 2\lambda w,\qquad
\frac{\partial J}{\partial b} = \frac{2}{n}\sum(\hat y - y)$$

**岭回归闭式解**（先中心化，避免惩罚截距）：

$$w^\* = (X_c^\top X_c + n\lambda I)^{-1}X_c^\top y_c,\qquad b^\* = \bar y - \bar x^\top w^\*$$

注意惩罚项要乘 `n`：损失用的是 **mean**，而正规方程来自 **sum**。

**结果解读**（见 `sol-04-正则化.py` 的输出）：

- `λ = 0`：与普通最小二乘一致；
- `λ` 增大：`‖w‖` 单调下降（收缩），训练 MSE 单调上升；
- 测试 MSE 先降后升——存在一个"偏差-方差"的甜点，这正是正则化的意义。

代码里 `RidgeGD` 的 `grad_w = 2/n·Xᵀerr + 2·lam·w` 就对应上面第一行。
