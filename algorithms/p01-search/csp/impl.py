"""约束满足问题（CSP）：回溯搜索 + 约束传播 —— 手写实现（搜索求解器）

与前面几个搜索实验的根本差别：**这里没有"图"，只有"约束"**。

    A* / minimax / MCTS / CFR 都在一张图（或博弈树）上找路径；
    CSP 的问题是：给一堆变量各挑一个值，使**所有约束同时满足**。
    "状态空间"不是给定的图，而是**约束定义出来的组合空间**。

经典例子：八皇后（任意两个皇后不同行同列同斜线）、数独（行/列/宫各不重复）、排课、地图着色。
暴力枚举的组合数是天文数字，但 CSP 的三个标准手段能把它们砍到可解：

  1. **回溯（backtracking）**：一次给一个变量赋值，冲突就退回换值
  2. **约束传播（forward checking / AC-3）**：赋值后立刻删掉邻居域里不可能的值
  3. **变量/取值排序（MRV / 度启发 / LCV）**：先挑"最受限制"的变量、先试"最不添乱"的值

本目录的形态由"约束求解"决定，没有 fit/predict：
- impl.py    CSP 数据结构 + 三种求解器（纯回溯 / 前向检查 / 维护弧一致 AC-3）
- baseline.py 对照版：**穷举**（不带任何剪枝的暴力搜索）+ 随机重排重启
- demo.py    八皇后与数独上量化"每种手段省了多少"

接口约定：
    CSP(variables, domains, constraints)
        variables:  变量名序列
        domains:    {变量: [可能取值]}
        constraints: [(变量A, 变量B, 判定函数)] —— 二元约束，判定函数返回 True 表示相容
    三种求解器都返回 SolveResult(assignment, nodes, backtracks, propagations)
"""

import itertools
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

Value = object


@dataclass
class SolveResult:
    """三种求解器共用的返回类型，便于并排比较。"""

    assignment: Optional[dict]      # 解（变量 → 取值）；无解为 None
    nodes: int = 0                  # 搜索树里"尝试赋值"的次数
    backtracks: int = 0             # 回退次数
    propagations: int = 0           # 约束传播时"删掉一个值"的次数
    peak_depth: int = 0             # 最大递归深度（内存代理指标）


class CSP:
    """约束满足问题。

    用法：
        csp = CSP(["x0","x1"], {"x0":[1,2], "x1":[1,2]}, [("x0","x1", lambda a,b: a!=b)])
        result = csp.solve(strategy="fc")
    """

    def __init__(self, variables, domains: dict, constraints: list) -> None:
        self.variables = list(variables)
        self.domains = {v: list(domains[v]) for v in self.variables}
        # 邻居表：变量 → [(另一个变量, 判定函数)]
        self.neighbors: dict = {v: [] for v in self.variables}
        for a, b, ok in constraints:
            self.neighbors[a].append((b, ok))
            if b != a:
                self.neighbors[b].append((a, (lambda f: (lambda y, x: f(x, y)))(ok)))
        for v in self.variables:
            if not self.domains[v]:
                raise ValueError(f"变量 {v} 的初始域为空：问题无解")

    # ---------------------------------------------------------------- 工具

    def all_constraints(self) -> list:
        """把邻居表还原成 (A, B, 判定) 列表（每个二元约束只留一份）。"""
        seen, out = set(), []
        for a in self.variables:
            for b, ok in self.neighbors[a]:
                key = (min(a, b), max(a, b))
                if key in seen:
                    continue
                seen.add(key)
                out.append((a, b, ok))
        return out

    def consistent(self, var: str, value, assignment: dict) -> bool:
        """把 var=value 放进当前部分赋值后，是否与所有**已赋值**邻居相容。"""
        for other, ok in self.neighbors[var]:
            if other in assignment and not ok(value, assignment[other]):
                return False
        return True

    def select_unassigned(self, assignment: dict, domains: dict, heuristic: str):
        """选下一个变量。MRV = 域最小的优先（最受限制的变量先定）。"""
        remaining = [v for v in self.variables if v not in assignment]
        if heuristic == "mrv":
            return min(remaining, key=lambda v: (len(domains[v]), -len(self.neighbors[v])))
        if heuristic == "degree":
            return max(remaining, key=lambda v: len(self.neighbors[v]))
        return remaining[0]                      # 声明顺序（最朴素）

    def order_values(self, var: str, domains: dict, assignment: dict, heuristic: str):
        """排序候选取值。LCV = 先试"约束邻居最少"的值（最不添乱）。"""
        values = list(domains[var])
        if heuristic != "lcv":
            return values

        def conflicts(value) -> int:
            total = 0
            for other, ok in self.neighbors[var]:
                if other in assignment:
                    continue
                total += sum(1 for ov in domains[other] if not ok(value, ov))
            return total

        return sorted(values, key=conflicts)


# ---------------------------------------------------------------- 三种求解器

def backtracking(csp: CSP, var_heuristic: str = "mrv",
                 value_heuristic: str = "lcv") -> SolveResult:
    """纯回溯：赋值 + 相容性检查，**不做任何前向传播**。"""
    res = SolveResult(assignment=None)
    assignment: dict = {}
    domains = {v: list(d) for v, d in csp.domains.items()}

    def rec() -> bool:
        res.peak_depth = max(res.peak_depth, len(assignment))
        if len(assignment) == len(csp.variables):
            res.assignment = dict(assignment)
            return True
        var = csp.select_unassigned(assignment, domains, var_heuristic)
        for value in csp.order_values(var, domains, assignment, value_heuristic):
            res.nodes += 1
            if csp.consistent(var, value, assignment):
                assignment[var] = value
                if rec():
                    return True
                del assignment[var]
                res.backtracks += 1
        return False

    rec()
    return res


