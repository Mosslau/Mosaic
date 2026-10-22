"""BERT / MLM — 手写实现（encoder-only）

    model = BertMLM(vocab_size=..., context=16).train(tokens, epochs=100)
    Z = model.encode(tokens)          # [CLS] 表示
    pred = model.predict_masked(tokens)

本文件实现：非 causal 多头自注意力、LayerNorm、FFN、残差、MLM head。
没有 generate：BERT 的目标是恢复被 mask 的 token，不是自回归生成。
"""

from __future__ import annotations

import numpy as np


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


class LayerNorm:
    def __init__(self, d_model: int, eps: float = 1e-5):
        self.eps = eps
        self.gamma = np.ones(d_model)
        self.beta = np.zeros(d_model)
        self.dgamma = np.zeros(d_model)
        self.dbeta = np.zeros(d_model)
        self.cache: dict = {}

    def forward(self, X):
        mu = X.mean(axis=-1, keepdims=True)
        var = X.var(axis=-1, keepdims=True)
        std = np.sqrt(var + self.eps)
        xhat = (X - mu) / std
        self.cache = {"xhat": xhat, "std": std}
        return self.gamma * xhat + self.beta

    def backward(self, d_out):
        c = self.cache
        xhat, std = c["xhat"], c["std"]
        self.dbeta = d_out.sum(axis=tuple(range(d_out.ndim - 1)))
        self.dgamma = (d_out * xhat).sum(axis=tuple(range(d_out.ndim - 1)))
        dxhat = d_out * self.gamma
        return (dxhat - dxhat.mean(-1, keepdims=True)
                - xhat * (dxhat * xhat).mean(-1, keepdims=True)) / std


class MultiHeadAttention:
    """非 causal：每个位置可以看所有非 pad 位置。"""

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

    def forward(self, X, key_mask=None):
        self.X = X
        self.key_mask = key_mask
        self.Q = self._split(X @ self.Wq)
        self.K = self._split(X @ self.Wk)
        self.V = self._split(X @ self.Wv)
        N, H, T, _ = self.Q.shape
        self.weights = np.zeros((N, H, T, T))
        outs = []
        for h in range(H):
            s = self.Q[:, h] @ self.K[:, h].swapaxes(-1, -2) / np.sqrt(self.d_head)
            if key_mask is not None:
                s = np.where(key_mask[:, None, :], s, -1e9)
            w = softmax(s)
            if key_mask is not None:
                w = np.where(key_mask[:, None, :], w, 0.0)
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
        for h in range(self.n_heads):
            W = self.weights[:, h]
            dV[:, h] = W.swapaxes(-1, -2) @ dh[:, h]
            dW = dh[:, h] @ self.V[:, h].swapaxes(-1, -2)
            dS = W * (dW - (dW * W).sum(-1, keepdims=True))
            if self.key_mask is not None:
                dS = np.where(self.key_mask[:, None, :], dS, 0.0)
            dQ[:, h] = dS @ self.K[:, h] / np.sqrt(self.d_head)
            dK[:, h] = dS.swapaxes(-1, -2) @ self.Q[:, h] / np.sqrt(self.d_head)
        Xf = self.X.reshape(-1, self.d_model)
        dQf, dKf, dVf = self._merge(dQ), self._merge(dK), self._merge(dV)
        self.dWq = Xf.T @ dQf.reshape(-1, self.d_model)
        self.dWk = Xf.T @ dKf.reshape(-1, self.d_model)
        self.dWv = Xf.T @ dVf.reshape(-1, self.d_model)
        self.dWo = dWo
        return dQf @ self.Wq.T + dKf @ self.Wk.T + dVf @ self.Wv.T


class FFN:
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


