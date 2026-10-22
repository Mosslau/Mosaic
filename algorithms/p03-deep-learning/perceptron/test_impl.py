"""感知机 — 性质测试（pytest）

覆盖：
- 线性可分：最后一轮零错误、训练/测试 100%
- 线性不可分：误差不归零、准确率接近随机
- 在线更新规则（单样本可手算）
- sign(0)=+1 的约定
- 标准化与 raw_coef/margin
- 样本顺序敏感性
- 与 sklearn 的准确率对齐
- 契约（标签、形状、NaN、未训练）
"""

import numpy as np
import pytest
from impl import Perceptron


def separable(n=160, seed=0):
    from sklearn.datasets import make_blobs
    from sklearn.model_selection import train_test_split
    X, y = make_blobs(n_samples=n, centers=[[-1.5, -1.5], [1.5, 1.5]],
                      cluster_std=0.5, random_state=seed)
    y = np.where(y == 1, 1, -1)
    return train_test_split(X, y, test_size=0.3, random_state=seed, stratify=y)


def xor(n=200, seed=1):
    rng = np.random.default_rng(seed)
    centers = np.array([[-1, -1], [-1, 1], [1, -1], [1, 1]])
    labels = np.array([-1, 1, 1, -1])
    X = np.vstack([c + rng.normal(0, 0.35, size=(n // 4, 2)) for c in centers])
    return X, np.repeat(labels, n // 4)


def test_separable_converges() -> None:
    X_tr, X_te, y_tr, y_te = separable()
    model = Perceptron(lr=0.1, epochs=50, random_state=0).fit(X_tr, y_tr)
    assert model.errors_per_epoch[-1] == 0
    assert np.mean(model.predict(X_tr) == y_tr) == 1.0
    assert np.mean(model.predict(X_te) == y_te) == 1.0
    assert model.epochs_run == len(model.errors_per_epoch)


def test_xor_does_not_converge() -> None:
    X, y = xor()
    model = Perceptron(lr=0.1, epochs=100, random_state=0).fit(X, y)
    assert model.errors_per_epoch[-1] > 0
    assert np.mean(model.predict(X) == y) < 0.8
    assert len(set(model.errors_per_epoch)) > 1


def test_update_rule_one_sample() -> None:
    X = np.array([[1.0, 0.0]])
    y = np.array([1.0])
    model = Perceptron(lr=1.0, epochs=1, random_state=0, standardize=False).fit(X, y)
    np.testing.assert_allclose(model.w, [1.0, 0.0])
    assert model.b == 1.0
    assert model.predict(X)[0] == 1


def test_sign_zero_is_positive() -> None:
    model = Perceptron(standardize=False)
    model.w = np.zeros(2)
    model.b = 0.0
    assert model.predict(np.array([[3.0, 4.0]]))[0] == 1


def test_standardization_and_margin() -> None:
    X_tr, _, y_tr, _ = separable()
    raw = Perceptron(lr=0.1, epochs=20, random_state=0, standardize=False).fit(X_tr, y_tr)
    std = Perceptron(lr=0.1, epochs=20, random_state=0, standardize=True).fit(X_tr, y_tr)
    assert raw.raw_coef.shape == (2,)
    assert std.raw_coef.shape == (2,)
    assert std.margin > 0


def test_order_sensitivity() -> None:
    X_tr, _, y_tr, _ = separable()
    margins = [Perceptron(lr=0.1, epochs=50, random_state=s).fit(X_tr, y_tr).margin
               for s in range(8)]
    assert np.std(margins) > 0.01


def test_matches_sklearn_accuracy() -> None:
    from framework import fit_perceptron
    X_tr, X_te, y_tr, y_te = separable()
    hand = Perceptron(lr=0.1, epochs=50, random_state=0).fit(X_tr, y_tr)
    sk = fit_perceptron(X_tr, y_tr, lr=0.1, epochs=50)
    assert abs(np.mean(hand.predict(X_te) == y_te)
               - np.mean(sk.predict(X_te) == y_te)) < 0.02


def test_torch_matches_hand() -> None:
    pytest.importorskip("torch")
    from framework import fit_torch_perceptron
    X_tr, X_te, y_tr, y_te = separable()
    hand = Perceptron(lr=0.1, epochs=50, random_state=0).fit(X_tr, y_tr)
    torch_model = fit_torch_perceptron(X_tr, y_tr, lr=0.1, epochs=50)
    assert torch_model.epochs_run == hand.epochs_run
    assert torch_model.errors_per_epoch == hand.errors_per_epoch
    assert np.mean(torch_model.predict(X_te) == y_te) == 1.0
    np.testing.assert_allclose(torch_model.coef_, hand.w, atol=1e-6)


def test_determinism() -> None:
    X_tr, _, y_tr, _ = separable()
    a = Perceptron(lr=0.1, epochs=30, random_state=7).fit(X_tr, y_tr)
    b = Perceptron(lr=0.1, epochs=30, random_state=7).fit(X_tr, y_tr)
    np.testing.assert_array_equal(a.w, b.w)
    assert a.b == b.b
    assert a.errors_per_epoch == b.errors_per_epoch


def test_invalid_inputs() -> None:
    X, y = xor()
    with pytest.raises(ValueError):
        Perceptron(lr=0)
    with pytest.raises(ValueError):
        Perceptron(epochs=0)
    with pytest.raises(ValueError):
        Perceptron().fit(X, np.where(y > 0, 2, 0))
    with pytest.raises(ValueError):
        Perceptron().fit(X[:, 0], y)
    with pytest.raises(ValueError):
        Perceptron().fit(X, y[:-1])
    bad = X.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        Perceptron().fit(bad, y)


def test_predict_before_fit() -> None:
    X, _ = xor()
    with pytest.raises(RuntimeError):
        Perceptron().predict(X)
