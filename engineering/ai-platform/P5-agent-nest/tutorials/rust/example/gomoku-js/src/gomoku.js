// 五子棋核心游戏库：零依赖、无 I/O，方便单元测试。

export const BOARD_SIZE = 15;
export const WIN_LENGTH = 5;

export const Player = Object.freeze({
  BLACK: 1,
  WHITE: 2,
});

export const STATUS = Object.freeze({
  ONGOING: 'ongoing',
  WON: 'won',
  DRAW: 'draw',
});

// 4 个判胜方向：水平、垂直、主对角线、副对角线。
const DIRS = Object.freeze([
  [0, 1],
  [1, 0],
  [1, 1],
  [1, -1],
]);

// 中心点，用于 AI 在同分时优先选择靠近中心的位置。
const CENTER = (BOARD_SIZE - 1) / 2;

export class GomokuError extends Error {
  constructor(message, code = 'INVALID_MOVE') {
    super(message);
    this.name = 'GomokuError';
    this.code = code;
  }
}

export function opponentOf(player) {
  return player === Player.BLACK ? Player.WHITE : Player.BLACK;
}

export function createBoard(size = BOARD_SIZE) {
  if (!Number.isInteger(size) || size < WIN_LENGTH) {
    throw new GomokuError(`棋盘尺寸至少为 ${WIN_LENGTH}`, 'INVALID_BOARD_SIZE');
  }
  return Array.from({ length: size }, () => Array(size).fill(null));
}

/**
 * 返回从 (row, col) 出发，沿 [dr, dc] 方向连续同色棋子的数量。
 * 不包含 (row, col) 本身。
 */
export function countDirection(board, row, col, dr, dc) {
  const player = board[row]?.[col];
  if (player == null) return 0;

  const size = board.length;
  let count = 0;
  let r = row + dr;
  let c = col + dc;
  while (r >= 0 && r < size && c >= 0 && c < size && board[r][c] === player) {
    count += 1;
    r += dr;
    c += dc;
  }
  return count;
}

/** 判断 (row, col) 的棋子是否形成 WIN_LENGTH 连珠。 */
export function isWinningMove(board, row, col) {
  const player = board[row]?.[col];
  if (player == null) return false;

  for (const [dr, dc] of DIRS) {
    const total = 1 + countDirection(board, row, col, dr, dc)
      + countDirection(board, row, col, -dr, -dc);
    if (total >= WIN_LENGTH) return true;
  }
  return false;
}

/**
 * 找出获胜连线（用于渲染高亮）。找不到返回 null。
 * 返回 { cells: [[r,c], ...], player }。
 */
export function findWinningLine(board) {
  const size = board.length;
  for (let r = 0; r < size; r += 1) {
    for (let c = 0; c < size; c += 1) {
      const player = board[r][c];
      if (player == null) continue;
      for (const [dr, dc] of DIRS) {
        const cells = [];
        let rr = r;
        let cc = c;
        while (rr >= 0 && rr < size && cc >= 0 && cc < size
          && board[rr][cc] === player) {
          cells.push([rr, cc]);
          rr += dr;
          cc += dc;
        }
        if (cells.length >= WIN_LENGTH) {
          return { cells: cells.slice(0, WIN_LENGTH), player };
        }
      }
    }
  }
  return null;
}

export class Game {
  /**
   * @param {number} [size=BOARD_SIZE] 棋盘边长。为简单起见，固定 15，但保留扩展。
   */
  constructor(size = BOARD_SIZE) {
    this.size = size;
    this.restart();
  }

  restart() {
    this.board = createBoard(this.size);
    this.currentPlayer = Player.BLACK;
    this.winner = null;
    this.status = STATUS.ONGOING;
    this.history = [];
  }

  /**
   * 落子。合法时推进游戏并返回结果对象。
   * @returns {{ status: string, winner?: number }}
   */
  place(row, col) {
    if (this.status !== STATUS.ONGOING) {
      throw new GomokuError('游戏已结束，请重新开始', 'GAME_OVER');
    }
    if (!this.inBounds(row, col)) {
      throw new GomokuError(`坐标 (${row}, ${col}) 超出棋盘范围`, 'OUT_OF_BOUNDS');
    }
    if (this.board[row][col] !== null) {
      throw new GomokuError(`坐标 (${row}, ${col}) 已有棋子`, 'CELL_OCCUPIED');
    }

    const player = this.currentPlayer;
    this.board[row][col] = player;
    this.history.push([row, col]);

    if (isWinningMove(this.board, row, col)) {
      this.status = STATUS.WON;
      this.winner = player;
      return { status: this.status, winner: player };
    }

    if (this.isFull()) {
      this.status = STATUS.DRAW;
      return { status: this.status };
    }

    this.currentPlayer = opponentOf(player);
    return { status: this.status };
  }

  inBounds(row, col) {
    return Number.isInteger(row) && Number.isInteger(col)
      && row >= 0 && row < this.size
      && col >= 0 && col < this.size;
  }

  isFull() {
    for (const row of this.board) {
      if (row.includes(null)) return false;
    }
    return true;
  }

  emptyCells() {
    const cells = [];
    for (let r = 0; r < this.size; r += 1) {
      for (let c = 0; c < this.size; c += 1) {
        if (this.board[r][c] === null) cells.push([r, c]);
      }
    }
    return cells;
  }

