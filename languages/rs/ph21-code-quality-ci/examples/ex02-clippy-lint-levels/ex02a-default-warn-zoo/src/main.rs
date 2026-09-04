// ex02a 默认组动物园：本文件故意携带 style / complexity / perf 三组默认 lint。
//
// 文件头声明（教学性覆盖）：这是演示「裸 cargo clippy 不拦 warning」的治理前样本，
// 不要把它当可提交的质量门禁代码；治理后版本见 exercises/sol-02 与 project 的 demo-app。
//
// 本机实测（cargo/clippy 1.92.0）默认触发名单（分组归属用主文档 3.3 的「-A 逐组关」法核实）：
//   warning: the loop variable `i` is only used to index `scores`   → style 组（needless_range_loop）
//   warning: manual implementation of Option::map                   → style 组（manual_map）
//   warning: this function has too many arguments (8/7)             → complexity 组（too_many_arguments）
//   warning: manually copying between slices                        → perf 组（manual_memcpy）
// 裸跑 cargo clippy：warning 一堆但退出 0；加 -D warnings 后退出非零（门禁语义）。
use std::collections::HashMap;

// style：for i in 0..v.len() 只用来取 v[i]，应改迭代器（rust-patterns：迭代器优于手写循环）
fn sum_scores(scores: &[i32]) -> i32 {
    let mut total = 0;
    for i in 0..scores.len() {
        total += scores[i];
    }
    total
}

// style：手写 match 实现 Option::map，应直接 opt.map(...)
fn bump(opt: Option<u32>) -> Option<u32> {
    match opt {
        Some(v) => Some(v + 1),
        None => None,
    }
}

// complexity：8 个参数超过 too_many_arguments 阈值（默认 >7）——故意不治理，让它触发。
// 治理方向见 ex03：要么拆结构体、要么用带理由的 #[allow]（本文件演示「裸触发」）。
fn parse_row(
    id: u32,
    name: &str,
    active: bool,
    score: i32,
    city: &str,
    tags: &[&str],
    created: u64,
    note: &str,
) -> HashMap<&'static str, String> {
    let mut m = HashMap::new();
    m.insert("id", id.to_string());
    m.insert("name", name.to_string());
    m.insert("active", active.to_string());
    m.insert("score", score.to_string());
    m.insert("city", city.to_string());
    m.insert("tags", tags.join(","));
    m.insert("created", created.to_string());
    m.insert("note", note.to_string());
    m
}

// perf：手写循环逐字节复制切片，应 copy_from_slice
fn copy_prefix(dst: &mut [u8], src: &[u8]) {
    for i in 0..src.len() {
        dst[i] = src[i];
    }
}

fn main() {
    let scores = vec![1, 2, 3, 4, 5];
    println!("sum={}", sum_scores(&scores));
    println!("bump={:?}", bump(Some(1)));
    let row = parse_row(
        7,
        "alice",
        true,
        99,
        "tokyo",
        &["a", "b"],
        1_700_000_000,
        "hi",
    );
    println!("row={}", row.len());
    let mut dst = [0u8; 4];
    copy_prefix(&mut dst, &[1, 2, 3, 4]);
    println!("dst={dst:?}");
}
