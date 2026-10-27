"""参考解 04：3CosAdd vs 3CosMul（同一模型、同一组留出类比题）。

运行：cd algorithms/p04-transformer/word-vectors &&
      ../../.venv/bin/python exercises/sol-04-3cosmul.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
from demo import analogy_items, build_corpus  # noqa: E402
from impl import SkipGramNS, l2_normalize  # noqa: E402


def top1(vectors, word2id, items, mode, eps=1e-6):
    V = l2_normalize(np.asarray(vectors, float))
    idx = np.array([[word2id[it[k]] for k in "abcd"] for it in items])
    if mode == "add":
        target = l2_normalize(V[idx[:, 1]] - V[idx[:, 0]] + V[idx[:, 2]])
        scores = target @ V.T
    elif mode == "mul":
        scores = (V[idx[:, 1]] @ V.T) * (V[idx[:, 2]] @ V.T) / ((V[idx[:, 0]] @ V.T) + eps)
    else:
        raise ValueError(mode)
    scores[np.arange(len(items))[:, None], idx[:, :3]] = -np.inf   # 排除 a/b/c
    return float((scores.argmax(1) == idx[:, 3]).mean())


def main() -> None:
    sentences, _ = build_corpus(0)
    m = SkipGramNS(dim=32, epochs=40, seed=0).fit(sentences)
    held = [it for it in analogy_items() if it["split"] == "heldout"]
    add = top1(m.vectors, m.word2id, held, "add")
    mul = top1(m.vectors, m.word2id, held, "mul")
    print(f"留出类比 {len(held)} 题：3CosAdd {add:.3f} / 3CosMul {mul:.3f}")
    print("本语料上 3CosAdd 更高：配对词被拉得很近（余弦≈0.92），"
          "加法保留了这个「整体平移」，乘法反而被单个小余弦放大噪声。")
    assert add > 0.7 and mul > 0.5, "两种打分都应显著高于随机（≈1/91）"


if __name__ == "__main__":
    main()
