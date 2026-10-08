"""A* 手写实现的性质测试（pytest）。

用法（仓库根）：.venv/bin/python -m pytest algorithms/p01-search/a-star/ -v
覆盖：
- 多 seed 自洽性：10 张随机图上 A*（两种平局策略）与 Dijkstra 的 path_cost 全相等
  （**注意**：该基线复用 impl.solve，只能证明自洽；独立性由下一项保证）
- 独立参考差分：另 8 张随机图上 A*（两种平局策略）与独立 BFS 参考的最短步数全相等
  ——这是最优性断言的**外部**依据（baseline.bfs_shortest_cost 不复用 impl.py）
- 无解判定：终点被围死时 path=None、path_cost=inf（独立参考同为 None）
- 退化输入：起点即终点时 path=[start]、path_cost=0、只扩展 1 个节点
- 输入校验：起终点越界或落在障碍上抛 ValueError；非法 tie_break 抛 ValueError；
  weight < 1 / 非有限数抛 ValueError；空网格 / 空行 / 锯齿数组抛 ValueError
- 加权 A*：w=1 即标准 A*（最优性由多 seed 覆盖）；w>1 只断言有解，不断言最优
- 已知局限回归：closed 不重开时，可采纳但不一致的 h 可静默次优（契约边界）
"""

import math

import pytest

from baseline import bfs_shortest_cost, dijkstra
from demo import GOAL, START, make_empty_grid, make_grid
from impl import solve


@pytest.mark.parametrize("seed", range(10))
def test_optimality_across_seeds(seed: int) -> None:
    """性质测试：多张随机图上，两种平局策略的 A* 都必须与 Dijkstra 同代价。

    口径提醒：`dijkstra` 复用 `solve`（h ≡ 0），本用例证明的是"同一份堆逻辑在
    有/无启发式下自洽"，**不构成对最优性的独立验证**——外部验证见
    `test_matches_independent_bfs_reference`。
    """
    grid, start, goal = make_grid(seed=seed)
    optimal = dijkstra(grid, start, goal).path_cost
    for tie_break in ("insertion", "large_g"):
        r = solve(grid, start, goal, tie_break=tie_break)
        assert r.path is not None, f"seed={seed} {tie_break}: 应有解"
        assert r.path_cost == optimal, (
            f"seed={seed} {tie_break}: A* 代价 {r.path_cost} ≠ 最优 {optimal}"
        )
        assert r.path[0] == start and r.path[-1] == goal
        # 路径相邻步必须是四方向单步（路径合法性）
        for (r1, c1), (r2, c2) in zip(r.path, r.path[1:]):
            assert abs(r1 - r2) + abs(c1 - c2) == 1


@pytest.mark.parametrize("seed", range(10, 18))
def test_matches_independent_bfs_reference(seed: int) -> None:
    """差分测试：两种平局策略的 A* 与**独立** BFS 参考的最短步数必须相等。

    与 `test_optimality_across_seeds` 的区别是验证的独立性：Dijkstra 基线复用
    `impl.solve`，两者不可能出现分歧；BFS 参考不共享 impl.py 的任何代码
    （不共享堆、平局策略、松弛逻辑），因此能把"最优性"从自证变成外部对照。
    """
    grid, start, goal = make_grid(seed=seed)
    reference = bfs_shortest_cost(grid, start, goal)
    assert reference.path_cost is not None, f"seed={seed}: 参考实现应判定有解"
    for tie_break in ("insertion", "large_g"):
        r = solve(grid, start, goal, tie_break=tie_break)
        assert r.path is not None, f"seed={seed} {tie_break}: 应有解"
        assert r.path_cost == reference.path_cost, (
            f"seed={seed} {tie_break}: A* 代价 {r.path_cost} "
            f"≠ 独立 BFS 参考 {reference.path_cost}"
        )


def test_malformed_grid_raises_value_error() -> None:
    """空网格 / 空行 / 锯齿数组都应抛 ValueError（与其他入参同一口径）。

    修前这三类入参会抛 IndexError（按 grid[0] 取列宽所致），口径与"越界 start 抛
    ValueError"不一致；本用例把口径固定下来。
    """
    malformed = [
        ([], (0, 0), (0, 0)),                # 空网格
        ([[]], (0, 0), (0, 0)),              # 单行零列
        ([[0, 0, 0], [0]], (1, 0), (0, 2)),  # 锯齿（第 1 行更短，起点在短行）
        ([[0], [0, 0, 0]], (1, 2), (0, 0)),  # 锯齿（第 0 行更短，起点在长行）
    ]
    for grid, start, goal in malformed:
        with pytest.raises(ValueError):
            solve(grid, start, goal)


