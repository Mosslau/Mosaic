// exercises/sol-04-if-else-to-match.rs —— if-else 与 match 两种写法输出成绩等级
// 验证环境：rustc 1.92.0
// 编译：rustc sol-04-if-else-to-match.rs -o sol04
// 运行：./sol04
// 已验证：本环境编译零警告，两版本对 95/85/75/60 输出一致（A/B/C/F）

// if-else 链版本
fn grade_if(score: u32) -> char {
    if score >= 90 {
        'A'
    } else if score >= 80 {
        'B'
    } else if score >= 70 {
        'C'
    } else {
        'F'
    }
}

// match 版本：范围模式 + 穷尽检查
fn grade_match(score: u32) -> char {
    match score {
        90..=100 => 'A',
        80..=89 => 'B',
        70..=79 => 'C',
        _ => 'F',
    }
}

fn main() {
    for score in [95, 85, 75, 60] {
        let a = grade_if(score);
        let b = grade_match(score);
        // 断言两个版本一致
        assert_eq!(a, b);
        println!("score={}: if-else={}, match={}", score, a, b);
    }
}
