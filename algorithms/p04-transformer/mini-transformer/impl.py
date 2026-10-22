"""迷你 Transformer Block — 手写实现（深度模型 · 组件/可训练块）

    block = TransformerBlock(d_model=32, n_heads=4, d_ff=64, vocab_size=32, context=16)
    out = block.forward(X)                 # X: (N,T,d_model)，causal 自注意力
    block.train(tokens, epochs=50)         # next-token 语言建模

本文件同时实现 LayerNorm、多头自注意力、FFN、残差与 pre-LN，便于把 Block 拆开讲。
"""

from __future__ import annotations

import numpy as np


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


class LayerNorm:
    def __init__(self, d_model: int, eps: float = 1e-5, random_state: int | None = 0):
        self.d_model = d_model
        self.eps = eps
        self.gamma = np.ones(d_model)
        self.beta = np.zeros(d_model)
        self.dgamma = np.zeros(d_model)
        self.dbeta = np.zeros(d_model)
        self.cache: dict = {}

    def forward(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        mu = X.mean(axis=-1, keepdims=True)
        var = X.var(axis=-1, keepdims=True)
        std = np.sqrt(var + self.eps)
        xhat = (X - mu) / std
        self.cache = {"xhat": xhat, "std": std}
        return self.gamma * xhat + self.beta

    def backward(self, d_out: np.ndarray) -> np.ndarray:
        c = self.cache
        xhat, std = c["xhat"], c["std"]
        self.dbeta = d_out.sum(axis=tuple(range(d_out.ndim - 1)))
        self.dgamma = (d_out * xhat).sum(axis=tuple(range(d_out.ndim - 1)))
        dxhat = d_out * self.gamma
        dx = (dxhat - dxhat.mean(axis=-1, keepdims=True)
              - xhat * (dxhat * xhat).mean(axis=-1, keepdims=True)) / std
        return dx


class _MHA:
    def __init__(self, d_model, n_heads, rng):
        if d_model % n_heads:
            raise ValueError("d_model 必须能被 n_heads 整除")
        self.d_model, self.n_heads = d_model, n_heads
        self.d_head = d_model // n_heads
        s = np.sqrt(2.0 / d_model)
        self.Wq = rng.normal(0, s, (d_model, d_model))
        self.Wk = rng.normal(0, s, (d_model, d_model))
        self.Wv = rng.normal(0, s, (d_model, d_model))
        self.Wo = rng.normal(0, s, (d_model, d_model))
        self.dWq = np.zeros_like(self.Wq)
        self.dWk = np.zeros_like(self.Wk)
        self.dWv = np.zeros_like(self.Wv)
        self.dWo = np.zeros_like(self.Wo)

    def _split(self, X):
        N, T, _ = X.shape
        return X.reshape(N, T, self.n_heads, self.d_head).transpose(0, 2, 1, 3)

    def _merge(self, X):
        N, H, T, D = X.shape
        return X.transpose(0, 2, 1, 3).reshape(N, T, H * D)

    def forward(self, X):
        self.X = X
        self.Q = self._split(X @ self.Wq)
        self.K = self._split(X @ self.Wk)
        self.V = self._split(X @ self.Wv)
        N, H, T, _ = self.Q.shape
        mask = np.tril(np.ones((T, T), dtype=bool))
        self.weights = np.zeros((N, H, T, T))
        outs = []
        for h in range(H):
            s = self.Q[:, h] @ self.K[:, h].swapaxes(-1, -2) / np.sqrt(self.d_head)
            s = np.where(mask[None], s, -1e9)
            w = softmax(s)
            self.weights[:, h] = w
            outs.append(w @ self.V[:, h])
        self.head_out = np.stack(outs, axis=1)
        self.merged = self._merge(self.head_out)
        return self.merged @ self.Wo

    def backward(self, d_out):
        dWo = self.merged.reshape(-1, self.d_model).T @ d_out.reshape(-1, self.d_model)
        d_merged = d_out @ self.Wo.T
        dh = d_merged.reshape(d_out.shape[0], -1, self.n_heads, self.d_head)\
            .transpose(0, 2, 1, 3)
        dQ = np.zeros_like(self.Q)
        dK = np.zeros_like(self.K)
        dV = np.zeros_like(self.V)
        T = d_out.shape[1]
        mask = np.tril(np.ones((T, T), dtype=bool))
        for h in range(self.n_heads):
            W = self.weights[:, h]
            dV[:, h] = W.swapaxes(-1, -2) @ dh[:, h]
            dW = dh[:, h] @ self.V[:, h].swapaxes(-1, -2)
            dS = W * (dW - (dW * W).sum(-1, keepdims=True))
            dS = np.where(mask[None], dS, 0.0)
            dQ[:, h] = dS @ self.K[:, h] / np.sqrt(self.d_head)
            dK[:, h] = dS.swapaxes(-1, -2) @ self.Q[:, h] / np.sqrt(self.d_head)
        Xf = self.X.reshape(-1, self.d_model)
        dQf = self._merge(dQ)
        dKf = self._merge(dK)
        dVf = self._merge(dV)
        self.dWq = Xf.T @ dQf.reshape(-1, self.d_model)
        self.dWk = Xf.T @ dKf.reshape(-1, self.d_model)
        self.dWv = Xf.T @ dVf.reshape(-1, self.d_model)
        self.dWo = dWo
        return dQf @ self.Wq.T + dKf @ self.Wk.T + dVf @ self.Wv.T


class _FFN:
    def __init__(self, d_model, d_ff, rng):
        self.W1 = rng.normal(0, np.sqrt(2 / d_model), (d_model, d_ff))
        self.b1 = np.zeros(d_ff)
        self.W2 = rng.normal(0, np.sqrt(2 / d_ff), (d_ff, d_model))
        self.b2 = np.zeros(d_model)
        self.dW1 = np.zeros_like(self.W1)
        self.db1 = np.zeros_like(self.b1)
        self.dW2 = np.zeros_like(self.W2)
        self.db2 = np.zeros_like(self.b2)

    def forward(self, X):
        self.X = X
        self.z = X @ self.W1 + self.b1
        self.h = np.maximum(self.z, 0)
        return self.h @ self.W2 + self.b2

    def backward(self, d_out):
        self.dW2 = self.h.reshape(-1, self.h.shape[-1]).T @ d_out.reshape(-1, d_out.shape[-1])
        self.db2 = d_out.sum(axis=tuple(range(d_out.ndim - 1)))
        dh = d_out @ self.W2.T
        dz = dh * (self.z > 0)
        self.dW1 = self.X.reshape(-1, self.X.shape[-1]).T @ dz.reshape(-1, dz.shape[-1])
        self.db1 = dz.sum(axis=tuple(range(dz.ndim - 1)))
        return dz @ self.W1.T


class TransformerBlock:
    """pre-LN Block：x = x + Attn(LN(x))；x = x + FFN(LN(x))。"""

    def __init__(self, d_model: int = 32, n_heads: int = 4, d_ff: int = 64,
                 causal: bool = True, vocab_size: int = 32, context: int = 16,
                 use_residual: bool = True, random_state: int | None = 0) -> None:
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_ff = d_ff
        self.causal = causal
        self.vocab_size = vocab_size
        self.context = context
        self.use_residual = use_residual
        rng = np.random.default_rng(random_state)
        self.ln1, self.ln2 = LayerNorm(d_model), LayerNorm(d_model)
        self.attn = _MHA(d_model, n_heads, rng)
        self.ffn = _FFN(d_model, d_ff, rng)
        self.E = rng.normal(0, 0.02, (vocab_size, d_model))
        self.P = rng.normal(0, 0.02, (context, d_model))
        self.Wlm = rng.normal(0, 0.02, (d_model, vocab_size))
        self.blm = np.zeros(vocab_size)
        self.dE = np.zeros_like(self.E)
        self.dP = np.zeros_like(self.P)
        self.dWlm = np.zeros_like(self.Wlm)
        self.dblm = np.zeros_like(self.blm)
        self.loss_history: list[float] = []
        self.acc_history: list[float] = []
        self._adam: dict[str, dict] = {}
        self._t = 0

    def forward(self, X: np.ndarray) -> np.ndarray:
        self.X = X
        h1 = self.ln1.forward(X)
        a = self.attn.forward(h1)
        x1 = X + a if self.use_residual else a
        h2 = self.ln2.forward(x1)
        f = self.ffn.forward(h2)
        self.x1 = x1
        return x1 + f if self.use_residual else f

    def backward(self, d_out: np.ndarray) -> np.ndarray:
        # FFN 支路：out = x1 + FFN(LN2(x1))
        d_h2 = self.ffn.backward(d_out)
        d_x1 = d_out + self.ln2.backward(d_h2) if self.use_residual else self.ln2.backward(d_h2)
        # 注意力支路：x1 = X + Attn(LN1(X))
        d_h1 = self.attn.backward(d_x1)
        dX = d_x1 + self.ln1.backward(d_h1) if self.use_residual else self.ln1.backward(d_h1)
        return dX

    def _params(self):
        return {
            "ln1.gamma": self.ln1.gamma, "ln1.beta": self.ln1.beta,
            "ln2.gamma": self.ln2.gamma, "ln2.beta": self.ln2.beta,
            "Wq": self.attn.Wq, "Wk": self.attn.Wk, "Wv": self.attn.Wv,
            "Wo": self.attn.Wo, "W1": self.ffn.W1, "b1": self.ffn.b1,
            "W2": self.ffn.W2, "b2": self.ffn.b2, "E": self.E, "P": self.P,
            "Wlm": self.Wlm, "blm": self.blm,
        }

    def _grads(self):
        return {
            "ln1.gamma": self.ln1.dgamma, "ln1.beta": self.ln1.dbeta,
            "ln2.gamma": self.ln2.dgamma, "ln2.beta": self.ln2.dbeta,
            "Wq": self.attn.dWq, "Wk": self.attn.dWk, "Wv": self.attn.dWv,
            "Wo": self.attn.dWo, "W1": self.ffn.dW1, "b1": self.ffn.db1,
            "W2": self.ffn.dW2, "b2": self.ffn.db2, "E": self.dE, "P": self.dP,
            "Wlm": self.dWlm, "blm": self.dblm,
        }

    def _adam_step(self, lr: float) -> None:
        self._t += 1
        for k, p in self._params().items():
            g = self._grads()[k]
            st = self._adam.setdefault(k, {"m": np.zeros_like(p), "v": np.zeros_like(p)})
            st["m"] = 0.9 * st["m"] + 0.1 * g
            st["v"] = 0.999 * st["v"] + 0.001 * (g * g)
            mh = st["m"] / (1 - 0.9 ** self._t)
            vh = st["v"] / (1 - 0.999 ** self._t)
            p -= lr * mh / (np.sqrt(vh) + 1e-8)

    def _windows(self, tokens):
        tokens = np.asarray(tokens, dtype=int)
        T = self.context
        xs, ys = [], []
        for i in range(0, len(tokens) - T, max(1, T // 2)):
            xs.append(tokens[i:i + T])
            ys.append(tokens[i + 1:i + T + 1])
        if not xs:
            raise ValueError("语料太短，至少需要 context+1 个 token")
        return np.array(xs), np.array(ys)



    def predict_next(self, tokens) -> tuple[int, np.ndarray]:
        """给定前缀，返回下一个 token 的 argmax 与概率。"""
        tokens = np.asarray(tokens, dtype=int)[-self.context:]
        T = len(tokens)
        out = self.forward(self.E[tokens][None] + self.P[None, :T])
        probs = softmax(out[0, -1] @ self.Wlm + self.blm)
        return int(probs.argmax()), probs

    def evaluate(self, tokens) -> dict:
        """在给定 token 序列上算 next-token loss / 准确率（不更新参数）。"""
        X, Y = self._windows(tokens)
        total, correct, n = 0.0, 0, 0
        for s in range(0, len(X), 16):
            xb, yb = X[s:s + 16], Y[s:s + 16]
            T = xb.shape[1]
            emb = self.E[xb] + self.P[:T]
            logits = self.forward(emb) @ self.Wlm + self.blm
            probs = softmax(logits)
            total += float(-np.log(np.clip(
                probs[np.arange(len(xb))[:, None], np.arange(T), yb], 1e-12, 1)).sum())
            correct += int((probs.argmax(-1) == yb).sum())
            n += yb.size
        return {"loss": total / n, "acc": correct / n}

    def train(self, tokens, epochs: int = 30, lr: float = 3e-3, batch_size: int = 16):
        X, Y = self._windows(tokens)
        rng = np.random.default_rng(0)
        self.loss_history, self.acc_history = [], []
        for _ in range(epochs):
            order = rng.permutation(len(X))
            total, correct, n = 0.0, 0, 0
            for s in range(0, len(X), batch_size):
                idx = order[s:s + batch_size]
                xb, yb = X[idx], Y[idx]
                B, T = xb.shape
                self.dE[...] = 0
                self.dP[...] = 0
                self.dWlm[...] = 0
                self.dblm[...] = 0
                emb = self.E[xb] + self.P[:T]
                out = self.forward(emb)
                logits = out @ self.Wlm + self.blm
                probs = softmax(logits)
                nll = -np.log(np.clip(probs[np.arange(B)[:, None], np.arange(T), yb], 1e-12, 1))
                total += float(nll.sum())
                correct += int((probs.argmax(-1) == yb).sum())
                n += yb.size
                dlogits = probs.copy()
                dlogits[np.arange(B)[:, None], np.arange(T), yb] -= 1
                dlogits /= yb.size
                self.dWlm = out.reshape(-1, self.d_model).T @ dlogits.reshape(-1, self.vocab_size)
                self.dblm = dlogits.sum(axis=(0, 1))
                d_out = dlogits @ self.Wlm.T
                d_emb = self.backward(d_out)
                np.add.at(self.dE, xb.reshape(-1), d_emb.reshape(-1, self.d_model))
                self.dP[:T] = d_emb.sum(axis=0)
                self._adam_step(lr)
            self.loss_history.append(total / n)
            self.acc_history.append(correct / n)
        return self.loss_history


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
