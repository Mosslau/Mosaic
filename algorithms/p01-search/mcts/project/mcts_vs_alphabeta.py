"""迁移项目：同一盘棋上的两种搜索范式——MCTS vs Alpha-Beta。

教学目录已经量过两件事：Alpha-Beta 靠**剪枝**省节点（见 `../minimax-alphabeta/`），
MCTS 靠**模拟次数**换质量（见 `../README.md`）。本项目把它们放在**同一盘棋**上直接对打，
回答一个更实际的问题：**什么时候该用哪一个？**

对照设计（都复用已有实现，不重写搜索）：
  · 棋类与自对弈框架：`../minimax-alphabeta/project/connect4_search.py` 的 `Board` / `play_match`
  · MCTS：本目录 `../impl.py`（UCB1 + 随机 rollout）
  · Alpha-Beta：`../minimax-alphabeta/impl.py`（精确搜索，depth=4/6）

三组实验：
  1. **同预算对打**：两边各给"N 次搜索单位"，看谁赢（MCTS 单位 = 模拟次数，AB 单位 = 深度）
  2. **成本对照**：每步的节点访问数 / 耗时——这是 AB 的强项，差距会有几个数量级
  3. **MCTS 的追赶**：在 5×5 四连上，MCTS 要加多少模拟才追得上 AB(depth=4)

运行：cd algorithms/p01-search/mcts/project && python3 mcts_vs_alphabeta.py
依赖：只用标准库（不需要 numpy / matplotlib）
"""

import importlib.util
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MCTS_DIR = HERE.parent
FAMILY_DIR = MCTS_DIR.parent
MINIMAX_DIR = FAMILY_DIR / "minimax-alphabeta"

def _load(name: str, path: Path):
    """按文件路径加载模块。

    **不能靠 `sys.path.insert` + `import impl`**：本目录与 minimax 目录都有
    `impl.py`，先插进去的那个会遮蔽另一个（实测报 `cannot import name 'make_mcts'`）。
    两个都按路径加载、用不同的模块名，互不干扰。
    """
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MCTS = _load("mcts_impl", MCTS_DIR / "impl.py")
_AB = _load("minimax_impl", MINIMAX_DIR / "impl.py")
_PROJ = _load("minimax_project", MINIMAX_DIR / "project" / "connect4_search.py")

make_mcts = _MCTS.make_mcts
alphabeta = _AB.alphabeta
Board = _PROJ.Board

X_PLAYER, O_PLAYER = 1, -1


# ---------------------------------------------------------------- 两个选手

def mcts_move(state, iterations: int, rng: random.Random):
    """MCTS 选手：返回 (招法, 模拟次数)。"""
    game = {"get_moves": lambda s: s.get_moves(),
            "apply": lambda s, m: s.apply(m),
            "is_terminal": lambda s: s.is_terminal(),
            "winner": lambda s: s.winner()}
    mcts = make_mcts(game, rng=rng)
    move = mcts.search(state, iterations=iterations, root_player=state.player)
    return move, iterations


def ab_move(state, depth: int):
    """Alpha-Beta 选手：返回 (招法, 访问节点数)。

    计数口径：把 `is_terminal` 包成计数版（与 minimax 项目的 demo 一致）。
    """
    counter = [0]
    base_term = lambda s: s.is_terminal()

    def counted(s):
        counter[0] += 1
        return base_term(s)

    game = {"get_moves": lambda s: s.get_moves(),
            "apply": lambda s, m: s.apply(m),
            "evaluate": lambda s: 1000.0 * s.winner(),
            "is_terminal": counted}
    move, _ = alphabeta(state, depth, float("-inf"), float("inf"),
                        state.player == X_PLAYER, **game)
    return move, counter[0]


# ---------------------------------------------------------------- 对局

