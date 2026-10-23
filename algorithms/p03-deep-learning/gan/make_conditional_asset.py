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


def main() -> None:
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
