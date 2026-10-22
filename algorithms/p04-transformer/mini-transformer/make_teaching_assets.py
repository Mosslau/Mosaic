"""迷你 Transformer Block — 图文素材生成器。

产出：
    00-残差消融.png     有/无残差的训练 loss
    01-LayerNorm.png    LN 前后分布
    02-训练曲线.png     loss / next-token acc
    03-注意力生长.gif   训练中注意力矩阵的变化
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
import impl  # noqa: E402


def train_setup():
    text = D.build_corpus()
    tr_text, te_text = D.split_tokens(text)
    tok = D.CharTokenizer(tr_text)
    tr, te = tok.encode(tr_text), tok.encode(te_text)
    return tr, te, tok, len(tok.itos)


def verify() -> None:
    tr, te, _, V = train_setup()
    b = impl.TransformerBlock(32, 4, 64, vocab_size=V, context=16, random_state=0)
    b.train(tr, epochs=40, lr=3e-3, batch_size=32)
    acc = b.evaluate(te)["acc"]
    assert acc > 0.5
    print(f"  ✓ 对账通过：Block test next-token acc {acc:.3f}")


def make_residual() -> None:
    tr, _, _, V = train_setup()
    with_r = impl.TransformerBlock(32, 4, 64, vocab_size=V, context=16, random_state=0)
    no_r = impl.TransformerBlock(32, 4, 64, vocab_size=V, context=16,
                                 use_residual=False, random_state=0)
    with_r.train(tr, epochs=40, lr=3e-3, batch_size=32)
    no_r.train(tr, epochs=40, lr=3e-3, batch_size=32)
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    ax.plot(with_r.loss_history, color="#3b5bdb", lw=2, label="有残差")
    ax.plot(no_r.loss_history, color="#c92a2a", lw=2, label="无残差")
    ax.set_xlabel("epoch")
    ax.set_ylabel("train loss")
    ax.set_title("残差消融：训练 loss 曲线（单层小配置）", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(IMAGES / "00-残差消融.png", dpi=130)
    plt.close(fig)


def make_ln() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2000, 32)) * 3 + 7
    ln = impl.LayerNorm(32)
    Y = ln.forward(X)
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.2))
    axes[0].hist(X.ravel(), bins=50, color="#868e96")
    axes[0].set_title(f"LN 前：mean={X.mean():.2f}, std={X.std():.2f}", fontsize=11)
    axes[1].hist(Y.ravel(), bins=50, color="#3b5bdb")
    axes[1].set_title(f"LN 后：mean={Y.mean():.2f}, std={Y.std():.2f}", fontsize=11)
    for ax in axes:
        ax.grid(True, alpha=0.3)
    fig.suptitle("LayerNorm 把每个位置的特征拉回 0 均值 / 1 方差", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-LayerNorm.png", dpi=130)
    plt.close(fig)


def make_curves() -> None:
    tr, te, _, V = train_setup()
    b = impl.TransformerBlock(32, 4, 64, vocab_size=V, context=16, random_state=0)
    b.train(tr, epochs=40, lr=3e-3, batch_size=32)
    m = b.evaluate(te)
    fig, ax1 = plt.subplots(figsize=(7.4, 4.6))
    ax1.plot(b.loss_history, color="#c92a2a", lw=2)
    ax1.set_xlabel("epoch")
    ax1.set_ylabel("train loss", color="#c92a2a")
    ax2 = ax1.twinx()
    ax2.plot(b.acc_history, color="#2b8a3e", lw=2)
    ax2.set_ylabel("train next-token acc", color="#2b8a3e")
    ax1.set_title(f"Block next-token 训练：test loss {m['loss']:.3f}, acc {m['acc']:.3f}",
                  fontsize=12)
    ax1.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-训练曲线.png", dpi=130)
    plt.close(fig)


def make_gif() -> None:
    tr, _, _, V = train_setup()
    b = impl.TransformerBlock(32, 4, 64, vocab_size=V, context=16, random_state=0)
    frames, weights = [], []
    for _ in range(8):
        b.train(tr, epochs=5, lr=3e-3, batch_size=32)
        T = 16
        xb = tr[:T][None]
        b.forward(b.E[xb] + b.P[:T])
        weights.append(b.attn.weights[0].mean(0))
        frames.append(5 * (len(frames) + 1))
    fig, ax = plt.subplots(figsize=(5.8, 4.8))

    def draw(k):
        ax.clear()
        ax.imshow(weights[k], cmap="Blues", vmin=0, vmax=1)
        ax.set_title(f"epoch {frames[k]} 的平均注意力", fontsize=11)
        ax.set_xlabel("Key")
        ax.set_ylabel("Query")

    anim = animation.FuncAnimation(fig, draw, frames=len(weights), interval=450)
    anim.save(IMAGES / "03-注意力生长.gif", writer=animation.PillowWriter(fps=2))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画残差消融 …")
    make_residual()
    print("② 画 LayerNorm …")
    make_ln()
    print("③ 画训练曲线 …")
    make_curves()
    print("④ 画注意力 GIF …")
    make_gif()
    print("\n产出：")
    for name in ("00-残差消融.png", "01-LayerNorm.png", "02-训练曲线.png", "03-注意力生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
