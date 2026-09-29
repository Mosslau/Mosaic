"""逻辑回归 — 手写实现（监督估计器）

自然接口与线性回归同族（fit / predict），差别在输出层：sigmoid 把线性组合
压到 (0,1) 当作概率。本实验要理解的是**交叉熵损失 + 它的梯度为何仍是
(pred - y) 这个干净形式**——这个"巧合"必须自己推一遍。

    model = Model(lr=0.1, epochs=500)
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_test)   # 连续概率
    label = model.predict(X_test)         # 阈值化后的 0/1
"""

import numpy as np


def sigmoid(z: np.ndarray) -> np.ndarray:
    """数值稳定版 sigmoid：对 z 正负分别处理，避免 exp 溢出。"""
    # TODO: 手写——z >= 0 时用 1/(1+exp(-z))，否则用 exp(z)/(1+exp(z))
    raise NotImplementedError("TODO: 手写数值稳定 sigmoid")


class Model:
    """逻辑回归：p = sigmoid(X @ w + b)，用交叉熵损失做梯度下降。"""

    def __init__(self, lr: float = 0.1, epochs: int = 500, threshold: float = 0.5) -> None:
        self.lr = lr
        self.epochs = epochs
        self.threshold = threshold
        self.w: np.ndarray | None = None
        self.b: float = 0.0
        self.loss_history: list[float] = []

    def fit(self, X: np.ndarray, y: np.ndarray) -> "Model":
        """手写梯度下降：交叉熵对 w 的梯度化简后与线性回归同形，README 要写出推导。"""
        # TODO: 手写
        #   p = sigmoid(X @ w + b)
        #   grad_w = 1/n * X.T @ (p - y)；grad_b = 1/n * (p - y).sum()
        #   注意：梯度形式虽与线性回归相同，但 p 含 sigmoid，不是同一个模型——别混
        raise NotImplementedError("TODO: 手写交叉熵梯度下降")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        # TODO: sigmoid(X @ w + b)
        raise NotImplementedError("TODO: 手写概率输出")

    def predict(self, X: np.ndarray) -> np.ndarray:
        # TODO: predict_proba >= threshold 转成 0/1
        raise NotImplementedError("TODO: 手写阈值化预测")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/predict，再到 demo.py 跑实验")
