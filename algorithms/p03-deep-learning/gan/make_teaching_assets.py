"""GAN — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-2D真假.png     4-Gaussians 真实点 vs 生成点
    01-模式覆盖.png    full / saturating / collapsed 的覆盖与熵
    02-8x8生成.png     8×8 digits 生成样本
    03-生成生长.gif    训练中生成点分布的变化
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.animation as animation
import matplotlib.pyplot as plt
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
from impl import GAN, mode_coverage  # noqa: E402

COLOR = dict(real="#3b5bdb", fake="#c92a2a", grid="#dee2e6")


def verify() -> None:
    X, centers = D.gaussians()
    full = GAN(data_dim=2, latent_dim=16, hidden=(64, 64), lr_g=5e-4, lr_d=5e-5,
               random_state=0).train(X, epochs=500, batch_size=64)
    m = mode_coverage(full.sample(500), centers)
    assert m["covered"] >= 3
    print(f"  ✓ 对账通过：2D 覆盖 {m['covered']}/4，熵 {m['entropy']:.2f}")


def make_2d() -> None:
    X, centers = D.gaussians()
    g = GAN(data_dim=2, latent_dim=16, hidden=(64, 64), lr_g=5e-4, lr_d=5e-5,
            random_state=0).train(X, epochs=500, batch_size=64)
    s = g.sample(500)
    fig, ax = plt.subplots(figsize=(6.6, 5.4))
    ax.scatter(X[:, 0], X[:, 1], s=8, color=COLOR["real"], alpha=0.4, label="真实")
    ax.scatter(s[:, 0], s[:, 1], s=8, color=COLOR["fake"], alpha=0.6, label="生成")
    ax.legend(fontsize=10)
    ax.set_title("2D 4-Gaussians：非饱和损失，4 个模态都覆盖", fontsize=12)
    ax.set_xlabel("x0")
    ax.set_ylabel("x1")
    ax.grid(True, color=COLOR["grid"], lw=0.5)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-2D真假.png", dpi=130)
    plt.close(fig)


def make_coverage() -> None:
    X, centers = D.gaussians()
    configs = [("full", dict(latent_dim=16, hidden=(64, 64), loss_type="non_saturating")),
               ("saturating", dict(latent_dim=16, hidden=(64, 64), loss_type="saturating")),
               ("collapsed", dict(latent_dim=1, hidden=(8, 8), loss_type="non_saturating"))]
    names, cov, ent = [], [], []
    for name, kw in configs:
        g = GAN(data_dim=2, lr_g=5e-4, lr_d=5e-5, random_state=0, **kw).train(
            X, epochs=500, batch_size=64)
        m = mode_coverage(g.sample(500), centers)
        names.append(name)
        cov.append(m["covered"])
        ent.append(m["entropy"])
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    bars = ax.bar(names, cov, color=[COLOR["real"], "#f08c00", COLOR["fake"]])
    for b, v, e in zip(bars, cov, ent):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.15, f"{v}/4\nH={e:.2f}", ha="center",
                fontsize=9)
    ax.set_ylim(0, 5)
    ax.set_ylabel("覆盖的模态数", fontsize=12)
    ax.set_title("非饱和损失覆盖 4 个模态；小容量/饱和损失掉队", fontsize=12)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-模式覆盖.png", dpi=130)
    plt.close(fig)


def make_digits() -> None:
    X_tr, X_te, y_tr, y_te = D.digits_data()
    g = GAN(data_dim=64, latent_dim=16, hidden=(32,), lr_g=2e-4, lr_d=5e-5,
            loss_type="non_saturating", out_sigmoid=True, g_steps=2,
            random_state=0).train(X_tr, epochs=150, batch_size=64)
    s = g.sample(16).reshape(-1, 8, 8)
    fig, axes = plt.subplots(2, 8, figsize=(8.0, 2.2))
    for ax, img in zip(axes.ravel(), s):
        ax.imshow(img, cmap="gray", vmin=0, vmax=1)
        ax.axis("off")
    fig.suptitle("8×8 digits GAN：模糊但有多样性（预测类别 4/10）", fontsize=11)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-8x8生成.png", dpi=130)
    plt.close(fig)


def make_gif() -> None:
    X, centers = D.gaussians()
    g = GAN(data_dim=2, latent_dim=16, hidden=(64, 64), lr_g=5e-4, lr_d=5e-5,
            random_state=0).train(X, epochs=500, batch_size=64)
    fig, ax = plt.subplots(figsize=(5.8, 5.2))
    frames = list(range(0, len(g.sample_history), 2))

    def draw(k: int) -> None:
        ax.clear()
        ax.scatter(X[:, 0], X[:, 1], s=5, color=COLOR["real"], alpha=0.25)
        s = g.sample_history[k]
        ax.scatter(s[:, 0], s[:, 1], s=8, color=COLOR["fake"], alpha=0.6)
        ax.set_title(f"生成点：第 {10 * (k * 2 + 1)} 轮", fontsize=10)
        ax.set_xlabel("x0")
        ax.set_ylabel("x1")

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=200)
    anim.save(IMAGES / "03-生成生长.gif", writer=animation.PillowWriter(fps=5))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画 2D 真假 …")
    make_2d()
    print("② 画模式覆盖 …")
    make_coverage()
    print("③ 画 8×8 生成 …")
    make_digits()
    print("④ 画生成 GIF …")
    make_gif()
    print("\n产出：")
    for name in ("00-2D真假.png", "01-模式覆盖.png", "02-8x8生成.png", "03-生成生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
