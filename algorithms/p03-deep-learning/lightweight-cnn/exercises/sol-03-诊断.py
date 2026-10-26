"""参考解 3：三种"看起来能跑"的 DS 实现，分别观测症状。

运行：
    python3 sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from impl import BatchNorm, Conv2D  # noqa: E402

rng = np.random.default_rng(0)


def depthwise_reference(X, W):
    """逐通道参考实现：W 形状 (C,1,3,3)。"""
    N, C, H, Wd = X.shape
    Xp = np.pad(X, ((0, 0), (0, 0), (1, 1), (1, 1)))
    out = np.zeros((N, C, H, Wd))
    for c in range(C):
        for i in range(H):
            for j in range(Wd):
                out[:, c, i, j] = np.sum(Xp[:, c, i:i + 3, j:j + 3] * W[c, 0])
    return out


X = rng.normal(size=(2, 4, 6, 6))

# A：groups 误设成 1，权重形状 (4,4,3,3) —— 不报错，但跨通道求和
bad = Conv2D(4, 4, 3, pad=1, groups=1)
good = Conv2D(4, 4, 3, pad=1, groups=4)
good.W[:] = bad.W[:, :1]  # 每个输出通道只保留它自己的那一份权重
ref = depthwise_reference(X, good.W)
print("A groups=1 与 depthwise 参考的最大差：", float(np.abs(bad.forward(X) - ref).max()))
assert np.abs(bad.forward(X) - ref).max() > 1e-3
print("  症状：静默算错（输出把 4 个通道加在一起），形状/训练都不会报错。")

# B：先 pointwise 再 depthwise（顺序反了）
pw_first = Conv2D(4, 4, 1)
pw_first.W[:, :, 0, 0] = np.eye(4) + 0.5
dw_after = Conv2D(4, 4, 3, pad=1, groups=4)
dw_after.W[:] = good.W
right = dw_after.forward(X)
wrong = dw_after.forward(pw_first.forward(X))
print("B 顺序反了的相对差：", float(np.abs(wrong - right).mean() / np.abs(right).mean()))
print("  症状：不再等价；1×1 先混合通道，depthwise 再逐通道卷积，结果不同（不可交换）。")

# C：BN 推理时仍用 training=True —— 单图预测依赖同批次的其它样本
bn = BatchNorm(3)
Xb = rng.normal(size=(8, 3, 4, 4)) + 1.0
bn.forward(Xb, training=True)
single = bn.forward(Xb[:1], training=True)
in_batch = bn.forward(Xb, training=True)[:1]
eval_single = bn.forward(Xb[:1], training=False)
eval_batch = bn.forward(Xb, training=False)[:1]
print("C training 模式单图 vs 批量：", float(np.abs(single - in_batch).max()))
print("C eval 模式单图 vs 批量：", float(np.abs(eval_single - eval_batch).max()))
assert np.abs(single - in_batch).max() > 1e-6
assert np.abs(eval_single - eval_batch).max() < 1e-12
print("  症状：推理结果随 batch 组成漂移；对应 test_bn_eval_is_batch_independent。")
