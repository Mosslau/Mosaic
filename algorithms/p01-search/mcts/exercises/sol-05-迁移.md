# 参考解：第 5 题（迁移）

这题要**动手改 `impl.py`**，所以没有独立脚本——下面是完整的做法与实测结论。

## 1. 改 rollout 策略

把 `MCTS._simulate` 里的"纯随机"换成"以概率 p 走启发式招法，否则随机"：

```python
def _simulate(self, state, mover):
    while not self._terminal(state):
        moves = self.get_moves(state)
        if not moves:
            break
        if self.rng.random() < 0.5:
            move = greedy_move(state, self.get_moves, self.apply, self.winner,
                               me=self._player_of(state), rng=self.rng)
        else:
            move = self.rng.choice(moves)
        state = self.apply(state, move)
    ...
```

其中"启发式招法"就是 `baseline.greedy_move`（能赢就赢 / 能挡就挡）；
`_player_of(state)` 需要知道当前轮到谁（用与根局面的走子数奇偶推出，或把 `mover` 沿路径带下来）。

## 2. 重新扫探索常数 C（对精确搜索、`iterations=10`、各 40 局）

| C | 纯随机 rollout 的不输率（原始实验三） | 混合 rollout（p=0.5）的不输率 |
|---|---|---|
| 0.00（纯利用） | **62%** | 见你的实测 |
| 0.50 | 48% | 见你的实测 |
| 1.41（默认） | 45% | 见你的实测 |
| 3.00 | 48% | 见你的实测 |

> 上表右列**故意留空**：这题的关键不是"另一个数字是多少"，而是**你要亲眼看它变了**。
> 参考做法：复制 `make_teaching_assets.py` 里的 `exploration_rows()`，把 `_play_vs_exact`
> 换成混合 rollout 版本，跑一遍即可。

## 3. 该期待什么（以及为什么）

- **混合 rollout 之后，最优 C 会往大的方向移。** 因为 rollout 变准了 ⇒ 每个分支的估值
  **方差更小**（不再是"乱下一通"），于是"多试几个分支"的收益变大、探索更划算；
  纯利用的优势（省次数）相对下降。
- **不输率的绝对水平也会提高**（在同样的 10 次模拟下）：rollout 更准相当于给每次模拟
  塞进了更多信息——这正是 AlphaZero 路线"用学习换模拟"要表达的东西：
  把知识塞进 rollout / 估值里，比单纯加模拟次数更有效。
- **另一条可能观察**：如果 p 太大（比如 p=1，rollout 完全按贪心走），
  模拟会变得**同质化**——同一个局面每次模拟几乎走出一样的线，样本多样性下降，
  反而可能变差。这也是"改进组件要重新调参"的另一面。

## 4. 这条练习要落到的结论

**组件改动会改变最优超参数。** 实验三说明"模拟次数少 ⇒ 纯利用更好"，
本题说明"rollout 变准 ⇒ 探索又变得划算"。所以 C 不是可以抄来的常数，
它必须与**模拟次数**和**rollout / 估值质量**一起调——真实引擎里这个参数是拿自对弈
反复扫出来的（AlphaZero 的 `c_puct` 就是这么定的）。

## 5. 与第 4 题的呼应

第 4 题用**先验**（PUCT）解决"次数少"的问题，本题用**更好的 rollout** 解决同一个问题——
两条路都在做同一件事：**让每一次模拟更值钱**。这也是 MCTS 系列演进的唯一主线。
