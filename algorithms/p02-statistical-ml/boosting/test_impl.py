"""Boosting / GBDT — 性质测试（pytest）

用法（本目录内）：uv run pytest test_impl.py -q

覆盖：
- 单棵回归树能拟合阶梯函数
- 加法模型：训练 MSE 随轮数单调下降；学习率越小、固定树数下拟合越不足
- 早停：树数被截断、`best_iteration_` 与 `val_score_` 对齐
- `staged_predict` 的长度与逐轮预测
- 与 sklearn 同参数下的测试 MSE 接近
- 重要性归一且能识别真特征
- 确定性与数据契约
"""

import numpy as np
import pytest
from impl import AdaBoostClassifier, GradientBoostingClassifier, GradientBoostingRegressor


def make_1d(n: int = 160, noise: float = 0.15, seed: int = 0):
    rng = np.random.default_rng(seed)
    x = rng.uniform(-3.0, 3.0, n)
    y = np.sin(x) + noise * rng.normal(size=n)
    from sklearn.model_selection import train_test_split
    return train_test_split(x[:, None], y, test_size=0.3, random_state=0)


def make_multi(n: int = 300, p: int = 8, informative: int = 3):
    from sklearn.datasets import make_regression
    X, y = make_regression(n_samples=n, n_features=p, n_informative=informative,
                           noise=8.0, shuffle=False, random_state=0)
    return X, y


def mse(y, p) -> float:
    return float(np.mean((np.asarray(y) - np.asarray(p)) ** 2))


# ---------------------------------------------------------------- 基础拟合

def test_boosting_reduces_training_mse() -> None:
    X_tr, _, y_tr, _ = make_1d()
    model = GradientBoostingRegressor(n_estimators=60, learning_rate=0.1,
                                      random_state=0).fit(X_tr, y_tr)
    base = mse(y_tr, np.full(len(y_tr), y_tr.mean()))
    scores = [mse(y_tr, p) for p in model.staged_predict(X_tr)]
    assert scores[0] == pytest.approx(base)
    assert scores[-1] < base * 0.1
    assert all(scores[i] >= scores[i + 1] - 1e-12 for i in range(len(scores) - 1))


def test_learning_rate_effect() -> None:
    X_tr, _, y_tr, _ = make_1d()
    slow = GradientBoostingRegressor(n_estimators=50, learning_rate=0.01,
                                     random_state=0).fit(X_tr, y_tr)
    fast = GradientBoostingRegressor(n_estimators=50, learning_rate=0.5,
                                     random_state=0).fit(X_tr, y_tr)
    assert mse(y_tr, slow.predict(X_tr)) > mse(y_tr, fast.predict(X_tr))


def test_staged_predict_length() -> None:
    X_tr, _, y_tr, _ = make_1d()
    model = GradientBoostingRegressor(n_estimators=25, random_state=0).fit(X_tr, y_tr)
    stages = list(model.staged_predict(X_tr))
    assert len(stages) == len(model.trees) + 1
    assert stages[-1] == pytest.approx(model.predict(X_tr))


# ---------------------------------------------------------------- 早停

def test_early_stopping_truncates() -> None:
    X_tr, X_te, y_tr, y_te = make_1d()
    from sklearn.model_selection import train_test_split
    X_sub, X_val, y_sub, y_val = train_test_split(X_tr, y_tr, test_size=0.25,
                                                  random_state=0)
    model = GradientBoostingRegressor(n_estimators=300, learning_rate=0.05,
                                      random_state=0).fit(
        X_sub, y_sub, eval_set=(X_val, y_val), early_stopping_rounds=5)
    assert model.best_iteration_ is not None
    assert len(model.trees) < 300
    assert len(model.trees) == model.best_iteration_
    assert len(model.val_score_) == len(model.trees)
    assert min(model.val_score_) <= model.val_score_[-1] + 1e-12
    assert np.isfinite(mse(y_te, model.predict(X_te)))


# ---------------------------------------------------------------- 对照

def test_matches_sklearn() -> None:
    from framework import fit_gbr
    X_tr, X_te, y_tr, y_te = make_1d()
    hand = GradientBoostingRegressor(n_estimators=60, learning_rate=0.1,
                                     max_depth=3, random_state=0).fit(X_tr, y_tr)
    sk = fit_gbr(X_tr, y_tr, n_estimators=60)
    assert abs(mse(y_te, hand.predict(X_te)) - mse(y_te, sk.predict(X_te))) < 0.02


