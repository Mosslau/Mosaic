"""迁移项目：真实数据上的 SVM —— 乳腺癌诊断 + C/γ 交叉验证

    uv run python breast_cancer.py

数据来自 sklearn 自带的 `load_breast_cancer`（真实临床特征，569 样本、30 维）。
与教学示例的差别：
1. 真实数据、特征尺度差异大 → 必须标准化；
2. 线性核已经很强（约 0.95），要回答"核到底带来多少增量"；
3. C 与 γ 两个超参必须在训练集内用 5 折 CV 选，测试集只报告最终结果。
"""

import sys
import time
from pathlib import Path

import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import KFold, train_test_split

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import KernelSVM  # noqa: E402

C_GRID = (1.0, 10.0, 100.0)
GAMMA_GRID = (0.003, 0.01, 0.03, 0.1)


def accuracy(y_true, y_pred) -> float:
    return float(np.mean(np.asarray(y_true) == np.asarray(y_pred)))


def cv_accuracy(C: float, gamma: float, X, y, k: int = 5) -> float:
    scores = []
    for train, val in KFold(n_splits=k, shuffle=True, random_state=0).split(X):
        model = KernelSVM(C=C, kernel="rbf", gamma=gamma, max_iter=120, tol=1e-4,
                          standardize=True).fit(X[train], y[train])
        scores.append(accuracy(y[val], model.predict(X[val])))
    return float(np.mean(scores))


def main() -> None:
    X, y0 = load_breast_cancer(return_X_y=True)
    y = np.where(y0 == 1, 1, -1)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0,
                                              stratify=y)
    print(f"样本 {len(y)}（训练 {len(y_tr)} / 测试 {len(y_te)}），特征 {X.shape[1]} 维；"
          f"正类占比 {np.mean(y == 1):.1%}")

    t0 = time.perf_counter()
    linear = KernelSVM(C=1.0, kernel="linear", max_iter=120, tol=1e-4,
                       standardize=True).fit(X_tr, y_tr)
    t_lin = time.perf_counter() - t0
    lin_acc = accuracy(y_te, linear.predict(X_te))
    print(f"\n线性核（C=1）：测试准确率 {lin_acc:.4f}，耗时 {t_lin:.2f}s")

    print("\nRBF 的 C/γ 网格（5 折 CV，只看训练集）：")
    print(f"{'C':>6} | {'gamma':>6} | {'CV acc':>7}")
    print("-" * 26)
    rows = []
    for C in C_GRID:
        for gamma in GAMMA_GRID:
            cv = cv_accuracy(C, gamma, X_tr, y_tr)
            rows.append({"C": C, "gamma": gamma, "cv": cv})
            print(f"{C:6.0f} | {gamma:6.3f} | {cv:7.4f}")

    best = max(rows, key=lambda r: r["cv"])
    t0 = time.perf_counter()
    rbf = KernelSVM(C=best["C"], kernel="rbf", gamma=best["gamma"], max_iter=120,
                    tol=1e-4, standardize=True).fit(X_tr, y_tr)
    t_rbf = time.perf_counter() - t0
    rbf_acc = accuracy(y_te, rbf.predict(X_te))
    sv_fraction = rbf.n_support / len(y_tr)

    print(f"\n选中的 (C, γ) = ({best['C']:.0f}, {best['gamma']})，CV {best['cv']:.4f}")
    print(f"RBF 测试准确率 {rbf_acc:.4f}，支持向量 {rbf.n_support}/{len(y_tr)} "
          f"（{sv_fraction:.1%}），耗时 {t_rbf:.2f}s")

    print("\n== 验收 ==")
    checks = [
        ("线性核测试准确率 ≥ 0.93", lin_acc >= 0.93),
        ("RBF 的 5 折 CV ≥ 0.95", best["cv"] >= 0.95),
        ("RBF 测试准确率 ≥ 0.95", rbf_acc >= 0.95),
        ("RBF 不差于线性核 1 个百分点以上", rbf_acc >= lin_acc - 0.01),
        ("支持向量占比 ≤ 60%", sv_fraction <= 0.60),
        ("选中的 γ 不是网格边界", best["gamma"] not in (GAMMA_GRID[0], GAMMA_GRID[-1])),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"
    print(f"\n→ 真实数据上线性核 {lin_acc:.3f}、RBF {rbf_acc:.3f}；"
          f"核的增量不大，但 CV 选参与支持向量占比给出了可解释的复杂度。")


if __name__ == "__main__":
    main()
