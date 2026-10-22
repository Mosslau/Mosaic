"""T5 / encoder-decoder — 手写实现

    model = T5Toy(vocab_size, ...).train(pairs)
    out = model.generate(src_ids)

encoder：双向 self-attention；decoder：causal self-attention + cross-attention。
toy 任务：字符序列 copy / reverse。
"""

from __future__ import annotations

import numpy as np

PAD, BOS, EOS = 0, 1, 2


def softmax(z):
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


class Vocab:
    def __init__(self, chars):
        self.itos = ["<pad>", "<bos>", "<eos>", "<copy>", "<rev>"] + sorted(chars)
        self.stoi = {c: i for i, c in enumerate(self.itos)}

    def encode(self, text):
        return [self.stoi[c] for c in text]

    def decode(self, ids):
        return "".join(self.itos[i] for i in ids if i >= 5)


class LayerNorm:
    def __init__(self, d, eps=1e-5):
        self.eps = eps
        self.gamma = np.ones(d)
        self.beta = np.zeros(d)
        self.dgamma = np.zeros(d)
        self.dbeta = np.zeros(d)
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

    def forward(self, Xq, Xkv=None, causal=False, key_mask=None):
        self.Xq = Xq
        self.Xkv = Xq if Xkv is None else Xkv
        self.self_attn = Xkv is None
        self.causal = causal
        self.key_mask = key_mask
        Q = self._split(Xq @ self.Wq)
        K = self._split(self.Xkv @ self.Wk)
        V = self._split(self.Xkv @ self.Wv)
        self.Q, self.K, self.V = Q, K, V
        N, H, Tq, _ = Q.shape
        Tk = K.shape[2]
        mask = None
        if causal:
            mask = np.tril(np.ones((Tq, Tk), dtype=bool))
        self.weights = np.zeros((N, H, Tq, Tk))
        outs = []
        for h in range(H):
            s = Q[:, h] @ K[:, h].swapaxes(-1, -2) / np.sqrt(self.d_head)
            if mask is not None:
                s = np.where(mask[None], s, -1e9)
            if key_mask is not None:
                s = np.where(key_mask[:, None, :], s, -1e9)
            w = softmax(s)
            if key_mask is not None:
                w = np.where(key_mask[:, None, :], w, 0.0)
            self.weights[:, h] = w
            outs.append(w @ V[:, h])
        self.merged = self._merge(np.stack(outs, 1))
        self.out = self.merged @ self.Wo
        return self.out

    def backward(self, d_out):
        dWo = self.merged.reshape(-1, self.d_model).T @ d_out.reshape(-1, self.d_model)
        dh = (d_out @ self.Wo.T).reshape(d_out.shape[0], -1, self.n_heads, self.d_head)\
            .transpose(0, 2, 1, 3)
        dQ, dK, dV = [np.zeros_like(x) for x in (self.Q, self.K, self.V)]
        Tq, Tk = d_out.shape[1], self.K.shape[2]
        cm = np.tril(np.ones((Tq, Tk), dtype=bool)) if self.causal else None
        for h in range(self.n_heads):
            W = self.weights[:, h]
            dV[:, h] = W.swapaxes(-1, -2) @ dh[:, h]
            dW = dh[:, h] @ self.V[:, h].swapaxes(-1, -2)
            dS = W * (dW - (dW * W).sum(-1, keepdims=True))
            if cm is not None:
                dS = np.where(cm[None], dS, 0.0)
            if self.key_mask is not None:
                dS = np.where(self.key_mask[:, None, :], dS, 0.0)
            dQ[:, h] = dS @ self.K[:, h] / np.sqrt(self.d_head)
            dK[:, h] = dS.swapaxes(-1, -2) @ self.Q[:, h] / np.sqrt(self.d_head)
        Xqf = self.Xq.reshape(-1, self.d_model)
        Xkvf = self.Xkv.reshape(-1, self.d_model)
        dQf, dKf, dVf = self._merge(dQ), self._merge(dK), self._merge(dV)
        self.dWq = Xqf.T @ dQf.reshape(-1, self.d_model)
        self.dWk = Xkvf.T @ dKf.reshape(-1, self.d_model)
        self.dWv = Xkvf.T @ dVf.reshape(-1, self.d_model)
        self.dWo = dWo
        dXq = dQf @ self.Wq.T
        dXkv = dKf @ self.Wk.T + dVf @ self.Wv.T
        return dXq + dXkv if self.self_attn else (dXq, dXkv)


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


class EncoderBlock:
    def __init__(self, d_model, n_heads, d_ff, rng):
        self.ln1, self.ln2 = LayerNorm(d_model), LayerNorm(d_model)
        self.attn = MHA(d_model, n_heads, rng)
        self.ffn = FFN(d_model, d_ff, rng)

    def forward(self, X, src_mask):
        self.X = X
        h1 = self.ln1.forward(X)
        a = self.attn.forward(h1, causal=False, key_mask=src_mask)
        self.x1 = X + a
        h2 = self.ln2.forward(self.x1)
        f = self.ffn.forward(h2)
        return self.x1 + f

    def backward(self, d_out):
        d_h2 = self.ffn.backward(d_out)
        d_x1 = d_out + self.ln2.backward(d_h2)
        d_h1 = self.attn.backward(d_x1)
        return d_x1 + self.ln1.backward(d_h1)


