// 五子棋核心库单元测试：node --test test/
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  BOARD_SIZE,
  Player,
  STATUS,
  GomokuError,
  Game,
  createBoard,
  opponentOf,
  isWinningMove,
  findWinningLine,
  bestMoveFor,
  renderBoard,
} from '../src/gomoku.js';

/** 按黑白交替顺序依次落子，返回 game，便于构造对局。 */
function play(game, moves) {
  for (const [row, col] of moves) {
    const result = game.place(row, col);
    if (result.status !== STATUS.ONGOING) return result;
  }
  return { status: game.status };
}

test('初始状态正确', () => {
  const game = new Game();
  assert.equal(game.size, BOARD_SIZE);
  assert.equal(game.currentPlayer, Player.BLACK);
  assert.equal(game.status, STATUS.ONGOING);
  assert.equal(game.winner, null);
  assert.equal(game.history.length, 0);
  assert.equal(game.isFull(), false);
});

test('createBoard 拒绝过小棋盘', () => {
  assert.throws(() => createBoard(4), (err) => {
    assert.ok(err instanceof GomokuError);
    assert.equal(err.code, 'INVALID_BOARD_SIZE');
    return true;
  });
});

test('越界落子抛出 OUT_OF_BOUNDS', () => {
  const game = new Game();
  assert.throws(() => game.place(-1, 0), (err) => err.code === 'OUT_OF_BOUNDS');
  assert.throws(() => game.place(0, BOARD_SIZE), (err) => err.code === 'OUT_OF_BOUNDS');
});

test('占用位置抛出 CELL_OCCUPIED', () => {
  const game = new Game();
  game.place(7, 7);
  assert.throws(() => game.place(7, 7), (err) => err.code === 'CELL_OCCUPIED');
});

test('黑白双方轮流落子', () => {
  const game = new Game();
  assert.equal(game.place(0, 0).status, STATUS.ONGOING);
  assert.equal(game.currentPlayer, Player.WHITE);
  assert.equal(game.place(1, 1).status, STATUS.ONGOING);
  assert.equal(game.currentPlayer, Player.BLACK);
  assert.equal(game.board[0][0], Player.BLACK);
  assert.equal(game.board[1][1], Player.WHITE);
});

test('水平五连获胜', () => {
  const game = new Game();
  const result = play(game, [
    [7, 3], [8, 3],
    [7, 4], [8, 4],
    [7, 5], [8, 5],
    [7, 6], [8, 6],
    [7, 7],
  ]);
  assert.equal(result.status, STATUS.WON);
  assert.equal(game.winner, Player.BLACK);
});

test('垂直五连获胜', () => {
  const game = new Game();
  const result = play(game, [
    [3, 7], [3, 8],
    [4, 7], [4, 8],
    [5, 7], [5, 8],
    [6, 7], [6, 8],
    [7, 7],
  ]);
  assert.equal(result.status, STATUS.WON);
  assert.equal(game.winner, Player.BLACK);
});

test('主对角线五连获胜', () => {
  const game = new Game();
  const result = play(game, [
    [3, 3], [3, 4],
    [4, 4], [4, 5],
    [5, 5], [5, 6],
    [6, 6], [6, 7],
    [7, 7],
  ]);
  assert.equal(result.status, STATUS.WON);
});

test('副对角线五连获胜', () => {
  const game = new Game();
  const result = play(game, [
    [3, 7], [3, 6],
    [4, 6], [4, 5],
    [5, 5], [5, 4],
    [6, 4], [6, 3],
    [7, 3],
  ]);
  assert.equal(result.status, STATUS.WON);
  assert.equal(game.winner, Player.BLACK);
});

test('白方获胜（非先手方）', () => {
  const game = new Game();
  const result = play(game, [
    [7, 0], [7, 1],
    [8, 0], [7, 2],
    [8, 1], [7, 3],
    [8, 2], [7, 4],
    [8, 3], [7, 5],
  ]);
  assert.equal(result.status, STATUS.WON);
  assert.equal(game.winner, Player.WHITE);
});

test('平局：5x5 棋盘无五连下满', () => {
  const game = new Game(5);
  // 直接构造无五连的满盘布局，只留最后一格空，确保最终结果为平局。
  const rows = [
    'BBBBW',
    'BBBBW',
    'BBBWW',
    'BWWWW',
    'WWWW.',
  ];
  for (let r = 0; r < 5; r += 1) {
    for (let c = 0; c < 5; c += 1) {
      const ch = rows[r][c];
      game.board[r][c] = ch === 'B' ? Player.BLACK : ch === 'W' ? Player.WHITE : null;
    }
  }
  game.currentPlayer = Player.BLACK;
  const result = game.place(4, 4);
  assert.equal(result.status, STATUS.DRAW);
  assert.equal(game.winner, null);
  assert.equal(game.isFull(), true);
});

