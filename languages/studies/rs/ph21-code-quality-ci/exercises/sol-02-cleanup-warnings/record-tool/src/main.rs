//! record-tool —— sol-02「清理 clippy warnings」的**治理后**参考实现（干净基线）。
//!
//! 对应治理前版本：`../../before/main.rs`（故意携带 style/complexity 组 lint，
//! 复制回 src/ 可在 `cargo clippy` 下复现 warning；治理内容逐条对照见 exercises/README 练习 2）。
//! 治理要点（与 rust-patterns 呼应）：
//!   - 手写下标循环 → 迭代器链（needless_range_loop / manual_memcpy 类）
//!   - 参数 `&Vec<T>` → `&[T]`（ptr_arg）
//!   - 生产路径无裸 unwrap（rust-patterns 反模式清单）

/// 一条迷你 WAL record（ph19 风格的简化教学结构）。
#[derive(Debug, Clone)]
pub struct Record {
    pub key: String,
    pub value: Vec<u8>,
}

/// 所有 key 的总长度。
pub fn total_key_chars(records: &[Record]) -> usize {
    records.iter().map(|r| r.key.chars().count()).sum()
}

/// 最长的 key；空输入返回 None。
pub fn longest_key(records: &[Record]) -> Option<&str> {
    records
        .iter()
        .map(|r| r.key.as_str())
        .max_by_key(|k| k.chars().count())
}

/// value 总字节数。
pub fn total_value_bytes(records: &[Record]) -> usize {
    records.iter().map(|r| r.value.len()).sum()
}

fn main() {
    let records = vec![
        Record {
            key: String::from("temperature"),
            value: b"36.5".to_vec(),
        },
        Record {
            key: String::from("humidity"),
            value: b"60".to_vec(),
        },
    ];
    println!("keys={}", total_key_chars(&records));
    println!("longest={:?}", longest_key(&records));
    println!("value_bytes={}", total_value_bytes(&records));
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<Record> {
        vec![
            Record {
                key: String::from("a"),
                value: b"1".to_vec(),
            },
            Record {
                key: String::from("bb"),
                value: b"22".to_vec(),
            },
        ]
    }

    #[test]
    fn total_key_chars_counts_all_keys() {
        assert_eq!(total_key_chars(&sample()), 3);
    }

    #[test]
    fn longest_key_returns_max_or_none() {
        assert_eq!(longest_key(&sample()), Some("bb"));
        assert_eq!(longest_key(&[]), None);
    }

    #[test]
    fn total_value_bytes_sums_values() {
        assert_eq!(total_value_bytes(&sample()), 3);
    }
}
