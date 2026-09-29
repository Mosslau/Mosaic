"""线性回归与梯度下降 — 手写实现（监督估计器）

自然接口由"估计器"这一类型决定：fit(X, y) 学参数，predict(X) 出预测。
本实验要理解的原理是**梯度下降本身**，所以训练循环必须手写。

    model = Model(lr=0.01, epochs=1000)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

变量对应 README「数学推导」段：w 是权重、b 是偏置、lr 是学习率、
grad_w / grad_b 是 MSE 损失对二者的偏导（手推结果写在 README）。
"""

import numpy as np


class Model:
    """线性回归：y_hat = X @ w + b，用批量梯度下降最小化 MSE。"""

    def __init__(self, lr: float = 0.01, epochs: int = 1000, tol: float = 1e-8) -> None:
        self.lr = lr
        self.epochs = epochs
        self.tol = tol
        self.w: np.ndarray | None = None
        self.b: float = 0.0
        self.loss_history: list[float] = []

    def fit(self, X: np.ndarray, y: np.ndarray) -> "Model":
        """手写批量梯度下降，逐轮记录 MSE 到 self.loss_history。"""
        # TODO: 手写
        #   1. 初始化 w = zeros(n_features)、b = 0
        #   2. 逐轮：y_hat = X @ w + b；err = y_hat - y
        #      grad_w = 2/n * X.T @ err；grad_b = 2/n * err.sum()
        #      w -= lr * grad_w；b -= lr * grad_b；记录 MSE
        #   3. 相邻两轮 loss 变化 < tol 时提前停止（收敛判据，README 要写清怎么选 tol）
        raise NotImplementedError("TODO: 手写批量梯度下降")

    def predict(self, X: np.ndarray) -> np.ndarray:
        # TODO: 返回 X @ w + b；未 fit 时抛 RuntimeError
        raise NotImplementedError("TODO: 手写前向预测")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/predict，再到 demo.py 跑实验")
