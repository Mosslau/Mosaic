"""参考解：第 4 题（实现）——两种 mask

    uv run python sol-04-mask.py
"""

import numpy as np


def main() -> None:
    T = 5
    enc = np.ones((T, T), dtype=bool)
    dec = np.tril(np.ones((T, T), dtype=bool))
    print("encoder mask:\n", enc.astype(int))
    print("decoder mask:\n", dec.astype(int))
    assert np.all(enc) and np.all(np.triu(dec, k=1) == 0)


if __name__ == "__main__":
    main()
