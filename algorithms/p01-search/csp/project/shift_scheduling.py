"""迁移项目：真实排班问题（硬约束 + 软约束）。

教学目录解的是"纯硬约束、有唯一解"的玩具问题（八皇后、数独）。
真实排班不一样：
  · **硬约束**（必须满足）：每班人数够、没人被排到不可用的班次、一人一天不排两班；
  · **软约束**（尽量满足）：尽量别给同一人连排夜班、班次尽量平均、尽量满足偏好；
  · 而且**常常无解**——这时你需要的不是"无解"三个字，而是"最不坏的方案"。

所以本项目做两件事：
  1. 用 `../impl.py` 的回溯 + 前向检查求**硬约束可行解**；
  2. 在可行解空间里用**贪心 + 局部改进**优化软约束代价（这是 CSP → COP 的迁移）。

运行：cd algorithms/p01-search/csp/project && python3 shift_scheduling.py
依赖：只用标准库
"""

import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from impl import CSP, solve  # noqa: E402

SHIFTS = ("早", "中", "夜")
DAYS = 7

#: 每天每班需要的人数（硬约束）
NEED = {"早": 1, "中": 2, "夜": 1}

#: 每个人的"不可用"班次（硬约束）：这里模拟"某人不能上夜班"
UNAVAILABLE = {"甲": {"夜"}, "乙": set(), "丙": set(), "丁": set(), "戊": set()}

#: 偏好（软约束）：某人更想上/不想上的班次
PREFER = {
    "甲": {"早": 1.0, "中": 0.4},
    "乙": {"中": 0.8, "夜": -0.6},
    "丙": {"早": 0.6, "夜": -0.2},
    "丁": {"中": 0.5},
    "戊": {"夜": 0.7, "早": -0.3},
}

PEOPLE = tuple(UNAVAILABLE)


# ---------------------------------------------------------------- 建模

def build_csp(seed: int = 0) -> tuple:
    """把"每天每班要几人"建成 CSP。

    变量：`(d, s, k)` = 第 d 天、班次 s 的**第 k 个名额**（因为每班要多人，
    所以用"名额"当变量，而不是"人当变量"——这样"每班人数"天然满足）。
    取值：候选人名（且排除不可用的人）。
    约束：同一人同一天不能占两个名额。
    """
    variables, domains = [], {}
    for d in range(DAYS):
        for s in SHIFTS:
            for k in range(NEED[s]):
                var = f"d{d}-{s}-{k}"
                variables.append(var)
                cands = [p for p in PEOPLE if s not in UNAVAILABLE[p]]
                domains[var] = list(cands)

    constraints = []
    for i, a in enumerate(variables):
        for b in variables[i + 1:]:
            da, sa, _ = a.split("-")
            db, sb, _ = b.split("-")
            if da == db:                      # 同一天 → 不能是同一个人
                constraints.append((a, b, lambda x, y: x != y))
    return CSP(variables, domains, constraints), variables


def soft_cost(assignment: dict) -> float:
    """软约束代价（越小越好）：偏好违背、连排夜班、班次不均衡。"""
    cost = 0.0
    per_person = {p: {s: 0 for s in SHIFTS} for p in PEOPLE}
    night_days = {p: [] for p in PEOPLE}

    for var, person in assignment.items():
        _, shift, _ = var.split("-")
        day = int(var.split("-")[0][1:])
        per_person[person][shift] += 1
        if shift == "夜":
            night_days[person].append(day)
        # 软约束 1：偏好（PREFER 里的正分是"想上"，负分是"不想上"）
        pref = PREFER.get(person, {}).get(shift, 0.0)
        cost -= pref                          # 想上却没上不给分；上了加"收益"就减代价

    # 软约束 2：连排夜班（同一人相邻两天都上夜班 → 惩罚）
    for person, days in night_days.items():
        days.sort()
        for a, b in zip(days, days[1:]):
            if b - a == 1:
                cost += 2.0

    # 软约束 3：班次不均衡（同一人的夜间班与早班数量差距）
    for person, counts in per_person.items():
        cost += 0.2 * abs(counts["夜"] - counts["早"])
    return cost


def hard_ok(assignment: dict) -> bool:
    """独立复核硬约束（不依赖求解器自报）：每班人数够、同一天不重复排人。"""
    filled = {(d, s): 0 for d in range(DAYS) for s in SHIFTS}
    per_day = {d: [] for d in range(DAYS)}
    for var, person in assignment.items():
        d = int(var.split("-")[0][1:])
        shift = var.split("-")[1]
        if shift in UNAVAILABLE[person]:
            return False                      # 排了不可用的人
        filled[(d, shift)] += 1
        per_day[d].append(person)
    for d in range(DAYS):
        if len(set(per_day[d])) != len(per_day[d]):
            return False                      # 同一天排了同一个人两次
    for (d, s), cnt in filled.items():
        if cnt != NEED[s]:
            return False                      # 人数不对
    return True


# ---------------------------------------------------------------- 优化

