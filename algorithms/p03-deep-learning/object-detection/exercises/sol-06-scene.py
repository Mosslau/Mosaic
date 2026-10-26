"""练习 06 参考解：2–3 个重叠目标的多目标场景迁移。

运行：uv run python exercises/sol-06-scene.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "project"))

from baseline import detect_dataset, tune_threshold  # noqa: E402
from detect_scene import best_conf, make_scene_dataset  # noqa: E402
from impl import TinyYOLO, average_precision, match_counts  # noqa: E402


def metrics(dets, gts, conf):
    picked = [d[d[:, 4] >= conf] if len(d) else d for d in dets]
    tp, fp, fn = match_counts(picked, gts, conf)
    return average_precision(picked, gts), tp / max(tp + fp, 1), tp / max(tp + fn, 1)


def main() -> None:
    Xtr, btr = make_scene_dataset(640, seed=200)
    Xva, bva = make_scene_dataset(160, seed=201)
    Xte, bte = make_scene_dataset(160, seed=202)
    model = TinyYOLO(channels=16, lr=0.02, epochs=100, batch_size=32, seed=0)
    model.fit(Xtr, btr)
    conf = best_conf(model.raw_predict(Xva, 0.5), bva)
    ap, p, r = metrics(model.raw_predict(Xte, 0.5), bte, conf)

    thresh, area = tune_threshold(Xva, bva)
    bconf = best_conf(detect_dataset(Xva, thresh, area), bva)
    bap, bp, br = metrics(detect_dataset(Xte, thresh, area), bte, bconf)

    print(f"目标/图 {sum(map(len, bte)) / len(bte):.2f}；conf {conf:.2f} / 基线 {bconf:.2f}")
    print(f"TinyYOLO-lite  mAP {ap:.3f}  P {p:.3f}  R {r:.3f}")
    print(f"阈值+连通域     mAP {bap:.3f}  P {bp:.3f}  R {br:.3f}")
    assert ap > 0.80 and ap > bap + 0.20, (ap, bap)
    print("✓ 多目标场景迁移验收通过")


if __name__ == "__main__":
    main()
