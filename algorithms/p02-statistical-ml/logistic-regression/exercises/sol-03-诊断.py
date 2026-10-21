"""参考解：第 3 题（判断）——三个变体的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import Model, accuracy, sigmoid  # noqa: E402


def train(X, y, lr=0.5, epochs=3000, tol=1e-10, mode="ok", sign=-1.0):
    """mode='ok' 用 p−y 的梯度；mode='z' 错用 z−y；sign=+1 模拟方向写反。"""
    mu, sigma = X.mean(0), X.std(0)
    sigma = np.where(sigma == 0, 1.0, sigma)
    Xs = (X - mu) / sigma
    w = np.zeros(X.shape[1])
    b = 0.0
    losses = []
    prev = float("inf")
    for _ in range(epochs):
        z = Xs @ w + b
        p = sigmoid(z)
        loss = float(np.mean(np.logaddexp(0.0, z) - y * z))
        losses.append(loss)
        if abs(prev - loss) < tol:
            break
        err = (z - y) if mode == "z" else (p - y)
        w += sign * lr * (Xs.T @ err) / len(y)
        b += sign * lr * float(err.mean())
        prev = loss
    return {"w": w / sigma, "b": float(b - mu @ (w / sigma)), "losses": np.asarray(losses)}


def main() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(300, 2))
    y = (rng.random(300) < sigmoid(1.5 * X[:, 0] - X[:, 1])).astype(float)

    ok = train(X, y)
    wrong_grad = train(X, y, mode="z")
    sign = train(X, y, sign=+1.0, epochs=100)
    print("A 梯度用 z−y：")
    print(f"   正确版最终 BCE {ok['losses'][-1]:.4f}；变体 A {wrong_grad['losses'][-1]:.4f}")
    print(f"   正确版 accuracy {accuracy(y, (X @ ok['w'] + ok['b'] >= 0).astype(int)):.4f}；"
          f"A {accuracy(y, (X @ wrong_grad['w'] + wrong_grad['b'] >= 0).astype(int)):.4f}")
    assert wrong_grad["losses"][-1] > ok["losses"][-1] * 1.05, "A 的损失应明显更高"

    print("\nB 更新取加号：")
    print(f"   前 5 轮 BCE：{np.round(sign['losses'][:5], 4).tolist()}")
    assert (not np.isfinite(sign["losses"][-1])) or sign["losses"][-1] > sign["losses"][0]

    print("\nC 用 z>=threshold 预测：")
    model = Model(lr=0.5, epochs=3000, tol=1e-10).fit(X, y)
    p = model.predict_proba(X)
    z = (X - model._mu) / model._sigma @ model.w + model.b
    for th in (0.3, 0.5, 0.9):
        rate_p = float((p >= th).mean())
        rate_z = float((z >= th).mean())
        print(f"   threshold={th}: p>=th 判正 {rate_p:.3f}；z>=th 判正 {rate_z:.3f}")
    rate_p = float((p >= 0.5).mean())
    rate_z = float((z >= 0.5).mean())
    assert rate_z < rate_p, "把阈值套在 logit 上会让预测偏负"

    print("\n→ A 学得慢且更差；B 发散；C 训练正常但预测阈值被偷换。")
    print("   C 的正确写法：先 sigmoid 得到概率，再与阈值比较。")


if __name__ == "__main__":
    main()
