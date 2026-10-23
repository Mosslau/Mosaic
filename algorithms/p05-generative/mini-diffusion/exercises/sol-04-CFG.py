"""参考解：第 4 题（实现）——CFG

    uv run python sol-04-CFG.py
"""

import numpy as np


def main() -> None:
    eps_un = np.array([[0.1, 0.2]])
    eps_c = np.array([[0.5, 0.6]])
    for w in (0.0, 1.0, 3.0):
        eps = eps_un + w * (eps_c - eps_un)
        print(w, eps)
    assert np.allclose(eps_un + 0 * (eps_c - eps_un), eps_un)
    assert np.allclose(eps_un + 1 * (eps_c - eps_un), eps_c)


if __name__ == "__main__":
    main()
