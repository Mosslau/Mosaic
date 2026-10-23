"""DDPM — PyTorch 对照。

同结构 MLP（时间嵌入 + 类别嵌入），训练预测 eps；支持无条件/条件/CFG 采样。
"""

from __future__ import annotations

import time

import torch
import torch.nn as nn


class TorchDenoiser(nn.Module):
    def __init__(self, num_classes=10, hidden=128):
        super().__init__()
        self.null = num_classes
        self.emb = nn.Embedding(num_classes + 1, 8)
        self.net = nn.Sequential(nn.Linear(64 + 16 + 8, hidden), nn.ReLU(),
                                 nn.Linear(hidden, hidden), nn.ReLU(),
                                 nn.Linear(hidden, 64))

    def te(self, t, n_steps):
        t = t.float() / n_steps
        freqs = torch.exp(-torch.log(torch.tensor(10000.0)) *
                          torch.arange(8).float() / 8)
        args = t[:, None] * freqs[None, :]
        return torch.cat([torch.sin(args), torch.cos(args)], 1)

    def forward(self, x, t, y, n_steps):
        return self.net(torch.cat([x, self.te(t, n_steps), self.emb(y)], 1))


def run_framework(Xtr, ytr, labels, n_steps=100, epochs=100, guidance=3.0):
    torch.manual_seed(0)
    net = TorchDenoiser()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    X = torch.as_tensor(Xtr, dtype=torch.float32)
    Y = torch.as_tensor(ytr, dtype=torch.long)
    betas = torch.linspace(1e-4, 0.02, n_steps)
    ab = torch.cumprod(1 - betas, 0)
    t0 = time.perf_counter()
    for _ in range(epochs):
        perm = torch.randperm(len(X))
        for s in range(0, len(X), 64):
            idx = perm[s:s + 64]
            xb, yb = X[idx], Y[idx].clone()
            t = torch.randint(0, n_steps, (len(xb),))
            eps = torch.randn_like(xb)
            xt = ab[t].sqrt()[:, None] * xb + (1 - ab[t]).sqrt()[:, None] * eps
            drop = torch.rand(len(xb)) < 0.1
            yb[drop] = net.null
            pred = net(xt, t, yb, n_steps)
            loss = ((pred - eps) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    train_time = time.perf_counter() - t0

    @torch.no_grad()
    def sample(n=200, labels=None, w=1.0):
        x = torch.randn(n, 64)
        if labels is None:
            y = torch.full((n,), net.null, dtype=torch.long)
        else:
            y = torch.as_tensor(labels)
        for t in reversed(range(n_steps)):
            tt = torch.full((n,), t)
            cond = net(x, tt, y, n_steps)
            if labels is None or w == 1.0:
                eps = cond
            else:
                un = net(x, tt, torch.full((n,), net.null), n_steps)
                eps = un + w * (cond - un)
            a = ab[t]
            ap = ab[t - 1] if t > 0 else torch.tensor(1.0)
            x0 = ((x - (1 - a).sqrt() * eps) / a.sqrt()).clamp(0, 1)
            if t > 0:
                mean = (ap.sqrt() * betas[t] / (1 - a) * x0
                        + (1 - betas[t]).sqrt() * (1 - ap) / (1 - a) * x)
                x = mean + (betas[t] * (1 - ap) / (1 - a)).sqrt() * torch.randn_like(x)
            else:
                x = x0
        return x.numpy()

    t1 = time.perf_counter()
    samples = sample(len(labels), labels, guidance)
    sample_time = time.perf_counter() - t1
    return {"loss": float(loss.detach()), "samples": samples, "sample_time": sample_time,
            "time_sec": train_time}


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 调用")