def test_importance_top_informative() -> None:
    X, y = make_multi()
    model = GradientBoostingRegressor(n_estimators=120, learning_rate=0.1,
                                      random_state=0).fit(X, y)
    imp = model.feature_importances_
    assert imp.sum() == pytest.approx(1.0)
    assert set(np.argsort(-imp)[:3].tolist()) == {0, 1, 2}


# ---------------------------------------------------------------- 契约

def test_determinism() -> None:
    X_tr, _, y_tr, _ = make_1d()
    a = GradientBoostingRegressor(n_estimators=30, subsample=0.8, random_state=0).fit(X_tr, y_tr)
    b = GradientBoostingRegressor(n_estimators=30, subsample=0.8, random_state=0).fit(X_tr, y_tr)
    np.testing.assert_allclose(a.predict(X_tr), b.predict(X_tr))


def test_invalid_params() -> None:
    with pytest.raises(ValueError):
        GradientBoostingRegressor(n_estimators=0)
    with pytest.raises(ValueError):
        GradientBoostingRegressor(learning_rate=0)
    with pytest.raises(ValueError):
        GradientBoostingRegressor(max_depth=0)
    with pytest.raises(ValueError):
        GradientBoostingRegressor(subsample=0)
    with pytest.raises(ValueError):
        GradientBoostingRegressor(subsample=1.5)


def test_invalid_data() -> None:
    X, y = make_multi()
    with pytest.raises(ValueError):
        GradientBoostingRegressor().fit(X[:, 0], y)
    with pytest.raises(ValueError):
        GradientBoostingRegressor().fit(X, y[:-1])
    bad = X.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        GradientBoostingRegressor().fit(bad, y)


def test_predict_before_fit() -> None:
    X, _ = make_multi()
    with pytest.raises(RuntimeError):
        GradientBoostingRegressor().predict(X)


# ---------------------------------------------------------------- 分类扩展

def make_binary():
    from sklearn.datasets import load_breast_cancer
    from sklearn.model_selection import train_test_split
    X, y = load_breast_cancer(return_X_y=True)
    return train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)


def test_adaboost_accuracy() -> None:
    X_tr, X_te, y_tr, y_te = make_binary()
    m = AdaBoostClassifier(n_estimators=50, random_state=0).fit(X_tr, y_tr)
    assert (m.predict(X_te) == y_te).mean() > 0.9
    assert len(list(m.staged_predict(X_te))) == len(m.estimators_)


def test_gbdt_classifier_accuracy() -> None:
    X_tr, X_te, y_tr, y_te = make_binary()
    m = GradientBoostingClassifier(n_estimators=50, random_state=0).fit(X_tr, y_tr)
    assert (m.predict(X_te) == y_te).mean() > 0.9
    p = m.predict_proba(X_te)
    np.testing.assert_allclose(p.sum(1), 1.0)
    assert m.train_score_[-1] < m.train_score_[0]


def test_classifier_matches_sklearn() -> None:
    from sklearn.ensemble import AdaBoostClassifier as SkAda
    from sklearn.ensemble import GradientBoostingClassifier as SkGB
    from sklearn.metrics import f1_score
    X_tr, X_te, y_tr, y_te = make_binary()
    for hand, sk in ((AdaBoostClassifier(n_estimators=50, random_state=0),
                      SkAda(n_estimators=50, random_state=0)),
                     (GradientBoostingClassifier(n_estimators=50, random_state=0),
                      SkGB(n_estimators=50, random_state=0))):
        hand.fit(X_tr, y_tr)
        sk.fit(X_tr, y_tr)
        f_hand = f1_score(y_te, hand.predict(X_te))
        f_sk = f1_score(y_te, sk.predict(X_te))
        assert abs(f_hand - f_sk) <= 0.08


def test_classifier_contracts() -> None:
    X_tr, X_te, _, _ = make_binary()
    with pytest.raises(ValueError):
        AdaBoostClassifier().fit(X_tr, np.ones(len(X_tr)))
    with pytest.raises(ValueError):
        GradientBoostingClassifier(n_estimators=0)
    with pytest.raises(RuntimeError):
        AdaBoostClassifier().predict(X_te)
    with pytest.raises(RuntimeError):
        GradientBoostingClassifier().predict_proba(X_te)
