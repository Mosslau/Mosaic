"""LeNet — PyTorch 框架对照（深度模型 · 判别式）

对照对象：`nn.Conv2d + BatchNorm2d + ReLU + MaxPool2d + Linear`。
支持与手写版相同的 `use_bn` / `use_residual` 开关，便于并排比较。

手写纪律只约束 impl.py；本文件可用现成层。
"""

from __future__ import annotations

import time

import numpy as np


class TorchLeNet:
    def __init__(self, n_classes: int = 10, lr: float = 0.003, epochs: int = 100,
                 batch_size: int = 64, use_bn: bool = False,
                 use_residual: bool = False, random_state: int | None = 0) -> None:
        import torch

        self._torch = torch
        self.n_classes = n_classes
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.use_bn = use_bn
        self.use_residual = use_residual
        self.random_state = random_state
        self.loss_history: list[float] = []
        self.classes_ = None

    def _build(self):
        torch = self._torch
        self.conv1 = torch.nn.Conv2d(1, 6, 3, padding=1)
        self.bn1 = torch.nn.BatchNorm2d(6) if self.use_bn else None
        self.conv2 = torch.nn.Conv2d(6, 16, 3, padding=1)
        self.skip = torch.nn.Conv2d(6, 16, 1) if self.use_residual else None
        self.bn2 = torch.nn.BatchNorm2d(16) if self.use_bn else None
        self.fc1 = torch.nn.Linear(64, 32)
        self.fc2 = torch.nn.Linear(32, self.n_classes)
        self.net = torch.nn.Module()
        for name in ("conv1", "bn1", "conv2", "skip", "bn2", "fc1", "fc2"):
            obj = getattr(self, name)
            if obj is not None:
                setattr(self.net, name, obj)
        self.opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        self.loss_fn = torch.nn.CrossEntropyLoss()

    def _forward(self, x):
        torch = self._torch
        x = self.conv1(x)
        if self.bn1 is not None:
            x = self.bn1(x)
        x = torch.relu(x)
        x = torch.max_pool2d(x, 2)
        z = self.conv2(x)
        if self.skip is not None:
            z = z + self.skip(x)
        if self.bn2 is not None:
            z = self.bn2(z)
        z = torch.relu(z)
        z = torch.max_pool2d(z, 2)
        z = z.flatten(1)
        z = torch.relu(self.fc1(z))
        return self.fc2(z)

    def fit(self, X, y):
        torch = self._torch
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y)
        self.classes_, yi = np.unique(y, return_inverse=True)
        torch.manual_seed(0 if self.random_state is None else self.random_state)
        self._build()
        Xt = torch.as_tensor(X, dtype=torch.float32)
        yt = torch.as_tensor(yi, dtype=torch.long)
        self.loss_history = []
        for _ in range(self.epochs):
            order = torch.randperm(len(Xt))
            for s in range(0, len(Xt), self.batch_size):
                idx = order[s:s + self.batch_size]
                self.opt.zero_grad()
                loss = self.loss_fn(self._forward(Xt[idx]), yt[idx])
                loss.backward()
                self.opt.step()
            with torch.no_grad():
                self.loss_history.append(float(self.loss_fn(self._forward(Xt), yt)))
        return self

    def predict_proba(self, X):
        torch = self._torch
        with torch.no_grad():
            logits = self._forward(torch.as_tensor(np.asarray(X, dtype=np.float32)))
            return torch.softmax(logits, dim=1).numpy()

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


def run_framework(X_train, X_test, y_train, y_test, **kwargs) -> dict:
    t0 = time.perf_counter()
    model = TorchLeNet(**kwargs).fit(X_train, y_train)
    elapsed = time.perf_counter() - t0
    return {
        "acc": float(np.mean(model.predict(X_test) == y_test)),
        "loss": float(model.loss_history[-1]),
        "time_sec": elapsed,
        "model": model,
    }


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
