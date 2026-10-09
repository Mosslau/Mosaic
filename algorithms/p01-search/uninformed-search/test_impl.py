"""DFS / BFS / UCS 的性质测试。

用法（本目录内）：python3 -m pytest test_impl.py -v

覆盖：
- **BFS 最优**：无权图上 BFS 的步数 = 独立 BFS 参考（复用 a-star 实验的 `bfs_shortest_cost`，不共享本目录代码）
- **UCS 最优**：带权图上 UCS 的总代价 ≤ 任何其他走法的代价（对小图做穷举校验）
- **UCS 在无权图上退化为 BFS**：两者代价必须逐个相同
- **DFS 的定位**：只要求"有解且合法"，**不断言最优**；并断言换邻接顺序会改变结果
- **内存口径**：三个算法都记录边界峰值，且峰值 ≥ 1
- **边界**：起点即终点、无解、越界 / 落在障碍上抛 ValueError
- **独立参考**：另写一份"朴素 Floyd 式松弛"作为带权最短路径的外部依据（不复用 impl）

口径与 impl.py 一致：expanded = 从边界取出的节点数；peak_frontier = 边界峰值。
"""

import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import impl  # noqa: E402
from demo import make_grid, make_terrain, terrain_cost  # noqa: E402
from impl import bfs, dfs, ucs  # noqa: E402


def _load_astar_baseline():
    """加载 a-star 实验的独立 BFS 参考（外部依据：不共享本目录任何代码）。

    坑：`../a-star/baseline.py` 内部写着 `from impl import SearchResult, solve`——
    而本目录也有 `impl.py`，直接 exec 会命中**本目录**那份（实测报 cannot import name 'solve'）。
    所以：
      1. 先在独立命名空间里按路径加载 a-star 的 impl；
      2. 临时把 `impl` 这个键指向它，让 baseline 的 import 拿到正确的那份；
      3. 加载完立刻把 `impl` 恢复成本目录的模块，不污染后续测试。
    """
    astar_dir = HERE.parent / "a-star"
    saved = {name: sys.modules.get(name) for name in ("impl", "baseline")}
    try:
        for name in ("impl", "baseline"):
            spec = importlib.util.spec_from_file_location(name, astar_dir / f"{name}.py")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        return sys.modules["baseline"]
    finally:
        # 恢复（或删除）临时占用的模块名
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        # 本目录的 impl 始终以 "impl" 存在于 sys.modules（测试文件已 import impl）
        sys.modules["impl"] = impl


# ---------------------------------------------------------------- 独立带权参考

def reference_weighted_cost(grid, start, goal, cost_of) -> float:
    """独立参考：Bellman-Ford 式反复松弛，不复用 impl 的堆逻辑。

    只用于小图（O(V·E)），作为"带权最短代价"的**外部依据**。
    """
    nodes = [(r, c) for r in range(len(grid)) for c in range(len(grid[0]))
             if grid[r][c] != -1]
    dist = {n: float("inf") for n in nodes}
    dist[start] = 0.0
    for _ in range(len(nodes)):
        changed = False
        for n in nodes:
            if dist[n] == float("inf"):
                continue
            for nb in impl.neighbors(grid, n):
                nd = dist[n] + cost_of(nb)
                if nd < dist[nb] - 1e-12:
                    dist[nb] = nd
                    changed = True
        if not changed:
            break
    return dist[goal]


# ---------------------------------------------------------------- BFS 最优性

@pytest.mark.parametrize("seed", [1, 2, 3, 7, 11])
def test_bfs_matches_independent_reference(seed: int) -> None:
    """无权图上 BFS 的步数必须等于独立参考（a-star 实验的 bfs_shortest_cost）。"""
    grid, start, goal = make_grid(seed=seed)
    baseline = _load_astar_baseline()
    ref = baseline.bfs_shortest_cost([[1 if v == -1 else 0 for v in row] for row in grid],
                                     start, goal)
    r = bfs(grid, start, goal)
    assert ref.path_cost is not None
    assert r.cost == float(ref.path_cost), (
        f"BFS 步数 {r.cost} ≠ 独立参考 {ref.path_cost}（seed={seed}）")


def test_bfs_path_is_contiguous_and_legal() -> None:
    """返回的路径必须首尾正确、每步相邻、不穿障碍。"""
    grid, start, goal = make_grid(seed=5)
    r = bfs(grid, start, goal)
    assert r.path[0] == start and r.path[-1] == goal
    for a, b in zip(r.path, r.path[1:]):
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1, f"{a} → {b} 不是相邻步"
        assert grid[b[0]][b[1]] != -1, f"{b} 是障碍"


# ---------------------------------------------------------------- UCS 最优性

