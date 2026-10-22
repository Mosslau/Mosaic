"""注意力机制 — 手写实现（深度模型 · 组件）

**本目录不是一个可独立训练的模型，而是一个组件**：没有 fit(X,y)，也没有 train(data)。
接口是前向 + 反向：

    attn = ScaledDotProductAttention(causal=True)
    out, weights = attn.forward(Q, K, V)       # (N,Tq,d), (N,Tk,d)
    dQ, dK, dV = attn.backward(d_out)

多头版本 `MultiHeadAttention` 额外有 Wq/Wk/Wv/Wo，供 Block/GPT/BERT/T5 复用。
"""

from __future__ import annotations

import numpy as np


def softmax(z: np.ndarray, axis: int = -1) -> np.ndarray:
    z = np.asarray(z, dtype=float)
    z = z - z.max(axis=axis, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=axis, keepdims=True)


def _prepare(Q, K, V, mask=None, causal=False):
    Q = np.asarray(Q, dtype=float)
    K = np.asarray(K, dtype=float)
    V = np.asarray(V, dtype=float)
    if Q.ndim == 2:
        Q, K, V = Q[None], K[None], V[None]
    if Q.ndim != 3 or K.ndim != 3 or V.ndim != 3:
        raise ValueError("Q/K/V 应为 (T,d) 或 (N,T,d)")
    if Q.shape[-1] != K.shape[-1]:
        raise ValueError("Q 与 K 的 d_k 必须一致")
    if K.shape[1] != V.shape[1]:
        raise ValueError("K 与 V 的 T 必须一致")
    Tq, Tk = Q.shape[1], K.shape[1]
    mask_arr = None
    if mask is not None:
        mask_arr = np.asarray(mask, dtype=bool)
        if mask_arr.shape != (Tq, Tk):
            raise ValueError(f"mask 形状应为 ({Tq},{Tk})，实际 {mask_arr.shape}")
    if causal:
        cm = np.tril(np.ones((Tq, Tk), dtype=bool))
        mask_arr = cm if mask_arr is None else (mask_arr & cm)
    return Q, K, V, mask_arr


class ScaledDotProductAttention:
    """Attention(Q,K,V) = softmax(Q K^T / sqrt(d_k)) V。无参数。"""

    def __init__(self, causal: bool = False) -> None:
        self.causal = causal
        self.cache: dict = {}

    def forward(self, Q, K, V, mask=None):
        Q, K, V, mask = _prepare(Q, K, V, mask, self.causal)
        dk = Q.shape[-1]
        scores = Q @ K.swapaxes(-1, -2) / np.sqrt(dk)
        if mask is not None:
            scores = np.where(mask[None], scores, -1e9)
        weights = softmax(scores, axis=-1)
        if mask is not None:
            # 整行都被 mask 时 softmax 会变成均匀分布；显式输出 0，避免聚合到填充位
            valid = mask.any(axis=-1, keepdims=True)
            weights = np.where(valid[None], weights, 0.0)
        out = weights @ V
        self.cache = {"Q": Q, "K": K, "V": V, "weights": weights,
                      "mask": mask, "dk": dk}
        return out, weights

    def backward(self, d_out):
        c = self.cache
        if not c:
            raise RuntimeError("请先调用 forward")
        Q, K, V, W, dk = c["Q"], c["K"], c["V"], c["weights"], c["dk"]
        dV = W.swapaxes(-1, -2) @ d_out
        dW = d_out @ V.swapaxes(-1, -2)
        # softmax 雅可比：dS = W * (dW - sum(dW*W))
        dS = W * (dW - np.sum(dW * W, axis=-1, keepdims=True))
        if c["mask"] is not None:
            dS = np.where(c["mask"][None], dS, 0.0)
        dQ = dS @ K / np.sqrt(dk)
        dK = dS.swapaxes(-1, -2) @ Q / np.sqrt(dk)
        return dQ, dK, dV


class MultiHeadAttention:
    """多头注意力：Wq/Wk/Wv/Wo，拆头 → scaled dot-product → 拼头。"""

    def __init__(self, d_model: int = 32, n_heads: int = 4, causal: bool = False,
                 random_state: int | None = 0) -> None:
        if d_model % n_heads:
            raise ValueError("d_model 必须能被 n_heads 整除")
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.causal = causal
        rng = np.random.default_rng(random_state)
        scale = np.sqrt(2.0 / d_model)
        self.Wq = rng.normal(0, scale, (d_model, d_model))
        self.Wk = rng.normal(0, scale, (d_model, d_model))
        self.Wv = rng.normal(0, scale, (d_model, d_model))
        self.Wo = rng.normal(0, scale, (d_model, d_model))

    def _split(self, X):
        N, T, _ = X.shape
        return X.reshape(N, T, self.n_heads, self.d_head).transpose(0, 2, 1, 3)

    def _merge(self, X):
        N, H, T, D = X.shape
        return X.transpose(0, 2, 1, 3).reshape(N, T, H * D)

    def forward(self, X, mask=None):
        X = np.asarray(X, dtype=float)
        if X.ndim == 2:
            X = X[None]
        self.X = X
        self.mask = mask
        self.Q = self._split(X @ self.Wq)
        self.K = self._split(X @ self.Wk)
        self.V = self._split(X @ self.Wv)
        outs, weights = [], []
        for h in range(self.n_heads):
            o, w = ScaledDotProductAttention(self.causal).forward(
                self.Q[:, h], self.K[:, h], self.V[:, h], mask)
            outs.append(o)
            weights.append(w)
        self.head_out = np.stack(outs, axis=1)          # (N,H,T,dh)
        merged = self._merge(self.head_out)
        self.merged = merged
        self.weights = np.stack(weights, axis=1)        # (N,H,T,T)
        return merged @ self.Wo, self.weights

    def backward(self, d_out):
        d_out = np.asarray(d_out, dtype=float)
        if d_out.ndim == 2:
            d_out = d_out[None]
        dW_o = self.merged.reshape(-1, self.d_model).T @ d_out.reshape(-1, self.d_model)
        d_merged = d_out @ self.Wo.T
        d_heads = d_merged.reshape(d_out.shape[0], -1, self.n_heads, self.d_head)\
            .transpose(0, 2, 1, 3)
        dQ = np.zeros_like(self.Q)
        dK = np.zeros_like(self.K)
        dV = np.zeros_like(self.V)
        for h in range(self.n_heads):
            att = ScaledDotProductAttention(self.causal)
            att.forward(self.Q[:, h], self.K[:, h], self.V[:, h], self.mask)
            dQ_h, dK_h, dV_h = att.backward(d_heads[:, h])
            dQ[:, h], dK[:, h], dV[:, h] = dQ_h, dK_h, dV_h
        dQf = self._merge(dQ) @ self.Wq.T
        dKf = self._merge(dK) @ self.Wk.T
        dVf = self._merge(dV) @ self.Wv.T
        dX = dQf + dKf + dVf
        Xf = self.X.reshape(-1, self.d_model)
        grads = {
            "Wq": Xf.T @ self._merge(dQ).reshape(-1, self.d_model),
            "Wk": Xf.T @ self._merge(dK).reshape(-1, self.d_model),
            "Wv": Xf.T @ self._merge(dV).reshape(-1, self.d_model),
            "Wo": dW_o,
        }
        return grads, dX


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
