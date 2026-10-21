"""PCA — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-主成分方向.png  二维相关数据的 PC1/PC2 与投影
    01-方差解释.png    digits 的碎石图 + 累计方差
    02-重建对比.png    原图与 k=1/5/20/50 的重建
    03-重建动画.gif    随主成分数增加的重建过程
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
from sklearn.datasets import load_digits

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

COLOR = dict(pc1="#c92a2a", pc2="#2b8a3e", pts="#3b5bdb", grid="#dee2e6",
             hl="#f6c344", text="#343a40")


def verify() -> None:
    X = D.make_correlated()
    hand = impl.PCA(n_components=2).fit(X)
    sk = framework.fit_pca(X, n_components=2)
    assert np.allclose(hand.explained_variance_ratio_, sk.explained_variance_ratio_, atol=1e-10)
    assert abs(float(np.dot(hand.components_[0], sk.components_[0]))) > 0.999

    Xd, _ = load_digits(return_X_y=True)
    pca = impl.PCA().fit(Xd)
    cum = np.cumsum(pca.explained_variance_ratio_)
    k90 = int(np.searchsorted(cum, 0.9) + 1)
    assert k90 == 21, "digits 90% 方差应为 21 个主成分"
    print(f"  ✓ 对账通过：2D 方差占比与 sklearn 一致；digits 90% 方差需 {k90} 个主成分")


def make_directions() -> None:
    X = D.make_correlated()
    pca = impl.PCA(n_components=2).fit(X)
    fig, ax = plt.subplots(figsize=(7.8, 6.2))
    ax.scatter(X[:, 0], X[:, 1], s=12, color=COLOR["pts"], alpha=0.45)
    for j, color in ((0, COLOR["pc1"]), (1, COLOR["pc2"])):
        vec = pca.components_[j] * np.sqrt(pca.explained_variance_[j])
        ax.annotate("", xy=vec * 2.2, xytext=(0, 0),
                    arrowprops=dict(arrowstyle="->", color=color, lw=2.6))
        ax.text(*(vec * 2.35), f"PC{j + 1}", color=color, fontsize=12, ha="center")
    ax.set_xlabel("x0")
    ax.set_ylabel("x1")
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.set_title(f"PC1 解释 {pca.explained_variance_ratio_[0]:.1%}，"
                 f"PC2 解释 {pca.explained_variance_ratio_[1]:.1%}", fontsize=13)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(IMAGES / "00-主成分方向.png", dpi=130)
    plt.close(fig)


def make_variance() -> None:
    X, _ = load_digits(return_X_y=True)
    pca = impl.PCA().fit(X)
    ratio = pca.explained_variance_ratio_
    cum = np.cumsum(ratio)
    k90 = int(np.searchsorted(cum, 0.90) + 1)
    k95 = int(np.searchsorted(cum, 0.95) + 1)

    fig, ax1 = plt.subplots(figsize=(9.6, 5.4))
    ax1.bar(np.arange(1, 21), ratio[:20], color=COLOR["pts"], alpha=0.8, label="单个主成分占比")
    ax1.set_xlabel("主成分序号", fontsize=12)
    ax1.set_ylabel("解释方差占比", fontsize=12)
    ax1.grid(True, axis="y", color=COLOR["grid"], lw=0.6)
    ax1.set_axisbelow(True)
    ax2 = ax1.twinx()
    ax2.plot(np.arange(1, 65), cum, color=COLOR["pc1"], lw=2, label="累计占比")
    for k, label in ((k90, "90%"), (k95, "95%")):
        ax2.axvline(k, color=COLOR["hl"], lw=1.8, ls=":")
        ax2.text(k + 0.4, 0.5, f"{label}\nk={k}", color=COLOR["text"], fontsize=9)
    ax2.set_ylabel("累计解释方差", fontsize=12, color=COLOR["pc1"])
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="center right")
    ax1.set_title("碎石图：前几个主成分贡献大，之后迅速变平", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-方差解释.png", dpi=130)
    plt.close(fig)


def _recon(X, k):
    pca = impl.PCA(n_components=k).fit(X)
    return pca.inverse_transform(pca.transform(X))


def make_reconstruction() -> None:
    X, _ = load_digits(return_X_y=True)
    ks = [1, 5, 20, 50]
    fig, axes = plt.subplots(1, len(ks) + 1, figsize=(13.2, 3.0))
    axes[0].imshow(X[0].reshape(8, 8), cmap="gray_r")
    axes[0].set_title("原图", fontsize=11)
    axes[0].axis("off")
    for ax, k in zip(axes[1:], ks):
        ax.imshow(_recon(X, k)[0].reshape(8, 8), cmap="gray_r")
        ax.set_title(f"k={k}", fontsize=11)
        ax.axis("off")
    fig.suptitle("主成分越多，重建越接近原图", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-重建对比.png", dpi=130)
    plt.close(fig)


def make_animation() -> None:
    X, _ = load_digits(return_X_y=True)
    frames = [1, 2, 3, 5, 8, 12, 20, 30, 45, 64]
    fig, ax = plt.subplots(figsize=(5.2, 5.4))

    def draw(k: int) -> None:
        ax.clear()
        ax.imshow(_recon(X, k)[0].reshape(8, 8), cmap="gray_r")
        ax.set_title(f"k = {k}", fontsize=12)
        ax.axis("off")

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=800)
    anim.save(IMAGES / "03-重建动画.gif", writer=animation.PillowWriter(fps=1.3))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画主成分方向 …")
    make_directions()
    print("② 画方差解释 …")
    make_variance()
    print("③ 画重建对比 …")
    make_reconstruction()
    print("④ 画重建动画 …")
    make_animation()
    print("\n产出：")
    for name in ("00-主成分方向.png", "01-方差解释.png", "02-重建对比.png", "03-重建动画.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
