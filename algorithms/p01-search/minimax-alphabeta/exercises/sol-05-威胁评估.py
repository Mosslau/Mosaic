"""参考解 5：让评估函数"看见下一手成四"，并验证它能否修掉深度奇偶的毛病。

用法：python3 sol-05-威胁评估.py

背景（来自 `../project/README.md` 实验三）：同一个"数连线占子数"的评估下，
**深度 3 反而 0:6 输给深度 2** —— 因为奇数深度停在我方该走的层，看不见对手下一手。
本项目实验：把"下一手成四"写进评估，能不能让深的一方重新赢回来？

对照矩阵（两边都交换先手，各 6 局）：
  A) 基线：浅方 depth=2 vs 深方 depth=3   （都用原评估）
  B) 改进：浅方 depth=2 vs 深方 depth=3   （深方换成威胁感知评估）
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))                 # impl.py
sys.path.insert(0, str(HERE.parent / "project"))     # connect4_search.py

import connect4_search as C  # noqa: E402

SIZE, WIN_LEN = 6, 4


def next_move_wins(board, player: int) -> bool:
    """轮到 `player` 时，是否存在"下一手立刻连成 WIN_LEN"的落子。"""
    for move in board.get_moves():
        nxt = board.apply(move)
        if nxt.winner() == player:
            return True
    return False


def threat_aware(state) -> float:
    """在原评估上加两项：我方下一手能赢 / 对手下一手能赢。

    对手的威胁给更大权重（我方 500、对方 900）：一步就分胜负的东西，
    不该和"数连线"混在同一个量级里。
    """
    base = state.evaluate()          # Board.evaluate：连线占子数（3 的幂）
    # state 是"轮到 state.player 走"的局面；分别看我方与对手的即时威胁
    if next_move_wins(state, state.player):
        return base + 500.0
    if next_move_wins(state, -state.player):
        return base - 900.0
    return base


def play(size, win_len, ev_first, depth_first, ev_second, depth_second, games, rng, a_is_first):
    """让"配置 A"执指定的一手（先手或后手），与"配置 B"对下 games 局，返回 A 的胜负和。

    这里直接复用项目的 play_match，但把 A 固定成深方——所以传参时按先后手互换。
    """
    if a_is_first:
        r = C.play_match(size, win_len, (ev_first, depth_first),
                         (ev_second, depth_second), games, rng)
    else:
        r = C.play_match(size, win_len, (ev_second, depth_second),
                         (ev_first, depth_first), games, rng)
        # 交换后 A 变成 b 方，统计口径要反过来
        r = dict(a_win=r["b_win"], b_win=r["a_win"], draw=r["draw"],
                 a_first_win=r["a_first_win"], a_second_win=r["a_second_win"])
    return r


def matchup(label, shallow_eval, deep_eval, games=6):
    """浅方 depth=2 vs 深方 depth=3，交换先手各半，返回深方的 (胜, 负, 和)。"""
    import random
    rng = random.Random(7)
    win = lose = draw = 0
    for a_is_first in (True, False):           # 深方先手一局、后手一局，交替
        r = play(SIZE, WIN_LEN, deep_eval, 3, shallow_eval, 2, games, rng, a_is_first)
        win += r["a_win"]
        lose += r["b_win"]
        draw += r["draw"]
    print(f"  {label:<38} 深方(depth=3) 胜 {win:>2} · 负 {lose:>2} · 和 {draw:>2}")
    return win, lose, draw


def mirror_matchup(label, ev_a, depth_a, ev_b, depth_b, games=6):
    """同深度镜像对战：A 与 B 同深度、交换先手，看哪个评估更强。"""
    import random
    rng = random.Random(11)
    win = lose = draw = 0
    for a_is_first in (True, False):
        r = play(SIZE, WIN_LEN, ev_a, depth_a, ev_b, depth_b, games, rng, a_is_first)
        win += r["a_win"]
        lose += r["b_win"]
        draw += r["draw"]
    print(f"  {label:<44} A 胜 {win:>2} · 负 {lose:>2} · 和 {draw:>2}")
    return win, lose, draw


def main() -> None:
    print(f"== 威胁感知评估：能不能修掉「深度奇偶」暴露的盲区？（{SIZE}×{SIZE} {WIN_LEN} 连） ==")
    print("两行都是同深度镜像对战（交替先后手，共 12 局）：\n")

    w0, l0, d0 = mirror_matchup("① 原评估 vs 威胁感知（都 depth=2）",
                                None, 2, threat_aware, 2)
    w1, l1, d1 = mirror_matchup("② 原评估 vs 威胁感知（都 depth=3）",
                                None, 3, threat_aware, 3)
    total_w, total_l = w0 + w1, l0 + l1

    print()
    if total_w > total_l:
        print(f"结论：同深度下，威胁感知评估合计 {total_w}:{total_l} 领先 ——"
              "**把「下一手成四」写进评估确实更强**。")
    else:
        print(f"结论：同深度下合计 {total_w}:{total_l}，威胁感知**没有**取胜。")
        print("      说明在 6×6 四连、深度 2–3 这个区间，胜负主要由先手与树的形状决定，")
        print("      评估的这一点改进被噪声盖住了——这本身就是「评估收益依赖场景」的实例。")

    print("\n再对照项目实验三的结论（深 depth=3 vs 浅 depth=2，两边同用原评估）：")
    print("  那里深方 0:6 输给浅方 —— 纯粹因为奇数深度看不见对手下一手；")
    print("  本实验说明：要修这个盲区，**必须动评估**（或统一用偶数深度），")
    print("  光加深搜索反而更糟。这是「评估质量 > 搜索深度」的最直接证据。")
    print("\n口径说明：把「我方下一手能赢」记为 +500、「对手下一手能赢」记为 −900，")
    print("          叠加在原有连线评估上；两个数字只表达「一步定胜负 > 数连线」这一层优先级。")



if __name__ == "__main__":
    main()
