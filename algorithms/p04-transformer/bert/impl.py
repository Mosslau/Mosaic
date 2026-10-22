"""BERT / MLM — 手写实现骨架（encoder-only）

    model = BertMLM(d_model=32, n_heads=4, n_layers=1).train(tokens)
    Z = model.encode(tokens)
    pred = model.predict_masked(masked_tokens)

TODO：实现非 causal 的多头注意力、MLM mask、只对 masked 位置计损、[CLS] 探针。
"""

from __future__ import annotations

import numpy as np


class BertMLM:
    def __init__(self, d_model: int = 32, n_heads: int = 4, n_layers: int = 1,
                 vocab_size: int = 64, random_state: int | None = 0) -> None:
        self.d_model = d_model
        self.n_heads = n_heads
        self.n_layers = n_layers
        self.vocab_size = vocab_size
        self.random_state = random_state
        self.loss_history: list[float] = []

    def forward(self, tokens: np.ndarray, mask: np.ndarray | None = None):
        raise NotImplementedError("TODO: BERT encoder + MLM head 前向")

    def backward(self, dlogits: np.ndarray, cache: dict) -> dict:
        raise NotImplementedError("TODO: MLM 反向（只对 masked 位置）")

    def train(self, tokens: np.ndarray, epochs: int = 50, lr: float = 1e-3):
        raise NotImplementedError("TODO: mask 15% token、只对被 mask 位置计损、Adam")

    def encode(self, tokens: np.ndarray) -> np.ndarray:
        raise NotImplementedError("TODO: 返回 [CLS] 或最后一层表示")

    def predict_masked(self, tokens: np.ndarray) -> np.ndarray:
        raise NotImplementedError("TODO: 预测 masked 位置的 token")


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现骨架，实验入口是 demo.py：uv run python demo.py")
