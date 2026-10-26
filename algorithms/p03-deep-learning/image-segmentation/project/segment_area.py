"""迁移项目：多形状分割 + 面积测量。

与教学实验的差别（三个新约束）：
1. 每张图有 1–3 个互不重叠的形状（教学实验 1–2 个）；
2. 不只算 IoU，还要数出连通域个数、测量每个形状的面积；
3. 面积以"像素数 × 标定系数"给出，并报告相对误差。

运行：cd project && uv run python segment_area.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from data import make_dataset  # noqa: E402
from impl import TinyUNet, dice, iou, pixel_accuracy  # noqa: E402

PIXEL_MM2 = 0.25          # 假设相机标定后每像素 0.25 mm²
TRAIN_N, TEST_N = 480, 96
SEED_TRAIN, SEED_TEST = 41, 43
EPOCHS = 60


def connected_components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """四邻域连通域标记；返回 (labels, 组件数)。"""
    mask = np.asarray(mask) > 0.5
    labels = np.zeros(mask.shape, dtype=int)
    count = 0
    for y, x in np.argwhere(mask):
        if labels[y, x]:
            continue
        count += 1
        labels[y, x] = count
        stack = [(int(y), int(x))]
        while stack:
            cy, cx = stack.pop()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] \
                        and mask[ny, nx] and not labels[ny, nx]:
                    labels[ny, nx] = count
                    stack.append((ny, nx))
    return labels, count


def component_areas(labels: np.ndarray, count: int) -> list[int]:
    return [int((labels == k).sum()) for k in range(1, count + 1)]


def remove_small_components(mask: np.ndarray, min_area: int = 15) -> np.ndarray:
    """后处理：去掉面积小于 min_area 的孤立噪点，避免把 1–2 像素算成一个形状。"""
    labels, count = connected_components(mask)
    keep = np.zeros_like(labels, dtype=bool)
    for k in range(1, count + 1):
        if int((labels == k).sum()) >= min_area:
            keep |= labels == k
    return keep


def match_components(gt_labels: np.ndarray, gt_n: int,
                     pred_labels: np.ndarray, pred_n: int) -> list[tuple[int, int, float]]:
    """每个 GT 组件配一个 IoU 最大的预测组件；只保留 IoU ≥ 0.5 的配对。"""
    pairs = []
    for g in range(1, gt_n + 1):
        gm = gt_labels == g
        best = (0.0, 0)
        for p in range(1, pred_n + 1):
            pm = pred_labels == p
            inter = int(np.logical_and(gm, pm).sum())
            if inter == 0:
                continue
            overlap = inter / float(gm.sum() + pm.sum() - inter)
            if overlap > best[0]:
                best = (overlap, p)
        if best[1] and best[0] >= 0.5:
            pairs.append((g, best[1], best[0]))
    return pairs


def evaluate(model, X: np.ndarray, Y: np.ndarray) -> dict:
    pred = model.predict(X)
    rows = []
    for i in range(len(X)):
        truth = Y[i, 0] > 0.5
        guess = remove_small_components(pred[i, 0], min_area=15)
        gt_labels, gt_n = connected_components(truth)
        pr_labels, pr_n = connected_components(guess)
        gt_areas = component_areas(gt_labels, gt_n)
        pr_areas = component_areas(pr_labels, pr_n)
        pairs = match_components(gt_labels, gt_n, pr_labels, pr_n)
        comp_errors = [abs(pr_areas[p - 1] - gt_areas[g - 1]) / gt_areas[g - 1]
                       for g, p, _ in pairs]
        rows.append({
            "iou": iou(guess, truth), "dice": dice(guess, truth),
            "pixel_acc": pixel_accuracy(guess, truth),
            "gt_n": gt_n, "pred_n": pr_n,
            "area_err": abs(int(guess.sum()) - int(truth.sum())) / max(int(truth.sum()), 1),
            "comp_err": float(np.mean(comp_errors)) if comp_errors else np.nan,
            "matched": len(pairs), "gt_components": gt_n,
        })
    return {"rows": rows, "pred": pred,
            "iou": float(np.mean([r["iou"] for r in rows])),
            "dice": float(np.mean([r["dice"] for r in rows])),
            "pixel_acc": float(np.mean([r["pixel_acc"] for r in rows])),
            "count_acc": float(np.mean([r["gt_n"] == r["pred_n"] for r in rows])),
            "area_err": float(np.mean([r["area_err"] for r in rows])),
            "comp_err": float(np.nanmean([r["comp_err"] for r in rows])),
            "match_rate": float(sum(r["matched"] for r in rows) /
                                max(sum(r["gt_components"] for r in rows), 1))}


def main() -> None:
    Xtr, Ytr = make_dataset(TRAIN_N, SEED_TRAIN, max_shapes=3)
    Xte, Yte = make_dataset(TEST_N, SEED_TEST, max_shapes=3)
    print(f"训练 {len(Xtr)} 张（1–3 形状），测试 {len(Xte)} 张；"
          f"前景占比 {Ytr.mean():.3f}")
    t0 = time.perf_counter()
    model = TinyUNet(lr=0.008, epochs=EPOCHS, batch_size=16, random_state=0).fit(Xtr, Ytr)
    fit_time = time.perf_counter() - t0
    res = evaluate(model, Xte, Yte)
    print(f"TinyUNet 训练 {fit_time:.1f}s，参数量 {model.count_params()}；"
          f"测试集平均 IoU {res['iou']:.4f} / Dice {res['dice']:.4f} / "
          f"pixel acc {res['pixel_acc']:.4f}")

    print("\n形状个数 | 样本 | 平均 IoU | 平均面积相对误差 | 组件数完全正确")
    print("-" * 66)
    for k in (1, 2, 3):
        rows = [r for r in res["rows"] if r["gt_n"] == k]
        if not rows:
            continue
        print(f"{k:8d} | {len(rows):4d} | {np.mean([r['iou'] for r in rows]):8.4f} | "
              f"{np.mean([r['area_err'] for r in rows]):16.2%} | "
              f"{np.mean([r['gt_n'] == r['pred_n'] for r in rows]):14.1%}")
    print(f"\n整体（预测 mask 先去掉 <15 像素的孤立噪点）：组件数正确率 {res['count_acc']:.1%}；"
          f"总面积为 {res['area_err']:.2%} 相对误差；"
          f"匹配组件的面积误差 {res['comp_err']:.2%}；匹配率 {res['match_rate']:.1%}")

    # 面积测量示例：一张 2 形状的测试图，把像素面积换算成 mm²
    demo_idx = next((i for i, r in enumerate(res["rows"]) if r["gt_n"] == 2), 0)
    truth = Yte[demo_idx, 0] > 0.5
    guess = remove_small_components(res["pred"][demo_idx, 0], min_area=15)
    gt_labels, gt_n = connected_components(truth)
    pr_labels, pr_n = connected_components(guess)
    gt_areas = sorted(component_areas(gt_labels, gt_n))
    pr_areas = sorted(component_areas(pr_labels, pr_n))
    print(f"\n样例 #{demo_idx}：真值 {gt_n} 个组件、面积 {gt_areas} 像素；"
          f"预测 {pr_n} 个组件、面积 {pr_areas} 像素")
    print(f"换算成物理面积（每像素 {PIXEL_MM2} mm²）：真值 "
          f"{[round(a * PIXEL_MM2, 1) for a in gt_areas]} mm²，预测 "
          f"{[round(a * PIXEL_MM2, 1) for a in pr_areas]} mm²")

    assert res["iou"] > 0.80, "多形状测试集 IoU 低于 0.80"
    assert res["dice"] > 0.88, "多形状测试集 Dice 低于 0.88"
    assert res["count_acc"] > 0.70, "组件数正确率低于 70%"
    assert res["area_err"] < 0.15, "总面积相对误差超过 15%"
    assert res["match_rate"] > 0.75, "组件匹配率低于 75%"
    print("\n✓ 验收通过：IoU / Dice / 组件数 / 面积误差全部达标")


if __name__ == "__main__":
    main()
