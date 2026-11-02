"""BERT / MLM — PyTorch 对照。

用 `nn.TransformerEncoderLayer(norm_first=True)`（非 causal）+ MLM head；
同数据、同 15% mask；比较 MLM loss/acc 与 [CLS] 探针。
"""

from __future__ import annotations

import time

import numpy as np
import torch
import torch.nn as nn
from sklearn.linear_model import LogisticRegression

PAD, MASK, CLS, SEP, UNK = 0, 1, 2, 3, 4


class TorchBERT(nn.Module):
    def __init__(self, vocab_size, context=16, d_model=32, n_heads=4, d_ff=64):
        super().__init__()
        self.E = nn.Embedding(vocab_size, d_model, padding_idx=PAD)
        self.P = nn.Parameter(torch.zeros(context, d_model))
        layer = nn.TransformerEncoderLayer(d_model, n_heads, d_ff, dropout=0.0,
                                           batch_first=True, norm_first=True)
        self.enc = layer
        self.lm = nn.Linear(d_model, vocab_size)

    def forward(self, tokens):
        T = tokens.shape[1]
        x = self.E(tokens) + self.P[:T]
        pad = tokens == PAD
        out = self.enc(x, src_key_padding_mask=pad)
        return self.lm(out), out


def _eval_mask(tokens, seed=123, vocab_size=None):
    rng = np.random.default_rng(seed)
    inp = tokens.copy()
    target = tokens.copy()
    mask_pos = np.zeros_like(tokens, dtype=bool)
    for n in range(len(tokens)):
        eligible = np.flatnonzero((tokens[n] != PAD) & (tokens[n] != CLS) &
                                  (tokens[n] != SEP))
        if len(eligible) == 0:
            continue
        k = max(1, int(round(len(eligible) * 0.15)))
        chosen = rng.choice(eligible, size=k, replace=False)
        mask_pos[n, chosen] = True
        for j in chosen:
            r = rng.random()
            if r < 0.8:
                inp[n, j] = MASK
            elif r < 0.9:
                inp[n, j] = int(rng.integers(5, vocab_size or (int(tokens.max()) + 1)))
    return inp, target, mask_pos


def run_framework(tokens, labels, tok, context=16, epochs=120,
                  test_tokens=None, test_labels=None):
    """在 train tokens 上训练，在独立 test tokens 上评估。

    默认 test_tokens=None 时退化为在同一批数据上评估（仅兼容旧调用）；
    demo 与测试都显式传独立 test 集，避免 train/test 泄漏。
    """
    eval_tokens = tokens if test_tokens is None else test_tokens
    eval_labels = labels if test_labels is None else test_labels
    torch.manual_seed(0)
    V = len(tok.itos)
    model = TorchBERT(V, context=context)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    lossf = nn.CrossEntropyLoss()
    rng = np.random.default_rng(0)
    t0 = time.perf_counter()
    for _ in range(epochs):
        inp = tokens.copy()
        target = tokens.copy()
        mask_pos = np.zeros_like(tokens, dtype=bool)
        for n in range(len(tokens)):
            eligible = np.flatnonzero((tokens[n] != PAD) & (tokens[n] != CLS) &
                                      (tokens[n] != SEP))
            if len(eligible) == 0:
                continue
            k = max(1, int(round(len(eligible) * 0.15)))
            chosen = rng.choice(eligible, size=k, replace=False)
            mask_pos[n, chosen] = True
            for j in chosen:
                r = rng.random()
                if r < 0.8:
                    inp[n, j] = MASK
                elif r < 0.9:
                    inp[n, j] = int(rng.integers(5, V))
        logits, _ = model(torch.as_tensor(inp))
        loss = lossf(logits[mask_pos], torch.as_tensor(target)[mask_pos])
        opt.zero_grad()
        loss.backward()
        opt.step()
    t = time.perf_counter() - t0
    eval_inp, eval_target, eval_mask = _eval_mask(eval_tokens, seed=123, vocab_size=V)
    with torch.no_grad():
        logits, _ = model(torch.as_tensor(eval_inp))
        pred = logits.argmax(-1).numpy()
        eval_loss = float(lossf(logits[eval_mask],
                                torch.as_tensor(eval_target)[eval_mask]))
        acc = float((pred[eval_mask] == eval_target[eval_mask]).mean())
        _, train_hidden = model(torch.as_tensor(tokens))
        _, test_hidden = model(torch.as_tensor(eval_tokens))
    clf = LogisticRegression(max_iter=2000)
    clf.fit(train_hidden[:, 0].numpy(), labels)
    probe = clf.score(test_hidden[:, 0].numpy(), eval_labels)
    return {"loss": eval_loss, "acc": acc, "probe": float(probe), "time_sec": t}


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 调用")
