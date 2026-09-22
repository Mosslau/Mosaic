// 命令行五子棋：node src/cli.js [pvp|pvc]
// 默认 pvc（人机对战），人类执黑先行。

import readline from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';

import {
  Player,
  STATUS,
  Game,
  bestMoveFor,
  findWinningLine,
  renderBoard,
} from './gomoku.js';

const mode = process.argv[2] === 'pvp' ? 'pvp' : 'pvc';
const HUMAN = Player.BLACK;
const AI = Player.WHITE;

function print(text = '') {
  console.log(text);
}

function printBoard(game, winningLine = null) {
  const cells = winningLine ? winningLine.cells : [];
  print(renderBoard(game.board, cells).join('\n'));
  const names = { [Player.BLACK]: 'X(黑)', [Player.WHITE]: 'O(白)' };
  print(`当前: ${names[game.currentPlayer]}`);
}

function parseMove(line) {
  const parts = line.trim().split(/\s+/);
  if (parts.length !== 2) return null;
  const row = Number(parts[0]);
  const col = Number(parts[1]);
  if (!Number.isInteger(row) || !Number.isInteger(col)) return null;
  return [row, col];
}

function announceEnd(game, winningLine) {
  if (game.status === STATUS.WON) {
    print(`\n${winningLine.player === Player.BLACK ? 'X(黑)' : 'O(白)'} 获胜！`);
  } else if (game.status === STATUS.DRAW) {
    print('\n平局，棋盘已满。');
  }
}

const game = new Game();
const rl = readline.createInterface({ input, output });
print(`五子棋（${mode === 'pvp' ? '双人对战' : '人机对战，你执黑'}）`);
print('输入格式: 行 列（例如 7 7）；命令: undo / restart / quit');
printBoard(game);

try {
  while (game.status === STATUS.ONGOING) {
    let row;
    let col;

    if (mode === 'pvc' && game.currentPlayer === AI) {
      const move = bestMoveFor(game.board, AI, game.size);
      if (!move) break;
      ({ row, col } = move);
      print(`AI 落子: ${row} ${col}`);
    } else {
      const answer = await rl.question('你的落子 > ');
      const command = answer.trim().toLowerCase();

      if (command === 'quit' || command === 'q') {
        print('再见！');
        break;
      }
      if (command === 'undo') {
        game.undo();
        if (mode === 'pvc' && game.currentPlayer === AI) game.undo();
        printBoard(game);
        continue;
      }
      if (command === 'restart') {
        game.restart();
        print('已重新开始。');
        printBoard(game);
        continue;
      }

      const move = parseMove(answer);
      if (!move) {
        print('无效输入，请使用: 行 列');
        continue;
      }
      [row, col] = move;
    }

    try {
      game.place(row, col);
    } catch (err) {
      print(`非法落子: ${err.message}`);
      continue;
    }

    const winningLine = game.status === STATUS.WON
      ? findWinningLine(game.board)
      : null;
    printBoard(game, winningLine);
    announceEnd(game, winningLine);
  }
} finally {
  rl.close();
}
