"""DDPM — 图文素材生成器。

产出：
    00-前向加噪.png   x0 → x_t 的闭式加噪
    01-训练曲线.png   eps MSE
    02-条件生成.png   class-conditional + CFG
    03-去噪生长.gif   从纯噪声逐步去噪
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
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
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

from impl import DDPM  # noqa: E402


def data():
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    return train_test_split(X, y, train_size=1200, random_state=0, stratify=y)


def setup():
    Xtr, Xte, ytr, yte = data()
    d = DDPM(n_steps=100, epochs=100, num_classes=10, hidden=128, random_state=0)
    d.train(Xtr, ytr)
    clf = LogisticRegression(max_iter=5000).fit(Xtr, ytr)
    return d, clf, Xte, yte


def verify() -> None:
    d, clf, _, _ = setup()
    labels = np.tile(np.arange(10), 20)
    s = d.sample(200, labels=labels, guidance=3.0, seed=1)
    acc = float((clf.predict(s) == labels).mean())
    assert acc > 0.8 and s.min() >= 0 and s.max() <= 1
    print(f"  ✓ 对账通过：CFG w=3 class acc {acc:.3f}")


def make_forward() -> None:
    Xtr, Xte, ytr, yte = data()
    d = DDPM(n_steps=100, random_state=0)
    x0 = Xte[0]
    fig, axes = plt.subplots(1, 5, figsize=(10, 2.2))
    for ax, t in zip(axes, (0, 25, 50, 75, 99)):
        eps = np.random.default_rng(0).normal(size=x0.shape)
        xt = d.q_sample(x0[None], np.array([t]), eps[None])[0]
        ax.imshow(xt.reshape(8, 8), cmap="gray", vmin=0, vmax=1)
        ax.set_title(f"t={t}", fontsize=10)
        ax.axis("off")
    fig.suptitle("前向闭式加噪：t 越大越接近纯噪声", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-前向加噪.png", dpi=130)
    plt.close(fig)


def make_curves() -> None:
    d, _, _, _ = setup()
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    ax.plot(d.loss_history, color="#c92a2a", lw=2)
    ax.set_xlabel("epoch")
    ax.set_ylabel("eps MSE")
    ax.set_title(f"DDPM 训练：loss {d.loss_history[0]:.3f} → {d.loss_history[-1]:.3f}",
                 fontsize=12)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-训练曲线.png", dpi=130)
    plt.close(fig)


def make_conditional() -> None:
    d, clf, _, _ = setup()
    labels = np.repeat(np.arange(10), 3)
    s = d.sample(30, labels=labels, guidance=3.0, seed=1).reshape(-1, 8, 8)
    acc = float((clf.predict(s.reshape(30, 64)) == labels).mean())
    fig, axes = plt.subplots(3, 10, figsize=(11, 3.6))
    for ax, img in zip(axes.ravel(), s):
        ax.imshow(img, cmap="gray", vmin=0, vmax=1)
        ax.axis("off")
    for j in range(10):
        axes[0, j].set_title(str(j), fontsize=9)
    fig.suptitle(f"class-conditional + CFG(w=3)：class acc {acc:.2f}", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-条件生成.png", dpi=130)
    plt.close(fig)


def make_gif() -> None:
    d, _, _, _ = setup()
    labels = np.array([3])
    rng = np.random.default_rng(1)
    x = rng.normal(size=(1, 64))
    frames = []
    for t in reversed(range(d.n_steps)):
        eps = d.predict_noise(x, np.array([t]), labels, guidance=3.0)
        ab = d.alphas_bar[t]
        x0 = np.clip((x - np.sqrt(1 - ab) * eps) / np.sqrt(ab), 0, 1)
        if t > 0:
            abp = d.alphas_bar[t - 1]
            mean = (np.sqrt(abp) * d.betas[t] / (1 - ab) * x0
                    + np.sqrt(d.alphas[t]) * (1 - abp) / (1 - ab) * x)
            var = d.betas[t] * (1 - abp) / (1 - ab)
            x = mean + np.sqrt(var) * rng.normal(size=x.shape)
        else:
            x = x0
        if t % 10 == 0 or t == 0:
            frames.append((t, x[0].reshape(8, 8).copy()))
    fig, ax = plt.subplots(figsize=(4.6, 4.6))

    def draw(i):
        ax.clear()
        ax.imshow(frames[i][1], cmap="gray", vmin=0, vmax=1)
        ax.set_title(f"去噪 t={frames[i][0]}", fontsize=11)
        ax.axis("off")

    anim = animation.FuncAnimation(fig, draw, frames=len(frames), interval=350)
    anim.save(IMAGES / "03-去噪生长.gif", writer=animation.PillowWriter(fps=3))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 前向加噪 …")
    make_forward()
    print("② 训练曲线 …")
    make_curves()
    print("③ 条件生成 …")
    make_conditional()
    print("④ 去噪 GIF …")
    make_gif()
    print("\n产出：")
    names = ("00-前向加噪.png", "01-训练曲线.png", "02-条件生成.png", "03-去噪生长.gif")
    for name in names:
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
