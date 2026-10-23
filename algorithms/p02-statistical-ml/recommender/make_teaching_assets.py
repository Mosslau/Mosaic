"""推荐系统 — 素材生成器。"""

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

from impl import ItemCF, MatrixFactorization, Popularity, make_data, recall_ndcg, train_test_mask  # noqa: E402


def setup():
    R = make_data(120, 60, seed=0)
    tr, te = train_test_mask(R, 0.2, 0)
    return R, tr, te, R * tr


def verify() -> None:
    R, tr, te, Rtr = setup()
    m = MatrixFactorization(16, 0.01, 0.05, 30, 0).fit(Rtr)
    rec, ndcg = recall_ndcg(m, R, tr, te, 10)
    assert 0 <= rec <= 1 and m.rmse(te, R) < 2
    print(f"  ✓ 对账通过：MF Recall@10 {rec:.3f}，RMSE {m.rmse(te, R):.3f}")


def make_heatmap() -> None:
    R, _, _, _ = setup()
    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    im = ax.imshow(R, aspect="auto", cmap="YlOrRd")
    ax.set_xlabel("item")
    ax.set_ylabel("user")
    ax.set_title("用户-物品评分矩阵（0=未评分）", fontsize=12)
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-评分矩阵.png", dpi=130)
    plt.close(fig)


def make_metrics() -> None:
    R, tr, te, Rtr = setup()
    rows = []
    for name, m in (("ItemCF", ItemCF(20)), ("MF(16)", MatrixFactorization(16, .01, .05, 30, 0)),
                    ("Popularity", Popularity())):
        m.fit(Rtr)
        rec, ndcg = recall_ndcg(m, R, tr, te, 10)
        rows.append((name, rec, ndcg))
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    x = np.arange(2)
    for i, (name, rec, ndcg) in enumerate(rows):
        ax.bar(x + (i - 1) * 0.22, [rec, ndcg], width=0.22, label=name)
    ax.set_xticks(x)
    ax.set_xticklabels(["Recall@10", "NDCG@10"])
    ax.set_ylim(0, 0.65)
    ax.set_title("推荐指标：MF 最好，流行度最弱", fontsize=12)
    ax.legend()
    fig.tight_layout()
    fig.savefig(IMAGES / "01-指标对比.png", dpi=130)
    plt.close(fig)


def make_example() -> None:
    R, tr, te, Rtr = setup()
    m = MatrixFactorization(16, .01, .05, 30, 0).fit(Rtr)
    recs = m.recommend(0, 8)
    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    ax.axis("off")
    ax.set_title("用户 0：已评分 vs 推荐", fontsize=12)
    seen = np.where(Rtr[0] > 0)[0][:10]
    ax.text(0.02, 0.7, "已评分 item：" + str(seen.tolist()), fontsize=9)
    ax.text(0.02, 0.45, "推荐 item：" + str(recs.tolist()), fontsize=9, color="#3b5bdb")
    ax.text(0.02, 0.2, "MF 推荐分数：" +
            str(np.round([m.predict(0, i) for i in recs], 2).tolist()), fontsize=9)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-推荐示例.png", dpi=130)
    plt.close(fig)


def make_gif() -> None:
    R, tr, _, Rtr = setup()
    m = MatrixFactorization(16, .01, .05, 30, 0)
    losses = []
    for _ in range(15):
        m.fit(Rtr)
        losses.append(m.loss_history[-1])
    fig, ax = plt.subplots(figsize=(6.0, 4.0))

    def draw(i):
        ax.clear()
        ax.plot(losses[:i + 1], "o-", color="#3b5bdb")
        ax.set_ylim(0, max(losses) * 1.1)
        ax.set_xlabel("fit call")
        ax.set_ylabel("train RMSE")
        ax.set_title(f"MF 训练 RMSE 下降（第 {i + 1} 次）")

    anim = animation.FuncAnimation(fig, draw, frames=len(losses), interval=300)
    anim.save(IMAGES / "03-训练下降.gif", writer=animation.PillowWriter(fps=4))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 热图 …")
    make_heatmap()
    print("② 指标 …")
    make_metrics()
    print("③ 示例 …")
    make_example()
    print("④ GIF …")
    make_gif()
    print("\n产出：")
    for name in ("00-评分矩阵.png", "01-指标对比.png", "02-推荐示例.png", "03-训练下降.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
