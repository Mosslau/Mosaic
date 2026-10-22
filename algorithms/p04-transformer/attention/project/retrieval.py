"""迁移项目：内容检索 —— attention vs mean pooling

    uv run python retrieval.py

记忆库 T=64 个 key/value；query 等于其中一个 key，要求返回对应 value。
attention 按内容打分选 key；mean pooling 把所有 value 平均，没有选择能力。
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import ScaledDotProductAttention  # noqa: E402


def main() -> None:
    rng = np.random.default_rng(0)
    T, D, n_q = 64, 32, 50
    K = rng.normal(size=(T, D))
    V = np.eye(T)
    att = ScaledDotProductAttention()
    hit_att = hit_mean = 0
    for _ in range(n_q):
        j = int(rng.integers(T))
        Q = K[j:j + 1]
        _, w = att.forward(Q, K, V)
        hit_att += int(np.argmax(w[0, 0]) == j)
        hit_mean += int(np.argmax(V.mean(axis=0)) == j)
    acc_a = hit_att / n_q
    acc_m = hit_mean / n_q
    print(f"T={T}, D={D}, queries={n_q}")
    print(f"attention top-1：{acc_a:.3f}")
    print(f"mean pooling top-1：{acc_m:.3f}")
    assert acc_a > 0.95 and acc_m < 0.1
    print("\n→ attention 能按 query 选 key；mean pooling 只会返回同一个平均向量。")


if __name__ == "__main__":
    main()
