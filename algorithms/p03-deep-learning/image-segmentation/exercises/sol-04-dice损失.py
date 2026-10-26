"""参考解 04（实现）：soft Dice loss + 手写梯度，与 BCE 同数据对比。

运行：cd exercises && uv run python sol-04-dice损失.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data import make_dataset  # noqa: E402
from impl import (  # noqa: E402
    TinyUNet,
    bce_with_logits,
    dice,
    iou,
    maxpool_backward,
    pixel_accuracy,
    relu_grad,
    sigmoid,
    upsample_backward,
)


def soft_dice_loss(proba: np.ndarray, target: np.ndarray, eps: float = 1e-6) -> float:
    p = proba.reshape(len(proba), -1)
    t = target.reshape(len(target), -1)
    inter = (p * t).sum(axis=1)
    denom = p.sum(axis=1) + t.sum(axis=1)
    return float(1.0 - np.mean((2.0 * inter + eps) / (denom + eps)))


def soft_dice_grad(proba: np.ndarray, target: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """dL/dp：L = 1 - mean_i (2I_i+eps)/(S_i+eps)。"""
    p = proba.reshape(len(proba), -1)
    t = target.reshape(len(target), -1)
    inter = (p * t).sum(axis=1, keepdims=True)
    denom = p.sum(axis=1, keepdims=True) + t.sum(axis=1, keepdims=True)
    d_dice = (2.0 * t * (denom + eps) - (2.0 * inter + eps)) / (denom + eps) ** 2
    return (-d_dice / len(p)).reshape(proba.shape)


def backward_from_logits_grad(model: TinyUNet, cache: dict, dlogits: np.ndarray) -> dict:
    """与 impl.TinyUNet.backward 相同，只是首层梯度由调用方给（BCE 或 Dice）。"""
    d = model.head.backward(dlogits) * relu_grad(cache["z3"])
    d = upsample_backward(model.conv3.backward(d))
    d = model.conv2.backward(d * relu_grad(cache["z2"]))
    d = maxpool_backward(d, cache["idx"], cache["pool_shape"]) * relu_grad(cache["z1"])
    model.conv1.backward(d)
    return {"conv1": (model.conv1.dW, model.conv1.db),
            "conv2": (model.conv2.dW, model.conv2.db),
            "conv3": (model.conv3.dW, model.conv3.db),
            "head": (model.head.dW, model.head.db)}


def train(mode: str, X: np.ndarray, Y: np.ndarray, epochs: int = 30,
          lr: float = 0.01, batch_size: int = 16, seed: int = 0):
    model = TinyUNet(lr=lr, epochs=epochs, batch_size=batch_size, random_state=seed)
    rng = np.random.default_rng(seed)
    model._init_params(rng)
    history = []
    for _ in range(epochs):
        order = rng.permutation(len(X))
        total = 0.0
        for s in range(0, len(X), batch_size):
            idx = order[s:s + batch_size]
            logits, cache = model.forward(X[idx])
            p = sigmoid(logits)
            if mode == "bce":
                loss = bce_with_logits(logits, Y[idx])
                dlogits = (p - Y[idx]) / len(idx)
            else:
                loss = soft_dice_loss(p, Y[idx])
                dlogits = soft_dice_grad(p, Y[idx]) * p * (1.0 - p)
            total += loss * len(idx)
            model._adam_step(backward_from_logits_grad(model, cache, dlogits))
        history.append(total / len(X))
    return model, history


def check_dice_grad() -> float:
    """中心差分校验 soft Dice 对 logits 的梯度。"""
    rng = np.random.default_rng(0)
    z = rng.normal(size=(2, 5))
    t = (rng.random((2, 5)) > 0.5).astype(float)
    p = sigmoid(z)
    analytic = soft_dice_grad(p, t) * p * (1 - p)
    numeric = np.zeros_like(z)
    for idx in np.ndindex(z.shape):
        old = z[idx]
        z[idx] = old + 1e-6
        plus = soft_dice_loss(sigmoid(z), t)
        z[idx] = old - 1e-6
        minus = soft_dice_loss(sigmoid(z), t)
        z[idx] = old
        numeric[idx] = (plus - minus) / 2e-6
    return float(np.max(np.abs(analytic - numeric)))


def main() -> None:
    err = check_dice_grad()
    print(f"soft Dice 对 logits 的梯度最大误差 {err:.2e}")
    assert err < 1e-7

    Xtr, Ytr = make_dataset(192, seed=11)
    Xte, Yte = make_dataset(48, seed=13)
    print(f"{'损失':8} | {'末轮 loss':>9} | {'pixel acc':>9} | {'IoU':>6} | {'Dice':>6}")
    print("-" * 52)
    results = {}
    for mode, name in (("bce", "BCE"), ("dice", "Dice")):
        model, hist = train(mode, Xtr, Ytr)
        pred = model.predict(Xte)
        results[mode] = (iou(pred, Yte), dice(pred, Yte))
        print(f"{name:8} | {hist[-1]:9.4f} | {pixel_accuracy(pred, Yte):9.4f} | "
              f"{results[mode][0]:6.4f} | {results[mode][1]:6.4f}")
        assert hist[-1] < 0.7 * hist[0], f"{name} loss 未下降"
    assert results["dice"][0] > 0.5 and results["dice"][1] > 0.6
    gap = abs(results["bce"][1] - results["dice"][1])
    print(f"两种损失的 Dice 差 {gap:.4f}：类别不平衡时 Dice 直接优化重叠率，"
          "但小批量下梯度更噪，差距不保证单向。")


if __name__ == "__main__":
    main()
