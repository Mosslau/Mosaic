"""卷积神经网络 LeNet — 手写实现（深度模型 · 判别式）

接口延续 MLP 的 fit / predict，但多了两个**必须在 numpy 里手写的算子**：
`im2col` 形式的卷积与它的转置（反传），以及池化的前向/反向路由。

    net = LeNet(n_classes=10, lr=0.01, epochs=5)
    net.fit(X_train, y_train)          # X: (N, 1, 28, 28)
    label = net.predict(X_test)

手写纪律：本实现用 numpy；若改用 torch，仅允许 `torch.Tensor` / `torch.autograd`，
**禁止 PyTorch 的现成卷积层与池化层**——卷积与池化正是本章的原理本身。
"""

import numpy as np


def im2col(X: np.ndarray, kh: int, kw: int, stride: int, pad: int) -> np.ndarray:
    """把 (N, C, H, W) 的滑窗摊平成 (N*out_h*out_w, C*kh*kw)，好让卷积退化成矩阵乘。"""
    # TODO: 手写——先按 pad 补零，再按 stride 取窗；这一步的空间换时间是本章性能要点
    raise NotImplementedError("TODO: 手写 im2col")


def col2im(dcol: np.ndarray, shape: tuple, kh: int, kw: int, stride: int, pad: int) -> np.ndarray:
    """im2col 的逆：把摊平的梯度按窗口位置**累加**回原图（重叠区域必须相加）。"""
    # TODO: 手写——重叠窗口的梯度累加是卷积反向传播最容易写错的地方
    raise NotImplementedError("TODO: 手写 col2im 梯度回填")


class LeNet:
    """LeNet-5 结构：conv → pool → conv → pool → fc → fc，全部手写。"""

    def __init__(self, n_classes: int = 10, lr: float = 0.01, epochs: int = 5,
                 batch_size: int = 64, random_state: int | None = None) -> None:
        self.n_classes = n_classes
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.random_state = random_state
        self.params: dict = {}
        self.loss_history: list[float] = []

    def forward(self, X: np.ndarray, cache: dict | None = None) -> np.ndarray:
        """逐层前向；传入 cache 时记录每层中间量供反向使用。"""
        # TODO: 手写——conv(im2col) → ReLU → maxpool(记录 argmax 供反传) → ... → softmax
        #   池化的 argmax 必须缓存：反向时梯度只回传给"当年最大的那个位置"
        raise NotImplementedError("TODO: 手写 LeNet 前向")

    def backward(self, grad_out: np.ndarray, cache: dict) -> dict:
        # TODO: 手写——fc 反传 → 池化反传（按 argmax 路由）→ conv 反传（col2im 累加）
        raise NotImplementedError("TODO: 手写 LeNet 反向")

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LeNet":
        # TODO: 手写小批量训练循环
        raise NotImplementedError("TODO: 手写训练循环")

    def predict(self, X: np.ndarray) -> np.ndarray:
        # TODO: 前向取 argmax
        raise NotImplementedError("TODO: 手写类别预测")


if __name__ == "__main__":
    raise SystemExit("请先完成 fit/predict，再到 demo.py 跑实验")
