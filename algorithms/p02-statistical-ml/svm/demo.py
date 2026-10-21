"""支持向量机 SVM — demo：同数据双跑 + 四组实验

    uv run python demo.py

产出：
    实验一    线性可分数据：原始问题（GD）、对偶（SMO）、sklearn 三方对照
    实验二    C 扫描：间隔、支持向量数、训练/测试准确率
    实验三    核技巧：同心圆上线性 vs RBF
    实验四    hinge vs logistic：间隔外 hinge 恰好为 0
    （耗时并入实验一/三的表中）
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import KernelSVM, LinearSVM, hinge_loss
from sklearn.model_selection import train_test_split

SEED = 0
REPEATS = 5


# ---------------------------------------------------------------- 数据

def make_blobs(n: int = 200, sep: float = 1.0, seed: int = SEED):
    rng = np.random.default_rng(seed)
    X0 = rng.normal([-sep, -sep], 0.6, size=(n // 2, 2))
    X1 = rng.normal([sep, sep], 0.6, size=(n - n // 2, 2))
    X = np.vstack([X0, X1])
    y = np.array([-1] * (n // 2) + [1] * (n - n // 2))
    idx = rng.permutation(n)
    return X[idx], y[idx]


def make_circles(n: int = 300, noise: float = 0.05, seed: int = 1):
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 2 * np.pi, n // 2, endpoint=False)
    r_in = 0.5 + noise * rng.normal(size=n // 2)
    r_out = 1.5 + noise * rng.normal(size=n // 2)
    X = np.vstack([np.c_[r_in * np.cos(t), r_in * np.sin(t)],
                   np.c_[r_out * np.cos(t), r_out * np.sin(t)]])
    y = np.array([-1] * (n // 2) + [1] * (n - n // 2))
    return X, y


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

def experiment_main() -> dict:
    X, y = make_blobs()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=SEED,
                                              stratify=y)
    print("== 实验一：线性可分数据上的三方对照 ==")
    print(f"{'方法':22} | {'训练 acc':>8} | {'测试 acc':>8} | "
          f"{'间隔':>6} | {'SV':>4} | {'耗时(ms)':>8}")
    print("-" * 78)

    lin, t_lin = _median_time(lambda: LinearSVM(C=1.0, lr=1e-3, epochs=20000,
                                                tol=1e-8, standardize=False).fit(X_tr, y_tr))
    ker, t_ker = _median_time(lambda: KernelSVM(
        C=1.0, kernel="linear", max_iter=100, tol=1e-4, standardize=False).fit(X_tr, y_tr))
    sk, t_sk = _median_time(lambda: framework.fit_svc(X_tr, y_tr, C=1.0, kernel="linear"))
    sk_lin, _ = _median_time(lambda: framework.fit_linear_svc(X_tr, y_tr, C=1.0))

    rows = [
        ("手写 LinearSVM（GD）", lin, t_lin, lin.margin, -1),
        ("手写 KernelSVM（SMO）", ker, t_ker, ker.margin, ker.n_support),
        ("sklearn SVC(linear)", sk, t_sk,
         float(2.0 / np.linalg.norm(sk.coef_[0])), int(sk.n_support_.sum())),
        ("sklearn LinearSVC", sk_lin, float("nan"), float(2.0 / np.linalg.norm(sk_lin.coef_[0])),
         int(sk_lin.support_vectors_.shape[0]) if hasattr(sk_lin, "support_vectors_") else -1),
    ]
    for name, model, t, margin, sv in rows:
        tr = accuracy(y_tr, model.predict(X_tr))
        te = accuracy(y_te, model.predict(X_te))
        t_str = "—" if not np.isfinite(t) else f"{t * 1000:.3f}"
        print(f"{name:22} | {tr:8.4f} | {te:8.4f} | {margin:6.3f} | {sv:>4} | {t_str:>8}")

    assert abs(accuracy(y_te, ker.predict(X_te)) - accuracy(y_te, sk.predict(X_te))) < 0.03, \
        "手写 SMO 与 sklearn SVC 的测试准确率应接近"
    assert abs(accuracy(y_te, lin.predict(X_te)) - accuracy(y_te, ker.predict(X_te))) < 0.03, \
        "原始问题与对偶问题应给出接近的解"
    print("\n→ 两条求解路线与框架的测试准确率在 3% 内一致；SMO 的 SV 数与 sklearn 同量级。\n")
    return {"lin": lin, "ker": ker, "sk": sk}


# ---------------------------------------------------------------- 实验二

def experiment_c() -> list:
    X, y = make_blobs()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=SEED,
                                              stratify=y)
    print("== 实验二：C 扫描（线性核，SMO） ==")
    print(f"{'C':>8} | {'训练 acc':>8} | {'测试 acc':>8} | {'间隔':>6} | {'SV':>4} | {'迭代':>4}")
    print("-" * 56)
    rows = []
    for C in (0.1, 1.0, 10.0, 100.0):
        model = KernelSVM(C=C, kernel="linear", max_iter=100, tol=1e-4,
                          standardize=False).fit(X_tr, y_tr)
        rows.append({"C": C, "train": accuracy(y_tr, model.predict(X_tr)),
                     "test": accuracy(y_te, model.predict(X_te)),
                     "margin": model.margin, "sv": model.n_support, "iter": model.n_iter})
        print(f"{C:8.2f} | {rows[-1]['train']:8.4f} | {rows[-1]['test']:8.4f} | "
              f"{rows[-1]['margin']:6.3f} | {rows[-1]['sv']:4d} | {rows[-1]['iter']:4d}")

    margins = [r["margin"] for r in rows]
    assert all(margins[i] >= margins[i + 1] - 1e-9 for i in range(len(margins) - 1)), \
        "C 增大时间隔应不增（软间隔收紧）"
    assert rows[-1]["sv"] <= rows[0]["sv"] + 5, "C 增大时支持向量通常减少（软间隔收紧）"
    print("\n→ C 小：间隔宽、更多样本被截在边界上（SV 多）；C 大：间隔窄、SV 少、更贴训练集。\n")
    return rows


# ---------------------------------------------------------------- 实验三

def experiment_kernel() -> dict:
    X, y = make_circles()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=SEED,
                                              stratify=y)
    print("== 实验三：核技巧（同心圆，C=10，70/30 切分） ==")
    print(f"{'方法':22} | {'训练 acc':>8} | {'测试 acc':>8} | {'SV':>4}")
    print("-" * 52)
    lin = KernelSVM(C=10.0, kernel="linear", max_iter=100, tol=1e-4,
                    standardize=False).fit(X_tr, y_tr)
    rbf = KernelSVM(C=10.0, kernel="rbf", max_iter=100, tol=1e-4,
                    standardize=False).fit(X_tr, y_tr)
    sk_rbf = framework.fit_svc(X_tr, y_tr, C=10.0, kernel="rbf")
    rows = {"linear": lin, "rbf": rbf, "sklearn_rbf": sk_rbf}
    for name, model in rows.items():
        tr = accuracy(y_tr, model.predict(X_tr))
        te = accuracy(y_te, model.predict(X_te))
        sv = model.n_support if hasattr(model, "n_support") else int(model.n_support_.sum())
        print(f"{name:22} | {tr:8.4f} | {te:8.4f} | {sv:>4}")

    lin_te = accuracy(y_te, lin.predict(X_te))
    rbf_te = accuracy(y_te, rbf.predict(X_te))
    assert lin_te < 0.80, "同心圆上线性核应当明显欠拟合"
    assert rbf_te >= 0.95, "RBF 核应能分开同心圆（测试集）"
    assert abs(rbf_te - accuracy(y_te, sk_rbf.predict(X_te))) < 0.05
    print(f"\n→ 线性核只能切一刀（测试 {lin_te:.2f}），RBF 把圆环分开"
          f"（测试 {rbf_te:.2f}）——这就是核技巧。\n")
    return rows


# ---------------------------------------------------------------- 实验四

def experiment_losses() -> None:
    print("== 实验四：hinge 与 logistic 的差别（y = +1，看不同 score） ==")
    print(f"{'score':>6} | {'hinge':>7} | {'logistic':>8}")
    print("-" * 28)
    for s in (-2.0, -1.0, 0.0, 1.0, 2.0, 3.0):
        h = float(np.maximum(0.0, 1.0 - s))
        log = float(np.log1p(np.exp(-s)))
        print(f"{s:6.1f} | {h:7.4f} | {log:8.4f}")
    assert hinge_loss(np.array([2.0, 3.0]), np.array([1.0, 1.0])) == 0.0
    print("\n→ |score| ≥ 1 后 hinge 恰好为 0（只由支持向量决定边界）；logistic 永远不为 0。\n")


def main() -> None:
    experiment_main()
    experiment_c()
    experiment_kernel()
    experiment_losses()


if __name__ == "__main__":
    main()
