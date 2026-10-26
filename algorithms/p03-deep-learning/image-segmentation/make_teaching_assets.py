"""图像分割 TinyUNet-lite — 教学素材生成器（4 张 PNG + 1 个 GIF）。

原则：素材全部由本脚本生成，且与 demo.py / impl.py 的数字逐项对账；
数字对不上直接 assert 失败，不输出图片。流程图在 README 里用 Mermaid 画，
本脚本只出"概念图 / 结构图 / 对比图 / 指标图 / 阈值动画"。

运行：cd algorithms/p03-deep-learning/image-segmentation && uv run python make_teaching_assets.py
产出（images/）：
    01-合成数据与灰度重叠.png
    02-TinyUNet结构.png
    03-分割结果对照.png
    04-损失与指标.png
    05-阈值扫描.gif
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation, font_manager, ft2font
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
IMAGES = HERE / "images"
IMAGES.mkdir(exist_ok=True)


def setup_cjk_font() -> str:
    """按字体名查 + FreeType 字形校验，找不到就报错，绝不生成方块版素材。"""
    candidates = (
        "Noto Sans CJK SC", "Noto Sans CJK JP", "Source Han Sans SC", "Source Han Sans CN",
        "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
        "PingFang SC", "Hiragino Sans GB", "Heiti TC", "STHeiti", "Songti SC",
        "Arial Unicode MS", "Microsoft YaHei", "SimHei",
    )
    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
        if Path(path).exists():
            font_manager.fontManager.addfont(path)
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((n for n in candidates if n in available), None)
    if chosen is None:
        raise SystemExit("找不到含中文字形的字体，拒绝生成方块版素材。")
    font_path = font_manager.findfont(font_manager.FontProperties(family=chosen))
    if ft2font.FT2Font(font_path).get_char_index(ord("中")) == 0:
        raise SystemExit(f"字体 {chosen}（{font_path}）不含中文字形")
    plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False
    return chosen


FONT = setup_cjk_font()

import demo  # noqa: E402  （字体配置完再导入实验模块）


def verify() -> dict:
    """跑 demo（固定种子）并把素材要用的数字与实测值对账。"""
    res = demo.run(verbose=False)
    cnn = res["cnn"]["test"]
    lr = res["baselines"]["pixel_lr"]
    otsu = res["baselines"]["otsu"]
    assert res["params"] == 2417, f"参数量漂移：{res['params']}"
    assert abs(cnn["pixel_acc"] - 0.9803) < 2e-3, cnn
    assert abs(cnn["iou"] - 0.8503) < 2e-3, cnn
    assert abs(cnn["dice"] - 0.9191) < 2e-3, cnn
    assert abs(lr["iou"] - 0.4774) < 2e-3, lr
    assert abs(otsu["iou"] - 0.1917) < 2e-3, otsu
    assert cnn["iou"] > lr["iou"] + 0.3, "CNN 相对像素基线的收益不足"
    assert res["loss"][-1] < 0.5 * res["loss"][0]
    assert abs(res["loss"][-1] - 0.0613) < 2e-3, res["loss"][-1]
    assert 0.05 < res["data"]["test"][1].mean() < 0.3
    print(f"✓ 对账通过：IoU {cnn['iou']:.4f} / Dice {cnn['dice']:.4f} / "
          f"像素基线 IoU {lr['iou']:.4f} / 参数量 {res['params']}")
    return res


def _count_components(mask: np.ndarray) -> int:
    """四邻域连通域计数（只用于挑一张"两个分开形状"的样例图）。"""
    m = mask.copy()
    count = 0
    while m.any():
        y, x = np.argwhere(m)[0]
        count += 1
        m[y, x] = False
        stack = [(int(y), int(x))]
        while stack:
            cy, cx = stack.pop()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < m.shape[0] and 0 <= nx < m.shape[1] and m[ny, nx]:
                    m[ny, nx] = False
                    stack.append((ny, nx))
    return count


def make_data_panel(res: dict) -> None:
    """图 1：两张样例的灰度图、真值、轮廓与前景/背景灰度直方图。"""
    X, Y = res["data"]["train"]
    areas = Y.sum(axis=(1, 2, 3))
    components = [_count_components(Y[i, 0] > 0.5) for i in range(len(Y))]
    fg = [X[i, 0][Y[i, 0] > 0.5] for i in range(len(Y))]
    one = [i for i in range(len(Y)) if components[i] == 1 and fg[i].max() < 0.55
           and areas[i] > 40]
    two = [i for i in range(len(Y)) if components[i] == 2 and fg[i].min() < 0.5
           and fg[i].max() > 0.65]
    assert one and two, "数据里应同时有单个圆和圆+矩形两种样例"
    picks = [int(sorted(one, key=lambda i: areas[i])[len(one) // 2]),
             int(sorted(two, key=lambda i: areas[i])[len(two) // 2])]
    fig, axes = plt.subplots(2, 4, figsize=(12, 6))
    for row, idx in enumerate(picks):
        img, mask = X[idx, 0], Y[idx, 0] > 0.5
        axes[row, 0].imshow(img, cmap="gray", vmin=0, vmax=1)
        axes[row, 0].set_ylabel("1 个形状（圆）" if row == 0 else "2 个形状（圆+矩形）",
                                fontsize=11)
        axes[row, 1].imshow(mask, cmap="gray", vmin=0, vmax=1)
        axes[row, 2].imshow(img, cmap="gray", vmin=0, vmax=1)
        axes[row, 2].contour(mask, colors="#39d353", linewidths=1.2)
        axes[row, 3].hist(img[~mask], bins=25, range=(0, 1), density=True,
                          alpha=0.6, color="#7a7a7a", label="背景")
        axes[row, 3].hist(img[mask], bins=25, range=(0, 1), density=True,
                          alpha=0.6, color="#e45756", label="前景")
        axes[row, 3].set_xlabel("灰度")
        axes[row, 3].set_yticks([])
        if row == 0:
            axes[row, 3].legend(fontsize=9)
    for ax, title in zip(axes[0], ("输入灰度图", "真值 mask", "真值轮廓", "灰度分布重叠")):
        ax.set_title(title, fontsize=12)
    for ax in axes.ravel():
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle("合成数据：圆形的灰度落在背景渐变中段，单看一个像素分不开", fontsize=14)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-合成数据与灰度重叠.png", dpi=120)
    plt.close(fig)


def make_architecture_panel(res: dict) -> None:
    """图 2：网络结构与每层张量形状；数字来自 impl 的参数量。"""
    stages = [
        ("输入", "(N,1,32,32)", 0),
        ("Conv 1→8，3×3 + ReLU", "(N,8,32,32)", 80),
        ("MaxPool 2×2", "(N,8,16,16)", 0),
        ("Conv 8→16，3×3 + ReLU", "(N,16,16,16)", 1168),
        ("最近邻上采样 ×2", "(N,16,32,32)", 0),
        ("Conv 16→8，3×3 + ReLU", "(N,8,32,32)", 1160),
        ("1×1 Conv → Sigmoid", "(N,1,32,32)", 9),
    ]
    assert sum(s[2] for s in stages) == res["params"], "结构图参数量对不上 impl"
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ys = np.linspace(0.90, 0.10, len(stages))
    for i, ((name, shape, params), y) in enumerate(zip(stages, ys)):
        color = "#dbeafe" if i <= 2 else "#dcfce7"
        box = FancyBboxPatch((0.06, y - 0.042), 0.56, 0.084,
                             boxstyle="round,pad=0.008,rounding_size=0.012",
                             facecolor=color, edgecolor="#334155", linewidth=1.2)
        ax.add_patch(box)
        ax.text(0.34, y + 0.012, name, ha="center", va="center", fontsize=11)
        ax.text(0.34, y - 0.020, shape, ha="center", va="center",
                fontsize=9, color="#475569")
        if params:
            ax.text(0.66, y, f"{params} 参数", va="center", fontsize=9, color="#b45309")
        if i < len(stages) - 1:
            ax.add_patch(FancyArrowPatch((0.34, y - 0.050), (0.34, ys[i + 1] + 0.050),
                                         arrowstyle="-|>", mutation_scale=14,
                                         color="#334155", linewidth=1.2))
    ax.text(0.015, 0.74, "编码器", rotation=90, va="center", fontsize=12, color="#1d4ed8")
    ax.text(0.015, 0.26, "解码器", rotation=90, va="center", fontsize=12, color="#15803d")
    ax.text(0.82, 0.93, "总参数\n" + f"{res['params']}", fontsize=11, va="center",
            bbox=dict(boxstyle="round", facecolor="#fef3c7", edgecolor="#d97706"))
    ax.text(0.06, 0.015,
            "与 U-Net 的差别：没有 skip connection，边界细节只靠 16×16 瓶颈上采样恢复。",
            fontsize=9, color="#64748b")
    ax.set_title("TinyUNet-lite：编码器-解码器与张量形状", fontsize=14)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-TinyUNet结构.png", dpi=120)
    plt.close(fig)


def make_predictions_panel(res: dict) -> None:
    """图 3：低/中/高 IoU 三个测试样本的四路对比。"""
    X, Y = res["data"]["test"]
    pred = res["model"].predict(X)
    lr_pred = res["baselines"]["lr_model"].predict(X)
    per_image = [demo.iou(pred[i], Y[i]) for i in range(len(X))]
    areas = Y.sum(axis=(1, 2, 3))
    components = [_count_components(Y[i, 0] > 0.5) for i in range(len(Y))]
    fg = [X[i, 0][Y[i, 0] > 0.5] for i in range(len(Y))]
    rect = [i for i in range(len(Y)) if components[i] == 1 and fg[i].min() > 0.55
            and areas[i] < 140]
    circle = [i for i in range(len(Y)) if components[i] == 1 and fg[i].max() < 0.55
              and areas[i] > 40]
    mixed = [i for i in range(len(Y)) if components[i] == 2 and fg[i].min() < 0.55
             and fg[i].max() > 0.65]
    assert rect and circle and mixed, "测试集应包含矩形、圆、圆+矩形三类样例"
    picks = [int(sorted(rect, key=lambda i: areas[i])[len(rect) // 2]),
             int(sorted(circle, key=lambda i: areas[i])[len(circle) // 2]),
             int(sorted(mixed, key=lambda i: areas[i])[len(mixed) // 2])]
    labels = ["矩形：基线能抓", "圆形：基线漏掉", "圆+矩形：基线只剩矩形"]
    fig, axes = plt.subplots(3, 5, figsize=(14, 8))
    for row, idx in enumerate(picks):
        img, truth = X[idx, 0], Y[idx, 0] > 0.5
        p, lp = pred[idx, 0], lr_pred[idx, 0]
        err = np.zeros((32, 32, 3))
        err[truth & p] = (0.9, 0.9, 0.9)
        err[~truth & p] = (0.9, 0.25, 0.25)      # FP 红
        err[truth & ~p] = (0.25, 0.45, 1.0)      # FN 蓝
        panels = [
            (img, "gray", "输入"),
            (truth, "gray", "真值"),
            (p, "gray", "TinyUNet"),
            (err, None, "错误图（红 FP / 蓝 FN）"),
            (lp, "gray", "像素逻辑回归"),
        ]
        for col, (arr, cmap, title) in enumerate(panels):
            axes[row, col].imshow(arr, cmap=cmap, vmin=0, vmax=1, interpolation="nearest")
            axes[row, col].set_xticks([])
            axes[row, col].set_yticks([])
            if row == 0:
                axes[row, col].set_title(title, fontsize=11)
        axes[row, 0].set_ylabel(f"{labels[row]}\nIoU {per_image[idx]:.2f}", fontsize=10)
    fig.suptitle("测试集对照：TinyUNet 保住圆形，像素基线只认出矩形", fontsize=14)
    fig.tight_layout()
    fig.savefig(IMAGES / "03-分割结果对照.png", dpi=120)
    plt.close(fig)
    assert demo.iou(pred, Y) > demo.iou(lr_pred, Y) + 0.3


def make_metrics_panel(res: dict) -> None:
    """图 4：训练损失曲线 + 三种方法的 pixel acc / IoU / Dice。"""
    cnn = res["cnn"]["test"]
    lr = res["baselines"]["pixel_lr"]
    otsu = res["baselines"]["otsu"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    loss = res["loss"]
    ax1.plot(range(1, len(loss) + 1), loss, color="#1d4ed8", linewidth=2)
    ax1.set_xlabel("epoch")
    ax1.set_ylabel("BCE loss")
    ax1.set_title("训练损失：0.4617 → 0.0613", fontsize=12)
    ax1.grid(alpha=0.3)
    ax1.annotate(f"{loss[-1]:.4f}", (len(loss), loss[-1]), textcoords="offset points",
                 xytext=(6, 8), fontsize=9, color="#1d4ed8")

    names = ["TinyUNet-lite", "像素逻辑回归", "Otsu"]
    metrics = {
        "pixel acc": [cnn["pixel_acc"], lr["pixel_acc"], otsu["pixel_acc"]],
        "IoU": [cnn["iou"], lr["iou"], otsu["iou"]],
        "Dice": [cnn["dice"], lr["dice"], otsu["dice"]],
    }
    colors = ["#2563eb", "#f59e0b", "#10b981"]
    x = np.arange(len(names))
    width = 0.25
    for k, (label, vals) in enumerate(metrics.items()):
        bars = ax2.bar(x + (k - 1) * width, vals, width, label=label, color=colors[k])
        for b, v in zip(bars, vals):
            ax2.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.3f}",
                     ha="center", fontsize=8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(names)
    ax2.set_ylim(0, 1.1)
    ax2.set_title("测试集指标（参数量 2417）", fontsize=12)
    ax2.legend(fontsize=9, ncol=3, loc="upper center")
    ax2.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(IMAGES / "04-损失与指标.png", dpi=120)
    plt.close(fig)
    assert abs(cnn["iou"] - 0.8503) < 2e-3 and abs(lr["iou"] - 0.4774) < 2e-3


def make_threshold_gif(res: dict) -> None:
    """阈值扫描：同一张概率图，mask 随阈值收缩/扩张。"""
    Xte, Yte = res["data"]["test"]
    areas = Yte.reshape(len(Yte), -1).sum(axis=1)
    i = int(np.argmax(areas))
    img, gt = Xte[i, 0], Yte[i, 0].astype(bool)
    prob = res["model"].predict_proba(Xte[i:i + 1])[0, 0]
    thresholds = np.linspace(0.2, 0.8, 13)
    fig, ax = plt.subplots(figsize=(5.2, 5.2))

    def draw(k: int) -> None:
        ax.clear()
        pred = prob >= thresholds[k]
        inter = float(np.logical_and(pred, gt).sum())
        union = float(np.logical_or(pred, gt).sum())
        iou_v = inter / union if union else 1.0
        ax.imshow(img, cmap="gray", vmin=0, vmax=1)
        ax.imshow(np.ma.masked_where(~pred, pred), cmap="autumn", alpha=0.45)
        ax.contour(gt, levels=[0.5], colors="#2f9e44", linewidths=1.2)
        ax.set_title(f"阈值 {thresholds[k]:.2f}：IoU {iou_v:.3f}", fontsize=11)
        ax.axis("off")
        fig.tight_layout()

    anim = animation.FuncAnimation(fig, draw, frames=len(thresholds), interval=300)
    anim.save(IMAGES / "05-阈值扫描.gif", writer=animation.PillowWriter(fps=3))
    plt.close(fig)


def main() -> None:
    res = verify()
    make_data_panel(res)
    make_architecture_panel(res)
    make_predictions_panel(res)
    make_metrics_panel(res)
    make_threshold_gif(res)
    files = sorted(IMAGES.glob("*.png"))
    assert len(files) == 4, f"应生成 4 张图，实际 {len(files)}"
    for f in files:
        assert f.stat().st_size > 20_000, f"{f.name} 体积异常，可能没画出来"
    gif = IMAGES / "05-阈值扫描.gif"
    assert gif.exists() and gif.stat().st_size > 10_000, gif
    print("✓ 已生成：", "、".join(f.name for f in files + [gif]))


if __name__ == "__main__":
    main()
