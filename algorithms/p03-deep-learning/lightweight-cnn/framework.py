"""轻量级 CNN — PyTorch 框架对照（深度模型 · 判别式）

与手写 `MobileNetLite` 等价：stem Conv-BN-ReLU，3 个深度可分离块
（depthwise 3×3 用 `groups=in_channels` + pointwise 1×1，各带 BN），
每块后 2×2 池化，全局平均池化 + 线性头；卷积同样不带 bias。

    net = TorchMobileNetLite(widths=(8,16,32,32)).fit(X, y)
    net.n_params()          # 应等于手写版 2858
    net.predict(X)

手写纪律只约束 impl.py；本文件可用现成层。
"""

from __future__ import annotations

import time

import numpy as np


class TorchMobileNetLite:
    def __init__(self, widths=(8, 16, 32, 32), n_classes: int = 10, lr: float = 0.01,
                 epochs: int = 20, batch_size: int = 64, random_state: int = 0,
                 threads: int = 1) -> None:
        import torch

        self._torch = torch
        self.threads = threads
        self.widths = tuple(int(w) for w in widths)
        self.n_classes, self.lr, self.epochs = n_classes, lr, epochs
        self.batch_size, self.random_state = batch_size, random_state
        self.history: dict[str, list[float]] = {"loss": [], "train_acc": []}
        self.classes_ = None

    def _build(self):
        torch, nn = self._torch, self._torch.nn
        w = self.widths
        self.stem = nn.Sequential(
            nn.Conv2d(1, w[0], 3, padding=1, bias=False), nn.BatchNorm2d(w[0]), nn.ReLU())
        blocks = []
        for i in range(len(w) - 1):
            blocks.append(nn.Sequential(
                # depthwise：groups=in_channels，每个通道单独卷积，不跨通道求和
                nn.Conv2d(w[i], w[i], 3, padding=1, groups=w[i], bias=False),
                nn.BatchNorm2d(w[i]), nn.ReLU(),
                nn.Conv2d(w[i], w[i + 1], 1, bias=False), nn.BatchNorm2d(w[i + 1]), nn.ReLU(),
                nn.MaxPool2d(2)))
        self.blocks = nn.ModuleList(blocks)
        self.head = nn.Linear(w[-1], self.n_classes)
        self.net = nn.Sequential(self.stem, *self.blocks, nn.AdaptiveAvgPool2d(1),
                                 nn.Flatten(), self.head)
        self.opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        self.loss_fn = nn.CrossEntropyLoss()

    def n_params(self) -> int:
        return int(sum(p.numel() for p in self.net.parameters()))

    def fit(self, X, y):
        torch = self._torch
        # 16×16 小张量上多线程调度开销远大于计算，固定单线程更快也更可复现
        torch.set_num_threads(self.threads)
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y)
        self.classes_, yi = np.unique(y, return_inverse=True)
        torch.manual_seed(self.random_state)
        self._build()
        Xt = torch.as_tensor(X)
        yt = torch.as_tensor(yi, dtype=torch.long)
        self.history = {"loss": [], "train_acc": []}
        for _ in range(self.epochs):
            order = torch.randperm(len(Xt))
            for s in range(0, len(Xt), self.batch_size):
                idx = order[s:s + self.batch_size]
                self.opt.zero_grad()
                loss = self.loss_fn(self.net(Xt[idx]), yt[idx])
                loss.backward()
                self.opt.step()
            with torch.no_grad():
                logits = self.net(Xt)
                self.history["loss"].append(float(self.loss_fn(logits, yt)))
                self.history["train_acc"].append(
                    float((logits.argmax(dim=1) == yt).float().mean()))
        return self

    def predict_proba(self, X):
        torch = self._torch
        with torch.no_grad():
            logits = self.net(torch.as_tensor(np.asarray(X, dtype=np.float32)))
            return torch.softmax(logits, dim=1).numpy()

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


def set_threads(n: int) -> None:
    """设置 torch CPU 线程数（延迟对照用；小张量上 1 线程通常最快）。"""
    import torch

    torch.set_num_threads(n)


def run_framework(X_train, X_test, y_train, y_test, **kwargs) -> dict:
    t0 = time.perf_counter()
    model = TorchMobileNetLite(**kwargs).fit(X_train, y_train)
    return {
        "acc": float(np.mean(model.predict(X_test) == y_test)),
        "time_sec": time.perf_counter() - t0,
        "model": model,
    }


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
