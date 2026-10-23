"""VAE — 图文素材生成器。

产出：
    00-重构对比.png  原图 / VAE / AE
    01-2D隐空间.png   VAE vs AE 的 2D latent
    02-先验采样.png   从 N(0,I) 采样再解码
    03-插值生长.gif   latent 插值
"""

import importlib.util
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

from impl import VAE  # noqa: E402


def load_ae():
    path = HERE.parent.parent / "p03-deep-learning" / "autoencoder" / "impl.py"
    spec = importlib.util.spec_from_file_location("p03_ae", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.AutoEncoder


def data():
    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    return train_test_split(X, y, train_size=1200, random_state=0, stratify=y)


def setup():
    Xtr, Xte, ytr, yte = data()
    vae = VAE(latent_dim=2, beta=1.0, epochs=100, random_state=0).fit(Xtr)
    ae = load_ae()(latent_dim=2, epochs=100, random_state=0).fit(Xtr)
    return Xtr, Xte, ytr, yte, vae, ae


def verify() -> None:
    _, Xte, _, _, vae, ae = setup()
    mse = float(np.mean((vae.reconstruct(Xte) - Xte) ** 2))
    assert mse < 0.1
    s = vae.sample(8)
    assert s.shape == (8, 64) and np.isfinite(s).all()
    print(f"  ✓ 对账通过：VAE test MSE {mse:.4f}；sample finite")


def make_recon() -> None:
    _, Xte, _, _, vae, ae = setup()
    idx = np.arange(8)
    fig, axes = plt.subplots(3, 8, figsize=(10.0, 4.2))
    for j, i in enumerate(idx):
        axes[0, j].imshow(Xte[i].reshape(8, 8), cmap="gray", vmin=0, vmax=1)
        axes[1, j].imshow(vae.reconstruct(Xte[i:i + 1])[0].reshape(8, 8), cmap="gray",
                          vmin=0, vmax=1)
        axes[2, j].imshow(ae.reconstruct(Xte[i:i + 1])[0].reshape(8, 8), cmap="gray",
                          vmin=0, vmax=1)
        for ax in axes[:, j]:
            ax.axis("off")
    for ax, label in zip(axes[:, 0], ("原始", "VAE", "AE")):
        ax.set_ylabel(label, fontsize=11)
    fig.suptitle("VAE vs AE：VAE 略模糊，但能采样；AE 只能重构", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-重构对比.png", dpi=130)
    plt.close(fig)


def make_latent() -> None:
    _, Xte, _, yte, vae, ae = setup()
    zm, _ = vae.encode(Xte)
    za = ae.encode(Xte)
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.4))
    for ax, Z, title in ((axes[0], zm, "VAE latent（先验约束）"),
                         (axes[1], za, "AE latent（无先验）")):
        sc = ax.scatter(Z[:, 0], Z[:, 1], c=yte, cmap="tab10", s=10)
        ax.set_title(title, fontsize=11)
        ax.grid(alpha=0.3)
    fig.colorbar(sc, ax=axes, label="digit")
    fig.suptitle("2D latent：VAE 更接近先验，AE 只追求重构", fontsize=13)
    fig.savefig(IMAGES / "01-2D隐空间.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def make_samples() -> None:
    _, _, _, _, vae, _ = setup()
    s = vae.sample(16).reshape(-1, 8, 8)
    fig, axes = plt.subplots(4, 4, figsize=(5.2, 5.2))
    for ax, img in zip(axes.ravel(), s):
        ax.imshow(img, cmap="gray", vmin=0, vmax=1)
        ax.axis("off")
    fig.suptitle("从 N(0,I) 采样再解码：VAE 的生成能力", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-先验采样.png", dpi=130)
    plt.close(fig)


def make_gif() -> None:
    _, Xte, _, _, vae, _ = setup()
    mu, _ = vae.encode(Xte[:2])
    frames = [vae.decode((mu[0] + a * (mu[1] - mu[0]))[None])[0].reshape(8, 8)
              for a in np.linspace(0, 1, 12)]
    fig, ax = plt.subplots(figsize=(4.6, 4.6))

    def draw(i):
        ax.clear()
        ax.imshow(frames[i], cmap="gray", vmin=0, vmax=1)
        ax.set_title(f"latent 插值 t={i / 11:.2f}", fontsize=11)
        ax.axis("off")

    anim = animation.FuncAnimation(fig, draw, frames=len(frames), interval=300)
    anim.save(IMAGES / "03-插值生长.gif", writer=animation.PillowWriter(fps=4))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 重构对比 …")
    make_recon()
    print("② 2D latent …")
    make_latent()
    print("③ 先验采样 …")
    make_samples()
    print("④ 插值 GIF …")
    make_gif()
    print("\n产出：")
    for name in ("00-重构对比.png", "01-2D隐空间.png", "02-先验采样.png", "03-插值生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
