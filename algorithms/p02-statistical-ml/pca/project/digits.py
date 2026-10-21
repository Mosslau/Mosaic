"""迁移项目：真实数据上的 PCA —— 手写数字 + kNN

    uv run python digits.py

数据：sklearn `load_digits`（1797×64，10 类）。
目标：
1. 先切分训练/测试，PCA 只在训练集上 fit（避免泄漏）；
2. 用 5 折 CV 选主成分数 k；
3. 比较原始像素与 PCA 降维后的 kNN 准确率、重建误差。
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import KFold, train_test_split
from sklearn.neighbors import KNeighborsClassifier

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import PCA  # noqa: E402

K_GRID = (10, 15, 20, 25, 30, 40)


def cv_accuracy(k: int, X, y, folds=5) -> float:
    scores = []
    for tr, va in KFold(n_splits=folds, shuffle=True, random_state=0).split(X):
        pca = PCA(n_components=k).fit(X[tr])
        knn = KNeighborsClassifier(n_neighbors=5).fit(pca.transform(X[tr]), y[tr])
        scores.append(float(np.mean(knn.predict(pca.transform(X[va])) == y[va])))
    return float(np.mean(scores))


def main() -> None:
    X, y = load_digits(return_X_y=True)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0,
                                              stratify=y)
    print(f"样本 {len(y)}（训练 {len(y_tr)} / 测试 {len(y_te)}），特征 64 维，10 类")

    raw = KNeighborsClassifier(n_neighbors=5).fit(X_tr, y_tr)
    raw_acc = float(np.mean(raw.predict(X_te) == y_te))
    print(f"\n原始像素 kNN：测试 {raw_acc:.4f}")

    print("\n主成分数 k 的 5 折 CV：")
    print(f"{'k':>3} | {'CV acc':>7}")
    print("-" * 16)
    rows = []
    for k in K_GRID:
        cv = cv_accuracy(k, X_tr, y_tr)
        rows.append({"k": k, "cv": cv})
        print(f"{k:3d} | {cv:7.4f}")
    best = max(rows, key=lambda r: r["cv"])

    pca = PCA(n_components=best["k"]).fit(X_tr)
    knn = KNeighborsClassifier(n_neighbors=5).fit(pca.transform(X_tr), y_tr)
    acc = float(np.mean(knn.predict(pca.transform(X_te)) == y_te))
    recon = float(np.mean((X_te - pca.inverse_transform(pca.transform(X_te))) ** 2))
    var = float(np.sum(pca.explained_variance_ratio_))

    print(f"\n选中 k={best['k']}（CV {best['cv']:.4f}）")
    print(f"PCA + kNN 测试 {acc:.4f}；累计方差 {var:.3f}；测试重建 MSE {recon:.3f}")

    print("\n== 验收 ==")
    checks = [
        ("选中的 k 在 10–40", 10 <= best["k"] <= 40),
        ("PCA + kNN 测试 ≥ 0.90", acc >= 0.90),
        ("PCA 不差于原始像素 2 个百分点", acc >= raw_acc - 0.02),
        ("5 折 CV ≥ 0.90", best["cv"] >= 0.90),
        ("测试重建 MSE < 5", recon < 5),
        ("累计方差 ≥ 0.85", var >= 0.85),
    ]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    assert all(ok for _, ok in checks), "有验收项未通过"
    print(f"\n→ 用 {best['k']}/64 个主成分，kNN 从 {raw_acc:.3f} 到 {acc:.3f}；"
          f"降维几乎不损精度，还省了 {(1 - best['k'] / 64):.0%} 的特征。")


if __name__ == "__main__":
    main()
