"""参考解 3：三个片段的行为实测。

用法：python3 sol-03-诊断.py

结论（由脚本实测）：
  A（前向检查忘恢复域）→ ❌ 漏解：明明有解的问题报"无解"
  B（邻居表只建单向）  → ❌ 解违反约束（而且求解器自己"以为"成功了）
  C（AC-3 忘入队）      → ⚠️ 不破坏正确性：只是传播不充分（变慢），解依然正确
"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from impl import CSP, SolveResult, backtracking, forward_checking  # noqa: E402


# ---------------------------------------------------------------- 片段 A

def fc_no_restore(csp: CSP, **kw) -> SolveResult:
    """片段 A：前向检查删了邻居域的值，但回退时不恢复。"""
    res = SolveResult(assignment=None)
    assignment, domains = {}, {v: list(d) for v, d in csp.domains.items()}

    def rec() -> bool:
        if len(assignment) == len(csp.variables):
            res.assignment = dict(assignment)
            return True
        var = csp.select_unassigned(assignment, domains, "mrv")
        for value in csp.order_values(var, domains, assignment, "lcv"):
            res.nodes += 1
            if not csp.consistent(var, value, assignment):
                continue
            for other, pred in csp.neighbors[var]:
                if other in assignment:
                    continue
                for ov in list(domains[other]):
                    if not pred(value, ov):
                        domains[other].remove(ov)          # ← 删了，回退时没加回来
                        res.propagations += 1
                if not domains[other]:
                    break
            assignment[var] = value
            if rec():
                return True
            del assignment[var]
            res.backtracks += 1
        return False

    rec()
    return res


# ---------------------------------------------------------------- 片段 B

def build_one_way(csp: CSP) -> CSP:
    """片段 B：邻居表只建单向（只登记 a → b）。"""
    broken = CSP(csp.variables, csp.domains, [])       # 先建空的，再手工塞单向表
    for a, b, ok in csp.all_constraints():
        broken.neighbors[a].append((b, ok))            # ← b 那一侧不建
    return broken


# ---------------------------------------------------------------- 片段 C

def ac3_no_requeue(csp: CSP, **kw) -> SolveResult:
    """片段 C：AC-3 的 revise 删值后，忘记把邻居的弧重新入队。"""
    from collections import deque
    res = SolveResult(assignment=None)
    assignment, domains = {}, {v: list(d) for v, d in csp.domains.items()}

    def revise(xi, xj):
        pred = dict(csp.neighbors[xi])[xj]
        changed = False
        for vi in list(domains[xi]):
            if not any(pred(vi, vj) for vj in domains[xj]):
                domains[xi].remove(vi)
                res.propagations += 1
                changed = True
        return changed

    def rec() -> bool:
        if len(assignment) == len(csp.variables):
            res.assignment = dict(assignment)
            return True
        var = csp.select_unassigned(assignment, domains, "mrv")
        for value in csp.order_values(var, domains, assignment, "lcv"):
            res.nodes += 1
            if not csp.consistent(var, value, assignment):
                continue
            saved = {v: list(d) for v, d in domains.items()}
            domains[var] = [value]
            assignment[var] = value
            queue = deque((o, var) for o, _ in csp.neighbors[var])
            ok = True
            while queue:
                xi, xj = queue.popleft()
                if revise(xi, xj):
                    if not domains[xi]:
                        ok = False
                        break
                    # ← 这里缺少：把 (xk, xi) 重新入队
            if ok and rec():
                return True
            del assignment[var]
            domains.clear()
            domains.update({v: list(d) for v, d in saved.items()})
            res.backtracks += 1
        return False

    rec()
    return res


# ---------------------------------------------------------------- 测试问题

def queens(n: int) -> CSP:
    variables = [f"q{r}" for r in range(n)]
    domains = {v: list(range(n)) for v in variables}
    cons = []
    for i in range(n):
        for j in range(i + 1, n):
            cons.append((variables[i], variables[j],
                         (lambda a, b, i=i, j=j: a != b and abs(a - b) != abs(i - j))))
    return CSP(variables, domains, cons)


def feasible_instance() -> CSP:
    """一个"有解但需要回退"的小问题（四变量图着色）。"""
    return CSP(["x", "y", "z", "w"],
               {"x": [1], "y": [1, 2], "z": [1, 2, 3], "w": [1, 2, 3]},
               [("x", "y", lambda a, b: a != b), ("y", "z", lambda a, b: a != b),
                ("z", "w", lambda a, b: a != b), ("w", "x", lambda a, b: a != b)])


def check_assignment(csp: CSP, assign: dict) -> bool:
    """独立复核：逐条约束检查（不看求解器自报）。"""
    if assign is None:
        return False
    return all(ok(assign[a], assign[b]) for a, b, ok in csp.all_constraints())


def main() -> None:
    print("== 四个实现在同一批问题上的表现 ==")
    instances = [("4 皇后", queens(4)), ("6 皇后", queens(6)), ("四变量着色", feasible_instance())]
    print(f"{'实现':<22} | " + " | ".join(f"{n:>10}" for n, _ in instances))
    print("-" * 66)

    def run(label, fn):
        cells = []
        for name, csp in instances:
            r = fn(csp)
            solvable = r.assignment is not None
            legal = check_assignment(csp, r.assignment) if solvable else True
            cells.append("解✓" if (solvable and legal) else
                         ("**错解**" if solvable else "报无解"))
        print(f"{label:<22} | " + " | ".join(f"{c:>10}" for c in cells))
        return cells

    good = run("正确（前向检查）", lambda c: forward_checking(c))
    a = run("片段 A：不回滚", lambda c: fc_no_restore(c))
    b = run("片段 B：单向邻居表", lambda c: backtracking(build_one_way(c)))
    c_ = run("片段 C：AC-3 不入队", lambda c: ac3_no_requeue(c))

    print("\n结论：")
    # A：漏解
    assert a[1] == "报无解", f"片段 A 应当漏解（6 皇后有解），实际 {a[1]}"
    print("   片段 A（不回滚）：**漏解** —— 6 皇后明明有解却报「无解」。不报错，最难查。")
    # B：错解
    assert "**错解**" in b, f"片段 B 应当产出违反约束的解，实际 {b}"
    print("   片段 B（单向邻居表）：**产出错解** —— 求解器以为成功了，解却违反约束。")
    print("      这也说明「独立复核」不能省：必须自己逐条检查约束，不能信求解器。")
    # C：不破坏正确性
    assert c_[1] == "解✓", f"片段 C 应当仍给出正确解，实际 {c_[1]}"
    print("   片段 C（AC-3 不入队）：**仍然正确** —— 只是传播不充分，搜索树更大（变慢）。")
    print("      区分「传播不充分（慢）」与「漏解（错）」是这道题的关键。")

    # 用节点数量化 C 的代价
    csp = queens(8)
    good_nodes = forward_checking(csp).nodes
    from impl import ac3 as ac3_correct
    correct_ac3 = ac3_correct(csp).nodes
    broken_ac3 = ac3_no_requeue(csp).nodes
    print(f"\n   节点数量化（8 皇后）：正确 AC-3 {correct_ac3} 个、"
          f"不入队的 AC-3 {broken_ac3} 个（多 {broken_ac3 / max(correct_ac3, 1):.1f} 倍）、"
          f"前向检查 {good_nodes} 个")


if __name__ == "__main__":
    main()
