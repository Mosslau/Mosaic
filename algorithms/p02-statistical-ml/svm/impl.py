"""支持向量机 SVM — 手写实现（监督估计器）

接口仍是估计器形态（fit / predict），但**优化目标不同**：SVM 最大化间隔，
损失是 hinge loss + L2 正则。所以本实验的 impl 要手写的是**合页损失下的
（子）梯度下降**，这是与逻辑回归最本质的对比点。

    model = Model(C=1.0, lr=0.01, epochs=1000)
    model.fit(X_train, y_train)          # y ∈ {-1, +1}
    label = model.predict(X_test)

标签约定：内部用 y ∈ {-1, +1}（hinge 的定义域），demo.py 负责从 {0,1} 映射过来。
"""

import numpy as np


class Model:
    """线性 SVM（hinge loss + L2 正则），用（子）梯度下降求解。"""

    def __init__(self, C: float = 1.0, lr: float = 0.01, epochs: int = 1000) -> None:
        self.C = C
        self.lr = lr
        self.epochs = epochs
        self.w: np.ndarray | None = None
        self.b: float = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "Model":
        """手写下述目标函数的（子）梯度下降，并记录每次迭代的合页损失。"""
        # 目标：min 1/2 * ||w||^2 + C * Σ max(0, 1 - y_i * (X_i @ w + b))
        # TODO: 手写
        #   1. 校验 y 取值只能是 -1/+1，否则抛 ValueError
        #   2. 每次迭代：margin = y * (X @ w + b)
        #      只有 margin < 1 的样本贡献梯度（这就是"支持向量"的由来——README 要点明）
        #      w 同时受正则项梯度 w 影响；C 控制两者的权衡
        raise NotImplementedError("TODO: 手写 hinge loss 子梯度下降")

    def predict(self, X: np.ndarray) -> np.ndarray:
        # TODO: sign(X @ w + b) -> {-1, +1}
        raise NotImplementedError("TODO: 手写符号判决")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/predict，再到 demo.py 跑实验")
