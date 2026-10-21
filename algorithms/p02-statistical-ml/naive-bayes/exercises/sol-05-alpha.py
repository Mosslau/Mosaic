"""参考解：第 5 题（迁移）——alpha 与 top 词

    uv run python sol-05-alpha.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import KFold, train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo as D  # noqa: E402
from impl import CountVectorizer, MultinomialNB  # noqa: E402


def acc(y, p):
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def main() -> None:
    docs, labels = D.make_corpus(n_per_class=150, noise=0.15, seed=0)
    dtr, dte, ytr, yte = train_test_split(docs, labels, test_size=0.3,
                                          random_state=0, stratify=labels)
    vec = CountVectorizer().fit(dtr)
    Xtr, Xte = vec.transform(dtr), vec.transform(dte)

    best = None
    for alpha in (0.01, 0.1, 1.0, 10.0):
        scores = []
        for tr, va in KFold(5, shuffle=True, random_state=0).split(Xtr):
            nb = MultinomialNB(alpha).fit(Xtr[tr], ytr[tr])
            scores.append(acc(ytr[va], nb.predict(Xtr[va])))
        cv = float(np.mean(scores))
        print(f"alpha={alpha:5.2f}  CV={cv:.4f}")
        if best is None or cv > best[1]:
            best = (alpha, cv)

    nb = MultinomialNB(best[0]).fit(Xtr, ytr)
    print(f"\n选中 alpha={best[0]}，测试 {acc(yte, nb.predict(Xte)):.4f}")
    is_ = int(np.where(nb.classes_ == "spam")[0][0])
    ih = int(np.where(nb.classes_ == "ham")[0][0])
    diff = nb.feature_log_prob_[is_] - nb.feature_log_prob_[ih]
    inv = {i: w for w, i in vec.vocabulary_.items()}
    top = [inv[i] for i in np.argsort(-diff)[:5]]
    print("top spam 词：" + "、".join(top))
    assert acc(yte, nb.predict(Xte)) >= 0.9
    assert sum(w in D.SPAM for w in top) >= 3
    print("\n→ alpha 不敏感；后验可以解释到具体词。")


if __name__ == "__main__":
    main()
