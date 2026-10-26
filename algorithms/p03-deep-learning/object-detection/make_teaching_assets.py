"""目标检测实验素材生成器（4 张图 + 1 个 GIF，全部由本脚本重跑生成）。

产出（images/）：
    01-任务与网格.png   32×32 图 + 8×8 网格 + objectness 标签
    02-编码与NMS.png    中心格偏移编码 + NMS 前/后候选框
    03-训练损失.png     60 轮训练损失
    04-检测对比.png     GT / TinyYOLO / 阈值基线 三行对比
    05-阈值扫描.gif     conf 从 0.05 扫到 0.95，框逐步出现/消失

对账：素材里的 mAP、P/R、loss、IoU 与 impl.py / demo.py 的实跑输出逐项断言，
不一致直接报错、不出图。运行：uv run python make_teaching_assets.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation, font_manager
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
IMAGES = HERE / "images"
IMAGES.mkdir(exist_ok=True)


def setup_cjk_font() -> str:
    names = ("Noto Sans CJK SC", "Noto Sans CJK JP", "Source Han Sans SC",
             "WenQuanYi Zen Hei", "Hiragino Sans GB", "PingFang SC", "Heiti TC",
             "STHeiti", "Songti SC", "Arial Unicode MS", "Microsoft YaHei", "SimHei")
    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
        if Path(path).exists():
            font_manager.fontManager.addfont(path)
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((n for n in names if n in available), None)
    if chosen is None:
        raise SystemExit("找不到含中文字形的字体，拒绝生成方块版素材")
    path = font_manager.findfont(font_manager.FontProperties(family=chosen))
    from matplotlib import ft2font
    if ft2font.FT2Font(path).get_char_index(ord("中")) == 0:
        raise SystemExit(f"字体 {chosen} 不含中文字形")
    plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False
    return chosen


FONT = setup_cjk_font()

from demo import run_experiment  # noqa: E402
from impl import SIZE, decode_cells, encode_targets, iou, match_counts, nms  # noqa: E402

GREEN, BLUE, GRAY = "#2f9e44", "#1c7ed6", "#adb5bd"


def draw_boxes(ax, boxes, color, ls="-", label=None, scores=None) -> None:
    for k, b in enumerate(np.asarray(boxes, float).reshape(-1, 4)):
        ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1],
                               fill=False, edgecolor=color, lw=1.6, ls=ls))
        if scores is not None:
            ax.text(b[0], b[1] - 0.6, f"{scores[k]:.2f}", color=color, fontsize=6)
    if label:
        ax.plot([], [], color=color, ls=ls, label=label)


def fig_task(r: dict) -> None:
    i = 10
    img, gt = r["Xte"][i, 0], r["bte"][i]
    obj, _ = encode_targets(gt)
    assert len(gt) == 2 and obj.sum() == 2, "素材选图应含 2 个目标、2 个正格"
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.2))
    ax = axes[0]
    ax.imshow(img, cmap="gray", vmin=0, vmax=1, extent=(0, SIZE, SIZE, 0))
    for g in range(1, 8):
        ax.axvline(g * 4, color="#ffe066", lw=0.7, alpha=0.8)
        ax.axhline(g * 4, color="#ffe066", lw=0.7, alpha=0.8)
    draw_boxes(ax, gt, GREEN, label="GT bbox")
    ax.set_title("32×32 灰度图：8×8 网格，每格 4×4 像素", fontsize=10)
    ax.set_xticks([0, 8, 16, 24, 32])
    ax.set_yticks([0, 8, 16, 24, 32])
    ax.legend(loc="upper right", fontsize=8)

    ax = axes[1]
    ax.imshow(obj, cmap="Oranges", vmin=0, vmax=1, extent=(0, 8, 8, 0))
    for gy, gx in zip(*np.nonzero(obj)):
        ax.text(gx + 0.5, gy + 0.55, "1", ha="center", va="center",
                color="#c92a2a", fontsize=11, fontweight="bold")
    ax.set_xticks(range(9))
    ax.set_yticks(range(9))
    ax.set_title("objectness 标签：只有目标中心格为 1", fontsize=10)
    ax.set_xlabel("网格列 gx")
    ax.set_ylabel("网格行 gy")
    fig.tight_layout()
    fig.savefig(IMAGES / "01-任务与网格.png", dpi=130)
    plt.close(fig)


def fig_encode_nms(r: dict) -> None:
    i = 84
    img, gt = r["Xte"][i, 0], r["bte"][i]
    raw = r["model"]._forward(r["Xte"][i:i + 1])[0]
    boxes, scores = decode_cells(raw)
    sel = scores >= 0.05                       # 只画有意义的候选框
    boxes, scores = boxes[sel], scores[sel]
    keep = nms(boxes, scores, 0.5)
    assert len(boxes) < 64 and len(keep) <= 5 and len(gt) == 2

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.2))
    ax = axes[0]
    ax.set_xlim(8, 22)
    ax.set_ylim(16, 2)
    for g in (8, 12, 16, 20):
        ax.axvline(g, color="#ced4da", lw=0.8)
        ax.axhline(g, color="#ced4da", lw=0.8)
    ax.add_patch(Rectangle((12, 8), 4, 4, fill=True, facecolor="#d0ebff",
                           edgecolor=BLUE, lw=1.8))
    ax.add_patch(Rectangle((11, 5), 8, 8, fill=False, edgecolor=GREEN, lw=1.8))
    ax.plot([15], [9], "o", color="#c92a2a", ms=5)
    ax.annotate("中心 (15,9)", (15, 9), (16.2, 6.2), fontsize=8,
                arrowprops=dict(arrowstyle="->", lw=0.8))
    ax.annotate("格 (gx=3, gy=2)", (14, 10), (17.2, 11.0), fontsize=8, color=BLUE,
                arrowprops=dict(arrowstyle="->", lw=0.8, color=BLUE))
    ax.text(8.3, 3.2, "fx=(15-12)/4=0.75\nfy=(9-8)/4=0.25\nw=8/32=0.25, h=0.25",
            fontsize=8, va="top", bbox=dict(fc="white", ec="#dee2e6", alpha=.9))
    ax.set_title("网格编码：中心落格 + 格内偏移 + 宽高", fontsize=10)
    ax.set_aspect("equal")

    ax = axes[1]
    ax.imshow(img, cmap="gray", vmin=0, vmax=1, extent=(0, SIZE, SIZE, 0))
    for b in boxes:
        ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1],
                               fill=False, edgecolor=GRAY, lw=0.5, alpha=0.5))
    draw_boxes(ax, boxes[keep], BLUE, label=f"NMS 保留 {len(keep)} 个")
    draw_boxes(ax, gt, GREEN, ls="--", label="GT")
    ax.set_xlim(0, SIZE)
    ax.set_ylim(SIZE, 0)
    ax.set_title(f"NMS：{len(boxes)} 个候选 → 保留 {len(keep)} 个（IoU>0.5）", fontsize=10)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-编码与NMS.png", dpi=130)
    plt.close(fig)


def fig_loss(r: dict) -> None:
    loss = np.asarray(r["model"].loss_history)
    assert abs(loss[0] - 3.535) < 0.01 and abs(loss[-1] - 0.333) < 0.01
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.plot(loss, color=BLUE, lw=1.6)
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss = BCE(objectness) + MSE(bbox)")
    ax.set_title(f"60 轮训练损失：{loss[0]:.3f} → {loss[-1]:.3f}"
                 f"（测试 mAP@0.5 {r['test']['map50']:.3f}）", fontsize=10)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(IMAGES / "03-训练损失.png", dpi=130)
    plt.close(fig)


def fig_compare(r: dict) -> None:
    rows = [10, 84, 135]
    fig, axes = plt.subplots(3, 3, figsize=(9.6, 9.2))
    for row, i in enumerate(rows):
        gt = r["bte"][i]
        model = r["test"]["dets"][i]
        base = r["base_test"]["dets"][i]
        panels = [(gt, None, "GT", GREEN),
                  (model[:, :4], model[:, 4], "TinyYOLO-lite", BLUE),
                  (base[:, :4], base[:, 4], "阈值+连通域", "#e8590c")]
        for col, (boxes, scores, name, color) in enumerate(panels):
            ax = axes[row, col]
            ax.imshow(r["Xte"][i, 0], cmap="gray", vmin=0, vmax=1,
                      extent=(0, SIZE, SIZE, 0))
            draw_boxes(ax, gt, GREEN, ls="--")
            if name != "GT":
                draw_boxes(ax, boxes, color, scores=scores)
            ax.set_xlim(0, SIZE)
            ax.set_ylim(SIZE, 0)
            ax.set_xticks([])
            ax.set_yticks([])
            if row == 0:
                ax.set_title(name, fontsize=10)
            if col == 0:
                ax.set_ylabel(f"图 #{i}\nGT {len(gt)}", fontsize=8)
            if name != "GT":
                dets = np.column_stack([boxes, scores]) if len(boxes) else np.zeros((0, 5))
                tp, fp, fn = match_counts([dets], [gt], conf=0.0)
                ax.set_xlabel(f"TP {tp} / FP {fp} / FN {fn}", fontsize=8)
    fig.suptitle("同一测试集：学习器找回被合并目标，也会多出重复框或漏检", fontsize=11)
    fig.tight_layout()
    fig.savefig(IMAGES / "04-检测对比.png", dpi=130)
    plt.close(fig)


def verify() -> dict:
    r = run_experiment(verbose=False)
    model, base = r["test"], r["base_test"]
    assert abs(model["map50"] - 0.9956) < 0.001, model["map50"]
    assert abs(base["map50"] - 0.9770) < 0.001, base["map50"]
    assert model["map50"] > base["map50"]
    assert abs(model["precision"] - 0.9838) < 0.002
    assert abs(base["precision"] - 0.9958) < 0.002
    assert abs(r["model"].loss_history[0] - 3.535) < 0.01
    assert abs(r["model"].loss_history[-1] - 0.333) < 0.01
    n_params = sum(p.size for p in (r["model"].conv.W, r["model"].conv.b,
                                    r["model"].head.W, r["model"].head.b))
    assert n_params == 245, n_params
    # 手算示例对账：bbox (11,5,19,13) 与预测 (12,6,20,14) 的 IoU = 49/79
    hand = iou(np.array([11.0, 5.0, 19.0, 13.0]),
               np.array([[12.0, 6.0, 20.0, 14.0]]))[0]
    assert abs(hand - 49.0 / 79.0) < 1e-12, hand
    obj, tbox = encode_targets(np.array([[11.0, 5.0, 19.0, 13.0]]))
    assert obj[2, 3] == 1 and abs(tbox[2, 3, 0] - np.log(3.0)) < 1e-6
    print(f"  ✓ 对账：模型 mAP {model['map50']:.4f} / 基线 {base['map50']:.4f}；"
          f"loss {r['model'].loss_history[0]:.3f} → {r['model'].loss_history[-1]:.3f}")
    return r


def fig_threshold_gif(r: dict) -> None:
    """置信度阈值扫描：同一个模型、同一张图，框随 conf 出现/消失。"""
    i = 10
    img, gt = r["Xte"][i, 0], r["bte"][i]
    confs = np.linspace(0.05, 0.95, 19)
    fig, ax = plt.subplots(figsize=(5.4, 5.4))

    def draw(k: int) -> None:
        ax.clear()
        ax.imshow(img, cmap="gray", vmin=0, vmax=1, extent=(0, SIZE, SIZE, 0))
        draw_boxes(ax, gt, GREEN, ls="--")
        dets = r["model"].predict(r["Xte"][i:i + 1], conf=float(confs[k]))[0]
        if len(dets):
            draw_boxes(ax, dets[:, :4], BLUE, scores=dets[:, 4])
        ax.set_xlim(0, SIZE)
        ax.set_ylim(SIZE, 0)
        ax.set_title(f"conf ≥ {confs[k]:.2f}：{len(dets)} 个预测框（GT {len(gt)} 个）",
                     fontsize=11)
        ax.axis("off")
        fig.tight_layout()

    anim = animation.FuncAnimation(fig, draw, frames=len(confs), interval=250)
    anim.save(IMAGES / "05-阈值扫描.gif", writer=animation.PillowWriter(fps=4))
    plt.close(fig)


def main() -> None:
    print("① 训练并对账 …")
    r = verify()
    print("② 任务与网格 …")
    fig_task(r)
    print("③ 编码与 NMS …")
    fig_encode_nms(r)
    print("④ 训练损失 …")
    fig_loss(r)
    print("⑤ 检测对比 …")
    fig_compare(r)
    print("⑥ 阈值扫描 GIF …")
    fig_threshold_gif(r)
    for name in ("01-任务与网格.png", "02-编码与NMS.png",
                 "03-训练损失.png", "04-检测对比.png", "05-阈值扫描.gif"):
        path = IMAGES / name
        assert path.exists() and path.stat().st_size > 10_000, path
        print(f"  {name}  {path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
