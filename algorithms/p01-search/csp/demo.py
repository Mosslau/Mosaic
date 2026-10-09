"""CSP demo：八皇后与数独上，量化"每种手段省了多少"。

四组实验：
  1. **三种求解策略对比**（八皇后 n=8..12）：纯回溯 / 前向检查 / 维护弧一致
  2. **启发式值多少**（八皇后 n=10）：变量排序（声明序 / MRV / 度）与取值排序（原序 / LCV）
  3. **现实规模**（数独）：三种策略在一个"世界最难"级别的题目上的表现
  4. **"不回溯"能走多远**：随机重启 vs 穷举 vs 回溯（说明为什么搜索必须有结构）

运行：cd algorithms/p01-search/csp && python3 demo.py
依赖：只用标准库
"""

import itertools
import random
import time

from baseline import enumerate_all, n_queens, random_restart, sudoku
from impl import SOLVERS, CSP, describe, solve

# 一个需要较多回溯的数独（"AI Escargot" 级别附近；0 表示空格）
SUDOKU_HARD = [
    8, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 3, 6, 0, 0, 0, 0, 0,
    0, 7, 0, 0, 9, 0, 2, 0, 0,
    0, 5, 0, 0, 0, 7, 0, 0, 0,
    0, 0, 0, 0, 4, 5, 7, 0, 0,
    0, 0, 0, 1, 0, 0, 0, 3, 0,
    0, 0, 1, 0, 0, 0, 0, 6, 8,
    0, 0, 8, 5, 0, 0, 0, 1, 0,
    0, 9, 0, 0, 0, 0, 4, 0, 0,
]


# ---------------------------------------------------------------- 实验一

def experiment_strategies(sizes=(8, 9, 10, 11, 12)) -> list:
    print("== 实验一：三种求解策略对比（n 皇后） ==")
    print(f"{'n':>3} | {'策略':>4} | {'节点':>8} | {'回退':>7} | {'传播':>8} | {'耗时(ms)':>9}")
    print("-" * 56)
    rows = []
    for n in sizes:
        csp = n_queens(n)
        for strategy in ("bt", "fc", "ac3"):
            t0 = time.perf_counter()
            r = solve(csp, strategy=strategy)
            ms = (time.perf_counter() - t0) * 1000
            rows.append((n, strategy, r.nodes, r.backtracks, r.propagations, ms))
            assert r.assignment is not None, f"{n} 皇后应当有解（{strategy}）"
            print(f"{n:>3} | {strategy:>4} | {r.nodes:>8} | {r.backtracks:>7} | "
                  f"{r.propagations:>8} | {ms:>9.1f}")
    # 断言：传播越强，节点越少（这是本实验的核心结论）
    for n in sizes:
        by = {s: next(r[2] for r in rows if r[0] == n and r[1] == s) for s in ("bt", "fc", "ac3")}
        assert by["fc"] <= by["bt"], f"n={n}: 前向检查不该比纯回溯差 {by}"
        assert by["ac3"] <= by["fc"], f"n={n}: 维护弧一致不该比前向检查差 {by}"
    print("\n→ 每一档都是 节点(bt) ≥ 节点(fc) ≥ 节点(ac3)：")
    print("   **约束传播越强，搜索树越小**——这就是 CSP 的核心思路。")
    return rows


# ---------------------------------------------------------------- 实验二

def experiment_heuristics(n: int = 10) -> dict:
    """同一个启发式在**两个不同结构**的问题上各值多少。

    为什么要两个：n 皇后每行的域大小完全相同（都是 n），MRV 无从发挥；
    数独里每个空格的候选数差别很大（1~9 个），MRV 才是主力。
    **启发式的价值跟问题结构强相关**——只在一个问题上试，会得出错误的一般结论。
    """
    print(f"\n== 实验二：启发式值多少（两个问题对照，全部用前向检查） ==")
    problems = {"n 皇后（n=10，各行域相同）": n_queens(n),
                "数独（各格候选数差别大）": sudoku(SUDOKU_HARD)}
    out = {}
    for pname, csp in problems.items():
        print(f"\n  【{pname}】")
        print(f"  {'变量排序':>8} | {'取值排序':>8} | {'节点':>9} | {'耗时(ms)':>9}")
        print("  " + "-" * 46)
        rows = []
        for vh in ("decl", "mrv"):
            for valh in ("decl", "lcv"):
                t0 = time.perf_counter()
                r = solve(csp, strategy="fc", var_heuristic=vh, value_heuristic=valh)
                ms = (time.perf_counter() - t0) * 1000
                rows.append((vh, valh, r.nodes, ms))
                print(f"  {vh:>8} | {valh:>8} | {r.nodes:>9} | {ms:>9.1f}")
        base = next(r for r in rows if r[0] == "decl" and r[1] == "decl")
        best = min(rows, key=lambda r: r[2])
        out[pname] = {"rows": rows, "base": base, "best": best,
                      "mrv_gain": base[2] / max(next(r for r in rows if r[0] == "mrv"
                                                     and r[1] == "decl")[2], 1),
                      "lcv_gain": base[2] / max(next(r for r in rows if r[0] == "decl"
                                                     and r[1] == "lcv")[2], 1)}
    print("\n→ 同一套启发式，两个问题上效果完全不同：")
    for pname, d in out.items():
        print(f"   · {pname}：MRV 单独把节点降 {d['mrv_gain']:.1f}×、LCV 降 {d['lcv_gain']:.1f}×")
    print("   结论：**启发式的价值取决于问题结构**——")
    print("   n 皇后每行域都一样大，MRV 没得挑；数独的候选数差别悬殊，MRV 才是主力。")
    print("   只在一个问题上做实验，会得出错误的一般结论。")
    return out


