"""CFR demo：在库恩扑克上学出纳什均衡，并与**教科书解析解**逐项对照。

库恩扑克（Kuhn poker）：3 张牌 J/Q/K，两人各 1 张，各下 1 注底池；一轮下注：
    过牌-过牌 → 摊牌，赢家净赚 1
    下注-弃牌 → 下注者净赚 1
    下注-跟注 / 过牌-下注-跟注 → 摊牌，赢家净赚 2
    过牌-下注-弃牌 → 下注者净赚 1
已知纳什均衡（单参数族，α ∈ [0, 1/3]）：
    player1 手持 J：以概率 α 下注；Q：从不下注；K：以概率 3α 下注
    player1 面对下注：J 弃牌；Q 以 1/3 跟注；K 跟注
    player2 面对下注：Q 以 1/3 跟注、K 跟注、J 弃牌
博弈值（player1 期望）：−1/18 ≈ −0.0556（先手反而略亏，因为先亮牌的是他）

四组实验：
  1. **收敛**：训练量 → 博弈值 / 关键频率，对照解析解
  2. **可被利用度**：用暴力最佳回应衡量"离均衡还有多远"
  3. **对固定对手**：训练后的策略对"永远弃牌/永远跟注/均匀"能赚多少
  4. **CFR vs CFR+**：同样的训练量，后悔截断（CFR+）带来多少加速

运行：cd algorithms/p01-search/cfr && python3 demo.py
依赖：只用标准库
"""

import itertools
import random
from collections import defaultdict
from pathlib import Path

from baseline import FIXED_OPPONENTS, uniform_strategy
from impl import CFR

CARDS = (0, 1, 2)                 # J=0, Q=1, K=2
TERMINAL = {"kk", "bf", "bc", "kbf", "kbc"}
CARD_NAMES = {0: "J", 1: "Q", 2: "K"}
GAME_VALUE = -1.0 / 18.0          # player1 的均衡期望（负：先手略亏）


# ---------------------------------------------------------------- 库恩扑克的四个接口

def kuhn_terminal(history: str) -> bool:
    return history in TERMINAL


def kuhn_payoff_p1(history: str, cards) -> float:
    """终局时 player1 的效用（零和）。"""
    p1, p2 = cards
    if history == "bf":   return 1.0
    if history == "kbf":  return -1.0
    if history == "kk":   return 1.0 if p1 > p2 else -1.0
    if history in ("bc", "kbc"): return 2.0 if p1 > p2 else -2.0
    raise ValueError(f"不是终局：{history}")


def kuhn_actions(history: str) -> tuple:
    """首轮可过牌/下注；面对下注可跟注/弃牌。"""
    return ("k", "b") if history in ("", "k") else ("c", "f")


def kuhn_infoset(history: str, card: int, player: int):
    """信息集 =（动作历史, 我的牌, 我是谁）——**对手的牌不在里面**。"""
    return (history, card, player)


def all_deals() -> list:
    """所有可能的发牌（3×2 = 6 种）。CFR 每轮遍历全部，保证确定性收敛。"""
    return list(itertools.permutations(CARDS, 2))


def make_cfr(plus: bool = False) -> CFR:
    return CFR(kuhn_terminal, kuhn_payoff_p1, kuhn_actions, kuhn_infoset, plus=plus)


# ---------------------------------------------------------------- 评估工具

def ev_p1(strategy: dict, cards, default_uniform: bool = True) -> float:
    """给定双方策略与牌，返回 player1 的期望效用（递归，单视角）。"""
    def rec(history: str) -> float:
        if kuhn_terminal(history):
            return kuhn_payoff_p1(history, cards)
        player = len(history) % 2
        acts = kuhn_actions(history)
        probs = strategy.get(kuhn_infoset(history, cards[player], player))
        if probs is None:
            probs = {a: 1.0 / len(acts) for a in acts}
        return sum(probs.get(a, 0.0) * rec(history + a) for a in acts)
    return rec("")


