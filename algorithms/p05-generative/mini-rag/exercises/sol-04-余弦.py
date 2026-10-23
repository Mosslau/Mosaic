"""参考解：第 4 题（实现）——余弦 top-k

    uv run python sol-04-余弦.py
"""

import numpy as np


def main() -> None:
    X = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    q = np.array([1.0, 1.0])
    Xn = X / np.linalg.norm(X, axis=1, keepdims=True)
    qn = q / np.linalg.norm(q)
    scores = Xn @ qn
    order = np.argsort(scores)[::-1][:2]
    print("scores:", np.round(scores, 3), "top2:", order.tolist())
    assert order[0] == 2 and abs(scores[order[0]] - 1.0) < 1e-9


if __name__ == "__main__":
    main()
