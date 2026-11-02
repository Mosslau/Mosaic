"""CLIP 式多模态 — demo：图文对比学习与检索"""

from __future__ import annotations

import time

import numpy as np
from baseline import random_retrieval, ridge_retrieval
from impl import CLIP, make_pairs
from sklearn.model_selection import train_test_split


def main() -> None:
    Xi, Xt, y = make_pairs(20, 12, 200, 0)
    idx = np.arange(len(y))
    tr, te = train_test_split(idx, test_size=0.3, random_state=0, stratify=y)
    t0 = time.perf_counter()
    m = CLIP(d=16, lr=0.2, epochs=300, tau=0.2, seed=0).fit(Xi[tr], Xt[tr])
    dt = time.perf_counter() - t0
    train_acc = m.retrieval_accuracy(Xi[tr], Xt[tr], y[tr])
    test_acc = m.retrieval_accuracy(Xi[te], Xt[te], y[te])
    ident = m.retrieval_accuracy(Xi[te], Xt[te])
    print(f"图文对 {len(Xi)}（train/test={len(tr)}/{len(te)}），"
          f"图像维 {Xi.shape[1]}，文本维 {Xt.shape[1]}，嵌入 16")
    print(f"loss {m.loss_history[0]:.3f} → {m.loss_history[-1]:.3f}；{dt:.2f}s")
    print(f"类别检索 acc：train {train_acc:.3f} / test {test_acc:.3f}")
    print(f"identity acc（test，唯一 token 未见过）{ident:.3f}")
    print(f"岭回归基线 class acc {ridge_retrieval(Xi[tr], Xt[tr], Xi[te], Xt[te], y[te]):.3f}")
    print(f"随机双塔基线 class acc {random_retrieval(Xi[te], Xt[te], y[te]):.3f}")
    S = m.similarity(Xi[te][:5], Xt[te][:5])
    print("前 5 对相似度对角线：", np.round(np.diag(S), 2).tolist())
    assert test_acc >= 0.8


if __name__ == "__main__":
    main()
