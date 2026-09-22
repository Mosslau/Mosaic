//! 五子棋核心规则库：15x15 棋盘、落子、胜负/平局判定与简单 AI。
//!
//! 本模块不包含终端交互逻辑，方便对核心规则进行单元测试。

use std::fmt;

/// 棋盘边长（标准五子棋为 15）。
pub const BOARD_SIZE: usize = 15;

/// 连成多少子获胜。
pub const WIN_LENGTH: usize = 5;

/// 对局双方。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Player {
    Black,
    White,
}

impl Player {
    /// 返回对手。
    pub fn opponent(self) -> Self {
        match self {
            Player::Black => Player::White,
            Player::White => Player::Black,
        }
    }

    /// 终端显示用符号。
    pub fn symbol(self) -> char {
        match self {
            Player::Black => 'X',
            Player::White => 'O',
        }
    }

    /// 中文名称。
    pub fn name_cn(self) -> &'static str {
        match self {
            Player::Black => "黑方",
            Player::White => "白方",
        }
    }
}

/// 棋盘。行、列下标均为 0 基；`None` 表示空位。
pub type Board = [[Option<Player>; BOARD_SIZE]; BOARD_SIZE];

/// 一步落子记录。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Move {
    pub row: usize,
    pub col: usize,
    pub player: Player,
}

/// 落子后的对局状态。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GameStatus {
    Ongoing,
    Won(Player),
    Draw,
}

/// 落子错误。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GomokuError {
    OutOfBounds,
    CellOccupied,
}

impl fmt::Display for GomokuError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            GomokuError::OutOfBounds => write!(f, "坐标超出棋盘范围"),
            GomokuError::CellOccupied => write!(f, "该位置已有棋子"),
        }
    }
}

impl std::error::Error for GomokuError {}

/// 玩家输入对局模式。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    /// 双人对战。
    Pvp,
    /// 人机对战（玩家执黑先行，电脑执白）。
    Pvc,
}

/// 人类玩家的一步操作。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HumanAction {
    /// 在 `(row, col)` 落子（0 基坐标）。
    Place(usize, usize),
    /// 悔棋。
    Undo,
    /// 退出本局。
    Quit,
}

/// 对局对象：维护棋盘、当前行动方与落子历史。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Game {
    board: Board,
    current: Player,
    history: Vec<Move>,
}

impl Default for Game {
    fn default() -> Self {
        Self::new()
    }
}

impl Game {
    /// 创建新对局，黑方先行。
    pub fn new() -> Self {
        Self {
            board: [[None; BOARD_SIZE]; BOARD_SIZE],
            current: Player::Black,
            history: Vec::new(),
        }
    }

    /// 返回当前棋盘。
    pub fn board(&self) -> &Board {
        &self.board
    }

    /// 返回当前轮到的一方。
    pub fn current_player(&self) -> Player {
        self.current
    }

    /// 返回上一步落子。
    pub fn last_move(&self) -> Option<&Move> {
        self.history.last()
    }

    /// 返回已落子步数。
    pub fn history_len(&self) -> usize {
        self.history.len()
    }

    /// 棋盘是否已下满。
    pub fn is_full(&self) -> bool {
        self.board
            .iter()
            .all(|row| row.iter().all(|cell| cell.is_some()))
    }

    /// 返回所有空位坐标。
    pub fn empty_cells(&self) -> Vec<(usize, usize)> {
        let mut cells = Vec::new();
        for (row, line) in self.board.iter().enumerate() {
            for (col, cell) in line.iter().enumerate() {
                if cell.is_none() {
                    cells.push((row, col));
                }
            }
        }
        cells
    }

