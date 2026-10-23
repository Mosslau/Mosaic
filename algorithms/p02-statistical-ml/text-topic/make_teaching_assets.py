"""文本主题模型 — 素材生成器。"""

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

from demo import make_docs  # noqa: E402
from impl import NMF, Tfidf  # noqa: E402


def setup():
    docs, labels, names = make_docs()
    tf = Tfidf().fit(docs)
    X = tf.transform(docs)
    m = NMF(3, 300, 0).fit(X)
    return docs, labels, names, tf, X, m


def verify():
    *_, X, m = setup()
    assert m.loss_history[-1] < m.loss_history[0]
    print(f"  ✓ loss {m.loss_history[0]:.3f} → {m.loss_history[-1]:.3f}")


def heat_topics():
    *_, tf, _, m = setup()
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    im = ax.imshow(m.H, aspect="auto", cmap="Blues")
    ax.set_yticks(range(3))
    ax.set_yticklabels([f"topic {k}" for k in range(3)])
    ax.set_xticks(range(len(tf.vocab)))
    ax.set_xticklabels(tf.vocab, rotation=90, fontsize=7)
    ax.set_title("topic × word 权重", fontsize=12)
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-主题词.png", dpi=130)
    plt.close(fig)


def heat_docs():
    *_, X, m = setup()
    W = m.transform(X)
    fig, ax = plt.subplots(figsize=(7.0, 6.0))
    im = ax.imshow(W, aspect="auto", cmap="YlOrRd")
    ax.set_xlabel("topic")
    ax.set_ylabel("doc")
    ax.set_title("doc × topic 权重", fontsize=12)
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-文档主题.png", dpi=130)
    plt.close(fig)


def loss_curve():
    *_, m = setup()
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    ax.plot(m.loss_history, color="#3b5bdb")
    ax.set_xlabel("epoch")
    ax.set_ylabel("||X-WH||")
    ax.set_title("NMF 重构误差", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-重构误差.png", dpi=130)
    plt.close(fig)


def gif_topics():
    docs, _, names, tf, X, _ = setup()
    fig, ax = plt.subplots(figsize=(6.0, 4.0))

    def draw(k):
        ax.clear()
        m = NMF(3, 20 + k * 20, 0).fit(X)
        words = m.top_words(tf.vocab, 5)
        ax.axis("off")
        ax.set_title(f"NMF {20 + k * 20} epochs", fontsize=12)
        for i, ws in enumerate(words):
            ax.text(0.05, 0.8 - i * 0.25, f"topic {i}: " + ", ".join(ws), fontsize=9)

    anim = animation.FuncAnimation(fig, draw, frames=8, interval=400)
    anim.save(IMAGES / "03-主题生长.gif", writer=animation.PillowWriter(fps=2))
    plt.close(fig)


def main():
    print("对账 …")
    verify()
    print("① 主题词 …")
    heat_topics()
    print("② 文档主题 …")
    heat_docs()
    print("③ 误差 …")
    loss_curve()
    print("④ GIF …")
    gif_topics()
    for name in ("00-主题词.png", "01-文档主题.png", "02-重构误差.png", "03-主题生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
