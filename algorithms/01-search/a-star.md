# A* 启发式搜索

> 状态：📖 理论文档（实验实现见 `a-star/` 目录）
> 对应文档章节：`roadmap/人工智能代表算法演进路线.md` 第 2.2.1 章

## 设计原理

**解决什么问题**：在状态空间（网格地图、游戏地图、路网）中找起点到终点的最短路径，且**利用终点方向信息加速**。

**核心思想一句话**：在 Dijkstra 的累计代价 g(n) 上加一个对终点的估计 h(n)，按 f(n) = g(n) + h(n) 排序——g 保最优性，h 给方向感。

**为什么比前两个都好**：

- 比 Dijkstra 快：Dijkstra 只回头看（g），全向无差别膨胀；A* 加了指南针，波前被拉成朝终点的椭圆，绕开大量无用区域
- 比贪心稳：贪心只向前看（h），容易被障碍带偏且不保证最优；A* 里的 g 像安全带，"已经花掉的代价"会惩罚瞎绕路，保证找到的路径不劣于最优解

1968 年由 Hart、Nilsson、Raphael 在斯坦福研究院为 Shakey 机器人寻路提出，是 AI 史上引用最广的算法之一。

## 数学推导

**评价函数**：

```
f(n) = g(n) + h(n)
```

- g(n)：起点 → n 的**实际**累计代价
- h(n)：n → 终点的**估计**代价（启发函数，来自领域知识）
- f(n)：经过 n 的整条路径的估计总代价

**关键性质 1：可采纳性（admissibility）**

> h(n) ≤ h*(n) 对所有 n 成立（h* 为真实剩余代价），即 **h 永不高估**，则 A* 树搜索保证最优。

**证明（反证）**：假设 A* 先扩展了次优终点 G（f(G) > C*，C* 为最优代价）。最优路径上必有未扩展节点 n。由可采纳性：

```
f(n) = g(n) + h(n) ≤ g(n) + h*(n) = C* < f(G)
```

n 的优先级高于 G，应先扩展 n——矛盾。故先弹出的终点必最优。

**关键性质 2：一致性（consistency / monotonicity）**

> h(n) ≤ c(n, n') + h(n') 对所有相邻 (n, n') 成立（三角不等式）。

一致性 ⇒ 可采纳性（沿最优路径归纳）。一致性下每个节点**至多扩展一次**（弹出时 g 已最终），closed 集判重安全，无需"重开"逻辑——图搜索版本的 A* 因此简单高效。网格上曼哈顿/欧氏/对角距离均天然一致。

**主导性（dominance）**：若 h₁ 和 h₂ 都可采纳且 h₂(n) ≥ h₁(n) 处处成立，则 h₂ 扩展的节点数 ≤ h₁——**h 越接近真实值（但不超过），搜索越高效**。取多个可采纳 h 的 max 仍可采纳，是常用的组合技巧。

**复杂度**：时间/空间最坏均为 O(b^d)，但实际强烈依赖 h 质量。绝对误差 Δ = h* - h 时，扩展节点数约为 O(b^Δ)——**好启发式是指数级收益**。

## 手写实现要点

实验实现见 `a-star/impl.py`：

```python
import heapq, itertools

def astar(grid, start, goal, heuristic):
    counter = itertools.count()          # 平局破解，保证堆元素可比
    heap = [(heuristic(start, goal), next(counter), start)]
    g_score = {start: 0}
    came_from = {}
    closed = set()
    while heap:
        f, _, node = heapq.heappop(heap)
        if node == goal:
            return reconstruct(came_from, node)
        if node in closed:
            continue                     # 过期堆项
        closed.add(node)
        for nb, cost in neighbors(grid, node):
            g2 = g_score[node] + cost
            if g2 < g_score.get(nb, float('inf')):
                g_score[nb] = g2
                came_from[nb] = node
                heapq.heappush(heap, (g2 + heuristic(nb, goal), next(counter), nb))
    return None                          # 无解
```

**容易踩的坑**：

- **平局处理**：heapq 比较 f 相等的元组时会继续比第二个元素；坐标元组可比，但若存自定义对象会 TypeError。用单调计数器（`itertools.count()`）是最稳的解法
- **过期堆项**：heapq 无 decrease-key；发现更优 g 时直接再入堆，弹出时用 closed 判重跳过。别试图原地改堆
- **终点判断在弹出时**，不是入队时——入队顺序不反映最优性
- **closed 判重的前提是一致性**：h 不一致时节点可能以更优 g 再次出现，需要重开逻辑（一致性启发式下省略是安全的）
- **障碍地图连通性**：demo 生成随机障碍后必须 BFS 预检起点终点连通，否则跑出一个无解
- 八方向网格注意对角移动的代价是 √2，h 也要相应换成对角距离，否则高估失去可采纳性

## 框架对照

A* 不在 sklearn/PyTorch 体系内（它是离散搜索，不是数值优化）。实验对照是**基线算法 Dijkstra**（实现见 `a-star/baseline.py`，等价于 h ≡ 0 的 A*）：

| 维度 | Dijkstra (h ≡ 0) | A* (曼哈顿 h) |
|---|---|---|
| 路径长度 | 最短 | 最短（**必须相等**，作断言验证） |
| 扩展节点数 | 多（圆形波前） | 少（椭圆波前） |
| 耗时 | 长 | 短 |
| 波前形状 | 无方向 | 朝终点拉伸 |

**同图双跑，路径长度断言相等**——最优性没丢；**扩展节点数差值 = 启发式 h 的量化贡献**。这是本实验的核心论证。

## 实验结果（预期）

- 开阔地图：A* 扩展节点数约为 Dijkstra 的 30-60%
- 障碍复杂地图：差距拉大至 5-10 倍；U 形障碍下贪心翻车、A* 仍最优
- 可视化：Dijkstra 的 closed 集是圆形波纹，A* 是朝终点拉伸的椭圆

## 局限与延伸

- **内存瓶颈**：open 集可能指数膨胀，大图先爆内存而非超时 → **IDA\***（迭代加深 + DFS 骨架，内存线性）、**SMA\***（有界内存）
- **h 设计是艺术**：h 太小退化为 Dijkstra，h 太大失去最优性 → 从**松弛问题**（relaxed problem）自动派生 h 是系统方法（如忽略障碍的直线距离 = 忽略约束的松弛解）
- **牺牲最优换速度**：加权 A*（f = g + w·h，w > 1，w-可采纳界内次优）、Anytime A*
- **网格专用加速**：JPS（Jump Point Search，利用网格对称性剪掉大量等价路径，快一个数量级）
- **工程版路网**：CH（Contraction Hierarchies）、ALT（A* + 地标 + 三角不等式）
- **Agent 语境**：A* 是"符号规划"的经典代表，与 LLM Agent 的搜索规划（Tree of Thoughts、MCTS、ReAct 的多步推理）一脉相承——本目录后续 Minimax / MCTS 正是这条线的延续
