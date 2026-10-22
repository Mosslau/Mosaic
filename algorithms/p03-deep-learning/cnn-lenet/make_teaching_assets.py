"""LeNet — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-手写vs torch.png  同结构手写 / torch 的损失曲线
    01-BN与残差.png      baseline / BN / residual / BN+residual 测试 acc
    02-特征图.png        conv1 的 6 个特征图（同一张数字）
    03-卷积核生长.gif    conv1 的 6 个 3×3 卷积核在训练中的变化
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
IMAGES = HERE / "images"
IMAGES.mkdir(exist_ok=True)


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
import framework  # noqa: E402
import impl  # noqa: E402

COLOR = dict(a="#3b5bdb", b="#c92a2a", c="#2b8a3e", d="#f08c00", grid="#dee2e6")


def verify() -> None:
    X_tr, X_te, y_tr, y_te = D.load_data()
    m = D._fit_hand(X_tr, y_tr, epochs=10)
    assert D.acc(y_te, m.predict(X_te)) > 0.6
    g = np.random.default_rng(0).normal(size=impl.im2col(X_tr[:2], 3, 3, 1, 1).shape)
    lhs = np.sum(impl.im2col(X_tr[:2], 3, 3, 1, 1) * g)
    rhs = np.sum(X_tr[:2] * impl.col2im(g, X_tr[:2].shape, 3, 3, 1, 1))
    assert abs(lhs - rhs) < 1e-8
    a = D.acc(y_te, m.predict(X_te))
    print(f"  ✓ 对账通过：10 轮 acc {a:.3f}；im2col 伴随误差 {abs(lhs-rhs):.1e}")


def make_losses() -> None:
    X_tr, X_te, y_tr, y_te = D.load_data()
    hand = D._fit_hand(X_tr, y_tr)
    torch_model = framework.TorchLeNet(lr=0.003, epochs=100, batch_size=64,
                                       random_state=0).fit(X_tr, y_tr)
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    ax.plot(hand.loss_history, color=COLOR["a"], lw=2, label="手写")
    ax.plot(torch_model.loss_history, color=COLOR["b"], lw=2, ls="--", label="torch")
    ax.set_yscale("log")
    ax.set_xlabel("epoch", fontsize=12)
    ax.set_ylabel("训练损失（对数）", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("手写 vs torch：小 LeNet 的损失曲线", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-手写vs-torch.png", dpi=130)
    plt.close(fig)


def make_bn_residual() -> None:
    X_tr, X_te, y_tr, y_te = D.load_data()
    names = ["baseline", "+BatchNorm", "+Residual", "+BN+Residual"]
    configs = [{}, {"use_bn": True}, {"use_residual": True},
               {"use_bn": True, "use_residual": True}]
    accs = []
    for kw in configs:
        m = D._fit_hand(X_tr, y_tr, **kw)
        accs.append(D.acc(y_te, m.predict(X_te)))
    fig, ax = plt.subplots(figsize=(8.8, 5.0))
    bars = ax.bar(names, accs, color=[COLOR["a"], COLOR["b"], COLOR["c"], COLOR["d"]], alpha=0.85)
    for b, v in zip(bars, accs):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.004, f"{v:.3f}", ha="center", fontsize=10)
    ax.set_ylim(0.85, 0.97)
    ax.set_ylabel("测试准确率", fontsize=12)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title("BatchNorm 稳定训练；BN+残差组合最好", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-BN与残差.png", dpi=130)
    plt.close(fig)


def make_feature_maps() -> None:
    X_tr, _, y_tr, _ = D.load_data()
    m = D._fit_hand(X_tr, y_tr)
    x = X_tr[0:1]
    z = impl.relu(m.conv1.forward(x))[0]
    fig, axes = plt.subplots(1, 6, figsize=(12.0, 2.5))
    for c, ax in enumerate(axes):
        ax.imshow(z[c], cmap="viridis")
        ax.set_title(f"通道 {c}", fontsize=9)
        ax.axis("off")
    fig.suptitle("conv1 的 6 个特征图（同一张 8×8 数字）", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-特征图.png", dpi=130)
    plt.close(fig)


def make_filter_gif() -> None:
    X_tr, _, y_tr, _ = D.load_data()
    m = D._fit_hand(X_tr, y_tr)
    frames = list(range(0, len(m.filter_history), 5))
    fig, axes = plt.subplots(1, 6, figsize=(10.0, 2.2))
    vmax = max(np.abs(w).max() for w in m.filter_history)

    def draw(k: int) -> None:
        for c, ax in enumerate(axes):
            ax.clear()
            ax.imshow(m.filter_history[k][c, 0], cmap="RdBu_r", vmin=-vmax, vmax=vmax)
            ax.set_title(f"核 {c}", fontsize=8)
            ax.axis("off")
        fig.suptitle(f"conv1 卷积核：第 {k + 1} 轮", fontsize=11)

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=250)
    anim.save(IMAGES / "03-卷积核生长.gif", writer=animation.PillowWriter(fps=4))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画损失曲线 …")
    make_losses()
    print("② 画 BN/残差 …")
    make_bn_residual()
    print("③ 画特征图 …")
    make_feature_maps()
    print("④ 画卷积核 GIF …")
    make_filter_gif()
    print("\n产出：")
    for name in ("00-手写vs-torch.png", "01-BN与残差.png", "02-特征图.png", "03-卷积核生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
