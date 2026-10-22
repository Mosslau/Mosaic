"""迷你 Transformer Block — PyTorch 对照。

用 `nn.TransformerEncoderLayer(norm_first=True)`（pre-LN）搭同样的 Block，
与手写版同语料、同 context、同轮数；只比较量级/趋势，不要求逐位一致。
"""

from __future__ import annotations

import time

import numpy as np
import torch
import torch.nn as nn


def _windows(tokens, T, stride):
    xs, ys = [], []
    for i in range(0, len(tokens) - T, stride):
        xs.append(tokens[i:i + T])
        ys.append(tokens[i + 1:i + T + 1])
    return np.array(xs), np.array(ys)


class TorchBlock(nn.Module):
    def __init__(self, vocab_size, d_model=32, n_heads=4, d_ff=64, context=16):
        super().__init__()
        self.E = nn.Embedding(vocab_size, d_model)
        self.P = nn.Parameter(torch.zeros(context, d_model))
        layer = nn.TransformerEncoderLayer(d_model, n_heads, d_ff, dropout=0.0,
                                           batch_first=True, norm_first=True)
        self.block = layer
        self.lm = nn.Linear(d_model, vocab_size)

    def forward(self, tokens):
        T = tokens.shape[1]
        x = self.E(tokens) + self.P[:T]
        mask = torch.triu(torch.ones(T, T, dtype=torch.bool), diagonal=1)
        return self.lm(self.block(x, src_mask=mask))


def run_framework(tr, te, vocab_size, context=16, epochs=40):
    torch.manual_seed(0)
    X, Y = _windows(tr, context, max(1, context // 2))
    Xte, Yte = _windows(te, context, max(1, context // 2))
    Xt, Yt = torch.as_tensor(X), torch.as_tensor(Y)
    model = TorchBlock(vocab_size, context=context)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    lossf = nn.CrossEntropyLoss()
    t0 = time.perf_counter()
    for _ in range(epochs):
        order = torch.randperm(len(Xt))
        for s in range(0, len(Xt), 32):
            idx = order[s:s + 32]
            opt.zero_grad()
            loss = lossf(model(Xt[idx]).reshape(-1, vocab_size), Yt[idx].reshape(-1))
            loss.backward()
            opt.step()
    train_time = time.perf_counter() - t0
    with torch.no_grad():
        logits = model(Xt).reshape(-1, vocab_size)
        train_loss = float(lossf(logits, Yt.reshape(-1)))
        logits_te = model(torch.as_tensor(Xte)).reshape(-1, vocab_size)
        test_loss = float(lossf(logits_te, torch.as_tensor(Yte).reshape(-1)))
        test_acc = float((logits_te.argmax(-1) == torch.as_tensor(Yte).reshape(-1)).float().mean())
    return {"train_loss": train_loss, "test_loss": test_loss, "test_acc": test_acc,
            "time_sec": train_time}


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 调用")
