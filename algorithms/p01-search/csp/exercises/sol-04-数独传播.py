"""参考解 4：给数独加"单元传播"（唯一余数法），并与 AC-3 对比。

用法：python3 sol-04-数独传播.py

单元传播有两条规则（人类解数独主要靠它们，比逐个二元约束传播强得多）：
  · **显式唯一**：某格只剩一个候选 → 定下来，并从同单元其他格删掉该值
  · **隐式唯一**：某值在某单元里只出现一次 → 定到那一格（即使该格候选还很多）
两条规则反复应用到不再变化（幂等）。
"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from demo import SUDOKU_HARD  # noqa: E402
from baseline import sudoku  # noqa: E402
from impl import ac3, forward_checking  # noqa: E402


# ---------------------------------------------------------------- 单元

def build_units() -> list:
    """数独的 27 个单元：9 行 + 9 列 + 9 宫。"""
    units = []
    for r in range(9):
        units.append([r * 9 + c for c in range(9)])
    for c in range(9):
        units.append([r * 9 + c for r in range(9)])
    for br in range(3):
        for bc in range(3):
            units.append([(br * 3 + dr) * 9 + (bc * 3 + dc)
                          for dr in range(3) for dc in range(3)])
    return units


UNITS = build_units()


def propagate_units(domains: dict, counters: dict) -> bool:
    """反复应用两条单元规则，直到不再变化。返回 False 表示出现空域（矛盾）。"""
    changed = True
    while changed:
        changed = False
        for unit in UNITS:
            cells = [f"c{i}" for i in unit]

            # 1) 显式唯一：只剩一个候选的格子，定下来并清理同单元
            for cell in cells:
                if len(domains[cell]) == 1:
                    val = domains[cell][0]
                    for other in cells:
                        if other != cell and val in domains[other]:
                            domains[other].remove(val)
                            counters["propagations"] += 1
                            changed = True
                            if not domains[other]:
                                return False

            # 2) 隐式唯一：某值在单元里只可能放在一个格子
            for val in range(1, 10):
                spots = [cell for cell in cells if val in domains[cell]]
                if len(spots) == 1:
                    cell = spots[0]
                    if len(domains[cell]) > 1:
                        domains[cell] = [val]
                        counters["propagations"] += 1
                        changed = True
                        for other in cells:
                            if other != cell and val in domains[other]:
                                domains[other].remove(val)
                                counters["propagations"] += 1
                                if not domains[other]:
                                    return False
    return True


def solve_with_units(csp, var_heuristic: str = "mrv") -> dict:
    """搜索 + 单元传播。"""
    counters = {"nodes": 0, "backtracks": 0, "propagations": 0}
    domains = {v: list(d) for v, d in csp.domains.items()}
    assignment = {}
    if not propagate_units(domains, counters):
        return {"assignment": None, **counters}

    def rec() -> bool:
        if all(len(domains[v]) == 1 for v in csp.variables):
            return True
        var = min((v for v in csp.variables if len(domains[v]) > 1),
                  key=lambda v: len(domains[v]))
        for value in list(domains[var]):
            counters["nodes"] += 1
            saved = {v: list(d) for v, d in domains.items()}
            domains[var] = [value]
            if propagate_units(domains, counters) and rec():
                return True
            domains.clear()
            domains.update({v: list(d) for v, d in saved.items()})
            counters["backtracks"] += 1
        return False

    ok = rec()
    if ok:
        assignment = {v: domains[v][0] for v in csp.variables}
    return {"assignment": assignment, **counters}


def check_sudoku(assignment: dict) -> bool:
    """独立复核：逐行/列/宫检查。"""
    grid = [assignment[f"c{i}"] for i in range(81)]
    if any(not (1 <= v <= 9) for v in grid):
        return False
    for unit in UNITS:
        vals = [grid[i] for i in unit]
        if len(set(vals)) != 9:
            return False
    return True


def main() -> None:
    csp = sudoku(SUDOKU_HARD)
    print("== 三种传播强度的对比（同一个数独题） ==")
    print(f"{'方法':>18} | {'节点':>8} | {'回退':>7} | {'传播':>8} | {'耗时(ms)':>9}")
    print("-" * 62)

    rows = {}
    for name, fn in (("前向检查", lambda: forward_checking(csp)),
                     ("AC-3（弧一致）", lambda: ac3(csp))):
        t0 = time.perf_counter()
        r = fn()
        ms = (time.perf_counter() - t0) * 1000
        assert r.assignment is not None and check_sudoku(r.assignment)
        rows[name] = (r.nodes, r.backtracks, r.propagations, ms)
        print(f"{name:>18} | {r.nodes:>8} | {r.backtracks:>7} | {r.propagations:>8} | {ms:>9.1f}")

    t0 = time.perf_counter()
    res = solve_with_units(csp)
    ms = (time.perf_counter() - t0) * 1000
    assert res["assignment"] is not None, "单元传播应当能解出"
    assert check_sudoku(res["assignment"]), "单元传播给出的解不合法"
    rows["单元传播"] = (res["nodes"], res["backtracks"], res["propagations"], ms)
    print(f"{'单元传播（本解法）':>18} | {res['nodes']:>8} | {res['backtracks']:>7} | "
          f"{res['propagations']:>8} | {ms:>9.1f}")

    # 自检断言
    ac3_nodes = rows["AC-3（弧一致）"][0]
    unit_nodes = rows["单元传播"][0]
    assert unit_nodes <= ac3_nodes, f"单元传播不该比 AC-3 差：{unit_nodes} vs {ac3_nodes}"
    print(f"\n→ 断言通过：单元传播的节点数 {unit_nodes} ≤ AC-3 的 {ac3_nodes}")

    # 幂等性
    counters = {"propagations": 0}
    domains = {v: list(d) for v, d in csp.domains.items()}
    propagate_units(domains, counters)
    snapshot = {v: tuple(d) for v, d in domains.items()}
    counters2 = {"propagations": 0}
    propagate_units(domains, counters2)
    assert snapshot == {v: tuple(d) for v, d in domains.items()}, "传播应当幂等"
    print(f"   幂等性检查通过（第二次传播删了 {counters2['propagations']} 个值，应为 0）")

    print("\n→ 结论：**隐式唯一**是数独最有效的推理规则——")
    print("   它把'某个数字在这个单元里只能放这里'这种全局信息用上了，")
    print("   而逐条二元约束传播看不到这种信息。这也是现代 CP 求解器做**全局约束**（AllDifferent）的原因。")


if __name__ == "__main__":
    main()
