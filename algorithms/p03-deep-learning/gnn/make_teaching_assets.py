"""GCN — 素材生成器。"""

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


def setup_cjk_font():
    names = ("Noto Sans CJK SC", "Noto Sans CJK JP", "Source Han Sans SC",
             "Hiragino Sans GB", "PingFang SC", "Heiti TC", "STHeiti", "Songti SC",
             "Arial Unicode MS", "Microsoft YaHei", "SimHei")
    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
        if Path(path).exists():
            font_manager.fontManager.addfont(path)
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((n for n in names if n in available), None)
    if chosen is None:
        raise SystemExit("找不到含中文字形的字体")
    font_path = font_manager.findfont(font_manager.FontProperties(family=chosen))
    from matplotlib import ft2font
    if ft2font.FT2Font(font_path).get_char_index(ord("中")) == 0:
        raise SystemExit("字体不含中文字形")
    plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False


setup_cjk_font()

from demo import mlp_fit_predict  # noqa: E402
from impl import GCN, make_sbm  # noqa: E402


def setup():
    A, X, y = make_sbm(30, 0.2, 0.08, 8, seed=0)
    train = np.zeros(len(y), bool)
    for c in (0, 1):
        train[np.where(y == c)[0][:6]] = True
    m = GCN(16, 2, 0.2, 200).fit(A, X, y, train)
    m._X = X
    return A, X, y, train, m


def verify():
    A, X, y, tr, m = setup()
    p = m.predict()
    assert (p[~tr] == y[~tr]).mean() > 0.75
    print(f"  ✓ GCN test acc {(p[~tr] == y[~tr]).mean():.3f}")


def graph():
    A, X, y, tr, _ = setup()
    n = len(y)
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    pos = np.c_[np.cos(ang), np.sin(ang)]
    fig, ax = plt.subplots(figsize=(6.6, 6.2))
    for i in range(n):
        for j in range(i + 1, n):
            if A[i, j]:
                ax.plot([pos[i, 0], pos[j, 0]], [pos[i, 1], pos[j, 1]],
                        color="#adb5bd", lw=0.3, alpha=0.6)
    ax.scatter(pos[:, 0], pos[:, 1], c=y, cmap="coolwarm", s=55)
    ax.scatter(pos[tr, 0], pos[tr, 1], facecolors="none", edgecolors="black", s=130)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("随机块图：颜色=社区，黑圈=训练节点", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-图结构.png", dpi=130)
    plt.close(fig)


def metrics():
    A, X, y, tr, m = setup()
    pg = m.predict()
    pm = mlp_fit_predict(X, y, tr)
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    vals = [(pg[~tr] == y[~tr]).mean(), (pm[~tr] == y[~tr]).mean()]
    ax.bar(["GCN", "MLP（仅特征）"], vals, color=["#3b5bdb", "#f08c00"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("test acc")
    ax.set_title("图结构带来的提升", fontsize=12)
    for i, v in enumerate(vals):
        ax.text(i, v + .02, f"{v:.3f}", ha="center")
    fig.tight_layout()
    fig.savefig(IMAGES / "01-GCN-vs-MLP.png", dpi=130)
    plt.close(fig)


def loss():
    *_, m = setup()
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.plot(m.loss_history, color="#3b5bdb")
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.set_title("GCN 训练损失", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-损失.png", dpi=130)
    plt.close(fig)


def gif():
    A, X, y, tr, _ = setup()
    fig, ax = plt.subplots(figsize=(5.8, 4.2))

    def draw(ep):
        m = GCN(16, 2, 0.2, ep + 1).fit(A, X, y, tr)
        m._X = X
        p = m.predict()
        ax.clear()
        ax.bar(["GCN test acc"], [(p[~tr] == y[~tr]).mean()], color="#3b5bdb")
        ax.set_ylim(0, 1.05)
        ax.set_title(f"epoch {ep + 1}，acc {(p[~tr] == y[~tr]).mean():.3f}")

    anim = animation.FuncAnimation(fig, draw, frames=20, interval=250)
    anim.save(IMAGES / "03-训练过程.gif", writer=animation.PillowWriter(fps=4))
    plt.close(fig)


def main():
    print("对账 …")
    verify()
    print("① 图 …")
    graph()
    print("② 指标 …")
    metrics()
    print("③ 损失 …")
    loss()
    print("④ GIF …")
    gif()
    for name in ("00-图结构.png", "01-GCN-vs-MLP.png", "02-损失.png", "03-训练过程.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
