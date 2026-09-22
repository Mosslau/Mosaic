// 参考实现：练习 3 —— clone / 索引快照 / 拆结构体 三种修复方式对比（可通过编译并运行）。
// 共同任务：在 Team 里找出最高分玩家，打印其名字，再把它的分数清零（读名字 + 改分数，
//           若用「持名借用」跨修改点会触发 E0502，见练习说明；这里给出三种避开冲突的修法）。
// 三种修法的取舍：
//  - clone：直观、一步到位，但每次复制多一次堆分配（String）；适合元素小、频率低、
//    或数据本来就要拥有化的边界（跨线程/跨 API）。
//  - 索引/短借用：零分配，把「先算下标、再借/改」拉开；代价是要求结构支持「拿到稳定下标
//    后再回来改」（Vec 在元素不变时下标稳定），读与写的位置因此被拉远。
//  - 拆结构体：把读写目标拆到不重叠的字段/容器上，借用检查器按字段放行；代价是数据结构
//    要为访问模式设计（平行数组），通常伴随一次较大的重构 —— 重构优先于 clone 的范例。
// 验证：rustc --edition 2021 sol-03-three-fixes.rs && ./sol-03-three-fixes（已验证：rustc 1.92.0 / macOS arm64）。

struct Player {
    name: String,
    score: u32,
}

struct Team {
    players: Vec<Player>,
}

/// 找最高分下标 —— 只返回 usize，函数内对 players 的借用随返回即收口。
fn top_idx(players: &[Player]) -> usize {
    players
        .iter()
        .enumerate()
        .max_by_key(|(_, p)| p.score)
        .map(|(i, _)| i)
        .unwrap_or(0)
}

// 修法 1：clone —— 先把名字复制成拥有值，再放心地改
fn reset_top_clone(team: &mut Team) {
    let idx = top_idx(&team.players);
    let name = team.players[idx].name.clone(); // 1 次堆分配，换来改数据的自由
    team.players[idx].score = 0; // 没有借用残留
    println!("[clone]   {name} 已清零");
}

// 修法 2：索引 + 短借用 —— 打印名字的借用只活在本语句，随后再改
fn reset_top_index(team: &mut Team) {
    let idx = top_idx(&team.players); // 只带回下标，不带借用
    println!("[index]   {} 已清零", team.players[idx].name); // 借用到此句结束
    team.players[idx].score = 0; // &mut 畅通
}

// 修法 3：拆结构体 —— 名字与分数放进两个平行容器，天然支持字段级分借
struct TeamSplit {
    names: Vec<String>,
    scores: Vec<u32>,
}

fn reset_top_split(team: &mut TeamSplit) {
    let idx = team
        .scores
        .iter()
        .enumerate()
        .max_by_key(|(_, s)| **s)
        .map(|(i, _)| i)
        .unwrap_or(0);
    println!("[split]   {} 已清零", team.names[idx]); // 只借 names 字段
    team.scores[idx] = 0; // 改 scores 字段：与上面借用不重叠
}

fn main() {
    // 修法 1 与 2 作用于同一结构
    let mut team = Team {
        players: vec![
            Player { name: "alice".into(), score: 30 },
            Player { name: "bob".into(), score: 90 },
            Player { name: "carol".into(), score: 60 },
        ],
    };
    reset_top_clone(&mut team);
    assert_eq!(team.players[1].score, 0);

    team.players[1].score = 90; // 恢复分数，演示下一种修法
    reset_top_index(&mut team);
    assert_eq!(team.players[1].score, 0);

    // 修法 3 需要先重构数据结构
    let mut split = TeamSplit {
        names: vec!["alice".into(), "bob".into(), "carol".into()],
        scores: vec![30, 90, 60],
    };
    reset_top_split(&mut split);
    assert_eq!(split.scores[1], 0);

    println!("三种修法都让最高分玩家清零，且原名字保持不变（clone 复制了名字、其余两种没复制）");
}
