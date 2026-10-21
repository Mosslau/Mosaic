"""朴素贝叶斯 — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-高斯NB边界.png   二维 blobs 上的二次决策边界
    01-文本与alpha.png  文本分类准确率随 alpha 的变化
    02-平滑与零概率.png alpha=0 时未见词的 log 概率为 −inf
    03-过度自信.png     重复特征前后最大后验的分布
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
import framework  # noqa: E402
import impl  # noqa: E402

COLOR = dict(pos="#c92a2a", neg="#3b5bdb", line="#2b8a3e", grid="#dee2e6",
             hl="#f6c344", text="#343a40")


def verify() -> None:
    X_tr, X_te, y_tr, y_te = D.make_blobs_data()
    hand = impl.GaussianNB().fit(X_tr, y_tr)
    sk = framework.fit_gaussian(X_tr, y_tr)
    assert abs(D.accuracy(y_te, hand.predict(X_te)) - D.accuracy(y_te, sk.predict(X_te))) < 0.02

    docs, labels = D.make_corpus()
    docs_tr, docs_te, y_tr2, y_te2 = train_test_split(docs, labels, test_size=0.3,
                                                      random_state=0, stratify=labels)
    vec = impl.CountVectorizer().fit(docs_tr)
    nb = impl.MultinomialNB(1.0).fit(vec.transform(docs_tr), y_tr2)
    acc = D.accuracy(y_te2, nb.predict(vec.transform(docs_te)))
    assert acc > 0.9
    print(f"  ✓ 对账通过：高斯 NB 与 sklearn 同；文本测试准确率 {acc:.3f}")


def make_boundary() -> None:
    X_tr, _, y_tr, _ = D.make_blobs_data()
    model = impl.GaussianNB().fit(X_tr, y_tr)
    xx, yy = np.meshgrid(np.linspace(X_tr[:, 0].min() - 1, X_tr[:, 0].max() + 1, 220),
                         np.linspace(X_tr[:, 1].min() - 1, X_tr[:, 1].max() + 1, 220))
    z = model.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)
    fig, ax = plt.subplots(figsize=(7.8, 6.2))
    ax.contourf(xx, yy, z, levels=[-0.5, 0.5, 1.5], colors=["#dbe4ff", "#ffe3e3"], alpha=0.85)
    ax.contour(xx, yy, z, levels=[0.5], colors=[COLOR["line"]], linewidths=2)
    ax.scatter(X_tr[y_tr == 0, 0], X_tr[y_tr == 0, 1], s=14, color=COLOR["neg"],
               alpha=0.7, label="类 0")
    ax.scatter(X_tr[y_tr == 1, 0], X_tr[y_tr == 1, 1], s=14, color=COLOR["pos"],
               alpha=0.7, label="类 1")
    ax.set_xlabel("x0")
    ax.set_ylabel("x1")
    ax.grid(True, color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9)
    ax.set_title("高斯 NB：各类各特征独立高斯 → 二次边界", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-高斯NB边界.png", dpi=130)
    plt.close(fig)


def make_alpha() -> None:
    docs, labels = D.make_corpus()
    docs_tr, docs_te, y_tr, y_te = train_test_split(docs, labels, test_size=0.3,
                                                    random_state=0, stratify=labels)
    vec = impl.CountVectorizer().fit(docs_tr)
    X_tr, X_te = vec.transform(docs_tr), vec.transform(docs_te)
    alphas = np.array([0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 50.0])
    train, test = [], []
    for a in alphas:
        nb = impl.MultinomialNB(float(a)).fit(X_tr, y_tr)
        train.append(D.accuracy(y_tr, nb.predict(X_tr)))
        test.append(D.accuracy(y_te, nb.predict(X_te)))
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    ax.plot(alphas, train, "o-", color=COLOR["neg"], lw=2, label="训练准确率")
    ax.plot(alphas, test, "s--", color=COLOR["pos"], lw=2, label="测试准确率")
    ax.set_xscale("log")
    ax.set_xlabel("alpha（对数轴）", fontsize=12)
    ax.set_ylabel("准确率", fontsize=12)
    ax.set_ylim(0.9, 1.01)
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("alpha 太小/太大都可能伤准确率；本数据在 0.01–10 很平", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-文本与alpha.png", dpi=130)
    plt.close(fig)


def make_smoothing() -> None:
    docs = ["good good", "good", "bad bad", "bad", "good"]
    labels = np.array(["A", "A", "B", "B", "A"])
    vec = impl.CountVectorizer().fit(docs)
    X = vec.transform(docs)
    j = vec.vocabulary_["bad"]
    alphas = [0.0, 0.1, 1.0, 10.0]
    vals = []
    for a in alphas:
        nb = impl.MultinomialNB(a).fit(X, labels)
        v = float(nb.feature_log_prob_[0, j])
        vals.append(v if np.isfinite(v) else -8.0)       # 画图时把 −inf 截到 −8
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    ax.bar([str(a) for a in alphas], vals,
           color=[COLOR["pos"] if a == 0 else COLOR["neg"] for a in alphas])
    ax.axhline(0, color=COLOR["text"], lw=0.8)
    ax.set_xlabel("alpha", fontsize=12)
    ax.set_ylabel("log P(bad | A)", fontsize=12)
    ax.text(0, -7.6, "−∞（零概率）", ha="center", fontsize=10, color=COLOR["pos"])
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title("拉普拉斯平滑：给没见过的词一个非零底数", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-平滑与零概率.png", dpi=130)
    plt.close(fig)


def make_confidence() -> None:
    X_tr, X_te, y_tr, y_te = D.make_blobs_data()
    base = impl.GaussianNB().fit(X_tr, y_tr)
    dup = impl.GaussianNB().fit(np.hstack([X_tr] * 3), y_tr)
    c1 = base.predict_proba(X_te).max(axis=1)
    c2 = dup.predict_proba(np.hstack([X_te] * 3)).max(axis=1)
    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    bins = np.linspace(0.5, 1.0, 25)
    ax.hist(c1, bins=bins, alpha=0.6, color=COLOR["neg"], label="原始特征")
    ax.hist(c2, bins=bins, alpha=0.6, color=COLOR["pos"], label="特征复制 3 份")
    ax.set_xlabel("最大后验概率", fontsize=12)
    ax.set_ylabel("测试样本数", fontsize=12)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("重复特征让 NB 把同一证据数多遍：后验更极端", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "03-过度自信.png", dpi=130)
    plt.close(fig)



def make_animation() -> None:
    X_tr, _, y_tr, _ = D.make_blobs_data()
    xx, yy = np.meshgrid(np.linspace(X_tr[:, 0].min() - 1, X_tr[:, 0].max() + 1, 160),
                         np.linspace(X_tr[:, 1].min() - 1, X_tr[:, 1].max() + 1, 160))
    grid = np.c_[xx.ravel(), yy.ravel()]
    frames = [10, 20, 40, 80, 140, len(X_tr)]
    fig, ax = plt.subplots(figsize=(7.2, 6.0))

    def draw(n: int) -> None:
        ax.clear()
        model = impl.GaussianNB().fit(X_tr[:n], y_tr[:n])
        z = model.predict(grid).reshape(xx.shape)
        ax.contourf(xx, yy, z, levels=[-0.5, 0.5, 1.5], colors=["#dbe4ff", "#ffe3e3"], alpha=0.85)
        ax.scatter(X_tr[:n, 0], X_tr[:n, 1], s=10,
                   c=[COLOR["neg"] if v == 0 else COLOR["pos"] for v in y_tr[:n]], alpha=0.7)
        ax.set_title(f"训练样本 n={n}", fontsize=12)
        ax.set_xlabel("x0")
        ax.set_ylabel("x1")

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=800)
    anim.save(IMAGES / "04-高斯NB生长.gif", writer=animation.PillowWriter(fps=1.3))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画高斯 NB 边界 …")
    make_boundary()
    print("② 画 alpha 曲线 …")
    make_alpha()
    print("③ 画平滑与零概率 …")
    make_smoothing()
    print("④ 画过度自信 …")
    make_confidence()
    print("⑤ 画高斯边界生长 …")
    make_animation()
    print("\n产出：")
    for name in ("00-高斯NB边界.png", "01-文本与alpha.png", "02-平滑与零概率.png",
                 "03-过度自信.png", "04-高斯NB生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
