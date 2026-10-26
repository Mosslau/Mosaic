"""参考解 2：用 impl.Conv2D 复算手算结果。"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from impl import Conv2D  # noqa: E402

X = np.stack([
    [[[1, 2, 3], [4, 5, 6], [7, 8, 9]]],
    [[[1, 0, 2], [0, 3, 0], [4, 0, 5]]],
], axis=1)  # (1, 2, 3, 3)

dw = Conv2D(2, 2, 3, pad=1, groups=2)
dw.W[0, 0] = [[0, 1, 0], [1, 0, 1], [0, 1, 0]]
dw.W[1, 0] = [[1, 0, 1], [0, 1, 0], [1, 0, 1]]
D = dw.forward(X)
print("2 channels center:", D[0, :, 1, 1])          # [20. 15.]

pw = Conv2D(2, 2, 1)
pw.W[:, :, 0, 0] = [[1.0, -0.5], [0.5, 1.0]]
Y = pw.forward(D)
print("pointwise center:", Y[0, :, 1, 1])          # [12.5 25. ]

params = dw.W.size + pw.W.size + 2 * 2 * 2          # 卷积 + 两层 BN 的 γ/β
print("params (conv + bn):", params)                # 30
assert np.allclose(D[0, :, 1, 1], [20, 15])
assert np.allclose(Y[0, :, 1, 1], [12.5, 25.0])
assert params == 30
