"""参考解：第 4 题（实现）——Mahalanobis 检测器

    uv run python sol-04-Mahalanobis.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import IsolationForest  # noqa: E402


class Mahalanobis:
    def __init__(self, contamination=0.05):
        self.contamination = contamination

    def fit(self, X):
        self.mu = X.mean(axis=0)
        cov = np.cov(X, rowvar=False)
        self.inv = np.linalg.inv(cov + 1e-9 * np.eye(cov.shape[0]))
        s = self.score_samples(X)
        self.threshold_ = float(np.quantile(s, 1 - self.contamination))
        return self

    def score_samples(self, X):
        d = X - self.mu
        return np.sqrt(np.einsum("ij,jk,ik->i", d, self.inv, d))


def main() -> None:
    X_tr, X_te, y = D.make_data()
    mah = Mahalanobis().fit(X_tr)
    iforest = IsolationForest(random_state=0).fit(X_tr)
    a1 = roc_auc_score(y, mah.score_samples(X_te))
    a2 = roc_auc_score(y, iforest.score_samples(X_te))
    print(f"Mahalanobis AUC：{a1:.3f}")
    print(f"IsolationForest AUC：{a2:.3f}")
    assert a1 > 0.9
    print("\n→ 单峰高斯上两者都强；多峰/局部异常时 Mahalanobis 会输给 IF/LOF。")


if __name__ == "__main__":
    main()
