"""Mini-GPT — 手写字符级自回归语言模型

    gpt = MiniGPT(vocab_size=..., context=16, n_layers=2).train(tokens)
    out = gpt.generate("the cat", n_steps=40, temperature=0.8, top_k=5)

结构：token embedding + 可学习位置嵌入 + N 个 pre-LN causal Block + LM head。
"""

from __future__ import annotations

import numpy as np


def softmax(z):
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


class CharTokenizer:
    def __init__(self, unk: str = "<unk>"):
        self.unk = unk
        self.stoi: dict[str, int] = {}
        self.itos: list[str] = []

    def fit(self, text: str) -> CharTokenizer:
        # 按频次降序、字符升序，保证跨运行可复现
        freq = {}
        for c in text:
            freq[c] = freq.get(c, 0) + 1
        chars = sorted(freq, key=lambda c: (-freq[c], c))
        self.itos = [self.unk] + chars
        self.stoi = {c: i for i, c in enumerate(self.itos)}
        return self

    def encode(self, text: str) -> np.ndarray:
        return np.array([self.stoi.get(c, 0) for c in text], dtype=int)

    def decode(self, ids) -> str:
        return "".join(self.itos[int(i)] for i in ids)


class LayerNorm:
    def __init__(self, d_model, eps=1e-5):
        self.eps = eps
        self.gamma = np.ones(d_model)
        self.beta = np.zeros(d_model)
        self.dgamma = np.zeros(d_model)
        self.dbeta = np.zeros(d_model)
        self.cache = {}

    def forward(self, X):
        mu = X.mean(-1, keepdims=True)
        var = X.var(-1, keepdims=True)
        std = np.sqrt(var + self.eps)
        xhat = (X - mu) / std
        self.cache = {"xhat": xhat, "std": std}
        return self.gamma * xhat + self.beta

    def backward(self, d_out):
        xhat, std = self.cache["xhat"], self.cache["std"]
        self.dbeta = d_out.sum(axis=tuple(range(d_out.ndim - 1)))
        self.dgamma = (d_out * xhat).sum(axis=tuple(range(d_out.ndim - 1)))
        dx = d_out * self.gamma
        return (dx - dx.mean(-1, keepdims=True)
                - xhat * (dx * xhat).mean(-1, keepdims=True)) / std


class MHA:
    def __init__(self, d_model, n_heads, rng):
        if d_model % n_heads:
            raise ValueError("d_model 必须能被 n_heads 整除")
        self.d_model, self.n_heads = d_model, n_heads
        self.d_head = d_model // n_heads
        s = np.sqrt(2 / d_model)
        self.Wq, self.Wk, self.Wv, self.Wo = [rng.normal(0, s, (d_model, d_model))
                                            for _ in range(4)]
        self.dWq, self.dWk, self.dWv, self.dWo = [np.zeros_like(x)
                                                  for x in (self.Wq, self.Wk, self.Wv, self.Wo)]

    def _split(self, X):
        N, T, _ = X.shape
        return X.reshape(N, T, self.n_heads, self.d_head).transpose(0, 2, 1, 3)

    def _merge(self, X):
        N, H, T, D = X.shape
        return X.transpose(0, 2, 1, 3).reshape(N, T, H * D)

    def forward(self, X):
        self.X = X
        Q, K, V = self._split(X @ self.Wq), self._split(X @ self.Wk), self._split(X @ self.Wv)
        self.Q, self.K, self.V = Q, K, V
        N, H, T, _ = Q.shape
        cm = np.tril(np.ones((T, T), dtype=bool))
        self.weights = np.zeros((N, H, T, T))
        outs = []
        for h in range(H):
            s = Q[:, h] @ K[:, h].swapaxes(-1, -2) / np.sqrt(self.d_head)
            s = np.where(cm[None], s, -1e9)
            w = softmax(s)
            self.weights[:, h] = w
            outs.append(w @ V[:, h])
        self.merged = self._merge(np.stack(outs, 1))
        return self.merged @ self.Wo

    def backward(self, d_out):
        dWo = self.merged.reshape(-1, self.d_model).T @ d_out.reshape(-1, self.d_model)
        dh = (d_out @ self.Wo.T).reshape(d_out.shape[0], -1, self.n_heads, self.d_head)\
            .transpose(0, 2, 1, 3)
        dQ, dK, dV = [np.zeros_like(x) for x in (self.Q, self.K, self.V)]
        T = d_out.shape[1]
        cm = np.tril(np.ones((T, T), dtype=bool))
        for h in range(self.n_heads):
            W = self.weights[:, h]
            dV[:, h] = W.swapaxes(-1, -2) @ dh[:, h]
            dW = dh[:, h] @ self.V[:, h].swapaxes(-1, -2)
            dS = W * (dW - (dW * W).sum(-1, keepdims=True))
            dS = np.where(cm[None], dS, 0.0)
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
        self.dW1, self.db1 = np.zeros_like(self.W1), np.zeros_like(self.b1)
        self.dW2, self.db2 = np.zeros_like(self.W2), np.zeros_like(self.b2)

    def forward(self, X):
        self.X = X
        self.z = X @ self.W1 + self.b1
        self.h = np.maximum(self.z, 0)
        return self.h @ self.W2 + self.b2

    def backward(self, d_out):
        self.dW2 = self.h.reshape(-1, self.h.shape[-1]).T @ d_out.reshape(-1, d_out.shape[-1])
        self.db2 = d_out.sum(axis=tuple(range(d_out.ndim - 1)))
        dz = (d_out @ self.W2.T) * (self.z > 0)
        self.dW1 = self.X.reshape(-1, self.X.shape[-1]).T @ dz.reshape(-1, dz.shape[-1])
        self.db1 = dz.sum(axis=tuple(range(dz.ndim - 1)))
        return dz @ self.W1.T


