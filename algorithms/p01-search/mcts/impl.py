"""蒙特卡洛树搜索 MCTS — 手写实现（搜索求解器）

MCTS 是"模拟驱动的决策搜索"，四步循环：
- Selection：从根节点沿 UCB1 选最有价值的子节点
- Expansion：展开未完全探索的节点
- Simulation：从该节点随机走子到终局（rollout）
- Backpropagation：把结果回传，更新路径上各节点的访问次数与累计胜值

本目录的形态由"模拟搜索"决定，没有 fit/predict：
- impl.py     手写 MCTS（UCB1 + 随机 rollout）
- baseline.py 随机策略对照（MCTS 的决策质量从对比中量化）
- demo.py     井字棋上 MCTS vs 随机基线，迭代次数 → 胜率收敛曲线

对弈接口约定（demo.py 用井字棋实现并注入）：
    get_moves(state) -> list[Any]   可走招法
    apply(state, move) -> state     走子后的新状态
    is_terminal(state) -> bool      是否终局
    winner(state) -> Optional[int]  终局赢家（None=平局），用于判断谁赢得本次 rollout

记账口径（**本实现最容易写错的地方**，写反会让整棵树反向选择）：
    每个节点只记一个累计量 `value`，含义是"**走出这一步的那一方**从这一步出发的收益"：
        +1 = 走这一步的一方最终赢；−1 = 输；0 = 平局
    于是节点自己的 `value / visits` 就是"轮到它的**父方**时，选这一步的平均收益"，
    Selection 阶段直接比大小即可，**不需要来回翻符号**。
    回传时每上一层翻转一次：父节点的"走出那一步的一方"正是对手。
"""

import math
import random
from typing import Any, Callable, Optional

Action = Any


class Node:
    """搜索树节点：记自己的统计量、从父节点走过来的那一步、以及那一步是谁走的。"""

    __slots__ = ("state", "parent", "action", "mover", "untried",
                 "children", "visits", "value")

    def __init__(self, state: Any, parent: Optional["Node"] = None,
                 action: Optional[Action] = None, mover: int = 1,
                 untried: Optional[list] = None) -> None:
        self.state = state
        self.parent = parent
        self.action = action               # 父节点走到本节点所用的招法
        self.mover = mover                 # 走出 action 的那一方（+1 / −1）
        self.untried = list(untried or [])
        self.children: dict = {}
        self.visits = 0
        self.value = 0.0                   # 口径见模块 docstring

    def __repr__(self) -> str:
        return f"Node(action={self.action!r}, mover={self.mover:+d}, " \
               f"visits={self.visits}, value={self.value:+.2f})"


class MCTS:
    """蒙特卡洛树搜索。

    用法：
        mcts = MCTS(get_moves, apply, is_terminal, winner, rng=random.Random(0))
        action = mcts.search(state, iterations=1000, root_player=1)
    """

    def __init__(
        self,
        get_moves: Callable,
        apply: Callable,
        is_terminal: Callable,
        winner: Callable,
        rng: Optional[random.Random] = None,
        exploration: float = math.sqrt(2.0),
    ) -> None:
        self.get_moves = get_moves
        self.apply = apply
        self.is_terminal = is_terminal
        self.winner = winner
        self.rng = rng if rng is not None else random.Random()
        self.exploration = exploration     # UCB1 的常数 C（默认 √2）
        self.last_stats: dict = {}         # 上一次 search 的统计，供实验观察

    # ---------------------------------------------------------------- 四个阶段

    def _select(self, node: Node) -> Node:
        """Selection：沿 UCB1 一路向下，直到遇到"还有未试招法"或"终局"的节点。"""
        while not self._terminal(node.state) and not node.untried:
            node = self._best_child(node)
        return node

    def _expand(self, node: Node) -> Node:
        """Expansion：随机挑一个未试过的招法展开。

        随机挑（不是按顺序挑）是为了避免"总是先展开第 0 个招法"的系统偏置；
        随机源用注入的 `rng`，固定种子时结果可复现。
        """
        if not node.untried or self._terminal(node.state):
            return node
        index = self.rng.randrange(len(node.untried))
        action = node.untried.pop(index)
        child_state = self.apply(node.state, action)
        child = Node(child_state, parent=node, action=action, mover=-node.mover,
                     untried=self.get_moves(child_state))
        node.children[action] = child
        return child

    def _simulate(self, state: Any, mover: int) -> float:
        """Simulation：随机走子到终局，返回**走出这一步的那一方**的收益（+1 / 0 / −1）。"""
        while not self._terminal(state):
            moves = self.get_moves(state)
            if not moves:
                break
            state = self.apply(state, self.rng.choice(moves))
        w = self.winner(state)
        if w is None or w == 0:            # 平局
            return 0.0
        return 1.0 if w == mover else -1.0

    def _backpropagate(self, node: Node, reward_for_mover: float) -> None:
        """Backpropagation：沿路径回传，**每上一层翻转一次符号**。"""
        r = reward_for_mover
        while node is not None:
            node.visits += 1
            node.value += r
            r = -r                         # 父节点的"走出那一步的一方"是对手
            node = node.parent

    # ---------------------------------------------------------------- 选择与查询

    def _best_child(self, node: Node) -> Node:
        """UCB1 选子节点：胜率项 + 探索项。未访问过的子节点优先（探索项当 ∞）。"""
        log_parent = math.log(node.visits) if node.visits > 1 else 0.0

        def ucb(child: Node) -> float:
            if child.visits == 0:
                return float("inf")
            return (child.value / child.visits
                    + self.exploration * math.sqrt(log_parent / child.visits))

        return max(node.children.values(), key=ucb)

    def _terminal(self, state: Any) -> bool:
        return bool(self.is_terminal(state)) or not self.get_moves(state)

    def search(self, state: Any, iterations: int = 1000,
               root_player: int = 1) -> Optional[Action]:
        """在给定局面下模拟 `iterations` 次，返回**访问次数最多**的招法。

        参数：
            state: 当前局面（轮到 `root_player` 走）
            iterations: 模拟次数——MCTS 唯一的质量旋钮
            root_player: 根局面轮到谁走（决定回传时的收益符号）

        返回：
            选中的招法；无可走招法时返回 None。

        为什么按**访问次数**而不是胜率选：访问少的分支胜率可能是 1/1（虚高），
        按访问次数选是 MCTS 的标准做法，等价于"最被信任的那一步"。
        """
        moves = self.get_moves(state)
        if not moves:
            return None
        if len(moves) == 1:
            return moves[0]

        root = Node(state, mover=-root_player, untried=list(moves))
        for _ in range(iterations):
            node = self._select(root)
            node = self._expand(node)
            reward = self._simulate(node.state, node.mover)
            self._backpropagate(node, reward)

        self.last_stats = {
            "iterations": iterations,
            "visits": {a: c.visits for a, c in root.children.items()},
            "win_rate": {a: (c.value / c.visits if c.visits else 0.0)
                         for a, c in root.children.items()},
        }
        return max(root.children, key=lambda a: root.children[a].visits)


def make_mcts(game: dict, rng: Optional[random.Random] = None,
              exploration: float = math.sqrt(2.0)) -> MCTS:
    """从对弈接口字典构造 MCTS（demo 与 project 都走这里，避免各处重复拼参数）。"""
    return MCTS(game["get_moves"], game["apply"], game["is_terminal"], game["winner"],
                rng=rng, exploration=exploration)


if __name__ == "__main__":
    raise SystemExit("本文件是搜索库，跑实验请执行：python3 demo.py")
