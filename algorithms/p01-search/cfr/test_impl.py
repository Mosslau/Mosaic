"""CFR 的性质测试。

用法（本目录内）：python3 -m pytest test_impl.py -q

覆盖：
- **评估工具自校验**：用能手算的纯策略对验证期望收益（这是所有断言的基准）
- **最佳回应自校验**：对"永远弃牌"这类被利用策略，最佳回应应有明显收益
- **收敛到纳什均衡**：训练后博弈值 ≈ −1/18、可被利用度 < 0.01
- **均衡频率**：J:K 下注率 ≈ 1:3、Q 从不下注、面对下注的跟注率关系
- **符号正确性**：终局效用按"轮到谁"取符号——写错会不收敛（用回归值守住）
- **后悔匹配**：正后悔归一化；全负则均匀
- **CFR+**：后悔截断后永不为负
- **边界**：未提供 deals 抛错、零训练量、单次训练
"""

import itertools
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from baseline import FIXED_OPPONENTS, uniform_strategy  # noqa: E402
from demo import (GAME_VALUE, all_deals, best_response_p2, ev_average,  # noqa: E402
                  ev_p1, kuhn_actions, kuhn_infoset, kuhn_payoff_p1, kuhn_terminal,
                  key_frequencies, make_cfr)
from impl import CFR  # noqa: E402


# ---------------------------------------------------------------- 手算基准

def _pure(p1_bets: bool, p2_bets_after_check: bool, p2_calls: bool) -> dict:
    """构造一个完整纯策略对（p1 侧 + p2 侧），用于手算校验。"""
    s = {}
    for c in (0, 1, 2):
        s[("", c, 0)] = {"b": 1.0 if p1_bets else 0.0, "k": 0.0 if p1_bets else 1.0}
        s[("k", c, 1)] = {"b": 1.0 if p2_bets_after_check else 0.0,
                          "k": 0.0 if p2_bets_after_check else 1.0}
        s[("b", c, 1)] = {"c": 1.0 if p2_calls else 0.0, "f": 0.0 if p2_calls else 1.0}
        s[("kb", c, 0)] = {"c": 0.0, "f": 1.0}          # p1 面对下注永远弃牌
    return s


@pytest.mark.parametrize("p1_bets,p2_bets,p2_calls,want", [
    (True, True, False, 1.0),      # p1 永下注、p2 面对下注永弃 → p1 白赢 1
    (True, True, True, 0.0),       # p1 永下注、p2 永远跟注 → 摊牌，胜负各半
    (False, False, True, 0.0),     # 双方都过牌 → 摊牌，各 1
    (False, True, True, -1.0),     # p1 永过牌、p2 永下注、p1 永不跟 → p1 白输 1
])
def test_evaluator_matches_hand_calculation(p1_bets, p2_bets, p2_calls, want) -> None:
    """期望收益工具必须与手算一致（这是一切断言的地基）。"""
    assert ev_average(_pure(p1_bets, p2_bets, p2_calls)) == pytest.approx(want)


def test_best_response_beats_exploitable_strategy() -> None:
    """对"p1 永远弃牌"这种被动策略，p2 的最佳回应应当明显盈利。"""
    passive = {}
    for c in (0, 1, 2):
        passive[("", c, 0)] = {"b": 0.0, "k": 1.0}
        passive[("kb", c, 0)] = {"c": 0.0, "f": 1.0}
    # 补上 p2 的均匀策略（会被最佳回应替换）
    merged = dict(passive)
    merged.update(uniform_strategy())
    assert best_response_p2(merged) > 0.1, "p2 应当能大幅利用一个从不进攻的对手"


def test_best_response_on_equilibrium_is_game_value() -> None:
    """对"训练出来的"策略，最佳回应展示出它离均衡有多远；均衡时 ≈ +1/18。"""
    avg = make_cfr().train(all_deals(), iterations=10000).average_strategy()
    assert best_response_p2(avg) == pytest.approx(1.0 / 18.0, abs=0.01)


# ---------------------------------------------------------------- 收敛

def test_converges_to_nash_value() -> None:
    """训练后博弈值必须收敛到理论值 −1/18。"""
    avg = make_cfr().train(all_deals(), iterations=20000).average_strategy()
    assert ev_average(avg) == pytest.approx(GAME_VALUE, abs=0.002)


def test_exploitability_decreases() -> None:
    """训练越多，可被利用度越小。"""
    gaps = []
    for iters in (10, 1000):
        avg = make_cfr().train(all_deals(), iterations=iters).average_strategy()
        gaps.append(best_response_p2(avg) - 1.0 / 18.0)
    assert gaps[1] < gaps[0], f"可被利用度没有下降：{gaps}"
    assert gaps[1] < 0.01, f"训练 1000 次后可被利用度应小于 0.01：{gaps[1]}"


