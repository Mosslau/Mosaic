"""随机森林 — demo：同数据双跑 + 五组实验

    uv run python demo.py

    实验一  单棵树 vs 森林（手写 vs sklearn）
    实验二  树数扫描：测试准确率与 OOB
    实验三  max_features 扫描（高维数据）
    实验四  特征重要性：真特征 vs 噪声特征
    实验五  稳定性：单树 vs 森林的跨种子方差
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import RandomForest
from sklearn.datasets import make_classification, make_moons
from sklearn.model_selection import train_test_split

SEED = 0
REPEATS = 3


def make_moons_data(n: int = 300, noise: float = 0.25):
    X, y = make_moons(n_samples=n, noise=noise, random_state=SEED)
    return train_test_split(X, y, test_size=0.3, random_state=SEED, stratify=y)


def make_high_dim(n: int = 400, p: int = 12, informative: int = 4):
    X, y = make_classification(n_samples=n, n_features=p, n_informative=informative,
                               n_redundant=0, n_repeated=0, class_sep=1.0,
                               flip_y=0.05, shuffle=False, random_state=SEED)
    return train_test_split(X, y, test_size=0.3, random_state=SEED, stratify=y)


def accuracy(y_true, y_pred) -> float:
    return float(np.mean(np.asarray(y_true) == np.asarray(y_pred)))


def _median_time(fn, repeats: int = REPEATS):
    times = []
    result = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return result, statistics.median(times)


# ---------------------------------------------------------------- 实验一

def experiment_main() -> None:
    X_tr, X_te, y_tr, y_te = make_moons_data()
    print("== 实验一：单棵树 vs 森林（moons，n_trees=100） ==")
    print(f"{'方法':26} | {'训练 acc':>8} | {'测试 acc':>8} | {'OOB':>7} | {'耗时(ms)':>8}")
    print("-" * 72)
    single = RandomForest(n_trees=1, max_features=None, random_state=SEED).fit(X_tr, y_tr)
    forest, t_forest = _median_time(
        lambda: RandomForest(n_trees=100, max_features="sqrt", random_state=SEED).fit(X_tr, y_tr))
    sk, t_sk = _median_time(lambda: framework.fit_forest(X_tr, y_tr, n_trees=100))

    for name, model, t in (("手写 单树（n_trees=1）", single, 0.0),
                           ("手写 森林（100 棵）", forest, t_forest),
                           ("sklearn 森林（100 棵）", sk, t_sk)):
        oob = model.oob_score_ if hasattr(model, "oob_score_") else model.oob_score(X_tr, y_tr)
        t_str = "—" if t == 0.0 else f"{t * 1000:.2f}"
        print(f"{name:26} | {accuracy(y_tr, model.predict(X_tr)):8.4f} | "
              f"{accuracy(y_te, model.predict(X_te)):8.4f} | {oob:7.4f} | {t_str:>8}")

    assert accuracy(y_te, forest.predict(X_te)) >= accuracy(y_te, single.predict(X_te)) - 0.01
    assert abs(accuracy(y_te, forest.predict(X_te)) - accuracy(y_te, sk.predict(X_te))) < 0.05
    print("\n→ 森林把单树的测试准确率拉高，OOB 与测试同量级；sklearn 主要快在 C 实现。\n")


# ---------------------------------------------------------------- 实验二

def experiment_n_trees() -> list:
    X_tr, X_te, y_tr, y_te = make_moons_data()
    print("== 实验二：树数扫描（moons） ==")
    print(f"{'n_trees':>7} | {'训练 acc':>8} | {'测试 acc':>8} | {'OOB':>7}")
    print("-" * 38)
    rows = []
    for n in (1, 5, 10, 25, 50, 100, 200):
        model = RandomForest(n_trees=n, random_state=SEED).fit(X_tr, y_tr)
        rows.append({"n": n, "train": accuracy(y_tr, model.predict(X_tr)),
                     "test": accuracy(y_te, model.predict(X_te)),
                     "oob": float(model.oob_score_)})
        print(f"{n:7d} | {rows[-1]['train']:8.4f} | {rows[-1]['test']:8.4f} | "
              f"{rows[-1]['oob']:7.4f}")

    assert rows[-1]["oob"] > rows[0]["oob"], "树数增加后 OOB 应改善"
    print("\n→ 树越多越稳；OOB 不用验证集就能估泛化，且随树数收敛。\n")
    return rows


# ---------------------------------------------------------------- 实验三

def experiment_max_features() -> list:
    X_tr, X_te, y_tr, y_te = make_high_dim()
    print("== 实验三：max_features 扫描（p=12，4 个真特征） ==")
    print(f"{'max_features':>14} | {'测试 acc':>8} | {'OOB':>7}")
    print("-" * 34)
    rows = []
    for mf in (1, "sqrt", "log2", 6, None):
        model = RandomForest(n_trees=100, max_features=mf, random_state=SEED).fit(X_tr, y_tr)
        rows.append({"mf": str(mf), "test": accuracy(y_te, model.predict(X_te)),
                     "oob": float(model.oob_score_)})
        print(f"{str(mf):>14} | {rows[-1]['test']:8.4f} | {rows[-1]['oob']:7.4f}")

    assert max(r["test"] for r in rows) - min(r["test"] for r in rows) < 0.15, \
        "max_features 的影响应在合理范围内"
    print("\n→ sqrt/log2 是常用默认：既保留随机性，又不至于每刀只看一个特征。\n")
    return rows


# ---------------------------------------------------------------- 实验四

def experiment_importance() -> None:
    X_tr, X_te, y_tr, y_te = make_high_dim()
    model = RandomForest(n_trees=100, random_state=SEED).fit(X_tr, y_tr)
    sk = framework.fit_forest(X_tr, y_tr)
    imp = model.feature_importances_
    order = np.argsort(-imp)
    print("== 实验四：特征重要性（前 6） ==")
    print(f"{'rank':>4} | {'特征':>4} | {'手写':>7} | {'sklearn':>7}")
    print("-" * 30)
    for rank, j in enumerate(order[:6], 1):
        print(f"{rank:4d} | x{j:<3} | {imp[j]:7.4f} | {sk.feature_importances_[j]:7.4f}")
    assert np.isclose(imp.sum(), 1.0)
    assert set(order[:4].tolist()) == {0, 1, 2, 3}, "top-4 应正好是真特征（x0–x3）"
    print("\n→ 森林把重要性摊到多棵树：真特征高、噪声低；sklearn 的排序与手写一致。\n")


# ---------------------------------------------------------------- 实验五

def experiment_stability() -> None:
    X_tr, X_te, y_tr, y_te = make_moons_data()
    print("== 实验五：稳定性（10 个随机种子） ==")
    single_acc, forest_acc = [], []
    for seed in range(10):
        single = RandomForest(n_trees=1, max_features=None, random_state=seed).fit(X_tr, y_tr)
        forest = RandomForest(n_trees=100, random_state=seed).fit(X_tr, y_tr)
        single_acc.append(accuracy(y_te, single.predict(X_te)))
        forest_acc.append(accuracy(y_te, forest.predict(X_te)))

    print(f"  单树：均值 {np.mean(single_acc):.4f}，标准差 {np.std(single_acc):.4f}")
    print(f"  森林：均值 {np.mean(forest_acc):.4f}，标准差 {np.std(forest_acc):.4f}")
    assert np.std(forest_acc) < np.std(single_acc), "森林的跨种子方差应小于单树"
    assert np.mean(forest_acc) > np.mean(single_acc), "森林平均准确率应更高"
    print("\n→ bagging 平均掉单树的方差：均值更高、波动更小。\n")


def main() -> None:
    experiment_main()
    experiment_n_trees()
    experiment_max_features()
    experiment_importance()
    experiment_stability()


if __name__ == "__main__":
    main()
