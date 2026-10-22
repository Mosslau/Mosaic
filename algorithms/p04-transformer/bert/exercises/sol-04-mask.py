"""参考解：第 4 题（实现）——15% mask

    uv run python sol-04-mask.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import BertMLM  # noqa: E402


def main() -> None:
    rng = np.random.default_rng(0)
    tokens = rng.integers(5, 20, size=(4, 12))
    tokens[:, 0] = 2
    tokens[:, -1] = 3
    m = BertMLM(20, context=12)
    inp, target, mask = m._make_mask(tokens, np.random.default_rng(0))
    print("选中位置：", np.argwhere(mask).tolist())
    print("特殊位置被 mask：", bool(mask[:, 0].any() or mask[:, -1].any()))
    assert not mask[:, 0].any() and not mask[:, -1].any()
    assert np.all(target == tokens)


if __name__ == "__main__":
    main()
