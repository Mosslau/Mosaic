"""参考解：第 5 题（迁移）——内容检索

    uv run python sol-05-检索.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import ScaledDotProductAttention  # noqa: E402


def main() -> None:
    rng = np.random.default_rng(0)
    T, D = 64, 32
    K = rng.normal(size=(T, D))
    V = np.eye(T)
    att = ScaledDotProductAttention()
    hit = 0
    for j in range(T):
        _, w = att.forward(K[j:j + 1], K, V)
        hit += int(np.argmax(w[0, 0]) == j)
    print(f"attention top-1：{hit / T:.3f}")
    assert hit / T > 0.95


if __name__ == "__main__":
    main()
