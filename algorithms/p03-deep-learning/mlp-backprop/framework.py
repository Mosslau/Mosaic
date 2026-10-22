"""MLP 与手写反向传播 — PyTorch 框架对照

对照对象：`nn.Linear + ReLU(+Dropout) + CrossEntropyLoss` 与现成优化器。
目的：
1. 验证手写反向传播的准确率/损失量级；
2. 对照框架的初始化、优化器、LR schedule、dropout 与自动微分；
3. 分析“同一配置下为什么不能逐位对齐”（初始化/数值精度/算子顺序）。

手写纪律只约束 impl.py；本文件可用现成层与优化器。
"""

from __future__ import annotations

import time

import numpy as np


class TorchMLP:
    def __init__(
        self,
        hidden_sizes: tuple[int, ...] = (64, 32),
        lr: float = 0.01,
        epochs: int = 30,
        batch_size: int = 32,
        optimizer: str = "adam",
        init: str = "he",
        weight_decay: float = 0.0,
        dropout: float = 0.0,
        lr_schedule: str = "none",
        lr_decay: float = 0.5,
        step_size: int = 10,
        early_stopping: bool = False,
        patience: int = 5,
        validation_split: float = 0.0,
        random_state: int | None = 0,
    ) -> None:
        import torch

        self._torch = torch
        self.hidden_sizes = tuple(hidden_sizes)
        self.lr = float(lr)
        self.epochs = int(epochs)
        self.batch_size = int(batch_size)
        self.optimizer_name = optimizer
        self.init = init
        self.weight_decay = float(weight_decay)
        self.dropout = float(dropout)
        self.lr_schedule = lr_schedule
        self.lr_decay = float(lr_decay)
        self.step_size = int(step_size)
        self.early_stopping = bool(early_stopping)
        self.patience = int(patience)
        self.validation_split = float(validation_split)
        self.random_state = random_state
        self.loss_history: list[float] = []
        self.val_loss_history: list[float] = []
        self.epochs_run = 0
        self.model = None
        self.classes_ = None

    def _build(self, n_features: int, n_classes: int) -> None:
        torch = self._torch
        layers = []
        last = n_features
        for h in self.hidden_sizes:
            layers += [torch.nn.Linear(last, h), torch.nn.ReLU()]
            if self.dropout > 0:
                layers.append(torch.nn.Dropout(self.dropout))
            last = h
        layers.append(torch.nn.Linear(last, n_classes))
        self.model = torch.nn.Sequential(*layers)
        for m in self.model:
            if isinstance(m, torch.nn.Linear):
                if self.init == "zero":
                    torch.nn.init.zeros_(m.weight)
                elif self.init == "random":
                    torch.nn.init.normal_(m.weight, 0.0, 0.01)
                elif self.init == "xavier":
                    torch.nn.init.xavier_uniform_(m.weight)
                else:
                    torch.nn.init.kaiming_normal_(m.weight, nonlinearity="relu")
                torch.nn.init.zeros_(m.bias)

        if self.optimizer_name == "sgd":
            self.opt = torch.optim.SGD(self.model.parameters(), lr=self.lr,
                                       momentum=0.0, weight_decay=self.weight_decay)
        elif self.optimizer_name == "momentum":
            self.opt = torch.optim.SGD(self.model.parameters(), lr=self.lr,
                                       momentum=0.9, weight_decay=self.weight_decay)
        else:
            self.opt = torch.optim.Adam(self.model.parameters(), lr=self.lr,
                                        weight_decay=self.weight_decay)
        self.loss_fn = torch.nn.CrossEntropyLoss()

    def _lr(self, epoch: int) -> float:
        if self.lr_schedule == "step":
            return self.lr * self.lr_decay ** (epoch // max(self.step_size, 1))
        if self.lr_schedule == "cosine":
            return 0.5 * self.lr * (1.0 + np.cos(np.pi * epoch / self.epochs))
        return self.lr

    def fit(self, X, y):
        torch = self._torch
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y)
        if X.ndim != 2 or y.ndim != 1 or len(X) != len(y):
            raise ValueError("X / y 形状不匹配")
        self.classes_, y_idx = np.unique(y, return_inverse=True)
        torch.manual_seed(0 if self.random_state is None else self.random_state)
        self._build(X.shape[1], len(self.classes_))

        X_fit, y_fit = X, y_idx
        X_val = y_val = None
        if self.validation_split > 0:
            rng = np.random.default_rng(self.random_state)
            n_val = max(1, int(len(X) * self.validation_split))
            idx = rng.permutation(len(X))
            val_idx, tr_idx = idx[:n_val], idx[n_val:]
            X_fit, y_fit = X[tr_idx], y_idx[tr_idx]
            X_val, y_val = X[val_idx], y_idx[val_idx]

        self.loss_history, self.val_loss_history = [], []
        best, wait = np.inf, 0
        for epoch in range(self.epochs):
            for g in self.opt.param_groups:
                g["lr"] = self._lr(epoch)
            self.model.train()
            order = torch.randperm(len(X_fit))
            for start in range(0, len(X_fit), self.batch_size):
                idx = order[start:start + self.batch_size]
                xb = torch.as_tensor(X_fit[idx.numpy()], dtype=torch.float32)
                yb = torch.as_tensor(y_fit[idx.numpy()], dtype=torch.long)
                self.opt.zero_grad()
                loss = self.loss_fn(self.model(xb), yb)
                loss.backward()
                self.opt.step()
            self.model.eval()
            with torch.no_grad():
                xb = torch.as_tensor(X_fit, dtype=torch.float32)
                train_loss = float(self.loss_fn(self.model(xb),
                                                torch.as_tensor(y_fit, dtype=torch.long)))
                self.loss_history.append(train_loss)
                if X_val is not None:
                    xv = torch.as_tensor(X_val, dtype=torch.float32)
                    val_loss = float(self.loss_fn(self.model(xv),
                                                  torch.as_tensor(y_val, dtype=torch.long)))
                    self.val_loss_history.append(val_loss)
                    monitor = val_loss
                else:
                    monitor = train_loss
            self.epochs_run += 1
            if self.early_stopping:
                if monitor < best - 1e-6:
                    best, wait = monitor, 0
                else:
                    wait += 1
                    if wait >= self.patience:
                        break
        return self

    def predict_proba(self, X):
        torch = self._torch
        self.model.eval()
        with torch.no_grad():
            logits = self.model(torch.as_tensor(np.asarray(X, dtype=np.float32)))
            return torch.softmax(logits, dim=1).numpy()

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


def fit_torch_mlp(X, y, **kwargs) -> TorchMLP:
    return TorchMLP(**kwargs).fit(X, y)


def run_framework(X_train, X_test, y_train, y_test, **kwargs) -> dict:
    """训练 torch MLP 并返回与手写版对齐的指标。"""
    t0 = time.perf_counter()
    model = TorchMLP(**kwargs).fit(X_train, y_train)
    elapsed = time.perf_counter() - t0
    pred = model.predict(X_test)
    return {
        "acc": float(np.mean(pred == y_test)),
        "loss": float(model.loss_history[-1]),
        "time_sec": elapsed,
        "model": model,
    }


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
