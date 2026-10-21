"""决策树 ID3/CART — demo：同数据双跑 + 五组实验

    uv run python demo.py

    实验一  手写 vs sklearn（gini, depth=4）
    实验二  gini vs entropy
    实验三  深度扫描：训练/测试准确率与叶子数
    实验四  代价复杂度剪枝（ccp_alpha）
    实验五  不稳定性：bootstrap 树的预测分歧
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import DecisionTree
from sklearn.datasets import make_moons
from sklearn.model_selection import train_test_split

SEED = 0
REPEATS = 5


def make_data(n: int = 300, noise: float = 0.25):
    X, y = make_moons(n_samples=n, noise=noise, random_state=SEED)
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
    X_tr, X_te, y_tr, y_te = make_data()
    print("== 实验一：手写 vs sklearn（gini，depth=4） ==")
    print(f"{'方法':16} | {'训练 acc':>8} | {'测试 acc':>8} | "
          f"{'叶子':>4} | {'深度':>4} | {'耗时(ms)':>8}")
    print("-" * 70)
    hand, t_hand = _median_time(lambda: DecisionTree(max_depth=4).fit(X_tr, y_tr))
    sk, t_sk = _median_time(lambda: framework.fit_tree(X_tr, y_tr, max_depth=4))

    for name, model, t in (("手写", hand, t_hand), ("sklearn", sk, t_sk)):
        print(f"{name:16} | {accuracy(y_tr, model.predict(X_tr)):8.4f} | "
              f"{accuracy(y_te, model.predict(X_te)):8.4f} | {model.get_n_leaves():4d} | "
              f"{model.get_depth():4d} | {t * 1000:8.3f}")

    agree = float(np.mean(hand.predict(X_te) == sk.predict(X_te)))
    print(f"\n测试集预测一致率：{agree:.4f}")
    assert abs(accuracy(y_te, hand.predict(X_te)) - accuracy(y_te, sk.predict(X_te))) < 0.03
    assert hand.get_n_leaves() == sk.get_n_leaves(), "同参数下叶子数应一致"
    print("→ 划分准则一致时，手写与 sklearn 的结构和准确率一致。\n")


# ---------------------------------------------------------------- 实验二

def experiment_criterion() -> list:
    X_tr, X_te, y_tr, y_te = make_data()
    print("== 实验二：gini vs entropy（depth=4） ==")
    print(f"{'criterion':10} | {'训练 acc':>8} | {'测试 acc':>8} | {'叶子':>4} | {'根不纯度':>8}")
    print("-" * 54)
    rows = []
    for criterion in ("gini", "entropy"):
        model = DecisionTree(criterion=criterion, max_depth=4).fit(X_tr, y_tr)
        rows.append({"criterion": criterion, "train": accuracy(y_tr, model.predict(X_tr)),
                     "test": accuracy(y_te, model.predict(X_te)),
                     "leaves": model.get_n_leaves(), "root": model.root["impurity"]})
        print(f"{criterion:10} | {rows[-1]['train']:8.4f} | {rows[-1]['test']:8.4f} | "
              f"{rows[-1]['leaves']:4d} | {rows[-1]['root']:8.4f}")
    print("→ 两种准则只在「选哪个切分」上有细微差别；本数据上 gini 测试略高，"
          "换数据/种子可能反过来。\n")
    return rows


# ---------------------------------------------------------------- 实验三

def experiment_depth() -> list:
    X_tr, X_te, y_tr, y_te = make_data()
    print("== 实验三：深度扫描（gini） ==")
    print(f"{'depth':>5} | {'训练 acc':>8} | {'测试 acc':>8} | {'叶子':>4}")
    print("-" * 34)
    rows = []
    for depth in range(1, 11):
        model = DecisionTree(max_depth=depth).fit(X_tr, y_tr)
        rows.append({"depth": depth, "train": accuracy(y_tr, model.predict(X_tr)),
                     "test": accuracy(y_te, model.predict(X_te)),
                     "leaves": model.get_n_leaves()})
        print(f"{depth:5d} | {rows[-1]['train']:8.4f} | {rows[-1]['test']:8.4f} | "
              f"{rows[-1]['leaves']:4d}")

    assert rows[0]["train"] < rows[3]["train"], "加深应提升训练准确率"
    assert rows[-1]["leaves"] >= rows[0]["leaves"], "叶子数随深度不减"
    best = max(rows, key=lambda r: r["test"])
    print(f"\n→ 测试最优在 depth={best['depth']}（{best['test']:.4f}）；"
          f"再深训练更高、测试不一定更好。\n")
    return rows


# ---------------------------------------------------------------- 实验四

def experiment_pruning() -> list:
    X_tr, X_te, y_tr, y_te = make_data()
    full = DecisionTree().fit(X_tr, y_tr)
    alphas, _ = framework.pruning_path(X_tr, y_tr)
    picks = np.unique(np.quantile(alphas, [0.0, 0.3, 0.6, 0.8, 0.9, 0.95, 1.0]))
    print("== 实验四：代价复杂度剪枝（ccp_alpha） ==")
    print(f"{'alpha':>8} | {'训练 acc':>8} | {'测试 acc':>8} | {'叶子':>4}")
    print("-" * 34)
    rows = []
    for alpha in picks:
        model = DecisionTree(ccp_alpha=float(alpha)).fit(X_tr, y_tr)
        rows.append({"alpha": float(alpha), "train": accuracy(y_tr, model.predict(X_tr)),
                     "test": accuracy(y_te, model.predict(X_te)),
                     "leaves": model.get_n_leaves()})
        print(f"{rows[-1]['alpha']:8.4f} | {rows[-1]['train']:8.4f} | "
              f"{rows[-1]['test']:8.4f} | {rows[-1]['leaves']:4d}")

    best = max(rows, key=lambda r: r["test"])
    assert best["leaves"] < full.get_n_leaves(), "剪枝后的叶子应少于完全树"
    print(f"\n→ 完全树 {full.get_n_leaves()} 叶；剪枝最优 alpha={best['alpha']:.4f}、"
          f"{best['leaves']} 叶、测试 {best['test']:.4f}。\n")
    return rows


# ---------------------------------------------------------------- 实验五

def experiment_instability(boot: int = 20) -> float:
    X_tr, X_te, y_tr, y_te = make_data()
    rng = np.random.default_rng(SEED)
    preds, accs = [], []
    for _ in range(boot):
        idx = rng.integers(0, len(y_tr), len(y_tr))
        model = DecisionTree(max_depth=4).fit(X_tr[idx], y_tr[idx])
        pred = model.predict(X_te)
        preds.append(pred)
        accs.append(accuracy(y_te, pred))

    preds = np.array(preds)
    disagree = [float(np.mean(preds[i] != preds[j]))
                for i in range(boot) for j in range(i + 1, boot)]
    mean_disagree = float(np.mean(disagree))

    print("== 实验五：不稳定性（bootstrap 20 棵树，depth=4） ==")
    print(f"  单树测试准确率：均值 {np.mean(accs):.4f}，标准差 {np.std(accs):.4f}")
    print(f"  两两预测分歧：均值 {mean_disagree:.4f}（0 = 完全相同，1 = 全相反）")
    assert mean_disagree > 0.05, "换一批训练样本，树应出现可见的结构差异"
    print("\n→ 只改动训练集的重采样，边界就会明显变化——这就是树的不稳定性，"
          "也是随机森林要 bagging 的动机。\n")
    return mean_disagree


def main() -> None:
    experiment_main()
    experiment_criterion()
    experiment_depth()
    experiment_pruning()
    experiment_instability()


if __name__ == "__main__":
    main()
