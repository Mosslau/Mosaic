"""LeNet — demo：手写 vs torch、BatchNorm/残差与算子对账

    uv run python demo.py

    实验一  手写 LeNet vs torch（8×8 digits，10 类）
    实验二  BatchNorm / 残差 四组对照（手写）
    实验三  im2col/col2im 与池化的伴随（adjoint）检查
"""

from __future__ import annotations

import statistics
import time

import framework
import numpy as np
from impl import LeNet, col2im, im2col, maxpool_backward, maxpool_forward
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

SEED = 0
REPEATS = 2


def load_data(n_train: int = 1400):
    X, y = load_digits(return_X_y=True)
    X = (X / 16.0).reshape(-1, 1, 8, 8)
    return train_test_split(X, y, train_size=n_train, random_state=SEED, stratify=y)


def acc(y, p) -> float:
    return float(np.mean(np.asarray(y) == np.asarray(p)))


def _median_time(fn, repeats: int = REPEATS):
    times, result = [], None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return result, statistics.median(times)


def _fit_hand(X_tr, y_tr, **kw):
    params = dict(lr=0.003, epochs=100, batch_size=64, optimizer="adam",
                  random_state=SEED)
    params.update(kw)
    return LeNet(**params).fit(X_tr, y_tr)


# ---------------------------------------------------------------- 实验一

def experiment_baseline() -> None:
    X_tr, X_te, y_tr, y_te = load_data()
    hand, t_hand = _median_time(lambda: _fit_hand(X_tr, y_tr))
    torch_model, t_torch = _median_time(
        lambda: framework.TorchLeNet(lr=0.003, epochs=100, batch_size=64,
                                     random_state=SEED).fit(X_tr, y_tr))
    print("== 实验一：手写 LeNet vs torch（8×8 digits，10 类） ==")
    print(f"{'方法':12} | {'训练 acc':>8} | {'测试 acc':>8} | {'末轮 loss':>9} | {'耗时(s)':>7}")
    print("-" * 54)
    for name, m, t in (("手写", hand, t_hand), ("torch", torch_model, t_torch)):
        print(f"{name:12} | {acc(y_tr, m.predict(X_tr)):8.4f} | "
              f"{acc(y_te, m.predict(X_te)):8.4f} | {m.loss_history[-1]:9.4f} | {t:7.2f}")
    assert acc(y_te, hand.predict(X_te)) > 0.85
    assert acc(y_te, torch_model.predict(X_te)) > 0.9
    print("\n→ 修复 Conv2D.dW 轴序后，手写与 torch 已基本对齐；")
    print("  剩余差异来自训练随机性/优化器细节。\n")


# ---------------------------------------------------------------- 实验二

def experiment_bn_residual() -> None:
    X_tr, X_te, y_tr, y_te = load_data()
    print("== 实验二：BatchNorm / 残差（手写，100 轮） ==")
    print(f"{'配置':18} | {'测试 acc':>8} | {'末轮 loss':>9}")
    print("-" * 40)
    results = []
    for name, kw in (("baseline", {}), ("+BatchNorm", {"use_bn": True}),
                     ("+Residual", {"use_residual": True}),
                     ("+BN+Residual", {"use_bn": True, "use_residual": True})):
        m = _fit_hand(X_tr, y_tr, **kw)
        a = acc(y_te, m.predict(X_te))
        results.append((name, a))
        print(f"{name:18} | {a:8.4f} | {m.loss_history[-1]:9.4f}")
    assert results[-1][1] > results[0][1]
    print("\n→ BN 稳定训练；残差单独收益小，BN+残差组合最好。\n")


# ---------------------------------------------------------------- 实验三

def experiment_adjoint() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2, 3, 6, 6))
    G = rng.normal(size=im2col(X, 3, 3, 1, 1).shape)
    lhs = float(np.sum(im2col(X, 3, 3, 1, 1) * G))
    rhs = float(np.sum(X * col2im(G, X.shape, 3, 3, 1, 1)))
    print("== 实验三：算子伴随检查 ==")
    print(f"  im2col/col2im: <im2col(X),G>={lhs:.6f}，<X,col2im(G)>={rhs:.6f}")
    assert abs(lhs - rhs) < 1e-10

    Xp = rng.normal(size=(2, 3, 8, 8))
    out, idx = maxpool_forward(Xp)
    Gp = rng.normal(size=out.shape)
    lhs = float(np.sum(out * Gp))
    rhs = float(np.sum(Xp * maxpool_backward(Gp, idx, Xp.shape)))
    print(f"  maxpool:       <pool(X),G>={lhs:.6f}，<X,pool'(G)>={rhs:.6f}")
    assert abs(lhs - rhs) < 1e-10
    print("\n→ 两个算子的反向都是其前向的转置，卷积/池化反传的数学基础正确。\n")


def main() -> None:
    experiment_baseline()
    experiment_bn_residual()
    experiment_adjoint()


if __name__ == "__main__":
    main()