    /// 在 `(row, col)` 落下当前玩家的一子。
    ///
    /// 入参为 0 基下标。成功时返回落子后的对局状态。
    pub fn place(&mut self, row: usize, col: usize) -> Result<GameStatus, GomokuError> {
        if row >= BOARD_SIZE || col >= BOARD_SIZE {
            return Err(GomokuError::OutOfBounds);
        }
        if self.board[row][col].is_some() {
            return Err(GomokuError::CellOccupied);
        }

        let player = self.current;
        self.board[row][col] = Some(player);
        self.history.push(Move { row, col, player });

        if self.has_won(row, col, player) {
            return Ok(GameStatus::Won(player));
        }
        if self.is_full() {
            return Ok(GameStatus::Draw);
        }

        self.current = player.opponent();
        Ok(GameStatus::Ongoing)
    }

    /// 悔棋一步，成功返回 `true`。
    pub fn undo(&mut self) -> bool {
        let Some(last) = self.history.pop() else {
            return false;
        };
        self.board[last.row][last.col] = None;
        self.current = last.player;
        true
    }

    /// 重新开始对局。
    pub fn restart(&mut self) {
        self.board = [[None; BOARD_SIZE]; BOARD_SIZE];
        self.current = Player::Black;
        self.history.clear();
    }

    /// 检查 `(row, col)` 处的棋子是否形成五连。
    pub fn has_won(&self, row: usize, col: usize, player: Player) -> bool {
        const DIRECTIONS: [(isize, isize); 4] = [(0, 1), (1, 0), (1, 1), (1, -1)];

        for (dr, dc) in DIRECTIONS {
            let mut count = 1;
            for sign in [-1_isize, 1] {
                let mut step = 1;
                loop {
                    let rr = row as isize + dr * sign * step;
                    let cc = col as isize + dc * sign * step;
                    if rr < 0 || rr >= BOARD_SIZE as isize || cc < 0 || cc >= BOARD_SIZE as isize {
                        break;
                    }
                    if self.board[rr as usize][cc as usize] == Some(player) {
                        count += 1;
                        step += 1;
                    } else {
                        break;
                    }
                }
            }
            if count >= WIN_LENGTH {
                return true;
            }
        }
        false
    }
}

/// 为 `player` 选择一个落子点，返回 0 基坐标 `(row, col)`。
///
/// 策略：对每个空位计算进攻评分（自己连子）和防守评分（阻挡对方连子），
/// 取综合分最高者；分数接近时优先选择靠近棋盘中心的位置。
pub fn best_move_for(board: &Board, player: Player) -> Option<(usize, usize)> {
    let opponent = player.opponent();
    let mut best: Option<(usize, usize, f64)> = None;

    for row in 0..BOARD_SIZE {
        for col in 0..BOARD_SIZE {
            if board[row][col].is_some() {
                continue;
            }

            let attack = score_cell(board, row, col, player);
            let defense = score_cell(board, row, col, opponent);
            let mut score = attack as f64 + defense as f64 * 0.9;

            // 轻微偏好中心，让开局与均势局面更合理。
            let center = (BOARD_SIZE / 2) as f64;
            let dr = row as f64 - center;
            let dc = col as f64 - center;
            let distance_sq = dr * dr + dc * dc;
            let max_distance_sq = center * center * 2.0;
            score += (1.0 - distance_sq / max_distance_sq) * 0.1;

            if best.is_none() || score > best.unwrap().2 {
                best = Some((row, col, score));
            }
        }
    }

    best.map(|(row, col, _)| (row, col))
}

/// 在 `(row, col)` 落下 `player` 后，该点沿四个方向的“连线潜力”评分。
///
/// 对每个方向分别向两侧延伸，统计连子数、空位可延伸数，并把中间有阻挡
/// 的片段单独计分。返回值越大，越值得落子。
fn score_cell(board: &Board, row: usize, col: usize, player: Player) -> i32 {
    const DIRECTIONS: [(isize, isize); 4] = [(0, 1), (1, 0), (1, 1), (1, -1)];
    let mut total = 0;

    for (dr, dc) in DIRECTIONS {
        // 正向与负向各统计一次，再合并。
        let (pos_count, pos_open) = scan_direction(board, row, col, player, dr, dc, 1);
        let (neg_count, neg_open) = scan_direction(board, row, col, player, dr, dc, -1);

        let count = pos_count + neg_count - 1;
        let open = pos_open + neg_open;
        total += shape_score(count, open);
    }

    total
}

