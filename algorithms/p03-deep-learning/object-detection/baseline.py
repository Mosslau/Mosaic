"""对照基线：颜色阈值 + 连通域（经典 CV 流水线）。

为什么选它而不是滑动窗口 + 逻辑回归：
1. 合成图的判别信息就是"亮"，阈值法不需要训练、参数可解释，是这类图像上
   成本最低的强基线；用它才能看清"学习"多付出了什么、换回了什么。
2. 滑动窗口 + 逻辑回归要枚举窗口尺度/步长（本图目标 6~10 像素、8×8 网格，
   窗口粒度直接决定上限），还会把对照变成"另一个学习器"，不如阈值法干净。
3. 阈值法在重叠目标、强噪点上会结构性失效——这正是网格预测 + NMS 要补的洞。

基线不是手写实现的一部分：按 skill 纪律②，`baseline.py` 可以用现成库，但这里
全部用 numpy + 标准库，保证零额外依赖。
"""

from __future__ import annotations

from collections import deque

import numpy as np
from impl import SIZE, nms


def box_blur(img: np.ndarray, k: int = 3) -> np.ndarray:
    """3×3 均值滤波：压掉孤立噪点，避免它们撑出小连通域。"""
    p = k // 2
    padded = np.pad(img, ((p, p), (p, p)), mode="edge")
    out = np.zeros_like(img, dtype=float)
    for i in range(k):
        for j in range(k):
            out += padded[i:i + SIZE, j:j + SIZE]
    return out / (k * k)


def connected_components(mask: np.ndarray) -> list[np.ndarray]:
    """4 邻域 BFS，返回每个连通域的像素坐标 (area,2)。"""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    comps: list[np.ndarray] = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        seen[y0, x0] = True
        queue, pixels = deque([(int(y0), int(x0))]), []
        while queue:
            y, x = queue.popleft()
            pixels.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        comps.append(np.asarray(pixels, dtype=int))
    return comps


def detect_image(img: np.ndarray, thresh: float = 0.5,
                 min_area: int = 12) -> np.ndarray:
    """单图：阈值 → 连通域 → 面积过滤 → bbox + 置信度 → NMS。返回 (k,5)。"""
    mask = box_blur(img) > thresh
    boxes, scores = [], []
    for pix in connected_components(mask):
        if len(pix) < min_area:
            continue
        y1, x1 = pix.min(axis=0)
        y2, x2 = pix.max(axis=0) + 1
        boxes.append([x1, y1, x2, y2])
        # 分数 = 平均亮度 × 面积的饱和项：大而亮的目标排在噪点前面
        score = float(img[pix[:, 0], pix[:, 1]].mean()) * min(1.0, len(pix) / 64.0) ** 0.5
        scores.append(score)
    if not boxes:
        return np.zeros((0, 5))
    boxes, scores = np.asarray(boxes, float), np.asarray(scores, float)
    keep = nms(boxes, scores, iou_thresh=0.3)
    return np.column_stack([boxes[keep], scores[keep]])


def detect_dataset(X: np.ndarray, thresh: float = 0.5,
                   min_area: int = 12) -> list[np.ndarray]:
    return [detect_image(np.asarray(x, dtype=float)[0], thresh, min_area) for x in X]


def tune_threshold(X: np.ndarray, gts: list[np.ndarray],
                   threshs=(0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65),
                   min_areas=(10, 16, 24)) -> tuple[float, int]:
    """在验证集上选 (阈值, 最小面积)，指标为 AP@0.5。"""
    from impl import average_precision

    best = (-1.0, 0.5, 12)
    for t in threshs:
        for a in min_areas:
            ap = average_precision(detect_dataset(X, t, a), gts)
            if ap > best[0]:
                best = (ap, t, a)
    return best[1], best[2]
