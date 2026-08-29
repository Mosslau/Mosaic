# 01-search 搜索算法家族总览

> 六份文档的导航页 + 家族关系速查

## 统一框架

所有图搜索共享同一个循环：

```
frontier = {start}
while frontier:
    node = frontier.pop_by_priority()   # ← 唯一的区别在这里
    if node == goal: return path
    frontier.add(expand(node))
```

**换一个优先级函数，就得到另一个算法**：

| 算法 | 优先级函数 | 数据结构 | 最优? | 完备? | 时间 | 空间 |
|---|---|---|---|---|---|---|
| [DFS](dfs.md) | 最新优先（深度最大） | 栈 | ❌ | ❌（无限深） | O(b^m) | **O(b·m)** |
| [BFS](bfs.md) | 最早优先（深度最小） | 队列 | ✅（无权） | ✅ | O(b^d) | O(b^d) |
| [UCS](ucs.md) | g 最小 | 优先队列 | ✅（非负权） | ✅ | O((b+E)log V) | O(V) |
| [Dijkstra](dijkstra.md) | g 最小（=UCS） | 优先队列 | ✅（非负权） | ✅ | O((V+E)log V) | O(V) |
| [贪心启发式](heuristic-greedy.md) | h 最小 | 优先队列 | ❌ | 有限图✅ | O(b^m) | O(b^m) |
| [A*](a-star.md) | f = g + h 最小 | 优先队列 | ✅（h 可采纳） | ✅ | 依赖 h 质量 | O(b^d) |

## 特例关系（一张表记住整个家族）

| 关系 | 读法 |
|---|---|
| BFS = 边权全 1 的 UCS | 按层扩展 = 按代价扩展（代价全是 1） |
| Dijkstra = h ≡ 0 的 A* | 没有方向信息的 A* |
| 贪心 = g ≡ 0 的 A* | 没有代价意识的 A* |
| UCS ≡ Dijkstra | 同一算法的 AI 名与图论名 |
| 加权 A*：f = g + w·h | w→0 是 Dijkstra，w→∞ 是贪心，w=1 是标准 A* |

## 两个对偶维度

```
                 不看代价 g          看代价 g
不看方向 h  │     DFS / BFS     │   UCS / Dijkstra   │
看方向 h    │     贪心最佳优先   │        A*          │
```

- **横轴**（g）：要不要为"已经走过的路"记账——决定**最优性**
- **纵轴**（h）：要不要为"还没走的路"算命——决定**方向感/速度**
- A* 是唯一两项都看的：最优性与方向感的平衡点

## 选择决策树

```
边权有负值？        → Bellman-Ford / SPFA（本家族都不适用）
只要遍历/任意解？    → DFS（省内存）
无权图最短路径？     → BFS
加权图、不知道终点？ → Dijkstra（全源距离表）
加权图、知道终点？   → A*（h 可采纳）或贪心（不要最优只要快）
内存装不下 open 集？ → IDA* / IDDFS
```

## 文档与实验的映射

| 文档 | 实验目录 |
|---|---|
| dfs.md / bfs.md / ucs.md | 无独立实验（基础概念，融入 a-star 的对照讨论） |
| dijkstra.md | `a-star/baseline.py` |
| heuristic-greedy.md | 可在 `a-star/demo.py` 中加第三个跑法 |
| **a-star.md** | **`a-star/`（主实验）** |
