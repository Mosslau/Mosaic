"""对照版：CSP 的两个"没有剪枝"的基线。

搜索族的对照是**基线算法**。CSP 的对照组要回答两个问题：

1. **约束传播值多少**：纯回溯已经用了"赋值时检查相容性"，
   那再往前一步（前向检查 / AC-3）到底省了多少？（见 demo 实验一~三）
2. **回溯本身值多少**：如果**完全不回溯**——只做枚举/随机试——
   完全解不出中等规模的问题（见 demo 实验四）。

`enumerate_all` 是"零剪枝"的极端：按字典序枚举所有赋值组合。
它只适合很小的实例，用来给"搜索树规模"当一个可计算的参照上界。
`random_restart` 是另一个极端：**随机**给所有变量赋值，冲突就整体重来，
不用任何结构化搜索——这是"局部搜索"路线的最朴素形式，八皇后上意外地好用。
"""

import itertools
import random
from typing import Optional

from impl import CSP, SolveResult


def enumerate_all(csp: CSP, limit: int = 5_000_000) -> SolveResult:
    """穷举：按字典序枚举所有组合，返回**第一个**满足全部约束的解。

    注意它连"部分赋值冲突就剪枝"都不做——每次都要把 n 个变量全赋完才检查。
    这是"没有搜索、只有枚举"的下界。
    """
    res = SolveResult(assignment=None)
    vars_ = csp.variables
    space = 1
    for v in vars_:
        space *= len(csp.domains[v])
        if space > limit:
            res.nodes = -space          # 负值表示"空间太大，没跑"
            return res
    for combo in itertools.product(*(csp.domains[v] for v in vars_)):
        res.nodes += 1
        assign = dict(zip(vars_, combo))
        if all(ok(assign[a], assign[b]) for a, b, ok in csp.all_constraints()):
            res.assignment = assign
            return res
    return res


def random_restart(csp: CSP, max_tries: int = 20000,
                   rng: Optional[random.Random] = None) -> SolveResult:
    """随机重启：每次给所有变量随机赋值，全满足就成功，否则整体重来。

    完全不用回溯/传播——这是"局部搜索"路线最朴素的形态。
    在八皇后上它意外地有效（因为解很多）；在数独上基本无效（解很少且约束紧）。
    """
    rng = rng or random.Random(0)
    res = SolveResult(assignment=None)
    for _ in range(max_tries):
        res.nodes += 1
        assign = {v: rng.choice(csp.domains[v]) for v in csp.variables}
        if all(ok(assign[a], assign[b]) for a, b, ok in csp.all_constraints()):
            res.assignment = assign
            return res
    return res


# ---------------------------------------------------------------- 问题构造（供 demo / baseline 共用）

def n_queens(n: int) -> CSP:
    """n 皇后：每行一个变量，取值是列号；两两不同列、不同斜线。"""
    variables = [f"q{r}" for r in range(n)]
    domains = {v: list(range(n)) for v in variables}

    def make_pred():
        def pred(col_a, col_b):
            return col_a != col_b
        return pred

    constraints = []
    for i in range(n):
        for j in range(i + 1, n):
            def pred(ca, cb, i=i, j=j):
                return ca != cb and abs(ca - cb) != abs(i - j)
            constraints.append((variables[i], variables[j], pred))
    return CSP(variables, domains, constraints)


def sudoku(puzzle: list) -> CSP:
    """数独：81 个变量，取值 1–9；同行/同列/同宫不重复。给定的格子域只有 1 个值。

    `puzzle` 是 81 个数字的列表，0 表示空格。
    """
    variables = [f"c{i}" for i in range(81)]
    domains = {f"c{i}": ([puzzle[i]] if puzzle[i] else list(range(1, 10)))
               for i in range(81)}
    constraints = []
    for i in range(81):
        r, c = divmod(i, 9)
        for j in range(i + 1, 81):
            r2, c2 = divmod(j, 9)
            same_unit = (r == r2 or c == c2
                         or (r // 3 == r2 // 3 and c // 3 == c2 // 3))
            if same_unit:
                constraints.append((f"c{i}", f"c{j}",
                                    (lambda a, b: a != b)))
    return CSP(variables, domains, constraints)
