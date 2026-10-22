"""参考解：第 4 题（实现）——LayerNorm

    uv run python sol-04-LayerNorm.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import LayerNorm  # noqa: E402


def main() -> None:
    rng = np.random.default_rng(0)
    ln = LayerNorm(5)
    X = rng.normal(size=(2, 3, 5))
    G = rng.normal(size=(2, 3, 5))
    out = ln.forward(X)
    print("每行均值：", np.round(out.mean(-1), 6))
    print("每行标准差：", np.round(out.std(-1), 6))
    ln.backward(G)

    def loss():
        return float(np.sum(ln.forward(X) * G))

    eps = 1e-6
    worst = 0.0
    for key in ("gamma", "beta"):
        arr = getattr(ln, key)
        for idx in range(5):
            old = arr[idx]
            arr[idx] = old + eps
            lp = loss()
            arr[idx] = old - eps
            lm = loss()
            arr[idx] = old
            worst = max(worst, abs((lp - lm) / (2 * eps) - getattr(ln, "d" + key)[idx]))
    print(f"梯度最大误差：{worst:.2e}")
    assert worst < 1e-5


if __name__ == "__main__":
    main()
