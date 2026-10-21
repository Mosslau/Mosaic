"""Boosting / GBDT — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-逐轮加法.png    1D 数据上第 1/5/20/100 棵树的拟合曲线
    01-学习率与树数.png  不同 lr 下测试 MSE 随树数的变化
    02-早停.png        训练/验证 MSE 随轮数，标出验证最优轮
    03-残差拟合.gif     逐轮预测的动画

运行：cd algorithms/p02-statistical-ml/boosting && uv run python make_teaching_assets.py
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
from sklearn.metrics import mean_squared_error
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

COLOR = dict(fit="#3b5bdb", stage="#e8590c", true="#2b8a3e", val="#c92a2a",
             grid="#dee2e6", hl="#f6c344", text="#343a40")


def verify() -> None:
    X_tr, X_te, y_tr, y_te = D.make_1d()
    hand = impl.GradientBoostingRegressor(n_estimators=100, learning_rate=0.1,
                                          random_state=0).fit(X_tr, y_tr)
    sk = framework.fit_gbr(X_tr, y_tr, n_estimators=100)
    diff = abs(D.mse(y_te, hand.predict(X_te)) - D.mse(y_te, sk.predict(X_te)))
    assert diff < 0.03, "手写与 sklearn 的测试 MSE 不一致"

    X_sub, X_val, y_sub, y_val = train_test_split(X_tr, y_tr, test_size=0.25,
                                                  random_state=0)
    early = impl.GradientBoostingRegressor(n_estimators=300, learning_rate=0.05,
                                           random_state=0).fit(
        X_sub, y_sub, eval_set=(X_val, y_val), early_stopping_rounds=10)
    assert early.best_iteration_ is not None and len(early.trees) < 300
    print(f"  ✓ 对账通过：手写 vs sklearn 测试 MSE 差 {diff:.4f}；"
          f"早停 {early.best_iteration_} 轮（上限 300）")


def make_stages() -> None:
    X_tr, X_te, y_tr, y_te = D.make_1d()
    model = impl.GradientBoostingRegressor(n_estimators=100, learning_rate=0.1,
                                           random_state=0).fit(X_tr, y_tr)
    xs = np.linspace(-3.2, 3.2, 400)[:, None]
    stages = list(model.staged_predict(xs))
    fig, ax = plt.subplots(figsize=(10.2, 5.8))
    ax.scatter(X_tr[:, 0], y_tr, s=12, color=COLOR["true"], alpha=0.55, label="训练数据")
    for k, color in ((1, "#adb5bd"), (5, "#74c0fc"), (20, COLOR["stage"]), (100, COLOR["fit"])):
        ax.plot(xs[:, 0], stages[k], lw=2.2, color=color, label=f"第 {k} 棵树后")
    ax.set_xlabel("x", fontsize=12)
    ax.set_ylabel("y", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("加法模型：每棵树只拟合当前残差，曲线逐轮逼近", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-逐轮加法.png", dpi=130)
    plt.close(fig)


def make_lr_curves() -> None:
    X_tr, X_te, y_tr, y_te = D.make_1d()
    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    for lr in (0.01, 0.05, 0.1, 0.3):
        model = impl.GradientBoostingRegressor(n_estimators=120, learning_rate=lr,
                                               random_state=0).fit(X_tr, y_tr)
        stages = list(model.staged_predict(X_te))
        scores = [mean_squared_error(y_te, p) for p in stages]
        ax.plot(range(len(scores)), scores, lw=1.9, label=f"lr={lr}")
    ax.set_yscale("log")
    ax.set_xlabel("树数（含基线）", fontsize=12)
    ax.set_ylabel("测试 MSE（对数轴）", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("学习率小：下降慢、需要更多树；学习率大：早期快、后期易过冲", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-学习率与树数.png", dpi=130)
    plt.close(fig)


def make_early_stopping() -> None:
    X_tr, _, y_tr, _ = D.make_1d()
    X_sub, X_val, y_sub, y_val = train_test_split(X_tr, y_tr, test_size=0.25,
                                                  random_state=0)
    model = impl.GradientBoostingRegressor(n_estimators=300, learning_rate=0.05,
                                           random_state=0).fit(
        X_sub, y_sub, eval_set=(X_val, y_val), early_stopping_rounds=10)
    it = np.arange(1, len(model.train_score_) + 1)
    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    ax.plot(it, model.train_score_, lw=1.8, color=COLOR["fit"], label="训练 MSE")
    ax.plot(it, model.val_score_, lw=1.8, color=COLOR["val"], label="验证 MSE")
    ax.axvline(model.best_iteration_, color=COLOR["hl"], lw=2, ls=":",
               label=f"验证最优：第 {model.best_iteration_} 轮")
    ax.set_xlabel("轮数", fontsize=12)
    ax.set_ylabel("MSE", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("早停：验证误差回升就停，而不是把 300 棵跑完", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-早停.png", dpi=130)
    plt.close(fig)


def make_animation() -> None:
    X_tr, _, y_tr, _ = D.make_1d()
    model = impl.GradientBoostingRegressor(n_estimators=100, learning_rate=0.1,
                                           random_state=0).fit(X_tr, y_tr)
    xs = np.linspace(-3.2, 3.2, 400)[:, None]
    stages = list(model.staged_predict(xs))
    frames = [1, 2, 5, 10, 20, 50, 100]
    fig, ax = plt.subplots(figsize=(7.8, 6.0))

    def draw(k: int) -> None:
        ax.clear()
        ax.scatter(X_tr[:, 0], y_tr, s=12, color=COLOR["true"], alpha=0.5)
        ax.plot(xs[:, 0], stages[k], color=COLOR["fit"], lw=2.5)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_title(f"第 {k} 棵树后的加法模型", fontsize=12)

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=800)
    anim.save(IMAGES / "03-残差拟合.gif", writer=animation.PillowWriter(fps=1.3))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画逐轮加法 …")
    make_stages()
    print("② 画学习率曲线 …")
    make_lr_curves()
    print("③ 画早停 …")
    make_early_stopping()
    print("④ 画残差拟合动画 …")
    make_animation()
    print("\n产出：")
    for name in ("00-逐轮加法.png", "01-学习率与树数.png", "02-早停.png", "03-残差拟合.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
