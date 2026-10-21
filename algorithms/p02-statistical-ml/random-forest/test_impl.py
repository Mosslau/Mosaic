"""随机森林 — 性质测试（pytest）

用法（本目录内）：uv run pytest test_impl.py -q

覆盖：
- bootstrap 的未入袋比例 ≈ 1/e ≈ 0.368
- max_features 的四种口径（sqrt / log2 / int / None）
- 森林 vs 单树：准确率提升、跨种子方差下降
- OOB：`oob_score_` 与 `oob_score(X, y)` 一致，且与测试准确率同量级
- 概率归一、特征重要性归一且能识别真特征
- 确定性与数据契约
"""

import numpy as np
import pytest
from impl import RandomForest


def moons(n: int = 300, seed: int = 0):
    from sklearn.datasets import make_moons
    X, y = make_moons(n_samples=n, noise=0.25, random_state=seed)
    from sklearn.model_selection import train_test_split
    return train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)


def informative(n: int = 300, p: int = 10, k: int = 3):
    from sklearn.datasets import make_classification
    X, y = make_classification(n_samples=n, n_features=p, n_informative=k,
                               n_redundant=0, n_repeated=0, shuffle=False,
                               random_state=0)
    return X, y


def acc(y, p) -> float:
    return float(np.mean(np.asarray(y) == np.asarray(p)))


# ---------------------------------------------------------------- 随机性

def test_oob_fraction_near_one_over_e() -> None:
    X_tr, _, y_tr, _ = moons()
    forest = RandomForest(n_trees=40, random_state=0).fit(X_tr, y_tr)
    frac = float(np.mean([m.mean() for m in forest._oob_masks]))
    assert abs(frac - 1 / np.e) < 0.03


def test_max_features_resolution() -> None:
    p = 12
    assert RandomForest(max_features="sqrt")._resolve_max_features(p) == int(np.sqrt(p))
    assert RandomForest(max_features="log2")._resolve_max_features(p) == int(np.log2(p))
    assert RandomForest(max_features=4)._resolve_max_features(p) == 4
    assert RandomForest(max_features=None)._resolve_max_features(p) == p
    assert RandomForest(max_features=0.5)._resolve_max_features(p) == 6


# ---------------------------------------------------------------- 集成效果

def test_forest_beats_single_tree() -> None:
    X_tr, X_te, y_tr, y_te = moons()
    single = RandomForest(n_trees=1, max_features=None, random_state=0).fit(X_tr, y_tr)
    forest = RandomForest(n_trees=60, random_state=0).fit(X_tr, y_tr)
    assert acc(y_te, forest.predict(X_te)) >= acc(y_te, single.predict(X_te)) - 0.01


def test_forest_variance_smaller_than_single() -> None:
    X_tr, X_te, y_tr, y_te = moons()
    single, forest = [], []
    for seed in range(6):
        s = RandomForest(n_trees=1, max_features=None, random_state=seed).fit(X_tr, y_tr)
        f = RandomForest(n_trees=60, random_state=seed).fit(X_tr, y_tr)
        single.append(acc(y_te, s.predict(X_te)))
        forest.append(acc(y_te, f.predict(X_te)))
    assert np.std(forest) < np.std(single)
    assert np.mean(forest) > np.mean(single)


# ---------------------------------------------------------------- OOB

def test_oob_score_matches_attribute_and_test() -> None:
    X_tr, X_te, y_tr, y_te = moons()
    forest = RandomForest(n_trees=60, random_state=0).fit(X_tr, y_tr)
    assert forest.oob_score_ is not None and np.isfinite(forest.oob_score_)
    assert forest.oob_score(X_tr, y_tr) == pytest.approx(forest.oob_score_)
    assert abs(forest.oob_score_ - acc(y_te, forest.predict(X_te))) < 0.12
    with pytest.raises(ValueError):
        forest.oob_score(X_tr[:-1], y_tr[:-1])


# ---------------------------------------------------------------- 输出

def test_predict_proba_normalized() -> None:
    X_tr, X_te, y_tr, y_te = moons()
    forest = RandomForest(n_trees=40, random_state=0).fit(X_tr, y_tr)
    proba = forest.predict_proba(X_te)
    assert np.allclose(proba.sum(axis=1), 1.0)
    np.testing.assert_array_equal(forest.classes_[np.argmax(proba, axis=1)],
                                  forest.predict(X_te))


def test_feature_importance_identifies_informative() -> None:
    X, y = informative()
    forest = RandomForest(n_trees=80, random_state=0).fit(X, y)
    imp = forest.feature_importances_
    assert imp.sum() == pytest.approx(1.0)
    assert set(np.argsort(-imp)[:3].tolist()) == {0, 1, 2}


def test_determinism_and_seed_effect() -> None:
    X_tr, X_te, y_tr, y_te = moons()
    a = RandomForest(n_trees=30, random_state=0).fit(X_tr, y_tr)
    b = RandomForest(n_trees=30, random_state=0).fit(X_tr, y_tr)
    np.testing.assert_allclose(a.predict_proba(X_te), b.predict_proba(X_te))
    c = RandomForest(n_trees=30, random_state=1).fit(X_tr, y_tr)
    assert not np.allclose(a.predict_proba(X_te), c.predict_proba(X_te))


# ---------------------------------------------------------------- 契约

def test_invalid_params() -> None:
    with pytest.raises(ValueError):
        RandomForest(n_trees=0)
    with pytest.raises(ValueError):
        RandomForest(max_depth=0)
    with pytest.raises(ValueError):
        RandomForest(max_features="bad")
    with pytest.raises(ValueError):
        RandomForest(max_features=0)
    with pytest.raises(ValueError):
        RandomForest(min_samples_leaf=0)


def test_invalid_data() -> None:
    X, y = informative()
    with pytest.raises(ValueError):
        RandomForest(n_trees=5).fit(X[:, 0], y)
    with pytest.raises(ValueError):
        RandomForest(n_trees=5).fit(X, y[:-1])
    bad = X.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        RandomForest(n_trees=5).fit(bad, y)


def test_predict_before_fit() -> None:
    X, _ = informative()
    with pytest.raises(RuntimeError):
        RandomForest().predict(X)
