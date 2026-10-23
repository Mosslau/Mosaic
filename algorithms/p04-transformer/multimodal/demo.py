"""CLIP 式多模态 — demo：图文对比学习与检索"""

from __future__ import annotations

import time

import numpy as np
from impl import CLIP, make_pairs


def main() -> None:
    Xi, Xt, y = make_pairs(20, 12, 200, 0)
    t0 = time.perf_counter()
    m = CLIP(d=16, lr=0.2, epochs=300, tau=0.2, seed=0).fit(Xi, Xt)
    dt = time.perf_counter() - t0
    print(f"图文对 {len(Xi)}，图像维 {Xi.shape[1]}，文本维 {Xt.shape[1]}，嵌入 16")
    print(f"loss {m.loss_history[0]:.3f} → {m.loss_history[-1]:.3f}；{dt:.2f}s")
    print(f"图像→文本 identity acc {m.retrieval_accuracy(Xi, Xt):.3f}")
    print(f"类别检索 acc {m.retrieval_accuracy(Xi, Xt, y):.3f}")
    S = m.similarity(Xi[:5], Xt[:5])
    print("前 5 对相似度对角线：", np.round(np.diag(S), 2).tolist())
    assert m.retrieval_accuracy(Xi, Xt, y) >= 0.9


if __name__ == "__main__":
    main()
