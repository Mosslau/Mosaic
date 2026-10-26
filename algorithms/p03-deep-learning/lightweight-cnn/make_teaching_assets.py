"""轻量级 CNN — 图文素材生成器（供 README 引用）。

产出（`images/`）：
    00-深度可分离卷积.png  标准卷积 vs depthwise + pointwise 的分解与参数量
    01-参数量对比.png      分阶段参数量：DS vs 同通道标准 Conv
    02-准确率与延迟.png    三路模型的测试 acc 与单批前向延迟
    03-训练曲线.png        训练损失与训练 acc 曲线
    04-训练过程.gif        训练损失/准确率随 epoch 逐步展开（时间维度）

脚本复用 demo.run_experiments() 的真实结果，断言素材里的数字与 impl/demo 一致。
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation, font_manager, patches

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
IMAGES = HERE / "images"
IMAGES.mkdir(exist_ok=True)

COLOR = dict(ds="#2b8a3e", std="#c92a2a", torch="#3b5bdb", grid="#dee2e6", dim="#868e96")


def setup_cjk_font() -> str:
    names = ("Noto Sans CJK SC", "Noto Sans CJK JP", "Source Han Sans SC", "Source Han Sans CN",
             "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
             "Hiragino Sans GB", "PingFang SC", "Heiti TC", "STHeiti", "Songti SC",
             "Arial Unicode MS", "Microsoft YaHei", "SimHei")
    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
        if Path(path).exists():
            font_manager.fontManager.addfont(path)
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((n for n in names if n in available), None)
    if chosen is None:
        raise SystemExit("找不到含中文字形的字体，拒绝生成方块版素材。")
    font_path = font_manager.findfont(font_manager.FontProperties(family=chosen))
    from matplotlib import ft2font
    if ft2font.FT2Font(font_path).get_char_index(ord("中")) == 0:
        raise SystemExit(f"字体 {chosen} 不含中文字形，拒绝生成方块版素材")
    plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False
    return chosen


FONT_USED = setup_cjk_font()

import demo as D  # noqa: E402


def verify(res: dict) -> None:
    """素材数字的唯一来源：与 impl/demo 的实际输出逐项对账。"""
    assert res["params"] == [2858, 15554, 2858], "参数与 impl.py 不一致"
    assert 5.0 < res["params"][1] / res["params"][0] < 6.0
    assert sum(res["stage_ds"].values()) == 2858
    assert sum(res["stage_std"].values()) == 15554
    assert res["stage_ds"]["block1"] == 248 and res["stage_std"]["block1"] == 1184
    assert res["stage_ds"]["block2"] == 752 and res["stage_ds"]["block3"] == 1440
    assert min(res["test_acc"]) > 0.95
    assert all(loss[0] > loss[-1] for loss in res["loss"])
    assert all(len(loss) == res["epochs"] for loss in res["loss"])
    assert all(ms > 0 for ms in res["latency_ms"])
    print(f"  ✓ 对账通过：参数 {res['params']}，acc {[round(a, 4) for a in res['test_acc']]}，"
          f"延迟 {[round(m, 2) for m in res['latency_ms']]} ms")


def _stack(ax, x, y, n, color, label, width=0.9, height=0.42):
    """画一摞通道方块，表示 n 个特征图/卷积核。"""
    for i in range(n):
        ax.add_patch(patches.Rectangle((x + i * 0.12, y + i * 0.10), width, height,
                                       facecolor=color, edgecolor="white", alpha=0.85, lw=1))
    ax.text(x + width / 2, y - 0.28, label, ha="center", va="top", fontsize=9)


def make_concept() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2))
    for ax in axes:
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 6.4)
        ax.axis("off")

    ax = axes[0]
    ax.set_title("标准 3×3 卷积：一个核跨全部输入通道", fontsize=12, pad=6)
    _stack(ax, 0.3, 3.6, 4, "#adb5bd", "输入 8 通道")
    ax.add_patch(patches.Rectangle((3.1, 2.9), 2.0, 1.9, facecolor=COLOR["std"],
                                   edgecolor="none", alpha=0.8))
    ax.text(4.1, 3.85, "3×3", color="white", ha="center", va="center", fontsize=13)
    ax.text(4.1, 2.55, "每个输出通道一个 3×3×8 核", ha="center", fontsize=9)
    _stack(ax, 6.5, 3.6, 4, "#74c0fc", "输出 16 通道")
    ax.annotate("", xy=(6.3, 4.1), xytext=(5.3, 4.1),
                arrowprops=dict(arrowstyle="->", lw=1.6, color="#343a40"))
    ax.text(2.0, 1.5, "参数量 = 3×3×8×16\n= 1152（+BN 32）", fontsize=11,
            bbox=dict(boxstyle="round,pad=0.4", fc="#fff5f5", ec=COLOR["std"]))
    ax.text(0.3, 0.5, "每个输出通道都加总全部 8 个输入通道", fontsize=9, color=COLOR["dim"])

    ax = axes[1]
    ax.set_title("深度可分离 = depthwise 3×3 + pointwise 1×1", fontsize=12, pad=6)
    _stack(ax, 0.3, 4.2, 4, "#adb5bd", "输入 8 通道")
    for i in range(3):
        ax.add_patch(patches.Rectangle((2.7 + i * 0.16, 3.9 + i * 0.14), 0.8, 0.8,
                                       facecolor=COLOR["ds"], edgecolor="white", alpha=0.85))
    ax.text(3.5, 3.1, "8 个 3×3 单通道核", ha="center", fontsize=9)
    ax.text(3.5, 2.55, "= 9×8 = 72", ha="center", fontsize=11, color=COLOR["ds"], weight="bold")
    _stack(ax, 5.4, 4.2, 4, "#95d5b2", "中间 8 通道")
    ax.add_patch(patches.Rectangle((7.3, 4.1), 0.7, 0.7, facecolor=COLOR["torch"],
                                   edgecolor="none", alpha=0.85))
    ax.text(7.65, 3.1, "16 个 1×1×8 核", ha="center", fontsize=9)
    ax.text(7.65, 2.55, "= 8×16 = 128", ha="center", fontsize=11,
            color=COLOR["torch"], weight="bold")
    _stack(ax, 8.6, 4.2, 4, "#74c0fc", "输出 16 通道")
    ax.text(2.2, 1.2, "参数量 = 72 + 128 = 200（+BN 48 → 248）", fontsize=11,
            bbox=dict(boxstyle="round,pad=0.4", fc="#ebfbee", ec=COLOR["ds"]))
    ax.text(0.3, 0.5, "depthwise 不跨通道求和；pointwise 负责通道混合", fontsize=9,
            color=COLOR["dim"])
    for x0, x1 in ((1.8, 2.55), (3.65, 5.25), (6.45, 7.15), (8.1, 8.45)):
        ax.annotate("", xy=(x1, 4.45), xytext=(x0, 4.45),
                    arrowprops=dict(arrowstyle="->", lw=1.3, color="#343a40"))

    fig.suptitle("同样的 8→16 通道：1152 vs 200 个卷积权重（约 5.8×）", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-深度可分离卷积.png", dpi=140)
    plt.close(fig)


def make_params(res: dict) -> None:
    stages = list(res["stage_ds"])
    ds = [res["stage_ds"][s] for s in stages]
    std = [res["stage_std"][s] for s in stages]
    x = np.arange(len(stages))
    fig, ax = plt.subplots(figsize=(9.6, 5.2))
    b1 = ax.bar(x - 0.19, ds, 0.38, color=COLOR["ds"], label="DS（depthwise+pointwise）")
    b2 = ax.bar(x + 0.19, std, 0.38, color=COLOR["std"], label="标准 3×3 卷积")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() * 1.12,
                    f"{int(b.get_height())}", ha="center", fontsize=9)
    ax.set_yscale("log")
    ax.set_ylim(50, 20000)
    ax.set_xticks(x, stages)
    ax.set_ylabel("参数量（对数刻度）", fontsize=11)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10, loc="upper left")
    ratio = res["params"][1] / res["params"][0]
    ax.set_title(f"总参数量 {res['params'][0]} vs {res['params'][1]}，压缩 {ratio:.2f}×",
                 fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-参数量对比.png", dpi=140)
    plt.close(fig)


def make_acc_latency(res: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
    colors = [COLOR["ds"], COLOR["std"], COLOR["torch"]]
    names = ["手写 DS", "手写标准 Conv", "torch DS"]

    ax = axes[0]
    bars = ax.bar(names, res["test_acc"], color=colors, alpha=0.9)
    for b, v in zip(bars, res["test_acc"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.002, f"{v:.4f}", ha="center", fontsize=10)
    ax.set_ylim(0.9, 1.0)
    ax.set_ylabel("测试准确率", fontsize=11)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title(f"测试 acc（{res['n_test']} 张，{res['epochs']} 轮）", fontsize=12)

    ax = axes[1]
    bars = ax.bar(names, res["latency_ms"], color=colors, alpha=0.9)
    for b, v in zip(bars, res["latency_ms"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.4, f"{v:.1f} ms", ha="center", fontsize=10)
    ax.set_ylim(0, max(res["latency_ms"]) * 1.25)
    ax.set_ylabel("单批前向延迟（ms）", fontsize=11)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title(f"前向延迟（batch=128，{D.REPEATS} 次中位数）", fontsize=12)

    fig.suptitle("参数少了 5.4×，准确率只差 0.005；加速并非等比例", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-准确率与延迟.png", dpi=140)
    plt.close(fig)


def make_curves(res: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    colors = [COLOR["ds"], COLOR["std"], COLOR["torch"]]
    names = ["手写 DS", "手写标准 Conv", "torch DS"]
    for name, color, loss in zip(names, colors, res["loss"]):
        axes[0].plot(loss, color=color, lw=1.8, label=name)
    axes[0].set_yscale("log")
    axes[0].set_xlabel("epoch")
    axes[0].set_ylabel("训练损失（对数）")
    axes[0].grid(True, color=COLOR["grid"], lw=0.6)
    axes[0].set_axisbelow(True)
    axes[0].legend(fontsize=9)
    axes[0].set_title("训练损失", fontsize=12)

    for name, color, acc in zip(names, colors, res["train_acc_hist"]):
        axes[1].plot(acc, color=color, lw=1.8, label=name)
    axes[1].set_xlabel("epoch")
    axes[1].set_ylabel("训练准确率")
    axes[1].set_ylim(0.8, 1.005)
    axes[1].grid(True, color=COLOR["grid"], lw=0.6)
    axes[1].set_axisbelow(True)
    axes[1].legend(fontsize=9, loc="lower right")
    axes[1].set_title("训练准确率", fontsize=12)

    fig.suptitle(f"三个模型都收敛（{res['epochs']} 轮，同数据同超参）", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "03-训练曲线.png", dpi=140)
    plt.close(fig)


def make_training_gif(res: dict) -> None:
    """训练过程 GIF：损失/准确率曲线随时间逐步展开。"""
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2))
    colors = [COLOR["ds"], COLOR["std"], COLOR["torch"]]
    names = ["手写 DS", "手写标准 Conv", "torch DS"]
    epochs = np.arange(1, res["epochs"] + 1)
    loss_top = max(max(loss) for loss in res["loss"]) * 1.2

    def draw(i: int) -> None:
        for ax in axes:
            ax.clear()
        for name, color, loss in zip(names, colors, res["loss"]):
            axes[0].plot(epochs[:i], loss[:i], color=color, lw=1.8, label=name)
        axes[0].set_yscale("log")
        axes[0].set_xlim(1, res["epochs"])
        axes[0].set_ylim(0.01, loss_top)
        axes[0].set_xlabel("epoch")
        axes[0].set_ylabel("训练损失（对数）")
        axes[0].grid(True, color=COLOR["grid"], lw=0.6)
        axes[0].set_axisbelow(True)
        axes[0].legend(fontsize=8, loc="upper right")
        axes[0].set_title("训练损失", fontsize=12)
        for name, color, acc in zip(names, colors, res["train_acc_hist"]):
            axes[1].plot(epochs[:i], acc[:i], color=color, lw=1.8, label=name)
        axes[1].set_xlim(1, res["epochs"])
        axes[1].set_ylim(0.8, 1.005)
        axes[1].set_xlabel("epoch")
        axes[1].set_ylabel("训练准确率")
        axes[1].grid(True, color=COLOR["grid"], lw=0.6)
        axes[1].set_axisbelow(True)
        axes[1].legend(fontsize=8, loc="lower right")
        axes[1].set_title("训练准确率", fontsize=12)
        fig.suptitle(f"训练过程：第 {i}/{res['epochs']} 轮（同数据同超参）", fontsize=13)
        fig.tight_layout()

    anim = animation.FuncAnimation(fig, draw, frames=range(2, res["epochs"] + 1), interval=120)
    anim.save(IMAGES / "04-训练过程.gif", writer=animation.PillowWriter(fps=6))
    plt.close(fig)


def main() -> None:
    print("训练三个模型并复用 demo 的结果……")
    res = D.run_experiments()
    verify(res)
    make_concept()
    make_params(res)
    make_acc_latency(res)
    make_curves(res)
    make_training_gif(res)
    for p in sorted(list(IMAGES.glob("*.png")) + list(IMAGES.glob("*.gif"))):
        print(f"  ✓ {p.relative_to(HERE)}  {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
