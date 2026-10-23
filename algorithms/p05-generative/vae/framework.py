"""VAE — PyTorch 对照。

同结构：64→32→(mu,logvar)→2→32→64；损失 = 重构（像素和）+ KL。
"""

from __future__ import annotations

import time

import numpy as np
import torch
import torch.nn as nn


class TorchVAE(nn.Module):
    def __init__(self, latent_dim=2, hidden=32):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(64, hidden), nn.ReLU())
        self.mu = nn.Linear(hidden, latent_dim)
        self.lv = nn.Linear(hidden, latent_dim)
        self.dec = nn.Sequential(nn.Linear(latent_dim, hidden), nn.ReLU(),
                                 nn.Linear(hidden, 64), nn.Sigmoid())

    def encode(self, x):
        h = self.enc(x)
        return self.mu(h), self.lv(h)

    def forward(self, x):
        mu, lv = self.encode(x)
        z = mu + torch.exp(0.5 * lv) * torch.randn_like(mu)
        return self.dec(z), mu, lv


def run_framework(X_train, X_test, latent_dim=2, beta=1.0, epochs=100):
    torch.manual_seed(0)
    X = torch.as_tensor(X_train, dtype=torch.float32)
    model = TorchVAE(latent_dim)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    t0 = time.perf_counter()
    for _ in range(epochs):
        perm = torch.randperm(len(X))
        for s in range(0, len(X), 64):
            xb = X[perm[s:s + 64]]
            xhat, mu, lv = model(xb)
            recon = ((xhat - xb) ** 2).sum(1).mean()
            kl = (-0.5 * (1 + lv - mu ** 2 - lv.exp()).sum(1)).mean()
            loss = recon + beta * kl
            opt.zero_grad()
            loss.backward()
            opt.step()
    t = time.perf_counter() - t0
    with torch.no_grad():
        mu, _ = model.encode(torch.as_tensor(X_test, dtype=torch.float32))
        rec = model.dec(mu).numpy()
        mse = float(np.mean((rec - X_test) ** 2))
        z = torch.randn(16, latent_dim)
        samples = model.dec(z).numpy()
    return {"mse": mse, "loss": float(loss.detach()), "time_sec": t,
            "samples": samples, "recon": rec}


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 调用")
