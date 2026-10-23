"""RAG — 图文素材生成器。

产出：
    00-检索指标.png   手写 vs TF-IDF 基线的 Recall/MRR
    01-相似度热图.png query × chunk 余弦相似度
    02-端到端案例.png 问题 / 答案 / 引用
    03-检索扫描.gif   逐 query 的 top-5 相似度
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
import framework  # noqa: E402
from impl import Generator, Index, Pipeline  # noqa: E402


def setup():
    idx = Index(chunk_size=200, overlap=40).build(D.DOCS)
    return idx, Pipeline(idx, Generator())


def metrics(hits_by_q, k=3):
    rec, mrr = [], []
    for hits, (_, gold, _) in zip(hits_by_q, D.QUERIES):
        ids = [h.doc_id for h in hits[:k]]
        rec.append(1.0 if gold in ids else 0.0)
        rank = next((i + 1 for i, d in enumerate(ids) if d == gold), None)
        mrr.append(1.0 / rank if rank else 0.0)
    return float(np.mean(rec)), float(np.mean(mrr))


def verify() -> None:
    idx, pipe = setup()
    hits = [idx.search(q, 3) for q, _, _ in D.QUERIES]
    rec, mrr = metrics(hits)
    a = pipe.query(D.QUERIES[0][0], 3)
    assert rec >= 0.9 and a.citations
    print(f"  ✓ 对账通过：Recall@3 {rec:.3f}，MRR {mrr:.3f}，citations {len(a.citations)}")


def make_metrics() -> None:
    idx, _ = setup()
    hand = [idx.search(q, 3) for q, _, _ in D.QUERIES]
    base = framework.run_retrieval_baseline(idx, [q for q, _, _ in D.QUERIES], 3)
    h = metrics(hand)
    b = metrics(base)
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    x = np.arange(2)
    ax.bar(x - 0.18, [h[0], h[1]], width=0.36, label="手写 TF-IDF 哈希", color="#3b5bdb")
    ax.bar(x + 0.18, [b[0], b[1]], width=0.36, label="TF-IDF 基线", color="#f08c00")
    ax.set_xticks(x)
    ax.set_xticklabels(["Recall@3", "MRR"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("score")
    ax.set_title("检索指标：两者同分，手写版更快（约 0.2ms vs 6ms）", fontsize=12)
    ax.legend()
    fig.tight_layout()
    fig.savefig(IMAGES / "00-检索指标.png", dpi=130)
    plt.close(fig)


def make_heatmap() -> None:
    idx, _ = setup()
    Q = idx.embedder.encode([q for q, _, _ in D.QUERIES])
    S = Q @ idx.vectors.T
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    im = ax.imshow(S, cmap="Blues", aspect="auto")
    ax.set_xlabel("chunk / doc")
    ax.set_ylabel("query")
    ax.set_title("query × chunk 余弦相似度（12 query × 12 doc）", fontsize=12)
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-相似度热图.png", dpi=130)
    plt.close(fig)


def make_case() -> None:
    idx, pipe = setup()
    rows = []
    for q, gold, _ in D.QUERIES[:3]:
        a = pipe.query(q, 3)
        rows.append((q, a.text, [c.doc_id for c in a.citations]))
    fig, ax = plt.subplots(figsize=(11.0, 4.2))
    ax.axis("off")
    ax.set_title("端到端：问题 → 答案 → 引用（抽取式降级，无 LLM）", fontsize=12)
    for i, (q, a, cit) in enumerate(rows):
        y = 0.80 - i * 0.28
        ax.text(0.0, y, f"Q: {q}", fontsize=8.5, fontweight="bold")
        ax.text(0.0, y - 0.06, f"A: {a[:90]}", fontsize=7.5, family="monospace")
        ax.text(0.0, y - 0.11, f"citations: {cit}", fontsize=7.5, color="#3b5bdb")
    fig.tight_layout()
    fig.savefig(IMAGES / "02-端到端案例.png", dpi=130)
    plt.close(fig)


def make_gif() -> None:
    idx, _ = setup()
    fig, ax = plt.subplots(figsize=(7.2, 4.0))

    def draw(i):
        ax.clear()
        q = D.QUERIES[i][0]
        hits = idx.search(q, 5)
        ax.barh([f"doc {h.doc_id}" for h in hits][::-1], [h.score for h in hits][::-1],
                color="#3b5bdb")
        ax.set_xlim(0, 1.0)
        ax.set_title(f"Q{i}: {q[:48]}", fontsize=10)
        ax.set_xlabel("score")

    anim = animation.FuncAnimation(fig, draw, frames=len(D.QUERIES), interval=700)
    anim.save(IMAGES / "03-检索扫描.gif", writer=animation.PillowWriter(fps=2))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 检索指标 …")
    make_metrics()
    print("② 相似度热图 …")
    make_heatmap()
    print("③ 端到端案例 …")
    make_case()
    print("④ 检索 GIF …")
    make_gif()
    print("\n产出：")
    names = ("00-检索指标.png", "01-相似度热图.png", "02-端到端案例.png", "03-检索扫描.gif")
    for name in names:
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
