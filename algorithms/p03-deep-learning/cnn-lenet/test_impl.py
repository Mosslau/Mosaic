"""LeNet — 性质测试（pytest）

覆盖：
- im2col/col2im 与 maxpool 的伴随（转置）性质
- conv 输出形状
- 小数据训练精度
- BatchNorm / 残差前向
- 契约
"""

import numpy as np
import pytest
from impl import LeNet, col2im, im2col, maxpool_backward, maxpool_forward


def small_data(n=300):
    from sklearn.datasets import load_digits
    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(-1, 1, 8, 8)
    return X[:n], y[:n]


def test_im2col_adjoint() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2, 3, 6, 6))
    G = rng.normal(size=im2col(X, 3, 3, 1, 1).shape)
    lhs = np.sum(im2col(X, 3, 3, 1, 1) * G)
    rhs = np.sum(X * col2im(G, X.shape, 3, 3, 1, 1))
    assert abs(lhs - rhs) < 1e-10


def test_maxpool_adjoint() -> None:
    rng = np.random.default_rng(1)
    X = rng.normal(size=(2, 3, 8, 8))
    out, idx = maxpool_forward(X)
    G = rng.normal(size=out.shape)
    lhs = np.sum(out * G)
    rhs = np.sum(X * maxpool_backward(G, idx, X.shape))
    assert abs(lhs - rhs) < 1e-10


def test_conv_shapes() -> None:
    from impl import Conv2D
    rng = np.random.default_rng(2)
    conv = Conv2D(6, 1, 3, 3, 1, 1, rng)
    X = rng.normal(size=(4, 1, 8, 8))
    assert conv.forward(X).shape == (4, 6, 8, 8)


@pytest.mark.parametrize("key,param_name,idx", [
    ("conv1", "W", (0, 0, 0, 0)),
    ("conv2", "W", (0, 0, 0, 0)),
    ("fc1", "W", (0, 0)),
    ("fc2", "W", (0, 0)),
    ("bn1", "gamma", (0,)),
    ("bn2", "gamma", (0,)),
    ("skip", "W", (0, 0, 0, 0)),
])
def test_backward_fd(key, param_name, idx) -> None:
    """卷积 / BN / 残差跳连的反向传播：七组参数有限差分。"""
    X, y = small_data(16)
    m = LeNet(use_bn=True, use_residual=True, optimizer="sgd", random_state=0)
    m._init_params(np.random.default_rng(0))
    y1 = np.eye(10)[y]
    proba, cache = m.forward(X, training=True)
    grads = m.backward(proba, y1, cache)

    def loss():
        p, _ = m.forward(X, training=True)
        return float(-np.mean(np.log(np.clip(
            p[np.arange(len(y)), y], 1e-12, 1))))

    eps = 1e-6
    param = getattr(getattr(m, key), param_name)
    analytic = float(grads[key][0][idx])
    old = param[idx]
    param[idx] = old + eps
    lp = loss()
    param[idx] = old - eps
    lm = loss()
    param[idx] = old
    assert abs((lp - lm) / (2 * eps) - analytic) < 1e-4, key


def test_heldout_accuracy() -> None:
    from sklearn.model_selection import train_test_split
    X, y = small_data(300)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=.3, random_state=0, stratify=y)
    m = LeNet(lr=0.003, epochs=10, batch_size=32, optimizer="adam", random_state=0).fit(Xtr, ytr)
    assert np.mean(m.predict(Xte) == yte) > 0.6


def test_torch_baseline_smoke() -> None:
    pytest.importorskip("torch")
    import framework
    from sklearn.model_selection import train_test_split
    X, y = small_data(200)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=.3, random_state=0, stratify=y)
    fm = framework.run_framework(Xtr, Xte, ytr, yte, epochs=2, lr=0.003, batch_size=32)
    assert np.isfinite(fm["loss"])
    assert 0 <= fm["acc"] <= 1


def test_train_small() -> None:
    X, y = small_data(300)
    m = LeNet(lr=0.003, epochs=15, batch_size=32, optimizer="adam", random_state=0).fit(X, y)
    assert np.mean(m.predict(X) == y) > 0.6
    assert len(m.loss_history) == 15


def test_bn_residual_forward() -> None:
    X, y = small_data(120)
    m = LeNet(lr=0.003, epochs=2, batch_size=32, use_bn=True,
              use_residual=True, random_state=0).fit(X, y)
    p = m.predict_proba(X)
    assert p.shape == (120, 10)
    np.testing.assert_allclose(p.sum(axis=1), 1.0)


def test_invalid_inputs() -> None:
    X, y = small_data(20)
    with pytest.raises(ValueError):
        LeNet().fit(X[:, 0], y)
    with pytest.raises(ValueError):
        LeNet().fit(X, y[:-1])
    with pytest.raises(ValueError):
        LeNet().fit(X[:, :, :4], y)
    with pytest.raises(ValueError):
        LeNet(optimizer="rmsprop")


def test_three_classes() -> None:
    X, y = small_data(120)
    m = LeNet(n_classes=3, lr=0.003, epochs=2, batch_size=32, random_state=0).fit(X, y % 3)
    assert m.predict_proba(X).shape == (120, 3)


def test_predict_before_fit() -> None:
    X, _ = small_data(10)
    with pytest.raises((AttributeError, RuntimeError)):
        LeNet().predict(X)
