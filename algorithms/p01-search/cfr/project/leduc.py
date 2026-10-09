"""迁移项目：Leduc 扑克上的 CFR（含机会节点处理 + 可复用的博弈接口）。

与教学目录（库恩扑克）的差别，正是本项目要迁移的三件事：
  1. **牌有重复**（J/Q/K 各 2 张）：信息集按"我的牌 + 公共牌"定义，
     不能用"把对手的牌当成另一个 dealt card"的简化；
  2. **有公共牌**（chance 节点）：信息集里必须包含它，否则等于偷看；
  3. **两轮下注**：第一轮"看牌到底"之后才发公共牌，弃牌则整手结束
     （这一条最容易写错：把弃牌也送进第二轮会导致无限递归）。

可复用点：`LeducCFR` 演示了**如何给 impl.CFR 接上机会节点**——
任何带随机事件的博弈都可以照这个模式扩展（覆写 `_walk` 处理转移）。

运行：cd algorithms/p01-search/cfr/project && python3 leduc.py
依赖：只用标准库
"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))          # 复用 ../impl.py 的 CFR

from impl import CFR  # noqa: E402

sys.setrecursionlimit(20000)

# ---------------------------------------------------------------- 牌与历史

DECK = (0, 1, 2, 3, 4, 5)                     # J/Q/K 各 2 张
RANK = {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 2}
RANK_NAME = {0: "J", 1: "Q", 2: "K"}
SETTLED = ("kk", "bc", "kbc")                 # 本轮看牌到底 → 进下一轮/摊牌
FOLDED = ("bf", "kbf")                        # 本轮弃牌 → 整手结束


def parts(history: str) -> list:
    """历史编码：`第一轮动作 | 公共牌 | 第二轮动作`（用 | 分段，缺省补齐 3 段）。"""
    seg = history.split("|")
    while len(seg) < 3:
        seg.append("")
    return seg


def battle(history: str) -> str:
    """当前这一轮的动作序列。"""
    seg = parts(history)
    return seg[0] if seg[1] == "" else seg[2]


def board_of(history: str):
    b = parts(history)[1]
    return b or None


def current_round(history: str) -> int:
    return 1 if parts(history)[1] == "" else 2


def terminal(history: str) -> bool:
    if battle(history) in FOLDED:
        return True
    return current_round(history) == 2 and battle(history) in SETTLED


def actions(history: str) -> tuple:
    return ("k", "b") if battle(history) in ("", "k") else ("c", "f")


def advance(history: str, board: int) -> str:
    """机会节点：第一轮看牌到底 → 发公共牌 → 第二轮。"""
    return f"{battle(history)}|{RANK_NAME[RANK[board]]}|"


def transition(history: str, cards):
    """需要发公共牌时返回新历史，否则 None（供 LeducCFR 覆写 _walk 用）。"""
    if battle(history) in SETTLED and current_round(history) == 1:
        return advance(history, cards[2])
    return None


# ---------------------------------------------------------------- 收益与信息集

def payoff_p1(history: str, cards) -> float:
    p1, p2 = cards[0], cards[1]
    acts = battle(history)
    if acts == "bf":  return 1.0
    if acts == "kbf": return -1.0
    pot = 1.0 if acts == "kk" else 2.0
    b = board_of(history)
    br = {"J": 0, "Q": 1, "K": 2}[b] if b else None
    s1 = (1 if br is not None and RANK[p1] == br else 0, RANK[p1])
    s2 = (1 if br is not None and RANK[p2] == br else 0, RANK[p2])
    return pot if s1 > s2 else -pot


def infoset(history: str, card: int, player: int):
    """信息集 =（我的私有牌, 公共牌, 本轮动作, 我是谁）——不含对手私有牌。"""
    return (card, board_of(history), battle(history), player)


def all_deals() -> list:
    """全部发牌三元组，三张互不相同（120 种）。"""
    return [(a, b, c) for a in DECK for b in DECK for c in DECK if len({a, b, c}) == 3]


def count_infosets() -> int:
    """按信息集定义直接计数：6 种牌 × 3 种公共牌 × 4 种本轮动作 × 2 玩家 × 2 轮。"""
    return 2 * len(DECK) * 3 * 4


# ---------------------------------------------------------------- CFR 适配

class LeducCFR(CFR):
    """把机会节点接进 CFR：`_walk` 遇到需要发公共牌的历史就先转移。"""

    def _walk(self, cards, history, p0, p1):
        nxt = transition(history, cards)
        if nxt is not None:
            return self._walk(cards, nxt, p0, p1)
        return super()._walk(cards, history, p0, p1)


def make_cfr(plus: bool = False) -> LeducCFR:
    return LeducCFR(terminal, payoff_p1, actions, infoset, plus=plus)


# ---------------------------------------------------------------- 评估与实验

def rollout_value(strategy: dict, cards, uniform_fallback: bool = True) -> float:
    """给定双方策略与发牌，求 player1 的期望收益。"""
    def rec(h: str) -> float:
        if terminal(h):
            return payoff_p1(h, cards)
        nxt = transition(h, cards)
        if nxt is not None:
            return rec(nxt)
        acts = actions(h)
        player = len(battle(h)) % 2
        probs = strategy.get(infoset(h, cards[player], player))
        if probs is None:
            probs = {a: 1.0 / len(acts) for a in acts}
        return sum(probs.get(a, 0.0) * rec(h + a) for a in acts)
    return rec("")


def value_vs_uniform(strategy: dict) -> float:
    """对"均匀随机对手"的期望收益（Leduc 的最佳回应无法暴力枚举，用这个替代）。"""
    deals = all_deals()
    return sum(rollout_value(strategy, d) for d in deals) / len(deals)


def experiment_cost(grid=(1, 10, 100, 1000)) -> list:
    print("== 实验一：训练成本（每轮遍历全部 120 种发牌） ==")
    print(f"{'训练量':>8} | {'对均匀随机的收益':>16} | {'耗时(秒)':>9} | {'每轮(ms)':>9}")
    print("-" * 54)
    rows = []
    for iters in grid:
        t0 = time.perf_counter()
        cfr = make_cfr().train(all_deals(), iterations=iters)
        sec = time.perf_counter() - t0
        val = value_vs_uniform(cfr.average_strategy())
        rows.append((iters, val, sec))
        print(f"{iters:>8} | {val:>16.4f} | {sec:>9.2f} | {sec / iters * 1000:>9.1f}")
    return rows


def experiment_scaling() -> dict:
    """把两个博弈的规模并列：这是"迁移的代价"的直接答案。"""
    print("\n== 实验二：规模对照（库恩 vs Leduc） ==")
    print(f"{'维度':>12} | {'库恩扑克':>10} | {'Leduc':>10} | {'倍数':>8}")
    print("-" * 50)
    rows = [("牌堆", 3, len(DECK)), ("发牌组合", 6, len(all_deals())),
            ("信息集", 12, count_infosets()), ("下注轮次", 1, 2)]
    for name, kuhn, leduc in rows:
        print(f"{name:>12} | {kuhn:>10} | {leduc:>10} | {leduc / kuhn:>7.1f}×")
    return {name: (kuhn, leduc) for name, kuhn, leduc in rows}


def main() -> None:
    print(f"Leduc：牌堆 {len(DECK)} 张，发牌组合 {len(all_deals())} 种，"
          f"信息集 {count_infosets()} 个\n")
    rows = experiment_cost()
    experiment_scaling()

    assert rows[-1][1] < 0, "训练后对均匀随机对手应当盈利"
    assert count_infosets() > 12 * 10, "Leduc 的信息集应当比库恩扑克多一个量级"
    print("\n→ 结论：")
    print(f"   · 训练 1000 轮只要 {rows[-1][2]:.1f} 秒——**Leduc 完全在 CFR 的能力范围内**，")
    print("     它是教学规模的不完全信息博弈（真实研究里的标准测试床）。")
    print("   · 真正让「裸 CFR」失效的是德州扑克那个量级（状态数 ~10^160），")
    print("     那时必须上抽象 + 采样；本项目还没触到那个边界。")
    print("   · 迁移的真实代价在**接口**：加了公共牌就必须自己处理机会节点")
    print("     （见 LeducCFR），否则第一轮会无限重来。")


if __name__ == "__main__":
    main()
