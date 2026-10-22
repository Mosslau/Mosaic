"""T5 / encoder-decoder — 性质测试（pytest）

覆盖：
- Vocab roundtrip
- encoder 双向 / decoder causal
- cross-attention 形状
- LM head 有限差分
- 训练 loss 下降、generate
- torch 形状、契约
"""

import itertools

import numpy as np
import pytest
from impl import BOS, EOS, T5Toy, Vocab, softmax


def make_data(n=64):
    v = Vocab("abc")
    seqs = ["".join(p) for p in itertools.product("abc", repeat=3)]
    rng = np.random.default_rng(0)
    order = rng.permutation(len(seqs))
    pairs = []
    for i, j in enumerate(order[:n]):
        s = seqs[j]
        rev = i % 2 == 1
        tgt = s[::-1] if rev else s
        src = [v.stoi["<rev>" if rev else "<copy>"]] + v.encode(s)
        pairs.append((src, [BOS] + v.encode(tgt), v.encode(tgt) + [EOS]))
    return v, pairs


def model(v):
    return T5Toy(len(v.itos), src_len=4, tgt_len=4, d_model=8, n_heads=2, d_ff=16)


def test_vocab_roundtrip() -> None:
    v = Vocab("abc")
    assert v.decode(v.encode("abc")) == "abc"
    assert v.stoi["<copy>"] == 3 and v.stoi["<rev>"] == 4


def test_encoder_bidirectional() -> None:
    v, pairs = make_data(4)
    m = model(v)
    src = np.array([p[0] for p in pairs])
    h1 = m.encode(src)
    src2 = src.copy()
    src2[0, -1] = v.stoi["c"] if src2[0, -1] != v.stoi["c"] else v.stoi["a"]
    h2 = m.encode(src2)
    # 改最后一个源 token，应该影响它前面的 encoder 表示
    assert not np.allclose(h1[0, :-1], h2[0, :-1])


def test_decoder_causal() -> None:
    v, pairs = make_data(2)
    m = model(v)
    src = np.array([p[0] for p in pairs])
    tin = np.array([p[1] for p in pairs])
    l1 = m.forward(src, tin)
    tin2 = tin.copy()
    tin2[0, -1] = (tin2[0, -1] + 1) % len(v.itos)
    l2 = m.forward(src, tin2)
    np.testing.assert_allclose(l1[0, :-1], l2[0, :-1])


def test_cross_attention_shape() -> None:
    v, pairs = make_data(2)
    m = model(v)
    m.forward(np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs]))
    W = m.dec.cross_attn.weights
    assert W.shape == (2, 2, 4, 4)   # (N,H,Tgt,Src)
    np.testing.assert_allclose(W.sum(-1), 1.0, atol=1e-6)


def test_lm_head_gradient() -> None:
    v, pairs = make_data(2)
    m = model(v)
    src = np.array([p[0] for p in pairs])
    tin = np.array([p[1] for p in pairs])
    tout = np.array([p[2] for p in pairs])
    logits = m.forward(src, tin)
    p = softmax(logits)
    N, T = tout.shape
    d = p.copy()
    d[np.arange(N)[:, None], np.arange(T), tout] -= 1
    d /= tout.size
    m.backward(d)

    def loss():
        pp = softmax(m.forward(src, tin))
        return float(-np.log(np.clip(
            pp[np.arange(N)[:, None], np.arange(T), tout], 1e-12, 1)).mean())

    eps = 1e-6
    idx = (0, 0)
    old = m.Wlm[idx]
    m.Wlm[idx] = old + eps
    lp = loss()
    m.Wlm[idx] = old - eps
    lm = loss()
    m.Wlm[idx] = old
    assert abs((lp - lm) / (2 * eps) - m.dWlm[idx]) < 1e-4


def test_train_loss_decreases() -> None:
    v, pairs = make_data(32)
    m = model(v)
    losses = m.train(pairs, epochs=20, lr=3e-3)
    assert losses[-1] < losses[0]


def test_generate_and_exact() -> None:
    v, pairs = make_data(64)
    m = model(v)
    m.train(pairs, epochs=30, lr=3e-3)
    p = pairs[0]
    ids = m.generate(p[0], 4, v)
    assert ids[0] == BOS
    assert all(0 <= i < len(v.itos) for i in ids)


def test_torch_parity_shape() -> None:
    pytest.importorskip("torch")
    from framework import TorchT5
    model_t = TorchT5(11, src_len=4, tgt_len=4, d_model=8, n_heads=2, d_ff=16)
    src = __import__("torch").randint(0, 11, (2, 4))
    tin = __import__("torch").randint(0, 11, (2, 3))
    logits, _ = model_t(src, tin)
    assert logits.shape == (2, 3, 11)


def test_invalid() -> None:
    v, pairs = make_data(2)
    m = model(v)
    with pytest.raises(ValueError):
        m.forward(np.array([pairs[0][0][:-1]]), np.array([pairs[0][1]]))
    with pytest.raises(ValueError):
        m.forward(np.array([pairs[0][0]]), np.array([[]], dtype=int))
    with pytest.raises(ValueError):
        m.generate(pairs[0][0][:-1], 4)
    with pytest.raises(ValueError):
        m.generate(pairs[0][0], 0)
    with pytest.raises(ValueError):
        T5Toy(10, src_len=4, tgt_len=4, d_model=7, n_heads=2)
    with pytest.raises(ValueError):
        T5Toy(10, src_len=0, tgt_len=4)
