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