  undo() {
    if (this.history.length === 0) return false;
    const [r, c] = this.history.pop();
    const player = this.board[r][c];
    this.board[r][c] = null;
    // 无论是否终局，被撤销的那一步都应由原落子方重新走。
    this.currentPlayer = player;
    this.winner = null;
    this.status = STATUS.ONGOING;
    return true;
  }
}

// ---------------------------------------------------------------------------
// 简单 AI：进攻 + 防守启发式评分。
// ---------------------------------------------------------------------------

/**
 * 计算从 (row, col) 的相邻格开始，沿 [dr, dc] 方向连续的 player 棋子数。
 * 不检查 (row, col) 本身，因为评分时空位尚未落子。
 */
function countRun(board, row, col, dr, dc, player) {
  const size = board.length;
  let count = 0;
  let r = row + dr;
  let c = col + dc;
  while (r >= 0 && r < size && c >= 0 && c < size && board[r][c] === player) {
    count += 1;
    r += dr;
    c += dc;
  }
  return count;
}

/**
 * 评估某空位落下 player 后，player 在该点的连子形状得分。
 */
export function scoreCell(board, row, col, player) {
  let score = 0;
  for (const [dr, dc] of DIRS) {
    const forward = countRun(board, row, col, dr, dc, player);
    const backward = countRun(board, row, col, -dr, -dc, player);
    const length = forward + backward + 1;
    let shape = 0;
    if (length >= 5) shape = 1_000_000;
    else if (length === 4) shape = 10_000;
    else if (length === 3) shape = 1_000;
    else if (length === 2) shape = 100;
    else shape = 10;

    const openEnds = openEndCount(board, row, col, dr, dc, player, forward, backward);
    if (length >= 4) shape *= 1 + openEnds * 0.5;
    else if (length >= 3 && openEnds === 2) shape *= 2;
    else if (length >= 2 && openEnds === 1) shape *= 1.2;

    score += shape;
  }
  return score;
}

function openEndCount(board, row, col, dr, dc, player, forward, backward) {
  const size = board.length;
  const candidates = [
    [row + dr * (forward + 1), col + dc * (forward + 1)],
    [row - dr * (backward + 1), col - dc * (backward + 1)],
  ];
  let open = 0;
  for (const [r, c] of candidates) {
    if (r >= 0 && r < size && c >= 0 && c < size && board[r][c] === null) {
      open += 1;
    }
  }
  return open;
}

function distanceFromCenter(row, col) {
  return Math.abs(row - CENTER) + Math.abs(col - CENTER);
}

/**
 * 返回 AI 认为的最佳落点 { row, col }；棋盘已满返回 null。
 * 策略：先找己方直接获胜点，再找必须防守点，否则取进攻+防守综合得分最高者。
 */
export function bestMoveFor(board, player, size = BOARD_SIZE) {
  const opponent = opponentOf(player);
  const empties = [];
  for (let r = 0; r < size; r += 1) {
    for (let c = 0; c < size; c += 1) {
      if (board[r]?.[c] === null) empties.push([r, c]);
    }
  }
  if (empties.length === 0) return null;

  let immediateWin = null;
  let mustDefend = null;

  for (const [r, c] of empties) {
    if (wouldWin(board, r, c, player)) {
      if (immediateWin == null
        || distanceFromCenter(r, c) < distanceFromCenter(...immediateWin)) {
        immediateWin = [r, c];
      }
    }
    if (wouldWin(board, r, c, opponent)) {
      if (mustDefend == null
        || distanceFromCenter(r, c) < distanceFromCenter(...mustDefend)) {
        mustDefend = [r, c];
      }
    }
  }

  if (immediateWin) return { row: immediateWin[0], col: immediateWin[1] };
  if (mustDefend) return { row: mustDefend[0], col: mustDefend[1] };

  let best = null;
  let bestScore = -Infinity;
  for (const [r, c] of empties) {
    const attack = scoreCell(board, r, c, player);
    const defense = scoreCell(board, r, c, opponent);
    const score = attack * 1.0 + defense * 0.9 - distanceFromCenter(r, c);
    if (score > bestScore) {
      bestScore = score;
      best = { row: r, col: c };
    }
  }
  return best;
}

function wouldWin(board, row, col, player) {
  board[row][col] = player;
  const wins = isWinningMove(board, row, col);
  board[row][col] = null;
  return wins;
}

/**
 * 渲染纯文本棋盘。winningCells 用于高亮获胜连线。
 * 返回字符串数组，便于 CLI 与测试使用。
 */
export function renderBoard(board, winningCells = []) {
  const winSet = new Set(winningCells.map(([r, c]) => `${r},${c}`));
  const size = board.length;
  const lines = [];

  const header = ['   ', ...[...Array(size).keys()].map((i) => String(i).padStart(2, ' '))];
  lines.push(header.join(' '));

  for (let r = 0; r < size; r += 1) {
    const rowLabel = String(r).padStart(2, ' ');
    const cells = [rowLabel, ' '];
    for (let c = 0; c < size; c += 1) {
      let glyph = '.';
      if (board[r][c] === Player.BLACK) glyph = 'X';
      if (board[r][c] === Player.WHITE) glyph = 'O';
      if (winSet.has(`${r},${c}`)) glyph = `(${glyph})`;
      cells.push(glyph.padEnd(3, ' '));
    }
    lines.push(cells.join(''));
  }
  return lines;
}
