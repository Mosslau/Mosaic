"""练习 04 参考解：手写 GIoU 与 GIoU-NMS。

GIoU = IoU - (最小闭包面积 - 并集面积) / 最小闭包面积，范围 [-1, 1]。
运行：uv run python exercises/sol-04-giou.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import iou  # noqa: E402


def giou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    """一个框与一组框的 GIoU。"""
    b = np.asarray(boxes, dtype=float).reshape(-1, 4)
    area = (box[2] - box[0]) * (box[3] - box[1])
    areas = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    x1 = np.maximum(box[0], b[:, 0])
    y1 = np.maximum(box[1], b[:, 1])
    x2 = np.minimum(box[2], b[:, 2])
    y2 = np.minimum(box[3], b[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    union = area + areas - inter
    hull = ((np.maximum(box[2], b[:, 2]) - np.minimum(box[0], b[:, 0]))
            * (np.maximum(box[3], b[:, 3]) - np.minimum(box[1], b[:, 1])))
    return inter / np.maximum(union, 1e-9) - (hull - union) / np.maximum(hull, 1e-9)


def nms_giou(boxes: np.ndarray, scores: np.ndarray,
             thresh: float = 0.5) -> np.ndarray:
    boxes = np.asarray(boxes, float).reshape(-1, 4)
    order = np.argsort(-np.asarray(scores, float))
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        order = rest[giou(boxes[i], boxes[rest]) <= thresh]
    return np.asarray(keep, int)


def main() -> None:
    a = np.array([0.0, 0.0, 10.0, 10.0])
    b = np.array([[1.0, 1.0, 11.0, 11.0], [20.0, 20.0, 30.0, 30.0]])
    g = giou(a, b)
    assert abs(giou(a, a[None])[0] - 1.0) < 1e-12
    assert g[0] < iou(a, b[:1])[0]                  # 同 IoU 时 GIoU 更小
    assert -1.0 <= g[1] < 0.0                       # 完全不相交 → 负值
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [20, 20, 30, 30]], float)
    scores = np.array([0.9, 0.8, 0.4])
    assert nms_giou(boxes, scores, 0.5).tolist() == [0, 2]
    print(f"GIoU(A,B)={g[0]:.4f} < IoU(A,B)={iou(a, b[:1])[0]:.4f}；"
          f"GIoU(A,C)={g[1]:.4f}；GIoU-NMS 保留 {nms_giou(boxes, scores).tolist()}")
    print("✓ GIoU / GIoU-NMS 自检通过")


if __name__ == "__main__":
    main()
