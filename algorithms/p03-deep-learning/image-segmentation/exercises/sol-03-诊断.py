"""参考解 03（判断）：三个"看起来能跑"的错误变体。

运行：cd exercises && uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data import make_dataset  # noqa: E402
from impl import (  # noqa: E402
    iou,
    maxpool_backward,
    maxpool_forward,
    pixel_accuracy,
    upsample_backward,
    upsample_nearest,
)


def adjoint_error_upsample() -> tuple[float, float]:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2, 3, 4, 4))
    G = rng.normal(size=(2, 3, 8, 8))
    lhs = float(np.sum(upsample_nearest(X) * G))
    correct = float(np.sum(X * upsample_backward(G)))
    wrong = float(np.sum(X * G[:, :, ::2, ::2]))   # 只取每个 2×2 块的左上
    return abs(lhs - correct), abs(lhs - wrong)


def adjoint_error_pool() -> tuple[float, float]:
    rng = np.random.default_rng(1)
    X = rng.normal(size=(2, 3, 8, 8))
    out, idx = maxpool_forward(X)
    G = rng.normal(size=out.shape)
    lhs = float(np.sum(out * G))
    correct = float(np.sum(X * maxpool_backward(G, idx, X.shape)))
    avg = G.reshape(2, 3, 4, 1, 4, 1) * np.full((1, 1, 1, 2, 1, 2), 0.25)
    wrong = float(np.sum(X * avg.reshape(X.shape)))  # 把梯度均分给 4 个位置
    return abs(lhs - correct), abs(lhs - wrong)


def metric_mismatch() -> tuple[float, float, float, float]:
    X, Y = make_dataset(64, seed=13)
    all_bg = np.zeros_like(Y)
    scores = [(iou(X > t, Y), pixel_accuracy(X > t, Y), t) for t in np.linspace(0.2, 0.8, 61)]
    best_iou, best_acc, best_t = max(scores)
    return pixel_accuracy(all_bg, Y), iou(all_bg, Y), best_acc, best_iou


def main() -> None:
    up_correct, up_wrong = adjoint_error_upsample()
    pool_correct, pool_wrong = adjoint_error_pool()
    bg_acc, bg_iou, best_acc, best_iou = metric_mismatch()
    print(f"A 上采样反向：正确伴随误差 {up_correct:.2e}；只取左上的误差 {up_wrong:.2e}")
    print(f"B 最大池化反向：argmax 路由误差 {pool_correct:.2e}；均分梯度误差 {pool_wrong:.2e}")
    print(f"C 指标背离：全预测背景 pixel acc {bg_acc:.4f} / IoU {bg_iou:.4f}；"
          f"最佳阈值 pixel acc {best_acc:.4f} / IoU {best_iou:.4f}")
    assert up_correct < 1e-10 and up_wrong > 1e-2
    assert pool_correct < 1e-10 and pool_wrong > 1e-2
    assert bg_acc > 0.85 and bg_iou == 0.0
    assert best_acc > 0.9 and best_iou < 0.6
    print("✓ 三个变体的症状均复现：伴随检查失败 / 梯度路由错误 / 指标背离")


if __name__ == "__main__":
    main()