def forward_checking(csp: CSP, var_heuristic: str = "mrv",
                     value_heuristic: str = "lcv") -> SolveResult:
    """前向检查：赋值后**立刻删掉未赋值邻居域里不相容的值**；某域空了就回退。

    比纯回溯强在哪：纯回溯要等到"下次给那个变量赋值"才发现冲突，
    前向检查**提前一步**发现死路。
    """
    res = SolveResult(assignment=None)
    assignment: dict = {}
    domains = {v: list(d) for v, d in csp.domains.items()}

    def rec() -> bool:
        res.peak_depth = max(res.peak_depth, len(assignment))
        if len(assignment) == len(csp.variables):
            res.assignment = dict(assignment)
            return True
        var = csp.select_unassigned(assignment, domains, var_heuristic)
        for value in csp.order_values(var, domains, assignment, value_heuristic):
            res.nodes += 1
            if not csp.consistent(var, value, assignment):
                continue
            # 前向检查：尝试从邻居域里删值，记录删了什么以便回滚
            removed = []
            ok = True
            for other, pred in csp.neighbors[var]:
                if other in assignment:
                    continue
                for ov in list(domains[other]):
                    if not pred(value, ov):
                        domains[other].remove(ov)
                        removed.append((other, ov))
                        res.propagations += 1
                if not domains[other]:
                    ok = False
                    break
            if ok:
                assignment[var] = value
                if rec():
                    return True
                del assignment[var]
            for other, ov in removed:                 # 回滚
                domains[other].append(ov)
            res.backtracks += 1
        return False

    rec()
    return res


def ac3(csp: CSP, var_heuristic: str = "mrv",
        value_heuristic: str = "lcv") -> SolveResult:
    """维护弧一致（AC-3）：每次赋值后反复传播，直到**所有弧都一致**。

    与 forward checking 的差别：FC 只看"被赋值变量的直接邻居"，
    AC-3 会**连锁传播**（邻居域变小后，可能让更远的变量域也能删值）。
    代价是每次传播更贵。

    弧 (Xi, Xj) 一致 = Xi 域里每个值都能在 Xj 域里找到至少一个相容值。
    """
    res = SolveResult(assignment=None)
    assignment: dict = {}
    domains = {v: list(d) for v, d in csp.domains.items()}

    def revise(xi: str, xj: str) -> bool:
        """把 Xi 域里"在 Xj 找不到支撑"的值删掉；有任何删除返回 True。"""
        pred = dict(csp.neighbors[xi])[xj]
        changed = False
        for vi in list(domains[xi]):
            if not any(pred(vi, vj) for vj in domains[xj]):
                domains[xi].remove(vi)
                res.propagations += 1
                changed = True
        return changed

    def propagate(queue: deque) -> bool:
        while queue:
            xi, xj = queue.popleft()
            if revise(xi, xj):
                if not domains[xi]:
                    return False
                for xk, _ in csp.neighbors[xi]:
                    if xk != xj:
                        queue.append((xk, xi))
        return True

    def rec() -> bool:
        res.peak_depth = max(res.peak_depth, len(assignment))
        if len(assignment) == len(csp.variables):
            res.assignment = dict(assignment)
            return True
        var = csp.select_unassigned(assignment, domains, var_heuristic)
        for value in csp.order_values(var, domains, assignment, value_heuristic):
            res.nodes += 1
            if not csp.consistent(var, value, assignment):
                continue
            saved = {v: list(d) for v, d in domains.items()}
            domains[var] = [value]                       # 赋值 = 把域缩成单值
            assignment[var] = value
            queue = deque((other, var) for other, _ in csp.neighbors[var])
            if propagate(queue) and rec():
                return True
            del assignment[var]
            domains.clear()
            domains.update({v: list(d) for v, d in saved.items()})
            res.backtracks += 1
        return False

    rec()
    return res


#: 统一入口
SOLVERS: dict = {
    "bt": backtracking,          # 纯回溯
    "fc": forward_checking,      # + 前向检查
    "ac3": ac3,                  # + 维护弧一致
}


def solve(csp: CSP, strategy: str = "fc", var_heuristic: str = "mrv",
          value_heuristic: str = "lcv") -> SolveResult:
    if strategy not in SOLVERS:
        raise ValueError(f"未知策略 {strategy}，可选：{sorted(SOLVERS)}")
    return SOLVERS[strategy](csp, var_heuristic=var_heuristic,
                             value_heuristic=value_heuristic)


def describe() -> dict:
    """三种策略与两种启发式的一句话说明（供 README / demo 直接引用）。"""
    return {
        "bt": "纯回溯：赋值 + 相容性检查，冲突了才退",
        "fc": "前向检查：赋值后立刻删掉邻居域里不相容的值",
        "ac3": "维护弧一致：赋值后连锁传播，直到所有弧都一致",
        "mrv": "变量启发：域最小的变量先赋值（最受限制优先）",
        "degree": "变量启发：邻居最多的变量先赋值",
        "lcv": "取值启发：先试「会对邻居造成最少删值」的值",
    }


if __name__ == "__main__":
    raise SystemExit("本文件是求解库，跑实验请执行：python3 demo.py")
