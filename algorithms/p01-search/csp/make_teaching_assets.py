"""CSP 图文素材生成器（供 README 引用）。

原则：素材全部由本脚本生成，且与 `demo.py` 的数字逐项对账——不一致直接报错（纪律④）。

产出（`images/` 目录）：
    01-传播的收益.png  三种策略在八皇后/数独上的节点数与耗时（对数轴）
    02-启发式对比.png  MRV / LCV 在两个结构不同的问题上各值多少

运行：cd algorithms/p01-search/csp && python3 make_teaching_assets.py
"""

import os
import sys
import time
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

from baseline import n_queens, sudoku  # noqa: E402
from demo import SUDOKU_HARD  # noqa: E402
from impl import solve  # noqa: E402

COLOR = dict(bt="#c92a2a", fc="#e8590c", ac3="#2b8a3e", grid="#dee2e6",
             text="#343a40", hl="#f6c344", queen="#3b5bdb", sudoku="#7048e8")


def strategy_nodes() -> dict:
    """三种策略在两个问题上的节点数（与 demo 同源取数）。"""
    out = {}
    for n in (8, 10, 12):
        csp = n_queens(n)
        out[f"{n} 皇后"] = {s: solve(csp, strategy=s).nodes for s in ("bt", "fc", "ac3")}
    csp = sudoku(SUDOKU_HARD)
    out["数独"] = {s: solve(csp, strategy=s).nodes for s in ("bt", "fc", "ac3")}
    return out


def heuristic_gain() -> dict:
    """MRV / LCV 在两个问题上的收益倍数。"""
    out = {}
    for name, csp in (("n 皇后(10)", n_queens(10)), ("数独", sudoku(SUDOKU_HARD))):
        base = solve(csp, strategy="fc", var_heuristic="decl", value_heuristic="decl").nodes
        mrv = solve(csp, strategy="fc", var_heuristic="mrv", value_heuristic="decl").nodes
        lcv = solve(csp, strategy="fc", var_heuristic="decl", value_heuristic="lcv").nodes
        out[name] = {"base": base, "mrv_gain": base / max(mrv, 1),
                     "lcv_gain": base / max(lcv, 1)}
    return out


def verify(nodes: dict, gains: dict) -> None:
    for pname, d in nodes.items():
        assert d["fc"] <= d["bt"], f"{pname}: 前向检查不该更差 {d}"
        assert d["ac3"] <= d["fc"], f"{pname}: AC-3 不该更差 {d}"
    # 核心结论：启发式的价值依赖问题结构（数独上 MRV 远强于 LCV；皇后上反过来）
    assert gains["数独"]["mrv_gain"] > gains["数独"]["lcv_gain"], f"数独上 MRV 应更强：{gains}"
    assert gains["n 皇后(10)"]["lcv_gain"] > gains["n 皇后(10)"]["mrv_gain"], \
        f"皇后上 LCV 应更强：{gains}"
    print(f"  ✓ 对账通过：数独上 MRV 收益 {gains['数独']['mrv_gain']:.1f}× / "
          f"LCV {gains['数独']['lcv_gain']:.1f}×；"
          f"皇后上 MRV {gains['n 皇后(10)']['mrv_gain']:.1f}× / "
          f"LCV {gains['n 皇后(10)']['lcv_gain']:.1f}×")


def make_propagation_figure(nodes: dict) -> None:
    problems = list(nodes)
    xs = np.arange(len(problems))
    width = 0.26
    fig, ax = plt.subplots(figsize=(12.8, 5.8))
    for i, (s, label, color) in enumerate((("bt", "纯回溯", COLOR["bt"]),
                                           ("fc", "前向检查", COLOR["fc"]),
                                           ("ac3", "维护弧一致", COLOR["ac3"]))):
        vals = [nodes[p][s] for p in problems]
        bars = ax.bar(xs + (i - 1) * width, vals, width=width, color=color, label=label)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, v * 1.15, f"{v:,}",
                    ha="center", fontsize=8.5)
    ax.set_yscale("log")
    ax.set_xticks(xs); ax.set_xticklabels(problems, fontsize=11)
    ax.set_ylabel("搜索节点数（对数轴）", fontsize=12)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.8); ax.set_axisbelow(True)
    ax.legend(fontsize=11)
    ax.set_ylim(top=max(nodes[p][s] for p in problems for s in ("bt", "fc", "ac3")) * 4)
    ax.set_title("约束传播越强，搜索树越小：节点数(纯回溯) ≥ (前向检查) ≥ (维护弧一致)",
                 fontsize=13, pad=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "01-传播的收益.png", dpi=130)
    plt.close(fig)


def make_heuristic_figure(gains: dict) -> None:
    problems = list(gains)
    xs = np.arange(len(problems))
    width = 0.32
    fig, ax = plt.subplots(figsize=(11.6, 5.6))
    mrv = [gains[p]["mrv_gain"] for p in problems]
    lcv = [gains[p]["lcv_gain"] for p in problems]
    b1 = ax.bar(xs - width / 2, mrv, width=width, color=COLOR["queen"], label="MRV（变量排序）")
    b2 = ax.bar(xs + width / 2, lcv, width=width, color=COLOR["hl"], label="LCV（取值排序）")
    for bars, vals in ((b1, mrv), (b2, lcv)):
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 0.2, f"{v:.1f}×",
                    ha="center", fontsize=11)
    ax.set_xticks(xs); ax.set_xticklabels(problems, fontsize=12)
    ax.set_ylabel("相对「声明序 + 原序」的节点数下降倍数", fontsize=12)
    ax.set_ylim(0, max(mrv + lcv) * 1.25)
    ax.grid(True, axis="y", color=COLOR["grid"], lw=0.8); ax.set_axisbelow(True)
    ax.legend(fontsize=11)
    ax.set_title("启发式的价值取决于问题结构：数独上 MRV 最强，皇后上 LCV 更强",
                 fontsize=13, pad=12)
    ax.text(0.5, 0.88,
            "n 皇后每行的候选数完全相同（都是 n），MRV 无从发挥；\n"
            "数独每个空格的候选数从 1 到 9 不等，MRV 才是主力。",
            transform=ax.transAxes, ha="center", va="top", fontsize=10.5, color=COLOR["text"])
    fig.tight_layout()
    fig.savefig(IMAGES / "02-启发式对比.png", dpi=130)
    plt.close(fig)


def main() -> None:
    print("取数：三种策略的节点数 …")
    nodes = strategy_nodes()
    print("取数：启发式收益 …")
    gains = heuristic_gain()
    verify(nodes, gains)
    print("① 画传播收益 …")
    make_propagation_figure(nodes)
    print("② 画启发式对比 …")
    make_heuristic_figure(gains)
    print("\n产出：")
    for name in ("01-传播的收益.png", "02-启发式对比.png"):
        print(f"  {name}  {(IMAGES / name).stat().st_size / 1024:.0f} KB")
    print("\n可粘贴进 README 的节点数表：")
    print("| 问题 | 纯回溯 | 前向检查 | 维护弧一致 |")
    print("|---|---|---|---|")
    for p in nodes:
        print(f"| {p} | {nodes[p]['bt']:,} | {nodes[p]['fc']:,} | {nodes[p]['ac3']:,} |")


if __name__ == "__main__":
    main()
