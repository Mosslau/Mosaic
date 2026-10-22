"""MLP 与手写反向传播 — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-手写vs torch.png  同配置的损失曲线
    01-初始化.png         zero / random / He / Xavier 的测试准确率
    02-正则化.png         无正则 / dropout / weight decay 的训练/测试 acc
    03-边界生长.gif       二维 moons 上 MLP 决策边界的训练过程
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
from sklearn.datasets import make_moons

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

COLOR = dict(train="#3b5bdb", test="#c92a2a", line="#2b8a3e", alt="#f08c00",
             grid="#dee2e6", hl="#f6c344", text="#343a40")


def verify() -> None:
    X_tr, X_te, y_tr, y_te = D.load_data()
    hand = D._fit_hand(X_tr, y_tr)
    torch_model = framework.fit_torch_mlp(X_tr, y_tr, hidden_sizes=(64, 32), lr=0.01,
                                          epochs=30, batch_size=32, optimizer="adam",
                                          init="he", random_state=0)
    a = D.acc(y_te, hand.predict(X_te))
    b = D.acc(y_te, torch_model.predict(X_te))
    assert a > 0.95 and b > 0.95
    zero = D._fit_hand(X_tr, y_tr, init="zero", epochs=20)
    assert D.acc(y_te, zero.predict(X_te)) < 0.2
    z = D.acc(y_te, zero.predict(X_te))
    print(f"  ✓ 对账通过：手写 {a:.4f} / torch {b:.4f}；zero-init {z:.4f}")


def make_losses() -> None:
    X_tr, X_te, y_tr, y_te = D.load_data()
    hand = D._fit_hand(X_tr, y_tr)
    torch_model = framework.fit_torch_mlp(X_tr, y_tr, hidden_sizes=(64, 32), lr=0.01,
                                          epochs=30, batch_size=32, optimizer="adam",
                                          init="he", random_state=0)
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    ax.plot(hand.loss_history, color=COLOR["train"], lw=2, label="手写")
    ax.plot(torch_model.loss_history, color=COLOR["test"], lw=2, ls="--", label="torch")
    ax.set_yscale("log")
    ax.set_xlabel("epoch", fontsize=12)
    ax.set_ylabel("训练损失（对数）", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("手写 vs torch：同配置下损失曲线量级一致", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-手写vs-torch.png", dpi=130)
    plt.close(fig)


def make_init() -> None:
    X_tr, X_te, y_tr, y_te = D.load_data()
    names = ["zero", "random", "he", "xavier"]
    accs = []
    for name in names:
        m = D._fit_hand(X_tr, y_tr, init=name, epochs=20)
        accs.append(D.acc(y_te, m.predict(X_te)))
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    colors = [COLOR["test"] if name == "zero" else COLOR["train"] for name in names]
    ax.bar(names, accs, color=colors, alpha=0.85)
    for i, v in enumerate(accs):
        ax.text(i, v + 0.01, f"{v:.3f}", ha="center", fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("测试准确率", fontsize=12)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title("初始化：全零学不动，He/Xavier 正常", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-初始化.png", dpi=130)
    plt.close(fig)


def make_regularization() -> None:
    X_tr, X_te, y_tr, y_te = D.load_data()
    names = ["无正则", "dropout=0.3", "weight_decay=1e-3"]
    configs = [{}, {"dropout": 0.3}, {"weight_decay": 1e-3}]
    train, test = [], []
    for kw in configs:
        m = D._fit_hand(X_tr, y_tr, **kw)
        train.append(D.acc(y_tr, m.predict(X_tr)))
        test.append(D.acc(y_te, m.predict(X_te)))
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    ax.bar(x - 0.18, train, 0.36, color=COLOR["train"], label="训练")
    ax.bar(x + 0.18, test, 0.36, color=COLOR["test"], label="测试")
    ax.set_xticks(x, names, fontsize=9)
    ax.set_ylim(0.9, 1.02)
    ax.set_ylabel("准确率", fontsize=12)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9)
    ax.set_title("正则不是“加上就更好”：本数据上测试 acc 反而略降", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-正则化.png", dpi=130)
    plt.close(fig)


def _proba(params, X):
    A = X
    for p in params[:-1]:
        A = impl.relu(A @ p["W"] + p["b"])
    z = A @ params[-1]["W"] + params[-1]["b"]
    return impl.softmax(z)


def make_animation() -> None:
    X, y = make_moons(n_samples=300, noise=0.2, random_state=0)
    model = impl.MLP(hidden_sizes=(16, 16), lr=0.05, epochs=60, batch_size=32,
                     optimizer="adam", init="he", random_state=0).fit(X, y)
    xx, yy = np.meshgrid(np.linspace(X[:, 0].min() - 0.5, X[:, 0].max() + 0.5, 160),
                         np.linspace(X[:, 1].min() - 0.5, X[:, 1].max() + 0.5, 160))
    grid = np.c_[xx.ravel(), yy.ravel()]
    fig, ax = plt.subplots(figsize=(7.2, 6.0))
    frames = list(range(0, len(model.param_history), 3))

    def draw(k: int) -> None:
        ax.clear()
        z = _proba(model.param_history[k], grid)[:, 1].reshape(xx.shape)
        ax.contourf(xx, yy, z, levels=18, cmap="RdBu_r", alpha=0.8)
        ax.scatter(X[y == 0, 0], X[y == 0, 1], s=12, color=COLOR["train"], alpha=0.7)
        ax.scatter(X[y == 1, 0], X[y == 1, 1], s=12, color=COLOR["test"], alpha=0.7)
        ax.set_title(f"MLP 边界：第 {k + 1} 轮", fontsize=12)
        ax.set_xlabel("x0")
        ax.set_ylabel("x1")

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=300)
    anim.save(IMAGES / "03-边界生长.gif", writer=animation.PillowWriter(fps=4))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画手写 vs torch 损失 …")
    make_losses()
    print("② 画初始化 …")
    make_init()
    print("③ 画正则 …")
    make_regularization()
    print("④ 画边界生长 …")
    make_animation()
    print("\n产出：")
    for name in ("00-手写vs-torch.png", "01-初始化.png", "02-正则化.png", "03-边界生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
