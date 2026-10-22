"""RNN 与 LSTM — 图文素材生成器（供 README 引用）。

产出（`images/` 目录）：
    00-parity准确率.png   RNN vs LSTM 的测试准确率
    01-梯度范数.png       h0 梯度范数随 T 的变化（对数轴）
    02-梯度裁剪.png       高学习率下裁剪前后梯度范数
    03-隐状态.gif         RNN/LSTM 在一条序列上的隐状态随时间变化
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
from impl import LSTM, RNN  # noqa: E402

COLOR = dict(rnn="#c92a2a", lstm="#3b5bdb", grid="#dee2e6")


def verify() -> None:
    X_tr, X_te, y_tr, y_te = D.split_data()
    rnn = RNN(input_size=2, hidden_size=32, n_classes=2, lr=0.01, epochs=20,
              batch_size=32, clip_norm=1.0, random_state=0).fit(X_tr, y_tr)
    lstm = LSTM(input_size=2, hidden_size=32, n_classes=2, lr=0.01, epochs=20,
                batch_size=32, clip_norm=1.0, random_state=0).fit(X_tr, y_tr)
    a = D.acc(y_te, lstm.predict(X_te))
    b = D.acc(y_te, rnn.predict(X_te))
    assert a > 0.9 and b < 0.7
    print(f"  ✓ 对账通过：LSTM {a:.3f} / RNN {b:.3f}")


def make_parity() -> None:
    X_tr, X_te, y_tr, y_te = D.split_data()
    vals = {}
    for name, cls in (("RNN", RNN), ("LSTM", LSTM)):
        m = cls(input_size=2, hidden_size=32, n_classes=2, lr=0.01, epochs=30,
                batch_size=32, clip_norm=1.0, random_state=0).fit(X_tr, y_tr)
        vals[name] = D.acc(y_te, m.predict(X_te))
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    bars = ax.bar(list(vals), list(vals.values()), color=[COLOR["rnn"], COLOR["lstm"]])
    for b, v in zip(bars, vals.values()):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.3f}", ha="center")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("测试准确率", fontsize=12)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title("parity（T=12）：LSTM 能记住，RNN 不能", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "00-parity准确率.png", dpi=130)
    plt.close(fig)


def make_grad_norm() -> None:
    X_tr, _, y_tr, _ = D.split_data()
    models = {}
    for name, cls in (("RNN", RNN), ("LSTM", LSTM)):
        models[name] = cls(input_size=2, hidden_size=32, n_classes=2, lr=0.01,
                           epochs=30, batch_size=32, clip_norm=1.0,
                           random_state=0).fit(X_tr, y_tr)
    Ts = [4, 8, 16, 32, 48]
    series = {}
    for name, m in models.items():
        series[name] = []
        for T in Ts:
            gs = [m.grad_norm_h0_for_T(*D.make_parity(200, T, seed=s)) for s in range(5)]
            series[name].append(float(np.mean(gs)))
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    ax.plot(Ts, series["RNN"], "o-", color=COLOR["rnn"], lw=2, label="RNN")
    ax.plot(Ts, series["LSTM"], "s-", color=COLOR["lstm"], lw=2, label="LSTM")
    ax.set_yscale("log")
    ax.set_xlabel("序列长度 T", fontsize=12)
    ax.set_ylabel("h0 梯度范数（对数）", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_title("RNN 的信用随 T 指数衰减；LSTM 的门控把它保住", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-梯度范数.png", dpi=130)
    plt.close(fig)


def make_clipping() -> None:
    X_tr, X_te, y_tr, y_te = D.split_data(2000, 20)
    norms = {}
    for clip in (None, 1.0):
        m = RNN(input_size=2, hidden_size=32, n_classes=2, lr=0.5, epochs=10,
                batch_size=32, clip_norm=clip, random_state=0).fit(X_tr, y_tr)
        norms["无裁剪" if clip is None else "裁剪=1.0"] = float(np.mean(m.grad_norm_history))
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    bars = ax.bar(list(norms), list(norms.values()), color=[COLOR["rnn"], COLOR["lstm"]])
    for b, v in zip(bars, norms.values()):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.5, f"{v:.2f}", ha="center")
    ax.set_ylabel("平均梯度范数", fontsize=12)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title("高学习率下：裁剪把梯度范数压到个位数", fontsize=13)
    fig.tight_layout()
    fig.savefig(IMAGES / "02-梯度裁剪.png", dpi=130)
    plt.close(fig)


def make_hidden_gif() -> None:
    X_tr, _, y_tr, _ = D.split_data()
    rnn = RNN(input_size=2, hidden_size=32, n_classes=2, lr=0.01, epochs=30,
              batch_size=32, clip_norm=1.0, random_state=0).fit(X_tr, y_tr)
    lstm = LSTM(input_size=2, hidden_size=32, n_classes=2, lr=0.01, epochs=30,
                batch_size=32, clip_norm=1.0, random_state=0).fit(X_tr, y_tr)
    X, y = D.make_parity(1, 48, seed=3)
    _, c1 = rnn.forward(X)
    _, c2 = lstm.forward(X)
    h1 = np.array([h[0] for h in c1["hs"][1:]])
    h2 = np.array([z["h"][0] for z in c2["cache"]])
    fig, axes = plt.subplots(2, 1, figsize=(8.0, 5.0))

    def draw(t: int) -> None:
        for ax, h, name in ((axes[0], h1, "RNN"), (axes[1], h2, "LSTM")):
            ax.clear()
            ax.imshow(h[:t + 1].T, aspect="auto", cmap="RdBu_r", vmin=-1, vmax=1,
                      extent=[0, 48, 32, 0])
            ax.set_xlim(0, 48)
            ax.set_ylabel("隐单元", fontsize=8)
            ax.set_title(f"{name}：前 {t + 1} 步", fontsize=10)
        axes[1].set_xlabel("时间步", fontsize=10)
        fig.suptitle(f"同一条 parity 序列（T=48，标签 {y[0]}）", fontsize=11)

    anim = animation.FuncAnimation(fig, draw, frames=range(0, 48, 2), interval=120)
    anim.save(IMAGES / "03-隐状态.gif", writer=animation.PillowWriter(fps=8))
    plt.close(fig)


def main() -> None:
    print("对账 …")
    verify()
    print("① 画 parity 准确率 …")
    make_parity()
    print("② 画梯度范数 …")
    make_grad_norm()
    print("③ 画梯度裁剪 …")
    make_clipping()
    print("④ 画隐状态 GIF …")
    make_hidden_gif()
    print("\n产出：")
    for name in ("00-parity准确率.png", "01-梯度范数.png", "02-梯度裁剪.png", "03-隐状态.gif"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
