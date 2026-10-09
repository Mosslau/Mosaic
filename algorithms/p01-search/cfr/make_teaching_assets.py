"""CFR 图文素材生成器（供 README 引用）。

原则：素材全部由本脚本生成，且与 `demo.py` 的数字逐项对账——不一致直接报错、不出图（纪律④）。

产出（`images/` 目录）：
    01-收敛曲线.png   训练量 → 博弈值（对照理论值 −1/18）+ 可被利用度
    02-策略对照.png   p1/p2 各信息集的学习结果 vs 理论均衡

运行：cd algorithms/p01-search/cfr && python3 make_teaching_assets.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
IMAGES = HERE / "images"
IMAGES.mkdir(exist_ok=True)


def setup_cjk_font() -> str:
    """注册一个**确实含中文字形**的字体；找不到就报错，绝不画方块。"""
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

COLOR = dict(value="#2b8a3e", theory="#c92a2a", gap="#3b5bdb", grid="#dee2e6",
             text="#343a40", bar="#f6c344", learned="#3b5bdb", target="#c92a2a")


def convergence_data(grid=(10, 100, 1000, 10000, 50000)) -> list:
    """与 demo.experiment_convergence 同源取数。"""
    rows = []
    for iters in grid:
        cfr = D.make_cfr().train(D.all_deals(), iterations=iters)
        avg = cfr.average_strategy()
        rows.append({"iters": iters, "value": D.ev_average(avg),
                     "regret_avg": cfr.positive_regret() / (iters * 6)})
    return rows


def exploitability_data(grid=(10, 100, 1000, 10000)) -> list:
    rows = []
    for iters in grid:
        avg = D.make_cfr().train(D.all_deals(), iterations=iters).average_strategy()
        rows.append({"iters": iters, "gap": D.best_response_p2(avg) - 1 / 18})
    return rows


def strategy_data() -> dict:
    avg = D.make_cfr().train(D.all_deals(), iterations=50000).average_strategy()
    return {"learned": D.key_frequencies(avg)}


def verify(conv: list, expl: list, strat: dict) -> None:
    assert abs(conv[-1]["value"] - D.GAME_VALUE) < 0.002, "博弈值应当收敛到 −1/18"
    assert expl[-1]["gap"] < expl[0]["gap"], "可被利用度应当下降"
    assert conv[-1]["regret_avg"] < conv[0]["regret_avg"], "平均后悔应当下降"
    f = strat["learned"]
    assert 2.0 < f["K_bet"] / f["J_bet"] < 4.5, f"K:J 下注率应接近 3:1，实际 {f}"
    assert f["Q_bet"] < 0.02, f"Q 不该下注：{f['Q_bet']}"
    print(f"  ✓ 对账通过：博弈值 {conv[-1]['value']:+.4f}（理论 {D.GAME_VALUE:+.4f}）；"
          f"可被利用度 {expl[0]['gap']:.4f} → {expl[-1]['gap']:.4f}；"
          f"K:J = {f['K_bet'] / f['J_bet']:.2f}")


def make_convergence(conv: list, expl: list) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 5.2))
    xs = [r["iters"] for r in conv]

    ax = axes[0]
    ax.plot(xs, [r["value"] for r in conv], "o-", color=COLOR["value"], lw=2, ms=7,
            label="训练后的博弈值")
    ax.axhline(D.GAME_VALUE, color=COLOR["theory"], ls="--", lw=1.6,
               label=f"理论值 −1/18 = {D.GAME_VALUE:.4f}")
    for x, r in zip(xs, conv):
        if x in (10, 100, 50000):
            ax.annotate(f"{r['value']:+.4f}", (x, r["value"]),
                        textcoords="offset points", xytext=(0, 9), ha="center", fontsize=9)
    ax.set_xscale("log"); ax.set_xticks(xs); ax.set_xticklabels([str(x) for x in xs])
    ax.set_xlabel("训练量（轮）", fontsize=12); ax.set_ylabel("博弈值（player1 期望）", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.8); ax.set_axisbelow(True)
    ax.legend(fontsize=11, loc="lower right")
    ax.set_title("博弈值精确收敛到理论值：这就是「学对了」", fontsize=12.5, pad=10)

    ax = axes[1]
    gx = [r["iters"] for r in expl]
    ax.plot(gx, [r["gap"] for r in expl], "s-", color=COLOR["gap"], lw=2, ms=7)
    for x, r in zip(gx, expl):
        ax.annotate(f"{r['gap']:.4f}", (x, r["gap"]), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=9)
    ax.set_xscale("log"); ax.set_xticks(gx); ax.set_xticklabels([str(x) for x in gx])
    ax.set_yscale("log")
    ax.set_xlabel("训练量（轮）", fontsize=12)
    ax.set_ylabel("可被利用度（对数轴）", fontsize=12)
    ax.grid(True, color=COLOR["grid"], lw=0.8); ax.set_axisbelow(True)
    ax.set_title("可被利用度下降：策略越来越「无法被针对」", fontsize=12.5, pad=10)

    fig.tight_layout()
    fig.savefig(IMAGES / "01-收敛曲线.png", dpi=130)
    plt.close(fig)


def make_strategy_figure(strat: dict) -> None:
    f = strat["learned"]
    labels = ["J 首轮下注", "Q 首轮下注", "K 首轮下注", "J 面对下注跟注",
              "Q 面对下注跟注", "K 面对下注跟注", "p2 用 Q 跟注"]
    learned = [f["J_bet"], f["Q_bet"], f["K_bet"], f["J_call"], f["Q_call"],
               f["K_call"], f["p2_Q_call"]]
    # 理论：J:α、Q:0、K:3α（用实测 α 反推）；面对下注 0 / 1/3 / 1；p2 用 Q 跟 1/3
    alpha = f["J_bet"]
    # 注意：p1「Q 面对下注的跟注率」在均衡族里**不唯一**（被均衡固定的是 p2 的 1/3），
    # 所以这一项不给"理论值"参照，留 nan 让柱子空着，避免把非唯一量当成真值。
    target = [alpha, 0.0, 3 * alpha, 0.0, float("nan"), 1.0, 1 / 3]

    xs = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(13.2, 5.8))
    ax.bar(xs - 0.2, learned, width=0.4, color=COLOR["learned"], label="CFR 学到的频率")
    ax.bar(xs + 0.2, target, width=0.4, color=COLOR["target"], alpha=0.85,
           label="理论均衡给出的频率（该量唯一时）")
    for i, (a, b) in enumerate(zip(learned, target)):
        ax.text(i - 0.2, a + 0.02, f"{a:.2f}", ha="center", fontsize=9.5)
        if b == b:                       # 非 nan 才标注
            ax.text(i + 0.2, b + 0.02, f"{b:.2f}", ha="center", fontsize=9.5, color="#8a2b2b")
        else:
            ax.text(i + 0.2, 0.04, "不唯一", ha="center", fontsize=9, color="#8a2b2b")
    ax.set_xticks(xs); ax.set_xticklabels(labels, fontsize=10.5)
    ax.set_ylabel("动作概率", fontsize=12); ax.set_ylim(0, 1.15)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.8); ax.set_axisbelow(True)
    ax.legend(fontsize=11)
    ax.set_title("学到的策略 vs 理论均衡：J:Q:K 下注率与「面对下注」的跟注率都对准了",
                 fontsize=13, pad=12)
    ax.text(0.5, 0.92,
            f"理论用 α = {alpha:.2f}（实测 J 的下注率）反推；均衡是一族，α ∈ [0, 1/3] 任意值都成立。\n"
            "K 的下注率是 0.66 而不是 1 —— 它必须与 J 保持 3:1；"
            "p1 用 Q 跟注的概率在均衡族里不唯一（被固定的只有 p2 的 1/3）。",
            transform=ax.transAxes, ha="center", va="top", fontsize=10.5, color=COLOR["text"])
    fig.tight_layout()
    fig.savefig(IMAGES / "02-策略对照.png", dpi=130)
    plt.close(fig)


def main() -> None:
    print("取数：收敛曲线 …")
    conv = convergence_data()
    print("取数：可被利用度 …")
    expl = exploitability_data()
    print("取数：策略对照 …")
    strat = strategy_data()
    verify(conv, expl, strat)
    print("① 画收敛曲线 …")
    make_convergence(conv, expl)
    print("② 画策略对照 …")
    make_strategy_figure(strat)
    print("\n产出：")
    for name in ("01-收敛曲线.png", "02-策略对照.png"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")
    print("\n可粘贴进 README 的收敛表：")
    print("| 训练量 | 博弈值 | 平均后悔 |")
    print("|---|---|---|")
    for r in conv:
        print(f"| {r['iters']} | {r['value']:+.4f} | {r['regret_avg']:.4f} |")
    print("\n可被利用度：")
    print("| 训练量 | 可被利用度 |")
    print("|---|---|")
    for r in expl:
        print(f"| {r['iters']} | {r['gap']:.4f} |")


if __name__ == "__main__":
    main()
