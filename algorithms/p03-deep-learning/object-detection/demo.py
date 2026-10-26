"""目标检测 demo：合成数据上 TinyYOLO-lite vs 颜色阈值 + 连通域。

跑法（在 algorithms/ 下）：uv run python p03-deep-learning/object-detection/demo.py
或在实验目录：uv run python demo.py
"""

from __future__ import annotations

import time

import numpy as np
from baseline import detect_dataset, tune_threshold
from impl import TinyYOLO, average_precision, make_dataset, match_counts

EPOCHS = 60
N_TRAIN, N_VAL, N_TEST = 480, 160, 160
CHANNELS = 16


def _best_f1_threshold(dets: list[np.ndarray], gts: list[np.ndarray]) -> float:
    """在验证集上按 F1 选置信度阈值（测试集不参与调参）。"""
    best_f1, best = -1.0, 0.5
    for conf in np.linspace(0.05, 0.95, 19):
        tp, fp, fn = match_counts(dets, gts, float(conf))
        f1 = 2 * tp / max(2 * tp + fp + fn, 1)
        if f1 > best_f1:
            best_f1, best = f1, float(conf)
    return best


def _metrics(dets: list[np.ndarray], gts: list[np.ndarray],
             conf: float | None = None) -> dict:
    conf = _best_f1_threshold(dets, gts) if conf is None else conf
    picked = [d[d[:, 4] >= conf] if len(d) else d for d in dets]
    tp, fp, fn = match_counts(picked, gts, conf)
    return {"conf": conf, "map50": average_precision(picked, gts),
            "precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1),
            "tp": tp, "fp": fp, "fn": fn, "dets": picked}


def run_experiment(epochs: int = EPOCHS, seed: int = 0, verbose: bool = True) -> dict:
    """训练 + 验证选阈值 + 测试；返回模型、数据和全部指标（素材脚本复用）。"""
    Xtr, btr = make_dataset(N_TRAIN, seed=0)
    Xva, bva = make_dataset(N_VAL, seed=1)
    Xte, bte = make_dataset(N_TEST, seed=2)
    assert all(len(b) for b in btr + bva + bte), "每个场景至少一个目标"

    model = TinyYOLO(channels=CHANNELS, lr=0.02, epochs=epochs,
                     batch_size=32, seed=seed)
    t0 = time.perf_counter()
    model.fit(Xtr, btr)
    train_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    val_raw = model.raw_predict(Xva)
    model_ms = (time.perf_counter() - t0) / N_VAL * 1000
    val = _metrics(val_raw, bva)

    t0 = time.perf_counter()
    test_raw = model.raw_predict(Xte)
    test_ms = (time.perf_counter() - t0) / N_TEST * 1000
    test = _metrics(test_raw, bte, val["conf"])   # 复用 val 阈值，不看 test

    thresh, min_area = tune_threshold(Xva, bva)
    bval_raw = detect_dataset(Xva, thresh, min_area)
    bval = _metrics(bval_raw, bva)
    t0 = time.perf_counter()
    btest_raw = detect_dataset(Xte, thresh, min_area)
    base_ms = (time.perf_counter() - t0) / N_TEST * 1000
    btest = _metrics(btest_raw, bte, bval["conf"])

    result = {
        "model": model, "Xtr": Xtr, "btr": btr, "Xva": Xva, "bva": bva,
        "Xte": Xte, "bte": bte, "val": val, "test": test,
        "base_val": bval, "base_test": btest, "thresh": thresh,
        "min_area": min_area, "train_s": train_s,
        "model_ms": model_ms, "base_ms": base_ms, "epochs": epochs,
    }
    if verbose:
        n_gt = sum(len(b) for b in bte)
        print(f"数据：train {N_TRAIN} / val {N_VAL} / test {N_TEST} 张 32×32；"
              f"测试集目标 {n_gt} 个")
        n_params = sum(p.size for p in (model.conv.W, model.conv.b,
                                        model.head.W, model.head.b))
        print(f"TinyYOLO-lite：4×4 池化 → conv 1→{CHANNELS} 3×3 + ReLU + 8×8 头；"
              f"参数 {n_params}")
        print(f"训练：{epochs} 轮，loss {model.loss_history[0]:.3f} → "
              f"{model.loss_history[-1]:.3f}，{train_s:.1f}s")
        print(f"阈值：模型 conf {test['conf']:.2f}（val 选）；"
              f"基线 thr {thresh:.2f} / min_area {min_area}（val 选）")
        print(f"{'方法':<18}{'mAP@0.5':>9}{'P':>8}{'R':>8}{'ms/图':>9}")
        print(f"{'TinyYOLO-lite':<18}{test['map50']:>9.3f}{test['precision']:>8.3f}"
              f"{test['recall']:>8.3f}{test_ms:>9.3f}")
        print(f"{'阈值+连通域':<18}{btest['map50']:>9.3f}{btest['precision']:>8.3f}"
              f"{btest['recall']:>8.3f}{base_ms:>9.3f}")
    assert test["map50"] > 0.60, f"模型 mAP 太低：{test['map50']:.3f}"
    assert btest["map50"] > 0.50, f"基线 mAP 太低：{btest['map50']:.3f}"
    assert model.loss_history[-1] < model.loss_history[0]
    return result


if __name__ == "__main__":
    run_experiment()
