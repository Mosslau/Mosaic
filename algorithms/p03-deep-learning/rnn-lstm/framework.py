"""RNN 与 LSTM — PyTorch 框架对照

对照对象：`nn.RNN` / `nn.LSTM` + `Linear`，多对一序列分类。
支持 `clip_norm`，与手写版的全局梯度裁剪对齐。
"""

from __future__ import annotations

import time

import numpy as np


class TorchSequence:
    def __init__(self, cell: str = "rnn", input_size: int = 2, hidden_size: int = 32,
                 n_classes: int = 2, lr: float = 0.01, epochs: int = 40,
                 batch_size: int = 32, clip_norm: float | None = 1.0,
                 random_state: int | None = 0) -> None:
        import torch

        self._torch = torch
        self.cell = cell
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.n_classes = n_classes
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.clip_norm = clip_norm
        self.random_state = random_state
        self.loss_history: list[float] = []
        self.classes_ = None

    def _build(self):
        torch = self._torch
        cls = torch.nn.LSTM if self.cell == "lstm" else torch.nn.RNN
        self.rnn = cls(self.input_size, self.hidden_size, batch_first=True)
        self.fc = torch.nn.Linear(self.hidden_size, self.n_classes)
        self.opt = torch.optim.Adam(list(self.rnn.parameters()) + list(self.fc.parameters()),
                                    lr=self.lr)
        self.loss_fn = torch.nn.CrossEntropyLoss()

    def _forward(self, x):
        out, _ = self.rnn(x)
        return self.fc(out[:, -1])

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
                if self.clip_norm is not None:
                    torch.nn.utils.clip_grad_norm_(
                        list(self.rnn.parameters()) + list(self.fc.parameters()),
                        self.clip_norm)
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
    model = TorchSequence(**kwargs).fit(X_train, y_train)
    return {"acc": float(np.mean(model.predict(X_test) == y_test)),
            "loss": float(model.loss_history[-1]),
            "time_sec": time.perf_counter() - t0, "model": model}


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
