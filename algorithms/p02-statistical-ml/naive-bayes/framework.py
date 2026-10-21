"""朴素贝叶斯 — 框架对照（监督估计器）

对照对象：sklearn `MultinomialNB`（文本/计数）与 `GaussianNB`（连续）。
口径：同一份数据、同一 `alpha`，比较准确率、概率与耗时。
sklearn 额外做了稀疏矩阵支持、`partial_fit` 在线更新与更细的数值处理。
"""

from __future__ import annotations

from sklearn.naive_bayes import GaussianNB, MultinomialNB


def fit_multinomial(X, y, alpha: float = 1.0) -> MultinomialNB:
    return MultinomialNB(alpha=alpha).fit(X, y)


def fit_gaussian(X, y) -> GaussianNB:
    return GaussianNB().fit(X, y)


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