# ---------------------------------------------------------------- 实验三

def experiment_sudoku() -> dict:
    print("\n== 实验三：现实规模（数独，世界最难级别） ==")
    csp = sudoku(SUDOKU_HARD)
    given = sum(1 for x in SUDOKU_HARD if x)
    print(f"  题目：{given} 个已知格、{81 - given} 个空格")
    print(f"{'策略':>4} | {'节点':>9} | {'回退':>8} | {'传播':>9} | {'耗时(ms)':>9}")
    print("-" * 52)
    out = {}
    for strategy in ("bt", "fc", "ac3"):
        t0 = time.perf_counter()
        r = solve(csp, strategy=strategy)
        ms = (time.perf_counter() - t0) * 1000
        out[strategy] = r
        assert r.assignment is not None, f"数独应当有解（{strategy}）"
        print(f"{strategy:>4} | {r.nodes:>9} | {r.backtracks:>8} | "
              f"{r.propagations:>9} | {ms:>9.1f}")
    # 校验解真的合法（独立于求解器自己）
    grid = [out["ac3"].assignment[f"c{i}"] for i in range(81)]
    assert all(1 <= v <= 9 for v in grid)
    for i in range(81):
        r_, c_ = divmod(i, 9)
        for j in range(i + 1, 81):
            r2, c2 = divmod(j, 9)
            if r_ == r2 or c_ == c2 or (r_ // 3 == r2 // 3 and c_ // 3 == c2 // 3):
                assert grid[i] != grid[j], "解违反了数独约束"
    print("\n→ 解已用**独立的合法性检查**验证（不依赖求解器自报）。")
    print("   AC-3 相对纯回溯把节点数砍掉一个量级以上——数独是'约束传播'的最佳舞台。")
    return out


# ---------------------------------------------------------------- 实验四

def experiment_no_search() -> dict:
    print("\n== 实验四：'不回溯'能走多远 ==")
    print("  对照三条路线：随机重启（无结构）、穷举（无剪枝）、回溯（有结构）")
    print(f"{'问题':>14} | {'随机重启':>18} | {'穷举':>18} | {'回溯(ac3)':>14}")
    print("-" * 74)
    out = {}
    for name, csp in (("8 皇后", n_queens(8)), ("10 皇后", n_queens(10))):
        rr = random_restart(csp, max_tries=20000, rng=random.Random(0))
        en = enumerate_all(csp, limit=2_000_000)
        ac = solve(csp, strategy="ac3")
        rr_txt = f"{'解出' if rr.assignment else '失败'}（{rr.nodes} 次尝试）"
        en_txt = "空间过大未跑" if en.nodes < 0 else (
            f"{'解出' if en.assignment else '失败'}（{en.nodes} 次）")
        out[name] = (rr, en, ac)
        print(f"{name:>14} | {rr_txt:>18} | {en_txt:>18} | "
              f"{'解出（' + str(ac.nodes) + ' 节点）':>14}")
    print("\n→ 三条路线的分野：")
    print("   · **随机重启**：完全不用结构，靠反复撞运气——小解空间里能撞上，紧约束下基本无效；")
    print("   · **穷举**：组合数一涨就爆炸（10 皇后是 10^10 量级），连跑都跑不动；")
    print("   · **回溯 + 传播**：把'部分赋值冲突'提前剪掉，才能在现实规模上求解。")
    rr8 = out["8 皇后"][0]
    assert rr8.assignment is None or rr8.nodes > 100, "随机重启即便成功也应耗很多次尝试"
    return out


def main() -> None:
    print("三种策略：")
    for k in ("bt", "fc", "ac3"):
        print(f"  {k:>4}：{describe()[k]}")
    print("两种启发式：")
    for k in ("mrv", "lcv"):
        print(f"  {k:>4}：{describe()[k]}")
    print()
    experiment_strategies()
    experiment_heuristics()
    experiment_sudoku()
    experiment_no_search()


if __name__ == "__main__":
    main()
