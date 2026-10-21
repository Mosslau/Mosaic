"""正则化与模型选择 — 性质测试（pytest）

用法（本目录内）：uv run pytest test_impl.py -q

覆盖：
- Ridge：正规方程残差为 0、λ=0 退化为 OLS、系数随 λ 收缩、截距正确
- Lasso：软阈值公式、KKT 次梯度条件、λ 增大更稀疏、λ=0 接近 OLS
- KFold：每折覆盖全部样本一次、训练/验证不重叠、同种子可复现
- 交叉验证：返回 k 个折 MSE、非法 k 报错
- 标准化：Ridge(standardize=True) 对特征缩放不敏感（惩罚的是标准化系数）
- 数据契约与确定性
"""

import numpy as np
import pytest
from impl import Lasso, Ridge, cross_val_mse, kfold_indices, mse, ridge_closed_form, soft_threshold


def make_data(n: int = 120, p: int = 6, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, p))
    w = np.array([2.0, -1.0, 0.5, 0.0, 0.0, 0.0])[:p]
    y = X @ w + 1.5 + rng.normal(0.0, 0.5, n)
    return X, y


# ---------------------------------------------------------------- Ridge

def test_ridge_normal_equations() -> None:
    X, y = make_data()
    lam = 0.7
    w, b = ridge_closed_form(X, y, lam)
    xm = X.mean(0)
    grad = (X - xm).T @ (X @ w + b - y) + len(y) * lam * w
    assert np.max(np.abs(grad)) < 1e-9


def test_ridge_lambda_zero_is_ols() -> None:
    X, y = make_data()
    w, b = ridge_closed_form(X, y, 0.0)
    A = np.hstack([X, np.ones((len(X), 1))])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    np.testing.assert_allclose(np.append(w, b), coef, atol=1e-8)


def test_ridge_shrinks_with_lambda() -> None:
    X, y = make_data()
    norms = [np.linalg.norm(Ridge(lam=lam).fit(X, y).coef) for lam in (0, 0.1, 1, 10)]
    assert all(norms[i] > norms[i + 1] for i in range(len(norms) - 1))


def test_ridge_predict_shape_and_before_fit() -> None:
    X, y = make_data()
    model = Ridge(lam=1.0).fit(X, y)
    assert model.predict(X).shape == (len(X),)
    with pytest.raises(RuntimeError):
        Ridge().predict(X)
    with pytest.raises(ValueError):
        model.predict(X[:, :2])


# ---------------------------------------------------------------- Lasso

def test_soft_threshold() -> None:
    assert soft_threshold(0.5, 1.0) == 0.0
    assert soft_threshold(-0.5, 1.0) == 0.0
    assert soft_threshold(2.0, 1.0) == pytest.approx(1.0)
    assert soft_threshold(-2.0, 1.0) == pytest.approx(-1.0)


def test_lasso_kkt_conditions() -> None:
    X, y = make_data()
    lam = 0.1
    model = Lasso(lam=lam, tol=1e-10).fit(X, y)
    xm = X.mean(0)
    Xc = X - xm
    r = Xc @ model.coef + model.intercept - y
    grad = Xc.T @ r / len(y)
    for j, w in enumerate(model.coef):
        if abs(w) > 1e-7:
            assert abs(grad[j] + lam * np.sign(w)) < 1e-5, f"第 {j} 个非零系数的 KKT 不满足"
        else:
            assert abs(grad[j]) <= lam + 1e-5, f"第 {j} 个零系数的次梯度超出 λ"


def test_lasso_sparsity_increases() -> None:
    X, y = make_data()
    nz = [np.sum(np.abs(Lasso(lam=lam).fit(X, y).coef) > 1e-8)
          for lam in (0.01, 0.1, 1.0)]
    assert nz[0] >= nz[1] >= nz[2]


def test_lasso_lambda_zero_near_ols() -> None:
    X, y = make_data()
    model = Lasso(lam=0.0, tol=1e-12, max_iter=20000).fit(X, y)
    w, b = ridge_closed_form(X, y, 0.0)
    np.testing.assert_allclose(model.coef, w, atol=1e-4)
    assert abs(model.intercept - b) < 1e-4


# ---------------------------------------------------------------- KFold / CV

def test_kfold_covers_each_sample_once() -> None:
    folds = kfold_indices(23, k=5, seed=0)
    assert len(folds) == 5
    val = np.concatenate([v for _, v in folds])
    assert sorted(val.tolist()) == list(range(23))
    for train, val_idx in folds:
        assert set(train).isdisjoint(set(val_idx.tolist()))


