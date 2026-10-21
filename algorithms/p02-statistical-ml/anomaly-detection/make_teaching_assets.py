"""异常检测 — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-孤立森林分数.png  分数等高线 + 正常/异常测试点
    01-阈值扫描.png      contamination 与精确率/召回率/F1
    02-三种方法分数.png  正常 vs 异常的分数分布
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from sklearn.metrics import roc_auc_score

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

COLOR = dict(normal="#3b5bdb", anomaly="#c92a2a", line="#2b8a3e",
             grid="#dee2e6", hl="#f6c344", text="#343a40")


def verify() -> None:
    X_tr, X_te, y = D.make_data()
    model = impl.IsolationForest(random_state=0).fit(X_tr)
    s = model.score_samples(X_te)
    assert roc_auc_score(y, s) > 0.95
    sk = framework.fit_iforest(X_tr)
    assert abs(roc_auc_score(y, s) - roc_auc_score(y, -sk.score_samples(X_te))) < 0.05
    print(f"  ✓ 对账通过：手写 AUC {roc_auc_score(y, s):.3f}；与 sklearn 一致")


def make_score_map() -> None:
    X_tr, X_te, y = D.make_data()
    model = impl.IsolationForest(random_state=0).fit(X_tr)
    xx, yy = np.meshgrid(np.linspace(-6, 6, 240), np.linspace(-6, 6, 240))
    z = model.score_samples(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)
    fig, ax = plt.subplots(figsize=(8.2, 6.4))
    cf = ax.contourf(xx, yy, z, levels=18, cmap="viridis", alpha=0.85)
    fig.colorbar(cf, ax=ax, label="异常分数（越高越异常）")
    ax.contour(xx, yy, z, levels=[model.threshold_], colors=[COLOR["hl"]], linewidths=2)
    ax.scatter(X_te[y == 0, 0], X_te[y == 0, 1], s=14, color=COLOR["normal"], label="正常")
    ax.scatter(X_te[y == 1, 0], X_te[y == 1, 1], s=28, color=COLOR["anomaly"],
               marker="x", label="异常")
    ax.set_xlabel("x0")
    ax.set_ylabel("x1")
    ax.legend(fontsize=9.5, loc="upper left")
    ax.set_title("孤立森林：边缘/稀疏处路径短、分数高", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-孤立森林分数.png", dpi=130)
    plt.close(fig)


def make_threshold() -> None:
    X_tr, X_te, y = D.make_data()
    cs = (0.01, 0.02, 0.05, 0.08, 0.12, 0.2)
    ps, rs, fs = [], [], []
    for c in cs:
        m = impl.IsolationForest(contamination=c, random_state=0).fit(X_tr)
        pred = np.where(m.score_samples(X_te) > m.threshold_, 1, 0)
        p, r = D.accuracy_metrics(y, pred)
        ps.append(p)
        rs.append(r)
        fs.append(0.0 if p + r == 0 else 2 * p * r / (p + r))
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    ax.plot(cs, ps, "o-", color=COLOR["normal"], lw=2, label="精确率")
    ax.plot(cs, rs, "s--", color=COLOR["anomaly"], lw=2, label="召回率")
    ax.plot(cs, fs, "^-", color=COLOR["line"], lw=2.2, label="F1")
    ax.set_xscale("log")
    ax.set_xlabel("contamination（对数轴）", fontsize=12)
    ax.set_ylabel("指标", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("阈值越松（contamination 大）：召回满、精确率降", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-阈值扫描.png", dpi=130)
    plt.close(fig)


def make_scores() -> None:
    X_tr, X_te, y = D.make_data()
    models = {
        "IsolationForest": impl.IsolationForest(random_state=0).fit(X_tr),
        "LOF": impl.LOF().fit(X_tr),
        "KDE": impl.KDE().fit(X_tr),
    }
    fig, axes = plt.subplots(1, 3, figsize=(13.4, 4.4))
    for ax, (name, model) in zip(axes, models.items()):
        s = model.score_samples(X_te)
        ax.hist(s[y == 0], bins=20, alpha=0.65, color=COLOR["normal"], label="正常")
        ax.hist(s[y == 1], bins=20, alpha=0.65, color=COLOR["anomaly"], label="异常")
        ax.set_title(f"{name}（AUC {roc_auc_score(y, s):.2f}）", fontsize=11.5)
        ax.set_xlabel("异常分数")
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-三种方法分数.png", dpi=130)
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画孤立森林分数 …")
    make_score_map()
    print("② 画阈值扫描 …")
    make_threshold()
    print("③ 画三种方法分数 …")
    make_scores()
    print("\n产出：")
    for name in ("00-孤立森林分数.png", "01-阈值扫描.png", "02-三种方法分数.png"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