def test_empty_grid_raises_value_error_before_position_check() -> None:
    """空网格应在起终点校验之前就报 ValueError（而不是 IndexError）。"""
    with pytest.raises(ValueError, match="grid 为空"):
        solve([], (0, 0), (0, 0))


def test_bfs_reference_agrees_on_unreachable_goal() -> None:
    """独立参考与 A* 在无解图上必须同为不可达（避免只在有解图上做差分）。"""
    grid = make_empty_grid()
    r, c = GOAL
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        grid[r + dr][c + dc] = 1
    reference = bfs_shortest_cost(grid, START, GOAL)
    assert reference.path_cost is None
    assert solve(grid, START, GOAL).path is None


def test_large_g_reaches_lower_bound_on_empty_grid() -> None:
    """无障碍地图：large_g 平局直冲终点，扩展数 = 路径节点数（理论下界）。"""
    grid = make_empty_grid()
    r = solve(grid, START, GOAL, tie_break="large_g")
    assert r.nodes_expanded == len(r.path) == 37  # (1,1)→(19,19) 曼哈顿 36 步 + 起点


def test_start_equals_goal() -> None:
    """退化输入：起点即终点时路径只有起点、代价 0、只扩展 1 个节点。"""
    grid = make_empty_grid()
    r = solve(grid, START, START)
    assert r.path == [START]
    assert r.path_cost == 0
    assert r.nodes_expanded == 1


def test_no_solution_returns_none() -> None:
    """终点被障碍围死：path=None、path_cost=inf。"""
    grid = make_empty_grid()
    r, c = GOAL
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):  # 围死终点的四个邻居
        grid[r + dr][c + dc] = 1
    result = solve(grid, START, GOAL)
    assert result.path is None
    assert math.isinf(result.path_cost)


def test_input_validation() -> None:
    """越界 / 障碍上的起终点、非法平局策略，都应抛 ValueError。"""
    grid = make_empty_grid()
    grid[5][5] = 1  # 造一个内部障碍
    with pytest.raises(ValueError):
        solve(grid, (0, 0), GOAL)          # start 在边界墙上
    with pytest.raises(ValueError):
        solve(grid, START, (5, 5))         # goal 是障碍
    with pytest.raises(ValueError):
        solve(grid, (99, 99), GOAL)        # start 越界
    with pytest.raises(ValueError):
        solve(grid, START, GOAL, tie_break="random")  # 非法策略
    for bad_weight in (0.5, 0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            solve(grid, START, GOAL, weight=bad_weight)  # w<1 或非有限数


def test_weight_w1_matches_default() -> None:
    """weight=1.0 必须与默认调用逐点一致（加权参数不改变标准 A* 行为）。"""
    grid, start, goal = make_grid()
    r_default = solve(grid, start, goal)
    r_w1 = solve(grid, start, goal, weight=1.0)
    assert r_w1.path_cost == r_default.path_cost
    assert r_w1.nodes_expanded == r_default.nodes_expanded


def test_weighted_astar_still_finds_a_path() -> None:
    """w>1 不保证最优，但在连通图上必须仍有解、且代价不优于最优值。"""
    grid, start, goal = make_grid()
    optimal = dijkstra(grid, start, goal).path_cost
    for w in (2.0, 5.0):
        r = solve(grid, start, goal, weight=w)
        assert r.path is not None
        assert r.path_cost >= optimal  # 次优只会更贵，不会更便宜


def test_known_limitation_admissible_but_inconsistent_heuristic() -> None:
    """已知局限回归：h 可采纳但不一致时，closed 不重开的实现可能静默次优。

    2×5 全通路网格，最优路径 (0,0)→(0,1)→(0,2)→(0,3)→(0,4)，代价 4。
    h((0,1))=3（紧），其余为 0：处处可采纳，但在 (0,1) 处
    h = 3 > c + h((0,2)) = 1，不一致。
    large_g 会让绕路到达的 (0,2)（g=f=4）先于 (0,1)（g=1、f=4）出堆并被封闭，
    之后 (0,1) 无法把它的 g 松弛回 2，返回次优代价 6。
    若将来改为支持重开节点的实现，本用例的断言应同步改为 h 可采纳即最优。
    """
    grid = [[0] * 5 for _ in range(2)]
    start, goal = (0, 0), (0, 4)

    def h(node: tuple[int, int], _goal: tuple[int, int]) -> int:
        return 3 if node == (0, 1) else 0

    optimal = solve(grid, start, goal, heuristic=h)  # insertion 的弹序恰好躲过
    assert optimal.path_cost == 4
    result = solve(grid, start, goal, heuristic=h, tie_break="large_g")
    assert result.path_cost == 6  # 已知局限：契约要求 h 一致，而非仅可采纳