def test_kfold_reproducible() -> None:
    a = kfold_indices(50, k=5, seed=3)
    b = kfold_indices(50, k=5, seed=3)
    for (tr_a, va_a), (tr_b, va_b) in zip(a, b):
        np.testing.assert_array_equal(tr_a, tr_b)
        np.testing.assert_array_equal(va_a, va_b)


def test_kfold_invalid_k() -> None:
    with pytest.raises(ValueError):
        kfold_indices(10, k=1)
    with pytest.raises(ValueError):
        kfold_indices(10, k=11)


def test_cross_val_returns_k_folds() -> None:
    X, y = make_data()
    mean, folds = cross_val_mse(lambda: Ridge(lam=1.0), X, y, k=4, seed=0)
    assert len(folds) == 4
    assert mean == pytest.approx(float(np.mean(folds)))
    assert all(np.isfinite(f) for f in folds)


# ---------------------------------------------------------------- 标准化

def test_standardized_ridge_is_scale_invariant() -> None:
    X, y = make_data()
    X2 = X.copy()
    X2[:, 0] *= 100.0
    p1 = Ridge(lam=1.0, standardize=True).fit(X, y).predict(X)
    p2 = Ridge(lam=1.0, standardize=True).fit(X2, y).predict(X2)
    np.testing.assert_allclose(p1, p2, atol=1e-6)


def test_raw_ridge_is_not_scale_invariant() -> None:
    X, y = make_data()
    X2 = X.copy()
    X2[:, 0] *= 100.0
    p1 = Ridge(lam=1.0, standardize=False).fit(X, y).predict(X)
    p2 = Ridge(lam=1.0, standardize=False).fit(X2, y).predict(X2)
    assert not np.allclose(p1, p2, atol=1e-3)


# ---------------------------------------------------------------- 契约

def test_mse_known() -> None:
    assert mse(np.array([1.0, 2.0]), np.array([1.0, 4.0])) == pytest.approx(2.0)
    with pytest.raises(ValueError):
        mse(np.array([1.0]), np.array([1.0, 2.0]))


def test_invalid_inputs() -> None:
    X, y = make_data()
    with pytest.raises(ValueError):
        Ridge(lam=-1)
    with pytest.raises(ValueError):
        Lasso(lam=-0.1)
    with pytest.raises(ValueError):
        Ridge().fit(X[:, 0], y)
    with pytest.raises(ValueError):
        Ridge().fit(X, y[:-1])
    bad = X.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        Ridge().fit(bad, y)


def test_training_is_deterministic() -> None:
    X, y = make_data()
    a = Ridge(lam=1.0).fit(X, y)
    b = Ridge(lam=1.0).fit(X, y)
    np.testing.assert_array_equal(a.coef, b.coef)
    assert a.intercept == b.intercept
    la = Lasso(lam=0.1).fit(X, y)
    lb = Lasso(lam=0.1).fit(X, y)
    np.testing.assert_array_equal(la.coef, lb.coef)

def test_lasso_kkt_with_correlated_features() -> None:
    """强相关特征下坐标下降仍应满足 KKT（收敛到同一子问题解）。"""
    rng = np.random.default_rng(5)
    x1 = rng.normal(size=150)
    x2 = x1 + 0.05 * rng.normal(size=150)
    X = np.column_stack([x1, x2])
    y = 2.0 * x1 + 2.0 * x2 + rng.normal(0.0, 0.2, 150)
    model = Lasso(lam=0.05, max_iter=20000, tol=1e-12).fit(X, y)

    xm = X.mean(0)
    Xc = X - xm
    r = Xc @ model.coef + model.intercept - y
    grad = Xc.T @ r / len(y)
    for j, w in enumerate(model.coef):
        if abs(w) > 1e-7:
            assert abs(grad[j] + 0.05 * np.sign(w)) < 1e-4
        else:
            assert abs(grad[j]) <= 0.05 + 1e-4


class _FoldSpy:
    """记录训练集样本；若在预测时看到训练样本就报错——用来抓 CV 泄漏。"""

    def fit(self, X, y):
        self.seen = {tuple(np.round(row, 12)) for row in X}
        return self

    def predict(self, X):
        for row in X:
            assert tuple(np.round(row, 12)) not in self.seen, "验证折样本出现在训练集中"
        return np.zeros(len(X))


def test_cv_never_predicts_on_training_rows() -> None:
    X, y = make_data()
    _, folds = cross_val_mse(_FoldSpy, X, y, k=5, seed=0)
    assert len(folds) == 5
    assert all(np.isfinite(f) for f in folds)

