"""T5 / encoder-decoder — PyTorch 对照。

`nn.TransformerEncoderLayer` + `nn.TransformerDecoderLayer`（pre-LN），
同数据/同 80 轮；比较 loss/token acc/exact，不要求逐位一致。
"""

from __future__ import annotations

import time

import numpy as np
import torch
import torch.nn as nn


class TorchT5(nn.Module):
    def __init__(self, vocab_size, src_len=5, tgt_len=5, d_model=32, n_heads=4, d_ff=64):
        super().__init__()
        self.PAD, self.BOS, self.EOS = 0, 1, 2
        self.E = nn.Embedding(vocab_size, d_model)
        self.Pe = nn.Parameter(torch.zeros(src_len, d_model))
        self.Pd = nn.Parameter(torch.zeros(tgt_len, d_model))
        self.enc = nn.TransformerEncoderLayer(d_model, n_heads, d_ff, dropout=0.0,
                                              batch_first=True, norm_first=True)
        self.dec = nn.TransformerDecoderLayer(d_model, n_heads, d_ff, dropout=0.0,
                                              batch_first=True, norm_first=True)
        self.lm = nn.Linear(d_model, vocab_size)

    def forward(self, src, tin):
        src_mask = src != self.PAD
        mem = self.enc(self.E(src) + self.Pe, src_key_padding_mask=~src_mask)
        T = tin.shape[1]
        cm = torch.triu(torch.ones(T, T, dtype=torch.bool), diagonal=1)
        out = self.dec(self.E(tin) + self.Pd[:T], mem, tgt_mask=cm,
                       memory_key_padding_mask=~src_mask)
        return self.lm(out), out

    @torch.no_grad()
    def generate(self, src, max_steps=4):
        src = torch.as_tensor(src)[None]
        mem = self.enc(self.E(src) + self.Pe)
        ids = [self.BOS]
        for _ in range(max_steps):
            tin = torch.as_tensor(ids)[None]
            T = tin.shape[1]
            cm = torch.triu(torch.ones(T, T, dtype=torch.bool), diagonal=1)
            out = self.dec(self.E(tin) + self.Pd[:T], mem, tgt_mask=cm)
            nxt = int(self.lm(out)[0, -1].argmax())
            ids.append(nxt)
            if nxt == self.EOS:
                break
        return ids


def run_framework(train, test, vocab_size, epochs=80):
    torch.manual_seed(0)
    model = TorchT5(vocab_size)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    lossf = nn.CrossEntropyLoss()
    src = torch.as_tensor(np.array([p[0] for p in train]))
    tin = torch.as_tensor(np.array([p[1] for p in train]))
    tout = torch.as_tensor(np.array([p[2] for p in train]))
    t0 = time.perf_counter()
    for _ in range(epochs):
        logits, _ = model(src, tin)
        loss = lossf(logits.reshape(-1, vocab_size), tout.reshape(-1))
        opt.zero_grad()
        loss.backward()
        opt.step()
    t = time.perf_counter() - t0
    with torch.no_grad():
        logits, _ = model(src, tin)
        acc = float((logits.argmax(-1) == tout).float().mean())
        exact = []
        for p in test:
            ids = model.generate(p[0])
            chars = [i for i in ids if i >= 5]
            exact.append(chars == p[2][:-1])
    return {"loss": float(loss.detach()), "acc": acc, "exact": float(np.mean(exact)),
            "time_sec": t}


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 调用")
