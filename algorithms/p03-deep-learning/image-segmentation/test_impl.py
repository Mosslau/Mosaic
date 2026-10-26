"""图像分割 TinyUNet-lite — 性质测试（pytest）。

覆盖：卷积/池化/上采样的前向与伴随、IoU/Dice、模型形状与参数量、
批量一致性、损失下降、小样本过拟合、数据确定性与输入契约。
"""

import numpy as np
import pytest
from data import make_dataset
from impl import (
    Conv2D,
    TinyUNet,
    col2im,
    dice,
    im2col,
    iou,
    maxpool_backward,
    maxpool_forward,
    upsample_backward,
    upsample_nearest,
)


def test_conv_forward_identity() -> None:
    rng = np.random.default_rng(0)
    conv = Conv2D(1, 1, 3, pad=1, rng=rng)
    conv.W[:] = 0.0
    conv.W[0, 0, 1, 1] = 1.0
    X = rng.normal(size=(2, 1, 6, 6))
    np.testing.assert_allclose(conv.forward(X), X, atol=1e-12)


def test_conv_gradient_matches_finite_difference() -> None:
    rng = np.random.default_rng(1)
    conv = Conv2D(2, 1, 3, pad=1, rng=rng)
    X = rng.normal(size=(1, 1, 4, 4))
    G = rng.normal(size=(1, 2, 4, 4))
    conv.forward(X)
    conv.backward(G)

    eps = 1e-6

    def numeric(layer, name, index) -> float:
        old = getattr(layer, name)[index]
        getattr(layer, name)[index] = old + eps
        plus = float(np.sum(layer.forward(X) * G))
        getattr(layer, name)[index] = old - eps
        minus = float(np.sum(layer.forward(X) * G))
        getattr(layer, name)[index] = old
        return (plus - minus) / (2 * eps)

    assert abs(conv.dW[0, 0, 1, 1] - numeric(conv, "W", (0, 0, 1, 1))) < 1e-8
    assert abs(conv.db[0] - numeric(conv, "b", 0)) < 1e-8


def test_im2col_adjoint() -> None:
    rng = np.random.default_rng(2)
    X = rng.normal(size=(2, 3, 6, 6))
    G = rng.normal(size=im2col(X, 3, 3, 1, 1).shape)
    lhs = float(np.sum(im2col(X, 3, 3, 1, 1) * G))
    rhs = float(np.sum(X * col2im(G, X.shape, 3, 3, 1, 1)))
    assert abs(lhs - rhs) < 1e-10


def test_maxpool_adjoint() -> None:
    rng = np.random.default_rng(3)
    X = rng.normal(size=(2, 3, 8, 8))
    out, idx = maxpool_forward(X)
    G = rng.normal(size=out.shape)
    lhs = float(np.sum(out * G))
    rhs = float(np.sum(X * maxpool_backward(G, idx, X.shape)))
    assert abs(lhs - rhs) < 1e-10
    assert out.shape == (2, 3, 4, 4)
    assert np.all(out == X.reshape(2, 3, 4, 2, 4, 2).transpose(0, 1, 2, 4, 3, 5)
                  .reshape(2, 3, 4, 4, 4).max(axis=-1))


def test_upsample_forward_backward() -> None:
    X = np.array([[[[1.0, 2.0], [3.0, 4.0]]]])
    out = upsample_nearest(X, 2)
    assert out.shape == (1, 1, 4, 4)
    np.testing.assert_array_equal(out[0, 0], [[1, 1, 2, 2], [1, 1, 2, 2],
                                              [3, 3, 4, 4], [3, 3, 4, 4]])
    np.testing.assert_array_equal(
        upsample_backward(np.ones((1, 1, 4, 4))), 4 * np.ones((1, 1, 2, 2)))

    rng = np.random.default_rng(4)
    X = rng.normal(size=(2, 3, 5, 5))
    G = rng.normal(size=(2, 3, 10, 10))
    lhs = float(np.sum(upsample_nearest(X, 2) * G))
    rhs = float(np.sum(X * upsample_backward(G, 2)))
    assert abs(lhs - rhs) < 1e-10
    with pytest.raises(ValueError):
        upsample_backward(np.zeros((1, 1, 5, 4)), 2)


