"""迁移项目：多目标场景检测（1–3 个目标、允许部分遮挡）。

与教学示例的差别：
1. 每张图 2–3 个目标（教学集 1–2 个）；
2. 目标允许重叠（IoU ≤ 0.35），且中心必须落在不同网格——这是 8×8 单类
   网格头的可表示边界；
3. 基线（颜色阈值 + 连通域）在重叠/相邻目标上会把多个目标并成一个连通域，
   正好用来检验"学习 + NMS"是否真的补上了这个洞。

运行：uv run python project/detect_scene.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from baseline import detect_dataset, tune_threshold  # noqa: E402
from impl import CELL, SIZE, TinyYOLO, average_precision, iou, make_image, match_counts  # noqa: E402

N_TRAIN, N_VAL, N_TEST = 640, 160, 200


def make_scene(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """2–3 个目标、中心格不冲突、两两 IoU ≤ 0.35 的场景。"""
    for _ in range(200):
        img, boxes = make_image(rng, max_objects=3, allow_overlap=True)
        if len(boxes) < 2:
            continue
        cells = {(int((b[0] + b[2]) / 2 // CELL), int((b[1] + b[3]) / 2 // CELL))
                 for b in boxes}
        overlap = any(iou(boxes[i], boxes[j:j + 1])[0] > 0.35
                      for i in range(len(boxes)) for j in range(i + 1, len(boxes)))
        if len(cells) == len(boxes) and not overlap:
            return img, boxes
    raise RuntimeError("场景生成失败：请放宽重叠约束")


def make_scene_dataset(n: int, seed: int) -> tuple[np.ndarray, list[np.ndarray]]:
    rng = np.random.default_rng(seed)
    X = np.empty((n, 1, SIZE, SIZE), dtype=np.float32)
    ys = []
    for i in range(n):
        X[i, 0], boxes = make_scene(rng)
        ys.append(boxes)
    return X, ys


def best_conf(dets: list[np.ndarray], gts: list[np.ndarray]) -> float:
    best_f1, best = -1.0, 0.5
    for conf in np.linspace(0.05, 0.95, 19):
        tp, fp, fn = match_counts(dets, gts, float(conf))
        f1 = 2 * tp / max(2 * tp + fp + fn, 1)
        if f1 > best_f1:
            best_f1, best = f1, float(conf)
    return best


def report(name: str, dets: list[np.ndarray], gts: list[np.ndarray],
           conf: float, ms: float) -> dict:
    picked = [d[d[:, 4] >= conf] if len(d) else d for d in dets]
    tp, fp, fn = match_counts(picked, gts, conf)
    out = {"conf": conf, "map50": average_precision(picked, gts),
           "precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1),
           "ms": ms, "tp": tp, "fp": fp, "fn": fn}
    print(f"{name:<16}mAP@0.5 {out['map50']:.3f}  P {out['precision']:.3f}  "
          f"R {out['recall']:.3f}  {ms:.3f} ms/图  (conf {conf:.2f})")
    return out


def main() -> None:
    Xtr, btr = make_scene_dataset(N_TRAIN, seed=100)
    Xva, bva = make_scene_dataset(N_VAL, seed=101)
    Xte, bte = make_scene_dataset(N_TEST, seed=102)
    n_obj = sum(len(b) for b in bte)
    print(f"场景：train {N_TRAIN} / val {N_VAL} / test {N_TEST}；"
          f"测试集 {n_obj} 个目标，平均 {n_obj / N_TEST:.2f} 个/图")

    model = TinyYOLO(channels=16, lr=0.02, epochs=100, batch_size=32, seed=0)
    t0 = time.perf_counter()
    model.fit(Xtr, btr)
    train_s = time.perf_counter() - t0
    print(f"训练：100 轮，loss {model.loss_history[0]:.3f} → "
          f"{model.loss_history[-1]:.3f}，{train_s:.1f}s")

    # NMS 阈值在 val 上按 AP 选，不许看 test
    nms_best = max((0.3, 0.4, 0.5),
                   key=lambda t: average_precision(model.raw_predict(Xva, t), bva))
    t0 = time.perf_counter()
    val_model = model.raw_predict(Xva, nms_best)
    model_conf = best_conf(val_model, bva)
    t0 = time.perf_counter()
    model_dets = model.raw_predict(Xte, nms_best)
    model_ms = (time.perf_counter() - t0) / N_TEST * 1000
    print(f"NMS 阈值（val 选）：{nms_best}；conf（val 选）：{model_conf:.2f}")
    m = report("TinyYOLO-lite", model_dets, bte, model_conf, model_ms)

    thresh, min_area = tune_threshold(Xva, bva)
    base_val = detect_dataset(Xva, thresh, min_area)
    base_conf = best_conf(base_val, bva)
    t0 = time.perf_counter()
    base_dets = detect_dataset(Xte, thresh, min_area)
    base_ms = (time.perf_counter() - t0) / N_TEST * 1000
    b = report("阈值+连通域", base_dets, bte, base_conf, base_ms)
    print(f"基线参数（val 选）：thr {thresh:.2f} / min_area {min_area} / "
          f"conf {base_conf:.2f}")

    assert m["map50"] > 0.80, f"项目验收失败：mAP {m['map50']:.3f} ≤ 0.80"
    assert m["map50"] > b["map50"] + 0.20, "学习器未明显超过基线"
    assert m["recall"] > 0.85, f"召回不足：{m['recall']:.3f}"
    print(f"验收通过：mAP {m['map50']:.3f} > 0.80，"
          f"且比基线高 {m['map50'] - b['map50']:.3f}")


if __name__ == "__main__":
    main()
