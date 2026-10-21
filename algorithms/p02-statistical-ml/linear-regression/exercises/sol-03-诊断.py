"""参考解：第 3 题（判断）——三个变体的症状

    uv run python sol-03-诊断.py

分别复现：
    A  梯度少乘 2（有效学习率减半）→ 收敛更慢，最终解不变
    B  更新用加号 → loss 单调上升并溢出
    C  特征尺度差 1000 倍、不标准化 → 同一个 lr 下发散
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from impl import Model


def gd_manual(X, y, lr=0.1, epochs=4000, tol=1e-10, grad_factor=2.0,
              sign=-1.0, standardize=True):
    """手写最小闭环，用来插入三种 bug（grad_factor / sign / standardize）。"""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if standardize:
        mu, sigma = X.mean(0), X.std(0)
        sigma = np.where(sigma == 0, 1.0, sigma)
    else:
        mu, sigma = np.zeros(X.shape[1]), np.ones(X.shape[1])
    Xs = (X - mu) / sigma
    w = np.zeros(X.shape[1])
    b = float(y.mean())
    losses = []
    prev = float("inf")
    for _ in range(epochs):
        err = Xs @ w + b - y
        loss = float(np.mean(err ** 2))
        losses.append(loss)
        if abs(prev - loss) < tol:
            break
        grad_w = grad_factor / len(y) * (Xs.T @ err)
        grad_b = grad_factor / len(y) * err.sum()
        w += sign * lr * grad_w
        b += sign * lr * grad_b
        prev = loss
    return {"w": w / sigma, "b": float(b - mu @ (w / sigma)),
            "losses": np.asarray(losses), "epochs": len(losses)}


def main() -> None:
    rng = np.random.default_rng(0)
    x = rng.uniform(-3, 3, size=(120, 1))
    y = 3.0 * x[:, 0] + 2.0 + rng.normal(0, 0.5, 120)

    correct = gd_manual(x, y)
    missing2 = gd_manual(x, y, grad_factor=1.0)
    sign_flip = gd_manual(x, y, sign=+1.0, epochs=200)
    print("A 少乘 2：")
    print(f"   正确版 {correct['epochs']:4d} 轮收敛，w={correct['w'][0]:.4f}")
    print(f"   变体 A {missing2['epochs']:4d} 轮收敛，w={missing2['w'][0]:.4f}"
          f"  → 轮数约 {missing2['epochs'] / correct['epochs']:.1f} 倍")
    assert abs(missing2["w"][0] - correct["w"][0]) < 1e-3
    assert missing2["epochs"] > correct["epochs"]

    print("\nB 更新取加号：")
    print(f"   前 5 轮 loss：{np.round(sign_flip['losses'][:5], 3).tolist()}")
    print(f"   最终 loss：{sign_flip['losses'][-1]:.3e}")
    assert (not np.isfinite(sign_flip["losses"][-1])) or sign_flip["losses"][-1] > 10

    print("\nC 尺度差 1000 倍、lr=0.01：")
    x1 = rng.normal(0, 1, 200)
    x2 = rng.normal(0, 1000, 200)
    X = np.column_stack([x1, x2])
    y2 = 2.0 * x1 + 0.003 * x2 + 5.0 + rng.normal(0, 0.5, 200)
    scaled = gd_manual(X, y2, lr=0.01, epochs=1500, standardize=True)
    raw = gd_manual(X, y2, lr=0.01, epochs=1500, standardize=False)
    print(f"   标准化：首轮 {scaled['losses'][0]:.3f} → 末轮 {scaled['losses'][-1]:.3f}")
    print(f"   不标准化：首轮 {raw['losses'][0]:.3f} → 末轮 {raw['losses'][-1]:.3f}")
    assert np.isfinite(scaled["losses"][-1]) and scaled["losses"][-1] < scaled["losses"][0]
    assert (not np.isfinite(raw["losses"][-1])) or raw["losses"][-1] > raw["losses"][0]

    # 与正式实现的交叉验证：正确版应与 Model 收敛到同一处
    model = Model(lr=0.1, epochs=4000, tol=1e-10).fit(x, y)
    print(f"\n交叉验证：手写最小闭环 w={correct['w'][0]:.6f}，"
          f"impl.Model w={model.raw_coef[0]:.6f}")
    assert abs(correct["w"][0] - model.raw_coef[0]) < 1e-6


if __name__ == "__main__":
    main()
