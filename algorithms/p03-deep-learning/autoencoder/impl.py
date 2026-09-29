"""自编码器 AutoEncoder — 手写实现（深度模型 · 无监督）

**无监督，所以没有 y**——目标就是重构输入自己。这带来一个与前面所有实验都不同的
接口形态：fit(X) + reconstruct(X)，核心指标是**重构误差**而不是准确率。

    ae = AutoEncoder(latent_dim=32, lr=0.01, epochs=50)
    ae.fit(X_train)                      # 无 y：目标是 X 自己
    Z = ae.encode(X_test)                # 压缩表示（这是最有用的产物）
    X_hat = ae.reconstruct(X_test)       # 重构
    err = ae.reconstruction_error(X_test)

按族总表，本目录同时给出 `encode/decode`（自编码器的自然接口）。
demo 的核心叙事：**降维到 2 维后可视化**，与同族的 PCA 对比线性/非线性子空间的差别
（在「局限与延伸」里链到 ../pca/）。
"""

import numpy as np


class AutoEncoder:
    """对称的编码器-解码器，瓶颈层即压缩表示。"""

    def __init__(self, latent_dim: int = 32, lr: float = 0.01, epochs: int = 50,
                 batch_size: int = 64, random_state: int | None = None) -> None:
        self.latent_dim = latent_dim
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.random_state = random_state
        self.params: dict = {}
        self.loss_history: list[float] = []

    def encode(self, X: np.ndarray) -> np.ndarray:
        # TODO: 手写——输入 → ... → 瓶颈层，输出压缩表示 Z
        raise NotImplementedError("TODO: 手写编码器前向")

    def decode(self, Z: np.ndarray) -> np.ndarray:
        # TODO: 手写——瓶颈 → ... → 输出层，重建 X_hat
        raise NotImplementedError("TODO: 手写解码器前向")

    def reconstruct(self, X: np.ndarray) -> np.ndarray:
        # TODO: decode(encode(X))
        raise NotImplementedError("TODO: 手写重构")

    def fit(self, X: np.ndarray) -> "AutoEncoder":
        """无监督训练：最小化 ||X - X_hat||^2，反向传播时**目标是输入自己**。"""
        # TODO: 手写
        #   反向传播的起点是 dL/dX_hat = 2(X_hat - X)/n —— 注意 y 就是 X
        raise NotImplementedError("TODO: 手写无监督训练循环")

    def reconstruction_error(self, X: np.ndarray) -> float:
        # TODO: 手写——返回平均 MSE，demo 用它对比不同 latent_dim
        raise NotImplementedError("TODO: 手写重构误差")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/encode/decode，再到 demo.py 跑实验")
