"""注意力机制 — 性质测试（pytest）

覆盖：
- 形状/权重归一化
- padding mask / causal mask
- d_k 缩放
- 单头有限差分（Q/K/V）
- 多头有限差分（Wq/Wk/Wv/Wo）
- 排列等变
- 手写 vs torch
- 契约
"""

import numpy as np
import pytest
from impl import MultiHeadAttention, ScaledDotProductAttention, softmax


def small():
    rng = np.random.default_rng(0)
    return rng.normal(size=(1, 3, 4)), rng.normal(size=(1, 4, 4)), rng.normal(size=(1, 4, 4))


def test_shapes_and_normalization() -> None:
    Q, K, V = small()
    out, w = ScaledDotProductAttention().forward(Q, K, V)
    assert out.shape == Q.shape
    assert w.shape == (1, 3, 4)
    np.testing.assert_allclose(w.sum(-1), 1.0)


def test_padding_mask() -> None:
    Q, K, V = small()
    mask = np.ones((3, 4), dtype=bool)
    mask[:, 2:] = False
    _, w = ScaledDotProductAttention().forward(Q, K, V, mask)
    np.testing.assert_allclose(w[..., 2:], 0.0)


def test_causal_mask_and_invariance() -> None:
    Q, K, V = small()
    out1, w1 = ScaledDotProductAttention(causal=True).forward(Q, K, V)
    assert np.allclose(np.triu(w1[0], k=1), 0.0)
    V2 = V.copy()
    V2[:, -1] += 100.0
    out2, _ = ScaledDotProductAttention(causal=True).forward(Q, K, V2)
    np.testing.assert_allclose(out1[:, :-1], out2[:, :-1])



def test_all_masked_row_outputs_zero() -> None:
    Q, K, V = small()
    mask = np.zeros((3, 4), dtype=bool)
    mask[0, :2] = True
    out, w = ScaledDotProductAttention().forward(Q, K, V, mask)
    assert np.isclose(w[0, 0].sum(), 1.0)
    np.testing.assert_allclose(w[0, 1:], 0.0)
    np.testing.assert_allclose(out[0, 1:], 0.0)

def test_scaling_reduces_sharpness() -> None:
    rng = np.random.default_rng(0)
    dk = 64
    Q = rng.normal(size=(1, 4, dk))
    K = rng.normal(size=(1, 8, dk))
    raw = Q @ K.swapaxes(-1, -2)
    w_raw = softmax(raw)
    w_sc = softmax(raw / np.sqrt(dk))
    assert w_raw.max() > w_sc.max()


def test_single_head_gradient() -> None:
    rng = np.random.default_rng(1)
    Q = rng.normal(size=(1, 3, 4))
    K = rng.normal(size=(1, 4, 4))
    V = rng.normal(size=(1, 4, 4))
    G = rng.normal(size=(1, 3, 4))
    att = ScaledDotProductAttention()
    out, _ = att.forward(Q, K, V)
    dQ, dK, dV = att.backward(G)

    def loss(Q, K, V):
        o, _ = att.forward(Q, K, V)
        return float(np.sum(o * G))

    worst = 0.0
    eps = 1e-6
    for arr, d in ((Q, dQ), (K, dK), (V, dV)):
        for idx in np.ndindex(arr.shape):
            old = arr[idx]
            arr[idx] = old + eps
            lp = loss(Q, K, V)
            arr[idx] = old - eps
            lm = loss(Q, K, V)
            arr[idx] = old
            worst = max(worst, abs((lp - lm) / (2 * eps) - d[idx]))
    assert worst < 1e-5


def test_multihead_gradient() -> None:
    rng = np.random.default_rng(2)
    X = rng.normal(size=(1, 3, 8))
    G = rng.normal(size=(1, 3, 8))
    m = MultiHeadAttention(8, 2, random_state=0)
    _, _ = m.forward(X)
    grads, _ = m.backward(G)

    def loss():
        o, _ = m.forward(X)
        return float(np.sum(o * G))

    eps = 1e-6
    worst = 0.0
    for key in ("Wq", "Wk", "Wv", "Wo"):
        arr = getattr(m, key)
        for idx in ((0, 0), (1, 2)):
            old = arr[idx]
            arr[idx] = old + eps
            lp = loss()
            arr[idx] = old - eps
            lm = loss()
            arr[idx] = old
            worst = max(worst, abs((lp - lm) / (2 * eps) - grads[key][idx]))
    assert worst < 1e-5


def test_permutation_equivariance() -> None:
    Q, K, V = small()
    K, V = K[:, :3], V[:, :3]
    out, _ = ScaledDotProductAttention().forward(Q, K, V)
    perm = np.array([2, 0, 1])
    out2, _ = ScaledDotProductAttention().forward(Q[:, perm], K[:, perm], V[:, perm])
    np.testing.assert_allclose(out[:, perm], out2)


def test_torch_parity() -> None:
    pytest.importorskip("torch")
    from framework import torch_attention
    Q, K, V = small()
    out, w = ScaledDotProductAttention().forward(Q, K, V)
    f_out, f_w = torch_attention(Q, K, V)
    np.testing.assert_allclose(out, f_out, atol=1e-6)
    np.testing.assert_allclose(w, f_w, atol=1e-6)


def test_invalid() -> None:
    Q, K, V = small()
    with pytest.raises(ValueError):
        ScaledDotProductAttention().forward(Q, K[:, :3], V)
    with pytest.raises(ValueError):
        ScaledDotProductAttention().forward(Q, K, V, mask=np.ones((2, 2), bool))
    with pytest.raises(ValueError):
        MultiHeadAttention(7, 2)
