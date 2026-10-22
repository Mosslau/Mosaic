"""注意力机制 — demo：mask、缩放、多头、检索与复杂度

    uv run python demo.py

    实验一  scaled dot-product + causal mask
    实验二  d_k 与 softmax 锐度
    实验三  多头注意力（不同头不同权重）
    实验四  内容检索：attention vs mean pooling
    实验五  O(T²) 成本与排列等变性
"""

from __future__ import annotations

import time

import framework
import numpy as np
from impl import MultiHeadAttention, ScaledDotProductAttention, softmax


def softmax_entropy(w):
    p = np.clip(w, 1e-12, 1)
    return float(-np.sum(p * np.log(p), axis=-1).mean())


def experiment_scaled() -> None:
    rng = np.random.default_rng(0)
    Q = rng.normal(size=(1, 4, 8))
    K = rng.normal(size=(1, 5, 8))
    V = rng.normal(size=(1, 5, 8))
    out, w = ScaledDotProductAttention().forward(Q, K, V)
    print("== 实验一：scaled dot-product + causal ==")
    print(f"输出 {out.shape}；权重形状 {w.shape}；行和 {w.sum(-1).ravel()[:3]}")
    assert np.allclose(w.sum(-1), 1.0)

    _, wc = ScaledDotProductAttention(causal=True).forward(Q, K[:, :4], V[:, :4])
    upper = np.triu(wc[0], k=1)
    print(f"causal 权重上三角最大值：{np.abs(upper).max():.2e}")
    assert np.allclose(upper, 0.0)

    V2 = V[:, :4].copy()
    V2[:, -1] += 100.0
    _, wc2 = ScaledDotProductAttention(causal=True).forward(Q, K[:, :4], V2)
    print(f"改未来 V 后，前面位置的权重是否不变：{np.allclose(wc[..., :-1], wc2[..., :-1])}")


def experiment_scaling() -> None:
    print("\n== 实验二：d_k 与 softmax 锐度（30 次随机取平均） ==")
    print(f"{'d_k':>5} | {'不缩放 max':>10} | {'缩放后 max':>10}")
    print("-" * 34)
    for dk in (2, 8, 32, 128):
        raw_max, sc_max = [], []
        for seed in range(30):
            rng = np.random.default_rng(seed)
            Q = rng.normal(size=(1, 4, dk))
            K = rng.normal(size=(1, 6, dk))
            raw = Q @ K.swapaxes(-1, -2)
            raw_max.append(float(softmax(raw).max()))
            sc_max.append(float(softmax(raw / np.sqrt(dk)).max()))
        print(f"{dk:5d} | {np.mean(raw_max):10.3f} | {np.mean(sc_max):10.3f}")
    print("→ 不除以 √d_k，d_k 越大 softmax 越尖；缩放把最大权重压回约 0.5。\n")


def experiment_multihead() -> None:
    rng = np.random.default_rng(2)
    X = rng.normal(size=(1, 6, 8))
    mha = MultiHeadAttention(8, 2, random_state=0)
    out, W = mha.forward(X)
    print("== 实验三：多头注意力 ==")
    print(f"输出 {out.shape}；权重 {W.shape}")
    for h in range(W.shape[1]):
        print(f"  head {h}: 最大权重 {W[0,h].max():.3f}，熵 {softmax_entropy(W[0,h]):.3f}")
    assert not np.allclose(W[:, 0], W[:, 1])
    print("→ 不同头学/算出不同的关注模式；本实验未训练，权重由随机投影决定。\n")


def experiment_retrieval() -> None:
    rng = np.random.default_rng(3)
    T, D = 32, 16
    K = rng.normal(size=(T, D))
    V = np.eye(T)
    j = 17
    Q = K[j:j + 1]
    out, w = ScaledDotProductAttention().forward(Q, K, V)
    pick = int(np.argmax(w[0, 0]))
    mean_pick = int(np.argmax(V.mean(axis=0)))
    print("== 实验四：内容检索（attention vs mean pooling） ==")
    print(f"目标 value 下标 {j}；attention 选中 {pick}；mean pooling 选中 {mean_pick}")
    assert pick == j
    print("→ attention 能按 query 动态选 key；mean pooling 把所有 value 平均，丢掉了选择能力。\n")


def experiment_cost() -> None:
    rng = np.random.default_rng(4)
    print("== 实验五：O(T²) 成本与排列等变性 ==")
    print(f"{'T':>4} | {'time(ms)':>9}")
    print("-" * 18)
    for T in (32, 64, 128, 256):
        X = rng.normal(size=(1, T, 16))
        t0 = time.perf_counter()
        MultiHeadAttention(16, 4, random_state=0).forward(X)
        print(f"{T:4d} | {(time.perf_counter() - t0) * 1000:9.2f}")

    Q = rng.normal(size=(1, 4, 8))
    K = rng.normal(size=(1, 4, 8))
    V = rng.normal(size=(1, 4, 8))
    a = ScaledDotProductAttention()
    o1, _ = a.forward(Q, K, V)
    perm = np.array([2, 0, 3, 1])
    o2, _ = a.forward(Q[:, perm], K[:, perm], V[:, perm])
    print(f"排列等变：{np.allclose(o1[:, perm], o2)}（没有位置编码时，输出只跟着 token 重排）")
    print("→ 这也解释了为什么 Block/GPT 必须加位置编码。\n")


def experiment_framework() -> None:
    rng = np.random.default_rng(5)
    Q = rng.normal(size=(1, 4, 8))
    K = rng.normal(size=(1, 5, 8))
    V = rng.normal(size=(1, 5, 8))
    out, w = ScaledDotProductAttention().forward(Q, K, V)
    f_out, f_w = framework.torch_attention(Q, K, V)
    print("== 手写 vs torch ==")
    print(f"输出最大差 {np.abs(out - f_out).max():.2e}；权重最大差 {np.abs(w - f_w).max():.2e}")
    assert np.abs(out - f_out).max() < 1e-6


def main() -> None:
    experiment_scaled()
    experiment_scaling()
    experiment_multihead()
    experiment_retrieval()
    experiment_cost()
    experiment_framework()


if __name__ == "__main__":
    main()