class Block:
    def __init__(self, d_model, n_heads, d_ff, rng):
        self.ln1, self.ln2 = LayerNorm(d_model), LayerNorm(d_model)
        self.attn = MHA(d_model, n_heads, rng)
        self.ffn = FFN(d_model, d_ff, rng)

    def forward(self, X):
        self.X = X
        self.h1 = self.ln1.forward(X)
        self.a = self.attn.forward(self.h1)
        self.x1 = X + self.a
        self.h2 = self.ln2.forward(self.x1)
        self.f = self.ffn.forward(self.h2)
        return self.x1 + self.f

    def backward(self, d_out):
        d_h2 = self.ffn.backward(d_out)
        d_x1 = d_out + self.ln2.backward(d_h2)
        d_h1 = self.attn.backward(d_x1)
        return d_x1 + self.ln1.backward(d_h1)


class MiniGPT:
    def __init__(self, vocab_size: int, context: int = 16, d_model: int = 32,
                 n_heads: int = 4, n_layers: int = 2, d_ff: int = 64,
                 random_state: int | None = 0) -> None:
        self.vocab_size = vocab_size
        if context < 1 or n_layers < 1:
            raise ValueError("context/n_layers 必须 >=1")
        self.context = context
        self.d_model = d_model
        self.n_layers = n_layers
        rng = np.random.default_rng(random_state)
        self.E = rng.normal(0, 0.02, (vocab_size, d_model))
        self.P = rng.normal(0, 0.02, (context, d_model))
        self.blocks = [Block(d_model, n_heads, d_ff, rng) for _ in range(n_layers)]
        self.Wlm = rng.normal(0, 0.02, (d_model, vocab_size))
        self.blm = np.zeros(vocab_size)
        self.loss_history: list[float] = []
        self.acc_history: list[float] = []
        self._adam: dict[str, dict] = {}
        self._t = 0

    def _all_params(self):
        d = {"E": self.E, "P": self.P, "Wlm": self.Wlm, "blm": self.blm}
        for i, b in enumerate(self.blocks):
            d.update({f"b{i}.ln1.gamma": b.ln1.gamma, f"b{i}.ln1.beta": b.ln1.beta,
                      f"b{i}.ln2.gamma": b.ln2.gamma, f"b{i}.ln2.beta": b.ln2.beta,
                      f"b{i}.Wq": b.attn.Wq, f"b{i}.Wk": b.attn.Wk,
                      f"b{i}.Wv": b.attn.Wv, f"b{i}.Wo": b.attn.Wo,
                      f"b{i}.W1": b.ffn.W1, f"b{i}.b1": b.ffn.b1,
                      f"b{i}.W2": b.ffn.W2, f"b{i}.b2": b.ffn.b2})
        return d

    def _all_grads(self):
        d = {"E": self.dE, "P": self.dP, "Wlm": self.dWlm, "blm": self.dblm}
        for i, b in enumerate(self.blocks):
            d.update({f"b{i}.ln1.gamma": b.ln1.dgamma, f"b{i}.ln1.beta": b.ln1.dbeta,
                      f"b{i}.ln2.gamma": b.ln2.dgamma, f"b{i}.ln2.beta": b.ln2.dbeta,
                      f"b{i}.Wq": b.attn.dWq, f"b{i}.Wk": b.attn.dWk,
                      f"b{i}.Wv": b.attn.dWv, f"b{i}.Wo": b.attn.dWo,
                      f"b{i}.W1": b.ffn.dW1, f"b{i}.b1": b.ffn.db1,
                      f"b{i}.W2": b.ffn.dW2, f"b{i}.b2": b.ffn.db2})
        return d

    def _step(self, lr):
        self._t += 1
        for k, p in self._all_params().items():
            g = self._all_grads()[k]
            st = self._adam.setdefault(k, {"m": np.zeros_like(p), "v": np.zeros_like(p)})
            st["m"] = 0.9 * st["m"] + 0.1 * g
            st["v"] = 0.999 * st["v"] + 0.001 * g * g
            p -= lr * (st["m"] / (1 - 0.9 ** self._t)) / (
                np.sqrt(st["v"] / (1 - 0.999 ** self._t)) + 1e-8)

    def forward(self, tokens):
        tokens = np.asarray(tokens, dtype=int)
        if tokens.ndim != 2 or tokens.shape[1] < 1:
            raise ValueError("tokens 应为 (B,T)，T>=1")
        if tokens.shape[1] > self.context:
            raise ValueError(f"T={tokens.shape[1]} 超过 context={self.context}")
        if tokens.min() < 0 or tokens.max() >= self.vocab_size:
            raise ValueError("token id 越界")
        N, T = tokens.shape
        self.tokens = tokens
        self.dE = np.zeros_like(self.E)
        self.dP = np.zeros_like(self.P)
        X = self.E[tokens] + self.P[:T]
        self.X0 = X
        for b in self.blocks:
            X = b.forward(X)
        self.hidden = X
        return X @ self.Wlm + self.blm

    def backward(self, dlogits):
        dWlm = self.hidden.reshape(-1, self.d_model).T @ dlogits.reshape(-1, self.vocab_size)
        self.dWlm = dWlm
        self.dblm = dlogits.sum(axis=(0, 1))
        dX = dlogits @ self.Wlm.T
        for b in reversed(self.blocks):
            dX = b.backward(dX)
        np.add.at(self.dE, self.tokens.reshape(-1), dX.reshape(-1, self.d_model))
        self.dP[:self.tokens.shape[1]] = dX.sum(0)
        return dX

    def _windows(self, tokens):
        T = self.context
        xs, ys = [], []
        for i in range(0, len(tokens) - T, max(1, T // 2)):
            xs.append(tokens[i:i + T])
            ys.append(tokens[i + 1:i + T + 1])
        if not xs:
            raise ValueError("语料太短")
        return np.array(xs), np.array(ys)

    def train(self, tokens, epochs: int = 60, lr: float = 3e-3, batch_size: int = 32):
        tokens = np.asarray(tokens, dtype=int)
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
                logits = self.forward(xb)
                probs = softmax(logits)
                nll = -np.log(np.clip(probs[np.arange(B)[:, None], np.arange(T), yb], 1e-12, 1))
                total += float(nll.sum())
                correct += int((probs.argmax(-1) == yb).sum())
                n += yb.size
                dlogits = probs.copy()
                dlogits[np.arange(B)[:, None], np.arange(T), yb] -= 1
                dlogits /= yb.size
                self.backward(dlogits)
                self._step(lr)
            self.loss_history.append(total / n)
            self.acc_history.append(correct / n)
        return self.loss_history

    def evaluate(self, tokens):
        X, Y = self._windows(np.asarray(tokens, dtype=int))
        total, correct, n = 0.0, 0, 0
        for s in range(0, len(X), 32):
            xb, yb = X[s:s + 32], Y[s:s + 32]
            B, T = xb.shape
            probs = softmax(self.forward(xb))
            total += float(-np.log(np.clip(
                probs[np.arange(B)[:, None], np.arange(T), yb], 1e-12, 1)).sum())
            correct += int((probs.argmax(-1) == yb).sum())
            n += yb.size
        return {"loss": total / n, "acc": correct / n}

    def generate(self, prompt: str, tokenizer: CharTokenizer, n_steps: int = 40,
                 temperature: float = 1.0, top_k: int | None = None, seed: int = 0):
        if not prompt:
            raise ValueError("prompt 不能为空")
        if temperature < 0:
            raise ValueError("temperature 不能为负")
        if top_k is not None and top_k < 1:
            raise ValueError("top_k 必须 >=1 或 None")
        rng = np.random.default_rng(seed)
        ids = list(tokenizer.encode(prompt))
        for _ in range(n_steps):
            ctx = np.array(ids[-self.context:])[None]
            probs = softmax(self.forward(ctx)[0, -1])
            if temperature <= 0:
                nxt = int(probs.argmax())
            else:
                logits = np.log(np.clip(probs, 1e-12, 1)) / temperature
                if top_k is not None:
                    k = min(top_k, len(logits))
                    keep = np.argsort(logits)[-k:]
                    mask = np.ones_like(logits, dtype=bool)
                    mask[keep] = False
                    logits[mask] = -1e9
                p = softmax(logits)
                nxt = int(rng.choice(len(p), p=p))
            ids.append(nxt)
        return tokenizer.decode(ids)


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