def test_iou_dice_known_values() -> None:
    target = np.array([[1, 1, 0, 0], [1, 1, 0, 0], [0, 0, 1, 1], [0, 0, 1, 1]])
    pred = np.array([[1, 1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 1], [0, 0, 0, 1]])
    assert abs(iou(pred, target) - 0.75) < 1e-12
    assert abs(dice(pred, target) - 6 / 7) < 1e-12


def test_metric_edge_cases() -> None:
    zero = np.zeros((2, 4, 4))
    one = np.ones((2, 4, 4))
    assert iou(zero, zero) == 1.0 and dice(zero, zero) == 1.0
    assert iou(one, zero) == 0.0 and dice(one, zero) == 0.0
    assert iou(one, one) == 1.0
    with pytest.raises(ValueError):
        iou(np.zeros((4, 4)), np.zeros((5, 4)))
    with pytest.raises(ValueError):
        dice(np.zeros((1, 4, 4)), np.zeros((2, 4, 4)))


def test_model_shapes_and_params() -> None:
    model = TinyUNet()
    model._init_params(np.random.default_rng(5))
    X = np.random.default_rng(6).normal(size=(3, 1, 32, 32))
    logits, cache = model.forward(X)
    assert logits.shape == (3, 1, 32, 32)
    assert cache["z1"].shape == (3, 8, 32, 32)
    assert cache["z2"].shape == (3, 16, 16, 16)
    assert cache["z3"].shape == (3, 8, 32, 32)
    assert model.count_params() == 2417
    proba = model.predict_proba(X)
    assert proba.shape == (3, 1, 32, 32)
    assert np.all((proba > 0) & (proba < 1))


def test_batch_single_consistency() -> None:
    model = TinyUNet()
    model._init_params(np.random.default_rng(7))
    X = np.random.default_rng(8).normal(size=(2, 1, 32, 32))
    batch = model.predict_proba(X)
    single = np.concatenate([model.predict_proba(X[i:i + 1]) for i in range(2)])
    np.testing.assert_allclose(batch, single, atol=1e-12)


def test_loss_decreases() -> None:
    X, Y = make_dataset(48, seed=21)
    model = TinyUNet(lr=0.02, epochs=8, batch_size=16, random_state=0).fit(X, Y)
    assert len(model.loss_history) == 8
    assert model.loss_history[-1] < 0.8 * model.loss_history[0]
    assert model.loss_history[-1] < model.loss_history[3]


def test_overfit_tiny_batch() -> None:
    X, Y = make_dataset(8, seed=22)
    model = TinyUNet(lr=0.03, epochs=600, batch_size=8, random_state=0).fit(X, Y)
    assert iou(model.predict(X), Y) > 0.85


def test_dataset_and_invalid_inputs() -> None:
    X1, Y1 = make_dataset(4, seed=31)
    X2, Y2 = make_dataset(4, seed=31)
    assert X1.shape == (4, 1, 32, 32) and Y1.shape == X1.shape
    assert set(np.unique(Y1)) <= {0.0, 1.0}
    np.testing.assert_array_equal(X1, X2)
    np.testing.assert_array_equal(Y1, Y2)
    with pytest.raises(ValueError):
        make_dataset(0)
    with pytest.raises(ValueError):
        make_dataset(2, max_shapes=0)
    with pytest.raises(ValueError):
        TinyUNet(lr=0.0)
    with pytest.raises(ValueError):
        TinyUNet().fit(np.zeros((2, 1, 8, 8)), np.zeros((2, 1, 8, 8)))
    with pytest.raises(ValueError):
        TinyUNet().fit(np.zeros((2, 1, 32, 32)), np.zeros((2, 32, 32)))
    with pytest.raises(ValueError):
        maxpool_forward(np.zeros((1, 1, 5, 4)))