class DecoderBlock:
    def __init__(self, d_model, n_heads, d_ff, rng):
        self.ln1, self.ln2, self.ln3 = LayerNorm(d_model), LayerNorm(d_model), LayerNorm(d_model)
        self.self_attn = MHA(d_model, n_heads, rng)
        self.cross_attn = MHA(d_model, n_heads, rng)
        self.ffn = FFN(d_model, d_ff, rng)

    def forward(self, Y, memory, src_mask):
        self.Y = Y
        self.memory = memory
        h1 = self.ln1.forward(Y)
        a = self.self_attn.forward(h1, causal=True)
        self.y1 = Y + a
        h2 = self.ln2.forward(self.y1)
        c = self.cross_attn.forward(h2, memory, causal=False, key_mask=src_mask)
        self.y2 = self.y1 + c
        h3 = self.ln3.forward(self.y2)
        f = self.ffn.forward(h3)
        return self.y2 + f

    def backward(self, d_out):
        d_h3 = self.ffn.backward(d_out)
        d_y2 = d_out + self.ln3.backward(d_h3)
        d_h2, d_mem = self.cross_attn.backward(d_y2)
        d_y1 = d_y2 + self.ln2.backward(d_h2)
        d_h1 = self.self_attn.backward(d_y1)
        dY = d_y1 + self.ln1.backward(d_h1)
        return dY, d_mem


