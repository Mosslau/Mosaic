#!/usr/bin/env python3
# examples/ex03-classification-metrics.py —— 模型评估：指标与混淆矩阵（主文档 3.5）
# 验证环境：Python 3.13.9（macOS arm64）+ numpy 2.3.5 + scikit-learn 1.7.2（本机已装并实测）
# 运行：python3 ex03-classification-metrics.py（离线可跑，已验证）
# 验证状态：已验证 —— 全部数字为固定 seed=42 下的本机实测，完全可复现；
#           换 seed 或数据划分会波动（约 ±1~2 个百分点），对比方向稳定
# 验证块数字实测：多数类 baseline acc 0.880；kNN acc 0.930 / macro-F1 0.728 /
#                少数类召回 [0.992, 0.458, 0.500]（漏一半故障）；RF acc 0.947 / macro-F1 0.793 /
#                召回 [0.996, 0.583, 0.583]；kNN 混淆矩阵 [[262,2,0],[13,11,0],[3,3,6]]
"""模型评估演示（roadmap 必会概念：能评估模型效果——指标要会挑）。

同一份部件传感器故障数据（健康 88% / 过压 8% / 过热振动 4%），四组模型对比：
  A. 准确率的骗局：多数类 baseline（全猜健康）acc 0.880——kNN acc 0.930 只比
     它高 0.05，且混淆矩阵显示 24 个过压故障漏了 13 个、12 个过热振动漏了 6 个：
     「93% 准」与「漏一半故障」同时成立，评估要看每个类，不能只看 acc。
  B. 指标各回答一个问题：precision（预测为故障里有几成真）、recall（真故障里
     抓住几成）、F1（二者调和）、macro-F1（对不平衡更公平：三类 F1 直接平均，
     不被健康类 88% 的样本数稀释）。
  C. 挑模型的判据：故障检测宁可多报不可漏报（recall 优先）；RF 在 acc 与
     macro-F1 上同时胜出（0.947 / 0.793），是这类数据的稳妥默认。
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler

SEED = 42
N = 1500
CLASSES = ["健康", "充电过压", "过热振动"]


def make_fault_data() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(SEED)
    n0, n1 = int(N * 0.88), int(N * 0.08)
    n2 = N - n0 - n1

    def gauss(mean: list[float], std: list[float], k: int) -> np.ndarray:
        return np.asarray(mean) + np.asarray(std) * rng.standard_normal((k, 5))

    X = np.vstack(
        [
            gauss([30, 3.7, 10, 0.5, 1.2], [5, 0.16, 2.8, 0.3, 0.12], n0),  # 健康
            gauss([34, 4.0, 8.5, 1.0, 1.4], [5, 0.3, 3.2, 0.4, 0.18], n1),  # 充电过压
            gauss([46, 3.7, 12, 1.6, 1.5], [12, 0.28, 4.5, 1.2, 0.35], n2),  # 过热振动
        ]
    )
    y = np.concatenate([np.zeros(n0), np.ones(n1), np.full(n2, 2)]).astype(int)
    idx = rng.permutation(N)
    return X[idx], y[idx]


def split_scaled() -> tuple[np.ndarray, ...]:
    X, y = make_fault_data()
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=0.4, stratify=y, random_state=SEED)
    X_va, X_te, y_va, y_te = train_test_split(
        X_tmp, y_tmp, test_size=0.5, stratify=y_tmp, random_state=SEED
    )
    scaler = StandardScaler().fit(X_tr)  # 缩放只在训练集拟合
    return (
        scaler.transform(X_tr),
        scaler.transform(X_va),
        scaler.transform(X_te),
        y_tr,
        y_va,
        y_te,
    )


def section_a_accuracy_trap() -> np.ndarray:
    print("== A. 准确率的骗局：多数类 baseline vs kNN ==")
    Xs_tr, Xs_va, Xs_te, y_tr, y_va, y_te = split_scaled()
    # baseline：永远猜最多的类（健康）
    base_acc = accuracy_score(y_te, np.zeros_like(y_te))
    knn = KNeighborsClassifier(n_neighbors=5).fit(Xs_tr, y_tr)
    knn_pred = knn.predict(Xs_te)
    print(f"   多数类 baseline acc {base_acc:.3f}（全猜健康也有 88% 正确！）")
    print(
        f"   kNN acc {accuracy_score(y_te, knn_pred):.3f} —— 只比 baseline 高 "
        f"{accuracy_score(y_te, knn_pred) - base_acc:.3f}，但看混淆矩阵："
    )
    cm = confusion_matrix(y_te, knn_pred)
    print("   混淆矩阵（行=真实 / 列=预测）: " + str(cm.tolist()))
    miss_healthy = cm[1, 0] + cm[2, 0]  # 被判成「健康」的故障
    miss_mix = cm[1, 2] + cm[2, 1]  # 两个故障类互相认错
    print(
        f"   24 个过压漏 {cm[1, 0] + cm[1, 2]}、12 个过热振动漏 {cm[2, 0] + cm[2, 1]} "
        f"—— {miss_healthy} 个故障被当成了健康，另有 {miss_mix} 个被认成另一个故障类！"
    )


def section_b_metrics_matrix() -> None:
    print("== B. 指标矩阵：四个模型、五个指标 ==")
    Xs_tr, Xs_va, Xs_te, y_tr, y_va, y_te = split_scaled()
    models: dict[str, object] = {
        "kNN(5)": KNeighborsClassifier(n_neighbors=5),
        "LogisticRegression": LogisticRegression(max_iter=3000),
        "RandomForest": RandomForestClassifier(n_estimators=200, random_state=SEED),
        "RF + class_weight=balanced": RandomForestClassifier(
            n_estimators=200, class_weight="balanced", random_state=SEED
        ),
    }
    print(f"{'模型':<28} {'acc':>6} {'macro-F1':>9} {'weighted-F1':>12}  各类 recall")
    for name, est in models.items():
        est.fit(Xs_tr, y_tr)  # type: ignore[operator]
        pred = est.predict(Xs_te)  # type: ignore[attr-defined]
        rec = recall_score(y_te, pred, average=None)
        print(
            f"{name:<28} {accuracy_score(y_te, pred):>6.3f} "
            f"{f1_score(y_te, pred, average='macro'):>9.3f} "
            f"{f1_score(y_te, pred, average='weighted'):>12.3f}  "
            + " ".join(f"{c} {r:.2f}" for c, r in zip(CLASSES, rec, strict=True))
        )
    print(
        "   读数：acc 相近（0.930~0.947）看不出差别；macro-F1 拉开差距——"
        "kNN 0.728 vs RF 0.793（对少数类更公平的尺子）"
    )


def section_c_confusion_detail() -> None:
    print("== C. 从混淆矩阵读模型行为（kNN vs RF）==")
    Xs_tr, Xs_va, Xs_te, y_tr, y_va, y_te = split_scaled()
    for name, model in (
        ("kNN(5)", KNeighborsClassifier(n_neighbors=5).fit(Xs_tr, y_tr)),
        (
            "RF",
            RandomForestClassifier(n_estimators=200, random_state=SEED).fit(Xs_tr, y_tr),
        ),
    ):
        pred = model.predict(Xs_te)
        print(f"   {name} 混淆矩阵: " + str(confusion_matrix(y_te, pred).tolist()))
    pred = (
        RandomForestClassifier(n_estimators=200, random_state=SEED).fit(Xs_tr, y_tr).predict(Xs_te)
    )
    print("   逐类 precision / recall / F1（RF，测试集）:")
    for i, c in enumerate(CLASSES):
        print(
            f"     {c}: precision {precision_score(y_te, pred, labels=[i], average=None)[0]:.3f}"
            f" / recall {recall_score(y_te, pred, labels=[i], average=None)[0]:.3f}"
            f" / F1 {f1_score(y_te, pred, labels=[i], average=None)[0]:.3f}"
        )


if __name__ == "__main__":
    section_a_accuracy_trap()
    section_b_metrics_matrix()
    section_c_confusion_detail()
