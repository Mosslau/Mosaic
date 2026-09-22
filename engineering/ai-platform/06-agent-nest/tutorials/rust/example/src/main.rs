//! 五子棋命令行交互入口。

use std::io::{self, Write};
use std::time::Duration;

use gomoku::{best_move_for, Game, GameStatus, HumanAction, Mode, Player, BOARD_SIZE};

fn main() {
    print_welcome();

    loop {
        match choose_mode() {
            Some(Mode::Pvp) => play_game(Mode::Pvp),
            Some(Mode::Pvc) => play_game(Mode::Pvc),
            None => {
                println!("再见！");
                break;
            }
        }
    }
}

/// 清屏并打印标题。
fn print_welcome() {
    clear_screen();
    println!("======================================");
    println!("              五 子 棋                ");
    println!("     15x15 棋盘 · 五子连珠获胜        ");
    println!("======================================");
    println!();
}

/// 打印主菜单并读取用户选择。
fn choose_mode() -> Option<Mode> {
    loop {
        println!("请选择模式：");
        println!("  [1] 双人对战（黑方 X vs 白方 O）");
        println!("  [2] 人机对战（你执黑，电脑执白）");
        println!("  [3] 退出");
        print!("请输入 1-3：");
        flush();

        match read_line().trim() {
            "1" => return Some(Mode::Pvp),
            "2" => return Some(Mode::Pvc),
            "3" => return None,
            _ => println!("输入无效，请重新选择。\n"),
        }
    }
}

/// 进行一整局游戏，结束后返回主菜单。
fn play_game(mode: Mode) {
    let mut game = Game::new();

    loop {
        clear_screen();
        print_board(&game);

        let current = game.current_player();
        println!("\n轮到{}（{}）", current.name_cn(), current.symbol());

        let human_action = if mode == Mode::Pvc && current == Player::White {
            println!("电脑正在思考...");
            std::thread::sleep(Duration::from_millis(300));

            match best_move_for(game.board(), Player::White) {
                Some((row, col)) => {
                    println!("电脑落子：{} {}", row + 1, col + 1);
                    HumanAction::Place(row, col)
                }
                None => {
                    println!("电脑找不到可落子的位置。");
                    wait_enter();
                    continue;
                }
            }
        } else {
            read_human_move()
        };

        match human_action {
            HumanAction::Quit => {
                println!("已退出本局。");
                return;
            }
            HumanAction::Undo => {
                // 人机模式下连悔两步，让回合回到玩家手中。
                if game.undo() && mode == Mode::Pvc {
                    game.undo();
                }
                println!("已悔棋。");
                wait_enter();
            }
            HumanAction::Place(row, col) => match game.place(row, col) {
                Ok(status) => match status {
                    GameStatus::Ongoing => {}
                    GameStatus::Won(player) => {
                        clear_screen();
                        print_board(&game);
                        println!("\n{}（{}）获胜！", player.name_cn(), player.symbol());
                        if play_again() {
                            game.restart();
                            continue;
                        }
                        return;
                    }
                    GameStatus::Draw => {
                        clear_screen();
                        print_board(&game);
                        println!("\n棋盘已满，平局！");
                        if play_again() {
                            game.restart();
                            continue;
                        }
                        return;
                    }
                },
                Err(err) => {
                    println!("落子失败：{}", err);
                    wait_enter();
                }
            },
        }
    }
}

/// 读取并解析人类玩家的输入。
fn read_human_move() -> HumanAction {
    loop {
        println!("请输入落子位置（行 列，如 8 8），u 悔棋，q 退出：");
        print!("> ");
        flush();

        let input = read_line();
        let command = input.trim().to_lowercase();

        if command == "u" || command == "undo" {
            return HumanAction::Undo;
        }
        if command == "q" || command == "quit" || command == "exit" {
            return HumanAction::Quit;
        }

        if let Some((row, col)) = parse_coordinate(&command) {
            return HumanAction::Place(row, col);
        }

        println!("输入无效：请输入 1-{} 之间的行列，例如 8 8。", BOARD_SIZE);
    }
}

/// 将 `8 8` 这类 1 基输入解析为 0 基坐标。
fn parse_coordinate(input: &str) -> Option<(usize, usize)> {
    let mut parts = input.split_whitespace();

    let row = parts.next()?.parse::<usize>().ok()?;
    let col = parts.next()?.parse::<usize>().ok()?;
    if parts.next().is_some() {
        return None;
    }

    if row == 0 || col == 0 || row > BOARD_SIZE || col > BOARD_SIZE {
        return None;
    }

    Some((row - 1, col - 1))
}

/// 打印棋盘。上一步落子用方括号标记。
fn print_board(game: &Game) {
    let board = game.board();
    let last = game.last_move();

    print!("   ");
    for col in 1..=BOARD_SIZE {
        print!("{col:>3}");
    }
    println!();

    for (row_index, line) in board.iter().enumerate() {
        print!("{row_index:>3}", row_index = row_index + 1);
        for (col_index, cell) in line.iter().enumerate() {
            let symbol = match cell {
                Some(player) => player.symbol(),
                None => '·',
            };

            let is_last = last
                .is_some_and(|last_move| last_move.row == row_index && last_move.col == col_index);

            if is_last {
                print!("[{symbol}]");
            } else {
                print!(" {symbol} ");
            }
        }
        println!();
    }
}

/// 询问是否再来一局。
fn play_again() -> bool {
    loop {
        print!("\n再来一局？(y/n)：");
        flush();

        match read_line().trim().to_lowercase().as_str() {
            "y" | "yes" => return true,
            "n" | "no" => return false,
            _ => println!("请输入 y 或 n。"),
        }
    }
}

/// 暂停，等待用户按回车。
fn wait_enter() {
    print!("\n按回车继续...");
    flush();
    read_line();
}

/// 读取一行输入；读取失败时返回空字符串。
fn read_line() -> String {
    let mut input = String::new();
    if io::stdin().read_line(&mut input).is_err() {
        return String::new();
    }
    input
}

/// 刷新标准输出。
fn flush() {
    let _ = io::stdout().flush();
}

/// 使用 ANSI 转义序列清屏。
fn clear_screen() {
    print!("\x1b[2J\x1b[1;1H");
    flush();
}