class BertMLM:
    def __init__(self, vocab_size: int, context: int = 16, d_model: int = 32,
                 n_heads: int = 4, d_ff: int = 64, pad_id: int = 0,
                 mask_id: int = 1, cls_id: int = 2, sep_id: int = 3,
                 random_state: int | None = 0) -> None:
        self.vocab_size = vocab_size
        self.context = context
        self.d_model = d_model
        self.pad_id, self.mask_id, self.cls_id = pad_id, mask_id, cls_id
        self.sep_id = sep_id
        rng = np.random.default_rng(random_state)
        self.ln1, self.ln2 = LayerNorm(d_model), LayerNorm(d_model)
        self.attn = MultiHeadAttention(d_model, n_heads, rng)
        self.ffn = FFN(d_model, d_ff, rng)
        self.E = rng.normal(0, 0.02, (vocab_size, d_model))
        self.P = rng.normal(0, 0.02, (context, d_model))
        self.Wlm = rng.normal(0, 0.02, (d_model, vocab_size))
        self.blm = np.zeros(vocab_size)
        self.loss_history: list[float] = []
        self.acc_history: list[float] = []
        self._adam: dict[str, dict] = {}
        self._t = 0

    def _forward(self, tokens):
        tokens = np.asarray(tokens, dtype=int)
        N, T = tokens.shape
        self.tokens = tokens
        X = self.E[tokens] + self.P[:T]
        self.X = X
        h1 = self.ln1.forward(X)
        a = self.attn.forward(h1, key_mask=tokens != self.pad_id)
        x1 = X + a
        h2 = self.ln2.forward(x1)
        f = self.ffn.forward(h2)
        self.x1 = x1
        self.out = x1 + f
        return self.out @ self.Wlm + self.blm

    def forward(self, tokens, mask=None):
        return self._forward(tokens)

    def _backward(self, dlogits):
        self._dE = np.zeros_like(self.E)
        self._dP = np.zeros_like(self.P)
        d_out = dlogits @ self.Wlm.T
        d_h2 = self.ffn.backward(d_out)
        d_x1 = d_out + self.ln2.backward(d_h2)
        d_h1 = self.attn.backward(d_x1)
        dX = d_x1 + self.ln1.backward(d_h1)
        np.add.at(self._dE, self.tokens.reshape(-1), dX.reshape(-1, self.d_model))
        self._dP[:self.tokens.shape[1]] = dX.sum(axis=0)
        self._dWlm = self.out.reshape(-1, self.d_model).T @ dlogits.reshape(-1, self.vocab_size)
        self._dblm = dlogits.sum(axis=(0, 1))
        return dX

    def _params(self):
        return {"ln1.gamma": self.ln1.gamma, "ln1.beta": self.ln1.beta,
                "ln2.gamma": self.ln2.gamma, "ln2.beta": self.ln2.beta,
                "Wq": self.attn.Wq, "Wk": self.attn.Wk, "Wv": self.attn.Wv,
                "Wo": self.attn.Wo, "W1": self.ffn.W1, "b1": self.ffn.b1,
                "W2": self.ffn.W2, "b2": self.ffn.b2, "E": self.E, "P": self.P,
                "Wlm": self.Wlm, "blm": self.blm}

    def _grads(self):
        return {"ln1.gamma": self.ln1.dgamma, "ln1.beta": self.ln1.dbeta,
                "ln2.gamma": self.ln2.dgamma, "ln2.beta": self.ln2.dbeta,
                "Wq": self.attn.dWq, "Wk": self.attn.dWk, "Wv": self.attn.dWv,
                "Wo": self.attn.dWo, "W1": self.ffn.dW1, "b1": self.ffn.db1,
                "W2": self.ffn.dW2, "b2": self.ffn.db2, "E": self._dE, "P": self._dP,
                "Wlm": self._dWlm, "blm": self._dblm}

    def _step(self, lr):
        self._t += 1
        for k, p in self._params().items():
            g = self._grads()[k]
            st = self._adam.setdefault(k, {"m": np.zeros_like(p), "v": np.zeros_like(p)})
            st["m"] = 0.9 * st["m"] + 0.1 * g
            st["v"] = 0.999 * st["v"] + 0.001 * (g * g)
            p -= lr * (st["m"] / (1 - 0.9 ** self._t)) / (
                np.sqrt(st["v"] / (1 - 0.999 ** self._t)) + 1e-8)

    def _make_mask(self, tokens, rng, mask_prob=0.15):
        inp = tokens.copy()
        target = tokens.copy()
        mask_pos = np.zeros_like(tokens, dtype=bool)
        eligible = (tokens != self.pad_id) & (tokens != self.cls_id) & \
                   (tokens != self.sep_id) & (tokens != self.mask_id)
        for n in range(tokens.shape[0]):
            idx = np.flatnonzero(eligible[n])
            if len(idx) == 0:
                continue
            k = max(1, int(round(len(idx) * mask_prob)))
            chosen = rng.choice(idx, size=k, replace=False)
            mask_pos[n, chosen] = True
            for j in chosen:
                r = rng.random()
                if r < 0.8:
                    inp[n, j] = self.mask_id
                elif r < 0.9:
                    inp[n, j] = int(rng.integers(5, self.vocab_size))
        return inp, target, mask_pos

    def evaluate(self, tokens, seed: int = 123):
        inp, target, mask_pos = self._make_mask(np.asarray(tokens, dtype=int),
                                                np.random.default_rng(seed))
        probs = softmax(self._forward(inp))
        sel = probs[mask_pos]
        tgt = target[mask_pos]
        loss = float(-np.log(np.clip(sel[np.arange(len(tgt)), tgt], 1e-12, 1)).mean())
        acc = float((probs.argmax(-1)[mask_pos] == tgt).mean())
        return {"loss": loss, "acc": acc, "masked": int(mask_pos.sum())}

    def train(self, tokens, epochs: int = 80, lr: float = 3e-3, mask_prob: float = 0.15,
              seed: int = 0):
        tokens = np.asarray(tokens, dtype=int)
        rng = np.random.default_rng(seed)
        self.loss_history, self.acc_history = [], []
        for _ in range(epochs):
            inp, target, mask_pos = self._make_mask(tokens, rng, mask_prob)
            logits = self._forward(inp)
            probs = softmax(logits)
            sel = probs[mask_pos]
            tgt = target[mask_pos]
            nll = -np.log(np.clip(sel[np.arange(len(tgt)), tgt], 1e-12, 1))
            loss = float(nll.mean())
            correct = int((probs.argmax(-1)[mask_pos] == tgt).sum())
            self.loss_history.append(loss)
            self.acc_history.append(correct / max(mask_pos.sum(), 1))
            dlogits = probs.copy()
            dlogits[np.arange(tokens.shape[0])[:, None], np.arange(tokens.shape[1])[None, :],
                    target] -= 1
            dlogits *= mask_pos[..., None]
            dlogits /= max(mask_pos.sum(), 1)
            self._backward(dlogits)
            self._step(lr)
        return self.loss_history

    def encode(self, tokens):
        # [CLS] 在位置 0；直接重算 hidden，返回最后一层表示。
        tokens = np.asarray(tokens, dtype=int)
        T = tokens.shape[1]
        X = self.E[tokens] + self.P[:T]
        h1 = self.ln1.forward(X)
        a = self.attn.forward(h1, key_mask=tokens != self.pad_id)
        x1 = X + a
        h2 = self.ln2.forward(x1)
        f = self.ffn.forward(h2)
        return (x1 + f)[:, 0]

    def predict_masked(self, tokens):
        logits = self._forward(np.asarray(tokens, dtype=int))
        return logits.argmax(-1)


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