class T5Toy:
    def __init__(self, vocab_size: int, src_len: int = 4, tgt_len: int = 5,
                 d_model: int = 32, n_heads: int = 4, d_ff: int = 64,
                 random_state: int | None = 0):
        if src_len < 1 or tgt_len < 1:
            raise ValueError("src_len/tgt_len 必须 >=1")
        self.vocab_size = vocab_size
        self.src_len, self.tgt_len = src_len, tgt_len
        self.d_model = d_model
        rng = np.random.default_rng(random_state)
        self.E = rng.normal(0, 0.02, (vocab_size, d_model))
        self.Pe = rng.normal(0, 0.02, (src_len, d_model))
        self.Pd = rng.normal(0, 0.02, (tgt_len, d_model))
        self.enc = EncoderBlock(d_model, n_heads, d_ff, rng)
        self.dec = DecoderBlock(d_model, n_heads, d_ff, rng)
        self.Wlm = rng.normal(0, 0.02, (d_model, vocab_size))
        self.blm = np.zeros(vocab_size)
        self.loss_history, self.acc_history = [], []
        self._adam, self._t = {}, 0

    def _params(self):
        d = {"E": self.E, "Pe": self.Pe, "Pd": self.Pd, "Wlm": self.Wlm, "blm": self.blm}
        for name, b in (("e", self.enc), ("d", self.dec)):
            d.update({f"{name}.ln1.gamma": b.ln1.gamma, f"{name}.ln1.beta": b.ln1.beta,
                      f"{name}.ln2.gamma": b.ln2.gamma, f"{name}.ln2.beta": b.ln2.beta})
            if name == "d":
                d.update({f"{name}.ln3.gamma": b.ln3.gamma, f"{name}.ln3.beta": b.ln3.beta})
            if name == "e":
                d.update({f"{name}.Wq": b.attn.Wq, f"{name}.Wk": b.attn.Wk,
                          f"{name}.Wv": b.attn.Wv, f"{name}.Wo": b.attn.Wo})
            else:
                for sub in ("self_attn", "cross_attn"):
                    att = getattr(b, sub)
                    d.update({f"{name}.{sub}.Wq": att.Wq, f"{name}.{sub}.Wk": att.Wk,
                              f"{name}.{sub}.Wv": att.Wv, f"{name}.{sub}.Wo": att.Wo})
            d.update({f"{name}.W1": b.ffn.W1, f"{name}.b1": b.ffn.b1,
                      f"{name}.W2": b.ffn.W2, f"{name}.b2": b.ffn.b2})
        return d

    def _grads(self):
        d = {"E": self.dE, "Pe": self.dPe, "Pd": self.dPd, "Wlm": self.dWlm, "blm": self.dblm}
        for name, b in (("e", self.enc), ("d", self.dec)):
            d.update({f"{name}.ln1.gamma": b.ln1.dgamma, f"{name}.ln1.beta": b.ln1.dbeta,
                      f"{name}.ln2.gamma": b.ln2.dgamma, f"{name}.ln2.beta": b.ln2.dbeta})
            if name == "d":
                d.update({f"{name}.ln3.gamma": b.ln3.dgamma,
                          f"{name}.ln3.beta": b.ln3.dbeta})
            if name == "e":
                d.update({f"{name}.Wq": b.attn.dWq, f"{name}.Wk": b.attn.dWk,
                          f"{name}.Wv": b.attn.dWv, f"{name}.Wo": b.attn.dWo})
            else:
                for sub in ("self_attn", "cross_attn"):
                    att = getattr(b, sub)
                    d.update({f"{name}.{sub}.Wq": att.dWq, f"{name}.{sub}.Wk": att.dWk,
                              f"{name}.{sub}.Wv": att.dWv, f"{name}.{sub}.Wo": att.dWo})
            d.update({f"{name}.W1": b.ffn.dW1, f"{name}.b1": b.ffn.db1,
                      f"{name}.W2": b.ffn.dW2, f"{name}.b2": b.ffn.db2})
        return d

    def _step(self, lr):
        self._t += 1
        for k, p in self._params().items():
            g = self._grads()[k]
            st = self._adam.setdefault(k, {"m": np.zeros_like(p), "v": np.zeros_like(p)})
            st["m"] = 0.9 * st["m"] + 0.1 * g
            st["v"] = 0.999 * st["v"] + 0.001 * g * g
            p -= lr * (st["m"] / (1 - 0.9 ** self._t)) / (
                np.sqrt(st["v"] / (1 - 0.999 ** self._t)) + 1e-8)

    def forward(self, src, tgt_in):
        src = np.asarray(src, dtype=int)
        tgt_in = np.asarray(tgt_in, dtype=int)
        if src.ndim != 2 or src.shape[1] != self.src_len:
            raise ValueError(f"src 应为 (B,{self.src_len})")
        if tgt_in.ndim != 2 or not (1 <= tgt_in.shape[1] <= self.tgt_len):
            raise ValueError(f"tgt_in 长度应在 1..{self.tgt_len}")
        if src.min() < 0 or src.max() >= self.vocab_size or \
           tgt_in.min() < 0 or tgt_in.max() >= self.vocab_size:
            raise ValueError("token id 越界")
        self.src, self.tgt_in = src, tgt_in
        src_mask = src != PAD
        self.src_mask = src_mask
        mem = self.enc.forward(self.E[src] + self.Pe, src_mask)
        self.memory = mem
        dec = self.dec.forward(self.E[tgt_in] + self.Pd[:tgt_in.shape[1]], mem, src_mask)
        self.dec_out = dec
        return dec @ self.Wlm + self.blm

    def backward(self, dlogits):
        self.dE = np.zeros_like(self.E)
        self.dPe = np.zeros_like(self.Pe)
        self.dPd = np.zeros_like(self.Pd)
        self.dWlm = self.dec_out.reshape(-1, self.d_model).T @ dlogits.reshape(-1, self.vocab_size)
        self.dblm = dlogits.sum(axis=(0, 1))
        d_dec = dlogits @ self.Wlm.T
        dY, d_mem = self.dec.backward(d_dec)
        d_mem_enc = self.enc.backward(d_mem)
        np.add.at(self.dE, self.src.reshape(-1), d_mem_enc.reshape(-1, self.d_model))
        np.add.at(self.dE, self.tgt_in.reshape(-1), dY.reshape(-1, self.d_model))
        self.dPe = d_mem_enc.sum(0)
        self.dPd[:self.tgt_in.shape[1]] = dY.sum(0)

    def train(self, pairs, epochs=80, lr=3e-3):
        if not pairs:
            raise ValueError("pairs 不能为空")
        src = np.array([p[0] for p in pairs])
        tin = np.array([p[1] for p in pairs])
        tout = np.array([p[2] for p in pairs])
        N, T = tout.shape
        self.loss_history, self.acc_history = [], []
        for _ in range(epochs):
            logits = self.forward(src, tin)
            probs = softmax(logits)
            nll = -np.log(np.clip(probs[np.arange(N)[:, None], np.arange(T), tout], 1e-12, 1))
            self.loss_history.append(float(nll.mean()))
            self.acc_history.append(float((probs.argmax(-1) == tout).mean()))
            dlogits = probs.copy()
            dlogits[np.arange(N)[:, None], np.arange(T), tout] -= 1
            dlogits /= tout.size
            self.backward(dlogits)
            self._step(lr)
        return self.loss_history

    def encode(self, src):
        src = np.asarray(src, dtype=int)
        return self.enc.forward(self.E[src] + self.Pe, src != PAD)

    def generate(self, src_ids, max_steps=8, vocab: Vocab | None = None):
        src_arr = np.asarray(src_ids, dtype=int)
        if src_arr.ndim != 1 or len(src_arr) != self.src_len:
            raise ValueError(f"src_ids 长度应为 {self.src_len}")
        if src_arr.min() < 0 or src_arr.max() >= self.vocab_size:
            raise ValueError("src_ids 越界")
        if max_steps < 1:
            raise ValueError("max_steps 必须 >=1")
        src = src_arr[None]
        mem = self.encode(src)
        ids = [BOS]
        for _ in range(min(max_steps, self.tgt_len - 1)):
            tgt = np.array(ids)[None]
            dec = self.dec.forward(self.E[tgt] + self.Pd[:len(ids)], mem, src != PAD)
            logits = dec @ self.Wlm + self.blm
            nxt = int(logits[0, -1].argmax())
            ids.append(nxt)
            if nxt == EOS:
                break
        return ids


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现库，实验入口是 demo.py：uv run python demo.py")