def improve(assignment: dict, variables: list, tries: int = 6000,
            rng: random.Random = None) -> tuple:
    """局部改进：**单点交换 + 2-opt 交换**，只在硬约束成立且代价不升时接受。

    为什么要 2-opt：排班问题里"单换一个人"几乎总会破坏硬约束（每个班次人数是定死的），
    实测单点交换的接受率为 0——必须一次换两个人（互相顶班）才动得了。
    这是**"可行域很窄"时的通用教训**：邻域定义得太小，局部搜索就一步都走不动。
    """
    rng = rng or random.Random(0)
    best = dict(assignment)
    best_cost = soft_cost(best)
    accepted_1 = accepted_2 = 0

    for _ in range(tries):
        if rng.random() < 0.5:
            # ---- 单点交换
            var = rng.choice(variables)
            old = best[var]
            cands = [p for p in PEOPLE
                     if p != old and var.split("-")[1] not in UNAVAILABLE[p]]
            if not cands:
                continue
            best[var] = rng.choice(cands)
            if hard_ok(best) and soft_cost(best) <= best_cost:
                best_cost = soft_cost(best)
                accepted_1 += 1
            else:
                best[var] = old
        else:
            # ---- 2-opt：交换两个名额上的人（互相顶班）
            v1, v2 = rng.sample(variables, 2)
            p1, p2 = best[v1], best[v2]
            if p1 == p2:
                continue
            if v1.split("-")[1] in UNAVAILABLE[p2] or v2.split("-")[1] in UNAVAILABLE[p1]:
                continue
            best[v1], best[v2] = p2, p1
            if hard_ok(best) and soft_cost(best) <= best_cost:
                best_cost = soft_cost(best)
                accepted_2 += 1
            else:
                best[v1], best[v2] = p1, p2

    return best, best_cost, accepted_1 + accepted_2, accepted_2


# ---------------------------------------------------------------- 展示

def render(assignment: dict) -> str:
    table = {}
    for var, person in assignment.items():
        d = int(var.split("-")[0][1:])
        shift = var.split("-")[1]
        table.setdefault((d, shift), []).append(person)
    lines = ["     " + "".join(f"{'周' + str(d + 1):>8}" for d in range(DAYS))]
    for s in SHIFTS:
        row = f"{s:>4} "
        for d in range(DAYS):
            row += f"{'/'.join(sorted(table.get((d, s), []))):>8}"
        lines.append(row)
    return "\n".join(lines)


def main() -> None:
    csp, variables = build_csp()
    print("== 排班问题（硬约束：每班人数 + 不可用班次 + 一天不排两班） ==")
    print(f"  变量 {len(variables)} 个（每天每班的「名额」），人员 {len(PEOPLE)} 人")
    print(f"  每班需求：{NEED}")
    print(f"  不可用：{ {p: sorted(s) for p, s in UNAVAILABLE.items() if s} }\n")

    print("== 第一步：求硬约束可行解（回溯 + 前向检查） ==")
    result = solve(csp, strategy="fc", var_heuristic="mrv", value_heuristic="lcv")
    assert result.assignment is not None, "硬约束在给定人员下应当可行"
    print(f"  求解：节点 {result.nodes}、回退 {result.backtracks}、传播 {result.propagations}")
    assert hard_ok(result.assignment), "求解器给出的解不满足硬约束！"
    print("  独立复核硬约束：通过 ✓")
    base_cost = soft_cost(result.assignment)
    print(f"  初始软代价：{base_cost:.2f}")

    print("\n== 第二步：局部改进降软代价（CSP → 约束优化） ==")
    improved, new_cost, accepted, accepted_2 = improve(
        result.assignment, variables, tries=8000, rng=random.Random(7))
    assert hard_ok(improved), "改进过程不能破坏硬约束"
    print(f"  改进后软代价：{new_cost:.2f}（比初始 {base_cost:.2f} 低 {base_cost - new_cost:.2f}）；"
          f"接受 {accepted} 次移动（其中 2-opt {accepted_2} 次）")
    print("  （代价可以为负：PREFER 的正分是「想上这个班」，上到了就是收益）")
    assert new_cost <= base_cost, "改进不该让代价变高"

    print("\n== 排班表（改进后） ==")
    print(render(improved))

    print("\n→ 结论：")
    print("   · 教学目录的 CSP 是「找一个可行解」；真实排班要的是「**可行解里最好的那个**」——")
    print("     这就是 CSP 与约束优化（COP）的分界。")
    print("   · 本项目的做法是两段式：**搜索找可行解 + 局部搜索降代价**。")
    print("   · 局部搜索的邻域必须够大：单点交换在这个问题上接受率为 0（换一个人必然破坏人数约束），")
    print("     加入 2-opt（两人互顶）之后才动得起来——**邻域太小，局部搜索一步都走不动**。")
    print("     也可以把软约束直接编码进搜索（分支限界），代价是搜索空间变大。")
    print("   · 硬约束的独立复核不能省：求解器「说自己解出来了」和「解真的合法」是两件事。")


if __name__ == "__main__":
    main()
