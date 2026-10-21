"""异常检测 — 性质测试（pytest）

覆盖：
- 孤立森林：分数范围、异常高于正常、阈值分位、确定性
- LOF：异常点 LOF 更高、novelty 打分
- KDE：正常点密度更高（负 log 密度更低）
- 阈值：predict 的异常数约等于 contamination*n
- 与 sklearn 的 AUC 对齐
- 契约
"""

import numpy as np
import pytest
from impl import KDE, LOF, IsolationForest, _c
from sklearn.metrics import roc_auc_score


def make_data(n_normal=240, n_out=30, seed=0):
    rng = np.random.default_rng(seed)
    normal = rng.normal(0, 1, size=(n_normal, 2))
    out = rng.normal([4, 4], 0.5, size=(n_out, 2))
    X_tr = normal[:200]
    X_te = np.vstack([normal[200:], out])
    y = np.array([0] * (n_normal - 200) + [1] * n_out)
    return X_tr, X_te, y


def test_correction_term() -> None:
    assert _c(1) == 0.0
    assert _c(4) == pytest.approx(1.8516, abs=1e-3)   # 文档手算的基准值
    assert _c(10) > 0
    assert _c(10) < _c(100)


def test_iforest_scores() -> None:
    X_tr, X_te, y = make_data()
    model = IsolationForest(n_trees=80, random_state=0).fit(X_tr)
    s = model.score_samples(X_te)
    assert s.min() >= 0 and s.max() <= 1
    assert s[y == 1].mean() > s[y == 0].mean()
    assert roc_auc_score(y, s) > 0.95


def test_iforest_threshold_count() -> None:
    X_tr, _, _ = make_data()
    model = IsolationForest(n_trees=80, contamination=0.1, random_state=0).fit(X_tr)
    pred = model.predict(X_tr)
    assert abs(np.sum(pred == 1) - 0.1 * len(X_tr)) <= 2
    assert model.threshold_ == pytest.approx(np.quantile(model.score_samples(X_tr), 0.9))


def test_lof_scores() -> None:
    X_tr, X_te, y = make_data()
    model = LOF(n_neighbors=20).fit(X_tr)
    s = model.score_samples(X_te)
    assert s[y == 1].mean() > s[y == 0].mean()
    assert roc_auc_score(y, s) > 0.9


def test_kde_scores() -> None:
    X_tr, X_te, y = make_data()
    model = KDE().fit(X_tr)
    s = model.score_samples(X_te)
    assert s[y == 1].mean() > s[y == 0].mean()
    assert roc_auc_score(y, s) > 0.9


def test_matches_sklearn_auc() -> None:
    from framework import fit_iforest
    X_tr, X_te, y = make_data()
    hand = IsolationForest(n_trees=100, random_state=0).fit(X_tr)
    sk = fit_iforest(X_tr)
    a = roc_auc_score(y, hand.score_samples(X_te))
    b = roc_auc_score(y, -sk.score_samples(X_te))
    assert abs(a - b) < 0.05


def test_determinism() -> None:
    X_tr, _, _ = make_data()
    a = IsolationForest(n_trees=50, random_state=7).fit(X_tr)
    b = IsolationForest(n_trees=50, random_state=7).fit(X_tr)
    np.testing.assert_allclose(a.score_samples(X_tr), b.score_samples(X_tr))


def test_invalid_inputs() -> None:
    X_tr, _, _ = make_data()
    with pytest.raises(ValueError):
        IsolationForest(n_trees=0)
    with pytest.raises(ValueError):
        IsolationForest(contamination=0)
    with pytest.raises(ValueError):
        LOF(n_neighbors=0)
    with pytest.raises(ValueError):
        KDE(contamination=0.8)
    with pytest.raises(ValueError):
        IsolationForest().fit(X_tr[:, 0])
    bad = X_tr.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        IsolationForest().fit(bad)


def test_predict_before_fit() -> None:
    X_tr, _, _ = make_data()
    with pytest.raises(RuntimeError):
        IsolationForest().predict(X_tr)
    with pytest.raises(RuntimeError):
        LOF().predict(X_tr)
    with pytest.raises(RuntimeError):
        KDE().predict(X_tr)