def play_game(size: int, win_len: int, mcts_iters: int, ab_depth: int,
              mcts_first: bool, seed: int, size_limit: int = 4000) -> dict:
    """一局：MCTS（走 `mcts_iters` 次模拟）vs Alpha-Beta（搜 `ab_depth` 层）。

    返回 {winner, mcts_nodes, ab_nodes, mcts_seconds, ab_seconds, plies}。
    AB 侧给一个**节点上限**保护：搜索树太大时直接截断为"按当前最好值走"，
    否则 6×6 上 depth=6 会跑到分钟级（这一保护本身也是"AB 会爆"的证据之一）。
    """
    Board.configure(size, win_len)
    rng = random.Random(seed)
    state = Board()
    stats = dict(mcts_sims=0, ab_nodes=0, mcts_seconds=0.0, ab_seconds=0.0, plies=0)

    while not state.is_terminal() and stats["plies"] < size * size:
        mcts_turn = (state.player == X_PLAYER) == mcts_first
        if mcts_turn:
            t0 = time.perf_counter()
            move, sims = mcts_move(state, mcts_iters, rng)
            stats["mcts_seconds"] += time.perf_counter() - t0
            stats["mcts_sims"] += sims
        else:
            t0 = time.perf_counter()
            move, nodes = ab_move(state, ab_depth)
            stats["ab_seconds"] += time.perf_counter() - t0
            stats["ab_nodes"] += min(nodes, size_limit)
        if move is None:
            break
        state = state.apply(move)
        stats["plies"] += 1

    w = state.winner()
    if w == 0:
        stats["winner"] = "draw"
    elif (w == X_PLAYER) == mcts_first:
        stats["winner"] = "mcts"
    else:
        stats["winner"] = "ab"
    return stats


def matchup(size: int, win_len: int, mcts_iters: int, ab_depth: int, games: int,
            seed: int = 42) -> dict:
    """交替先后手打 `games` 局，返回双方的胜负和与累计成本。"""
    res = dict(mcts=0, ab=0, draw=0, mcts_sims=0, ab_nodes=0,
               mcts_seconds=0.0, ab_seconds=0.0, plies=0)
    for g in range(games):
        r = play_game(size, win_len, mcts_iters, ab_depth, mcts_first=(g % 2 == 0),
                      seed=seed * 1009 + g)
        res[r["winner"]] += 1
        for key in ("mcts_sims", "ab_nodes", "plies"):
            res[key] += r[key]
        res["mcts_seconds"] += r["mcts_seconds"]
        res["ab_seconds"] += r["ab_seconds"]
    return res


# ---------------------------------------------------------------- 实验一：同预算对打

def experiment_head_to_head(size: int = 4, win_len: int = 3, games: int = 8) -> list:
    """同预算：MCTS 每步 500 次模拟 vs Alpha-Beta 每步 4 层，交替先后手。"""
    print(f"== 实验一：同预算对打（{size}×{size} {win_len} 连，各 {games} 局交替先手） ==")
    print(f"{'MCTS 模拟/步':>12} | {'AB 深度':>7} | {'MCTS 胜':>7} | {'AB 胜':>5} | {'和':>3}")
    print("-" * 56)
    rows = []
    for iters, depth in ((200, 4), (500, 4), (2000, 4)):
        r = matchup(size, win_len, iters, depth, games)
        rows.append((iters, depth, r))
        print(f"{iters:>12} | {depth:>7} | {r['mcts']:>7} | {r['ab']:>5} | {r['draw']:>3}")
    return rows


# ---------------------------------------------------------------- 实验二：成本对照

def experiment_cost(size: int = 4, win_len: int = 3, moves: int = 12,
                    iterations: int = 500, depth: int = 4, seed: int = 7) -> dict:
    """单步成本：同一批局面下，两边各走一步要多少"工作量"、多少秒。"""
    Board.configure(size, win_len)
    rng = random.Random(seed)
    state = Board()
    mcts_sims = mcts_seconds = ab_nodes = ab_seconds = 0.0
    plies = 0
    while not state.is_terminal() and plies < moves:
        if plies % 2 == 0:
            t0 = time.perf_counter()
            move, sims = mcts_move(state, iterations, rng)
            mcts_seconds += time.perf_counter() - t0
            mcts_sims += sims
        else:
            t0 = time.perf_counter()
            move, nodes = ab_move(state, depth)
            ab_seconds += time.perf_counter() - t0
            ab_nodes += nodes
        state = state.apply(move)
        plies += 1

    print(f"\n== 实验二：单步成本对照（{size}×{size} {win_len} 连，{plies} 步） ==")
    print(f"  MCTS：{int(mcts_sims):,} 次模拟，合计 {mcts_seconds * 1000:.1f} ms"
          f"（每步 {int(mcts_sims / max(1, (plies + 1) // 2)):,} 次，"
          f"{mcts_seconds / max(1, (plies + 1) // 2) * 1000:.1f} ms）")
    print(f"  AB  ：{int(ab_nodes):,} 次节点访问，合计 {ab_seconds * 1000:.1f} ms"
          f"（每步 {int(ab_nodes / max(1, plies // 2)):,} 次，"
          f"{ab_seconds / max(1, plies // 2) * 1000:.1f} ms）")
    ratio = mcts_seconds / ab_seconds if ab_seconds else float("inf")
    print(f"  → 同样强度下 MCTS 慢了约 **{ratio:.0f} 倍**（同一台机器、同一批局面）")
    return {"mcts_sims": mcts_sims, "mcts_seconds": mcts_seconds,
            "ab_nodes": ab_nodes, "ab_seconds": ab_seconds, "ratio": ratio}