/// 沿 `(dr, dc)` 的 `sign` 方向扫描 `player` 的连续棋子。
///
/// 返回 `(连续棋子数, 端点是否为空)`；`连续棋子数` 包含 `(row, col)` 自身，
/// `端点为空` 表示该方向第一枚非己方棋子是空位。
fn scan_direction(
    board: &Board,
    row: usize,
    col: usize,
    player: Player,
    dr: isize,
    dc: isize,
    sign: isize,
) -> (i32, i32) {
    let mut count = 1;
    let mut open = 0;

    let mut step = 1;
    loop {
        let rr = row as isize + dr * sign * step;
        let cc = col as isize + dc * sign * step;
        if rr < 0 || rr >= BOARD_SIZE as isize || cc < 0 || cc >= BOARD_SIZE as isize {
            break;
        }
        match board[rr as usize][cc as usize] {
            Some(p) if p == player => {
                count += 1;
                step += 1;
            }
            None => {
                open = 1;
                break;
            }
            Some(_) => break,
        }
    }

    (count, open)
}

/// 把“连续子数 + 两端开放数”转换为落子价值分。
///
/// 活三、冲四等棋形通过长度与开放端数量体现；形成五连或超过五连得分最高。
fn shape_score(count: i32, open: i32) -> i32 {
    match count {
        0 | 1 => 0,
        2 => match open {
            2 => 10,
            1 => 3,
            _ => 0,
        },
        3 => match open {
            2 => 100,
            1 => 30,
            _ => 0,
        },
        4 => match open {
            2 => 1000,
            1 => 300,
            _ => 0,
        },
        _ => 100000,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 依次落下多个 0 基坐标；每个非终局落子都应返回 `Ongoing`。
    fn place_many(mut game: Game, moves: &[(usize, usize)]) -> Game {
        for &(row, col) in moves {
            let player = game.current;
            assert_eq!(
                game.place(row, col),
                Ok(GameStatus::Ongoing),
                "落子失败：({row}, {col})"
            );
            assert_eq!(game.board[row][col], Some(player));
        }
        game
    }

    #[test]
    fn new_game_starts_with_black_on_empty_board() {
        let game = Game::new();
        assert_eq!(game.current_player(), Player::Black);
        assert_eq!(game.history_len(), 0);
        assert!(game.empty_cells().len() == BOARD_SIZE * BOARD_SIZE);
        assert!(!game.is_full());
    }

    #[test]
    fn default_equals_new() {
        assert_eq!(Game::default(), Game::new());
    }

    #[test]
    fn place_returns_ongoing_and_switches_player() {
        let mut game = Game::new();
        assert_eq!(game.place(7, 7), Ok(GameStatus::Ongoing));
        assert_eq!(game.board[7][7], Some(Player::Black));
        assert_eq!(game.current_player(), Player::White);
        assert_eq!(game.history_len(), 1);
    }

    #[test]
    fn place_rejects_out_of_bounds() {
        let mut game = Game::new();
        assert_eq!(game.place(BOARD_SIZE, 0), Err(GomokuError::OutOfBounds));
        assert_eq!(game.place(0, BOARD_SIZE), Err(GomokuError::OutOfBounds));
        assert_eq!(game.history_len(), 0);
    }

    #[test]
    fn place_rejects_occupied_cell() {
        let mut game = Game::new();
        game.place(7, 7).unwrap();
        assert_eq!(game.place(7, 7), Err(GomokuError::CellOccupied));
        assert_eq!(game.history_len(), 1);
    }

    #[test]
    fn horizontal_five_wins() {
        let mut game = Game::new();
        game = place_many(
            game,
            &[
                (7, 7),
                (0, 0),
                (7, 8),
                (0, 1),
                (7, 9),
                (0, 2),
                (7, 10),
                (0, 3),
            ],
        );
        assert_eq!(game.place(7, 11), Ok(GameStatus::Won(Player::Black)));
        assert_eq!(game.history_len(), 9);
    }

    #[test]
    fn vertical_five_wins() {
        let mut game = Game::new();
        game = place_many(
            game,
            &[
                (7, 7),
                (0, 0),
                (8, 7),
                (0, 1),
                (9, 7),
                (0, 2),
                (10, 7),
                (0, 3),
            ],
        );
        assert_eq!(game.place(11, 7), Ok(GameStatus::Won(Player::Black)));
    }

    #[test]
    fn diagonal_five_wins() {
        let mut game = Game::new();
        game = place_many(
            game,
            &[
                (7, 7),
                (0, 0),
                (8, 8),
                (0, 1),
                (9, 9),
                (0, 2),
                (10, 10),
                (0, 3),
            ],
        );
        assert_eq!(game.place(11, 11), Ok(GameStatus::Won(Player::Black)));
    }

    #[test]
    fn anti_diagonal_five_wins() {
        let mut game = Game::new();
        game = place_many(
            game,
            &[
                (11, 7),
                (0, 0),
                (10, 8),
                (0, 1),
                (9, 9),
                (0, 2),
                (8, 10),
                (0, 3),
            ],
        );
        assert_eq!(game.place(7, 11), Ok(GameStatus::Won(Player::Black)));
    }

    #[test]
    fn white_can_win() {
        let mut game = Game::new();
        game = place_many(
            game,
            &[
                (0, 0),
                (7, 7),
                (0, 1),
                (7, 8),
                (1, 0),
                (7, 9),
                (1, 1),
                (7, 10),
                (2, 0),
            ],
        );
        assert_eq!(game.place(7, 11), Ok(GameStatus::Won(Player::White)));
    }

    #[test]
    fn five_with_gap_on_one_side_does_not_win() {
        let mut game = Game::new();
        game = place_many(
            game,
            &[(7, 7), (0, 0), (7, 8), (0, 1), (7, 10), (0, 2), (7, 11)],
        );
        // 黑方在 (7,9) 留空，四连并不连续，不应判胜。
        assert_eq!(game.place(7, 9), Ok(GameStatus::Ongoing));
    }

    #[test]
    fn undo_removes_last_move_and_restores_player() {
        let mut game = Game::new();
        game.place(7, 7).unwrap();
        game.place(8, 8).unwrap();
        assert!(game.undo());
        assert_eq!(game.board[8][8], None);
        assert_eq!(game.current_player(), Player::White);
        assert_eq!(game.history_len(), 1);
        assert!(game.undo());
        assert_eq!(game.board[7][7], None);
        assert_eq!(game.current_player(), Player::Black);
        assert_eq!(game.history_len(), 0);
    }

    #[test]
    fn undo_on_empty_history_returns_false() {
        let mut game = Game::new();
        assert!(!game.undo());
    }

    #[test]
    fn restart_clears_board_and_history() {
        let mut game = Game::new();
        game.place(7, 7).unwrap();
        game.place(8, 8).unwrap();
        game.restart();
        assert_eq!(game.current_player(), Player::Black);
        assert_eq!(game.history_len(), 0);
        assert_eq!(game.empty_cells().len(), BOARD_SIZE * BOARD_SIZE);
    }

    #[test]
    fn full_board_without_five_is_draw() {
        let mut game = Game::new();
        // 用无五连的二染色直接填满棋盘：Black 当 (row + 2*col) % 5 < 2。
        for row in 0..BOARD_SIZE {
            for col in 0..BOARD_SIZE {
                let player = if (row + 2 * col) % 5 < 2 {
                    Player::Black
                } else {
                    Player::White
                };
                game.board[row][col] = Some(player);
            }
        }
        assert!(game.is_full());
        assert!(!game.has_won(0, 0, Player::Black));
        assert!(!game.has_won(0, 0, Player::White));

        // 空出 (0,0) 后由白方落子，棋盘填满但无五连，应判和。
        game.board[0][0] = None;
        game.current = Player::White;
        assert_eq!(game.place(0, 0), Ok(GameStatus::Draw));
        assert!(game.is_full());
    }

    #[test]
    fn opponent_swaps_player() {
        assert_eq!(Player::Black.opponent(), Player::White);
        assert_eq!(Player::White.opponent(), Player::Black);
    }

    #[test]
    fn symbols_and_names_are_correct() {
        assert_eq!(Player::Black.symbol(), 'X');
        assert_eq!(Player::White.symbol(), 'O');
        assert_eq!(Player::Black.name_cn(), "黑方");
        assert_eq!(Player::White.name_cn(), "白方");
    }

    #[test]
    fn error_display_is_readable() {
        assert_eq!(GomokuError::OutOfBounds.to_string(), "坐标超出棋盘范围");
        assert_eq!(GomokuError::CellOccupied.to_string(), "该位置已有棋子");
    }

    #[test]
    fn best_move_returns_empty_cell_on_empty_board() {
        let game = Game::new();
        let (row, col) = best_move_for(game.board(), Player::Black).expect("空棋盘应有落子点");
        assert!(row < BOARD_SIZE && col < BOARD_SIZE);
        assert_eq!(game.board()[row][col], None);
    }

    #[test]
    fn best_move_returns_none_on_full_board() {
        let mut game = Game::new();
        // 直接用测试权限填满棋盘，避免依赖 120 步人工摆子。
        for row in 0..BOARD_SIZE {
            for col in 0..BOARD_SIZE {
                game.board[row][col] = Some(Player::Black);
            }
        }
        assert!(game.is_full());
        assert_eq!(best_move_for(game.board(), Player::Black), None);
    }

    #[test]
    fn best_move_blocks_immediate_opponent_win() {
        let mut game = Game::new();
        // 白方在 (7,7)..(7,10) 已有四连，左端被黑子挡住，
        // 只有 (7,11) 是白方下一步成五的点；黑方必须封堵这里。
        game.board[7][6] = Some(Player::Black);
        game.board[7][7] = Some(Player::White);
        game.board[7][8] = Some(Player::White);
        game.board[7][9] = Some(Player::White);
        game.board[7][10] = Some(Player::White);
        let (row, col) = best_move_for(game.board(), Player::Black).unwrap();
        assert_eq!((row, col), (7, 11));
    }

    #[test]
    fn has_won_detects_exactly_five_and_ignores_shorter() {
        let mut game = Game::new();
        // 前三步黑子不构成五连；补足白方闲子后黑方再落两子。
        game = place_many(game, &[(7, 7), (0, 0), (7, 8), (2, 2), (7, 9), (4, 4)]);
        assert!(!game.has_won(7, 9, Player::Black));

        assert_eq!(game.place(7, 10), Ok(GameStatus::Ongoing));
        assert!(!game.has_won(7, 10, Player::Black));

        assert_eq!(game.place(6, 6), Ok(GameStatus::Ongoing));
        assert_eq!(game.place(7, 11), Ok(GameStatus::Won(Player::Black)));
    }

    #[test]
    fn has_won_is_direction_agnostic() {
        let mut game = Game::new();
        game = place_many(
            game,
            &[
                (7, 7),
                (0, 0),
                (8, 8),
                (0, 1),
                (9, 9),
                (0, 2),
                (10, 10),
                (0, 3),
            ],
        );
        assert_eq!(game.place(11, 11), Ok(GameStatus::Won(Player::Black)));
    }

    #[test]
    fn score_cell_prefers_open_center_lines() {
        let game = Game::new();
        let center_score = score_cell(game.board(), 7, 7, Player::Black);
        let edge_score = score_cell(game.board(), 0, 0, Player::Black);
        assert!(center_score >= edge_score);
    }
}
