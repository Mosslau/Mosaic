"""参考解 3：把三个片段的行为实测出来，而不是凭直觉判断。

用法：python3 sol-03-诊断.py

结论预览（由脚本实测）：
  片段 A（终局不按轮到谁取符号）→ ❌ 真问题：学出来的策略偏离均衡
  片段 B（信息集键不含"我是谁"）→ ❌ 真问题：两个玩家的策略表互相覆盖
  片段 C（直接拿后悔当概率）    → ❌ 真问题：后悔会变负、也不是归一化概率
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from demo import (GAME_VALUE, all_deals, best_response_p2, ev_average,  # noqa: E402
                  kuhn_actions, kuhn_infoset, kuhn_payoff_p1, kuhn_terminal, make_cfr)
from impl import CFR  # noqa: E402


# ---------------------------------------------------------------- 片段 A：终局符号

class NoSignFlip(CFR):
    def _walk(self, cards, history, p0, p1):
        if self.terminal(history):
            return self.payoff_p1(history, cards)        # ← 缺"按轮到谁取负"
        return super()._walk(cards, history, p0, p1)


# ---------------------------------------------------------------- 片段 B：信息集缺"我是谁"

class NoPlayerInKey(CFR):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)

    def _walk(self, cards, history, p0, p1):
        player = len(history) % 2
        if self.terminal(history):
            u1 = self.payoff_p1(history, cards)
            return u1 if player == 0 else -u1
        acts = tuple(self.actions(history))
        key = (history, cards[player])                   # ← 少了 player
        strategy = self._current_strategy(key, acts)
        action_utils, node_util = [0.0] * len(acts), 0.0
        for i, a in enumerate(acts):
            child = (self._walk(cards, history + a, p0 * strategy[i], p1) if player == 0
                     else self._walk(cards, history + a, p0, p1 * strategy[i]))
            action_utils[i] = -child
            node_util += strategy[i] * action_utils[i]
        opp, own = (p1, p0) if player == 0 else (p0, p1)
        for i, a in enumerate(acts):
            regret = opp * (action_utils[i] - node_util)
            self.regret[key][a] = max(self.regret[key][a] + regret, 0.0) if self.plus \
                else self.regret[key][a] + regret
            self.strategy_sum[key][a] += own * strategy[i]
        return node_util


# ---------------------------------------------------------------- 片段 C：拿后悔当概率

class RegretAsStrategy(CFR):
    def average_strategy(self):
        out = {}
        for key, sums in self.regret.items():
            acts = tuple(self.regret[key].keys())
            out[key] = {a: self.regret[key][a] for a in acts}      # ← 直接用它当概率
        return out


def evaluate(cls, label: str, iters: int = 2000) -> dict:
    if cls is RegretAsStrategy:
        engine = cls(kuhn_terminal, kuhn_payoff_p1, kuhn_actions, kuhn_infoset)
    else:
        engine = cls(kuhn_terminal, kuhn_payoff_p1, kuhn_actions, kuhn_infoset)
    engine.train(all_deals(), iterations=iters)
    strat = engine.average_strategy()
    # 策略表的键数量：正确版本应有 3 个玩家侧信息集 × 各 3 张牌 = 12 个键
    keys = len(strat)
    # 概率是否合法（片段 C 会出现负值或和不为 1）
    legal = all(all(v >= -1e-9 for v in d.values()) and abs(sum(d.values()) - 1.0) < 1e-6
                for d in strat.values() if d)
    try:
        gap = best_response_p2(strat) - 1.0 / 18.0
        value = ev_average(strat)
    except Exception as exc:                       # 片段 C 可能直接算不出有限值
        gap, value = float("nan"), float("nan")
        print(f"    （计算期望时异常：{type(exc).__name__}）")
    print(f"  {label:<26} 键数={keys:>3}  合法概率={legal}  "
          f"博弈值={value:+.4f}  可被利用度={gap:+.4f}")
    return {"keys": keys, "legal": legal, "value": value, "gap": gap}


def main() -> None:
    iters = 2000
    print(f"== 四个实现，同样训练 {iters} 轮（库恩扑克） ==")
    print(f"  {'实现':<26} {'':<10} {'':<12} {'（理论 −0.0556）':<18} {'（越接近 0 越好）'}")
    good = evaluate(make_cfr().__class__, "正确实现")
    a = evaluate(NoSignFlip, "片段 A：终局不取符号")
    b = evaluate(NoPlayerInKey, "片段 B：键缺「我是谁」")
    c = evaluate(RegretAsStrategy, "片段 C：拿后悔当概率")

    print("\n结论：")
    print(f"  片段 A：博弈值偏离 {abs(a['value'] - GAME_VALUE):.4f}（正确实现只偏 "
          f"{abs(good['value'] - GAME_VALUE):.4f}）——**不报错，但学不对**。")
    assert abs(a["value"] - GAME_VALUE) > abs(good["value"] - GAME_VALUE) * 3, "A 应当明显更差"
    # 注意：B 的键数**恰好也是 12**（键的形状不同但个数相同）——
    # 所以"数键"不是好指标，真正的证据是**可被利用度飙升**：
    # 不同玩家、不同历史被映射到同一个键，策略表互相覆盖。
    print(f"  片段 B：键数 {b['keys']}（看起来正常！）但可被利用度 {b['gap']:+.4f} "
          f"vs 正确实现 {good['gap']:+.4f}——**键的形状错了，数量蒙混过关**。")
    assert b["gap"] > good["gap"] * 10, "B 应当明显更可被利用"
    print(f"  片段 C：概率合法={c['legal']}——后悔可正可负、也不归一化，"
          "直接当概率会得到无意义的「策略」。")
    assert not c["legal"], "C 应当产生非法概率"
    print("\n→ 三个片段都不报错，但都破坏了正确性。这正是 CFR 难调试的原因：")
    print("   它的中间量（后悔、策略和）都不是最终策略，只有平均策略能被检验。")


if __name__ == "__main__":
    main()
