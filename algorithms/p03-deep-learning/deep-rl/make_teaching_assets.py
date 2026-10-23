"""DQN — 素材生成器。"""

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


def setup_cjk_font():
    names = ("Noto Sans CJK SC", "Noto Sans CJK JP", "Source Han Sans SC",
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


setup_cjk_font()

from demo import random_policy  # noqa: E402
from impl import DQN, GOAL  # noqa: E402


def setup():
    return DQN().fit(1000, 50, 0)


def verify():
    m = setup()
    acc = m.evaluate(20)
    assert acc >= .8
    print(f"  ✓ greedy success {acc:.2f}")


def grid():
    m = setup()
    pol = m.policy()
    arrows = ["↑", "↓", "←", "→"]
    fig, ax = plt.subplots(figsize=(5.6, 5.4))
    for i, a in enumerate(pol):
        r, c = divmod(i, 4)
        color = "#d3f9d8" if i == GOAL else "white"
        ax.add_patch(plt.Rectangle((c, 3 - r), 1, 1, facecolor=color, edgecolor="black"))
        ax.text(c + .5, 3 - r + .5, "G" if i == GOAL else arrows[a],
                ha="center", va="center", fontsize=18)
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 4)
    ax.axis("off")
    ax.set_title("学到的贪心策略（G=目标）", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-网格策略.png", dpi=130)
    plt.close(fig)


def success():
    m = setup()
    vals = [m.evaluate(20), random_policy(20)]
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    ax.bar(["DQN（贪心）", "随机策略"], vals, color=["#3b5bdb", "#f08c00"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("success rate")
    ax.set_title("DQN 学到策略", fontsize=12)
    for i, v in enumerate(vals):
        ax.text(i, v + .02, f"{v:.2f}", ha="center")
    fig.tight_layout()
    fig.savefig(IMAGES / "01-成功率.png", dpi=130)
    plt.close(fig)


def loss():
    m = setup()
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.plot(m.loss_history, color="#3b5bdb")
    ax.set_xlabel("train step")
    ax.set_ylabel("TD MSE")
    ax.set_title("DQN 训练损失", fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-损失.png", dpi=130)
    plt.close(fig)


def gif():
    fig, ax = plt.subplots(figsize=(5.2, 4.2))

    def draw(i):
        m = DQN().fit(100 + i * 100, 50, 0)
        ax.clear()
        ax.bar(["success"], [m.evaluate(10)], color="#3b5bdb")
        ax.set_ylim(0, 1.05)
        ax.set_title(f"{100 + i * 100} episodes")

    anim = animation.FuncAnimation(fig, draw, frames=8, interval=300)
    anim.save(IMAGES / "03-训练过程.gif", writer=animation.PillowWriter(fps=3))
    plt.close(fig)


def main():
    print("对账 …")
    verify()
    print("① 策略 …")
    grid()
    print("② 成功率 …")
    success()
    print("③ 损失 …")
    loss()
    print("④ GIF …")
    gif()
    for name in ("00-网格策略.png", "01-成功率.png", "02-损失.png", "03-训练过程.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
