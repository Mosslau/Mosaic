# 代码评审记录（REVIEW）

项目：`example/gomoku-js`
评审范围：`src/gomoku.js`、`src/cli.js`、`test/gomoku.test.js`、`package.json`
结论：**通过（有条件）**。核心逻辑简洁、无第三方依赖，已修复两个会影响正确性的缺陷；剩余问题均为小型改进项。

---

## 1. 评审结论概览

| 严重度 | 数量 | 说明 |
| --- | --- | --- |
| Blocker | 0 | 无阻塞问题 |
| Major | 0 | 两个 Major 缺陷已在评审过程中修复 |
| Minor | 2 | CLI 终局后无法悔棋/重开、`bestMoveFor` 使用固定中心点 |
| Suggestion | 2 | 输入解析可增强、平局测试依赖手工构造盘面 |

---

## 2. 已修复问题

### 2.1 AI 评分函数对空位永远返回 0（Major）

- 位置：`src/gomoku.js` 原 `scoreCell`
- 现象：`scoreCell` 原先调用 `countDirection` 统计以“当前格”为起点的连续子数。评分对象是空位，起点格子没有棋子，因此四个方向计数始终为 0，导致 AI 在非必赢/非必防时退化为只按“离中心距离”选点，棋力明显错误。
- 修复：新增 `countRun(board, row, col, dr, dc, player)`，从相邻格开始计数，`scoreCell` 使用 `forward + backward + 1` 估算落子后长度，并配合 `openEndCount` 计算开放端。
- 影响：AI 在一般局面下重新拥有进攻/防守判断。

### 2.2 终局后悔棋无法正确恢复回合（Major）

- 位置：`src/gomoku.js` 原 `undo`
- 现象：终局（胜/平）时 `place` 不会切换 `currentPlayer`。原 `undo` 使用 `opponentOf(currentPlayer)` 恢复回合，终局后执行会得到错误的下一手方。
- 修复：`undo` 先取出被撤销的 `[r, c]`，读取该位置的 `player`，再将 `currentPlayer` 设为该 `player`，同时清空 `winner`、恢复 `ONGOING`。
- 影响：终局后仍可悔棋，且回合正确。

---

## 3. 仍存在的 Minor 问题

### 3.1 CLI 终局后无法使用 `undo` / `restart`（Minor）

- 位置：`src/cli.js`
- 现象：`Game.place` 返回 `won` 或 `draw` 后，CLI 的主循环直接打印结果并退出；但命令解析中的 `undo` / `restart` 只在循环内可用。因此用户在“刚下完最后一手想悔棋看一步”的场景下没有入口。
- 建议：终局后进入一个短小的“终局循环”，接受 `undo` / `restart` / `quit`，或至少在提示语中说明“请重新运行后重开”。

### 3.2 `bestMoveFor` 的中心点计算按固定棋盘假设（Minor）

- 位置：`src/gomoku.js` `bestMoveFor` / `distanceFromCenter`
- 现象：`distanceFromCenter` 使用模块常量 `CENTER`，而 `bestMoveFor` 可接收 `size` 参数。当 `size !== BOARD_SIZE`（如 5×5 测试棋盘）时，距离计算会失真。
- 影响：当前项目只实际使用 15×15，AI 正常；但函数签名暗示可扩展，行为不完全一致。
- 建议：`distanceFromCenter(row, col, size)` 从棋盘尺寸推导中心点。

---

## 4. 测试与质量

- 使用 Node 内置 `node --test`，无第三方测试依赖。
- 测试覆盖：初始状态、非法输入、越界/占位、横向/纵向/斜向胜利、平局、悔棋、终局后悔棋、AI 必须防守与直接取胜等。
- 评审期间发现并修正平局测试盘面：原棋盘格纹 `(r + c) % 2` 会产生同色主对角线（5 连），导致测试“平局”实际已分出胜负。现改为手工构造的无五连满盘：
  ```
  BBBBW
  BBBBW
  BBBWW
  BWWWW
  WWWW.
  ```
  最后一格落黑后为平局。
- 当前全量测试：`node --test` 通过（exit=0）。

### 测试建议
- 可增加 `wouldWin` / `scoreCell` 的直接单测，验证 AI 修复不再回归。
- 可增加 `renderBoard` 的高亮输出快照测试。

---

## 5. 设计一致性

- `src/gomoku.js` 保持纯逻辑、无 I/O，便于测试；`src/cli.js` 负责交互；职责划分清晰。
- `Game.place` 返回值 `{ status, winner? }` 设计合理，调用方无需再查询胜负。
- 平局判定在胜利判定之后，符合“最后一手成五连不算平局”的规则。
- 项目无第三方依赖，符合“保持简单”的目标。

---

## 6. 最终判定

核心逻辑可用，两个 Major 缺陷已修复并有测试锁定。建议在后续迭代中处理两个 Minor 项（尤其是 CLI 终局交互），但不阻塞当前交付。
