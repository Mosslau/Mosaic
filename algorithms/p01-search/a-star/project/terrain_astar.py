"""迁移项目：地形代价地图上的最小代价路径。

与教学示例的差别（这就是"迁移"）：
- 每格有地形代价 1–9，进入一格的代价是该格的地形代价（不再恒为 1）
- 曼哈顿距离不再直接可用作启发式——要用"每步最小代价 × 曼哈顿距离"才不高估
- 对比对象仍是 Dijkstra（h ≡ 0）：代价必须一致，且 A* 应少扩展节点

运行：
    cd algorithms/p01-search/a-star/project
    ../../../../.venv/bin/python terrain_astar.py

产出：out/terrain.png（地形 + A*/Dijkstra 路径对比图）
"""

from __future__ import annotations

import heapq
import itertools
import math
import os
import random
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
for _f in FONT_CANDIDATES:
    if Path(_f).exists():
        font_manager.fontManager.addfont(_f)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=_f).get_name()
        break

ROWS, COLS = 20, 20
START, GOAL = (0, 0), (ROWS - 1, COLS - 1)
MIN_COST = 1.0  # 地形代价下界 → 启发式系数


def make_terrain(seed: int = 42) -> list[list[int]]:
    """固定种子生成 1–9 的地形代价；起点终点强制为 1。"""
    rng = random.Random(seed)
    terrain = [[rng.randint(1, 9) for _ in range(COLS)] for _ in range(ROWS)]
    terrain[START[0]][START[1]] = 1
    terrain[GOAL[0]][GOAL[1]] = 1
    return terrain


def neighbors(node: tuple[int, int]):
    r, c = node
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < ROWS and 0 <= nc < COLS:
            yield (nr, nc)


def heuristic(node: tuple[int, int]) -> float:
    """不高估：每走一步至少花 MIN_COST，所以剩余代价 ≥ MIN_COST × 曼哈顿距离。"""
    return MIN_COST * (abs(GOAL[0] - node[0]) + abs(GOAL[1] - node[1]))


def zero(_node: tuple[int, int]) -> float:
    return 0.0


def search(terrain, h):
    """返回 (路径, 总代价, 扩展节点数)。"""
    order = itertools.count()
    g = {START: 0.0}
    came: dict[tuple[int, int], tuple[int, int]] = {}
    closed: set[tuple[int, int]] = set()
    expanded = 0
    heap = [(h(START), next(order), START)]
    while heap:
        _, _, node = heapq.heappop(heap)
        if node in closed:
            continue
        closed.add(node)
        expanded += 1
        if node == GOAL:
            path = [node]
            while node != START:
                node = came[node]
                path.append(node)
            return path[::-1], g[GOAL], expanded
        for nb in neighbors(node):
            ng = g[node] + terrain[nb[0]][nb[1]]  # 代价算在"进入的格子"上
            if ng < g.get(nb, math.inf):
                g[nb] = ng
                came[nb] = node
                heapq.heappush(heap, (ng + h(nb), next(order), nb))
    raise AssertionError("随机地形起点终点必然连通（无墙）")


def draw(terrain, paths, stats, path_png: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 6.4))
    for ax, (name, path), (expanded, cost) in zip(axes, paths, stats):
        ax.imshow(np.array(terrain), cmap="YlOrBr", origin="upper")
        ax.plot([c for _, c in path], [r for r, _ in path], "-", color="#1f4fd8",
                lw=2.6, label="路径")
        ax.scatter([START[1]], [START[0]], marker="o", s=120, facecolors="none",
                   edgecolors="#0b6b0b", lw=2.4, label="起点")
        ax.scatter([GOAL[1]], [GOAL[0]], marker="*", s=180, c="#00a0a0",
                   edgecolors="#004d4d", lw=1, label="终点")
        ax.set_title(f"{name}\n总代价 {cost:.0f} · 扩展 {expanded} 格", fontsize=13)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle("地形代价地图（颜色越深越贵）：曼哈顿启发式的迁移用法", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path_png, dpi=120)
    plt.close(fig)


def main() -> None:
    terrain = make_terrain(seed=42)
    a_path, a_cost, a_exp = search(terrain, heuristic)
    d_path, d_cost, d_exp = search(terrain, zero)
    assert a_cost == d_cost, f"A* 代价 {a_cost} != Dijkstra {d_cost}"

    print("地形代价地图 20×20（代价 1–9，种子 42）")
    print(f"  A*（h = 1 × 曼哈顿）   总代价 {a_cost:.0f}  扩展 {a_exp} 格")
    print(f"  Dijkstra（h ≡ 0）      总代价 {d_cost:.0f}  扩展 {d_exp} 格")
    print(f"  代价一致 ✓；A* 少扩展 {(1 - a_exp / d_exp) * 100:.0f}%")

    draw(terrain, [("A*", a_path), ("Dijkstra", d_path)],
         [(a_exp, a_cost), (d_exp, d_cost)], OUT / "terrain.png")
    print("  对比图已保存：", OUT / "terrain.png")


if __name__ == "__main__":
    main()
