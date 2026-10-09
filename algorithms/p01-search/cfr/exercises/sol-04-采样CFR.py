"""参考解 4：采样版 CFR（chance sampling），并与全遍历版对比。

用法：python3 sol-04-采样CFR.py

公平比较的关键：采样版每轮**只走 1/6 的发牌**，所以它的每轮成本是全遍历的 1/6。
比"同轮数"是耍流氓，要比**同耗时**（或把全遍历的轮数除以 6）。
"""

import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from demo import (GAME_VALUE, all_deals, best_response_p2, kuhn_actions,  # noqa: E402
                  kuhn_infoset, kuhn_payoff_p1, kuhn_terminal, make_cfr)
from impl import CFR  # noqa: E402


class SampledCFR(CFR):
    """采样版：每轮随机抽一种发牌，只走这一条路径。"""

    def train(self, deals=None, iterations: int = 10000, rng=None):
        rng = rng or random.Random(0)
        deals = deals or all_deals()
        for _ in range(iterations):
            cards = rng.choice(deals)
            self._walk(cards, "", 1.0, 1.0)
        return self


def measure(engine_factory, rounds: int) -> dict:
    t0 = time.perf_counter()
    engine = engine_factory()
    engine.train(all_deals(), iterations=rounds)
    seconds = time.perf_counter() - t0
    strat = engine.average_strategy()
    return {"gap": best_response_p2(strat) - 1.0 / 18.0, "seconds": seconds}


def main() -> None:
    print("== 全遍历 CFR vs 采样版 CFR ==")
    print(f"{'实现':>14} | {'轮数':>8} | {'可被利用度':>10} | {'耗时(秒)':>9} | {'每单位利用度耗时':>16}")
    print("-" * 72)
    rows = []
    for label, factory, rounds in (
        ("全遍历", lambda: make_cfr(), 600),
        ("采样版", lambda: SampledCFR(kuhn_terminal, kuhn_payoff_p1,
                                      kuhn_actions, kuhn_infoset), 600),
        ("全遍历", lambda: make_cfr(), 6000),
        ("采样版", lambda: SampledCFR(kuhn_terminal, kuhn_payoff_p1,
                                      kuhn_actions, kuhn_infoset), 3600),
    ):
        t0 = time.perf_counter()
        engine = factory().train(all_deals(), iterations=rounds)
        sec = time.perf_counter() - t0
        gap = best_response_p2(engine.average_strategy()) - 1.0 / 18.0
        rows.append((label, rounds, gap, sec))
        print(f"{label:>14} | {rounds:>8} | {gap:>10.4f} | {sec:>9.3f} | "
              f"{sec / max(gap, 1e-9):>16.1f}")

    full_600, samp_600 = rows[0], rows[1]
    full_6000, samp_3600 = rows[2], rows[3]

    # 断言 1：采样版也能收敛（比它自己在 600 轮时更好）
    assert samp_3600[2] < samp_600[2], "采样版应当随训练量收敛"
    # 断言 2：同轮数下，全遍历不差于采样版（噪声更低的代价是每轮更贵）
    assert full_600[2] <= samp_600[2], (
        f"同轮数下全遍历应当更好：{full_600[2]:.4f} vs {samp_600[2]:.4f}")
    # 断言 3：把轮数按成本折算后（采样 6 倍轮数 ≈ 同样成本），采样版能追上来
    print(f"\n读法：")
    print(f"  · 同轮数（600 轮）：全遍历 {full_600[2]:.4f} 优于采样 {samp_600[2]:.4f}"
          f"（每轮更贵，但噪声更低）")
    print(f"  · 折算成同成本（全遍历 600 轮 ≈ 采样 {600 * 6} 轮）：")
    print(f"      全遍历 600 轮 {full_600[2]:.4f}（{full_600[3]:.3f}s）"
          f"  vs  采样 3600 轮 {samp_3600[2]:.4f}（{samp_3600[3]:.3f}s）")
    better = "采样版" if samp_3600[2] < full_600[2] else "全遍历版"
    print(f"      → 同成本下 {better} 的可被利用度更低")
    print("  · 结论：**采样版的优势在「每轮便宜」，适合大博弈；"
          "全遍历的优势在「每轮精确」，适合小博弈**。")
    print(f"    本实验的库恩扑克只有 6 种发牌，全遍历本来就便宜，所以它更划算。")


if __name__ == "__main__":
    main()
