"""对照版：A* 与本目录三个算法的对照基线。

搜索族的对照对象是**基线算法**（见 `references/algorithm-families.md`）。
本实验的定位特殊——它本身就是 A* 实验的基线，所以"对照"要反过来做：

| 对照 | 谁更强 | 量化什么 |
|---|---|---|
| A*（带 h） vs **UCS**（无 h） | A* | h 把扩展数砍掉多少（同一张图、同一个最优解） |
| A*（带 h） vs **BFS** | 各有胜负 | 无权图上扩展数接近，但 A* 能处理带权图 |
| A*（带 h） vs **DFS** | A* | DFS 快但**不保证最优**——拿"解的质量"换速度 |

本文件只放**独立参考实现**，不放搜索算法本身（三个算法在 `impl.py`）：
`astar_reference` 按路径加载 A* 实验的 `impl.py`，避免同名模块遮蔽。

用法（本目录内）：
    from baseline import astar_reference, load_astar
    A = load_astar()
    result = A.solve(grid01, start, goal)      # grid01：0 可走 / 1 障碍
"""

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
ASTAR_DIR = HERE.parent / "a-star"


@dataclass
class AstarResult:
    """A* 结果的瘦身视图（只留对比需要的字段，字段名与本目录 SearchResult 对齐）。"""

    path: Optional[list]
    cost: float
    expanded: int

    @classmethod
    def from_astar(cls, r) -> "AstarResult":
        return cls(path=list(r.path), cost=float(r.path_cost), expanded=int(r.nodes_expanded))


def load_astar():
    """按**文件路径**加载 `../a-star/impl.py`。

    坑：本目录也有 `impl.py`，用 `sys.path.insert` + `import impl` 会命中本目录那份。
    加载完立刻把 `impl` 这个键恢复，避免污染后续 import。
    """
    saved = sys.modules.get("impl")
    try:
        spec = importlib.util.spec_from_file_location("astar_impl", ASTAR_DIR / "impl.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if saved is None:
            sys.modules.pop("impl", None)
        else:
            sys.modules["impl"] = saved


def astar_reference(grid: list, start: tuple, goal: tuple,
                    tie_break: str = "large_g") -> AstarResult:
    """用 A* 实验的实现解同一个问题（输入输出口径与本目录 `impl.py` 对齐）。

    注意地图口径差异：A* 实验用 0=可走 / 1=障碍；本目录用 -1=障碍 / 其余=可走。
    `to_astar_grid` 负责转换，本函数只接受已转换好的 0/1 地图。
    """
    module = load_astar()
    return AstarResult.from_astar(module.solve(grid, start, goal, tie_break=tie_break))


def to_astar_grid(grid: list) -> list:
    """本目录地图（-1=障碍）→ A* 实验地图（1=障碍 / 0=可走）。"""
    return [[1 if v == -1 else 0 for v in row] for row in grid]


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，跑对比请执行：python3 demo.py")
