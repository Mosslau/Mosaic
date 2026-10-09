"""参考解 5：考试排考（资源受限 + 硬软约束）。

用法：python3 sol-05-迁移.py

场景：6 门课、3 个时间段、2 间教室；教室有容量；有冲突的课程对不能同时段。

建模的关键取舍：**变量 = 课程，取值 = (时间段, 教室) 组合**。
  · 容量约束 → 直接按课程人数过滤取值域（天然满足，不用进约束表）
  · "冲突课程不能同时段" → 约束作用在**时间段**上，而不是完整取值上
    （这是个容易写错的地方：写成"取值不相等"就变成"不能同教室同时段"，语义偏了）
"""

import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from impl import CSP, solve  # noqa: E402

COURSES = ("算法", "数据库", "网络", "操作系统", "编译原理", "机器学习")
SIZE = {"算法": 40, "数据库": 60, "网络": 50, "操作系统": 45, "编译原理": 30, "机器学习": 70}
SLOTS = ("周一1", "周一2", "周二1")
ROOMS = {"A101": 80, "B202": 45}

#: 有学生同时选了两门 → 不能排同一时段
# 冲突图：6 门课排成一个环（相邻不能同时段）。环是 2 色可染的，
# 所以 3 个时段**一定够**（有解），但每门课还要挑教室 → 仍有多种可行解。
# 试过加"跨边"让它更紧：连加三条都不小心做成了不可 3 着色的图（实测才发现），
# 于是这里老实选一个**可解**的构造——**"实例可解"必须实测确认，不能靠推演**。
N = len(COURSES)
CONFLICTS = [(COURSES[i], COURSES[(i + 1) % N]) for i in range(N)]

#: 软约束：希望这几门课排在一起（同一时段）
PREFER_SAME_SLOT = [("算法", "编译原理"), ("数据库", "机器学习")]


def build_csp() -> CSP:
    """变量 = 课程；取值 = 容量够的 (时段, 教室)。"""
    domains = {}
    for c in COURSES:
        domains[c] = [(s, r) for s in SLOTS for r in ROOMS if ROOMS[r] >= SIZE[c]]

    constraints = []
    # 硬约束 1：同一时段同一教室只能排一门课
    for i, a in enumerate(COURSES):
        for b in COURSES[i + 1:]:
            constraints.append((a, b, lambda x, y: x != y))
    # 硬约束 2：冲突课程不能同时段（注意：比较的是**时段**，不是完整取值）
    for a, b in CONFLICTS:
        constraints.append((a, b, lambda x, y: x[0] != y[0]))
    return CSP(list(COURSES), domains, constraints)


def hard_ok(assignment: dict) -> bool:
    """独立复核硬约束。"""
    for i, a in enumerate(COURSES):
        for b in COURSES[i + 1:]:
            if assignment[a] == assignment[b]:
                return False                     # 同时段同教室
    for a, b in CONFLICTS:
        if assignment[a][0] == assignment[b][0]:
            return False                         # 冲突课程同时段
    for c in COURSES:
        slot, room = assignment[c]
        if ROOMS[room] < SIZE[c]:
            return False                         # 容量不够
    return True


def soft_cost(assignment: dict) -> float:
    """软约束代价：偏好同段的课没排在一起则惩罚；时段分布不均也惩罚。"""
    cost = 0.0
    for a, b in PREFER_SAME_SLOT:
        if assignment[a][0] != assignment[b][0]:
            cost += 1.0
    per_slot = {s: 0 for s in SLOTS}
    for c in COURSES:
        per_slot[assignment[c][0]] += 1
    cost += 0.3 * (max(per_slot.values()) - min(per_slot.values()))
    return cost


def improve(assignment: dict, tries: int = 3000, rng: random.Random = None) -> tuple:
    """局部搜索：单点 + 2-opt，只在硬约束成立且代价不升时接受。"""
    rng = rng or random.Random(3)
    best = dict(assignment)
    best_cost = soft_cost(best)
    acc1 = acc2 = 0
    domains = build_csp().domains

    for _ in range(tries):
        if rng.random() < 0.5:
            c = rng.choice(COURSES)
            old = best[c]
            best[c] = rng.choice(domains[c])
            if hard_ok(best) and soft_cost(best) <= best_cost:
                best_cost = soft_cost(best)
                acc1 += 1
            else:
                best[c] = old
        else:
            c1, c2 = rng.sample(COURSES, 2)
            v1, v2 = best[c1], best[c2]
            best[c1], best[c2] = v2, v1
            if hard_ok(best) and soft_cost(best) <= best_cost:
                best_cost = soft_cost(best)
                acc2 += 1
            else:
                best[c1], best[c2] = v1, v2
    return best, best_cost, acc1, acc2


