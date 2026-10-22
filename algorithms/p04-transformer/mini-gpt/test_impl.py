"""Mini-GPT — 性质测试（pytest）

覆盖：
- tokenizer roundtrip / <unk> / 可复现
- 前向形状、causal 不变性
- LM head 有限差分
- 训练 loss 下降、evaluate
- greedy / top-k 生成
- torch 对照、契约
"""

import numpy as np
import pytest
from impl import CharTokenizer, MiniGPT, softmax


def tok_data():
    tok = CharTokenizer().fit("the cat sees the ball. the dog sees the cat. ")
    ids = tok.encode("the cat sees the ball. the dog sees the cat. ")
    return tok, ids


def test_tokenizer_roundtrip() -> None:
    tok, _ = tok_data()
    text = "the cat sees the ball."
    assert tok.decode(tok.encode(text)) == text
    assert tok.encode("z")[0] == 0          # <unk>
    assert tok.itos[0] == "<unk>"


def test_forward_shape() -> None:
    tok, ids = tok_data()
    g = MiniGPT(len(tok.itos), context=8, d_model=8, n_heads=2, n_layers=2, d_ff=16)
    batch = np.array([ids[:8], ids[:8]])
    assert g.forward(batch).shape == (2, 8, len(tok.itos))
    assert g.hidden.shape == (2, 8, 8)


def test_causal_invariance() -> None:
    tok, ids = tok_data()
    g = MiniGPT(len(tok.itos), context=8, d_model=8, n_heads=2, n_layers=1, d_ff=16)
    x = ids[:8][None]
    h1 = g.forward(x)
    x2 = x.copy()
    x2[0, -1] = (x2[0, -1] + 1) % len(tok.itos)
    h2 = g.forward(x2)
    np.testing.assert_allclose(h1[:, :-1], h2[:, :-1])


def test_lm_head_gradient() -> None:
    tok, ids = tok_data()
    g = MiniGPT(len(tok.itos), context=8, d_model=8, n_heads=2, n_layers=1, d_ff=16)
    x = ids[:8][None]
    y = ids[1:9][None]
    logits = g.forward(x)
    p = softmax(logits)
    d = p.copy()
    d[np.arange(1)[:, None], np.arange(8), y] -= 1
    d /= 8
    g.backward(d)

    def loss():
        pp = softmax(g.forward(x))
        return float(-np.log(np.clip(pp[0, np.arange(8), y[0]], 1e-12, 1)).mean())

    eps = 1e-6
    idx = (0, 0)
    old = g.Wlm[idx]
    g.Wlm[idx] = old + eps
    lp = loss()
    g.Wlm[idx] = old - eps
    lm = loss()
    g.Wlm[idx] = old
    assert abs((lp - lm) / (2 * eps) - g.dWlm[idx]) < 1e-4


def test_train_loss_decreases() -> None:
    tok, ids = tok_data()
    g = MiniGPT(len(tok.itos), context=8, d_model=8, n_heads=2, n_layers=1, d_ff=16)
    losses = g.train(ids, epochs=12, lr=3e-3, batch_size=8)
    assert losses[-1] < losses[0]


def test_evaluate() -> None:
    tok, ids = tok_data()
    g = MiniGPT(len(tok.itos), context=8, d_model=8, n_heads=2, n_layers=1, d_ff=16)
    m = g.evaluate(ids)
    assert 0 <= m["acc"] <= 1 and m["loss"] > 0


def test_generate_greedy_and_topk() -> None:
    tok, ids = tok_data()
    g = MiniGPT(len(tok.itos), context=8, d_model=8, n_heads=2, n_layers=1, d_ff=16)
    g.train(ids, epochs=10, lr=3e-3, batch_size=8)
    a = g.generate("the", tok, n_steps=5, temperature=0.0)
    b = g.generate("the", tok, n_steps=5, temperature=0.0)
    assert a == b
    c = g.generate("the", tok, n_steps=5, temperature=0.8, top_k=1, seed=0)
    assert c == a
    d = g.generate("the", tok, n_steps=5, temperature=0.8, top_k=3, seed=0)
    assert len(d) == len("the") + 5


def test_torch_parity_shape() -> None:
    pytest.importorskip("torch")
    from framework import TorchGPT
    model = TorchGPT(20, context=8, d_model=8, n_heads=2, n_layers=2, d_ff=16)
    x = __import__("torch").randint(0, 20, (2, 8))
    assert model(x).shape == (2, 8, 20)


def test_invalid() -> None:
    with pytest.raises(ValueError):
        MiniGPT(10, context=8, d_model=7, n_heads=2, n_layers=1)
    tok, ids = tok_data()
    g = MiniGPT(len(tok.itos), context=8)
    with pytest.raises(ValueError):
        g.train(ids[:4], epochs=1)
    with pytest.raises(ValueError):
        g.generate("", tok, n_steps=1)
    with pytest.raises(ValueError):
        g.generate("the", tok, n_steps=1, temperature=-0.1)
    with pytest.raises(ValueError):
        g.generate("the", tok, n_steps=1, top_k=0)
    with pytest.raises(ValueError):
        g.forward(np.zeros((1, 9), dtype=int))
