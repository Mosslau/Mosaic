"""注意力机制 — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-注意力与causal.png  权重热图 + causal mask
    01-缩放.png            d_k 对最大权重的影响（不缩放 vs 缩放）
    02-多头.png            两个头的权重热图
    03-权重生长.gif        查询位置变化时，注意力权重怎么移动
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

import impl  # noqa: E402


def verify() -> None:
    rng = np.random.default_rng(0)
    Q = rng.normal(size=(1, 4, 8))
    K = rng.normal(size=(1, 5, 8))
    V = rng.normal(size=(1, 5, 8))
    out, w = impl.ScaledDotProductAttention().forward(Q, K, V)
    import framework
    f_out, f_w = framework.torch_attention(Q, K, V)
    assert np.abs(out - f_out).max() < 1e-6
    assert np.allclose(w.sum(-1), 1.0)
    print("  ✓ 对账通过：手写 vs torch <1e-6；权重行和=1")


def make_heatmap() -> None:
    rng = np.random.default_rng(1)
    Q = rng.normal(size=(1, 6, 8))
    K = rng.normal(size=(1, 8, 8))
    V = rng.normal(size=(1, 8, 8))
    _, w = impl.ScaledDotProductAttention().forward(Q, K, V)
    _, wc = impl.ScaledDotProductAttention(causal=True).forward(Q, K[:1, :6], V[:1, :6])
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.4))
    for ax, M, title in ((axes[0], w[0], "普通注意力"), (axes[1], wc[0], "causal mask")):
        im = ax.imshow(M, cmap="Blues", aspect="auto")
        ax.set_title(title, fontsize=12)
        ax.set_xlabel("Key 位置")
        ax.set_ylabel("Query 位置")
        fig.colorbar(im, ax=ax)
    fig.suptitle("注意力权重：每行和为 1；causal 把未来置零", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-注意力与causal.png", dpi=130)
    plt.close(fig)


def make_scaling() -> None:
    ds = [2, 4, 8, 16, 32, 64, 128]
    raw_max, sc_max = [], []
    for dk in ds:
        r, s = [], []
        for seed in range(30):
            rng = np.random.default_rng(seed)
            Q = rng.normal(size=(1, 4, dk))
            K = rng.normal(size=(1, 6, dk))
            scores = Q @ K.swapaxes(-1, -2)
            r.append(float(impl.softmax(scores).max()))
            s.append(float(impl.softmax(scores / np.sqrt(dk)).max()))
        raw_max.append(float(np.mean(r)))
        sc_max.append(float(np.mean(s)))
    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    ax.plot(ds, raw_max, "o-", color="#c92a2a", lw=2, label="不缩放")
    ax.plot(ds, sc_max, "s--", color="#3b5bdb", lw=2, label="除以 √d_k")
    ax.set_xscale("log", base=2)
    ax.set_xlabel("d_k", fontsize=12)
    ax.set_ylabel("平均最大注意力权重", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)
    ax.set_title("不缩放时 d_k 越大、softmax 越尖；缩放把方差拉回 O(1)", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-缩放.png", dpi=130)
    plt.close(fig)


def make_multihead() -> None:
    rng = np.random.default_rng(3)
    X = rng.normal(size=(1, 7, 8))
    mha = impl.MultiHeadAttention(8, 2, random_state=0)
    _, W = mha.forward(X)
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    for h, ax in enumerate(axes):
        im = ax.imshow(W[0, h], cmap="viridis", aspect="auto")
        ax.set_title(f"head {h}", fontsize=12)
        ax.set_xlabel("Key")
        ax.set_ylabel("Query")
        fig.colorbar(im, ax=ax)
    fig.suptitle("同一输入，不同头的注意力模式不同", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-多头.png", dpi=130)
    plt.close(fig)


def make_gif() -> None:
    rng = np.random.default_rng(4)
    Q = rng.normal(size=(1, 10, 8))
    K = rng.normal(size=(1, 10, 8))
    V = rng.normal(size=(1, 10, 8))
    att = impl.ScaledDotProductAttention()
    fig, ax = plt.subplots(figsize=(5.6, 4.8))
    frames = list(range(10))

    def draw(q: int) -> None:
        _, w = att.forward(Q[:, q:q + 1], K, V)
        ax.clear()
        ax.imshow(w[0], cmap="Blues", aspect="auto", vmin=0, vmax=1)
        ax.set_title(f"Query 位置 {q} 的注意力", fontsize=11)
        ax.set_xlabel("Key")
        ax.set_ylabel("权重")

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=350)
    anim.save(IMAGES / "03-权重生长.gif", writer=animation.PillowWriter(fps=3))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画注意力/causal …")
    make_heatmap()
    print("② 画缩放 …")
    make_scaling()
    print("③ 画多头 …")
    make_multihead()
    print("④ 画权重 GIF …")
    make_gif()
    print("\n产出：")
    for name in ("00-注意力与causal.png", "01-缩放.png", "02-多头.png", "03-权重生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
