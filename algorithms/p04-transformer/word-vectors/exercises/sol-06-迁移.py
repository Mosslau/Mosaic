"""参考解 06：用词向量做 8 类关系词的 5 近邻分类（留一法）。

运行：cd algorithms/p04-transformer/word-vectors && ../../.venv/bin/python exercises/sol-06-迁移.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
from demo import GROUP_OF, PARTNER_OF, build_corpus  # noqa: E402
from impl import SkipGramNS, l2_normalize  # noqa: E402


def leave_one_out(sims, labels, words, k=5, drop_partner=False):
    """留一法 kNN：每个词用其余词投票，返回准确率（sims 是词向量子矩阵的余弦矩阵）。"""
    correct = 0
    for i, w in enumerate(words):
        cand = [j for j in range(len(words)) if j != i
                and not (drop_partner and words[j] == PARTNER_OF[w])]
        top = np.array(cand)[np.argsort(-sims[i, cand])[:k]]
        votes = [labels[j] for j in top]
        correct += int(max(set(votes), key=votes.count) == labels[i])
    return correct / len(words)


def main() -> None:
    sentences, _ = build_corpus(0)
    m = SkipGramNS(dim=32, epochs=40, seed=0).fit(sentences)
    words = [w for w in m.vocab if w in GROUP_OF]
    labels = [GROUP_OF[w] for w in words]
    V = l2_normalize(m.vectors[[m.word2id[w] for w in words]])
    sims = V @ V.T
    for drop in (False, True):
        acc = leave_one_out(sims, labels, words, k=5, drop_partner=drop)
        print(f"{'排除' if drop else '包含'}配对词：5-NN 留一准确率 {acc:.3f}"
              f"（{len(words)} 词 / {len(set(labels))} 类）")
    acc = leave_one_out(sims, labels, words, k=5, drop_partner=True)
    print("\n包含配对词时准确率反而更低：配对词是训练时的正样本、最近邻几乎总是它，"
          "而它属于**另一类**，投票会把人带偏——所以做类别纯度/分类时必须先排除配对词。")
    assert len(words) == 56 and len(set(labels)) == 8
    assert acc > 0.8, "迁移分类准确率过低"


if __name__ == "__main__":
    main()
