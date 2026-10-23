"""条件 GAN 样本网格素材。"""

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from conditional import ConditionalGAN
from demo import digits_data

HERE = Path(__file__).resolve().parent
IMAGES = HERE / "images"

def setup_cjk_font() -> None:
    from matplotlib import font_manager
    names = ("Noto Sans CJK SC", "Noto Sans CJK JP", "Source Han Sans SC",
             "Source Han Sans CN", "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
             "Hiragino Sans GB", "PingFang SC", "Heiti TC", "STHeiti", "Songti SC",
             "Arial Unicode MS", "Microsoft YaHei", "SimHei")
    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
        if Path(path).exists():
            font_manager.fontManager.addfont(path)
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((n for n in names if n in available), None)
    if chosen is None:
        raise SystemExit("找不到含中文字形的字体")
    font_path = font_manager.findfont(font_manager.FontProperties(family=chosen))
    from matplotlib import ft2font
    if ft2font.FT2Font(font_path).get_char_index(ord("中")) == 0:
        raise SystemExit("字体不含中文字形")
    plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False



def main() -> None:
    setup_cjk_font()
    Xtr, _, ytr, _ = digits_data()
    c = ConditionalGAN().train(Xtr, ytr)
    labels = np.tile(np.arange(10), 5)
    s = c.sample(50, labels=labels, seed=1)
    fig, axes = plt.subplots(5, 10, figsize=(9.0, 5.0))
    for i, ax in enumerate(axes.ravel()):
        ax.imshow(s[i].reshape(8, 8), cmap="gray")
        ax.set_title(str(labels[i]), fontsize=7)
        ax.axis("off")
    fig.suptitle("条件 GAN：每列一个类别（5 个样本/类）", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "04-条件生成.png", dpi=130)
    print("saved", (IMAGES / "04-条件生成.png").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
