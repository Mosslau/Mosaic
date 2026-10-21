"""决策树 ID3/CART — 性质测试（pytest）

用法（本目录内）：uv run pytest test_impl.py -q

覆盖：
- 熵/基尼的已知值（纯节点、二分类均衡、多分类）
- 一维数据上的最优切分点与递归划分
- max_depth / min_samples_leaf / min_samples_split 的约束
- ccp_alpha 剪枝：叶子减少、根仍是同一棵树
- predict_proba 归一、与 predict 一致
- 特征重要性：有信息特征 > 噪声特征
- 与 sklearn 同参数下的叶子数一致（划分准则对齐）
- 确定性与数据契约
"""

import numpy as np
import pytest
from impl import DecisionTree, entropy, gini


def make_moons(n: int = 200, seed: int = 0):
    from sklearn.datasets import make_moons
    return make_moons(n_samples=n, noise=0.25, random_state=seed)


# ---------------------------------------------------------------- 不纯度

def test_entropy_known() -> None:
    assert entropy(np.array([0, 0, 0])) == 0.0
    assert entropy(np.array([0, 1])) == pytest.approx(1.0)
    assert entropy(np.array([0, 0, 1, 1])) == pytest.approx(1.0)
    assert entropy(np.array([0, 1, 2])) == pytest.approx(np.log2(3))


def test_gini_known() -> None:
    assert gini(np.array([0, 0, 0])) == 0.0
    assert gini(np.array([0, 1])) == pytest.approx(0.5)
    assert gini(np.array([0, 0, 1, 1])) == pytest.approx(0.5)
    assert gini(np.array([0, 1, 2])) == pytest.approx(2.0 / 3.0)


# ---------------------------------------------------------------- 划分

def test_single_feature_split() -> None:
    X = np.array([[0.0], [0.1], [0.2], [0.9], [1.0], [1.1]])
    y = np.array([0, 0, 0, 1, 1, 1])
    tree = DecisionTree().fit(X, y)
    assert tree.get_n_leaves() == 2
    assert 0.2 < tree.root["threshold"] < 0.9
    np.testing.assert_array_equal(tree.predict(X), y)


def test_pure_node_is_leaf() -> None:
    X = np.array([[0.0], [1.0], [2.0]])
    y = np.array([1, 1, 1])
    tree = DecisionTree().fit(X, y)
    assert tree.get_depth() == 0
    assert tree.get_n_leaves() == 1


def test_depth_limit() -> None:
    X, y = make_moons()
    for depth in (1, 2, 3, 4):
        tree = DecisionTree(max_depth=depth).fit(X, y)
        assert tree.get_depth() <= depth


def test_min_samples_leaf_respected() -> None:
    X, y = make_moons()
    leaf = 12
    tree = DecisionTree(min_samples_leaf=leaf).fit(X, y)

    def walk(node):
        if "feature" not in node:
            assert node["n"] >= leaf
            return
        walk(node["left"])
        walk(node["right"])

    walk(tree.root)


def test_min_samples_split() -> None:
    X, y = make_moons()
    tree = DecisionTree(min_samples_split=1000).fit(X, y)
    assert tree.get_depth() == 0


# ---------------------------------------------------------------- 剪枝

def test_pruning_reduces_leaves() -> None:
    X, y = make_moons()
    full = DecisionTree().fit(X, y)
    pruned = DecisionTree(ccp_alpha=0.02).fit(X, y)
    assert pruned.get_n_leaves() < full.get_n_leaves()
    assert pruned.get_depth() <= full.get_depth()


def test_pruning_keeps_predictions_shape() -> None:
    X, y = make_moons()
    tree = DecisionTree(ccp_alpha=0.05).fit(X, y)
    pred = tree.predict(X)
    assert pred.shape == y.shape
    assert set(np.unique(pred)).issubset(set(np.unique(y)))


# ---------------------------------------------------------------- 输出

def test_predict_proba_normalized() -> None:
    X, y = make_moons()
    tree = DecisionTree(max_depth=3).fit(X, y)
    proba = tree.predict_proba(X)
    assert np.allclose(proba.sum(axis=1), 1.0)
    assert np.array_equal(tree.classes_[np.argmax(proba, axis=1)], tree.predict(X))


def test_feature_importance_and_determinism() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 3))
    X[:, 2] = rng.normal(size=200)              # 第 3 列是噪声
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    a = DecisionTree(max_depth=3).fit(X, y)
    b = DecisionTree(max_depth=3).fit(X, y)
    np.testing.assert_allclose(a.feature_importances_, b.feature_importances_)
    assert a.feature_importances_.sum() == pytest.approx(1.0)
    assert a.feature_importances_[2] < max(a.feature_importances_[0], a.feature_importances_[1])


def test_matches_sklearn_leaves() -> None:
    from framework import fit_tree
    X, y = make_moons()
    for depth in (2, 4, None):
        hand = DecisionTree(max_depth=depth).fit(X, y)
        sk = fit_tree(X, y, max_depth=depth)
        assert hand.get_n_leaves() == sk.get_n_leaves()
        assert hand.get_depth() == sk.get_depth()
        assert np.mean(hand.predict(X) == sk.predict(X)) > 0.98


# ---------------------------------------------------------------- 契约

def test_invalid_inputs() -> None:
    X, y = make_moons()
    with pytest.raises(ValueError):
        DecisionTree(criterion="logloss")
    with pytest.raises(ValueError):
        DecisionTree(max_depth=0)
    with pytest.raises(ValueError):
        DecisionTree(min_samples_split=1)
    with pytest.raises(ValueError):
        DecisionTree().fit(X[:, 0], y)
    with pytest.raises(ValueError):
        DecisionTree().fit(X, y[:-1])
    bad = X.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        DecisionTree().fit(bad, y)


def test_predict_before_fit() -> None:
    X, _ = make_moons()
    with pytest.raises(RuntimeError):
        DecisionTree().predict(X)