def enumerate_feasible(csp) -> list:
    """小实例上**枚举全部可行解**（6 门课 × 6 种取值 = 46656 组合，可以暴力）。

    为什么值得做：局部搜索只能保证"局部最优"，不能保证"全局最优"。
    在小实例上把全局最优算出来，才能判断"局部搜索没改进"到底是
    「陷在局部最优」还是「已经到最优了」——这两件事的结论完全相反。
    """
    import itertools
    out = []
    for combo in itertools.product(*(csp.domains[c] for c in COURSES)):
        a = dict(zip(COURSES, combo))
        if hard_ok(a):
            out.append((soft_cost(a), a))
    return sorted(out, key=lambda x: x[0])


def render(assignment: dict) -> str:
    lines = [f"{'时段':>8} | {'教室 A101(80)':>14} | {'教室 B202(45)':>14}"]
    lines.append("-" * 46)
    for s in SLOTS:
        a = [c for c in COURSES if assignment[c] == (s, "A101")]
        b = [c for c in COURSES if assignment[c] == (s, "B202")]
        lines.append(f"{s:>8} | {'/'.join(a) or '—':>14} | {'/'.join(b) or '—':>14}")
    return "\n".join(lines)


def main() -> None:
    csp = build_csp()
    print("== 考试排考（6 门课 / 3 时段 / 2 教室） ==")
    print(f"  课程人数：{SIZE}")
    print(f"  教室容量：{ROOMS}")
    print(f"  冲突课程对：{CONFLICTS}")
    print(f"  偏好同段：{PREFER_SAME_SLOT}\n")

    print("== 第一步：求硬约束可行解 ==")
    t0 = time.perf_counter()
    result = solve(csp, strategy="fc", var_heuristic="mrv", value_heuristic="lcv")
    ms = (time.perf_counter() - t0) * 1000
    assert result.assignment is not None, "应当有可行解"
    print(f"  节点 {result.nodes}、回退 {result.backtracks}、传播 {result.propagations}、"
          f"耗时 {ms:.1f} ms")
    assert hard_ok(result.assignment), "求解器的解不满足硬约束"
    print("  独立复核硬约束：通过 ✓")
    base = soft_cost(result.assignment)
    print(f"  初始软代价：{base:.2f}")

    print("\n== 第二步：局部搜索降软代价 ==")
    improved, new_cost, acc1, acc2 = improve(result.assignment, rng=random.Random(3))
    assert hard_ok(improved), "改进不能破坏硬约束"
    assert new_cost <= base, "改进不该升高代价"
    print(f"  改进后软代价：{new_cost:.2f}（比初始低 {base - new_cost:.2f}）")
    print(f"  接受的移动：单点 {acc1} 次、2-opt {acc2} 次")

    print("\n== 排考表 ==")
    print(render(improved))

    # ---- 算出全局最优，判断"没改进"是局部最优还是已经最优
    finite = enumerate_feasible(csp)
    best_cost = finite[0][0]
    print(f"\n== 对照：枚举全部可行解（共 {len(finite)} 个） ==")
    print(f"  全局最优软代价：{best_cost:.2f}；求解器给出的：{base:.2f}")
    if abs(best_cost - base) < 1e-9 and acc1 + acc2 == 0:
        print("  → **求解器一上来就给到了全局最优**，所以局部搜索没有改进空间。")
    elif abs(new_cost - best_cost) < 1e-9:
        print("  → 局部搜索已经到达全局最优。")
    else:
        print(f"  → 局部搜索停在 {new_cost:.2f}，**未达全局最优 {best_cost:.2f}**（陷在局部最优）。")

    print("\n→ 回答第 4 问（与 ../project/ 的排班问题对照）：")
    print(f"   本题单点交换接受 {acc1} 次、2-opt 接受 {acc2} 次；"
          f"软代价从 {base:.2f} → {new_cost:.2f}。")
    print("   两个问题的现象**不同**，恰好说明一条更重要的道理：")
    print(f"   · 排班项目：单点交换接受 0 次、2-opt 77 次（必须换两个人）")
    print(f"   · 本题：单点交换动得起来（{acc1} 次），但**无可改进之处**")
    print("   所以「局部搜索没改进」有两种完全不同的原因：")
    print("     ① **邻域太小**（一步都走不动）→ 要换更大的邻域（如 2-opt）；")
    print("     ② **已经在最优**（走动了但代价不降）→ 此时不该乱改。")
    print("   **分清这两者，必须先知道全局最优长什么样**——本题靠枚举做到了。")


if __name__ == "__main__":
    main()
