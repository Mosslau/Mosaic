"""参考解：第 3 题（判断）——三个 NB bug 的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import MultinomialNB  # noqa: E402


def main() -> None:
    X = np.array([[2.0, 0.0], [0.0, 2.0]])
    y = np.array(["A", "B"])

    print("A alpha=0：")
    nb0 = MultinomialNB(0.0).fit(X, y)
    nb1 = MultinomialNB(1.0).fit(X, y)
    print(f"   alpha=0: log P(bad|A) = {nb0.feature_log_prob_[0, 1]:.4f}")
    print(f"   alpha=1: log P(bad|A) = {nb1.feature_log_prob_[0, 1]:.4f}")
    assert np.isneginf(nb0.feature_log_prob_[0, 1])

    print("\nB 先验按总词数：")
    # A 类 2 条长文档（各 50 词），B 类 8 条短文档（各 3 词）
    labels = np.array(["A"] * 2 + ["B"] * 8)
    counts = np.array([[50.0, 0.0]] * 2 + [[0.0, 3.0]] * 8)
    nb = MultinomialNB(1.0).fit(counts, labels)
    token_prior_A = counts[labels == "A"].sum() / counts.sum()
    print(f"   文档先验 P(A) = 2/10 = 0.200；词数先验 = {token_prior_A:.3f}")
    assert nb.class_log_prior_[0] == np.log(0.2)
    assert token_prior_A > 0.7

    print("\nC 直接连乘：")
    probs = np.full(500, 0.01)
    product = float(np.prod(probs))
    logsum = float(np.sum(np.log(probs)))
    print(f"   连乘 500 个 0.01 = {product:.3e}；log 和 = {logsum:.2f}")
    assert product == 0.0 and np.isfinite(logsum)
    print("\n→ A 零概率；B 先验口径错；C 下溢为 0。")


if __name__ == "__main__":
    main()
