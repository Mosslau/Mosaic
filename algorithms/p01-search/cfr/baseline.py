"""对照版：库恩扑克上的两个基线策略。

搜索族的对照对象是**基线算法**（见 references/algorithm-families.md）。
CFR 是"自我博弈学出来的策略"，所以对照要回答两个问题：

1. **比瞎打好多少**：均匀随机策略（每个信息集上等概率选动作）
2. **比固定套路好多少**：几个固定的对手策略（永远弃牌 / 永远跟注 / 总下注）

对照的价值在于量化"训练"本身：CFR 学出来的策略对"永远跟注"这种烂对手
必须能盈利，而且要明显优于均匀随机策略——否则训练没起作用。
"""

CARDS = (0, 1, 2)


def uniform_strategy() -> dict:
    """均匀随机策略：每个信息集上等概率选动作（"没学过的策略"）。"""
    keys = ([("", c, 0) for c in CARDS] + [("k", c, 1) for c in CARDS]
            + [("b", c, 1) for c in CARDS] + [("kb", c, 0) for c in CARDS])
    out = {}
    for h, c, player in keys:
        acts = ("k", "b") if h in ("", "k") else ("c", "f")
        out[(h, c, player)] = {a: 1.0 / len(acts) for a in acts}
    return out


#: 三个固定对手策略（player2 侧）——都在 "k"/"b" 两个信息集上给策略
FIXED_OPPONENTS = {
    "永远弃牌": {
        **{("k", c, 1): {"b": 0.0, "k": 1.0} for c in CARDS},
        **{("b", c, 1): {"c": 0.0, "f": 1.0} for c in CARDS},
    },
    "永远跟注": {
        **{("k", c, 1): {"b": 1.0, "k": 0.0} for c in CARDS},
        **{("b", c, 1): {"c": 1.0, "f": 0.0} for c in CARDS},
    },
    "总是下注": {
        **{("k", c, 1): {"b": 1.0, "k": 0.0} for c in CARDS},
        **{("b", c, 1): {"c": 0.5, "f": 0.5} for c in CARDS},
    },
}


if __name__ == "__main__":
    raise SystemExit("本文件是对照库，跑实验请执行：python3 demo.py")
