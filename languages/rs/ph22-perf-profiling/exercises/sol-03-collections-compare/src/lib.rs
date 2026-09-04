//! sol-03：容器比较的被测数据与三种容器操作。
//!
//! 统一负载：批量插入 `n` 个 `(key, value)`，再查找其中一半 key。
//! 三种容器各给一个执行函数，语义等价、结果一致：
//!
//! - Vec：push 后 `sort_unstable`，查找用 `binary_search`；
//! - BTreeMap：键有序，插入/查找均 O(log n)；
//! - HashMap：期望 O(1)，但散列有常数开销。
//!
//! 返回 `(命中数, 命中值的和)` 让黑盒有东西可吞。

/// 生成 n 个不重复的 `(key, value)` 对，key 形如 `k000001`。
pub fn sample_pairs(n: usize) -> Vec<(String, u64)> {
    (0..n)
        .map(|i| (format!("k{i:06}"), (i as u64).wrapping_mul(31)))
        .collect()
}

/// Vec 路径。
pub fn op_vec(pairs: &[(String, u64)]) -> (usize, u64) {
    let mut v: Vec<(String, u64)> = pairs.to_vec();
    v.sort_unstable_by(|a, b| a.0.cmp(&b.0));
    let mut hits = 0usize;
    let mut sum = 0u64;
    for (key, _) in pairs.iter().step_by(2) {
        if let Ok(idx) = v.binary_search_by(|(k, _)| k.as_str().cmp(key)) {
            hits += 1;
            sum = sum.wrapping_add(v[idx].1);
        }
    }
    (hits, sum)
}

/// BTreeMap 路径。
pub fn op_btree(pairs: &[(String, u64)]) -> (usize, u64) {
    let map: std::collections::BTreeMap<&str, u64> =
        pairs.iter().map(|(k, v)| (k.as_str(), *v)).collect();
    let mut hits = 0usize;
    let mut sum = 0u64;
    for (key, _) in pairs.iter().step_by(2) {
        if let Some(v) = map.get(key.as_str()) {
            hits += 1;
            sum = sum.wrapping_add(*v);
        }
    }
    (hits, sum)
}

/// HashMap 路径。
pub fn op_hashmap(pairs: &[(String, u64)]) -> (usize, u64) {
    let map: std::collections::HashMap<&str, u64> =
        pairs.iter().map(|(k, v)| (k.as_str(), *v)).collect();
    let mut hits = 0usize;
    let mut sum = 0u64;
    for (key, _) in pairs.iter().step_by(2) {
        if let Some(v) = map.get(key.as_str()) {
            hits += 1;
            sum = sum.wrapping_add(*v);
        }
    }
    (hits, sum)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn three_containers_agree() {
        let pairs = sample_pairs(10_000);
        let a = op_vec(&pairs);
        let b = op_btree(&pairs);
        let c = op_hashmap(&pairs);
        assert_eq!(a, b);
        assert_eq!(b, c);
        assert_eq!(a.0, 5_000, "step_by(2) 恰好命中一半");
    }
}
