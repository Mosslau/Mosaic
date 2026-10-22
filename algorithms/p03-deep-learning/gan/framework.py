"""GAN — PyTorch 框架对照（深度模型 · 生成式）

对照对象：G/D 两个 MLP + Adam，支持 non-saturating / saturating 损失。
"""

from __future__ import annotations

import time

import numpy as np


class TorchGAN:
    def __init__(self, data_dim=2, latent_dim=8, hidden=(64, 64), lr_g=2e-4,
                 lr_d=2e-4, loss_type="non_saturating", out_sigmoid=False,
                 g_steps=1, random_state=0) -> None:
        import torch

        self._torch = torch
        self.data_dim, self.latent_dim = data_dim, latent_dim
        self.hidden = tuple(hidden)
        self.lr_g, self.lr_d = lr_g, lr_d
        self.loss_type = loss_type
        self.out_sigmoid = out_sigmoid
        self.g_steps = g_steps
        self.random_state = random_state
        self.d_loss_history: list[float] = []
        self.g_loss_history: list[float] = []

    def _mlp(self, sizes, sigmoid_out=False):
        torch = self._torch
        layers = []
        for a, b in zip(sizes[:-1], sizes[1:]):
            layers.append(torch.nn.Linear(a, b))
            if b != sizes[-1]:
                layers.append(torch.nn.LeakyReLU(0.01))
        if sigmoid_out:
            layers.append(torch.nn.Sigmoid())
        return torch.nn.Sequential(*layers)

    def _build(self):
        torch = self._torch
        self.G = self._mlp([self.latent_dim, *self.hidden, self.data_dim], self.out_sigmoid)
        self.D = self._mlp([self.data_dim, *self.hidden, 1], True)
        self.optg = torch.optim.Adam(self.G.parameters(), lr=self.lr_g, betas=(0.5, 0.999))
        self.optd = torch.optim.Adam(self.D.parameters(), lr=self.lr_d, betas=(0.5, 0.999))
        self.bce = torch.nn.BCELoss()

    def train(self, X, epochs=200, batch_size=64):
        torch = self._torch
        X = np.asarray(X, dtype=np.float32)
        torch.manual_seed(0 if self.random_state is None else self.random_state)
        self._build()
        Xt = torch.as_tensor(X, dtype=torch.float32)
        n = len(Xt)
        self.d_loss_history, self.g_loss_history = [], []
        for _ in range(epochs):
            order = torch.randperm(n)
            for s in range(0, n, batch_size):
                real = Xt[order[s:s + batch_size]]
                m = len(real)
                z = torch.randn(m, self.latent_dim)
                fake = self.G(z).detach()
                self.optd.zero_grad()
                loss_d = self.bce(self.D(real), torch.ones(m, 1)) + \
                    self.bce(self.D(fake), torch.zeros(m, 1))
                loss_d.backward()
                self.optd.step()
                for _ in range(self.g_steps):
                    z = torch.randn(m, self.latent_dim)
                    out = self.D(self.G(z))
                    if self.loss_type == "non_saturating":
                        loss_g = -torch.log(torch.clamp(out, 1e-8, 1)).mean()
                    else:
                        loss_g = torch.log(torch.clamp(1 - out, 1e-8, 1)).mean()
                    self.optg.zero_grad()
                    loss_g.backward()
                    self.optg.step()
            self.d_loss_history.append(float(loss_d.detach()))
            self.g_loss_history.append(float(loss_g.detach()))
        return self

    def sample(self, n=16):
        torch = self._torch
        with torch.no_grad():
            return self.G(torch.randn(n, self.latent_dim)).numpy()


def run_framework(X, **kwargs):
    t0 = time.perf_counter()
    model = TorchGAN(**kwargs).train(X, epochs=kwargs.pop("epochs", 200),
                                     batch_size=kwargs.pop("batch_size", 64))
    return {"time_sec": time.perf_counter() - t0, "model": model}


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
