"""CLIP 式多模态 — 素材生成器。"""

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.animation as animation
import matplotlib.pyplot as plt
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

from impl import CLIP, make_pairs  # noqa: E402


def setup():
    Xi, Xt, y = make_pairs(20, 12, 200, 0)
    m = CLIP(d=16, lr=.2, epochs=300, tau=.2, seed=0).fit(Xi, Xt)
    return Xi, Xt, y, m


def verify():
    Xi, Xt, y, m = setup()
    assert m.retrieval_accuracy(Xi, Xt, y) >= .9
    print(f"  ✓ class acc {m.retrieval_accuracy(Xi, Xt, y):.3f}")


def sim():
    Xi, Xt, _, m = setup()
    S = m.similarity(Xi[:20], Xt[:20])
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    im = ax.imshow(S, cmap="viridis")
    ax.set_title("前 20 对图文相似度（对角线=正样本）", fontsize=11)
    ax.set_xlabel("text")
    ax.set_ylabel("image")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-相似度.png", dpi=130)
    plt.close(fig)


def bars():
    Xi, Xt, y, m = setup()
    vals = [m.retrieval_accuracy(Xi, Xt), m.retrieval_accuracy(Xi, Xt, y)]
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    ax.bar(["identity", "class"], vals, color=["#3b5bdb", "#f08c00"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("accuracy")
    ax.set_title("图文检索", fontsize=12)
    for i, v in enumerate(vals):
        ax.text(i, v + .02, f"{v:.3f}", ha="center")
    fig.tight_layout()
    fig.savefig(IMAGES / "01-检索准确率.png", dpi=130)
    plt.close(fig)


def loss():
    *_, m = setup()
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.plot(m.loss_history, color="#3b5bdb")
    ax.set_xlabel("epoch")
    ax.set_ylabel("contrastive loss")
    ax.set_title("CLIP 对比损失", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-损失.png", dpi=130)
    plt.close(fig)


def gif():
    Xi, Xt, y, _ = setup()
    fig, ax = plt.subplots(figsize=(5.6, 4.0))

    def draw(ep):
        m = CLIP(d=16, lr=.2, epochs=20 + ep * 30, seed=0).fit(Xi, Xt)
        ax.clear()
        ax.bar(["class acc"], [m.retrieval_accuracy(Xi, Xt, y)], color="#3b5bdb")
        ax.set_ylim(0, 1.05)
        ax.set_title(f"{20 + ep * 30} epochs")

    anim = animation.FuncAnimation(fig, draw, frames=8, interval=300)
    anim.save(IMAGES / "03-训练过程.gif", writer=animation.PillowWriter(fps=3))
    plt.close(fig)


def main():
    print("对账 …")
    verify()
    print("① 相似度 …")
    sim()
    print("② 检索 …")
    bars()
    print("③ 损失 …")
    loss()
    print("④ GIF …")
    gif()
    for name in ("00-相似度.png", "01-检索准确率.png", "02-损失.png", "03-训练过程.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
