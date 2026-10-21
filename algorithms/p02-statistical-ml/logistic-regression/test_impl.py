"""逻辑回归 — 性质测试（pytest）

用法（本目录内）：uv run pytest test_impl.py -q

覆盖：
- sigmoid：极端值不溢出、对称性、单调性
- 梯度：解析梯度 vs 中心差分
- 收敛：可分数据上准确率 1.0、损失趋近 0；系数方向正确
- 指标：BCE 已知值、混淆矩阵/精确率/召回率、AUC 的三种极端情形
- 阈值：同一模型换阈值只改预测标签，不改概率
- 类别权重：balanced 提升少数类召回
- 数据契约：y 非 0/1、维度/长度/空/NaN、非法阈值与 class_weight
- 确定性：同数据同参数两次训练完全一致
"""

import numpy as np
import pytest
from impl import (
    Model,
    accuracy,
    binary_cross_entropy,
    confusion,
    f1,
    precision,
    recall,
    roc_auc,
    sigmoid,
)


def make_data(n: int = 200, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3))
    logits = X @ np.array([1.2, -0.8, 0.5]) + 0.3
    y = (rng.random(n) < sigmoid(logits)).astype(float)
    return X, y


def make_separable(n: int = 120, seed: int = 1):
    rng = np.random.default_rng(seed)
    X0 = rng.normal([-2.0, -1.0], 0.4, size=(n // 2, 2))
    X1 = rng.normal([2.0, 1.0], 0.4, size=(n - n // 2, 2))
    X = np.vstack([X0, X1])
    y = np.array([0.0] * (n // 2) + [1.0] * (n - n // 2))
    return X, y


# ---------------------------------------------------------------- sigmoid

def test_sigmoid_is_stable() -> None:
    z = np.array([-1000.0, -50.0, 0.0, 50.0, 1000.0])
    out = sigmoid(z)
    assert np.all(np.isfinite(out))
    assert out[0] == 0.0 and out[-1] == 1.0
    assert out[2] == 0.5
    assert np.all(np.diff(out) >= 0)          # 饱和后相等（float 分辨率），不应下降
    z_mid = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    assert np.all(np.diff(sigmoid(z_mid)) > 0)


def test_sigmoid_symmetry() -> None:
    z = np.array([-3.0, -0.5, 0.0, 0.5, 3.0])
    np.testing.assert_allclose(sigmoid(-z), 1.0 - sigmoid(z), atol=1e-15)


# ---------------------------------------------------------------- 梯度

def test_gradient_matches_finite_difference() -> None:
    X, y = make_data()
    mu, sigma = X.mean(0), X.std(0)
    Xs = (X - mu) / sigma
    w = np.array([0.4, -0.3, 0.2])
    b = -0.1
    z = Xs @ w + b
    p = sigmoid(z)
    grad_w = Xs.T @ (p - y) / len(y)
    grad_b = float(np.mean(p - y))

    eps = 1e-6
    num_w = np.zeros_like(w)
    for i in range(w.size):
        wp, wm = w.copy(), w.copy()
        wp[i] += eps
        wm[i] -= eps
        lp = np.mean(np.logaddexp(0.0, Xs @ wp + b) - y * (Xs @ wp + b))
        lm = np.mean(np.logaddexp(0.0, Xs @ wm + b) - y * (Xs @ wm + b))
        num_w[i] = (lp - lm) / (2 * eps)
    lb_p = np.mean(np.logaddexp(0.0, z + eps) - y * (z + eps))
    lb_m = np.mean(np.logaddexp(0.0, z - eps) - y * (z - eps))
    num_b = (lb_p - lb_m) / (2 * eps)

    np.testing.assert_allclose(grad_w, num_w, rtol=1e-6, atol=1e-8)
    assert abs(grad_b - num_b) < 1e-8


# ---------------------------------------------------------------- 收敛

def test_converges_on_separable_data() -> None:
    X, y = make_separable()
    model = Model(lr=0.5, epochs=5000, tol=1e-12).fit(X, y)
    assert accuracy(y, model.predict(X)) == 1.0
    assert model.loss_history[-1] < 0.05
    assert model.raw_coef[0] > 0 and model.raw_coef[1] > 0


def test_training_reduces_loss_monotonically() -> None:
    X, y = make_data()
    model = Model(lr=0.5, epochs=300, tol=0.0).fit(X, y)
    losses = np.asarray(model.loss_history)
    assert np.all(np.diff(losses) <= 1e-12)


def test_larger_lr_converges_faster_until_instability() -> None:
    X, y = make_data()
    slow = Model(lr=0.01, epochs=3000, tol=1e-10).fit(X, y)
    fast = Model(lr=0.5, epochs=3000, tol=1e-10).fit(X, y)
    assert fast.epochs_run < slow.epochs_run


# ---------------------------------------------------------------- 指标

def test_bce_known_values() -> None:
    y = np.array([0.0, 1.0])
    assert binary_cross_entropy(y, np.array([0.0, 1.0])) == pytest.approx(0.0, abs=1e-12)
    assert binary_cross_entropy(y, np.array([0.5, 0.5])) == pytest.approx(np.log(2))


def test_confusion_metrics() -> None:
    y = np.array([1, 1, 0, 0, 1])
    pred = np.array([1, 0, 0, 1, 1])
    assert confusion(y, pred) == (2, 1, 1, 1)
    assert precision(y, pred) == pytest.approx(2 / 3)
    assert recall(y, pred) == pytest.approx(2 / 3)
    assert f1(y, pred) == pytest.approx(2 / 3)
    assert accuracy(y, pred) == pytest.approx(3 / 5)


def test_roc_auc_extremes() -> None:
    y = np.array([0, 0, 1, 1])
    assert roc_auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert roc_auc(y, np.array([0.9, 0.8, 0.2, 0.1])) == pytest.approx(0.0)
    assert roc_auc(y, np.array([0.5, 0.5, 0.5, 0.5])) == pytest.approx(0.5)


def test_threshold_only_changes_labels() -> None:
    X, y = make_data()
    low = Model(lr=0.5, epochs=1000, threshold=0.2).fit(X, y)
    high = Model(lr=0.5, epochs=1000, threshold=0.8).fit(X, y)
    np.testing.assert_allclose(low.predict_proba(X), high.predict_proba(X))
    assert low.predict(X).sum() >= high.predict(X).sum()


def test_class_weight_balanced_improves_recall() -> None:
    rng = np.random.default_rng(7)
    X = np.vstack([rng.normal([-1, 0], 1, size=(600, 2)),
                   rng.normal([1.2, 0], 1, size=(60, 2))])
    y = np.array([0.0] * 600 + [1.0] * 60)
    plain = Model(lr=0.5, epochs=3000, tol=1e-10).fit(X, y)
    balanced = Model(lr=0.5, epochs=3000, tol=1e-10,
                     class_weight="balanced").fit(X, y)
    assert recall(y, balanced.predict(X)) > recall(y, plain.predict(X))


# ---------------------------------------------------------------- 数据契约

def test_predict_before_fit_raises() -> None:
    with pytest.raises(RuntimeError):
        Model().predict_proba(np.zeros((2, 2)))


def test_invalid_inputs_raise() -> None:
    X, y = make_data()
    with pytest.raises(ValueError):
        Model().fit(X[:, 0], y)                 # X 一维
    with pytest.raises(ValueError):
        Model().fit(X, y[:-1])                  # 长度不一致
    with pytest.raises(ValueError):
        Model().fit(np.empty((0, 3)), np.empty(0))
    with pytest.raises(ValueError):
        Model().fit(X, y + 2)                   # y 不是 0/1
    bad = X.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        Model().fit(bad, y)
    with pytest.raises(ValueError):
        Model(lr=0.0)
    with pytest.raises(ValueError):
        Model(epochs=0)
    with pytest.raises(ValueError):
        Model(threshold=1.0)
    with pytest.raises(ValueError):
        Model(class_weight="unknown")


def test_predict_shape_checked() -> None:
    X, y = make_data()
    model = Model(epochs=10).fit(X, y)
    with pytest.raises(ValueError):
        model.predict_proba(X[:, :2])
    with pytest.raises(ValueError):
        model.predict(X[0])


# ---------------------------------------------------------------- 确定性

def test_training_is_deterministic() -> None:
    X, y = make_data()
    a = Model(lr=0.5, epochs=200).fit(X, y)
    b = Model(lr=0.5, epochs=200).fit(X, y)
    np.testing.assert_array_equal(a.w, b.w)
    assert a.b == b.b
    assert a.loss_history == b.loss_history
