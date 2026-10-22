"""感知机 — demo：收敛、震荡、顺序敏感性与逻辑回归边界对比

    uv run python demo.py

    实验一  线性可分：感知机收敛、与 sklearn/逻辑回归对比
    实验二  线性不可分（XOR）：误差震荡、不收敛
    实验三  样本顺序敏感性：同一数据、不同种子 → 不同边界
    实验四  重叠数据：感知机 vs 逻辑回归（间隔/概率/AUC）
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import Perceptron
from sklearn.datasets import make_blobs
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

SEED = 0
REPEATS = 3


def make_separable(n: int = 200, seed: int = SEED):
    X, y = make_blobs(n_samples=n, centers=[[-1.5, -1.5], [1.5, 1.5]],
                      cluster_std=0.5, random_state=seed)
    y = np.where(y == 1, 1, -1)
    return train_test_split(X, y, test_size=0.3, random_state=seed, stratify=y)


def make_xor(n: int = 240, seed: int = 1):
    rng = np.random.default_rng(seed)
    centers = np.array([[-1, -1], [-1, 1], [1, -1], [1, 1]])
    labels = np.array([-1, 1, 1, -1])
    X = np.vstack([c + rng.normal(0, 0.35, size=(n // 4, 2)) for c in centers])
    y = np.repeat(labels, n // 4)
    return X, y


def make_overlap(n: int = 300, seed: int = 2):
    X, y = make_blobs(n_samples=n, centers=[[-1.0, 0.0], [1.0, 0.0]],
                      cluster_std=1.0, random_state=seed)
    y = np.where(y == 1, 1, -1)
    return train_test_split(X, y, test_size=0.3, random_state=seed, stratify=y)


def acc(y, p) -> float:
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

def experiment_separable() -> None:
    X_tr, X_te, y_tr, y_te = make_separable()
    print("== 实验一：线性可分（手写 vs sklearn vs torch vs 逻辑回归） ==")
    print(f"{'方法':14} | {'训练 acc':>8} | {'测试 acc':>8} | {'轮数':>4} | {'耗时(ms)':>8}")
    print("-" * 52)

    try:
        torch_model, t_torch = _median_time(
            lambda: framework.fit_torch_perceptron(X_tr, y_tr, lr=0.1, epochs=50))
    except ImportError:
        torch_model, t_torch = None, None
    hand, t_hand = _median_time(lambda: Perceptron(lr=0.1, epochs=50,
                                                   random_state=SEED).fit(X_tr, y_tr))
    sk, t_sk = _median_time(lambda: framework.fit_perceptron(X_tr, y_tr, lr=0.1, epochs=50))
    log, t_log = _median_time(lambda: framework.fit_logistic(X_tr, y_tr))

    for name, model, train_acc, test_acc, epochs, t in (
        ("手写感知机", hand, acc(y_tr, hand.predict(X_tr)), acc(y_te, hand.predict(X_te)),
         hand.epochs_run, t_hand),
        ("sklearn 感知机", sk, acc(y_tr, sk.predict(X_tr)), acc(y_te, sk.predict(X_te)),
         sk.n_iter_, t_sk),
        ("逻辑回归", log, acc(y_tr, log.predict(X_tr)), acc(y_te, log.predict(X_te)),
         "—", t_log),
    ):
        print(f"{name:14} | {train_acc:8.4f} | {test_acc:8.4f} | "
              f"{str(epochs):>4} | {t * 1000:8.3f}")
    if torch_model is not None:
        print(f"{'torch 感知机':14} | {acc(y_tr, torch_model.predict(X_tr)):8.4f} | "
              f"{acc(y_te, torch_model.predict(X_te)):8.4f} | "
              f"{torch_model.epochs_run:>4} | {t_torch * 1000:8.3f}")

    assert acc(y_te, hand.predict(X_te)) == 1.0
    assert hand.errors_per_epoch[-1] == 0, "线性可分时最后一轮应零错误"
    assert abs(acc(y_te, hand.predict(X_te)) - acc(y_te, sk.predict(X_te))) < 0.02
    print(f"\n→ 手写 {hand.epochs_run} 轮收敛；它的间隔 {hand.margin:.2f} 只是「停在哪」，"
          "不是最大间隔。四者都 100% 分对，但边界/耗时不同。\n")


# ---------------------------------------------------------------- 实验二

def experiment_xor() -> None:
    X, y = make_xor()
    hand = Perceptron(lr=0.1, epochs=100, random_state=SEED).fit(X, y)
    sk = framework.fit_perceptron(X, y, lr=0.1, epochs=100)
    print("== 实验二：线性不可分（XOR） ==")
    print(f"手写每轮错误数（前 10）：{hand.errors_per_epoch[:10]}")
    print(f"手写最后一轮错误：{hand.errors_per_epoch[-1]}；测试 acc {acc(y, hand.predict(X)):.3f}")
    print(f"sklearn 测试 acc {acc(y, sk.predict(X)):.3f}")
    assert hand.errors_per_epoch[-1] > 0, "不可分时最后一轮不应零错误"
    assert acc(y, hand.predict(X)) < 0.8
    assert len(set(hand.errors_per_epoch)) > 1, "误差应在 epoch 间摆动"
    print("\n→ 线性边界切不开 XOR：误差不归零、准确率在 0.5 附近震荡。\n")


# ---------------------------------------------------------------- 实验三

def experiment_order() -> None:
    X_tr, X_te, y_tr, y_te = make_separable()
    margins = []
    for seed in range(10):
        m = Perceptron(lr=0.1, epochs=50, random_state=seed).fit(X_tr, y_tr)
        margins.append(m.margin)
    print("== 实验三：样本顺序敏感性（10 个种子） ==")
    print("  间隔：" + "、".join(f"{v:.2f}" for v in margins))
    print(f"  均值 {np.mean(margins):.3f}，标准差 {np.std(margins):.3f}，"
          f"最小 {min(margins):.3f}，最大 {max(margins):.3f}")
    assert np.std(margins) > 0.01, "不同更新顺序应得到不同边界"
    print("\n→ 都分对，但停在不同分隔超平面上；感知机不保证最大间隔。\n")


# ---------------------------------------------------------------- 实验四

def experiment_overlap() -> None:
    X_tr, X_te, y_tr, y_te = make_overlap()
    hand = Perceptron(lr=0.05, epochs=100, random_state=SEED).fit(X_tr, y_tr)
    log = framework.fit_logistic(X_tr, y_tr)
    p_acc = acc(y_te, hand.predict(X_te))
    l_acc = acc(y_te, log.predict(X_te))
    p_auc = roc_auc_score(y_te, hand.decision_function(X_te))
    l_auc = roc_auc_score(y_te, log.decision_function(X_te))
    print("== 实验四：重叠数据（感知机 vs 逻辑回归） ==")
    print(f"  感知机：acc {p_acc:.3f}，AUC {p_auc:.3f}，间隔 {hand.margin:.3f}")
    print(f"  逻辑回归：acc {l_acc:.3f}，AUC {l_auc:.3f}，"
          f"间隔 {2.0 / np.linalg.norm(log.coef_[0]):.3f}")
    assert l_acc >= p_acc - 0.02
    assert l_auc > 0.8
    print("\n→ 重叠时逻辑回归更好：它优化概率/对数损失，感知机只追「分对」，"
          "对难分样本没有概率可用。\n")


def main() -> None:
    experiment_separable()
    experiment_xor()
    experiment_order()
    experiment_overlap()


if __name__ == "__main__":
    main()
