"""练习 05 参考解：独立实现 PR 曲线与 VOC 全点 AP，并与 impl 对拍。

运行：uv run python exercises/sol-05-pr-ap.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import average_precision, iou  # noqa: E402


def ap_manual(dets: list[np.ndarray], gts: list[np.ndarray],
              thresh: float = 0.5) -> float:
    """按分数全局排序，逐图贪心匹配，再用全点插值算 AP。"""
    records = sorted([(float(d[4]), i, d[:4]) for i, ds in enumerate(dets) for d in ds],
                     key=lambda r: -r[0])
    used = [np.zeros(len(g), dtype=bool) for g in gts]
    tp = np.zeros(len(records))
    for k, (_, i, box) in enumerate(records):
        if not len(gts[i]):
            continue
        ov = iou(box, gts[i])
        ov[used[i]] = -1.0
        j = int(np.argmax(ov))
        if ov[j] >= thresh:
            tp[k], used[i][j] = 1.0, True
    total = sum(len(g) for g in gts)
    if not tp.sum() or not total:
        return 0.0
    ctp = np.cumsum(tp)
    rec = ctp / total
    prec = ctp / np.maximum(ctp + np.cumsum(1 - tp), 1e-9)
    mrec = np.concatenate([[0.0], rec, [1.0]])
    mpre = np.concatenate([[0.0], prec, [0.0]])
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])
    return float(np.sum((mrec[1:] - mrec[:-1]) * mpre[1:]))


def main() -> None:
    gts = [np.array([[0, 0, 10, 10], [20, 20, 30, 30]], float)]
    dets = [np.array([[0, 0, 10, 10, 0.9], [1, 1, 11, 11, 0.8],
                      [20, 20, 30, 30, 0.7], [40, 40, 50, 50, 0.6]])]
    mine = ap_manual(dets, gts)
    ref = average_precision(dets, gts)
    assert abs(mine - 5.0 / 6.0) < 1e-12, mine
    assert abs(mine - ref) < 1e-9, (mine, ref)
    assert ap_manual([np.zeros((0, 5))], gts) == 0.0
    print(f"手写 AP = {mine:.6f}；impl AP = {ref:.6f}；手算 5/6 = {5 / 6:.6f}")
    print("✓ PR/AP 对拍通过")


if __name__ == "__main__":
    main()
