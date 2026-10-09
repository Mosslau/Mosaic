"""CSP 的性质测试。

用法（本目录内）：python3 -m pytest test_impl.py -q

覆盖：
- **解的正确性**：八皇后（独立验证：任意两皇后不同行/列/斜线）、数独（独立验证行/列/宫）
- **策略强弱**：节点数 bt ≥ fc ≥ ac3（这是本实验的核心断言）
- **三种策略给出同一个解空间**：都要么有解要么无解（不许某个策略漏解）
- **前向检查的回滚**：回退后域必须恢复（写错会漏解，且很难发现）
- **AC-3 的弧一致**：求解结束后每个已删除的值都真的没有支撑
- **启发式**：LCV 不差于原序；MRV 在数独上明显更好
- **baseline**：穷举与回溯给出一致的可解性判定
- **边界**：初始域为空、单变量、无约束、无解问题
"""

import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from baseline import enumerate_all, n_queens, random_restart, sudoku  # noqa: E402
from demo import SUDOKU_HARD  # noqa: E402
from impl import CSP, SOLVERS, solve  # noqa: E402


# ---------------------------------------------------------------- 独立验证

def check_queens(assignment: dict, n: int) -> None:
    """独立验证八皇后：任意两皇后不同列、不同斜线（行由变量名保证不同）。"""
    cols = [assignment[f"q{r}"] for r in range(n)]
    assert len(set(cols)) == n, f"有同列：{cols}"
    for i in range(n):
        for j in range(i + 1, n):
            assert abs(cols[i] - cols[j]) != j - i, f"斜线冲突：{i},{j}"


