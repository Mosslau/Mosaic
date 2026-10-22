"""T5 / encoder-decoder — 手写实现骨架

    model = T5Toy(d_model=32, n_heads=4, n_layers=1).train(pairs)
    out = model.generate(src, n_steps=16)

TODO：encoder 双向 self-attn；decoder causal self-attn + cross-attn；
teacher forcing（tgt 右移）、生成循环。
"""

from __future__ import annotations

import numpy as np


class T5Toy:
    def __init__(self, d_model: int = 32, n_heads: int = 4, n_layers: int = 1,
                 vocab_size: int = 64, random_state: int | None = 0) -> None:
        self.d_model = d_model
        self.n_heads = n_heads
        self.n_layers = n_layers
        self.vocab_size = vocab_size
        self.random_state = random_state
        self.loss_history: list[float] = []

    def forward(self, src: np.ndarray, tgt: np.ndarray):
        raise NotImplementedError("TODO: encoder + decoder + cross-attention 前向")

    def backward(self, dlogits: np.ndarray, cache: dict) -> dict:
        raise NotImplementedError("TODO: decoder→cross→encoder 全链路反向")

    def train(self, pairs, epochs: int = 50, lr: float = 1e-3):
        raise NotImplementedError("TODO: teacher forcing + Adam")

    def generate(self, src: np.ndarray, n_steps: int = 16, temperature: float = 1.0):
        raise NotImplementedError("TODO: 自回归生成")


if __name__ == "__main__":
    raise SystemExit("本文件是手写实现骨架，实验入口是 demo.py：uv run python demo.py")
