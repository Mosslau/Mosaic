#!/usr/bin/env python3
# exercises/sol-02-fault-classification.py —— 练习 2 参考实现：故障分类与评估
# 验证环境：Python 3.13.9（macOS arm64）+ numpy 2.3.5 + scikit-learn 1.7.2（本机已装并实测）
# 运行：python3 sol-02-fault-classification.py（离线可跑，已验证）
# 验证状态：已验证 —— 固定 seed=7（与示例不同的种子，答案是你自己跑出来的），数字可复现；
#           随数据划分/随机种子波动（±1~2 个百分点）
# 验证块数字实测（seed=7）：kNN(3) acc 0.958 / macro-F1 0.829；kNN(7) macro-F1 0.762；
#                RF acc 0.962 / macro-F1 0.859（胜出）；RF+class_weight=balanced macro-F1 0.822
#                （本数据轻度不平衡，balanced 反而略降——体会「加权不是免费午餐」）
"""练习 2（故障分类，对应 roadmap）：分类 + 评估指标 + 类别不平衡。

任务：用 kNN / 随机森林对部件传感器故障（健康 88% / 过压 8% / 过热振动 4%）分类，
用准确率 + macro-F1 + 混淆矩阵评估并挑选模型。要点：
  1. 换一个随机种子（seed=7），数据与示例不同——数字必须自己跑出来；
  2. k 值越小，少数类召回越高但噪声越敏感（kNN(3) macro-F1 0.829 > kNN(7) 0.762）；
  3. RF 全面胜出（macro-F1 0.859）；class_weight=balanced 在本数据上反而略降
     （0.822）——轻度不平衡时加权会牺牲多数类精度，重不平衡（如故障率 1‰）才
     该上加权/重采样；
  4. 混淆矩阵读法：漏报（真故障判成健康）比误报更致命。
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler

SEED = 7  # 故意与示例 ex03（seed=42）不同
N = 1500
CLASSES = ["健康", "补能过压", "过热振动"]


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


def main() -> None:
    X, y = make_fault_data()
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.3, stratify=y, random_state=SEED
    )
    scaler = StandardScaler().fit(X_tr)
    Xs_tr, Xs_te = scaler.transform(X_tr), scaler.transform(X_te)

    print(f"== 故障分类（seed={SEED}，测试集 {len(y_te)} 条）==")
    results: list[tuple[str, float, float]] = []
    for k in (3, 5, 7):
        model = KNeighborsClassifier(n_neighbors=k).fit(Xs_tr, y_tr)
        pred = model.predict(Xs_te)
        mf = f1_score(y_te, pred, average="macro")
        results.append((f"kNN(k={k})", accuracy_score(y_te, pred), mf))
        rec = recall_score(y_te, pred, average=None)
        print(
            f"  kNN(k={k}): acc {accuracy_score(y_te, pred):.3f} / macro-F1 {mf:.3f}"
            f" / 各类 recall {rec[0]:.3f}/{rec[1]:.3f}/{rec[2]:.3f}"
        )

    for cw in (None, "balanced"):
        model = RandomForestClassifier(
            n_estimators=200, class_weight=cw, random_state=SEED
        ).fit(X_tr, y_tr)
        pred = model.predict(X_te)
        mf = f1_score(y_te, pred, average="macro")
        results.append((f"RF(cw={cw})", accuracy_score(y_te, pred), mf))
        rec = recall_score(y_te, pred, average=None)
        print(
            f"  RF(class_weight={cw}): acc {accuracy_score(y_te, pred):.3f} / macro-F1 {mf:.3f}"
            f" / 各类 recall {rec[0]:.3f}/{rec[1]:.3f}/{rec[2]:.3f}"
        )

    best_name, best_acc, best_mf = max(results, key=lambda r: r[2])
    print(
        f"\n  按 macro-F1 选模型：{best_name}（acc {best_acc:.3f} / macro-F1 {best_mf:.3f}）"
    )

    rf = RandomForestClassifier(n_estimators=200, random_state=SEED).fit(X_tr, y_tr)
    pred = rf.predict(X_te)
    print(
        f"  RF 混淆矩阵（行=真实 / 列=预测）: {confusion_matrix(y_te, pred).tolist()}"
    )
    miss = int(confusion_matrix(y_te, pred)[1, 0]) + int(
        confusion_matrix(y_te, pred)[2, 0]
    )
    print(f"  漏报（故障判成健康）{miss} 条 —— 故障检测场景漏报的代价 > 误报")

    # 验收：RF 的 macro-F1 ≥ 0.8 且优于 kNN(7)；kNN 小 k 的少数类召回应高于大 k
    rf_mf = max(r[2] for r in results if r[0].startswith("RF(cw=None"))
    knn7_mf = next(r[2] for r in results if r[0] == "kNN(k=7)")
    knn3_mf = next(r[2] for r in results if r[0] == "kNN(k=3)")
    assert rf_mf >= 0.8, "RF macro-F1 应 ≥ 0.8"
    assert rf_mf > knn7_mf, "RF 应优于 kNN(7)"
    assert knn3_mf > knn7_mf, "kNN 小 k 的 macro-F1 应高于大 k（少数类更不被淹没）"
    print("\n验收通过：会跑分类评估流程、会用 macro-F1 选模型、会读混淆矩阵")


if __name__ == "__main__":
    main()
