# A* 启发式搜索

> 状态：⬜ 未开始
> 对应文档章节：`roadmap/人工智能代表算法演进路线.md` 第 2.2.1 章

搜索求解器：本目录不是 sklearn 估计器，接口由 A* 自身的形态决定。

## 设计原理

（这个算法要解决什么问题？核心思想一句话概括。它为什么比之前的方法好？）

## 数学推导

（f = g + h；h 的可采纳性 / 一致性；手推一遍再写代码）

## 目录形态（本算法的"类型"）

| 文件 | 角色 | 接口 |
|---|---|---|
| `impl.py` | 手写 A* | `solve(grid, start, goal, heuristic=manhattan) -> SearchResult` |
| `baseline.py` | Dijkstra 对照 | `dijkstra(grid, start, goal) -> SearchResult`（h ≡ 0 的 A*） |
| `demo.py` | 同图双跑对比 | 路径长度 / 扩展节点数 / 耗时 |

## 手写实现要点

（open 集 heapq 按 f 排序与平局处理；closed 判重；障碍地图生成要保证连通；
可采纳启发式的选取——纯 Python 实现，无需 numpy）

## 基线对照

（对照对象是 Dijkstra 而非 sklearn：两条路径应一致，Dijkstra 扩展节点更多——
启发式 h 的收益由此量化；结果记录到下方「实验结果」）

## 实验结果

（地图参数、评价指标、可视化结论）
（**A* vs Dijkstra 对比**：扩展节点数 / 耗时差异、差异原因分析）

## 局限与延伸

（这个算法的边界在哪里？它引出了哪个后续算法？）