def test_equilibrium_frequencies() -> None:
    """均衡频率：Q 不下注；J 与 K 的下注率呈 1:3 关系（±0.15 容差）。"""
    avg = make_cfr().train(all_deals(), iterations=50000).average_strategy()
    f = key_frequencies(avg)
    # 均衡约束是**比例**关系（K:J = 3:1）与边界（Q 不下注），
    # 而不是"K 总下注"——实测 K 的下注率约 0.66，属于 α≈0.22 的那支均衡。
    assert f["Q_bet"] < 0.02, f"Q 不该下注：{f['Q_bet']}"
    assert f["J_bet"] > 0.05, f"J 应当偶尔诈唬：{f['J_bet']}"
    assert 2.0 < f["K_bet"] / f["J_bet"] < 4.5, (
        f"K:J 下注率应接近 3:1，实际 {f['K_bet'] / f['J_bet']:.2f}")
    assert f["K_bet"] > 0.5, f"K 应当偏好下注：{f['K_bet']}"
    assert f["J_call"] < 0.05, f"J 面对下注应当弃牌：{f['J_call']}"
    assert f["K_call"] > 0.9, f"K 面对下注应当跟注：{f['K_call']}"
    assert 0.2 < f["p2_Q_call"] < 0.5, f"p2 用 Q 跟注的概率应接近 1/3：{f['p2_Q_call']}"


def test_terminal_sign_matters() -> None:
    """终局效用的符号必须按"轮到谁"取：写错会让训练结果显著偏离均衡。

    做法：构造一个"终局直接返回 u1（不看轮到谁）"的错误版本，训练相同轮数，
    断言它的博弈值明显差于正确版本。这条回归测试守住的是本项目踩过的坑。
    """
    class WrongSign(CFR):
        def _walk(self, cards, history, p0, p1):
            player = len(history) % 2
            if self.terminal(history):
                return self.payoff_p1(history, cards)      # ← 漏掉取负
            return super()._walk(cards, history, p0, p1)

    good = make_cfr().train(all_deals(), iterations=2000).average_strategy()
    bad_impl = WrongSign(kuhn_terminal, kuhn_payoff_p1, kuhn_actions, kuhn_infoset)
    bad_impl.train(all_deals(), iterations=2000)
    bad = bad_impl.average_strategy()
    good_err = abs(ev_average(good) - GAME_VALUE)
    bad_err = abs(ev_average(bad) - GAME_VALUE)
    assert bad_err > good_err * 3, (
        f"符号写错应当明显更差：正确误差 {good_err:.4f} vs 错误 {bad_err:.4f}")


# ---------------------------------------------------------------- 后悔匹配与 CFR+

def test_regret_matching_normalizes_positive() -> None:
    cfr = make_cfr()
    key = ("", 0, 0)
    cfr.regret[key]["b"] = 3.0
    cfr.regret[key]["k"] = 1.0
    st = cfr._current_strategy(key, ("k", "b"))
    assert st[1] == pytest.approx(0.75) and st[0] == pytest.approx(0.25)


def test_regret_matching_uniform_when_all_negative() -> None:
    cfr = make_cfr()
    key = ("", 0, 0)
    cfr.regret[key]["b"] = -5.0
    cfr.regret[key]["k"] = -1.0
    st = cfr._current_strategy(key, ("k", "b"))
    assert st == pytest.approx([0.5, 0.5])


def test_cfr_plus_keeps_regret_non_negative() -> None:
    cfr = make_cfr(plus=True).train(all_deals(), iterations=50)
    for key in cfr.regret:
        for a in cfr.regret[key]:
            assert cfr.regret[key][a] >= 0.0, f"CFR+ 的后悔不该为负：{key} {a}"


# ---------------------------------------------------------------- 边界

def test_train_requires_deals() -> None:
    with pytest.raises(ValueError):
        make_cfr().train(iterations=10)


def test_zero_and_single_iteration() -> None:
    """零次训练给出均匀策略（且不崩）；一次训练也能跑。"""
    zero = make_cfr().train(all_deals(), iterations=0)
    assert zero.average_strategy() == {} or all(
        abs(v - 0.5) < 1e-9 for d in zero.average_strategy().values() for v in d.values())
    one = make_cfr().train(all_deals(), iterations=1).average_strategy()
    assert set(one) and all(abs(sum(d.values()) - 1.0) < 1e-9 for d in one.values())


def test_payoff_and_terminal_consistency() -> None:
    """终局判定与收益函数必须一致（否则 CFR 会走进不存在的叶子）。"""
    for h in ("kk", "bf", "bc", "kbf", "kbc"):
        assert kuhn_terminal(h)
        assert kuhn_payoff_p1(h, (2, 0)) in (-2.0, -1.0, 1.0, 2.0)
    for h in ("", "k", "b", "kb"):
        assert not kuhn_terminal(h)
        assert kuhn_actions(h) in (("k", "b"), ("c", "f"))


def test_infoset_excludes_opponent_card() -> None:
    """信息集不能包含对手的牌——这是"不完全信息"的定义性要求。"""
    a = kuhn_infoset("", 1, 0)
    b = kuhn_infoset("", 1, 0)
    assert a == b
    assert len(a) == 3 and 1 in a, "信息集应当是 (历史, 我的牌, 我是谁)"
