"""参考解：第 3 题（判断）——三个 MLP bug 的症状

    uv run python sol-03-诊断.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import impl  # noqa: E402
from impl import MLP  # noqa: E402
from test_impl import digits  # noqa: E402


def xor_data(n=400, seed=0):
    rng = np.random.default_rng(seed)
    centers = np.array([[-1, -1], [-1, 1], [1, -1], [1, 1]])
    labels = np.array([0, 1, 1, 0])
    X = np.vstack([c + rng.normal(0, 0.2, size=(n // 4, 2)) for c in centers])
    return X, np.repeat(labels, n // 4)


def main() -> None:
    X_tr, X_te, y_tr, y_te = digits()

    print("A 前向不做 ReLU（等价于线性网络，XOR 数据）：")
    X, y = xor_data()
    normal = MLP(hidden_sizes=(16, 16), lr=0.05, epochs=100, optimizer="adam",
                 random_state=0).fit(X, y)
    old_relu, old_grad = impl.relu, impl.relu_grad
    impl.relu = lambda z: z
    impl.relu_grad = lambda z: np.ones_like(z)
    try:
        broken = MLP(hidden_sizes=(16, 16), lr=0.05, epochs=100, optimizer="adam",
                     random_state=0).fit(X, y)
    finally:
        impl.relu, impl.relu_grad = old_relu, old_grad
    a_norm = np.mean(normal.predict(X) == y)
    a_bad = np.mean(broken.predict(X) == y)
    print(f"   正常 {a_norm:.3f}；无 ReLU {a_bad:.3f}")
    assert a_norm > 0.9 and a_bad < 0.7

    print("\nB softmax 不减最大值：")
    with np.errstate(over="ignore"):
        naive = np.exp(np.array([1000.0, 1001.0]))
    stable = impl.softmax(np.array([[1000.0, 1001.0]]))
    print(f"   naive exp = {naive}；stable = {stable}")
    assert np.isinf(naive).any() and np.isfinite(stable).all()

    print("\nC 全零初始化：")
    zero = MLP(hidden_sizes=(32,), lr=0.01, epochs=10, optimizer="adam",
               init="zero", random_state=0).fit(X_tr, y_tr)
    print(f"   测试 acc {np.mean(zero.predict(X_te) == y_te):.3f}")
    assert np.mean(zero.predict(X_te) == y_te) < 0.2
    print("\n→ A 退化；B 溢出；C 对称性失败。")


if __name__ == "__main__":
    main()
