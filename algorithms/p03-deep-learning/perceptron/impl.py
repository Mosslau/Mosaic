"""感知机 — 手写实现（深度模型 · 判别式）

深度学习的第一块砖。形态上**与同族监督估计器相似（fit / predict）**，但实现路径
完全不同：感知机是**在线错误驱动更新**，没有损失函数、没有梯度下降——
这是它和逻辑回归最本质的区别（README「设计原理」段要点明）。

    p = Perceptron(lr=0.1, epochs=10, random_state=42)
    p.fit(X_train, y_train)        # y ∈ {-1, +1}
    label = p.predict(X_test)

**必须手写并说明的一点**：感知机收敛定理只在**线性可分**时成立。
demo.py 要故意跑一组线性不可分数据，观察它不收敛（epoch 间准确率来回摆）。
"""

import numpy as np


class Perceptron:
    """感知机：y_hat = sign(X @ w + b)，错分即更新（不涉及损失函数）。"""

    def __init__(self, lr: float = 0.1, epochs: int = 10, random_state: int | None = None) -> None:
        self.lr = lr
        self.epochs = epochs
        self.random_state = random_state
        self.w: np.ndarray | None = None
        self.b: float = 0.0
        self.errors_per_epoch: list[int] = []

    def fit(self, X: np.ndarray, y: np.ndarray) -> "Perceptron":
        """手写在线更新：遍历样本，错分则 w += lr * y_i * x_i、b += lr * y_i。"""
        # TODO: 手写
        #   1. 校验 y ∈ {-1, +1}
        #   2. 每个 epoch 打乱样本顺序（顺序会影响结果，README 说明为什么）
        #   3. 逐样本：若 y_i * (x_i @ w + b) <= 0 则更新 w、b
        #   4. 记录 self.errors_per_epoch —— demo 用它画收敛曲线 / 展示不可分时的不收敛
        raise NotImplementedError("TODO: 手写感知机在线更新")

    def predict(self, X: np.ndarray) -> np.ndarray:
        # TODO: sign(X @ w + b)，注意 sign(0) 取 +1（约定要写进 README）
        raise NotImplementedError("TODO: 手写符号判决")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/predict，再到 demo.py 跑实验")
