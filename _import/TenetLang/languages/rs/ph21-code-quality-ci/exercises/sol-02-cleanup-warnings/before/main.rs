//! 治理前版本（sol-02 样例）——故意携带 clippy lint，仅作「清理 warnings」练习起点。
//!
//! 运行前提：这是**故意写差**的教学样例，不要在真实项目中使用；把它复制到
//! record-tool/src/main.rs（或独立 crate）后跑 `cargo clippy`，可复现以下 5 处 warning
//!（本机 cargo/clippy 1.92.0 实测，行号以副本为准）：
//!   the loop variable `i` is only used to index `records`  ×2  → style：needless_range_loop
//!   writing `&Vec` instead of `&[_]` ...                        → style：ptr_arg
//!   manual implementation of `Option::map`                       → style：manual_map
//!   this function has too many arguments (8/7)                   → complexity：too_many_arguments
//! 治理后参考实现：record-tool/src/main.rs（全绿）。
#![allow(dead_code)] // 样例聚焦 lint 治理，不关注死代码

#[derive(Debug, Clone)]
pub struct Record {
    pub key: String,
    pub value: Vec<u8>,
}

/// style：手写下标循环，只用来取 records[i] —— 应改迭代器
pub fn total_key_chars(records: &[Record]) -> usize {
    let mut total = 0;
    for i in 0..records.len() {
        total += records[i].key.chars().count();
    }
    total
}

/// style：参数写 &Vec —— 应写 &[T]（调用方无谓构造 Vec）
pub fn longest_key(records: &Vec<Record>) -> Option<&str> {
    let mut best: Option<&Record> = None;
    for i in 0..records.len() {
        match &best {
            None => best = Some(&records[i]),
            Some(cur) if records[i].key.len() > cur.key.len() => best = Some(&records[i]),
            Some(_) => {}
        }
    }
    best.map(|r| r.key.as_str())
}

/// style：手写 match 当 map —— 应 match 改 map
pub fn describe(r: &Record) -> Option<String> {
    match r.value.first() {
        Some(b) => Some(format!("first byte {b}")),
        None => None,
    }
}

/// complexity：8 个参数超阈值
pub fn merge_record(
    a_key: String,
    a_value: Vec<u8>,
    b_key: String,
    b_value: Vec<u8>,
    c_key: String,
    c_value: Vec<u8>,
    d_key: String,
    d_value: Vec<u8>,
) -> Vec<Record> {
    vec![
        Record { key: a_key, value: a_value },
        Record { key: b_key, value: b_value },
        Record { key: c_key, value: c_value },
        Record { key: d_key, value: d_value },
    ]
}

pub fn main() {
    let records = merge_record(
        String::from("a"),
        b"1".to_vec(),
        String::from("bb"),
        b"22".to_vec(),
        String::from("ccc"),
        b"333".to_vec(),
        String::from("d"),
        b"4".to_vec(),
    );
    println!("{}", total_key_chars(&records));
    println!("{:?}", longest_key(&records));
    println!("{:?}", describe(&records[0]));
}
