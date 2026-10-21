"""线性回归与梯度下降 — 性质测试（pytest）

用法（本目录内）：uv run pytest test_impl.py -q

覆盖：
- 梯度校验：解析梯度 vs 中心差分（本实验最核心的一条）
- 最优性：手写 GD 与闭式解在同一数据上的预测/系数一致
- 收敛性：y = 3x + 2 上学到的参数接近真实值
- 数据契约：未 fit 预测、X 维度/长度/空/NaN、超参非法都抛明确异常
- 数值边界：常数列（方差为 0）不产生 inf，截距吸收常数项
- 指标工具：mse / r2 的已知值与全常数标签口径
- 确定性：同一数据、同一参数两次训练结果逐位相同
"""

import numpy as np
import pytest
from impl import Model, closed_form, mse, r2


def make_xy(n: int = 60, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3))
    y = X @ np.array([1.5, -2.0, 0.5]) + 0.7 + rng.normal(0.0, 0.3, n)
    return X, y


# ---------------------------------------------------------------- 梯度与最优性

def test_gradient_matches_finite_difference() -> None:
    X, y = make_xy()
    Xs = (X - X.mean(axis=0)) / X.std(axis=0)
    w = np.array([0.3, -0.2, 0.1])
    b = 0.4
    grad_w, grad_b = Model()._gradients(Xs, y, w, b)

    eps = 1e-6
    num_w = np.zeros_like(w)
    for i in range(w.size):
        w_plus, w_minus = w.copy(), w.copy()
        w_plus[i] += eps
        w_minus[i] -= eps
        loss_plus = np.mean((Xs @ w_plus + b - y) ** 2)
        loss_minus = np.mean((Xs @ w_minus + b - y) ** 2)
        num_w[i] = (loss_plus - loss_minus) / (2 * eps)
    num_b = (np.mean((Xs @ w + (b + eps) - y) ** 2)
             - np.mean((Xs @ w + (b - eps) - y) ** 2)) / (2 * eps)

    np.testing.assert_allclose(grad_w, num_w, rtol=1e-6, atol=1e-7)
    assert abs(grad_b - num_b) < 1e-7


def test_gd_matches_closed_form() -> None:
    X, y = make_xy()
    model = Model(lr=0.1, epochs=20000, tol=1e-14).fit(X, y)
    w_cf, b_cf = closed_form(X, y)

    np.testing.assert_allclose(model.raw_coef, w_cf, rtol=1e-5, atol=1e-6)
    assert abs(model.raw_intercept - b_cf) < 1e-6
    assert abs(mse(y, model.predict(X)) - mse(y, X @ w_cf + b_cf)) < 1e-8


def test_learns_true_parameters() -> None:
    rng = np.random.default_rng(3)
    x = rng.uniform(-2, 2, size=(80, 1))
    y = 3.0 * x[:, 0] + 2.0
    model = Model(lr=0.1, epochs=5000, tol=1e-14).fit(x, y)
    assert abs(model.raw_coef[0] - 3.0) < 1e-6
    assert abs(model.raw_intercept - 2.0) < 1e-6


# ---------------------------------------------------------------- 数据契约

def test_predict_before_fit_raises() -> None:
    with pytest.raises(RuntimeError):
        Model().predict(np.zeros((2, 1)))


def test_invalid_inputs_raise() -> None:
    X, y = make_xy()
    with pytest.raises(ValueError):
        Model().fit(X[:, 0], y)              # X 一维
    with pytest.raises(ValueError):
        Model().fit(X, y[:-1])               # 样本数不一致
    with pytest.raises(ValueError):
        Model().fit(np.empty((0, 3)), np.empty(0))   # 空数据
    bad = X.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        Model().fit(bad, y)                  # NaN
    with pytest.raises(ValueError):
        Model(lr=0.0)                        # 学习率非正
    with pytest.raises(ValueError):
        Model(epochs=0)                      # 轮数非法
    with pytest.raises(ValueError):
        Model(tol=-1.0)                      # 容差为负


def test_predict_shape_checked() -> None:
    X, y = make_xy()
    model = Model(epochs=10).fit(X, y)
    with pytest.raises(ValueError):
        model.predict(X[:, :2])
    with pytest.raises(ValueError):
        model.predict(X[0])


# ---------------------------------------------------------------- 数值边界

def test_constant_feature_is_safe() -> None:
    rng = np.random.default_rng(7)
    x = rng.normal(size=(50, 1))
    X = np.hstack([x, np.full((50, 1), 3.0)])   # 第二列方差为 0
    y = 2.0 * x[:, 0] + 1.0
    model = Model(lr=0.1, epochs=2000, tol=1e-12).fit(X, y)
    assert np.all(np.isfinite(model.raw_coef))
    assert abs(model.raw_coef[0] - 2.0) < 1e-4
    assert abs(model.raw_coef[1]) < 1e-4       # 常数列的斜率应为 0，截距吸收它
    assert abs(model.raw_intercept - 1.0) < 1e-3


def test_no_standardize_still_works_on_small_scale() -> None:
    rng = np.random.default_rng(11)
    x = rng.uniform(-1, 1, size=(60, 1))
    y = 2.0 * x[:, 0] - 0.5
    model = Model(lr=0.1, epochs=5000, tol=1e-14, standardize=False).fit(x, y)
    assert abs(model.raw_coef[0] - 2.0) < 1e-4
    assert abs(model.raw_intercept + 0.5) < 1e-4


# ---------------------------------------------------------------- 指标工具

def test_mse_and_r2_known_values() -> None:
    y = np.array([1.0, 2.0, 3.0])
    pred = np.array([1.0, 2.0, 4.0])
    assert mse(y, pred) == pytest.approx(1.0 / 3.0)
    assert r2(y, pred) == pytest.approx(1.0 - (1.0 / 2.0))
    with pytest.raises(ValueError):
        mse(y, pred[:2])


def test_r2_constant_labels() -> None:
    y = np.full(5, 2.0)
    assert r2(y, y.copy()) == 1.0
    assert r2(y, y + 1.0) == 0.0


# ---------------------------------------------------------------- 确定性

def test_training_is_deterministic() -> None:
    X, y = make_xy()
    a = Model(lr=0.05, epochs=500).fit(X, y)
    b = Model(lr=0.05, epochs=500).fit(X, y)
    np.testing.assert_array_equal(a.w, b.w)
    assert a.b == b.b
    assert a.loss_history == b.loss_history
