"""Mini-GPT — 图文素材生成器。

产出：
    00-训练曲线.png   loss / acc
    01-采样策略.png   greedy / temperature / top-k 生成对比
    02-注意力.png     第一层平均注意力
    03-注意力生长.gif 训练中注意力变化
"""

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
from impl import CharTokenizer, MiniGPT  # noqa: E402


def setup():
    text = D.build_corpus()
    tr_text, te_text = D.split_text(text)
    tok = CharTokenizer().fit(tr_text)
    tr, te = tok.encode(tr_text), tok.encode(te_text)
    g = MiniGPT(len(tok.itos), context=16, d_model=32, n_heads=4, n_layers=2,
                d_ff=64, random_state=0)
    return tok, tr, te, g


def verify() -> None:
    tok, tr, te, g = setup()
    g.train(tr, epochs=80, lr=3e-3, batch_size=32)
    acc = g.evaluate(te)["acc"]
    out = g.generate("the cat", tok, n_steps=20, temperature=0.0)
    assert acc > 0.8 and len(out) > len("the cat")
    print(f"  ✓ 对账通过：test acc {acc:.3f}，生成 {out[:30]!r}")


def make_curves() -> None:
    tok, tr, te, g = setup()
    g.train(tr, epochs=80, lr=3e-3, batch_size=32)
    m = g.evaluate(te)
    fig, ax1 = plt.subplots(figsize=(7.4, 4.6))
    ax1.plot(g.loss_history, color="#c92a2a", lw=2)
    ax1.set_xlabel("epoch")
    ax1.set_ylabel("train loss", color="#c92a2a")
    ax2 = ax1.twinx()
    ax2.plot(g.acc_history, color="#2b8a3e", lw=2)
    ax2.set_ylabel("train acc", color="#2b8a3e")
    ax1.set_title(f"Mini-GPT：test loss {m['loss']:.3f}, acc {m['acc']:.3f}", fontsize=12)
    ax1.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-训练曲线.png", dpi=130)
    plt.close(fig)


def make_sampling() -> None:
    tok, tr, te, g = setup()
    g.train(tr, epochs=80, lr=3e-3, batch_size=32)
    rows = [
        ("greedy", g.generate("the cat", tok, 36, temperature=0.0)),
        ("T=0.8", g.generate("the cat", tok, 36, temperature=0.8, seed=1)),
        ("T=1.2", g.generate("the cat", tok, 36, temperature=1.2, seed=1)),
        ("top-k=5, T=0.8", g.generate("the cat", tok, 36, temperature=0.8, top_k=5, seed=1)),
    ]
    fig, ax = plt.subplots(figsize=(11.0, 3.6))
    ax.axis("off")
    ax.set_title("同一 prompt，不同采样策略", fontsize=13, pad=12)
    for i, (name, text) in enumerate(rows):
        ax.text(0.0, 0.85 - i * 0.23, f"{name:14}", fontsize=10, fontweight="bold")
        ax.text(0.20, 0.85 - i * 0.23, repr(text), fontsize=8, family="monospace")
    fig.tight_layout()
    fig.savefig(IMAGES / "01-采样策略.png", dpi=130)
    plt.close(fig)


def make_attention() -> None:
    tok, tr, te, g = setup()
    g.train(tr, epochs=80, lr=3e-3, batch_size=32)
    x = tr[:16][None]
    g.forward(x)
    W = g.blocks[0].attn.weights[0].mean(0)
    chars = [tok.itos[i] for i in x[0]]
    fig, ax = plt.subplots(figsize=(7.6, 6.2))
    im = ax.imshow(W, cmap="Blues")
    ax.set_xticks(range(len(chars)))
    ax.set_xticklabels(chars, fontsize=8)
    ax.set_yticks(range(len(chars)))
    ax.set_yticklabels(chars, fontsize=8)
    ax.set_title("第一层平均注意力：causal，上三角为 0", fontsize=12)
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-注意力.png", dpi=130)
    plt.close(fig)


def make_gif() -> None:
    tok, tr, te, g = setup()
    weights, frames = [], []
    for k in range(10):
        g.train(tr, epochs=8, lr=3e-3, batch_size=32)
        g.forward(tr[:16][None])
        weights.append(g.blocks[0].attn.weights[0].mean(0))
        frames.append(8 * (k + 1))
    fig, ax = plt.subplots(figsize=(5.8, 4.8))

    def draw(i):
        ax.clear()
        ax.imshow(weights[i], cmap="Blues", vmin=0, vmax=1)
        ax.set_title(f"epoch {frames[i]} 的注意力", fontsize=11)

    anim = animation.FuncAnimation(fig, draw, frames=len(weights), interval=400)
    anim.save(IMAGES / "03-注意力生长.gif", writer=animation.PillowWriter(fps=3))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 训练曲线 …")
    make_curves()
    print("② 采样策略 …")
    make_sampling()
    print("③ 注意力 …")
    make_attention()
    print("④ 注意力 GIF …")
    make_gif()
    print("\n产出：")
    for name in ("00-训练曲线.png", "01-采样策略.png", "02-注意力.png", "03-注意力生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
