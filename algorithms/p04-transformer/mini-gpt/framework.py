"""Mini-GPT — PyTorch 对照。

用 `nn.TransformerEncoderLayer(norm_first=True)` + causal mask 堆 N 层；
同语料/同 context/同轮数，比较 loss/acc 与生成。
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


class TorchGPT(nn.Module):
    def __init__(self, vocab_size, context=16, d_model=32, n_heads=4, n_layers=2, d_ff=64):
        super().__init__()
        self.E = nn.Embedding(vocab_size, d_model)
        self.P = nn.Parameter(torch.zeros(context, d_model))
        layer = nn.TransformerEncoderLayer(d_model, n_heads, d_ff, dropout=0.0,
                                           batch_first=True, norm_first=True)
        self.blocks = nn.TransformerEncoder(layer, num_layers=n_layers, enable_nested_tensor=False)
        self.lm = nn.Linear(d_model, vocab_size)

    def forward(self, tokens):
        T = tokens.shape[1]
        x = self.E(tokens) + self.P[:T]
        mask = torch.triu(torch.ones(T, T, dtype=torch.bool), diagonal=1)
        return self.lm(self.blocks(x, mask=mask))

    @torch.no_grad()
    def generate(self, prompt, tokenizer, n_steps=20, temperature=1.0, top_k=None):
        ids = list(tokenizer.encode(prompt))
        for _ in range(n_steps):
            ctx = torch.as_tensor(ids[-self.P.shape[0]:])[None]
            probs = torch.softmax(self(ctx)[0, -1], dim=-1)
            if temperature <= 0:
                nxt = int(probs.argmax())
            else:
                logits = torch.log(probs.clamp_min(1e-12)) / temperature
                if top_k is not None:
                    k = min(top_k, logits.numel())
                    vals, _ = torch.topk(logits, k)
                    logits[logits < vals[-1]] = -1e9
                nxt = int(torch.multinomial(torch.softmax(logits, -1), 1))
            ids.append(nxt)
        return tokenizer.decode(ids)


def run_framework(tr, te, vocab_size, context=16, n_layers=2, epochs=80):
    torch.manual_seed(0)
    T = context
    X, Y = _windows(tr, T, T // 2)
    Xte, Yte = _windows(te, T, T // 2)
    Xt, Yt = torch.as_tensor(X), torch.as_tensor(Y)
    model = TorchGPT(vocab_size, context=T, n_layers=n_layers)
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
        train_loss = float(lossf(model(Xt).reshape(-1, vocab_size), Yt.reshape(-1)))
        logits = model(torch.as_tensor(Xte)).reshape(-1, vocab_size)
        test_loss = float(lossf(logits, torch.as_tensor(Yte).reshape(-1)))
        test_acc = float((logits.argmax(-1) == torch.as_tensor(Yte).reshape(-1)).float().mean())
    return {"train_loss": train_loss, "test_loss": test_loss, "test_acc": test_acc,
            "time_sec": train_time}


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 调用")
