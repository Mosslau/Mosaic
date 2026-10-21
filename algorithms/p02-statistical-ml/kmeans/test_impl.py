"""K-Means — 性质测试（pytest）

用法（本目录内）：uv run pytest test_impl.py -q

覆盖：
- K-Means++ 返回 k 个来自 X 的簇心、可复现
- k=1 的 inertia 等于"到均值的平方和"
- 与 sklearn 的 inertia/标签对齐；inertia 随 k 单调不增
- predict / fit_predict 一致；transform 形状
- K-Means++ 的跨种子方差小于随机初始化
- 轮廓系数：分离良好的两团接近 1，单簇为 0
- 空簇/重复点不崩；确定性与契约
"""

import numpy as np
import pytest
from impl import KMeans, kmeans_plus_plus, silhouette_score
from sklearn.datasets import make_blobs
from sklearn.metrics import adjusted_rand_score


def blobs(n: int = 240, k: int = 3, seed: int = 0):
    return make_blobs(n_samples=n, centers=k, cluster_std=0.7, random_state=seed)


def test_plus_plus_returns_points_and_reproducible() -> None:
    X, _ = blobs()
    rng1 = np.random.default_rng(0)
    rng2 = np.random.default_rng(0)
    c1 = kmeans_plus_plus(X, 3, rng1)
    c2 = kmeans_plus_plus(X, 3, rng2)
    assert c1.shape == (3, X.shape[1])
    assert all(any(np.allclose(c, x) for x in X) for c in c1)
    np.testing.assert_allclose(c1, c2)


def test_k1_equals_mean() -> None:
    X, _ = make_blobs(n_samples=100, centers=1, cluster_std=1.0, random_state=0)
    model = KMeans(n_clusters=1, n_init=1, random_state=0).fit(X)
    expected = float(np.sum((X - X.mean(axis=0)) ** 2))
    assert model.inertia_ == pytest.approx(expected, rel=1e-9)


def test_matches_sklearn_inertia() -> None:
    from framework import fit_kmeans
    X, y = blobs()
    hand = KMeans(n_clusters=3, n_init=10, random_state=0).fit(X)
    sk = fit_kmeans(X, n_clusters=3, random_state=0, n_init=10)
    assert hand.inertia_ == pytest.approx(sk.inertia_, abs=1.0)
    assert adjusted_rand_score(hand.labels_, y) > 0.9


def test_inertia_monotone_in_k() -> None:
    X, _ = blobs()
    inertias = [KMeans(n_clusters=k, n_init=5, random_state=0).fit(X).inertia_
                for k in (1, 2, 3, 4)]
    assert all(inertias[i] >= inertias[i + 1] - 1e-9 for i in range(3))


def test_predict_and_fit_predict() -> None:
    X, _ = blobs()
    model = KMeans(n_clusters=3, n_init=5, random_state=0).fit(X)
    np.testing.assert_array_equal(model.predict(X), model.labels_)
    fresh = KMeans(n_clusters=3, n_init=5, random_state=0)
    np.testing.assert_array_equal(fresh.fit_predict(X), model.labels_)
    assert model.transform(X).shape == (len(X), 3)


def test_plus_plus_lower_variance() -> None:
    X, _ = make_blobs(n_samples=400, centers=6, cluster_std=0.35, random_state=0)
    random_vals, pp_vals = [], []
    for seed in range(10):
        random_vals.append(KMeans(n_clusters=6, n_init=1, init="random",
                                  random_state=seed).fit(X).inertia_)
        pp_vals.append(KMeans(n_clusters=6, n_init=1, init="kmeans++",
                              random_state=seed).fit(X).inertia_)
    assert np.mean(pp_vals) < np.mean(random_vals)
    assert np.std(pp_vals) < np.std(random_vals)


def test_silhouette() -> None:
    X, y = make_blobs(n_samples=100, centers=2, cluster_std=0.3, random_state=0)
    assert silhouette_score(X, y) > 0.8
    assert silhouette_score(X, np.zeros(len(X), dtype=int)) == 0.0
    with pytest.raises(Exception):
        silhouette_score(X, y[:-1])


def test_duplicate_points_and_empty_clusters() -> None:
    X = np.ones((20, 2))
    model = KMeans(n_clusters=3, n_init=3, random_state=0).fit(X)
    assert np.isfinite(model.inertia_)
    assert model.inertia_ == pytest.approx(0.0)
    assert model.cluster_centers_.shape == (3, 2)


def test_determinism() -> None:
    X, _ = blobs()
    a = KMeans(n_clusters=3, n_init=5, random_state=3).fit(X)
    b = KMeans(n_clusters=3, n_init=5, random_state=3).fit(X)
    np.testing.assert_allclose(a.cluster_centers_, b.cluster_centers_)
    assert a.inertia_ == pytest.approx(b.inertia_)


def test_invalid_inputs() -> None:
    X, _ = blobs()
    with pytest.raises(ValueError):
        KMeans(n_clusters=0)
    with pytest.raises(ValueError):
        KMeans(max_iter=0)
    with pytest.raises(ValueError):
        KMeans(init="bad")
    with pytest.raises(ValueError):
        KMeans(n_clusters=len(X) + 1).fit(X)
    with pytest.raises(ValueError):
        KMeans().fit(X[:, 0])
    bad = X.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        KMeans().fit(bad)


def test_history_has_multiple_steps() -> None:
    X, _ = blobs()
    model = KMeans(n_clusters=3, n_init=10, random_state=0).fit(X)
    assert len(model.history_) >= 2
    assert model.history_[-1]["inertia"] == pytest.approx(model.inertia_)


def test_predict_before_fit() -> None:
    X, _ = blobs()
    with pytest.raises(RuntimeError):
        KMeans().predict(X)
