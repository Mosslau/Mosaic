"""参考解：第 4 题（实现）——全局梯度裁剪

    uv run python sol-04-裁剪.py
"""

import numpy as np


def clip_gradients(grads, clip):
    norm = float(np.sqrt(sum(np.sum(g ** 2) for g in grads.values())))
    if norm > clip:
        scale = clip / (norm + 1e-12)
        return {k: g * scale for k, g in grads.items()}, norm
    return grads, norm


def main() -> None:
    rng = np.random.default_rng(0)
    grads = {"W": rng.normal(size=(4, 3)), "b": rng.normal(size=4)}
    clipped, norm = clip_gradients(grads, 1.0)
    new_norm = np.sqrt(sum(np.sum(g ** 2) for g in clipped.values()))
    flat = np.concatenate([g.ravel() for g in grads.values()])
    flat2 = np.concatenate([g.ravel() for g in clipped.values()])
    cos = float(flat @ flat2 / (np.linalg.norm(flat) * np.linalg.norm(flat2)))
    print(f"原范数 {norm:.4f}；裁剪后 {new_norm:.4f}；余弦相似度 {cos:.6f}")
    assert abs(new_norm - 1.0) < 1e-10 and cos > 0.999


if __name__ == "__main__":
    main()