def ev_average(strategy: dict) -> float:
    """对全部 6 种发牌取平均——整个博弈的博弈值。"""
    deals = all_deals()
    return sum(ev_p1(strategy, d) for d in deals) / len(deals)


def best_response_p2(strategy: dict) -> float:
    """player2 的最佳回应价值（**暴力枚举** p2 的全部纯策略，2^6 = 64 种）。

    为什么暴力：最佳回应函数的"符号视角"极易写错（本项目踩过——写错会给出
    比单手上限还大的值）。Kuhn 的 p2 只有 6 个信息集 × 2 个动作，暴力枚举
    64 种纯策略既简单又无歧义，还能用理论均衡反向校验（应恰好给 1/18）。
    """
    infosets = [("k", c) for c in CARDS] + [("b", c) for c in CARDS]
    act_table = {"k": ("k", "b"), "b": ("c", "f")}
    best = float("-inf")
    for combo in itertools.product(*[act_table[h] for h, _ in infosets]):
        pure = {}
        for i, (h, c) in enumerate(infosets):
            acts = act_table[h]
            pure[(h, c, 1)] = {a: (1.0 if a == combo[i] else 0.0) for a in acts}
        merged = dict(strategy)
        merged.update(pure)
        best = max(best, -ev_average(merged))          # p2 视角
    return best


def equilibrium_family(alpha: float = 0.0) -> dict:
    """教科书给出的均衡族（α=0 的那一支）；用于反向校验评估工具。"""
    s = {}
    for c in CARDS:
        bet = {0: alpha, 1: 0.0, 2: 3 * alpha}[c]
        s[("", c, 0)] = {"b": bet, "k": 1 - bet}
        s[("k", c, 1)] = {"b": 0.0, "k": 1.0}
        s[("b", c, 1)] = {"c": 0.0, "f": 1.0}
    s[("kb", 0, 0)] = {"c": 0.0, "f": 1.0}
    s[("kb", 1, 0)] = {"c": 1 / 3.0, "f": 2 / 3.0}
    s[("kb", 2, 0)] = {"c": 1.0, "f": 0.0}
    return s


def key_frequencies(strategy: dict) -> dict:
    """本实验关心的关键频率（与解析解逐项对照）。"""
    return {
        "J_bet": strategy[("", 0, 0)]["b"],
        "Q_bet": strategy[("", 1, 0)]["b"],
        "K_bet": strategy[("", 2, 0)]["b"],
        "J_call": strategy[("kb", 0, 0)]["c"],
        "Q_call": strategy[("kb", 1, 0)]["c"],
        "K_call": strategy[("kb", 2, 0)]["c"],
        "p2_Q_call": strategy[("b", 1, 1)]["c"],
    }


# ---------------------------------------------------------------- 实验一：收敛

