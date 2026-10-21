"""迁移项目：文本垃圾短信分类 —— 词袋 + 多项式 NB

    uv run python spam.py

语料为合成的 SMS 风格文本（每类 200 条、30 词词表、20% 噪声词），
重点不在数据规模，而在完整走通：
文本 → 词袋 → 多项式 NB → 用 CV 选 alpha → 测试 → 解释 top 词。
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import KFold, train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import demo as D  # noqa: E402
import framework  # noqa: E402
from impl import CountVectorizer, MultinomialNB  # noqa: E402

ALPHAS = (0.01, 0.1, 0.5, 1.0, 5.0, 10.0)


def accuracy(y, p) -> float:
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def cv_accuracy(alpha, X, y, folds=5) -> float:
    scores = []
    for tr, va in KFold(n_splits=folds, shuffle=True, random_state=0).split(X):
        nb = MultinomialNB(alpha=alpha).fit(X[tr], y[tr])
        scores.append(accuracy(y[va], nb.predict(X[va])))
    return float(np.mean(scores))


def main() -> None:
    docs, labels = D.make_corpus(n_per_class=200, noise=0.5, seed=0, p_class=0.5)
    docs_tr, docs_te, y_tr, y_te = train_test_split(docs, labels, test_size=0.3,
                                                    random_state=0, stratify=labels)
    vec = CountVectorizer().fit(docs_tr)
    X_tr, X_te = vec.transform(docs_tr), vec.transform(docs_te)
    print(f"语料 {len(docs)} 条（训练 {len(y_tr)} / 测试 {len(y_te)}）；"
          f"词表 {len(vec.vocabulary_)} 个词")

    print("\nalpha 的 5 折 CV：")
    print(f"{'alpha':>6} | {'CV acc':>7}")
    print("-" * 18)
    rows = []
    for a in ALPHAS:
        cv = cv_accuracy(a, X_tr, y_tr)
        rows.append({"alpha": a, "cv": cv})
        print(f"{a:6.2f} | {cv:7.4f}")
    best = max(rows, key=lambda r: r["cv"])

    nb = MultinomialNB(best["alpha"]).fit(X_tr, y_tr)
    acc = accuracy(y_te, nb.predict(X_te))
    sk = framework.fit_multinomial(X_tr, y_tr, alpha=best["alpha"])
    sk_acc = accuracy(y_te, sk.predict(X_te))

    # top 词：log P(w|spam) − log P(w|ham)
    i_spam = int(np.where(nb.classes_ == "spam")[0][0])
    i_ham = int(np.where(nb.classes_ == "ham")[0][0])
    diff = nb.feature_log_prob_[i_spam] - nb.feature_log_prob_[i_ham]
    order = np.argsort(-diff)[:5]
    inv = {i: w for w, i in vec.vocabulary_.items()}
    top = [(inv[i], float(diff[i])) for i in order]
    print(f"\n选中 alpha={best['alpha']}（CV {best['cv']:.4f}）")
    print(f"测试准确率：手写 {acc:.4f}；sklearn {sk_acc:.4f}")
    print("最像 spam 的词：" + "、".join(f"{w}({v:+.2f})" for w, v in top))

    print("\n== 验收 ==")
    checks = [
        ("测试准确率 ≥ 0.92", acc >= 0.92),
        ("5 折 CV ≥ 0.92", best["cv"] >= 0.92),
        ("选中的 alpha > 0", best["alpha"] > 0),
        ("手写与 sklearn 测试差 ≤ 1 个百分点", abs(acc - sk_acc) <= 0.01),
        ("词表 ≥ 20 个词", len(vec.vocabulary_) >= 20),
        ("top 词里有已知 spam 词", any(w in D.SPAM for w, _ in top)),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"
    print(f"\n→ 文本 → 词袋 → NB：{len(vec.vocabulary_)} 维、alpha={best['alpha']}、"
          f"测试 {acc:.3f}；概率可解释到词。")


if __name__ == "__main__":
    main()
