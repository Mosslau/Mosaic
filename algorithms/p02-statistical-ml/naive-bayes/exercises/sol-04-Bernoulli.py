"""参考解：第 4 题（实现）——Bernoulli NB

    uv run python sol-04-Bernoulli.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import CountVectorizer, MultinomialNB  # noqa: E402


class BernoulliNB:
    def __init__(self, alpha=1.0):
        self.alpha = alpha

    def fit(self, X, y):
        Xb = (np.asarray(X) > 0).astype(float)
        self.classes_, yi = np.unique(y, return_inverse=True)
        k = len(self.classes_)
        n_c = np.bincount(yi, minlength=k).astype(float)
        occ = np.zeros((k, Xb.shape[1]))
        for c in range(k):
            occ[c] = Xb[yi == c].sum(axis=0)
        self.log_p = np.log((occ + self.alpha) / (n_c[:, None] + 2 * self.alpha))
        self.log_1p = np.log(1 - np.exp(self.log_p))
        self.log_prior = np.log(n_c / len(X))
        return self

    def predict(self, X):
        Xb = (np.asarray(X) > 0).astype(float)
        jll = (Xb @ self.log_p.T + (1 - Xb) @ self.log_1p.T + self.log_prior)
        return self.classes_[np.argmax(jll, axis=1)]


def acc(y, p):
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def main() -> None:
    docs, labels = D.make_corpus(n_per_class=150, noise=0.15, seed=0)
    dtr, dte, ytr, yte = train_test_split(docs, labels, test_size=0.3,
                                          random_state=0, stratify=labels)
    vec = CountVectorizer().fit(dtr)
    Xtr, Xte = vec.transform(dtr), vec.transform(dte)
    mult = MultinomialNB(1.0).fit(Xtr, ytr)
    bern = BernoulliNB(1.0).fit(Xtr, ytr)
    print(f"Multinomial 测试：{acc(yte, mult.predict(Xte)):.4f}")
    print(f"Bernoulli   测试：{acc(yte, bern.predict(Xte)):.4f}")
    assert acc(yte, bern.predict(Xte)) >= 0.9
    print("\n→ Bernoulli 只看词是否出现，短文本上同样强；Multinomial 还利用词频。")


if __name__ == "__main__":
    main()