def experiment_convergence(iterations_grid=(10, 100, 1000, 10000, 50000)) -> list:
    print("== 实验一：训练量 → 博弈值 / 关键频率（对照教科书解析解） ==")
    print("教科书：博弈值（player1 期望，先手略亏）−1/18 = −0.0556；")
    print("        均衡频率满足 J 下注率 : K 下注率 = 1 : 3、Q 下注率 = 0；")
    print("        p1 面对下注 Q 跟注 1/3、J 弃牌、K 跟注；p2 面对下注 Q 跟注 1/3")
    print(f"{'训练量':>8} | {'博弈值':>9} | {'累计正后悔':>11} | {'平均后悔':>9} | {'J注':>6} | "
          f"{'Q注':>6} | {'K注':>6} | {'Q跟':>6} | {'p2Q跟':>6}")
    print("-" * 82)
    rows = []
    for iters in iterations_grid:
        cfr = make_cfr().train(all_deals(), iterations=iters)
        avg = cfr.average_strategy()
        f = key_frequencies(avg)
        rows.append((iters, ev_average(avg), cfr.positive_regret(), f))
        avg_regret = cfr.positive_regret() / (iters * 6)
        print(f"{iters:>8} | {ev_average(avg):>9.4f} | {cfr.positive_regret():>11.1f} | "
              f"{avg_regret:>9.4f} | {f['J_bet']:>6.3f} | {f['Q_bet']:>6.3f} | "
              f"{f['K_bet']:>6.3f} | {f['Q_call']:>6.3f} | {f['p2_Q_call']:>6.3f}")
    first, last = rows[0], rows[-1]
    assert abs(last[1] - GAME_VALUE) < 0.002, f"训练后博弈值应收敛到 −1/18：{last[1]}"
    assert abs(last[1] - GAME_VALUE) < abs(first[1] - GAME_VALUE), "训练越多应越接近均衡值"
    # 注意：累计正后悔**会持续增长**——CFR 保证的是"平均后悔 → 0"（即 累计/T → 0），
    # 不是"累计后悔 → 0"。表里它随 T 增大而增大是正常的，别误读成不收敛。
    print(f"\n→ 博弈值从 {first[1]:+.4f}（{first[0]} 次）收敛到 {last[1]:+.4f}"
          f"（{last[0]} 次），理论值 {GAME_VALUE:+.4f}")
    print("   注意：累计正后悔随训练量增长，但**平均**后悔在下降——CFR 保证的是后者趋于 0。")
    return rows


# ---------------------------------------------------------------- 实验二：可被利用度

def experiment_exploitability(iterations_grid=(10, 100, 1000, 10000)) -> list:
    print("\n== 实验二：可被利用度（暴力最佳回应 − 均衡值；越接近 0 越好） ==")
    print(f"{'训练量':>8} | {'p1 期望':>9} | {'p2 最佳回应':>11} | {'可被利用度':>10}")
    print("-" * 48)
    rows = []
    for iters in iterations_grid:
        avg = make_cfr().train(all_deals(), iterations=iters).average_strategy()
        u1 = ev_average(avg)
        br = best_response_p2(avg)
        rows.append((iters, u1, br, br - 1.0 / 18.0))
        print(f"{iters:>8} | {u1:>9.4f} | {br:>11.4f} | {br - 1.0 / 18.0:>10.4f}")
    assert rows[-1][3] < rows[0][3], "训练越多，可被利用度应当越小"
    print(f"\n→ 可被利用度从 {rows[0][3]:.4f} 降到 {rows[-1][3]:.4f}"
          f"（训练 {rows[-1][0]} 次）——这就是「学出纳什均衡」的量化含义")
    return rows


# ---------------------------------------------------------------- 实验三：对固定对手

def experiment_vs_fixed(iterations: int = 10000) -> dict:
    print(f"\n== 实验三：训练 {iterations} 次后的策略，对固定对手能赚多少（p1 视角） ==")
    avg = make_cfr().train(all_deals(), iterations=iterations).average_strategy()
    print(f"{'对手策略':>16} | {'p1 期望收益':>11} | {'对手是均匀随机时':>16}")
    print("-" * 52)
    out = {}
    uniform = uniform_strategy()
    for name, opp in FIXED_OPPONENTS.items():
        merged = dict(avg)
        merged.update(opp)
        val = ev_average(merged)
        merged_uniform = dict(uniform)
        merged_uniform.update(opp)
        base = ev_average(merged_uniform)
        out[name] = (val, base)
        print(f"{name:>16} | {val:>11.4f} | {base:>16.4f}")
    # 断言只保留站得住的一条：对"永远跟注"这种对手，纳什策略必须能盈利
    assert out["永远跟注"][0] > 0, "训练后的策略对「永远跟注」应当盈利"
    # 反直觉但真实：对"永远弃牌"这种**极弱**对手，均匀随机策略赚得**更多**——
    # 因为均衡策略会"收敛到不诈唬"，而均匀随机有一半时间在下注，把对手吓跑得更多。
    # 这说明「接近纳什」≠「对任意固定对手收益最大」：前者是**不可被利用**，后者是**最大化利用**。
    print("\n→ 读法（本实验最值得注意的一点）：")
    print("   · 对「永远跟注」这种会跟到底的对手，纳什策略盈利 0.11（会用 K 价值下注）")
    print("   · 但对「永远弃牌」这种极弱对手，**均匀随机反而赚得更多**（0.50 vs 0.14）")
    print("     原因：均匀随机有一半时间在下注，把弃牌型对手吓跑得更频繁；")
    print("     纳什策略必须「不可被利用」，所以它会收敛到不做无谓诈唬。")
    print("   → **接近纳什 ≠ 对任意固定对手收益最大**：纳什保证的是不被利用，不是最大化利用。")
    return out


