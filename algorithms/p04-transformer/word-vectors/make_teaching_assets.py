"""词向量 — 教学素材生成器（4 张 PNG + 1 个 GIF）。

原则：图里的每个数字都来自 demo.run() 的同一份结果，并与下方 REFERENCE 对账；
对不上直接报错、不出图。流程图不在这里——主循环用 Mermaid 写在 README 正文。
运行：cd algorithms/p04-transformer/word-vectors && ../../.venv/bin/python make_teaching_assets.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation, font_manager

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
IMAGES = HERE / "images"
IMAGES.mkdir(exist_ok=True)

plt.rcParams["axes.unicode_minus"] = False


def setup_cjk_font() -> str:
    names = ("Noto Sans CJK SC", "Noto Sans CJK JP", "Source Han Sans SC",
             "Hiragino Sans GB", "PingFang SC", "Heiti TC", "STHeiti", "Songti SC",
             "Arial Unicode MS", "Microsoft YaHei", "SimHei")
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((n for n in names if n in available), None)
    if chosen is None:
        raise SystemExit("找不到含中文字形的字体，拒绝生成方块版素材")
    path = font_manager.findfont(font_manager.FontProperties(family=chosen))
    from matplotlib import ft2font
    if ft2font.FT2Font(path).get_char_index(ord("中")) == 0:
        raise SystemExit(f"字体 {chosen} 不含中文字形，拒绝生成方块版素材")
    plt.rcParams["font.family"] = chosen
    return chosen


FONT = setup_cjk_font()

from demo import COUNTRIES, RELATION_SETS, SIDES, run  # noqa: E402
from impl import l2_normalize  # noqa: E402

# 与 demo.py 输出对账的参考值（3 位小数；改超参/语料后必须同步重跑本脚本）
REFERENCE = {
    "corpus": {"sentences": 3916, "tokens": 33262, "vocab": 94},
    "sgns": {16: (0.810, 0.882), 32: (0.833, 0.761), 64: (0.810, 0.611)},
    "ppmi": {16: (0.143, 1.000), 32: (0.190, 1.000), 64: (0.167, 1.000)},
}
TOL = 5e-4


def setup():
    """跑一次 demo.run()，所有图与断言共用这一份结果。"""
    res = run()
    meta = res["corpus"]
    for k, v in REFERENCE["corpus"].items():
        assert meta[k] == v, f"语料 {k} 与 README 参考值不一致：{meta[k]} != {v}"
    for dim in (16, 32, 64):
        for key, ref in (("impl", REFERENCE["sgns"][dim]), ("baseline", REFERENCE["ppmi"][dim])):
            got = (res[key][dim]["analogy_heldout"], res[key][dim]["purity"])
            assert abs(got[0] - ref[0]) < TOL and abs(got[1] - ref[1]) < TOL, (
                f"dim={dim} {key} 的数字与 demo 参考值不一致：{got} != {ref}")
    # 语义断言：关系结构确实被学到，且基线呈塌缩形态
    assert res["impl"][32]["analogy_heldout"] > res["baseline"][32]["analogy_heldout"] + 0.5
    assert res["impl"][32]["analogy_heldout"] > 0.7
    assert res["baseline"][32]["same_side_cos"] > 0.6
    print(f"  ✓ 对账通过：SGNS 32 维 留出类比 {res['impl'][32]['analogy_heldout']:.3f} / "
          f"PPMI-SVD {res['baseline'][32]['analogy_heldout']:.3f}")
    return res


def _pca2(X):
    X = np.asarray(X, float)
    X = X - X.mean(0)
    _, _, vt = np.linalg.svd(X, full_matrices=False)
    return X @ vt[:2].T


def make_space(res):
    """概念图：左 = PCA 投影 + 国家→首都箭头；右 = 各关系的偏移方向一致性。"""
    m = res["models"]["impl"][32]
    X = _pca2(m.vectors)
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.8))
    ax = axes[0]
    colors = {"country-capital": "#3b5bdb", "male-female": "#c92a2a",
              "singular-plural": "#2b8a3e", "present-past": "#e8590c"}
    for name, _ in RELATION_SETS:
        left, right = SIDES[name]
        for words, marker, side in ((left, "o", "左"), (right, "^", "右")):
            pts = X[[m.word2id[w] for w in words]]
            ax.scatter(pts[:, 0], pts[:, 1], s=26, marker=marker, color=colors[name],
                       alpha=.8, label=f"{name} · {side}")
    for C, K in COUNTRIES[:4]:
        i, j = m.word2id[C], m.word2id[K]
        ax.annotate("", xy=X[j], xytext=X[i],
                    arrowprops={"arrowstyle": "->", "color": "#212529", "lw": 1.3, "alpha": .85})
    C0 = COUNTRIES[0][0]
    ax.annotate(C0, X[m.word2id[C0]], fontsize=8, color="#212529",
                xytext=(-38, 6), textcoords="offset points")
    ax.set_aspect("equal")                      # 等比例，箭头方向才不会被拉伸误导
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title("SGNS 32 维：同类词成簇，国家→首都的箭头同向", fontsize=10)
    handles, labels = ax.get_legend_handles_labels()

    ax = axes[1]
    names, vals = [], []
    for name, pairs in RELATION_SETS:
        off = l2_normalize(np.array([m.vectors[m.word2id[b]] - m.vectors[m.word2id[a]]
                                     for a, b in pairs]))
        vals.append(float(np.median((off @ off.T)[np.triu_indices(len(pairs), 1)])))
        names.append(name)
    ax.bar(range(len(names)), vals, color=[colors[n] for n in names], alpha=.85)
    for i, v in enumerate(vals):
        ax.text(i, v + .02, f"{v:.2f}", ha="center", fontsize=9)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=15, fontsize=8)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("同关系偏移向量的两两余弦中位数")
    ax.set_title("偏移方向一致性：越接近 1，关系越像一个固定方向", fontsize=10)
    ax.grid(axis="y", alpha=.25)
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=7, frameon=False)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(IMAGES / "00-关系方向.png", dpi=130)
    plt.close(fig)


def make_loss(res):
    """训练图：逐 epoch 的负采样损失（dim=32）。"""
    loss = res["impl"][32]["loss"]
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    ax.plot(range(1, len(loss) + 1), loss, color="#3b5bdb", lw=1.8)
    ax.set_xlabel("epoch")
    ax.set_ylabel("SGNS 损失（每对样本）")
    ax.set_title(f"训练损失 {loss[0]:.2f} → {loss[-1]:.2f}（dim=32，"
                 f"{res['impl'][32]['pairs']} 个训练对）", fontsize=11)
    ax.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-训练损失.png", dpi=130)
    plt.close(fig)


def make_compare(res):
    """对比图：留出类比准确率 / 最近邻纯度随维度的变化。"""
    dims = [16, 32, 64]
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.0))
    for ax, metric, ylabel in ((axes[0], "analogy_heldout", "留出类比 top-1"),
                               (axes[1], "purity", "最近邻纯度")):
        s = [res["impl"][d][metric] for d in dims]
        b = [res["baseline"][d][metric] for d in dims]
        x = np.arange(len(dims))
        ax.bar(x - .18, s, .36, label="SGNS（手写）", color="#3b5bdb")
        ax.bar(x + .18, b, .36, label="PPMI-SVD（基线）", color="#adb5bd")
        for xi, v in zip(x - .18, s):
            ax.text(xi, v + .02, f"{v:.2f}", ha="center", fontsize=8)
        for xi, v in zip(x + .18, b):
            ax.text(xi, v + .02, f"{v:.2f}", ha="center", fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels([f"dim={d}" for d in dims])
        ax.set_ylim(0, 1.08)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=.25)
        ax.legend(fontsize=8, frameon=False)
    axes[1].set_title("纯度 1.00 = 同角色词几乎同向量（塌缩）", fontsize=9)
    fig.suptitle("同一份语料：SGNS 保住关系结构，PPMI-SVD 塌缩成类别", fontsize=11)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-性能对比.png", dpi=130)
    plt.close(fig)


def make_heatmap(res):
    """对比图：20 个国家/首都词的相似度矩阵——SGNS 有配对亮块，PPMI 配对不更近。"""
    words = [w for pair in COUNTRIES for w in pair]
    pair_set = {(a, b) for a, b in COUNTRIES} | {(b, a) for a, b in COUNTRIES}
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 5.0))
    stats = {}
    for ax, key, title in ((axes[0], "impl", "SGNS 32 维"),
                           (axes[1], "baseline", "PPMI-SVD 32 维")):
        model = res["models"][key][32]
        V = l2_normalize(model.vectors[[model.word2id[w] for w in words]])
        S = V @ V.T
        own = float(np.mean([S[words.index(a), words.index(b)] for a, b in COUNTRIES]))
        other = float(np.mean([S[i, j] for i, wi in enumerate(words) for j, wj in enumerate(words)
                               if i != j and (wi, wj) not in pair_set]))
        im = ax.imshow(S, cmap="RdBu_r", vmin=-.2, vmax=1.0)
        ax.set_xticks(range(len(words)))
        ax.set_yticks(range(len(words)))
        ax.set_xticklabels(words, rotation=90, fontsize=6)
        ax.set_yticklabels(words, fontsize=6)
        stats[key] = (own, other)
        ax.set_title(f"{title}：配对 {own:.2f} / 非配对 {other:.2f}", fontsize=9.5)
    fig.colorbar(im, ax=axes, shrink=.8, label="余弦相似度")
    (s_own, s_oth), (b_own, b_oth) = stats["impl"], stats["baseline"]
    fig.suptitle(f"20 个国家/首都词的两两余弦：SGNS 配对 {s_own:.2f} vs 非配对 {s_oth:.2f}；"
                 f"PPMI 配对 {b_own:.2f} vs 非配对 {b_oth:.2f}（配对反而不更近）", fontsize=9.5)
    fig.savefig(IMAGES / "03-相似度热图.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def make_loss_gif(res) -> None:
    """训练过程：三个维度的 SGNS loss 随 epoch 逐步展开。"""
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    colors = {16: "#2b8a3e", 32: "#3b5bdb", 64: "#c92a2a"}
    n = len(res["impl"][32]["loss"])
    epochs = np.arange(1, n + 1)
    top = max(max(res["impl"][d]["loss"]) for d in (16, 32, 64)) * 1.15

    def draw(i: int) -> None:
        ax.clear()
        for dim in (16, 32, 64):
            ax.plot(epochs[:i], res["impl"][dim]["loss"][:i],
                    color=colors[dim], lw=1.8, label=f"dim={dim}")
        ax.set_xlim(1, n)
        ax.set_ylim(0, top)
        ax.set_xlabel("epoch")
        ax.set_ylabel("SGNS loss")
        ax.grid(True, color="#dee2e6", lw=0.6)
        ax.set_axisbelow(True)
        ax.legend(fontsize=9)
        ax.set_title(f"训练过程：第 {i}/{n} 轮（三个维度同语料）", fontsize=12)
        fig.tight_layout()

    anim = animation.FuncAnimation(fig, draw, frames=range(2, n + 1), interval=120)
    anim.save(IMAGES / "04-训练过程.gif", writer=animation.PillowWriter(fps=6))
    plt.close(fig)


def main() -> None:
    print(f"字体：{FONT}")
    print("对账 …")
    res = setup()
    print("① 关系方向 …")
    make_space(res)
    print("② 训练损失 …")
    make_loss(res)
    print("③ 性能对比 …")
    make_compare(res)
    print("④ 相似度热图 …")
    make_heatmap(res)
    print("⑤ 训练过程 GIF …")
    make_loss_gif(res)
    for name in ("00-关系方向.png", "01-训练损失.png", "02-性能对比.png",
                 "03-相似度热图.png", "04-训练过程.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
