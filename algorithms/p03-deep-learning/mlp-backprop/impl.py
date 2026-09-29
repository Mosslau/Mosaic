"""MLP 与手写反向传播 — 手写实现（深度模型 · 判别式）

本仓库**最重要的一篇手写实验**：后面 CNN / RNN / Transformer 的反向传播都是
这里那套链式法则的复用。接口仍是 fit / predict，但内部必须把**每一层的
前向缓存与反向梯度**都自己算出来。

    mlp = MLP(hidden_sizes=(64, 32), lr=0.01, epochs=100)
    mlp.fit(X_train, y_train)
    proba = mlp.predict_proba(X_test)
    label = mlp.predict(X_test)

手写纪律（按族细化）：允许 `torch.Tensor` / `torch.autograd`（张量与求导是工具），
**禁止 PyTorch 的现成层与现成优化器**（如 Linear 层、Adam 优化器）——层与优化器
正是本实验要理解的原理。本实现用 numpy 即可，不依赖 torch。
"""

import numpy as np


def relu(z: np.ndarray) -> np.ndarray:
    # TODO: 手写 max(0, z)
    raise NotImplementedError("TODO: 手写 ReLU")


def relu_grad(z: np.ndarray) -> np.ndarray:
    """ReLU 的导数：z > 0 处为 1，否则 0（**注意 z=0 的次梯度取 0**，README 说明）。"""
    # TODO: 手写
    raise NotImplementedError("TODO: 手写 ReLU 导数")


def softmax(z: np.ndarray) -> np.ndarray:
    """数值稳定版：先减去每行最大值再取 exp，最后归一化。"""
    # TODO: 手写
    raise NotImplementedError("TODO: 手写数值稳定 softmax")


class MLP:
    """多层感知机：任意隐层数量，交叉熵损失 + 手写反向传播。"""

    def __init__(
        self,
        hidden_sizes: tuple[int, ...] = (64, 32),
        lr: float = 0.01,
        epochs: int = 100,
        batch_size: int = 32,
        random_state: int | None = None,
    ) -> None:
        self.hidden_sizes = hidden_sizes
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.random_state = random_state
        self.params: list[dict] = []          # 每层的 {"W": ..., "b": ...}
        self.loss_history: list[float] = []

    def _init_params(self, n_features: int, n_classes: int) -> None:
        """He 初始化（ReLU 配套）：W ~ N(0, sqrt(2/fan_in))；全 0 初始化会导致对称性无法打破。"""
        # TODO: 手写——README「手写实现要点」要写清为什么不能全零初始化
        raise NotImplementedError("TODO: 手写 He 初始化")

    def forward(self, X: np.ndarray) -> tuple[np.ndarray, list[dict]]:
        """前向传播，**同时缓存每层的中间量**（反向要用）。返回 (输出概率, 缓存)。"""
        # TODO: 手写——隐层 ReLU、输出层 softmax
        raise NotImplementedError("TODO: 手写前向传播（含缓存）")

    def backward(self, cache: list[dict], y_onehot: np.ndarray) -> list[dict]:
        """链式法则逐层回传，返回每层梯度（与 self.params 同结构）。"""
        # TODO: 手写
        #   输出层：softmax + 交叉熵的组合梯度化简为 (proba - y_onehot)/n
        #   隐层：dZ = dA * relu_grad(Z)；dW = A_prev.T @ dZ；db = dZ.sum(axis=0)
        #   **必须逐层乘上该层激活的导数**——漏乘是本章最常见的错误
        raise NotImplementedError("TODO: 手写反向传播")

    def fit(self, X: np.ndarray, y: np.ndarray) -> "MLP":
        # TODO: 手写——one-hot 编码 y、小批量打乱、逐 batch {forward, backward, 更新}、记录 loss
        raise NotImplementedError("TODO: 手写训练循环")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        # TODO: forward 取概率
        raise NotImplementedError("TODO: 手写概率输出")

    def predict(self, X: np.ndarray) -> np.ndarray:
        # TODO: 取 argmax
        raise NotImplementedError("TODO: 手写类别预测")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/predict，再到 demo.py 跑实验")
