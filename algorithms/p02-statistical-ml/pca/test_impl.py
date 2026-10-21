"""PCA — 性质测试（pytest）

用法（本目录内）：uv run pytest test_impl.py -q

覆盖：
- 主成分正交、按方差降序
- 方差占比和为 1；前 k 个占比等于特征值占比
- k=2 无损重建；k=1 的重建误差等于被丢掉的方差
- 浮点 n_components（方差占比）选出的 k
- 标准化改变载荷；whiten 后各维方差≈1
- 符号约定可复现；契约
"""

import numpy as np
import pytest
from impl import PCA


def correlated(n: int = 300, rho: float = 0.9, seed: int = 0):
    rng = np.random.default_rng(seed)
    return rng.multivariate_normal([0.0, 0.0], [[1.0, rho], [rho, 1.0]], size=n)


def test_components_orthonormal_and_sorted() -> None:
    X = correlated()
    pca = PCA(n_components=2).fit(X)
    C = pca.components_
    np.testing.assert_allclose(C @ C.T, np.eye(2), atol=1e-12)
    assert np.all(np.diff(pca.explained_variance_) <= 1e-12)
    assert pca.explained_variance_ratio_.sum() == pytest.approx(1.0)


def test_first_component_direction() -> None:
    X = correlated()
    pca = PCA(n_components=1).fit(X)
    assert abs(pca.components_[0, 0]) == pytest.approx(1 / np.sqrt(2), abs=0.02)
    assert abs(pca.components_[0, 1]) == pytest.approx(1 / np.sqrt(2), abs=0.02)
    assert pca.explained_variance_ratio_[0] > 0.9


def test_reconstruction_error_equals_discarded_variance() -> None:
    X = correlated()
    pca = PCA(n_components=1).fit(X)
    Z = pca.transform(X)
    Xr = pca.inverse_transform(Z)
    mse = float(np.mean((X - Xr) ** 2))
    full = PCA().fit(X)
    # 被丢弃的方差按样本平均、再除以特征数（MSE 是逐元素平均）
    expected = float(full.explained_variance_[1] * (len(X) - 1) / len(X) / X.shape[1])
    assert mse == pytest.approx(expected, rel=1e-9)


def test_full_reconstruction() -> None:
    X = correlated()
    pca = PCA().fit(X)
    Xr = pca.inverse_transform(pca.transform(X))
    np.testing.assert_allclose(X, Xr, atol=1e-12)


def test_float_n_components_variance_target() -> None:
    X = correlated()
    pca = PCA(n_components=0.9).fit(X)
    assert pca.components_.shape[0] == 1
    full = PCA().fit(X)
    assert pca.explained_variance_ratio_[0] >= 0.9
    assert full.explained_variance_ratio_[0] >= 0.9


def test_standardize_changes_loadings() -> None:
    rng = np.random.default_rng(0)
    t = rng.normal(size=400)
    X = np.c_[10 * t + rng.normal(scale=0.5, size=400),
              t + rng.normal(scale=0.5, size=400)]
    raw = PCA(n_components=1).fit(X)
    std = PCA(n_components=1, standardize=True).fit(X)
    assert abs(raw.components_[0, 0]) > 0.95
    assert min(abs(std.components_[0])) > 0.6


def test_whiten() -> None:
    X = correlated()
    pca = PCA(n_components=2, whiten=True).fit(X)
    Z = pca.transform(X)
    assert np.allclose(Z.var(axis=0, ddof=1), 1.0, atol=1e-6)


def test_determinism_and_sign_convention() -> None:
    X = correlated()
    a = PCA(n_components=2).fit(X)
    b = PCA(n_components=2).fit(X)
    np.testing.assert_array_equal(a.components_, b.components_)
    for row in a.components_:
        assert row[np.argmax(np.abs(row))] > 0


def test_invalid_inputs() -> None:
    X = correlated()
    with pytest.raises(ValueError):
        PCA(n_components=0)
    with pytest.raises(ValueError):
        PCA(n_components=1.5)
    with pytest.raises(ValueError):
        PCA(n_components=-0.1)
    with pytest.raises(ValueError):
        PCA().fit(X[:, 0])
    with pytest.raises(ValueError):
        PCA().fit(X[:1])
    bad = X.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        PCA().fit(bad)


def test_transform_before_fit() -> None:
    X = correlated()
    with pytest.raises(RuntimeError):
        PCA().transform(X)
