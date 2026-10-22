"""迷你 Transformer Block — 性质测试（pytest）

覆盖：
- LayerNorm 归一化/仿射/梯度
- Block 形状、残差、causal
- Block 输入有限差分
- next-token 训练 loss 下降
- torch 对照
- 契约
"""

import numpy as np
import pytest
from impl import LayerNorm, TransformerBlock


def test_layernorm_normalizes() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2, 3, 5)) * 3 + 7
    ln = LayerNorm(5)
    out = ln.forward(X)
    np.testing.assert_allclose(out.mean(-1), 0.0, atol=1e-6)
    np.testing.assert_allclose(out.std(-1), 1.0, atol=1e-3)


def test_layernorm_gradient() -> None:
    rng = np.random.default_rng(1)
    ln = LayerNorm(5)
    X = rng.normal(size=(2, 3, 5))
    G = rng.normal(size=(2, 3, 5))
    ln.forward(X)
    ln.backward(G)

    def loss():
        return float(np.sum(ln.forward(X) * G))

    eps = 1e-6
    for key in ("gamma", "beta"):
        arr = getattr(ln, key)
        idx = 2
        old = arr[idx]
        arr[idx] = old + eps
        lp = loss()
        arr[idx] = old - eps
        lm = loss()
        arr[idx] = old
        assert abs((lp - lm) / (2 * eps) - getattr(ln, "d" + key)[idx]) < 1e-5


def test_block_shape_and_residual() -> None:
    rng = np.random.default_rng(2)
    X = rng.normal(size=(2, 5, 8))
    b = TransformerBlock(8, 2, 16, vocab_size=10, context=5)
    out = b.forward(X)
    assert out.shape == X.shape
    assert b.backward(np.ones_like(out)).shape == X.shape

    b2 = TransformerBlock(8, 2, 16, vocab_size=10, context=5, use_residual=False)
    assert b2.forward(X).shape == X.shape


def test_block_input_gradient() -> None:
    rng = np.random.default_rng(3)
    b = TransformerBlock(4, 2, 8, vocab_size=6, context=4)
    X = rng.normal(size=(1, 4, 4))
    G = rng.normal(size=(1, 4, 4))
    b.forward(X)
    dX = b.backward(G)

    def loss():
        return float(np.sum(b.forward(X) * G))

    eps = 1e-6
    worst = 0.0
    for idx in np.ndindex(X.shape):
        old = X[idx]
        X[idx] = old + eps
        lp = loss()
        X[idx] = old - eps
        lm = loss()
        X[idx] = old
        worst = max(worst, abs((lp - lm) / (2 * eps) - dX[idx]))
    assert worst < 1e-5


def test_causal_invariance() -> None:
    rng = np.random.default_rng(4)
    b = TransformerBlock(8, 2, 16, vocab_size=10, context=5)
    X = rng.normal(size=(1, 5, 8))
    out1 = b.forward(X)
    X2 = X.copy()
    X2[:, -1] += 10.0
    out2 = b.forward(X2)
    np.testing.assert_allclose(out1[:, :-1], out2[:, :-1])


def test_train_loss_decreases() -> None:
    rng = np.random.default_rng(5)
    b = TransformerBlock(8, 2, 16, vocab_size=5, context=4)
    tokens = rng.integers(0, 5, size=120)
    losses = b.train(tokens, epochs=8, lr=3e-3, batch_size=16)
    assert losses[-1] < losses[0]


def test_evaluate() -> None:
    rng = np.random.default_rng(6)
    b = TransformerBlock(8, 2, 16, vocab_size=5, context=4)
    tokens = rng.integers(0, 5, size=80)
    m = b.evaluate(tokens)
    assert 0 <= m["acc"] <= 1
    assert m["loss"] > 0


def test_torch_parity() -> None:
    pytest.importorskip("torch")
    from framework import TorchBlock
    model = TorchBlock(11, d_model=8, n_heads=2, d_ff=16, context=4)
    x = __import__("torch").randint(0, 11, (2, 4))
    assert model(x).shape == (2, 4, 11)


def test_invalid() -> None:
    with pytest.raises(ValueError):
        TransformerBlock(7, 2, 8, vocab_size=5, context=3)
    b = TransformerBlock(8, 2, 16, vocab_size=5, context=4)
    with pytest.raises(ValueError):
        b.train([1, 2, 3], epochs=1)
