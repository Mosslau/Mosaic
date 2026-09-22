//! sol-01：练习 1 参考实现 —— 热点函数与被测对象（DUT）。
//!
//! 一个典型热点：把形如 `user:42` / `order:9001` 的记录 key 拆成「前缀 + 编号」。
//! 两种实现：
//!
//! - `split_key_ref`：`split_once(':')` 借用切片 + 数字解析，零分配；
//! - `split_key_owned`：先 `to_string()` 再拆（教学中故意低效的对照，模拟
//!   真实代码里「先把 &str 转 String 图省事」的写法）。
//!
//! 想换成你自己的热点函数时，保持 `fn split_key_ref(&str) -> Option<(..)>` 的
//! 函数形状与 bench 的调用方式即可——基准 crate 的骨架是通用的。

/// 借用实现：返回前缀切片与编号。
pub fn split_key_ref(key: &str) -> Option<(&str, u64)> {
    let (prefix, id) = key.split_once(':')?;
    let id: u64 = id.parse().ok()?;
    Some((prefix, id))
}

/// 复制实现：为教学对照刻意先 to_string 再拆（每次调用多一次堆分配）。
pub fn split_key_owned(key: &str) -> Option<(String, u64)> {
    let owned = key.to_owned();
    let (prefix, id) = owned.split_once(':')?;
    let id: u64 = id.parse().ok()?;
    Some((prefix.to_owned(), id))
}

/// 构造 n 条 `prefix:{i}` 样式的 key（prefix 在几个固定值里轮换）。
pub fn sample_keys(n: usize) -> Vec<String> {
    const PREFIXES: [&str; 4] = ["user", "order", "device", "session"];
    (0..n)
        .map(|i| format!("{}:{i}", PREFIXES[i % PREFIXES.len()]))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn both_implementations_agree() {
        let key = "user:42";
        assert_eq!(split_key_ref(key), Some(("user", 42)));
        assert_eq!(split_key_owned(key), Some(("user".to_owned(), 42)));
    }

    #[test]
    fn malformed_keys_are_none() {
        assert_eq!(split_key_ref("noseparator"), None);
        assert_eq!(split_key_ref("user:abc"), None);
        assert_eq!(split_key_owned("user:abc"), None);
    }
}