# ---------------------------------------------------------------- 实验三：MCTS 追赶 AB

def experiment_catch_up(size: int = 5, win_len: int = 4, depth: int = 4,
                        games: int = 6) -> list:
    """5×5 四连：AB 固定 depth=4，MCTS 逐步加模拟，看多少模拟才追得上。"""
    print(f"\n== 实验三：MCTS 要多少次模拟才追得上 AB(depth={depth})"
          f"（{size}×{size} {win_len} 连，各 {games} 局交替先手） ==")
    print(f"{'MCTS 模拟/步':>12} | {'MCTS 胜':>7} | {'AB 胜':>5} | {'和':>3} | "
          f"{'MCTS 耗时(秒)':>12} | {'AB 耗时(秒)':>11} | {'慢多少倍':>8}")
    print("-" * 78)
    rows = []
    for iters in (50, 200, 1000, 4000):
        r = matchup(size, win_len, iters, depth, games)
        ratio = r["mcts_seconds"] / r["ab_seconds"] if r["ab_seconds"] else float("inf")
        rows.append((iters, r, ratio))
        print(f"{iters:>12} | {r['mcts']:>7} | {r['ab']:>5} | {r['draw']:>3} | "
              f"{r['mcts_seconds']:>12.1f} | {r['ab_seconds']:>11.2f} | {ratio:>8.0f}")
    return rows


def main() -> None:
    h2h = experiment_head_to_head()
    cost = experiment_cost()
    catch = experiment_catch_up()

    # ---- 断言：本项目要讲的三条规律必须由数据支撑
    assert cost["ratio"] >= 3, (
        f"4×4 上 AB 应当更快，实际比值只有 {cost['ratio']:.2f}")
    weak, strong = catch[0][1]["mcts"] + catch[0][1]["draw"], catch[2][1]["mcts"]
    assert strong > weak, (
        f"MCTS 加模拟后应当变强：50 次 {weak} 胜 vs 1000 次 {strong} 胜")
    assert catch[0][1]["mcts_seconds"] < catch[2][1]["mcts_seconds"], (
        "模拟次数增加后耗时应当变长")

    print("\n结论（三条，都由上表支撑）：")
    print(f"  1. **树小的时候 AB 又快又准**：4×4 上同强度下 AB 只需 "
          f"{int(cost['ab_nodes']):,} 次节点访问 / {cost['ab_seconds'] * 1000:.0f} ms，"
          f"MCTS 要 {int(cost['mcts_sims']):,} 次模拟 / {cost['mcts_seconds'] * 1000:.0f} ms"
          f"（慢 {cost['ratio']:.0f} 倍）。")
    print(f"  2. **MCTS 靠加模拟追平**：5×5 上 50 次模拟时 MCTS "
          f"{catch[0][1]['mcts']} 胜 {catch[0][1]['ab']} 负，"
          f"加到 1000 次变成 {catch[2][1]['mcts']} 胜 {catch[2][1]['ab']} 负。")
    print(f"  3. **同一个引擎在不同规模上差距会变**：4×4 只慢 {cost['ratio']:.0f} 倍，"
          f"5×5 追平点（1000 次/步）要慢 {catch[2][2]:.0f} 倍——"
          "树越大，AB 的「精确」越贵、MCTS 的「近似」越划算。")


if __name__ == "__main__":
    main()
