"""正则化与模型选择 — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-正则化路径.png   Ridge / Lasso 的系数随 λ 的变化（收缩 vs 稀疏）
    01-CV曲线.png       5 折 CV 误差 vs λ，标出选中的 λ 与测试误差
    02-偏差方差.png     偏差²、方差、总误差随模型复杂度的变化
    03-路径动画.gif     系数沿正则化路径移动的过程

运行：cd algorithms/p02-statistical-ml/regularization && uv run python make_teaching_assets.py
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

# 注册字体之后再导入 numpy 之外的项目模块
import demo as D  # noqa: E402
import framework  # noqa: E402
import impl  # noqa: E402

COLOR = dict(ridge="#3b5bdb", lasso="#e8590c", cv="#2b8a3e", test="#c92a2a",
             grid="#dee2e6", text="#343a40", hl="#f6c344")


# ---------------------------------------------------------------- 取数

def ridge_path_data():
    X, y = D.make_sparse()
    X_tr, _, y_tr, _ = train_test_split(X, y, test_size=0.3, random_state=D.SEED)
    lams = np.logspace(-3, 2, 40)
    coefs = np.array([impl.Ridge(lam=lam).fit(X_tr, y_tr).coef for lam in lams])
    sk = framework.fit_ridge(X_tr, y_tr, lam=1.0)
    hand = impl.Ridge(lam=1.0).fit(X_tr, y_tr)
    return {"lams": lams, "coefs": coefs, "sk": sk, "hand": hand}


def lasso_path_data():
    X, y = D.make_sparse()
    X_tr, _, y_tr, _ = train_test_split(X, y, test_size=0.3, random_state=D.SEED)
    lams = np.logspace(-2, 0, 30)
    coefs = np.array([impl.Lasso(lam=lam).fit(X_tr, y_tr).coef for lam in lams])
    sk = framework.fit_lasso(X_tr, y_tr, lam=0.1)
    hand = impl.Lasso(lam=0.1).fit(X_tr, y_tr)
    return {"lams": lams, "coefs": coefs, "sk": sk, "hand": hand}


def cv_data():
    X, y = D.make_sparse(n=200, noise=3.0, seed=1)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=D.SEED)
    lams = np.logspace(-3, 1, 25)
    rows = []
    for lam in lams:
        cv, _ = impl.cross_val_mse(lambda lam=lam: impl.Ridge(lam=lam), X_tr, y_tr, k=5, seed=0)
        model = impl.Ridge(lam=lam).fit(X_tr, y_tr)
        rows.append((float(lam), cv, impl.mse(y_te, model.predict(X_te))))
    return rows


def bias_variance_data(repeats: int = 80):
    rng = np.random.default_rng(D.SEED)
    x_test = np.linspace(-3, 3, 200)
    f_test = D.true_f(x_test)
    rows = []
    for degree in range(1, 10):
        preds = np.zeros((repeats, len(x_test)))
        for r in range(repeats):
            x = rng.uniform(-3, 3, 30)
            y = D.true_f(x) + rng.normal(0, 0.4, 30)
            model = impl.Ridge(lam=0.0, standardize=True).fit(D.poly_features(x, degree), y)
            preds[r] = model.predict(D.poly_features(x_test, degree))
        mean_pred = preds.mean(axis=0)
        bias2 = float(np.mean((mean_pred - f_test) ** 2))
        var = float(np.mean(preds.var(axis=0)))
        rows.append({"degree": degree, "bias2": bias2, "var": var, "mse": bias2 + var})
    return rows


# ---------------------------------------------------------------- 对账

def verify(rp, lp, cv, bv) -> None:
    assert np.max(np.abs(rp["hand"].coef - rp["sk"].coef_)) < 1e-8, "Ridge 与 sklearn 不一致"
    assert np.max(np.abs(lp["hand"].coef - lp["sk"].coef_)) < 1e-6, "Lasso 与 sklearn 不一致"
    assert np.all(np.diff(np.linalg.norm(rp["coefs"], axis=1)) <= 1e-9), "Ridge 路径应单调收缩"
    nz = [int(np.sum(np.abs(c) > 1e-8)) for c in lp["coefs"]]
    assert nz[0] >= nz[-1] and nz[-1] <= 3, "Lasso 路径应逐步稀疏"
    best = min(cv, key=lambda r: r[1])
    zero = min(cv, key=lambda r: r[0])
    assert best[0] > 1e-3 and best[2] <= zero[2] * 1.02, "CV 选中的 λ 应有效"
    best_bv = min(bv, key=lambda r: r["mse"])
    assert 1 < best_bv["degree"] < 9, "偏差-方差曲线应有内部最优"
    print(f"  ✓ 对账通过：Ridge/Lasso 与 sklearn 一致；Lasso 非零数 {nz[0]}→{nz[-1]}；"
          f"CV 选中 λ={best[0]:.4f}；偏差-方差最优次数 {best_bv['degree']}")


# ---------------------------------------------------------------- 图 1：正则化路径

def make_paths(rp, lp) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.4))
    for ax, data, color, title in (
        (axes[0], rp, COLOR["ridge"], "Ridge：系数整体收缩，不会变成 0"),
        (axes[1], lp, COLOR["lasso"], "Lasso：系数被压到恰好 0"),
    ):
        for j in range(data["coefs"].shape[1]):
            ax.plot(data["lams"], data["coefs"][:, j], lw=1.8, color=color, alpha=0.55
                    if j >= 3 else 0.95)
        ax.set_xscale("log")
        ax.set_xlabel("λ（对数轴）", fontsize=12)
        ax.set_ylabel("系数", fontsize=12)
        ax.axhline(0, color=COLOR["text"], lw=0.8)
        ax.grid(True, color=COLOR["grid"], lw=0.7)
        ax.set_axisbelow(True)
        ax.set_title(title, fontsize=12.5)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-正则化路径.png", dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- 图 2：CV 曲线

def make_cv(cv) -> None:
    lams = [r[0] for r in cv]
    cvs = [r[1] for r in cv]
    tests = [r[2] for r in cv]
    best = min(cv, key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    ax.plot(lams, cvs, "o-", color=COLOR["cv"], lw=2.0, ms=4, label="5 折 CV 误差")
    ax.plot(lams, tests, "s--", color=COLOR["test"], lw=1.6, ms=3.5, label="测试误差（只作对照）")
    ax.axvline(best[0], color=COLOR["hl"], lw=2.0, ls=":",
               label=f"CV 选中的 λ = {best[0]:.3f}")
    ax.set_xscale("log")
    ax.set_xlabel("λ（对数轴）", fontsize=12)
    ax.set_ylabel("MSE", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("交叉验证在训练集内部选 λ；测试误差只是事后的体检", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-CV曲线.png", dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- 图 3：偏差-方差

def make_bias_variance(bv) -> None:
    d = [r["degree"] for r in bv]
    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    ax.plot(d, [r["bias2"] for r in bv], "o-", color=COLOR["ridge"], lw=2.0, label="偏差²")
    ax.plot(d, [r["var"] for r in bv], "s-", color=COLOR["lasso"], lw=2.0, label="方差")
    ax.plot(d, [r["mse"] for r in bv], "^-", color=COLOR["cv"], lw=2.4,
            label="总误差 = 偏差² + 方差")
    ax.set_yscale("log")
    ax.set_xlabel("多项式次数（模型复杂度）", fontsize=12)
    ax.set_ylabel("误差（对数轴）", fontsize=12)
    ax.grid(True, which="both", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10.5)
    ax.set_title("欠拟合端偏差大，过拟合端方差爆炸——中间才是甜点", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-偏差方差.png", dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- 图 4：动画

def make_animation(rp) -> None:
    coefs = rp["coefs"]
    fig, ax = plt.subplots(figsize=(9.0, 5.4))
    xs = np.arange(coefs.shape[1])

    def draw(k: int) -> None:
        ax.clear()
        ax.bar(xs, coefs[k], color=[COLOR["ridge"] if j < 3 else "#adb5bd"
                                    for j in range(coefs.shape[1])])
        ax.axhline(0, color=COLOR["text"], lw=0.8)
        ax.set_ylim(coefs.min() * 1.1 - 0.1, coefs.max() * 1.1 + 0.1)
        ax.set_xticks(xs)
        ax.set_xticklabels([f"x{j}" for j in xs], fontsize=9)
        ax.set_ylabel("系数", fontsize=11)
        ax.set_title(f"Ridge 路径：λ = {rp['lams'][k]:.4f}", fontsize=12.5)

    anim = animation.FuncAnimation(fig, draw, frames=len(coefs), interval=140)
    anim.save(IMAGES / "03-路径动画.gif", writer=animation.PillowWriter(fps=8))
    plt.close(fig)


def main() -> None:
    print("取数：Ridge / Lasso 路径 …")
    rp, lp = ridge_path_data(), lasso_path_data()
    print("取数：CV 曲线 …")
    cv = cv_data()
    print("取数：偏差-方差 …")
    bv = bias_variance_data()
    print("对账 …")
    verify(rp, lp, cv, bv)

    print("① 画正则化路径 …")
    make_paths(rp, lp)
    print("② 画 CV 曲线 …")
    make_cv(cv)
    print("③ 画偏差-方差 …")
    make_bias_variance(bv)
    print("④ 画路径动画 …")
    make_animation(rp)

    print("\n产出：")
    for name in ("00-正则化路径.png", "01-CV曲线.png", "02-偏差方差.png", "03-路径动画.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
