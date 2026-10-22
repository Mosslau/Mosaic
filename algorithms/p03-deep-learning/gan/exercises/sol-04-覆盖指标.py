"""参考解：第 4 题（实现）——覆盖指标

    uv run python sol-04-覆盖指标.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import mode_coverage  # noqa: E402


def main() -> None:
    centers = np.array([[0.0, 0.0], [5.0, 5.0]])
    samples = np.array([[0.0, 0.1], [5.1, 5.0], [100.0, 100.0]])
    m = mode_coverage(samples, centers, threshold=0.35)
    print(m)
    assert m["covered"] == 2 and m["counts"].tolist() == [1, 1]
    print("→ 覆盖 2/2，熵 log2≈0.693")


if __name__ == "__main__":
    main()
