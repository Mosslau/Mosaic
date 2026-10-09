"""反事实遗憾最小化（CFR）—— 手写实现（搜索求解器）

CFR 解决的是**不完全信息博弈**：我看不到对手的牌，所以 minimax/MCTS 那种
"把状态当公共知识"的搜索全部失效。CFR 换了个思路：

    不去算"哪个动作最好"，而是**让每个信息集上各动作的累计后悔趋于平衡**——
    当一个信息集上所有动作的后悔都不再增长，就没有动作能被长期改进，
    这个策略就是纳什均衡。

三个概念（本实现的全部内容）：
  · **信息集（infoset）**：我"知道什么"——在我的视角下无法区分的世界状态的集合。
    库恩扑克里就是 `(我看到的动作历史, 我手上的牌)`；**对手的牌不在里面**。
  · **反事实价值**：假设我自己一路打到这里（概率 1），只按对手到达这里的概率加权，
    这个动作能带来多少收益。"反事实"= 不考虑我自己走到这里的概率。
  · **后悔匹配**：把正后悔归一化成下一轮的动作概率（负后悔截断为 0）。

本目录的形态由"自我博弈训练"决定，没有 fit/predict：
- impl.py    手写 CFR（当前行动者视角回传 + 信息集后悔表）
- baseline.py 对照版：均匀随机策略 + 一个固定策略（量化"学出来比瞎打好多少"）
- demo.py    库恩扑克上学到纳什均衡：与教科书解析解逐项对照

对弈接口约定（demo.py 注入具体博弈）：
    terminal(history)  -> bool             是否终局
    payoff_p1(history, cards) -> float     终局时 player1 的效用（零和）
    actions(history)   -> tuple[str, ...]  当前可行动作
    infoset(history, card, player) -> key  信息集标识
"""

import itertools
import random
from collections import defaultdict
from typing import Callable, Iterable, Optional


class CFR:
    """反事实遗憾最小化。

    用法：
        cfr = CFR(terminal, payoff_p1, actions, infoset)
        cfr.train(deals, iterations=10000)         # deals: 所有可能发牌的列表
        strategy = cfr.average_strategy()          # 平均策略（这才是收敛到均衡的那个）
    """

    def __init__(self, terminal: Callable, payoff_p1: Callable,
                 actions: Callable, infoset: Callable,
                 plus: bool = False) -> None:
        self.terminal = terminal
        self.payoff_p1 = payoff_p1
        self.actions = actions
        self.infoset = infoset
        self.plus = plus                      # CFR+：后悔截断到非负（收敛快得多）
        self.regret: dict = defaultdict(lambda: defaultdict(float))
        self.strategy_sum: dict = defaultdict(lambda: defaultdict(float))

    # ---------------------------------------------------------------- 策略

    def _current_strategy(self, key, acts: Iterable[str]) -> list:
        """后悔匹配：正后悔归一化；全非正则取均匀。"""
        acts = tuple(acts)
        positive = [max(self.regret[key][a], 0.0) for a in acts]
        total = sum(positive)
        if total > 0:
            return [p / total for p in positive]
        return [1.0 / len(acts)] * len(acts)

    def average_strategy(self) -> dict:
        """平均策略：按**自身到达概率**加权的历史策略平均。

        为什么不能用最后一轮策略：CFR 的当前策略会持续震荡（它一直在"追"后悔），
        收敛的是**平均策略**——这是 CFR 最容易被忽略的一点。
        """
        out = {}
        for key, sums in self.strategy_sum.items():
            acts = tuple(sums.keys())
            total = sum(sums.values())
            if total > 0:
                out[key] = {a: sums[a] / total for a in acts}
            else:
                out[key] = {a: 1.0 / len(acts) for a in acts}
        return out

    # ---------------------------------------------------------------- 训练

    def _walk(self, cards, history: str, p0: float, p1: float) -> float:
        """返回**当前行动者**的期望效用（零和）。

        关键细节：终局效用也要按"轮到谁"取符号——轮到 player1 时是 u1，
        轮到 player2 时是 −u1。漏掉这一处符号，策略会"看起来收敛"但仍然可被利用。
        """
        player = len(history) % 2
        if self.terminal(history):
            u1 = self.payoff_p1(history, cards)
            return u1 if player == 0 else -u1

        acts = tuple(self.actions(history))
        key = self.infoset(history, cards[player], player)
        strategy = self._current_strategy(key, acts)

        action_utils, node_util = [0.0] * len(acts), 0.0
        for i, a in enumerate(acts):
            if player == 0:
                child = self._walk(cards, history + a, p0 * strategy[i], p1)
            else:
                child = self._walk(cards, history + a, p0, p1 * strategy[i])
            action_utils[i] = -child                     # 子节点返回的是对手视角
            node_util += strategy[i] * action_utils[i]

        # 反事实权重：对手到达概率（"假设我一定走到这里"）
        opponent_reach, own_reach = (p1, p0) if player == 0 else (p0, p1)
        for i, a in enumerate(acts):
            regret = opponent_reach * (action_utils[i] - node_util)
            if self.plus:
                self.regret[key][a] = max(self.regret[key][a] + regret, 0.0)
            else:
                self.regret[key][a] += regret
            self.strategy_sum[key][a] += own_reach * strategy[i]
        return node_util

    def train(self, deals: Optional[list] = None, iterations: int = 10000,
              rng: Optional[random.Random] = None) -> "CFR":
        """训练。

        参数 `deals`：所有可能的"发牌"（本实现把每个 deal 当成一次完整遍历）。
        遍历全部 deal（而不是采样）是 CFR 的**确定性**版本，收敛更稳、结果可复现。
        """
        if deals is None:
            raise ValueError("必须提供 deals（否则无法枚举对手的私有状态）")
        for _ in range(iterations):
            for cards in deals:
                self._walk(cards, "", 1.0, 1.0)
        return self

    # ---------------------------------------------------------------- 观察

    def positive_regret(self) -> float:
        """累计正后悔（收敛指标：训练足够久后应停止增长）。"""
        return sum(max(self.regret[k][a], 0.0)
                   for k in self.regret for a in self.regret[k])

    def best_action(self, key) -> Optional[str]:
        """某个信息集上的平均策略最优动作。"""
        avg = self.average_strategy().get(key)
        if not avg:
            return None
        return max(avg, key=lambda a: avg[a])