test('悔棋恢复棋盘并切换回合', () => {
  const game = new Game();
  game.place(7, 7); // 黑
  game.place(8, 8); // 白
  assert.equal(game.currentPlayer, Player.BLACK);

  assert.equal(game.undo(), true);
  assert.equal(game.board[8][8], null);
  assert.equal(game.board[7][7], Player.BLACK);
  assert.equal(game.currentPlayer, Player.WHITE);

  assert.equal(game.undo(), true);
  assert.equal(game.board[7][7], null);
  assert.equal(game.currentPlayer, Player.BLACK);

  assert.equal(game.undo(), false);
});

test('获胜后仍可悔棋，并回到原胜方回合', () => {
  const game = new Game();
  play(game, [
    [7, 3], [8, 3],
    [7, 4], [8, 4],
    [7, 5], [8, 5],
    [7, 6], [8, 6],
    [7, 7],
  ]);
  assert.equal(game.status, STATUS.WON);
  assert.equal(game.winner, Player.BLACK);

  assert.equal(game.undo(), true);
  assert.equal(game.status, STATUS.ONGOING);
  assert.equal(game.winner, null);
  assert.equal(game.currentPlayer, Player.BLACK);
  assert.equal(game.board[7][7], null);
  assert.equal(game.board[7][6], Player.BLACK);
});

test('平局后仍可悔棋，并回到最后一手方回合', () => {
  const game = new Game(5);
  const rows = [
    'BBBBW',
    'BBBBW',
    'BBBWW',
    'BWWWW',
    'WWWW.',
  ];
  for (let r = 0; r < 5; r += 1) {
    for (let c = 0; c < 5; c += 1) {
      const ch = rows[r][c];
      game.board[r][c] = ch === 'B' ? Player.BLACK : ch === 'W' ? Player.WHITE : null;
    }
  }
  game.currentPlayer = Player.BLACK;
  game.place(4, 4);
  assert.equal(game.status, STATUS.DRAW);

  assert.equal(game.undo(), true);
  assert.equal(game.status, STATUS.ONGOING);
  assert.equal(game.currentPlayer, Player.BLACK);
  assert.equal(game.board[4][4], null);
});

test('重新开始清空状态', () => {
  const game = new Game();
  game.place(7, 7);
  game.place(7, 8);
  game.restart();
  assert.equal(game.status, STATUS.ONGOING);
  assert.equal(game.history.length, 0);
  assert.equal(game.isFull(), false);
  assert.equal(game.board[7][7], null);
});

test('findWinningLine 返回五连坐标', () => {
  const game = new Game();
  game.board[7][3] = Player.BLACK;
  game.board[7][4] = Player.BLACK;
  game.board[7][5] = Player.BLACK;
  game.board[7][6] = Player.BLACK;
  game.board[7][7] = Player.BLACK;

  const line = findWinningLine(game.board);
  assert.ok(line);
  assert.equal(line.player, Player.BLACK);
  assert.equal(line.cells.length, 5);
  assert.deepEqual(line.cells, [[7, 3], [7, 4], [7, 5], [7, 6], [7, 7]]);
});

test('isWinningMove 与 opponentOf', () => {
  assert.equal(opponentOf(Player.BLACK), Player.WHITE);
  assert.equal(opponentOf(Player.WHITE), Player.BLACK);

  const board = createBoard();
  board[0][0] = Player.BLACK;
  assert.equal(isWinningMove(board, 0, 0), false);
});

test('AI 能发现直接获胜点', () => {
  const board = createBoard();
  for (const c of [3, 4, 5, 6]) board[7][c] = Player.BLACK;
  const move = bestMoveFor(board, Player.BLACK);
  assert.ok(move);
  assert.equal(move.row, 7);
  assert.ok([2, 7].includes(move.col), `期望堵两端，实际 col=${move.col}`);
});

test('AI 能阻挡对手四连', () => {
  const board = createBoard();
  for (const c of [3, 4, 5, 6]) board[7][c] = Player.WHITE;
  const move = bestMoveFor(board, Player.BLACK);
  assert.ok(move);
  assert.equal(move.row, 7);
  assert.ok([2, 7].includes(move.col), `期望堵两端，实际 col=${move.col}`);
});

test('AI 对满盘返回 null', () => {
  const board = createBoard();
  for (let r = 0; r < BOARD_SIZE; r += 1) {
    for (let c = 0; c < BOARD_SIZE; c += 1) {
      board[r][c] = (r + c) % 2 === 0 ? Player.BLACK : Player.WHITE;
    }
  }
  assert.equal(bestMoveFor(board, Player.BLACK), null);
});

test('renderBoard 输出包含双方棋子', () => {
  const game = new Game();
  game.board[0][0] = Player.BLACK;
  game.board[1][1] = Player.WHITE;
  const lines = renderBoard(game.board);
  assert.equal(lines.length, BOARD_SIZE + 1);
  assert.ok(lines[1].includes('X'));
  assert.ok(lines[2].includes('O'));
});
