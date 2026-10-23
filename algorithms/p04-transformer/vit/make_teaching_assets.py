"""ViT-lite — 素材生成器。"""

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

from demo import load  # noqa: E402
from impl import ViT  # noqa: E402


def setup():
    Xtr, Xte, ytr, yte = load()
    m = ViT(d=64, lr=.1, epochs=200, seed=0).fit(Xtr, ytr)
    return Xtr, Xte, ytr, yte, m


def verify():
    Xtr, Xte, ytr, yte, m = setup()
    acc = (m.predict(Xte) == yte).mean()
    assert acc > .75
    print(f"  ✓ test acc {acc:.3f}")


def patches():
    Xtr, _, _, _, _ = setup()
    img = Xtr[0, 0]
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    ax.imshow(img, cmap="gray")
    for i in range(2):
        for j in range(2):
            ax.add_patch(plt.Rectangle((j * 4 - .5, i * 4 - .5), 4, 4,
                                       fill=False, edgecolor="#3b5bdb", lw=2))
    ax.set_title("8×8 → 2×2 个 4×4 patch + cls", fontsize=12)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(IMAGES / "00-patch切分.png", dpi=130)
    plt.close(fig)


def attention():
    Xtr, _, _, _, m = setup()
    m.patches = Xtr[:1].reshape(1, 4, 16)
    m.forward()
    P = m.P[0]
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    im = ax.imshow(P, cmap="Blues")
    ax.set_xticks(range(5))
    ax.set_yticks(range(5))
    ax.set_xticklabels(["cls", "p0", "p1", "p2", "p3"])
    ax.set_yticklabels(["cls", "p0", "p1", "p2", "p3"])
    ax.set_title("单头注意力（cls + 4 patch）", fontsize=12)
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-注意力.png", dpi=130)
    plt.close(fig)


def curves():
    Xtr, Xte, ytr, yte, m = setup()
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.plot(m.loss_history, color="#3b5bdb")
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.set_title(f"ViT 训练损失（test acc {(m.predict(Xte)==yte).mean():.3f}）", fontsize=11)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-损失.png", dpi=130)
    plt.close(fig)


def gif():
    Xtr, Xte, ytr, yte = load()
    fig, ax = plt.subplots(figsize=(5.4, 4.0))

    def draw(ep):
        m = ViT(d=64, lr=.1, epochs=20 + ep * 20, seed=0).fit(Xtr, ytr)
        ax.clear()
        ax.bar(["test acc"], [(m.predict(Xte) == yte).mean()], color="#3b5bdb")
        ax.set_ylim(0, 1.0)
        ax.set_title(f"{20 + ep * 20} epochs")

    anim = animation.FuncAnimation(fig, draw, frames=6, interval=300)
    anim.save(IMAGES / "03-训练过程.gif", writer=animation.PillowWriter(fps=2))
    plt.close(fig)


def main():
    print("对账 …")
    verify()
    print("① patch …")
    patches()
    print("② 注意力 …")
    attention()
    print("③ 损失 …")
    curves()
    print("④ GIF …")
    gif()
    for name in ("00-patch切分.png", "01-注意力.png", "02-损失.png", "03-训练过程.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
