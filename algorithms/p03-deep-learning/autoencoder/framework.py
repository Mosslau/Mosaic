"""AutoEncoder — PyTorch 框架对照（深度模型 · 无监督）

对照对象：对称 MLP（64→32→latent→32→64，sigmoid 输出，MSE），支持 denoising。
"""

from __future__ import annotations

import numpy as np


class TorchAE:
    def __init__(self, latent_dim: int = 2, lr: float = 0.01, epochs: int = 100,
                 batch_size: int = 64, denoising: float = 0.0,
                 random_state: int | None = 0) -> None:
        import torch

        self._torch = torch
        self.latent_dim = latent_dim
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.denoising = denoising
        self.random_state = random_state
        self.loss_history: list[float] = []

    def _build(self, d: int):
        torch = self._torch
        H = 32
        self.enc = torch.nn.Sequential(
            torch.nn.Linear(d, H), torch.nn.ReLU(),
            torch.nn.Linear(H, self.latent_dim))
        self.dec = torch.nn.Sequential(
            torch.nn.Linear(self.latent_dim, H), torch.nn.ReLU(),
            torch.nn.Linear(H, d), torch.nn.Sigmoid())
        self.opt = torch.optim.Adam(list(self.enc.parameters()) + list(self.dec.parameters()),
                                    lr=self.lr)

    def fit(self, X):
        torch = self._torch
        X = np.asarray(X, dtype=np.float32)
        torch.manual_seed(0 if self.random_state is None else self.random_state)
        self._build(X.shape[1])
        Xt = torch.as_tensor(X, dtype=torch.float32)
        self.loss_history = []
        for _ in range(self.epochs):
            order = torch.randperm(len(Xt))
            for s in range(0, len(Xt), self.batch_size):
                idx = order[s:s + self.batch_size]
                clean = Xt[idx]
                noisy = clean
                if self.denoising > 0:
                    noisy = clean + torch.randn_like(clean) * self.denoising
                self.opt.zero_grad()
                loss = torch.mean((self.dec(self.enc(noisy)) - clean) ** 2)
                loss.backward()
                self.opt.step()
            with torch.no_grad():
                self.loss_history.append(float(torch.mean((self.dec(self.enc(Xt)) - Xt) ** 2)))
        return self

    def encode(self, X):
        torch = self._torch
        with torch.no_grad():
            return self.enc(torch.as_tensor(np.asarray(X, dtype=np.float32))).numpy()

    def decode(self, Z):
        torch = self._torch
        with torch.no_grad():
            return self.dec(torch.as_tensor(np.asarray(Z, dtype=np.float32))).numpy()

    def reconstruct(self, X):
        return self.decode(self.encode(X))

    def reconstruction_error(self, X):
        X = np.asarray(X, dtype=float)
        return float(np.mean((self.reconstruct(X) - X) ** 2))


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
