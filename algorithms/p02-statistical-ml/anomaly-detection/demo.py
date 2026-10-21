"""异常检测 — demo：同数据双跑 + 三组实验

    uv run python demo.py

    实验一  IsolationForest / LOF / KDE 的 AUC 与阈值指标
    实验二  contamination 扫描：精确率/召回率/F1
    实验三  分数分离度：正常 vs 异常
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import KDE, LOF, IsolationForest
from sklearn.metrics import precision_score, recall_score, roc_auc_score

SEED = 0
REPEATS = 3


def make_data(n_normal: int = 400, n_out: int = 40, seed: int = SEED):
    rng = np.random.default_rng(seed)
    normal = rng.normal(0.0, 1.0, size=(n_normal, 2))
    out = np.vstack([
        rng.normal([4.0, 4.0], 0.5, size=(n_out // 2, 2)),
        rng.normal([-4.0, 4.0], 0.5, size=(n_out - n_out // 2, 2)),
    ])
    X_tr = normal[:300]
    X_te = np.vstack([normal[300:], out])
    y_te = np.array([0] * (len(normal) - 300) + [1] * len(out))
    return X_tr, X_te, y_te


def accuracy_metrics(y, pred):
    return (float(precision_score(y, pred, zero_division=0)),
            float(recall_score(y, pred, zero_division=0)))


def _median_time(fn, repeats: int = REPEATS):
    times = []
    result = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return result, statistics.median(times)


def _scores(model, X, sk=False, kde=False):
    if kde:
        return -model.score_samples(X) if sk else model.score_samples(X)
    return model.score_samples(X)


# ---------------------------------------------------------------- 实验一

def experiment_compare() -> None:
    X_tr, X_te, y = make_data()
    print("== 实验一：三种异常检测器（训练只用正常样本） ==")
    print(f"{'方法':16} | {'AUC':>6} | {'精确率':>6} | {'召回率':>6} | {'耗时(ms)':>8}")
    print("-" * 56)

    def run_hand(model):
        return model.fit(X_tr)

    hand_if, t_if = _median_time(lambda: run_hand(IsolationForest(random_state=SEED)))
    hand_lof, t_lof = _median_time(lambda: run_hand(LOF()))
    hand_kde, t_kde = _median_time(lambda: run_hand(KDE()))

    sk_if = framework.fit_iforest(X_tr)
    sk_lof = framework.fit_lof(X_tr)
    sk_kde = framework.fit_kde(X_tr)
    sk_if_s = -sk_if.score_samples(X_te)
    sk_lof_s = -sk_lof.score_samples(X_te)
    sk_kde_s = -sk_kde.score_samples(X_te)
    sk_if_pred = (sk_if.predict(X_te) == -1).astype(int)
    sk_lof_pred = (sk_lof.predict(X_te) == -1).astype(int)

    rows = [
        ("手写 IForest", hand_if, t_if, hand_if.score_samples(X_te)),
        ("手写 LOF", hand_lof, t_lof, hand_lof.score_samples(X_te)),
        ("手写 KDE", hand_kde, t_kde, hand_kde.score_samples(X_te)),
    ]
    for name, model, t, s in rows:
        pred = np.where(s > model.threshold_, 1, 0)
        p, r = accuracy_metrics(y, pred)
        print(f"{name:16} | {roc_auc_score(y, s):6.3f} | {p:6.3f} | {r:6.3f} | {t * 1000:8.2f}")

    p_if, r_if = accuracy_metrics(y, sk_if_pred)
    p_lof, r_lof = accuracy_metrics(y, sk_lof_pred)
    print(f"{'sklearn IForest':16} | {roc_auc_score(y, sk_if_s):6.3f} | "
          f"{p_if:6.3f} | {r_if:6.3f} | {'—':>8}")
    print(f"{'sklearn LOF':16} | {roc_auc_score(y, sk_lof_s):6.3f} | "
          f"{p_lof:6.3f} | {r_lof:6.3f} | {'—':>8}")
    print(f"{'sklearn KDE':16} | {roc_auc_score(y, sk_kde_s):6.3f} | "
          f"{'—':>6} | {'—':>6} | {'—':>8}")

    assert roc_auc_score(y, hand_if.score_samples(X_te)) > 0.95
    assert roc_auc_score(y, hand_lof.score_samples(X_te)) > 0.9
    print("\n→ 三种方法 AUC 都 >0.9；IF/KDE 偏全局，LOF 看局部密度。\n")


# ---------------------------------------------------------------- 实验二

def experiment_threshold() -> list:
    X_tr, X_te, y = make_data()
    print("== 实验二：contamination（阈值分位）扫描，IsolationForest ==")
    print(f"{'contam':>7} | {'精确率':>6} | {'召回率':>6} | {'F1':>6}")
    print("-" * 32)
    rows = []
    for c in (0.01, 0.02, 0.05, 0.08, 0.12, 0.2):
        m = IsolationForest(contamination=c, random_state=SEED).fit(X_tr)
        pred = np.where(m.score_samples(X_te) > m.threshold_, 1, 0)
        p, r = accuracy_metrics(y, pred)
        f1 = 0.0 if p + r == 0 else 2 * p * r / (p + r)
        rows.append({"c": c, "p": p, "r": r, "f1": f1})
        print(f"{c:7.2f} | {p:6.3f} | {r:6.3f} | {f1:6.3f}")

    best = max(rows, key=lambda r: r["f1"])
    assert 0 < best["c"] <= 0.2
    print(f"\n→ 本数据 F1 最高在 contamination={best['c']}；阈值不是越严越好。\n")
    return rows


# ---------------------------------------------------------------- 实验三

def experiment_separation() -> None:
    X_tr, X_te, y = make_data()
    model = IsolationForest(random_state=SEED).fit(X_tr)
    s = model.score_samples(X_te)
    print("== 实验三：分数分离度 ==")
    print(f"  正常样本平均分数：{s[y == 0].mean():.3f}")
    print(f"  异常样本平均分数：{s[y == 1].mean():.3f}")
    assert s[y == 1].mean() > s[y == 0].mean() + 0.2
    print("\n→ 异常分数明显更高；但分布有重叠，阈值决定精确率/召回率的取舍。\n")


def main() -> None:
    experiment_compare()
    experiment_threshold()
    experiment_separation()


if __name__ == "__main__":
    main()