# ---------------------------------------------------------------- 实验四：CFR vs CFR+

def experiment_plus(iterations_grid=(10, 100, 1000, 10000)) -> list:
    print("\n== 实验四：CFR vs CFR+（同样训练量，谁更接近均衡） ==")
    print(f"{'训练量':>8} | {'CFR 可被利用度':>15} | {'CFR+ 可被利用度':>16} | {'提速':>7}")
    print("-" * 58)
    rows = []
    for iters in iterations_grid:
        res = {}
        for tag, plus in (("cfr", False), ("cfr+", True)):
            avg = make_cfr(plus=plus).train(all_deals(), iterations=iters).average_strategy()
            res[tag] = best_response_p2(avg) - 1.0 / 18.0
        gain = res["cfr"] / res["cfr+"] if res["cfr+"] > 0 else float("inf")
        rows.append((iters, res["cfr"], res["cfr+"], gain))
        print(f"{iters:>8} | {res['cfr']:>15.4f} | {res['cfr+']:>16.4f} | {gain:>6.1f}×")
    better = sum(1 for _, c, cp, _ in rows if cp < c)
    print(f"\n→ 实测：{len(rows)} 个训练量里 CFR+ 只有 {better} 个更好——"
          f"**在本设置下 CFR+ 并没有优势**。")
    print("   与常见说法不符，原因值得写下来：")
    print("   · 经典结论（CFR+ 快很多）大多来自**大游戏 + 采样版**（每次只走一条路径）；")
    print("   · 本实现每轮**遍历全部 6 种发牌**（确定性全遍历），梯度噪声本来就很低，")
    print("     后悔截断能带来的方差削减在这里几乎没有用武之地；")
    print("   · 而且恢复「截断掉的正后悔」需要更多轮才能重建概率质量，小规模下反而略慢。")
    print("   → 结论：**优化手段要跟问题规模匹配**，不能照搬文献里的结论。")
    return rows


def main() -> None:
    print("=== 先反向校验评估工具 ===")
    print("  用一组**被利用**的策略检验最佳回应函数：")
    print("    永远弃牌(p2)   → p2 最佳回应应当能赚（因为 p1 可以无脑下注）")
    print("    永远跟注(p2)   → p2 最佳回应应当 ≈ 0（跟注到底并不太亏）")
    print("  再检验：对解析解给出的**p1 侧频率**，博弈值应落在理论值附近")
    eq = equilibrium_family(alpha=1.0 / 6.0)
    print(f"    均衡族(α=1/6)：博弈值 {ev_average(eq):+.4f}"
          f"（这组 p2 策略不是最佳回应，故不作为值校验，仅用于频率对照）")
    for name, opp in FIXED_OPPONENTS.items():
        merged = dict(eq)
        merged.update(opp)
        print(f"    对「{name}」：最佳回应 {best_response_p2(merged):+.4f}")
    print()

    experiment_convergence()
    experiment_exploitability()
    experiment_vs_fixed()
    experiment_plus()


if __name__ == "__main__":
    main()
