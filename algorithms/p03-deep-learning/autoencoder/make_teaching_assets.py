"""AutoEncoder — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-重构对比.png    原图 / AE2 / PCA2
    01-2D隐空间.png    AE vs PCA 的 2D latent（按数字着色）
    02-去噪.png        干净 / 加噪 / denoising AE
    03-隐空间生长.gif  AE 的 2D latent 在训练中的变化
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
from sklearn.decomposition import PCA

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
import impl  # noqa: E402


def verify() -> None:
    X_tr, X_te, y_tr, y_te = D.load_data()
    ae = impl.AutoEncoder(latent_dim=2, epochs=100, random_state=0).fit(X_tr)
    pca = PCA(n_components=2).fit(X_tr)
    p = D.mse(pca.inverse_transform(pca.transform(X_te)), X_te)
    assert ae.reconstruction_error(X_te) < p
    print(f"  ✓ 对账通过：AE {ae.reconstruction_error(X_te):.4f} < PCA {p:.4f}")


def encode_with(params, X):
    a1 = impl.relu(X @ params["W1"] + params["b1"])
    return a1 @ params["W2"] + params["b2"]


def make_reconstruction() -> None:
    X_tr, X_te, y_tr, y_te = D.load_data()
    ae = impl.AutoEncoder(latent_dim=2, epochs=100, random_state=0).fit(X_tr)
    pca = PCA(n_components=2).fit(X_tr)
    rec_ae = ae.reconstruct(X_te[:8])
    rec_pca = pca.inverse_transform(pca.transform(X_te[:8]))
    fig, axes = plt.subplots(3, 8, figsize=(12.0, 4.8))
    for j in range(8):
        for i, (img, label) in enumerate(((X_te[j], "原图"),
                                          (rec_ae[j], "AE2"),
                                          (rec_pca[j], "PCA2"))):
            axes[i, j].imshow(img.reshape(8, 8), cmap="gray", vmin=0, vmax=1)
            axes[i, j].axis("off")
            if j == 0:
                axes[i, j].set_title(label, fontsize=10, loc="left")
    fig.suptitle("2D 压缩：AE 保留笔画，PCA 更模糊", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-重构对比.png", dpi=130)
    plt.close(fig)


def make_latent() -> None:
    X_tr, X_te, y_tr, y_te = D.load_data()
    ae = impl.AutoEncoder(latent_dim=2, epochs=100, random_state=0).fit(X_tr)
    pca = PCA(n_components=2).fit(X_tr)
    Za, Zp = ae.encode(X_te), pca.transform(X_te)
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.0))
    for ax, Z, title in ((axes[0], Za, "AE latent"), (axes[1], Zp, "PCA latent")):
        sc = ax.scatter(Z[:, 0], Z[:, 1], c=y_te, cmap="tab10", s=10)
        ax.set_title(title, fontsize=12)
        ax.set_xlabel("z0")
        ax.set_ylabel("z1")
        ax.grid(True, alpha=0.3)
    fig.colorbar(sc, ax=axes, label="digit")
    fig.suptitle("同一批测试样本的 2D 表示", fontsize=13)
    fig.savefig(IMAGES / "01-2D隐空间.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def make_denoising() -> None:
    X_tr, X_te, y_tr, y_te = D.load_data()
    rng = np.random.default_rng(0)
    noisy = np.clip(X_te[:8] + rng.normal(0, 0.3, (8, 64)), 0, 1)
    ae = impl.AutoEncoder(latent_dim=8, epochs=100, denoising=0.3, random_state=0).fit(X_tr)
    rec = ae.reconstruct(noisy)
    fig, axes = plt.subplots(3, 8, figsize=(12.0, 4.8))
    for j in range(8):
        for i, (img, label) in enumerate(((X_te[j], "干净"), (noisy[j], "加噪"),
                                          (rec[j], "去噪"))):
            axes[i, j].imshow(img.reshape(8, 8), cmap="gray", vmin=0, vmax=1)
            axes[i, j].axis("off")
            if j == 0:
                axes[i, j].set_title(label, fontsize=10, loc="left")
    fig.suptitle("denoising AE：输入加噪，目标仍是干净图", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-去噪.png", dpi=130)
    plt.close(fig)


def make_latent_gif() -> None:
    X_tr, X_te, y_tr, y_te = D.load_data()
    ae = impl.AutoEncoder(latent_dim=2, epochs=100, random_state=0).fit(X_tr)
    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    frames = list(range(0, len(ae.param_history), 10))

    def draw(k: int) -> None:
        ax.clear()
        Z = encode_with(ae.param_history[k], X_te)
        ax.scatter(Z[:, 0], Z[:, 1], c=y_te, cmap="tab10", s=8)
        ax.set_title(f"AE 2D latent：第 {k + 1} 轮", fontsize=11)
        ax.set_xlabel("z0")
        ax.set_ylabel("z1")

    anim = animation.FuncAnimation(fig, draw, frames=frames, interval=250)
    anim.save(IMAGES / "03-隐空间生长.gif", writer=animation.PillowWriter(fps=4))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画重构对比 …")
    make_reconstruction()
    print("② 画 2D latent …")
    make_latent()
    print("③ 画去噪 …")
    make_denoising()
    print("④ 画 latent GIF …")
    make_latent_gif()
    print("\n产出：")
    for name in ("00-重构对比.png", "01-2D隐空间.png", "02-去噪.png", "03-隐空间生长.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