@pytest.mark.parametrize("seed", [200, 201, 202])
def test_ucs_matches_independent_weighted_reference(seed: int) -> None:
    """带权图上 UCS 的总代价必须等于独立参考（Bellman-Ford 式松弛）。"""
    grid, start, goal = make_terrain(seed=seed)
    cost_of = lambda n, g=grid: terrain_cost(n, g)
    r = ucs(grid, start, goal, cost_of=cost_of)
    ref = reference_weighted_cost(grid, start, goal, cost_of)
    assert r.cost == pytest.approx(ref), f"UCS {r.cost} ≠ 独立参考 {ref}（seed={seed}）"


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_ucs_equals_bfs_on_unweighted(seed: int) -> None:
    """无权图上 UCS 退化为 BFS：两者代价必须逐个相同。"""
    grid, start, goal = make_grid(seed=seed)
    r_bfs, r_ucs = bfs(grid, start, goal), ucs(grid, start, goal)
    assert r_bfs.cost == r_ucs.cost, f"无权图上两者应等价：{r_bfs.cost} vs {r_ucs.cost}"


# ---------------------------------------------------------------- BFS 在带权图上会次优

def test_bfs_is_not_optimal_on_weighted() -> None:
    """BFS 只保证步数最少；带权图上它找到的路**总代价可能严格更大**。"""
    grid, start, goal = make_terrain(seed=204)
    cost_of = lambda n, g=grid: terrain_cost(n, g)
    r_bfs, r_ucs = bfs(grid, start, goal), ucs(grid, start, goal, cost_of=cost_of)
    bfs_cost = float(sum(cost_of(n) for n in r_bfs.path[1:]))
    assert len(r_bfs.path) <= len(r_ucs.path), "BFS 的步数不该多于 UCS"
    assert bfs_cost > r_ucs.cost, (
        f"这张图上 BFS 应当次优：BFS 代价 {bfs_cost} vs UCS {r_ucs.cost}")


# ---------------------------------------------------------------- DFS 的定位

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_dfs_finds_a_solution_but_may_be_longer(seed: int) -> None:
    """DFS 必须找到解（本实现用 visited 防环），但**不断言最优**。"""
    grid, start, goal = make_grid(seed=seed)
    r_dfs, r_bfs = dfs(grid, start, goal), bfs(grid, start, goal)
    assert r_dfs.path is not None, "有解图上 DFS 必须找到解"
    assert r_dfs.path[0] == start and r_dfs.path[-1] == goal
    assert r_dfs.cost >= r_bfs.cost, "DFS 的步数不该短于 BFS（BFS 是最优的）"


def test_dfs_result_depends_on_neighbor_order() -> None:
    """同一张图、同一个算法，换邻接顺序会给出不同长度的路径。"""
    grid, start, goal = make_grid(seed=42)
    original = impl.DIRECTIONS
    try:
        lengths = []
        for dirs in (((-1, 0), (1, 0), (0, -1), (0, 1)),
                     ((0, 1), (0, -1), (1, 0), (-1, 0)),
                     ((0, -1), (0, 1), (-1, 0), (1, 0))):
            impl.DIRECTIONS = dirs
            lengths.append(len(dfs(grid, start, goal).path))
        assert len(set(lengths)) > 1, f"三种顺序应当给出不同长度，实际 {lengths}"
    finally:
        impl.DIRECTIONS = original


# ---------------------------------------------------------------- 记账口径与边界

def test_all_algorithms_report_frontier_peak() -> None:
    """三个算法都要报边界峰值，且 ≥ 1（取出过一个节点）。"""
    grid, start, goal = make_grid(seed=9)
    for name, fn in (("dfs", dfs), ("bfs", bfs), ("ucs", ucs)):
        r = fn(grid, start, goal)
        assert r.peak_frontier >= 1, f"{name} 的边界峰值异常：{r.peak_frontier}"
        assert r.expanded >= 1, f"{name} 的扩展数异常：{r.expanded}"


def test_start_equals_goal() -> None:
    """起点即终点：三个算法都应返回单点路径、0 代价。"""
    grid = [[0, 0], [0, 0]]
    for name, fn in (("dfs", dfs), ("bfs", bfs), ("ucs", ucs)):
        r = fn(grid, (0, 0), (0, 0))
        assert r.path == [(0, 0)] and r.cost == 0, f"{name} 处理起点即终点有误：{r}"


def test_unreachable_goal_returns_none() -> None:
    """目标被围死：三个算法都返回 path=None、cost=inf。"""
    grid = [[0, -1, 0],
            [-1, -1, 0],
            [0, 0, 0]]
    for name, fn in (("dfs", dfs), ("bfs", bfs), ("ucs", ucs)):
        r = fn(grid, (0, 0), (2, 2))
        assert r.path is None and r.cost == float("inf"), f"{name} 无解处理有误：{r}"


def test_invalid_inputs_raise_value_error() -> None:
    """空图 / 非矩形 / 越界 / 起点在障碍上：统一 ValueError。"""
    good = [[0, 0], [0, 0]]
    cases = [([], (0, 0), (0, 0)),
             ([[0, 0], [0]], (0, 0), (0, 1)),
             (good, (5, 5), (0, 0)),
             ([[-1, 0], [0, 0]], (0, 0), (1, 1))]
    for grid, start, goal in cases:
        for name, fn in (("dfs", dfs), ("bfs", bfs), ("ucs", ucs)):
            with pytest.raises(ValueError):
                fn(grid, start, goal)
