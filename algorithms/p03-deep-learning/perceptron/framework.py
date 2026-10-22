"""感知机 — 框架对照（深度模型 · 判别式）

两路对照：

- **sklearn `linear_model.Perceptron`**：同算法的经典实现，作稳定基线；
- **PyTorch**：用 `nn.Linear` + `optim.SGD` 逐样本更新，模拟感知机的在线规则。

口径：同一数据、同一标准化、同一 `lr` / `epochs` / 随机种子、零初始化，
比较准确率、每轮错误数与迭代行为。感知机是 p03 里唯一保留 sklearn 主对照的实验，
torch 版用于验证“同一更新规则在框架里怎么写”，不替代 sklearn 基线。
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression, Perceptron
from sklearn.preprocessing import StandardScaler


def fit_perceptron(X, y, lr: float = 0.1, epochs: int = 10, random_state: int = 0):
    """sklearn 基线：同算法、C 级实现。"""
    return Perceptron(eta0=lr, max_iter=epochs, shuffle=True, tol=None,
                      random_state=random_state).fit(X, y)


def fit_logistic(X, y, random_state: int = 0):
    """经典概率基线（不是深度框架对照）。"""
    return LogisticRegression(max_iter=5000, random_state=random_state).fit(X, y)


class TorchPerceptron:
    """PyTorch 版感知机：`nn.Linear` + 逐样本 SGD，零初始化。

    感知机损失 `max(0, −y·score)` 对错分样本的梯度是 `−y·x`，
    所以 SGD(lr) 的更新与 `w += lr·y·x` 等价；对分对的样本梯度为 0，不更新。
    """

    def __init__(self, lr: float = 0.1, epochs: int = 10,
                 random_state: int | None = 0, standardize: bool = True) -> None:
        import torch

        self._torch = torch
        self.lr = float(lr)
        self.epochs = int(epochs)
        self.random_state = random_state
        self.standardize = bool(standardize)
        self.errors_per_epoch: list[int] = []
        self.epochs_run = 0
        self.linear = None
        self.scaler = None

    def fit(self, X, y):
        torch = self._torch
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        if X.ndim != 2 or y.ndim != 1 or len(X) != len(y):
            raise ValueError("X / y 形状不匹配")
        if not np.all((y == 1) | (y == -1)):
            raise ValueError("感知机的 y 必须是 −1 / +1")

        if self.standardize:
            self.scaler = StandardScaler().fit(X)
            Xs = self.scaler.transform(X)
        else:
            Xs = X
        Xs = Xs.astype(np.float32)

        torch.manual_seed(0 if self.random_state is None else self.random_state)
        self.linear = torch.nn.Linear(X.shape[1], 1)
        torch.nn.init.zeros_(self.linear.weight)
        torch.nn.init.zeros_(self.linear.bias)
        opt = torch.optim.SGD(self.linear.parameters(), lr=self.lr,
                              momentum=0.0, weight_decay=0.0)

        rng = np.random.default_rng(self.random_state)
        self.errors_per_epoch = []
        self.epochs_run = 0
        for _ in range(self.epochs):
            errors = 0
            for i in rng.permutation(len(X)):
                xb = torch.as_tensor(Xs[i:i + 1], dtype=torch.float32)
                yb = torch.as_tensor(y[i:i + 1], dtype=torch.float32)
                opt.zero_grad()
                margin = yb * self.linear(xb).squeeze(1)
                if margin.item() <= 0:      # 含恰好落在边界上：与手写版一致
                    errors += 1
                    (-margin).mean().backward()
                    opt.step()
            self.errors_per_epoch.append(errors)
            self.epochs_run += 1
            if errors == 0:
                break
        return self

    def decision_function(self, X) -> np.ndarray:
        torch = self._torch
        X = np.asarray(X, dtype=np.float64)
        Xs = self.scaler.transform(X) if self.scaler is not None else X
        with torch.no_grad():
            out = self.linear(torch.as_tensor(Xs, dtype=torch.float32))
        return out.detach().numpy().ravel()

    def predict(self, X) -> np.ndarray:
        return np.where(self.decision_function(X) >= 0, 1, -1)

    @property
    def coef_(self) -> np.ndarray:
        return self.linear.weight.detach().numpy().ravel()

    @property
    def intercept_(self) -> float:
        return float(self.linear.bias.detach().numpy().ravel()[0])


def fit_torch_perceptron(X, y, lr: float = 0.1, epochs: int = 10,
                         random_state: int = 0) -> TorchPerceptron:
    """PyTorch 版感知机；torch 未安装时由调用方捕获 ImportError。"""
    return TorchPerceptron(lr=lr, epochs=epochs, random_state=random_state).fit(X, y)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
