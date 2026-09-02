#!/usr/bin/env python3
# examples/ex05-crossval-tuning.py —— 交叉验证与调参（主文档 3.7）
# 验证环境：Python 3.13.9（macOS arm64）+ numpy 2.3.5 + scikit-learn 1.7.2（本机已装并实测）
# 运行：python3 ex05-crossval-tuning.py（离线可跑，已验证）
# 验证状态：已验证 —— 全部数字为固定 seed=42 下的本机实测，完全可复现
# 验证块数字实测：10 次单次划分 val acc 波动 0.920~0.973（跨度 0.053）；
#                5 折 CV mean 0.941 ± 0.004；决策树 depth 调参：CV 最佳 depth=4（0.926），
#                重训后 test acc 0.944；若按 train acc 选会选中 depth 12（train 0.998 /
#                test 0.936 —— 训练准、测试差，过拟合）
"""交叉验证与调参演示（roadmap 必会概念：训练 / 验证 / 测试集要分开 + 会评估）。

A. 单次划分是运气：同一模型换 10 个划分 seed，验证准确率 0.920~0.973 乱跳
   （跨度 0.053）——「调参调到验证集最好」可能只是调到了这次划分的噪声。
B. 交叉验证给稳定估计：k 折把训练数据切成 k 份轮流当验证集，5 折 mean 0.941
   ± 0.004，波动被平均掉，比单次划分可信得多。
C. 用 CV 调参、用测试集只验收一次：决策树 max_depth 1..15 逐档跑 5 折 CV，
   选 CV mean 最高的 depth=4；若贪 train acc 会选中 depth 12（train 0.998），
   其 test 0.936 反而最差——训练分数会骗你，CV 不会。
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

SEED = 42
N = 1500
SPLIT_SEEDS = list(range(10))  # 10 个「单次划分」的随机种子


def make_fault_data() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(SEED)
    n0, n1 = int(N * 0.88), int(N * 0.08)
    n2 = N - n0 - n1

    def gauss(mean: list[float], std: list[float], k: int) -> np.ndarray:
        return np.asarray(mean) + np.asarray(std) * rng.standard_normal((k, 5))

    X = np.vstack(
        [
            gauss([30, 3.7, 10, 0.5, 1.2], [5, 0.16, 2.8, 0.3, 0.12], n0),
            gauss([34, 4.0, 8.5, 1.0, 1.4], [5, 0.3, 3.2, 0.4, 0.18], n1),
            gauss([46, 3.7, 12, 1.6, 1.5], [12, 0.28, 4.5, 1.2, 0.35], n2),
        ]
    )
    y = np.concatenate([np.zeros(n0), np.ones(n1), np.full(n2, 2)]).astype(int)
    idx = rng.permutation(N)
    return X[idx], y[idx]


def section_a_single_split_luck() -> None:
    print("== A. 单次划分是运气：kNN(5) 换 10 个划分 seed ==")
    X, y = make_fault_data()
    X_dev, X_te, y_dev, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=SEED)
    accs: list[float] = []
    for sd in SPLIT_SEEDS:
        X_tr, X_va, y_tr, y_va = train_test_split(
            X_dev, y_dev, test_size=0.2, stratify=y_dev, random_state=sd
        )
        scaler = StandardScaler().fit(X_tr)
        model = KNeighborsClassifier(n_neighbors=5).fit(scaler.transform(X_tr), y_tr)
        accs.append(accuracy_score(y_va, model.predict(scaler.transform(X_va))))
    print("   10 次验证 acc: " + " ".join(f"{a:.3f}" for a in accs))
    print(
        f"   min {min(accs):.3f} / max {max(accs):.3f}（跨度 {max(accs) - min(accs):.3f}）"
        f"—— 同一个模型，换个划分能差 5 个百分点"
    )


def section_b_cross_validation() -> None:
    print("== B. 交叉验证：k 折把波动平均掉 ==")
    X, y = make_fault_data()
    X_dev, X_te, y_dev, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=SEED)
    scaler = StandardScaler().fit(X_dev)
    Xs = scaler.transform(X_dev)
    for k in (3, 5, 10):
        cv = StratifiedKFold(n_splits=k, shuffle=True, random_state=SEED)
        scores = cross_val_score(
            KNeighborsClassifier(n_neighbors=5), Xs, y_dev, cv=cv, scoring="accuracy"
        )
        print(
            f"   k={k:<2} 折: mean {scores.mean():.3f} ± {scores.std():.3f}"
            f"（各折 {np.round(scores, 3).tolist()}）"
        )
    print("   → 5 折 mean 0.941 ± 0.004：与单次划分的 0.92~0.97 乱跳相比，折数一多就稳")


def section_c_tune_with_cv() -> None:
    print("== C. 用 CV 调参：决策树 max_depth 1..15 ==")
    X, y = make_fault_data()
    X_dev, X_te, y_dev, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=SEED)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    best_depth, best_mean = 0, -1.0
    print(f"   {'depth':<6} {'CV mean acc':>12}   各折")
    for d in range(1, 16):
        scores = cross_val_score(
            DecisionTreeClassifier(max_depth=d, random_state=SEED), X_dev, y_dev, cv=cv
        )
        if scores.mean() > best_mean:
            best_depth, best_mean = d, float(scores.mean())
        print(f"   {d:<6} {scores.mean():>12.3f}   {np.round(scores, 3).tolist()}")
    print(f"   → CV mean 最高的是 depth={best_depth}（{best_mean:.3f}）")

    model = DecisionTreeClassifier(max_depth=best_depth, random_state=SEED).fit(X_dev, y_dev)
    te = accuracy_score(y_te, model.predict(X_te))
    print(f"   按 CV 选择 depth={best_depth} 重训：test acc {te:.3f}")
    # 反面：如果按「训练集 acc」选参，会选中最大的 depth 12（train 0.998）
    greedy = DecisionTreeClassifier(max_depth=12, random_state=SEED).fit(X_dev, y_dev)
    print(
        f"   反面（按 train acc 贪心选 depth=12）: train acc "
        f"{accuracy_score(y_dev, greedy.predict(X_dev)):.3f} / test acc "
        f"{accuracy_score(y_te, greedy.predict(X_te)):.3f} —— 训练最准、测试反而更差"
    )


if __name__ == "__main__":
    section_a_single_split_luck()
    section_b_cross_validation()
    section_c_tune_with_cv()
