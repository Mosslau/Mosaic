"""图像分割 TinyUNet-lite — demo：手写模型 vs 逐像素基线

    uv run python demo.py

    实验一  TinyUNet-lite 训练与验证（32×32 合成图，1–2 个形状）
    实验二  同测试集对照：逐像素逻辑回归 / Otsu 阈值
    实验三  阈值敏感性与边界带准确率
"""

from __future__ import annotations

import contextlib
import io
import time

import numpy as np
from baseline import OtsuSegmenter, PixelLogistic
from data import make_dataset
from impl import TinyUNet, dice, iou, pixel_accuracy

SPLITS = {"train": (320, 11), "val": (64, 12), "test": (64, 13)}
LR, EPOCHS, BATCH = 0.008, 60, 16


def load_data() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    return {name: make_dataset(n, seed, allow_overlap=False)
            for name, (n, seed) in SPLITS.items()}


def score(pred: np.ndarray, target: np.ndarray) -> dict[str, float]:
    return {"pixel_acc": pixel_accuracy(pred, target),
            "iou": iou(pred, target), "dice": dice(pred, target)}


def evaluate(model, X: np.ndarray, y: np.ndarray) -> dict[str, float]:
    return score(model.predict(X), y)


def train_tinyunet(data, epochs: int = EPOCHS, lr: float = LR):
    t0 = time.perf_counter()
    model = TinyUNet(lr=lr, epochs=epochs, batch_size=BATCH, random_state=0)
    model.fit(*data["train"])
    return model, time.perf_counter() - t0


def _dilate(mask: np.ndarray) -> np.ndarray:
    out = mask.copy()
    for axis, shift in ((1, 1), (1, -1), (2, 1), (2, -1)):
        out |= np.roll(mask, shift, axis=axis)
    return out


def boundary_band(target: np.ndarray, width: int = 1) -> np.ndarray:
    """目标 mask 的内边界向外膨胀 width 像素，得到固定评估带。"""
    m = np.asarray(target) > 0.5
    core = m.copy()
    for axis, shift in ((1, 1), (1, -1), (2, 1), (2, -1)):
        core &= np.roll(m, shift, axis=axis)
    band = m & ~core
    for _ in range(width):
        band = _dilate(band)
    return band


def experiment_train(data, epochs: int = EPOCHS):
    model, seconds = train_tinyunet(data, epochs)
    print(f"== 实验一：TinyUNet-lite 训练（{epochs} 轮，Adam，BCE） ==")
    print(f"参数量 {model.count_params()}；loss {model.loss_history[0]:.4f} → "
          f"{model.loss_history[-1]:.4f}；训练 {seconds:.1f}s")
    results = {name: evaluate(model, *data[name]) for name in ("train", "val", "test")}
    print(f"{'split':6} | {'pixel acc':>9} | {'IoU':>6} | {'Dice':>6}")
    print("-" * 38)
    for name, m in results.items():
        print(f"{name:6} | {m['pixel_acc']:9.4f} | {m['iou']:6.4f} | {m['dice']:6.4f}")
    assert model.loss_history[-1] < 0.5 * model.loss_history[0], "loss 未明显下降"
    assert results["test"]["iou"] > 0.75, "测试 IoU 过低"
    return model, seconds, results


def experiment_baselines(data, cnn_test: dict) -> dict:
    Xtr, Ytr = data["train"]
    Xte, Yte = data["test"]
    print("\n== 实验二：同测试集对照（都只看单像素灰度） ==")
    t0 = time.perf_counter()
    lr_model = PixelLogistic().fit(Xtr, Ytr)
    lr_time = time.perf_counter() - t0
    lr_test = evaluate(lr_model, Xte, Yte)
    t0 = time.perf_counter()
    otsu = OtsuSegmenter().fit(Xtr, Ytr)
    otsu_time = time.perf_counter() - t0
    otsu_test = evaluate(otsu, Xte, Yte)
    rows = [("TinyUNet-lite", cnn_test, None),
            ("逐像素逻辑回归", lr_test, lr_time),
            (f"Otsu（阈值 {otsu.threshold:.3f}）", otsu_test, otsu_time)]
    print(f"{'方法':22} | {'pixel acc':>9} | {'IoU':>6} | {'Dice':>6} | {'耗时(s)':>8}")
    print("-" * 68)
    for name, m, seconds in rows:
        cost = "训练见上" if seconds is None else f"{seconds:.2f}"
        print(f"{name:22} | {m['pixel_acc']:9.4f} | {m['iou']:6.4f} | "
              f"{m['dice']:6.4f} | {cost:>8}")
    assert cnn_test["iou"] > lr_test["iou"] + 0.2, "CNN 相对像素基线收益不足"
    assert cnn_test["dice"] > lr_test["dice"] + 0.2, "Dice 收益不足"
    return {"pixel_lr": lr_test, "otsu": otsu_test, "pixel_lr_time": lr_time,
            "otsu_time": otsu_time, "otsu_threshold": otsu.threshold,
            "lr_model": lr_model}


def experiment_threshold_and_boundary(data, model, baselines) -> dict:
    Xv, Yv = data["val"]
    Xte, Yte = data["test"]
    proba = model.predict_proba(Xv)
    grid = np.linspace(0.2, 0.8, 25)
    scores = [iou(proba > t, Yv) for t in grid]
    best_t = float(grid[int(np.argmax(scores))])
    print("\n== 实验三：阈值敏感性与边界带 ==")
    print(f"验证集阈值扫描 0.20–0.80：0.50 处 IoU {iou(proba > 0.5, Yv):.4f}，"
          f"最佳阈值 {best_t:.2f} 处 IoU {max(scores):.4f}")

    band = boundary_band(Yte)
    cnn_pred = model.predict(Xte)
    lr_pred = baselines["lr_model"].predict(Xte)
    truth = Yte > 0.5
    cnn_band = float(np.mean(cnn_pred[band] == truth[band]))
    lr_band = float(np.mean(lr_pred[band] == truth[band]))
    print(f"边界带像素（{band.sum() / band.size:.1%} 区域）：TinyUNet acc {cnn_band:.4f}，"
          f"像素逻辑回归 acc {lr_band:.4f}")
    assert cnn_band > lr_band, "CNN 在边界带没有优势"
    return {"best_threshold": best_t, "best_iou": float(max(scores)),
            "iou_at_050": float(iou(proba > 0.5, Yv)),
            "band_ratio": float(band.sum() / band.size),
            "cnn_band_acc": cnn_band, "lr_band_acc": lr_band}


def _run(epochs: int) -> dict:
    data = load_data()
    model, seconds, cnn = experiment_train(data, epochs)
    baselines = experiment_baselines(data, cnn["test"])
    analysis = experiment_threshold_and_boundary(data, model, baselines)
    return {"data": data, "model": model, "cnn": cnn, "baselines": baselines,
            "analysis": analysis, "seconds": seconds,
            "params": model.count_params(), "loss": model.loss_history}


def run(epochs: int = EPOCHS, verbose: bool = True) -> dict:
    if verbose:
        return _run(epochs)
    with contextlib.redirect_stdout(io.StringIO()):
        return _run(epochs)


def main() -> None:
    run()
    print("\n→ 结论：单像素灰度重叠时，逐像素基线把圆形整片漏掉；")
    print("  编码器-解码器利用局部上下文，IoU/Dice 与边界带准确率都明显更高。")
    print("→ 复现命令：uv run python demo.py")


if __name__ == "__main__":
    main()
