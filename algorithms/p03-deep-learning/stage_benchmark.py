"""p03 阶段横向对照（同一份 digits 数据，PyTorch 框架口径）

    uv run python stage_benchmark.py

目的：把 p03 的模型族放在**同一份 8×8 digits** 上做选型级比较；手写实现与框架的
一致性由各实验的 test/demo 保证（这里不再重复逐位对账）。

三块：
1. 10 分类：逻辑回归 / MLP / LeNet(BN+残差) / LSTM(行序列)
2. 无监督：AE(latent=8) vs PCA(8) 的重构 MSE
3. 序列：parity T=12 的 RNN vs LSTM

4.3.2–4.3.4（轻量 CNN / 检测 / 分割）的任务、数据与指标不同，见族导读 §13
「任务特定补充」；本脚本只做同一份 digits 口径，不混入。
"""

from __future__ import annotations

import time

import numpy as np
import torch
import torch.nn as nn
from sklearn.datasets import load_digits
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

SEED = 0


def digits():
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    return train_test_split(X, y, train_size=1200, random_state=SEED, stratify=y)


def count_params(model) -> int:
    return sum(p.numel() for p in model.parameters())


class MLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 10))

    def forward(self, x):
        return self.net(x)


class LeNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.c1 = nn.Conv2d(1, 6, 3, padding=1)
        self.b1 = nn.BatchNorm2d(6)
        self.c2 = nn.Conv2d(6, 16, 3, padding=1)
        self.skip = nn.Conv2d(6, 16, 1)
        self.b2 = nn.BatchNorm2d(16)
        self.fc = nn.Sequential(nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 10))

    def forward(self, x):
        x = torch.relu(self.b1(self.c1(x)))
        x = torch.max_pool2d(x, 2)
        z = self.c2(x) + self.skip(x)
        z = torch.relu(self.b2(z))
        z = torch.max_pool2d(z, 2)
        return self.fc(z.flatten(1))


class LSTMNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.rnn = nn.LSTM(8, 32, batch_first=True)
        self.fc = nn.Linear(32, 10)

    def forward(self, x):
        out, _ = self.rnn(x)
        return self.fc(out[:, -1])


def train_torch(model, X, y, epochs, lr, batch=64):
    torch.manual_seed(SEED)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    lossf = nn.CrossEntropyLoss()
    Xt = torch.as_tensor(X, dtype=torch.float32)
    yt = torch.as_tensor(y, dtype=torch.long)
    t0 = time.perf_counter()
    for _ in range(epochs):
        order = torch.randperm(len(Xt))
        for s in range(0, len(Xt), batch):
            idx = order[s:s + batch]
            opt.zero_grad()
            loss = lossf(model(Xt[idx]), yt[idx])
            loss.backward()
            opt.step()
    return time.perf_counter() - t0


def classification() -> None:
    X_tr, X_te, y_tr, y_te = digits()
    flat_tr, flat_te = X_tr, X_te
    seq_tr = torch.as_tensor(X_tr.reshape(-1, 8, 8), dtype=torch.float32)
    seq_te = torch.as_tensor(X_te.reshape(-1, 8, 8), dtype=torch.float32)

    print("== 10 分类：digits 8×8（1200/597） ==")
    print(f"{'模型':16} | {'acc':>6} | {'macro F1':>8} | {'params':>8} | "
          f"{'epochs':>6} | {'time(s)':>7}")
    print("-" * 70)

    log = LogisticRegression(max_iter=5000).fit(flat_tr, y_tr)
    pred = log.predict(flat_te)
    log_acc = float(np.mean(pred == y_te))
    print(f"{'逻辑回归':16} | {log_acc:6.3f} | "
          f"{f1_score(y_te, pred, average='macro'):8.3f} | {'—':>8} | {0:6d} | {0:7.2f}")
    assert log_acc > 0.9

    models = [
        ("MLP", MLP(), flat_tr, flat_te, 40, 0.01),
        ("LeNet(BN+res)", LeNet(), X_tr.reshape(-1, 1, 8, 8),
         X_te.reshape(-1, 1, 8, 8), 80, 0.003),
        ("LSTM(行序列)", LSTMNet(), seq_tr.numpy(), seq_te.numpy(), 40, 0.01),
    ]
    for name, model, A, B, epochs, lr, is_seq in models:
        if not is_seq:
            A_t = torch.as_tensor(A, dtype=torch.float32)
        else:
            A_t = torch.as_tensor(A, dtype=torch.float32)
        t = train_torch(model, A_t.numpy(), y_tr, epochs, lr)
        with torch.no_grad():
            pred = model(torch.as_tensor(B, dtype=torch.float32)).argmax(1).numpy()
        acc = float(np.mean(pred == y_te))
        if name.startswith("LeNet"):
            assert acc > 0.95
        elif name.startswith("LSTM"):
            assert acc > 0.9
        else:
            assert acc > 0.9
        print(f"{name:16} | {acc:6.3f} | "
              f"{f1_score(y_te, pred, average='macro'):8.3f} | "
              f"{count_params(model):8d} | {epochs:6d} | {t:7.2f}")


def unsupervised() -> None:
    X_tr, X_te, _, _ = digits()
    from autoencoder.framework import TorchAE

    torch.manual_seed(SEED)
    ae = TorchAE(latent_dim=8, lr=0.01, epochs=100, random_state=SEED).fit(
        X_tr.reshape(len(X_tr), -1))
    pca = PCA(n_components=8).fit(X_tr.reshape(len(X_tr), -1))
    rec = pca.inverse_transform(pca.transform(X_te.reshape(len(X_te), -1)))
    print("\n== 无监督：latent=8 重构 MSE ==")
    ae_err = ae.reconstruction_error(X_te.reshape(len(X_te), -1))
    pca_err = float(np.mean((rec - X_te.reshape(len(X_te), -1)) ** 2))
    print(f"AE  {ae_err:.4f}")
    print(f"PCA {pca_err:.4f}")
    assert ae_err < pca_err


def sequence() -> None:
    rng = np.random.default_rng(SEED)
    n, T = 5000, 12
    X = rng.integers(0, 2, size=(n, T))
    y = X.sum(axis=1) % 2
    X = np.eye(2)[X]
    X_tr, X_te, y_tr, y_te = X[:4000], X[4000:], y[:4000], y[4000:]
    print("\n== 序列：parity T=12（4000/1000） ==")
    print(f"{'模型':10} | {'acc':>6} | {'params':>7} | {'time(s)':>7}")
    print("-" * 34)
    for name, cell in (("RNN", nn.RNN), ("LSTM", nn.LSTM)):
        rnn = cell(2, 32, batch_first=True)
        fc = nn.Linear(32, 2)
        class Seq(nn.Module):
            def __init__(self):
                super().__init__()
                self.rnn, self.fc = rnn, fc
            def forward(self, x):
                out, _ = self.rnn(x)
                return self.fc(out[:, -1])
        net = Seq()
        t = train_torch(net, X_tr, y_tr, 40, 0.01)
        with torch.no_grad():
            pred = net(torch.as_tensor(X_te, dtype=torch.float32)).argmax(1).numpy()
        acc = float(np.mean(pred == y_te))
        if name == "RNN":
            assert acc < 0.7
        else:
            assert acc > 0.9
        print(f"{name:10} | {acc:6.3f} | {count_params(net):7d} | {t:7.2f}")


def main() -> None:
    classification()
    unsupervised()
    sequence()


if __name__ == "__main__":
    main()
