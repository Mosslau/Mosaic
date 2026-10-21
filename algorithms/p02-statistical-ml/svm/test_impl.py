"""支持向量机 SVM — 性质测试（pytest）

用法（本目录内）：uv run pytest test_impl.py -q

覆盖：
- hinge loss 已知值；原始问题（GD）在可分数据上收敛
- C 的几何效果：C 增大 → 间隔变小
- 原始 vs 对偶：线性核下两者的间隔/准确率接近
- 对偶 KKT：0<α<C 时 y·f=1；α=0 时 y·f≥1；α=C 时 y·f≤1
- 核矩阵：对称、对角为正、RBF 取值在 (0,1]
- 核技巧：同心圆上 RBF 明显优于线性核
- 数据契约：标签必须是 ±1、维度/长度/NaN、非法 C/kernel
- 确定性：同数据同参数训练结果一致
"""

import numpy as np
import pytest
from impl import KernelSVM, LinearSVM, _kernel, hinge_loss


def make_blobs(n: int = 120, seed: int = 0):
    rng = np.random.default_rng(seed)
    X0 = rng.normal([-1, -1], 0.5, size=(n // 2, 2))
    X1 = rng.normal([1, 1], 0.5, size=(n - n // 2, 2))
    X = np.vstack([X0, X1])
    y = np.array([-1] * (n // 2) + [1] * (n - n // 2))
    return X, y


def make_circles(n: int = 160, seed: int = 1):
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 2 * np.pi, n // 2, endpoint=False)
    r_in = 0.5 + 0.03 * rng.normal(size=n // 2)
    r_out = 1.5 + 0.03 * rng.normal(size=n // 2)
    X = np.vstack([np.c_[r_in * np.cos(t), r_in * np.sin(t)],
                   np.c_[r_out * np.cos(t), r_out * np.sin(t)]])
    y = np.array([-1] * (n // 2) + [1] * (n - n // 2))
    return X, y


# ---------------------------------------------------------------- hinge / 原始

def test_hinge_loss_known_values() -> None:
    assert hinge_loss(np.array([2.0, 3.0]), np.array([1.0, 1.0])) == 0.0
    assert hinge_loss(np.array([0.0]), np.array([1.0])) == pytest.approx(1.0)
    assert hinge_loss(np.array([-1.0]), np.array([1.0])) == pytest.approx(2.0)


def test_linear_svm_separable() -> None:
    X, y = make_blobs()
    model = LinearSVM(C=1.0, lr=1e-3, epochs=20000, tol=1e-8).fit(X, y)
    assert np.mean(model.predict(X) == y) >= 0.98
    assert model.margin > 0


def test_larger_c_smaller_margin() -> None:
    X, y = make_blobs()
    margins = []
    for C in (0.1, 1.0, 10.0):
        model = LinearSVM(C=C, lr=1e-3, epochs=20000, tol=1e-8).fit(X, y)
        margins.append(model.margin)
    assert margins[0] > margins[1] > margins[2]


# ---------------------------------------------------------------- 对偶 / KKT

def test_linear_kernel_matches_primal() -> None:
    X, y = make_blobs()
    primal = LinearSVM(C=1.0, lr=1e-3, epochs=20000, tol=1e-8).fit(X, y)
    dual = KernelSVM(C=1.0, kernel="linear", max_iter=100, tol=1e-4).fit(X, y)
    assert abs(primal.margin - dual.margin) < 0.1
    assert abs(np.mean(primal.predict(X) == y) - np.mean(dual.predict(X) == y)) < 0.02


def test_dual_kkt_conditions() -> None:
    X, y = make_blobs()
    C = 1.0
    model = KernelSVM(C=C, kernel="linear", max_iter=200, tol=1e-4).fit(X, y)
    Xs = (X - model._mu) / model._sigma
    K = Xs @ Xs.T
    f = K @ (model.alpha * y) + model.b
    yf = y * f
    for a, v in zip(model.alpha, yf):
        if 1e-6 < a < C - 1e-6:
            assert abs(v - 1.0) < 0.05, f"自由 SV 的 y·f 应为 1，实际 {v}"
        elif a <= 1e-6:
            assert v >= 1.0 - 0.05, f"α=0 的样本应满足 y·f ≥ 1，实际 {v}"
        else:
            assert v <= 1.0 + 0.05, f"α=C 的样本应满足 y·f ≤ 1，实际 {v}"


def test_kernel_matrix_properties() -> None:
    rng = np.random.default_rng(0)
    A = rng.normal(size=(20, 3))
    K_lin = _kernel(A, A, "linear", 1.0, 3, 1.0)
    np.testing.assert_allclose(K_lin, K_lin.T)
    assert np.all(np.diag(K_lin) > 0)
    K_rbf = _kernel(A, A, "rbf", 0.5, 3, 1.0)
    assert np.allclose(K_rbf, K_rbf.T)
    assert np.all((K_rbf > 0) & (K_rbf <= 1.0 + 1e-12))


def test_rbf_handles_circles() -> None:
    from sklearn.model_selection import train_test_split
    X, y = make_circles()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0,
                                              stratify=y)
    linear = KernelSVM(C=10.0, kernel="linear", max_iter=100, tol=1e-4).fit(X_tr, y_tr)
    rbf = KernelSVM(C=10.0, kernel="rbf", max_iter=100, tol=1e-4).fit(X_tr, y_tr)
    assert np.mean(linear.predict(X_te) == y_te) < 0.8
    assert np.mean(rbf.predict(X_te) == y_te) >= 0.95


def test_poly_kernel_solves_xor() -> None:
    X = np.array([[-1.0, -1.0], [1.0, 1.0], [-1.0, 1.0], [1.0, -1.0]])
    y = np.array([-1.0, -1.0, 1.0, 1.0])
    linear = KernelSVM(C=10.0, kernel="poly", degree=1, coef0=1.0, gamma=1.0,
                       max_iter=200, tol=1e-5, standardize=False).fit(X, y)
    quad = KernelSVM(C=10.0, kernel="poly", degree=2, coef0=1.0, gamma=1.0,
                     max_iter=200, tol=1e-5, standardize=False).fit(X, y)
    assert np.mean(linear.predict(X) == y) <= 0.75
    assert np.mean(quad.predict(X) == y) == 1.0


# ---------------------------------------------------------------- 契约

def test_predict_before_fit_raises() -> None:
    X, _ = make_blobs()
    with pytest.raises(RuntimeError):
        LinearSVM().predict(X)
    with pytest.raises(RuntimeError):
        KernelSVM().predict(X)


def test_invalid_inputs() -> None:
    X, y = make_blobs()
    with pytest.raises(ValueError):
        LinearSVM(C=0.0)
    with pytest.raises(ValueError):
        LinearSVM().fit(X, np.where(y > 0, 2, 0))       # 标签不是 ±1
    with pytest.raises(ValueError):
        LinearSVM().fit(X[:, 0], y)
    with pytest.raises(ValueError):
        LinearSVM().fit(X, y[:-1])
    bad = X.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        LinearSVM().fit(bad, y)
    with pytest.raises(ValueError):
        KernelSVM(kernel="cosine")


def test_training_is_deterministic() -> None:
    X, y = make_blobs()
    a = LinearSVM(C=1.0, lr=1e-3, epochs=300).fit(X, y)
    b = LinearSVM(C=1.0, lr=1e-3, epochs=300).fit(X, y)
    np.testing.assert_array_equal(a.w, b.w)
    assert a.b == b.b
    ka = KernelSVM(C=1.0, kernel="linear", max_iter=20).fit(X, y)
    kb = KernelSVM(C=1.0, kernel="linear", max_iter=20).fit(X, y)
    np.testing.assert_array_equal(ka.alpha, kb.alpha)
    assert ka.b == kb.b
