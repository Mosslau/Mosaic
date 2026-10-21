"""p02 阶段横向对照（同一份真实数据，框架口径）

本脚本用 sklearn 的成熟实现做**选型级**横向比较；手写实现与框架的一致性
由各实验的 test_impl.py / demo.py 保证（误差在 1e-8 ~ 1e-3 量级）。

    uv run python stage_benchmark.py

三块：
1. 二分类（breast cancer）：逻辑回归 / RBF-SVM / 决策树 / 随机森林 / GBDT / 高斯 NB
2. 回归（diabetes）：线性 / Ridge / Lasso / 随机森林 / GBDT
3. 无监督（digits）：K-Means ARI、PCA 90% 方差、IsolationForest/LOF one-class AUC
"""

from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans
from sklearn.datasets import load_breast_cancer, load_diabetes, load_digits
from sklearn.decomposition import PCA
from sklearn.ensemble import (
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    IsolationForest,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LassoCV, LinearRegression, LogisticRegression, RidgeCV
from sklearn.metrics import adjusted_rand_score, roc_auc_score, silhouette_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_validate
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KernelDensity, LocalOutlierFactor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier


def classification() -> None:
    X, y = load_breast_cancer(return_X_y=True)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    models = {
        "逻辑回归": make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)),
        "RBF-SVM": make_pipeline(StandardScaler(),
                                    SVC(kernel="rbf", C=1.0, gamma="scale", random_state=0)),
        "决策树(d=4)": DecisionTreeClassifier(max_depth=4, random_state=0),
        "随机森林(200)": RandomForestClassifier(n_estimators=200, random_state=0, n_jobs=1),
        "GBDT(100)": HistGradientBoostingClassifier(max_iter=100, random_state=0),
        "高斯 NB": GaussianNB(),
    }
    print("== 二分类：breast cancer（5 折 CV） ==")
    print(f"{'模型':16} | {'acc':>7} | {'F1':>7} | {'AUC':>7} | {'fit ms':>7}")
    print("-" * 56)
    for name, model in models.items():
        r = cross_validate(model, X, y, cv=cv,
                           scoring={"acc": "accuracy", "f1": "f1", "auc": "roc_auc"})
        print(f"{name:16} | {r['test_acc'].mean():7.4f} | {r['test_f1'].mean():7.4f} | "
              f"{r['test_auc'].mean():7.4f} | {r['fit_time'].mean() * 1000:7.1f}")


def regression() -> None:
    X, y = load_diabetes(return_X_y=True)
    cv = KFold(n_splits=5, shuffle=True, random_state=0)
    models = {
        "线性回归": LinearRegression(),
        "RidgeCV": make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20))),
        "LassoCV": make_pipeline(StandardScaler(), LassoCV(cv=5, random_state=0, max_iter=50000)),
        "随机森林(200)": RandomForestRegressor(n_estimators=200, random_state=0, n_jobs=1),
        "GBDT(100)": GradientBoostingRegressor(n_estimators=100, learning_rate=0.05,
                                               max_depth=3, random_state=0),
    }
    print("\n== 回归：diabetes（5 折 CV） ==")
    print(f"{'模型':14} | {'RMSE':>8} | {'R²':>7} | {'fit ms':>7}")
    print("-" * 44)
    for name, model in models.items():
        r = cross_validate(model, X, y, cv=cv,
                           scoring={"rmse": "neg_root_mean_squared_error", "r2": "r2"})
        print(f"{name:14} | {-r['test_rmse'].mean():8.3f} | {r['test_r2'].mean():7.4f} | "
              f"{r['fit_time'].mean() * 1000:7.1f}")


def unsupervised() -> None:
    X, y = load_digits(return_X_y=True)
    km = KMeans(n_clusters=10, n_init=10, random_state=0).fit(X)
    pca = PCA(n_components=0.9).fit(X)
    rec = pca.inverse_transform(pca.transform(X))
    print("\n== 无监督：digits ==")
    print(f"K-Means(k=10)：ARI {adjusted_rand_score(y, km.labels_):.4f}，"
          f"轮廓 {silhouette_score(X, km.labels_):.4f}")
    print(f"PCA 90% 方差：{pca.n_components_} 个主成分，重建 MSE {np.mean((X - rec) ** 2):.3f}")

    normal, anomaly = X[y == 0], X[y != 0]
    X_tr = normal[:120]
    X_te = np.vstack([normal[120:], anomaly[:100]])
    y_te = np.r_[np.zeros(len(normal) - 120), np.ones(100)]
    for name, model, to_score in (
        ("IsolationForest", IsolationForest(n_estimators=100, contamination=0.05,
                                            random_state=0), lambda s: -s),
        ("LOF", LocalOutlierFactor(n_neighbors=20, novelty=True, contamination=0.05),
         lambda s: -s),
        ("KDE", KernelDensity(bandwidth=1.0), lambda s: -s),
    ):
        model.fit(X_tr)
        s = to_score(model.score_samples(X_te))
        print(f"{name:16} one-class AUC：{roc_auc_score(y_te, s):.4f}")


def main() -> None:
    classification()
    regression()
    unsupervised()


if __name__ == "__main__":
    main()
