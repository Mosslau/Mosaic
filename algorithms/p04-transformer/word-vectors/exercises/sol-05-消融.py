"""参考解 05：负采样个数 × 向量来源 的消融表。

运行：cd algorithms/p04-transformer/word-vectors && ../../.venv/bin/python exercises/sol-05-消融.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402

from demo import analogy_items, build_corpus  # noqa: E402
from impl import SkipGramNS, l2_normalize  # noqa: E402


def top1(vectors, word2id, items):
    V = l2_normalize(np.asarray(vectors, float))
    idx = np.array([[word2id[it[k]] for k in "abcd"] for it in items])
    target = l2_normalize(V[idx[:, 1]] - V[idx[:, 0]] + V[idx[:, 2]])
    scores = target @ V.T
    scores[np.arange(len(items))[:, None], idx[:, :3]] = -np.inf
    return float((scores.argmax(1) == idx[:, 3]).mean())


def main() -> None:
    sentences, _ = build_corpus(0)
    held = [it for it in analogy_items() if it["split"] == "heldout"]
    rows = []
    print("negative | W_in  | W_out | W_in+W_out | 训练耗时")
    for neg in (0, 1, 5, 15):
        t0 = time.perf_counter()
        m = SkipGramNS(dim=32, epochs=40, negative=neg, seed=0).fit(sentences)
        dt = time.perf_counter() - t0
        sources = {"W_in": m.W_in, "W_out": m.W_out, "W_in+W_out": m.W_in + m.W_out}
        acc = {k: top1(v, m.word2id, held) for k, v in sources.items()}
        rows.append((neg, acc))
        print(f" {neg:7d} | {acc['W_in']:.3f} | {acc['W_out']:.3f} | "
              f"{acc['W_in+W_out']:.3f}      | {dt:.1f}s")
    best = [a["W_in+W_out"] for n, a in rows if n == 5][0]
    assert abs(best - 0.833) < 0.03, f"negative=5 + W_in+W_out 应与 demo 的 0.833 一致，实际 {best:.3f}"
    spread_source = max(a["W_in+W_out"] - a["W_in"] for _, a in rows)
    spread_neg = max(a["W_in+W_out"] for _, a in rows) - min(a["W_in+W_out"] for _, a in rows)
    print(f"\n向量来源造成的最大差 {spread_source:.3f}；负采样个数造成的最大差 {spread_neg:.3f}")
    print("→ 取哪个矩阵当词向量，比调 negative 影响更大。")


if __name__ == "__main__":
    main()
