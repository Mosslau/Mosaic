"""参考解 5：Leduc 扑克（6 张牌 + 公共牌）上的 CFR。

用法：python3 sol-05-迁移.py

与库恩扑克的两个关键差别（本题考点）：
  1. **牌有重复**（J/Q/K 各 2 张）；
  2. **有公共牌**（chance 节点）→ 信息集**必须包含公共牌**。

历史编码用 `|` 分段（必须是**字符串**，与 impl.CFR 的接口一致）：
    "k"           第一轮过牌
    "kb"          第一轮过牌后被下注
    "kk|Q|"       第一轮看牌到底 → 公共牌 Q → 第二轮刚开始
    "kk|Q|b"      第二轮下注
三段：`第一轮动作 | 公共牌 | 第二轮动作`。

**本题踩过的坑（值得写下来）**：
  · 用扁平的 "r0"/"r1" 追加公共牌，会让"取本轮动作"的切片假设失效 → 无限递归；
  · 弃牌在第一轮就结束整手牌，**不该**进第二轮（早期版本让它进了）；
  · 第一轮与第二轮的终局动作字符串完全相同（"kk"、"bc"），必须靠分段区分。
"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from impl import CFR  # noqa: E402

sys.setrecursionlimit(20000)

DECK = (0, 1, 2, 3, 4, 5)                        # J/Q/K 各 2 张
RANK = {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 2}
RANK_NAME = {0: "J", 1: "Q", 2: "K"}
SETTLED = ("kk", "bc", "kbc")                    # 本轮看牌到底
FOLDED = ("bf", "kbf")                           # 本轮以弃牌结束


# ---------------------------------------------------------------- 历史工具

def parts(history: str) -> list:
    """拆成 [第一轮动作, 公共牌, 第二轮动作]（没到第二轮时后两段为空）。"""
    seg = history.split("|")
    while len(seg) < 3:
        seg.append("")
    return seg


def battle(history: str) -> str:
    """当前这一轮的动作序列。"""
    seg = parts(history)
    return seg[0] if seg[1] == "" else seg[2]


def board_of(history: str):
    """公共牌（字符串形式的牌力 J/Q/K），未发出则为 None。"""
    b = parts(history)[1]
    return b if b else None


def current_round(history: str) -> int:
    return 1 if parts(history)[1] == "" else 2


def leduc_terminal(history: str) -> bool:
    if battle(history) in FOLDED:
        return True                                  # 弃牌立即结束整手牌
    if current_round(history) == 2 and battle(history) in SETTLED:
        return True                                  # 第二轮看牌到底 → 摊牌
    return False


def leduc_actions(history: str) -> tuple:
    return ("k", "b") if battle(history) in ("", "k") else ("c", "f")


def advance(history: str, board: int) -> str:
    """第一轮看牌到底 → 发公共牌 → 第二轮开始。"""
    return f"{battle(history)}|{RANK_NAME[RANK[board]]}|"   # board 是牌 ID，先折算牌力


def leduc_payoff_p1(history: str, cards) -> float:
    p1, p2 = cards[0], cards[1]                      # 私有牌；公共牌在历史里
    acts = battle(history)
    if acts == "bf":  return 1.0                     # 第一轮对手弃牌
    if acts == "kbf": return -1.0
    pot = 1.0 if acts == "kk" else 2.0               # 摊牌底池
    b = board_of(history)
    br = {"J": 0, "Q": 1, "K": 2}[b] if b else None
    s1 = (1 if br is not None and RANK[p1] == br else 0, RANK[p1])
    s2 = (1 if br is not None and RANK[p2] == br else 0, RANK[p2])
    return pot if s1 > s2 else -pot


def leduc_infoset(history: str, card: int, player: int):
    """信息集 =（我的私有牌, 公共牌, 本轮动作, 我是谁）——不含对手私有牌。"""
    return (card, board_of(history), battle(history), player)


def all_deals() -> list:
    return [(a, b, c) for a in DECK for b in DECK for c in DECK if len({a, b, c}) == 3]


def enumerate_infosets() -> int:
    """直接**按信息集定义**枚举数量（不遍历发牌、不展开博弈树）。

    信息集 = (我的牌, 公共牌, 本轮动作, 我是谁)：
      · 我的牌：6 种具体牌 · 公共牌：3 种牌力
      · 本轮动作 ∈ {"", k, b, kb} · 我是谁：2
    两轮各一份 → 直接相乘。早期用"遍历 120 种发牌 + 展开全树"数，几十秒跑不完；
    按定义枚举是毫秒级——**先想清楚"要数的东西是什么"，再决定怎么数**。
    """
    return 2 * len(DECK) * 3 * 4


def transition(history: str, cards):
    """机会节点：第一轮看牌到底 → 发公共牌（本轮发牌里的第三张）。

    返回新历史，或 None（不需要转移）。
    这一步**必须由使用方显式处理**：impl.CFR 的 `_walk` 只按"动作"递归，
    它不知道"什么时候该发公共牌"。早期版本没处理 → 第二轮永远进不去、
    第一轮无限重来 → RecursionError。
    """
    if battle(history) in SETTLED and current_round(history) == 1:
        return advance(history, cards[2])
    return None


class LeducCFR(CFR):
    """在 _walk 里加入机会节点转移的 CFR（其余逻辑完全复用 impl.CFR）。"""

    def _walk(self, cards, history, p0, p1):
        nxt = transition(history, cards)
        if nxt is not None:
            return self._walk(cards, nxt, p0, p1)
        return super()._walk(cards, history, p0, p1)


def evaluate_vs_uniform(strategy: dict) -> float:
    """对均匀随机对手的期望收益（Leduc 信息集太多，暴力最佳回应不可行）。"""
    tot = 0.0
    for cards in all_deals():
        def rec(h: str) -> float:
            if leduc_terminal(h):
                return leduc_payoff_p1(h, cards)
            if battle(h) in SETTLED and current_round(h) == 1:
                return rec(advance(h, cards[2]))          # 发公共牌，进第二轮
            acts = leduc_actions(h)
            player = len(battle(h)) % 2
            probs = strategy.get(leduc_infoset(h, cards[player], player))
            if probs is None:
                probs = {a: 1.0 / len(acts) for a in acts}
            return sum(probs.get(a, 0.0) * rec(h + a) for a in acts)
        tot += rec("")
    return tot / len(all_deals())


def main() -> None:
    deals = all_deals()
    print("== Leduc 扑克的规模 ==")
    print(f"  牌堆 6 张（J/Q/K 各 2 张）：发牌组合 {len(deals)} 种（库恩扑克只有 6 种）")
    n_info = enumerate_infosets()
    print(f"  信息集数量：**{n_info}**（库恩扑克 12 个）—— 放大约 {n_info / 12:.0f} 倍")
    print("  → 这就是「为什么更贵」的直接答案：博弈树宽了一个量级。")

    print(f"\n== 训练（每轮遍历全部 {len(deals)} 种发牌） ==")
    print(f"{'训练量':>8} | {'对均匀随机的收益':>16} | {'耗时(秒)':>9}")
    print("-" * 42)
    last = None
    for iters in (1, 10, 100, 1000):
        t0 = time.perf_counter()
        cfr = LeducCFR(leduc_terminal, leduc_payoff_p1, leduc_actions, leduc_infoset)
        cfr.train(deals, iterations=iters)
        sec = time.perf_counter() - t0
        val = evaluate_vs_uniform(cfr.average_strategy())
        print(f"{iters:>8} | {val:>16.4f} | {sec:>9.2f}")
        last = (iters, val, sec)

    print("\n→ 结论（都由上表数字读出）：")
    print(f"   · 信息集 12 → {n_info}（{n_info / 12:.0f} 倍）、发牌 6 → {len(deals)}（{len(deals) / 6:.0f} 倍）：")
    print(f"     每轮成本随之上涨，但**绝对值仍然很小**——训练 {last[0]} 轮只要 {last[2]:.2f} 秒。")
    print("   · 所以「Leduc 已经大到不能用 CFR」是**错的**：它是教学规模的不完全信息博弈，")
    print("     CFR 在它上面完全跑得动（真实研究里 Leduc 正是标准测试床）。")
    print("   · 真正让「裸 CFR」失效的是**德州扑克那个量级**（状态数 ~10^160）：")
    print("     那时必须引入抽象 + 采样；本项目在 Leduc 上还没触到那个边界。")
    print("   · 本题真正的收获是**迁移的接口代价**：加了公共牌之后，CFR 的 _walk 不再够用——")
    print("     必须自己处理**机会节点**（见本文件的 LeducCFR）。")
    print("   · 本题的「可被利用度」没算：Leduc 的最佳回应无法像库恩扑克那样暴力枚举 64 种纯策略，")
    print("     所以退化成对固定对手的收益指标（这个取舍本身就是本题要体会的）。")


if __name__ == "__main__":
    main()
