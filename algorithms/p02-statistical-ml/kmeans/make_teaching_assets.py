"""K-Means — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-聚类与质心.png   3 团数据 + 簇心
    01-肘部与轮廓.png   inertia / 轮廓系数随 K 的变化
    02-初始化敏感性.png 随机初始化 vs K-Means++ 的 inertia 分布
    03-Lloyd迭代.gif    分派 → 更新簇心的逐轮动画
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
from sklearn.metrics import adjusted_rand_score

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

COLOR = dict(c0="#3b5bdb", c1="#c92a2a", c2="#2b8a3e", c3="#e8590c",
             grid="#dee2e6", hl="#f6c344", text="#343a40")
PALETTE = [COLOR["c0"], COLOR["c1"], COLOR["c2"], COLOR["c3"], "#7048e8", "#0b7285"]


def verify() -> None:
    X, _ = D.make_data()
    hand = impl.KMeans(n_clusters=3, n_init=10, random_state=0).fit(X)
    sk = framework.fit_kmeans(X, n_clusters=3, random_state=0, n_init=10)
    assert abs(hand.inertia_ - sk.inertia_) < 1.0

    _, y = D.make_moons_data()
    moons = impl.KMeans(n_clusters=2, n_init=10, random_state=0).fit(D.make_moons_data()[0])
    ari = adjusted_rand_score(y, moons.labels_)
    assert ari < 0.8
    print(f"  ✓ 对账通过：inertia {hand.inertia_:.3f}（sklearn 同）；"
          f"双月 ARI {ari:.3f}（K-Means 的局限）")


def make_clusters() -> None:
    X, y = D.make_data()
    model = impl.KMeans(n_clusters=3, n_init=10, random_state=0).fit(X)
    fig, ax = plt.subplots(figsize=(7.8, 6.2))
    for j in range(3):
        ax.scatter(X[model.labels_ == j, 0], X[model.labels_ == j, 1], s=16,
                   color=PALETTE[j], alpha=0.7, label=f"簇 {j}")
    ax.scatter(model.cluster_centers_[:, 0], model.cluster_centers_[:, 1], s=220,
               marker="X", color=COLOR["hl"], edgecolor=COLOR["text"], linewidths=1.5,
               label="簇心", zorder=5)
    ax.set_xlabel("x0")
    ax.set_ylabel("x1")
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9.5)
    ax.set_title(f"K-Means（k=3，inertia={model.inertia_:.1f}）", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-聚类与质心.png", dpi=130)
    plt.close(fig)


def make_k_curve() -> None:
    X, _ = D.make_data()
    ks = list(range(1, 9))
    inertia, sil = [], []
    for k in ks:
        m = impl.KMeans(n_clusters=k, n_init=10, random_state=0).fit(X)
        inertia.append(m.inertia_)
        sil.append(impl.silhouette_score(X, m.labels_) if k > 1 else 0.0)
    fig, ax1 = plt.subplots(figsize=(9.4, 5.4))
    ax1.plot(ks, inertia, "o-", color=COLOR["c0"], lw=2, label="inertia")
    ax1.set_xlabel("K", fontsize=12)
    ax1.set_ylabel("inertia", fontsize=12, color=COLOR["c0"])
    ax1.grid(True, color=COLOR["grid"], lw=0.7)
    ax2 = ax1.twinx()
    ax2.plot(ks, sil, "s--", color=COLOR["c1"], lw=2, label="轮廓系数")
    ax2.set_ylabel("轮廓系数", fontsize=12, color=COLOR["c1"])
    ax1.set_title("肘部看 inertia，峰值看轮廓系数；本数据都指向 k=3", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-肘部与轮廓.png", dpi=130)
    plt.close(fig)


def make_init() -> None:
    X, _ = D.make_data()
    rows, labels = [], []
    for init in ("random", "kmeans++"):
        vals = [impl.KMeans(n_clusters=3, n_init=1, init=init,
                            random_state=s).fit(X).inertia_ for s in range(20)]
        rows.append(vals)
        labels.append(init)
    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    bp = ax.boxplot(rows, tick_labels=labels, patch_artist=True, widths=0.45)
    for patch, color in zip(bp["boxes"], (COLOR["c1"], COLOR["c2"])):
        patch.set_facecolor(color)
        patch.set_alpha(0.45)
    for i, vals in enumerate(rows, 1):
        ax.scatter(np.full(len(vals), i) + np.random.default_rng(0).normal(0, 0.04, len(vals)),
                   vals, s=16, color=COLOR["text"], alpha=0.6)
    ax.set_ylabel("inertia（越小越好）", fontsize=12)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.set_title("20 个种子的 inertia：K-Means++ 的尾部更短", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-初始化敏感性.png", dpi=130)
    plt.close(fig)


def make_animation() -> None:
    X, _ = D.make_data()
    model = impl.KMeans(n_clusters=3, n_init=10, random_state=0).fit(X)
    history = model.history_
    fig, ax = plt.subplots(figsize=(7.6, 6.0))

    def draw(idx: int) -> None:
        ax.clear()
        rec = history[idx]
        for j in range(3):
            ax.scatter(X[rec["labels"] == j, 0], X[rec["labels"] == j, 1], s=14,
                       color=PALETTE[j], alpha=0.7)
        ax.scatter(rec["centers"][:, 0], rec["centers"][:, 1], s=180, marker="X",
                   color=COLOR["hl"], edgecolor=COLOR["text"], linewidths=1.2, zorder=5)
        ax.set_xlabel("x0")
        ax.set_ylabel("x1")
        ax.set_title(f"第 {rec['iter']} 轮：inertia={rec['inertia']:.1f}", fontsize=12)

    anim = animation.FuncAnimation(fig, draw, frames=len(history), interval=700)
    anim.save(IMAGES / "03-Lloyd迭代.gif", writer=animation.PillowWriter(fps=1.4))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画聚类与质心 …")
    make_clusters()
    print("② 画肘部/轮廓 …")
    make_k_curve()
    print("③ 画初始化敏感性 …")
    make_init()
    print("④ 画 Lloyd 迭代 …")
    make_animation()
    print("\n产出：")
    for name in ("00-聚类与质心.png", "01-肘部与轮廓.png", "02-初始化敏感性.png",
                 "03-Lloyd迭代.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
