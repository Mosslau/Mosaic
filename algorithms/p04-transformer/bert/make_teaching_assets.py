"""BERT / MLM — 图文素材生成器。

产出：
    00-MLM掩码.png     15% mask 的示意
    01-MLM训练.png     MLM loss / masked acc
    02-注意力.png      [CLS] 对其他 token 的注意力
    03-注意力生长.gif  训练中注意力变化
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
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

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
from impl import BertMLM  # noqa: E402


def setup():
    texts, labels = D.build_data()
    tok = D.BertTokenizer(texts)
    tokens = tok.encode(texts, context=16)
    m = BertMLM(len(tok.itos), context=16, d_model=32, n_heads=4, d_ff=64,
                random_state=0)
    return texts, labels, tok, tokens, m


def verify() -> None:
    texts, labels, tok, tokens, m = setup()
    m.train(tokens, epochs=200, lr=1e-3)
    ev = m.evaluate(tokens)
    X = m.encode(tokens)
    Xtr, Xte, ytr, yte = train_test_split(X, labels, test_size=0.3, random_state=0,
                                          stratify=labels)
    probe = LogisticRegression(max_iter=2000).fit(Xtr, ytr).score(Xte, yte)
    assert ev["acc"] > 0.8 and probe > 0.8
    print(f"  ✓ 对账通过：MLM acc {ev['acc']:.3f}，[CLS] probe {probe:.3f}")


def make_mask() -> None:
    texts, _, tok, tokens, m = setup()
    inp, target, mask = m._make_mask(tokens[:1], np.random.default_rng(0))
    chars = [tok.itos[i] for i in inp[0]]
    fig, ax = plt.subplots(figsize=(11.0, 3.0))
    ax.axis("off")
    for j, ch in enumerate(chars):
        color = "#ffd8a8" if mask[0, j] else "#e7f5ff"
        ax.text(j, 0, ch if ch.strip() else "·", ha="center", va="center", fontsize=14,
                bbox=dict(boxstyle="round,pad=0.35", fc=color, ec="#adb5bd"))
    ax.set_xlim(-1, len(chars))
    ax.set_title("15% token 被 mask（橙色）；只对这些位置算 MLM loss", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-MLM掩码.png", dpi=130)
    plt.close(fig)


def make_curves() -> None:
    _, _, _, tokens, m = setup()
    m.train(tokens, epochs=200, lr=1e-3)
    fig, ax1 = plt.subplots(figsize=(7.4, 4.6))
    ax1.plot(m.loss_history, color="#c92a2a", lw=2)
    ax1.set_xlabel("epoch")
    ax1.set_ylabel("MLM loss", color="#c92a2a")
    ax2 = ax1.twinx()
    ax2.plot(m.acc_history, color="#2b8a3e", lw=2)
    ax2.set_ylabel("masked acc", color="#2b8a3e")
    ax1.set_title("MLM：loss 下降、masked acc 上升", fontsize=12)
    ax1.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-MLM训练.png", dpi=130)
    plt.close(fig)


def make_attention() -> None:
    _, _, tok, tokens, m = setup()
    m.train(tokens, epochs=200, lr=1e-3)
    m.encode(tokens[:1])
    W = m.attn.weights[0].mean(0)   # 平均头
    chars = [tok.itos[i] for i in tokens[0]]
    fig, ax = plt.subplots(figsize=(8.0, 6.4))
    im = ax.imshow(W, cmap="Blues")
    ax.set_xticks(range(len(chars)))
    ax.set_xticklabels(chars, fontsize=8)
    ax.set_yticks(range(len(chars)))
    ax.set_yticklabels(chars, fontsize=8)
    ax.set_title("BERT 双向注意力（平均头）：[CLS] 可看全句", fontsize=12)
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-注意力.png", dpi=130)
    plt.close(fig)


def make_gif() -> None:
    _, _, tok, tokens, m = setup()
    weights, frames = [], []
    for k in range(10):
        m.train(tokens, epochs=20, lr=1e-3)
        m.encode(tokens[:1])
        weights.append(m.attn.weights[0].mean(0))
        frames.append(20 * (k + 1))
    fig, ax = plt.subplots(figsize=(5.8, 4.8))

    def draw(i):
        ax.clear()
        ax.imshow(weights[i], cmap="Blues", vmin=0, vmax=1)
        ax.set_title(f"epoch {frames[i]} 的平均注意力", fontsize=11)

    anim = animation.FuncAnimation(fig, draw, frames=len(weights), interval=400)
    anim.save(IMAGES / "03-注意力生长.gif", writer=animation.PillowWriter(fps=3))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画 MLM 掩码 …")
    make_mask()
    print("② 画训练曲线 …")
    make_curves()
    print("③ 画注意力 …")
    make_attention()
    print("④ 画注意力 GIF …")
    make_gif()
    print("\n产出：")
    for name in ("00-MLM掩码.png", "01-MLM训练.png", "02-注意力.png", "03-注意力生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
