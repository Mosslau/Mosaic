"""参考解：第 4 题（实现）——整网梯度检查

    uv run python sol-04-梯度检查.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import MLP  # noqa: E402


def main() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(5, 3))
    y = np.eye(3)[[0, 1, 2, 0, 1]]
    m = MLP(hidden_sizes=(4,), init="random", weight_decay=0.0, random_state=0)
    m._init_params(3, 3)
    _, cache = m.forward(X)
    grads = m.backward(cache, y)

    eps = 1e-6
    worst = 0.0
    for layer in range(len(m.params)):
        for key in ("W", "b"):
            arr = m.params[layer][key]
            for idx in np.ndindex(arr.shape):
                old = arr[idx]
                arr[idx] = old + eps
                plus = m._loss(X, y)
                arr[idx] = old - eps
                minus = m._loss(X, y)
                arr[idx] = old
                num = (plus - minus) / (2 * eps)
                worst = max(worst, abs(num - grads[layer][key][idx]))
    print(f"最大绝对误差：{worst:.3e}")
    assert worst < 1e-5
    print("→ 解析梯度与有限差分一致，反向传播实现正确。")


if __name__ == "__main__":
    main()
