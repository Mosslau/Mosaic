"""参考解：第 3 题（判断）——三个 LeNet 实现 bug 的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import col2im, im2col, maxpool_backward, maxpool_forward  # noqa: E402


def bad_col2im(dcol, shape, kh, kw, stride=1, pad=0):
    N, C, H, W = shape
    Hp, Wp = H + 2 * pad, W + 2 * pad
    out_h = (Hp - kh) // stride + 1
    out_w = (Wp - kw) // stride + 1
    cols = dcol.reshape(N, out_h, out_w, C, kh, kw)
    dX = np.zeros((N, C, Hp, Wp))
    for i in range(kh):
        for j in range(kw):
            # 错：赋值而不是累加
            dX[:, :, i:i + stride * out_h:stride, j:j + stride * out_w:stride] = \
                cols[:, :, :, :, i, j].transpose(0, 3, 1, 2)
    return dX[:, :, pad:pad + H, pad:pad + W] if pad else dX


def main() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2, 3, 6, 6))
    G = rng.normal(size=im2col(X, 3, 3, 1, 1).shape)
    good = abs(np.sum(im2col(X, 3, 3, 1, 1) * G)
               - np.sum(X * col2im(G, X.shape, 3, 3, 1, 1)))
    bad = abs(np.sum(im2col(X, 3, 3, 1, 1) * G)
              - np.sum(X * bad_col2im(G, X.shape, 3, 3, 1, 1)))
    print(f"A col2im：正确伴随误差 {good:.2e}；赋值版 {bad:.2e}")
    assert bad > good

    Xp = rng.normal(size=(2, 3, 8, 8))
    out, idx = maxpool_forward(Xp)
    Gp = rng.normal(size=out.shape)
    lhs = np.sum(out * Gp)
    rhs_arg = np.sum(Xp * maxpool_backward(Gp, idx, Xp.shape))
    # 错：平均分给窗口
    d = np.repeat(np.repeat(Gp / 4, 2, axis=2), 2, axis=3)
    rhs_avg = np.sum(Xp * d)
    print(f"B 池化：argmax 伴随 {abs(lhs-rhs_arg):.2e}；平均反传 {abs(lhs-rhs_avg):.2e}")
    assert abs(lhs - rhs_arg) < 1e-10 and abs(lhs - rhs_avg) > 1e-3
    print("C BN：训练/推理用不同统计量；用 batch 统计推理会让同一图随 batch 漂移（见 README）。")
    print("\n→ A 丢梯度；B 路由错；C 推理统计错。")


if __name__ == "__main__":
    main()
