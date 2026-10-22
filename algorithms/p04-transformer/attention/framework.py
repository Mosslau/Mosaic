"""注意力机制 — PyTorch 对照

用 torch 张量手写同样的 scaled dot-product（便于逐位对账），
另外提供 `torch_mha` 调 `nn.MultiheadAttention` 作为工程对照。
"""

from __future__ import annotations

import torch


def torch_attention(Q, K, V, mask=None, causal=False):
    Q = torch.as_tensor(Q, dtype=torch.float32)
    K = torch.as_tensor(K, dtype=torch.float32)
    V = torch.as_tensor(V, dtype=torch.float32)
    dk = Q.shape[-1]
    scores = Q @ K.transpose(-2, -1) / (dk ** 0.5)
    if causal:
        Tq, Tk = scores.shape[-2:]
        cm = torch.tril(torch.ones(Tq, Tk, dtype=torch.bool))
        scores = scores.masked_fill(~cm, -1e9)
    if mask is not None:
        m = torch.as_tensor(mask, dtype=torch.bool)
        scores = scores.masked_fill(~m, -1e9)
    w = torch.softmax(scores, dim=-1)
    return (w @ V).numpy(), w.numpy()


def torch_mha(X, d_model=32, n_heads=4):
    """nn.MultiheadAttention 工程对照：只返回输出，不保证权重与手写逐位一致。"""
    X = torch.as_tensor(X, dtype=torch.float32)
    layer = torch.nn.MultiheadAttention(d_model, n_heads, batch_first=True)
    out, _ = layer(X, X, X, need_weights=False)
    return out.detach().numpy()


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，由 demo.py 统一调用：uv run python demo.py")
