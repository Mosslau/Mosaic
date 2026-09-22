# 五子棋（Gomoku）JavaScript 版 — 设计文档

## 1. 目标

实现一个**零依赖**、可测试、可交互的五子棋示例，放在 `example/gomoku-js` 下。

- 简单：只依赖 Node.js 内置模块（`node:readline`、`node:test`）。
- 完整：包含核心规则、简单 AI、命令行交互、单元测试、代码审查报告。

## 2. 需求拆解

| 编号 | 需求 | 优先级 |
| --- | --- | --- |
| R1 | 15 × 15 棋盘，黑白双方轮流落子 | 必须 |
| R2 | 非法落子（越界、已占用）要报错 | 必须 |
| R3 | 横、竖、两条对角线任意方向连成 5 子判胜 | 必须 |
| R4 | 棋盘下满且无人获胜判平局 | 必须 |
| R5 | 支持悔棋与重新开始 | 必须 |
| R6 | 提供简单 AI 对手 | 应有 |
| R7 | 命令行可玩 | 应有 |

## 3. 架构

```
gomoku-js/
├── package.json          # npm 脚本：start / test
├── DESIGN.md             # 本设计文档
├── REVIEW.md             # 代码审查报告
├── src/
│   ├── gomoku.js         # 核心游戏库（纯函数 + Game 类）
│   └── cli.js            # 命令行入口
└── test/
    └── gomoku.test.js    # 单元测试（node:test + node:assert）
```

分层：

- **核心层 `gomoku.js`**：不依赖任何 I/O，便于测试。
  - `Player`、`STATUS`：常量。
  - `GomokuError`：领域错误。
  - `Game`：状态机，负责落子、判胜、悔棋、重开。
  - `findWinningLine` / `bestMoveFor` / `scoreCell`：规则与 AI 的纯函数。
- **表现层 `cli.js`**：读取用户输入、渲染棋盘、调用核心层。

## 4. 核心数据结构

```js
// 棋盘：15x15 二维数组，null 表示空，Player.BLACK/WHITE 表示棋子
const board = Array.from({ length: 15 }, () => Array(15).fill(null));

// 落子结果：统一用对象返回，避免字符串魔法值歧义
{ status: 'ongoing' | 'won' | 'draw', winner?: Player.BLACK | Player.WHITE }
```

## 5. 关键算法

### 5.1 胜负判定

落子后只检查最后一步棋子的 4 个方向（水平、垂直、主对角线、副对角线），
向正反两个方向延伸计数。时间复杂度 O(1)（棋盘大小固定时），比全盘扫描更高效。

```
方向向量：
  DIRS = [[0,1],[1,0],[1,1],[1,-1]]
对每个方向：
  count = 1
  向 +d 延伸：连续同色则 count++
  向 -d 延伸：连续同色则 count++
  count >= 5 => 胜
```

### 5.2 简单 AI

采用「进攻 + 防守」的启发式评分，在空位中选择得分最高的落点：

1. 遍历所有空位，对每个空位计算：
   - `attack = shapeScore(模拟黑子落在这里，对黑子连子形状打分)`
   - `defense = shapeScore(模拟白子落在这里，对白子连子形状打分)`
   - 总得分 `attack * 1.0 + defense * 0.9`（进攻权重略高）。
2. 返回最高分的空位；出现同分时优先选靠近棋盘中心的点。
3. 若已经存在直接获胜点（形成五连），立即返回该点。

形状得分（连续同色计数）：

| 连续棋子数 | 得分 |
| --- | --- |
| >= 5 | 1,000,000 |
| 4 | 10,000 |
| 3 | 1,000 |
| 2 | 100 |
| 1 | 10 |

同时给「活三/冲四」做轻量修正：计算方向两端是否为空，若两端都为空则分数 ×2
（更容易形成活连），仅一端为空则分数 ×1.2。

> 说明：这不是最强 AI，只是“足够玩”的启发式实现，符合“简单一点”的目标。

## 6. 接口设计

```js
import { Player, STATUS, Game, GomokuError, bestMoveFor } from './src/gomoku.js';

const game = new Game(15);
game.place(7, 7);                        // { status: 'ongoing' }
game.place(7, 8);
game.currentPlayer;                      // Player.BLACK
game.winner;                             // 胜者，未结束时为 null
game.undo();                             // 悔棋
game.restart();                          // 重开
bestMoveFor(game.board, Player.BLACK);   // { row, col }
```

## 7. 测试策略

使用 Node 内置的 `node --test`，无第三方依赖。测试覆盖：

- 初始状态
- 非法落子（越界、占用）
- 横 / 竖 / 主对角线 / 副对角线获胜
- 平局（用小棋盘场景模拟，或构造满盘）
- 悔棋与重开
- AI 能直接取胜、能阻止对手取胜
- `findWinningLine` 纯函数边界

## 8. 边界与风险

- 棋盘大小固定为 15，构造函数参数保留扩展能力，但测试按 15 覆盖。
- `bestMoveFor` 对满盘返回 `null`。
- 并发/异步不在范围内；CLI 为同步交互。
