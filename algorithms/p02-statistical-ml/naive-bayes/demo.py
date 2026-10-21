"""朴素贝叶斯 — demo：同数据双跑 + 四组实验

    uv run python demo.py

    实验一  高斯 NB（二维 blobs） vs sklearn
    实验二  文本分类：词袋 + 多项式 NB，alpha 扫描
    实验三  拉普拉斯平滑：alpha=0 的零概率问题
    实验四  条件独立被违反：重复特征让后验过度自信
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import CountVectorizer, GaussianNB, MultinomialNB
from sklearn.datasets import make_blobs
from sklearn.model_selection import train_test_split

SEED = 0
REPEATS = 3


def make_blobs_data(n: int = 300, seed: int = SEED):
    X, y = make_blobs(n_samples=n, centers=2, cluster_std=1.2, random_state=seed)
    return train_test_split(X, y, test_size=0.3, random_state=SEED, stratify=y)


SPAM = ["free", "win", "prize", "click", "offer", "cash", "urgent", "claim",
        "deal", "reward"]
HAM = ["meeting", "project", "report", "schedule", "team", "lunch", "review",
       "deadline", "budget", "update"]
SHARED = ["please", "today", "tomorrow", "the", "a", "to", "your", "our", "is", "for"]


def make_corpus(n_per_class: int = 150, noise: float = 0.15, seed: int = 0,
                p_class: float = 0.65):
    rng = np.random.default_rng(seed)
    docs, labels = [], []
    for label, words, other in (("spam", SPAM, HAM), ("ham", HAM, SPAM)):
        for _ in range(n_per_class):
            length = int(rng.integers(4, 11))
            toks = [str(rng.choice(words)) if rng.random() < p_class else str(rng.choice(SHARED))
                    for _ in range(length)]
            if rng.random() < noise:
                toks.append(str(rng.choice(other)))
            docs.append(" ".join(toks))
            labels.append(label)
    return docs, np.array(labels)


def accuracy(y, p) -> float:
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def _median_time(fn, repeats: int = REPEATS):
    times = []
    result = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return result, statistics.median(times)


# ---------------------------------------------------------------- 实验一

def experiment_gaussian() -> None:
    X_tr, X_te, y_tr, y_te = make_blobs_data()
    print("== 实验一：高斯 NB（二维 blobs） ==")
    print(f"{'方法':12} | {'训练 acc':>8} | {'测试 acc':>8} | "
          f"{'平均最大后验':>12} | {'耗时(ms)':>8}")
    print("-" * 66)
    hand, t_hand = _median_time(lambda: GaussianNB().fit(X_tr, y_tr))
    sk, t_sk = _median_time(lambda: framework.fit_gaussian(X_tr, y_tr))
    for name, model, t in (("手写", hand, t_hand), ("sklearn", sk, t_sk)):
        proba = model.predict_proba(X_te)
        print(f"{name:12} | {accuracy(y_tr, model.predict(X_tr)):8.4f} | "
              f"{accuracy(y_te, model.predict(X_te)):8.4f} | "
              f"{float(np.mean(proba.max(axis=1))):12.4f} | {t * 1000:8.3f}")
    assert abs(accuracy(y_te, hand.predict(X_te)) - accuracy(y_te, sk.predict(X_te))) < 0.02
    print("\n→ 同参数下准确率/概率与 sklearn 一致；NB 的决策边界是二次曲线。\n")


# ---------------------------------------------------------------- 实验二

def experiment_text() -> list:
    docs, labels = make_corpus()
    docs_tr, docs_te, y_tr, y_te = train_test_split(docs, labels, test_size=0.3,
                                                    random_state=SEED, stratify=labels)
    vec = CountVectorizer().fit(docs_tr)
    X_tr, X_te = vec.transform(docs_tr), vec.transform(docs_te)
    print("== 实验二：文本分类（词袋 + 多项式 NB） ==")
    print(f"词表 {len(vec.vocabulary_)} 个词；训练 {len(y_tr)} / 测试 {len(y_te)}")
    print(f"{'alpha':>7} | {'训练 acc':>8} | {'测试 acc':>8}")
    print("-" * 30)
    rows = []
    for alpha in (0.01, 0.1, 1.0, 10.0):
        nb = MultinomialNB(alpha=alpha).fit(X_tr, y_tr)
        rows.append({"alpha": alpha, "train": accuracy(y_tr, nb.predict(X_tr)),
                     "test": accuracy(y_te, nb.predict(X_te))})
        print(f"{alpha:7.2f} | {rows[-1]['train']:8.4f} | {rows[-1]['test']:8.4f}")

    sk = framework.fit_multinomial(X_tr, y_tr, alpha=1.0)
    hand = MultinomialNB(alpha=1.0).fit(X_tr, y_tr)
    print(f"\nalpha=1：手写测试 {accuracy(y_te, hand.predict(X_te)):.4f}；"
          f"sklearn 测试 {accuracy(y_te, sk.predict(X_te)):.4f}")
    assert abs(accuracy(y_te, hand.predict(X_te)) - accuracy(y_te, sk.predict(X_te))) < 0.02
    assert max(r["test"] for r in rows) > 0.9
    print("\n→ 文本被词袋 + 条件独立假设压缩成计数矩阵；alpha 在 0.1–1 附近较稳。\n")
    return rows


# ---------------------------------------------------------------- 实验三

def experiment_smoothing() -> None:
    docs = ["good good", "good", "bad bad", "bad", "good"]
    labels = np.array(["A", "A", "B", "B", "A"])
    vec = CountVectorizer().fit(docs)
    X = vec.transform(docs)
    j_bad = vec.vocabulary_["bad"]
    print("== 实验三：拉普拉斯平滑（alpha=0 vs 1） ==")
    print(f"{'alpha':>6} | {'log P(bad|A)':>14} | {'log P(bad|B)':>14}")
    print("-" * 42)
    logs = {}
    for alpha in (0.0, 1.0):
        nb = MultinomialNB(alpha=alpha).fit(X, labels)
        a = float(nb.feature_log_prob_[0, j_bad])
        b = float(nb.feature_log_prob_[1, j_bad])
        logs[alpha] = (a, b)
        print(f"{alpha:6.1f} | {a:14.4f} | {b:14.4f}")
    assert np.isneginf(logs[0.0][0]), "alpha=0 时未见词的概率应为 0（log = −inf）"
    assert np.isfinite(logs[1.0][0]), "平滑后应为有限值"
    print("\n→ 不平滑时，任何'某类没见过的词'都会把整类后验打成 0；alpha 给所有词加一个底数。\n")


# ---------------------------------------------------------------- 实验四

def experiment_independence() -> None:
    X_tr, X_te, y_tr, y_te = make_blobs_data()
    base = GaussianNB().fit(X_tr, y_tr)
    X_dup_tr = np.hstack([X_tr] * 3)          # 把两个特征各复制 3 份
    X_dup_te = np.hstack([X_te] * 3)
    dup = GaussianNB().fit(X_dup_tr, y_tr)
    conf_base = float(np.mean(base.predict_proba(X_te).max(axis=1)))
    conf_dup = float(np.mean(dup.predict_proba(X_dup_te).max(axis=1)))
    acc_base = accuracy(y_te, base.predict(X_te))
    acc_dup = accuracy(y_te, dup.predict(X_dup_te))
    print("== 实验四：条件独立被违反（把特征复制 3 份） ==")
    print(f"  原始平均最大后验：{conf_base:.4f}（准确率 {acc_base:.4f}）")
    print(f"  复制 3 份后：     {conf_dup:.4f}（准确率 {acc_dup:.4f}）")
    assert conf_dup > conf_base, "重复特征会被 NB 当成两份独立证据，后验更极端"
    print("\n→ 特征相关时，NB 会把同一份证据数两遍：概率过度自信，但分类边界未必变差。\n")


def main() -> None:
    experiment_gaussian()
    experiment_text()
    experiment_smoothing()
    experiment_independence()


if __name__ == "__main__":
    main()
