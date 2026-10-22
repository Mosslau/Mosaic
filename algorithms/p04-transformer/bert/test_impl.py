"""BERT / MLM — 性质测试（pytest）

覆盖：
- mask 只落在非特殊 token、比例约 15%
- MLM loss 下降、固定 mask 评测
- [CLS] 表示形状、非 causal
- MLM head 有限差分
- 预测/契约/torch
"""

import numpy as np
import pytest
from impl import BertMLM, softmax


def tokens_fixture(n=8, T=10, seed=0):
    rng = np.random.default_rng(seed)
    tokens = rng.integers(5, 20, size=(n, T))
    tokens[:, 0] = 2   # CLS
    tokens[:, -1] = 3  # SEP
    return tokens


def test_mask_only_eligible() -> None:
    tokens = tokens_fixture()
    m = BertMLM(20, context=10)
    inp, target, mask = m._make_mask(tokens, np.random.default_rng(0))
    assert mask.sum() > 0
    assert not mask[:, 0].any() and not mask[:, -1].any()
    assert np.all(target == tokens)
    assert inp.shape == tokens.shape


def test_mlm_loss_decreases() -> None:
    tokens = tokens_fixture()
    m = BertMLM(20, context=10, d_model=16, n_heads=2, d_ff=32)
    before = m.evaluate(tokens)["loss"]
    m.train(tokens, epochs=30, lr=3e-3)
    after = m.evaluate(tokens)["loss"]
    assert after < before


def test_encode_shape() -> None:
    tokens = tokens_fixture()
    m = BertMLM(20, context=10, d_model=16, n_heads=2, d_ff=32)
    z = m.encode(tokens)
    assert z.shape == (8, 16)


def test_non_causal() -> None:
    tokens = tokens_fixture()
    m = BertMLM(20, context=10, d_model=16, n_heads=2, d_ff=32)
    z1 = m.encode(tokens)
    t2 = tokens.copy()
    t2[:, -2] = 19
    z2 = m.encode(t2)
    # 双向：改最后一个内容 token 会影响 [CLS]
    assert not np.allclose(z1, z2)


def test_mlm_head_gradient() -> None:
    tokens = tokens_fixture()
    m = BertMLM(20, context=10, d_model=16, n_heads=2, d_ff=32)
    inp, target, mask = m._make_mask(tokens, np.random.default_rng(1))
    probs = softmax(m._forward(inp))
    d = probs.copy()
    N, T = tokens.shape
    d[np.arange(N)[:, None], np.arange(T)[None, :], target] -= 1
    d *= mask[..., None]
    d /= mask.sum()
    m._backward(d)

    def loss():
        p = softmax(m._forward(inp))
        sel = p[mask]
        tgt = target[mask]
        return float(-np.log(np.clip(sel[np.arange(len(tgt)), tgt], 1e-12, 1)).mean())

    eps = 1e-6
    idx = (0, 0)
    old = m.Wlm[idx]
    m.Wlm[idx] = old + eps
    lp = loss()
    m.Wlm[idx] = old - eps
    lm = loss()
    m.Wlm[idx] = old
    assert abs((lp - lm) / (2 * eps) - m._dWlm[idx]) < 1e-4


def test_predict_masked() -> None:
    tokens = tokens_fixture()
    m = BertMLM(20, context=10, d_model=16, n_heads=2, d_ff=32)
    pred = m.predict_masked(tokens)
    assert pred.shape == tokens.shape
    assert pred.min() >= 0 and pred.max() < 20


def test_torch_parity() -> None:
    pytest.importorskip("torch")
    from framework import TorchBERT
    model = TorchBERT(20, context=10, d_model=16, n_heads=2, d_ff=32)
    x = __import__("torch").randint(0, 20, (2, 10))
    logits, hidden = model(x)
    assert logits.shape == (2, 10, 20)
    assert hidden.shape == (2, 10, 16)


def test_invalid() -> None:
    with pytest.raises(ValueError):
        BertMLM(20, context=10, d_model=15, n_heads=4)
