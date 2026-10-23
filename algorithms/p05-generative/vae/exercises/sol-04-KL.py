"""参考解：第 4 题（实现）——KL 闭式

    uv run python sol-04-KL.py
"""

import numpy as np


def main() -> None:
    mu = np.array([[0.0, 1.0], [0.5, -0.5]])
    lv = np.zeros_like(mu)
    kl = -0.5 * np.sum(1 + lv - mu ** 2 - np.exp(lv), axis=1)
    print("KL per sample:", kl, "mean:", kl.mean())
    assert np.all(kl >= 0) and abs(kl.mean() - 0.375) < 1e-12

    eps = 1e-6
    idx = (0, 1)
    old = mu[idx]
    mu[idx] = old + eps
    kp = -0.5 * np.sum(1 + lv - mu ** 2 - np.exp(lv), axis=1).mean()
    mu[idx] = old - eps
    km = -0.5 * np.sum(1 + lv - mu ** 2 - np.exp(lv), axis=1).mean()
    mu[idx] = old
    print("dKL/dmu:", (kp - km) / (2 * eps), "formula:", old / len(mu))


if __name__ == "__main__":
    main()
