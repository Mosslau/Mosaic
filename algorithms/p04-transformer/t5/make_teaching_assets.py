"""T5 / encoder-decoder — 图文素材生成器。

产出：
    00-copy-reverse.png  copy/reverse 预测样例
    01-两种mask.png      encoder 双向 vs decoder causal
    02-cross-attention.png  decoder 对 encoder 的 cross-attention
    03-cross生长.gif    训练中 cross-attention 变化
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
from impl import T5Toy  # noqa: E402


def setup():
    return (*D.build_pairs(),)


def train_model(vocab, train, epochs=80):
    m = T5Toy(len(vocab.itos), src_len=5, tgt_len=5, d_model=32, n_heads=4,
              d_ff=64, random_state=0)
    m.train(train, epochs=epochs, lr=3e-3)
    return m


def verify() -> None:
    vocab, train, test = D.build_pairs()
    m = train_model(vocab, train)
    ex = [D.exact(m.generate(p[0], 5, vocab), p[2]) for p in test]
    assert np.mean(ex) > 0.9
    print(f"  ✓ 对账通过：test exact {np.mean(ex):.3f}")


def make_examples() -> None:
    vocab, train, test = D.build_pairs()
    m = train_model(vocab, train)
    rows = []
    for i in (0, 1):
        pred = m.generate(test[i][0], 5, vocab)
        rows.append((vocab.decode(test[i][0]), vocab.decode(test[i][2]), vocab.decode(pred)))
    fig, ax = plt.subplots(figsize=(9.0, 3.2))
    ax.axis("off")
    headers = ["源（含 <copy>/<rev>）", "目标", "预测"]
    for j, h in enumerate(headers):
        ax.text(0.02 + j * 0.33, 0.85, h, fontsize=11, fontweight="bold")
    for i, (src, tgt, pred) in enumerate(rows):
        for j, val in enumerate((src, tgt, pred)):
            ax.text(0.02 + j * 0.33, 0.55 - i * 0.30, repr(val), fontsize=10, family="monospace")
    ax.set_title("T5 toy：copy / reverse（测试样例）", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-copy-reverse.png", dpi=130)
    plt.close(fig)


def make_masks() -> None:
    T = 5
    enc = np.ones((T, T))
    dec = np.tril(np.ones((T, T)))
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.4))
    for ax, M, title in ((axes[0], enc, "encoder：双向"), (axes[1], dec, "decoder：causal")):
        ax.imshow(M, cmap="Blues", vmin=0, vmax=1)
        ax.set_title(title, fontsize=12)
        ax.set_xlabel("Key")
        ax.set_ylabel("Query")
    fig.suptitle("同一个 Block，两种 mask：encoder 看全句，decoder 只看左边", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-两种mask.png", dpi=130)
    plt.close(fig)


def make_cross() -> None:
    vocab, train, test = D.build_pairs()
    m = train_model(vocab, train)
    m.generate(test[0][0], 5, vocab)
    W = m.dec.cross_attn.weights[0].mean(0)
    fig, ax = plt.subplots(figsize=(6.6, 4.8))
    im = ax.imshow(W, cmap="Blues")
    ax.set_title("decoder 对 encoder 的 cross-attention（平均头）", fontsize=12)
    ax.set_xlabel("源 token")
    ax.set_ylabel("目标 token")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-cross-attention.png", dpi=130)
    plt.close(fig)


def make_gif() -> None:
    vocab, train, test = D.build_pairs()
    m = T5Toy(len(vocab.itos), src_len=5, tgt_len=5, d_model=32, n_heads=4,
              d_ff=64, random_state=0)
    weights, frames = [], []
    for k in range(10):
        m.train(train, epochs=8, lr=3e-3)
        m.generate(test[0][0], 5, vocab)
        weights.append(m.dec.cross_attn.weights[0].mean(0))
        frames.append(8 * (k + 1))
    fig, ax = plt.subplots(figsize=(5.8, 4.8))

    def draw(i):
        ax.clear()
        ax.imshow(weights[i], cmap="Blues", vmin=0, vmax=1)
        ax.set_title(f"epoch {frames[i]} 的 cross-attention", fontsize=11)

    anim = animation.FuncAnimation(fig, draw, frames=len(weights), interval=400)
    anim.save(IMAGES / "03-cross生长.gif", writer=animation.PillowWriter(fps=3))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① copy/reverse 样例 …")
    make_examples()
    print("② 两种 mask …")
    make_masks()
    print("③ cross-attention …")
    make_cross()
    print("④ cross-attention GIF …")
    make_gif()
    print("\n产出：")
    names = ("00-copy-reverse.png", "01-两种mask.png",
             "02-cross-attention.png", "03-cross生长.gif")
    for name in names:
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