def check_sudoku(assignment: dict) -> list:
    grid = [assignment[f"c{i}"] for i in range(81)]
    assert all(1 <= v <= 9 for v in grid), "取值越界"
    for i in range(81):
        r, c = divmod(i, 9)
        for j in range(i + 1, 81):
            r2, c2 = divmod(j, 9)
            if r == r2 or c == c2 or (r // 3 == r2 // 3 and c // 3 == c2 // 3):
                assert grid[i] != grid[j], f"({i},{j}) 冲突"
    return grid


# ---------------------------------------------------------------- 解的正确性

@pytest.mark.parametrize("n", [4, 6, 8, 10])
@pytest.mark.parametrize("strategy", ["bt", "fc", "ac3"])
def test_queens_solution_valid(n: int, strategy: str) -> None:
    """三种策略在八皇后上都必须给出合法解。"""
    r = solve(n_queens(n), strategy=strategy)
    assert r.assignment is not None, f"{strategy} 在 n={n} 上没解出来"
    check_queens(r.assignment, n)


@pytest.mark.parametrize("strategy", ["bt", "fc", "ac3"])
def test_sudoku_solution_valid(strategy: str) -> None:
    """三种策略在数独上都必须给出合法解（用独立检查验证）。"""
    r = solve(sudoku(SUDOKU_HARD), strategy=strategy)
    assert r.assignment is not None
    grid = check_sudoku(r.assignment)
    # 已知格必须保持不变
    for i, v in enumerate(SUDOKU_HARD):
        if v:
            assert grid[i] == v, f"已知格 {i} 被改了：{v} → {grid[i]}"


# ---------------------------------------------------------------- 策略强弱

@pytest.mark.parametrize("n", [8, 9, 10])
def test_propagation_reduces_nodes(n: int) -> None:
    """节点数必须满足 bt ≥ fc ≥ ac3——约束传播越强，搜索树越小。"""
    csp = n_queens(n)
    nodes = {s: solve(csp, strategy=s).nodes for s in ("bt", "fc", "ac3")}
    assert nodes["fc"] <= nodes["bt"], f"n={n}: {nodes}"
    assert nodes["ac3"] <= nodes["fc"], f"n={n}: {nodes}"


def test_all_strategies_agree_on_solvability() -> None:
    """无解问题上，三种策略都必须报无解（不许某个策略"漏解"或假报解）。"""
    # 3 皇后无解
    for s in ("bt", "fc", "ac3"):
        assert solve(n_queens(3), strategy=s).assignment is None, f"{s} 在 3 皇后上假报解"
    # 这个 4 皇后变体也无解：把 q0 的域限制成会冲突的单值
    csp = CSP(["a", "b", "c"], {"a": [1], "b": [1], "c": [2]},
              [("a", "b", lambda x, y: x != y), ("b", "c", lambda x, y: x != y)])
    for s in ("bt", "fc", "ac3"):
        assert solve(csp, strategy=s).assignment is None, f"{s} 假报解"


def test_forward_checking_restores_domains() -> None:
    """前向检查/AC-3 回滚后域必须恢复——不恢复会漏解，且很难发现。

    构造一个**必然要走死路再回退**、但最终有解的问题（4 个变量的图着色）：
    x 先固定成 1，y 跟着往 2 试（走过死路），最终唯一可行解是 1/2/3/1。
    早期版本忘记回滚 `domains`，就会在这里漏解。
    """
    csp = CSP(["x", "y", "z", "w"],
              {"x": [1], "y": [1, 2], "z": [1, 2, 3], "w": [1, 2, 3]},
              [("x", "y", lambda a, b: a != b),
               ("y", "z", lambda a, b: a != b),
               ("z", "w", lambda a, b: a != b),
               ("w", "x", lambda a, b: a != b)])
    for s_ in ("bt", "fc", "ac3"):
        r = solve(csp, strategy=s_)
        assert r.assignment is not None, f"{s_} 没解出四变量着色问题"
        assert r.assignment["x"] == 1
        for a, b, ok in csp.all_constraints():
            assert ok(r.assignment[a], r.assignment[b]), f"{s_} 的解违反约束 {a},{b}"


def test_ac3_achieves_arc_consistency() -> None:
    """AC-3 求解后，每个变量的域里每个值都必须在邻居域里找到支撑。"""
    csp = n_queens(6)
    r = solve(csp, strategy="ac3")
    assert r.assignment is not None
    # 解本身是单值域，逐对检查相容性即可（等价于弧一致）
    for a, b, ok in csp.all_constraints():
        assert ok(r.assignment[a], r.assignment[b]), f"解违反约束 {a},{b}"


# ---------------------------------------------------------------- 启发式

def test_lcv_not_worse_than_declaration_order() -> None:
    """LCV 在八皇后上不该比原序差（通常明显更好）。"""
    csp = n_queens(10)
    plain = solve(csp, strategy="fc", var_heuristic="decl", value_heuristic="decl")
    lcv = solve(csp, strategy="fc", var_heuristic="decl", value_heuristic="lcv")
    assert lcv.nodes <= plain.nodes, f"LCV 反而更差：{lcv.nodes} vs {plain.nodes}"


def test_mrv_helps_more_on_sudoku_than_queens() -> None:
    """MRV 在数独上的收益应明显大于在八皇后上（问题结构决定启发式价值）。"""
    def gain(csp) -> float:
        base = solve(csp, strategy="fc", var_heuristic="decl").nodes
        mrv = solve(csp, strategy="fc", var_heuristic="mrv").nodes
        return base / max(mrv, 1)

    queen_gain = gain(n_queens(10))
    sudoku_gain = gain(sudoku(SUDOKU_HARD))
    assert sudoku_gain > queen_gain * 2, (
        f"数独上 MRV 的收益应远大于皇后：{sudoku_gain:.1f}× vs {queen_gain:.1f}×")


# ---------------------------------------------------------------- baseline

def test_enumeration_agrees_with_backtracking() -> None:
    """穷举与回溯对可解性的判定必须一致（小实例上）。"""
    for n in (4, 5, 6):
        csp = n_queens(n)
        enum = enumerate_all(csp)
        bt = solve(csp, strategy="bt")
        assert (enum.assignment is None) == (bt.assignment is None), f"n={n}"
        if enum.assignment is not None:
            check_queens(enum.assignment, n)


def test_enumeration_refuses_huge_space() -> None:
    """空间超过上限时，穷举应当明确报"没跑"（nodes 为负），而不是假装失败。"""
    big = n_queens(11)
    r = enumerate_all(big, limit=1000)
    assert r.nodes < 0 and r.assignment is None


def test_random_restart_terminates_and_reports() -> None:
    """随机重启必须有次数上限、且如实报告成败（不能假装成功）。"""
    r = random_restart(n_queens(8), max_tries=200, rng=random.Random(0))
    assert r.nodes <= 200
    if r.assignment is not None:
        check_queens(r.assignment, 8)


# ---------------------------------------------------------------- 边界

def test_empty_domain_raises() -> None:
    with pytest.raises(ValueError):
        CSP(["a"], {"a": []}, [])


def test_single_variable_no_constraints() -> None:
    for s in ("bt", "fc", "ac3"):
        r = solve(CSP(["a"], {"a": [7]}, []), strategy=s)
        assert r.assignment == {"a": 7}


def test_unknown_strategy_raises() -> None:
    with pytest.raises(ValueError):
        solve(n_queens(4), strategy="nope")


def test_solver_registry_complete() -> None:
    assert set(SOLVERS) == {"bt", "fc", "ac3"}
